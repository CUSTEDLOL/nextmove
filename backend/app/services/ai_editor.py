import json
from datetime import datetime, timezone
from app.services.openai_client import get_openai_client as _get_openai_client


async def parse_edit_instruction(text: str) -> dict | None:
    """
    Parse a natural-language edit instruction into a structured dict.
    Returns one of:
      {"field": "deadline", "value": "YYYY-MM-DD"}
      {"field": "title", "value": "New title"}
      {"field": "delete"}
    Returns None if the instruction can't be parsed.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
        field = result.get("field")
        if field not in ("deadline", "title", "delete"):
            return None
        if field == "deadline":
            try:
                datetime.fromisoformat(result.get("value", ""))
            except (ValueError, TypeError):
                return None
        return result
    except (json.JSONDecodeError, AttributeError):
        return None
