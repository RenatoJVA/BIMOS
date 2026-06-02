#!/bin/sh
# ============================================================
#  BIMOS — Debian post-install script
#  Runs as root after dpkg installs the package.
# ============================================================
set -e

# ── Permissions ───────────────────────────────────────────
chmod 755 /usr/bin/bimos
chmod -R 755 /opt/bimos/dockers

# ── Desktop database ──────────────────────────────────────
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

# ── Icon cache ────────────────────────────────────────────
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/pixmaps || true
fi

echo "BIMOS installed successfully."

# ── Docker Check Warning ──────────────────────────────────
MISSING_DEPS=""
if ! command -v docker >/dev/null 2>&1; then
    MISSING_DEPS="docker (or docker-ce)"
fi
if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
    if [ -n "$MISSING_DEPS" ]; then
        MISSING_DEPS="$MISSING_DEPS and docker-compose-plugin"
    else
        MISSING_DEPS="docker-compose-plugin"
    fi
fi

if [ -n "$MISSING_DEPS" ]; then
    echo "--------------------------------------------------------"
    echo "⚠️  WARNING: BIMOS requires Docker to run molecular pipelines,"
    echo "   but $MISSING_DEPS could not be found."
    echo "   Please make sure Docker and Docker Compose are installed:"
    echo "   https://docs.docker.com/engine/install/"
    echo "--------------------------------------------------------"
fi

echo "Launch with:  bimos BIMOS_GUI"
echo "Or open the BIMOS shortcut in your application menu."
