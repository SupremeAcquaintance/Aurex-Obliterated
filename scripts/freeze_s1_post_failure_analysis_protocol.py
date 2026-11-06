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
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

OUTCOME_RESULT_PATH = Path("data/evidence/s1_1_development_outcome_result_v1.json")
OUTCOME_AUDIT_PATH = Path("data/evidence/s1_1_development_outcome_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_post_failure_analysis_protocol_v1.json")
BUILDER_PATH = Path("scripts/freeze_s1_post_failure_analysis_protocol.py")


def build_protocol(*, frozen_at: datetime) -> S1PostFailureAnalysisProtocol:
    result = S11DevelopmentOutcomeResult.model_validate_json(
        OUTCOME_RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S11DevelopmentOutcomeAudit.model_validate_json(
        OUTCOME_AUDIT_PATH.read_text(encoding="utf-8")
    )
    ledger_path = PROJECT_ROOT / result.outcome_ledger_path
    if (
        result.decision != "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        or audit.decision != "CONFIRM_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        or audit.result_evidence_hash != result.result_evidence_hash
        or audit.result_file_sha256 != file_sha256(OUTCOME_RESULT_PATH)
        or file_sha256(ledger_path) != result.outcome_ledger_file_sha256
        or result.validation_values_read != 0
        or result.holdout_values_read != 0
        or result.orders_submitted != 0
    ):
        raise ValueError("S1 failure-analysis input lineage changed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "outcome_result_file_sha256": file_sha256(OUTCOME_RESULT_PATH),
        "outcome_result_evidence_hash": result.result_evidence_hash,
        "outcome_audit_file_sha256": file_sha256(OUTCOME_AUDIT_PATH),
        "outcome_audit_evidence_hash": audit.audit_evidence_hash,
        "outcome_ledger_file_sha256": result.outcome_ledger_file_sha256,
    }
    provisional = S1PostFailureAnalysisProtocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S1PostFailureAnalysisProtocol.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the S1 failure-analysis protocol.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1 failure-analysis protocol exists: {args.output}")
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(
        protocol.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        "metrics=0 validation=0 holdout=0 variants=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
