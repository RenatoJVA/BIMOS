import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from bimos.docking.pipeline import DockingPipeline
from bimos.docking.sdf import split_multi_molecule_sdf


def test_docking_pipeline_initialization(tmp_path: Path) -> None:
    pipeline = DockingPipeline(output_dir=str(tmp_path / "dock_out"))
    assert pipeline.output_dir.exists()
    assert (pipeline.output_dir / "proteins").exists()
    assert (pipeline.output_dir / "ligands").exists()
    assert (pipeline.output_dir / "results").exists()
    assert (pipeline.output_dir / "results" / "bests").exists()


def test_docking_pipeline_file_not_found(tmp_path: Path) -> None:
    pipeline = DockingPipeline(output_dir=str(tmp_path / "dock_out"))
    with pytest.raises(FileNotFoundError, match="not found"):
        pipeline.run(
            protein_pdb=str(tmp_path / "nonexistent.pdb"),
            ligands_sdf=str(tmp_path / "nonexistent.sdf"),
        )


def test_docking_pipeline_full_flow(mock_container, tmp_path: Path, sample_receptor: Path, sample_ligands: Path) -> None:
    pipeline = DockingPipeline(output_dir=str(tmp_path / "dock_out"))
    def mock_prepare_receptor(pdb_path):
        pdbqt = pdb_path.with_suffix(".pdbqt")
        pdbqt.write_text("ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n")
        return pdbqt
    def mock_prepare_ligand(sdf_path):
        pdbqt = sdf_path.with_suffix(".pdbqt")
        pdbqt.write_text("REMARK VINA RESULT:    -7.5   0.000   0.000\nATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n")
        return pdbqt
    def mock_write_conf(pdbqt_path, conf_path):
        conf_path.write_text("center_x = 0.0\ncenter_y = 0.0\ncenter_z = 0.0\n")
    def mock_container_run(cmd, work_dir):
        out_flag = cmd.index("--out") + 1 if "--out" in cmd else None
        if out_flag:
            out_path = work_dir / cmd[out_flag]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("REMARK VINA RESULT:    -7.5   0.000   0.000\n")
        return 0
    with patch.object(pipeline, "_prepare_receptor", side_effect=mock_prepare_receptor):
        with patch.object(pipeline, "_prepare_ligand", side_effect=mock_prepare_ligand):
            with patch.object(pipeline, "_write_grid_box_conf", side_effect=mock_write_conf):
                with patch.object(pipeline, "_container_run", side_effect=mock_container_run):
                    with patch("bimos.docking.pipeline.split_multi_molecule_sdf", return_value=[tmp_path / "lig1.sdf"]):
                        result = pipeline.run(
                            protein_pdb=str(sample_receptor),
                            ligands_sdf=str(sample_ligands),
                        )
    assert result["status"] == "completed"
    assert "output_dir" in result


def test_read_coords(tmp_path: Path) -> None:
    pdbqt = tmp_path / "test.pdbqt"
    pdbqt.write_text(
        "ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n"
        "ATOM      2  CA  MET A   1      13.695   9.565   8.214  1.00  0.00           C\n"
    )
    xs, ys, zs = DockingPipeline._read_coords(pdbqt)
    assert len(xs) == 2
    assert xs == [12.234, 13.695]
    assert ys == [9.679, 9.565]
    assert zs == [8.022, 8.214]


def test_read_coords_empty(tmp_path: Path) -> None:
    pdbqt = tmp_path / "empty.pdbqt"
    pdbqt.write_text("REMARK no atoms\n")
    xs, ys, zs = DockingPipeline._read_coords(pdbqt)
    assert xs == []
    assert ys == []
    assert zs == []


def test_extract_best_score(tmp_path: Path) -> None:
    pdbqt = tmp_path / "out.pdbqt"
    pdbqt.write_text(
        "REMARK VINA RESULT:    -7.5   0.000   0.000\n"
        "ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n"
    )
    score = DockingPipeline._extract_best_score(pdbqt)
    assert score == -7.5


def test_extract_best_score_no_remark(tmp_path: Path) -> None:
    pdbqt = tmp_path / "no_score.pdbqt"
    pdbqt.write_text("ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n")
    score = DockingPipeline._extract_best_score(pdbqt)
    assert score is None


def test_run_docking_pipeline_function(mock_container, tmp_path: Path, sample_receptor: Path, sample_ligands: Path) -> None:
    from bimos.docking.pipeline import DockingPipeline, run_docking_pipeline
    out_dir = tmp_path / "dock_func"
    def mock_prepare_receptor(pdb_path):
        pdbqt = pdb_path.with_suffix(".pdbqt")
        pdbqt.parent.mkdir(parents=True, exist_ok=True)
        pdbqt.write_text("ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n")
        return pdbqt
    def mock_prepare_ligand(sdf_path):
        pdbqt = sdf_path.with_suffix(".pdbqt")
        pdbqt.write_text("REMARK VINA RESULT:    -7.5   0.000   0.000\nATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\n")
        return pdbqt
    def mock_write_conf(pdbqt_path, conf_path):
        conf_path.parent.mkdir(parents=True, exist_ok=True)
        conf_path.write_text("center_x = 0.0\n")
    def mock_container_run(cmd, work_dir):
        out_flag = cmd.index("--out") + 1 if "--out" in cmd else None
        if out_flag:
            out_path = work_dir / cmd[out_flag]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("REMARK VINA RESULT:    -7.5   0.000   0.000\n")
        return 0
    with patch.object(DockingPipeline, "_prepare_receptor", side_effect=mock_prepare_receptor):
        with patch.object(DockingPipeline, "_prepare_ligand", side_effect=mock_prepare_ligand):
            with patch.object(DockingPipeline, "_write_grid_box_conf", side_effect=mock_write_conf):
                with patch.object(DockingPipeline, "_container_run", side_effect=mock_container_run):
                    with patch("bimos.docking.pipeline.split_multi_molecule_sdf", return_value=[tmp_path / "lig1.sdf"]):
                        result = run_docking_pipeline(
                            protein_pdb=str(sample_receptor),
                            ligands_sdf=str(sample_ligands),
                            output_dir=str(out_dir),
                        )
                        assert result["status"] == "completed"


def test_split_multi_molecule_sdf(tmp_path: Path, sample_ligands: Path) -> None:
    files = split_multi_molecule_sdf(sample_ligands, tmp_path)
    assert len(files) == 2
    for f in files:
        assert f.exists()
        assert f.suffix == ".sdf"


def test_split_sdf_empty(tmp_path: Path) -> None:
    empty = tmp_path / "empty.sdf"
    empty.write_text("")
    files = split_multi_molecule_sdf(empty, tmp_path / "output")
    assert files == []
