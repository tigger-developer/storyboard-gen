#!/usr/bin/env bash
# ABOUTME: Build macOS .app bundle and DMG for storyboard-gen GUI.
# ABOUTME: Uses PyInstaller to freeze the PySide6 GUI into a standalone application.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INIT_PY="$PROJECT_ROOT/src/storyboard_gen/__init__.py"

VERSION="${1:-$(grep '__version__' "$INIT_PY" | sed 's/.*"\(.*\)".*/\1/')}"

APP_NAME="Storyboard Gen"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"
BUILD_VENV="$BUILD_DIR/venv"

usage() {
    cat >&2 <<USAGE
Usage: $(basename "$0") [VERSION]

  VERSION   Semantic version (x.y.z). If omitted, reads from __init__.py.

Builds a macOS .app bundle and DMG for the storyboard-gen GUI.

Requirements:
  - python3.12
  - create-dmg (brew install create-dmg) — optional, falls back to hdiutil

Examples:
  $(basename "$0")           # Use version from __init__.py
  $(basename "$0") 0.60.0    # Explicit version
USAGE
    exit 2
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
fi

echo "=== Building $APP_NAME v$VERSION ==="

# Check python3.12 is available
if ! command -v python3.12 > /dev/null 2>&1; then
    echo "Error: python3.12 not found. Install via: brew install python@3.12" >&2
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$DIST_DIR" "$BUILD_DIR"

# Create fresh build venv
echo "Creating build venv..."
python3.12 -m venv "$BUILD_VENV"
# shellcheck disable=SC1091 # Build venv created above
source "$BUILD_VENV/bin/activate"

pip install --upgrade pip -q
pip install pyinstaller -q
pip install "${PROJECT_ROOT}[gui,all]" -q

# Determine icon flag
ICON_FLAG=()
ICON_PATH="$PROJECT_ROOT/resources/icon.icns"
if [[ -f "$ICON_PATH" ]]; then
    ICON_FLAG=(--icon "$ICON_PATH")
    echo "Using icon: $ICON_PATH"
fi

# Build .app bundle
echo "Running PyInstaller..."
pyinstaller --windowed \
    --name "$APP_NAME" \
    "${ICON_FLAG[@]}" \
    --target-arch arm64 \
    --osx-bundle-identifier "com.tigger04.storyboard-gen" \
    --hidden-import storyboard_gen.providers.google \
    --hidden-import storyboard_gen.providers.fal \
    --hidden-import storyboard_gen.providers.replicate \
    --exclude-module QtWebEngine \
    --exclude-module Qt3D \
    --exclude-module QtBluetooth \
    --exclude-module QtNfc \
    --exclude-module QtRemoteObjects \
    --exclude-module QtSensors \
    --exclude-module QtSerialPort \
    --exclude-module QtTest \
    --exclude-module QtPositioning \
    --noconfirm \
    "$PROJECT_ROOT/src/storyboard_gen/gui/__main__.py"

deactivate

# Verify .app exists
if [[ ! -d "$DIST_DIR/$APP_NAME.app" ]]; then
    echo "Error: PyInstaller failed to create $APP_NAME.app" >&2
    exit 1
fi

echo "App bundle created: $DIST_DIR/$APP_NAME.app"

# Create DMG
DMG_NAME="storyboard-gen-gui-${VERSION}.dmg"
echo "Creating DMG: $DMG_NAME"

if command -v create-dmg > /dev/null 2>&1; then
    create-dmg \
        --volname "$APP_NAME" \
        --icon "$APP_NAME.app" 150 200 \
        --app-drop-link 450 200 \
        "$DIST_DIR/$DMG_NAME" \
        "$DIST_DIR/$APP_NAME.app"
else
    echo "create-dmg not found, using hdiutil (install create-dmg for prettier DMGs)..."
    hdiutil create -volname "$APP_NAME" \
        -srcfolder "$DIST_DIR/$APP_NAME.app" \
        -ov \
        -format UDZO \
        "$DIST_DIR/$DMG_NAME"
fi

echo ""
echo "=== Build complete ==="
echo "  App:  $DIST_DIR/$APP_NAME.app"
echo "  DMG:  $DIST_DIR/$DMG_NAME"
