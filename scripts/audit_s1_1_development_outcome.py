from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1BtcPriceRowV2,
)
from aurex.backtest_engine.s1_development_outcome import (  # noqa: E402
    S11DevelopmentOutcomeProtocol,
)
from aurex.backtest_engine.s1_development_outcome_audit import (  # noqa: E402
    S11DevelopmentOutcomeAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeExecutionContract,
    S11DevelopmentOutcomeResult,
)
from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureRow,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_1_development_outcome import (  # noqa: E402
    evaluate_primary_gates,
    file_sha256,
    ledger_bytes,
    load_jsonl,
    runner_contract_hash,
    simulate_candidate,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")
DEFAULT_CONTRACT = Path(
    "data/evidence/s1_1_development_outcome_execution_contract_v1.json"
)
DEFAULT_PREREGISTRATION = Path("data/evidence/s1_strategy_preregistration_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_1_development_outcome_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_1_development_outcome_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_1_development_outcome.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1.1 development outcome.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol = S11DevelopmentOutcomeProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    contract = S11DevelopmentOutcomeExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    preregistration = S1StrategyPreregistration.model_validate_json(
        args.preregistration.read_text(encoding="utf-8")
    )
    result = S11DevelopmentOutcomeResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        result.runner_contract_hash != runner_contract_hash()
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
    ):
        raise SystemExit("S1.1 outcome lineage changed")
    features = load_jsonl(PROJECT_ROOT / protocol.feature_dataset_path, S1NfciFeatureRow)
    prices = load_jsonl(PROJECT_ROOT / protocol.price_dataset_path, S1BtcPriceRowV2)
    outcomes = []
    ledgers = []
    for candidate in preregistration.candidates:
        outcome, intervals = simulate_candidate(
            features=features,
            prices=prices,
            candidate=candidate,
            protocol=protocol,
        )
        outcomes.append(outcome)
        ledgers.extend(intervals)
    ledger_path = PROJECT_ROOT / result.outcome_ledger_path
    if (
        ledger_path.read_bytes() != ledger_bytes(tuple(ledgers))
        or file_sha256(ledger_path) != result.outcome_ledger_file_sha256
        or tuple(outcomes) != result.candidate_outcomes
    ):
        raise SystemExit("S1.1 outcome ledger or candidate metrics changed")
    primary = next(item for item in outcomes if item.role == "PRIMARY_ELIGIBILITY")
    gates = evaluate_primary_gates(primary, preregistration)
    if gates != result.primary_gate_results:
        raise SystemExit("S1.1 primary gates changed")
    failed_gate_ids = tuple(item.gate_id for item in gates if item.status == "FAIL")
    payload = {
        "audited_at": datetime.now(UTC),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "execution_contract_file_sha256": file_sha256(args.contract),
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "result_file_sha256": file_sha256(args.result),
        "result_evidence_hash": result.result_evidence_hash,
        "outcome_ledger_file_sha256": result.outcome_ledger_file_sha256,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "failed_gate_ids": failed_gate_ids,
    }
    provisional = S11DevelopmentOutcomeAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S11DevelopmentOutcomeAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 outcome audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} gates={audit.primary_passed_gate_count}/12 "
        f"decision={audit.decision} validation=0 holdout=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
