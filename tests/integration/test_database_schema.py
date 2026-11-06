from datetime import UTC, datetime
from decimal import Decimal

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from aurex.config.settings import get_settings
from aurex.db.base import Base
from aurex.db.models import (
    Account,
    RiskDecision,
    RiskProfile,
    Signal,
    SignalEvent,
    Symbol,
)
from aurex.domain.enums import Direction, MarketRegime, SignalStatus

REQUIRED_TABLES = {
    "accounts",
    "risk_profiles",
    "signals",
    "signal_events",
    "market_states",
    "market_candles",
    "strategy_scores",
    "risk_decisions",
    "paper_orders",
    "paper_trades",
    "trade_journal_entries",
    "positions",
    "equity_curve_points",
    "strategy_runs",
    "backtest_runs",
    "backtest_datasets",
    "backtest_dataset_candles",
    "backtest_reference_replay_runs",
    "backtest_reference_replay_validations",
    "backtest_parity_runs",
    "backtest_protocols",
    "backtest_results",
    "backtest_trades",
    "symbols",
    "system_events",
    "strategy_configs",
    "analyst_notes",
    "broker_connections",
    "order_intents",
    "broker_orders",
    "broker_fills",
    "broker_position_snapshots",
    "broker_reconciliation_reports",
    "live_readiness_checks",
    "live_deployment_plans",
    "live_deployment_gates",
    "live_daily_review_reports",
    "live_approval_records",
    "live_paper_evidence_reports",
    "live_broker_statement_reports",
    "live_profit_milestone_reports",
    "live_approval_packets",
    "paper_evidence_import_batches",
    "strategy_evidence_reviews",
    "prediction_markets",
    "prediction_contracts",
    "prediction_order_intents",
    "prediction_orders",
    "prediction_fills",
    "prediction_positions",
    "prediction_settlements",
    "prediction_reconciliation_reports",
    "prediction_evidence_events",
    "strategy_research_candidates",
    "strategy_research_observations",
    "strategy_research_backtest_runs",
}


