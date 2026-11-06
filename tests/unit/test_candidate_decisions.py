from copy import deepcopy
from decimal import getcontext

from aurex.backtest_engine.candidate_decisions import (
    SLOW_BREAKOUT_SPOT_REQUIRED_BINDINGS,
    evaluate_slow_breakout_spot_cross_market,
)


def validation_fixture(symbol: str) -> dict:
    suffix = "e" if symbol == "ETHUSDT" else "s"
    return {
        "status": "PASSED",
        "strategy": "slow_breakout_spot_v1",
        "strategy_version": "1.0.0",
        "symbol": symbol,
        "timeframe": "4h",
        "reference_replay_run_id": f"replay-{suffix}",
        "protocol_id": f"protocol-{suffix}",
        "validation_evidence_hash": suffix * 64,
        "statistical_acceptance_passed": True,
        "binding_checks": [
            {"name": name, "status": "PASS"}
            for name in sorted(SLOW_BREAKOUT_SPOT_REQUIRED_BINDINGS)
        ],
        "metrics_snapshot": {
            "total_trades": 30,
            "total_net_pl": "40",
            "gross_profit": "100",
            "gross_loss": "60",
            "cost_sensitivity": {
                "scenarios": [
                    {
                        "name": "stress_150_percent",
                        "total_net_pl": "20",
                    }
                ]
            },
        },
    }


def test_slow_breakout_cross_market_accepts_only_joint_clean_edge() -> None:
    eth = validation_fixture("ETHUSDT")
    sol = validation_fixture("SOLUSDT")

    decision = evaluate_slow_breakout_spot_cross_market([sol, eth])
    reordered = evaluate_slow_breakout_spot_cross_market([eth, sol])

    assert decision["status"] == "ACCEPT"
    assert decision["candidate_eligible_for_parity"] is True
    assert decision["candidate_eligible_for_paper"] is False
    assert decision["combined"]["total_trades"] == 60
    assert decision["combined"]["total_net_pl"] == "80"
    assert decision["combined"]["profit_factor"] == "1.666666666666666666666666667"
    assert decision["combined"]["stress_150_percent_net_pl"] == "40"
    assert decision["reasons"] == []
    assert decision["decision_evidence_hash"] == reordered["decision_evidence_hash"]


def test_slow_breakout_decision_ignores_process_decimal_precision() -> None:
    original_precision = getcontext().prec
    try:
        getcontext().prec = 60
        decision = evaluate_slow_breakout_spot_cross_market(
            [validation_fixture("ETHUSDT"), validation_fixture("SOLUSDT")]
        )
    finally:
        getcontext().prec = original_precision

    assert decision["combined"]["profit_factor"] == (
        "1.666666666666666666666666667"
    )


def test_slow_breakout_cross_market_rejects_one_losing_symbol() -> None:
    eth = validation_fixture("ETHUSDT")
    sol = validation_fixture("SOLUSDT")
    sol["status"] = "REJECTED"
    sol["statistical_acceptance_passed"] = False
    sol["metrics_snapshot"]["total_net_pl"] = "-1"

    decision = evaluate_slow_breakout_spot_cross_market([eth, sol])

    assert decision["status"] == "REJECT"
    assert "SOLUSDT:individual_validation_failed" in decision["reasons"]
    assert "SOLUSDT:base_net_negative" in decision["reasons"]


def test_slow_breakout_cross_market_rejects_binding_and_concentration_failures() -> None:
    eth = validation_fixture("ETHUSDT")
    sol = validation_fixture("SOLUSDT")
    eth["binding_checks"] = [
        check
        for check in eth["binding_checks"]
        if check["name"] != "protocol_registered_before_reference_replay"
    ]
    eth["metrics_snapshot"]["gross_profit"] = "190"
    sol["metrics_snapshot"]["gross_profit"] = "10"

    decision = evaluate_slow_breakout_spot_cross_market([eth, sol])

    assert decision["status"] == "REJECT"
    assert "ETHUSDT:required_binding_missing" in decision["reasons"]
    assert "ETHUSDT:gross_profit_concentration_exceeds_gate" in decision["reasons"]


def test_slow_breakout_cross_market_rejects_nonpositive_cost_stress() -> None:
    eth = validation_fixture("ETHUSDT")
    sol = validation_fixture("SOLUSDT")
    for item in (eth, sol):
        item["metrics_snapshot"]["cost_sensitivity"]["scenarios"][0][
            "total_net_pl"
        ] = "-1"

    decision = evaluate_slow_breakout_spot_cross_market([deepcopy(eth), deepcopy(sol)])

    assert decision["status"] == "REJECT"
    assert "combined_stress_150_percent_net_not_positive" in decision["reasons"]
