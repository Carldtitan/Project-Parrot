use std::{thread, time::Duration};

use anyhow::{Context, Result};
use arboard::Clipboard;
use rdev::{simulate, EventType, Key};

#[derive(Clone)]
pub struct TextInserter {
    restore_clipboard: bool,
}

impl TextInserter {
    pub fn new(restore_clipboard: bool) -> Self {
        Self { restore_clipboard }
    }

    pub fn paste(&self, text: &str) -> Result<()> {
        let mut clipboard = Clipboard::new().context("failed to open clipboard")?;
        let old_clipboard = if self.restore_clipboard {
            clipboard.get_text().ok()
        } else {
            None
        };

        clipboard
            .set_text(text.to_string())
            .context("failed to set clipboard text")?;
        thread::sleep(Duration::from_millis(80));
        send_ctrl_v()?;

        if let Some(old_clipboard) = old_clipboard {
            thread::sleep(Duration::from_millis(80));
            let _ = clipboard.set_text(old_clipboard);
        }
        Ok(())
    }
}

fn send_ctrl_v() -> Result<()> {
    simulate(&EventType::KeyPress(Key::ControlLeft))
        .map_err(|_| anyhow::anyhow!("failed to press Ctrl"))?;
    simulate(&EventType::KeyPress(Key::KeyV)).map_err(|_| anyhow::anyhow!("failed to press V"))?;
    simulate(&EventType::KeyRelease(Key::KeyV))
        .map_err(|_| anyhow::anyhow!("failed to release V"))?;
    simulate(&EventType::KeyRelease(Key::ControlLeft))
        .map_err(|_| anyhow::anyhow!("failed to release Ctrl"))?;
    Ok(())
}
