"""Add approval packet due diligence fields.

Revision ID: 20260606_0012
Revises: 20260606_0011
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0012"
down_revision: str | None = "20260606_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "live_approval_packets",
        sa.Column(
            "account_constraints_reference",
            sa.Text(),
            nullable=False,
            server_default="UNRECORDED",
        ),
    )
    op.add_column(
        "live_approval_packets",
        sa.Column(
            "execution_policy_reference",
            sa.Text(),
            nullable=False,
            server_default="UNRECORDED",
        ),
    )
    op.add_column(
        "live_approval_packets",
        sa.Column(
            "fee_slippage_model_reference",
            sa.Text(),
            nullable=False,
            server_default="UNRECORDED",
        ),
    )
    op.add_column(
        "live_approval_packets",
        sa.Column(
            "paper_to_live_checklist_reference",
            sa.Text(),
            nullable=False,
            server_default="UNRECORDED",
        ),
    )
    op.add_column("live_approval_packets", sa.Column("sandbox_test_reference", sa.Text()))
    op.add_column(
        "live_approval_packets",
        sa.Column("leverage_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("live_approval_packets", "leverage_allowed")
    op.drop_column("live_approval_packets", "sandbox_test_reference")
    op.drop_column("live_approval_packets", "paper_to_live_checklist_reference")
    op.drop_column("live_approval_packets", "fee_slippage_model_reference")
    op.drop_column("live_approval_packets", "execution_policy_reference")
    op.drop_column("live_approval_packets", "account_constraints_reference")
