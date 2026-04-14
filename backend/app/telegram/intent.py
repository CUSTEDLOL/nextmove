from openai import AsyncOpenAI
from app.config import settings

_TODAY = ["today", "what should i", "my priority", "what's next", "what do i do", "schedule", "show me today", "what's on"]
_COMPLETE = ["done", "finished", "completed", "submitted", "wrapped up", "handed in", "sent it", "just did"]
_SKIP = ["skip", "push", "reschedule", "postpone", "not today", "not doing", "later", "delay"]
_LIST = ["list", "all tasks", "show tasks", "show me everything", "everything i have", "all my tasks"]
_ADD_TASK = ["add ", "remind me", "track ", "don't forget", "new task", "create task"]

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def classify_intent(text: str, has_pending_steps: bool) -> str:
    if has_pending_steps:
        return "steps_reply"

    lower = text.lower()

    if any(p in lower for p in _COMPLETE):
        return "complete"
    if any(p in lower for p in _SKIP):
        return "skip"
    if any(p in lower for p in _TODAY):
        return "today"
    if any(p in lower for p in _LIST):
        return "list"
    if any(p in lower for p in _ADD_TASK):
        return "add_task"

    return await _gpt_classify(text)


async def _gpt_classify(text: str) -> str:
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You classify student messages for a productivity bot. "
                    "Return exactly one word.\n"
                    "'dump' = message contains multiple tasks, deadlines, events, assignments, or commitments to track.\n"
                    "'add_task' = message asks to add or track a single specific task.\n"
                    "'unclear' = chit-chat, greetings, questions about something else, or random text."
                )
            },
            {"role": "user", "content": text}
        ],
        max_tokens=5,
        temperature=0,
    )
    result = response.choices[0].message.content.strip().lower()
    return result if result in ("dump", "add_task", "unclear") else "unclear"
