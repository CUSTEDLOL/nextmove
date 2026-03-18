import pytest
import uuid
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Task, ScheduleBlock
from tests.conftest import engine

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TASKS_USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True, scope="module")
def setup_tasks_overrides():
    """Set dependency overrides for this module, clean up after."""
    test_user = User(
        id=TASKS_USER_ID,
        email=f"tasks_{TASKS_USER_ID}@uni.edu",
        name="Alice",
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

    # Seed user
    db = TestingSession()
    db.add(User(id=TASKS_USER_ID, email=f"tasks_{TASKS_USER_ID}@uni.edu", name="Alice", timezone="UTC"))
    db.commit()
    db.close()

    yield

    # Teardown — order matters: blocks → tasks → user (foreign keys)
    db = TestingSession()
    db.query(ScheduleBlock).filter(ScheduleBlock.user_id == TASKS_USER_ID).delete()
    db.query(Task).filter(Task.user_id == TASKS_USER_ID).delete()
    db.query(User).filter(User.id == TASKS_USER_ID).delete()
    db.commit()
    db.close()
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_add_single_task(client):
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


def test_list_tasks(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_today_tasks(client):
    resp = client.get("/api/tasks/today")
    assert resp.status_code == 200
    data = resp.json()
    assert "primary" in data
    assert "secondary" in data
    assert isinstance(data["secondary"], list)


@patch("app.routers.tasks.parse_brain_dump")
def test_brain_dump(mock_parse, client):
    from app.services.ai_parser import ParsedTask
    mock_parse.return_value = [
        ParsedTask(title="Finish ML assignment", deadline="2026-03-25",
                   effort="high", importance=4, context="Study"),
        ParsedTask(title="Review lecture notes", deadline=None,
                   effort="low", importance=2, context="Study"),
    ]
    resp = client.post("/api/tasks/dump", json={
        "text": "Finish ML by Friday and review notes tonight"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 2
    assert "Finish ML assignment" in [t["title"] for t in data["tasks"]]


def test_complete_task(client):
    create_resp = client.post("/api/tasks", json={
        "title": "Task to complete",
        "effort": "low",
        "importance": 2
    })
    task_id = create_resp.json()["id"]
    resp = client.post(f"/api/tasks/{task_id}/complete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
