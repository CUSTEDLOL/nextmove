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
async def test_unknown_user_prompted_for_web_redirect():
    """Unknown user gets a redirect to the web app — not an email prompt."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("hello", chat_id=99999999)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None):
        await handle_message(update, ctx)
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "connect" in call_args.lower() or "web app" in call_args.lower() or "link" in call_args.lower()


@pytest.mark.asyncio
async def test_unknown_user_email_message_shows_redirect():
    """An email-looking message from an unlinked user still shows the web redirect."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("test@example.com", chat_id=99999999)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None):
        await handle_message(update, ctx)
    call_args = update.effective_message.reply_text.call_args[0][0]
    # Must show redirect, never attempt account linking inline
    assert "connect" in call_args.lower() or "web app" in call_args.lower() or "link" in call_args.lower()
    # reply_text must have been called exactly once (redirect only, no follow-up)
    assert update.effective_message.reply_text.call_count == 1


@pytest.mark.asyncio
async def test_unknown_user_code_message_shows_redirect():
    """A 6-digit message from an unlinked user shows the web redirect, not code verification."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("654321", chat_id=55501)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None):
        await handle_message(update, ctx)
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "connect" in call_args.lower() or "web app" in call_args.lower() or "link" in call_args.lower()
    assert update.effective_message.reply_text.call_count == 1


@pytest.mark.asyncio
async def test_unknown_user_redirect_includes_inline_button():
    """The redirect reply must include an InlineKeyboardMarkup with the web app URL."""
    from app.telegram.handlers.message import handle_message
    from telegram import InlineKeyboardMarkup
    update = _make_update("anything", chat_id=77777)
    ctx = _make_context()
    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None):
        await handle_message(update, ctx)
    kwargs = update.effective_message.reply_text.call_args[1]
    assert "reply_markup" in kwargs
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    # The keyboard must contain a button whose URL ends with /settings
    button = markup.inline_keyboard[0][0]
    assert button.url.endswith("/settings")


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
