import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_current_user


def _mock_user(linked: bool = False):
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "test@example.com"
    u.telegram_chat_id = 12345 if linked else None
    return u


def test_link_status_unlinked():
    user = _mock_user(linked=False)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app, raise_server_exceptions=True)
        res = client.get("/api/telegram/link-status")
        assert res.status_code == 200
        assert res.json() == {"linked": False}
    finally:
        app.dependency_overrides.clear()


def test_link_status_linked():
    user = _mock_user(linked=True)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app, raise_server_exceptions=True)
        res = client.get("/api/telegram/link-status")
        assert res.status_code == 200
        assert res.json() == {"linked": True}
    finally:
        app.dependency_overrides.clear()


def test_link_token_returns_url():
    user = _mock_user(linked=False)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with patch("app.routers.telegram.store_web_link_token", return_value="tok123"), \
             patch("app.routers.telegram.settings") as mock_cfg:
            mock_cfg.telegram_bot_username = "NextMoveBot"
            client = TestClient(app, raise_server_exceptions=True)
            res = client.post("/api/telegram/link-token")
        assert res.status_code == 200
        assert res.json()["url"] == "https://t.me/NextMoveBot?start=tok123"
    finally:
        app.dependency_overrides.clear()
