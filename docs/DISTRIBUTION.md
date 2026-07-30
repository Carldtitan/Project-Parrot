# Windows distribution

`scripts\package_windows.ps1` is the supported release entry point. It produces
an NSIS installer under `release\`.

## Installed layout

Electron Builder places application code in `resources\app.asar` and the native
runtime beside it:

```text
resources\
  app.asar
  backend\
    project-parrot.exe
    bin\
      stt_worker\
        stt_worker.exe
        ...
    scripts\
      setup_models.py
    requirements-app.txt
    README.md
```

The Rust engine finds the packaged worker relative to its own executable. The
Electron main process starts the Rust engine with piped standard input and
output:

- Electron sends `quit` over stdin for graceful shutdown.
- Rust emits `PARROT_EVENT` JSON lines for UI status and live transcription.
- Human-readable backend output is retained in the collapsed Diagnostics panel.

## What is bundled

- Electron runtime and the desktop UI.
- Optimized Rust hotkey, audio, formatter-client, and paste engine.
- PyInstaller-packaged Python runtime and both STT implementations.
- Runtime metadata required by ONNX Runtime, onnx-asr, faster-whisper, and
  CTranslate2.

## What downloads after installation

- Parakeet or faster-whisper model weights, cached locally by Hugging Face.
- `qwen2.5:3b-instruct`, pulled and served locally by Ollama.

Weights are not placed in the installer because they make updates unnecessarily
large and have their own upstream licenses and cache lifecycle.

## Release checklist

1. Run `cargo fmt --all -- --check`.
2. Run `cargo test --locked`.
3. Run `npm run check`.
4. Run `scripts\package_windows.ps1`.
5. Install the generated NSIS package on a clean Windows user account.
6. Confirm the app starts in the tray and the settings window can be closed.
7. Optionally pull Qwen using **Install formatter** under Preferences.
8. Dictate into Notepad, a browser text field, and a multiline editor.
9. Confirm **Quit Project Parrot** removes both the Rust and STT worker
   processes.
