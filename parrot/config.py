from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class AppConfig:
    hotkey_label: str = "Ctrl+Space"
    sample_rate: int = 16_000
    channels: int = 1
    whisper_model_name: str = "small.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    ollama_model: str = "qwen2.5:1.5b"
    cleanup_enabled: bool = True
    live_preview_enabled: bool = True
    live_stt_interval_seconds: float = 0.4
    live_min_audio_seconds: float = 0.7
    restore_clipboard: bool = True
    paste_delay_seconds: float = 0.08

    @property
    def recordings_dir(self) -> Path:
        return ROOT_DIR / "recordings"


CONFIG = AppConfig()
