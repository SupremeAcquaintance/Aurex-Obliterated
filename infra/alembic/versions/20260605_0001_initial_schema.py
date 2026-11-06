"""Initial schema

Revision ID: 20260605_0001
Revises: None
Create Date: 2026-06-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260605_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def id_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
    ]


def enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    direction_enum = enum("LONG", "SHORT", name="direction")
    market_regime_enum = enum(
        "TRENDING_UP",
        "TRENDING_DOWN",
        "RANGING",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "BREAKOUT_EXPANSION",
        "CHOPPY_DANGER_ZONE",
        "UNKNOWN",
        name="marketregime",
    )
    signal_status_enum = enum(
        "RECEIVED",
        "VALIDATED",
        "REJECTED_INVALID",
        "DUPLICATE_REJECTED",
        "SCORED",
        "RISK_APPROVED",
        "RISK_REJECTED",
        "PAPER_ORDER_CREATED",
        "PAPER_EXECUTED",
        "CLOSED",
        "ANALYZED",
        name="signalstatus",
    )
    order_status_enum = enum("CREATED", "FILLED", "CANCELLED", "REJECTED", name="orderstatus")
    trade_status_enum = enum("OPEN", "CLOSED", name="tradestatus")
    position_status_enum = enum("OPEN", "CLOSED", name="positionstatus")
    strategy_run_status_enum = enum(
        "DRAFT",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        name="strategyrunstatus",
    )
    backtest_status_enum = enum("DRAFT", "RUNNING", "COMPLETED", "FAILED", name="backteststatus")
    event_severity_enum = enum("INFO", "WARNING", "ERROR", "CRITICAL", name="systemeventseverity")

    op.create_table(
        "accounts",
        *id_columns(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("starting_equity", sa.Numeric(20, 8), nullable=False),
        sa.Column("current_equity", sa.Numeric(20, 8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "backtest_runs",
        *id_columns(),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("status", backtest_status_enum, nullable=False),
        sa.Column("data_source", sa.String(length=100), nullable=False),
        sa.Column("data_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("in_sample_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("in_sample_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("out_of_sample_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("out_of_sample_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backtest_runs_config_hash", "backtest_runs", ["config_hash"])
    op.create_index("ix_backtest_runs_strategy", "backtest_runs", ["strategy"])

    op.create_table(
        "strategy_runs",
        *id_columns(),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("status", strategy_run_status_enum, nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_runs_strategy", "strategy_runs", ["strategy"])

    op.create_table(
        "symbols",
        *id_columns(),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("base_asset", sa.String(length=32), nullable=True),
        sa.Column("quote_asset", sa.String(length=32), nullable=True),
        sa.Column("asset_class", sa.String(length=32), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_symbols_symbol", "symbols", ["symbol"])

    op.create_table(
        "system_events",
        *id_columns(),
        sa.Column("severity", event_severity_enum, nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_category", "system_events", ["category"])
    op.create_index("ix_system_events_occurred_at", "system_events", ["occurred_at"])
    op.create_index("ix_system_events_severity", "system_events", ["severity"])

    op.create_table(
        "backtest_results",
        *id_columns(),
        sa.Column("backtest_run_id", sa.String(length=36), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False),
        sa.Column("losses", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("average_win", sa.Numeric(20, 8), nullable=True),
        sa.Column("average_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("expectancy", sa.Numeric(20, 8), nullable=True),
        sa.Column("profit_factor", sa.Numeric(12, 6), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(20, 8), nullable=True),
        sa.Column("total_net_pl", sa.Numeric(20, 8), nullable=True),
        sa.Column("metrics_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["backtest_run_id"], ["backtest_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("backtest_run_id"),
    )
    op.create_index("ix_backtest_results_backtest_run_id", "backtest_results", ["backtest_run_id"])

    op.create_table(
        "equity_curve_points",
        *id_columns(),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("equity", sa.Numeric(20, 8), nullable=False),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=False),
        sa.Column("drawdown", sa.Numeric(20, 8), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_equity_curve_points_account_id", "equity_curve_points", ["account_id"])
    op.create_index("ix_equity_curve_points_recorded_at", "equity_curve_points", ["recorded_at"])

    op.create_table(
        "positions",
        *id_columns(),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("status", position_status_enum, nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("average_entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_positions_account_id", "positions", ["account_id"])
    op.create_index("ix_positions_status", "positions", ["status"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_index("ix_positions_symbol_id", "positions", ["symbol_id"])

    op.create_table(
        "risk_profiles",
        *id_columns(),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("risk_per_trade", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_daily_loss", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_weekly_loss", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_open_positions", sa.Integer(), nullable=False),
        sa.Column("minimum_reward_risk", sa.Numeric(12, 6), nullable=False),
        sa.Column("duplicate_cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("max_signal_age_seconds", sa.Integer(), nullable=False),
        sa.Column("loss_cooldown_count", sa.Integer(), nullable=False),
        sa.Column("kill_switch_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_profiles_account_id", "risk_profiles", ["account_id"])

    op.create_table(
        "signals",
        *id_columns(),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=True),
        sa.Column("market_regime", market_regime_enum, nullable=False),
        sa.Column("status", signal_status_enum, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("duplicate_of_signal_id", sa.String(length=36), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["duplicate_of_signal_id"], ["signals.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_duplicate_of_signal_id", "signals", ["duplicate_of_signal_id"])
    op.create_index(
        "ix_signals_dedupe_window",
        "signals",
        ["symbol", "strategy", "timeframe", "direction", "source_timestamp"],
    )
    op.create_index("ix_signals_idempotency_key", "signals", ["idempotency_key"])
    op.create_index("ix_signals_status", "signals", ["status"])
    op.create_index("ix_signals_strategy", "signals", ["strategy"])
    op.create_index("ix_signals_symbol", "signals", ["symbol"])
    op.create_index("ix_signals_symbol_id", "signals", ["symbol_id"])

    op.create_table(
        "market_states",
        *id_columns(),
        sa.Column("signal_id", sa.String(length=36), nullable=True),
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("regime", market_regime_enum, nullable=False),
        sa.Column("confidence", sa.Numeric(12, 6), nullable=True),
        sa.Column("inputs_snapshot", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_states_signal_id", "market_states", ["signal_id"])
    op.create_index("ix_market_states_symbol", "market_states", ["symbol"])
    op.create_index("ix_market_states_symbol_id", "market_states", ["symbol_id"])

    op.create_table(
        "risk_decisions",
        *id_columns(),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("risk_profile_id", sa.String(length=36), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reward_risk", sa.Numeric(12, 6), nullable=True),
        sa.Column("risk_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("position_size", sa.Numeric(28, 12), nullable=True),
        sa.Column("account_equity", sa.Numeric(20, 8), nullable=True),
        sa.Column("rules_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["risk_profile_id"], ["risk_profiles.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_decisions_risk_profile_id", "risk_decisions", ["risk_profile_id"])
    op.create_index("ix_risk_decisions_signal_id", "risk_decisions", ["signal_id"])

    op.create_table(
        "signal_events",
        *id_columns(),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("status", signal_status_enum, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_events_signal_id", "signal_events", ["signal_id"])

    op.create_table(
        "strategy_scores",
        *id_columns(),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("score", sa.Numeric(12, 6), nullable=False),
        sa.Column("confidence", sa.Numeric(12, 6), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("features_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_scores_signal_id", "strategy_scores", ["signal_id"])
    op.create_index("ix_strategy_scores_strategy", "strategy_scores", ["strategy"])

    op.create_table(
        "paper_orders",
        *id_columns(),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("risk_decision_id", sa.String(length=36), nullable=False),
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("status", order_status_enum, nullable=False),
        sa.Column("requested_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("filled_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("slippage", sa.Numeric(20, 8), nullable=False),
        sa.Column("fill_model", sa.String(length=64), nullable=False),
        sa.Column("created_order_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["risk_decision_id"], ["risk_decisions.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_orders_signal_id", "paper_orders", ["signal_id"])
    op.create_index("ix_paper_orders_symbol_id", "paper_orders", ["symbol_id"])

    op.create_table(
        "paper_trades",
        *id_columns(),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("paper_order_id", sa.String(length=36), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("symbol_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("timeframe", sa.String(length=32), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("status", trade_status_enum, nullable=False),
        sa.Column("market_regime", market_regime_enum, nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("stop_loss", sa.Numeric(20, 8), nullable=False),
        sa.Column("take_profit", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("risk_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pl", sa.Numeric(20, 8), nullable=True),
        sa.Column("r_multiple", sa.Numeric(12, 6), nullable=True),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("slippage", sa.Numeric(20, 8), nullable=False),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["paper_order_id"], ["paper_orders.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_trades_account_id", "paper_trades", ["account_id"])
    op.create_index("ix_paper_trades_paper_order_id", "paper_trades", ["paper_order_id"])
    op.create_index("ix_paper_trades_status", "paper_trades", ["status"])
    op.create_index("ix_paper_trades_strategy", "paper_trades", ["strategy"])
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])
    op.create_index("ix_paper_trades_symbol_id", "paper_trades", ["symbol_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_trades_symbol_id", table_name="paper_trades")
    op.drop_index("ix_paper_trades_symbol", table_name="paper_trades")
    op.drop_index("ix_paper_trades_strategy", table_name="paper_trades")
    op.drop_index("ix_paper_trades_status", table_name="paper_trades")
    op.drop_index("ix_paper_trades_paper_order_id", table_name="paper_trades")
    op.drop_index("ix_paper_trades_account_id", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("ix_paper_orders_symbol_id", table_name="paper_orders")
    op.drop_index("ix_paper_orders_signal_id", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_index("ix_strategy_scores_strategy", table_name="strategy_scores")
    op.drop_index("ix_strategy_scores_signal_id", table_name="strategy_scores")
    op.drop_table("strategy_scores")
    op.drop_index("ix_signal_events_signal_id", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_index("ix_risk_decisions_signal_id", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_risk_profile_id", table_name="risk_decisions")
    op.drop_table("risk_decisions")
    op.drop_index("ix_market_states_symbol_id", table_name="market_states")
    op.drop_index("ix_market_states_symbol", table_name="market_states")
    op.drop_index("ix_market_states_signal_id", table_name="market_states")
    op.drop_table("market_states")
    op.drop_index("ix_signals_symbol_id", table_name="signals")
    op.drop_index("ix_signals_symbol", table_name="signals")
    op.drop_index("ix_signals_strategy", table_name="signals")
    op.drop_index("ix_signals_status", table_name="signals")
    op.drop_index("ix_signals_idempotency_key", table_name="signals")
    op.drop_index("ix_signals_duplicate_of_signal_id", table_name="signals")
    op.drop_index("ix_signals_dedupe_window", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_risk_profiles_account_id", table_name="risk_profiles")
    op.drop_table("risk_profiles")
    op.drop_index("ix_positions_symbol_id", table_name="positions")
    op.drop_index("ix_positions_symbol", table_name="positions")
    op.drop_index("ix_positions_status", table_name="positions")
    op.drop_index("ix_positions_account_id", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_equity_curve_points_recorded_at", table_name="equity_curve_points")
    op.drop_index("ix_equity_curve_points_account_id", table_name="equity_curve_points")
    op.drop_table("equity_curve_points")
    op.drop_index("ix_backtest_results_backtest_run_id", table_name="backtest_results")
    op.drop_table("backtest_results")
    op.drop_index("ix_system_events_severity", table_name="system_events")
    op.drop_index("ix_system_events_occurred_at", table_name="system_events")
    op.drop_index("ix_system_events_category", table_name="system_events")
    op.drop_table("system_events")
    op.drop_index("ix_symbols_symbol", table_name="symbols")
    op.drop_table("symbols")
    op.drop_index("ix_strategy_runs_strategy", table_name="strategy_runs")
    op.drop_table("strategy_runs")
    op.drop_index("ix_backtest_runs_strategy", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_config_hash", table_name="backtest_runs")
    op.drop_table("backtest_runs")
    op.drop_table("accounts")
