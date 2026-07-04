mod audio;
mod cleaner;
mod config;
mod hotkeys;
mod inserter;
mod moonshine;

use std::{
    io::{self, Write},
    path::PathBuf,
    sync::mpsc,
    thread,
    time::Instant,
};

use anyhow::{Context, Result};
use clap::Parser;

use crate::{
    audio::Recorder,
    cleaner::OllamaCleaner,
    config::{AppConfig, Args},
    hotkeys::{HotkeyEvent, HotkeyListener},
    inserter::TextInserter,
    moonshine::MoonshineWorker,
};

fn main() -> Result<()> {
    let args = Args::parse();
    let config = AppConfig::from_args(args)?;

    log("Project Parrot Rust MVP is running.");
    log(&format!(
        "Hotkey: hold {}, speak, release Space to paste.",
        config.hotkey_label
    ));
    log(&format!(
        "Moonshine STT: {} ({})",
        config.mode,
        config.moonshine_model_dir.display()
    ));
    log(&format!("Ollama cleanup model: {}", config.ollama_model));
    log(&format!(
        "Ollama keep_alive: {}",
        config.ollama_keep_alive
    ));
    log("Live preview: raw Moonshine streaming transcript.");
    log("Final paste: strict local Qwen dictation formatting.");
    log("Quit: Ctrl+C or Ctrl+Alt+Q.");

    let started = Instant::now();
    log("Loading Moonshine model...");
    let moonshine = MoonshineWorker::start(&config).context("failed to start Moonshine STT")?;
    log(&format!(
        "Moonshine model ready in {:.1}s.",
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
                    moonshine.begin_utterance()?;
                    let (audio_tx, audio_rx) = mpsc::channel::<Vec<f32>>();
                    let sink = moonshine.audio_sink();
                    audio_forwarder = Some(thread::spawn(move || {
                        for samples in audio_rx {
                            if let Err(error) = sink.send_audio(&samples) {
                                log(&format!("Moonshine audio stream error: {error:#}"));
                                break;
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
                let raw = moonshine.end_utterance()?;
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
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}
