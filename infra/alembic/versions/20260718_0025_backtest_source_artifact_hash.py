"""Bind backtest runs to their exact imported source artifact.

Revision ID: 20260718_0025
Revises: 20260717_0024
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0025"
down_revision: str | None = "20260717_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column("source_artifact_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_backtest_runs_source_artifact_hash",
        "backtest_runs",
        ["source_artifact_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_runs_source_artifact_hash",
        table_name="backtest_runs",
    )
    op.drop_column("backtest_runs", "source_artifact_hash")
