"""request metadata

Revision ID: 0003_requests
Revises: 0002_core
Create Date: 2026-07-26 16:28:21.261848
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_requests"
down_revision: str | None = "0002_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Server defaults keep upgrades valid when request definitions already exist.
    with op.batch_alter_table("imported_requests") as batch:
        batch.add_column(
            sa.Column(
                "approved_state_change",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column("expected_markers", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(
            sa.Column(
                "sensitivity",
                sa.String(length=24),
                nullable=False,
                server_default="internal",
            )
        )
    with op.batch_alter_table("imported_requests") as batch:
        batch.alter_column("approved_state_change", server_default=None)
        batch.alter_column("expected_markers", server_default=None)
        batch.alter_column("tags", server_default=None)
        batch.alter_column("sensitivity", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("imported_requests") as batch:
        batch.drop_column("sensitivity")
        batch.drop_column("tags")
        batch.drop_column("expected_markers")
        batch.drop_column("approved_state_change")
