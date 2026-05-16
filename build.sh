#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "→ Build Prompt-Live.app"
.venv/bin/pip install --quiet pyinstaller
.venv/bin/pyinstaller prompt-live.spec --clean --noconfirm

echo ""
echo "✓ App générée : dist/Prompt-Live.app"
