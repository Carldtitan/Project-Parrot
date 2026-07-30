mod audio;
mod cleaner;
mod config;
mod foreground;
mod hotkeys;
mod inserter;
mod stt_worker;
mod text_intelligence;

use std::{
    io::{self, BufRead, Write},
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, RecvTimeoutError},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

use anyhow::{Context, Result};
use clap::Parser;

use crate::{
    audio::Recorder,
    cleaner::OllamaCleaner,
    config::{AppConfig, Args},
    foreground::active_window_title,
    hotkeys::{HotkeyBindings, HotkeyEvent, HotkeyListener},
    inserter::TextInserter,
    stt_worker::SttWorker,
    text_intelligence::TextIntelligence,
};

const FINAL_CAPTURE_GRACE: Duration = Duration::from_millis(180);

fn main() -> Result<()> {
    let args = Args::parse();
    let config = AppConfig::from_args(args)?;

    log("Project Parrot is running.");
    log(&format!(
        "Shortcuts: push-to-talk {}, hands-free {}, cancel {}, paste last {}.",
        config.push_to_talk_shortcut,
        config.hands_free_shortcut,
        config.cancel_shortcut,
        config.paste_last_shortcut
    ));
    log(&format!("STT engine: {}", config.stt_engine));
    log(&format!("STT threads: {}", config.stt_threads));
    log(&format!("Ollama cleanup model: {}", config.ollama_model));
    log(&format!(
        "Live preview: every {:.1}s over a {:.1}s rolling window.",
        config.update_interval, config.live_window_seconds
    ));
    log(&format!(
        "Long sessions: warning at {}s, automatic finish at {}s.",
        config.session_warning_seconds, config.session_limit_seconds
    ));

    let started = Instant::now();
    log("Loading and warming STT model...");
    emit_status("starting", "Loading the local speech model...");
    let stt = SttWorker::start(&config).context("failed to start STT")?;
    log(&format!(
        "STT model ready in {:.1}s.",
        started.elapsed().as_secs_f32()
    ));

    let cleaner = OllamaCleaner::new(
        config.ollama_model.clone(),
        config.ollama_keep_alive.clone(),
    );
    let formatter_ready = start_formatter_warmup(cleaner.clone());
    let intelligence = TextIntelligence::from_path(config.personalization_path.as_deref());
    let inserter = TextInserter::new(config.restore_clipboard);
    let mut recorder =
        Recorder::new(config.sample_rate).context("failed to initialize recorder")?;
    let mut audio_forwarder: Option<thread::JoinHandle<()>> = None;
    let mut recording_started: Option<Instant> = None;
    let mut active_window = String::new();
    let mut warning_sent = false;
    let mut hands_free = false;
    let mut last_transcript = String::new();

    let bindings = HotkeyBindings::parse(
        &config.push_to_talk_shortcut,
        &config.hands_free_shortcut,
        &config.cancel_shortcut,
        &config.paste_last_shortcut,
    )?;
    let (tx, rx) = mpsc::channel();
    let _listener = HotkeyListener::start(tx.clone(), bindings)?;
    if config.control_stdin {
        start_control_listener(tx);
    }
    emit_mode(false);
    emit_status(
        "ready",
        &format!("Ready. Hold {} to dictate.", config.push_to_talk_shortcut),
    );

    loop {
        let event = match rx.recv_timeout(Duration::from_millis(250)) {
            Ok(event) => event,
            Err(RecvTimeoutError::Disconnected) => HotkeyEvent::Quit,
            Err(RecvTimeoutError::Timeout) => {
                let Some(session_started) = recording_started else {
                    continue;
                };
                let elapsed = session_started.elapsed().as_secs();
                if elapsed >= config.session_limit_seconds {
                    hands_free = false;
                    emit_mode(false);
                    log("Long-session limit reached; finishing automatically.");
                    HotkeyEvent::StopRecording
                } else {
                    if elapsed >= config.session_warning_seconds && !warning_sent {
                        warning_sent = true;
                        let remaining = config.session_limit_seconds.saturating_sub(elapsed);
                        emit_status(
                            "recording",
                            &format!(
                                "Long session — Parrot will finish safely in about {remaining} seconds."
                            ),
                        );
                    }
                    continue;
                }
            }
        };

        match event {
            HotkeyEvent::StartRecording => {
                if recorder.is_recording() {
                    continue;
                }
                active_window = active_window_title();
                recording_started = Some(start_recording(
                    &stt,
                    &mut recorder,
                    &config,
                    &mut audio_forwarder,
                    false,
                )?);
                warning_sent = false;
            }
            HotkeyEvent::ToggleHandsFree => {
                if recorder.is_recording() && hands_free {
                    hands_free = false;
                    emit_mode(false);
                    let result = finish_recording(
                        &stt,
                        &mut recorder,
                        &config,
                        &mut audio_forwarder,
                        &cleaner,
                        &formatter_ready,
                        &intelligence,
                        &inserter,
                        &active_window,
                    )?;
                    if let Some(text) = result {
                        last_transcript = text;
                    }
                    recording_started = None;
                } else if recorder.is_recording() {
                    hands_free = true;
                    emit_mode(true);
                    emit_status(
                        "recording",
                        &format!(
                            "Hands-free listening. Press {} again to finish.",
                            config.hands_free_shortcut
                        ),
                    );
                } else {
                    hands_free = true;
                    emit_mode(true);
                    active_window = active_window_title();
                    recording_started = Some(start_recording(
                        &stt,
                        &mut recorder,
                        &config,
                        &mut audio_forwarder,
                        true,
                    )?);
                    warning_sent = false;
                }
            }
            HotkeyEvent::StopRecording => {
                if !recorder.is_recording() || hands_free {
                    continue;
                }
                let result = finish_recording(
                    &stt,
                    &mut recorder,
                    &config,
                    &mut audio_forwarder,
                    &cleaner,
                    &formatter_ready,
                    &intelligence,
                    &inserter,
                    &active_window,
                )?;
                if let Some(text) = result {
                    last_transcript = text;
                }
                recording_started = None;
            }
            HotkeyEvent::Cancel => {
                hands_free = false;
                emit_mode(false);
                if recorder.is_recording() {
                    cancel_recording(&stt, &mut recorder, &mut audio_forwarder)?;
                }
                recording_started = None;
                warning_sent = false;
            }
            HotkeyEvent::PasteLast => {
                if last_transcript.is_empty() {
                    emit_status("ready", "There is no previous dictation to paste yet.");
                } else {
                    paste_recovered(&inserter, &last_transcript)?;
                }
            }
            HotkeyEvent::PasteText(text) => {
                let text = text.trim();
                if !text.is_empty() {
                    paste_recovered(&inserter, text)?;
                    last_transcript = text.to_string();
                }
            }
            HotkeyEvent::Quit => {
                if recorder.is_recording() {
                    let _ = recorder.stop();
                    let _ = stt.cancel_utterance();
                }
                if let Some(handle) = audio_forwarder.take() {
                    let _ = handle.join();
                }
                log("Stopped.");
                emit_status("stopped", "Dictation is stopped.");
                break;
            }
        }
    }

    Ok(())
}

