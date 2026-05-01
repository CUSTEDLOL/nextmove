from telegram.helpers import escape_markdown


def esc(text: str) -> str:
    """Escape text for MarkdownV2 Telegram messages."""
    return escape_markdown(str(text), version=2)
