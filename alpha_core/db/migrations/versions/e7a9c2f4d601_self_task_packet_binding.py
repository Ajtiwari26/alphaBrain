"""self_task_packet_binding

Revision ID: e7a9c2f4d601
Revises: d5e8f1a2b304
Create Date: 2026-08-27 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a9c2f4d601"
down_revision = "d5e8f1a2b304"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add packet_sha256 to tasks
    op.add_column("tasks", sa.Column("packet_sha256", sa.String(length=64), nullable=True))

    # Add scope_sha256 to approvals
    op.add_column("approvals", sa.Column("scope_sha256", sa.String(length=64), nullable=True))

    # Add packet_sha256 to task_attempts
    op.add_column("task_attempts", sa.Column("packet_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column("task_attempts", "packet_sha256")
    op.drop_column("approvals", "scope_sha256")
    op.drop_column("tasks", "packet_sha256")
