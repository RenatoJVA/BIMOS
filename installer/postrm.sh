#!/bin/sh
# ============================================================
#  BIMOS — Debian post-remove script
#
#  ``remove``  keeps user data (upgrade-safe).
#  ``purge``   also removes the installing user's data, as required by the
#              institutional "no residue" policy.
#
#  The package cannot run ``bimos uninstall`` here: by the time postrm runs,
#  /opt/bimos/lib is already gone. The same locations are removed directly.
#  Multi-user hosts: every other user must run ``bimos uninstall`` first.
# ============================================================
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    # Remove lib dir (binary + .so dependencies + bundled dockers)
    rm -rf /opt/bimos/lib
    rmdir /opt/bimos 2>/dev/null || true
fi

if [ "$1" = "purge" ]; then
    # dpkg runs postrm as root; $SUDO_USER identifies the account that ran
    # ``apt purge``. Plain ``apt purge`` from a root shell has no SUDO_USER,
    # and the data can only be removed by that user running bimos uninstall.
    if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
        USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        if [ -n "$USER_HOME" ] && [ "$USER_HOME" != "/" ] && [ -d "$USER_HOME" ]; then
            rm -rf \
                "${USER_HOME:?}/.bimos" \
                "${USER_HOME:?}/.config/BIMOS.conf" \
                "${USER_HOME:?}/.local/share/BIMOS" \
                "${USER_HOME:?}/.cache/BIMOS" \
                "${USER_HOME:?}/.pywebview"
            # Container image lives in the user's rootless Podman/Docker store.
            if command -v podman >/dev/null 2>&1; then
                su -s /bin/sh "$SUDO_USER" -c \
                    'podman rmi -f localhost/bimos/global:latest >/dev/null 2>&1 || true' || true
            elif command -v docker >/dev/null 2>&1; then
                su -s /bin/sh "$SUDO_USER" -c \
                    'docker rmi -f localhost/bimos/global:latest >/dev/null 2>&1 || true' || true
            fi
        fi
    fi
    echo "BIMOS has been removed (user data purged for ${SUDO_USER:-the installing user})."
elif [ "$1" = "remove" ]; then
    echo "BIMOS has been removed. User data in ~/.bimos was kept; run 'bimos uninstall' to purge it."
fi
