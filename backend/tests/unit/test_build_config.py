"""Regression tests for the release/build configuration files."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_api_dockerfile_copies_package_source() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY bimos ./bimos" in dockerfile
    assert dockerfile.index("COPY bimos ./bimos") < dockerfile.index("python -m build --wheel")


def test_ci_installs_fpm_before_builder() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert "gem install fpm" in workflow
    assert "fpm --version" in workflow
    assert workflow.index("gem install fpm") < workflow.index("pixi run python ../builder.py")


def test_ci_is_manual_until_the_budget_is_approved() -> None:
    import yaml

    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get(True, workflow.get("on"))
    assert triggers == {"workflow_dispatch": None}


def test_ci_uses_least_privilege_permissions() -> None:
    import yaml

    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    )
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["build-linux"]
    assert workflow["jobs"]["release"]["permissions"] == {"contents": "write"}


def test_ci_checks_tag_against_pyproject_version() -> None:
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")

    assert "Verify tag matches pyproject version" in workflow
    assert 'v${VERSION}' in workflow
    assert workflow.index("Verify tag matches pyproject version") < workflow.index(
        "pixi run python ../builder.py"
    )


def _pyproject_version() -> str:
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match, "pyproject.toml lost its version field"
    return match.group(1)


def test_version_has_a_single_source() -> None:
    """pyproject.toml is the source; server/frontend must not drift from it."""
    version = _pyproject_version()

    server = (ROOT / "backend" / "bimos" / "api" / "server.py").read_text(encoding="utf-8")
    settings = (ROOT / "backend" / "bimos" / "config" / "settings.py").read_text(encoding="utf-8")
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert f'version="{version}"' not in server
    assert f'app_version: str = "{version}"' not in settings
    assert "version=settings.app_version" in server
    assert "_package_version()" in settings
    assert package["version"] == version


def test_dockers_are_packaged_once() -> None:
    """The Dockerfile ships only inside the Nuitka tree (dist/dockers).

    ``setup.py`` resolves it relative to the package, so a second copy under
    /opt/bimos/dockers was redundant.
    """
    builder = (ROOT / "builder.py").read_text(encoding="utf-8")
    nsi = (ROOT / "installer" / "bimos.nsi").read_text(encoding="utf-8")
    postinst = (ROOT / "installer" / "postinst.sh").read_text(encoding="utf-8")
    postrm = (ROOT / "installer" / "postrm.sh").read_text(encoding="utf-8")
    build = (ROOT / "backend" / "build.py").read_text(encoding="utf-8")

    assert "--include-data-dir=dockers=dockers" in build
    assert "/opt/bimos/dockers" not in builder
    assert "/opt/bimos/dockers" not in postinst
    assert "/opt/bimos/dockers" not in postrm
    assert "opt/bimos/lib/dockers/Dockerfile.bimos" in builder
    assert "DOCKERS_DIR_PATH" not in nsi


def test_macos_build_has_no_qt() -> None:
    """macOS uses pywebview/Cocoa; Qt must never enter the bundle."""
    build = (ROOT / "backend" / "build.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")

    macos_branch = build.split("elif is_macos:", 1)[1].split("else:", 1)[0]
    assert "qtpy" not in macos_branch
    assert "pyqt6" not in macos_branch
    assert "webview.platforms.cocoa" in macos_branch
    assert "--disable-plugin=pywebview" in macos_branch
    assert "--include-module={module}" in macos_branch
    assert "--macos-create-app-bundle" in macos_branch

    gui_extra = pyproject.split("gui = [", 1)[1].split("]", 1)[0]
    assert "pyqt6>=6.11.0; sys_platform == 'linux'" in gui_extra
    assert "qtpy>=2.4.3; sys_platform == 'linux'" in gui_extra
    assert "sys_platform != 'win32'" not in gui_extra


def test_macos_package_is_a_portable_bundle_not_a_dmg() -> None:
    builder = (ROOT / "builder.py").read_text(encoding="utf-8")
    script = (ROOT / "installer" / "build_macos_bundle.sh").read_text(encoding="utf-8")

    for marker in (
        "package_macos_bundle",
        "verify_macos_bundle",
        "macos-arm64.tar.gz",
    ):
        assert marker in builder
    assert "create-dmg" not in builder.split("def package_macos_bundle", 1)[1]

    for marker in (
        "codesign --force --sign -",
        "codesign --verify --deep --strict",
        "NSAllowsLocalNetworking",
        "Uninstall BIMOS.command",
        "macos_launcher.c",
        "tar --xattrs",
        "COPYFILE_DISABLE=1",
    ):
        assert marker in script


def test_tar_gz_archives_are_hashed() -> None:
    build = (ROOT / "backend" / "build.py").read_text(encoding="utf-8")
    assert '".tar.gz"' in build
    assert "path.name.lower().endswith(_CHECKSUM_SUFFIXES)" in build


def test_macos_binary_opens_the_gui_when_launched_directly() -> None:
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert '_is_frozen() and sys.platform == "darwin"' in main
    assert 'sys.argv = [sys.argv[0], "-g"]' in main


def test_windows_uninstaller_purges_user_data() -> None:
    nsi = (ROOT / "installer" / "bimos.nsi").read_text(encoding="utf-8")
    assert 'WriteRegStr   HKLM "${UNINSTALL_KEY}" "UserProfile"' in nsi

    uninstall = nsi.split('Section "Uninstall"')[1]
    assert 'ReadRegStr $1 HKLM "${UNINSTALL_KEY}" "UserProfile"' in uninstall
    assert 'RMDir /r "$1\\.bimos"' in uninstall
    assert 'RMDir /r "$1\\AppData\\Local\\BIMOS.exe.WebView2"' in uninstall


def test_linux_postrm_distinguishes_remove_from_purge() -> None:
    postrm = (ROOT / "installer" / "postrm.sh").read_text(encoding="utf-8")
    assert '[ "$1" = "purge" ]' in postrm
    assert "SUDO_USER" in postrm
    assert "BIMOS.conf" in postrm
    assert "local/share/BIMOS" in postrm
    assert "rmi -f localhost/bimos/global:latest" in postrm


def test_setup_refuses_to_build_the_cuda_image_on_macos(
    monkeypatch, tmp_path
) -> None:
    """Prevent a multi-GB CUDA build on a Mac that cannot run it."""
    from click.testing import CliRunner

    from bimos.cli.commands import setup as setup_module
    from bimos.infrastructure import container
    from bimos.shared import user_config

    monkeypatch.setattr(setup_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(setup_module.settings, "ensure_dirs", lambda: None)
    monkeypatch.setattr(user_config, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(user_config, "is_custom", lambda name: False)

    def fail_build(**kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("build_image must not run on macOS")

    monkeypatch.setattr(container, "build_image", fail_build)

    result = CliRunner().invoke(setup_module.setup, [])
    assert result.exit_code == 0, result.output
    assert "requires Linux" in result.output

    result = CliRunner().invoke(setup_module.setup, ["--config-only"])
    assert result.exit_code == 0, result.output
