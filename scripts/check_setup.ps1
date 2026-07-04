$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $PSScriptRoot

Write-Host "Python:"
python --version

Write-Host "`nPython packages:"
$packageCheck = @'
import importlib.util
for name in ["faster_whisper", "sounddevice", "pynput", "pyautogui", "requests"]:
    print(f"{name}: {importlib.util.find_spec(name) is not None}")
'@
$packageCheck | python -

Write-Host "`nOllama models:"
ollama list
