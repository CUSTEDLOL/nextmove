from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import datetime
import uuid


class CalendarConnectionResponse(BaseModel):
    uses_google_calendar: bool
    google_calendar_connected: bool


class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    recurrence_rule: Optional[str] = None

    @model_validator(mode="after")
    def end_must_be_after_start(self) -> "CalendarEventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    is_all_day: bool
    source: str

    class Config:
        from_attributes = True
