import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ai_parser import parse_brain_dump, ParsedTask


def _mock_openai_response(data: dict):
    msg = MagicMock()
    msg.content = json.dumps(data)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_parse_single_task():
    mock_response = {
        "tasks": [
            {"title": "Finish ML assignment", "deadline": "2026-03-20",
             "effort": "high", "importance": 4, "context": "Study", "dependencies": []}
        ]
    }
    with patch("app.services.ai_parser.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(mock_response)
        )
        result = await parse_brain_dump("Finish ML assignment by Friday", user_timezone="UTC")

    assert len(result) == 1
    assert result[0].title == "Finish ML assignment"
    assert result[0].effort == "high"
    assert result[0].importance == 4


@pytest.mark.asyncio
async def test_parse_multiple_tasks():
    mock_response = {
        "tasks": [
            {"title": "Finish ML assignment", "deadline": "2026-03-20",
             "effort": "high", "importance": 4, "context": "Study", "dependencies": []},
            {"title": "Review lecture notes", "deadline": "2026-03-18",
             "effort": "low", "importance": 2, "context": "Study", "dependencies": []}
        ]
    }
    with patch("app.services.ai_parser.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(mock_response)
        )
        result = await parse_brain_dump(
            "Finish ML assignment by Friday and review lecture notes tonight",
            user_timezone="UTC"
        )

    assert len(result) == 2
    titles = [t.title for t in result]
    assert "Finish ML assignment" in titles
    assert "Review lecture notes" in titles


@pytest.mark.asyncio
async def test_parse_task_no_deadline():
    mock_response = {
        "tasks": [
            {"title": "Clean up notes", "deadline": None,
             "effort": "low", "importance": 1, "context": "Study", "dependencies": []}
        ]
    }
    with patch("app.services.ai_parser.openai_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(mock_response)
        )
        result = await parse_brain_dump("Clean up notes sometime", user_timezone="UTC")

    assert result[0].deadline is None
