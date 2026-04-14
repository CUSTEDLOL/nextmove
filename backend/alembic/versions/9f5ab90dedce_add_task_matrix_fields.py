"""add task matrix fields

Revision ID: 9f5ab90dedce
Revises: 61ddd59d9179
Create Date: 2026-04-04 04:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f5ab90dedce"
down_revision: Union[str, None] = "61ddd59d9179"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("urgency_score", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("importance_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "importance_score")
    op.drop_column("tasks", "urgency_score")
    op.drop_column("tasks", "notes")
