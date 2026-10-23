from pathlib import Path
from typing import Any

import pytest

from bimos.molecular_dynamics.pipeline import MolecularDynamicsPipeline, Stage


def test_md_pipeline_initialization(tmp_path: Path) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path / "md_out"))
    assert pipeline.output_dir.exists()


def test_clean_pdb(tmp_path: Path) -> None:
    input_pdb = tmp_path / "input.pdb"
    input_pdb.write_text(
        "ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n"
        "HETATM    2  O   HOH A   2      13.000  10.000   9.000  1.00  0.00           O\n"
        "ATOM      3  CA  MET A   1      13.695   9.565   8.214  1.00  0.00           C\n"
        "END\n"
    )
    output_pdb = tmp_path / "output.pdb"
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    pipeline._clean_pdb(input_pdb, output_pdb)
    content = output_pdb.read_text()
    assert "HOH" not in content
    assert "MET" in content


def test_detect_stage_returns_prep(tmp_path: Path) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    stage = pipeline._detect_stage(tmp_path, "Apo-protein", is_holo=False)
    assert stage == Stage.PREP


def test_detect_resname(tmp_path: Path) -> None:
    gro = tmp_path / "ligand.gro"
    gro.write_text(
        "Ligand\n"
        "    5\n"
        "    1LIG     C    1   0.000   0.000   0.000\n"
        "    2LIG     C    2   1.234   0.000   0.000\n"
        "    3LIG     C    3   2.345   1.234   0.000\n"
        "    4LIG     H    4   2.800   1.800   0.000\n"
        "    5LIG     O    5   1.500   2.000   0.000\n"
        "   1.000   1.000   1.000\n"
    )
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    resname = pipeline._detect_resname(gro)
    assert resname == "LIG"


def test_log_has(tmp_path: Path) -> None:
    log = tmp_path / "test.log"
    log.write_text("Finished mdrun on rank 0\n")
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    assert pipeline._log_contains(tmp_path, "test.log", "Finished mdrun") is True
    assert pipeline._log_contains(tmp_path, "test.log", "not found") is False


def test_log_has_missing_file(tmp_path: Path) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    assert pipeline._log_contains(tmp_path, "missing.log", "anything") is False


def test_fix_histidines(tmp_path: Path) -> None:
    input_pdb = tmp_path / "input.pdb"
    input_pdb.write_text(
        "ATOM      1  N   HIS A   1      12.234   9.679   8.022  1.00  0.00           N\n"
        "ATOM      2  CA  HIS A   1      13.695   9.565   8.214  1.00  0.00           C\n"
        "ATOM      3  HD1 HIS A   1      14.000  10.000   9.000  1.00  0.00           H\n"
        "ATOM      4  HE2 HIS A   1      15.000  11.000  10.000  1.00  0.00           H\n"
        "END\n"
    )
    output_pdb = tmp_path / "output.pdb"
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    pipeline._fix_histidines(input_pdb, output_pdb)
    content = output_pdb.read_text()
    assert "HISH" in content


def test_get_box(tmp_path: Path) -> None:
    gro = tmp_path / "box.gro"
    gro.write_text("System\n    1\n    1MET  C    1   0.000   0.000   0.000\n   5.0   5.0   5.0\n")
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    box = pipeline._get_box(gro)
    assert box == ["5.0", "5.0", "5.0"]


def test_get_parallel_args(monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "get_threads", lambda: 4)
    pipeline = MolecularDynamicsPipeline(output_dir="/tmp")
    args = pipeline._get_parallel_args()
    assert args == ["-ntmpi", "1", "-ntomp", "4"]


def _minimization_fake(converged: bool = True, rc: int = 0) -> Any:
    calls: list[list[str]] = []

    def _gmx(args: list[str], work: Path, stdin: str = "") -> int:
        calls.append(args)
        if args[0] == "mdrun" and rc == 0:
            log_name = args[args.index("-g") + 1]
            (work / log_name).write_text(
                "Converged to Fmax!\n" if converged else "did not converge to Fmax\n"
            )
        return rc

    return calls, _gmx


def test_minimization_uses_explicit_log_and_convergence(tmp_path: Path, monkeypatch) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    calls, fake = _minimization_fake()
    monkeypatch.setattr(pipeline, "_gmx", fake)

    pipeline._run_minimization("comp", tmp_path, is_holo=False)

    assert (tmp_path / "min-comp-steep-mdrun.log").exists()
    assert (tmp_path / "min-comp-cg-mdrun.log").exists()
    mdrun_calls = [args for args in calls if args[0] == "mdrun"]
    assert len(mdrun_calls) == 2
    assert all("-g" in args for args in mdrun_calls)


