"""Add immutable reference replay validation evidence.

Revision ID: 20260718_0028
Revises: 20260718_0027
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0028"
down_revision: str | None = "20260718_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_reference_replay_validations",
        sa.Column("reference_replay_run_id", sa.String(length=36), nullable=False),
        sa.Column("protocol_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("evaluator_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("statistical_acceptance_passed", sa.Boolean(), nullable=False),
        sa.Column("replay_record_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("engine_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("dataset_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("protocol_hash", sa.String(length=64), nullable=False),
        sa.Column("trade_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.Column("acceptance_snapshot", sa.JSON(), nullable=False),
        sa.Column("binding_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason_snapshot", sa.JSON(), nullable=False),
        sa.Column("warning_snapshot", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["backtest_datasets.id"]),
        sa.ForeignKeyConstraint(["protocol_id"], ["backtest_protocols.id"]),
        sa.ForeignKeyConstraint(
            ["reference_replay_run_id"],
            ["backtest_reference_replay_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("validation_evidence_hash"),
    )
    for name, columns in (
        ("ix_bt_replay_validations_replay", ["reference_replay_run_id"]),
        ("ix_bt_replay_validations_protocol", ["protocol_id"]),
        ("ix_bt_replay_validations_dataset", ["dataset_id"]),
        ("ix_bt_replay_validations_strategy", ["strategy"]),
        ("ix_bt_replay_validations_symbol", ["symbol"]),
        ("ix_bt_replay_validations_status", ["status"]),
        ("ix_bt_replay_validations_hash", ["validation_evidence_hash"]),
        ("ix_bt_replay_validations_recorded", ["recorded_at"]),
    ):
        op.create_index(name, "backtest_reference_replay_validations", columns)


def downgrade() -> None:
    for name in (
        "ix_bt_replay_validations_recorded",
        "ix_bt_replay_validations_hash",
        "ix_bt_replay_validations_status",
        "ix_bt_replay_validations_symbol",
        "ix_bt_replay_validations_strategy",
        "ix_bt_replay_validations_dataset",
        "ix_bt_replay_validations_protocol",
        "ix_bt_replay_validations_replay",
    ):
        op.drop_index(name, table_name="backtest_reference_replay_validations")
    op.drop_table("backtest_reference_replay_validations")
