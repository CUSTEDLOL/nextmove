"""
Tests for workers/notification_jobs.py
All external calls (DB, Telegram) are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_morning_brief_sends_to_linked_users():
    """morning_brief_job sends a message to each user with a telegram_chat_id."""
    mock_user = MagicMock()
    mock_user.id = "user-1"
    mock_user.name = "Alice"
    mock_user.telegram_chat_id = 12345

    mock_primary = MagicMock()
    mock_primary.title = "Essay"
    mock_primary.effort = "high"
    mock_primary.deadline = datetime.utcnow() + timedelta(days=1)

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs.task_service.get_today") as mock_today, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]

        mock_today.return_value = MagicMock(primary=mock_primary, secondary=[])
        mock_send.return_value = None

        from app.workers.notification_jobs import morning_brief_job
        await morning_brief_job()

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == 12345
        assert "Essay" in args[1]


@pytest.mark.asyncio
async def test_morning_brief_skips_unlinked_users():
    """morning_brief_job does not send to users without telegram_chat_id."""
    mock_user = MagicMock()
    mock_user.telegram_chat_id = None

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]

        from app.workers.notification_jobs import morning_brief_job
        await morning_brief_job()

        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_evening_wrapup_counts_completed():
    """evening_wrapup_job reports correct count of completed tasks today."""
    mock_user = MagicMock()
    mock_user.id = "user-1"
    mock_user.telegram_chat_id = 12345

    with patch("app.workers.notification_jobs.SessionLocal") as mock_session_cls, \
         patch("app.workers.notification_jobs._send_telegram_message") as mock_send:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        # First call: users list; subsequent calls: completed count, missed count
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_user]
        mock_db.query.return_value.filter.return_value.count.side_effect = [2, 0]

        from app.workers.notification_jobs import evening_wrapup_job
        await evening_wrapup_job()

        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert "2" in args[1]
