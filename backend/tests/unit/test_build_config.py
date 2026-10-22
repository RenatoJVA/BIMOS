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