fn start_recording(
    stt: &SttWorker,
    recorder: &mut Recorder,
    config: &AppConfig,
    audio_forwarder: &mut Option<thread::JoinHandle<()>>,
    hands_free: bool,
) -> Result<Instant> {
    stt.begin_utterance()?;
    let (audio_tx, audio_rx) = mpsc::sync_channel::<Vec<f32>>(2);
    let sink = stt.audio_sink();
    let live_send_interval = Duration::from_secs_f32(config.update_interval.max(0.25));
    *audio_forwarder = Some(thread::spawn(move || {
        let mut pending = Vec::new();
        let mut last_sent = Instant::now() - live_send_interval;
        for samples in audio_rx {
            pending.extend_from_slice(&samples);
            if last_sent.elapsed() >= live_send_interval {
                if let Err(error) = sink.send_audio(&pending) {
                    log(&format!("STT audio stream error: {error:#}"));
                    break;
                }
                pending.clear();
                last_sent = Instant::now();
            }
        }
        if !pending.is_empty() {
            let _ = sink.send_audio(&pending);
        }
    }));
    recorder.start_with_sender(audio_tx)?;
    log(if hands_free {
        "Hands-free recording started."
    } else {
        "Push-to-talk recording started."
    });
    let message = if hands_free {
        format!(
            "Hands-free listening. Press {} again to finish.",
            config.hands_free_shortcut
        )
    } else {
        "Listening. Release the shortcut to finish.".to_string()
    };
    emit_status("recording", &message);
    Ok(Instant::now())
}

