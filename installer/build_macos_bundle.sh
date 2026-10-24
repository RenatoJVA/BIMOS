#!/usr/bin/env bash
# ============================================================
#  BIMOS — macOS portable bundle builder
#  Requires: Xcode command line tools (clang), codesign, tar
#  Run from the repository root:
#      bash installer/build_macos_bundle.sh [VERSION]
#
#  Produces installer/dist/BIMOS-<version>-macos-arm64.tar.gz containing:
#      BIMOS.app                 native app bundle (Cocoa, no Qt)
#      Uninstall BIMOS.command   standalone purge helper
#      LEEME.txt                 first-run / uninstall instructions
#
#  There is no DMG and no installer: the archive is unpacked and BIMOS.app is
#  run in place (or dragged to /Applications). Nothing is written outside the
#  user's home; configuration and data live in ~/.bimos.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="BIMOS"
BUNDLE_ARCH="arm64"
DIST_DIR="backend/dist/main.dist"
BINARY_NAME="bimos.bin"
BINARY_SRC="${DIST_DIR}/${BINARY_NAME}"
STAGING="installer/staging"
APP_BUNDLE="${STAGING}/${APP_NAME}.app"
HELPER_SRC="installer/assets/Uninstall BIMOS.command"

# ── Version: arg > pyproject.toml > fallback ───────────────
if [ $# -ge 1 ]; then
    VERSION="$1"
elif VERSION=$(grep -E '^version\s*=' backend/pyproject.toml | head -1 | cut -d'"' -f2); then
    :
else
    VERSION="0.1.0"
    echo "Warning: could not read version from backend/pyproject.toml, using ${VERSION}"
fi
ARCHIVE="installer/dist/${APP_NAME}-${VERSION}-macos-${BUNDLE_ARCH}.tar.gz"

# ── Preconditions ─────────────────────────────────────────
if [ "$(uname -s)" != "Darwin" ]; then
    echo "Error: this script only runs on macOS."
    exit 1
fi
if [ "$(uname -m)" != "${BUNDLE_ARCH}" ]; then
    echo "Error: the macOS bundle is arm64-only (host is $(uname -m))."
    exit 1
fi
for tool in clang codesign tar; do
    if ! command -v "$tool" &>/dev/null; then
        echo "Error: required tool not found: ${tool}"
        [ "$tool" = "clang" ] && echo "       Install Xcode command line tools: xcode-select --install"
        exit 1
    fi
done

NUITKA_APP="backend/dist/main.app"
NUITKA_APP_BIN="${NUITKA_APP}/Contents/MacOS/${BINARY_NAME}"

if [ ! -f "$BINARY_SRC" ] && [ ! -x "$NUITKA_APP_BIN" ]; then
    echo "Error: Nuitka output not found (${BINARY_SRC} or ${NUITKA_APP_BIN})"
    echo "       Build it first: python builder.py --target macos --skip-installer"
    exit 1
fi
if [ ! -f "$HELPER_SRC" ]; then
    echo "Error: uninstall helper not found at ${HELPER_SRC}"
    exit 1
fi

# ── Clean staging ─────────────────────────────────────────
echo "==> Building ${APP_NAME}.app (version ${VERSION})..."
rm -rf "$STAGING"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# Nuitka may emit a complete app bundle (PyObjC requires one) or a plain
# standalone tree. Prefer the bundle; fall back to the tree + launcher.
USED_NUITKA_BUNDLE=0
EXECUTABLE_NAME="BIMOS"
if [ -x "$NUITKA_APP_BIN" ]; then
    echo "    source: $NUITKA_APP"
    cp -R "${NUITKA_APP}/." "${APP_BUNDLE}/"
    USED_NUITKA_BUNDLE=1
    # main.py injects -g when the frozen macOS binary gets no CLI arguments,
    # so the Nuitka executable can be the bundle main executable directly.
    EXECUTABLE_NAME="$BINARY_NAME"
else
    echo "    source: $DIST_DIR"
    NESTED_DIR="${APP_BUNDLE}/Contents/Resources/bimos"
    mkdir -p "$NESTED_DIR"
    cp -R "${DIST_DIR}/." "$NESTED_DIR/"
fi
mkdir -p "${APP_BUNDLE}/Contents/MacOS" "${APP_BUNDLE}/Contents/Resources"

if [ "$USED_NUITKA_BUNDLE" -eq 0 ]; then
    # Compiled launcher: a real Mach-O main executable (signable) that execs
    # the Nuitka binary with -g. Nuitka's own bundle already has a directory
    # named BIMOS under MacOS, so this path is only used for main.dist.
    clang -O2 -Wall -Wextra \
        -o "${APP_BUNDLE}/Contents/MacOS/${EXECUTABLE_NAME}" \
        installer/assets/macos_launcher.c
    chmod +x "${APP_BUNDLE}/Contents/MacOS/${EXECUTABLE_NAME}"
fi

# Legal documents travel inside the bundle
for doc in LICENSE NOTICE.md TERMS.md PRIVACY.md; do
    [ -f "$doc" ] && cp "$doc" "${APP_BUNDLE}/Contents/Resources/${doc}"
done

# Icon (generated from the committed iconset; never committed itself)
if [ -f "installer/assets/bimos.icns" ]; then
    cp "installer/assets/bimos.icns" "${APP_BUNDLE}/Contents/Resources/bimos.icns"
else
    echo "Warning: bimos.icns not found, skipping icon."
    echo "         Generate it with: iconutil -c icns installer/assets/bimos.iconset -o installer/assets/bimos.icns"
fi

# ── Info.plist ────────────────────────────────────────────
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
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
    <key>CFBundleExecutable</key>        <string>${EXECUTABLE_NAME}</string>
    <key>CFBundleIconFile</key>          <string>bimos</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
    <key>LSMinimumSystemVersion</key>    <string>12.0</string>
    <key>NSHighResolutionCapable</key>   <true/>
    <key>NSRequiresAquaSystemAppearance</key><false/>
    <!-- The UI and API run on loopback only; App Transport Security must allow
         plain HTTP to 127.0.0.1 (WKWebView blocks it otherwise). -->
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsLocalNetworking</key><true/>
    </dict>
</dict>
</plist>
PLIST

# ── Uninstall helper + readme ─────────────────────────────
install -m 0755 "$HELPER_SRC" "${STAGING}/Uninstall BIMOS.command"
install -m 0755 "$HELPER_SRC" "${APP_BUNDLE}/Contents/Resources/Uninstall BIMOS.command"

cat > "${STAGING}/LEEME.txt" << README
BIMOS ${VERSION} — macOS (Apple Silicon / arm64)
================================================

1. CÓMO EJECUTAR
   - Abre BIMOS.app desde esta carpeta, o arrástrala a /Applications y ábrela
     desde allí. No hay instalador: nada se copia fuera de la carpeta de la app.
   - La primera vez se crea ~/.bimos con la configuración, el workspace, la
     caché y los logs. Ahí vive TODO lo que BIMOS escribe en tu cuenta.

2. PRIMER INICIO (Gatekeeper)
   Este paquete usa firma ad-hoc (no está notarizado por Apple). Si macOS
   bloquea la app: clic derecho sobre BIMOS.app > Abrir > Abrir.
   Alternativa desde Terminal:
       xattr -dr com.apple.quarantine /ruta/a/BIMOS.app

3. QUÉ NO HACE
   - No instala Python, pixi, conda, CUDA, GROMACS, Vina ni Boltz en el sistema.
   - No agrega comandos al PATH ni crea servicios/LaunchAgents.
   - No construye la imagen científica: en macOS no hay NVIDIA/CUDA. Para
     ejecutar trabajos científicos usa un servidor Linux con GPU
     (BIMOS_REMOTE_URL) o consulta la documentación.

4. CÓMO DESINSTALAR (purga completa)
   Doble clic en "Uninstall BIMOS.command". Cierra la app y elimina:
       - BIMOS.app (la copia que estés usando)
       - ~/.bimos
       - el estado web de macOS asociado a org.bimos.app
       - la imagen/contenedores de BIMOS, si existieran
   El helper funciona aunque la app esté dañada o no arranque.
   Para ver qué haría sin borrar nada:
       ./Uninstall\ BIMOS.command --dry-run

5. AYUDA
   Documentación: docs/ dentro del repositorio del proyecto.
   Licencia: LICENSE (GPLv3). Términos y privacidad: TERMS.md, PRIVACY.md.
README

# ── Sign (ad-hoc, inside-out) ─────────────────────────────
echo "==> Signing (ad-hoc)..."

if [ "$USED_NUITKA_BUNDLE" -eq 1 ]; then
    # Nuitka ad-hoc signs its payload (mandatory on macOS), including detached
    # signatures stored in extended attributes. Do NOT run xattr -cr here: it
    # would strip those signatures and codesign --strict would fail. Only the
    # re-sealed bundle changed (Info.plist + resources).
    codesign --force --sign - "$APP_BUNDLE"
else
    xattr -cr "$APP_BUNDLE"
    while IFS= read -r -d '' lib; do
        codesign --force --sign - "$lib" >/dev/null 2>&1 || {
            echo "Error: failed to sign ${lib}"
            exit 1
        }
    done < <(find "$NESTED_DIR" -type f \( -name '*.so' -o -name '*.dylib' \) -print0)

    codesign --force --sign - "${NESTED_DIR}/${BINARY_NAME}"
    codesign --force --sign - "${APP_BUNDLE}/Contents/MacOS/${EXECUTABLE_NAME}"
    codesign --force --sign - "$APP_BUNDLE"
fi

codesign --verify --deep --strict "$APP_BUNDLE"
echo "    signature OK"

# ── Archive ───────────────────────────────────────────────
mkdir -p installer/dist
rm -f "$ARCHIVE"

echo "==> Creating ${ARCHIVE}..."
# Nuitka stores detached signatures for non-Mach-O payload files in extended
# attributes (com.apple.cs.*). They must survive the archive or
# codesign --verify --deep --strict fails after extraction.
COPYFILE_DISABLE=1 tar --xattrs -czf "$ARCHIVE" \
    -C "$STAGING" \
    "${APP_NAME}.app" \
    "Uninstall BIMOS.command" \
    "LEEME.txt"

if ! tar -tzf "$ARCHIVE" | grep -Eq "${APP_NAME}.app/Contents/MacOS/(${BINARY_NAME}|${APP_NAME})$"; then
    echo "Error: archive is missing the app executable"
    exit 1
fi

SIZE_MB=$(du -m "$ARCHIVE" | cut -f1)
SHA256=$(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1)

echo ""
echo "✅  macOS bundle ready: ${ARCHIVE}"
echo "    size   : ${SIZE_MB} MB"
echo "    sha256 : ${SHA256}"
