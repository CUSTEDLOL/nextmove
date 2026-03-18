import pytest
import uuid
from datetime import datetime
from app.telegram.handlers.today import format_today_message
from app.schemas.tasks import TaskResponse


def make_task(title, effort="medium", priority=5.0):
    return TaskResponse(
        id=uuid.uuid4(),
        title=title,
        deadline=None,
        effort=effort,
        importance=3,
        context="Study",
        priority_index=priority,
        status="pending",
        created_at=datetime.utcnow()
    )


def test_format_today_with_primary_and_secondary():
    primary = make_task("Finish ML assignment", effort="high", priority=8.5)
    secondary = [make_task("Review notes", effort="low", priority=3.0)]
    msg = format_today_message(primary, secondary)
    assert "Finish ML assignment" in msg
    assert "Review notes" in msg
    assert "🎯" in msg


def test_format_today_primary_only():
    primary = make_task("Write essay", effort="high")
    msg = format_today_message(primary, [])
    assert "Write essay" in msg
    assert "🎯" in msg


def test_format_today_no_tasks():
    msg = format_today_message(None, [])
    assert "no" in msg.lower() or "clear" in msg.lower() or "empty" in msg.lower()


def test_format_shows_effort():
    primary = make_task("Hard task", effort="high")
    msg = format_today_message(primary, [])
    assert "high" in msg.lower()
