"""BIMOS FastAPI application server and Desktop GUI runner."""

import os
import threading
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

# Resolve path to UI assets (works natively and inside Nuitka)
BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"
print(f"[DEBUG] UI_DIR resolved to: {UI_DIR}")
if UI_DIR.exists():
    print(f"[DEBUG] UI_DIR exists. Contents: {os.listdir(UI_DIR)}")
else:
    print("[DEBUG] UI_DIR does NOT exist at that path.")

if UI_DIR.exists() and UI_DIR.is_dir():
    # Mount the frontend assets at root for direct access
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
else:
    @app.get("/")
    async def root():
        return {"name": "BIMOS", "version": "0.1.0", "docs": "/docs", "ui": "Not compiled"}


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

    # Create native desktop window via pywebview
    import webview
    
    # Environment variables to fix common rendering issues on Linux
    os.environ["QTWEBENGINE_DISABLE_GBM"] = "1"
    os.environ["QT_XCB_GL_INTEGRATION"] = "none"
    # Disable GPU to fully avoid GBM/Vulkan fallback warnings if drivers are problematic
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --num-raster-threads=4"
    
    url = f"http://{host}:{port}/"
    
    webview.create_window(
        "BIMOS Dashboard",
        url,
        width=1200,
        height=800,
        min_size=(800, 600),
        background_color="#0f1115"
    )
    
    # Start the native UI event loop forcing QT
    # debug=False helps suppress some Chromium logs
    webview.start(gui='qt', debug=False)
