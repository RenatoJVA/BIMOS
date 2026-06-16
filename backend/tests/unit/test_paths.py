from pathlib import Path

from bimos.shared.paths import PACKAGE_ROOT, SCRIPTS_DIR, CONFIG_DIR, DEFAULTS_DIR, INFRA_CONFIG_DIR


def test_package_root_resolved() -> None:
    assert PACKAGE_ROOT.exists()
    assert (PACKAGE_ROOT / "__init__.py").exists()


def test_scripts_dir() -> None:
    assert SCRIPTS_DIR == PACKAGE_ROOT / "scripts"
    assert SCRIPTS_DIR.name == "scripts"


def test_config_dir() -> None:
    assert CONFIG_DIR == PACKAGE_ROOT / "config"


def test_defaults_dir() -> None:
    assert DEFAULTS_DIR == CONFIG_DIR / "defaults"


def test_infra_config_dir() -> None:
    assert INFRA_CONFIG_DIR == PACKAGE_ROOT / "infrastructure" / "config"


def test_paths_are_absolute() -> None:
    assert PACKAGE_ROOT.is_absolute()
    assert SCRIPTS_DIR.is_absolute()
    assert CONFIG_DIR.is_absolute()
    assert DEFAULTS_DIR.is_absolute()
    assert INFRA_CONFIG_DIR.is_absolute()
