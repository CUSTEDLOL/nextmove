"""
Tests for app/telegram/db_helpers.py

Covers:
- get_steps_for_chat_id returns dicts (not ORM objects) — fixes DetachedInstanceError
- set_pending_steps / get_pending_steps_task_id / clear_pending_steps round-trip
- list_tasks_for_chat_id returns a list
- complete_top_task_for_chat_id marks highest-priority task completed
- skip_top_task_for_chat_id marks highest-priority task rescheduled
"""
import pytest
import uuid
import asyncio
import os
from unittest.mock import AsyncMock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Task, ScheduleBlock

# ---------------------------------------------------------------------------
# DB setup (mirrors conftest.py pattern)
# ---------------------------------------------------------------------------
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://nextmove:nextmove@localhost:5432/nextmove"),
)
engine = create_engine(TEST_DB_URL)
TestingSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

CHAT_ID = 9_000_001  # unique enough not to collide with other tests


@pytest.fixture(autouse=True)
def clean_test_user():
    """
    Create a fresh test user + tasks before each test, clean up after.
    Uses a unique email per run to avoid UNIQUE constraint issues.
    Teardown clears pending_steps_task_id FK before deleting tasks to avoid
    FK constraint violations.
    """
    db = TestingSessionFactory()
    # Ensure no leftover users from prior failed runs with this CHAT_ID
    stale = db.query(User).filter(User.telegram_chat_id == CHAT_ID).all()
    for s in stale:
        s.pending_steps_task_id = None
        s.pending_edit_task_id = None
    db.flush()
    for s in stale:
        db.query(ScheduleBlock).filter(ScheduleBlock.user_id == s.id).delete()
        db.query(Task).filter(Task.user_id == s.id).delete()
        db.delete(s)
    db.commit()

    unique_suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"dbhelpers_test_{unique_suffix}@test.com",
        hashed_password="x",
        telegram_chat_id=CHAT_ID,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    yield user_id  # tests that need the user_id can receive via fixture parameter

    # teardown — open a fresh session so we see any changes made by db_helpers
    db.close()
    teardown_db = TestingSessionFactory()
    try:
        # Clear pending_steps FK first to avoid FK violation when deleting tasks
        user_row = teardown_db.query(User).filter(User.id == user_id).first()
        if user_row:
            user_row.pending_steps_task_id = None
            user_row.pending_edit_task_id = None
            teardown_db.flush()
        teardown_db.query(ScheduleBlock).filter(ScheduleBlock.user_id == user_id).delete()
        teardown_db.query(Task).filter(Task.user_id == user_id).delete()
        teardown_db.query(User).filter(User.id == user_id).delete()
        teardown_db.commit()
    finally:
        teardown_db.close()


