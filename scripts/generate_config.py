#!/usr/bin/env python3
"""Generate a Parrot configuration file with customizable settings."""

import json
import sys
from pathlib import Path

DEFAULT_CONFIG = {
    "push_to_talk_shortcut": "Ctrl+Space",
    "hands_free_shortcut": "Ctrl+Alt+Space",
    "cancel_shortcut": "Ctrl+Alt+Escape",
    "paste_last_shortcut": "Ctrl+Alt+V",
    "stt_engine": "Parakeet",
    "stt_threads": 4,
    "ollama_model": "qwen2.5",
    "ollama_keep_alive": "-1m",
    "update_interval": 0.5,
    "live_window_seconds": 5.0,
    "session_warning_seconds": 300,
    "session_limit_seconds": 600,
    "sample_rate": 16000,
    "restore_clipboard": True,
    "control_stdin": False,
}

def main():
    output_path = Path.home() / "parrot_config.json"

    print("🐦 Parrot Configuration Generator")
    print("=" * 50)
    print(f"\nThis will create: {output_path}\n")

    config = DEFAULT_CONFIG.copy()

    # Hotkey customization
    print("Hotkeys (press Enter to keep default):")
    ptt = input(f"  Push-to-talk [{config['push_to_talk_shortcut']}]: ").strip()
    if ptt:
        config['push_to_talk_shortcut'] = ptt

    hf = input(f"  Hands-free [{config['hands_free_shortcut']}]: ").strip()
    if hf:
        config['hands_free_shortcut'] = hf

    cancel = input(f"  Cancel [{config['cancel_shortcut']}]: ").strip()
    if cancel:
        config['cancel_shortcut'] = cancel

    paste = input(f"  Paste last [{config['paste_last_shortcut']}]: ").strip()
    if paste:
        config['paste_last_shortcut'] = paste

    # STT configuration
    print(f"\nSTT threads [{config['stt_threads']}]: ", end="")
    try:
        threads = int(input().strip() or config['stt_threads'])
        config['stt_threads'] = max(1, min(16, threads))
    except ValueError:
        pass

    # Save config
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Config saved to: {output_path}")
    print("\nTo use this config, run Parrot with:")
    print(f"  project-parrot --personalization-path {output_path}")

if __name__ == "__main__":
    main()
