$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)
cargo build --release
