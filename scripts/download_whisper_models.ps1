$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$modelDir = Join-Path $root "models\whisper"
New-Item -ItemType Directory -Force -Path $modelDir | Out-Null

$models = @(
    "tiny.en",
    "base.en",
    "small.en"
)

foreach ($model in $models) {
    $fileName = "ggml-$model.bin"
    $target = Join-Path $modelDir $fileName
    if (Test-Path $target) {
        Write-Host "$fileName already exists"
        continue
    }

    $url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$fileName"
    Write-Host "Downloading $fileName..."
    Invoke-WebRequest -Uri $url -OutFile $target
}

Write-Host "Whisper models are ready in $modelDir"
