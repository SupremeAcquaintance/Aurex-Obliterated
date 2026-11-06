"""Add strategy portfolio controls

Revision ID: 20260606_0004
Revises: 20260606_0003
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0004"
down_revision: str | None = "20260606_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_configs",
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_regimes", sa.JSON(), nullable=False),
        sa.Column("risk_per_trade", sa.Numeric(12, 6), nullable=True),
        sa.Column("minimum_reward_risk", sa.Numeric(12, 6), nullable=True),
        sa.Column("max_open_positions", sa.Integer(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy"),
    )
    op.create_index("ix_strategy_configs_strategy", "strategy_configs", ["strategy"])


def downgrade() -> None:
    op.drop_index("ix_strategy_configs_strategy", table_name="strategy_configs")
    op.drop_table("strategy_configs")
