param(
    [switch]$SkipWorkerExe,
    [int]$Threads = [Math]::Max(1, [Environment]::ProcessorCount - 2)
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 -Threads $Threads
cargo build --release

$PackageDir = Join-Path $Root "dist\ProjectParrot"
if (Test-Path $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "scripts") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $PackageDir "bin") | Out-Null

Copy-Item target\release\project-parrot.exe $PackageDir
Copy-Item scripts\stt_worker.py (Join-Path $PackageDir "scripts")
Copy-Item scripts\setup_models.py (Join-Path $PackageDir "scripts")
Copy-Item requirements-app.txt $PackageDir
Copy-Item README.md $PackageDir

if (-not $SkipWorkerExe) {
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
    & $Python -m pip install pyinstaller
    & $Python -m PyInstaller `
        --noconfirm `
        --onedir `
        --name stt_worker `
        --copy-metadata onnx-asr `
        --copy-metadata onnxruntime `
        --copy-metadata faster-whisper `
        --copy-metadata ctranslate2 `
        --copy-metadata huggingface-hub `
        --collect-data onnx_asr `
        scripts\stt_worker.py
    Copy-Item dist\stt_worker (Join-Path $PackageDir "bin\stt_worker") -Recurse
}

@"
Project Parrot Windows package

First run on a new machine:
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements-app.txt
  .venv\Scripts\python.exe scripts\setup_models.py

Run:
  project-parrot.exe --stt parakeet

Fallback:
  project-parrot.exe --stt small-en
"@ | Set-Content -Path (Join-Path $PackageDir "RUN.txt") -Encoding UTF8

Write-Host "Package written to $PackageDir"
