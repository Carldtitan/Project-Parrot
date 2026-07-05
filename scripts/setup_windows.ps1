param(
    [int]$Threads = [Math]::Max(1, [Environment]::ProcessorCount - 2),
    [string]$FormatterModel = "qwen2.5:3b-instruct"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is required for setup. Install Python 3.12+ from python.org, then rerun this script."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
Invoke-Checked $Python -m pip install --upgrade pip
Invoke-Checked $Python -m pip install -r requirements-app.txt
Invoke-Checked $Python scripts\setup_models.py --threads $Threads

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama is required for strict local formatting. Install Ollama, then rerun this script."
}

$InstalledOllamaModels = ollama list
if ($InstalledOllamaModels -notmatch [Regex]::Escape($FormatterModel)) {
    Write-Host ""
    Write-Host "Pulling formatter model: $FormatterModel"
    Invoke-Checked "ollama" pull $FormatterModel
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run:"
Write-Host "  cargo run --release -- --ollama-model $FormatterModel"
