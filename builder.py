#!/usr/bin/env python3
"""
BIMOS Master Builder
====================
Builds the Nuitka binary and then wraps it in a native package:

  Linux   →  .deb  (via fpm)
  Windows →  .exe  (via NSIS / makensis)
  macOS   →  portable .tar.gz with BIMOS.app (no installer, no DMG)

Usage:
    python builder.py [OPTIONS]

Options:
    --skip-frontend    Skip building the frontend (use existing bimos/ui/)
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
    """Build the frontend and sync it into backend/bimos/ui via backend/build.py.

    Delegates to ``backend/build.py --skip-nuitka`` so there is a single source
    of truth for the frontend build/sync step.
    """
    info("Building Frontend (bun)...")
    require("bun", "Install bun: https://bun.sh")
    run([sys.executable, "build.py", "--skip-nuitka"], cwd=root / "backend")
    ok("Frontend built and synced")


def build_nuitka(root: Path):
    info("Compiling with Nuitka...")
    backend = root / "backend"
    # Frontend already built/synced by build_frontend(); skip to avoid rebuild.
    run([sys.executable, "build.py", "--skip-frontend"], cwd=backend)
    ok("Nuitka compilation done")


# ── Verification ────────────────────────────────────────────────────────────

def _find_binary(root: Path) -> Path | None:
    """Locate the compiled binary in either Nuitka output layout.

    On macOS ``--macos-create-app-bundle`` puts the executable inside
    ``main.app/Contents/MacOS``; plain standalone (Linux/Windows) uses
    ``main.dist``.
    """
    candidates = [
        root / "backend" / "dist" / "main.dist" / "bimos.bin",
        root / "backend" / "dist" / "main.dist" / "bimos.exe",
        root / "backend" / "dist" / "main.app" / "Contents" / "MacOS" / "bimos.bin",
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def smoke_test_binary(root: Path, version: str):
    """Execute the compiled binary with --version and demand an exact match."""
    binary = _find_binary(root)
    if binary is None:
        error(f"Binary not found under {root / 'backend' / 'dist'}")
        sys.exit(1)

    proc = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=120)
    expected = f"bimos, version {version}"
    if proc.returncode != 0 or expected not in (proc.stdout + proc.stderr):
        error(f"Binary smoke test failed: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}")
        sys.exit(1)
    ok(f"Smoke test {binary.name}: {expected}")


def check_runtime_libs(root: Path):
    """Gate: QtWebEngine's NSS chain must resolve from the bundle itself.

    Nuitka standalone omits libnss3/libnssutil3 (treated as system libraries);
    if the bundle ships libsmime3.so but not its NSS dependencies, every host
    with an older system NSS dies on import with a version-symbol error.
    Reproduced here by resolving dependencies against the dist directory first.
    """
    if platform.system() != "Linux":
        return
    dist = root / "backend" / "dist" / "main.dist"
    ldd = shutil.which("ldd")
    if not ldd or not dist.is_dir():
        warn("Runtime-lib check skipped (ldd or dist missing)")
        return
    problematic: list[str] = []
    for obj in ("libQt6WebEngineCore.so.6", "QtWebEngineProcess", "libsmime3.so"):
        target = dist / obj
        if not target.exists():
            continue
        proc = subprocess.run(
            [ldd, str(target)],
            capture_output=True,
            text=True,
            env={"LD_LIBRARY_PATH": str(dist), "PATH": os.environ.get("PATH", "/usr/bin")},
        )
        for line in proc.stdout.splitlines():
            if "not found" in line:
                problematic.append(f"{obj}: {line.strip()}")
    if problematic:
        error(f"Bundle runtime resolution failed ({len(problematic)} problem(s)):")
        for item in problematic[:8]:
            print(f"         {item}")
        sys.exit(1)
    ok("Runtime libs: QtWebEngine NSS chain resolves from the bundle")


def check_stripped(root: Path):
    """Audit hardening H-02: shipped binary must carry no debug symbols.

    ELF hosts (Linux) are inspected with ``readelf``; Mach-O hosts (macOS) with
    ``otool -l``. Mach-O has no ``.symtab`` section but exports a ``__DWARF``
    segment when debug info leaks into the release.
    """
    if platform.system() == "Windows":
        warn("Stripped check skipped on windows (readelf not applicable)")
        return
    binary = _find_binary(root)
    if binary is None:
        warn("compiled binary not found — stripped check skipped")
        return
    if platform.system() == "Darwin":
        check_stripped_macho(binary)
        return
    proc = subprocess.run(["readelf", "-S", str(binary)], capture_output=True, text=True)
    sections = proc.stdout
    debug = [ln for ln in sections.splitlines() if ".debug" in ln or ".symtab" in ln]
    if debug:
        error(f"Binary still exposes {len(debug)} debug/symbol sections:")
        for ln in debug[:5]:
            print(f"         {ln.strip()}")
        sys.exit(1)
    ok("ELF stripped: 0 .debug/.symtab sections")


def check_stripped_macho(binary: Path):
    """Fail when the Mach-O binary still carries DWARF debug sections."""
    otool = shutil.which("otool")
    if not otool:
        warn("otool not available — Mach-O stripped check skipped")
        return
    proc = subprocess.run([otool, "-l", str(binary)], capture_output=True, text=True)
    if proc.returncode != 0:
        warn(f"otool failed on {binary.name} — Mach-O stripped check skipped")
        return
    debug = [
        ln.strip()
        for ln in proc.stdout.splitlines()
        if "__DWARF" in ln or "__debug_" in ln
    ]
    if debug:
        error(f"Mach-O binary still exposes {len(debug)} DWARF section(s):")
        for ln in debug[:5]:
            print(f"         {ln}")
        sys.exit(1)
    ok("Mach-O without DWARF sections")


def write_manifests(root: Path):
    """Integrity H-01: SHA256SUMS for backend/dist and installer/dist."""
    sys.path.insert(0, str(root / "backend"))
    import build as backend_build

    for dist_dir in (root / "backend" / "dist", root / "installer" / "dist"):
        if not dist_dir.exists():
            warn(f"{dist_dir} does not exist — manifest skipped")
            continue
        if backend_build._write_checksums(dist_dir) is None:
            warn(f"No artifacts to hash in {dist_dir}")
        else:
            ok(f"SHA256SUMS updated in {dist_dir.relative_to(root)}")


def verify_deb(root: Path, version: str):
    """Structural audit of the .deb without installing: metadata, payload, hash."""
    deb = root / "installer" / "dist" / f"bimos_{version}_amd64.deb"
    if not deb.exists():
        warn(f".deb not found: {deb} — verify skipped")
        return
    if not shutil.which("dpkg-deb"):
        warn("dpkg-deb not available — .deb verification skipped")
        return

    pkg_version = subprocess.run(
        ["dpkg-deb", "-f", str(deb), "Version"], capture_output=True, text=True
    ).stdout.strip()
    if pkg_version != version:
        error(f".deb version mismatch: package={pkg_version!r} expected={version!r}")
        sys.exit(1)
    ok(f".deb metadata: version {pkg_version}")

    staging = root / "installer" / "dist" / ".verify_stage"
    staging.exists() and shutil.rmtree(staging)
    staging.mkdir(parents=True)
    subprocess.run(["dpkg-deb", "-x", str(deb), str(staging)], cwd=root, check=True, capture_output=True)

    expected_payload = [
        staging / "opt/bimos/lib/bimos.bin",
        staging / "usr/bin/bimos",
        staging / "usr/share/applications/bimos.desktop",
        staging / "usr/share/doc/bimos/README.md",
        # Dockers ship inside the Nuitka standalone tree (dist/dockers),
        # which fpm maps to /opt/bimos/lib. setup.py resolves them relative
        # to the package, so no second copy is packaged.
        staging / "opt/bimos/lib/dockers/Dockerfile.bimos",
    ]
    missing = [p.relative_to(staging) for p in expected_payload if not p.exists()]
    # Legal docs are best-effort: flagged at packaging time, not structural failures
    optional_payload = [
        ("LICENSE", staging / "usr/share/doc/bimos/LICENSE"),
        ("NOTICE.md", staging / "usr/share/doc/bimos/NOTICE.md"),
        ("TERMS.md", staging / "usr/share/doc/bimos/TERMS.md"),
        ("PRIVACY.md", staging / "usr/share/doc/bimos/PRIVACY.md"),
    ]
    optional_missing = [name for name, p in optional_payload if not p.exists()]
    if missing:
        error(f".deb payload missing {len(missing)} file(s):")
        for m in missing:
            print(f"         {m}")
        shutil.rmtree(staging)
        sys.exit(1)
    if optional_missing:
        warn(f"Legal docs omitted from .deb: {', '.join(optional_missing)} (source files now "
             "exist — rebuilding will include them; see package_linux_deb mappings)")
    else:
        ok("Legal docs included: LICENSE, NOTICE, TERMS, PRIVACY")
    ok("Payload: binary, wrapper, desktop entry, docs and dockers present")

    dist_binary = root / "backend" / "dist" / "main.dist" / "bimos.bin"
    pkg_binary = staging / "opt/bimos/lib/bimos.bin"
    if dist_binary.exists():
        h1 = subprocess.run(["sha256sum", str(dist_binary)], capture_output=True, text=True).stdout.split()[0]
        h2 = subprocess.run(["sha256sum", str(pkg_binary)], capture_output=True, text=True).stdout.split()[0]
        if h1 != h2:
            error("Packaged binary hash differs from dist/main.dist/bimos.bin")
            print(f"         dist={h1}")
            print(f"         .deb={h2}")
            shutil.rmtree(staging)
            sys.exit(1)
        ok("Packaged binary hash == dist binary hash")

    shutil.rmtree(staging)
    ok(f".deb audit clean → {deb.name}")


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_macos_bundle(root: Path, version: str) -> Path | None:
    """Structural audit of the macOS portable bundle without installing it.

    Extracts to a temporary directory and checks layout, signing, architecture,
    link paths and size. The archive is what the user downloads, so every check
    runs against the extracted copy (permissions included).
    """
    bundle = root / "installer" / "dist" / f"BIMOS-{version}-macos-arm64.tar.gz"
    if not bundle.exists():
        warn(f"macOS bundle not found: {bundle} — verify skipped")
        return None

    staging = root / "installer" / "dist" / ".verify_macos"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        subprocess.run(
            ["tar", "--xattrs", "-xzf", str(bundle), "-C", str(staging)],
            check=True,
            capture_output=True,
        )
        app = staging / "BIMOS.app"
        resources = app / "Contents" / "Resources"
        binary = next(
            (
                candidate
                for candidate in (
                    app / "Contents" / "MacOS" / "bimos.bin",
                    resources / "bimos" / "bimos.bin",
                )
                if candidate.exists()
            ),
            None,
        )
        info_plist = app / "Contents" / "Info.plist"
        helper = staging / "Uninstall BIMOS.command"
        plist_text = info_plist.read_text(encoding="utf-8") if info_plist.exists() else ""
        match = re.search(
            r"<key>CFBundleExecutable</key>\s*<string>([^<]+)</string>", plist_text
        )
        executable_name = match.group(1) if match else "BIMOS"

        expected = [
            app / "Contents" / "MacOS" / executable_name,
            info_plist,
            resources / "bimos.icns",
            helper,
            staging / "LEEME.txt",
        ]
        if binary is not None:
            expected.append(binary)
        missing = [p.relative_to(staging) for p in expected if not p.exists()]
        if missing:
            error(f"macOS bundle payload missing {len(missing)} file(s):")
            for item in missing:
                print(f"         {item}")
            sys.exit(1)
        if binary is None:
            error("BIMOS.app has no bimos.bin executable")
            sys.exit(1)
        if not os.access(helper, os.X_OK):
            error(f"Uninstall helper is not executable: {helper.relative_to(staging)}")
            sys.exit(1)
        ok("Payload: app, executable, Info.plist, icon, uninstall helper and LEEME")

        for marker in ("org.bimos.app", "NSAllowsLocalNetworking"):
            if marker not in plist_text:
                error(f"Info.plist is missing {marker}")
                sys.exit(1)
        ok("Info.plist: bundle id and local networking exception present")

        codesign = shutil.which("codesign")
        if codesign:
            proc = subprocess.run(
                [codesign, "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                error("codesign verification failed:")
                print(f"         {proc.stderr.strip() or proc.stdout.strip()}")
                sys.exit(1)
            ok("Signature verified (ad-hoc, codesign --deep --strict)")
        else:
            warn("codesign not available — signature not verified")

        lipo = shutil.which("lipo")
        if lipo:
            archs = subprocess.run(
                [lipo, "-archs", str(binary)], capture_output=True, text=True
            ).stdout.split()
            if archs != ["arm64"]:
                error(f"Unexpected architectures: {archs or 'unknown'} (expected arm64)")
                sys.exit(1)
            ok("Architecture: arm64")

        otool = shutil.which("otool")
        if otool:
            linked = subprocess.run(
                [otool, "-L", str(binary)], capture_output=True, text=True
            ).stdout
            # The first line is "<binary>:"; only dependency lines matter.
            leaks = [
                line.strip()
                for line in linked.splitlines()[1:]
                if re.search(r"/opt/homebrew|/usr/local|/Users/", line)
            ]
            if leaks:
                error("Binary links against absolute build-machine paths:")
                for line in leaks[:8]:
                    print(f"         {line}")
                sys.exit(1)
            ok("otool: no absolute build-machine paths")

        size_mb = bundle.stat().st_size / (1024 * 1024)
        if size_mb > 200:
            error(f"Bundle is {size_mb:.1f} MB (limit: 200 MB)")
            sys.exit(1)
        ok(f"Size: {size_mb:.1f} MB (limit: 200 MB)")
        ok(f"SHA256 {bundle.name}: {_sha256_file(bundle)}")
        return bundle
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def verify_all(root: Path, version: str):
    info("Verifying build artifacts (no compilation)...")
    smoke_test_binary(root, version)
    check_stripped(root)
    check_runtime_libs(root)
    if platform.system() == "Darwin":
        verify_macos_bundle(root, version)
    write_manifests(root)
    verify_deb(root, version)


# ── Installer builders ───────────────────────────────────────────────────────

def package_linux_deb(root: Path, version: str):
    info("Packaging → Linux .deb (fpm)...")
    require("fpm", "Install fpm: gem install fpm  OR  apt install ruby-dev && gem install fpm")

    binary_dir = root / "backend" / "dist" / "main.dist"
    if not (binary_dir / "bimos.bin").exists():
        error(f"Binary not found: {binary_dir / 'bimos.bin'}")
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
        "--maintainer",     "Renato J. V. A. <https://github.com/RenatoJVA/BIMOS/issues>",
        "--license",        "GPLv3",
        "--category",       "science",
        "--deb-recommends", "docker.io (>= 20.0)",
        "--deb-recommends", "docker-compose-plugin (>= 2.0)",
        "--after-install",  str(root / "installer" / "postinst.sh"),
        "--after-remove",   str(root / "installer" / "postrm.sh"),
        "--package",        str(out_dir / deb_name),
        "--force",
    ]

    # Create the shell wrapper that will go at /usr/bin/bimos
    wrapper = root / "installer" / "assets" / "bimos-wrapper.sh"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text("#!/bin/sh\nexec /opt/bimos/lib/bimos.bin \"$@\"\n")
    wrapper.chmod(0o755)

    # Map: source=destination
    #   - trailing slash on source dirs extracts *contents* rather than the dir itself
    #   - bimos.bin RPATH = $ORIGIN, so .so deps must live alongside it
    file_mappings = [
        (f"{binary_dir}/",                                "/opt/bimos/lib"),
        (str(wrapper),                                    "/usr/bin/bimos"),
        (str(root / "backend" / "README.md"),             "/usr/share/doc/bimos/README.md"),
        (str(root / "installer" / "assets" / "bimos.desktop"),
                                                          "/usr/share/applications/bimos.desktop"),
    ]

    # Legal documents shipped with every package (GPLv3 + third-party notices
    # + terms of use + privacy policy). Debian/FPM convention: /usr/share/doc.
    for doc in ("LICENSE", "NOTICE.md", "TERMS.md", "PRIVACY.md"):
        doc_path = root / doc
        if doc_path.exists():
            file_mappings.append((str(doc_path), f"/usr/share/doc/bimos/{doc}"))
        else:
            warn(f"{doc} not found — package will omit it")

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
            r"BIMOS \x97 Biomolecular Modeling Suite\par"
            r"\par"
            r"BIMOS is free software licensed under the GNU General Public License\par"
            r"version 3 (GPLv3). The full license text is in the file LICENSE.rtf\par"
            r"next to this installer and in docs/LICENSE after installation.\par"
            r"\par"
            r"BIMOS is provided without warranty, as described in TERMS.md.\par"
            r"Bundled third-party components (GROMACS, AutoDock Vina, Boltz, Meeko,\par"
            r"RDKit, PyTorch and system libraries) keep their own licenses; see\par"
            r"docs/NOTICE.md. ORCA and Gaussian 16 are NOT distributed with BIMOS.\par"
            r"}", encoding='utf-8'
        )
        ok(f"Created default LICENSE.rtf")

    # Stage legal documents for the Windows package ($INSTDIR\docs)
    legal_dir = out_dir / "legal-docs"
    if legal_dir.exists():
        shutil.rmtree(legal_dir)
    legal_dir.mkdir(parents=True, exist_ok=True)
    for doc in ("LICENSE", "NOTICE.md", "TERMS.md", "PRIVACY.md"):
        doc_path = root / doc
        if doc_path.exists():
            shutil.copy2(doc_path, legal_dir / doc)
        else:
            warn(f"{doc} not found — Windows package will omit it")

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
    license_path = str(license_file).replace("\\", "\\\\")
    legal_docs_path = str(legal_dir).replace("\\", "\\\\")
    
    nsi_patched = nsi_patched.replace("LICENSE_FILE_PATH", license_path)
    nsi_patched = nsi_patched.replace("LEGAL_DOCS_DIR_PATH", legal_docs_path)
    nsi_patched = nsi_patched.replace("BINARY_DIR_PATH", binary_path)
    nsi_patched = nsi_patched.replace("README_FILE_PATH", readme_path)

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


def package_macos_bundle(root: Path, version: str):
    info("Packaging → macOS portable bundle (.tar.gz)...")
    script = root / "installer" / "build_macos_bundle.sh"
    if not script.exists():
        error(f"macOS bundle script not found: {script}")
        sys.exit(1)
    script.chmod(0o755)
    run(["bash", str(script), version], cwd=root)
    ok(f"macOS bundle ready → installer/dist/BIMOS-{version}-macos-arm64.tar.gz")


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
    p.add_argument("--skip-frontend",  action="store_true", help="Skip building/syncing the frontend")
    p.add_argument("--skip-nuitka",    action="store_true", help="Skip Nuitka compilation")
    p.add_argument("--skip-installer", action="store_true", help="Only compile, no installer")
    p.add_argument("--verify",         action="store_true", help="Verify existing artifacts only: smoke test, debug sections, SHA256SUMS, .deb/.tar.gz audit")
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

    if args.verify:
        verify_all(root, version)
        return

    # ── Step 1: Frontend ────────────────────────────────────
    if not args.skip_frontend:
        build_frontend(root)
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
            package_macos_bundle(root, version)

    # ── Step 4: Verify artifacts ────────────────────────────
    if not args.skip_nuitka:
        verify_all(root, version)
    else:
        warn("Skipping verification (no build)")

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
