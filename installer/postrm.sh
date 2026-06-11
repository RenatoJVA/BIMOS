#!/bin/sh
# ============================================================
#  BIMOS — Debian post-remove script
# ============================================================
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    # Remove lib dir (binary + .so dependencies)
    rm -rf /opt/bimos/lib
    # Remove optional data dirs if empty
    rmdir /opt/bimos/dockers 2>/dev/null || true
    rmdir /opt/bimos 2>/dev/null || true
    echo "BIMOS has been removed."
fi
