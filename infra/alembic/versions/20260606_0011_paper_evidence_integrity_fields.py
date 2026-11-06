"""Add paper evidence integrity fields.

Revision ID: 20260606_0011
Revises: 20260606_0010
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0011"
down_revision: str | None = "20260606_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("max_allowed_drawdown", sa.Numeric(20, 8), nullable=False, server_default="0"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("unexplained_trade_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("risk_rule_violation_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("live_paper_evidence_reports", "risk_rule_violation_count")
    op.drop_column("live_paper_evidence_reports", "unexplained_trade_count")
    op.drop_column("live_paper_evidence_reports", "max_allowed_drawdown")
