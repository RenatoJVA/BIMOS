"""PostgreSQL search-index contract for the ligand test set."""


def _ligand_table():  # type: ignore[no-untyped-def]
    from bimos.config.settings import settings

    if not settings.database_url:
        settings.database_url = "sqlite:///:memory:"
    from bimos.infrastructure.database import Ligand

    return Ligand.__table__


def test_ligand_table_has_trigram_indexes() -> None:
    table = _ligand_table()
    indexes = {index.name: index for index in table.indexes}

    for name in ("ix_ligands_name_trgm", "ix_ligands_cid_trgm", "ix_ligands_smiles_trgm"):
        assert name in indexes
        options = indexes[name].dialect_options["postgresql"]
        assert options["using"] == "gin"
        assert options["ops"]


def test_ligand_table_has_property_range_index() -> None:
    indexes = {index.name: index for index in _ligand_table().indexes}

    assert "ix_ligands_logp_mw" in indexes
    assert [column.name for column in indexes["ix_ligands_logp_mw"].columns] == [
        "logp",
        "molar_mass",
    ]
