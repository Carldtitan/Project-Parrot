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


def worker_command(engine: str, threads: int, source_worker: bool = False) -> list[str]:
    bundled = ROOT / ".build" / "stt_worker" / "stt_worker.exe"
    if bundled.exists() and not source_worker:
        return [str(bundled), "--engine", engine, "--threads", str(threads)]
    return [
        sys.executable,
        str(ROOT / "scripts" / "stt_worker.py"),
        "--engine",
        engine,
        "--threads",
        str(threads),
    ]


def build_fixture(target_seconds: float) -> tuple[np.ndarray, int, str, int]:
    if target_seconds <= 0:
        sample = load_benchmark_dataset("dummy", limit=1, max_audio_minutes=1)[0]
        return (
            np.asarray(sample["array"], dtype="<f4"),
            int(sample["sampling_rate"]),
            str(sample["text"]),
            1,
        )

    rows = load_benchmark_dataset(
        "dummy",
        limit=100,
        max_audio_minutes=max(2.0, target_seconds / 60.0 + 1.0),
    )
    sample_rate = int(rows[0]["sampling_rate"])
    silence = np.zeros(int(sample_rate * 0.20), dtype="<f4")
    parts: list[np.ndarray] = []
    references: list[str] = []
    total_samples = 0
    for row in rows:
        if int(row["sampling_rate"]) != sample_rate:
            raise RuntimeError("Long fixture contains mixed sample rates")
        parts.append(np.asarray(row["array"], dtype="<f4"))
        parts.append(silence)
        references.append(str(row["text"]))
        total_samples += len(parts[-2]) + len(silence)
        if total_samples / sample_rate >= target_seconds:
            break

    if total_samples / sample_rate < target_seconds:
        raise RuntimeError(
            f"Dataset only supplied {total_samples / sample_rate:.1f}s "
            f"for a requested {target_seconds:.1f}s fixture"
        )
    return np.concatenate(parts), sample_rate, " ".join(references), len(references)


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
    parser.add_argument(
        "--max-live-wer",
        type=float,
        help="Optional WER gate for the final live preview as well as final output.",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--update-interval", type=float, default=0.5)
    parser.add_argument("--live-window-seconds", type=float, default=3.0)
    parser.add_argument(
        "--target-seconds",
        type=float,
        default=0.0,
        help="Build a varied fixture at least this long from consecutive samples.",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Stream audio at microphone speed instead of the faster test rate.",
    )
    parser.add_argument(
        "--source-worker",
        action="store_true",
        help="Use scripts/stt_worker.py even when a packaged worker exists.",
    )
    args = parser.parse_args()

    audio, sample_rate, reference, fixture_segments = build_fixture(
        max(0.0, args.target_seconds)
    )

    command = worker_command(args.engine, max(1, args.threads), args.source_worker)
    command.extend(
        [
            "--update-interval",
            str(max(0.25, args.update_interval)),
            "--live-window-seconds",
            str(max(2.0, args.live_window_seconds)),
        ]
    )
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
            time.sleep(len(chunk) / sample_rate if args.realtime else 0.05)

        send(process, {"type": "stop"})
        final = wait_for_event(events, "final", args.timeout)
        elapsed = time.monotonic() - streamed_at
        hypothesis = str(final.get("text", "")).strip()
        score = jiwer.wer(normalize(reference), normalize(hypothesis))
        reference_words = normalize(reference).split()
        final_words = normalize(hypothesis).split()
        last_partial = str(partials[-1].get("text", "")).strip() if partials else ""
        live_words = normalize(last_partial).split()
        live_score = (
            jiwer.wer(normalize(reference), normalize(last_partial))
            if last_partial
            else 1.0
        )
        live_ok = args.max_live_wer is None or live_score <= args.max_live_wer

        result = {
            "status": (
                "ok"
                if partials and hypothesis and score <= args.max_wer and live_ok
                else "failed"
            ),
            "engine": ready.get("engine"),
            "runtime": ready.get("runtime"),
            "sample_seconds": round(len(audio) / sample_rate, 3),
            "fixture_segments": fixture_segments,
            "final_chunk_count": final.get("chunk_count"),
            "recognized_audio_seconds": final.get("audio_seconds"),
            "wall_seconds": round(elapsed, 3),
            "partial_count": len(partials),
            "first_partial": partials[0]["text"] if partials else "",
            "last_partial": last_partial,
            "live_words": len(live_words),
            "live_word_coverage": round(
                len(live_words) / max(1, len(reference_words)),
                4,
            ),
            "live_wer": round(live_score, 4),
            "max_live_wer": args.max_live_wer,
            "reference": reference,
            "final": hypothesis,
            "reference_words": len(reference_words),
            "final_words": len(final_words),
            "word_coverage": round(len(final_words) / max(1, len(reference_words)), 4),
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
