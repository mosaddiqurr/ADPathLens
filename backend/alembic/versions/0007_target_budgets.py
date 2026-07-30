"""target execution budget and response policy

Revision ID: 0007_target_budgets
Revises: 0006_worker_findings
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_target_budgets"
down_revision: str | None = "0006_worker_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("targets") as batch:
        batch.add_column(
            sa.Column(
                "request_count_used",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column(
                "maximum_response_bytes",
                sa.Integer(),
                nullable=False,
                server_default=str(2 * 1024 * 1024),
            )
        )
        batch.add_column(sa.Column("last_execution_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("targets") as batch:
        batch.alter_column("request_count_used", server_default=None)
        batch.alter_column("maximum_response_bytes", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("targets") as batch:
        batch.drop_column("last_execution_at")
        batch.drop_column("maximum_response_bytes")
        batch.drop_column("request_count_used")
