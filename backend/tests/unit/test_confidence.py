"""Tests for best-structure selection across Boltz output layouts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bimos.prediction.confidence import pick_best_boltz


def _write(root: Path, rel: str, score: float, suffix: str = ".cif") -> None:
    """Create a confidence JSON plus its matching structure file."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"confidence_score": score}), encoding="utf-8")
    struct = path.parent / (path.name.replace("confidence_", "").replace(".json", suffix))
    struct.write_text("data\n", encoding="utf-8")


def test_empty_dir_returns_none(tmp_path: Path) -> None:
    assert pick_best_boltz(tmp_path / "nope") is None


def test_empty_predictions_dir_returns_none(tmp_path: Path) -> None:
    (tmp_path / "predictions").mkdir()
    assert pick_best_boltz(tmp_path / "predictions") is None


def test_boltz1_flat_layout(tmp_path: Path) -> None:
    """Boltz-1 wrote confidence files one level below the predictions root."""
    pred = tmp_path / "predictions"
    _write(pred, "model_1/confidence_seq_model_0.json", 0.70)
    _write(pred, "model_1/confidence_seq_model_1.json", 0.91)

    best = pick_best_boltz(pred)
    assert best is not None
    assert best["score"] == 0.91
    assert best["struct_path"].name == "seq_model_1.cif"


def test_boltz2_nested_layout(tmp_path: Path) -> None:
    """Boltz-2 nests results three levels deep; the scan must still find them."""
    pred = tmp_path / "predictions"
    _write(pred, "model_1/boltz_results_seq/predictions/seq/confidence_seq_model_0.json", 0.62)
    _write(pred, "model_2/boltz_results_seq/predictions/seq/confidence_seq_model_0.json", 0.88)

    best = pick_best_boltz(pred)
    assert best is not None
    assert best["score"] == 0.88
    assert best["struct_path"].name == "seq_model_0.cif"
    assert "model_2" in str(best["struct_path"])


def test_boltz2_ranks_across_models(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    for index, score in enumerate([0.5, 0.95, 0.75], start=1):
        _write(
            pred,
            f"model_{index}/boltz_results_seq/predictions/seq/confidence_seq_model_0.json",
            score,
        )
    best = pick_best_boltz(pred)
    assert best is not None
    assert best["score"] == 0.95
    assert "model_2" in str(best["struct_path"])


def test_supports_pdb_output_format(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    _write(pred, "model_1/boltz_results_x/predictions/x/confidence_x_model_0.json", 0.8, suffix=".pdb")
    best = pick_best_boltz(pred)
    assert best is not None
    assert best["struct_path"].suffix == ".pdb"


def test_score_is_float(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    _write(pred, "model_1/confidence_x_model_0.json", 1)
    best = pick_best_boltz(pred)
    assert best is not None
    assert isinstance(best["score"], float)


def test_skips_confidence_without_score(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    path = pred / "model_1" / "confidence_x_model_0.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"ptm": 0.9}), encoding="utf-8")
    (path.parent / "x_model_0.cif").write_text("data\n", encoding="utf-8")
    assert pick_best_boltz(pred) is None


def test_skips_confidence_without_matching_structure(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    path = pred / "model_1" / "confidence_x_model_0.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"confidence_score": 0.9}), encoding="utf-8")
    assert pick_best_boltz(pred) is None


def test_skips_corrupt_json(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    bad = pred / "model_1" / "confidence_x_model_0.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    (bad.parent / "x_model_0.cif").write_text("data\n", encoding="utf-8")
    _write(pred, "model_2/confidence_x_model_0.json", 0.4)
    best = pick_best_boltz(pred)
    assert best is not None
    assert best["score"] == 0.4


def test_ignores_unrelated_json_files(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    other = pred / "model_1" / "processed" / "manifest.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"confidence_score": 0.99}), encoding="utf-8")
    _write(pred, "model_1/confidence_x_model_0.json", 0.5)
    best = pick_best_boltz(pred)
    assert best is not None
    assert best["score"] == 0.5


def test_deterministic_on_ties(tmp_path: Path) -> None:
    pred = tmp_path / "predictions"
    _write(pred, "model_1/boltz_results_x/predictions/x/confidence_x_model_0.json", 0.9)
    _write(pred, "model_2/boltz_results_x/predictions/x/confidence_x_model_0.json", 0.9)
    first = pick_best_boltz(pred)
    second = pick_best_boltz(pred)
    assert first is not None and second is not None
    assert first["struct_path"] == second["struct_path"]


def test_ties_prefer_boltz1_flat_order(tmp_path: Path) -> None:
    """With equal scores the first path in sorted order wins, so it is stable."""
    pred = tmp_path / "predictions"
    _write(pred, "model_1/confidence_x_model_0.json", 0.9)
    _write(pred, "model_2/confidence_x_model_0.json", 0.9)
    best = pick_best_boltz(pred)
    assert best is not None
    assert "model_1" in str(best["struct_path"])


# --------------------------------------------------------------------------- #
# --model override pairing
# --------------------------------------------------------------------------- #
def test_model_override_moves_the_tuned_step_scale() -> None:
    """``--model boltz1`` must not run Boltz-1 weights with the Boltz-2 scale."""
    from bimos.prediction.boltz import _apply_model_override

    cfg = {"model": "boltz2", "step_scale": 1.5, "num_models": 5}
    assert _apply_model_override(cfg, "boltz1") == {
        "model": "boltz1",
        "step_scale": 1.638,
        "num_models": 5,
    }
    assert _apply_model_override(cfg, "boltz2")["step_scale"] == 1.5


def test_model_override_preserves_unrelated_keys() -> None:
    from bimos.prediction.boltz import _apply_model_override

    cfg = {"step_scale": 1.0, "num_workers": 8}
    result = _apply_model_override(cfg, "boltz2")
    assert result["num_workers"] == 8
    assert result["step_scale"] == 1.5


def test_model_override_rejects_an_unknown_model() -> None:
    from bimos.prediction.boltz import _apply_model_override

    with pytest.raises(ValueError, match="model must be one of"):
        _apply_model_override({"step_scale": 1.5}, "alphafold")
