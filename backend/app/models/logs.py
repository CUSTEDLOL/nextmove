import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Index, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ProductivityLog(Base):
    __tablename__ = "productivity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    scheduled_start = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    was_completed = Column(Boolean, nullable=True)
    procrastination_detected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    task = relationship("Task", back_populates="productivity_logs")


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    channel = Column(String, default="telegram")

    __table_args__ = (
        Index("ix_notification_log_user_type_sent", "user_id", "type", "sent_at"),
    )
