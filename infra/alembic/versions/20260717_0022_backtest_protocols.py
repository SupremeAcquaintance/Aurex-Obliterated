"""Add immutable backtest protocol ledger.

Revision ID: 20260717_0022
Revises: 20260625_0021
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0022"
down_revision: str | None = "20260625_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_protocols",
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("protocol_hash", sa.String(length=64), nullable=False),
        sa.Column("protocol_snapshot", sa.JSON(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_backtest_protocols_strategy",
        "backtest_protocols",
        ["strategy"],
    )
    op.create_index(
        "ix_backtest_protocols_protocol_hash",
        "backtest_protocols",
        ["protocol_hash"],
    )
    op.create_index(
        "ix_backtest_protocols_registered_at",
        "backtest_protocols",
        ["registered_at"],
    )

    with op.batch_alter_table("backtest_runs") as batch:
        batch.add_column(sa.Column("protocol_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("protocol_evidence_hash", sa.String(length=64), nullable=True)
        )
        batch.create_foreign_key(
            "fk_backtest_runs_protocol_id_backtest_protocols",
            "backtest_protocols",
            ["protocol_id"],
            ["id"],
        )
        batch.create_index(
            "ix_backtest_runs_protocol_id",
            ["protocol_id"],
            unique=True,
        )
        batch.create_index(
            "ix_backtest_runs_protocol_evidence_hash",
            ["protocol_evidence_hash"],
        )


def downgrade() -> None:
    with op.batch_alter_table("backtest_runs") as batch:
        batch.drop_index("ix_backtest_runs_protocol_evidence_hash")
        batch.drop_index("ix_backtest_runs_protocol_id")
        batch.drop_constraint(
            "fk_backtest_runs_protocol_id_backtest_protocols",
            type_="foreignkey",
        )
        batch.drop_column("protocol_evidence_hash")
        batch.drop_column("protocol_id")

    op.drop_index("ix_backtest_protocols_registered_at", table_name="backtest_protocols")
    op.drop_index("ix_backtest_protocols_protocol_hash", table_name="backtest_protocols")
    op.drop_index("ix_backtest_protocols_strategy", table_name="backtest_protocols")
    op.drop_table("backtest_protocols")
