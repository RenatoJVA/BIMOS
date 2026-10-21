#!/usr/bin/env bash
# ============================================================
#  BIMOS — macOS DMG builder
#  Requires: create-dmg  (brew install create-dmg)
#  Run from repo root:
#      bash installer/build_dmg.sh [VERSION]
#
#  VERSION defaults to the value in backend/pyproject.toml.
#  The Nuitka standalone tree (main.dist/) is copied wholesale into
#  Contents/MacOS so the bundled .so dependencies travel with the binary.
# ============================================================
set -euo pipefail

APP_NAME="BIMOS"

# ── Version: arg > pyproject.toml > fallback ───────────────
if [ $# -ge 1 ]; then
    VERSION="$1"
elif VERSION=$(grep -E '^version\s*=' backend/pyproject.toml | head -1 | cut -d'"' -f2); then
    :
else
    VERSION="0.1.0"
    echo "Warning: could not read version from backend/pyproject.toml, using ${VERSION}"
fi

# Nuitka --standalone output: main.dist/ contains the binary + all .so deps
DIST_DIR="backend/dist/main.dist"
BINARY_NAME="bimos.bin"   # build.py renames the output to bimos.bin on macOS/Linux
BINARY_SRC="${DIST_DIR}/${BINARY_NAME}"

APP_BUNDLE="installer/staging/${APP_NAME}.app"
DMG_OUT="installer/dist/${APP_NAME}-${VERSION}.dmg"

# ── Dependency checks ─────────────────────────────────────
if ! command -v create-dmg &>/dev/null; then
    echo "Error: create-dmg not found. Install with: brew install create-dmg"
    exit 1
fi

if [ ! -f "$BINARY_SRC" ]; then
    echo "Error: Nuitka binary not found at ${BINARY_SRC}"
    echo "       Build it first:  python builder.py --target macos --skip-installer"
    exit 1
fi

# ── Build .app bundle ─────────────────────────────────────
echo "==> Building .app bundle (version ${VERSION})..."
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy the whole standalone tree (binary + bundled .so files) into Resources
# so the executable resolves its dependencies through its RPATH ($ORIGIN).
NESTED_DIR="$APP_BUNDLE/Contents/Resources/bimos"
mkdir -p "$NESTED_DIR"
cp -R "${DIST_DIR}/." "$NESTED_DIR/"

# macOS runs CFBundleExecutable with no arguments, and the GUI only starts with
# "-g", so a small shell wrapper is used instead of the raw binary.
cat > "$APP_BUNDLE/Contents/MacOS/${APP_NAME}" << LAUNCHER
#!/bin/sh
# Launch the BIMOS desktop UI. There is no BIMOS_GUI argument -- the GUI is
# started with -g (see backend/bimos/cli/main.py).
DIR=\$(cd "\$(dirname "\$0")" && pwd)
exec "\$DIR/../Resources/bimos/${BINARY_NAME}" -g "\$@"
LAUNCHER
chmod +x "$APP_BUNDLE/Contents/MacOS/${APP_NAME}"

# Ship the legal documents inside the bundle
for doc in LICENSE NOTICE.md TERMS.md PRIVACY.md; do
    [ -f "$doc" ] && cp "$doc" "$APP_BUNDLE/Contents/Resources/$doc"
done

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
    <!-- The GUI is launched by the Contents/MacOS/${APP_NAME} wrapper
         (which passes -g), not by ProgramArguments, which is not a
         valid Info.plist key. -->
</dict>
</plist>
PLIST

echo "   .app bundle created at $APP_BUNDLE"

# ── Build DMG ─────────────────────────────────────────────
mkdir -p "installer/dist"

echo "==> Building DMG with create-dmg..."

# Icon and background are optional assets -- only pass the flags when present.
DMG_ICON_ARGS=()
DMG_BG_ARGS=()
[ -f "installer/assets/bimos.icns" ] \
    && DMG_ICON_ARGS=(--volicon "installer/assets/bimos.icns")
[ -f "installer/assets/dmg_background.png" ] \
    && DMG_BG_ARGS=(--background "installer/assets/dmg_background.png")

create-dmg \
    --volname "${APP_NAME} ${VERSION}" \
    ${DMG_ICON_ARGS[@]+"${DMG_ICON_ARGS[@]}"} \
    ${DMG_BG_ARGS[@]+"${DMG_BG_ARGS[@]}"} \
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
