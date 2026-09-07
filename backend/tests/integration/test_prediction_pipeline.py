import json
from pathlib import Path

import pytest

from bimos.prediction.confidence import pick_best_boltz
from bimos.prediction.fasta import read_sequences, write_boltz_yaml


def test_write_boltz_yaml(tmp_path: Path) -> None:
    fasta = tmp_path / "test.fasta"
    fasta.write_text(">protein\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n")
    yaml_path = tmp_path / "output.yaml"
    seqs = write_boltz_yaml(fasta, yaml_path)
    assert len(seqs) == 1
    assert "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES" in seqs[0]
    content = yaml_path.read_text()
    assert "sequences:" in content
    assert "protein:" in content


def test_read_sequences(tmp_path: Path) -> None:
    fasta = tmp_path / "multi.fasta"
    fasta.write_text(">seq1\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n>seq2\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG\n")
    seqs = read_sequences(fasta)
    assert len(seqs) == 2


def test_read_sequences_single(tmp_path: Path) -> None:
    fasta = tmp_path / "single.fasta"
    fasta.write_text(">test\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG\n")
    seqs = read_sequences(fasta)
    assert len(seqs) == 1
    assert seqs[0].startswith("MQIFVK")


def test_read_sequences_empty_raises(tmp_path: Path) -> None:
    fasta = tmp_path / "empty.fasta"
    fasta.write_text("")
    with pytest.raises(ValueError, match="No sequences found"):
        read_sequences(fasta)


def test_pick_best_boltz_none(tmp_path: Path) -> None:
    result = pick_best_boltz(tmp_path)
    assert result is None


def test_pick_best_boltz_finds_best(tmp_path: Path) -> None:
    (tmp_path / "model_1").mkdir(parents=True)
    for i, score in enumerate([0.75, 0.85]):
        conf = tmp_path / "model_1" / f"confidence_{i}.json"
        conf.write_text(json.dumps({"confidence_score": score}))
        cif = tmp_path / "model_1" / f"{i}.cif"
        cif.write_text("data_structure\n")
    best = pick_best_boltz(tmp_path)
    assert best is not None
    assert best["score"] == 0.85


def test_boltz_build_cli_args() -> None:
    from bimos.prediction.boltz import BoltzPipeline

    pipeline = BoltzPipeline(output_dir="/tmp")
    cfg = {
        "num_models": 5,
        "recycling_steps": 3,
        "sampling_steps": 200,
        "diffusion_samples": 1,
        "max_parallel_samples": 4,
        "step_scale": 1.0,
        "max_msa_seqs": 1024,
        "num_subsampled_msa": 256,
        "num_workers": 4,
        "preprocessing_threads": 4,
        "output_format": "cif",
        "use_msa_server": True,
        "msa_pairing_strategy": "greedy",
        "subsample_msa": True,
        "use_potentials": True,
        "write_full_pae": True,
        "write_full_pde": True,
        "override": True,
        "no_kernels": False,
    }
    args = pipeline._build_cli_args("test.yaml", "/workspace/predictions/model_1", cfg)
    assert "boltz" in args
    assert "predict" in args
    assert "test.yaml" in args[2]
    assert "--recycling_steps" in args
