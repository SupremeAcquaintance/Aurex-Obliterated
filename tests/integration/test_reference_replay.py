from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.reference_replay import (
    OpenReplayPosition,
    atr_series,
    documented_outage_coverage_reasons,
    ema_series,
    higher_timeframe_ema_series,
    resolve_bracket_exit,
    rsi_series,
)
from aurex.backtest_engine.reference_validation import (
    COST_AUDIT_EVALUATOR_VERSION,
    EVALUATOR_VERSION,
    LEGACY_EVALUATOR_VERSION,
    evaluate_reference_replay_validation,
    reference_cost_sensitivity_snapshot,
    reference_metric_trade_inputs,
)
from aurex.backtest_engine.schemas import (
    BacktestTradeInput,
    OhlcvCandle,
    ReferenceReplayValidationRequest,
)
from aurex.backtest_engine.service import calculate_backtest_metrics
from aurex.db.base import Base
from aurex.db.models import (
    BacktestProtocol,
    BacktestReferenceReplayRun,
    BacktestReferenceReplayValidation,
)
from aurex.domain.enums import Direction


def client_fixture() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_session_factory = session_factory
    return TestClient(app)


def replay_candles() -> list[OhlcvCandle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[OhlcvCandle] = []
    for index, close in enumerate(
        [
            Decimal("100"),
            Decimal("101"),
            Decimal("102"),
            Decimal("103"),
            Decimal("104"),
            Decimal("105"),
            Decimal("106"),
            Decimal("107"),
        ]
    ):
        candles.append(
            OhlcvCandle(
                timestamp=start + timedelta(minutes=15 * index),
                open=close - Decimal("0.3"),
                high=close + Decimal("0.2"),
                low=close - Decimal("0.5"),
                close=close,
                volume=Decimal("10"),
            )
        )
    candles.extend(
        [
            OhlcvCandle(
                timestamp=start + timedelta(hours=2),
                open=Decimal("105.5"),
                high=Decimal("105.7"),
                low=Decimal("103.8"),
                close=Decimal("104"),
                volume=Decimal("12"),
            ),
            OhlcvCandle(
                timestamp=start + timedelta(hours=2, minutes=15),
                open=Decimal("104.2"),
                high=Decimal("106.3"),
                low=Decimal("104"),
                close=Decimal("106.1"),
                volume=Decimal("12"),
            ),
            OhlcvCandle(
                timestamp=start + timedelta(hours=2, minutes=30),
                open=Decimal("106.2"),
                high=Decimal("109"),
                low=Decimal("106"),
                close=Decimal("108.5"),
                volume=Decimal("13"),
            ),
            OhlcvCandle(
                timestamp=start + timedelta(hours=2, minutes=45),
                open=Decimal("108.5"),
                high=Decimal("109"),
                low=Decimal("108"),
                close=Decimal("108.8"),
                volume=Decimal("11"),
            ),
            OhlcvCandle(
                timestamp=start + timedelta(hours=3),
                open=Decimal("108.8"),
                high=Decimal("109"),
                low=Decimal("108.4"),
                close=Decimal("108.7"),
                volume=Decimal("10"),
            ),
        ]
    )
    return candles


def candles_csv(candles: list[OhlcvCandle]) -> str:
    rows = ["timestamp,open,high,low,close,volume"]
    rows.extend(
        ",".join(
            [
                candle.timestamp.isoformat().replace("+00:00", "Z"),
                str(candle.open),
                str(candle.high),
                str(candle.low),
                str(candle.close),
                str(candle.volume),
            ]
        )
        for candle in candles
    )
    return "\n".join(rows)


def replay_parameters(*, backtest_start: str = "2026-01-01T02:00:00Z") -> dict:
    return {
        "initial_capital": "1000",
        "backtest_start": backtest_start,
        "backtest_end": "2026-01-01T02:45:00Z",
        "higher_timeframe": "60",
        "pullback_ema_fast": 2,
        "pullback_ema_slow": 3,
        "trend_ema": 3,
        "htf_ema_fast": 1,
        "htf_ema_slow": 2,
        "rsi_length": 2,
        "atr_length": 2,
        "atr_multiplier": "1",
        "reward_risk": "1",
        "swing_lookback": 2,
        "pullback_atr_tolerance": "1",
        "stop_mode": "ATR",
        "risk_per_trade_percent": "0.5",
        "max_position_value_percent": "95",
        "enable_long": True,
        "enable_short": True,
    }


def import_replay_dataset(client: TestClient) -> str:
    response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "reference-replay-fixture",
            "source_reference": "fixture://reference-replay/BTCUSDT/15m",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "csv_text": candles_csv(replay_candles()),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def import_documented_outage_replay_dataset(client: TestClient) -> str:
    candles = replay_candles()
    missing = candles.pop(-2)
    next_observed = candles[-1]
    response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "reference-replay-documented-outage-fixture",
            "source_reference": "fixture://reference-replay/BTCUSDT/15m/outage",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7_with_documented_outages",
            "documented_gaps": [
                {
                    "start": missing.timestamp.isoformat(),
                    "end": next_observed.timestamp.isoformat(),
                    "reason": "Fixture exchange outage removed one complete candle.",
                    "source_reference": "https://status.example.test/incidents/replay",
                }
            ],
            "csv_text": candles_csv(candles),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def replay_payload(dataset_id: str, *, backtest_start: str = "2026-01-01T02:00:00Z") -> dict:
    return {
        "dataset_id": dataset_id,
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "parameters": replay_parameters(backtest_start=backtest_start),
        "tick_size": "0.1",
        "point_value": "1",
        "minimum_contract": "0.001",
        "commission_percent": "0.05",
        "slippage_ticks": 2,
        "intrabar_policy": "stop_first",
    }


def validation_protocol_payload(
    *,
    min_trades: int = 1,
    risk_per_trade: str = "0.005",
    execution_spec: dict[str, str] | None = None,
) -> dict:
    return {
        "strategy": "trend_pullback_v1",
        "strategy_version": "1.3.0",
        "symbols": ["BTCUSDT"],
        "timeframe": "15m",
        "data_source": "tradingview-export",
        "csv_timezone": "UTC",
        "source_reference": "tradingview://strategy-tester/BINANCE:BTCUSDT/15m",
        "data_start": "2026-01-01T02:00:00Z",
        "data_end": "2026-01-01T02:45:00Z",
        "in_sample_start": "2026-01-01T02:00:00Z",
        "in_sample_end": "2026-01-01T02:14:59Z",
        "out_of_sample_start": "2026-01-01T02:15:00Z",
        "out_of_sample_end": "2026-01-01T02:45:00Z",
        "parameters": replay_parameters(),
        "cost_model": {"commission_percent": "0.05"},
        "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
        "risk_snapshot": {
            "risk_per_trade": risk_per_trade,
            **(execution_spec or {}),
        },
        "walk_forward_windows": [],
        "acceptance_criteria": {
            "min_trades": min_trades,
            "min_profit_factor": "1",
            "require_positive_expectancy": True,
            "max_drawdown": "100",
            "require_sample_windows": True,
            "require_out_of_sample_metrics": True,
            "min_out_of_sample_trades": 1,
            "min_out_of_sample_profit_factor": "1",
            "require_out_of_sample_positive_expectancy": True,
            "require_cost_model": True,
            "require_slippage_model": True,
            "require_risk_snapshot": True,
            "require_trade_dates": True,
            "min_active_trading_days": 1,
            "max_single_day_trade_share": "1",
            "require_market_regime_breakdown": True,
            "require_walk_forward_validation": False,
            "min_walk_forward_windows": 1,
            "min_walk_forward_trades_per_window": 1,
            "min_walk_forward_pass_rate": "0",
        },
    }


def record_replay_and_protocol(
    client: TestClient,
    *,
    min_trades: int = 1,
    risk_per_trade: str = "0.005",
    execution_spec: dict[str, str] | None = None,
) -> tuple[str, str]:
    dataset_id = import_replay_dataset(client)
    protocol = client.post(
        "/backtests/protocols",
        json=validation_protocol_payload(
            min_trades=min_trades,
            risk_per_trade=risk_per_trade,
            execution_spec=execution_spec,
        ),
    )
    assert protocol.status_code == 201, protocol.text
    replay = client.post(
        "/backtests/reference-replay/runs",
        json=replay_payload(dataset_id),
    )
    assert replay.status_code == 201, replay.text
    return replay.json()["id"], protocol.json()["id"]


def test_reference_indicator_series_are_causal_and_deterministic() -> None:
    ema = ema_series([Decimal("1"), Decimal("2"), Decimal("3")], 2)
    assert ema[0] == Decimal("1")
    assert abs(ema[1] - Decimal("1.666666666666666666666666667")) < Decimal("1e-26")
    assert abs(ema[2] - Decimal("2.555555555555555555555555556")) < Decimal("1e-26")
    assert rsi_series([Decimal("1"), Decimal("2"), Decimal("1")], 2) == [
        None,
        None,
        Decimal("50"),
    ]
    candles = replay_candles()[:3]
    atr = atr_series(candles, 2)
    assert atr[0] is None
    assert atr[1] == Decimal("0.95")


def test_higher_timeframe_values_use_only_the_previous_confirmed_bar() -> None:
    candles = replay_candles()[:8]
    values = higher_timeframe_ema_series(
        candles,
        base_seconds=900,
        higher_seconds=3600,
        fast_length=1,
        slow_length=2,
    )

    assert values[:4] == [(None, None)] * 4
    assert values[4:] == [(Decimal("103"), Decimal("103"))] * 4


def test_same_bar_stop_and_target_resolve_conservatively_to_stop() -> None:
    position = OpenReplayPosition(
        direction=Direction.LONG,
        entry_at=datetime(2026, 1, 1, tzinfo=UTC),
        signal_price=Decimal("100"),
        entry_price=Decimal("100.2"),
        stop_loss=Decimal("90"),
        take_profit=Decimal("110"),
        quantity=Decimal("1"),
        entry_fee=Decimal("0"),
        entry_slippage=Decimal("0.2"),
        initial_risk=Decimal("10"),
        point_value=Decimal("1"),
        market_regime="TRENDING_UP",
    )
    candle = OhlcvCandle(
        timestamp=datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("111"),
        low=Decimal("89"),
        close=Decimal("100"),
        volume=Decimal("10"),
    )

    fill = resolve_bracket_exit(
        candle,
        position,
        tick_size=Decimal("0.1"),
        slippage_ticks=2,
    )

    assert fill is not None
    assert fill.reason == "STOP_AND_TARGET_AMBIGUOUS"
    assert fill.price == Decimal("89.8")
    assert fill.intrabar_ambiguous is True


def test_reference_validation_drawdown_includes_a_first_trade_loss() -> None:
    trades = [
        BacktestTradeInput(realized_pl=Decimal("-10"), equity=Decimal("990")),
        BacktestTradeInput(realized_pl=Decimal("5"), equity=Decimal("995")),
    ]

    legacy_metrics = calculate_backtest_metrics(
        reference_metric_trade_inputs(
            trades,
            evaluator_version=LEGACY_EVALUATOR_VERSION,
        )
    )
    current_metric_trades = reference_metric_trade_inputs(
        trades,
        evaluator_version=EVALUATOR_VERSION,
    )
    current_metrics = calculate_backtest_metrics(current_metric_trades)

    assert legacy_metrics.max_drawdown == Decimal("0")
    assert current_metrics.max_drawdown == Decimal("10")
    assert all(trade.equity is None for trade in current_metric_trades)
    assert [trade.equity for trade in trades] == [Decimal("990"), Decimal("995")]


def test_reference_cost_sensitivity_reconciles_base_and_scales_costs() -> None:
    trades = [
        BacktestTradeInput(
            realized_pl=Decimal("-11"),
            fees=Decimal("1"),
            slippage=Decimal("2"),
        )
    ]
    replay_metrics = {
        "total_net_pl": "-11",
        "expectancy": "-11",
        "profit_factor": "0",
        "max_drawdown": "11",
    }

    snapshot = reference_cost_sensitivity_snapshot(trades, replay_metrics)
    scenarios = {item["name"]: item for item in snapshot["scenarios"]}

    assert snapshot["gross_before_modeled_costs"] == "-8"
    assert snapshot["base_case_matches_reference_replay"] is True
    assert scenarios["zero_cost_upper_bound"]["total_net_pl"] == "-8"
    assert scenarios["base_case"]["total_net_pl"] == "-11"
    assert scenarios["stress_200_percent"]["total_net_pl"] == "-14"


def test_reference_replay_is_deterministic_comparison_only_and_no_write() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        first = client.post(
            "/backtests/reference-replay/preflight",
            json=replay_payload(dataset_id),
        )
        second = client.post(
            "/backtests/reference-replay/preflight",
            json=replay_payload(dataset_id),
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        body = first.json()
        assert body["status"] == "READY"
        assert body["comparison_only"] is True
        assert body["acceptance_eligible"] is False
        assert body["mutates_ledger"] is False
        assert len(body["engine_evidence_hash"]) == 64
        assert body["engine_evidence_hash"] == second.json()["engine_evidence_hash"]
        assert body["trades"] == second.json()["trades"]
        assert body["metrics"] == second.json()["metrics"]
        assert len(body["trades"]) == 1
        assert body["trades"][0]["direction"] == "LONG"
        assert body["trades"][0]["exit_reason"] == "TAKE_PROFIT"
        assert body["diagnostics"]["long_setups"] == 1
        assert client.get("/backtests/reports").json() == []


def test_reference_replay_records_fully_documented_outage_dataset() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_documented_outage_replay_dataset(client)
        dataset = client.get(f"/backtests/ohlcv/datasets/{dataset_id}")
        assert dataset.status_code == 200, dataset.text
        quality = dataset.json()["quality_snapshot"]
        assert documented_outage_coverage_reasons(quality) == []

        recorded = client.post(
            "/backtests/reference-replay/runs",
            json=replay_payload(dataset_id),
        )

        assert recorded.status_code == 201, recorded.text
        body = recorded.json()
        assert body["status"] == "READY"
        assert body["assumptions"]["dataset_continuity"] == (
            "continuous_24_7_with_documented_outages"
        )
        assert body["assumptions"]["documented_outage_gap_count"] == 1
        assert any("no synthetic candles" in warning for warning in body["warnings"])
        audit = client.get(f"/backtests/reference-replay/runs/{body['id']}/audit")
        assert audit.status_code == 200, audit.text
        assert audit.json()["status"] == "PASS"


def test_documented_outage_replay_reaudit_detects_count_contradiction() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_documented_outage_replay_dataset(client)
        quality = client.get(f"/backtests/ohlcv/datasets/{dataset_id}").json()[
            "quality_snapshot"
        ]

    quality["undocumented_gap_count"] = 1
    assert "documented_outage_count_mismatch" in documented_outage_coverage_reasons(
        quality
    )


def test_reference_replay_blocks_insufficient_pre_window_warmup() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        response = client.post(
            "/backtests/reference-replay/preflight",
            json=replay_payload(dataset_id, backtest_start="2026-01-01T00:00:00Z"),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "BLOCKED"
        assert body["engine_evidence_hash"] is None
        assert body["trades"] == []
        assert "insufficient_pre_window_indicator_warmup" in body["reasons"]
        assert body["acceptance_eligible"] is False


def test_reference_replay_record_is_immutable_idempotent_and_auditable() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        payload = replay_payload(dataset_id)
        first = client.post("/backtests/reference-replay/runs", json=payload)
        second = client.post("/backtests/reference-replay/runs", json=payload)

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        body = first.json()
        assert body["status"] == "READY"
        assert body["immutable"] is True
        assert body["comparison_only"] is True
        assert body["acceptance_eligible"] is False
        assert body["mutates_ledger"] is True
        assert len(body["record_evidence_hash"]) == 64
        assert second.json()["id"] == body["id"]
        assert second.json()["reused_existing"] is True

        listed = client.get("/backtests/reference-replay/runs")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [body["id"]]
        assert "trades" not in listed.json()[0]

        audit = client.get(f"/backtests/reference-replay/runs/{body['id']}/audit")
        assert audit.status_code == 200
        assert audit.json()["status"] == "PASS"
        assert audit.json()["record_evidence_hash_matches"] is True
        assert audit.json()["dataset_evidence_hash_matches"] is True
        assert audit.json()["engine_evidence_hash_matches"] is True
        assert audit.json()["result_snapshot_matches"] is True

        with client.app.state.test_session_factory() as session:
            assert len(
                session.execute(select(BacktestReferenceReplayRun)).scalars().all()
            ) == 1


def test_reference_replay_audit_detects_persisted_result_tampering() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        recorded = client.post(
            "/backtests/reference-replay/runs",
            json=replay_payload(dataset_id),
        )
        assert recorded.status_code == 201, recorded.text
        record_id = recorded.json()["id"]

        with client.app.state.test_session_factory() as session:
            record = session.get(BacktestReferenceReplayRun, record_id)
            assert record is not None
            tampered = dict(record.result_snapshot)
            tampered["metrics"] = {
                **tampered["metrics"],
                "total_net_pl": "999999",
            }
            record.result_snapshot = tampered
            session.commit()

        audit = client.get(f"/backtests/reference-replay/runs/{record_id}/audit")
        assert audit.status_code == 200
        body = audit.json()
        assert body["status"] == "BLOCKED"
        assert body["record_evidence_hash_matches"] is False
        assert body["result_snapshot_matches"] is False
        assert "reference_replay_record_evidence_hash_mismatch" in body["reasons"]
        assert "reference_replay_result_snapshot_drift" in body["reasons"]


def test_blocked_reference_replay_cannot_be_recorded() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        response = client.post(
            "/backtests/reference-replay/runs",
            json=replay_payload(dataset_id, backtest_start="2026-01-01T00:00:00Z"),
        )

        assert response.status_code == 400
        assert "cannot be recorded" in response.json()["detail"]
        assert client.get("/backtests/reference-replay/runs").json() == []


def test_reference_replay_validation_reuses_frozen_statistical_evaluator() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(client)
        payload = {
            "reference_replay_run_id": replay_id,
            "protocol_id": protocol_id,
        }
        preflight = client.post(
            "/backtests/reference-replay/validations/preflight",
            json=payload,
        )
        assert preflight.status_code == 200, preflight.text
        body = preflight.json()
        assert body["status"] == "PASSED"
        assert body["evaluator_version"] == EVALUATOR_VERSION
        assert body["statistical_acceptance_passed"] is True
        assert body["comparison_only"] is True
        assert body["promotion_eligible"] is False
        assert body["paper_eligible"] is False
        assert body["metrics_snapshot"]["out_of_sample"]["total_trades"] == 1
        assert body["metrics_snapshot"]["trade_distribution"][
            "active_trading_days"
        ] == 1
        assert body["metrics_snapshot"]["market_regime_breakdown"][
            "missing_market_regime_count"
        ] == 0
        replay_metrics = client.get(
            f"/backtests/reference-replay/runs/{replay_id}"
        ).json()["metrics"]
        assert body["metrics_snapshot"]["max_drawdown"] == replay_metrics[
            "max_drawdown"
        ]
        assert body["metrics_snapshot"]["drawdown_evidence"][
            "matches_reference_replay"
        ] is True
        sensitivity = body["metrics_snapshot"]["cost_sensitivity"]
        assert sensitivity["base_case_matches_reference_replay"] is True
        scenario_net = {
            item["name"]: Decimal(item["total_net_pl"])
            for item in sensitivity["scenarios"]
        }
        assert scenario_net["zero_cost_upper_bound"] >= scenario_net["base_case"]
        assert scenario_net["base_case"] >= scenario_net["stress_200_percent"]
        assert body["metrics_snapshot"]["sample_assignment"] == {
            "in_sample_trade_count": 0,
            "out_of_sample_trade_count": 1,
            "unassigned_trade_count": 0,
            "purge_gap_start": "2026-01-01T02:14:59+00:00",
            "purge_gap_end": "2026-01-01T02:15:00+00:00",
        }
        assert all(check["status"] == "PASS" for check in body["binding_checks"])

        first = client.post("/backtests/reference-replay/validations", json=payload)
        second = client.post("/backtests/reference-replay/validations", json=payload)
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["reused_existing"] is True

        audit = client.get(
            f"/backtests/reference-replay/validations/{first.json()['id']}/audit"
        )
        assert audit.status_code == 200
        assert audit.json()["status"] == "PASS"
        assert audit.json()["record_evidence_hash_matches"] is True
        assert audit.json()["source_evidence_matches"] is True
        assert audit.json()["evaluation_matches"] is True

        with client.app.state.test_session_factory() as session:
            protocol = session.get(BacktestProtocol, protocol_id)
            assert protocol is not None
            assert protocol.backtest_run is None
            assert len(
                session.execute(
                    select(BacktestReferenceReplayValidation)
                ).scalars().all()
            ) == 1


def test_reference_replay_validation_keeps_legacy_records_auditable() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(client)
        request_payload = {
            "reference_replay_run_id": replay_id,
            "protocol_id": protocol_id,
        }
        recorded = client.post(
            "/backtests/reference-replay/validations",
            json=request_payload,
        )
        assert recorded.status_code == 201, recorded.text
        validation_id = recorded.json()["id"]

        with client.app.state.test_session_factory() as session:
            legacy = evaluate_reference_replay_validation(
                session,
                ReferenceReplayValidationRequest.model_validate(request_payload),
                evaluator_version=LEGACY_EVALUATOR_VERSION,
            )
            record = session.get(BacktestReferenceReplayValidation, validation_id)
            assert record is not None
            assert legacy.validation_evidence_hash is not None
            record.evaluator_version = legacy.evaluator_version
            record.status = legacy.status
            record.statistical_acceptance_passed = legacy.statistical_acceptance_passed
            record.trade_evidence_hash = str(legacy.trade_evidence_hash)
            record.validation_evidence_hash = legacy.validation_evidence_hash
            record.metrics_snapshot = legacy.metrics_snapshot
            record.acceptance_snapshot = legacy.acceptance_snapshot
            record.binding_snapshot = legacy.binding_checks
            record.reason_snapshot = legacy.acceptance_reasons
            record.warning_snapshot = legacy.warnings
            session.commit()

        audit = client.get(
            f"/backtests/reference-replay/validations/{validation_id}/audit"
        )
        assert audit.status_code == 200, audit.text
        assert audit.json()["status"] == "PASS"
        assert audit.json()["record_evidence_hash_matches"] is True
        assert audit.json()["evaluation_matches"] is True


def test_rejected_reference_replay_validation_is_recordable_negative_evidence() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(client, min_trades=2)
        payload = {
            "reference_replay_run_id": replay_id,
            "protocol_id": protocol_id,
        }
        response = client.post(
            "/backtests/reference-replay/validations",
            json=payload,
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "REJECTED"
        assert body["statistical_acceptance_passed"] is False
        assert "Total trades 1 below minimum 2" in body["acceptance_reasons"]
        assert body["immutable"] is True


def test_reference_replay_validation_blocks_protocol_binding_mismatch() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(
            client,
            risk_per_trade="0.01",
        )
        payload = {
            "reference_replay_run_id": replay_id,
            "protocol_id": protocol_id,
        }
        preflight = client.post(
            "/backtests/reference-replay/validations/preflight",
            json=payload,
        )
        record = client.post(
            "/backtests/reference-replay/validations",
            json=payload,
        )

        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "BLOCKED"
        assert "risk_per_trade_mismatch" in preflight.json()["reasons"]
        assert preflight.json()["validation_evidence_hash"] is None
        assert record.status_code == 400
        assert "cannot be recorded" in record.json()["detail"]


def test_reference_replay_validation_binds_declared_execution_spec() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(
            client,
            execution_spec={
                "tick_size": "0.1",
                "point_value": "1",
                "minimum_contract": "0.001",
            },
        )
        preflight = client.post(
            "/backtests/reference-replay/validations/preflight",
            json={
                "reference_replay_run_id": replay_id,
                "protocol_id": protocol_id,
            },
        )

        assert preflight.status_code == 200, preflight.text
        body = preflight.json()
        assert body["status"] == "PASSED"
        binding_by_name = {item["name"]: item for item in body["binding_checks"]}
        assert binding_by_name["tick_size"]["status"] == "PASS"
        assert binding_by_name["point_value"]["status"] == "PASS"
        assert binding_by_name["minimum_contract"]["status"] == "PASS"


def test_reference_replay_validation_blocks_execution_spec_mismatch() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        protocol = client.post(
            "/backtests/protocols",
            json=validation_protocol_payload(
                execution_spec={
                    "tick_size": "0.2",
                    "point_value": "1",
                    "minimum_contract": "0.001",
                }
            ),
        )
        assert protocol.status_code == 201, protocol.text
        replay = client.post(
            "/backtests/reference-replay/runs",
            json=replay_payload(dataset_id),
        )
        assert replay.status_code == 201, replay.text
        preflight = client.post(
            "/backtests/reference-replay/validations/preflight",
            json={
                "reference_replay_run_id": replay.json()["id"],
                "protocol_id": protocol.json()["id"],
            },
        )

        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["status"] == "BLOCKED"
        assert "tick_size_mismatch" in preflight.json()["reasons"]


def test_reference_replay_validation_blocks_protocol_registered_after_replay() -> None:
    client = client_fixture()
    with client:
        dataset_id = import_replay_dataset(client)
        replay = client.post(
            "/backtests/reference-replay/runs",
            json=replay_payload(dataset_id),
        )
        assert replay.status_code == 201, replay.text
        protocol = client.post(
            "/backtests/protocols",
            json=validation_protocol_payload(),
        )
        assert protocol.status_code == 201, protocol.text
        payload = {
            "reference_replay_run_id": replay.json()["id"],
            "protocol_id": protocol.json()["id"],
        }

        current = client.post(
            "/backtests/reference-replay/validations/preflight",
            json=payload,
        )
        recorded = client.post(
            "/backtests/reference-replay/validations",
            json=payload,
        )

        assert current.status_code == 200, current.text
        assert current.json()["status"] == "BLOCKED"
        assert current.json()["metrics_snapshot"] == {}
        assert (
            "protocol_registered_before_reference_replay_mismatch"
            in current.json()["reasons"]
        )
        assert recorded.status_code == 400

        with client.app.state.test_session_factory() as session:
            historical = evaluate_reference_replay_validation(
                session,
                ReferenceReplayValidationRequest.model_validate(payload),
                evaluator_version=COST_AUDIT_EVALUATOR_VERSION,
            )
            assert historical.status == "PASSED"
            assert all(
                check["name"] != "protocol_registered_before_reference_replay"
                for check in historical.binding_checks
            )


def test_reference_replay_validation_audit_detects_metrics_tampering() -> None:
    client = client_fixture()
    with client:
        replay_id, protocol_id = record_replay_and_protocol(client, min_trades=2)
        recorded = client.post(
            "/backtests/reference-replay/validations",
            json={
                "reference_replay_run_id": replay_id,
                "protocol_id": protocol_id,
            },
        )
        assert recorded.status_code == 201, recorded.text
        validation_id = recorded.json()["id"]

        with client.app.state.test_session_factory() as session:
            validation = session.get(
                BacktestReferenceReplayValidation,
                validation_id,
            )
            assert validation is not None
            metrics = dict(validation.metrics_snapshot)
            metrics["out_of_sample"] = {
                **metrics["out_of_sample"],
                "expectancy": "999999",
            }
            validation.metrics_snapshot = metrics
            session.commit()

        audit = client.get(
            f"/backtests/reference-replay/validations/{validation_id}/audit"
        )
        assert audit.status_code == 200
        body = audit.json()
        assert body["status"] == "BLOCKED"
        assert body["record_evidence_hash_matches"] is False
        assert body["source_evidence_matches"] is True
        assert body["evaluation_matches"] is True
        assert "reference_validation_record_evidence_hash_mismatch" in body["reasons"]
        assert "reference_validation_evaluation_drift" not in body["reasons"]
