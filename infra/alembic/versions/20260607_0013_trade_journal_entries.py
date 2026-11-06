"""Add trade journal entries.

Revision ID: 20260607_0013
Revises: 20260606_0012
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260607_0013"
down_revision: str | None = "20260606_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_journal_entries",
        sa.Column("paper_trade_id", sa.String(length=36), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("execution_notes", sa.Text()),
        sa.Column("outcome_notes", sa.Text()),
        sa.Column("rule_followed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("emotional_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("journaled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["paper_trade_id"], ["paper_trades.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_trade_journal_entries_paper_trade_id"),
        "trade_journal_entries",
        ["paper_trade_id"],
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("journaled_trade_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column("unjournaled_trade_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "live_paper_evidence_reports",
        sa.Column(
            "journal_rule_violation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("live_paper_evidence_reports", "journal_rule_violation_count")
    op.drop_column("live_paper_evidence_reports", "unjournaled_trade_count")
    op.drop_column("live_paper_evidence_reports", "journaled_trade_count")
    op.drop_index(op.f("ix_trade_journal_entries_paper_trade_id"), "trade_journal_entries")
    op.drop_table("trade_journal_entries")
