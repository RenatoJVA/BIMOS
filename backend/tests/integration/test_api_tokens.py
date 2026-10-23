"""Named API tokens, roles and revocation."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bimos.api.server import app
from bimos.config.settings import settings


@pytest.fixture
def token_db(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    if not settings.database_url:
        settings.database_url = "sqlite:///:memory:"
    from bimos.infrastructure import database

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'tokens.db'}")
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=engine, autocommit=False, autoflush=False),
    )
    database.Base.metadata.create_all(bind=engine)
    yield database
    engine.dispose()


def test_named_tokens_roles_and_revocation(token_db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "api_token", "admin-secret")
    admin = {"Authorization": "Bearer admin-secret"}

    with TestClient(app) as client:
        created_editor = client.post(
            "/api/v1/tokens",
            headers=admin,
            json={"name": "editor", "role": "editor"},
        )
        assert created_editor.status_code == 201, created_editor.text
        editor_token = created_editor.json()["token"]
        assert editor_token.startswith("bimos_")
        assert "token_hash" not in created_editor.json()

        created_viewer = client.post(
            "/api/v1/tokens",
            headers=admin,
            json={"name": "viewer", "role": "viewer"},
        )
        assert created_viewer.status_code == 201, created_viewer.text
        viewer_token = created_viewer.json()["token"]
        viewer_id = created_viewer.json()["id"]

        admin_list = client.get("/api/v1/tokens", headers=admin)
        assert admin_list.status_code == 200
        assert len(admin_list.json()) == 2
        assert all("token" not in item for item in admin_list.json())

        editor = {"Authorization": f"Bearer {editor_token}"}
        viewer = {"Authorization": f"Bearer {viewer_token}"}
        assert client.get("/api/v1/tokens", headers=viewer).status_code == 403
        assert client.get("/api/v1/ligands", headers=viewer).status_code == 200

        forbidden = client.post(
            "/api/v1/ligands",
            headers=viewer,
            json={"name": "Viewer ligand", "cid": "VIEWER_1"},
        )
        assert forbidden.status_code == 403

        created_ligand = client.post(
            "/api/v1/ligands",
            headers=editor,
            json={"name": "Editor ligand", "cid": "EDITOR_1"},
        )
        assert created_ligand.status_code == 201
        assert client.delete("/api/v1/ligands/EDITOR_1", headers=editor).status_code == 403
        assert client.delete("/api/v1/ligands/EDITOR_1", headers=admin).status_code == 204

        assert client.delete(f"/api/v1/tokens/{viewer_id}", headers=admin).status_code == 204
        assert client.get("/api/v1/ligands", headers=viewer).status_code == 401


def test_token_creation_requires_admin(token_db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "api_token", "admin-secret")
    admin = {"Authorization": "Bearer admin-secret"}
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/tokens",
            headers=admin,
            json={"name": "viewer", "role": "viewer"},
        )
        viewer = {"Authorization": f"Bearer {created.json()['token']}"}
        response = client.post(
            "/api/v1/tokens",
            headers=viewer,
            json={"name": "other", "role": "admin"},
        )
        assert response.status_code == 403
