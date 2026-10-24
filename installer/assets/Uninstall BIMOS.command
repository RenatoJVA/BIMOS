#!/bin/bash
# ============================================================
#  BIMOS — macOS uninstaller / full purge
#
#  Double-click this file in Finder, or run:
#      ./Uninstall\ BIMOS.command [--dry-run]
#
#  It is standalone on purpose: it keeps working even when BIMOS.app is
#  damaged or cannot start. It first asks the app's own purger (single source
#  of truth) and falls back to the embedded manifest below.
#
#  Environment overrides (testing):
#      BIMOS_APP_PATH   app bundle to remove
#      BIMOS_BASE_PATH  data directory (default: ~/.bimos)
# ============================================================

APP_NAME="BIMOS"
BUNDLE_ID="org.bimos.app"
IMAGE="localhost/bimos/global:latest"
DRY_RUN=0

# BEGIN BIMOS MANIFEST (keep in sync with backend/bimos/infrastructure/purge.py)
MANIFEST_JSON=$(
cat <<'JSON'
{
  "app_paths": [
    "/Applications/BIMOS.app",
    "~/Applications/BIMOS.app"
  ],
  "bundle_id": "org.bimos.app",
  "data_paths": [
    "~/.bimos"
  ],
  "image": "localhost/bimos/global:latest",
  "linux_paths": [
    "~/.config/BIMOS.conf",
    "~/.local/share/BIMOS",
    "~/.cache/BIMOS",
    "~/.pywebview",
    "/opt/bimos",
    "/usr/bin/bimos",
    "/usr/share/applications/bimos.desktop",
    "/usr/share/pixmaps/bimos.png",
    "/usr/share/doc/bimos"
  ],
  "macos_paths": [
    "~/Library/WebKit/org.bimos.app",
    "~/Library/Caches/org.bimos.app",
    "~/Library/HTTPStorages/org.bimos.app",
    "~/Library/Saved Application State/org.bimos.app.savedState",
    "~/Library/Preferences/org.bimos.app.plist",
    "~/Library/Application Support/org.bimos.app"
  ],
  "version": 1,
  "windows_paths": [
    "%LOCALAPPDATA%/pywebview",
    "%LOCALAPPDATA%/BIMOS.exe.WebView2",
    "%APPDATA%/BIMOS"
  ]
}
JSON
)
# END BIMOS MANIFEST

usage() {
    echo "Usage: $(basename "$0") [--dry-run]"
    echo ""
    echo "Removes BIMOS.app, ~/.bimos, the macOS web state and the BIMOS"
    echo "container image. --dry-run only lists what would be deleted."
}

FROM_TEMP=0
for arg in "$@"; do
    case "$arg" in
        --dry-run|-n) DRY_RUN=1 ;;
        --from-temp) FROM_TEMP=1 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown option: $arg"; usage; exit 2 ;;
    esac
done
if [ "$FROM_TEMP" -eq 1 ]; then
    trap 'rm -f "$0"' EXIT
fi

echo "============================================================"
echo " BIMOS uninstaller"
if [ "$DRY_RUN" -eq 1 ]; then
    echo " DRY RUN: nothing will be deleted"
fi
echo "============================================================"
echo ""

# ── Locate the app bundle ─────────────────────────────────
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP=""
CANDIDATES=()
[ -n "${BIMOS_APP_PATH:-}" ] && CANDIDATES+=("$BIMOS_APP_PATH")
CANDIDATES+=("$SCRIPT_DIR/${APP_NAME}.app" "/Applications/${APP_NAME}.app" "$HOME/Applications/${APP_NAME}.app")
for candidate in "${CANDIDATES[@]}"; do
    if [ -d "$candidate" ]; then
        APP="$candidate"
        break
    fi
done

if [ -n "$APP" ]; then
    echo "App bundle : $APP"
else
    echo "App bundle : not found (only user data will be purged)"
fi
echo ""

