from datetime import datetime
from typing import Optional
from pydantic import BaseModel

EFFORT_MAP = {"low": 2, "medium": 5, "high": 9}


class TaskInput(BaseModel):
    deadline: Optional[datetime]
    effort: str = "medium"
    importance: int = 3      # 1-5
    dependency_count: int = 0


def _urgency_score(deadline: Optional[datetime]) -> float:
    """0-10. Higher = more urgent. Overdue = 10."""
    if deadline is None:
        return 3.0
    hours_remaining = (deadline - datetime.utcnow()).total_seconds() / 3600
    if hours_remaining <= 0:
        return 10.0
    elif hours_remaining <= 24:
        return 9.0
    elif hours_remaining <= 48:
        return 7.5
    elif hours_remaining <= 72:
        return 6.0
    elif hours_remaining <= 168:   # 1 week
        return 4.0
    elif hours_remaining <= 336:   # 2 weeks
        return 2.0
    else:
        return 1.0


def _importance_score(importance: int) -> float:
    """Maps 1-5 → 0-10."""
    return (importance - 1) / 4 * 10


def _effort_score(effort: str) -> float:
    """High effort tasks get higher score so they're not buried."""
    return float(EFFORT_MAP.get(effort, 5))


def _dependency_score(count: int) -> float:
    """Tasks blocking other tasks get priority."""
    return min(count * 2.5, 10.0)


def score_task(task: TaskInput) -> float:
    U = _urgency_score(task.deadline)
    I = _importance_score(task.importance)
    E = _effort_score(task.effort)
    D = _dependency_score(task.dependency_count)
    return round(0.35 * U + 0.30 * I + 0.20 * E + 0.15 * D, 2)
