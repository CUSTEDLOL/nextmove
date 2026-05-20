"""tighten notification_log schema

Revision ID: a3f7e1c8b204
Revises: 9f5ab90dedce
Create Date: 2026-04-19 00:00:00.000000

- Make notification_log.user_id NOT NULL
- Make notification_log.type NOT NULL
- Add composite index on (user_id, type, sent_at) for the daily dedup query
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f7e1c8b204"
down_revision: Union[str, None] = "9f5ab90dedce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove any orphaned rows that would violate the new NOT NULL constraints.
    op.execute(
        "DELETE FROM notification_log WHERE user_id IS NULL OR type IS NULL"
    )

    op.alter_column(
        "notification_log", "user_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "notification_log", "type",
        existing_type=sa.String(),
        nullable=False,
    )
    op.create_index(
        "ix_notification_log_user_type_sent",
        "notification_log",
        ["user_id", "type", "sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_log_user_type_sent", table_name="notification_log")
    op.alter_column(
        "notification_log", "type",
        existing_type=sa.String(),
        nullable=True,
    )
    op.alter_column(
        "notification_log", "user_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
