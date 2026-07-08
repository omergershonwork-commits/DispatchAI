from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def telegram_text_payload() -> dict:
    return {
        "update_id": 123456,
        "message": {
            "message_id": 42,
            "date": 1_725_000_000,
            "chat": {
                "id": 987654321,
                "type": "private",
                "first_name": "Omer",
            },
            "from": {
                "id": 111222333,
                "is_bot": False,
                "first_name": "Omer",
                "username": "omer_user",
            },
            "text": "I need help near Dizengoff Center",
        },
    }


def test_telegram_webhook_accepts_text_message() -> None:
    response = client.post("/webhooks/telegram", json=telegram_text_payload())

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "telegram",
        "update_id": 123456,
        "message_id": 42,
        "chat_id": 987654321,
        "has_text": True,
    }


def test_telegram_webhook_accepts_update_without_message() -> None:
    response = client.post("/webhooks/telegram", json={"update_id": 123457})

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "source": "telegram",
        "update_id": 123457,
        "message_id": None,
        "chat_id": None,
        "has_text": False,
    }


def test_telegram_webhook_rejects_missing_update_id() -> None:
    payload = telegram_text_payload()
    del payload["update_id"]

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 422


def test_telegram_webhook_rejects_invalid_message_shape() -> None:
    payload = telegram_text_payload()
    payload["message"]["chat"] = None

    response = client.post("/webhooks/telegram", json=payload)

    assert response.status_code == 422
