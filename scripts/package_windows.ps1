$ErrorActionPreference = "Stop"

# Kept as the stable public entry point for existing documentation and scripts.
& (Join-Path $PSScriptRoot "package_desktop.ps1") @args
exit $LASTEXITCODE
