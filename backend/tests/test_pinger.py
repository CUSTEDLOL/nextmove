import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import NotificationLog, ScheduleBlock, Task, User
from tests.conftest import TestingSessionFactory


CHAT_ID = 9_100_001
CHAT_ID_TZ = 9_100_002


def _cleanup_user(chat_id: int) -> None:
    db = TestingSessionFactory()
    try:
        stale_users = db.query(User).filter(User.telegram_chat_id == chat_id).all()
        for user in stale_users:
            user.pending_steps_task_id = None
            user.pending_edit_task_id = None
        db.flush()

        for user in stale_users:
            db.query(NotificationLog).filter(NotificationLog.user_id == user.id).delete()
            db.query(ScheduleBlock).filter(ScheduleBlock.user_id == user.id).delete()
            db.query(Task).filter(Task.user_id == user.id).delete()
            db.delete(user)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def linked_user_id():
    _cleanup_user(CHAT_ID)

    db = TestingSessionFactory()
    try:
        user = User(
            email=f"pinger_test_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="x",
            telegram_chat_id=CHAT_ID,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    yield user_id

    _cleanup_user(CHAT_ID)


@pytest.fixture
def linked_user_sydney():
    """User in Australia/Sydney (UTC+10 in April, no DST)."""
    _cleanup_user(CHAT_ID_TZ)

    db = TestingSessionFactory()
    try:
        user = User(
            email=f"pinger_tz_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password="x",
            telegram_chat_id=CHAT_ID_TZ,
            timezone="Australia/Sydney",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    yield user_id

    _cleanup_user(CHAT_ID_TZ)


def _create_task(
    user_id,
    *,
    title: str,
    created_at: datetime,
    status: str = "scheduled",
    priority: float = 8.0,
):
    db = TestingSessionFactory()
    try:
        task = Task(
            user_id=user_id,
            title=title,
            status=status,
            priority_index=priority,
            effort="medium",
            importance=3,
            created_at=created_at,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def _create_subtask(user_id, parent_task_id, *, title: str, created_at: datetime):
    db = TestingSessionFactory()
    try:
        task = Task(
            user_id=user_id,
            parent_task_id=parent_task_id,
            title=title,
            status="scheduled",
            priority_index=5.0,
            effort="low",
            importance=2,
            created_at=created_at,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def _create_schedule_block(user_id, task_id, *, start_time: datetime, end_time: datetime):
    db = TestingSessionFactory()
    try:
        block = ScheduleBlock(
            user_id=user_id,
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
        )
        db.add(block)
        db.commit()
        return block.id
    finally:
        db.close()


def _notification_logs_for_task(user_id, task_id) -> list[NotificationLog]:
    db = TestingSessionFactory()
    try:
        return (
            db.query(NotificationLog)
            .filter(
                NotificationLog.user_id == user_id,
                NotificationLog.type == f"missed_block:{task_id}",
            )
            .all()
        )
    finally:
        db.close()


def _calls_for_chat(send_message_mock: AsyncMock, chat_id: int):
    return [
        call.kwargs
        for call in send_message_mock.await_args_list
        if call.kwargs.get("chat_id") == chat_id
    ]


# ---------------------------------------------------------------------------
# Existing happy-path tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinger_sends_when_task_has_missed_block_today(linked_user_id):
    now = datetime.utcnow()
    task_id = _create_task(
        linked_user_id,
        title="Prep stats slides",
        created_at=now,
    )
    _create_schedule_block(
        linked_user_id,
        task_id,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=30),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application",
        return_value=mock_app,
    ):
        from app.services.pinger import ping_procrastinating_users

        await ping_procrastinating_users()

    calls = _calls_for_chat(mock_app.bot.send_message, CHAT_ID)
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["chat_id"] == CHAT_ID
    assert "Prep stats slides" in kwargs["text"]

    logs = _notification_logs_for_task(linked_user_id, task_id)
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_pinger_skips_old_tasks_without_a_missed_schedule_block(linked_user_id):
    _create_task(
        linked_user_id,
        title="Old backlog task",
        created_at=datetime.utcnow() - timedelta(days=4),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application",
        return_value=mock_app,
    ):
        from app.services.pinger import ping_procrastinating_users

        await ping_procrastinating_users()

    calls = _calls_for_chat(mock_app.bot.send_message, CHAT_ID)
    assert calls == []


@pytest.mark.asyncio
async def test_pinger_only_sends_once_per_task_per_day(linked_user_id):
    now = datetime.utcnow()
    task_id = _create_task(
        linked_user_id,
        title="Review lecture notes",
        created_at=now - timedelta(days=3),
    )
    _create_schedule_block(
        linked_user_id,
        task_id,
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=1),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application",
        return_value=mock_app,
    ):
        from app.services.pinger import ping_procrastinating_users

        await ping_procrastinating_users()
        await ping_procrastinating_users()

    calls = _calls_for_chat(mock_app.bot.send_message, CHAT_ID)
    assert len(calls) == 1

    logs = _notification_logs_for_task(linked_user_id, task_id)
    assert len(logs) == 1


# ---------------------------------------------------------------------------
# Regression tests — filter correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinger_silent_for_future_block(linked_user_id):
    now = datetime.utcnow()
    task_id = _create_task(linked_user_id, title="Future assignment", created_at=now)
    _create_schedule_block(
        linked_user_id, task_id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users()

    assert _calls_for_chat(mock_app.bot.send_message, CHAT_ID) == []


@pytest.mark.asyncio
async def test_pinger_silent_for_completed_task(linked_user_id):
    now = datetime.utcnow()
    task_id = _create_task(
        linked_user_id, title="Already done task", created_at=now, status="completed"
    )
    _create_schedule_block(
        linked_user_id, task_id,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=30),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users()

    assert _calls_for_chat(mock_app.bot.send_message, CHAT_ID) == []


@pytest.mark.asyncio
async def test_pinger_silent_for_subtask(linked_user_id):
    now = datetime.utcnow()
    parent_id = _create_task(linked_user_id, title="Parent task", created_at=now)
    subtask_id = _create_subtask(
        linked_user_id, parent_id, title="Child task", created_at=now
    )
    _create_schedule_block(
        linked_user_id, subtask_id,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=30),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users()

    assert _calls_for_chat(mock_app.bot.send_message, CHAT_ID) == []


# ---------------------------------------------------------------------------
# Race-condition fix — log committed before send
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinger_log_written_before_send_prevents_repinge_after_failure(linked_user_id):
    """If send_message raises, the NotificationLog must already be committed
    so the next hourly run does not re-ping the user."""
    now = datetime.utcnow()
    task_id = _create_task(linked_user_id, title="Urgent lab report", created_at=now)
    _create_schedule_block(
        linked_user_id, task_id,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=30),
    )

    mock_app_fail = MagicMock()
    mock_app_fail.bot.send_message = AsyncMock(side_effect=RuntimeError("Telegram down"))

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app_fail
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users()

    logs = _notification_logs_for_task(linked_user_id, task_id)
    assert len(logs) == 1, "Log must be written before send so failures don't cause re-pings"

    mock_app_ok = MagicMock()
    mock_app_ok.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app_ok
    ):
        await ping_procrastinating_users()

    assert _calls_for_chat(mock_app_ok.bot.send_message, CHAT_ID) == []


# ---------------------------------------------------------------------------
# Timezone — "today" in user's local timezone, not UTC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinger_uses_user_timezone_for_today_boundary(linked_user_sydney):
    """A block that ended before UTC midnight but within the user's local 'today'
    (Australia/Sydney, UTC+10 in April) must still trigger a ping.

    Timeline (all UTC):
      block ends  2026-04-19 22:30  =  2026-04-20 08:30 AEST  → "today" for Sydney
      pinger runs 2026-04-20 00:30  =  2026-04-20 10:30 AEST  → also "today"
      UTC today_start = 2026-04-20 00:00 — block is BEFORE it without TZ fix.
    """
    fake_now = datetime(2026, 4, 20, 0, 30, 0)
    block_end = datetime(2026, 4, 19, 22, 30, 0)

    task_id = _create_task(
        linked_user_sydney,
        title="Morning lecture notes",
        created_at=block_end - timedelta(hours=1),
    )
    _create_schedule_block(
        linked_user_sydney, task_id,
        start_time=block_end - timedelta(hours=1),
        end_time=block_end,
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users(_now=fake_now)

    calls = _calls_for_chat(mock_app.bot.send_message, CHAT_ID_TZ)
    assert len(calls) == 1, "Should ping when block is 'today' in user's local timezone"


# ---------------------------------------------------------------------------
# Privacy — no internal UTC label exposed in message text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinger_message_does_not_expose_utc_label(linked_user_id):
    """Message text must not contain 'UTC' — that's server-internal detail."""
    now = datetime.utcnow()
    task_id = _create_task(linked_user_id, title="Read chapter 4", created_at=now)
    _create_schedule_block(
        linked_user_id, task_id,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=30),
    )

    mock_app = MagicMock()
    mock_app.bot.send_message = AsyncMock()

    with patch("app.services.pinger.SessionLocal", TestingSessionFactory), patch(
        "app.telegram.bot.get_application", return_value=mock_app
    ):
        from app.services.pinger import ping_procrastinating_users
        await ping_procrastinating_users()

    calls = _calls_for_chat(mock_app.bot.send_message, CHAT_ID)
    assert len(calls) == 1
    assert "UTC" not in calls[0]["text"]
