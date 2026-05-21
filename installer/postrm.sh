#!/bin/sh
# ============================================================
#  BIMOS — Debian post-remove script
# ============================================================
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

# Remove optional data dir if empty
rmdir /opt/bimos 2>/dev/null || true

echo "BIMOS has been removed."
