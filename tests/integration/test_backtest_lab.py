from collections.abc import Generator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.backtest_engine.eligibility import persisted_trade_evidence_reasons
from aurex.backtest_engine.schemas import (
    AcceptanceCriteria,
    BacktestProtocolCreate,
    BacktestReportCreate,
    BacktestTradeInput,
    WalkForwardWindowInput,
)
from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    BacktestLab,
    build_config_hash,
    calculate_backtest_metrics,
    load_ohlcv_csv,
    load_trade_csv,
    strategy_parameter_fingerprint,
)
from aurex.db.base import Base
from aurex.db.models import BacktestProtocol, BacktestRun, BacktestTrade


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db_session:
        yield db_session

    Base.metadata.drop_all(engine)


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def report_payload() -> BacktestReportCreate:
    parameters = dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE)
    return BacktestReportCreate(
        strategy="trend_pullback_v1",
        strategy_version="1.3.0",
        symbols=["BTCUSDT"],
        timeframe="15m",
        data_source="fixture_csv",
        csv_timezone="UTC",
        source_reference="fixture://backtests/trend-pullback-v1",
        data_start=datetime(2026, 1, 1, tzinfo=UTC),
        data_end=datetime(2026, 3, 31, tzinfo=UTC),
        in_sample_start=datetime(2026, 1, 1, tzinfo=UTC),
        in_sample_end=datetime(2026, 2, 15, tzinfo=UTC),
        out_of_sample_start=datetime(2026, 2, 16, tzinfo=UTC),
        out_of_sample_end=datetime(2026, 3, 31, tzinfo=UTC),
        parameters=parameters,
        cost_model={"commission_percent": "0.05"},
        slippage_model={"type": "fixed_bps", "bps": "2"},
        risk_snapshot={"risk_per_trade": "0.005"},
        trades=[
            BacktestTradeInput(
                realized_pl=Decimal("10"),
                closed_at=datetime(2026, 1, 10, tzinfo=UTC),
                market_regime="TRENDING_UP",
            ),
            BacktestTradeInput(
                realized_pl=Decimal("-5"),
                closed_at=datetime(2026, 1, 20, tzinfo=UTC),
                market_regime="TRENDING_UP",
            ),
            BacktestTradeInput(
                realized_pl=Decimal("10"),
                closed_at=datetime(2026, 3, 1, tzinfo=UTC),
                market_regime="TRENDING_UP",
            ),
        ],
        walk_forward_windows=[
            WalkForwardWindowInput(
                window_id="wf-1",
                train_start=datetime(2026, 1, 1, tzinfo=UTC),
                train_end=datetime(2026, 1, 5, tzinfo=UTC),
                test_start=datetime(2026, 1, 6, tzinfo=UTC),
                test_end=datetime(2026, 1, 15, tzinfo=UTC),
                configuration_reference="fixture://walk-forward/wf-1",
                parameters=parameters,
            ),
            WalkForwardWindowInput(
                window_id="wf-2",
                train_start=datetime(2026, 1, 1, tzinfo=UTC),
                train_end=datetime(2026, 1, 15, tzinfo=UTC),
                test_start=datetime(2026, 1, 16, tzinfo=UTC),
                test_end=datetime(2026, 2, 15, tzinfo=UTC),
                configuration_reference="fixture://walk-forward/wf-2",
                parameters=parameters,
            ),
        ],
        acceptance_criteria=AcceptanceCriteria(
            min_trades=2,
            min_profit_factor=Decimal("1.5"),
            max_drawdown=Decimal("5"),
            min_out_of_sample_trades=1,
            min_active_trading_days=2,
            max_single_day_trade_share=Decimal("0.5"),
            min_walk_forward_windows=2,
            min_walk_forward_trades_per_window=1,
            min_walk_forward_pass_rate=Decimal("0.5"),
        ),
    )


def protocol_request_payload(payload: BacktestReportCreate | dict) -> dict:
    if isinstance(payload, BacktestReportCreate):
        request = payload.model_dump(mode="json")
    else:
        request = dict(payload)
    for key in ("protocol_id", "source_format", "csv_format", "csv_text", "trades"):
        request.pop(key, None)
    return request


def register_session_protocol(
    session: Session,
    payload: BacktestReportCreate,
) -> None:
    protocol = BacktestLab(session).register_protocol(
        BacktestProtocolCreate.model_validate(protocol_request_payload(payload))
    )
    payload.protocol_id = protocol.id


def register_client_protocol(client: TestClient, payload: dict) -> dict:
    response = client.post("/backtests/protocols", json=protocol_request_payload(payload))
    assert response.status_code == 201, response.text
    protocol = response.json()
    payload["protocol_id"] = protocol["id"]
    return protocol


def test_backtest_metrics_match_known_fixture_data() -> None:
    metrics = calculate_backtest_metrics(
        [
            BacktestTradeInput(realized_pl=Decimal("10")),
            BacktestTradeInput(realized_pl=Decimal("-5")),
        ]
    )

    assert metrics.total_trades == 2
    assert metrics.wins == 1
    assert metrics.losses == 1
    assert metrics.win_rate == Decimal("0.5")
    assert metrics.average_win == Decimal("10")
    assert metrics.average_loss == Decimal("5")
    assert metrics.expectancy == Decimal("2.5")
    assert metrics.profit_factor == Decimal("2")
    assert metrics.max_drawdown == Decimal("5")
    assert metrics.total_net_pl == Decimal("5")


def test_config_hash_is_deterministic() -> None:
    payload = report_payload()

    assert build_config_hash(payload) == build_config_hash(report_payload())


