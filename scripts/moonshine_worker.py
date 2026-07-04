import argparse
import base64
import json
import struct
import sys
import traceback
from pathlib import Path

from moonshine_voice.moonshine_api import ModelArch
from moonshine_voice.transcriber import (
    LineCompleted,
    LineTextChanged,
    Transcriber,
    TranscriptEventListener,
)


ARCHES = {
    "tiny-streaming": ModelArch.TINY_STREAMING,
    "small-streaming": ModelArch.SMALL_STREAMING,
    "medium-streaming": ModelArch.MEDIUM_STREAMING,
}


def emit(payload):
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def decode_f32le(payload):
    raw = base64.b64decode(payload)
    if len(raw) % 4 != 0:
        raise ValueError("audio payload length is not a multiple of 4 bytes")
    count = len(raw) // 4
    return list(struct.unpack("<" + ("f" * count), raw))


def transcript_text(transcript):
    return " ".join(line.text.strip() for line in transcript.lines if line.text.strip()).strip()


class JsonListener(TranscriptEventListener):
    def on_line_text_changed(self, event: LineTextChanged):
        text = event.line.text.strip()
        if text:
            emit(
                {
                    "type": "partial",
                    "text": text,
                    "latency_ms": event.line.last_transcription_latency_ms,
                }
            )

    def on_line_completed(self, event: LineCompleted):
        text = event.line.text.strip()
        if text:
            emit(
                {
                    "type": "line_completed",
                    "text": text,
                    "latency_ms": event.line.last_transcription_latency_ms,
                }
            )


def main():
    parser = argparse.ArgumentParser(description="Project Parrot Moonshine worker")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--model-arch", choices=sorted(ARCHES), required=True)
    parser.add_argument("--update-interval", type=float, default=0.18)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        emit({"type": "error", "message": f"missing Moonshine model dir: {model_dir}"})
        return 2

    try:
        transcriber = Transcriber(
            model_path=str(model_dir),
            model_arch=ARCHES[args.model_arch],
            update_interval=args.update_interval,
        )
    except Exception as exc:
        emit({"type": "error", "message": f"failed to load Moonshine model: {exc}"})
        return 2

    stream = None
    listener = JsonListener()
    emit({"type": "ready", "model_dir": str(model_dir), "model_arch": args.model_arch})

    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                message_type = message.get("type")

                if message_type == "start":
                    if stream is not None:
                        stream.close()
                    stream = transcriber.create_stream(update_interval=args.update_interval)
                    stream.add_listener(listener)
                    stream.start()
                    emit({"type": "started"})

                elif message_type == "audio":
                    if stream is None:
                        emit({"type": "error", "message": "audio received before start"})
                        continue
                    samples = decode_f32le(message["samples"])
                    sample_rate = int(message.get("sample_rate", 16000))
                    stream.add_audio(samples, sample_rate)

                elif message_type == "stop":
                    if stream is None:
                        emit({"type": "final", "text": ""})
                        continue
                    transcript = stream.stop()
                    final_text = transcript_text(transcript)
                    stream.close()
                    stream = None
                    emit({"type": "final", "text": final_text})

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
        if stream is not None:
            stream.close()
        transcriber.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
