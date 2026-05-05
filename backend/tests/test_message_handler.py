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


# ---------------------------------------------------------------------------
# C-3 — Email-link verification code flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_email_sends_code_does_not_link_directly():
    """Sending an email must generate a code and NOT immediately link the account."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("student@uni.edu", chat_id=55501)
    ctx = _make_context()

    store_mock = MagicMock(return_value="123456")
    fake_user = MagicMock()
    fake_user.telegram_chat_id = None

    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None), \
         patch("app.telegram.link_service.store_link_code", store_mock), \
         patch("app.telegram.link_service.send_link_email", MagicMock()), \
         patch("app.telegram.handlers.message.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user
        await handle_message(update, ctx)

    # Code must have been stored — account not linked yet
    store_mock.assert_called_once_with("student@uni.edu", 55501)
    reply = update.effective_message.reply_text.call_args[0][0]
    # Reply must mention a code was sent — NOT a "you're all set" confirmation
    assert "code" in reply.lower() or "email" in reply.lower()
    assert "linked" not in reply.lower()


@pytest.mark.asyncio
async def test_valid_code_links_account_and_confirms():
    """A correct 6-digit code links the Telegram chat to the account."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("123456", chat_id=55501)
    ctx = _make_context()

    fake_user = MagicMock()
    fake_user.name = "Alice"
    fake_user.telegram_chat_id = None

    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None), \
         patch("app.telegram.link_service.verify_and_consume_link_code",
               return_value="student@uni.edu") as verify_mock, \
         patch("app.telegram.handlers.message.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_db.query.return_value.filter.return_value.first.return_value = fake_user
        await handle_message(update, ctx)

    verify_mock.assert_called_once_with("123456", 55501)
    assert fake_user.telegram_chat_id == 55501
    mock_db.commit.assert_called_once()
    first_reply = update.effective_message.reply_text.call_args_list[0][0][0]
    assert "linked" in first_reply.lower() or "set" in first_reply.lower()


@pytest.mark.asyncio
async def test_expired_or_wrong_code_shows_error():
    """An invalid or expired 6-digit code shows a clear error — account not touched."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("999999", chat_id=55501)
    ctx = _make_context()

    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None), \
         patch("app.telegram.link_service.verify_and_consume_link_code", return_value=None):
        await handle_message(update, ctx)

    reply = update.effective_message.reply_text.call_args[0][0]
    assert any(w in reply.lower() for w in ("expired", "invalid", "code", "try again"))


@pytest.mark.asyncio
async def test_email_link_same_reply_for_unknown_email():
    """Unknown email gets the same reply as a known email — prevents enumeration."""
    from app.telegram.handlers.message import _handle_email_link

    replies = []
    for user_exists in (True, False):
        update = _make_update("anyone@example.com", chat_id=55501)
        fake_user = MagicMock() if user_exists else None

        with patch("app.telegram.link_service.store_link_code", return_value="111111"), \
             patch("app.telegram.link_service.send_link_email", MagicMock()), \
             patch("app.telegram.handlers.message.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = fake_user
            await _handle_email_link(update, "anyone@example.com", 55501)

        replies.append(update.effective_message.reply_text.call_args[0][0])

    assert replies[0] == replies[1], "Reply must be identical for known and unknown email"


@pytest.mark.asyncio
async def test_six_digit_code_checked_before_email_classification():
    """A 6-digit message from an unlinked user goes to code verification, not email flow."""
    from app.telegram.handlers.message import handle_message
    update = _make_update("654321", chat_id=55501)
    ctx = _make_context()

    handle_code_mock = AsyncMock()

    with patch("app.telegram.handlers.message._get_user_by_chat_id", return_value=None), \
         patch("app.telegram.handlers.message._handle_link_code", handle_code_mock):
        await handle_message(update, ctx)

    handle_code_mock.assert_called_once_with(update, "654321", 55501)
