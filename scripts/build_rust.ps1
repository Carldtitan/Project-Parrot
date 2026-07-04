$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$cmakeCandidates = @(
    "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin",
    "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin",
    "C:\Program Files\CMake\bin"
)

$cmakePath = $cmakeCandidates | Where-Object { Test-Path (Join-Path $_ "cmake.exe") } | Select-Object -First 1

if ($cmakePath) {
    $env:PATH = "$cmakePath;$env:PATH"
    Write-Host "Using CMake from $cmakePath"
} else {
    Write-Host "Missing cmake.exe. Install CMake or Visual Studio C++ Build Tools with CMake."
    exit 1
}

$libclangCandidates = @(
    "C:\Program Files\LLVM\bin\libclang.dll",
    "C:\Program Files (x86)\LLVM\bin\libclang.dll"
)
$libclang = $libclangCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $libclang) {
    $libclang = Get-ChildItem -Path "C:\Program Files", "C:\Program Files (x86)", (Join-Path $root "vendor") -Recurse -Filter "libclang.dll" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if ($libclang) {
    $env:LIBCLANG_PATH = Split-Path -Parent $libclang
    Write-Host "Using libclang from $env:LIBCLANG_PATH"
} else {
    Write-Host "Missing libclang.dll. Install LLVM or place libclang.dll under vendor\llvm."
    Write-Host "Build cannot continue because whisper-rs generates native bindings."
    exit 1
}

$env:GGML_NATIVE = "ON"
Write-Host "Using GGML_NATIVE=ON for CPU-specific whisper.cpp build"

cargo build --release
