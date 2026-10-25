"""Tests for the residue-free uninstaller (``bimos uninstall``)."""

import json
from pathlib import Path

import pytest

from bimos.infrastructure import purge

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated HOME so no test can touch the real user account."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.delenv("BIMOS_BASE_PATH", raising=False)
    monkeypatch.delenv("BIMOS_WORKSPACE", raising=False)
    monkeypatch.delenv("BIMOS_CACHE", raising=False)
    monkeypatch.delenv("BIMOS_LOGS", raising=False)
    monkeypatch.delenv("BIMOS_APP_PATH", raising=False)
    monkeypatch.setattr(purge, "container_runtime", lambda: None)
    return home_dir


def _make_base(home: Path) -> Path:
    base = home / ".bimos"
    (base / "config").mkdir(parents=True)
    (base / ".env").write_text("BIMOS_HOST=127.0.0.1\n", encoding="utf-8")
    (base / "config" / "docking.yaml").write_text("threads: 1\n", encoding="utf-8")
    (base / "workspace").mkdir()
    (base / "workspace" / "job.txt").write_text("data\n", encoding="utf-8")
    return base


def test_manifest_covers_data_web_state_and_image(home: Path) -> None:
    manifest = purge.static_manifest()
    assert "~/.bimos" in manifest["data_paths"]
    assert "~/Library/WebKit/org.bimos.app" in manifest["macos_paths"]
    assert manifest["image"] == "localhost/bimos/global:latest"
    assert "/Applications/BIMOS.app" in manifest["app_paths"]


def test_helper_manifest_does_not_drift() -> None:
    """The standalone shell uninstaller embeds the same manifest as purge.py."""
    helper = (ROOT / "installer" / "assets" / "Uninstall BIMOS.command").read_text(
        encoding="utf-8"
    )
    block = helper.split("# BEGIN BIMOS MANIFEST", 1)[1].split("# END BIMOS MANIFEST", 1)[0]
    embedded = json.loads(block[block.index("{") : block.rindex("}") + 1])
    assert embedded == purge.static_manifest()


def test_dry_run_deletes_nothing(home: Path) -> None:
    base = _make_base(home)
    report = purge.purge(dry_run=True, base_path=base)
    assert base.exists()
    assert (base / ".env").exists()
    assert any(str(base) in item for item in report.removed)


def test_purge_removes_data_and_web_state(home: Path) -> None:
    base = _make_base(home)
    webkit = home / "Library" / "WebKit" / "org.bimos.app"
    webkit.mkdir(parents=True)
    preferences = home / "Library" / "Preferences" / "org.bimos.app.plist"
    preferences.parent.mkdir(parents=True)
    preferences.write_text("plist\n", encoding="utf-8")

    report = purge.purge(base_path=base, remove_app=False)

    assert report.ok(), report.as_dict()
    assert not base.exists()
    assert not webkit.exists()
    assert not preferences.exists()


def test_purge_keeps_the_app_bundle_by_default(home: Path) -> None:
    base = _make_base(home)
    app = home / "Applications" / "BIMOS.app"
    app.mkdir(parents=True)

    purge.purge(base_path=base, extra_app_paths=[app])

    assert app.exists()
    assert not base.exists()


def test_purge_can_remove_the_app_bundle(home: Path) -> None:
    base = _make_base(home)
    app = home / "Applications" / "BIMOS.app"
    app.mkdir(parents=True)

    report = purge.purge(base_path=base, remove_app=True, extra_app_paths=[app])

    assert report.ok(), report.as_dict()
    assert not app.exists()


def test_keep_data_preserves_the_base_directory(home: Path) -> None:
    base = _make_base(home)
    webkit = home / "Library" / "WebKit" / "org.bimos.app"
    webkit.mkdir(parents=True)

    report = purge.purge(base_path=base, keep_data=True)

    assert base.exists()
    assert (base / "workspace" / "job.txt").exists()
    assert not webkit.exists()
    assert any("--keep-data" in item for item in report.skipped)


def test_purge_is_idempotent(home: Path) -> None:
    base = _make_base(home)

    first = purge.purge(base_path=base)
    second = purge.purge(base_path=base)

    assert first.ok()
    assert second.ok()
    assert second.removed == []
    assert second.remaining == []


def test_unsafe_paths_are_rejected(home: Path) -> None:
    for unsafe in (Path("/"), Path.home(), Path.home().parent):
        with pytest.raises(purge.UnsafePathError):
            purge.assert_safe_path(unsafe)


def test_symlink_target_is_never_deleted(home: Path) -> None:
    target = home / "precious"
    target.mkdir()
    (target / "keep.txt").write_text("keep\n", encoding="utf-8")
    link = home / "link"
    link.symlink_to(target, target_is_directory=True)

    report = purge.PurgeReport()
    purge.remove_residue(
        purge.Residue(kind="dir", description="link", path=link), report
    )

    assert not link.exists()
    assert (target / "keep.txt").exists()
    assert report.errors == []


def test_custom_base_path_requires_bimos_markers(home: Path) -> None:
    custom = home / "random-folder"
    custom.mkdir()
    (custom / "notes.txt").write_text("not bimos\n", encoding="utf-8")

    with pytest.raises(purge.UnsafePathError):
        purge.purge(base_path=custom)

    report = purge.purge(base_path=custom, force_path=True)
    assert report.ok(), report.as_dict()
    assert not custom.exists()


