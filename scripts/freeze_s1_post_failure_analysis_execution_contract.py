from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1PostFailureAnalysisExecutionContract,
    S1PostFailureAnalysisProtocol,
    S1PostFailureAnalysisProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s1_post_failure_analysis import runner_contract_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_post_failure_analysis_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_post_failure_analysis_execution_contract_v1.json"
)
RESULT_PATH = Path("data/evidence/s1_post_failure_analysis_result_v1.json")
AUDIT_PATH = Path("data/evidence/s1_post_failure_analysis_audit_v1.json")
BUILDER_PATH = Path("scripts/freeze_s1_post_failure_analysis_execution_contract.py")
TEST_IDS = (
    "PROTOCOL_FORBIDS_RESCUE_AND_EXECUTION",
    "GROSS_EQUITY_COMPOUNDS_EXISTING_INTERVALS",
    "DRAWDOWN_EARLIEST_TIE_AND_RECOVERY",
    "DRAWDOWN_UNRECOVERED_STATE",
    "MAXIMAL_CONTIGUOUS_LONG_EPISODES",
    "TAIL_MAGNITUDE_AND_SEQUENCE_TIEBREAK",
    "DIAGNOSTIC_DUPLICATE_POSITION_VECTORS",
    "ACTUAL_FAILED_LINEAGE_DEVELOPMENT_ONLY",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze S1 failure-analysis execution.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    audit = S1PostFailureAnalysisProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    if (
        audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.next_authorization
        != "AUTHORIZE_S1_POST_FAILURE_ANALYSIS_RUNNER_IMPLEMENTATION_ONLY"
        or RESULT_PATH.exists()
        or AUDIT_PATH.exists()
    ):
        raise SystemExit("S1 failure-analysis execution authority is not clean")
    payload = {
        "frozen_at": datetime.now(UTC),
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(args.protocol_audit),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "outcome_result_file_sha256": protocol.outcome_result_file_sha256,
        "outcome_ledger_file_sha256": protocol.outcome_ledger_file_sha256,
        "synthetic_test_ids": TEST_IDS,
    }
    provisional = S1PostFailureAnalysisExecutionContract.model_construct(
        **payload, contract_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    contract = S1PostFailureAnalysisExecutionContract.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis execution contract exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        contract.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"runner={contract.runner_contract_hash} tests={len(TEST_IDS)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
