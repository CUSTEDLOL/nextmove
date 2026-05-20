"""
Tests for Task 2: Skip→Delete with confirmation, Reschedule→pick date, Start task button.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_reschedule_callback_sends_when_keyboard():
    """Clicking Reschedule sends a 'when?' message with date buttons."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "reschedule:task-123"
    update.callback_query.answer = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.db_helpers.get_task_for_chat_id") as mock_get:
        mock_get.return_value = MagicMock(title="Essay", id="task-123")
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    update.callback_query.message.reply_text.assert_called_once()
    call_text = update.callback_query.message.reply_text.call_args[0][0]
    assert "when" in call_text.lower() or "push" in call_text.lower()


@pytest.mark.asyncio
async def test_skip_shows_confirmation_keyboard():
    """Clicking Skip shows a confirmation message before deleting."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "skip:task-123"
    update.callback_query.answer = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.db_helpers.get_task_for_chat_id") as mock_get:
        mock_get.return_value = MagicMock(title="Essay", id="task-123")
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    update.callback_query.message.reply_text.assert_called_once()
    call_text = update.callback_query.message.reply_text.call_args[0][0]
    assert "Essay" in call_text


@pytest.mark.asyncio
async def test_skip_confirm_deletes_task():
    """Confirming skip calls delete_task_for_chat_id."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "skip_confirm:task-123"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat.id = 42
    update.effective_message = AsyncMock()
    context = MagicMock()

    with patch("app.telegram.handlers.callbacks.delete_task_for_chat_id") as mock_del, \
         patch("app.telegram.handlers.callbacks.today_command") as mock_today:
        mock_del.return_value = True
        mock_today.return_value = None
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    mock_del.assert_called_once_with(42, "task-123")


@pytest.mark.asyncio
async def test_reschedule_pick_updates_deadline():
    """Picking 'In 3 days' calls reschedule_task_for_chat_id with correct deadline."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "reschedule_pick:task-123:3"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat.id = 42
    update.effective_message = AsyncMock()
    context = MagicMock()

    with patch("app.telegram.handlers.callbacks.reschedule_task_for_chat_id") as mock_reschedule, \
         patch("app.telegram.handlers.callbacks.today_command") as mock_today:
        mock_reschedule.return_value = MagicMock(title="Essay")
        mock_today.return_value = None
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    mock_reschedule.assert_called_once()
    args = mock_reschedule.call_args[0]
    assert args[0] == 42
    assert args[1] == "task-123"
    expected_date = datetime.utcnow() + timedelta(days=3)
    actual_date = args[2]
    assert abs((actual_date - expected_date).total_seconds()) < 60


@pytest.mark.asyncio
async def test_start_callback_marks_in_progress():
    """Clicking Start calls start_task_for_chat_id."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = "start:task-123"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.effective_chat.id = 42
    context = MagicMock()

    with patch("app.telegram.handlers.callbacks.start_task_for_chat_id") as mock_start:
        mock_start.return_value = MagicMock(title="Essay")
        from app.telegram.handlers.callbacks import handle_callback
        await handle_callback(update, context)

    mock_start.assert_called_once_with(42, "task-123")