def test_walk_forward_plan_is_deterministic_chronological_and_read_only(
    client: TestClient,
) -> None:
    payload = {
        "strategy": "trend_pullback_v1",
        "in_sample_start": "2026-01-01T00:00:00Z",
        "in_sample_end": "2026-02-15T00:00:00Z",
        "parameters": TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
        "window_count": 3,
        "initial_training_fraction": "0.333333",
    }

    first = client.post("/backtests/window-plan", json=payload)
    second = client.post("/backtests/window-plan", json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    body = first.json()
    assert second.json() == body
    assert body["status"] == "READY"
    assert body["method"] == "explicit_anchored_fixed_parameter"
    assert body["window_count"] == 3
    assert body["outcome_fields_inspected"] == []
    assert body["mutates_ledger"] is False
    assert len(body["plan_hash"]) == 64
    windows = body["windows"]
    assert windows[0]["train_start"] == "2026-01-01T00:00:00Z"
    assert windows[-1]["test_end"] == "2026-02-15T00:00:00Z"
    for index, window in enumerate(windows):
        assert window["parameters"] == TREND_PULLBACK_V1_PARAMETER_TEMPLATE
        assert datetime.fromisoformat(window["train_start"]) < datetime.fromisoformat(
            window["train_end"]
        )
        assert datetime.fromisoformat(window["train_end"]) < datetime.fromisoformat(
            window["test_start"]
        )
        assert datetime.fromisoformat(window["test_start"]) < datetime.fromisoformat(
            window["test_end"]
        )
        if index:
            assert windows[index - 1]["test_end"] == window["train_end"]
            assert datetime.fromisoformat(windows[index - 1]["test_end"]) < datetime.fromisoformat(
                window["test_start"]
            )
    assert client.get("/backtests/protocols").json() == []
    assert client.get("/backtests/reports").json() == []


@pytest.mark.parametrize(
    ("updates", "expected_detail"),
    [
        (
            {
                "in_sample_start": "2026-02-15T00:00:00Z",
                "in_sample_end": "2026-01-01T00:00:00Z",
            },
            "In-sample start must be before in-sample end",
        ),
        ({"parameters": {}}, "Complete strategy parameters are required"),
    ],
)
def test_walk_forward_plan_rejects_invalid_scope(
    client: TestClient,
    updates: dict,
    expected_detail: str,
) -> None:
    payload = {
        "strategy": "trend_pullback_v1",
        "in_sample_start": "2026-01-01T00:00:00Z",
        "in_sample_end": "2026-02-15T00:00:00Z",
        "parameters": TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
        "window_count": 3,
    }
    payload.update(updates)

    response = client.post("/backtests/window-plan", json=payload)

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


def test_backtest_report_is_stored_with_acceptance_passed(session: Session) -> None:
    payload = report_payload()
    register_session_protocol(session, payload)
    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.config_hash == build_config_hash(report_payload())
    assert run.strategy_version == "1.3.0"
    assert run.cost_model == {"commission_percent": "0.05"}
    assert run.slippage_model == {"type": "fixed_bps", "bps": "2"}
    assert run.result is not None
    assert run.result.total_trades == 3
    assert run.result.profit_factor == Decimal("4.000000")
    assert run.result.acceptance_passed is True
    assert run.result.acceptance_reasons == ["Acceptance gate passed"]
    assert run.result.metrics_snapshot["out_of_sample"]["total_trades"] == 1
    assert run.result.metrics_snapshot["walk_forward"]["window_count"] == 2
    assert run.result.metrics_snapshot["walk_forward"]["passed_windows"] == 1
    assert run.result.metrics_snapshot["trade_distribution"]["active_trading_days"] == 3
    assert run.result.metrics_snapshot["market_regime_breakdown"][
        "missing_market_regime_count"
    ] == 0
    assert run.result.metrics_snapshot["strategy_parameter_evidence"]["complete"] is True
    assert persisted_trade_evidence_reasons(run, run.result) == []


def test_backtest_acceptance_gate_rejects_weak_report(session: Session) -> None:
    payload = report_payload()
    payload.trades = [BacktestTradeInput(realized_pl=Decimal("-5"))]
    payload.acceptance_criteria = AcceptanceCriteria(
        min_trades=2,
        min_profit_factor=Decimal("1.5"),
        max_drawdown=Decimal("2"),
    )

    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.result is not None
    assert run.result.acceptance_passed is False
    assert "Total trades 1 below minimum 2" in run.result.acceptance_reasons
    assert "Expectancy -5 is not positive" in run.result.acceptance_reasons
    assert "Max drawdown 5 exceeds limit 2" in run.result.acceptance_reasons


def test_backtest_acceptance_gate_allows_profitable_report_with_no_losses(
    session: Session,
) -> None:
    payload = report_payload()
    payload.trades = [
        BacktestTradeInput(
            realized_pl=Decimal("5"),
            closed_at=datetime(2026, 1, 10, tzinfo=UTC),
            market_regime="TRENDING_UP",
        ),
        BacktestTradeInput(
            realized_pl=Decimal("5"),
            closed_at=datetime(2026, 1, 20, tzinfo=UTC),
            market_regime="TRENDING_UP",
        ),
        BacktestTradeInput(
            realized_pl=Decimal("10"),
            closed_at=datetime(2026, 3, 1, tzinfo=UTC),
            market_regime="TRENDING_UP",
        ),
    ]
    payload.acceptance_criteria = AcceptanceCriteria(
        min_trades=2,
        min_profit_factor=Decimal("1.5"),
        max_drawdown=Decimal("0"),
        min_out_of_sample_trades=1,
        min_active_trading_days=2,
        max_single_day_trade_share=Decimal("0.5"),
        min_walk_forward_windows=2,
        min_walk_forward_trades_per_window=1,
        min_walk_forward_pass_rate=Decimal("1"),
    )
    register_session_protocol(session, payload)
    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.result is not None
    assert run.result.profit_factor is None
    assert run.result.acceptance_passed is True
    assert run.result.acceptance_reasons == ["Acceptance gate passed"]


def test_backtest_acceptance_gate_rejects_walk_forward_decay(
    session: Session,
) -> None:
    payload = report_payload()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload.trades = [
        BacktestTradeInput(
            realized_pl=Decimal("2"),
            closed_at=start + timedelta(days=index),
            market_regime="TRENDING_UP",
        )
        for index in range(20)
    ] + [
        BacktestTradeInput(
            realized_pl=Decimal("-2"),
            closed_at=start + timedelta(days=20 + index),
            market_regime="TRENDING_UP",
        )
        for index in range(10)
    ]
    payload.acceptance_criteria = AcceptanceCriteria(
        min_trades=30,
        min_profit_factor=Decimal("1.15"),
        max_drawdown=Decimal("50"),
        min_out_of_sample_trades=5,
        min_active_trading_days=15,
        max_single_day_trade_share=Decimal("0.25"),
        min_walk_forward_windows=3,
        min_walk_forward_trades_per_window=5,
        min_walk_forward_pass_rate=Decimal("1"),
    )
    payload.walk_forward_windows = [
        WalkForwardWindowInput(
            window_id="wf-1",
            train_start=start,
            train_end=start + timedelta(days=4),
            test_start=start + timedelta(days=5),
            test_end=start + timedelta(days=9),
            configuration_reference="fixture://walk-forward/wf-1",
            parameters=payload.parameters,
        ),
        WalkForwardWindowInput(
            window_id="wf-2",
            train_start=start,
            train_end=start + timedelta(days=9),
            test_start=start + timedelta(days=10),
            test_end=start + timedelta(days=19),
            configuration_reference="fixture://walk-forward/wf-2",
            parameters=payload.parameters,
        ),
        WalkForwardWindowInput(
            window_id="wf-3",
            train_start=start,
            train_end=start + timedelta(days=19),
            test_start=start + timedelta(days=20),
            test_end=start + timedelta(days=29),
            configuration_reference="fixture://walk-forward/wf-3",
            parameters=payload.parameters,
        ),
    ]

    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.result is not None
    assert run.result.acceptance_passed is False
    assert "Walk-forward pass rate" in " ".join(run.result.acceptance_reasons)
    assert run.result.metrics_snapshot["walk_forward"]["window_count"] == 3
    assert run.result.metrics_snapshot["walk_forward"]["passed_windows"] == 2


def test_backtest_acceptance_rejects_diagnostic_trade_slices(
    session: Session,
) -> None:
    payload = report_payload()
    payload.walk_forward_windows = []

    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.result is not None
    assert run.result.acceptance_passed is False
    snapshot = run.result.metrics_snapshot["walk_forward"]
    assert snapshot["method"] == "chronological_trade_slices"
    assert snapshot["acceptance_eligible"] is False
    assert "automatic trade slices are diagnostic only" in " ".join(
        run.result.acceptance_reasons
    )


def test_backtest_acceptance_rejects_walk_forward_parameter_drift(
    session: Session,
) -> None:
    payload = report_payload()
    drifted_parameters = dict(payload.parameters)
    drifted_parameters["reward_risk"] = "9.0"
    payload.walk_forward_windows[0] = payload.walk_forward_windows[0].model_copy(
        update={"parameters": drifted_parameters}
    )

    run = BacktestLab(session).create_report(payload)
    session.commit()

    assert run.result is not None
    assert run.result.acceptance_passed is False
    snapshot = run.result.metrics_snapshot["walk_forward"]
    assert snapshot["invalid_window_count"] == 1
    assert snapshot["windows"][0]["validation_reasons"] == [
        "walk_forward_strategy_parameters_do_not_match_report"
    ]
    assert "invalid definition" in " ".join(run.result.acceptance_reasons)


def test_csv_adapters_parse_ohlcv_and_trade_data() -> None:
    ohlcv = load_ohlcv_csv(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00Z,100,105,95,102,1234\n"
    )
    trades = load_trade_csv(
        "realized_pl,equity,strategy,market_regime,r_multiple,closed_at\n"
        "10,1010,trend_pullback_v1,TRENDING_UP,2,2026-01-01T01:00:00Z\n"
    )

    assert len(ohlcv) == 1
    assert ohlcv[0].close == Decimal("102")
    assert len(trades) == 1
    assert trades[0].realized_pl == Decimal("10")
    assert trades[0].strategy == "trend_pullback_v1"


def test_backtest_api_creates_and_exports_report(client: TestClient) -> None:
    payload = report_payload().model_dump(mode="json")
    protocol = register_client_protocol(client, payload)

    response = client.post("/backtests/reports", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["strategy"] == "trend_pullback_v1"
    assert body["protocol_id"] == protocol["id"]
    assert body["protocol_evidence_hash"] == protocol["protocol_hash"]
    assert body["config_hash"]
    assert body["result"]["total_trades"] == 3
    assert body["result"]["acceptance_passed"] is True

    list_response = client.get("/backtests/reports")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    csv_response = client.get(f"/backtests/reports/{body['id']}/csv")
    assert csv_response.status_code == 200
    assert "config_hash" in csv_response.text
    assert "acceptance_passed,True" in csv_response.text


def test_backtest_protocol_registration_is_idempotent_and_immutable(
    client: TestClient,
) -> None:
    payload = report_payload().model_dump(mode="json")
    request = protocol_request_payload(payload)

    first = client.post("/backtests/protocols", json=request)
    second = client.post("/backtests/protocols", json=request)
    listed = client.get("/backtests/protocols")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "REGISTERED"
    assert first.json()["immutable"] is True
    assert first.json()["protocol_hash"]
    assert first.json()["protocol_snapshot"]["strategy"] == "trend_pullback_v1"
    source = first.json()["protocol_snapshot"]["strategy_source_evidence"]
    assert source["ready"] is True
    assert source["pine_version"] == "1.3.0"
    assert len(source["pine_source_sha256"]) == 64
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_current_tradingview_protocol_has_ready_source_bound_run_manifest(
    client: TestClient,
) -> None:
    payload = report_payload().model_dump(mode="json")
    payload.update(
        {
            "data_source": "tradingview-export",
            "source_reference": "tradingview://strategy-tester/BINANCE:BTCUSDT/15m",
            "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
        }
    )
    protocol = register_client_protocol(client, payload)

    response = client.get(
        f"/backtests/protocols/{protocol['id']}/run-manifest"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["protocol_status"] == "REGISTERED"
    assert body["strategy_version"] == "1.3.0"
    assert body["symbol"] == "BTCUSDT"
    assert body["tradingview_setup"]["chart"]["ticker_id"] == "BINANCE:BTCUSDT"
    assert body["source_evidence"]["ready"] is True
    assert len(body["source_evidence"]["pine_source_sha256"]) == 64
    assert len(body["manifest_hash"]) == 64
    assert all(check["passed"] for check in body["checks"])
    assert body["tradingview_setup"]["inputs"] == payload["parameters"]
    assert body["mutates_ledger"] is False

    package_response = client.get(
        f"/backtests/protocols/{protocol['id']}/tradingview-run-package"
    )
    assert package_response.status_code == 200
    run_package = package_response.json()
    pine_source = Path("pine/strategies/trend_pullback_v1.pine").read_bytes().decode(
        "utf-8"
    )
    assert run_package["status"] == "READY"
    assert run_package["protocol_id"] == protocol["id"]
    assert run_package["manifest_hash"] == body["manifest_hash"]
    assert len(run_package["package_hash"]) == 64
    assert run_package["ticker_id"] == "BINANCE:BTCUSDT"
    assert run_package["pine_source"] == pine_source
    assert run_package["pine_source_sha256"] == body["source_evidence"][
        "pine_source_sha256"
    ]
    assert run_package["source_byte_length"] == Path(
        "pine/strategies/trend_pullback_v1.pine"
    ).stat().st_size
    assert run_package["source_line_count"] == len(pine_source.splitlines())
    assert run_package["tradingview_url"].endswith("BINANCE%3ABTCUSDT")
    assert run_package["mutates_ledger"] is False

    consumed_payload = dict(payload)
    consumed_payload["protocol_id"] = protocol["id"]
    consumed = client.post("/backtests/reports", json=consumed_payload)
    assert consumed.status_code == 201, consumed.text
    consumed_package_response = client.get(
        f"/backtests/protocols/{protocol['id']}/tradingview-run-package"
    )
    assert consumed_package_response.status_code == 200
    consumed_package = consumed_package_response.json()
    assert consumed_package["status"] == "BLOCKED"
    assert "protocol_unconsumed" in consumed_package["reasons"]
    assert consumed_package["manifest_hash"] == run_package["manifest_hash"]
    assert consumed_package["package_hash"] == run_package["package_hash"]
    assert consumed_package["pine_source_sha256"] == run_package["pine_source_sha256"]


def test_tradingview_protocol_rejects_unqualified_exchange_reference(
    client: TestClient,
) -> None:
    payload = report_payload().model_dump(mode="json")
    payload.update(
        {
            "data_source": "tradingview-export",
            "source_reference": "tradingview://strategy-tester/BTCUSDT/15m",
            "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
        }
    )

    response = client.post(
        "/backtests/protocols",
        json=protocol_request_payload(payload),
    )

    assert response.status_code == 400
    assert "<VENUE>:<SYMBOL>" in response.json()["detail"]


def test_run_manifest_blocks_recorded_pine_source_drift(session: Session) -> None:
    payload = report_payload()
    payload.data_source = "tradingview-export"
    payload.source_reference = "tradingview://strategy-tester/BINANCE:BTCUSDT/15m"
    payload.slippage_model = {"type": "fixed_ticks", "ticks": "2"}
    protocol = BacktestLab(session).register_protocol(
        BacktestProtocolCreate.model_validate(protocol_request_payload(payload))
    )
    snapshot = deepcopy(protocol.protocol_snapshot)
    snapshot["strategy_source_evidence"]["pine_source_sha256"] = "0" * 64
    protocol.protocol_snapshot = snapshot

    manifest = BacktestLab(session).run_manifest(protocol)

    assert manifest["status"] == "BLOCKED"
    assert "protocol_integrity" in manifest["reasons"]
    assert "pine_source_current" in manifest["reasons"]


def test_backtest_without_protocol_is_stored_but_cannot_be_accepted(
    client: TestClient,
) -> None:
    response = client.post(
        "/backtests/reports",
        json=report_payload().model_dump(mode="json"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["protocol_id"] is None
    assert body["result"]["acceptance_passed"] is False
    assert "must be registered before report evaluation" in " ".join(
        body["result"]["acceptance_reasons"]
    )
    protocol = body["result"]["metrics_snapshot"]["backtest_protocol"]
    assert protocol["status"] == "BLOCKED"
    assert protocol["reasons"] == ["backtest_protocol_missing"]


def test_backtest_protocol_mismatch_does_not_consume_protocol(
    client: TestClient,
) -> None:
    payload = report_payload().model_dump(mode="json")
    protocol = register_client_protocol(client, payload)
    mismatched = deepcopy(payload)
    mismatched["timeframe"] = "30m"

    rejected = client.post("/backtests/reports", json=mismatched)
    available = client.get(f"/backtests/protocols/{protocol['id']}")

    assert rejected.status_code == 201
    assert rejected.json()["result"]["acceptance_passed"] is False
    assert "do not match the registered protocol" in " ".join(
        rejected.json()["result"]["acceptance_reasons"]
    )
    assert rejected.json()["protocol_id"] is None
    assert available.status_code == 200
    assert available.json()["status"] == "REGISTERED"


def test_backtest_protocol_is_single_use(client: TestClient) -> None:
    payload = report_payload().model_dump(mode="json")
    protocol = register_client_protocol(client, payload)

    first = client.post("/backtests/reports", json=payload)
    second = client.post("/backtests/reports", json=payload)
    consumed = client.get(f"/backtests/protocols/{protocol['id']}")

    assert first.status_code == 201
    assert first.json()["result"]["acceptance_passed"] is True
    assert second.status_code == 201
    assert second.json()["result"]["acceptance_passed"] is False
    assert "already been consumed" in " ".join(
        second.json()["result"]["acceptance_reasons"]
    )
    assert consumed.json()["status"] == "CONSUMED"
    assert consumed.json()["consumed_by_run_id"] == first.json()["id"]


def test_backtest_strategy_setup_returns_core_pine_contract(
    client: TestClient,
) -> None:
    response = client.get(
        "/backtests/strategy-setup?strategy=trend_pullback_v1&symbol=btcusdt&timeframe=30m"
    )

    assert response.status_code == 200
    body = response.json()
    expected_fingerprint = strategy_parameter_fingerprint(
        "trend_pullback_v1",
        TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    )
    assert body["strategy"] == "trend_pullback_v1"
    assert body["strategy_version"] == "1.3.0"
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "30m"
    assert body["pine_path"] == "pine/strategies/trend_pullback_v1.pine"
    assert body["docs_path"] == "docs/pine/trend_pullback_v1.md"
    assert body["strategy_source_evidence"]["ready"] is True
    assert len(body["strategy_source_evidence"]["pine_source_sha256"]) == 64
    assert body["venue"] == "BINANCE"
    assert body["ticker_id"] == "BINANCE:BTCUSDT"
    assert body["source_reference"] == (
        "tradingview://strategy-tester/BINANCE:BTCUSDT/30m"
    )
    assert body["parameters"] == TREND_PULLBACK_V1_PARAMETER_TEMPLATE
    assert body["settings_fingerprint"] == expected_fingerprint
    assert body["required_parameters"] == list(TREND_PULLBACK_V1_PARAMETER_TEMPLATE)
    assert body["cost_model"] == {"commission_percent": "0.05"}
    assert body["slippage_model"] == {"type": "fixed_ticks", "ticks": "2"}
    assert body["risk_snapshot"] == {"risk_per_trade": "0.005"}
    assert body["walk_forward_method"] == "explicit_anchored_fixed_parameter"
    assert body["walk_forward_windows"] == []
    assert body["acceptance_criteria"]["min_trades"] == 100
    assert body["acceptance_criteria"]["min_out_of_sample_trades"] == 30
    assert body["acceptance_criteria"]["min_walk_forward_windows"] == 3
    assert body["mutates_ledger"] is False
    assert "completed-trades CSV" in body["next_actions"][2]


def backtest_report_csv_payload(csv_text: str) -> dict:
    payload = report_payload().model_dump(mode="json", exclude={"trades"})
    payload["csv_text"] = csv_text
    return payload


def backtest_report_csv() -> str:
    return "\n".join(
        [
            "realized_pl,closed_at,market_regime,strategy,symbol,equity,r_multiple",
            (
                "10,2026-01-10T00:00:00Z,TRENDING_UP,trend_pullback_v1,"
                "BTCUSDT,1010,2"
            ),
            (
                "-5,2026-01-20T00:00:00Z,TRENDING_UP,trend_pullback_v1,"
                "BTCUSDT,1005,-1"
            ),
            (
                "10,2026-03-01T00:00:00Z,TRENDING_UP,trend_pullback_v1,"
                "BTCUSDT,1015,2"
            ),
        ]
    )


def tradingview_completed_trades_csv() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "tradingview_completed_trades.csv"
    ).read_text(encoding="utf-8")


def tradingview_csv_payload(csv_text: str) -> dict:
    payload = report_payload().model_dump(mode="json", exclude={"trades", "source_format"})
    payload.update(
        {
            "data_source": "tradingview-export",
            "csv_format": "auto",
            "csv_timezone": "UTC",
            "source_reference": "tradingview://strategy-tester/BINANCE:BTCUSDT/15m",
            "slippage_model": {"type": "fixed_ticks", "ticks": "2"},
            "csv_text": csv_text,
        }
    )
    payload["walk_forward_windows"] = [
        {
            "window_id": "wf-1",
            "train_start": "2026-01-01T00:00:00Z",
            "train_end": "2026-01-15T00:00:00Z",
            "test_start": "2026-01-16T00:00:00Z",
            "test_end": "2026-01-25T00:00:00Z",
            "configuration_reference": "fixture://tradingview/wf-1",
            "parameters": dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE),
        },
        {
            "window_id": "wf-2",
            "train_start": "2026-01-01T00:00:00Z",
            "train_end": "2026-01-25T00:00:00Z",
            "test_start": "2026-01-26T00:00:00Z",
            "test_end": "2026-02-04T00:00:00Z",
            "configuration_reference": "fixture://tradingview/wf-2",
            "parameters": dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE),
        },
        {
            "window_id": "wf-3",
            "train_start": "2026-01-01T00:00:00Z",
            "train_end": "2026-02-04T00:00:00Z",
            "test_start": "2026-02-05T00:00:00Z",
            "test_end": "2026-02-15T00:00:00Z",
            "configuration_reference": "fixture://tradingview/wf-3",
            "parameters": dict(TREND_PULLBACK_V1_PARAMETER_TEMPLATE),
        },
    ]
    return payload


def strong_tradingview_completed_trades_csv() -> str:
    header = (
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,"
        "Commission USD,Slippage USD,Cumulative P&L USD,Symbol"
    )
    rows = [header]
    cumulative = Decimal("0")
    in_sample_start = datetime(2026, 1, 1, tzinfo=UTC)
    out_of_sample_start = datetime(2026, 2, 16, tzinfo=UTC)
    for index in range(100):
        closed_at = (
            in_sample_start + timedelta(days=index % 45)
            if index < 50
            else out_of_sample_start + timedelta(days=(index - 50) % 44)
        )
        entry_at = closed_at - timedelta(minutes=15)
        realized_pl = Decimal("-1") if index % 4 == 0 else Decimal("2")
        cumulative += realized_pl
        trade_number = index + 1
        exit_price = "102" if realized_pl > 0 else "99"
        rows.append(
            f"{trade_number},Entry long,AUREX-LONG-TRENDING_UP,"
            f"{entry_at.strftime('%Y-%m-%d %H:%M:%S')},100,1,,,,,BTCUSDT"
        )
        rows.append(
            f"{trade_number},Exit long,AUREX-LONG-EXIT,"
            f"{closed_at.strftime('%Y-%m-%d %H:%M:%S')},{exit_price},1,"
            f"{realized_pl},0.05,0.02,{cumulative},BTCUSDT"
        )
    return "\n".join(rows)


def test_backtest_report_csv_preflight_and_import_create_report(
    client: TestClient,
) -> None:
    payload = backtest_report_csv_payload(backtest_report_csv())
    register_client_protocol(client, payload)

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    reports_before_import = client.get("/backtests/reports")
    imported = client.post("/backtests/reports/import-csv", json=payload)
    reports_after_import = client.get("/backtests/reports")
    template = client.get("/backtests/report-template.csv")

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["rows_received"] == 3
    assert preflight_body["importable_count"] == 3
    assert preflight_body["rejected_count"] == 0
    assert preflight_body["analysis_summary"]["acceptance_passed"] is True
    assert preflight_body["analysis_summary"]["metrics_snapshot"]["out_of_sample"][
        "total_trades"
    ] == 1
    assert reports_before_import.status_code == 200
    assert reports_before_import.json() == []

    assert imported.status_code == 201
    imported_body = imported.json()
    assert imported_body["result"]["acceptance_passed"] is True
    assert imported_body["result"]["metrics_snapshot"]["trade_distribution"][
        "active_trading_days"
    ] == 3
    assert reports_after_import.status_code == 200
    assert len(reports_after_import.json()) == 1
    assert template.status_code == 200
    assert "realized_pl,closed_at,market_regime" in template.text


def test_tradingview_completed_trades_preflight_import_and_persistence(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(tradingview_completed_trades_csv())

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["source_format"] == "tradingview"
    assert len(preflight_body["source_artifact_hash"]) == 64
    assert preflight_body["rows_received"] == 4
    assert preflight_body["importable_count"] == 2
    assert preflight_body["rejected_count"] == 0
    assert preflight_body["analysis_summary"]["status_counts"] == {
        "READY": 2,
        "SKIPPED": 2,
    }
    assert preflight_body["analysis_summary"]["acceptance_passed"] is False
    assert any(
        reason.startswith("Walk-forward pass rate")
        for reason in preflight_body["analysis_summary"]["acceptance_reasons"]
    )
    assert preflight_body["analysis_summary"]["metrics_snapshot"]["cost_evidence"] == {
        "realized_pl_semantics": "reported_net_pl",
        "trade_count": 2,
        "fees_provided_count": 2,
        "fees_missing_count": 0,
        "slippage_provided_count": 2,
        "slippage_missing_count": 0,
        "cost_model_declared": True,
        "slippage_model_declared": True,
        "missing_trade_costs_are_not_assumed_zero": True,
    }

    assert imported.status_code == 201
    imported_body = imported.json()
    assert imported_body["source_format"] == "tradingview"
    assert imported_body["source_artifact_hash"] == preflight_body[
        "source_artifact_hash"
    ]
    assert imported_body["source_reference"] == (
        "tradingview://strategy-tester/BINANCE:BTCUSDT/15m"
    )
    assert imported_body["evidence_hash"] == preflight_body["evidence_hash"]
    assert imported_body["result"]["total_trades"] == 2
    assert imported_body["result"]["acceptance_passed"] is False

    persisted = client.get(f"/backtests/reports/{imported_body['id']}/trades")
    assert persisted.status_code == 200
    trades = persisted.json()
    assert len(trades) == 2
    assert trades[0]["external_trade_id"] == "1"
    assert trades[0]["direction"] == "LONG"
    assert trades[0]["market_regime"] == "TRENDING_UP"
    assert trades[0]["entry_price"] == "100.00000000"
    assert trades[0]["exit_price"] == "95.00000000"
    assert trades[0]["fees"] == "0.10000000"
    assert trades[0]["slippage"] == "0.05000000"
    assert trades[0]["costs_snapshot"]["fees_status"] == "PROVIDED"
    assert trades[1]["external_trade_id"] == "2"
    assert trades[1]["direction"] == "SHORT"
    assert trades[1]["market_regime"] == "TRENDING_DOWN"


def test_tradingview_import_rejects_missing_semantic_headers(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(
        "Trade #,Type,Signal,Date/Time,Price USD\n"
        "1,Exit long,AUREX-LONG-TRENDING_UP,2026-01-10 11:00:00,95\n"
    )
    payload["csv_format"] = "tradingview"

    response = client.post("/backtests/reports/preflight-csv", json=payload)

    assert response.status_code == 400
    assert "TradingView completed-trades CSV must provide semantic fields" in (
        response.json()["detail"]
    )


def test_backtest_import_rejects_header_only_csv(client: TestClient) -> None:
    payload = tradingview_csv_payload(
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD\n"
    )

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["status"] == "REJECTED"
    assert body["rows_received"] == 0
    assert body["importable_count"] == 0
    assert body["rejected_count"] == 0
    assert body["analysis_summary"]["diagnostic"]["status"] == (
        "NO_COMPLETED_TRADE_ROWS"
    )
    assert body["analysis_summary"]["diagnostic"]["reasons"] == [
        "csv_contains_headers_but_no_trade_rows"
    ]
    assert "Pine strategy creates closed trades" in body["analysis_summary"][
        "diagnostic"
    ]["next_action"]
    assert imported.status_code == 400
    assert "must be READY" in imported.json()["detail"]


def test_tradingview_entry_rows_without_exits_return_no_trade_diagnostic(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(
        "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,Symbol\n"
        "1,Entry long,AUREX-LONG-TRENDING_UP,2026-01-10 10:00:00,100,1,,BTCUSDT\n"
    )

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["status"] == "REJECTED"
    assert body["rows_received"] == 1
    assert body["importable_count"] == 0
    assert body["rejected_count"] == 1
    assert body["analysis_summary"]["fix_queue"] == [
        {"reason": "entry_row_missing_completed_exit", "count": 1, "rows": [2]}
    ]
    assert body["analysis_summary"]["diagnostic"]["status"] == (
        "ENTRY_ROWS_WITHOUT_COMPLETED_EXITS"
    )
    assert body["analysis_summary"]["diagnostic"]["reasons"] == [
        "tradingview_entries_have_no_completed_exits"
    ]
    assert "completed TradingView trades" in body["analysis_summary"]["diagnostic"][
        "next_action"
    ]
    assert imported.status_code == 400
    assert "must be READY" in imported.json()["detail"]


def test_one_trade_tradingview_backtest_imports_but_fails_evidence_gate(
    client: TestClient,
) -> None:
    rows = tradingview_completed_trades_csv().splitlines()
    payload = tradingview_csv_payload("\n".join(rows[:3]))

    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert imported.status_code == 201
    result = imported.json()["result"]
    assert result["total_trades"] == 1
    assert result["acceptance_passed"] is False
    assert "Total trades 1 below minimum 2" in result["acceptance_reasons"]
    assert "Out-of-sample trades 0 below minimum 1" in result["acceptance_reasons"]


def test_small_tradingview_sample_fails_production_evidence_thresholds(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")

    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert imported.status_code == 201
    result = imported.json()["result"]
    assert result["acceptance_passed"] is False
    assert "Total trades 2 below minimum 100" in result["acceptance_reasons"]
    assert "Out-of-sample trades 1 below minimum 30" in result["acceptance_reasons"]


def test_strong_tradingview_fixture_passes_only_when_all_gates_are_met(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    register_client_protocol(client, payload)

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["importable_count"] == 100
    assert preflight_body["analysis_summary"]["acceptance_passed"] is True
    assert preflight_body["analysis_summary"]["acceptance_reasons"] == [
        "Acceptance gate passed"
    ]

    assert imported.status_code == 201
    body = imported.json()
    snapshot = body["result"]["metrics_snapshot"]
    assert body["result"]["acceptance_passed"] is True
    assert body["result"]["total_trades"] == 100
    assert snapshot["out_of_sample"]["total_trades"] == 50
    assert Decimal(snapshot["out_of_sample"]["expectancy"]) > 0
    assert Decimal(snapshot["out_of_sample"]["profit_factor"]) >= Decimal("1.15")
    assert snapshot["walk_forward"]["window_count"] == 3
    assert Decimal(snapshot["walk_forward"]["pass_rate"]) >= Decimal("0.66")
    assert snapshot["trade_distribution"]["active_trading_days"] >= 15
    assert Decimal(snapshot["trade_distribution"]["max_single_day_trade_share"]) <= (
        Decimal("0.25")
    )
    assert snapshot["market_regime_breakdown"]["missing_market_regime_count"] == 0

    persisted = client.get(f"/backtests/reports/{body['id']}/trades?limit=500")
    assert persisted.status_code == 200
    assert len(persisted.json()) == 100

    deployment = client.get("/live/deployment").json()
    gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
    accepted_gate = gates["accepted_backtest_complete"]
    assert accepted_gate["status"] == "PASS"
    assert accepted_gate["evidence_snapshot"]["live_readiness_reasons"] == []
    source_evidence = accepted_gate["evidence_snapshot"]["source_evidence"]
    assert source_evidence["policy"] == "core_pine_tradingview_export_v2"
    assert source_evidence["trusted"] is True


def test_known_pine_backtest_requires_complete_strategy_parameters(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    payload["parameters"] = {"reward_risk": "2.0"}

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)

    assert preflight.status_code == 200
    preflight_body = preflight.json()
    assert preflight_body["status"] == "READY"
    assert preflight_body["analysis_summary"]["acceptance_passed"] is False
    assert preflight_body["analysis_summary"]["diagnostic"]["status"] == (
        "EVIDENCE_GATE_BLOCKED"
    )
    assert any(
        reason.startswith("Strategy parameters missing for trend_pullback_v1")
        for reason in preflight_body["analysis_summary"]["acceptance_reasons"]
    )
    parameter_evidence = preflight_body["analysis_summary"]["metrics_snapshot"][
        "strategy_parameter_evidence"
    ]
    assert parameter_evidence["complete"] is False
    assert "pullback_ema_fast" in parameter_evidence["missing_parameters"]
    assert imported.status_code == 201
    assert imported.json()["result"]["acceptance_passed"] is False


def test_persisted_backtest_parameter_tampering_blocks_live_evidence_gate(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    register_client_protocol(client, payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)
    assert imported.status_code == 201
    run_id = imported.json()["id"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None
        run.parameters = {"reward_risk": "2.0"}
        session.commit()

    deployment = client.get("/live/deployment").json()
    gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
    accepted_gate = gates["accepted_backtest_complete"]
    assert accepted_gate["status"] == "BLOCKED"
    evidence = accepted_gate["evidence_snapshot"]
    assert "accepted_backtest_strategy_parameters_missing" in evidence[
        "live_readiness_reasons"
    ]
    assert evidence["strategy_parameter_evidence"]["complete"] is False
    assert "pullback_ema_fast" in evidence["strategy_parameter_evidence"][
        "missing_parameters"
    ]


def test_persisted_backtest_trade_tampering_blocks_live_evidence_gate(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    register_client_protocol(client, payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)
    assert imported.status_code == 201
    run_id = imported.json()["id"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        trade = session.execute(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_run_id == run_id)
            .order_by(BacktestTrade.sequence.asc())
            .limit(1)
        ).scalar_one()
        trade.realized_pl = trade.realized_pl + Decimal("1")
        session.commit()

    deployment = client.get("/live/deployment").json()
    gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
    accepted_gate = gates["accepted_backtest_complete"]
    assert accepted_gate["status"] == "BLOCKED"
    assert "accepted_backtest_persisted_trade_hash_mismatch" in accepted_gate[
        "evidence_snapshot"
    ]["live_readiness_reasons"]


def test_walk_forward_snapshot_tampering_blocks_live_evidence_gate(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    register_client_protocol(client, payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)
    assert imported.status_code == 201
    run_id = imported.json()["id"]

    with next(client.app.dependency_overrides[get_db]()) as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None
        assert run.result is not None
        metrics_snapshot = deepcopy(run.result.metrics_snapshot)
        metrics_snapshot["walk_forward"]["windows"][0]["summary"]["expectancy"] = "999"
        run.result.metrics_snapshot = metrics_snapshot
        session.commit()

    deployment = client.get("/live/deployment").json()
    gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
    accepted_gate = gates["accepted_backtest_complete"]
    assert accepted_gate["status"] == "BLOCKED"
    assert "accepted_backtest_walk_forward_evidence_hash_mismatch" in accepted_gate[
        "evidence_snapshot"
    ]["live_readiness_reasons"]


def test_backtest_protocol_tampering_blocks_live_evidence_gate(
    client: TestClient,
) -> None:
    payload = tradingview_csv_payload(strong_tradingview_completed_trades_csv())
    payload["acceptance_criteria"] = AcceptanceCriteria(
        max_drawdown=Decimal("50")
    ).model_dump(mode="json")
    protocol = register_client_protocol(client, payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)
    assert imported.status_code == 201
    assert imported.json()["result"]["acceptance_passed"] is True

    with next(client.app.dependency_overrides[get_db]()) as session:
        record = session.get(BacktestProtocol, protocol["id"])
        assert record is not None
        snapshot = deepcopy(record.protocol_snapshot)
        snapshot["timeframe"] = "1m"
        record.protocol_snapshot = snapshot
        session.commit()

    deployment = client.get("/live/deployment").json()
    gates = {gate["gate_key"]: gate for gate in deployment["gates"]}
    accepted_gate = gates["accepted_backtest_complete"]
    assert accepted_gate["status"] == "BLOCKED"
    assert "accepted_backtest_protocol_integrity_mismatch" in accepted_gate[
        "evidence_snapshot"
    ]["live_readiness_reasons"]


def test_tradingview_missing_cost_columns_are_explicit_not_zero(
    client: TestClient,
) -> None:
    csv_text = "\n".join(
        [
            "Trade #,Type,Signal,Date/Time,Price USD,Contracts,Net P&L USD,Symbol",
            (
                "1,Entry long,AUREX-LONG-TRENDING_UP,2026-01-10 10:00:00,"
                "100,1,,BTCUSDT"
            ),
            (
                "1,Exit long,AUREX-LONG-EXIT,2026-01-10 11:00:00,"
                "105,1,5,BTCUSDT"
            ),
        ]
    )
    payload = tradingview_csv_payload(csv_text)

    imported = client.post("/backtests/reports/import-csv", json=payload)
    assert imported.status_code == 201
    body = imported.json()
    cost_evidence = body["result"]["metrics_snapshot"]["cost_evidence"]
    assert cost_evidence["fees_missing_count"] == 1
    assert cost_evidence["slippage_missing_count"] == 1
    assert cost_evidence["missing_trade_costs_are_not_assumed_zero"] is True

    trade = client.get(f"/backtests/reports/{body['id']}/trades").json()[0]
    assert trade["fees"] is None
    assert trade["slippage"] is None
    assert trade["costs_snapshot"]["fees_status"] == "MISSING"
    assert trade["costs_snapshot"]["slippage_status"] == "MISSING"


def test_backtest_report_csv_preflight_flags_bad_rows_without_report(
    client: TestClient,
) -> None:
    bad_csv = "\n".join(
        [
            "realized_pl,closed_at,market_regime,strategy,symbol,equity,r_multiple",
            "10,2026-03-01T00:00:00Z,TRENDING_UP,other_strategy,BTCUSDT,1010,2",
            "-5,2026-01-10T00:00:00Z,,trend_pullback_v1,ETHUSDT,1005,-1",
        ]
    )
    payload = backtest_report_csv_payload(bad_csv)

    preflight = client.post("/backtests/reports/preflight-csv", json=payload)
    imported = client.post("/backtests/reports/import-csv", json=payload)
    reports = client.get("/backtests/reports")

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["status"] == "REJECTED"
    assert body["importable_count"] == 0
    assert body["rejected_count"] == 2
    assert body["analysis_summary"]["rejected_reasons"] == {
        "market_regime_is_required": 1,
        "strategy_does_not_match_report": 1,
    }
    assert body["analysis_summary"]["fix_queue"] == [
        {"reason": "market_regime_is_required", "count": 1, "rows": [3]},
        {"reason": "strategy_does_not_match_report", "count": 1, "rows": [2]},
    ]
    assert imported.status_code == 400
    assert "must be READY" in imported.json()["detail"]
    assert reports.status_code == 200
    assert reports.json() == []


def test_backtest_report_csv_preflight_rejects_missing_required_headers(
    client: TestClient,
) -> None:
    payload = backtest_report_csv_payload(
        "closed_at,market_regime\n"
        "2026-03-01T00:00:00Z,TRENDING_UP\n"
    )

    response = client.post("/backtests/reports/preflight-csv", json=payload)

    assert response.status_code == 400
    assert "Backtest report CSV must include" in response.json()["detail"]


def test_backtest_csv_import_endpoints(client: TestClient) -> None:
    ohlcv_response = client.post(
        "/backtests/ohlcv/import-csv",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "source": "fixture",
            "source_reference": "fixture://ohlcv/BTCUSDT/15m",
            "csv_timezone": "UTC",
            "continuity": "continuous_24_7",
            "csv_text": "timestamp,open,high,low,close,volume\n"
            "2026-01-01T00:00:00Z,100,105,95,102,1234\n",
        },
    )
    trade_response = client.post(
        "/backtests/trades/import-csv",
        json={
            "csv_text": "realized_pl,equity,strategy,market_regime,r_multiple,closed_at\n"
            "10,1010,trend_pullback_v1,TRENDING_UP,2,2026-01-01T01:00:00Z\n"
        },
    )

    assert ohlcv_response.status_code == 201
    assert ohlcv_response.json()["symbol"] == "BTCUSDT"
    assert ohlcv_response.json()["timeframe"] == "15m"
    assert ohlcv_response.json()["row_count"] == 1
    assert ohlcv_response.json()["immutable"] is True
    assert len(ohlcv_response.json()["evidence_hash"]) == 64
    assert trade_response.status_code == 200
    assert trade_response.json()["trades"] == 1
    assert trade_response.json()["parsed_trades"][0]["realized_pl"] == "10"
