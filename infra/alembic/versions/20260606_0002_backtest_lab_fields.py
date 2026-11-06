"""Add backtest lab fields

Revision ID: 20260606_0002
Revises: 20260605_0001
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0002"
down_revision: str | None = "20260605_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.add_column(sa.Column("symbols", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("timeframe", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("cost_model", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("slippage_model", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("risk_snapshot", sa.JSON(), nullable=True))

    with op.batch_alter_table("backtest_results") as batch:
        batch.add_column(sa.Column("breakeven", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("acceptance_passed", sa.Boolean(), nullable=True))
        batch.add_column(sa.Column("acceptance_reasons", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("acceptance_snapshot", sa.JSON(), nullable=True))

    with op.batch_alter_table("backtest_results") as batch:
        batch.alter_column("breakeven", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("backtest_results") as batch:
        batch.drop_column("acceptance_snapshot")
        batch.drop_column("acceptance_reasons")
        batch.drop_column("acceptance_passed")
        batch.drop_column("breakeven")

    with op.batch_alter_table("backtest_runs") as batch:
        batch.drop_column("risk_snapshot")
        batch.drop_column("slippage_model")
        batch.drop_column("cost_model")
        batch.drop_column("timeframe")
        batch.drop_column("symbols")

