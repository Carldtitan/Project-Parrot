import argparse
import base64
import contextlib
import io
import json
import logging
import os
import tempfile
import struct
import sys
import time
import traceback
import wave
from pathlib import Path

import numpy as np


UNIFIED_MODEL_ID = "nvidia/parakeet-unified-en-0.6b"
PARAKEET_MODEL_ID = "nemo-parakeet-tdt-0.6b-v3"
WHISPER_FALLBACK_MODEL_ID = "small.en"

os.environ.setdefault("NEMO_LOG_LEVEL", "ERROR")
os.environ.setdefault("TQDM_DISABLE", "1")
logging.getLogger("nemo_logger").setLevel(logging.ERROR)
logging.getLogger("nemo").setLevel(logging.ERROR)


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True), flush=True)


@contextlib.contextmanager
def suppress_library_output():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


def decode_f32le(payload):
    raw = base64.b64decode(payload)
    if len(raw) % 4 != 0:
        raise ValueError("audio payload length is not a multiple of 4 bytes")
    count = len(raw) // 4
    return struct.unpack("<" + ("f" * count), raw)


def load_parakeet(threads):
    import onnx_asr
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, threads)
    options.inter_op_num_threads = 1
    model = onnx_asr.load_model(
        PARAKEET_MODEL_ID,
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    return model


def load_unified(_threads):
    with suppress_library_output():
        import torch
        from omegaconf import OmegaConf
        from nemo.utils import logging as nemo_logging
        from nemo.collections.asr.models import ASRModel

        nemo_logging.setLevel(logging.ERROR)
        torch.set_grad_enabled(False)
        model = ASRModel.from_pretrained(UNIFIED_MODEL_ID, map_location="cpu")
        model.eval()
        if model.cfg.get("validation_ds") is None:
            OmegaConf.set_struct(model.cfg, False)
            model.cfg.validation_ds = OmegaConf.create({"use_start_end_token": False})
    return model


def load_faster_whisper_small(threads):
    from faster_whisper import WhisperModel

    return WhisperModel(
        WHISPER_FALLBACK_MODEL_ID,
        device="cpu",
        compute_type="float32",
        cpu_threads=max(1, threads),
    )


def write_temp_wav(audio, sample_rate):
    audio = np.asarray(audio, dtype=np.float32)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)
    handle = tempfile.NamedTemporaryFile(prefix="parrot-unified-", suffix=".wav", delete=False)
    path = Path(handle.name)
    handle.close()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return path


def normalize_audio(audio):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if peak > 0.98:
        audio = audio / peak * 0.98
    rms = float(np.sqrt(np.mean(audio * audio)))
    target_rms = 0.06
    if 0.001 < rms < target_rms:
        audio = audio * min(target_rms / rms, 8.0)
    return np.clip(audio, -1.0, 1.0).astype(np.float32)


def is_probably_silence(audio):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return True
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio * audio)))
    return peak < 0.006 or rms < 0.0015


def trim_silence(audio, sample_rate):
    audio = np.asarray(audio, dtype=np.float32)
    if audio.size == 0:
        return audio

    frame = max(1, int(sample_rate * 0.02))
    hop = max(1, int(sample_rate * 0.01))
    if audio.size <= frame:
        return audio

    rms_values = []
    starts = []
    for start in range(0, audio.size - frame + 1, hop):
        chunk = audio[start : start + frame]
        rms_values.append(float(np.sqrt(np.mean(chunk * chunk))))
        starts.append(start)

    if not rms_values:
        return audio

    noise_floor = float(np.percentile(rms_values, 20))
    threshold = max(0.008, noise_floor * 2.5)
    voiced = [idx for idx, rms in enumerate(rms_values) if rms >= threshold]
    if not voiced:
        return np.asarray([], dtype=np.float32)

    pad = int(sample_rate * 0.12)
    first = max(0, starts[voiced[0]] - pad)
    last = min(audio.size, starts[voiced[-1]] + frame + pad)
    return audio[first:last]


def prepare_final_audio(audio, sample_rate):
    return normalize_audio(trim_silence(audio, sample_rate))


def normalize_nemo_output(result):
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, list):
        if not result:
            return ""
        return normalize_nemo_output(result[0])
    if hasattr(result, "text"):
        return str(result.text).strip()
    return str(result).strip()


def transcribe_unified(model, audio, sample_rate):
    path = write_temp_wav(audio, sample_rate)
    try:
        with suppress_library_output():
            result = model.transcribe([str(path)], batch_size=1, verbose=False)
        return normalize_nemo_output(result)
    finally:
        try:
            path.unlink()
        except OSError:
            pass


