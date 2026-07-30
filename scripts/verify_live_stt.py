"""Exercise Parrot's live worker protocol with a known clean speech sample."""

from __future__ import annotations

import argparse
import base64
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import jiwer
import numpy as np

from benchmark_stt import load_benchmark_dataset, normalize


ROOT = Path(__file__).resolve().parents[1]


def worker_command(engine: str, threads: int) -> list[str]:
    bundled = ROOT / ".build" / "stt_worker" / "stt_worker.exe"
    if bundled.exists():
        return [str(bundled), "--engine", engine, "--threads", str(threads)]
    return [
        sys.executable,
        str(ROOT / "scripts" / "stt_worker.py"),
        "--engine",
        engine,
        "--threads",
        str(threads),
    ]


def send(process: subprocess.Popen[str], message: dict) -> None:
    assert process.stdin is not None
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def wait_for_event(
    events: queue.Queue[dict],
    event_type: str,
    timeout: float,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = events.get(timeout=min(0.5, deadline - time.monotonic()))
        except queue.Empty:
            continue
        if event.get("type") == "error":
            raise RuntimeError(event.get("message", "STT worker error"))
        if event.get("type") == event_type:
            return event
    raise TimeoutError(f"Timed out waiting for STT event: {event_type}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify live partial and final transcription through Parrot's worker protocol."
    )
    parser.add_argument("--engine", choices=["parakeet", "small-en"], default="parakeet")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-wer", type=float, default=0.20)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    sample = load_benchmark_dataset("dummy", limit=1, max_audio_minutes=1)[0]
    audio = np.asarray(sample["array"], dtype="<f4")
    sample_rate = int(sample["sampling_rate"])
    reference = str(sample["text"])

    command = worker_command(args.engine, max(1, args.threads))
    command.extend(["--update-interval", "0.5", "--live-window-seconds", "3.0"])
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    events: queue.Queue[dict] = queue.Queue()
    partials: list[dict] = []

    def collect() -> None:
        assert process.stdout is not None
        for raw_line in process.stdout:
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "partial":
                partials.append(event)
            events.put(event)

    reader = threading.Thread(target=collect, name="live-stt-verifier", daemon=True)
    reader.start()

    try:
        ready = wait_for_event(events, "ready", args.timeout)
        send(process, {"type": "start"})
        wait_for_event(events, "started", 10)

        chunk_size = max(1, int(sample_rate * 0.5))
        streamed_at = time.monotonic()
        for offset in range(0, len(audio), chunk_size):
            chunk = audio[offset : offset + chunk_size]
            send(
                process,
                {
                    "type": "audio",
                    "sample_rate": sample_rate,
                    "samples": base64.b64encode(chunk.tobytes()).decode("ascii"),
                },
            )
            time.sleep(0.05)

        send(process, {"type": "stop"})
        final = wait_for_event(events, "final", args.timeout)
        elapsed = time.monotonic() - streamed_at
        hypothesis = str(final.get("text", "")).strip()
        score = jiwer.wer(normalize(reference), normalize(hypothesis))

        result = {
            "status": "ok" if partials and hypothesis and score <= args.max_wer else "failed",
            "engine": ready.get("engine"),
            "runtime": ready.get("runtime"),
            "sample_seconds": round(len(audio) / sample_rate, 3),
            "wall_seconds": round(elapsed, 3),
            "partial_count": len(partials),
            "first_partial": partials[0]["text"] if partials else "",
            "reference": reference,
            "final": hypothesis,
            "wer": round(score, 4),
            "max_wer": args.max_wer,
        }
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "ok" else 1
    finally:
        if process.poll() is None:
            try:
                send(process, {"type": "quit"})
                process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
