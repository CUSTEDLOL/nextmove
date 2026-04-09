import pytest
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task, ScheduleBlock
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SCHEDULE_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True, scope="module")
def setup_schedule_overrides():
    test_user = User(
        id=SCHEDULE_USER_ID,
        email=f"schedule_{SCHEDULE_USER_ID}@uni.edu",
        name="Riley",
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
        id=SCHEDULE_USER_ID,
        email=f"schedule_{SCHEDULE_USER_ID}@uni.edu",
        name="Riley",
        timezone="UTC",
        study_start_hour=9,
        study_end_hour=22,
    ))
    db.commit()
    db.close()

    yield

    db = TestingSession()
    db.query(ScheduleBlock).filter(ScheduleBlock.user_id == SCHEDULE_USER_ID).delete()
    db.query(Task).filter(Task.user_id == SCHEDULE_USER_ID).delete()
    db.query(User).filter(User.id == SCHEDULE_USER_ID).delete()
    db.commit()
    db.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_schedule_rebuild_creates_blocks(client):
    db = TestingSession()
    try:
        db.add(Task(
            user_id=SCHEDULE_USER_ID,
            title="Deep work block",
            effort="high",
            importance=5,
            urgency_score=90,
            importance_score=95,
            priority_index=9.4,
            status="pending",
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/schedule/rebuild")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entry_type"] == "block"


def test_free_slots_endpoint_returns_time_ranges(client):
    resp = client.get("/api/schedule/free-slots")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "start" in data[0]
    assert "end" in data[0]


def test_schedule_respects_user_timezone():
    """A UTC+8 user with study_start=9 should get blocks starting at 01:00 UTC."""
    from app.services.schedule_runner import run_schedule_for_user
    from app.models import Task, ScheduleBlock
    db = TestingSession()
    try:
        tz_user_id = uuid.uuid4()
        tz_user = User(
            id=tz_user_id,
            email=f"tz_{tz_user_id}@uni.edu",
            name="TZ Tester",
            timezone="Asia/Singapore",   # UTC+8
            study_start_hour=9,
            study_end_hour=22,
        )
        db.add(tz_user)
        db.add(Task(
            user_id=tz_user_id,
            title="TZ test task",
            effort="low",
            priority_index=5.0,
            status="pending",
        ))
        db.commit()

        # Simulate scheduler running at 00:00 UTC = 08:00 Asia/Singapore on 2026-04-09
        reference_utc = datetime(2026, 4, 9, 0, 0, 0)
        blocks = run_schedule_for_user(tz_user, db, date=reference_utc)
        assert len(blocks) >= 1
        # First block should start at 01:00 UTC (= 09:00 Asia/Singapore)
        assert blocks[0].start_time.hour == 1
    finally:
        db.query(ScheduleBlock).filter(ScheduleBlock.user_id == tz_user_id).delete()
        db.query(Task).filter(Task.user_id == tz_user_id).delete()
        db.query(User).filter(User.id == tz_user_id).delete()
        db.commit()
        db.close()