def transcribe_parakeet(model, audio, sample_rate):
    text = model.recognize(audio, sample_rate=sample_rate)
    if isinstance(text, list):
        text = " ".join(str(item) for item in text)
    return str(text).strip()


def transcribe_faster_whisper(model, audio, sample_rate):
    segments, _info = model.transcribe(
        audio,
        language="en",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe(engine, model, audio, sample_rate):
    if len(audio) == 0:
        return ""
    if is_probably_silence(audio):
        return ""
    if engine == "unified":
        return transcribe_unified(model, audio, sample_rate)
    if engine == "parakeet":
        return transcribe_parakeet(model, audio, sample_rate)
    if engine == "small-en":
        return transcribe_faster_whisper(model, audio, sample_rate)
    raise ValueError(f"unknown engine: {engine}")


def live_window(buffer, sample_rate, max_seconds):
    max_samples = int(sample_rate * max_seconds)
    if len(buffer) <= max_samples:
        return np.asarray(buffer, dtype=np.float32)
    return np.asarray(buffer[-max_samples:], dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="Project Parrot kept-alive STT worker")
    parser.add_argument("--engine", choices=["unified", "parakeet", "small-en"], default="small-en")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--update-interval", type=float, default=0.7)
    parser.add_argument("--live-window-seconds", type=float, default=8.0)
    args = parser.parse_args()

    sample_rate = 16000
    started = time.perf_counter()
    try:
        if args.engine == "unified":
            model = load_unified(args.threads)
            model_name = UNIFIED_MODEL_ID
            runtime = "nemo-pytorch-cpu"
        elif args.engine == "parakeet":
            model = load_parakeet(args.threads)
            model_name = PARAKEET_MODEL_ID
            runtime = "onnxruntime-cpu"
        else:
            model = load_faster_whisper_small(args.threads)
            model_name = WHISPER_FALLBACK_MODEL_ID
            runtime = "ctranslate2-cpu"
    except Exception as exc:
        emit({"type": "error", "message": f"failed to load {args.engine}: {exc}"})
        return 2

    # Warm once so the first user utterance does not pay graph/session setup.
    try:
        silence = np.zeros(sample_rate // 2, dtype=np.float32)
        transcribe(args.engine, model, silence, sample_rate)
    except Exception:
        pass

    emit(
        {
            "type": "ready",
            "engine": args.engine,
            "model": model_name,
            "runtime": runtime,
            "load_seconds": round(time.perf_counter() - started, 3),
        }
    )

    buffer = []
    recording = False
    last_live_at = 0.0
    last_live_text = ""

    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                message_type = message.get("type")

                if message_type == "start":
                    buffer = []
                    recording = True
                    last_live_at = 0.0
                    last_live_text = ""
                    emit({"type": "started"})

                elif message_type == "audio":
                    if not recording:
                        continue
                    sample_rate = int(message.get("sample_rate", sample_rate))
                    buffer.extend(decode_f32le(message["samples"]))
                    now = time.perf_counter()
                    enough_audio = len(buffer) >= int(sample_rate * 0.7)
                    enough_time = now - last_live_at >= args.update_interval
                    if enough_audio and enough_time:
                        last_live_at = now
                        window = live_window(buffer, sample_rate, args.live_window_seconds)
                        live_started = time.perf_counter()
                        text = transcribe(args.engine, model, window, sample_rate)
                        latency_ms = int((time.perf_counter() - live_started) * 1000)
                        if text and text != last_live_text:
                            last_live_text = text
                            emit({"type": "partial", "text": text, "latency_ms": latency_ms})

                elif message_type == "stop":
                    recording = False
                    if "samples" in message:
                        sample_rate = int(message.get("sample_rate", sample_rate))
                        audio = np.asarray(decode_f32le(message["samples"]), dtype=np.float32)
                    else:
                        audio = np.asarray(buffer, dtype=np.float32)
                    audio = prepare_final_audio(audio, sample_rate)
                    final_started = time.perf_counter()
                    text = transcribe(args.engine, model, audio, sample_rate)
                    latency_ms = int((time.perf_counter() - final_started) * 1000)
                    emit({"type": "final", "text": text, "latency_ms": latency_ms})

                elif message_type == "shutdown":
                    break

                else:
                    emit({"type": "error", "message": f"unknown message type: {message_type}"})

            except Exception as exc:
                emit(
                    {
                        "type": "error",
                        "message": str(exc),
                        "traceback": traceback.format_exc(limit=3),
                    }
                )
    finally:
        del model

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
