"""Unit tests for directed docking grid (pure Python, no containers)."""

from pathlib import Path

import pytest

from bimos.docking.config import DockingConfig
from bimos.docking.pipeline import DockingPipeline

PDBQT = """ATOM      1  CA  GLU A 375      10.000  10.000  10.000  1.00  0.00           C
ATOM      2  CB  GLU A 375      12.000  10.000  10.000  1.00  0.00           C
ATOM      3  NE2 HIS A 347       0.000   0.000   0.000  1.00  0.00           N
"""

SDF_REF = """ref
  test

  2  1  0  0  0  0            999 V2000
   10.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   12.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
"""


def _receptor(tmp_path: Path) -> Path:
    pdbqt = tmp_path / "rec.pdbqt"
    pdbqt.write_text(PDBQT)
    return pdbqt


def test_config_manual_overrides_ok() -> None:
    cfg = DockingConfig.resolve(
        center_x=1.0, center_y=2.0, center_z=3.0, size_x=20.0, size_y=20.0, size_z=20.0, mode="manual"
    )
    assert cfg.grid_mode == "manual"
    assert (cfg.center_x, cfg.size_x) == (1.0, 20.0)


def test_config_manual_partial_raises() -> None:
    with pytest.raises(ValueError, match="manual"):
        DockingConfig.resolve(mode="manual", center_x=1.0)


def test_config_bad_mode_raises() -> None:
    with pytest.raises(ValueError, match="mode"):
        DockingConfig.resolve(mode="sphere")


def test_config_bad_size_raises() -> None:
    with pytest.raises(ValueError, match="size_x"):
        DockingConfig.resolve(
            mode="manual", center_x=0.0, center_y=0.0, center_z=0.0,
            size_x=0.0, size_y=20.0, size_z=20.0,
        )


def test_config_non_numeric_raises() -> None:
    with pytest.raises(ValueError, match="numeric"):
        DockingConfig.resolve(mode="manual", center_x="abc")


def test_init_rejects_center_without_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="together"):
        DockingPipeline(output_dir=str(tmp_path), center=(1.0, 2.0, 3.0))


def test_init_rejects_conflict(tmp_path: Path) -> None:
    ref = tmp_path / "ref.sdf"
    ref.write_text(SDF_REF)
    with pytest.raises(ValueError, match="incompatible"):
        DockingPipeline(
            output_dir=str(tmp_path), center=(1.0, 2.0, 3.0), size=(20.0, 20.0, 20.0),
            center_on=str(ref),
        )


def test_init_rejects_missing_reference(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Reference ligand"):
        DockingPipeline(output_dir=str(tmp_path), center_on=str(tmp_path / "no.sdf"))


def test_init_rejects_bad_pocket(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        DockingPipeline(output_dir=str(tmp_path), pocket_residues="ABC")


def test_init_rejects_lone_padding(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="padding"):
        DockingPipeline(output_dir=str(tmp_path), padding=4.0)


def test_resolve_explicit(tmp_path: Path) -> None:
    pipe = DockingPipeline(
        output_dir=str(tmp_path), center=(1.0, 2.0, 3.0), size=(20.0, 22.0, 24.0)
    )
    mode, center, size = pipe._resolve_grid(_receptor(tmp_path))
    assert mode == "manual"
    assert center == (1.0, 2.0, 3.0)
    assert size == (20.0, 22.0, 24.0)


def test_resolve_center_on(tmp_path: Path) -> None:
    ref = tmp_path / "ref.sdf"
    ref.write_text(SDF_REF)
    pipe = DockingPipeline(output_dir=str(tmp_path), center_on=str(ref), padding=4.0)
    mode, center, size = pipe._resolve_grid(_receptor(tmp_path))
    assert mode == "center-on"
    assert center == pytest.approx((11.0, 0.0, 0.0))
    assert size == pytest.approx((6.0, 5.0, 5.0))


def test_resolve_pocket(tmp_path: Path) -> None:
    pipe = DockingPipeline(output_dir=str(tmp_path), pocket_residues="A:375", padding=4.0)
    mode, center, size = pipe._resolve_grid(_receptor(tmp_path))
    assert mode == "pocket"
    assert center == pytest.approx((11.0, 10.0, 10.0))
    assert size == pytest.approx((6.0, 5.0, 5.0))


def test_resolve_yaml_manual(tmp_path: Path) -> None:
    pipe = DockingPipeline(
        output_dir=str(tmp_path), mode="manual",
        center_x=1.0, center_y=2.0, center_z=3.0, size_x=20.0, size_y=20.0, size_z=20.0,
    )
    mode, center, size = pipe._resolve_grid(_receptor(tmp_path))
    assert mode == "manual"
    assert center == (1.0, 2.0, 3.0)


def test_resolve_auto_default(tmp_path: Path) -> None:
    pipe = DockingPipeline(output_dir=str(tmp_path))
    mode, center, size = pipe._resolve_grid(_receptor(tmp_path))
    assert mode == "auto"
    # Centroid of (10,10,10),(12,10,10),(0,0,0) with default margin 1.0.
    assert center == pytest.approx((22 / 3, 20 / 3, 20 / 3))
    assert size[0] == pytest.approx(12.0 + pipe.config.margin)


def test_write_conf_manual_content(tmp_path: Path) -> None:
    pipe = DockingPipeline(
        output_dir=str(tmp_path), center=(1.5, 2.5, 3.5), size=(20.0, 20.0, 20.0)
    )
    conf = tmp_path / "box.conf"
    pipe._write_grid_box_conf(_receptor(tmp_path), conf)
    text = conf.read_text()
    assert "center_x = 1.5" in text
    assert "size_z = 20.0" in text


def test_write_conf_warns_blind_de_facto(tmp_path: Path) -> None:
    logged: list[str] = []
    pipe = DockingPipeline(
        output_dir=str(tmp_path),
        on_output=logged.append,
        center=(6.0, 5.0, 5.0),
        size=(50.0, 50.0, 50.0),
    )
    pipe._write_grid_box_conf(_receptor(tmp_path), tmp_path / "box.conf")
    assert any("blind" in line for line in logged)
