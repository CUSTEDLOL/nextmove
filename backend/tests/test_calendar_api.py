import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, CalendarEvent
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CAL_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True, scope="module")
def setup_calendar_overrides():
    test_user = User(
        id=CAL_USER_ID,
        email=f"cal_{CAL_USER_ID}@uni.edu",
        name="Bob",
        timezone="UTC"
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
    db.add(User(id=CAL_USER_ID, email=f"cal_{CAL_USER_ID}@uni.edu", name="Bob", timezone="UTC"))
    db.commit()
    db.close()

    yield

    db = TestingSession()
    db.query(CalendarEvent).filter(CalendarEvent.user_id == CAL_USER_ID).delete()
    db.query(User).filter(User.id == CAL_USER_ID).delete()
    db.commit()
    db.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_create_calendar_event(client):
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=2)
    resp = client.post("/api/calendar/events", json={
        "title": "Study session",
        "start_time": start.isoformat(),
        "end_time": end.isoformat()
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Study session"
    assert "id" in data


def test_list_calendar_events(client):
    resp = client.get("/api/calendar/events")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_delete_calendar_event(client):
    start = datetime.utcnow() + timedelta(hours=3)
    end = start + timedelta(hours=1)
    create_resp = client.post("/api/calendar/events", json={
        "title": "Temp event",
        "start_time": start.isoformat(),
        "end_time": end.isoformat()
    })
    event_id = create_resp.json()["id"]
    del_resp = client.delete(f"/api/calendar/events/{event_id}")
    assert del_resp.status_code == 200
    ids = [e["id"] for e in client.get("/api/calendar/events").json()]
    assert event_id not in ids
