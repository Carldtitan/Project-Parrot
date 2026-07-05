mod audio;
mod cleaner;
mod config;
mod hotkeys;
mod inserter;
mod stt_worker;

use std::{
    io::{self, Write},
    path::PathBuf,
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};

use anyhow::{Context, Result};
use clap::Parser;

use crate::{
    audio::Recorder,
    cleaner::OllamaCleaner,
    config::{AppConfig, Args},
    hotkeys::{HotkeyEvent, HotkeyListener},
    inserter::TextInserter,
    stt_worker::SttWorker,
};

fn main() -> Result<()> {
    let args = Args::parse();
    let config = AppConfig::from_args(args)?;

    log("Project Parrot Rust MVP is running.");
    log(&format!(
        "Hotkey: hold {}, speak, release Space to paste.",
        config.hotkey_label
    ));
    log(&format!("STT engine: {}", config.stt_engine));
    log(&format!("STT threads: {}", config.stt_threads));
    log(&format!("Ollama cleanup model: {}", config.ollama_model));
    log(&format!(
        "Ollama keep_alive: {}",
        config.ollama_keep_alive
    ));
    log(&format!(
        "Live preview: rolling raw STT every {:.1}s over {:.1}s window.",
        config.update_interval,
        config.live_window_seconds
    ));
    log("Final paste: strict local Qwen dictation formatting.");
    log("Quit: Ctrl+C or Ctrl+Alt+Q.");

    let started = Instant::now();
    log("Loading and warming STT model...");
    let stt = SttWorker::start(&config).context("failed to start STT")?;
    log(&format!(
        "STT model ready in {:.1}s.",
        started.elapsed().as_secs_f32()
    ));

    let cleaner = OllamaCleaner::new(
        config.ollama_model.clone(),
        config.ollama_keep_alive.clone(),
    );
    let qwen_started = Instant::now();
    log("Warming Qwen formatter...");
    match cleaner.warmup() {
        Ok(()) => log(&format!(
            "Qwen formatter ready in {:.1}s.",
            qwen_started.elapsed().as_secs_f32()
        )),
        Err(error) => log(&format!(
            "Qwen warmup failed; cleanup may be slow: {error:#}"
        )),
    }
    let inserter = TextInserter::new(config.restore_clipboard);
    let mut recorder =
        Recorder::new(config.sample_rate).context("failed to initialize recorder")?;
    let mut audio_forwarder: Option<thread::JoinHandle<()>> = None;
    let (tx, rx) = mpsc::channel();
    let _listener = HotkeyListener::start(tx)?;

    for event in rx {
        match event {
            HotkeyEvent::StartRecording => {
                if !recorder.is_recording() {
                    stt.begin_utterance()?;
                    let (audio_tx, audio_rx) = mpsc::sync_channel::<Vec<f32>>(2);
                    let sink = stt.audio_sink();
                    let live_send_interval =
                        Duration::from_secs_f32(config.update_interval.max(0.25));
                    audio_forwarder = Some(thread::spawn(move || {
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
                    }));
                    recorder.start_with_sender(audio_tx)?;
                    log("Recording...");
                }
            }
            HotkeyEvent::StopRecording => {
                if !recorder.is_recording() {
                    continue;
                }
                let audio = recorder.stop()?;
                if let Some(handle) = audio_forwarder.take() {
                    let _ = handle.join();
                }
                let seconds = audio.len() as f32 / config.sample_rate as f32;
                log(&format!("Captured {:.1}s audio.", seconds));

                if seconds < 0.25 {
                    log("No useful audio captured.");
                    continue;
                }

                let stt_started = Instant::now();
                let raw = stt.end_utterance(&audio)?;
                log(&format!(
                    "Final raw ({:.1}s): {}",
                    stt_started.elapsed().as_secs_f32(),
                    raw
                ));
                if raw.trim().is_empty() {
                    log("No transcript returned.");
                    continue;
                }
                process_final_text(&cleaner, &inserter, &raw)?;
            }
            HotkeyEvent::Quit => {
                if recorder.is_recording() {
                    let _ = recorder.stop();
                }
                if let Some(handle) = audio_forwarder.take() {
                    let _ = handle.join();
                }
                log("Stopped.");
                break;
            }
        }
    }

    Ok(())
}

fn process_final_text(
    cleaner: &OllamaCleaner,
    inserter: &TextInserter,
    raw: &str,
) -> Result<()> {
    let clean_started = Instant::now();
    log("Formatting with strict local Qwen...");
    let clean = cleaner.clean(&raw).unwrap_or_else(|error| {
        log(&format!("Formatting failed, using raw transcript: {error:#}"));
        raw.to_string()
    });
    log(&format!(
        "Formatted ({:.1}s): {}",
        clean_started.elapsed().as_secs_f32(),
        clean
    ));

    log("Pasting into focused app...");
    inserter.paste(clean.trim())?;
    log("Done.");
    Ok(())
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
