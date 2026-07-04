from __future__ import annotations

import argparse
from dataclasses import replace
import threading
import time

from pynput import keyboard

from .cleaner import CleanupError, OllamaCleaner
from .config import CONFIG
from .inserter import TextInserter
from .recorder import PushToTalkRecorder
from .status import log
from .transcriber import FasterWhisperTranscriber, TranscriptionError


class ParrotApp:
    def __init__(self, config=CONFIG) -> None:  # noqa: ANN001
        self.config = config
        self.recorder = PushToTalkRecorder(config.sample_rate, config.channels)
        self.transcriber = FasterWhisperTranscriber(
            config.whisper_model_name,
            config.whisper_device,
            config.whisper_compute_type,
        )
        self.cleaner = OllamaCleaner(config.ollama_model)
        self.inserter = TextInserter(config.restore_clipboard, config.paste_delay_seconds)
        self.transcription_lock = threading.Lock()
        self.ctrl_down = False
        self.alt_down = False
        self.space_down = False
        self.quit_down = False
        self.c_down = False
        self.processing = False
        self.live_preview_running = False
        self.stop_event = threading.Event()

    def run(self) -> None:
        log("Project Parrot MVP is running.")
        log(f"Hotkey: hold {self.config.hotkey_label}, speak, release Space to paste.")
        log(
            f"Whisper model: {self.config.whisper_model_name} "
            f"({self.config.whisper_device}, {self.config.whisper_compute_type})"
        )
        log(f"Ollama cleanup model: {self.config.ollama_model}")
        if self.config.live_preview_enabled:
            log(
                "Live preview: rough STT every "
                f"{self.config.live_stt_interval_seconds:.1f}s. "
                "Only final text is cleaned and pasted."
            )
        log("Quit: Ctrl+C or Ctrl+Alt+Q.")
        self._preload_models()

        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        listener.start()
        try:
            while not self.stop_event.wait(0.2):
                pass
        except KeyboardInterrupt:
            log("Ctrl+C received. Shutting down...")
        finally:
            if self.recorder.is_recording:
                self.recorder.stop_and_get_audio()
            listener.stop()
            log("Stopped.")

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
            self.ctrl_down = True
        elif key in {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r}:
            self.alt_down = True
        elif key == keyboard.Key.space:
            self.space_down = True
        elif _is_char_key(key, "q"):
            self.quit_down = True
        elif _is_char_key(key, "c"):
            self.c_down = True

        if self.ctrl_down and self.alt_down and self.quit_down:
            log("Quit hotkey received. Shutting down...")
            self.stop_event.set()
            return
        if self.ctrl_down and self.c_down:
            log("Ctrl+C hotkey received. Shutting down...")
            self.stop_event.set()
            return

        if self.ctrl_down and self.space_down and not self.recorder.is_recording and not self.processing:
            self.recorder.start()
            if self.config.live_preview_enabled:
                self.live_preview_running = True
                threading.Thread(target=self._live_preview_loop, daemon=True).start()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if key == keyboard.Key.space:
            self.space_down = False
            if self.recorder.is_recording:
                threading.Thread(target=self._finish_recording, daemon=True).start()
        elif key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
            self.ctrl_down = False
        elif key in {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r}:
            self.alt_down = False
        elif _is_char_key(key, "q"):
            self.quit_down = False
        elif _is_char_key(key, "c"):
            self.c_down = False

    def _finish_recording(self) -> None:
        self.live_preview_running = False
        self.processing = True
        try:
            audio, seconds = self.recorder.stop_and_get_audio()
            if audio is None or seconds < 0.25:
                return

            log("Transcribing...")
            with self.transcription_lock:
                transcript = self.transcriber.transcribe(audio)
            log(f"Raw: {transcript}")

            final_text = transcript
            if self.config.cleanup_enabled and transcript:
                log("Cleaning with Ollama...")
                final_text = self.cleaner.clean(transcript)
                log(f"Clean: {final_text}")

            if final_text:
                log("Pasting into focused app...")
                self.inserter.paste(final_text)
                log("Done.")
        except (TranscriptionError, CleanupError, OSError, RuntimeError) as exc:
            log(f"Error: {exc}")
        finally:
            time.sleep(0.1)
            self.processing = False

    def _live_preview_loop(self) -> None:
        last_transcript = ""

        while self.live_preview_running and self.recorder.is_recording and not self.stop_event.is_set():
            time.sleep(self.config.live_stt_interval_seconds)

            try:
                audio, seconds = self.recorder.get_snapshot()
                if seconds < self.config.live_min_audio_seconds:
                    continue
                if audio is None:
                    continue

                if not self.transcription_lock.acquire(blocking=False):
                    continue
                try:
                    transcript = self.transcriber.transcribe(audio)
                finally:
                    self.transcription_lock.release()

                transcript = transcript.strip()
                if not transcript or transcript == last_transcript:
                    continue

                last_transcript = transcript
                log(f"Live raw: {transcript}")
            except (TranscriptionError, CleanupError, OSError, RuntimeError) as exc:
                log(f"Live preview error: {exc}")
                time.sleep(0.5)

    def _preload_models(self) -> None:
        try:
            log("Loading Whisper model...")
            started = time.monotonic()
            self.transcriber.preload()
            elapsed = time.monotonic() - started
            log(f"Whisper model ready in {elapsed:.1f}s.")
        except TranscriptionError as exc:
            log(f"Whisper preload failed: {exc}")


def main() -> None:
    args = _parse_args()
    config = replace(CONFIG, whisper_model_name=args.model)
    ParrotApp(config).run()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project Parrot local dictation MVP")
    parser.add_argument(
        "--model",
        choices=("base.en", "small.en"),
        default=CONFIG.whisper_model_name,
        help="Whisper model to use. small.en is the default quality mode; base.en is faster.",
    )
    return parser.parse_args()


def _is_char_key(key: keyboard.Key | keyboard.KeyCode, char: str) -> bool:
    return isinstance(key, keyboard.KeyCode) and key.char is not None and key.char.lower() == char


if __name__ == "__main__":
    main()
