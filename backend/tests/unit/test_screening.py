"""Unit tests for the screening cascade (stage functions mocked, no containers)."""

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from bimos.cli.main import cli
from bimos.screening.cascade import ScreenCascade


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "LIG-DIN"
    lib.mkdir()
    for stem in ("JZ4", "L2"):
        (lib / f"{stem}.gro").write_text("TITLE\n1\n    1LIG     C    1   0.0 0.0 0.0\n 1.0 1.0 1.0\n")
        (lib / f"{stem}.itp").write_text("[ moleculetype ]\nJZ4 3\n")
    return lib


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, str]:
    pdb = tmp_path / "3HTB.pdb"
    pdb.write_text("ATOM      1  N   MET A   1      1.0 2.0 3.0  1.00  0.00           N\nEND\n")
    sdf = tmp_path / "ligs.sdf"
    sdf.write_text("m\n  t\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n")
    return {"protein": str(pdb), "sdf": str(sdf)}


def _ranking() -> list[dict[str, Any]]:
    return [
        {"complex": "3HTB-AAA", "best_pose": "/x/3HTB-AAA-1.pdbqt", "best_score_kcal_mol": -9.0},
        {"complex": "3HTB-JZ4", "best_pose": "/x/3HTB-JZ4-1.pdbqt", "best_score_kcal_mol": -8.0},
        {"complex": "3HTB-L2", "best_pose": "/x/3HTB-L2-1.pdbqt", "best_score_kcal_mol": -6.0},
    ]


def test_select_top_n_skips_missing_pair(tmp_path: Path, library: Path) -> None:
    cascade = ScreenCascade(output_dir=str(tmp_path / "s"))
    selections = cascade._select_top_n(_ranking(), library)
    assert [s["candidate"] for s in selections] == ["JZ4", "L2"]
    assert selections[0]["score"] == pytest.approx(-8.0)


def test_select_top_n_respects_limit(tmp_path: Path, library: Path) -> None:
    cascade = ScreenCascade(output_dir=str(tmp_path / "s"), top_n=1)
    selections = cascade._select_top_n(_ranking(), library)
    assert [s["candidate"] for s in selections] == ["JZ4"]


def test_select_top_n_cutoff_aborts(tmp_path: Path, library: Path) -> None:
    cascade = ScreenCascade(output_dir=str(tmp_path / "s"), min_score=-9.5)
    with pytest.raises(RuntimeError, match="No viable candidate"):
        cascade._select_top_n(_ranking(), library)


def test_select_top_n_empty_aborts(tmp_path: Path, library: Path) -> None:
    cascade = ScreenCascade(output_dir=str(tmp_path / "s"))
    with pytest.raises(RuntimeError, match="No viable candidate"):
        cascade._select_top_n([], library)


def test_top_n_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="top_n"):
        ScreenCascade(output_dir=str(tmp_path / "s"), top_n=0)


def _install_mocks(monkeypatch: pytest.MonkeyPatch, ranking: list[dict[str, Any]]) -> dict[str, int]:
    calls = {"md": 0, "dock": 0, "qm": 0}

    def _md(**kwargs: Any) -> dict[str, Any]:
        calls["md"] += 1
        out = Path(str(kwargs["output_dir"])) / "comp"
        out.mkdir(parents=True, exist_ok=True)
        return {"status": "completed", "output_dir": str(out)}

    def _dock(**kwargs: Any) -> dict[str, Any]:
        calls["dock"] += 1
        return {"status": "completed", "results": ranking, "output_dir": str(kwargs["output_dir"])}

    def _qm(directory: str, **kwargs: Any) -> dict[str, Any]:
        calls["qm"] += 1
        qm_dir = Path(directory)
        gro = next(qm_dir.glob("*.gro"))
        hirsh = gro.with_name(f"{gro.stem}-hirsh.itp")
        hirsh.write_text("[ atoms ]\n")
        return {"status": "completed", "results": [str(hirsh)]}

    monkeypatch.setattr("bimos.screening.cascade.run_md_simulation", _md)
    monkeypatch.setattr("bimos.screening.cascade.run_docking_pipeline", _dock)
    monkeypatch.setattr("bimos.screening.cascade.run_orca_pipeline", _qm)
    return calls


def test_full_run_to_report(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_mocks(monkeypatch, _ranking())
    out = tmp_path / "screen"
    result = ScreenCascade(output_dir=str(out)).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )
    assert result["status"] == "completed"
    assert result["candidates"] == ["JZ4", "L2"]
    assert result["candidate"] == "JZ4"  # singular alias = best hit
    assert len(result["holo_dirs"]) == 2
    assert Path(result["report"]).exists()
    assert calls == {"md": 3, "dock": 1, "qm": 2}  # APO + 2 HOLO
    report = Path(result["report"]).read_text()
    assert "JZ4" in report and "holo_ok" in report


def test_top_n_one_runs_single_holo(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_mocks(monkeypatch, _ranking())
    result = ScreenCascade(output_dir=str(tmp_path / "s"), top_n=1).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )
    assert result["candidates"] == ["JZ4"]
    assert calls == {"md": 2, "dock": 1, "qm": 1}


