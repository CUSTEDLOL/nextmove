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


def test_user_has_pending_steps_task_id(db):
    user = User(email="test@uni.edu", name="Alice", timezone="UTC")
    db.add(user)
    db.commit()
    # Should not raise AttributeError
    assert hasattr(user, "pending_steps_task_id")
    assert user.pending_steps_task_id is None


def test_user_pending_steps_task_id_can_be_set(db):
    user = User(email="student@uni.edu", name="Bob", timezone="UTC")
    db.add(user)
    db.commit()

    task = Task(
        user_id=user.id,
        title="Write essay",
        effort="high",
        importance=8,
        status="pending",
    )
    db.add(task)
    db.commit()

    user.pending_steps_task_id = task.id
    db.commit()
    db.refresh(user)
    assert user.pending_steps_task_id == task.id
