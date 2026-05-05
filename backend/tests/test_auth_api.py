import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import User
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_FAKE_GOOGLE_USER = {
    "email": "",          # filled per test
    "name": "Google Student",
    "access_token": "goog-access-tok",
    "refresh_token": "goog-refresh-tok",
}


# ---------------------------------------------------------------------------
# Secure Google exchange (C-4 fix)
# ---------------------------------------------------------------------------

def test_google_exchange_uses_server_side_code_exchange():
    """POST {code, redirect_uri} → exchange function called, JWT returned."""
    client = TestClient(app)
    email = f"google_{uuid.uuid4().hex[:8]}@example.com"
    fake_info = {**_FAKE_GOOGLE_USER, "email": email}

    try:
        with patch("app.routers.auth.exchange_code_for_user_info", return_value=fake_info) as ex_mock:
            resp = client.post("/api/auth/google/exchange", json={
                "code": "4/0AfJohXnFAKECODE",
                "redirect_uri": "http://localhost:3000/auth/callback",
                "timezone": "Asia/Singapore",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["user_id"]
        ex_mock.assert_called_once_with("4/0AfJohXnFAKECODE", "http://localhost:3000/auth/callback")
    finally:
        db = TestingSession()
        try:
            db.query(User).filter(User.email == email).delete()
            db.commit()
        finally:
            db.close()


def test_google_exchange_email_comes_from_google_not_client():
    """The email stored is the one Google verified, not anything the client supplies."""
    client = TestClient(app)
    google_email = f"real_{uuid.uuid4().hex[:8]}@gmail.com"
    fake_info = {**_FAKE_GOOGLE_USER, "email": google_email}

    try:
        with patch("app.routers.auth.exchange_code_for_user_info", return_value=fake_info):
            resp = client.post("/api/auth/google/exchange", json={
                "code": "anycode",
                "redirect_uri": "http://localhost:3000/auth/callback",
            })

        assert resp.status_code == 200
        db = TestingSession()
        try:
            user = db.query(User).filter(User.email == google_email).first()
            assert user is not None, "User must be created under Google-verified email"
            assert user.google_access_token == "goog-access-tok"
            assert user.uses_google_calendar is True
        finally:
            db.close()
    finally:
        db = TestingSession()
        try:
            db.query(User).filter(User.email == google_email).delete()
            db.commit()
        finally:
            db.close()


def test_google_exchange_returns_401_when_google_rejects_code():
    """If Google rejects the code, the endpoint returns 401."""
    client = TestClient(app)
    with patch("app.routers.auth.exchange_code_for_user_info",
               side_effect=ValueError("invalid_grant")):
        resp = client.post("/api/auth/google/exchange", json={
            "code": "expired-code",
            "redirect_uri": "http://localhost:3000/auth/callback",
        })
    assert resp.status_code == 401


def test_google_exchange_rejects_old_access_token_format():
    """Sending raw {email, access_token} (old insecure format) must be rejected with 422."""
    client = TestClient(app)
    resp = client.post("/api/auth/google/exchange", json={
        "email": "attacker@evil.com",
        "access_token": "stolen-token",
    })
    assert resp.status_code == 422
