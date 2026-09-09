#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
uv sync --extra dev
uv run pix serve --host 0.0.0.0 --port 8000