def test_minimization_fails_on_grompp_error(tmp_path: Path, monkeypatch) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    _, fake = _minimization_fake(rc=1)
    monkeypatch.setattr(pipeline, "_gmx", fake)

    with pytest.raises(RuntimeError, match="grompp failed"):
        pipeline._run_minimization("comp", tmp_path, is_holo=False)


def test_minimization_fails_without_log(tmp_path: Path, monkeypatch) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))

    def _gmx(args: list[str], work: Path, stdin: str = "") -> int:
        return 0

    monkeypatch.setattr(pipeline, "_gmx", _gmx)

    with pytest.raises(RuntimeError, match="no minimization log"):
        pipeline._run_minimization("comp", tmp_path, is_holo=False)


def test_minimization_continues_after_max_iterations_without_convergence(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    calls, fake = _minimization_fake(converged=False)
    monkeypatch.setattr(pipeline, "_gmx", fake)
    # Force a single iteration per integrator so the max-iterations path is exercised.
    object.__setattr__(pipeline.md_config, "max_min_iterations", 1)

    with caplog.at_level("WARNING", logger="bimos.molecular_dynamics"):
        pipeline._run_minimization("comp", tmp_path, is_holo=False)

    mdrun_calls = [args for args in calls if args[0] == "mdrun"]
    assert len(mdrun_calls) == 2
    assert "without Fmax convergence" in caplog.text


def test_detect_stage_requires_finished_minimization_logs(tmp_path: Path) -> None:
    (tmp_path / "min-comp.gro").write_text("gro\n")
    (tmp_path / "comp.top").write_text("top\n")
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))

    assert pipeline._detect_stage(tmp_path, "comp", is_holo=False) == Stage.MINIMIZATION

    (tmp_path / "min-comp-steep-mdrun.log").write_text(
        "Converged to Fmax!\nFinished mdrun on rank 0\n"
    )
    (tmp_path / "min-comp-cg-mdrun.log").write_text(
        "Converged to Fmax!\nFinished mdrun on rank 0\n"
    )
    assert pipeline._detect_stage(tmp_path, "comp", is_holo=False) == Stage.NVT

    (tmp_path / "min-comp-cg-mdrun.log").write_text(
        "did not converge to Fmax\nFinished mdrun on rank 0\n"
    )
    assert pipeline._detect_stage(tmp_path, "comp", is_holo=False) == Stage.NVT

    (tmp_path / "min-comp-cg-mdrun.log").write_text("did not converge to Fmax\n")
    assert pipeline._detect_stage(tmp_path, "comp", is_holo=False) == Stage.MINIMIZATION


def test_minimization_trjcat_uses_container_relative_paths(tmp_path: Path, monkeypatch) -> None:
    pipeline = MolecularDynamicsPipeline(output_dir=str(tmp_path))
    calls: list[list[str]] = []
    cg_runs = 0

    def _gmx(args: list[str], work: Path, stdin: str = "") -> int:
        nonlocal cg_runs
        calls.append(args)
        if args[0] == "trjcat":
            (work / args[args.index("-o") + 1]).write_bytes(b"joined")
            return 0
        if args[0] != "mdrun":
            return 0
        opts = {args[i]: args[i + 1] for i in range(len(args) - 1) if args[i].startswith("-")}
        (work / f"{opts['-deffnm']}.trr").write_bytes(b"trajectory")
        log_name = opts["-g"]
        if "-cg-" in log_name:
            cg_runs += 1
        converged = not ("-cg-" in log_name and cg_runs == 1)
        (work / log_name).write_text(
            "Converged to Fmax!\n" if converged else "did not converge to Fmax\n"
        )
        return 0

    monkeypatch.setattr(pipeline, "_gmx", _gmx)
    pipeline._run_minimization("comp", tmp_path, is_holo=False)

    trjcat_calls = [args for args in calls if args[0] == "trjcat"]
    assert trjcat_calls, "expected the second CG iteration to concatenate trajectories"
    assert trjcat_calls[0][2] == "min-comp-traj.trr"
    assert trjcat_calls[0][3] == "min-comp.trr"
    assert not any(arg.startswith("/") for arg in trjcat_calls[0])
