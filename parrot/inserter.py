from __future__ import annotations

import time

import pyautogui
import pyperclip


class TextInserter:
    def __init__(self, restore_clipboard: bool, paste_delay_seconds: float) -> None:
        self.restore_clipboard = restore_clipboard
        self.paste_delay_seconds = paste_delay_seconds

    def paste(self, text: str) -> None:
        if not text.strip():
            return

        old_clipboard = None
        if self.restore_clipboard:
            try:
                old_clipboard = pyperclip.paste()
            except pyperclip.PyperclipException:
                old_clipboard = None

        pyperclip.copy(text)
        time.sleep(self.paste_delay_seconds)
        pyautogui.hotkey("ctrl", "v")

        if self.restore_clipboard and old_clipboard is not None:
            time.sleep(self.paste_delay_seconds)
            pyperclip.copy(old_clipboard)

