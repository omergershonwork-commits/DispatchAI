from fastapi.testclient import TestClient

from app.api import health as health_module
from app.main import app

client = TestClient(app)


def test_ready_returns_200_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: True,
    )

    response = client.get("/ready")

    assert response.status_code == 200


def test_ready_returns_status_ready_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: True,
    )

    response = client.get("/ready")

    assert response.json() == {
        "status": "ready",
        "service": "backend",
        "database": "ok",
    }


def test_ready_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: False,
    )

    response = client.get("/ready")

    assert response.status_code == 503


def test_ready_returns_not_ready_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "check_database_connection",
        lambda: False,
    )

    response = client.get("/ready")

    assert response.json() == {
        "status": "not_ready",
        "service": "backend",
        "database": "unavailable",
    }
