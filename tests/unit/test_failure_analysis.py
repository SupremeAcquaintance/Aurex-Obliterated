from datetime import UTC, datetime, timedelta

from aurex.backtest_engine.failure_analysis import analyze_reference_replay_failure
from aurex.db.models import BacktestReferenceReplayRun


def replay_fixture() -> BacktestReferenceReplayRun:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    trades = [
        trade_fixture(1, start, "LONG", "1.9", "0.2", "0.1", "1.7", "TAKE_PROFIT"),
        trade_fixture(
            2,
            start + timedelta(days=1),
            "SHORT",
            "-1.1",
            "0.2",
            "0.1",
            "-1.3",
            "STOP_LOSS",
        ),
        trade_fixture(
            3,
            start + timedelta(days=2),
            "SHORT",
            "-1.1",
            "0.2",
            "0.1",
            "-1.3",
            "STOP_LOSS",
        ),
    ]
    return BacktestReferenceReplayRun(
        id="replay-1",
        dataset_id="dataset-1",
        strategy="candidate_v1",
        strategy_version="1.0.0",
        engine_version="engine-v1",
        status="READY",
        dataset_evidence_hash="a" * 64,
        engine_evidence_hash="b" * 64,
        record_evidence_hash="c" * 64,
        request_snapshot={},
        result_snapshot={"trades": trades},
        recorded_at=start,
    )


def trade_fixture(
    sequence: int,
    entry_at: datetime,
    direction: str,
    gross_pl: str,
    fees: str,
    slippage: str,
    realized_pl: str,
    exit_reason: str,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "direction": direction,
        "entry_at": entry_at.isoformat(),
        "closed_at": (entry_at + timedelta(minutes=30)).isoformat(),
        "signal_price": "100",
        "entry_price": "100",
        "stop_loss": "99",
        "take_profit": "102",
        "exit_price": "102" if realized_pl.startswith("1") else "99",
        "quantity": "1",
        "gross_pl": gross_pl,
        "fees": fees,
        "slippage": slippage,
        "realized_pl": realized_pl,
        "equity": "1000",
        "r_multiple": realized_pl,
        "market_regime": "TEST_REGIME",
        "exit_reason": exit_reason,
        "intrabar_ambiguous": False,
    }


def test_failure_analysis_is_deterministic_and_reconciles_costs() -> None:
    replay = replay_fixture()

    first = analyze_reference_replay_failure(replay)
    second = analyze_reference_replay_failure(replay)

    assert first == second
    assert len(first["analysis_evidence_hash"]) == 64
    assert first["development_only"] is True
    assert first["promotion_eligible"] is False
    summary = first["summary"]
    assert summary["gross_before_modeled_costs"] == "0"
    assert summary["fill_price_gross_pl"] == "-0.3"
    assert summary["total_modeled_costs"] == "0.9"
    assert summary["total_net_pl"] == "-0.9"
    assert summary["reconciliation_delta"] == "0"
    assert summary["reconciles"] is True
    assert first["stability"]["maximum_consecutive_losses"] == 2
    assert "mechanism_negative_before_modeled_costs" in first["diagnoses"]


def test_failure_analysis_attributes_direction_and_duration() -> None:
    report = analyze_reference_replay_failure(replay_fixture())

    assert report["by_direction"]["LONG"]["total_trades"] == 1
    assert report["by_direction"]["SHORT"]["total_trades"] == 2
    assert report["by_direction"]["SHORT"]["total_net_pl"] == "-2.6"
    assert report["by_holding_duration"]["02_15_to_60_minutes"][
        "total_trades"
    ] == 3
    assert report["turnover"]["average_holding_minutes"] == "30"
