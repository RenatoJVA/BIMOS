#!/usr/bin/env python3
"""
BIMOS Master Builder
====================
Builds the Nuitka binary and then wraps it in a native installer:

  Linux   →  .deb  (via fpm)
  Windows →  .exe  (via NSIS / makensis)
  macOS   →  .dmg  (via create-dmg)

Usage:
    python builder.py [OPTIONS]

Options:
    --skip-frontend    Skip 'bun run build' (use existing dist/)
    --skip-nuitka      Skip Nuitka compilation (use existing binary)
    --skip-installer   Only compile; do not package installer
    --target linux|windows|macos   Override auto-detected platform
    --version X.Y.Z   Override version from pyproject.toml
"""

import argparse
import platform
import re
import shutil
import subprocess
import sys
import os
from pathlib import Path


# ── ANSI helpers ────────────────────────────────────────────────────────────

def info(msg):   print(f"\n\033[1;34m==>\033[0m \033[1m{msg}\033[0m")
def ok(msg):     print(f"\033[1;32m  [OK]\033[0m  {msg}")
def warn(msg):   print(f"\033[1;33m  [WARN]\033[0m  {msg}")
def error(msg):  print(f"\033[1;31m  [ERROR]\033[0m  {msg}")


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    """Run a command and raise on failure."""
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    env_full = {**os.environ, **(env or {})}
    subprocess.run(cmd, cwd=cwd, check=True, env=env_full)


def require(tool: str, hint: str = "") -> str:
    """Abort if a required tool is not on PATH."""
    path = shutil.which(tool)
    if not path:
        error(f"Required tool not found: {tool}")
        if hint:
            print(f"         {hint}")
        sys.exit(1)
    return path


# ── Version helpers ──────────────────────────────────────────────────────────

def read_version(root: Path) -> str:
    pyproject = root / "backend" / "pyproject.toml"
    text = pyproject.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "0.1.0"


# ── Build steps ─────────────────────────────────────────────────────────────

def build_frontend(root: Path):
    info("Building Frontend (bun)...")
    require("bun", "Install bun: https://bun.sh")
    run(["bun", "run", "build"], cwd=root / "frontend")
    ok("Frontend built")


def sync_ui(root: Path):
    info("Syncing Frontend → Backend UI...")
    src = root / "frontend" / "dist"
    dst = root / "backend" / "bimos" / "ui"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    ok(f"Copied {src} → {dst}")


def build_nuitka(root: Path):
    info("Compiling with Nuitka...")
    backend = root / "backend"
    if shutil.which("uv"):
        run(["uv", "run", "python", "build.py"], cwd=backend)
    else:
        run([sys.executable, "build.py"], cwd=backend)
    ok("Nuitka compilation done")


# ── Installer builders ───────────────────────────────────────────────────────

def package_linux_deb(root: Path, version: str):
    info("Packaging → Linux .deb (fpm)...")
    require("fpm", "Install fpm: gem install fpm  OR  apt install ruby-dev && gem install fpm")

    binary = root / "backend" / "dist" / "bimos"
    if not binary.exists():
        error(f"Binary not found: {binary}")
        sys.exit(1)

    out_dir = root / "installer" / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build arg list
    deb_name = f"bimos_{version}_amd64.deb"
    cmd = [
        "fpm",
        "-s", "dir",
        "-t", "deb",
        "--name",           "bimos",
        "--version",        version,
        "--architecture",   "amd64",
        "--description",    "Biomolecular Modeling Suite — virtual screening, docking, MD and QM",
        "--url",            "https://github.com/RenatoJVA/BIMOS",
        "--maintainer",     "Renato J. V. A. <renatojva@example.com>",
        "--license",        "GPLv3",
        "--category",       "science",
        "--deb-recommends", "docker.io (>= 20.0)",
        "--deb-recommends", "docker-compose-plugin (>= 2.0)",
        "--after-install",  str(root / "installer" / "postinst.sh"),
        "--after-remove",   str(root / "installer" / "postrm.sh"),
        "--package",        str(out_dir / deb_name),
        "--force",
    ]

    # Map: source=destination
    file_mappings = [
        (str(binary),                                     "/usr/bin/bimos"),
        (str(root / "backend" / "dockers"),               "/opt/bimos/dockers"),
        (str(root / "backend" / "README.md"),             "/usr/share/doc/bimos/README.md"),
        (str(root / "installer" / "assets" / "bimos.desktop"),
                                                          "/usr/share/applications/bimos.desktop"),
    ]

    icon = root / "installer" / "assets" / "bimos.png"
    if icon.exists():
        file_mappings.append((str(icon), "/usr/share/pixmaps/bimos.png"))
    else:
        warn("bimos.png not found in installer/assets/ — skipping icon in package")

    for src, dst in file_mappings:
        if Path(src).exists():
            cmd.append(f"{src}={dst}")
        else:
            warn(f"Skipping missing file: {src}")

    run(cmd, cwd=root)
    ok(f".deb ready → installer/dist/{deb_name}")


