import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Task


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_user(db):
    user = User(email="test@uni.edu", name="Alice", timezone="UTC")
    db.add(user)
    db.commit()
    assert user.id is not None
    assert user.email == "test@uni.edu"


def test_create_task(db):
    user = User(email="test@uni.edu", name="Alice", timezone="UTC")
    db.add(user)
    db.commit()
    task = Task(
        user_id=user.id,
        title="Finish ML assignment",
        effort="high",
        importance=4,
        status="pending"
    )
    db.add(task)
    db.commit()
    assert task.id is not None
    assert task.priority_index is None  # not yet scored


def test_task_status_values(db):
    user = User(email="test2@uni.edu", name="Bob", timezone="UTC")
    db.add(user)
    db.commit()
    for status in ["pending", "scheduled", "in_progress", "completed", "missed", "rescheduled"]:
        task = Task(
            user_id=user.id,
            title=f"Task {status}",
            effort="low",
            importance=1,
            status=status
        )
        db.add(task)
    db.commit()
    assert db.query(Task).filter_by(user_id=user.id).count() == 6
