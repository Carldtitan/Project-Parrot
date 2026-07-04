from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd

from .status import log


class PushToTalkRecorder:
    def __init__(self, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._on_audio,
            )
            self._stream.start()
            self._recording = True
            log("Recording...")

    def stop_and_get_audio(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            if not self._recording:
                return None, 0.0

            stream = self._stream
            self._stream = None
            self._recording = False
            audio = self._audio_from_frames_locked()

        if stream is not None:
            stream.stop()
            stream.close()

        if audio is None or audio.size == 0:
            log("No audio captured.")
            return None, 0.0

        seconds = audio.shape[0] / self.sample_rate
        log(f"Captured {seconds:.1f}s audio.")
        return self._to_float32_mono(audio), seconds

    def get_snapshot(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            audio = self._audio_from_frames_locked()

        if audio is None or audio.size == 0:
            return None, 0.0

        seconds = audio.shape[0] / self.sample_rate
        return self._to_float32_mono(audio), seconds

    def _on_audio(self, indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
        if status:
            log(f"Audio warning: {status}")
        with self._lock:
            if self._recording:
                self._frames.append(indata.copy())

    def _audio_from_frames_locked(self) -> np.ndarray | None:
        if not self._frames:
            return None
        return np.concatenate(self._frames, axis=0)

    def _to_float32_mono(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 2:
            audio = audio[:, 0]
        return (audio.astype(np.float32) / 32768.0).copy()
