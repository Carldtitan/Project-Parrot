import argparse
import base64
from difflib import SequenceMatcher
import json
import re
import struct
import sys
import time
import traceback

import numpy as np


PARAKEET_MODEL_ID = "nemo-parakeet-tdt-0.6b-v3"
WHISPER_FALLBACK_MODEL_ID = "small.en"
FINAL_TRAILING_PADDING_SECONDS = 0.35


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True), flush=True)


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


def load_faster_whisper_small(threads):
    from faster_whisper import WhisperModel

    return WhisperModel(
        WHISPER_FALLBACK_MODEL_ID,
        device="cpu",
        compute_type="float32",
        cpu_threads=max(1, threads),
    )


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

    leading_pad = int(sample_rate * 0.12)
    trailing_pad = int(sample_rate * 0.24)
    first = max(0, starts[voiced[0]] - leading_pad)
    last = min(audio.size, starts[voiced[-1]] + frame + trailing_pad)
    return audio[first:last]


def prepare_final_audio(audio, sample_rate):
    source = np.asarray(audio, dtype=np.float32)
    trimmed = trim_silence(source, sample_rate)

    # Some laptop microphones produce speech below the conservative trimming
    # threshold even though the recognizer can transcribe the untrimmed signal.
    # Never discard an otherwise useful utterance solely because trimming found
    # too little voiced audio.
    minimum_useful_samples = int(sample_rate * 0.25)
    if source.size >= minimum_useful_samples and trimmed.size < minimum_useful_samples:
        trimmed = source

    normalized = normalize_audio(trimmed)
    if is_probably_silence(normalized):
        return normalized

    # Transducer models make a more stable final-token decision when speech is
    # followed by a clean non-speech boundary. This also prevents the last
    # phoneme from being treated as a clipped, unfinished word.
    trailing_silence = np.zeros(
        int(sample_rate * FINAL_TRAILING_PADDING_SECONDS),
        dtype=np.float32,
    )
    return np.concatenate((normalized, trailing_silence))


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
    if engine == "parakeet":
        return transcribe_parakeet(model, audio, sample_rate)
    if engine == "small-en":
        return transcribe_faster_whisper(model, audio, sample_rate)
    raise ValueError(f"unknown engine: {engine}")


def live_window(buffer, sample_rate, max_seconds):
    max_samples = int(sample_rate * max_seconds)
    if len(buffer) <= max_samples:
        return np.asarray(buffer, dtype=np.float32), False
    return np.asarray(buffer[-max_samples:], dtype=np.float32), True


def normalized_token(token):
    return re.sub(r"[^\w']+", "", token.casefold())


def merge_rolling_transcript(previous, current):
    """Join overlapping rolling-window transcripts without losing old words."""
    previous = str(previous or "").strip()
    current = str(current or "").strip()
    if not previous:
        return current
    if not current:
        return previous

    previous_words = previous.split()
    current_words = current.split()
    previous_keys = [normalized_token(word) for word in previous_words]
    current_keys = [normalized_token(word) for word in current_words]

    if previous_keys == current_keys:
        return current

    max_overlap = min(len(previous_keys), len(current_keys))
    for overlap in range(max_overlap, 0, -1):
        if previous_keys[-overlap:] == current_keys[:overlap]:
            return " ".join(previous_words[:-overlap] + current_words)

    # Recognition can revise one or two words between passes. Anchor on the
    # strongest shared phrase near the moving boundary and replace that tail
    # with the newer hypothesis.
    tail_start = max(0, len(previous_keys) - max(24, len(current_keys) * 2))
    matcher = SequenceMatcher(
        None,
        previous_keys[tail_start:],
        current_keys,
        autojunk=False,
    )
    candidates = [
        block
        for block in matcher.get_matching_blocks()
        if block.size >= 2
        and block.b <= max(3, len(current_keys) // 3)
    ]
    if candidates:
        anchor = max(candidates, key=lambda block: (block.size, -block.b))
        previous_anchor = tail_start + anchor.a
        return " ".join(
            previous_words[:previous_anchor] + current_words[anchor.b:]
        )

    # A one-word boundary is still useful for short phrases.
    if previous_keys[-1] == current_keys[0]:
        return " ".join(previous_words[:-1] + current_words)

    return f"{previous} {current}".strip()


def recover_live_tail(final_text, live_text):
    """Restore words omitted only from the end of the full-utterance pass."""
    final_text = str(final_text or "").strip()
    live_text = str(live_text or "").strip()
    if not final_text:
        return live_text
    if not live_text:
        return final_text

    final_words = final_text.split()
    live_words = live_text.split()
    final_keys = [normalized_token(word) for word in final_words]
    live_keys = [normalized_token(word) for word in live_words]
    similarity = SequenceMatcher(None, final_keys, live_keys, autojunk=False).ratio()

    max_anchor = min(10, len(final_keys), len(live_keys))
    for anchor_size in range(max_anchor, 0, -1):
        anchor = final_keys[-anchor_size:]
        for live_start in range(len(live_keys) - anchor_size, -1, -1):
            if live_keys[live_start : live_start + anchor_size] != anchor:
                continue
            tail = live_words[live_start + anchor_size :]
            if not tail:
                continue
            if anchor_size < 2 and similarity < 0.70:
                continue
            if len(tail) > max(12, len(final_words) // 2):
                continue

            base = re.sub(r"[.!?,;:]+$", "", final_text).rstrip()
            return f"{base} {' '.join(tail)}".strip()

    return final_text


def main():
    parser = argparse.ArgumentParser(description="Project Parrot kept-alive STT worker")
    parser.add_argument("--engine", choices=["parakeet", "small-en"], default="small-en")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--update-interval", type=float, default=0.5)
    parser.add_argument("--live-window-seconds", type=float, default=8.0)
    args = parser.parse_args()

    sample_rate = 16000
    started = time.perf_counter()
    try:
        if args.engine == "parakeet":
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
    last_emitted_text = ""

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
                    last_emitted_text = ""
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
                        window, is_rolling = live_window(
                            buffer,
                            sample_rate,
                            args.live_window_seconds,
                        )
                        window = normalize_audio(window)
                        live_started = time.perf_counter()
                        text = transcribe(args.engine, model, window, sample_rate)
                        latency_ms = int((time.perf_counter() - live_started) * 1000)
                        if text:
                            last_live_text = (
                                merge_rolling_transcript(last_live_text, text)
                                if is_rolling
                                else text
                            )
                        if last_live_text and last_live_text != last_emitted_text:
                            last_emitted_text = last_live_text
                            emit(
                                {
                                    "type": "partial",
                                    "text": last_live_text,
                                    "latency_ms": latency_ms,
                                }
                            )

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
                    used_live_fallback = not text and bool(last_live_text)
                    used_live_tail = False
                    if used_live_fallback:
                        text = last_live_text
                    elif text and last_live_text:
                        recovered_text = recover_live_tail(text, last_live_text)
                        used_live_tail = recovered_text != text
                        text = recovered_text
                    emit(
                        {
                            "type": "final",
                            "text": text,
                            "latency_ms": latency_ms,
                            "used_live_fallback": used_live_fallback,
                            "used_live_tail": used_live_tail,
                        }
                    )

                elif message_type == "cancel":
                    recording = False
                    buffer = []
                    last_live_text = ""
                    last_emitted_text = ""

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