def package_windows_nsis(root: Path, version: str):
    info("Packaging → Windows .exe (NSIS)...")
    makensis = shutil.which("makensis")
    if not makensis:
        # Try common Windows paths if cross-compiling with Wine
        for candidate in [
            r"C:\Program Files (x86)\NSIS\makensis.exe",
            r"C:\Program Files\NSIS\makensis.exe",
        ]:
            if Path(candidate).exists():
                makensis = candidate
                break
    if not makensis:
        error("makensis not found.")
        print("         Linux: sudo apt install nsis")
        print("         macOS: brew install nsis")
        print("         Windows: https://nsis.sourceforge.io/Download")
        sys.exit(1)

    out_dir = root / "installer" / "dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = root / "installer" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Create LICENSE.rtf if missing
    license_file = assets_dir / "LICENSE.rtf"
    if not license_file.exists():
        license_file.write_text(
            r"{\rtf1\ansi\ansicpg1252\deff0\deflang1033"
            r"{\fonttbl{\f0\fnil\fcharset0 Courier New;}}"
            r"{\*\generator Riched20 6.00.3790;}\viewkind4\uc1\pard\f0\fs20"
            r"BIMOS — Biomolecular Modeling Suite\par"
            r"\par"
            r"This software is provided as-is. See project LICENSE for terms.\par"
            r"}", encoding='utf-8'
        )
        ok(f"Created default LICENSE.rtf")

    # Create README.md if missing
    readme_file = root / "README.md"
    if not readme_file.exists():
        readme_file.write_text("# BIMOS\n\nBiomolecular Modeling Suite\n")
        ok("Created default README.md")

    # Verify binary dir exists (from standalone mode)
    binary_dir = root / "backend" / "dist" / "main.dist"
    if not binary_dir.exists():
        error(f"Binary directory not found: {binary_dir}")
        sys.exit(1)

    # Verify dockers dir exists
    dockers_dir = root / "backend" / "dockers"
    if not dockers_dir.exists():
        warn(f"Dockers directory not found: {dockers_dir}")
        dockers_dir.mkdir(parents=True, exist_ok=True)

    nsi_script = root / "installer" / "bimos.nsi"

    # Patch NSI with absolute paths
    nsi_text = nsi_script.read_text(encoding='utf-8')
    nsi_patched = nsi_text.replace(
        'OutFile           "dist\\BIMOS-',
        f'OutFile           "{out_dir}\\BIMOS-',
    )
    
    # Replace file/directory paths with absolute paths
    binary_path = str(binary_dir).replace("\\", "\\\\")
    readme_path = str(readme_file).replace("\\", "\\\\")
    dockers_path = str(dockers_dir).replace("\\", "\\\\")
    license_path = str(license_file).replace("\\", "\\\\")
    
    nsi_patched = nsi_patched.replace("LICENSE_FILE_PATH", license_path)
    nsi_patched = nsi_patched.replace("BINARY_DIR_PATH", binary_path)
    nsi_patched = nsi_patched.replace("README_FILE_PATH", readme_path)
    nsi_patched = nsi_patched.replace("DOCKERS_DIR_PATH", dockers_path)

    # Inject MUI asset definitions if files exist
    mui_defs = []

    if (assets_dir / "bimos.ico").exists():
        icon_path = str(assets_dir / "bimos.ico").replace("\\", "\\\\")
        mui_defs.append(f'!define MUI_ICON                  "{icon_path}"')
        mui_defs.append(f'!define MUI_UNICON                "{icon_path}"')
    else:
        warn("bimos.ico not found — installer will use default icon")

    if (assets_dir / "wizard_banner.bmp").exists():
        banner_path = str(assets_dir / "wizard_banner.bmp").replace("\\", "\\\\")
        mui_defs.append(f'!define MUI_WELCOMEFINISHPAGE_BITMAP   "{banner_path}"')
        mui_defs.append(f'!define MUI_UNWELCOMEFINISHPAGE_BITMAP "{banner_path}"')
    else:
        warn("wizard_banner.bmp not found — welcome page will have no banner")

    if (assets_dir / "header.bmp").exists():
        header_path = str(assets_dir / "header.bmp").replace("\\", "\\\\")
        mui_defs.append('!define MUI_HEADERIMAGE')
        mui_defs.append(f'!define MUI_HEADERIMAGE_BITMAP    "{header_path}"')
        mui_defs.append('!define MUI_HEADERIMAGE_RIGHT')
    else:
        warn("header.bmp not found — installer header will use default")

    # Insert MUI definitions after the placeholder comment
    if mui_defs:
        mui_block = "\n".join(mui_defs)
        nsi_patched = nsi_patched.replace(
            "; OPTIONAL: MUI_ICON, MUI_UNICON (set by builder.py if assets exist)\n"
            "; OPTIONAL: MUI_WELCOMEFINISHPAGE_BITMAP, MUI_UNWELCOMEFINISHPAGE_BITMAP\n"
            "; OPTIONAL: MUI_HEADERIMAGE, MUI_HEADERIMAGE_BITMAP, MUI_HEADERIMAGE_RIGHT",
            mui_block,
        )

    patched_nsi = root / "installer" / "_bimos_patched.nsi"
    patched_nsi.write_text(nsi_patched, encoding='utf-8')

    try:
        run([makensis, f"/DAPP_VERSION={version}", str(patched_nsi)], cwd=root)
    finally:
        patched_nsi.unlink(missing_ok=True)

    ok(f"Windows installer ready → installer/dist/BIMOS-{version}-Setup.exe")


