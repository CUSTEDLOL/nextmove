from datetime import datetime, timedelta
from app.services.matrix_scorer import score_task, TaskInput


def test_urgent_important_task_scores_high():
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(hours=12),
        effort="high",
        importance=5,
        dependency_count=2
    )
    score = score_task(task)
    assert score > 7.0


def test_low_priority_task_scores_low():
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(days=30),
        effort="low",
        importance=1,
        dependency_count=0
    )
    score = score_task(task)
    assert score < 3.5


def test_overdue_task_scores_max_urgency():
    task = TaskInput(
        deadline=datetime.utcnow() - timedelta(hours=1),  # past deadline
        effort="medium",
        importance=3,
        dependency_count=0
    )
    score = score_task(task)
    # Urgency = 10 (overdue), so score should be high
    assert score >= 6.0


def test_no_deadline_gets_default_urgency():
    task = TaskInput(
        deadline=None,
        effort="medium",
        importance=3,
        dependency_count=0
    )
    score = score_task(task)
    assert 0.0 <= score <= 10.0


def test_score_is_bounded():
    task = TaskInput(
        deadline=datetime.utcnow() + timedelta(hours=1),
        effort="high",
        importance=5,
        dependency_count=10
    )
    score = score_task(task)
    assert 0.0 <= score <= 10.0
