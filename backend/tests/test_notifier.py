import pytest
import uuid
from datetime import datetime
from app.services.notifier import (
    build_morning_brief, build_procrastination_prompt,
    build_pretask_nudge, build_evening_wrapup
)
from app.schemas.tasks import TaskResponse


def make_task(title, effort="medium"):
    return TaskResponse(
        id=uuid.uuid4(), title=title, deadline=None,
        effort=effort, importance=3, context="Study",
        priority_index=5.0, status="scheduled",
        created_at=datetime.utcnow()
    )


def test_morning_brief_with_tasks():
    primary = make_task("Finish stats assignment", "high")
    secondary = [make_task("Review chapter 3", "low")]
    msg = build_morning_brief("Alice", primary, secondary)
    assert "Alice" in msg
    assert "Finish stats assignment" in msg
    assert "Review chapter 3" in msg
    assert "🎯" in msg


def test_morning_brief_no_tasks():
    msg = build_morning_brief("Bob", None, [])
    assert "Bob" in msg
    # Should say something about no tasks
    assert any(w in msg.lower() for w in ["no", "clear", "nothing", "empty"])


def test_procrastination_prompt_contains_task():
    task = make_task("Study for econ midterm", "high")
    msg = build_procrastination_prompt(task)
    assert "Study for econ midterm" in msg
    assert "?" in msg  # asks a question


def test_pretask_nudge_contains_task():
    task = make_task("Write lab report", "medium")
    msg = build_pretask_nudge(task)
    assert "Write lab report" in msg


def test_evening_wrapup_completed():
    msg = build_evening_wrapup(completed_count=3, missed_count=1)
    assert "3" in msg
    assert "1" in msg


def test_evening_wrapup_nothing():
    msg = build_evening_wrapup(completed_count=0, missed_count=0)
    assert len(msg) > 0  # at least says something
