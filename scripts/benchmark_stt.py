import argparse
import csv
import gc
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import jiwer
import numpy as np
from datasets import Audio, load_dataset


DATASET_SPECS = {
    "dummy": {
        "name": "hf-internal-testing/librispeech_asr_dummy",
        "config": "clean",
        "split": "validation",
        "text_column": "text",
        "id_columns": ["id", "file"],
        "streaming": False,
        "trust_remote_code": False,
        "description": "Tiny smoke-test dataset. Not a serious product benchmark.",
    },
    "common-voice": {
        "name": "DTU54DL/common-voice",
        "config": None,
        "split": "test",
        "text_column": "sentence",
        "id_columns": ["id", "path", "audio"],
        "streaming": True,
        "trust_remote_code": False,
        "description": "Common Voice-derived English crowd-speech subset with accent labels.",
    },
    "librispeech-other": {
        "name": "openslr/librispeech_asr",
        "config": "other",
        "split": "test",
        "text_column": "text",
        "id_columns": ["id", "file"],
        "streaming": True,
        "trust_remote_code": False,
        "description": "LibriSpeech test.other. Standard harder read-speech ASR benchmark.",
    },
    "earnings22": {
        "name": "distil-whisper/earnings22",
        "config": "chunked",
        "split": "test",
        "text_column": "transcription",
        "id_columns": ["file_id", "segment_id"],
        "streaming": True,
        "trust_remote_code": False,
        "description": "Earnings-22 chunked. Real-world accented professional speech.",
    },
}

DEFAULT_MODELS = [
    "moonshine-small",
    "moonshine-medium",
    "faster-whisper-small.en",
    "faster-whisper-medium.en",
    "faster-whisper-large-v3-turbo",
    "parakeet-tdt-0.6b-v3-onnx",
]

MODEL_SPECS = {
    "moonshine-small": {
        "engine": "Moonshine streaming runtime",
        "stt": "Moonshine Small Streaming",
        "mode": "streaming",
    },
    "moonshine-medium": {
        "engine": "Moonshine streaming runtime",
        "stt": "Moonshine Medium Streaming",
        "mode": "streaming",
    },
    "faster-whisper-small.en": {
        "engine": "CTranslate2 via faster-whisper",
        "stt": "Whisper small.en",
        "mode": "file/offline",
    },
    "faster-whisper-medium.en": {
        "engine": "CTranslate2 via faster-whisper",
        "stt": "Whisper medium.en",
        "mode": "file/offline",
    },
    "faster-whisper-large-v3-turbo": {
        "engine": "CTranslate2 via faster-whisper",
        "stt": "Whisper large-v3-turbo",
        "mode": "file/offline",
    },
    "parakeet-tdt-0.6b-v3-onnx": {
        "engine": "ONNX Runtime via onnx-asr",
        "stt": "NVIDIA Parakeet TDT 0.6B v3",
        "mode": "file/offline",
    },
}


class SkippedBenchmark(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize(text: str) -> str:
    return jiwer.Compose(
        [
            jiwer.ToLowerCase(),
            jiwer.RemovePunctuation(),
            jiwer.RemoveMultipleSpaces(),
            jiwer.Strip(),
        ]
    )(text)


def model_spec(model_name: str) -> dict:
    return MODEL_SPECS.get(
        model_name,
        {"engine": "unknown", "stt": model_name, "mode": "unknown"},
    )


def load_benchmark_dataset(dataset_id: str, limit: int, max_audio_minutes: float | None):
    spec = dataset_spec(dataset_id)
    load_kwargs = {
        "split": spec["split"],
        "streaming": spec["streaming"],
        "trust_remote_code": spec["trust_remote_code"],
    }
    if spec["config"]:
        dataset = load_dataset(spec["name"], spec["config"], **load_kwargs)
    else:
        dataset = load_dataset(spec["name"], **load_kwargs)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))
    rows = []
    max_audio_seconds = max_audio_minutes * 60.0 if max_audio_minutes else None
    total_audio_seconds = 0.0
    iterable = dataset
    if not spec["streaming"]:
        iterable = dataset.select(range(min(limit, len(dataset))))
    for row in iterable:
        audio = row["audio"]
        audio_array = np.asarray(audio["array"], dtype=np.float32)
        duration = len(audio_array) / int(audio["sampling_rate"])
        if max_audio_seconds and rows and total_audio_seconds + duration > max_audio_seconds:
            break
        rows.append(
            {
                "id": dataset_row_id(row, spec, len(rows)),
                "text": str(row[spec["text_column"]]),
                "array": audio_array,
                "sampling_rate": int(audio["sampling_rate"]),
            }
        )
        total_audio_seconds += duration
        if len(rows) >= limit:
            break
    if not rows:
        raise RuntimeError(f"No benchmark rows loaded for dataset {dataset_id}")
    return rows


