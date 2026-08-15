#!/usr/bin/env bash
# Build a double-clickable Keyhold.app bundle for macOS, registered to open
# .vault files (see packaging/Keyhold.spec for the file-association setup).
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean packaging/Keyhold.spec

echo "Built dist/Keyhold.app"

# Tell Launch Services about the new bundle right away, so double-clicking a
# .vault file works without first opening the app or dragging it to
# /Applications. Safe to skip if this helper isn't present.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ -x "$LSREGISTER" ]; then
    "$LSREGISTER" -f "$PWD/dist/Keyhold.app"
    echo "Registered dist/Keyhold.app with Launch Services"
fi
