import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bimos.cli.main import cli
from bimos.prediction.confidence import pick_best_boltz
from bimos.prediction.fasta import read_sequences, write_boltz_yaml
from bimos.shared.hardware import GpuInfo


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def packaged_boltz_config() -> Any:
    """Force the packaged boltz.yaml, never the developer's ~/.bimos/config."""
    import yaml

    defaults = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "bimos" / "config" / "defaults" / "boltz.yaml").read_text()
    )
    with patch("bimos.prediction.boltz.resolve", return_value=(defaults, MagicMock(value="default"))):
        yield defaults


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


def _flag_value(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


def test_boltz_defaults_to_boltz2() -> None:
    """The engine must never switch silently: --model is always explicit."""
    from bimos.prediction.boltz import BoltzPipeline

    cfg = {
        "num_models": 5,
        "recycling_steps": 10,
        "sampling_steps": 200,
        "diffusion_samples": 50,
        "max_parallel_samples": 6,
        "step_scale": 1.5,
        "max_msa_seqs": 8192,
        "num_subsampled_msa": 1024,
        "num_workers": 8,
        "preprocessing_threads": 16,
        "output_format": "mmcif",
        "model": "boltz2",
    }
    args = BoltzPipeline(output_dir="/tmp")._build_cli_args(
        "s.yaml", "/workspace/predictions/model_1", cfg
    )
    assert _flag_value(args, "--model") == "boltz2"
    assert _flag_value(args, "--step_scale") == "1.5"
    assert _flag_value(args, "--output_format") == "mmcif"


def test_boltz_model_defaults_when_config_omits_it() -> None:
    """A pre-migration config without 'model' must still yield boltz2."""
    from bimos.prediction.boltz import DEFAULT_MODEL, BoltzPipeline

    cfg = {
        "num_models": 5,
        "recycling_steps": 3,
        "sampling_steps": 200,
        "diffusion_samples": 1,
        "max_parallel_samples": 4,
        "step_scale": 1.638,
        "max_msa_seqs": 1024,
        "num_subsampled_msa": 256,
        "num_workers": 4,
        "preprocessing_threads": 4,
        "output_format": "mmcif",
    }
    args = BoltzPipeline(output_dir="/tmp")._build_cli_args(
        "s.yaml", "/workspace/predictions/model_1", cfg
    )
    assert DEFAULT_MODEL == "boltz2"
    assert _flag_value(args, "--model") == "boltz2"


def test_boltz_rejects_unknown_model() -> None:
    from bimos.prediction.boltz import BoltzPipeline

    cfg = {
        "num_models": 5,
        "recycling_steps": 3,
        "sampling_steps": 200,
        "diffusion_samples": 1,
        "max_parallel_samples": 4,
        "step_scale": 1.5,
        "max_msa_seqs": 1024,
        "num_subsampled_msa": 256,
        "num_workers": 4,
        "preprocessing_threads": 4,
        "output_format": "mmcif",
        "model": "boltz9",
    }
    with pytest.raises(ValueError, match="model must be one of"):
        BoltzPipeline(output_dir="/tmp")._build_cli_args(
            "s.yaml", "/workspace/predictions/model_1", cfg
        )


def test_boltz_all_flags_exist_in_v2() -> None:
    """Every flag BIMOS emits must still be a Boltz-2 option."""
    from bimos.prediction.boltz import BoltzPipeline

    cfg = {
        "num_models": 5,
        "recycling_steps": 10,
        "sampling_steps": 200,
        "diffusion_samples": 50,
        "max_parallel_samples": 6,
        "step_scale": 1.5,
        "max_msa_seqs": 8192,
        "num_subsampled_msa": 1024,
        "num_workers": 8,
        "preprocessing_threads": 16,
        "output_format": "mmcif",
        "model": "boltz2",
        "use_msa_server": True,
        "msa_pairing_strategy": "complete",
        "subsample_msa": True,
        "use_potentials": True,
        "write_full_pae": True,
        "write_full_pde": True,
        "override": True,
        "no_kernels": True,
    }
    args = BoltzPipeline(output_dir="/tmp")._build_cli_args(
        "s.yaml", "/workspace/predictions/model_1", cfg
    )
    expected = {
        "--out_dir", "--cache", "--model", "--recycling_steps", "--sampling_steps",
        "--diffusion_samples", "--max_parallel_samples", "--step_scale",
        "--max_msa_seqs", "--num_subsampled_msa", "--num_workers",
        "--preprocessing-threads", "--output_format", "--use_msa_server",
        "--msa_pairing_strategy", "--subsample_msa", "--use_potentials",
        "--write_full_pae", "--write_full_pde", "--override", "--no_kernels",
    }
    assert expected <= set(args)


def test_boltz2_packaged_defaults() -> None:
    """The shipped config must target Boltz-2 with its tuned step scale."""
    from bimos.shared.user_config import _packaged_default_yaml

    cfg = _packaged_default_yaml("boltz")
    assert cfg["model"] == "boltz2"
    assert cfg["step_scale"] == 1.5


def test_legacy_config_warning_fires_for_old_step_scale(caplog) -> None:
    import logging

    from bimos.prediction.boltz import BoltzPipeline

    with caplog.at_level(logging.WARNING, logger="bimos.prediction.boltz"):
        BoltzPipeline._warn_legacy_config({"step_scale": 1.638})
    assert "predates the Boltz-2 migration" in caplog.text


def test_legacy_config_silent_when_tuned(caplog) -> None:
    import logging

    from bimos.prediction.boltz import BoltzPipeline

    with caplog.at_level(logging.WARNING, logger="bimos.prediction.boltz"):
        BoltzPipeline._warn_legacy_config({"model": "boltz2", "step_scale": 1.5})
        BoltzPipeline._warn_legacy_config({"step_scale": 1.5})
    assert "predates the Boltz-2 migration" not in caplog.text


# --------------------------------------------------------------------------- #
# --model
# --------------------------------------------------------------------------- #
def test_model_flag_reaches_the_container(
    runner: CliRunner, tmp_path: Path, packaged_boltz_config: Any
) -> None:
    """``--model`` must override the config, not just be accepted."""
    inputs = tmp_path / "in"
    inputs.mkdir()
    fasta = inputs / "seq.fasta"
    fasta.write_text(">seq\nMKTAYIAKQRQISFVKSHFSRQ\n")
    captured: list[list[str]] = []

    def fake_run(**kwargs: Any) -> dict[str, Any]:
        captured.append(list(kwargs["command"]))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    gpu = GpuInfo(name="NVIDIA RTX 4090", vram_total_gb=24.0, vram_free_gb=23.0)
    with (
        patch("bimos.shared.hardware.detect_gpus", return_value=[gpu]),
        patch("bimos.infrastructure.container.run", side_effect=fake_run),
        patch("bimos.prediction.boltz.BoltzPipeline._preflight_gpu"),
        patch(
            "bimos.prediction.boltz.pick_best_boltz",
            return_value=(tmp_path / "out" / "best.cif", 0.5),
        ),
    ):
        result = runner.invoke(
            cli, ["predict", str(fasta), "-o", str(tmp_path / "out"), "-n", "1", "--model", "boltz1"]
        )

    assert result.exit_code == 0, result.output
    assert captured, "the container was never invoked"
    command = captured[0]
    assert command[command.index("--model") + 1] == "boltz1"
    # Boltz-1 is tuned for 1.638, so the override must not silently pair it
    # with the Boltz-2 step scale from the packaged config.
    assert float(command[command.index("--step_scale") + 1]) == 1.638


def test_model_flag_defaults_to_the_config(
    runner: CliRunner, tmp_path: Path, packaged_boltz_config: Any
) -> None:
    inputs = tmp_path / "in"
    inputs.mkdir()
    fasta = inputs / "seq.fasta"
    fasta.write_text(">seq\nMKTAYIAKQRQISFVKSHFSRQ\n")
    captured: list[list[str]] = []

    def fake_run(**kwargs: Any) -> dict[str, Any]:
        captured.append(list(kwargs["command"]))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    gpu = GpuInfo(name="NVIDIA RTX 4090", vram_total_gb=24.0, vram_free_gb=23.0)
    with (
        patch("bimos.shared.hardware.detect_gpus", return_value=[gpu]),
        patch("bimos.infrastructure.container.run", side_effect=fake_run),
        patch("bimos.prediction.boltz.BoltzPipeline._preflight_gpu"),
        patch(
            "bimos.prediction.boltz.pick_best_boltz",
            return_value=(tmp_path / "out" / "best.cif", 0.5),
        ),
    ):
        result = runner.invoke(cli, ["predict", str(fasta), "-o", str(tmp_path / "out"), "-n", "1"])

    assert result.exit_code == 0, result.output
    command = captured[0]
    assert command[command.index("--model") + 1] == "boltz2"
    assert float(command[command.index("--step_scale") + 1]) == 1.5


def test_model_flag_rejects_an_unknown_release(runner: CliRunner, tmp_path: Path) -> None:
    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">seq\nMKTAYIAKQRQISFVKSHFSRQ\n")
    result = runner.invoke(cli, ["predict", str(fasta), "-o", str(tmp_path / "out"), "--model", "boltz3"])
    assert result.exit_code == 2
    assert "boltz3" in result.output
