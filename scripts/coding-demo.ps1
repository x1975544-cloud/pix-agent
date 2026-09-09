$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")
uv run python -m pix.coding_demo --print-json
