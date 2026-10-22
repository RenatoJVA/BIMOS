#!/bin/sh
# ============================================================
#  BIMOS — Debian post-install script
#  Runs as root after dpkg installs the package.
# ============================================================
set -e

# ── Permissions ───────────────────────────────────────────
# The wrapper at /usr/bin/bimos (set by fpm)
chmod 755 /usr/bin/bimos
# The full lib tree (binary + .so dependencies from Nuitka standalone)
if [ -d /opt/bimos/lib ]; then
    chmod -R 755 /opt/bimos/lib
fi
# Docker pipeline files live under /opt/bimos/lib/dockers and are covered by
# the recursive chmod above; there is no second copy to fix permissions on.

# ── Desktop database ──────────────────────────────────────
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

# ── Icon cache ────────────────────────────────────────────
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/pixmaps || true
fi

echo "BIMOS installed successfully."

# ── Container runtime check warning ────────────────────────
# BIMOS prefers Podman but supports Docker; either is acceptable.
RUNTIME=""
if command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
fi

if [ -z "$RUNTIME" ]; then
    echo "--------------------------------------------------------"
    echo "⚠️  WARNING: BIMOS requires a container runtime to run"
    echo "   molecular pipelines, but neither podman nor docker was"
    echo "   found. Install one of:"
    echo "     https://podman.io/docs/installation"
    echo "     https://docs.docker.com/engine/install/"
    echo "--------------------------------------------------------"
fi

echo "Launch with:  bimos -g"
echo "Or open the BIMOS shortcut in your application menu."