def test_failed_hit_continues_with_rest(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_mocks(monkeypatch, _ranking())

    def _qm_flaky(directory: str, **kwargs: Any) -> dict[str, Any]:
        if "JZ4" in directory:
            raise RuntimeError("orca down")
        qm_dir = Path(directory)
        gro = next(qm_dir.glob("*.gro"))
        hirsh = gro.with_name(f"{gro.stem}-hirsh.itp")
        hirsh.write_text("[ atoms ]\n")
        return {"status": "completed", "results": [str(hirsh)]}

    monkeypatch.setattr("bimos.screening.cascade.run_orca_pipeline", _qm_flaky)
    result = ScreenCascade(output_dir=str(tmp_path / "s")).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )
    assert result["status"] == "completed"
    assert result["candidates"] == ["JZ4", "L2"]
    assert result["holo_dirs"][0] == ""
    assert result["holo_dirs"][1] != ""


def test_all_hits_fail_aborts(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_mocks(monkeypatch, _ranking())
    monkeypatch.setattr(
        "bimos.screening.cascade.run_orca_pipeline",
        lambda directory, **kwargs: (_ for _ in ()).throw(RuntimeError("orca down")),
    )
    with pytest.raises(RuntimeError, match="failed for all hits"):
        ScreenCascade(output_dir=str(tmp_path / "s")).run(
            protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
        )


def test_resume_skips_completed_stages(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_mocks(monkeypatch, _ranking())
    out = tmp_path / "screen"
    ScreenCascade(output_dir=str(out)).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )

    def _boom(**kwargs: Any) -> Any:
        raise AssertionError("should not re-run completed stages")

    monkeypatch.setattr("bimos.screening.cascade.run_md_simulation", _boom)
    monkeypatch.setattr("bimos.screening.cascade.run_docking_pipeline", _boom)
    monkeypatch.setattr("bimos.screening.cascade.run_orca_pipeline", _boom)
    result = ScreenCascade(output_dir=str(out)).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )
    assert result["status"] == "completed"
    assert result["candidates"] == ["JZ4", "L2"]


def test_legacy_single_selection_state_migrates(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "screen"
    (out / "holo").mkdir(parents=True)
    legacy = {
        "stage": "report",
        "artifacts": {
            "ranking": _ranking(),
            "selection": {"candidate": "JZ4", "gro": "g", "itp": "i", "score": -8.0},
            "hirsh_itp": "h",
            "holo_dir": "d",
        },
    }
    (out / "screen.json").write_text(json.dumps(legacy))
    result = ScreenCascade(output_dir=str(out)).run(
        protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
    )
    assert result["status"] == "completed"
    assert result["candidates"] == ["JZ4"]


def test_dock_without_results_aborts(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_mocks(monkeypatch, [])
    with pytest.raises(RuntimeError, match="no valid poses"):
        ScreenCascade(output_dir=str(tmp_path / "s")).run(
            protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
        )


def test_qm_without_charges_aborts(
    tmp_path: Path, library: Path, inputs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_mocks(monkeypatch, _ranking())
    monkeypatch.setattr(
        "bimos.screening.cascade.run_orca_pipeline",
        lambda directory, **kwargs: {"status": "completed", "results": []},
    )
    with pytest.raises(RuntimeError, match="failed for all hits"):
        ScreenCascade(output_dir=str(tmp_path / "s")).run(
            protein=inputs["protein"], ligands_sdf=inputs["sdf"], ligand_dir=str(library)
        )


def test_run_rejects_conflicting_inputs(tmp_path: Path, library: Path, inputs: dict[str, str]) -> None:
    cascade = ScreenCascade(output_dir=str(tmp_path / "s"))
    with pytest.raises(ValueError, match="mutually exclusive"):
        cascade.run(ligands_sdf=inputs["sdf"], ligand_dir=str(library))
    with pytest.raises(ValueError, match="mutually exclusive"):
        cascade.run(protein=inputs["protein"], ligand_dir=str(library))


def test_screen_help_has_examples() -> None:
    result = CliRunner().invoke(cli, ["screen", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output
    assert "--ligand-dir" in result.output
    assert "--top-n" in result.output


def test_screen_requires_ligand_dir(tmp_path: Path) -> None:
    pdb = tmp_path / "p.pdb"
    pdb.write_text("ATOM\n")
    result = CliRunner().invoke(cli, ["screen", "-p", str(pdb)])
    assert result.exit_code != 0


def test_screen_rejects_protein_conflict(tmp_path: Path, library: Path, inputs: dict[str, str]) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "screen",
            "-p",
            inputs["protein"],
            "--protein-eq",
            inputs["protein"],
            "--ligands",
            inputs["sdf"],
            "--ligand-dir",
            str(library),
        ],
    )
    assert result.exit_code != 0


def test_screen_rejects_top_n_zero(tmp_path: Path, library: Path, inputs: dict[str, str]) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "screen",
            "-p",
            inputs["protein"],
            "--ligands",
            inputs["sdf"],
            "--ligand-dir",
            str(library),
            "--top-n",
            "0",
        ],
    )
    assert result.exit_code != 0
