import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models import User
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_google_exchange_creates_backend_user_and_token():
    client = TestClient(app)
    email = f"google_{uuid.uuid4()}@example.com"

    try:
        resp = client.post("/api/auth/google/exchange", json={
            "email": email,
            "name": "Google Student",
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "timezone": "Asia/Singapore",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["user_id"]

        db = TestingSession()
        try:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert user.google_access_token == "google-access-token"
            assert user.google_refresh_token == "google-refresh-token"
            assert user.uses_google_calendar is True
        finally:
            db.close()
    finally:
        cleanup_db = TestingSession()
        try:
            cleanup_db.query(User).filter(User.email == email).delete()
            cleanup_db.commit()
        finally:
            cleanup_db.close()
