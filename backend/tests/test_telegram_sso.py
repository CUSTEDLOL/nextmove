import pytest
from unittest.mock import MagicMock, patch


def _make_redis(data: dict):
    """Return a mock Redis that acts on a plain dict."""
    r = MagicMock()
    r.setex = lambda key, ttl, val: data.update({key: val})
    r.getdel = lambda key: data.pop(key, None)
    return r


def test_store_web_link_token_returns_token_and_writes_redis():
    store = {}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import store_web_link_token
        token = store_web_link_token("user-uuid-123")
    assert len(token) > 20
    assert f"tgauth:{token}" in store
    assert store[f"tgauth:{token}"] == "user-uuid-123"


def test_consume_web_link_token_returns_user_id_and_deletes_key():
    token = "abc123token"
    store = {f"tgauth:{token}": "user-uuid-456"}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import consume_web_link_token
        result = consume_web_link_token(token)
    assert result == "user-uuid-456"
    assert f"tgauth:{token}" not in store


def test_consume_web_link_token_returns_none_for_missing_token():
    store = {}
    with patch("app.telegram.link_service._get_redis", return_value=_make_redis(store)):
        from app.telegram.link_service import consume_web_link_token
        result = consume_web_link_token("no-such-token")
    assert result is None
