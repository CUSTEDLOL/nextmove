import json
from datetime import datetime
from openai import AsyncOpenAI
from app.config import settings

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def parse_edit_instruction(text: str) -> dict | None:
    """
    Parse a natural-language edit instruction into a structured dict.
    Returns one of:
      {"field": "deadline", "value": "YYYY-MM-DD"}
      {"field": "title", "value": "New title"}
      {"field": "delete"}
    Returns None if the instruction can't be parsed.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Today is {today}. Parse a task edit instruction into JSON.\n"
                    "Return exactly one of these JSON shapes (no markdown, no extra text):\n"
                    '  {"field":"deadline","value":"YYYY-MM-DD"}  — if changing deadline\n'
                    '  {"field":"title","value":"new title"}       — if renaming\n'
                    '  {"field":"delete"}                          — if deleting\n'
                    "If unsure, return null."
                ),
            },
            {"role": "user", "content": text},
        ],
        max_tokens=60,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
        if result is None:
            return None
        if result.get("field") not in ("deadline", "title", "delete"):
            return None
        return result
    except (json.JSONDecodeError, AttributeError):
        return None
