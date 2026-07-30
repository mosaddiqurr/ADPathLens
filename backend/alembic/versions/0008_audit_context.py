"""audit outcome and correlation context

Revision ID: 0008_audit_context
Revises: 0007_target_budgets
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_audit_context"
down_revision: str | None = "0007_target_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("project_id", sa.String(length=36)))
        batch.add_column(
            sa.Column(
                "outcome",
                sa.String(length=24),
                nullable=False,
                server_default="success",
            )
        )
        batch.add_column(sa.Column("safe_metadata", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("correlation_id", sa.String(length=64)))
        batch.create_index("ix_audit_events_project_id", ["project_id"], unique=False)
    op.execute(
        "UPDATE audit_events SET correlation_id = request_id "
        "WHERE correlation_id IS NULL AND request_id IS NOT NULL"
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("outcome", server_default=None)
        batch.alter_column("safe_metadata", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_project_id")
        batch.drop_column("correlation_id")
        batch.drop_column("safe_metadata")
        batch.drop_column("outcome")
        batch.drop_column("project_id")