def test_alembic_initial_schema_upgrade_and_downgrade(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "aurex_migration_test.db"
    monkeypatch.setenv("AUREX_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()

    config = Config("alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    assert REQUIRED_TABLES.issubset(set(inspector.get_table_names()))
    signal_indexes = {index["name"]: index for index in inspector.get_indexes("signals")}
    assert signal_indexes["uq_signals_canonical_idempotency_key"]["unique"] == 1
    backtest_run_columns = {column["name"] for column in inspector.get_columns("backtest_runs")}
    backtest_dataset_columns = {
        column["name"] for column in inspector.get_columns("backtest_datasets")
    }
    backtest_dataset_candle_columns = {
        column["name"] for column in inspector.get_columns("backtest_dataset_candles")
    }
    backtest_reference_replay_columns = {
        column["name"]
        for column in inspector.get_columns("backtest_reference_replay_runs")
    }
    backtest_reference_validation_columns = {
        column["name"]
        for column in inspector.get_columns("backtest_reference_replay_validations")
    }
    backtest_parity_columns = {
        column["name"] for column in inspector.get_columns("backtest_parity_runs")
    }
    backtest_protocol_columns = {
        column["name"] for column in inspector.get_columns("backtest_protocols")
    }
    backtest_result_columns = {
        column["name"] for column in inspector.get_columns("backtest_results")
    }
    backtest_trade_columns = {
        column["name"] for column in inspector.get_columns("backtest_trades")
    }
    market_candle_columns = {column["name"] for column in inspector.get_columns("market_candles")}
    strategy_config_columns = {
        column["name"] for column in inspector.get_columns("strategy_configs")
    }
    analyst_note_columns = {column["name"] for column in inspector.get_columns("analyst_notes")}
    broker_connection_columns = {
        column["name"] for column in inspector.get_columns("broker_connections")
    }
    order_intent_columns = {column["name"] for column in inspector.get_columns("order_intents")}
    reconciliation_columns = {
        column["name"] for column in inspector.get_columns("broker_reconciliation_reports")
    }
    readiness_columns = {
        column["name"] for column in inspector.get_columns("live_readiness_checks")
    }
    live_deployment_plan_columns = {
        column["name"] for column in inspector.get_columns("live_deployment_plans")
    }
    live_deployment_gate_columns = {
        column["name"] for column in inspector.get_columns("live_deployment_gates")
    }
    daily_review_columns = {
        column["name"] for column in inspector.get_columns("live_daily_review_reports")
    }
    approval_record_columns = {
        column["name"] for column in inspector.get_columns("live_approval_records")
    }
    paper_evidence_columns = {
        column["name"] for column in inspector.get_columns("live_paper_evidence_reports")
    }
    approval_packet_columns = {
        column["name"] for column in inspector.get_columns("live_approval_packets")
    }
    broker_statement_columns = {
        column["name"] for column in inspector.get_columns("live_broker_statement_reports")
    }
    profit_milestone_columns = {
        column["name"] for column in inspector.get_columns("live_profit_milestone_reports")
    }
    trade_journal_columns = {
        column["name"] for column in inspector.get_columns("trade_journal_entries")
    }
    paper_evidence_import_columns = {
        column["name"] for column in inspector.get_columns("paper_evidence_import_batches")
    }
    strategy_evidence_review_columns = {
        column["name"] for column in inspector.get_columns("strategy_evidence_reviews")
    }
    prediction_market_columns = {
        column["name"] for column in inspector.get_columns("prediction_markets")
    }
    prediction_contract_columns = {
        column["name"] for column in inspector.get_columns("prediction_contracts")
    }
    prediction_intent_columns = {
        column["name"] for column in inspector.get_columns("prediction_order_intents")
    }
    prediction_order_columns = {
        column["name"] for column in inspector.get_columns("prediction_orders")
    }
    prediction_fill_columns = {
        column["name"] for column in inspector.get_columns("prediction_fills")
    }
    prediction_position_columns = {
        column["name"] for column in inspector.get_columns("prediction_positions")
    }
    prediction_settlement_columns = {
        column["name"] for column in inspector.get_columns("prediction_settlements")
    }
    prediction_reconciliation_columns = {
        column["name"] for column in inspector.get_columns("prediction_reconciliation_reports")
    }
    prediction_evidence_columns = {
        column["name"] for column in inspector.get_columns("prediction_evidence_events")
    }
    strategy_research_candidate_columns = {
        column["name"] for column in inspector.get_columns("strategy_research_candidates")
    }
    strategy_research_observation_columns = {
        column["name"] for column in inspector.get_columns("strategy_research_observations")
    }
    strategy_research_backtest_run_columns = {
        column["name"] for column in inspector.get_columns("strategy_research_backtest_runs")
    }
    assert {
        "symbol",
        "timeframe",
        "source",
        "source_reference",
        "csv_timezone",
        "continuity",
        "data_start",
        "data_end",
        "row_count",
        "evidence_hash",
        "quality_snapshot",
        "imported_at",
    }.issubset(backtest_dataset_columns)
    assert {
        "dataset_id",
        "strategy",
        "strategy_version",
        "engine_version",
        "status",
        "dataset_evidence_hash",
        "engine_evidence_hash",
        "record_evidence_hash",
        "request_snapshot",
        "result_snapshot",
        "recorded_at",
    }.issubset(backtest_reference_replay_columns)
    assert {
        "reference_replay_run_id",
        "protocol_id",
        "dataset_id",
        "strategy",
        "strategy_version",
        "symbol",
        "timeframe",
        "evaluator_version",
        "status",
        "statistical_acceptance_passed",
        "replay_record_evidence_hash",
        "engine_evidence_hash",
        "dataset_evidence_hash",
        "protocol_hash",
        "trade_evidence_hash",
        "validation_evidence_hash",
        "request_snapshot",
        "metrics_snapshot",
        "acceptance_snapshot",
        "binding_snapshot",
        "reason_snapshot",
        "warning_snapshot",
        "recorded_at",
    }.issubset(backtest_reference_validation_columns)
    assert {
        "dataset_id",
        "sequence",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }.issubset(backtest_dataset_candle_columns)
    assert {
        "dataset_id",
        "tradingview_run_id",
        "strategy",
        "strategy_version",
        "engine_version",
        "status",
        "dataset_evidence_hash",
        "tradingview_evidence_hash",
        "replay_evidence_hash",
        "evidence_hash",
        "request_snapshot",
        "summary_snapshot",
        "mismatch_snapshot",
        "reason_snapshot",
        "warning_snapshot",
        "recorded_at",
    }.issubset(backtest_parity_columns)
    assert {
        "protocol_id",
        "protocol_evidence_hash",
        "symbols",
        "timeframe",
        "cost_model",
        "slippage_model",
        "risk_snapshot",
        "source_format",
        "source_reference",
        "evidence_hash",
    }.issubset(backtest_run_columns)
    assert {
        "strategy",
        "strategy_version",
        "symbols",
        "timeframe",
        "protocol_hash",
        "protocol_snapshot",
        "registered_at",
    }.issubset(backtest_protocol_columns)
    assert {
        "breakeven",
        "acceptance_passed",
        "acceptance_reasons",
        "acceptance_snapshot",
    }.issubset(backtest_result_columns)
    assert {
        "backtest_run_id",
        "sequence",
        "external_trade_id",
        "source_format",
        "strategy",
        "symbol",
        "direction",
        "entry_at",
        "closed_at",
        "entry_price",
        "exit_price",
        "quantity",
        "gross_pl",
        "fees",
        "slippage",
        "realized_pl",
        "equity",
        "r_multiple",
        "market_regime",
        "costs_snapshot",
        "raw_row",
    }.issubset(backtest_trade_columns)
    assert {
        "symbol",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }.issubset(market_candle_columns)
    assert {
        "strategy",
        "version",
        "display_name",
        "is_enabled",
        "allowed_regimes",
        "risk_per_trade",
        "minimum_reward_risk",
        "max_open_positions",
    }.issubset(strategy_config_columns)
    assert {
        "trade_id",
        "strategy",
        "symbol",
        "note_type",
        "severity",
        "title",
        "summary",
        "recommendation",
        "confidence",
        "evidence_snapshot",
        "advisory_only",
        "generated_at",
    }.issubset(analyst_note_columns)
    assert {
        "broker_name",
        "environment",
        "status",
        "live_trading_enabled",
        "capabilities",
    }.issubset(broker_connection_columns)
    assert {
        "risk_decision_id",
        "broker_connection_id",
        "strategy",
        "symbol",
        "quantity",
        "requested_price",
        "status",
        "idempotency_key",
    }.issubset(order_intent_columns)
    assert {
        "broker_connection_id",
        "status",
        "summary",
        "discrepancies",
        "broker_snapshot",
        "aurex_snapshot",
    }.issubset(reconciliation_columns)
    assert {
        "check_key",
        "name",
        "status",
        "required",
        "evidence_snapshot",
    }.issubset(readiness_columns)
    assert {
        "broker_connection_id",
        "account_id",
        "strategy",
        "symbols",
        "status",
        "risk_per_trade",
        "max_daily_loss",
        "max_weekly_loss",
        "max_open_positions",
        "target_net_profit",
        "live_trading_enabled",
        "approval_snapshot",
        "rules_snapshot",
    }.issubset(live_deployment_plan_columns)
    assert {
        "live_deployment_plan_id",
        "gate_key",
        "name",
        "status",
        "required",
        "evidence_snapshot",
    }.issubset(live_deployment_gate_columns)
    assert {
        "live_deployment_plan_id",
        "review_date",
        "status",
        "realized_pl",
        "trade_count",
        "rule_violations",
        "reconciliation_status",
        "review_snapshot",
    }.issubset(daily_review_columns)
    assert {
        "live_deployment_plan_id",
        "approval_type",
        "status",
        "approver",
        "evidence_reference",
        "evidence_snapshot",
        "approved_at",
        "revoked_at",
    }.issubset(approval_record_columns)
    assert {
        "live_deployment_plan_id",
        "status",
        "total_trades",
        "minimum_trades",
        "first_trade_at",
        "latest_trade_at",
        "calendar_days_observed",
        "minimum_calendar_days",
        "expectancy",
        "profit_factor",
        "win_rate",
        "max_drawdown",
        "max_allowed_drawdown",
        "unexplained_trade_count",
        "risk_rule_violation_count",
        "journaled_trade_count",
        "unjournaled_trade_count",
        "journal_rule_violation_count",
        "total_net_pl",
        "reasons",
        "requirements_snapshot",
        "evidence_snapshot",
        "generated_at",
    }.issubset(paper_evidence_columns)
    assert {
        "live_deployment_plan_id",
        "status",
        "statement_reference",
        "statement_start_at",
        "statement_end_at",
        "broker_trade_count",
        "aurex_trade_count",
        "broker_net_pl",
        "aurex_net_pl",
        "broker_fees",
        "aurex_fees",
        "broker_slippage",
        "aurex_slippage",
        "discrepancies",
        "statement_snapshot",
        "aurex_snapshot",
        "notes",
        "reconciled_at",
    }.issubset(broker_statement_columns)
    assert {
        "live_deployment_plan_id",
        "status",
        "target_net_profit",
        "total_net_pl",
        "trade_count",
        "first_trade_at",
        "latest_trade_at",
        "journaled_trade_count",
        "unjournaled_trade_count",
        "journal_rule_violation_count",
        "unexplained_trade_count",
        "risk_rule_violation_count",
        "daily_loss_breach_count",
        "weekly_loss_breach_count",
        "broker_statement_report_id",
        "broker_statement_status",
        "kill_switch_enabled",
        "live_execution_adapter_implemented",
        "reasons",
        "requirements_snapshot",
        "evidence_snapshot",
        "generated_at",
    }.issubset(profit_milestone_columns)
    assert {
        "live_deployment_plan_id",
        "broker_connection_id",
        "account_id",
        "status",
        "broker_name",
        "account_label",
        "account_type",
        "asset_class",
        "jurisdiction",
        "currency",
        "broker_terms_reference",
        "fee_schedule_reference",
        "margin_policy_reference",
        "account_constraints_reference",
        "execution_policy_reference",
        "fee_slippage_model_reference",
        "paper_to_live_checklist_reference",
        "sandbox_test_reference",
        "leverage_allowed",
        "credentials_stored",
        "evidence_snapshot",
        "reviewed_at",
    }.issubset(approval_packet_columns)
    assert {
        "paper_trade_id",
        "author",
        "thesis",
        "execution_notes",
        "outcome_notes",
        "rule_followed",
        "emotional_override",
        "evidence_snapshot",
        "journaled_at",
    }.issubset(trade_journal_columns)
    assert {
        "account_id",
        "source",
        "source_reference",
        "import_hash",
        "status",
        "rows_received",
        "imported_count",
        "skipped_count",
        "rejected_count",
        "required_headers",
        "row_results",
        "evidence_snapshot",
        "imported_at",
    }.issubset(paper_evidence_import_columns)
    assert {
        "live_deployment_plan_id",
        "decision",
        "strategy",
        "symbols",
        "summary",
        "reasons",
        "next_actions",
        "gate_snapshot",
        "evidence_snapshot",
        "reviewed_at",
    }.issubset(strategy_evidence_review_columns)
    assert {
        "venue",
        "event_ticker",
        "title",
        "category",
        "status",
        "closes_at",
        "raw_payload",
        "first_seen_at",
        "last_seen_at",
    }.issubset(prediction_market_columns)
    assert {
        "market_id",
        "venue",
        "contract_ticker",
        "title",
        "status",
        "yes_bid_price",
        "yes_ask_price",
        "no_bid_price",
        "no_ask_price",
        "expiration_at",
        "settlement_value",
        "raw_payload",
    }.issubset(prediction_contract_columns)
    assert {
        "contract_id",
        "signal_id",
        "risk_decision_id",
        "broker_connection_id",
        "strategy",
        "side",
        "action",
        "order_type",
        "quantity",
        "limit_price",
        "max_cost",
        "expected_edge",
        "confidence",
        "status",
        "idempotency_key",
        "intent_snapshot",
        "created_intent_at",
        "expires_at",
    }.issubset(prediction_intent_columns)
    assert {
        "order_intent_id",
        "broker_connection_id",
        "external_order_id",
        "status",
        "side",
        "action",
        "quantity",
        "filled_quantity",
        "limit_price",
        "average_fill_price",
        "fees",
        "submitted_at",
        "cancelled_at",
        "external_updated_at",
        "raw_payload",
    }.issubset(prediction_order_columns)
    assert {
        "order_id",
        "external_fill_id",
        "side",
        "action",
        "quantity",
        "price",
        "fees",
        "filled_at",
        "raw_payload",
    }.issubset(prediction_fill_columns)
    assert {
        "account_id",
        "contract_id",
        "side",
        "quantity",
        "average_entry_price",
        "realized_pl",
        "fees",
        "status",
        "opened_at",
        "closed_at",
        "raw_payload",
    }.issubset(prediction_position_columns)
    assert {
        "contract_id",
        "position_id",
        "settlement_value",
        "gross_payout",
        "realized_pl",
        "fees",
        "settled_at",
        "raw_payload",
    }.issubset(prediction_settlement_columns)
    assert {
        "broker_connection_id",
        "status",
        "summary",
        "discrepancies",
        "venue_snapshot",
        "aurex_snapshot",
        "reconciled_at",
    }.issubset(prediction_reconciliation_columns)
    assert {
        "kind",
        "entity_type",
        "entity_id",
        "strategy",
        "contract_ticker",
        "evidence_hash",
        "payload",
        "occurred_at",
    }.issubset(prediction_evidence_columns)
    assert {
        "source",
        "candidate_key",
        "strategy",
        "display_name",
        "hypothesis",
        "status",
        "trade_eligible",
        "eligibility_reason",
        "required_evidence",
        "evidence_hash",
        "source_reference",
        "raw_payload",
        "normalized_payload",
        "first_seen_at",
        "last_seen_at",
    }.issubset(strategy_research_candidate_columns)
    assert {
        "candidate_id",
        "observation_type",
        "source_event_id",
        "symbol",
        "contract_ticker",
        "side",
        "confidence",
        "implied_probability",
        "expected_edge",
        "observation_snapshot",
        "raw_payload",
        "evidence_hash",
        "observed_at",
        "resolved_at",
        "outcome_snapshot",
    }.issubset(strategy_research_observation_columns)
    assert {
        "candidate_id",
        "strategy",
        "accepted",
        "decision",
        "reason",
        "reasons",
        "metrics",
        "requirements",
        "evidence_hash",
        "reviewed_at",
    }.issubset(strategy_research_backtest_run_columns)

    command.downgrade(config, "base")
    inspector = inspect(engine)
    assert REQUIRED_TABLES.isdisjoint(set(inspector.get_table_names()))

    get_settings.cache_clear()


def test_core_models_persist_signal_and_risk_decision() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        account = Account(
            name="paper-main",
            mode="paper",
            currency="USD",
            starting_equity=Decimal("1000"),
            current_equity=Decimal("1000"),
        )
        risk_profile = RiskProfile(account=account, name="default")
        symbol = Symbol(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            asset_class="crypto",
            exchange="paper",
        )
        signal = Signal(
            source="tradingview",
            strategy="trend_pullback_v1",
            symbol_ref=symbol,
            symbol="BTCUSDT",
            timeframe="15m",
            direction=Direction.LONG,
            entry_price=Decimal("68250.50"),
            stop_loss=Decimal("67800.00"),
            take_profit=Decimal("69200.00"),
            market_regime=MarketRegime.TRENDING_UP,
            status=SignalStatus.RECEIVED,
            idempotency_key="trend_pullback_v1:BTCUSDT:15m:LONG:2026-06-05T10:15:00Z",
            raw_payload={"source": "tradingview"},
            normalized_payload={"symbol": "BTCUSDT"},
            source_timestamp=now,
            received_at=now,
        )
        event = SignalEvent(
            signal=signal,
            status=SignalStatus.RECEIVED,
            message="Signal received",
            metadata_json={"stage": "intake"},
        )
        decision = RiskDecision(
            signal=signal,
            risk_profile_id=risk_profile.id,
            approved=True,
            reason="Reward:risk and sizing rules passed",
            reward_risk=Decimal("2.108333"),
            risk_amount=Decimal("5.00"),
            position_size=Decimal("0.011098779134"),
            account_equity=Decimal("1000"),
            rules_snapshot={"risk_per_trade": "0.005"},
        )

        session.add_all([account, risk_profile, symbol, signal, event, decision])
        session.commit()

        saved_signal = session.execute(
            select(Signal).where(Signal.symbol == "BTCUSDT")
        ).scalar_one()

        assert saved_signal.strategy == "trend_pullback_v1"
        assert saved_signal.direction == Direction.LONG
        assert saved_signal.market_regime == MarketRegime.TRENDING_UP
        assert saved_signal.events[0].status == SignalStatus.RECEIVED
        assert saved_signal.risk_decisions[0].approved is True
        assert saved_signal.risk_decisions[0].position_size == Decimal("0.011098779134")
