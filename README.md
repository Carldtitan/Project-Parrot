# Project Parrot

Local Wispr Flow-style dictation MVP for Windows.

## Current MVP

```text
Ctrl+Space push-to-talk
-> Rust global hotkey + microphone capture
-> kept-alive local STT worker
-> Parakeet ONNX CPU by default
-> faster-whisper small.en CPU fallback
-> strict local Qwen2.5 3B Instruct formatter through Ollama
-> clipboard paste into the focused app
```

No cloud transcription. No TTS. No voice chat model. No GPU requirement.

## Runtime Roles

- Rust: desktop shell, hotkey, audio capture, worker lifecycle, paste.
- Parakeet ONNX: default local speech-to-text through ONNX Runtime CPU.
- faster-whisper `small.en`: fallback local speech-to-text through CTranslate2 CPU.
- Qwen2.5 3B Instruct via Ollama: strict final text formatter only.

## Streaming Behavior

Parakeet TDT v3 through the current ONNX path is an offline recognizer, not a
native stateful streaming graph. Project Parrot keeps the model loaded and gives
a streaming user experience by repeatedly transcribing a rolling window while
recording.

```text
while speaking: rolling live preview over recent audio
on release: final full-utterance STT pass
after final: strict Qwen formatting and paste
```

The final paste uses the full utterance, not the unstable live preview.

## Setup

Run the Windows setup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

This creates `.venv`, installs app runtime packages, downloads/checks Parakeet
ONNX and faster-whisper `small.en`, and runs smoke tests.

Build the Rust app:

```powershell
cargo build --release
```

Run default Parakeet mode:

```powershell
.\target\release\project-parrot.exe --stt parakeet
```

Run fallback mode:

```powershell
.\target\release\project-parrot.exe --stt small-en
```

Useful options:

```powershell
.\target\release\project-parrot.exe --stt parakeet --update-interval 0.7 --live-window-seconds 8
.\target\release\project-parrot.exe --stt parakeet --stt-threads 6
.\target\release\project-parrot.exe --ollama-keep-alive -1m
```

By default, Qwen is kept loaded in Ollama after warmup. The Rust app defaults
to `qwen2.5:3b-instruct`, which was the best latency/quality balance in the
local Qwen2.5 cleanup benchmark under `benchmarks/cleanup_qwen25_instruct`.

## Packaging

Fast Windows packaging path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package_windows.ps1
```

This writes:

```text
dist\ProjectParrot
```

The package includes the Rust executable, scripts, app requirements, and
optional PyInstaller-built STT worker folder. A new machine still needs model
download through `scripts\setup_models.py` unless you distribute the Hugging
Face cache separately.

## Formatter Behavior

The local Qwen formatter is intentionally strict:

- Preserves words, order, clauses, and names.
- Fixes capitalization, punctuation, and spacing.
- Adapts to the writing mood already present in the transcript.
- Does not summarize, rewrite, answer, or add new meaning.
- Falls back to raw STT if the formatted text drifts too far.

## Usage

1. Click into any text box.
2. Hold `Ctrl+Space`.
3. Speak.
4. Release `Space`.
5. The formatted text is pasted at the cursor.

Quit with `Ctrl+Alt+Q`, or press `Ctrl+C` in the terminal.
