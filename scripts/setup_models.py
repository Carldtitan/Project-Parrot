import argparse
import tempfile
import wave
from pathlib import Path

import numpy as np


PARAKEET_REPO = "istupakov/parakeet-tdt-0.6b-v3-onnx"
UNIFIED_MODEL_ID = "nvidia/parakeet-unified-en-0.6b"
PARAKEET_MODEL_ID = "nemo-parakeet-tdt-0.6b-v3"
WHISPER_MODEL_ID = "small.en"


def smoke_wav() -> Path:
    path = Path(tempfile.gettempdir()) / "project-parrot-silence.wav"
    audio = np.zeros(16000, dtype=np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(audio.tobytes())
    return path


def setup_parakeet(threads: int) -> None:
    from huggingface_hub import snapshot_download
    import onnx_asr
    import onnxruntime as ort

    print(f"Downloading/checking Parakeet ONNX: {PARAKEET_REPO}")
    path = snapshot_download(repo_id=PARAKEET_REPO)
    print(f"Parakeet files ready: {path}")

    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, threads)
    options.inter_op_num_threads = 1
    print("Loading Parakeet through onnx-asr...")
    model = onnx_asr.load_model(
        PARAKEET_MODEL_ID,
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    text = model.recognize(np.zeros(16000, dtype=np.float32), sample_rate=16000)
    print(f"Parakeet smoke OK: {str(text)[:80]!r}")
    del model


def setup_unified() -> None:
    import torch
    from nemo.collections.asr.models import ASRModel

    print(f"Downloading/checking Parakeet Unified: {UNIFIED_MODEL_ID}")
    torch.set_grad_enabled(False)
    model = ASRModel.from_pretrained(UNIFIED_MODEL_ID, map_location="cpu")
    model.eval()
    print("Parakeet Unified smoke OK: model loaded on CPU")
    del model


def setup_small_en(threads: int) -> None:
    from faster_whisper import WhisperModel

    print(f"Downloading/checking faster-whisper fallback: {WHISPER_MODEL_ID}")
    model = WhisperModel(
        WHISPER_MODEL_ID,
        device="cpu",
        compute_type="float32",
        cpu_threads=max(1, threads),
    )
    segments, _info = model.transcribe(str(smoke_wav()), language="en", beam_size=1)
    list(segments)
    print("faster-whisper small.en smoke OK")
    del model


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Project Parrot local STT models")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--skip-unified", action="store_true")
    parser.add_argument("--skip-parakeet", action="store_true")
    parser.add_argument("--skip-small-en", action="store_true")
    args = parser.parse_args()

    if not args.skip_unified:
        setup_unified()
    if not args.skip_parakeet:
        setup_parakeet(args.threads)
    if not args.skip_small_en:
        setup_small_en(args.threads)
    print("Project Parrot models are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
