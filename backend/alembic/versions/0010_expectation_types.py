"""align persisted comparison expectations with the public API

Revision ID: 0010_expectation_types
Revises: 0009_run_cancellation
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_expectation_types"
down_revision: str | None = "0009_run_cancellation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_EXPECTATIONS = (
    "expected_behaviour IN "
    "('lower_denied','limited_fields','different_records','ownership_separation',"
    "'authenticated_only','tenant_separation','sensitive_fields_limited',"
    "'method_protection','object_existence_indistinguishable','baseline_consistency','custom')"
)
_LEGACY_EXPECTATIONS = (
    "expected_behaviour IN "
    "('lower_denied','limited_fields','different_records','ownership_separation','custom')"
)


def upgrade() -> None:
    with op.batch_alter_table("test_cases") as batch:
        batch.drop_constraint(op.f("ck_test_cases_valid_expectation"), type_="check")
        batch.create_check_constraint("valid_expectation", _ALL_EXPECTATIONS)


def downgrade() -> None:
    op.execute(
        "UPDATE test_cases SET expected_behaviour = 'custom' "
        "WHERE expected_behaviour NOT IN "
        "('lower_denied','limited_fields','different_records','ownership_separation','custom')"
    )
    with op.batch_alter_table("test_cases") as batch:
        batch.drop_constraint(op.f("ck_test_cases_valid_expectation"), type_="check")
        batch.create_check_constraint("valid_expectation", _LEGACY_EXPECTATIONS)