#[allow(clippy::too_many_arguments)]
fn finish_recording(
    stt: &SttWorker,
    recorder: &mut Recorder,
    config: &AppConfig,
    audio_forwarder: &mut Option<thread::JoinHandle<()>>,
    cleaner: &OllamaCleaner,
    formatter_ready: &AtomicBool,
    intelligence: &TextIntelligence,
    inserter: &TextInserter,
    active_window: &str,
) -> Result<Option<String>> {
    // Key-up can arrive while the microphone driver still has the final
    // phoneme in flight. Keep the stream open briefly so the last word is not
    // clipped before the full-utterance recognition pass.
    thread::sleep(FINAL_CAPTURE_GRACE);
    let audio = recorder.stop()?;
    if let Some(handle) = audio_forwarder.take() {
        let _ = handle.join();
    }
    let seconds = audio.len() as f32 / config.sample_rate as f32;
    log(&format!("Captured {:.1}s audio.", seconds));

    if seconds < 0.25 {
        let _ = stt.cancel_utterance();
        log("No useful audio captured.");
        emit_partial("");
        emit_status("ready", "No speech detected. Ready to try again.");
        return Ok(None);
    }

    emit_status("processing", "Transcribing locally...");
    let stt_started = Instant::now();
    let raw = stt.end_utterance(&audio)?;
    log(&format!(
        "Final raw ({:.1}s): {}",
        stt_started.elapsed().as_secs_f32(),
        raw
    ));
    if raw.trim().is_empty() {
        log("No transcript returned.");
        emit_partial("");
        emit_status("ready", "No speech detected. Ready to try again.");
        return Ok(None);
    }

    let text = process_final_text(
        cleaner,
        inserter,
        intelligence,
        &raw,
        active_window,
        seconds,
        formatter_ready,
    )?;
    Ok(Some(text))
}

