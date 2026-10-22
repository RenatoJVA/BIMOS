from pathlib import Path

from bimos.shared.user_config import (
    ConfigProfile,
    _deep_merge,
    clamp,
    ensure_user_configs,
    is_custom,
    resolve,
    user_config_dir,
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


def test_max_profile_caps_qm_jobs_to_installed_ram(
    tmp_path: Path, monkeypatch
) -> None:
    """``--max`` must not request more QM jobs than the host RAM can hold.

    Regression guard: on a 126 GB host the MAX profile asked for 8 ORCA jobs
    at 32 GB each (250 GB), so the hardware guard blocked every QM run before
    the pipeline could start.
    """
    from bimos.shared.hardware import MemInfo

    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.settings.max_threads", True)
    monkeypatch.setattr("bimos.shared.user_config.settings.get_threads", lambda: 16)
    monkeypatch.setattr(
        "bimos.shared.hardware.detect_mem",
        lambda: MemInfo(total_gb=126.0, avail_gb=113.0),
    )

    orca, _ = resolve("orca", max_mode=True)
    gaussian, _ = resolve("gaussian", max_mode=True)

    assert orca["orca"]["maxcore_mb"] == 32768
    assert gaussian["gaussian"]["mem"] == "32GB"
    assert orca["orca"]["max_jobs"] == 3
    assert gaussian["gaussian"]["max_jobs"] == 3


def test_max_profile_uses_64gb_per_job_when_two_fit(
    tmp_path: Path, monkeypatch
) -> None:
    from bimos.shared.hardware import MemInfo

    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.settings.max_threads", True)
    monkeypatch.setattr("bimos.shared.user_config.settings.get_threads", lambda: 16)
    monkeypatch.setattr(
        "bimos.shared.hardware.detect_mem",
        lambda: MemInfo(total_gb=512.0, avail_gb=500.0),
    )

    orca, _ = resolve("orca", max_mode=True)
    gaussian, _ = resolve("gaussian", max_mode=True)

    assert orca["orca"]["maxcore_mb"] == 65536
    assert gaussian["gaussian"]["mem"] == "64GB"
    assert orca["orca"]["max_jobs"] == 8
    assert gaussian["gaussian"]["max_jobs"] == 8

def test_custom_profile_keeps_new_packaged_defaults(
    tmp_path: Path, monkeypatch
) -> None:
    """Upgrades must not drop defaults absent from an older custom file."""
    monkeypatch.setattr("bimos.shared.user_config.settings.base_path", tmp_path)
    monkeypatch.setattr("bimos.shared.user_config.settings.max_threads", False)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "docking.yaml").write_text("vina:\n  times: 7\n", encoding="utf-8")

    data, profile = resolve("docking", max_mode=False)

    assert profile == ConfigProfile.CUSTOM
    assert data["vina"]["times"] == 7
    assert data["vina"]["exhaustiveness"] == 12
    assert data["grid"]["mode"] == "auto"
