from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1PostFailureAnalysisExecutionAudit,
    S1PostFailureAnalysisExecutionContract,
    S1PostFailureAnalysisProtocol,
    S1PostFailureAnalysisProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_post_failure_analysis_execution_contract import (  # noqa: E402
    TEST_IDS,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402
from scripts.run_s1_post_failure_analysis import runner_contract_hash  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_post_failure_analysis_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s1_post_failure_analysis_execution_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_post_failure_analysis_execution_audit_v1.json"
)
AUDITOR_PATH = Path("scripts/audit_s1_post_failure_analysis_execution_contract.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit S1 failure-analysis execution.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = S1PostFailureAnalysisProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = S1PostFailureAnalysisExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    builder_path = Path(
        "scripts/freeze_s1_post_failure_analysis_execution_contract.py"
    )
    if (
        contract.builder_contract_hash
        != file_sha256(PROJECT_ROOT / builder_path)
        or contract.protocol_file_sha256 != file_sha256(args.protocol)
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_audit_file_sha256 != file_sha256(args.protocol_audit)
        or contract.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or contract.runner_contract_hash != runner_contract_hash()
        or contract.outcome_result_file_sha256 != protocol.outcome_result_file_sha256
        or contract.outcome_ledger_file_sha256 != protocol.outcome_ledger_file_sha256
        or contract.synthetic_test_ids != TEST_IDS
    ):
        raise SystemExit("S1 failure-analysis execution contract did not reconstruct")
    payload = {
        "audited_at": datetime.now(UTC),
        "contract_file_sha256": file_sha256(args.contract),
        "contract_evidence_hash": contract.contract_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "runner_contract_hash": contract.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "synthetic_test_ids": TEST_IDS,
    }
    provisional = S1PostFailureAnalysisExecutionAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1PostFailureAnalysisExecutionAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis execution audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"contract={audit.contract_evidence_hash} values=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
