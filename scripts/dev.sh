#!/usr/bin/env bash
set -euo pipefail

uv sync --extra dev
uv run pix serve --host 0.0.0.0 --port 8000
