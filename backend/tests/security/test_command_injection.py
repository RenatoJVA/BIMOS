import pytest
from fastapi.testclient import TestClient

from bimos.api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_command_injection_in_predict_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict",
        json={
            "name": "protein; rm -rf /",
            "sequence": "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES",
        },
    )
    assert response.status_code in (200, 202, 422)


def test_command_injection_in_predict_boltz_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict-boltz",
        json={
            "name": "$(cat /etc/passwd)",
            "fasta_content": ">test\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n",
        },
    )
    assert response.status_code in (200, 202, 422)


def test_command_injection_backticks(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict",
        json={
            "name": "protein`cat /etc/passwd`",
            "sequence": "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES",
        },
    )
    assert response.status_code in (200, 202, 422)


def test_command_injection_pipe(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict",
        json={
            "name": "protein | ls -la",
            "sequence": "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES",
        },
    )
    assert response.status_code in (200, 202, 422)


def test_command_injection_semicolon(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict",
        json={
            "name": "protein; echo hacked",
            "sequence": "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES",
        },
    )
    assert response.status_code in (200, 202, 422)


def test_command_injection_newline(client: TestClient) -> None:
    response = client.post(
        "/api/v1/predict",
        json={
            "name": "protein\nls -la",
            "sequence": "MKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES",
        },
    )
    assert response.status_code in (200, 202, 422)