def dataset_spec(dataset_id: str) -> dict:
    if dataset_id not in DATASET_SPECS:
        known = ", ".join(sorted(DATASET_SPECS))
        raise RuntimeError(f"Unknown dataset {dataset_id}. Known datasets: {known}")
    return DATASET_SPECS[dataset_id]


def dataset_row_id(row: dict, spec: dict, fallback: int) -> str:
    parts = []
    for column in spec["id_columns"]:
        if column == "audio":
            audio = row.get("audio") or {}
            value = audio.get("path") if isinstance(audio, dict) else None
        else:
            value = row.get(column)
        if value is not None:
            parts.append(str(value))
    return safe_id("-".join(parts) if parts else str(fallback))


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def transcribe_moonshine(model_name: str, rows, update_interval: float):
    from moonshine_voice.moonshine_api import ModelArch
    from moonshine_voice.transcriber import Transcriber

    arches = {
        "moonshine-small": ("small-streaming", ModelArch.SMALL_STREAMING),
        "moonshine-medium": ("medium-streaming", ModelArch.MEDIUM_STREAMING),
    }
    folder, arch = arches[model_name]
    model_dir = (
        repo_root()
        / "models"
        / "moonshine"
        / "download.moonshine.ai"
        / "model"
        / f"{folder}-en"
        / "quantized"
    )
    if not model_dir.exists():
        raise RuntimeError(f"Missing Moonshine model directory: {model_dir}")

    load_started = time.perf_counter()
    transcriber = Transcriber(str(model_dir), arch)
    load_seconds = time.perf_counter() - load_started
    out = []
    try:
        for row in rows:
            stream = transcriber.create_stream(update_interval=update_interval)
            chunk_size = max(1, int(row["sampling_rate"] * 0.10))
            started = time.perf_counter()
            stream.start()
            try:
                audio = row["array"].astype(np.float32).tolist()
                for index in range(0, len(audio), chunk_size):
                    stream.add_audio(audio[index : index + chunk_size], row["sampling_rate"])
                transcript = stream.stop()
            finally:
                stream.close()
            text = " ".join(line.text.strip() for line in transcript.lines if line.text.strip())
            out.append((text.strip(), time.perf_counter() - started))
    finally:
        transcriber.close()
    return load_seconds, out, "cpu"


def cuda_available_for_faster_whisper() -> bool:
    if subprocess.run(["where", "nvidia-smi"], capture_output=True, text=True, shell=True).returncode != 0:
        return False
    try:
        import ctranslate2

        devices = ctranslate2.get_cuda_device_count()
        return devices > 0
    except Exception:
        return False


def transcribe_faster_whisper(model_name: str, rows, allow_slow_cpu: bool, requested_device: str):
    from faster_whisper import WhisperModel

    fw_model = model_name.removeprefix("faster-whisper-")
    if requested_device == "cuda":
        return run_faster_whisper(fw_model, rows, "cuda", "float16")
    if requested_device == "cpu":
        if is_large_whisper(fw_model) and not allow_slow_cpu:
            raise SkippedBenchmark(
                "Large faster-whisper model would run on CPU and is disabled by default. "
                "Fix CUDA/cuBLAS or rerun with --allow-slow-cpu."
            )
        return run_faster_whisper(fw_model, rows, "cpu", "float32")

    use_cuda = cuda_available_for_faster_whisper()
    if use_cuda:
        try:
            return run_faster_whisper(fw_model, rows, "cuda", "float16")
        except Exception as error:
            print(f"CUDA faster-whisper failed, retrying CPU: {error}", file=sys.stderr)
            gc.collect()
            if is_large_whisper(fw_model) and not allow_slow_cpu:
                raise SkippedBenchmark(
                    "CUDA failed and CPU fallback for this large model is disabled. "
                    "Fix CUDA/cuBLAS or rerun with --allow-slow-cpu."
                )
            load_seconds, out, device = run_faster_whisper(fw_model, rows, "cpu", "float32")
            return load_seconds, out, f"cpu:float32(cuda_failed:{type(error).__name__})"
    if is_large_whisper(fw_model) and not allow_slow_cpu:
        raise SkippedBenchmark(
            "Large faster-whisper model would run on CPU and is disabled by default. "
            "Fix CUDA/cuBLAS or rerun with --allow-slow-cpu."
        )
    return run_faster_whisper(fw_model, rows, "cpu", "float32")


