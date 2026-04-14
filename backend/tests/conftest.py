"""
Shared test configuration. Each test module that needs its own user
should use the `set_overrides` helper to scope dependency overrides.
"""
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Task, CalendarEvent  # noqa: F401 — registers all tables

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://nextmove:nextmove@localhost:5432/nextmove"),
)
engine = create_engine(TEST_DB_URL)
TestingSessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_test_migrations():
    """Ensure the shared Postgres test DB is at the current Alembic head."""
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DB_URL
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        if original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_database_url


@pytest.fixture(scope="session", autouse=True)
def apply_test_migrations():
    run_test_migrations()


def make_test_db():
    db = TestingSessionFactory()
    try:
        yield db
    finally:
        db.close()
