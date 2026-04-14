import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True, scope="module")
def setup_user_overrides():
    test_user = User(
        id=USER_ID,
        email=f"user_{USER_ID}@uni.edu",
        name="Casey",
        timezone="UTC",
        study_start_hour=9,
        study_end_hour=22,
    )

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    db = TestingSession()
    db.add(User(
        id=USER_ID,
        email=f"user_{USER_ID}@uni.edu",
        name="Casey",
        timezone="UTC",
        study_start_hour=9,
        study_end_hour=22,
    ))
    db.commit()
    db.close()

    yield

    db = TestingSession()
    db.query(User).filter(User.id == USER_ID).delete()
    db.commit()
    db.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_get_me(client):
    resp = client.get("/api/users/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == f"user_{USER_ID}@uni.edu"
    assert data["name"] == "Casey"
    assert data["timezone"] == "UTC"
    assert data["study_start_hour"] == 9


def test_patch_me(client):
    resp = client.patch("/api/users/me", json={
        "name": "Casey Updated",
        "timezone": "Asia/Singapore",
        "study_start_hour": 8,
        "study_end_hour": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Casey Updated"
    assert data["timezone"] == "Asia/Singapore"
    assert data["study_start_hour"] == 8
    assert data["study_end_hour"] == 20
