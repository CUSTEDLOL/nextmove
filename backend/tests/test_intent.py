import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_classifies_today_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("what should I do today", has_pending_steps=False) == "today"
    assert await classify_intent("what's my priority", has_pending_steps=False) == "today"
    assert await classify_intent("show me my schedule", has_pending_steps=False) == "today"

@pytest.mark.asyncio
async def test_classifies_complete_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("I'm done", has_pending_steps=False) == "complete"
    assert await classify_intent("just submitted my report", has_pending_steps=False) == "complete"
    assert await classify_intent("finished the lab", has_pending_steps=False) == "complete"

@pytest.mark.asyncio
async def test_classifies_skip_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("skip this", has_pending_steps=False) == "skip"
    assert await classify_intent("not doing that today", has_pending_steps=False) == "skip"
    assert await classify_intent("postpone the meeting", has_pending_steps=False) == "skip"

@pytest.mark.asyncio
async def test_classifies_list_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("show all my tasks", has_pending_steps=False) == "list"
    assert await classify_intent("list everything", has_pending_steps=False) == "list"

@pytest.mark.asyncio
async def test_steps_reply_takes_priority():
    from app.telegram.intent import classify_intent
    assert await classify_intent("prepare slides, rehearse notes", has_pending_steps=True) == "steps_reply"

@pytest.mark.asyncio
async def test_classifies_add_task_keywords():
    from app.telegram.intent import classify_intent
    assert await classify_intent("add essay due Friday", has_pending_steps=False) == "add_task"
    assert await classify_intent("remind me about lab report on Monday", has_pending_steps=False) == "add_task"
    assert await classify_intent("track my project proposal", has_pending_steps=False) == "add_task"
    assert await classify_intent("new task: finish homework", has_pending_steps=False) == "add_task"

@pytest.mark.asyncio
async def test_gpt_fallback_dump(monkeypatch):
    from app.telegram import intent as intent_mod
    monkeypatch.setattr(intent_mod, "_gpt_classify", AsyncMock(return_value="dump"))
    from app.telegram.intent import classify_intent
    result = await classify_intent("I have a meeting Friday and an exam on Monday at 9am", has_pending_steps=False)
    assert result == "dump"

@pytest.mark.asyncio
async def test_gpt_fallback_unclear(monkeypatch):
    from app.telegram import intent as intent_mod
    monkeypatch.setattr(intent_mod, "_gpt_classify", AsyncMock(return_value="unclear"))
    from app.telegram.intent import classify_intent
    result = await classify_intent("haha nice", has_pending_steps=False)
    assert result == "unclear"

@pytest.mark.asyncio
async def test_steps_reply_overrides_keyword_match():
    from app.telegram.intent import classify_intent
    # "done" would normally match _COMPLETE, but has_pending_steps=True overrides it
    assert await classify_intent("done", has_pending_steps=True) == "steps_reply"
    # "today" would normally match _TODAY
    assert await classify_intent("what should I do today", has_pending_steps=True) == "steps_reply"
