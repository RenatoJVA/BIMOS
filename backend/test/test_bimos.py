"""
BIMOS Test Suite — uses test/1AKI.pdb (lysozyme) as a real input.

Tests verify:
  1. Container runtime is detected.
  2. FASTA parsing and YAML generation produce valid output.
  3. Grid box calculation from PDB coordinates is correct.
  4. SDF splitting works.
  5. Job store creates, updates, and queries records.
  6. CLI --help is reachable for all commands.

These tests do NOT start containers (no network/image required).
Use them to validate the logic layer before running real pipelines.
"""

import pytest
from pathlib import Path
from click.testing import CliRunner
from bimos.cli.main import cli

TEST_DIR = Path(__file__).parent
PDB_FILE = TEST_DIR / "1AKI.pdb"

# ── 1. Container runtime ──────────────────────────────────────────────────────

def test_container_runtime_detected():
    from bimos.config.settings import settings
    runtime = settings.container_runtime()
    assert runtime in ("podman", "docker"), f"Unknown runtime: {runtime}"


# ── 2. FASTA parsing / YAML generation ───────────────────────────────────────

def test_build_yaml_single_sequence(tmp_path):
    from bimos.core.protein import _build_yaml

    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">test_protein\nMKTAYIAKQRQISFVKSHFSRQ\n")

    yaml_out = tmp_path / "seq.yaml"
    seq = _build_yaml(fasta, yaml_out)

    assert yaml_out.exists()
    content = yaml_out.read_text()
    assert "sequences:" in content
    assert "MKTAYIAKQRQISFVKSHFSRQ" in content
    assert seq == "MKTAYIAKQRQISFVKSHFSRQ"


def test_build_yaml_multi_sequence(tmp_path):
    from bimos.core.protein import _build_yaml

    fasta = tmp_path / "multi.fasta"
    fasta.write_text(">chain_A\nACDEFGH\n>chain_B\nKLMNPQR\n")

    yaml_out = tmp_path / "multi.yaml"
    seq = _build_yaml(fasta, yaml_out)

    assert "ACDEFGH" in seq
    assert "KLMNPQR" in seq
    assert ":" in seq  # chains joined by ":"


def test_build_yaml_empty_fasta_raises(tmp_path):
    from bimos.core.protein import _build_yaml

    fasta = tmp_path / "empty.fasta"
    fasta.write_text("")

    with pytest.raises(ValueError, match="No sequences"):
        _build_yaml(fasta, tmp_path / "out.yaml")


# ── 3. Grid box calculation ───────────────────────────────────────────────────

def test_grid_box_uses_real_pdb(tmp_path):
    from bimos.core.docking import _read_coords, _grid_box_conf

    assert PDB_FILE.exists(), "test/1AKI.pdb not found"

    xs, ys, zs = _read_coords(PDB_FILE)
    assert len(xs) > 0, "No ATOM/HETATM coordinates in 1AKI.pdb"

    conf_path = tmp_path / "receptor.conf"
    _grid_box_conf(
        pdbqt_path=PDB_FILE,
        conf_path=conf_path,
        margin=1.0,
        num_modes=9,
        energy_range=3.0,
        exhaustiveness=8,
    )

    assert conf_path.exists()
    content = conf_path.read_text()
    assert "center_x" in content
    assert "size_x" in content
    assert "exhaustiveness = 8" in content


def test_grid_box_empty_pdb_raises(tmp_path):
    from bimos.core.docking import _grid_box_conf

    empty_pdb = tmp_path / "empty.pdb"
    empty_pdb.write_text("HEADER empty\n")

    with pytest.raises(ValueError, match="No ATOM/HETATM"):
        _grid_box_conf(empty_pdb, tmp_path / "out.conf",
                       margin=1.0, num_modes=9, energy_range=3.0, exhaustiveness=8)


# ── 4. SDF splitting ─────────────────────────────────────────────────────────

_MINIMAL_SDF = """\
aspirin
  RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
$$$$
ibuprofen
  RDKit          3D

  2  1  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.5000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
M  END
$$$$
"""


def test_split_sdf_two_molecules(tmp_path):
    from bimos.core.docking import _split_sdf

    sdf = tmp_path / "ligands.sdf"
    sdf.write_text(_MINIMAL_SDF)

    result = _split_sdf(sdf, tmp_path / "split")
    assert len(result) == 2
    names = [p.stem for p in result]
    assert "aspirin" in names
    assert "ibuprofen" in names


def test_split_sdf_empty_file(tmp_path):
    from bimos.core.docking import _split_sdf

    sdf = tmp_path / "empty.sdf"
    sdf.write_text("")
    result = _split_sdf(sdf, tmp_path / "split")
    assert result == []


# ── 5. Job store ──────────────────────────────────────────────────────────────

def test_job_lifecycle():
    from bimos.infrastructure.job_store import JobStore, JobStatus

    s = JobStore()
    job = s.create(kind="predict", meta={"fasta": "seq.fasta"})

    assert s.get(job.id) is not None
    assert s.get(job.id).status == JobStatus.PENDING

    s.start(job.id)
    assert s.get(job.id).status == JobStatus.RUNNING

    s.log(job.id, "step 1 done")
    assert "step 1 done" in s.get_logs(job.id)

    s.complete(job.id, exit_code=0)
    assert s.get(job.id).status == JobStatus.COMPLETED


def test_job_failure():
    from bimos.infrastructure.job_store import JobStore, JobStatus

    s = JobStore()
    job = s.create(kind="dock")
    s.start(job.id)
    s.fail(job.id, "container error")

    r = s.get(job.id)
    assert r.status == JobStatus.FAILED
    assert "container error" in r.error


def test_job_list_and_delete():
    from bimos.infrastructure.job_store import JobStore

    s = JobStore()
    j1 = s.create(kind="simulate")
    s.create(kind="qm")

    assert len(s.list_all()) == 2
    assert s.delete(j1.id)
    assert len(s.list_all()) == 1
    assert not s.delete("nonexistent")




# ── 6. CLI help reachable ─────────────────────────────────────────────────────


@pytest.mark.parametrize("cmd", [
    ["--help"],
    ["predict", "--help"],
    ["dock", "--help"],
    ["simulate", "--help"],
    ["qm", "--help"],
    ["jobs", "--help"],
    ["db", "--help"],
    ["gui", "--help"],
    ["setup", "--help"],
])
def test_cli_help(cmd):
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0, f"Command {cmd} failed:\n{result.output}"
    assert "Usage:" in result.output or "Options:" in result.output