def _create_task(user_id, title="Test task", priority=5.0, parent_id=None):
    db = TestingSessionFactory()
    task = Task(
        user_id=user_id,
        title=title,
        status="pending",
        priority_index=priority,
        parent_task_id=parent_id,
        effort="medium",
        importance=3,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id
    db.close()
    return task_id


# ---------------------------------------------------------------------------
# Helper to run async functions in tests
# ---------------------------------------------------------------------------
def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetStepsForChatId:
    """get_steps_for_chat_id must return dicts, not ORM objects."""

    def test_returns_dicts_not_orm_objects(self, clean_test_user):
        from app.telegram.db_helpers import get_steps_for_chat_id

        user_id = clean_test_user
        parent_id = _create_task(user_id, "Parent task")
        _create_task(user_id, "Step 1", parent_id=parent_id)
        _create_task(user_id, "Step 2", parent_id=parent_id)

        result = run(get_steps_for_chat_id(CHAT_ID, str(parent_id)))
        assert result is not None
        parent_data, steps_data = result

        # steps must be plain dicts with a "status" key (not ORM objects)
        assert isinstance(steps_data, list)
        assert len(steps_data) == 2
        for step in steps_data:
            assert isinstance(step, dict), "Steps must be dicts, not ORM objects"
            assert "status" in step, "Step dict must have 'status' key"
            assert "title" in step
            assert "id" in step

    def test_accessing_status_does_not_raise(self, clean_test_user):
        """Accessing .status after session close must not raise DetachedInstanceError."""
        from app.telegram.db_helpers import get_steps_for_chat_id

        user_id = clean_test_user
        parent_id = _create_task(user_id, "Parent task")
        _create_task(user_id, "Step A", parent_id=parent_id)

        result = run(get_steps_for_chat_id(CHAT_ID, str(parent_id)))
        assert result is not None
        _, steps_data = result

        # This would raise DetachedInstanceError on ORM objects after session close
        for step in steps_data:
            _ = step["status"]  # must not raise

    def test_unknown_chat_returns_none(self, clean_test_user):
        from app.telegram.db_helpers import get_steps_for_chat_id

        result = run(get_steps_for_chat_id(99999999, str(uuid.uuid4())))
        assert result is None

    def test_unknown_task_returns_none(self, clean_test_user):
        from app.telegram.db_helpers import get_steps_for_chat_id

        result = run(get_steps_for_chat_id(CHAT_ID, str(uuid.uuid4())))
        assert result is None


class TestPendingSteps:
    """set/get/clear pending_steps_task_id on the User row."""

    def test_set_then_get(self, clean_test_user):
        from app.telegram.db_helpers import set_pending_steps, get_pending_steps_task_id

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task for pending steps")

        run(set_pending_steps(CHAT_ID, str(task_id)))
        result = run(get_pending_steps_task_id(CHAT_ID))
        assert result == task_id

    def test_clear_removes_value(self, clean_test_user):
        from app.telegram.db_helpers import (
            set_pending_steps,
            clear_pending_steps,
            get_pending_steps_task_id,
        )

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task to clear")

        run(set_pending_steps(CHAT_ID, str(task_id)))
        run(clear_pending_steps(CHAT_ID))

        result = run(get_pending_steps_task_id(CHAT_ID))
        assert result is None

    def test_get_without_set_returns_none(self, clean_test_user):
        from app.telegram.db_helpers import get_pending_steps_task_id

        result = run(get_pending_steps_task_id(CHAT_ID))
        assert result is None

    def test_unknown_chat_set_is_noop(self):
        from app.telegram.db_helpers import set_pending_steps

        # Should not raise even for unknown chat
        run(set_pending_steps(99999999, str(uuid.uuid4())))


class TestListTasksForChatId:
    """list_tasks_for_chat_id returns a list of TaskResponse."""

    def test_returns_list(self, clean_test_user):
        from app.telegram.db_helpers import list_tasks_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Task A", priority=7.0)
        _create_task(user_id, "Task B", priority=3.0)

        result = run(list_tasks_for_chat_id(CHAT_ID))
        assert isinstance(result, list)
        assert len(result) == 2

    def test_returns_empty_list_when_no_tasks(self, clean_test_user):
        from app.telegram.db_helpers import list_tasks_for_chat_id

        result = run(list_tasks_for_chat_id(CHAT_ID))
        assert result == []

    def test_unknown_chat_returns_none(self):
        from app.telegram.db_helpers import list_tasks_for_chat_id

        result = run(list_tasks_for_chat_id(99999999))
        assert result is None

    def test_ordered_by_priority_desc(self, clean_test_user):
        from app.telegram.db_helpers import list_tasks_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Low priority", priority=1.0)
        _create_task(user_id, "High priority", priority=9.0)

        result = run(list_tasks_for_chat_id(CHAT_ID))
        assert result[0].title == "High priority"


class TestProcessDumpForChatId:
    def test_process_dump_reruns_schedule(self, clean_test_user):
        from app.services.ai_parser import ParsedTask
        from app.telegram.db_helpers import process_dump_for_chat_id

        parsed = [
            ParsedTask(
                title="Draft essay outline",
                deadline=None,
                effort="medium",
                importance=4,
                context="Study",
                steps=["Open notes"],
            )
        ]

        with patch("app.telegram.db_helpers.parse_brain_dump", AsyncMock(return_value=parsed)), \
             patch("app.telegram.db_helpers.run_schedule_for_user") as schedule_mock:
            result = run(process_dump_for_chat_id(CHAT_ID, "draft essay outline"))

        assert result is not None
        schedule_mock.assert_called_once()


class TestCompleteTopTaskForChatId:
    """complete_top_task_for_chat_id marks highest-priority task completed."""

    def test_completes_highest_priority_task(self, clean_test_user):
        from app.telegram.db_helpers import complete_top_task_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Low task", priority=2.0)
        _create_task(user_id, "Top task", priority=9.0)

        result = run(complete_top_task_for_chat_id(CHAT_ID))
        assert result is not None
        assert result.title == "Top task"
        assert result.status == "completed"

    def test_completing_top_task_reruns_schedule(self, clean_test_user):
        from app.telegram.db_helpers import complete_top_task_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Top task", priority=9.0)

        with patch("app.telegram.db_helpers.run_schedule_for_user") as schedule_mock:
            result = run(complete_top_task_for_chat_id(CHAT_ID))

        assert result is not None
        schedule_mock.assert_called_once()

    def test_returns_none_when_no_tasks(self, clean_test_user):
        from app.telegram.db_helpers import complete_top_task_for_chat_id

        result = run(complete_top_task_for_chat_id(CHAT_ID))
        assert result is None

    def test_unknown_chat_returns_none(self):
        from app.telegram.db_helpers import complete_top_task_for_chat_id

        result = run(complete_top_task_for_chat_id(99999999))
        assert result is None


class TestSkipTopTaskForChatId:
    """skip_top_task_for_chat_id reschedules highest-priority task."""

    def test_skips_highest_priority_task(self, clean_test_user):
        from app.telegram.db_helpers import skip_top_task_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Low task", priority=1.0)
        _create_task(user_id, "Top task", priority=8.0)

        result = run(skip_top_task_for_chat_id(CHAT_ID))
        assert result is not None
        assert result.title == "Top task"
        assert result.status == "rescheduled"

    def test_skipping_top_task_reruns_schedule(self, clean_test_user):
        from app.telegram.db_helpers import skip_top_task_for_chat_id

        user_id = clean_test_user
        _create_task(user_id, "Top task", priority=8.0)

        with patch("app.telegram.db_helpers.run_schedule_for_user") as schedule_mock:
            result = run(skip_top_task_for_chat_id(CHAT_ID))

        assert result is not None
        schedule_mock.assert_called_once()

    def test_returns_none_when_no_tasks(self, clean_test_user):
        from app.telegram.db_helpers import skip_top_task_for_chat_id

        result = run(skip_top_task_for_chat_id(CHAT_ID))
        assert result is None

    def test_unknown_chat_returns_none(self):
        from app.telegram.db_helpers import skip_top_task_for_chat_id

        result = run(skip_top_task_for_chat_id(99999999))
        assert result is None


class TestPendingEdit:
    """set/get/clear pending_edit_task_id and apply_task_edit helpers."""

    def test_set_and_get_pending_edit(self, clean_test_user):
        from app.telegram.db_helpers import set_pending_edit, get_pending_edit_task_id

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task for pending edit")

        run(set_pending_edit(CHAT_ID, str(task_id)))
        result = run(get_pending_edit_task_id(CHAT_ID))
        assert result == task_id

    def test_clear_pending_edit(self, clean_test_user):
        from app.telegram.db_helpers import set_pending_edit, clear_pending_edit, get_pending_edit_task_id

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task to clear edit")

        run(set_pending_edit(CHAT_ID, str(task_id)))
        run(clear_pending_edit(CHAT_ID))
        result = run(get_pending_edit_task_id(CHAT_ID))
        assert result is None

    def test_apply_task_edit_deadline(self, clean_test_user):
        from app.telegram.db_helpers import apply_task_edit

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task for deadline edit")

        with patch("app.telegram.db_helpers.run_schedule_for_user") as schedule_mock:
            ok = run(apply_task_edit(CHAT_ID, str(task_id), {"field": "deadline", "value": "2026-04-01"}))

        assert ok is True
        schedule_mock.assert_called_once()

    def test_apply_task_edit_title(self, clean_test_user):
        from app.telegram.db_helpers import apply_task_edit

        user_id = clean_test_user
        task_id = _create_task(user_id, "Original title")

        ok = run(apply_task_edit(CHAT_ID, str(task_id), {"field": "title", "value": "New Title"}))
        assert ok is True

    def test_apply_task_edit_delete(self, clean_test_user):
        from app.telegram.db_helpers import apply_task_edit

        user_id = clean_test_user
        task_id = _create_task(user_id, "Task to delete")

        ok = run(apply_task_edit(CHAT_ID, str(task_id), {"field": "delete"}))
        assert ok is True
