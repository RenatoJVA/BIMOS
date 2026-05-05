"""BIMOS FastAPI application server and Desktop GUI runner."""

import os
import time
import threading
import subprocess
import uvicorn
from pathlib import Path
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
async def get_system_theme():
    """Endpoint for the frontend to poll the current OS theme."""
    is_dark = _detect_system_dark_mode()
    return {"theme": "dark" if is_dark else "light"}


# Resolve path to UI assets (works natively and inside Nuitka)
BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"


if UI_DIR.exists() and UI_DIR.is_dir():
    # Mount the frontend assets at root for direct access
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
else:
    @app.get("/")
    async def root():
        return {"name": "BIMOS", "version": "0.1.0", "docs": "/docs", "ui": "Not compiled"}


def _detect_system_dark_mode() -> bool:
    """
    Detect whether the OS is currently in dark mode using safe subprocess calls.
    Returns True if dark, False if light.
    """
    # Method 1: dconf — reads the actual user value (Ubuntu/Yaru stores it here
    # while gsettings may return the schema default instead of the override).
    try:
        r = subprocess.run(
            ["dconf", "read", "/org/gnome/desktop/interface/color-scheme"],
            capture_output=True, text=True, timeout=2,
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
            capture_output=True, text=True, timeout=2,
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
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and "dark" in r.stdout.lower():
            return True
    except Exception:
        pass

    # Method 4: KDE Plasma
    try:
        r = subprocess.run(
            ["kreadconfig5", "--group", "General", "--key", "ColorScheme"],
            capture_output=True, text=True, timeout=2,
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


def _run_server(host: str, port: int):
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_server(host: str = "127.0.0.1", port: int = 8000, desktop: bool = True) -> None:
    """
    Start the FastAPI server. If desktop is True, run it in a background thread
    and start a native pywebview window for a seamless desktop app experience.
    """
    if not desktop:
        _run_server(host, port)
        return

    # Start FastAPI in a daemon thread
    t = threading.Thread(target=_run_server, args=(host, port), daemon=True)
    t.start()
    # Give uvicorn a moment to bind before Qt opens the URL
    time.sleep(0.8)

    # Detect OS color scheme BEFORE creating the window so background matches
    is_dark = _detect_system_dark_mode()
    system_theme = "dark" if is_dark else "light"
    bg_color = "#000000" if is_dark else "#f5f5f5"

    # Create native desktop window via pywebview
    import webview

    # Environment variables to fix common rendering issues on Linux
    os.environ["QTWEBENGINE_DISABLE_GBM"] = "1"
    os.environ["QT_XCB_GL_INTEGRATION"] = "none"
    # Disable GPU to fully avoid GBM/Vulkan fallback warnings if drivers are problematic
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--disable-gpu --disable-software-rasterizer --num-raster-threads=4"
    )

    # Pass the detected system theme as a URL query parameter.
    # QtWebEngine does NOT relay prefers-color-scheme from the OS automatically,
    # so the frontend reads this param to apply the correct theme in Auto mode.
    url = f"http://{host}:{port}/?systemTheme={system_theme}"

    webview.create_window(
        "BIMOS Dashboard",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
        background_color=bg_color,
    )

    # Start the native UI event loop forcing QT
    webview.start(gui="qt", debug=False)

    # Exiting abruptly to bypass QtWebEngine memory cleanup which triggers a Nuitka segfault.
    # The moment webview window is closed, it returns here.
    os._exit(0)
