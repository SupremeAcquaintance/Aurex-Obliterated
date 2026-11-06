from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_transport_v2 import (  # noqa: E402
    S1_V2_PASS,
    S1SourceTransportAmendmentV2,
    S1SourceTransportAuditV2,
    S1SourceTransportResultV2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_source_transport_amendment_v2 import (  # noqa: E402
    build_amendment,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_source_transport_v2 import (  # noqa: E402
    RUNNER_PATH,
    build_requests,
    build_result,
)

DEFAULT_AMENDMENT = Path("data/evidence/s1_source_transport_amendment_v2.json")
DEFAULT_RESULT = Path("data/evidence/s1_source_transport_result_v2.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_source_transport_audit_v2.json")
AUDITOR_PATH = Path("scripts/audit_s1_source_transport_v2.py")


def build_audit(
    *,
    amendment_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S1SourceTransportAuditV2:
    amendment = S1SourceTransportAmendmentV2.model_validate_json(
        amendment_path.read_text(encoding="utf-8")
    )
    if amendment != build_amendment(frozen_at=amendment.frozen_at):
        raise ValueError("S1 v2 amendment differs from reconstruction")
    result = S1SourceTransportResultV2.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    expected = build_result(
        amendment_path=amendment_path,
        amendment=amendment,
        requests=build_requests(amendment),
        responses=result.responses,
        completed_at=result.completed_at,
    )
    if result != expected:
        raise ValueError("S1 v2 result differs from reconstruction")
    runner_hash = file_sha256(PROJECT_ROOT / RUNNER_PATH)
    if result.runner_source_sha256 != runner_hash:
        raise ValueError("S1 v2 runner source changed")
    payload = {
        "audited_at": audited_at,
        "amendment_file_sha256": file_sha256(amendment_path),
        "amendment_evidence_hash": amendment.amendment_evidence_hash,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "runner_source_sha256": runner_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "decision": (
            "PASS_S1_V2_RESULT_RECONSTRUCTED"
            if result.decision == S1_V2_PASS
            else "STOP_S1_V2_RESULT_RECONSTRUCTED"
        ),
        "next_authorization": result.next_authorization,
    }
    provisional = S1SourceTransportAuditV2.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return S1SourceTransportAuditV2.model_validate(complete)


def write_atomic(path: Path, audit: S1SourceTransportAuditV2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 v2 audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1SourceTransportAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("S1 v2 audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1 source transport v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SourceTransportAuditV2.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            amendment_path=args.amendment,
            result_path=args.result,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 v2 audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 v2 audit: {args.output}")
    audit = build_audit(
        amendment_path=args.amendment,
        result_path=args.result,
        audited_at=datetime.now(UTC),
    )
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
