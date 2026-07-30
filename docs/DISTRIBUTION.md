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

- Electron sends control commands over stdin for hands-free start/finish,
  cancel, re-paste, and graceful shutdown.
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
3. Run `npm test`.
4. Run `npm run test:e2e`.
5. Run `npm run verify:live-stt`.
6. Run `npm run verify:long-stt` when the Parakeet model is available.
7. Run `npm run verify:extended-stt` to exercise minute-scale segmentation.
8. Run
   `python -m unittest scripts.test_stt_worker scripts.test_cleanup_pipeline`.
9. Run `scripts\package_windows.ps1`.
10. Install the generated NSIS package on a clean Windows user account.
11. Confirm the app starts in the tray and the settings window can be closed.
12. Test push-to-talk, hands-free, cancel, and paste-previous in Notepad.
13. Dictate continuously for at least one minute and compare the final text
    with the live preview; neither may omit a section.
14. Dictate a three-step procedure without saying numbers; confirm Qwen returns
    a numbered list in a multiline editor.
15. End a sentence immediately before releasing push-to-talk; confirm the final
    words survive the full recognition pass.
16. Add a dictionary entry and snippet, then confirm both affect a dictation.
17. Confirm history and usage totals persist after restarting the app.
18. Optionally pull Qwen using **Install formatter** under Advanced settings.
19. Confirm **Quit Project Parrot** removes both the Rust and STT worker
    processes.
