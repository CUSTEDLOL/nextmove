"""
Shared test configuration. Each test module that needs its own user
should use the `set_overrides` helper to scope dependency overrides.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Task, CalendarEvent  # noqa: F401 — registers all tables

TEST_DB_URL = "postgresql://nextmove:nextmove@localhost:5433/nextmove"
engine = create_engine(TEST_DB_URL)
TestingSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_test_db():
    db = TestingSessionFactory()
    try:
        yield db
    finally:
        db.close()
