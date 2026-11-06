"""Add paper evidence collection window fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0010"
down_revision: str | None = "20260606_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("minimum_trades", sa.Integer(), nullable=False, server_default="100"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("first_trade_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("latest_trade_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("calendar_days_observed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("minimum_calendar_days", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("live_paper_evidence_reports", "minimum_calendar_days")
    op.drop_column("live_paper_evidence_reports", "calendar_days_observed")
    op.drop_column("live_paper_evidence_reports", "latest_trade_at")
    op.drop_column("live_paper_evidence_reports", "first_trade_at")
    op.drop_column("live_paper_evidence_reports", "minimum_trades")
