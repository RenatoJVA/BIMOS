#!/usr/bin/env bash
# ============================================================
#  BIMOS — macOS DMG builder
#  Requires: create-dmg  (brew install create-dmg)
#  Run from repo root:  bash installer/build_dmg.sh
# ============================================================
set -euo pipefail

VERSION="0.1.0"
APP_NAME="BIMOS"
BINARY_SRC="backend/dist/bimos"
APP_BUNDLE="installer/staging/${APP_NAME}.app"
DMG_OUT="installer/dist/${APP_NAME}-${VERSION}.dmg"

# ── Dependency check ──────────────────────────────────────
if ! command -v create-dmg &>/dev/null; then
    echo "Error: create-dmg not found. Install with: brew install create-dmg"
    exit 1
fi

# ── Build .app bundle ─────────────────────────────────────
echo "==> Building .app bundle..."
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy binary
cp "$BINARY_SRC" "$APP_BUNDLE/Contents/MacOS/${APP_NAME}"
chmod +x "$APP_BUNDLE/Contents/MacOS/${APP_NAME}"

# Copy icon
cp "installer/assets/bimos.icns" "$APP_BUNDLE/Contents/Resources/bimos.icns" 2>/dev/null || \
    echo "Warning: bimos.icns not found, skipping icon."

# Write Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>              <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>       <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>        <string>org.bimos.app</string>
    <key>CFBundleVersion</key>           <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key><string>${VERSION}</string>
    <key>CFBundleExecutable</key>        <string>${APP_NAME}</string>
    <key>CFBundleIconFile</key>          <string>bimos</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>LSMinimumSystemVersion</key>    <string>12.0</string>
    <key>NSHighResolutionCapable</key>   <true/>
    <key>NSRequiresAquaSystemAppearance</key><false/>
    <!-- Pass BIMOS_GUI arg so the bundle opens the GUI automatically -->
    <key>ProgramArguments</key>
    <array>
        <string>bimos</string>
        <string>BIMOS_GUI</string>
    </array>
</dict>
</plist>
PLIST

echo "   .app bundle created at $APP_BUNDLE"

# ── Build DMG ─────────────────────────────────────────────
mkdir -p "installer/dist"

echo "==> Building DMG with create-dmg..."
create-dmg \
    --volname "${APP_NAME} ${VERSION}" \
    --volicon "installer/assets/bimos.icns" \
    --background "installer/assets/dmg_background.png" \
    --window-pos  200 120 \
    --window-size 660 400 \
    --icon-size   128 \
    --icon "${APP_NAME}.app" 165 185 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link  495 185 \
    --no-internet-enable \
    "$DMG_OUT" \
    "installer/staging/"

echo ""
echo "✅  DMG ready: $DMG_OUT"