def is_large_whisper(model_name: str) -> bool:
    return "large" in model_name


def run_faster_whisper(fw_model: str, rows, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    load_started = time.perf_counter()
    model = WhisperModel(fw_model, device=device, compute_type=compute_type)
    load_seconds = time.perf_counter() - load_started

    out = []
    with tempfile.TemporaryDirectory(prefix="parrot-fw-") as tmp:
        tmp = Path(tmp)
        for row in rows:
            wav_path = tmp / f"{safe_id(row['id'])}.wav"
            write_wav(wav_path, row["array"], row["sampling_rate"])
            started = time.perf_counter()
            segments, _info = model.transcribe(
                str(wav_path),
                language="en",
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            out.append((text, time.perf_counter() - started))
    del model
    gc.collect()
    return load_seconds, out, f"{device}:{compute_type}"


def transcribe_parakeet_onnx(rows, threads: int):
    import onnx_asr
    import onnxruntime as ort

    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = max(1, threads)
    sess_options.inter_op_num_threads = 1
    providers = ["CPUExecutionProvider"]
    load_started = time.perf_counter()
    model = onnx_asr.load_model(
        "nemo-parakeet-tdt-0.6b-v3",
        sess_options=sess_options,
        providers=providers,
    )
    load_seconds = time.perf_counter() - load_started
    out = []
    for row in rows:
        started = time.perf_counter()
        text = model.recognize(row["array"], sample_rate=row["sampling_rate"])
        if isinstance(text, list):
            text = " ".join(str(item) for item in text)
        out.append((str(text).strip(), time.perf_counter() - started))
    del model
    gc.collect()
    return load_seconds, out, "cpu:onnxruntime"


def clean_cli_output(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if not line.lower().startswith(("load_backend", "usage:"))]
    return " ".join(lines).strip()


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def worker(args) -> int:
    dataset = dataset_spec(args.dataset)
    rows = load_benchmark_dataset(args.dataset, args.limit, args.max_audio_minutes)
    model_name = args.model
    spec = model_spec(model_name)
    result = {
        "model": model_name,
        "stt": spec["stt"],
        "engine": spec["engine"],
        "mode": spec["mode"],
        "dataset_id": args.dataset,
        "dataset": dataset["name"],
        "dataset_config": dataset["config"],
        "dataset_split": dataset["split"],
        "dataset_description": dataset["description"],
        "limit": len(rows),
        "status": "ok",
        "error": None,
        "rows": [],
    }
    try:
        if model_name.startswith("moonshine-"):
            load_seconds, outputs, device = transcribe_moonshine(
                model_name, rows, args.update_interval
            )
        elif model_name.startswith("faster-whisper-"):
            if model_name == "faster-whisper-large-v3-turbo" and not args.allow_large:
                raise SkippedBenchmark(
                    "Skipped by default because this model is unsafe when CUDA/cuBLAS is not confirmed. "
                    "Rerun with --allow-large after CUDA is fixed."
                )
            load_seconds, outputs, device = transcribe_faster_whisper(
                model_name, rows, args.allow_slow_cpu, args.faster_whisper_device
            )
        elif model_name == "parakeet-tdt-0.6b-v3-onnx":
            load_seconds, outputs, device = transcribe_parakeet_onnx(rows, args.threads)
        else:
            raise RuntimeError(f"Unknown model: {model_name}")

        result["device"] = device
        result["load_seconds"] = load_seconds
        refs = []
        hyps = []
        total_audio = 0.0
        total_transcribe = 0.0
        for row, (hypothesis, seconds) in zip(rows, outputs):
            duration = len(row["array"]) / row["sampling_rate"]
            reference_norm = normalize(row["text"])
            hypothesis_norm = normalize(hypothesis)
            refs.append(reference_norm)
            hyps.append(hypothesis_norm)
            total_audio += duration
            total_transcribe += seconds
            result["rows"].append(
                {
                    "id": row["id"],
                    "duration": duration,
                    "seconds": seconds,
                    "rtf": seconds / duration if duration else None,
                    "wer_normalized": jiwer.wer(reference_norm, hypothesis_norm),
                    "wer_raw": jiwer.wer(row["text"], hypothesis),
                    "cer_normalized": jiwer.cer(reference_norm, hypothesis_norm),
                    "reference": row["text"],
                    "hypothesis": hypothesis,
                }
            )
        result["audio_seconds"] = total_audio
        result["transcribe_seconds"] = total_transcribe
        result["rtf"] = total_transcribe / total_audio if total_audio else None
        result["wer_normalized"] = jiwer.wer(refs, hyps)
        result["cer_normalized"] = jiwer.cer(refs, hyps)
    except SkippedBenchmark as error:
        result["status"] = "skipped"
        result["error"] = str(error)
    except Exception as error:
        result["status"] = "error"
        result["error"] = repr(error)

    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["status"] in {"ok", "skipped"} else 2


def controller(args) -> int:
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    models = parse_models(args.models)
    dataset = dataset_spec(args.dataset)
    print(
        f"Benchmarking {len(models)} model(s) on {args.dataset} "
        f"({dataset['name']}), limit={args.limit}, max_audio_minutes={args.max_audio_minutes}"
    )
    print("Each model runs in a fresh Python process so memory is released after it exits.\n")

    rows = []
    for model in models:
        output = results_dir / f"{safe_id(model)}.json"
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--model",
            model,
            "--limit",
            str(args.limit),
            "--dataset",
            args.dataset,
            "--max-audio-minutes",
            str(args.max_audio_minutes or 0),
            "--update-interval",
            str(args.update_interval),
            "--threads",
            str(args.threads),
            "--output",
            str(output),
            "--faster-whisper-device",
            args.faster_whisper_device,
        ]
        if args.allow_slow_cpu:
            cmd.append("--allow-slow-cpu")
        if args.allow_large:
            cmd.append("--allow-large")
        print(f"==> {model}")
        started = time.perf_counter()
        peak_ram_mb = None
        try:
            proc, peak_ram_mb = run_child_with_timeout(cmd, args.model_timeout_seconds)
        except subprocess.TimeoutExpired:
            data = timeout_result(model, args.dataset, args.limit, args.model_timeout_seconds)
            data["peak_ram_mb"] = peak_ram_mb
            output.write_text(json.dumps(data, indent=2), encoding="utf-8")
            elapsed = time.perf_counter() - started
            print(f"    TIMEOUT after {elapsed:.1f}s")
            rows.append(data)
            continue
        elapsed = time.perf_counter() - started
        data = json.loads(output.read_text(encoding="utf-8"))
        data["peak_ram_mb"] = peak_ram_mb
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        if data["status"] == "ok":
            print(
                f"    WER={data['wer_normalized']:.2%} RTF={data['rtf']:.2f} "
                f"load={data['load_seconds']:.2f}s device={data.get('device')} elapsed={elapsed:.1f}s"
            )
        elif data["status"] == "skipped":
            print(f"    SKIPPED: {data['error']}")
        else:
            print(f"    ERROR: {data['error']}")
        rows.append(data)

    summary_path = results_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "dataset_id",
                "dataset",
                "dataset_config",
                "dataset_split",
                "stt",
                "engine",
                "mode",
                "status",
                "device",
                "load_seconds",
                "audio_seconds",
                "transcribe_seconds",
                "rtf",
                "wer_normalized",
                "cer_normalized",
                "peak_ram_mb",
                "error",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in writer.fieldnames})
    print(f"\nWrote {summary_path}")
    write_report(results_dir, rows)
    return 0


