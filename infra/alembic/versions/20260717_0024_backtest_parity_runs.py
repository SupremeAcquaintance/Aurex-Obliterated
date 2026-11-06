"""Add immutable backtest parity evidence.

Revision ID: 20260717_0024
Revises: 20260717_0023
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0024"
down_revision: str | None = "20260717_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_parity_runs",
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("tradingview_run_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dataset_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("tradingview_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("replay_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("summary_snapshot", sa.JSON(), nullable=False),
        sa.Column("mismatch_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason_snapshot", sa.JSON(), nullable=False),
        sa.Column("warning_snapshot", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["backtest_datasets.id"]),
        sa.ForeignKeyConstraint(["tradingview_run_id"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_hash"),
    )
    op.create_index("ix_backtest_parity_runs_dataset_id", "backtest_parity_runs", ["dataset_id"])
    op.create_index(
        "ix_backtest_parity_runs_tradingview_run_id",
        "backtest_parity_runs",
        ["tradingview_run_id"],
    )
    op.create_index("ix_backtest_parity_runs_strategy", "backtest_parity_runs", ["strategy"])
    op.create_index("ix_backtest_parity_runs_status", "backtest_parity_runs", ["status"])
    op.create_index(
        "ix_backtest_parity_runs_evidence_hash",
        "backtest_parity_runs",
        ["evidence_hash"],
    )
    op.create_index(
        "ix_backtest_parity_runs_recorded_at",
        "backtest_parity_runs",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_parity_runs_recorded_at", table_name="backtest_parity_runs")
    op.drop_index("ix_backtest_parity_runs_evidence_hash", table_name="backtest_parity_runs")
    op.drop_index("ix_backtest_parity_runs_status", table_name="backtest_parity_runs")
    op.drop_index("ix_backtest_parity_runs_strategy", table_name="backtest_parity_runs")
    op.drop_index(
        "ix_backtest_parity_runs_tradingview_run_id",
        table_name="backtest_parity_runs",
    )
    op.drop_index("ix_backtest_parity_runs_dataset_id", table_name="backtest_parity_runs")
    op.drop_table("backtest_parity_runs")