# If this helper was launched from inside the bundle, deleting the bundle
# mid-run would pull the script out from under bash. Re-exec from a temp copy.
case "$SCRIPT_DIR/" in
    "$APP"/*)
        if [ "$DRY_RUN" -eq 0 ] && [ "$FROM_TEMP" -eq 0 ]; then
            TMP_SCRIPT=$(mktemp "${TMPDIR:-/tmp}/bimos-uninstall.XXXXXX") || exit 1
            cp "$0" "$TMP_SCRIPT"
            chmod +x "$TMP_SCRIPT"
            exec "$TMP_SCRIPT" --from-temp
        fi
        ;;
esac

# ── Quit BIMOS ────────────────────────────────────────────
if [ "$DRY_RUN" -eq 0 ] && [ -n "$APP" ]; then
    osascript -e 'tell application "BIMOS" to quit' >/dev/null 2>&1 || true
    pkill -f "$APP/Contents/Resources/bimos/bimos.bin" >/dev/null 2>&1 || true
    sleep 1
fi

# ── Prefer the app's own purger ───────────────────────────
BINARY_OK=0
BIN="$APP/Contents/Resources/bimos/bimos.bin"
[ -x "$BIN" ] || BIN="$APP/Contents/MacOS/bimos.bin"
if [ -x "$BIN" ]; then
    echo "==> Asking the bundled purger for its manifest..."
    PURGE_ARGS=(uninstall --yes --no-remove-app --json)
    [ "$DRY_RUN" -eq 1 ] && PURGE_ARGS+=(--dry-run)
    if "$BIN" "${PURGE_ARGS[@]}"; then
        BINARY_OK=1
        echo "    bundled purge completed"
    else
        echo "    bundled purge failed or reported residues; using the fallback manifest"
    fi
    echo ""
fi

# ── Fallback: remove every known location ─────────────────
safe_rm() {
    target="$1"
    [ -z "$target" ] && return 0
    case "$target" in
        "/"|"$HOME"|"$HOME/"|"/Applications"|"/System"|"/Library"|"/Users"|"/usr"|"/opt"|"/etc"|"/var"|"/private")
            echo "  REFUSED (protected): $target"
            return 1
            ;;
    esac
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  would remove: $target"
        return 0
    fi
    if [ -L "$target" ]; then
        rm -f "$target"
    else
        rm -rf "$target"
    fi
}

PATHS=()
BASE_DIR="${BIMOS_BASE_PATH:-$HOME/.bimos}"
PATHS+=("$BASE_DIR")
PATHS+=(
    "$HOME/Library/WebKit/$BUNDLE_ID"
    "$HOME/Library/Caches/$BUNDLE_ID"
    "$HOME/Library/HTTPStorages/$BUNDLE_ID"
    "$HOME/Library/Saved Application State/$BUNDLE_ID.savedState"
    "$HOME/Library/Preferences/$BUNDLE_ID.plist"
    "$HOME/Library/Application Support/$BUNDLE_ID"
)

# Custom workspace/cache/logs recorded by the app (paths.json).
if [ -f "$BASE_DIR/paths.json" ]; then
    for key in workspace cache logs; do
        value=$(sed -n "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$BASE_DIR/paths.json" | head -1)
        case "$value" in
            ""|"$BASE_DIR"|"$BASE_DIR"/*) ;;
            /*) PATHS+=("$value") ;;
        esac
    done
fi

if [ "$BINARY_OK" -eq 0 ]; then
    echo "==> Removing user data and web state..."
    for path in "${PATHS[@]}"; do
        safe_rm "$path"
    done

    RUNTIME=$(command -v podman || command -v docker || true)
    if [ -n "$RUNTIME" ]; then
        echo "==> Removing BIMOS containers and image..."
        CONTAINERS=$("$RUNTIME" ps -a --filter "ancestor=$IMAGE" -q 2>/dev/null | tr '\n' ' ')
        if [ -n "$CONTAINERS" ]; then
            if [ "$DRY_RUN" -eq 1 ]; then
                echo "  would remove containers: $CONTAINERS"
            else
                # shellcheck disable=SC2086  # word splitting is intended: IDs
                "$RUNTIME" rm -f $CONTAINERS >/dev/null 2>&1 || true
            fi
        fi
        if "$RUNTIME" image exists "$IMAGE" >/dev/null 2>&1; then
            if [ "$DRY_RUN" -eq 1 ]; then
                echo "  would remove image: $IMAGE"
            else
                "$RUNTIME" rmi -f "$IMAGE" >/dev/null 2>&1 || true
            fi
        fi
    fi
    echo ""
fi

# ── Remove the app bundle itself ──────────────────────────
if [ -n "$APP" ]; then
    case "$APP" in
        */"${APP_NAME}.app") ;;
        *) echo "Refusing to delete unexpected bundle path: $APP"; APP="" ;;
    esac
fi
if [ -n "$APP" ]; then
    echo "==> Removing application bundle..."
    safe_rm "$APP"
    echo ""
fi

# ── Verify ────────────────────────────────────────────────
if [ "$DRY_RUN" -eq 1 ]; then
    echo "DRY RUN complete: nothing was deleted."
    exit 0
fi

echo "==> Verifying..."
REMAINING=()
for path in "${PATHS[@]}"; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        REMAINING+=("$path")
    fi
done
if [ -n "$APP" ] && { [ -e "$APP" ] || [ -L "$APP" ]; }; then
    REMAINING+=("$APP")
fi
RUNTIME=$(command -v podman || command -v docker || true)
if [ -n "$RUNTIME" ] && "$RUNTIME" image exists "$IMAGE" >/dev/null 2>&1; then
    REMAINING+=("container image $IMAGE")
fi

echo ""
if [ "${#REMAINING[@]}" -eq 0 ]; then
    echo "PASS: no BIMOS-owned residue remains."
    echo "(macOS backups, unified logs and Spotlight indexes are system-owned"
    echo " and outside the scope of the application purge.)"
    RESULT=0
else
    echo "FAIL: these residues are still present:"
    for item in "${REMAINING[@]}"; do
        echo "  - $item"
    done
    RESULT=1
fi

echo ""
if [ -t 0 ]; then
    read -r -n 1 -s -p "Press any key to close this window..."
    echo ""
fi
exit "$RESULT"
