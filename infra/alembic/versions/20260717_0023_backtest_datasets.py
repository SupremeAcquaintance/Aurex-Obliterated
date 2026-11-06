"""Add immutable backtest OHLCV datasets.

Revision ID: 20260717_0023
Revises: 20260717_0022
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0023"
down_revision: str | None = "20260717_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_datasets",
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("csv_timezone", sa.String(length=64), nullable=False),
        sa.Column("continuity", sa.String(length=32), nullable=False),
        sa.Column("data_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("quality_snapshot", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_hash"),
    )
    op.create_index("ix_backtest_datasets_symbol", "backtest_datasets", ["symbol"])
    op.create_index("ix_backtest_datasets_timeframe", "backtest_datasets", ["timeframe"])
    op.create_index(
        "ix_backtest_datasets_evidence_hash",
        "backtest_datasets",
        ["evidence_hash"],
    )
    op.create_index(
        "ix_backtest_datasets_imported_at",
        "backtest_datasets",
        ["imported_at"],
    )

    op.create_table(
        "backtest_dataset_candles",
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.String(length=80), nullable=False),
        sa.Column("high", sa.String(length=80), nullable=False),
        sa.Column("low", sa.String(length=80), nullable=False),
        sa.Column("close", sa.String(length=80), nullable=False),
        sa.Column("volume", sa.String(length=80), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["backtest_datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_dataset_candles_dataset_id",
        "backtest_dataset_candles",
        ["dataset_id"],
    )
    op.create_index(
        "ix_backtest_dataset_candles_timestamp",
        "backtest_dataset_candles",
        ["timestamp"],
    )
    op.create_index(
        "ix_backtest_dataset_candles_dataset_sequence",
        "backtest_dataset_candles",
        ["dataset_id", "sequence"],
        unique=True,
    )
    op.create_index(
        "ix_backtest_dataset_candles_dataset_timestamp",
        "backtest_dataset_candles",
        ["dataset_id", "timestamp"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_dataset_candles_dataset_timestamp",
        table_name="backtest_dataset_candles",
    )
    op.drop_index(
        "ix_backtest_dataset_candles_dataset_sequence",
        table_name="backtest_dataset_candles",
    )
    op.drop_index(
        "ix_backtest_dataset_candles_timestamp",
        table_name="backtest_dataset_candles",
    )
    op.drop_index(
        "ix_backtest_dataset_candles_dataset_id",
        table_name="backtest_dataset_candles",
    )
    op.drop_table("backtest_dataset_candles")

    op.drop_index("ix_backtest_datasets_imported_at", table_name="backtest_datasets")
    op.drop_index("ix_backtest_datasets_evidence_hash", table_name="backtest_datasets")
    op.drop_index("ix_backtest_datasets_timeframe", table_name="backtest_datasets")
    op.drop_index("ix_backtest_datasets_symbol", table_name="backtest_datasets")
    op.drop_table("backtest_datasets")