fn cancel_recording(
    stt: &SttWorker,
    recorder: &mut Recorder,
    audio_forwarder: &mut Option<thread::JoinHandle<()>>,
) -> Result<()> {
    let _ = recorder.stop()?;
    if let Some(handle) = audio_forwarder.take() {
        let _ = handle.join();
    }
    stt.cancel_utterance()?;
    emit_partial("");
    log("Dictation cancelled.");
    emit_status("ready", "Cancelled. Nothing was pasted.");
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn process_final_text(
    cleaner: &OllamaCleaner,
    inserter: &TextInserter,
    intelligence: &TextIntelligence,
    raw: &str,
    active_window: &str,
    duration_seconds: f32,
    formatter_ready: &AtomicBool,
) -> Result<String> {
    let prepared = intelligence.prepare(raw, active_window);
    let clean = if prepared.is_snippet {
        log("Expanded a local voice snippet.");
        prepared.text
    } else if formatter_ready.load(Ordering::SeqCst) {
        let clean_started = Instant::now();
        log("Formatting locally...");
        emit_status("formatting", "Cleaning and formatting locally...");
        let clean = cleaner
            .clean(&prepared.text, active_window, prepared.developer_context)
            .unwrap_or_else(|error| {
                formatter_ready.store(false, Ordering::SeqCst);
                log(&format!(
                    "Formatting failed, using deterministic cleanup: {error:#}"
                ));
                emit_formatter(
                    "unavailable",
                    "The optional formatter is unavailable. Local cleanup is still active.",
                );
                prepared.text.clone()
            });
        log(&format!(
            "Formatted ({:.1}s): {}",
            clean_started.elapsed().as_secs_f32(),
            clean
        ));
        clean
    } else {
        log("Optional formatter is unavailable; using deterministic local cleanup.");
        prepared.text
    };
    let clean = intelligence.finalize(&clean);

    log("Pasting into focused app...");
    emit_status("pasting", "Pasting into the focused app...");
    emit_final(&clean, duration_seconds, prepared.developer_context);
    inserter.paste(&clean)?;
    log("Done.");
    emit_status(
        "ready",
        "Done. Your previous dictation is ready to recover.",
    );
    Ok(clean)
}

fn paste_recovered(inserter: &TextInserter, text: &str) -> Result<()> {
    log("Pasting recovered dictation...");
    emit_status("pasting", "Pasting the previous dictation...");
    inserter.paste(text)?;
    emit_repaste(text);
    emit_status("ready", "Previous dictation pasted.");
    Ok(())
}

fn start_formatter_warmup(cleaner: OllamaCleaner) -> Arc<AtomicBool> {
    let ready = Arc::new(AtomicBool::new(false));
    let thread_ready = Arc::clone(&ready);
    thread::Builder::new()
        .name("parrot-formatter-warmup".to_string())
        .spawn(move || {
            let started = Instant::now();
            log("Warming the optional local formatter...");
            emit_formatter(
                "warming",
                "The optional local formatter is warming in the background.",
            );
            match cleaner.warmup() {
                Ok(()) => {
                    thread_ready.store(true, Ordering::SeqCst);
                    let message = format!(
                        "Local formatter ready in {:.1}s.",
                        started.elapsed().as_secs_f32()
                    );
                    log(&message);
                    emit_formatter("ready", &message);
                }
                Err(error) => {
                    let message = format!(
                        "Optional formatter unavailable; deterministic cleanup is active: {error:#}"
                    );
                    log(&message);
                    emit_formatter("unavailable", &message);
                }
            }
        })
        .ok();
    ready
}

fn start_control_listener(tx: mpsc::Sender<HotkeyEvent>) {
    thread::Builder::new()
        .name("parrot-control".to_string())
        .spawn(move || {
            let stdin = io::stdin();
            for line in stdin.lock().lines().map_while(|line| line.ok()) {
                let trimmed = line.trim();
                let event = if trimmed.eq_ignore_ascii_case("quit") {
                    Some(HotkeyEvent::Quit)
                } else {
                    serde_json::from_str::<serde_json::Value>(trimmed)
                        .ok()
                        .and_then(|message| match message["type"].as_str()? {
                            "quit" => Some(HotkeyEvent::Quit),
                            "toggle-hands-free" => Some(HotkeyEvent::ToggleHandsFree),
                            "cancel" => Some(HotkeyEvent::Cancel),
                            "paste-last" => Some(HotkeyEvent::PasteLast),
                            "paste" => Some(HotkeyEvent::PasteText(
                                message["text"].as_str().unwrap_or_default().to_string(),
                            )),
                            _ => None,
                        })
                };
                if let Some(event) = event {
                    let quitting = matches!(event, HotkeyEvent::Quit);
                    let _ = tx.send(event);
                    if quitting {
                        break;
                    }
                }
            }
        })
        .ok();
}

pub fn emit_status(state: &str, message: &str) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "status",
            "state": state,
            "message": message,
        })
    );
    let _ = io::stdout().flush();
}

pub fn emit_partial(text: &str) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "partial",
            "text": text,
        })
    );
    let _ = io::stdout().flush();
}

pub fn emit_final(text: &str, duration_seconds: f32, developer_context: bool) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "final",
            "text": text,
            "durationSeconds": duration_seconds,
            "developerContext": developer_context,
        })
    );
    let _ = io::stdout().flush();
}

pub fn emit_repaste(text: &str) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "repaste",
            "text": text,
        })
    );
    let _ = io::stdout().flush();
}

pub fn emit_mode(hands_free: bool) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "mode",
            "handsFree": hands_free,
        })
    );
    let _ = io::stdout().flush();
}

pub fn emit_formatter(state: &str, message: &str) {
    println!(
        "PARROT_EVENT {}",
        serde_json::json!({
            "type": "formatter",
            "state": state,
            "message": message,
        })
    );
    let _ = io::stdout().flush();
}

pub fn log(message: &str) {
    let now = chrono_like_time();
    println!("[{now}] {message}");
    let _ = io::stdout().flush();
}

fn chrono_like_time() -> String {
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let local = now % 86_400;
    let hour = local / 3600;
    let minute = (local % 3600) / 60;
    let second = local % 60;
    format!("{hour:02}:{minute:02}:{second:02}")
}

pub fn workspace_root() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            if dir.join("scripts").exists() || dir.join("bin").exists() {
                return dir.to_path_buf();
            }
        }
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
