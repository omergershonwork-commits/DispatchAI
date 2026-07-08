from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_status_ok() -> None:
    response = client.get("/health")

    assert response.json()["status"] == "ok"


def test_ready_returns_200() -> None:
    response = client.get("/ready")

    assert response.status_code == 200


def test_ready_returns_status_ready() -> None:
    response = client.get("/ready")

    assert response.json()["status"] == "ready"