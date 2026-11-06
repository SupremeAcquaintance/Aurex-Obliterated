"""Add immutable reference replay evidence.

Revision ID: 20260718_0027
Revises: 20260718_0026
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0027"
down_revision: str | None = "20260718_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_reference_replay_runs",
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dataset_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("engine_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("record_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["backtest_datasets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engine_evidence_hash"),
        sa.UniqueConstraint("record_evidence_hash"),
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_dataset_id",
        "backtest_reference_replay_runs",
        ["dataset_id"],
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_strategy",
        "backtest_reference_replay_runs",
        ["strategy"],
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_status",
        "backtest_reference_replay_runs",
        ["status"],
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_engine_evidence_hash",
        "backtest_reference_replay_runs",
        ["engine_evidence_hash"],
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_record_evidence_hash",
        "backtest_reference_replay_runs",
        ["record_evidence_hash"],
    )
    op.create_index(
        "ix_backtest_reference_replay_runs_recorded_at",
        "backtest_reference_replay_runs",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_backtest_reference_replay_runs_recorded_at",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_index(
        "ix_backtest_reference_replay_runs_record_evidence_hash",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_index(
        "ix_backtest_reference_replay_runs_engine_evidence_hash",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_index(
        "ix_backtest_reference_replay_runs_status",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_index(
        "ix_backtest_reference_replay_runs_strategy",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_index(
        "ix_backtest_reference_replay_runs_dataset_id",
        table_name="backtest_reference_replay_runs",
    )
    op.drop_table("backtest_reference_replay_runs")
