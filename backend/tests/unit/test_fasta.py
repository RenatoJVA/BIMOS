import pytest
from pathlib import Path
from bimos.prediction.fasta import read_sequences, read_yaml_sequences, ensure_yaml, write_boltz_yaml


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


def test_read_yaml_sequences(tmp_path: Path) -> None:
    y = tmp_path / "test.yaml"
    y.write_text("version: 1\nsequences:\n  - protein:\n      id: A\n      sequence: MKFL\n")
    seqs = read_yaml_sequences(y)
    assert seqs == ["MKFL"]


def test_read_yaml_sequences_multi(tmp_path: Path) -> None:
    y = tmp_path / "multi.yaml"
    y.write_text(
        "sequences:\n"
        "  - protein:\n"
        "      id: A\n"
        "      sequence: AAA\n"
        "  - protein:\n"
        "      id: B\n"
        "      sequence: BBB\n"
    )
    seqs = read_yaml_sequences(y)
    assert seqs == ["AAA", "BBB"]


def test_read_yaml_sequences_empty_raises(tmp_path: Path) -> None:
    y = tmp_path / "empty.yaml"
    y.write_text("sequences: []\n")
    with pytest.raises(ValueError, match="No sequences found"):
        read_yaml_sequences(y)


def test_ensure_yaml_from_fasta(tmp_path: Path) -> None:
    fasta = tmp_path / "input.fasta"
    fasta.write_text(">test\nMKFL\n")
    result = ensure_yaml(fasta, tmp_path)
    assert result.suffix == ".yaml"
    assert result.exists()
    seqs = read_yaml_sequences(result)
    assert seqs == ["MKFL"]


def test_ensure_yaml_from_yaml(tmp_path: Path) -> None:
    src = tmp_path / "input.yaml"
    src.write_text("sequences:\n  - protein:\n      id: A\n      sequence: MKFL\n")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = ensure_yaml(src, out_dir)
    assert result == out_dir / "input.yaml"
    assert result.exists()
    assert result.read_text() == src.read_text()
