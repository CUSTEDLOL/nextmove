"""
Runs after brain dump or manual trigger.
Pipeline: pending tasks → free slots → scheduler → ScheduleBlock rows saved.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import User, Task, ScheduleBlock
from app.services.scheduler import build_schedule, FreeSlot, TaskToSchedule
from app.services.calendar_builtin import get_builtin_free_slots

ACTIVE_SCHEDULE_STATUSES = ["pending", "scheduled", "in_progress"]


def _get_free_slots(user: User, date: datetime, db: Session, study_start: int = 9, study_end: int = 22) -> list[FreeSlot]:
    tz_str = user.timezone or "UTC"
    if user.uses_google_calendar and user.google_access_token:
        try:
            from app.services.calendar_google import get_google_service, get_free_slots as gcal_free
            service = get_google_service(user.google_access_token, user.google_refresh_token)
            slots = gcal_free(service, "primary", date, study_start, study_end)
            return [FreeSlot(start=s.start, end=s.end) for s in slots]
        except Exception:
            pass  # Fall through to built-in calendar on any Google error

    return get_builtin_free_slots(user.id, date, study_start, study_end, db, tz_str=tz_str)


def get_free_slots_for_user(user: User, db: Session, date: datetime = None) -> list[FreeSlot]:
    if date is None:
        date = datetime.utcnow()
    study_start = user.study_start_hour or 9
    study_end = user.study_end_hour or 22
    return _get_free_slots(user, date, db, study_start, study_end)


def run_schedule_for_user(user: User, db: Session, date: datetime = None) -> list[ScheduleBlock]:
    """
    Assign all pending/rescheduled tasks to calendar slots.
    Clears existing future blocks first (idempotent).
    Returns the new schedule blocks created.
    """
    if date is None:
        date = datetime.utcnow()

    today_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    db.query(ScheduleBlock).filter(
        ScheduleBlock.user_id == user.id,
        ScheduleBlock.start_time >= today_start
    ).delete(synchronize_session=False)

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.parent_task_id.is_(None),
            Task.status.in_(ACTIVE_SCHEDULE_STATUSES),
        )
        .order_by(Task.priority_index.desc())
        .all()
    )
    if not tasks:
        db.commit()
        return []

    study_start = user.study_start_hour or 9
    study_end = user.study_end_hour or 22
    free_slots = _get_free_slots(user, date, db, study_start, study_end)
    tasks_to_schedule = [
        TaskToSchedule(
            id=str(t.id),
            title=t.title,
            effort=t.effort or "medium",
            priority_index=t.priority_index or 5.0,
        )
        for t in tasks
    ]

    scheduled_blocks = build_schedule(tasks_to_schedule, free_slots, study_start, study_end)

    task_map = {str(t.id): t for t in tasks}
    created = []
    for block in scheduled_blocks:
        task = task_map.get(block.task_id)
        if not task:
            continue
        sb = ScheduleBlock(
            task_id=task.id,
            user_id=user.id,
            start_time=block.start,
            end_time=block.end,
        )
        db.add(sb)
        task.status = "scheduled"
        created.append(sb)

    db.commit()
    return created
