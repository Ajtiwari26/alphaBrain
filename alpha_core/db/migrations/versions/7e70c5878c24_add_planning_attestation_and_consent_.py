"""add_planning_attestation_and_consent_fields

Revision ID: 7e70c5878c24
Revises: ea716532600e
Create Date: 2026-10-01 04:41:15.535975

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e70c5878c24"
down_revision: str | Sequence[str] | None = "ea716532600e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("planning_attestation_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("plan_blueprint_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("consents") as batch_op:
        batch_op.add_column(sa.Column("phone_number", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))
        batch_op.create_index("ix_consents_phone_number", ["phone_number"], unique=False)
        batch_op.create_index("ix_consent_phone_type", ["phone_number", "consent_type"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("consents") as batch_op:
        batch_op.drop_index("ix_consent_phone_type")
        batch_op.drop_index("ix_consents_phone_number")
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("phone_number")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("plan_blueprint_json")
        batch_op.drop_column("planning_attestation_json")
