"""Persist normalized backtest trade evidence.

Revision ID: 20260623_0018
Revises: 20260607_0017
Create Date: 2026-06-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0018"
down_revision: str | None = "20260607_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.add_column(
            sa.Column(
                "source_format",
                sa.String(length=32),
                nullable=False,
                server_default="aurex_json",
            )
        )
        batch.add_column(sa.Column("source_reference", sa.Text(), nullable=True))
        batch.add_column(sa.Column("evidence_hash", sa.String(length=64), nullable=True))
        batch.create_index("ix_backtest_runs_evidence_hash", ["evidence_hash"])

    op.create_table(
        "backtest_trades",
        sa.Column("backtest_run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("external_trade_id", sa.String(length=128), nullable=True),
        sa.Column("source_format", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=True),
        sa.Column("direction", sa.String(length=5), nullable=True),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=True),
        sa.Column("gross_pl", sa.Numeric(20, 8), nullable=True),
        sa.Column("fees", sa.Numeric(20, 8), nullable=True),
        sa.Column("slippage", sa.Numeric(20, 8), nullable=True),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("equity", sa.Numeric(20, 8), nullable=True),
        sa.Column("r_multiple", sa.Numeric(12, 6), nullable=True),
        sa.Column("market_regime", sa.String(length=64), nullable=True),
        sa.Column("costs_snapshot", sa.JSON(), nullable=False),
        sa.Column("raw_row", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_trades_backtest_run_id",
        "backtest_trades",
        ["backtest_run_id"],
    )
    op.create_index(
        "ix_backtest_trades_closed_at",
        "backtest_trades",
        ["closed_at"],
    )
    op.create_index(
        "ix_backtest_trades_external_trade_id",
        "backtest_trades",
        ["external_trade_id"],
    )
    op.create_index(
        "ix_backtest_trades_market_regime",
        "backtest_trades",
        ["market_regime"],
    )
    op.create_index(
        "ix_backtest_trades_strategy",
        "backtest_trades",
        ["strategy"],
    )
    op.create_index(
        "ix_backtest_trades_symbol",
        "backtest_trades",
        ["symbol"],
    )
    op.create_index(
        "ix_backtest_trades_run_sequence",
        "backtest_trades",
        ["backtest_run_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_trades_run_sequence", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_symbol", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_strategy", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_market_regime", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_external_trade_id", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_closed_at", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_backtest_run_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")

    with op.batch_alter_table("backtest_runs") as batch:
        batch.drop_index("ix_backtest_runs_evidence_hash")
        batch.drop_column("evidence_hash")
        batch.drop_column("source_reference")
        batch.drop_column("source_format")
