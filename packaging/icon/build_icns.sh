#!/usr/bin/env bash
# Regenerate AppIcon.icns from AppIcon.png (run generate_icon.py first if the
# design changed). Uses macOS's built-in sips/iconutil, no extra tools needed.
set -euo pipefail
cd "$(dirname "$0")"

rm -rf AppIcon.iconset
mkdir AppIcon.iconset

for size in 16 32 128 256 512; do
    sips -z "$size" "$size" AppIcon.png --out "AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" AppIcon.png --out "AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns AppIcon.iconset -o AppIcon.icns
rm -rf AppIcon.iconset

echo "Built packaging/icon/AppIcon.icns"
