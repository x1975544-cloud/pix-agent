#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO="$ROOT/.demo/hello-fastapi"

rm -rf "$DEMO"
mkdir -p "$DEMO"
cp -R "$ROOT/examples/demo-project/." "$DEMO/"
cd "$DEMO"
git init -q
git config user.email "pix-demo@example.com"
git config user.name "PiX Demo"
git add .
git commit -q -m "chore: initialize demo project"

cd "$ROOT"
uv run pix run \
  --workspace "$DEMO" \
  "Add a health check endpoint to this FastAPI project and make its tests pass"
