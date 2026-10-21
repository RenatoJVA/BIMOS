"""Legal compliance: third-party notices stay accurate (pure file reads)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NOTICE = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
BACKEND_README = (ROOT / "backend" / "README.md").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "backend" / "dockers" / "Dockerfile.bimos").read_text(encoding="utf-8")
SECURITY = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
DOCS_INDEX = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
DOCS_DEVELOPMENT = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
FRONTEND_README = (ROOT / "frontend" / "README.md").read_text(encoding="utf-8")
SPEC = (ROOT / "installer" / "bimos.spec").read_text(encoding="utf-8")
NSI = (ROOT / "installer" / "bimos.nsi").read_text(encoding="utf-8")
BUILDER = (ROOT / "builder.py").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
DESKTOP_ENTRY = (ROOT / "installer" / "assets" / "bimos.desktop").read_text(encoding="utf-8")
POSTINST = (ROOT / "installer" / "postinst.sh").read_text(encoding="utf-8")
BUILD_DMG = (ROOT / "installer" / "build_dmg.sh").read_text(encoding="utf-8")

LEGAL_DOCS = ("LICENSE", "NOTICE.md", "TERMS.md", "PRIVACY.md")


def test_notice_covers_bundled_components() -> None:
    for component in (
        "GROMACS",
        "AutoDock Vina",
        "Boltz",
        "Meeko",
        "RDKit",
        "PyTorch",
        "FFTW",
        "OpenBabel",
        "CUDA",
        "Ubuntu",
    ):
        assert component in NOTICE, f"NOTICE.md missing {component}"


def test_notice_names_non_distributed_qm() -> None:
    assert "ORCA" in NOTICE and "Gaussian" in NOTICE
    assert "never distributed" in NOTICE


def test_meeko_is_lgpl_with_pinned_source() -> None:
    assert "LGPL" in NOTICE
    assert "v0.8.0" in NOTICE
    meeko_section = NOTICE.split("## Meeko")[1].split("## RDKit")[0]
    assert "BSD" not in meeko_section
    # Installed from PyPI, so the pin is an exact wheel version rather than a
    # git tag; both are recorded so the artifact is identifiable either way.
    assert "meeko==0.8.0" in meeko_section
    assert "meeko==${MEEKO_VERSION}" in DOCKERFILE
    assert "ARG MEEKO_VERSION=0.8.0" in DOCKERFILE


def test_scientific_image_is_reproducible() -> None:
    """The image must not drift between builds, and downloads must be checked.

    Regression guard: the image used to `git clone --depth 1` the head of
    boltz' and Meeko's repositories, so two builds of the same tag shipped
    different code, and tarball downloads went unverified.
    """
    for line in DOCKERFILE.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "git clone" not in stripped, f"unpinned clone in Dockerfile: {stripped}"
        assert "2>/dev/null" not in stripped, f"silenced failure in Dockerfile: {stripped}"
    assert "sha256sum -c" in DOCKERFILE
    for pin in ('"boltz==${BOLTZ_VERSION}"', "ARG BOLTZ_VERSION=2.2.1"):
        assert pin in DOCKERFILE
    # No unpinned Python dependency may creep back in.
    for spec in re.findall(r'pip3 install[^\n]*(?:\\\n[^\n]*)*', DOCKERFILE):
        for token in re.findall(r'"\s*([A-Za-z0-9_.-]+)(?:[=<>!~][^"]*)?\s*"', spec):
            if token in {"torch", "boltz", "meeko", "cuequivariance", "cuequivariance-torch"}:
                continue  # covered by an ARG assertion above
            assert re.search(rf'"{re.escape(token)}==', spec), f"unpinned dependency: {token}"


def test_runtime_image_ships_no_compiler() -> None:
    """Every runtime dependency is a wheel or a pure-Python sdist.

    Keeping the compiler out of the runtime stage is what makes the image small
    and hardens it; the GROMACS builder stage is the only place one is needed.
    """
    runtime = DOCKERFILE.split("Stage 2: runtime image", 1)[1]
    apt = runtime.split("RUN mkdir", 1)[0]
    for package in ("build-essential", "python3.12-dev", "python3.12-venv", "gcc", "g++"):
        assert package not in apt, f"toolchain package {package} leaked into the runtime image"
    assert "build-essential" in DOCKERFILE.split("Stage 2", 1)[0], "builder stage lost its toolchain"


def test_boltz_kernels_are_opt_in() -> None:
    """cuequivariance is a year newer than boltz, so it stays off by default.

    boltz.yaml ships `no_kernels: true` and boltz only imports cuequivariance
    inside its kernel_* functions, so the default image must not depend on it.
    """
    assert "ARG INSTALL_BOLTZ_KERNELS=OFF" in DOCKERFILE
    assert 'if [ "${INSTALL_BOLTZ_KERNELS}" = "ON" ]; then' in DOCKERFILE
    boltz_yaml = (ROOT / "backend" / "bimos" / "config" / "defaults" / "boltz.yaml").read_text(
        encoding="utf-8"
    )
    assert "no_kernels: true" in boltz_yaml
    assert "model: boltz2" in boltz_yaml


def test_boltz_points_to_official_repo() -> None:
    assert "jwohlwend/boltz" in NOTICE
    assert "jlab-design" not in NOTICE


def test_no_esmfold_distribution_claims() -> None:
    assert "ESMFold" not in NOTICE
    assert "ESMFold" not in README
    assert "ESMFold" not in BACKEND_README


def test_terms_and_privacy_exist() -> None:
    terms = (ROOT / "TERMS.md").read_text(encoding="utf-8")
    privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
    assert "ORCA" in terms and "Gaussian" in terms
    assert "MSA" in privacy and "telemetry" in privacy.lower()
    assert "NOTICE.md" in terms


def test_security_policy_defers_to_privacy_doc() -> None:
    assert "PRIVACY.md" in SECURITY
    assert "MSA" in SECURITY
    assert "does **not** collect, transmit, or store" not in SECURITY


def test_no_esmfold_in_active_docs() -> None:
    for name, content in (
        ("docs/index.md", DOCS_INDEX),
        ("docs/development.md", DOCS_DEVELOPMENT),
        ("frontend/README.md", FRONTEND_README),
    ):
        assert "ESMFold" not in content, f"{name} still mentions ESMFold"


def test_frontend_readme_matches_actual_stack() -> None:
    assert "React 19" in FRONTEND_README
    assert "React 18" not in FRONTEND_README


def test_install_docs_do_not_advertise_unpublished_image() -> None:
    installation = (ROOT / "docs" / "installation.md").read_text(encoding="utf-8")
    assert "ghcr.io/renatojva/bimos" not in installation
    assert "bimos serve" not in installation
    assert "bimos setup" in installation


def test_compose_uses_a_real_cli_invocation() -> None:
    assert '"serve"' not in COMPOSE
    assert '"-g", "--headless"' in COMPOSE


def test_packages_ship_every_legal_document() -> None:
    for doc in LEGAL_DOCS:
        assert f"/usr/share/doc/bimos/{doc}" in SPEC, f"bimos.spec omits {doc}"
        assert doc in BUILDER, f"builder.py omits {doc}"
    assert "LEGAL_DOCS_DIR_PATH" in NSI
    assert "LEGAL_DOCS_DIR_PATH" in BUILDER
    assert '$INSTDIR\\docs' in NSI


def test_no_placeholder_project_metadata() -> None:
    for name, content in (("bimos.spec", SPEC), ("SECURITY.md", SECURITY), ("bimos.nsi", NSI)):
        assert "your-org" not in content, f"{name} still has your-org placeholder"
        assert "example.com" not in content, f"{name} still has example.com placeholder"
    assert "https://github.com/RenatoJVA/BIMOS" in SPEC
    assert "https://github.com/RenatoJVA/BIMOS" in NSI
    assert "example.com" not in BUILDER


def test_package_metadata_carries_the_real_author_email() -> None:
    """``example.com`` in pyproject.toml would ship as bogus package metadata."""
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert "example.com" not in pyproject
    assert "renato.vace@gmail.com" in pyproject


def test_windows_uninstaller_removes_the_standalone_tree() -> None:
    """``File /r`` installs the whole Nuitka tree, so ``RMDir /r`` must remove it.

    A non-recursive ``RMDir`` would strand DLLs and block $INSTDIR removal.
    """
    uninstall = NSI.split('Section "Uninstall"')[1]
    assert 'RMDir  /r "$INSTDIR"' in uninstall
    assert 'RMDir  "$INSTDIR"' not in uninstall


def test_privacy_does_not_promise_cpu_boltz() -> None:
    """_preflight_gpu() requires a GPU even with use_msa_server: false."""
    privacy = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
    assert "CPU-only fallback" not in privacy
    assert "a GPU is still required" in privacy


def test_no_phantom_gui_argument() -> None:
    """``BIMOS_GUI`` never existed; the GUI is started with ``-g``.

    Regression guard: a bogus arg made the Linux .desktop entry and the macOS
    bundle show the CLI help instead of launching the UI.
    """
    for name, content in (
        ("bimos.desktop", DESKTOP_ENTRY),
        ("postinst.sh", POSTINST),
        ("bimos.nsi", NSI),
    ):
        assert "BIMOS_GUI" not in content, f"{name} still passes the phantom BIMOS_GUI arg"
    assert "Exec=bimos -g" in DESKTOP_ENTRY
    assert "bimos -g" in POSTINST
    # The DMG script documents the phantom arg in a comment; what matters is
    # that the launcher really passes -g (inside a quoted heredoc).
    assert 'exec "\\$DIR/../Resources/bimos/${BINARY_NAME}" -g "\\$@"' in BUILD_DMG
    assert "bimos.bin\" BIMOS_GUI" not in BUILD_DMG


def test_dmg_builder_uses_nuitka_standalone_layout() -> None:
    """Nuitka --standalone emits main.dist/bimos.bin plus its .so tree."""
    assert 'DIST_DIR="backend/dist/main.dist"' in BUILD_DMG
    assert 'BINARY_SRC="${DIST_DIR}/${BINARY_NAME}"' in BUILD_DMG
    # The old script copied a non-existent backend/dist/bimos
    assert "BINARY_SRC=\"backend/dist/bimos\"" not in BUILD_DMG
    # Info.plist: ProgramArguments is not a valid key
    assert "<key>ProgramArguments</key>" not in BUILD_DMG
    # Version must come from the CLI arg or pyproject, not a lone constant
    assert 'VERSION="$1"' in BUILD_DMG
    assert "backend/pyproject.toml" in BUILD_DMG
    assert "Version: arg > pyproject.toml > fallback" in BUILD_DMG


def test_spec_file_is_marked_as_reference_only() -> None:
    assert "DO NOT BUILD FROM THIS FILE" in SPEC
    assert "REFERENCE (NOT USED BY THE BUILDER)" in SPEC
    assert "Nothing in the repository parses" in SPEC


def test_postinst_accepts_podman() -> None:
    assert "podman" in POSTINST
    assert "docker" in POSTINST


def test_dockerignore_keeps_needed_files_and_drops_local_artifacts() -> None:
    """Both images build with ``context: backend``, so that file is the one used.

    Guards two failure modes: a build that copies a local .venv, and a build
    that fails because .dockerignore excluded something a COPY needs.
    """
    dockerignore = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")
    patterns = {
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    for required in (".venv/", "node_modules/", "__pycache__/", "dist/"):
        assert required in patterns, f"backend/.dockerignore does not exclude {required}"
    for needed in ("pyproject.toml", "README.md"):
        assert needed not in patterns, f"backend/.dockerignore must not exclude {needed}"
    assert (ROOT / "backend" / ".dockerignore").exists()
    assert (ROOT / ".dockerignore").exists()
