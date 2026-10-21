"""Ligand property filters (local SQLite reads only, no containers)."""

from pathlib import Path

import pytest

from bimos.infrastructure.chembl_db import (
    apply_filters,
    count_candidates,
    export_to_sdf,
    normalize_filters,
    search_candidates,
)


def test_normalize_druglike_defaults() -> None:
    active = normalize_filters(None, druglike=True)
    assert active["max_mw"] == pytest.approx(500.0)
    assert active["max_hbd"] == 5
    assert normalize_filters(None) == {}


def test_normalize_override_and_unknown() -> None:
    active = normalize_filters({"max_mw": 450}, druglike=True)
    assert active["max_mw"] == pytest.approx(450.0)
    with pytest.raises(ValueError, match="Unknown filter"):
        normalize_filters({"max_foo": 1})
    with pytest.raises(ValueError, match="requires a number"):
        normalize_filters({"max_mw": "abc"})
    with pytest.raises(ValueError, match="Inverted range"):
        normalize_filters({"min_mw": 500, "max_mw": 100})


def test_apply_filters_empty() -> None:
    sql, params = apply_filters("SELECT * FROM t", [], {})
    assert sql == "SELECT * FROM t"
    assert params == []


def test_apply_filters_builds_and_clause() -> None:
    sql, params = apply_filters("SELECT * FROM t", [], {"max_mw": 500.0, "min_logp": 1.0})
    assert "WHERE" in sql and "peso_mol <= ?" in sql and "alogp >= ?" in sql
    assert params == [500.0, 1.0]


def test_search_unfiltered_returns_rows() -> None:
    rows = search_candidates("candidates_1000", "acid")
    assert len(rows) > 0
    assert "peso_mol" in rows[0]


def test_search_druglike_reduces() -> None:
    all_rows = search_candidates("candidates_1000", "acid")
    druglike = search_candidates("candidates_1000", "acid", druglike=True)
    assert 0 < len(druglike) <= len(all_rows)
    assert all(r["peso_mol"] <= 500.0 for r in druglike)


def test_search_respects_bounds() -> None:
    rows = search_candidates("candidates_1000", "a", {"min_mw": 400.0, "max_logp": 3.0})
    assert len(rows) > 0
    assert all(r["peso_mol"] >= 400.0 and r["alogp"] <= 3.0 for r in rows)


def test_export_filtered_subset(tmp_path: Path) -> None:
    full = tmp_path / "full.sdf"
    filt = tmp_path / "filt.sdf"
    n_full = export_to_sdf("candidates_1000", full)
    n_filt = export_to_sdf("candidates_1000", filt, {"max_mw": 250.0})
    assert n_full > 0 and 0 <= n_filt < n_full


def test_natural_product_and_phase_filters() -> None:
    nps = search_candidates("phytocompounds_300", "a", {"natural_product": 1})
    assert len(nps) > 0
    approved = search_candidates("candidates_1000", "a", {"min_phase": 4.0})
    assert len(approved) > 0
    calm = search_candidates("candidates_1000", "a", {"max_aromatic": 1})
    assert len(calm) > 0


def test_count_candidates_matches_search() -> None:
    total = count_candidates("candidates_1000", "acid", {"max_mw": 400.0})
    rows = search_candidates("candidates_1000", "acid", {"max_mw": 400.0})
    assert total >= len(rows) > 0
    assert count_candidates("candidates_1000", "acid", {"min_mw": 99999.0}) == 0


def test_search_returns_defensive_copies() -> None:
    first = search_candidates("candidates_1000", "acid")
    first[0]["peso_mol"] = -1.0
    first.append({"fake": True})
    second = search_candidates("candidates_1000", "acid")
    assert all(r.get("peso_mol", 0) != -1.0 for r in second)
    assert not any("fake" in r for r in second)


def test_cli_db_query_with_filters() -> None:
    from click.testing import CliRunner

    from bimos.cli.main import cli

    result = CliRunner().invoke(cli, ["db", "query", "acid", "-d", "candidates_1000", "--max-mw", "400"])
    assert result.exit_code == 0, result.output
    assert "matches" in result.output


def test_cli_db_export_druglike(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from bimos.cli.main import cli

    out = tmp_path / "dl.sdf"
    result = CliRunner().invoke(cli, ["db", "export", "candidates_1000", str(out), "--druglike"])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_cli_db_rejects_inverted_range() -> None:
    from click.testing import CliRunner

    from bimos.cli.main import cli

    result = CliRunner().invoke(
        cli, ["db", "query", "acid", "-d", "candidates_1000", "--min-mw", "500", "--max-mw", "100"]
    )
    assert result.exit_code != 0


def test_pg_filtered_query_in_memory() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from bimos.infrastructure.database import Base, Ligand, PropertyBounds, _filtered_query

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as db:
        db.add_all(
            [
                Ligand(name="Light", cid="C1", logp=1.0, molar_mass=200.0),
                Ligand(name="Heavy", cid="C2", logp=6.0, molar_mass=700.0),
                Ligand(name="Light2", cid="C3", logp=2.0, molar_mass=250.0),
            ]
        )
        db.commit()
        names = sorted(
            row.name
            for row in _filtered_query(db, "Light", bounds=PropertyBounds(max_mw=500.0, max_logp=5.0)).all()
        )
        assert names == ["Light", "Light2"]
        assert _filtered_query(db, "Light", bounds=PropertyBounds(min_mw=900.0)).count() == 0
