"""
BIMOS Nuitka Build Script.
Compiles the application into a standalone CLI/Desktop executable.
"""

import subprocess
import sys
import platform
from pathlib import Path


def main():
    print("Building BIMOS with Nuitka...")
    # Ensure frontend UI is present
    if not (Path("bimos") / "ui" / "index.html").exists():
        print("Error: Frontend UI not found in bimos/ui/")
        print(
            "Run 'bun run build' in frontend/ and copy 'dist/' to 'backend/bimos/ui/'"
        )
        sys.exit(1)

    import os
    import shutil

    # Clean previous build artifacts to prevent Nuitka AssertionErrors
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir)

    cores = max(1, int((os.cpu_count() or 1) * 0.5))

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
        "--include-package=qtpy",
        # Do NOT add --include-package=webview here.
        # Nuitka's built-in pywebview plugin traces and manages webview
        # submodule inclusion/exclusion per platform automatically.
        # Forcing it overrides plugin decisions (e.g. excluding android on
        # Windows) and causes a FATAL "Conflict between user and plugin" error.
        "--include-package=rich",
        "--include-package=rich_click",
        "--enable-plugin=pyqt6",
        # (Platform-specific exclusions appended below when needed)
        # Output configuration
        "--output-dir=dist",
        "--output-filename=bimos",
        "--assume-yes-for-downloads",
        "--static-libpython=no",
        "main.py",
    ]

    # On Windows:
    #  1. Attach to the console so CLI commands (e.g. bimos --help) print correctly.
    #     This also prevents double-clicking the .exe from flashing a black terminal.
    #  2. Do NOT manually exclude any webview.platforms.* sub-modules.
    #     Nuitka's built-in pywebview plugin already decides what to include/exclude.
    #     Adding --nofollow-import-to=webview.platforms.* here causes a FATAL
    #     "Conflict between user and plugin decision" error.
    if platform.system().lower() == "windows":
        cmd.insert(len(cmd) - 5, "--windows-console-mode=attach")

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
