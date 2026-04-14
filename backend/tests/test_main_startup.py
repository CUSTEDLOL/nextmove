from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import NetworkError


@pytest.mark.asyncio
async def test_initialize_telegram_bot_returns_app_when_available():
    from app.main import initialize_telegram_bot

    fake_bot = MagicMock()
    fake_bot.set_my_commands = AsyncMock()
    fake_app = MagicMock()
    fake_app.initialize = AsyncMock()
    fake_app.shutdown = AsyncMock()
    fake_app.bot = fake_bot

    with patch("app.telegram.bot.get_application", return_value=fake_app):
        result = await initialize_telegram_bot()

    assert result is fake_app
    fake_app.initialize.assert_awaited_once()
    fake_bot.set_my_commands.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_telegram_bot_returns_none_when_network_fails():
    from app.main import initialize_telegram_bot

    fake_bot = MagicMock()
    fake_bot.set_my_commands = AsyncMock()
    fake_app = MagicMock()
    fake_app.initialize = AsyncMock(side_effect=NetworkError("offline"))
    fake_app.shutdown = AsyncMock()
    fake_app.bot = fake_bot

    with patch("app.telegram.bot.get_application", return_value=fake_app):
        result = await initialize_telegram_bot()

    assert result is None
    fake_bot.set_my_commands.assert_not_called()
