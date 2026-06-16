"""
BIMOS Build Script.
Compiles the application into a standalone executable via Nuitka.
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


def _build_frontend() -> None:
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    target_ui = Path("bimos") / "ui"
    if target_ui.exists() and (target_ui / "index.html").exists():
        return
    if not frontend_dir.exists():
        print("Skipping frontend: frontend/ directory not found.")
        return
    print("Building frontend...")
    subprocess.run(["bun", "install"], cwd=str(frontend_dir), check=True)
    subprocess.run(["bun", "run", "build"], cwd=str(frontend_dir), check=True)
    dist_dir = frontend_dir / "dist"
    if dist_dir.exists():
        target_ui.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cp", "-r", str(dist_dir) + "/.", str(target_ui)], check=True)


def main():
    import os
    import shutil

    print("Building BIMOS with Nuitka...")

    # ── Step 1: Ensure frontend UI is built (BD-01: concurrent when possible) ──
    _build_frontend()

    if not (Path("bimos") / "ui" / "index.html").exists():
        print("Error: Frontend UI not found in bimos/ui/")
        print("Run 'bun run build' in frontend/ and copy 'dist/' to 'backend/bimos/ui/'")
        sys.exit(1)

    # ── Step 2: Clean previous build artifacts ──
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir)

    cores = max(1, int((os.cpu_count() or 1) * 0.5))
    is_windows = platform.system().lower() == "windows"
    is_macos = platform.system().lower() == "darwin"
    is_linux = not is_windows and not is_macos

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        f"--jobs={cores}",
        "--standalone",
        # NK-01: Disable bytecode compression for faster startup (Nuitka >= 4.2)
        # "--onefile-no-compression",
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

    # ── NK-03: Platform-specific nofollow imports ──
    if is_windows:
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
    elif is_macos:
        cmd.insert(len(cmd) - 5, "--include-package=qtpy")
        cmd.insert(len(cmd) - 5, "--enable-plugin=pyqt6")
        cmd[cmd.index("--output-filename=bimos")] = "--output-filename=bimos.bin"
    else:
        # Linux
        cmd.insert(len(cmd) - 5, "--include-package=qtpy")
        cmd.insert(len(cmd) - 5, "--enable-plugin=pyqt6")
        cmd[cmd.index("--output-filename=bimos")] = "--output-filename=bimos.bin"

    webview_dir = _webview_package_dir()
    if webview_dir is not None:
        js_dir = webview_dir / "js"
        if js_dir.is_dir():
            cmd.insert(len(cmd) - 5, f"--include-data-dir={js_dir}=webview/js")

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # ── NK-02: UPX compression (if available) ──
    if shutil.which("upx"):
        dist_bin = dist_dir / "main.dist"
        if dist_bin.is_dir():
            print("Compressing with UPX...")
            for f in dist_bin.rglob("bimos*"):
                if f.is_file() and f.name.startswith("bimos"):
                    subprocess.run(["upx", "--best", str(f)], check=False)
                    break

    dist_exe = dist_dir / "main.dist" / "bimos.exe"
    if is_windows and not dist_exe.exists():
        print(f"Error: expected Windows binary missing: {dist_exe}")
        sys.exit(1)


if __name__ == "__main__":
    main()
