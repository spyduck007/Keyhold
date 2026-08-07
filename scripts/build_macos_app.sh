#!/usr/bin/env bash
# Build a double-clickable USB Vault.app bundle for macOS.
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller \
    --name "USB Vault" \
    --windowed \
    --noconfirm \
    --clean \
    --icon "packaging/icon/AppIcon.icns" \
    --osx-bundle-identifier "com.usbvault.desktop" \
    --paths src \
    packaging/macos_entry.py

echo "Built dist/USB Vault.app"
