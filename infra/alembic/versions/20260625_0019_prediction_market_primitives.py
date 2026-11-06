"""Add prediction-market research and paper-execution primitives.

Revision ID: 20260625_0019
Revises: 20260623_0018
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0019"
down_revision: str | None = "20260623_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "prediction_markets",
        sa.Column("venue", sa.String(length=16), nullable=False),
        sa.Column("event_ticker", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prediction_markets_venue_event",
        "prediction_markets",
        ["venue", "event_ticker"],
        unique=True,
    )
    op.create_index("ix_prediction_markets_venue", "prediction_markets", ["venue"])
    op.create_index("ix_prediction_markets_event_ticker", "prediction_markets", ["event_ticker"])
    op.create_index("ix_prediction_markets_status", "prediction_markets", ["status"])

    op.create_table(
        "prediction_contracts",
        sa.Column("market_id", sa.String(length=36), nullable=False),
        sa.Column("venue", sa.String(length=16), nullable=False),
        sa.Column("contract_ticker", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("yes_bid_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("yes_ask_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("no_bid_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("no_ask_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("expiration_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settlement_value", sa.Numeric(12, 6), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["market_id"], ["prediction_markets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prediction_contracts_venue_ticker",
        "prediction_contracts",
        ["venue", "contract_ticker"],
        unique=True,
    )
    op.create_index("ix_prediction_contracts_market_id", "prediction_contracts", ["market_id"])
    op.create_index("ix_prediction_contracts_venue", "prediction_contracts", ["venue"])
    op.create_index(
        "ix_prediction_contracts_contract_ticker",
        "prediction_contracts",
        ["contract_ticker"],
    )
    op.create_index("ix_prediction_contracts_status", "prediction_contracts", ["status"])

    op.create_table(
        "prediction_order_intents",
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("signal_id", sa.String(length=36), nullable=True),
        sa.Column("risk_decision_id", sa.String(length=36), nullable=True),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=True),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("side", sa.String(length=3), nullable=False),
        sa.Column("action", sa.String(length=4), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("limit_price", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("expected_edge", sa.Numeric(12, 6), nullable=True),
        sa.Column("confidence", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("intent_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_intent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *audit_columns(),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["prediction_contracts.id"]),
        sa.ForeignKeyConstraint(["risk_decision_id"], ["risk_decisions.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_prediction_order_intents_contract_id",
        "prediction_order_intents",
        ["contract_id"],
    )
    op.create_index(
        "ix_prediction_order_intents_signal_id",
        "prediction_order_intents",
        ["signal_id"],
    )
    op.create_index(
        "ix_prediction_order_intents_risk_decision_id",
        "prediction_order_intents",
        ["risk_decision_id"],
    )
    op.create_index(
        "ix_prediction_order_intents_broker_connection_id",
        "prediction_order_intents",
        ["broker_connection_id"],
    )
    op.create_index(
        "ix_prediction_order_intents_strategy",
        "prediction_order_intents",
        ["strategy"],
    )
    op.create_index("ix_prediction_order_intents_side", "prediction_order_intents", ["side"])
    op.create_index("ix_prediction_order_intents_status", "prediction_order_intents", ["status"])

    op.create_table(
        "prediction_orders",
        sa.Column("order_intent_id", sa.String(length=36), nullable=False),
        sa.Column("broker_connection_id", sa.String(length=36), nullable=True),
        sa.Column("external_order_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=3), nullable=False),
        sa.Column("action", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("limit_price", sa.Numeric(12, 6), nullable=False),
        sa.Column("average_fill_price", sa.Numeric(12, 6), nullable=True),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["order_intent_id"], ["prediction_order_intents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id"),
    )
    op.create_index(
        "ix_prediction_orders_order_intent_id",
        "prediction_orders",
        ["order_intent_id"],
    )
    op.create_index(
        "ix_prediction_orders_broker_connection_id",
        "prediction_orders",
        ["broker_connection_id"],
    )
    op.create_index(
        "ix_prediction_orders_external_order_id",
        "prediction_orders",
        ["external_order_id"],
    )
    op.create_index("ix_prediction_orders_status", "prediction_orders", ["status"])
    op.create_index("ix_prediction_orders_side", "prediction_orders", ["side"])

    op.create_table(
        "prediction_fills",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("external_fill_id", sa.String(length=128), nullable=False),
        sa.Column("side", sa.String(length=3), nullable=False),
        sa.Column("action", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("price", sa.Numeric(12, 6), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["order_id"], ["prediction_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_fill_id"),
    )
    op.create_index("ix_prediction_fills_order_id", "prediction_fills", ["order_id"])
    op.create_index("ix_prediction_fills_side", "prediction_fills", ["side"])

    op.create_table(
        "prediction_positions",
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("side", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(12, 6), nullable=False),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["prediction_contracts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_positions_account_id", "prediction_positions", ["account_id"])
    op.create_index("ix_prediction_positions_contract_id", "prediction_positions", ["contract_id"])
    op.create_index("ix_prediction_positions_side", "prediction_positions", ["side"])
    op.create_index("ix_prediction_positions_status", "prediction_positions", ["status"])
    op.create_index(
        "ix_prediction_positions_contract_side_status",
        "prediction_positions",
        ["contract_id", "side", "status"],
    )

    op.create_table(
        "prediction_settlements",
        sa.Column("contract_id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("settlement_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("gross_payout", sa.Numeric(20, 8), nullable=False),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["contract_id"], ["prediction_contracts.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["prediction_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prediction_settlements_contract_id",
        "prediction_settlements",
        ["contract_id"],
    )
    op.create_index(
        "ix_prediction_settlements_position_id",
        "prediction_settlements",
        ["position_id"],
    )

    op.create_table(
        "prediction_reconciliation_reports",
        sa.Column("broker_connection_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
        sa.Column("venue_snapshot", sa.JSON(), nullable=False),
        sa.Column("aurex_snapshot", sa.JSON(), nullable=False),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prediction_reconciliation_reports_broker_connection_id",
        "prediction_reconciliation_reports",
        ["broker_connection_id"],
    )
    op.create_index(
        "ix_prediction_reconciliation_reports_status",
        "prediction_reconciliation_reports",
        ["status"],
    )

    op.create_table(
        "prediction_evidence_events",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("strategy", sa.String(length=100), nullable=True),
        sa.Column("contract_ticker", sa.String(length=160), nullable=True),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prediction_evidence_events_kind", "prediction_evidence_events", ["kind"])
    op.create_index(
        "ix_prediction_evidence_events_entity_type",
        "prediction_evidence_events",
        ["entity_type"],
    )
    op.create_index(
        "ix_prediction_evidence_events_entity_id",
        "prediction_evidence_events",
        ["entity_id"],
    )
    op.create_index(
        "ix_prediction_evidence_events_strategy",
        "prediction_evidence_events",
        ["strategy"],
    )
    op.create_index(
        "ix_prediction_evidence_events_contract_ticker",
        "prediction_evidence_events",
        ["contract_ticker"],
    )
    op.create_index(
        "ix_prediction_evidence_events_evidence_hash",
        "prediction_evidence_events",
        ["evidence_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_evidence_events_evidence_hash",
        table_name="prediction_evidence_events",
    )
    op.drop_index(
        "ix_prediction_evidence_events_contract_ticker",
        table_name="prediction_evidence_events",
    )
    op.drop_index("ix_prediction_evidence_events_strategy", table_name="prediction_evidence_events")
    op.drop_index(
        "ix_prediction_evidence_events_entity_id",
        table_name="prediction_evidence_events",
    )
    op.drop_index(
        "ix_prediction_evidence_events_entity_type",
        table_name="prediction_evidence_events",
    )
    op.drop_index("ix_prediction_evidence_events_kind", table_name="prediction_evidence_events")
    op.drop_table("prediction_evidence_events")

    op.drop_index(
        "ix_prediction_reconciliation_reports_status",
        table_name="prediction_reconciliation_reports",
    )
    op.drop_index(
        "ix_prediction_reconciliation_reports_broker_connection_id",
        table_name="prediction_reconciliation_reports",
    )
    op.drop_table("prediction_reconciliation_reports")

    op.drop_index("ix_prediction_settlements_position_id", table_name="prediction_settlements")
    op.drop_index("ix_prediction_settlements_contract_id", table_name="prediction_settlements")
    op.drop_table("prediction_settlements")

    op.drop_index(
        "ix_prediction_positions_contract_side_status",
        table_name="prediction_positions",
    )
    op.drop_index("ix_prediction_positions_status", table_name="prediction_positions")
    op.drop_index("ix_prediction_positions_side", table_name="prediction_positions")
    op.drop_index("ix_prediction_positions_contract_id", table_name="prediction_positions")
    op.drop_index("ix_prediction_positions_account_id", table_name="prediction_positions")
    op.drop_table("prediction_positions")

    op.drop_index("ix_prediction_fills_side", table_name="prediction_fills")
    op.drop_index("ix_prediction_fills_order_id", table_name="prediction_fills")
    op.drop_table("prediction_fills")

    op.drop_index("ix_prediction_orders_side", table_name="prediction_orders")
    op.drop_index("ix_prediction_orders_status", table_name="prediction_orders")
    op.drop_index("ix_prediction_orders_external_order_id", table_name="prediction_orders")
    op.drop_index("ix_prediction_orders_broker_connection_id", table_name="prediction_orders")
    op.drop_index("ix_prediction_orders_order_intent_id", table_name="prediction_orders")
    op.drop_table("prediction_orders")

    op.drop_index("ix_prediction_order_intents_status", table_name="prediction_order_intents")
    op.drop_index("ix_prediction_order_intents_side", table_name="prediction_order_intents")
    op.drop_index("ix_prediction_order_intents_strategy", table_name="prediction_order_intents")
    op.drop_index(
        "ix_prediction_order_intents_broker_connection_id",
        table_name="prediction_order_intents",
    )
    op.drop_index(
        "ix_prediction_order_intents_risk_decision_id",
        table_name="prediction_order_intents",
    )
    op.drop_index("ix_prediction_order_intents_signal_id", table_name="prediction_order_intents")
    op.drop_index("ix_prediction_order_intents_contract_id", table_name="prediction_order_intents")
    op.drop_table("prediction_order_intents")

    op.drop_index("ix_prediction_contracts_status", table_name="prediction_contracts")
    op.drop_index("ix_prediction_contracts_contract_ticker", table_name="prediction_contracts")
    op.drop_index("ix_prediction_contracts_venue", table_name="prediction_contracts")
    op.drop_index("ix_prediction_contracts_market_id", table_name="prediction_contracts")
    op.drop_index("ix_prediction_contracts_venue_ticker", table_name="prediction_contracts")
    op.drop_table("prediction_contracts")

    op.drop_index("ix_prediction_markets_status", table_name="prediction_markets")
    op.drop_index("ix_prediction_markets_event_ticker", table_name="prediction_markets")
    op.drop_index("ix_prediction_markets_venue", table_name="prediction_markets")
    op.drop_index("ix_prediction_markets_venue_event", table_name="prediction_markets")
    op.drop_table("prediction_markets")
