"""H5 ligand management API and web panel."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bimos.api.server import app
from bimos.config.settings import settings


@pytest.fixture
def ligand_db(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    if not settings.database_url:
        settings.database_url = "sqlite:///:memory:"
    from bimos.infrastructure import database

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'ligands.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=engine, autocommit=False, autoflush=False),
    )
    database.Base.metadata.create_all(bind=engine)
    yield database
    engine.dispose()


def test_ligand_crud_and_soft_delete(ligand_db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "api_token", "")

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ligands",
            json={
                "name": "Panel test",
                "cid": "PANEL_1",
                "smiles": "CCO",
                "logp": 1.2,
                "molar_mass": 46.07,
                "source": "test",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["cid"] == "PANEL_1"

        duplicate = client.post(
            "/api/v1/ligands",
            json={"name": "Duplicate", "cid": "PANEL_1"},
        )
        assert duplicate.status_code == 409

        listed = client.get("/api/v1/ligands", params={"q": "Panel"})
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["source"] == "test"

        updated = client.patch(
            "/api/v1/ligands/PANEL_1",
            json={"name": "Panel updated", "logp": 2.0},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["name"] == "Panel updated"
        assert updated.json()["logp"] == 2.0

        deleted = client.delete("/api/v1/ligands/PANEL_1")
        assert deleted.status_code == 204

        assert client.get("/api/v1/ligands", params={"q": "Panel"}).json()["total"] == 0
        hidden = ligand_db.get_ligand("PANEL_1", include_inactive=True)
        assert hidden is not None
        assert hidden.active is False


def test_ligand_endpoints_require_token_when_configured(  # type: ignore[no-untyped-def]
    ligand_db, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "api_token", "test-secret")

    with TestClient(app) as client:
        assert client.get("/api/v1/ligands").status_code == 401
        allowed = client.get(
            "/api/v1/ligands",
            headers={"Authorization": "Bearer test-secret"},
        )
        assert allowed.status_code == 200


def test_admin_panel_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/admin/ligands")

    assert response.status_code == 200
    assert "Gestión de ligandos" in response.text
    assert "BIMOS_API_TOKEN" in response.text
    assert "Tokens de API" in response.text
    assert "token-create" in response.text
