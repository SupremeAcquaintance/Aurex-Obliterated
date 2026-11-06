from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome_audit import (  # noqa: E402
    S11DevelopmentOutcomeAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeResult,
)
from aurex.backtest_engine.s1_post_failure_analysis import (  # noqa: E402
    S1PostFailureAnalysisProtocol,
    S1PostFailureAnalysisProtocolAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_post_failure_analysis_protocol_audit_v1.json")
OUTCOME_RESULT_PATH = Path("data/evidence/s1_1_development_outcome_result_v1.json")
OUTCOME_AUDIT_PATH = Path("data/evidence/s1_1_development_outcome_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_post_failure_analysis_protocol.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the S1 failure-analysis protocol.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    protocol = S1PostFailureAnalysisProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = S11DevelopmentOutcomeResult.model_validate_json(
        OUTCOME_RESULT_PATH.read_text(encoding="utf-8")
    )
    outcome_audit = S11DevelopmentOutcomeAudit.model_validate_json(
        OUTCOME_AUDIT_PATH.read_text(encoding="utf-8")
    )
    ledger_path = PROJECT_ROOT / protocol.outcome_ledger_path
    if (
        protocol.builder_contract_hash
        != file_sha256(PROJECT_ROOT / Path("scripts/freeze_s1_post_failure_analysis_protocol.py"))
        or protocol.outcome_result_file_sha256 != file_sha256(OUTCOME_RESULT_PATH)
        or protocol.outcome_result_evidence_hash != result.result_evidence_hash
        or protocol.outcome_audit_file_sha256 != file_sha256(OUTCOME_AUDIT_PATH)
        or protocol.outcome_audit_evidence_hash != outcome_audit.audit_evidence_hash
        or protocol.outcome_ledger_file_sha256 != file_sha256(ledger_path)
        or result.decision != "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED"
    ):
        raise SystemExit("S1 failure-analysis protocol did not reconstruct")
    payload = {
        "audited_at": datetime.now(UTC),
        "protocol_file_sha256": file_sha256(args.protocol),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "outcome_result_evidence_hash": result.result_evidence_hash,
        "outcome_audit_evidence_hash": outcome_audit.audit_evidence_hash,
        "outcome_ledger_file_sha256": file_sha256(ledger_path),
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S1PostFailureAnalysisProtocolAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1PostFailureAnalysisProtocolAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis protocol audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"protocol={audit.protocol_evidence_hash} metrics=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
