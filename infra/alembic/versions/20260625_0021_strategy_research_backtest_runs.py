"""Add strategy research backtest run ledger.

Revision ID: 20260625_0021
Revises: 20260625_0020
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0021"
down_revision: str | None = "20260625_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "strategy_research_backtest_runs",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["candidate_id"], ["strategy_research_candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_candidate_id",
        "strategy_research_backtest_runs",
        ["candidate_id"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_strategy",
        "strategy_research_backtest_runs",
        ["strategy"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_accepted",
        "strategy_research_backtest_runs",
        ["accepted"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_decision",
        "strategy_research_backtest_runs",
        ["decision"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_evidence_hash",
        "strategy_research_backtest_runs",
        ["evidence_hash"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_reviewed_at",
        "strategy_research_backtest_runs",
        ["reviewed_at"],
    )
    op.create_index(
        "ix_strategy_research_backtest_runs_candidate_reviewed",
        "strategy_research_backtest_runs",
        ["candidate_id", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_research_backtest_runs_candidate_reviewed",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_reviewed_at",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_evidence_hash",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_decision",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_accepted",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_strategy",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_index(
        "ix_strategy_research_backtest_runs_candidate_id",
        table_name="strategy_research_backtest_runs",
    )
    op.drop_table("strategy_research_backtest_runs")
