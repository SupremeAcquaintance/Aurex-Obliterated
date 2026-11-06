import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.jam_reversal_failure_analysis import (
    JAM_FAILURE_ANALYSIS_ID,
    JAM_FAILURE_FINDINGS,
    JAM_SUCCESSOR_REQUIREMENTS,
    JamFailureFacts,
    JamReversalFailureAnalysis,
    audit_jam_reversal_failure_analysis,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DECISION_PATH = Path(
    "data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json"
)
LEDGER_PATH = Path("data/evidence/strategy_contamination_ledger_v2.json")
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json"
)


def load_inputs() -> tuple[dict[str, object], StrategyContaminationLedger]:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    stored_decision_hash = decision["artifact_evidence_hash"]
    calculated_decision_hash = universe_evidence_hash(
        {
            key: value
            for key, value in decision.items()
            if key != "artifact_evidence_hash"
        }
    )
    if calculated_decision_hash != stored_decision_hash:
        raise ValueError("Jam historical decision failed its evidence-hash audit")
    if (
        decision["decision"] != "REJECT_CURRENT_VERSION"
        or decision["paper_authorized"]
        or decision["production_authorized"]
        or decision["replay_audit"]["status"] != "PASS"
        or decision["validation_audit"]["status"] != "PASS"
    ):
        raise ValueError("Jam historical decision is not the frozen rejection")

    ledger = StrategyContaminationLedger.model_validate_json(
        LEDGER_PATH.read_text(encoding="utf-8")
    )
    if not audit_contamination_ledger(ledger):
        raise ValueError("Jam contamination ledger v2 failed its evidence-hash audit")
    matching_records = [
        record
        for record in ledger.records
        if record.record_id == "jam-reversal-spot-btc-15m-2023-2026"
    ]
    if len(matching_records) != 1:
        raise ValueError("Jam contamination ledger v2 lacks the retired decision")
    if (
        matching_records[0].source_evidence_hashes.get("artifact")
        != stored_decision_hash
    ):
        raise ValueError("Jam contamination record is not bound to the decision")
    return decision, ledger


def build_analysis(
    decision: dict[str, object],
    ledger: StrategyContaminationLedger,
) -> JamReversalFailureAnalysis:
    validation = decision["validation"]
    metrics = validation["metrics_snapshot"]
    cost_sensitivity = metrics["cost_sensitivity"]
    base_case = next(
        scenario
        for scenario in cost_sensitivity["scenarios"]
        if scenario["name"] == "base_case"
    )
    facts = JamFailureFacts(
        total_trades=metrics["total_trades"],
        in_sample_trades=metrics["in_sample"]["total_trades"],
        out_of_sample_trades=metrics["out_of_sample"]["total_trades"],
        wins=metrics["wins"],
        losses=metrics["losses"],
        walk_forward_windows=metrics["walk_forward"]["window_count"],
        walk_forward_passed_windows=metrics["walk_forward"]["passed_windows"],
        gross_before_modeled_costs=Decimal(
            cost_sensitivity["gross_before_modeled_costs"]
        ),
        base_modeled_costs=Decimal(base_case["total_modeled_cost"]),
        base_net_pl=Decimal(metrics["total_net_pl"]),
        base_profit_factor=Decimal(metrics["profit_factor"]),
        base_expectancy=Decimal(metrics["expectancy"]),
        out_of_sample_net_pl=Decimal(metrics["out_of_sample"]["total_net_pl"]),
        out_of_sample_profit_factor=Decimal(
            metrics["out_of_sample"]["profit_factor"]
        ),
        out_of_sample_expectancy=Decimal(
            metrics["out_of_sample"]["expectancy"]
        ),
        max_drawdown=Decimal(metrics["max_drawdown"]),
        max_drawdown_gate=Decimal(
            validation["acceptance_snapshot"]["max_drawdown"]
        ),
    )
    payload = {
        "analysis_id": JAM_FAILURE_ANALYSIS_ID,
        "analyzed_at": datetime.fromisoformat(decision["completed_at"]),
        "historical_decision_evidence_hash": decision["artifact_evidence_hash"],
        "protocol_evidence_hash": decision["protocol_hash"],
        "replay_record_evidence_hash": decision["replay"]["record_evidence_hash"],
        "validation_evidence_hash": validation["validation_evidence_hash"],
        "contamination_ledger_evidence_hash": ledger.ledger_evidence_hash,
        "source_audits_passed": True,
        "failed_acceptance_gates": validation["acceptance_reasons"],
        "facts": facts,
        "findings": JAM_FAILURE_FINDINGS,
        "successor_requirements": JAM_SUCCESSOR_REQUIREMENTS,
    }
    provisional = JamReversalFailureAnalysis.model_construct(
        **payload,
        analysis_evidence_hash="0" * 64,
    )
    complete_payload = provisional.model_dump()
    complete_payload["analysis_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"analysis_evidence_hash"})
    )
    return JamReversalFailureAnalysis.model_validate(complete_payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or verify the no-new-returns Jam failure analysis."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decision, ledger = load_inputs()
    expected = build_analysis(decision, ledger)
    if args.check:
        stored = JamReversalFailureAnalysis.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        if not audit_jam_reversal_failure_analysis(stored):
            raise SystemExit("Stored Jam failure analysis failed its hash audit")
        if stored != expected:
            raise SystemExit("Stored Jam failure analysis differs from its rebuild")
        print(f"PASS {stored.analysis_evidence_hash}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(expected.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {args.output} {expected.analysis_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
