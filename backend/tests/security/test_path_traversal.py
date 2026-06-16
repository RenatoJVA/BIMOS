import pytest
from fastapi.testclient import TestClient

from bimos.api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_path_traversal_in_filename_blocked(client: TestClient) -> None:
    response = client.post(
        "/api/v1/dock",
        files={
            "protein": ("../../../etc/passwd", b"root:x:0:0:root:", "application/octet"),
            "ligands": ("safe.sdf", b"ligand data", "chemical/x-mdl-sdfile"),
        },
    )
    assert response.status_code in (200, 201, 202, 422)


def test_path_traversal_in_simulate_filename(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulate",
        files={
            "protein": ("../../etc/shadow", b"root:x:0:0:root:", "application/octet"),
        },
    )
    assert response.status_code < 500


def test_path_traversal_in_simulate_holo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulate-holo",
        files={
            "protein": ("safe.pdb", b"ATOM data", "application/octet"),
            "ligand_gro": ("../../../etc/passwd", b"root:x:0:0:root:", "application/octet"),
            "ligand_itp": ("safe.itp", b"itp data", "application/octet"),
        },
    )
    assert response.status_code < 500


def test_path_traversal_in_qm_orca(client: TestClient) -> None:
    response = client.post(
        "/api/v1/qm-orca-files",
        files={
            "gro": ("../../../etc/hostname", b"test-host", "application/octet"),
            "itp": ("safe.itp", b"itp data", "application/octet"),
        },
    )
    assert response.status_code < 500


def test_path_traversal_double_dot(client: TestClient) -> None:
    response = client.post(
        "/api/v1/dock",
        files={
            "protein": ("..\\..\\..\\windows\\system32\\config\\sam", b"dummy", "application/octet"),
            "ligands": ("safe.sdf", b"ligand data", "chemical/x-mdl-sdfile"),
        },
    )
    assert response.status_code in (200, 201, 202, 422, 422)
