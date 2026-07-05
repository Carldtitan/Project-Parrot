param(
    [int]$Threads = [Math]::Max(1, [Environment]::ProcessorCount - 2),
    [string]$FormatterModel = "qwen2.5:3b-instruct"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required for setup. Install Python 3.12+ from python.org, then rerun this script."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-app.txt
& $Python scripts\setup_models.py --threads $Threads

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama is required for strict local formatting. Install Ollama, then rerun this script."
}

$InstalledOllamaModels = ollama list
if ($InstalledOllamaModels -notmatch [Regex]::Escape($FormatterModel)) {
    Write-Host ""
    Write-Host "Pulling formatter model: $FormatterModel"
    ollama pull $FormatterModel
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run:"
Write-Host "  cargo run --release -- --stt parakeet --ollama-model $FormatterModel"
