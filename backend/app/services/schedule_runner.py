"""
Runs after brain dump or manual trigger.
Pipeline: pending tasks → free slots → scheduler → ScheduleBlock rows saved.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import User, Task, ScheduleBlock
from app.services.scheduler import build_schedule, FreeSlot, TaskToSchedule
from app.services.calendar_builtin import get_builtin_free_slots

logger = logging.getLogger(__name__)

ACTIVE_SCHEDULE_STATUSES = ["pending", "scheduled", "in_progress", "rescheduled"]


def _get_free_slots(user: User, date: datetime, db: Session, study_start: int = 9, study_end: int = 22) -> list[FreeSlot]:
    tz_str = user.timezone or "UTC"
    if user.uses_google_calendar and user.google_access_token:
        try:
            from app.services.calendar_google import get_google_service, get_free_slots as gcal_free
            service = get_google_service(user.google_access_token, user.google_refresh_token)
            slots = gcal_free(service, "primary", date, study_start, study_end, tz_str=tz_str)
            return [FreeSlot(start=s.start, end=s.end) for s in slots]
        except Exception as exc:
            logger.warning("Google Calendar sync failed for user %s: %s", user.id, exc)
            # If the error is an auth failure (401), clear the Google Calendar flag so the
            # user is not repeatedly hitting an invalid token on every schedule run.
            exc_str = str(exc).lower()
            if "401" in exc_str or "unauthorized" in exc_str or "invalid_grant" in exc_str:
                user.uses_google_calendar = False
                user.google_access_token = None
                db.add(user)
                db.flush()
            # Fall through to built-in calendar on any Google error

    return get_builtin_free_slots(user.id, date, study_start, study_end, db, tz_str=tz_str)


def get_free_slots_for_user(user: User, db: Session, date: datetime = None) -> list[FreeSlot]:
    if date is None:
        date = datetime.now(timezone.utc).replace(tzinfo=None)
    study_start = user.study_start_hour or 9
    study_end = user.study_end_hour or 22
    return _get_free_slots(user, date, db, study_start, study_end)


def run_schedule_for_user(user: User, db: Session, date: datetime = None) -> list[ScheduleBlock]:
    """
    Assign all pending, scheduled, in_progress, and rescheduled tasks to calendar slots.
    Clears existing future blocks first (idempotent).
    Returns the new schedule blocks created.
    """
    if date is None:
        date = datetime.now(timezone.utc).replace(tzinfo=None)

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
