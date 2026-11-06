"""Add market candles

Revision ID: 20260606_0003
Revises: 20260606_0002
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0003"
down_revision: str | None = "20260606_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_candles",
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 12), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_candles_symbol", "market_candles", ["symbol"])
    op.create_index("ix_market_candles_symbol_id", "market_candles", ["symbol_id"])
    op.create_index(
        "ix_market_candles_symbol_timeframe_timestamp",
        "market_candles",
        ["symbol", "timeframe", "timestamp"],
        unique=True,
    )
    op.create_index("ix_market_candles_timeframe", "market_candles", ["timeframe"])
    op.create_index("ix_market_candles_timestamp", "market_candles", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_market_candles_timestamp", table_name="market_candles")
    op.drop_index("ix_market_candles_timeframe", table_name="market_candles")
    op.drop_index("ix_market_candles_symbol_timeframe_timestamp", table_name="market_candles")
    op.drop_index("ix_market_candles_symbol_id", table_name="market_candles")
    op.drop_index("ix_market_candles_symbol", table_name="market_candles")
    op.drop_table("market_candles")
