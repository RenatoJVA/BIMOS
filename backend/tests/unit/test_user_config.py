from pathlib import Path
from unittest.mock import patch
import yaml

from bimos.shared.user_config import (
    clamp,
    resolve,
    is_custom,
    ensure_user_configs,
    _max_patch,
    _deep_merge,
    user_config_dir,
    ConfigProfile,
)


def test_clamp_within_range() -> None:
    assert clamp(5, 0, 10) == 5


def test_clamp_below_low() -> None:
    assert clamp(-1, 0, 10) == 0


def test_clamp_above_high() -> None:
    assert clamp(15, 0, 10) == 10


def test_resolve_default_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.settings.max_threads", False)
    data, profile = resolve("docking", max_mode=False)
    assert profile == ConfigProfile.DEFAULT
    assert isinstance(data, dict)


def test_resolve_max_profile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.settings.max_threads", True)
    monkeypatch.setattr(
        "bimos.shared.user_config.settings.get_threads",
        lambda: 8,
    )
    data, profile = resolve("docking", max_mode=True)
    assert profile == ConfigProfile.MAX


def test_is_custom_returns_false_if_not_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    assert not is_custom("docking")


def test_deep_merge_simple() -> None:
    base = {"a": 1, "b": 2}
    patch = {"b": 3, "c": 4}
    result = _deep_merge(base, patch)
    assert result == {"a": 1, "b": 3, "c": 4}


def test_deep_merge_nested() -> None:
    base = {"a": {"x": 1, "y": 2}}
    patch = {"a": {"y": 99, "z": 3}}
    result = _deep_merge(base, patch)
    assert result == {"a": {"x": 1, "y": 99, "z": 3}}


def test_user_config_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    assert user_config_dir() == tmp_path / "config"


def test_ensure_user_configs_creates_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.DEFAULTS_DIR", tmp_path / "defaults")
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults" / "docking.yaml").write_text("key: value\n")
    ensure_user_configs()
    assert (tmp_path / "config" / "docking.yaml").exists()
