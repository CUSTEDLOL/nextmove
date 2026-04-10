from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, ScheduleBlock, Task
from app.services.schedule_runner import get_free_slots_for_user, run_schedule_for_user

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class ScheduleEntry(BaseModel):
    id: str
    task_id: str
    task_title: str
    effort: str | None
    start_time: datetime
    end_time: datetime
    entry_type: str   # "block" | "deadline"


class FreeSlotEntry(BaseModel):
    start: datetime
    end: datetime


def _load_db_user(db: Session, user_id) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    return user if user else None


def _build_schedule_entries(db: Session, user: User) -> list[ScheduleEntry]:
    if user is None:
        return []

    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=31)
    result: list[ScheduleEntry] = []

    # 1. Scheduled work blocks — bulk-load tasks to avoid N+1 queries
    blocks = (
        db.query(ScheduleBlock)
        .filter(
            ScheduleBlock.user_id == user.id,
            ScheduleBlock.start_time >= start,
            ScheduleBlock.start_time < end,
        )
        .order_by(ScheduleBlock.start_time)
        .all()
    )
    task_ids = [b.task_id for b in blocks]
    tasks_map: dict = {}
    if task_ids:
        tasks_map = {
            t.id: t
            for t in db.query(Task).filter(Task.id.in_(task_ids)).all()
        }
    for b in blocks:
        task = tasks_map.get(b.task_id)
        result.append(ScheduleEntry(
            id=str(b.id),
            task_id=str(b.task_id),
            task_title=task.title if task else "Unknown",
            effort=task.effort if task else None,
            start_time=b.start_time,
            end_time=b.end_time,
            entry_type="block",
        ))

    # 2. Deadline events — tasks with a deadline, shown as a 30-min marker at deadline time
    deadline_tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.deadline.isnot(None),
            Task.deadline >= start,
            Task.deadline < end,
            Task.parent_task_id.is_(None),   # top-level only
        )
        .all()
    )
    for t in deadline_tasks:
        result.append(ScheduleEntry(
            id=f"deadline-{t.id}",
            task_id=str(t.id),
            task_title=f"Due: {t.title}",
            effort=t.effort,
            start_time=t.deadline,
            end_time=t.deadline + timedelta(minutes=30),
            entry_type="deadline",
        ))

    return sorted(result, key=lambda x: x.start_time)


@router.get("", response_model=list[ScheduleEntry])
def get_schedule(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _build_schedule_entries(db, _load_db_user(db, user.id))


@router.post("/rebuild", response_model=list[ScheduleEntry])
def rebuild_schedule(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = _load_db_user(db, user.id)
    if db_user is None:
        return []
    run_schedule_for_user(db_user, db)
    return _build_schedule_entries(db, db_user)


@router.get("/free-slots", response_model=list[FreeSlotEntry])
def get_free_slots(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = _load_db_user(db, user.id)
    if db_user is None:
        return []
    slots = get_free_slots_for_user(db_user, db)
    return [FreeSlotEntry(start=slot.start, end=slot.end) for slot in slots]
