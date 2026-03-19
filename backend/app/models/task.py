import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    raw_input = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    effort = Column(String, nullable=True)       # 'low', 'medium', 'high'
    importance = Column(Integer, nullable=True)  # 1-5
    context = Column(String, nullable=True)      # 'Study', 'Admin', 'Personal'
    priority_index = Column(Float, nullable=True)
    status = Column(String, default="pending")
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    google_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tasks", foreign_keys=[user_id])
    schedule_blocks = relationship("ScheduleBlock", back_populates="task")
    subtasks = relationship("Task", backref="parent", remote_side="Task.id")
    productivity_logs = relationship("ProductivityLog", back_populates="task")
