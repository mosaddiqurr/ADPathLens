"""complete lifecycle, remediation, comparison, and audit contract

Revision ID: 0003_completion
Revises: 0002_schema
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_completion"
down_revision: str | None = "0002_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("datasets", sa.Column("rejected_record_count", sa.Integer(), server_default="0", nullable=False))

    for table in ("directory_nodes", "directory_relationships"):
        op.add_column(table, sa.Column("stable_fingerprint", sa.String(length=64), server_default="", nullable=False))
        op.add_column(
            table,
            sa.Column(
                "first_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(f"ix_{table}_stable_fingerprint", table, ["stable_fingerprint"], unique=False)
        op.execute(f"UPDATE {table} SET stable_fingerprint = 'legacy-' || id")
    op.execute("UPDATE directory_nodes SET first_seen_at = created_at, last_seen_at = created_at")
    op.execute("UPDATE directory_relationships SET first_seen_at = created_at, last_seen_at = created_at")

    with op.batch_alter_table("audit_events") as batch:
        batch.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("outcome", sa.String(length=32), server_default="success", nullable=False))
        batch.add_column(sa.Column("correlation_id", sa.String(length=128), nullable=True))
        batch.create_foreign_key(
            "fk_audit_events_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_audit_events_project_id", ["project_id"], unique=False)
        batch.create_index("ix_audit_events_outcome", ["outcome"], unique=False)
        batch.create_index("ix_audit_events_correlation_id", ["correlation_id"], unique=False)

    op.add_column(
        "privilege_paths",
        sa.Column("scoring_components", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )

    op.add_column(
        "risk_findings",
        sa.Column("stable_fingerprint", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "risk_findings",
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "risk_findings",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column("risk_findings", sa.Column("recurrence_count", sa.Integer(), server_default="1", nullable=False))
    op.execute("UPDATE risk_findings SET first_seen_at = created_at, last_seen_at = updated_at")
    op.execute("UPDATE risk_findings SET stable_fingerprint = 'legacy-' || id")
    op.create_index("ix_risk_findings_stable_fingerprint", "risk_findings", ["stable_fingerprint"], unique=False)

    with op.batch_alter_table("remediation_actions") as batch:
        batch.add_column(sa.Column("assigned_to", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("expected_outcome", sa.Text(), server_default="", nullable=False))
        batch.add_column(sa.Column("actual_outcome", sa.Text(), server_default="", nullable=False))
        batch.add_column(
            sa.Column(
                "verification_state",
                sa.String(length=32),
                server_default="not_verified",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_remediation_actions_assigned_to_users",
            "users",
            ["assigned_to"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_remediation_actions_assigned_to", ["assigned_to"], unique=False)
        batch.create_index(
            "ix_remediation_actions_verification_state",
            ["verification_state"],
            unique=False,
        )
    op.create_table(
        "remediation_action_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("remediation_action_id", sa.String(length=36), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("previous_progress", sa.Integer(), nullable=True),
        sa.Column("new_progress", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.String(length=36), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["remediation_action_id"],
            ["remediation_actions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_remediation_action_history_remediation_action_id",
        "remediation_action_history",
        ["remediation_action_id"],
        unique=False,
    )
    op.create_index(
        "ix_remediation_action_history_new_status",
        "remediation_action_history",
        ["new_status"],
        unique=False,
    )

    comparison_columns = (
        sa.Column("status", sa.String(length=32), server_default="complete", nullable=False),
        sa.Column("nodes_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("relationships_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paths_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("findings_added", sa.Integer(), server_default="0", nullable=False),
        sa.Column("findings_resolved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("findings_reopened", sa.Integer(), server_default="0", nullable=False),
        sa.Column("severity_changes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remediation_outcomes", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
    )
    for column in comparison_columns:
        op.add_column("snapshot_comparisons", column)
    op.create_index("ix_snapshot_comparisons_status", "snapshot_comparisons", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_snapshot_comparisons_status", table_name="snapshot_comparisons")
    for name in (
        "error_code",
        "remediation_outcomes",
        "severity_changes",
        "findings_reopened",
        "findings_resolved",
        "findings_added",
        "paths_unchanged",
        "relationships_unchanged",
        "nodes_unchanged",
        "status",
    ):
        op.drop_column("snapshot_comparisons", name)

    op.drop_index("ix_remediation_action_history_new_status", table_name="remediation_action_history")
    op.drop_index(
        "ix_remediation_action_history_remediation_action_id",
        table_name="remediation_action_history",
    )
    op.drop_table("remediation_action_history")
    with op.batch_alter_table("remediation_actions") as batch:
        batch.drop_index("ix_remediation_actions_verification_state")
        batch.drop_index("ix_remediation_actions_assigned_to")
        batch.drop_constraint("fk_remediation_actions_assigned_to_users", type_="foreignkey")
        for name in (
            "completed_at",
            "verification_state",
            "actual_outcome",
            "expected_outcome",
            "progress_percent",
            "due_at",
            "assigned_to",
        ):
            batch.drop_column(name)

    op.drop_index("ix_risk_findings_stable_fingerprint", table_name="risk_findings")
    for name in ("recurrence_count", "last_seen_at", "first_seen_at", "stable_fingerprint"):
        op.drop_column("risk_findings", name)
    op.drop_column("privilege_paths", "scoring_components")

    with op.batch_alter_table("audit_events") as batch:
        batch.drop_index("ix_audit_events_correlation_id")
        batch.drop_index("ix_audit_events_outcome")
        batch.drop_index("ix_audit_events_project_id")
        batch.drop_constraint("fk_audit_events_project_id_projects", type_="foreignkey")
        for name in ("correlation_id", "outcome", "project_id"):
            batch.drop_column(name)

    for table in ("directory_relationships", "directory_nodes"):
        op.drop_index(f"ix_{table}_stable_fingerprint", table_name=table)
        for name in ("last_seen_at", "first_seen_at", "stable_fingerprint"):
            op.drop_column(table, name)
    op.drop_column("datasets", "rejected_record_count")
    op.drop_column("datasets", "warning_count")
