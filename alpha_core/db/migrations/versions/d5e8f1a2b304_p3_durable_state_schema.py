"""P3 durable state schema: memberships, clients, consents, decisions, open questions, change requests, workflows, task dependencies.

Revision ID: d5e8f1a2b304
Revises: c8f9a1d2e603
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e8f1a2b304"
down_revision = "c8f9a1d2e603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Soft-delete columns
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("client_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key("fk_projects_client_id", "clients", ["client_id"], ["id"])

    with op.batch_alter_table("spec_versions") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Clients table
    op.create_table(
        "clients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. Memberships table
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("role", sa.String(32), server_default="client", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )

    # 4. Consents table
    op.create_table(
        "consents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("consent_type", sa.String(64), nullable=False),
        sa.Column("granted", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consent_project_user", "consents", ["project_id", "user_id"])

    # 5. Decisions table
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("spec_id", sa.String(64), sa.ForeignKey("spec_versions.id"), nullable=True),
        sa.Column("meeting_id", sa.String(64), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("alternatives_json", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(64), server_default="founder", nullable=False),
        sa.Column("status", sa.String(32), server_default="approved", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Open Questions table
    op.create_table(
        "open_questions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("spec_id", sa.String(64), sa.ForeignKey("spec_versions.id"), nullable=True),
        sa.Column("meeting_id", sa.String(64), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("context", sa.Text, nullable=False),
        sa.Column("owner", sa.String(32), server_default="founder", nullable=False),
        sa.Column("resolved", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 7. Change Requests table
    op.create_table(
        "change_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("impact_summary", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), server_default="submitted", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 8. Workflows table
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("phase", sa.String(32), server_default="intake", nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("details_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 9. Task Dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("depends_on_task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("required_status", sa.String(32), server_default="completed", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),
    )


def downgrade() -> None:
    op.drop_table("task_dependencies")
    op.drop_table("workflows")
    op.drop_table("change_requests")
    op.drop_table("open_questions")
    op.drop_table("decisions")
    op.drop_index("ix_consent_project_user", "consents")
    op.drop_table("consents")
    op.drop_table("memberships")
    op.drop_table("clients")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("deleted_at")

    with op.batch_alter_table("spec_versions") as batch_op:
        batch_op.drop_column("deleted_at")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_client_id", type_="foreignkey")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("client_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("deleted_at")

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("deleted_at")
