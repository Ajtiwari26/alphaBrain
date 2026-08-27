"""Add next eligible timestamp for task retry backoff.

Revision ID: c8f9a1d2e603
Revises: b4c7d2e8f901
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op

revision = "c8f9a1d2e603"
down_revision = "b4c7d2e8f901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "next_eligible_at")
