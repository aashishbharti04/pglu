#!/usr/bin/env bash
# Build the Pglu APK. Run inside the WSL venv from the project root.
#   source ~/.aiodl-venv/bin/activate
#   bash scripts/build_apk.sh
set -euo pipefail

if ! command -v buildozer >/dev/null 2>&1; then
    echo "Buildozer not found. Did you activate the venv (~/.aiodl-venv)?"
    exit 1
fi

echo "Building debug APK (this downloads ~3 GB of Android SDK/NDK on first run)..."
buildozer android debug

echo
echo "Done. APK is at:"
ls -la bin/*.apk 2>/dev/null || echo "  bin/ (no APK yet — check the buildozer output above for errors)"
echo
echo "To install on a phone connected via USB with debugging enabled:"
echo "    buildozer android deploy run"
