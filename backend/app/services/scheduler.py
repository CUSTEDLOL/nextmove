from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel

EFFORT_HOURS_DEFAULT = {"low": 1, "medium": 2, "high": 4}


class FreeSlot(BaseModel):
    start: datetime
    end: datetime

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600

    def is_peak(self) -> bool:
        """Morning 6am–noon: best for hard work."""
        return 6 <= self.start.hour < 12

    def is_mid(self) -> bool:
        """Afternoon noon–6pm: medium tasks."""
        return 12 <= self.start.hour < 18

    def is_evening(self) -> bool:
        """Evening 6pm+: light tasks."""
        return self.start.hour >= 18


class TaskToSchedule(BaseModel):
    id: str
    title: str
    effort: str           # 'low', 'medium', 'high'
    priority_index: float
    estimated_hours: Optional[float] = None

    @property
    def hours_needed(self) -> float:
        return self.estimated_hours or float(EFFORT_HOURS_DEFAULT.get(self.effort, 2))

    def prefers_slot(self, slot: FreeSlot) -> bool:
        if self.effort == "high":
            return slot.is_peak()
        elif self.effort == "medium":
            return slot.is_mid() or slot.is_peak()
        else:
            return slot.is_evening() or slot.is_mid()


class ScheduledBlock(BaseModel):
    task_id: str
    task_title: str
    start: datetime
    end: datetime


def build_schedule(
    tasks: list[TaskToSchedule],
    free_slots: list[FreeSlot],
    study_start: int = 9,
    study_end: int = 22,
) -> list[ScheduledBlock]:
    """
    Assign tasks to free slots respecting energy-effort matching.
    Higher priority tasks are placed first.
    Idempotent: same inputs always produce same output.
    """
    sorted_tasks = sorted(tasks, key=lambda t: t.priority_index, reverse=True)
    # Deep copy slots so original is unchanged (idempotency)
    remaining = [FreeSlot(start=s.start, end=s.end) for s in sorted(free_slots, key=lambda s: s.start)]
    result = []

    for task in sorted_tasks:
        block = _try_assign(task, remaining, prefer_match=True)
        if not block:
            block = _try_assign(task, remaining, prefer_match=False)
        if block:
            result.append(block)

    return result


def _try_assign(
    task: TaskToSchedule,
    slots: list[FreeSlot],
    prefer_match: bool,
) -> Optional[ScheduledBlock]:
    duration = timedelta(hours=task.hours_needed)
    for i, slot in enumerate(slots):
        if prefer_match and not task.prefers_slot(slot):
            continue
        if slot.duration_hours >= task.hours_needed:
            block_start = slot.start
            block_end = block_start + duration
            # Shrink or remove the consumed slot
            new_start = block_end
            if (slot.end - new_start).total_seconds() > 0:
                slots[i] = FreeSlot(start=new_start, end=slot.end)
            else:
                slots.pop(i)
            return ScheduledBlock(
                task_id=task.id,
                task_title=task.title,
                start=block_start,
                end=block_end
            )
    return None
