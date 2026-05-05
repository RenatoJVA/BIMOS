#!/usr/bin/env python3
import subprocess
import shutil
import sys
import os
from pathlib import Path

def print_step(msg):
    print(f"\n\033[1;34m==>\033[0m \033[1m{msg}\033[0m")

def run_command(cmd, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)

def main():
    root_dir = Path(__file__).parent.resolve()
    frontend_dir = root_dir / "frontend"
    backend_dir = root_dir / "backend"
    ui_dir = backend_dir / "bimos" / "ui"

    # 1. Build Frontend
    print_step("Building Frontend with Bun...")
    run_command(["bun", "run", "build"], cwd=frontend_dir)

    # 2. Sync UI to Backend
    print_step("Syncing UI to Backend...")
    if ui_dir.exists():
        shutil.rmtree(ui_dir)
    ui_dir.mkdir(parents=True)
    
    dist_dir = frontend_dir / "dist"
    for item in dist_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, ui_dir / item.name)
        else:
            shutil.copy2(item, ui_dir / item.name)
    print(f"Copied {dist_dir} to {ui_dir}")

    # 3. Build Backend Executable (Nuitka)
    print_step("Compiling Backend with Nuitka...")
    if shutil.which("uv"):
        run_command(["uv", "run", "python", "build.py"], cwd=backend_dir)
    else:
        run_command([sys.executable, "build.py"], cwd=backend_dir)

    print_step("Success! BIMOS has been built.")
    print(f"Executable located at: {backend_dir / 'dist' / 'bimos'}")

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\n\033[1;31mError during build:\033[0m {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\033[1;31mUnexpected error:\033[0m {e}")
        sys.exit(1)