def package_macos_dmg(root: Path, version: str):
    info("Packaging → macOS .dmg (create-dmg)...")
    require("create-dmg", "Install: brew install create-dmg")

    script = root / "installer" / "build_dmg.sh"
    script.chmod(0o755)
    run(["bash", str(script)], cwd=root)
    ok(f"macOS DMG ready → installer/dist/BIMOS-{version}.dmg")


# ── Main ────────────────────────────────────────────────────────────────────

def detect_target() -> str:
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return "linux"


def parse_args():
    p = argparse.ArgumentParser(
        description="BIMOS build + installer packager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--skip-frontend",  action="store_true", help="Skip bun build")
    p.add_argument("--skip-nuitka",    action="store_true", help="Skip Nuitka compilation")
    p.add_argument("--skip-installer", action="store_true", help="Only compile, no installer")
    p.add_argument(
        "--target",
        choices=["linux", "windows", "macos"],
        default=None,
        help="Target platform (default: auto-detect)",
    )
    p.add_argument("--version", default=None, help="Override app version")
    return p.parse_args()


def main():
    args = parse_args()
    root = Path(__file__).parent.resolve()

    target  = args.target or detect_target()
    version = args.version or read_version(root)

    print(f"\n\033[1;35m{'─'*55}\033[0m")
    print(f"\033[1;35m  BIMOS Builder  v{version}  →  {target.upper()}\033[0m")
    print(f"\033[1;35m{'─'*55}\033[0m")

    # ── Step 1: Frontend ────────────────────────────────────
    if not args.skip_frontend:
        build_frontend(root)
        sync_ui(root)
    else:
        warn("Skipping frontend build")

    # ── Step 2: Nuitka binary ───────────────────────────────
    if not args.skip_nuitka:
        build_nuitka(root)
    else:
        warn("Skipping Nuitka compilation")

    # With standalone (no onefile), Nuitka creates main.dist
    binary_dir = root / "backend" / "dist" / "main.dist"
    if not binary_dir.exists() and not args.skip_nuitka:
        error(f"Binary folder not found after build: {binary_dir}")
        sys.exit(1)

    # ── Step 3: Installer ───────────────────────────────────
    if args.skip_installer:
        warn("Skipping installer packaging")
    else:
        if target == "linux":
            package_linux_deb(root, version)
        elif target == "windows":
            package_windows_nsis(root, version)
        elif target == "macos":
            package_macos_dmg(root, version)

    # ── Done ────────────────────────────────────────────────
    print(f"\n\033[1;32m{'─'*55}\033[0m")
    print(f"\033[1;32m  [OK]  Build complete!\033[0m")
    print(f"\033[1;32m{'─'*55}\033[0m")
    binary_path = binary_dir if 'binary_dir' in locals() else root / "backend" / "dist" / "main.dist"
    print(f"  Binary    : {binary_path}")
    print(f"  Installer : {root / 'installer' / 'dist'}/")
    print()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        error(f"Command failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        warn("Build cancelled by user.")
        sys.exit(130)
