from __future__ import annotations

import warnings

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from faster_whisper import WhisperModel


class TranscriptionError(RuntimeError):
    pass


class FasterWhisperTranscriber:
    def __init__(self, model_name: str, device: str, compute_type: str) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model: WhisperModel | None = None

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""

        try:
            segments, _info = self._get_model().transcribe(
                audio,
                language="en",
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:  # noqa: BLE001
            raise TranscriptionError(f"faster-whisper failed: {exc}") from exc

    def preload(self) -> None:
        self._get_model()
        silence = np.zeros(16000, dtype=np.float32)
        self.transcribe(silence)

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model
