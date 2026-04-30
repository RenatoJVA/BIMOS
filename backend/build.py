"""
BIMOS Nuitka Build Script.
Compiles the application into a standalone CLI/Desktop executable.
"""
import subprocess
import sys
from pathlib import Path

def main():
    print("Building BIMOS with Nuitka...")
    # Ensure frontend UI is present
    if not (Path("bimos") / "ui" / "index.html").exists():
        print("Error: Frontend UI not found in bimos/ui/")
        print("Run 'bun run build' in frontend/ and copy 'dist/' to 'backend/bimos/ui/'")
        sys.exit(1)

    import os
    cores = max(1, int((os.cpu_count() or 1) * 0.8))

    cmd = [
        sys.executable, "-m", "nuitka",
        f"--jobs={cores}",
        "--standalone",
        "--onefile",
        # Embed the React static files
        "--include-data-dir=bimos/ui=bimos/ui",
        # Ensure packages are traced
        "--include-package=bimos",
        "--include-package=qtpy",
        "--include-package=webview",
        "--enable-plugin=pyqt6",
        # Output configuration
        "--output-filename=bimos-cli",
        "--assume-yes-for-downloads",
        "--static-libpython=no",
        "main.py"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()
