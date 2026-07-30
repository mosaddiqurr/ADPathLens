"""binary observation metadata

Revision ID: 0005_binary
Revises: 0004_anonymous
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_binary"
down_revision: str | None = "0004_anonymous"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("observations") as batch:
        batch.add_column(
            sa.Column(
                "is_binary",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("observations") as batch:
        batch.alter_column("is_binary", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("observations") as batch:
        batch.drop_column("is_binary")
