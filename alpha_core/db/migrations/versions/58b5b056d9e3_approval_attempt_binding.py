"""approval_attempt_binding

Revision ID: 58b5b056d9e3
Revises: e7a9c2f4d601
Create Date: 2026-08-28 08:13:29.854511

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "58b5b056d9e3"
down_revision: str | Sequence[str] | None = "e7a9c2f4d601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_approvals_attempt_id", "task_attempts", ["attempt_id"], ["id"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("approvals") as batch_op:
        batch_op.drop_constraint("fk_approvals_attempt_id", type_="foreignkey")
        batch_op.drop_column("attempt_id")
