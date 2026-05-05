from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

EFFORT_MAP = {"low": 2, "medium": 5, "high": 9}


class TaskInput(BaseModel):
    deadline: Optional[datetime]
    effort: str = "medium"
    importance: int = 3      # 1-5
    dependency_count: int = 0


def _urgency_score(deadline: Optional[datetime]) -> float:
    """0-10 scale. Higher = more urgent. Overdue = 10."""
    if deadline is None:
        return 3.0
    hours_remaining = (deadline - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 3600
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
    """Maps 1-5 → 0-10 scale."""
    return (importance - 1) / 4 * 10


def _effort_score(effort: str) -> float:
    """High effort tasks get higher score so they're not buried. 0-10 scale."""
    return float(EFFORT_MAP.get(effort, 5))


def _dependency_score(count: int) -> float:
    """Tasks blocking other tasks get priority. 0-10 scale."""
    return min(count * 2.5, 10.0)


def urgency_score(deadline: Optional[datetime]) -> float:
    """Returns urgency on a 0-10 scale."""
    return round(_urgency_score(deadline), 2)


def importance_score(importance: int) -> float:
    """Returns importance on a 0-10 scale."""
    return round(_importance_score(importance), 2)


# NOTE: normalized_*_score functions return 0-10 (same scale as the raw scores).
# The "normalized" prefix is kept for API compatibility but no longer means ×10.
def normalized_urgency_score(deadline: Optional[datetime]) -> float:
    """Returns urgency on a 0-10 scale (identical to urgency_score; kept for compatibility)."""
    return urgency_score(deadline)


def normalized_importance_score(importance: int) -> float:
    """Returns importance on a 0-10 scale (identical to importance_score; kept for compatibility)."""
    return importance_score(importance)


def score_task_from_matrix(
    urgency_score_value: float,
    importance_score_value: float,
    effort: str = "medium",
    dependency_count: int = 0,
) -> float:
    """
    Priority index formula: P = 0.35×U + 0.30×I + 0.20×E + 0.15×D
    All inputs (U, I, E, D) are expected on a 0-10 scale.
    Output is a 0-10 priority index.
    """
    U = urgency_score_value        # 0-10
    I = importance_score_value     # 0-10
    E = _effort_score(effort)      # 0-10
    D = _dependency_score(dependency_count)  # 0-10
    return round(0.35 * U + 0.30 * I + 0.20 * E + 0.15 * D, 2)


def score_task(task: TaskInput) -> float:
    return score_task_from_matrix(
        normalized_urgency_score(task.deadline),
        normalized_importance_score(task.importance),
        effort=task.effort,
        dependency_count=task.dependency_count,
    )
