from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1SourceTimingAmendmentAuditV2,
    S1SourceTimingAmendmentV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_source_timing_amendment_v2 import (  # noqa: E402
    DEFAULT_FAILED_AUDIT,
    DEFAULT_FAILED_RESULT,
    DEFAULT_PREREGISTRATION,
    DEFAULT_PREREGISTRATION_AUDIT,
    build_amendment,
)
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

DEFAULT_AMENDMENT = Path("data/evidence/s1_source_timing_amendment_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_source_timing_amendment_audit_v2.json")
AUDITOR_PATH = Path("scripts/audit_s1_source_timing_amendment_v2.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1.1 timing amendment.")
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument(
        "--preregistration-audit",
        type=Path,
        default=DEFAULT_PREREGISTRATION_AUDIT,
    )
    parser.add_argument("--failed-result", type=Path, default=DEFAULT_FAILED_RESULT)
    parser.add_argument("--failed-audit", type=Path, default=DEFAULT_FAILED_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    amendment = S1SourceTimingAmendmentV2.model_validate_json(
        args.amendment.read_text(encoding="utf-8")
    )
    reconstructed = build_amendment(
        preregistration_path=args.preregistration,
        preregistration_audit_path=args.preregistration_audit,
        failed_result_path=args.failed_result,
        failed_audit_path=args.failed_audit,
        frozen_at=amendment.frozen_at,
    )
    if reconstructed != amendment:
        raise SystemExit("S1.1 timing amendment did not reconstruct exactly")
    payload = {
        "audited_at": datetime.now(UTC),
        "amendment_file_sha256": file_sha256(args.amendment),
        "amendment_evidence_hash": amendment.amendment_evidence_hash,
        "builder_contract_hash": amendment.builder_contract_hash,
        "failed_source_result_evidence_hash": (
            amendment.failed_source_result_evidence_hash
        ),
        "failed_source_audit_evidence_hash": amendment.failed_source_audit_evidence_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
    }
    provisional = S1SourceTimingAmendmentAuditV2.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S1SourceTimingAmendmentAuditV2.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 timing amendment audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"amendment={audit.amendment_evidence_hash} returns=0 outcomes=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
