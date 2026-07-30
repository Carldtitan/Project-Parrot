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
FINAL_DIRECT_PASS_SECONDS = 90.0
FINAL_CHUNK_SECONDS = 18.0
FINAL_CHUNK_OVERLAP_SECONDS = 1.5
FINAL_SPLIT_SEARCH_SECONDS = 2.0


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
    # Quiet speech can have low average energy while still containing clear
    # phoneme peaks. Requiring both values to be tiny avoids rejecting soft
    # voices solely because their RMS is below a conservative VAD threshold.
    return peak < 0.004 and rms < 0.001


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
    if is_probably_silence(source):
        return source

    # The final pass is deliberately lossless. Trimming based on an energy
    # threshold can remove a softly spoken first or last phrase even when the
    # middle of the utterance is loud. Parakeet handles surrounding silence,
    # so preserve every captured sample and only append a clean end boundary.
    normalized = normalize_audio(source)

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


def split_final_audio(
    audio,
    sample_rate,
    chunk_seconds=FINAL_CHUNK_SECONDS,
    overlap_seconds=FINAL_CHUNK_OVERLAP_SECONDS,
):
    """Split long speech near quiet boundaries while retaining overlap."""
    audio = np.asarray(audio, dtype=np.float32)
    max_samples = max(1, int(sample_rate * chunk_seconds))
    if audio.size <= max_samples:
        return [audio]

    overlap_samples = max(0, int(sample_rate * overlap_seconds))
    search_samples = max(1, int(sample_rate * FINAL_SPLIT_SEARCH_SECONDS))
    minimum_samples = max(1, int(sample_rate * 8.0))
    frame = max(1, int(sample_rate * 0.03))
    hop = max(1, int(sample_rate * 0.01))
    chunks = []
    start = 0

    while audio.size - start > max_samples:
        target = start + max_samples
        search_start = max(start + minimum_samples, target - search_samples)
        search_end = min(audio.size - frame, target + search_samples)
        split = target
        best_rms = float("inf")
        for candidate in range(search_start, search_end + 1, hop):
            window = audio[candidate : candidate + frame]
            rms = float(np.sqrt(np.mean(window * window)))
            if rms < best_rms:
                best_rms = rms
                split = candidate + frame // 2

        split = max(start + minimum_samples, min(split, audio.size))
        chunks.append(audio[start:split])
        next_start = max(start + 1, split - overlap_samples)
        if next_start <= start:
            next_start = split
        start = next_start

    if start < audio.size:
        chunks.append(audio[start:])
    return chunks


def transcribe_final(engine, model, audio, sample_rate):
    # Parakeet is more accurate when it can use the complete discourse context
    # for ordinary dictations. The exact one-minute quality fixture reaches
    # near-perfect coverage as a single pass but loses a phrase when divided at
    # an unlucky acoustic boundary. Reserve segmentation for genuinely long
    # recordings that approach the model's practical context limit.
    if len(audio) <= int(sample_rate * FINAL_DIRECT_PASS_SECONDS):
        prepared = normalize_audio(audio)
        return transcribe(engine, model, prepared, sample_rate).strip(), 1

    chunks = split_final_audio(audio, sample_rate)
    merged = ""
    segment_padding = np.zeros(
        int(sample_rate * FINAL_TRAILING_PADDING_SECONDS),
        dtype=np.float32,
    )
    for index, chunk in enumerate(chunks):
        prepared = normalize_audio(chunk)
        if index < len(chunks) - 1 and not is_probably_silence(prepared):
            prepared = np.concatenate((prepared, segment_padding))
        segment = transcribe(engine, model, prepared, sample_rate)
        if segment:
            merged = merge_final_segments(merged, segment)
    return merged.strip(), len(chunks)


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


def merge_final_segments(previous, current):
    """Join final overlapping chunks without discarding unmatched old words."""
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

    max_overlap = min(16, len(previous_keys), len(current_keys))
    for overlap in range(max_overlap, 0, -1):
        if previous_keys[-overlap:] == current_keys[:overlap]:
            return " ".join(previous_words[:-overlap] + current_words)

    # Parakeet can revise one word inside the overlap. Find a strong contiguous
    # boundary anchor, collapse that shared phrase to the newer spelling, and
    # retain both unmatched tails. Deliberately ignore isolated later matches
    # such as "his" or "the"; treating them as anchors can reorder text.
    boundary_words = 24
    previous_tail_start = max(0, len(previous_keys) - boundary_words)
    current_head_end = min(len(current_keys), boundary_words)
    previous_tail = previous_keys[previous_tail_start:]
    current_head = current_keys[:current_head_end]

    def equivalent(left, right):
        if left == right:
            return True
        if min(len(left), len(right)) < 4:
            return False
        return SequenceMatcher(None, left, right, autojunk=False).ratio() >= 0.78

    anchors = []
    for previous_index in range(len(previous_tail)):
        for current_index in range(min(9, len(current_head))):
            length = 0
            while (
                previous_index + length < len(previous_tail)
                and current_index + length < len(current_head)
                and equivalent(
                    previous_tail[previous_index + length],
                    current_head[current_index + length],
                )
            ):
                length += 1
            if (
                length >= 2
                and len(previous_tail) - previous_index - length <= 8
            ):
                anchors.append((length, previous_index, current_index))

    if anchors:
        length, previous_index, current_index = max(
            anchors,
            key=lambda anchor: (anchor[0], anchor[1], -anchor[2]),
        )
        merged = previous_words[: previous_tail_start + previous_index]
        merged.extend(
            current_words[current_index : current_index + length]
        )
        merged.extend(
            previous_words[previous_tail_start + previous_index + length :]
        )
        merged.extend(current_words[current_index + length :])
        return " ".join(merged)

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
                    text, chunk_count = transcribe_final(
                        args.engine,
                        model,
                        audio,
                        sample_rate,
                    )
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
                            "audio_seconds": round(len(audio) / sample_rate, 3),
                            "chunk_count": chunk_count,
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
