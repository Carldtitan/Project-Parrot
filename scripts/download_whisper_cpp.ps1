$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$vendorDir = Join-Path $root "vendor\whisper.cpp"
$zipPath = Join-Path $env:TEMP "whisper-bin-x64.zip"
$whisperCli = Join-Path $vendorDir "Release\whisper-cli.exe"

New-Item -ItemType Directory -Force -Path $vendorDir | Out-Null

if (Test-Path $whisperCli) {
    Write-Host "whisper-cli.exe already exists at $whisperCli"
    exit 0
}

Write-Host "Looking up latest whisper.cpp release..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/whisper.cpp/releases/latest"
$asset = $release.assets | Where-Object { $_.name -eq "whisper-bin-x64.zip" } | Select-Object -First 1

if (-not $asset) {
    throw "Could not find whisper-bin-x64.zip in the latest whisper.cpp release."
}

Write-Host "Downloading $($asset.name)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath

Write-Host "Extracting to $vendorDir..."
Expand-Archive -Force -LiteralPath $zipPath -DestinationPath $vendorDir

$found = Get-ChildItem -Path $vendorDir -Recurse -Filter "whisper-cli.exe" | Select-Object -First 1
if (-not $found) {
    throw "Downloaded archive did not contain whisper-cli.exe."
}

Write-Host "whisper-cli.exe is ready at $whisperCli"
