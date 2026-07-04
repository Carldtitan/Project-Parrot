# STT Benchmark Harness

This benchmark uses public audio only:

```text
hf-internal-testing/librispeech_asr_dummy
```

It runs each STT/model in a fresh Python process so memory is released when that
model finishes.

## Setup Check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_stt_benchmarks.ps1
```

## Fast Smoke Test

```powershell
python scripts\benchmark_stt.py --models all --limit 1 --results-dir benchmarks\smoke
```

## Full Local Benchmark

```powershell
python scripts\benchmark_stt.py --models all --limit 73 --results-dir benchmarks\results
```

## Three-Dataset Product Benchmark

This runs separate reports for each dataset and one combined report:

```powershell
python scripts\benchmark_suite.py --datasets common-voice,librispeech-other,earnings22 --models all --limit 100 --max-audio-minutes 20 --results-dir benchmarks\suite_20min
```

Outputs:

```text
benchmarks\suite_20min\combined_summary.csv
benchmarks\suite_20min\combined_report.html
benchmarks\suite_20min\combined_*.png
benchmarks\suite_20min\common-voice\report.html
benchmarks\suite_20min\librispeech-other\report.html
benchmarks\suite_20min\earnings22\report.html
```

Datasets:

| Dataset id | Source | What it tests |
|---|---|---|
| `common-voice` | `DTU54DL/common-voice` | Common Voice-derived crowd speech with accent labels |
| `librispeech-other` | `openslr/librispeech_asr`, config `other`, split `test` | Standard harder read-speech ASR benchmark |
| `earnings22` | `distil-whisper/earnings22`, config `chunked`, split `test` | Real-world accented professional speech |

## Focused Benchmark

```powershell
python scripts\benchmark_stt.py --models faster-whisper-small.en,faster-whisper-medium.en,faster-whisper-large-v3-turbo --limit 20 --results-dir benchmarks\faster_whisper
```

The benchmark defaults faster-whisper to CPU because this machine currently sees
CUDA but cannot run CTranslate2 CUDA inference. After CUDA/cuBLAS is fixed, use:

```powershell
python scripts\benchmark_stt.py --models faster-whisper-small.en,faster-whisper-medium.en --faster-whisper-device cuda --limit 20 --results-dir benchmarks\faster_whisper_cuda
```

By default, `faster-whisper-large-v3-turbo` is skipped if CUDA is not working,
because CPU fallback can hang for a long time on a weak machine. To force it
anyway:

```powershell
python scripts\benchmark_stt.py --models faster-whisper-large-v3-turbo --limit 5 --allow-large --allow-slow-cpu --results-dir benchmarks\large_cpu_test
```

## Models And Engines

| Model id | STT | Engine |
|---|---|---|
| `moonshine-small` | Moonshine Small Streaming | Moonshine streaming runtime |
| `moonshine-medium` | Moonshine Medium Streaming | Moonshine streaming runtime |
| `faster-whisper-small.en` | Whisper small.en | CTranslate2 via faster-whisper |
| `faster-whisper-medium.en` | Whisper medium.en | CTranslate2 via faster-whisper |
| `faster-whisper-large-v3-turbo` | Whisper large-v3-turbo | CTranslate2 via faster-whisper |
| `parakeet-tdt-0.6b-v3-onnx` | NVIDIA Parakeet TDT 0.6B v3 | ONNX Runtime via onnx-asr |

## Output

Each model writes one JSON file and the controller writes:

```text
benchmarks\results\summary.csv
benchmarks\results\report.html
benchmarks\results\*_bar.png
```

Important columns:

- `wer_normalized`: normalized word error rate, lower is better.
- `cer_normalized`: normalized character error rate, lower is better.
- `rtf`: transcribe seconds divided by audio seconds, lower is faster.
- `load_seconds`: model load time.
- `peak_ram_mb`: peak RAM used by that model's worker process.
- `device`: actual backend used, including CUDA fallback notes.

## Parakeet

The harness uses `onnx-asr`:

```powershell
python -m pip install "onnx-asr[cpu,hub]"
```

The benchmark model id is `nemo-parakeet-tdt-0.6b-v3`. The first run may
download model files from Hugging Face through `onnx-asr`.