def test_custom_base_path_with_paths_manifest_is_accepted(home: Path) -> None:
    custom = home / "data"
    custom.mkdir()
    (custom / "paths.json").write_text('{"version": 1}\n', encoding="utf-8")

    report = purge.purge(base_path=custom)

    assert report.ok(), report.as_dict()
    assert not custom.exists()


def test_verify_reports_residues_and_clears_after_purge(home: Path) -> None:
    base = _make_base(home)

    before = purge.verify_purge(base_path=base)
    assert any(str(base) in item for item in before.remaining)

    purge.purge(base_path=base)
    after = purge.verify_purge(base_path=base)
    assert after.remaining == []


def test_custom_external_paths_are_discovered_and_purged(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _make_base(home)
    workspace = tmp_path / "elsewhere" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "result.txt").write_text("result\n", encoding="utf-8")
    (base / "paths.json").write_text(
        json.dumps(
            {
                "version": 1,
                "base": str(base),
                "workspace": str(workspace),
                "cache": str(base / "cache"),
                "logs": str(base / "logs"),
            }
        ),
        encoding="utf-8",
    )

    residues = purge.collect_residues(base_path=base)
    assert any(residue.path == workspace for residue in residues)

    report = purge.purge(base_path=base)
    assert report.ok(), report.as_dict()
    assert not workspace.exists()


def test_recorded_outputs_are_optional(
    home: Path, tmp_path: Path
) -> None:
    base = _make_base(home)
    jobs = base / "workspace" / ".jobs"
    jobs.mkdir(parents=True)
    output = tmp_path / "results"
    output.mkdir()
    (jobs / "abc.json").write_text(
        json.dumps({"id": "abc", "output_dir": str(output)}), encoding="utf-8"
    )

    without = purge.collect_residues(base_path=base)
    assert all(residue.path != output for residue in without)

    with_outputs = purge.collect_residues(base_path=base, include_outputs=True)
    assert any(residue.path == output for residue in with_outputs)

    report = purge.purge(base_path=base, include_outputs=True)
    assert report.ok(), report.as_dict()
    assert not output.exists()


def test_container_removal_uses_argv_and_never_shells_out(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], *, check: bool = False):  # type: ignore[no-untyped-def]
        calls.append(argv)
        import subprocess

        if argv[1] == "ps":
            return subprocess.CompletedProcess(argv, 0, "abc123\n", "")
        if argv[1] == "image":
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(purge, "container_runtime", lambda: "/usr/bin/podman")
    monkeypatch.setattr(purge, "_run", fake_run)

    report = purge.PurgeReport()
    purge.remove_residue(
        purge.Residue(
            kind="containers",
            description="image",
            image="localhost/bimos/global:latest",
        ),
        report,
    )

    assert report.errors == []
    assert ["/usr/bin/podman", "rm", "-f", "abc123"] in calls
    assert ["/usr/bin/podman", "rmi", "-f", "localhost/bimos/global:latest"] in calls
    assert all("system" not in call for call in calls)


def test_report_json_is_machine_readable() -> None:
    report = purge.PurgeReport(removed=["a"], skipped=["b"])
    payload = json.loads(json.dumps(report.as_dict()))
    assert payload["ok"] is True
    assert payload["removed"] == ["a"]
    assert set(payload) == {"ok", "dry_run", "removed", "skipped", "errors", "remaining"}


def test_cli_print_manifest_exits_zero() -> None:
    from click.testing import CliRunner

    from bimos.cli.commands.uninstall import uninstall

    result = CliRunner().invoke(uninstall, ["--print-manifest"])
    assert result.exit_code == 0
    assert json.loads(result.output)["bundle_id"] == "org.bimos.app"


def test_cli_verify_returns_three_when_residues_remain(home: Path) -> None:
    from click.testing import CliRunner

    from bimos.cli.commands.uninstall import uninstall

    base = _make_base(home)
    result = CliRunner().invoke(
        uninstall, ["--verify", "--base-path", str(base), "--json"]
    )
    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["remaining"]


def test_cli_uninstall_skips_first_run_bootstrap(monkeypatch) -> None:
    """`bimos uninstall` must not recreate ~/.bimos before deleting it."""
    from click.testing import CliRunner

    from bimos.cli import main as cli_main

    calls: list[str] = []
    monkeypatch.setattr(
        "bimos.config.settings.initialize",
        lambda *args, **kwargs: calls.append("initialize") or False,
    )
    monkeypatch.setattr(
        "bimos.config.settings.settings.ensure_dirs",
        lambda: calls.append("ensure_dirs"),
    )

    result = CliRunner().invoke(cli_main.cli, ["uninstall", "--print-manifest"])

    assert result.exit_code == 0, result.output
    assert calls == []


def test_cli_purge_without_confirmation_aborts(home: Path) -> None:
    from click.testing import CliRunner

    from bimos.cli.commands.uninstall import uninstall

    base = _make_base(home)
    result = CliRunner().invoke(
        uninstall, ["--base-path", str(base), "--json"], input=""
    )
    assert result.exit_code == 2
    assert base.exists()


def test_cli_purge_yes_removes_data(home: Path) -> None:
    from click.testing import CliRunner

    from bimos.cli.commands.uninstall import uninstall

    base = _make_base(home)
    result = CliRunner().invoke(
        uninstall, ["--yes", "--base-path", str(base), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert not base.exists()
