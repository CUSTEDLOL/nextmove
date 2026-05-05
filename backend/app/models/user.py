import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
from app.services.crypto import EncryptedString


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    hashed_password = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
    google_access_token = Column(EncryptedString, nullable=True)
    google_refresh_token = Column(EncryptedString, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    pending_steps_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    pending_edit_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    uses_google_calendar = Column(Boolean, default=False)
    study_start_hour = Column(Integer, default=9)
    study_end_hour = Column(Integer, default=22)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    tasks = relationship("Task", back_populates="user", foreign_keys="Task.user_id")
    schedule_blocks = relationship("ScheduleBlock", back_populates="user")
    calendar_events = relationship("CalendarEvent", back_populates="user")
