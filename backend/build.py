"""
BIMOS Nuitka Build Script.
Compiles the application into a standalone CLI/Desktop executable.
"""

import importlib.util
import subprocess
import sys
import platform
from pathlib import Path


def _webview_package_dir() -> Path | None:
    spec = importlib.util.find_spec("webview")
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent


def main():
    import os
    import shutil

    print("Building BIMOS with Nuitka...")
    # Ensure frontend UI is present
    if not (Path("bimos") / "ui" / "index.html").exists():
        print("Error: Frontend UI not found in bimos/ui/")
        print(
            "Run 'bun run build' in frontend/ and copy 'dist/' to 'backend/bimos/ui/'"
        )
        sys.exit(1)

    # Clean previous build artifacts to prevent Nuitka AssertionErrors
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir)

    cores = max(1, int((os.cpu_count() or 1) * 0.5))
    is_windows = platform.system().lower() == "windows"

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        f"--jobs={cores}",
        "--standalone",
        # Embed the React static files
        "--include-data-dir=bimos/ui=bimos/ui",
        "--include-data-dir=bimos/scripts=bimos/scripts",
        "--include-data-dir=bimos/infrastructure/config=bimos/infrastructure/config",
        "--include-data-dir=bimos/infrastructure/data=bimos/infrastructure/data",
        "--include-data-dir=bimos/config/defaults=bimos/config/defaults",
        "--include-data-dir=dockers=dockers",
        "--include-data-file=bimos/cli/manual.yaml=bimos/cli/manual.yaml",
        # Ensure packages are traced
        "--include-package=bimos",
        "--include-package=rich",
        "--include-package=rich_click",
        # Output configuration
        "--output-dir=dist",
        "--output-filename=bimos",
        "--assume-yes-for-downloads",
        "--static-libpython=no",
        "main.py",
    ]

    webview_dir = _webview_package_dir()
    if webview_dir is not None:
        js_dir = webview_dir / "js"
        if js_dir.is_dir():
            cmd.insert(len(cmd) - 5, f"--include-data-dir={js_dir}=webview/js")

    if is_windows:
        # Nuitka's pywebview plugin whitelists winforms but omits win32, which
        # winforms imports. Disabling the plugin lets the import graph bundle
        # win32/winforms; we exclude unused backends to limit size.
        cmd.insert(len(cmd) - 5, "--disable-plugin=pywebview")
        for unused in (
            "webview.platforms.android",
            "webview.platforms.gtk",
            "webview.platforms.qt",
            "webview.platforms.cocoa",
            "webview.platforms.cef",
        ):
            cmd.insert(len(cmd) - 5, f"--nofollow-import-to={unused}")
        cmd.insert(len(cmd) - 5, "--include-package=pythonnet")
        cmd.insert(len(cmd) - 5, "--include-package=clr_loader")
        cmd.insert(len(cmd) - 5, "--windows-console-mode=attach")
        cmd.insert(len(cmd) - 5, "--no-deployment-flag=excluded-module-usage")
    else:
        # Linux / macOS: Qt desktop via pywebview + PyQt6 (plugin handles webview)
        cmd.insert(len(cmd) - 5, "--include-package=qtpy")
        cmd.insert(len(cmd) - 5, "--enable-plugin=pyqt6")

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    dist_exe = dist_dir / "main.dist" / "bimos.exe"
    if is_windows and not dist_exe.exists():
        print(f"Error: expected Windows binary missing: {dist_exe}")
        sys.exit(1)


if __name__ == "__main__":
    main()
