"""
Unit tests for services/task_service.py
No database required — all DB calls are mocked.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from app.services import task_service
from app.models.task import Task


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "user-1"
    user.timezone = "UTC"
    user.study_start_hour = 9
    user.study_end_hour = 22
    return user


@pytest.fixture
def mock_task():
    task = MagicMock(spec=Task)
    task.id = "task-1"
    task.title = "Write essay"
    task.deadline = datetime.utcnow() + timedelta(days=2)
    task.effort = "high"
    task.importance = 4
    task.priority_index = None
    task.parent_task_id = None
    task.status = "pending"
    return task


def test_apply_task_scores_sets_priority_index(mock_task):
    task_service.apply_task_scores(mock_task, recompute=True)
    assert mock_task.priority_index is not None
    assert isinstance(mock_task.priority_index, float)


def test_apply_task_scores_skips_when_already_set(mock_task):
    mock_task.priority_index = 5.5
    task_service.apply_task_scores(mock_task, recompute=False)
    assert mock_task.priority_index == 5.5


def test_generate_why_overdue():
    task = MagicMock(spec=Task)
    task.title = "Lab report"
    task.deadline = datetime.utcnow() - timedelta(days=2)
    task.importance = 3
    task.effort = "medium"
    result = task_service.generate_why(task)
    assert "overdue" in result
    assert "Lab report" in result


def test_generate_why_due_today():
    task = MagicMock(spec=Task)
    task.title = "Exam prep"
    task.deadline = datetime.utcnow() + timedelta(hours=3)
    task.importance = 5
    task.effort = "high"
    result = task_service.generate_why(task)
    assert "due today" in result
    assert "critically important" in result


def test_generate_why_no_deadline():
    task = MagicMock(spec=Task)
    task.title = "Old chore"
    task.deadline = None
    task.importance = 2
    task.effort = "low"
    result = task_service.generate_why(task)
    assert "Old chore" in result
    assert "no deadline" in result
