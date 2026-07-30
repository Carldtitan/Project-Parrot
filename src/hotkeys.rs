use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc::Sender,
    Arc,
};

use anyhow::{bail, Context, Result};
use rdev::{listen, Button, Event, EventType, Key};

#[derive(Debug)]
pub enum HotkeyEvent {
    StartRecording,
    StopRecording,
    ToggleHandsFree,
    Cancel,
    PasteLast,
    PasteText(String),
    Quit,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Trigger {
    Key(Key),
    Mouse(Button),
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Binding {
    ctrl: bool,
    alt: bool,
    shift: bool,
    meta: bool,
    trigger: Trigger,
}

#[derive(Clone)]
pub struct HotkeyBindings {
    push_to_talk: Binding,
    hands_free: Binding,
    cancel: Binding,
    paste_last: Binding,
}

impl HotkeyBindings {
    pub fn parse(
        push_to_talk: &str,
        hands_free: &str,
        cancel: &str,
        paste_last: &str,
    ) -> Result<Self> {
        Ok(Self {
            push_to_talk: Binding::parse(push_to_talk).context("invalid push-to-talk shortcut")?,
            hands_free: Binding::parse(hands_free).context("invalid hands-free shortcut")?,
            cancel: Binding::parse(cancel).context("invalid cancel shortcut")?,
            paste_last: Binding::parse(paste_last).context("invalid paste-last shortcut")?,
        })
    }
}

impl Binding {
    fn parse(label: &str) -> Result<Self> {
        let mut ctrl = false;
        let mut alt = false;
        let mut shift = false;
        let mut meta = false;
        let mut trigger = None;

        for part in label
            .split('+')
            .map(str::trim)
            .filter(|part| !part.is_empty())
        {
            match part.to_ascii_lowercase().as_str() {
                "ctrl" | "control" => ctrl = true,
                "alt" => alt = true,
                "shift" => shift = true,
                "win" | "meta" | "super" => meta = true,
                "mouse4" => trigger = Some(Trigger::Mouse(Button::Unknown(1))),
                "mouse5" => trigger = Some(Trigger::Mouse(Button::Unknown(2))),
                value => {
                    if trigger.is_some() {
                        bail!("shortcut has more than one trigger");
                    }
                    trigger = Some(Trigger::Key(parse_key(value)?));
                }
            }
        }

        Ok(Self {
            ctrl,
            alt,
            shift,
            meta,
            trigger: trigger.ok_or_else(|| anyhow::anyhow!("shortcut has no trigger"))?,
        })
    }
}

fn parse_key(value: &str) -> Result<Key> {
    let key = match value {
        "space" => Key::Space,
        "escape" | "esc" => Key::Escape,
        "f1" => Key::F1,
        "f2" => Key::F2,
        "f3" => Key::F3,
        "f4" => Key::F4,
        "f5" => Key::F5,
        "f6" => Key::F6,
        "f7" => Key::F7,
        "f8" => Key::F8,
        "f9" => Key::F9,
        "f10" => Key::F10,
        "f11" => Key::F11,
        "f12" => Key::F12,
        "a" => Key::KeyA,
        "b" => Key::KeyB,
        "c" => Key::KeyC,
        "d" => Key::KeyD,
        "e" => Key::KeyE,
        "f" => Key::KeyF,
        "g" => Key::KeyG,
        "h" => Key::KeyH,
        "i" => Key::KeyI,
        "j" => Key::KeyJ,
        "k" => Key::KeyK,
        "l" => Key::KeyL,
        "m" => Key::KeyM,
        "n" => Key::KeyN,
        "o" => Key::KeyO,
        "p" => Key::KeyP,
        "q" => Key::KeyQ,
        "r" => Key::KeyR,
        "s" => Key::KeyS,
        "t" => Key::KeyT,
        "u" => Key::KeyU,
        "v" => Key::KeyV,
        "w" => Key::KeyW,
        "x" => Key::KeyX,
        "y" => Key::KeyY,
        "z" => Key::KeyZ,
        _ => bail!("unsupported shortcut key: {value}"),
    };
    Ok(key)
}

#[derive(Default)]
struct Modifiers {
    ctrl: AtomicBool,
    alt: AtomicBool,
    shift: AtomicBool,
    meta: AtomicBool,
}

impl Modifiers {
    fn update(&self, key: Key, pressed: bool) {
        let target = match key {
            Key::ControlLeft | Key::ControlRight => Some(&self.ctrl),
            Key::Alt | Key::AltGr => Some(&self.alt),
            Key::ShiftLeft | Key::ShiftRight => Some(&self.shift),
            Key::MetaLeft | Key::MetaRight => Some(&self.meta),
            _ => None,
        };
        if let Some(target) = target {
            target.store(pressed, Ordering::SeqCst);
        }
    }

    fn matches(&self, binding: &Binding) -> bool {
        self.ctrl.load(Ordering::SeqCst) == binding.ctrl
            && self.alt.load(Ordering::SeqCst) == binding.alt
            && self.shift.load(Ordering::SeqCst) == binding.shift
            && self.meta.load(Ordering::SeqCst) == binding.meta
    }
}

pub struct HotkeyListener {
    _thread: std::thread::JoinHandle<()>,
}

impl HotkeyListener {
    pub fn start(tx: Sender<HotkeyEvent>, bindings: HotkeyBindings) -> Result<Self> {
        let modifiers = Arc::new(Modifiers::default());
        let push_active = Arc::new(AtomicBool::new(false));
        let hands_active = Arc::new(AtomicBool::new(false));
        let cancel_active = Arc::new(AtomicBool::new(false));
        let paste_active = Arc::new(AtomicBool::new(false));

        let handle = std::thread::Builder::new()
            .name("parrot-hotkeys".to_string())
            .spawn(move || {
                let callback = move |event: Event| {
                    handle_event(
                        event,
                        &tx,
                        &bindings,
                        &modifiers,
                        &push_active,
                        &hands_active,
                        &cancel_active,
                        &paste_active,
                    );
                };
                if let Err(error) = listen(callback) {
                    eprintln!("global keyboard listener failed: {error:?}");
                }
            })
            .context("failed to start hotkey listener")?;

        Ok(Self { _thread: handle })
    }
}

#[allow(clippy::too_many_arguments)]
fn handle_event(
    event: Event,
    tx: &Sender<HotkeyEvent>,
    bindings: &HotkeyBindings,
    modifiers: &Modifiers,
    push_active: &AtomicBool,
    hands_active: &AtomicBool,
    cancel_active: &AtomicBool,
    paste_active: &AtomicBool,
) {
    match event.event_type {
        EventType::KeyPress(key) => {
            modifiers.update(key, true);
            handle_press(
                &Trigger::Key(key),
                tx,
                bindings,
                modifiers,
                push_active,
                hands_active,
                cancel_active,
                paste_active,
            );
        }
        EventType::KeyRelease(key) => {
            handle_release(
                &Trigger::Key(key),
                tx,
                bindings,
                push_active,
                hands_active,
                cancel_active,
                paste_active,
            );
            if is_modifier(key) && push_active.swap(false, Ordering::SeqCst) {
                let _ = tx.send(HotkeyEvent::StopRecording);
            }
            modifiers.update(key, false);
        }
        EventType::ButtonPress(button) => handle_press(
            &Trigger::Mouse(button),
            tx,
            bindings,
            modifiers,
            push_active,
            hands_active,
            cancel_active,
            paste_active,
        ),
        EventType::ButtonRelease(button) => handle_release(
            &Trigger::Mouse(button),
            tx,
            bindings,
            push_active,
            hands_active,
            cancel_active,
            paste_active,
        ),
        _ => {}
    }
}

#[allow(clippy::too_many_arguments)]
fn handle_press(
    trigger: &Trigger,
    tx: &Sender<HotkeyEvent>,
    bindings: &HotkeyBindings,
    modifiers: &Modifiers,
    push_active: &AtomicBool,
    hands_active: &AtomicBool,
    cancel_active: &AtomicBool,
    paste_active: &AtomicBool,
) {
    if trigger == &bindings.push_to_talk.trigger
        && modifiers.matches(&bindings.push_to_talk)
        && !push_active.swap(true, Ordering::SeqCst)
    {
        let _ = tx.send(HotkeyEvent::StartRecording);
    } else if trigger == &bindings.hands_free.trigger
        && modifiers.matches(&bindings.hands_free)
        && !hands_active.swap(true, Ordering::SeqCst)
    {
        let _ = tx.send(HotkeyEvent::ToggleHandsFree);
    } else if trigger == &bindings.cancel.trigger
        && modifiers.matches(&bindings.cancel)
        && !cancel_active.swap(true, Ordering::SeqCst)
    {
        let _ = tx.send(HotkeyEvent::Cancel);
    } else if trigger == &bindings.paste_last.trigger
        && modifiers.matches(&bindings.paste_last)
        && !paste_active.swap(true, Ordering::SeqCst)
    {
        let _ = tx.send(HotkeyEvent::PasteLast);
    }
}

fn handle_release(
    trigger: &Trigger,
    tx: &Sender<HotkeyEvent>,
    bindings: &HotkeyBindings,
    push_active: &AtomicBool,
    hands_active: &AtomicBool,
    cancel_active: &AtomicBool,
    paste_active: &AtomicBool,
) {
    if trigger == &bindings.push_to_talk.trigger && push_active.swap(false, Ordering::SeqCst) {
        let _ = tx.send(HotkeyEvent::StopRecording);
    }
    if trigger == &bindings.hands_free.trigger {
        hands_active.store(false, Ordering::SeqCst);
    }
    if trigger == &bindings.cancel.trigger {
        cancel_active.store(false, Ordering::SeqCst);
    }
    if trigger == &bindings.paste_last.trigger {
        paste_active.store(false, Ordering::SeqCst);
    }
}

fn is_modifier(key: Key) -> bool {
    matches!(
        key,
        Key::ControlLeft
            | Key::ControlRight
            | Key::Alt
            | Key::AltGr
            | Key::ShiftLeft
            | Key::ShiftRight
            | Key::MetaLeft
            | Key::MetaRight
    )
}

#[cfg(test)]
mod tests {
    use super::{Binding, HotkeyBindings, Trigger};
    use rdev::{Button, Key};

    #[test]
    fn parses_keyboard_and_mouse_shortcuts() {
        let keyboard = Binding::parse("Ctrl+Alt+V").expect("keyboard shortcut should parse");
        assert!(keyboard.ctrl);
        assert!(keyboard.alt);
        assert_eq!(keyboard.trigger, Trigger::Key(Key::KeyV));

        let mouse = Binding::parse("Mouse5").expect("mouse shortcut should parse");
        assert_eq!(mouse.trigger, Trigger::Mouse(Button::Unknown(2)));
    }

    #[test]
    fn parses_the_full_action_set() {
        HotkeyBindings::parse("Ctrl+Space", "Ctrl+Alt+Space", "Ctrl+Alt+Escape", "F10")
            .expect("all supported actions should parse");
    }
}
