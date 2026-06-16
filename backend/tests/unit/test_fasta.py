import pytest
from pathlib import Path
from bimos.prediction.fasta import read_sequences, write_boltz_yaml


def test_read_sequences_single(tmp_path: Path) -> None:
    f = tmp_path / "test.fasta"
    f.write_text(">seq1\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n")
    seqs = read_sequences(f)
    assert len(seqs) == 1
    assert seqs[0].startswith("MKFL")


def test_read_sequences_multi(tmp_path: Path) -> None:
    f = tmp_path / "multi.fasta"
    f.write_text(">seq1\nAAAA\n>seq2\nBBBB\n")
    seqs = read_sequences(f)
    assert len(seqs) == 2


def test_read_sequences_empty_raises(tmp_path: Path) -> None:
    f = tmp_path / "empty.fasta"
    f.write_text("")
    with pytest.raises(ValueError, match="No sequences found"):
        read_sequences(f)


def test_read_sequences_skips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "blank.fasta"
    f.write_text(">seq1\nAAAA\n\n>seq2\nBBBB\n\n")
    seqs = read_sequences(f)
    assert len(seqs) == 2


def test_write_boltz_yaml(tmp_path: Path) -> None:
    fasta = tmp_path / "input.fasta"
    yaml_out = tmp_path / "output.yaml"
    fasta.write_text(">protein\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n")
    seqs = write_boltz_yaml(fasta, yaml_out)
    assert len(seqs) == 1
    assert yaml_out.exists()
    content = yaml_out.read_text()
    assert "sequences:" in content
    assert "protein:" in content
