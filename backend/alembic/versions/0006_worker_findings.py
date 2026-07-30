"""durable worker claims and stable finding evidence

Revision ID: 0006_worker_findings
Revises: 0005_binary
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_worker_findings"
down_revision: str | None = "0005_binary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("execution_jobs") as batch:
        batch.drop_constraint(op.f("ck_execution_jobs_valid_status"), type_="check")
        batch.create_check_constraint(
            "valid_status",
            "status IN "
            "('queued','claimed','running','cancelling','completed','failed','cancelled','interrupted')",
        )
        batch.add_column(sa.Column("worker_id", sa.String(length=120)))
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("correlation_id", sa.String(length=36)))
        batch.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_index(
            "ix_execution_jobs_status_heartbeat",
            ["status", "heartbeat_at"],
            unique=False,
        )
    op.execute("UPDATE execution_jobs SET correlation_id = id WHERE correlation_id IS NULL")
    with op.batch_alter_table("execution_jobs") as batch:
        batch.alter_column("correlation_id", nullable=False)
        batch.alter_column("attempt_count", server_default=None)

    with op.batch_alter_table("findings") as batch:
        batch.add_column(sa.Column("fingerprint", sa.String(length=64)))
        batch.add_column(sa.Column("first_seen_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("recurrence_count", sa.Integer(), nullable=False, server_default="1")
        )
    op.execute(
        "UPDATE findings SET fingerprint = id, first_seen_at = created_at, "
        "last_seen_at = updated_at WHERE fingerprint IS NULL"
    )
    with op.batch_alter_table("findings") as batch:
        batch.alter_column("fingerprint", nullable=False)
        batch.alter_column("first_seen_at", nullable=False)
        batch.alter_column("last_seen_at", nullable=False)
        batch.alter_column("recurrence_count", server_default=None)
        batch.create_unique_constraint(
            "finding_fingerprint_per_project", ["project_id", "fingerprint"]
        )

    with op.batch_alter_table("finding_evidence") as batch:
        batch.add_column(sa.Column("observation_id", sa.String(length=36)))
        batch.add_column(sa.Column("comparison_run_id", sa.String(length=36)))
        batch.add_column(sa.Column("safe_metadata", sa.JSON(), nullable=False, server_default="{}"))
        batch.create_foreign_key(
            "fk_finding_evidence_observation_id_observations",
            "observations",
            ["observation_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_finding_evidence_comparison_run_id_comparison_runs",
            "comparison_runs",
            ["comparison_run_id"],
            ["id"],
        )
    with op.batch_alter_table("finding_evidence") as batch:
        batch.alter_column("safe_metadata", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("finding_evidence") as batch:
        batch.drop_constraint(
            "fk_finding_evidence_comparison_run_id_comparison_runs", type_="foreignkey"
        )
        batch.drop_constraint("fk_finding_evidence_observation_id_observations", type_="foreignkey")
        batch.drop_column("safe_metadata")
        batch.drop_column("comparison_run_id")
        batch.drop_column("observation_id")
    with op.batch_alter_table("findings") as batch:
        batch.drop_constraint("finding_fingerprint_per_project", type_="unique")
        batch.drop_column("recurrence_count")
        batch.drop_column("last_seen_at")
        batch.drop_column("first_seen_at")
        batch.drop_column("fingerprint")
    with op.batch_alter_table("execution_jobs") as batch:
        batch.drop_index("ix_execution_jobs_status_heartbeat")
        batch.drop_column("attempt_count")
        batch.drop_column("correlation_id")
        batch.drop_column("heartbeat_at")
        batch.drop_column("claimed_at")
        batch.drop_column("worker_id")
        batch.drop_constraint(op.f("ck_execution_jobs_valid_status"), type_="check")
        batch.create_check_constraint(
            "valid_status",
            "status IN ('queued','running','completed','failed','cancelled','interrupted')",
        )
