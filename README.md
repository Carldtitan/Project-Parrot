# Project Parrot

Local Wispr Flow-style dictation MVP for Windows.

## Current Rust MVP

```text
Ctrl+Space push-to-talk
-> Rust global hotkey + microphone capture
-> live audio chunks streamed to Moonshine
-> Moonshine Small/Medium Streaming STT
-> strict local Qwen formatter through Ollama
-> clipboard paste into the focused app
```

No cloud transcription. No TTS. No voice chat model.

## Runtime Roles

- Rust: desktop shell, hotkey, audio capture, streaming transport, paste.
- Moonshine: local streaming speech-to-text.
- Qwen via Ollama: strict final text formatter only.

## Setup

Install Python dependencies for the Moonshine worker:

```powershell
python -m pip install -r requirements.txt
```

Build the Rust app:

```powershell
cargo build --release
```

The app expects a Moonshine model directory:

```text
models\moonshine\download.moonshine.ai\model\small-streaming-en\quantized
models\moonshine\download.moonshine.ai\model\medium-streaming-en\quantized
```

Download the default Small Streaming model:

```powershell
python -m moonshine_voice.download --stt --language en --model-arch 4 --root models\moonshine
```

Download the Medium Streaming accuracy model:

```powershell
python -m moonshine_voice.download --stt --language en --model-arch 5 --root models\moonshine
```

Run small mode:

```powershell
.\target\release\project-parrot.exe --mode small
```

Run accuracy mode:

```powershell
.\target\release\project-parrot.exe --mode medium
```

By default, Qwen is kept loaded in Ollama after warmup:

```powershell
.\target\release\project-parrot.exe --ollama-keep-alive -1m
```

Use another Ollama duration later if you want a user-facing setting, such as
`-1m`, `30m`, `2h`, or `0` to unload immediately after a request.

Or pass an explicit model directory:

```powershell
.\target\release\project-parrot.exe --mode small --moonshine-model-dir C:\path\to\small-streaming-en
```

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
