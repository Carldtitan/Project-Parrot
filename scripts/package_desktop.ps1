param(
    [switch]$SkipPythonInstall,
    [switch]$SkipNpmInstall,
    [switch]$UseSystemPython
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BuildRoot = Join-Path $Root ".build"
$WorkerOutput = Join-Path $BuildRoot "stt_worker"
$WorkerScratch = Join-Path $BuildRoot "pyinstaller-work-clean"
$IconPath = Join-Path $BuildRoot "icon.png"

Set-Location $Root

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required to package Project Parrot."
    }
}

Assert-Command "cargo"
Assert-Command "npm"
Assert-Command "python"
$Python = if ($UseSystemPython) {
    (Get-Command python).Source
} else {
    Join-Path $Root ".venv\Scripts\python.exe"
}

function New-ParrotIcon {
    param([Parameter(Mandatory = $true)][string]$Path)

    Add-Type -AssemblyName System.Drawing
    $Bitmap = [Drawing.Bitmap]::new(256, 256)
    $Graphics = [Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $Graphics.Clear([Drawing.Color]::FromArgb(28, 23, 33))

    $FontCollection = [Drawing.Text.PrivateFontCollection]::new()
    $FontCollection.AddFontFile(
        (Join-Path $Root "desktop\assets\fonts\SchibstedGrotesk-Variable.ttf")
    )
    $Font = [Drawing.Font]::new(
        $FontCollection.Families[0],
        138,
        [Drawing.FontStyle]::Bold,
        [Drawing.GraphicsUnit]::Pixel
    )
    $TextBrush = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(251, 249, 252))
    $AccentBrush = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(217, 255, 87))
    $Format = [Drawing.StringFormat]::new()
    $Format.Alignment = [Drawing.StringAlignment]::Center
    $Format.LineAlignment = [Drawing.StringAlignment]::Center

    $Graphics.DrawString(
        "P",
        $Font,
        $TextBrush,
        [Drawing.RectangleF]::new(0, -5, 256, 256),
        $Format
    )
    $Graphics.FillPolygon(
        $AccentBrush,
        [Drawing.Point[]]@(
            [Drawing.Point]::new(210, 20),
            [Drawing.Point]::new(238, 48),
            [Drawing.Point]::new(210, 76),
            [Drawing.Point]::new(182, 48)
        )
    )
    $Bitmap.Save($Path, [Drawing.Imaging.ImageFormat]::Png)

    $Format.Dispose()
    $AccentBrush.Dispose()
    $TextBrush.Dispose()
    $Font.Dispose()
    $FontCollection.Dispose()
    $Graphics.Dispose()
    $Bitmap.Dispose()
}

Write-Host "1/4 Building the Rust dictation engine..."
cargo build --release
if ($LASTEXITCODE -ne 0) {
    throw "Rust release build failed."
}

Write-Host "2/4 Building the self-contained STT worker..."
if (-not $UseSystemPython -and -not (Test-Path $Python)) {
    python -m venv .venv
}
if (-not $SkipPythonInstall) {
    if (-not $UseSystemPython) {
        & $Python -m pip install --upgrade pip
    }
    & $Python -m pip install -r requirements-app.txt pyinstaller
}

if (Test-Path $WorkerOutput) {
    $ResolvedBuildRoot = [IO.Path]::GetFullPath($BuildRoot)
    $ResolvedWorkerOutput = [IO.Path]::GetFullPath($WorkerOutput)
    if (-not $ResolvedWorkerOutput.StartsWith($ResolvedBuildRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a worker path outside .build."
    }
    Remove-Item -LiteralPath $WorkerOutput -Recurse -Force
}

& $Python -m PyInstaller `
    --noconfirm `
    --onedir `
    --name stt_worker `
    --distpath $BuildRoot `
    --workpath $WorkerScratch `
    --specpath $BuildRoot `
    --copy-metadata onnx-asr `
    --copy-metadata onnxruntime `
    --copy-metadata faster-whisper `
    --copy-metadata ctranslate2 `
    --copy-metadata huggingface-hub `
    --collect-data onnx_asr `
    --collect-data faster_whisper `
    --collect-data ctranslate2 `
    --exclude-module torch `
    --exclude-module torchvision `
    --exclude-module torchaudio `
    --exclude-module tensorflow `
    --exclude-module keras `
    --exclude-module jax `
    --exclude-module jaxlib `
    --exclude-module matplotlib `
    --exclude-module pandas `
    --exclude-module scipy `
    --exclude-module sklearn `
    --exclude-module cv2 `
    --exclude-module pytest `
    --exclude-module pygame `
    --exclude-module IPython `
    --exclude-module ipykernel `
    --exclude-module jupyter `
    --exclude-module zmq `
    --exclude-module jedi `
    --exclude-module PIL `
    --exclude-module tkinter `
    --exclude-module cryptography `
    --exclude-module nacl `
    --exclude-module psutil `
    scripts\stt_worker.py
if ($LASTEXITCODE -ne 0) {
    throw "STT worker packaging failed."
}

Write-Host "3/4 Installing the Electron build dependencies..."
if (-not $SkipNpmInstall) {
    if (Test-Path (Join-Path $Root "package-lock.json")) {
        npm ci
    } else {
        npm install
    }
    if ($LASTEXITCODE -ne 0) {
        throw "npm dependency installation failed."
    }
}

Write-Host "4/4 Creating the Windows installer..."
if (-not (Test-Path $BuildRoot)) {
    New-Item -ItemType Directory -Path $BuildRoot | Out-Null
}
New-ParrotIcon -Path $IconPath
npm run dist
if ($LASTEXITCODE -ne 0) {
    throw "Electron packaging failed."
}

Write-Host ""
Write-Host "Project Parrot installer is ready under:"
Write-Host "  $Root\release"
