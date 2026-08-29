"""add task_checkpoints schema

Revision ID: ea716532600e
Revises: 58b5b056d9e3
Create Date: 2026-08-29 12:01:59.758582

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea716532600e"
down_revision: str | Sequence[str] | None = "58b5b056d9e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "task_checkpoints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("repo_reference", sa.String(length=512), nullable=False),
        sa.Column("base_commit", sa.String(length=128), nullable=False),
        sa.Column("worktree_path", sa.String(length=512), nullable=False),
        sa.Column("worktree_head", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("execution_stage", sa.String(length=64), nullable=False),
        sa.Column("lease_token_hash", sa.String(length=64), nullable=False),
        sa.Column("side_effect_state", sa.String(length=32), nullable=False),
        sa.Column("scrubbed_payload", sa.JSON(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["task_attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("task_id", "attempt_number", "sequence", name="uq_task_attempt_seq"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("task_checkpoints")