def run_child_with_timeout(cmd, timeout_seconds: int):
    try:
        import psutil
    except Exception:
        return subprocess.run(cmd, cwd=str(repo_root()), timeout=timeout_seconds), None

    proc = subprocess.Popen(cmd, cwd=str(repo_root()))
    ps_proc = psutil.Process(proc.pid)
    peak_ram_mb = 0.0
    started = time.perf_counter()
    while proc.poll() is None:
        try:
            rss = ps_proc.memory_info().rss
            for child in ps_proc.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.Error:
                    pass
            peak_ram_mb = max(peak_ram_mb, rss / (1024 * 1024))
        except psutil.Error:
            pass
        if time.perf_counter() - started > timeout_seconds:
            terminate_process_tree(proc.pid)
            raise subprocess.TimeoutExpired(cmd, timeout_seconds)
        time.sleep(0.5)
    return subprocess.CompletedProcess(cmd, proc.returncode), peak_ram_mb or None


def terminate_process_tree(pid: int) -> None:
    try:
        import psutil

        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for process in children:
            process.kill()
        parent.kill()
        _, alive = psutil.wait_procs(children + [parent], timeout=5)
        for process in alive:
            process.kill()
    except Exception:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)


def timeout_result(model_name: str, dataset_id: str, limit: int, timeout_seconds: int) -> dict:
    spec = model_spec(model_name)
    dataset = dataset_spec(dataset_id)
    return {
        "model": model_name,
        "stt": spec["stt"],
        "engine": spec["engine"],
        "mode": spec["mode"],
        "dataset_id": dataset_id,
        "dataset": dataset["name"],
        "dataset_config": dataset["config"],
        "dataset_split": dataset["split"],
        "limit": limit,
        "status": "timeout",
        "error": f"Timed out after {timeout_seconds}s",
        "rows": [],
    }


