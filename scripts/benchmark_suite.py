import argparse
import csv
import html
import subprocess
import sys
from pathlib import Path


DEFAULT_DATASETS = ["common-voice", "librispeech-other", "earnings22"]
METRICS = [
    ("wer_normalized", "WER lower is better", True),
    ("cer_normalized", "CER lower is better", True),
    ("rtf", "RTF lower is better", False),
    ("load_seconds", "Load Seconds lower is better", False),
    ("peak_ram_mb", "Peak RAM MB lower is better", False),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def parse_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def run_suite(args) -> int:
    root = repo_root()
    results_root = Path(args.results_dir)
    results_root.mkdir(parents=True, exist_ok=True)
    datasets = parse_list(args.datasets)
    all_rows = []

    for dataset in datasets:
        dataset_dir = results_root / safe_name(dataset)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(root / "scripts" / "benchmark_stt.py"),
            "--dataset",
            dataset,
            "--models",
            args.models,
            "--limit",
            str(args.limit),
            "--max-audio-minutes",
            str(args.max_audio_minutes),
            "--model-timeout-seconds",
            str(args.model_timeout_seconds),
            "--faster-whisper-device",
            args.faster_whisper_device,
            "--results-dir",
            str(dataset_dir),
        ]
        if args.allow_large:
            cmd.append("--allow-large")
        if args.allow_slow_cpu:
            cmd.append("--allow-slow-cpu")
        print(f"\n=== Dataset: {dataset} ===")
        subprocess.run(cmd, cwd=str(root), check=False)
        summary = dataset_dir / "summary.csv"
        if summary.exists():
            with summary.open(newline="", encoding="utf-8") as handle:
                all_rows.extend(csv.DictReader(handle))
        else:
            print(f"WARNING: missing summary: {summary}")

    write_combined_summary(results_root, all_rows)
    write_combined_report(results_root, all_rows)
    return 0


def write_combined_summary(results_root: Path, rows: list[dict]) -> None:
    path = results_root / "combined_summary.csv"
    fieldnames = [
        "dataset_id",
        "model",
        "stt",
        "engine",
        "mode",
        "status",
        "device",
        "audio_seconds",
        "transcribe_seconds",
        "rtf",
        "wer_normalized",
        "cer_normalized",
        "peak_ram_mb",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})
    print(f"\nWrote {path}")


def write_combined_report(results_root: Path, rows: list[dict]) -> None:
    chart_paths = write_combined_charts(results_root, rows)
    table = []
    for row in rows:
        table.append(
            "<tr>"
            f"<td>{html.escape(row.get('dataset_id', ''))}</td>"
            f"<td>{html.escape(row.get('model', ''))}</td>"
            f"<td>{html.escape(row.get('engine', ''))}</td>"
            f"<td>{html.escape(row.get('status', ''))}</td>"
            f"<td>{html.escape(row.get('device', ''))}</td>"
            f"<td>{metric(row.get('wer_normalized'), True)}</td>"
            f"<td>{metric(row.get('cer_normalized'), True)}</td>"
            f"<td>{metric(row.get('rtf'))}</td>"
            f"<td>{metric(row.get('peak_ram_mb'))}</td>"
            f"<td>{html.escape(row.get('error', '') or '')}</td>"
            "</tr>"
        )
    charts = "\n".join(
        f'<h2>{html.escape(path.stem.replace("_", " ").title())}</h2><img src="{html.escape(path.name)}" />'
        for path in chart_paths
    )
    path = results_root / "combined_report.html"
    path.write_text(
        f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Project Parrot STT Benchmark Suite</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f7; }}
    img {{ max-width: 1100px; width: 100%; display: block; margin: 12px 0 28px; }}
    .note {{ color: #52606d; }}
  </style>
</head>
<body>
  <h1>Project Parrot STT Benchmark Suite</h1>
  <p class="note">Separate dataset reports are in subfolders. This page combines all completed rows.</p>
  {charts}
  <h2>Combined Summary</h2>
  <table>
    <thead><tr><th>Dataset</th><th>Model</th><th>Engine</th><th>Status</th><th>Device</th><th>WER</th><th>CER</th><th>RTF</th><th>Peak RAM MB</th><th>Error</th></tr></thead>
    <tbody>{''.join(table)}</tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )
    print(f"Wrote {path}")


def write_combined_charts(results_root: Path, rows: list[dict]) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok_rows = [row for row in rows if row.get("status") == "ok"]
    if not ok_rows:
        return []

    charts = []
    for key, title, percent in METRICS:
        values = []
        labels = []
        for row in ok_rows:
            raw = row.get(key)
            if raw in (None, ""):
                continue
            value = float(raw)
            values.append(value * 100 if percent else value)
            labels.append(f"{row.get('dataset_id')} | {row.get('model')}")
        if not values:
            continue
        height = max(5, min(14, 0.36 * len(values)))
        fig, ax = plt.subplots(figsize=(12, height))
        ax.barh(labels, values)
        ax.set_title(title)
        ax.grid(axis="x", alpha=0.25)
        if percent:
            ax.set_xlabel("Percent")
        fig.tight_layout()
        path = results_root / f"combined_{key}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        charts.append(path)
    return charts


def metric(value, percent: bool = False) -> str:
    if value in (None, ""):
        return ""
    number = float(value)
    return f"{number:.2%}" if percent else f"{number:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Parrot multi-dataset STT benchmark")
    parser.add_argument("--datasets", default=",".join(DEFAULT_DATASETS))
    parser.add_argument("--models", default="all")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-audio-minutes", type=float, default=20)
    parser.add_argument("--model-timeout-seconds", type=int, default=1800)
    parser.add_argument("--faster-whisper-device", choices=["cpu", "cuda", "auto"], default="cpu")
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--allow-slow-cpu", action="store_true")
    parser.add_argument("--results-dir", default=str(Path("benchmarks") / "suite"))
    return run_suite(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
