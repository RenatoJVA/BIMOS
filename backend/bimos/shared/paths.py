"""Canonical filesystem paths for the BIMOS package."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PACKAGE_ROOT / "scripts"
CONFIG_DIR = PACKAGE_ROOT / "config"
DEFAULTS_DIR = CONFIG_DIR / "defaults"
INFRA_CONFIG_DIR = PACKAGE_ROOT / "infrastructure" / "config"
