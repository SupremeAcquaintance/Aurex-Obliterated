from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeResult,
)
from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1PostFailureAnalysisAudit,
    S1PostFailureAnalysisExecutionContract,
    S1PostFailureAnalysisProtocol,
    S1PostFailureAnalysisResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s1_post_failure_analysis import (  # noqa: E402
    load_ledger,
    reconstruct_analysis,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
DEFAULT_CONTRACT = Path(
    "data/evidence/s1_post_failure_analysis_execution_contract_v1.json"
)
DEFAULT_OUTCOME_RESULT = Path("data/evidence/s1_1_development_outcome_result_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_post_failure_analysis_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_post_failure_analysis_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_post_failure_analysis.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S1 failure analysis.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--outcome-result", type=Path, default=DEFAULT_OUTCOME_RESULT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    contract = S1PostFailureAnalysisExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    outcome_result = S11DevelopmentOutcomeResult.model_validate_json(
        args.outcome_result.read_text(encoding="utf-8")
    )
    result = S1PostFailureAnalysisResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    rows = load_ledger(PROJECT_ROOT / protocol.outcome_ledger_path)
    reconstructed = reconstruct_analysis(
        completed_at=result.completed_at,
        protocol=protocol,
        contract=contract,
        outcome_result=outcome_result,
        rows=rows,
        protocol_path=args.protocol,
        contract_path=args.contract,
        outcome_result_path=args.outcome_result,
    )
    if (
        reconstructed != result
        or result.runner_contract_hash != runner_contract_hash()
        or result.decision != "RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE"
        or result.next_authorization != "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"
        or result.validation_values_read != 0
        or result.holdout_values_read != 0
        or result.parameter_variants_evaluated != 0
        or result.orders_submitted != 0
    ):
        raise SystemExit("S1 failure analysis did not reconstruct")
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
    }
    provisional = S1PostFailureAnalysisAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1PostFailureAnalysisAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} decision={audit.decision} "
        "validation=0 holdout=0 variants=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
