from datetime import datetime, timedelta
from app.services.scheduler import build_schedule, FreeSlot, TaskToSchedule


def make_slot(hour_start, hour_end, day_offset=0):
    base = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    base += timedelta(days=day_offset)
    return FreeSlot(start=base.replace(hour=hour_start), end=base.replace(hour=hour_end))


def test_high_effort_task_goes_to_morning():
    slots = [make_slot(9, 12), make_slot(14, 16), make_slot(20, 22)]
    tasks = [TaskToSchedule(id="1", title="Hard assignment", effort="high", priority_index=8.0)]
    result = build_schedule(tasks, slots)
    assert len(result) == 1
    assert result[0].start.hour == 9  # morning peak slot


def test_low_effort_task_avoids_morning():
    slots = [make_slot(9, 12), make_slot(20, 22)]
    tasks = [TaskToSchedule(id="1", title="Read chapter", effort="low", priority_index=3.0)]
    result = build_schedule(tasks, slots)
    assert len(result) == 1
    assert result[0].start.hour >= 14  # not the morning slot


def test_multiple_tasks_all_scheduled():
    slots = [make_slot(9, 12), make_slot(14, 16), make_slot(20, 22)]
    tasks = [
        TaskToSchedule(id="1", title="Exam prep", effort="high", priority_index=9.0),
        TaskToSchedule(id="2", title="Review notes", effort="low", priority_index=3.0),
    ]
    result = build_schedule(tasks, slots)
    assert len(result) == 2
    scheduled_ids = [r.task_id for r in result]
    assert "1" in scheduled_ids
    assert "2" in scheduled_ids


def test_no_double_booking():
    slots = [make_slot(9, 10)]  # only 1 hour free
    tasks = [
        TaskToSchedule(id="1", title="Task A", effort="medium", priority_index=7.0, estimated_hours=1),
        TaskToSchedule(id="2", title="Task B", effort="medium", priority_index=6.0, estimated_hours=1),
    ]
    result = build_schedule(tasks, slots)
    assert len(result) == 1  # only one fits in the single slot


def test_idempotent_same_output():
    slots = [make_slot(9, 12), make_slot(14, 16)]
    tasks = [
        TaskToSchedule(id="1", title="Task A", effort="high", priority_index=8.0),
        TaskToSchedule(id="2", title="Task B", effort="low", priority_index=3.0),
    ]
    result1 = build_schedule(tasks, slots)
    result2 = build_schedule(tasks, slots)
    assert [(r.task_id, r.start) for r in result1] == [(r.task_id, r.start) for r in result2]
