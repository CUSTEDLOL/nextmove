"""clear plaintext google tokens before encryption is enabled

Revision ID: b9c2d4e6f018
Revises: a3f7e1c8b204
Create Date: 2026-04-20 00:00:00.000000

Existing google_access_token / google_refresh_token values were stored as
plaintext. Now that EncryptedString is in place, those values cannot be
decrypted (they were never encrypted). This migration nullifies them so users
re-authorise Google Calendar — the next write will be encrypted correctly.

In production: run this migration, then have users reconnect Google Calendar.
"""
from typing import Sequence, Union
from alembic import op


revision: str = "b9c2d4e6f018"
down_revision: Union[str, None] = "a3f7e1c8b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET google_access_token = NULL, google_refresh_token = NULL, "
        "uses_google_calendar = FALSE "
        "WHERE google_access_token IS NOT NULL"
    )


def downgrade() -> None:
    # Cannot recover plaintext tokens — downgrade is a no-op.
    pass
