import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from openai import AsyncOpenAI
from app.config import settings

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


class ParsedTask(BaseModel):
    title: str
    deadline: Optional[str] = None      # ISO date string or None
    effort: str = "medium"              # 'low', 'medium', 'high'
    importance: int = 3                 # 1-5
    context: str = "Study"             # 'Study', 'Admin', 'Personal', 'Other'
    dependencies: list[str] = []        # titles of tasks this depends on


SYSTEM_PROMPT = """You are a task extraction assistant for a student productivity app.
Extract all tasks from the user's text. Return valid JSON only.

Rules:
- effort: 'low' (reading, review), 'medium' (problem sets, labs), 'high' (assignments, projects, exams)
- importance: 1 (nice to do) to 5 (critical / graded)
- context: 'Study', 'Admin', 'Personal', 'Other'
- deadline: ISO 8601 date string (YYYY-MM-DD) or null if not mentioned
- Interpret relative dates ('tonight', 'Friday', 'next week') using today's date provided

Return format:
{"tasks": [{"title": "...", "deadline": "YYYY-MM-DD or null", "effort": "low|medium|high", "importance": 1-5, "context": "...", "dependencies": []}]}"""


async def parse_brain_dump(text: str, user_timezone: str = "UTC") -> list[ParsedTask]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    user_message = f"Today's date: {today}. Timezone: {user_timezone}.\n\nUser text: {text}"

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    return [ParsedTask(**t) for t in data.get("tasks", [])]
