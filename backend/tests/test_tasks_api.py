import pytest
import uuid
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Base, User, Task, ScheduleBlock, CalendarEvent  # noqa: F401

# Use real Postgres for API tests (PostgreSQL UUID support required)
TEST_DB_URL = "postgresql://nextmove:nextmove@localhost:5432/nextmove"
engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a unique test user per test run so tests don't collide
TEST_USER_ID = uuid.uuid4()
mock_user = User(id=TEST_USER_ID, email=f"test_{TEST_USER_ID}@uni.edu", name="Alice", timezone="UTC")


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: mock_user
client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def seed_user():
    """Insert test user into Postgres once for all tests in this module."""
    db = TestingSession()
    db.add(User(
        id=TEST_USER_ID,
        email=f"test_{TEST_USER_ID}@uni.edu",
        name="Alice",
        timezone="UTC"
    ))
    db.commit()
    db.close()
    yield
    # Cleanup after all tests
    db = TestingSession()
    db.query(Task).filter(Task.user_id == TEST_USER_ID).delete()
    db.query(User).filter(User.id == TEST_USER_ID).delete()
    db.commit()
    db.close()


def test_add_single_task():
    resp = client.post("/api/tasks", json={
        "title": "Study for exam",
        "effort": "high",
        "importance": 4
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Study for exam"
    assert data["status"] == "pending"
    assert data["priority_index"] is not None
    assert data["priority_index"] > 0


def test_list_tasks():
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_today_tasks():
    resp = client.get("/api/tasks/today")
    assert resp.status_code == 200
    data = resp.json()
    assert "primary" in data
    assert "secondary" in data
    assert isinstance(data["secondary"], list)


@patch("app.routers.tasks.parse_brain_dump")
def test_brain_dump(mock_parse):
    from app.services.ai_parser import ParsedTask
    mock_parse.return_value = [
        ParsedTask(title="Finish ML assignment", deadline="2026-03-25",
                   effort="high", importance=4, context="Study"),
        ParsedTask(title="Review lecture notes", deadline=None,
                   effort="low", importance=2, context="Study"),
    ]
    resp = client.post("/api/tasks/dump", json={
        "text": "Finish ML assignment by Friday and review lecture notes tonight"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 2
    titles = [t["title"] for t in data["tasks"]]
    assert "Finish ML assignment" in titles


def test_complete_task():
    create_resp = client.post("/api/tasks", json={
        "title": "Task to complete",
        "effort": "low",
        "importance": 2
    })
    task_id = create_resp.json()["id"]
    resp = client.post(f"/api/tasks/{task_id}/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
