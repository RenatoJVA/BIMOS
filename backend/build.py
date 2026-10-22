"""
BIMOS Build Script.
Compiles the application into a standalone executable via Nuitka.
"""

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# H-01: artefacts that identify a released BIMOS build. Anything hashed here is
# what a licensee verifies before installing, so the list is intentionally narrow.
_CHECKSUM_SUFFIXES = (".exe", ".bin", ".deb", ".dmg", ".AppImage", ".msi")
_CHECKSUM_MANIFEST = "SHA256SUMS"


def _strip_debug_binaries(dist_dir: Path) -> None:
    """H-02: drop ELF debug/symbol tables from the compilation output.

    Nuitka 4.2+ rejects ``--strip`` (option removed), so the equivalent is
    applied post-compilation to every ELF artifact that goes into the
    distribution. Silently skipped when ``strip`` is unavailable (Windows).
    """
    strip = shutil.which("strip")
    if not strip:
        return
    seen: set[Path] = set()
    for elf in dist_dir.rglob("*"):
        if elf.is_symlink() or not elf.is_file():
            continue
        with elf.open("rb") as handle:
            probe = handle.read(4)
        if probe != b"\x7fELF" or elf in seen:
            continue
        seen.add(elf)
        subprocess.run([strip, "--strip-all", str(elf)], check=False, capture_output=True)


# NSS runtime bits that QtWebEngine needs at runtime but Nuitka standalone omits
# (it classifies libnss3/libnssutil3 etc. as system libraries). Without them the
# bundled libsmime3.so resolves the host's older NSS and the import of
# PyQt6.QtWebEngineCore dies with "version `NSSUTIL_3.101' not found".
_NSS_LIBS = (
    "libnss3.so",
    "libnssutil3.so",
    "libssl3.so",
    "libnssckbi.so",
    "libfreebl3.so",
    "libfreebl3.chk",
    "libfreeblpriv3.so",
    "libfreeblpriv3.chk",
    "libsoftokn3.so",
    "libsoftokn3.chk",
    "libsmime3.so",
    "libnspr4.so",
    "libplc4.so",
    "libplds4.so",
)


def _bundle_nss_libs(dist_dir: Path) -> None:
    """Ship the NSS runtime from the build environment next to the binary.

    QtWebEngineCore links (and dlopens) against NSS; the standalone bundle only
    carries the pieces Nuitka traced, so the loader falls back to the host NSS,
    which is frequently older than the one the environment was built against.
    Copying the environment's own NSS into ``dist_dir`` root (where the
    ``$ORIGIN`` RPATH of every bundled library points) makes the resolution
    deterministic on any host.
    """
    if platform.system().lower() != "linux":
        return
    source_dir = Path(sys.prefix) / "lib"
    if not source_dir.is_dir():
        print(f"Warning: {source_dir} not found; NSS bundling skipped.")
        return
    copied, present = [], []
    for name in _NSS_LIBS:
        target = dist_dir / name
        if target.exists():
            present.append(name)
            continue
        source = source_dir / name
        if not source.exists():
            print(f"Warning: {name} not found in {source_dir}; skipping.")
            continue
        shutil.copy2(source, target)
        copied.append(name)
    if copied:
        print(f"NSS runtime bundled from env: {', '.join(copied)} ({len(copied)} file(s)); "
              f"{len(present)} already present.")


def _write_checksums(dist_dir: Path) -> Path | None:
    """Emit ``SHA256SUMS`` for the released artefacts under *dist_dir*.

    An unsigned binary is indistinguishable from a tampered one, so every
    distribution must ship this manifest next to the artefacts. Returns the
    manifest path, or ``None`` when there is nothing to hash.
    """
    import hashlib

    def _is_released(path: Path) -> bool:
        rel = path.relative_to(dist_dir)
        if path.suffix.lower() not in _CHECKSUM_SUFFIXES:
            return False
        # Nuitka intermediates live under main.<mode>.build; releases ship main.dist
        return not any(part.endswith(".build") for part in rel.parts)

    targets = sorted(path for path in dist_dir.rglob("*") if path.is_file() and _is_released(path))
    if not targets:
        print("Warning: no distributable artefact found; skipping SHA256SUMS.")
        return None

    lines = []
    for path in targets:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {path.relative_to(dist_dir).as_posix()}")

    manifest = dist_dir / _CHECKSUM_MANIFEST
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {manifest} ({len(targets)} artefact(s)):")
    for line in lines:
        print(f"  {line}")
    return manifest


def _webview_package_dir() -> Path | None:
    spec = importlib.util.find_spec("webview")
    if spec is None or not spec.origin:
        return None
    return Path(spec.origin).resolve().parent


def _build_frontend(skip: bool = False) -> None:
    """Build frontend sources and sync ``frontend/dist`` into ``bimos/ui``.

    The sync always replaces ``bimos/ui`` so stale hashed assets from a
    previous build (e.g. old ESMFold-era bundles) cannot leak into the
    packaged binary.
    """
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    target_ui = Path("bimos") / "ui"
    if not frontend_dir.exists():
        print("Skipping frontend: frontend/ directory not found.")
        return
    if skip:
        print("Skipping frontend build (--skip-frontend).")
    else:
        print("Building frontend...")
        subprocess.run(["bun", "install"], cwd=str(frontend_dir), check=True)
        subprocess.run(["bun", "run", "build"], cwd=str(frontend_dir), check=True)
    dist_dir = frontend_dir / "dist"
    if not (dist_dir / "index.html").exists():
        print(f"Error: frontend build output missing: {dist_dir / 'index.html'}")
        sys.exit(1)
    if target_ui.exists():
        shutil.rmtree(target_ui)
    shutil.copytree(dist_dir, target_ui)
    print(f"Synced {dist_dir} → {target_ui}")


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Build BIMOS frontend + Nuitka binary.")
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip 'bun run build'; sync existing frontend/dist into bimos/ui.",
    )
    parser.add_argument(
        "--skip-nuitka",
        action="store_true",
        help="Only build/sync the frontend; do not compile with Nuitka.",
    )
    args = parser.parse_args()

    print("Building BIMOS with Nuitka...")

    # ── Step 1: Ensure frontend UI is built (BD-01) ──
    _build_frontend(skip=args.skip_frontend)

    if not (Path("bimos") / "ui" / "index.html").exists():
        print("Error: Frontend UI not found in bimos/ui/")
        print("Run 'bun run build' in frontend/ and copy 'dist/' to 'backend/bimos/ui/'")
        sys.exit(1)

    if args.skip_nuitka:
        print("Frontend ready. Skipping Nuitka compilation.")
        return

    # ── Step 2: Clean previous build artifacts ──
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("Cleaning previous build artifacts...")
        shutil.rmtree(dist_dir)

    cores = max(1, int((os.cpu_count() or 1) * 0.8))
    is_windows = platform.system().lower() == "windows"
    is_macos = platform.system().lower() == "darwin"

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
        "--include-data-files=bimos/scripts/*.py=bimos/scripts/",
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

    # H-02. Strip debug/symbol tables from all ELF artifacts produced
    # (Nuitka >= 4.2 does not accept ``--strip`` anymore, so we do it here).
    _strip_debug_binaries(dist_dir)

    # Bundle the environment's NSS runtime next to the binary: Nuitka standalone
    # omits libnss3/libnssutil3 (treated as system libraries), and without them
    # QtWebEngine resolves the host NSS and dies on version mismatch.
    _bundle_nss_libs(dist_dir / "main.dist")

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

    # ── H-01: integrity manifest for whatever gets shipped ──
    _write_checksums(dist_dir)


if __name__ == "__main__":
    main()
