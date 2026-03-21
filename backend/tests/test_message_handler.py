import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(text, chat_id=12345):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_message.reply_text = AsyncMock()
    update.message = update.effective_message
    update.message.text = text
    update.callback_query = None
    return update


def _make_context():
    return MagicMock()


@pytest.mark.asyncio
async def test_unknown_user_prompted_for_email():
    """Unknown user gets onboarding prompt."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("hello", chat_id=99999999)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None):
        await handle_message(update, ctx)
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "email" in call_args.lower() or "link" in call_args.lower() or "register" in call_args.lower()


@pytest.mark.asyncio
async def test_email_message_triggers_link():
    """A message that looks like an email triggers account linking."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("test@example.com", chat_id=99999999)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None), \
         patch("app.telegram.handlers.message._handle_email_link", AsyncMock()) as link_mock:
        await handle_message(update, ctx)
    link_mock.assert_called_once()


@pytest.mark.asyncio
async def test_today_intent_calls_today():
    """Today intent delegates to today_command."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("what should I do today", chat_id=12345)
    ctx = _make_context()
    fake_user = MagicMock()
    today_mock = AsyncMock()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=fake_user), \
         patch("app.telegram.db_helpers.get_pending_steps_task_id", AsyncMock(return_value=None)), \
         patch("app.telegram.intent.classify_intent", AsyncMock(return_value="today")), \
         patch("app.telegram.handlers.today.today_command", today_mock):
        await handle_message(update, ctx)
    today_mock.assert_called_once()


@pytest.mark.asyncio
async def test_unclear_intent_sends_nudge():
    """Unclear intent sends a helpful nudge."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("haha", chat_id=12345)
    ctx = _make_context()
    fake_user = MagicMock()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=fake_user), \
         patch("app.telegram.db_helpers.get_pending_steps_task_id", AsyncMock(return_value=None)), \
         patch("app.telegram.intent.classify_intent", AsyncMock(return_value="unclear")):
        await handle_message(update, ctx)
    update.effective_message.reply_text.assert_called_once()
    reply = update.effective_message.reply_text.call_args[0][0]
    assert len(reply) > 10  # some meaningful response
