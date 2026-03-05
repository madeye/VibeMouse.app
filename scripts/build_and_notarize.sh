#!/usr/bin/env bash
# Build, sign, notarize, and package VibeMouse.app into a distributable zip.
#
# Usage:
#   bash scripts/build_and_notarize.sh
#
# Prerequisites:
#   - "Developer ID Application" certificate installed in Keychain
#   - Notarization credentials stored via:
#       xcrun notarytool store-credentials "VibeMouse-notarize" \
#         --apple-id "YOUR_EMAIL" --team-id "YOUR_TEAM_ID" --password "APP_SPECIFIC_PASSWORD"
#   - Python 3.10+ virtualenv activated (or will be created in .venv)
#   - macOS 12+
#
# Environment variables:
#   VIBEMOUSE_SIGN_IDENTITY  — signing identity (default: "Developer ID Application")
#   VIBEMOUSE_NOTARIZE_PROFILE — notarytool keychain profile (default: "VibeMouse-notarize")

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

SIGN_IDENTITY="${VIBEMOUSE_SIGN_IDENTITY:-Developer ID Application}"
NOTARIZE_PROFILE="${VIBEMOUSE_NOTARIZE_PROFILE:-VibeMouse-notarize}"
APP_PATH="$PROJECT_DIR/dist/VibeMouse.app"
ENTITLEMENTS="$PROJECT_DIR/entitlements.plist"
VERSION=$(python3 -c "from vibemouse import __version__; print(__version__)" 2>/dev/null || echo "0.0.0")
ZIP_NAME="VibeMouse-${VERSION}.zip"
ZIP_PATH="$PROJECT_DIR/dist/$ZIP_NAME"

# --- 1. Build with PyInstaller ---

# Ensure virtualenv
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d .venv ]; then
        echo "Creating virtualenv..."
        python3 -m venv .venv
    fi
    source .venv/bin/activate
fi

echo "Installing dependencies..."
pip install -e ".[dev]" --quiet

echo "Building VibeMouse.app..."
pyinstaller build/VibeMouse.spec \
    --distpath "$PROJECT_DIR/dist" \
    --workpath "$PROJECT_DIR/build/pyinstaller_work" \
    --noconfirm

# --- 2. Code sign all binaries individually ---

echo ""
echo "Signing embedded binaries..."

# Sign all .so and .dylib files inside the app bundle individually.
# --deep is deprecated for notarization; sign each binary with --timestamp.
find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" \) | while read -r lib; do
    codesign --force --options runtime \
        --timestamp \
        --sign "$SIGN_IDENTITY" \
        "$lib"
done

echo "Signing main executable..."
codesign --force --options runtime \
    --timestamp \
    --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" \
    "$APP_PATH/Contents/MacOS/VibeMouse"

echo "Signing app bundle..."
codesign --force --options runtime \
    --timestamp \
    --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" \
    "$APP_PATH"

# --- 3. Verify signature ---

echo ""
echo "Verifying code signature..."
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

# --- 4. Create zip for notarization ---

echo ""
echo "Creating zip..."
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

# --- 5. Notarize ---

echo ""
echo "Submitting for notarization (this may take several minutes)..."
xcrun notarytool submit "$ZIP_PATH" \
    --keychain-profile "$NOTARIZE_PROFILE" \
    --wait

# --- 6. Staple ---

echo "Stapling notarization ticket to app..."
xcrun stapler staple "$APP_PATH"

# Re-create zip with stapled app
echo "Re-creating zip with stapled app..."
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

# --- 7. Final verification ---

echo ""
echo "Final Gatekeeper check..."
spctl --assess --verbose=2 --type execute "$APP_PATH"
xcrun stapler validate "$APP_PATH"

echo ""
echo "Distribution build complete: $ZIP_PATH"
echo ""
echo "Verification commands:"
echo "  codesign --verify --deep --strict --verbose=2 dist/VibeMouse.app"
echo "  spctl --assess --verbose=2 --type execute dist/VibeMouse.app"
echo "  xcrun stapler validate dist/VibeMouse.app"
