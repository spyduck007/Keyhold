#!/usr/bin/env bash
# Build a double-clickable Keyhold.app bundle for macOS.
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller \
    --name "Keyhold" \
    --windowed \
    --noconfirm \
    --clean \
    --icon "packaging/icon/AppIcon.icns" \
    --osx-bundle-identifier "com.keyhold.desktop" \
    --paths src \
    packaging/macos_entry.py

echo "Built dist/Keyhold.app"
