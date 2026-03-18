from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    recurrence_rule: Optional[str] = None


class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    source: str

    class Config:
        from_attributes = True