def write_report(results_dir: Path, rows: list[dict]) -> None:
    chart_paths = []
    try:
        chart_paths = write_charts(results_dir, rows)
    except Exception as error:
        (results_dir / "report_error.txt").write_text(repr(error), encoding="utf-8")

    report_path = results_dir / "report.html"
    table_rows = []
    for row in rows:
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('model', '')))}</td>"
            f"<td>{html.escape(str(row.get('engine', '')))}</td>"
            f"<td>{html.escape(str(row.get('status', '')))}</td>"
            f"<td>{html.escape(str(row.get('device', '')))}</td>"
            f"<td>{format_metric(row.get('wer_normalized'), percent=True)}</td>"
            f"<td>{format_metric(row.get('cer_normalized'), percent=True)}</td>"
            f"<td>{format_metric(row.get('rtf'))}</td>"
            f"<td>{format_metric(row.get('load_seconds'))}</td>"
            f"<td>{format_metric(row.get('peak_ram_mb'))}</td>"
            f"<td>{html.escape(str(row.get('error') or ''))}</td>"
            "</tr>"
        )
    charts_html = "\n".join(
        f'<h2>{html.escape(path.stem.replace("_", " ").title())}</h2><img src="{html.escape(path.name)}" />'
        for path in chart_paths
    )
    report_path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Project Parrot STT Benchmark</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f7; }}
    img {{ max-width: 920px; width: 100%; display: block; margin: 12px 0 28px; }}
    .note {{ color: #52606d; }}
  </style>
</head>
<body>
  <h1>Project Parrot STT Benchmark</h1>
  <p class="note">Dataset: {html.escape(str(rows[0].get('dataset_id', 'unknown') if rows else 'unknown'))}. Lower WER, CER, RTF, load time, and RAM are better.</p>
  {charts_html}
  <h2>Summary</h2>
  <table>
    <thead><tr><th>Model</th><th>Engine</th><th>Status</th><th>Device</th><th>WER</th><th>CER</th><th>RTF</th><th>Load s</th><th>Peak RAM MB</th><th>Error</th></tr></thead>
    <tbody>{''.join(table_rows)}</tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(f"Wrote {report_path}")


def write_charts(results_dir: Path, rows: list[dict]) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    if not ok_rows:
        return []

    charts = []
    metrics = [
        ("wer_normalized", "WER lower is better", "wer_bar.png", True),
        ("cer_normalized", "CER lower is better", "cer_bar.png", True),
        ("rtf", "RTF lower is better", "rtf_bar.png", False),
        ("load_seconds", "Load Seconds lower is better", "load_time_bar.png", False),
        ("peak_ram_mb", "Peak RAM MB lower is better", "peak_ram_bar.png", False),
    ]
    labels = [row["model"] for row in ok_rows]
    for metric, title, filename, percent in metrics:
        values = [row.get(metric) for row in ok_rows]
        if all(value is None for value in values):
            continue
        plot_values = [(value * 100 if percent and value is not None else value) for value in values]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(labels, plot_values)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
        if percent:
            ax.set_ylabel("Percent")
        fig.tight_layout()
        path = results_dir / filename
        fig.savefig(path, dpi=150)
        plt.close(fig)
        charts.append(path)
    return charts


def format_metric(value, percent: bool = False) -> str:
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value))
    if percent:
        return f"{value:.2%}"
    return f"{value:.2f}"


def parse_models(value: str):
    if value.strip().lower() == "all":
        return DEFAULT_MODELS
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Parrot local STT benchmark")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--models", default="all")
    parser.add_argument("--model", default=None)
    parser.add_argument("--dataset", choices=sorted(DATASET_SPECS), default="dummy")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument(
        "--max-audio-minutes",
        type=float,
        default=0,
        help="Stop after this much dataset audio. Use 0 for no audio-minute cap.",
    )
    parser.add_argument("--update-interval", type=float, default=0.35)
    parser.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    parser.add_argument("--faster-whisper-device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--model-timeout-seconds", type=int, default=900)
    parser.add_argument("--allow-slow-cpu", action="store_true")
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--results-dir", default=str(Path("benchmarks") / "results"))
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.max_audio_minutes <= 0:
        args.max_audio_minutes = None

    if args.worker:
        if not args.model or not args.output:
            raise SystemExit("--worker requires --model and --output")
        return worker(args)
    return controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
