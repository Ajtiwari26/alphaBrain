"""Persist worker identity on each task attempt.

Revision ID: b4c7d2e8f901
Revises: a39338425c61
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c7d2e8f901"
down_revision = "a39338425c61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_attempts", sa.Column("worker_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("task_attempts", "worker_id")
