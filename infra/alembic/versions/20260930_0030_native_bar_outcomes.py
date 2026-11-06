"""Add atomic native bar outcome/checkpoint records.

Revision ID: 20260930_0030
Revises: 20260718_0029
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0030"
down_revision: str | None = "20260718_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "native_bar_outcomes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stream_key", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("candle_id", sa.String(64), nullable=False),
        sa.Column("signal_id", sa.String(36), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_native_bar_stream_sequence",
        "native_bar_outcomes",
        ["stream_key", "sequence"],
        unique=True,
    )
    op.create_index(
        "uq_native_bar_stream_candle",
        "native_bar_outcomes",
        ["stream_key", "candle_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_native_bar_stream_candle", table_name="native_bar_outcomes")
    op.drop_index("uq_native_bar_stream_sequence", table_name="native_bar_outcomes")
    op.drop_table("native_bar_outcomes")
