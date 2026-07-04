use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::Sender,
    Arc,
};

use anyhow::{Context, Result};
use rdev::{listen, Event, EventType, Key};

#[derive(Debug)]
pub enum HotkeyEvent {
    StartRecording,
    StopRecording,
    Quit,
}

pub struct HotkeyListener {
    _thread: std::thread::JoinHandle<()>,
}

impl HotkeyListener {
    pub fn start(tx: Sender<HotkeyEvent>) -> Result<Self> {
        let ctrl_down = Arc::new(AtomicBool::new(false));
        let alt_down = Arc::new(AtomicBool::new(false));
        let space_recording = Arc::new(AtomicBool::new(false));

        let thread_ctrl = Arc::clone(&ctrl_down);
        let thread_alt = Arc::clone(&alt_down);
        let thread_space = Arc::clone(&space_recording);

        let handle = std::thread::Builder::new()
            .name("parrot-hotkeys".to_string())
            .spawn(move || {
                let callback = move |event: Event| {
                    handle_event(event, &tx, &thread_ctrl, &thread_alt, &thread_space);
                };
                if let Err(error) = listen(callback) {
                    eprintln!("global keyboard listener failed: {error:?}");
                }
            })
            .context("failed to start hotkey listener")?;

        Ok(Self { _thread: handle })
    }
}

fn handle_event(
    event: Event,
    tx: &Sender<HotkeyEvent>,
    ctrl_down: &AtomicBool,
    alt_down: &AtomicBool,
    space_recording: &AtomicBool,
) {
    match event.event_type {
        EventType::KeyPress(key) => {
            set_modifier(key, true, ctrl_down, alt_down);

            if key == Key::Space
                && ctrl_down.load(Ordering::SeqCst)
                && !space_recording.swap(true, Ordering::SeqCst)
            {
                let _ = tx.send(HotkeyEvent::StartRecording);
            }

            if key == Key::KeyC && ctrl_down.load(Ordering::SeqCst) {
                let _ = tx.send(HotkeyEvent::Quit);
            }
            if key == Key::KeyQ
                && ctrl_down.load(Ordering::SeqCst)
                && alt_down.load(Ordering::SeqCst)
            {
                let _ = tx.send(HotkeyEvent::Quit);
            }
        }
        EventType::KeyRelease(key) => {
            if key == Key::Space && space_recording.swap(false, Ordering::SeqCst) {
                let _ = tx.send(HotkeyEvent::StopRecording);
            }
            set_modifier(key, false, ctrl_down, alt_down);
        }
        _ => {}
    }
}

fn set_modifier(key: Key, pressed: bool, ctrl_down: &AtomicBool, alt_down: &AtomicBool) {
    match key {
        Key::ControlLeft | Key::ControlRight => ctrl_down.store(pressed, Ordering::SeqCst),
        Key::Alt | Key::AltGr => alt_down.store(pressed, Ordering::SeqCst),
        _ => {}
    }
}
