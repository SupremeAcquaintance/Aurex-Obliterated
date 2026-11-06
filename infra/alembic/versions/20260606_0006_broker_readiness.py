"""Add broker readiness records

Revision ID: 20260606_0006
Revises: 20260606_0005
Create Date: 2026-06-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_0006"
down_revision: str | None = "20260606_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_connections",
        sa.Column("broker_name", sa.String(length=100), nullable=False),
        sa.Column("environment", sa.String(length=7), nullable=False),
        sa.Column("account_label", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=17), nullable=False),
        sa.Column("live_trading_enabled", sa.Boolean(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broker_connections_broker_name", "broker_connections", ["broker_name"])
    op.create_index("ix_broker_connections_environment", "broker_connections", ["environment"])
    op.create_index("ix_broker_connections_status", "broker_connections", ["status"])

    op.create_table(
        "order_intents",
        sa.Column("signal_id", sa.String(length=36), nullable=True),
        sa.Column("risk_decision_id", sa.String(length=36), nullable=True),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=5), nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("requested_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=True),
        sa.Column("time_in_force", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("intent_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_intent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["risk_decision_id"], ["risk_decisions.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_order_intents_broker_connection_id",
        "order_intents",
        ["broker_connection_id"],
    )
    op.create_index("ix_order_intents_risk_decision_id", "order_intents", ["risk_decision_id"])
    op.create_index("ix_order_intents_signal_id", "order_intents", ["signal_id"])
    op.create_index("ix_order_intents_status", "order_intents", ["status"])
    op.create_index("ix_order_intents_strategy", "order_intents", ["strategy"])
    op.create_index("ix_order_intents_symbol", "order_intents", ["symbol"])

    op.create_table(
        "broker_orders",
        sa.Column("order_intent_id", sa.String(length=36), nullable=False),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=5), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("requested_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("average_fill_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["order_intent_id"], ["order_intents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id"),
    )
    op.create_index(
        "ix_broker_orders_broker_connection_id",
        "broker_orders",
        ["broker_connection_id"],
    )
    op.create_index("ix_broker_orders_order_intent_id", "broker_orders", ["order_intent_id"])
    op.create_index("ix_broker_orders_status", "broker_orders", ["status"])
    op.create_index("ix_broker_orders_symbol", "broker_orders", ["symbol"])

    op.create_table(
        "broker_fills",
        sa.Column("broker_order_id", sa.String(length=36), nullable=False),
        sa.Column("external_fill_id", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=5), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["broker_order_id"], ["broker_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_fill_id"),
    )
    op.create_index("ix_broker_fills_broker_order_id", "broker_fills", ["broker_order_id"])
    op.create_index("ix_broker_fills_symbol", "broker_fills", ["symbol"])

    op.create_table(
        "broker_position_snapshots",
        sa.Column("broker_connection_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=5), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_broker_position_snapshots_broker_connection_id",
        "broker_position_snapshots",
        ["broker_connection_id"],
    )
    op.create_index("ix_broker_position_snapshots_symbol", "broker_position_snapshots", ["symbol"])

    op.create_table(
        "broker_reconciliation_reports",
        sa.Column("broker_connection_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=11), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
        sa.Column("broker_snapshot", sa.JSON(), nullable=False),
        sa.Column("aurex_snapshot", sa.JSON(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_broker_reconciliation_reports_broker_connection_id",
        "broker_reconciliation_reports",
        ["broker_connection_id"],
    )
    op.create_index(
        "ix_broker_reconciliation_reports_status",
        "broker_reconciliation_reports",
        ["status"],
    )

    op.create_table(
        "live_readiness_checks",
        sa.Column("check_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=7), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("check_key"),
    )
    op.create_index("ix_live_readiness_checks_check_key", "live_readiness_checks", ["check_key"])
    op.create_index("ix_live_readiness_checks_status", "live_readiness_checks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_live_readiness_checks_status", table_name="live_readiness_checks")
    op.drop_index("ix_live_readiness_checks_check_key", table_name="live_readiness_checks")
    op.drop_table("live_readiness_checks")
    op.drop_index(
        "ix_broker_reconciliation_reports_status",
        table_name="broker_reconciliation_reports",
    )
    op.drop_index(
        "ix_broker_reconciliation_reports_broker_connection_id",
        table_name="broker_reconciliation_reports",
    )
    op.drop_table("broker_reconciliation_reports")
    op.drop_index("ix_broker_position_snapshots_symbol", table_name="broker_position_snapshots")
    op.drop_index(
        "ix_broker_position_snapshots_broker_connection_id",
        table_name="broker_position_snapshots",
    )
    op.drop_table("broker_position_snapshots")
    op.drop_index("ix_broker_fills_symbol", table_name="broker_fills")
    op.drop_index("ix_broker_fills_broker_order_id", table_name="broker_fills")
    op.drop_table("broker_fills")
    op.drop_index("ix_broker_orders_symbol", table_name="broker_orders")
    op.drop_index("ix_broker_orders_status", table_name="broker_orders")
    op.drop_index("ix_broker_orders_order_intent_id", table_name="broker_orders")
    op.drop_index("ix_broker_orders_broker_connection_id", table_name="broker_orders")
    op.drop_table("broker_orders")
    op.drop_index("ix_order_intents_symbol", table_name="order_intents")
    op.drop_index("ix_order_intents_strategy", table_name="order_intents")
    op.drop_index("ix_order_intents_status", table_name="order_intents")
    op.drop_index("ix_order_intents_signal_id", table_name="order_intents")
    op.drop_index("ix_order_intents_risk_decision_id", table_name="order_intents")
    op.drop_index("ix_order_intents_broker_connection_id", table_name="order_intents")
    op.drop_table("order_intents")
    op.drop_index("ix_broker_connections_status", table_name="broker_connections")
    op.drop_index("ix_broker_connections_environment", table_name="broker_connections")
    op.drop_index("ix_broker_connections_broker_name", table_name="broker_connections")
    op.drop_table("broker_connections")
