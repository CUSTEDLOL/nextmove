"""
Web → Telegram SSO token service.

Flow:
  1. Logged-in web user hits POST /api/telegram/link-token
     → store_web_link_token() generates a URL-safe token, stores it in
       Redis for 10 minutes keyed to the user's UUID, and returns it.
  2. User opens t.me/Bot?start=<token> and taps Start.
     → consume_web_link_token() validates the token, deletes it, and
       returns the user_id so the bot handler can write telegram_chat_id.
"""
import logging
import secrets

import redis as redis_lib

from app.config import settings

logger = logging.getLogger(__name__)

_TOKEN_TTL = 600  # 10 minutes
_PREFIX = "tgauth:"


def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.redis_url, decode_responses=True)


def store_web_link_token(user_id: str) -> str:
    """Mint a one-time SSO token tied to user_id. Returns the token."""
    token = secrets.token_urlsafe(32)
    _get_redis().setex(f"{_PREFIX}{token}", _TOKEN_TTL, user_id)
    return token


def consume_web_link_token(token: str, chat_id: int) -> str | None:
    """
    Exchange a web SSO token for the linked user_id.
    Deletes the token on success (one-time use).
    Returns None if the token is missing or expired.
    chat_id is accepted but not validated here — the caller writes it.
    """
    r = _get_redis()
    user_id = r.get(f"{_PREFIX}{token}")
    if not user_id:
        return None
    r.delete(f"{_PREFIX}{token}")
    return user_id
