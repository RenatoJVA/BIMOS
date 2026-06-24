"""BIMOS FastAPI application server and Desktop GUI runner."""

import os
import sys
import time
import threading
import subprocess
import uvicorn
from pathlib import Path
import socket
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from bimos.api.routes import router

app = FastAPI(
    title="BIMOS API",
    version="0.1.0",
    description="Biomolecular Modeling Suite — Backend API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/v1/system/theme")
async def get_system_theme():  # type: ignore[no-untyped-def]
    """Endpoint for the frontend to poll the current OS theme."""
    is_dark = _detect_system_dark_mode()
    return {"theme": "dark" if is_dark else "light"}


@app.get("/api/v1/system/license")
async def get_license_status():  # type: ignore[no-untyped-def]
    """Return the current license status for the frontend badge."""
    from bimos.shared.license import _read_obfuscated, validate_key
    stored = _read_obfuscated()
    if stored is None:
        return {"status": "unlicensed", "type": None}
    valid, msg = validate_key(stored)
    parts = stored.split("|")
    lic_type = parts[1] if len(parts) >= 3 else None
    return {
        "status": "active" if valid else "invalid",
        "type": lic_type,
        "message": msg,
    }


# Resolve path to UI assets (works natively and inside Nuitka)
BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"


if UI_DIR.exists() and UI_DIR.is_dir():
    # Mount the frontend assets at root for direct access
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
else:

    @app.get("/")
    async def root():  # type: ignore[no-untyped-def]
        return {"name": "BIMOS", "version": "0.1.0", "docs": "/docs", "ui": "Not compiled"}


def _detect_system_dark_mode() -> bool:
    """
    Detect whether the OS is currently in dark mode using safe subprocess calls.
    Returns True if dark, False if light.
    """
    # Method 0 (Windows): Read from Windows Registry
    if sys.platform == "win32":
        try:
            import winreg

            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                )
                # AppsUseLightTheme: 1 = light, 0 = dark
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return value == 0  # True if dark (0), False if light (1)
            except (OSError, FileNotFoundError):
                # Registry key not found — fall through
                pass
        except Exception:
            pass

    # Method 1: dconf — reads the actual user value (Ubuntu/Yaru stores it here
    # while gsettings may return the schema default instead of the override).
    try:
        r = subprocess.run(
            ["dconf", "read", "/org/gnome/desktop/interface/color-scheme"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            val = r.stdout.strip().strip("'")
            if val == "prefer-dark":
                return True
            if val == "prefer-light":
                return False
            # empty / unset → fall through
    except Exception:
        pass

    # Method 2: gsettings color-scheme (GNOME 42+ — works when not overridden)
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            val = r.stdout.strip().strip("'")
            if val == "prefer-dark":
                return True
            if val == "prefer-light":
                return False
            # 'default' = follow GTK theme → fall through
    except Exception:
        pass

    # Method 3: GTK theme name containing 'dark'
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and "dark" in r.stdout.lower():
            return True
    except Exception:
        pass

    # Method 4: KDE Plasma
    try:
        r = subprocess.run(
            ["kreadconfig5", "--group", "General", "--key", "ColorScheme"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and "dark" in r.stdout.lower():
            return True
    except Exception:
        pass

    # Method 5: Explicit env-var override (BIMOS_THEME=dark|light)
    env_theme = os.environ.get("BIMOS_THEME", "").lower()
    if env_theme == "dark":
        return True
    if env_theme == "light":
        return False

    return False  # default: light


def _run_server(host: str, port: int):  # type: ignore[no-untyped-def]
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _is_reachable(url: str, timeout: int = 3) -> bool:
    """Check if a URL is reachable via socket connection."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (80 if parsed.scheme == "http" else 443)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def start_server(
    host: str = "127.0.0.1", port: int = 8000, desktop: bool = True, remote_url: str = ""
) -> None:
    """
    Start the FastAPI server. If desktop is True, run it in a background thread
    and start a native pywebview window for a seamless desktop app experience.

    If remote_url is provided, the local server is NOT started, and the UI
    connects directly to the remote instance.
    """
    if remote_url:
        if not _is_reachable(remote_url):
            print(f"\n\033[1;31mError:\033[0m Remote server {remote_url} is unreachable.")
            print(
                "Please ensure the BIMOS API is running on the remote host or unset BIMOS_REMOTE_URL in your .env file."
            )
            sys.exit(1)
        target_url = remote_url
    else:
        if not desktop:
            _run_server(host, port)
            return

        # Start FastAPI in a daemon thread
        t = threading.Thread(target=_run_server, args=(host, port), daemon=True)
        t.start()
        # Give uvicorn a moment to bind before Qt opens the URL
        time.sleep(0.8)
        target_url = f"http://{host}:{port}"

    # Detect OS color scheme BEFORE creating the window so background matches
    is_dark = _detect_system_dark_mode()
    system_theme = "dark" if is_dark else "light"
    bg_color = "#000000" if is_dark else "#f5f5f5"

    # Create native desktop window via pywebview
    import webview

    # Ensure Nuitka traces win32 (winforms imports it; the pywebview plugin omits it).
    if sys.platform == "win32":
        import webview.platforms.win32  # noqa: F401

    # Linux uses Qt/WebEngine; Windows uses WinForms + WebView2; macOS uses Cocoa.
    desktop_gui = "qt" if sys.platform.startswith("linux") else None

    if sys.platform.startswith("linux"):
        # Environment variables to fix common rendering issues on Linux
        os.environ["QTWEBENGINE_DISABLE_GBM"] = "1"
        os.environ["QT_XCB_GL_INTEGRATION"] = "none"
        os.environ["QT_QUICK_BACKEND"] = "software"
        os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"

        # Silence Qt and X11 warnings (especially the "Cannot create platform OpenGL context" one)
        os.environ["QT_LOGGING_RULES"] = (
            "qt.qpa.xcb.gl=false;qt.qpa.gl=false;qt.quick.backend=false;*.debug=false;*.critical=false;*=false"
        )

        # Disable GPU to fully avoid GBM/Vulkan fallback warnings if drivers are problematic
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            "--disable-gpu --num-raster-threads=4 --log-level=3 --silent --disable-logging"
        )

    # Pass the detected system theme as a URL query parameter.
    # QtWebEngine does NOT relay prefers-color-scheme from the OS automatically,
    # so the frontend reads this param to apply the correct theme in Auto mode.
    # We ensure the URL ends with /? or just & if it already has params.
    sep = "&" if "?" in target_url else "?"
    url = f"{target_url}{sep}systemTheme={system_theme}"

    webview.create_window(
        "BIMOS Dashboard",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
        background_color=bg_color,
    )

    def _on_start():  # type: ignore[no-untyped-def]
        icon_path = UI_DIR / "BIMOS-500px.png"
        if icon_path.exists() and hasattr(window, "set_icon") and window is not None:
            window.set_icon(str(icon_path))

        if sys.platform.startswith("linux"):
            try:
                from PyQt6.QtGui import QGuiApplication

                app = QGuiApplication.instance()
                if app:
                    app.setDesktopFileName("bimos")  # type: ignore[attr-defined]
                    app.setApplicationName("BIMOS")
            except ImportError:
                pass

    webview.start(gui=desktop_gui, debug=False, func=_on_start)  # type: ignore[arg-type]

    sys.exit(0)
