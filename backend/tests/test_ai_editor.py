import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_parse_deadline_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"deadline","value":"2026-04-04"}'))
        result = await parse_edit_instruction("deadline is this Friday")
    assert result["field"] == "deadline"

@pytest.mark.asyncio
async def test_parse_title_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"title","value":"Study for finals"}'))
        result = await parse_edit_instruction("rename it to Study for finals")
    assert result["field"] == "title"
    assert result["value"] == "Study for finals"

@pytest.mark.asyncio
async def test_parse_delete_edit():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response('{"field":"delete"}'))
        result = await parse_edit_instruction("delete this")
    assert result["field"] == "delete"

@pytest.mark.asyncio
async def test_parse_invalid_returns_none():
    from app.services.ai_editor import parse_edit_instruction
    with patch("app.services.ai_editor._get_openai_client") as mock:
        mock.return_value.chat.completions.create = AsyncMock(return_value=_mock_response("not json"))
        result = await parse_edit_instruction("hello there")
    assert result is None

def _mock_response(content: str):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.choices[0].message.content = content
    return r
