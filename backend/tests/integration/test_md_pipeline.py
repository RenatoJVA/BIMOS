from pathlib import Path
from unittest.mock import MagicMock, patch

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
