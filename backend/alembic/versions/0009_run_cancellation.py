"""distinguish user cancellation from restart interruption

Revision ID: 0009_run_cancellation
Revises: 0008_audit_context
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_run_cancellation"
down_revision: str | None = "0008_audit_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("comparison_runs") as batch:
        batch.drop_constraint(op.f("ck_comparison_runs_valid_status"), type_="check")
        batch.create_check_constraint(
            "valid_status",
            "status IN "
            "('queued','running','cancelling','cancelled','completed','failed','interrupted')",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE comparison_runs SET status = 'interrupted' "
        "WHERE status IN ('cancelling','cancelled')"
    )
    with op.batch_alter_table("comparison_runs") as batch:
        batch.drop_constraint(op.f("ck_comparison_runs_valid_status"), type_="check")
        batch.create_check_constraint(
            "valid_status",
            "status IN ('queued','running','completed','failed','interrupted')",
        )
