import argparse
import json
import tarfile
import time
import urllib.request
from pathlib import Path

import jiwer
import numpy as np
import soundfile as sf
from moonshine_voice.moonshine_api import ModelArch
from moonshine_voice.transcriber import Transcriber


MINI_LIBRISPEECH_URL = "http://www.openslr.org/resources/31/dev-clean-2.tar.gz"
MODEL_ARCHES = {
    "small": ModelArch.SMALL_STREAMING,
    "medium": ModelArch.MEDIUM_STREAMING,
}


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def extract_tar(tar_path: Path, dest: Path) -> None:
    marker = dest / ".extracted"
    if marker.exists():
        return
    print(f"Extracting {tar_path}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(dest)
    marker.write_text("ok", encoding="utf-8")


def load_references(root: Path) -> dict[str, str]:
    refs = {}
    for transcript_path in root.rglob("*.trans.txt"):
        for line in transcript_path.read_text(encoding="utf-8").splitlines():
            utterance_id, text = line.split(" ", 1)
            refs[utterance_id] = text
    return refs


def load_audio(path: Path) -> tuple[list[float], int]:
    audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
    if isinstance(audio, np.ndarray) and audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio.astype("float32").tolist(), int(sample_rate)


def transcript_text(transcript) -> str:
    return " ".join(line.text.strip() for line in transcript.lines if line.text.strip()).strip()


def stream_transcribe(transcriber: Transcriber, audio: list[float], sample_rate: int, update_interval: float) -> tuple[str, float]:
    stream = transcriber.create_stream(update_interval=update_interval)
    chunk_size = max(1, int(sample_rate * 0.10))
    started = time.perf_counter()
    stream.start()
    try:
        for index in range(0, len(audio), chunk_size):
            stream.add_audio(audio[index : index + chunk_size], sample_rate)
        transcript = stream.stop()
        return transcript_text(transcript), time.perf_counter() - started
    finally:
        stream.close()


def normalize_text(text: str) -> str:
    return jiwer.Compose(
        [
            jiwer.ToLowerCase(),
            jiwer.RemovePunctuation(),
            jiwer.RemoveMultipleSpaces(),
            jiwer.Strip(),
        ]
    )(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Moonshine on Mini LibriSpeech")
    parser.add_argument("--mode", choices=sorted(MODEL_ARCHES), default="small")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--update-interval", type=float, default=0.35)
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks") / "mini_librispeech")
    parser.add_argument("--model-root", type=Path, default=Path("models") / "moonshine")
    args = parser.parse_args()

    archive = args.data_dir / "dev-clean-2.tar.gz"
    download_file(MINI_LIBRISPEECH_URL, archive)
    extract_tar(archive, args.data_dir)

    dataset_root = args.data_dir / "LibriSpeech" / "dev-clean-2"
    refs = load_references(dataset_root)
    audio_paths = sorted(dataset_root.rglob("*.flac"))[: args.limit]
    if not audio_paths:
        raise RuntimeError(f"no FLAC files found under {dataset_root}")

    model_dir = (
        args.model_root
        / "download.moonshine.ai"
        / "model"
        / f"{args.mode}-streaming-en"
        / "quantized"
    )
    if not model_dir.exists():
        raise RuntimeError(f"missing Moonshine model dir: {model_dir}")

    print(f"Model: {args.mode} ({model_dir})")
    print(f"Dataset: Mini LibriSpeech dev-clean-2")
    print(f"Samples: {len(audio_paths)}")

    load_started = time.perf_counter()
    transcriber = Transcriber(str(model_dir), MODEL_ARCHES[args.mode])
    print(f"Load seconds: {time.perf_counter() - load_started:.2f}")

    rows = []
    try:
        for audio_path in audio_paths:
            utterance_id = audio_path.stem
            reference = refs[utterance_id]
            audio, sample_rate = load_audio(audio_path)
            hypothesis, elapsed = stream_transcribe(
                transcriber, audio, sample_rate, args.update_interval
            )
            duration = len(audio) / sample_rate
            wer = jiwer.wer(normalize_text(reference), normalize_text(hypothesis))
            rows.append(
                {
                    "id": utterance_id,
                    "duration": duration,
                    "seconds": elapsed,
                    "rtf": elapsed / duration,
                    "wer": wer,
                    "reference": reference,
                    "hypothesis": hypothesis,
                }
            )
            print(f"{utterance_id}: WER={wer:.2%}, RTF={elapsed / duration:.2f}x")
    finally:
        transcriber.close()

    total_ref = [normalize_text(row["reference"]) for row in rows]
    total_hyp = [normalize_text(row["hypothesis"]) for row in rows]
    avg_wer = jiwer.wer(total_ref, total_hyp)
    avg_rtf = sum(row["rtf"] for row in rows) / len(rows)

    result = {
        "mode": args.mode,
        "update_interval": args.update_interval,
        "samples": len(rows),
        "wer": avg_wer,
        "avg_rtf": avg_rtf,
        "rows": rows,
    }
    output_path = Path("benchmarks") / f"moonshine_{args.mode}_mini_librispeech.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nOverall WER: {avg_wer:.2%}")
    print(f"Average RTF: {avg_rtf:.2f}x")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
