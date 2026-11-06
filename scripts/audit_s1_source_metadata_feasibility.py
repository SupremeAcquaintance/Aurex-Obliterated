from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_source_feasibility import (  # noqa: E402
    S1_SOURCE_PASS_DECISION,
    S1SourceMetadataAudit,
    S1SourceMetadataProtocol,
    S1SourceMetadataResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_source_metadata_feasibility import (  # noqa: E402
    build_protocol,
)
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_source_metadata_feasibility import (  # noqa: E402
    RUNNER_PATH,
    build_result,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/s1_source_metadata_feasibility_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/s1_source_metadata_feasibility_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_source_metadata_feasibility_audit_v1.json"
)
AUDITOR_PATH = Path("scripts/audit_s1_source_metadata_feasibility.py")


def build_audit(
    *,
    protocol_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S1SourceMetadataAudit:
    protocol = S1SourceMetadataProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise ValueError("S1 source protocol differs from reconstruction")
    result = S1SourceMetadataResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    reconstructed = build_result(
        protocol_path=protocol_path,
        protocol=protocol,
        responses=result.responses,
        completed_at=result.completed_at,
    )
    if result != reconstructed:
        raise ValueError("S1 source result differs from reconstruction")
    runner_hash = file_sha256(PROJECT_ROOT / RUNNER_PATH)
    if result.runner_source_sha256 != runner_hash:
        raise ValueError("S1 source runner changed")
    payload = {
        "audited_at": audited_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "runner_source_sha256": runner_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "decision": (
            "PASS_S1_METADATA_RESULT_RECONSTRUCTED"
            if result.decision == S1_SOURCE_PASS_DECISION
            else "STOP_S1_METADATA_RESULT_RECONSTRUCTED"
        ),
        "next_authorization": result.next_authorization,
    }
    provisional = S1SourceMetadataAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump()
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return S1SourceMetadataAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1SourceMetadataAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 source audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1SourceMetadataAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 source audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1 source metadata result.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1SourceMetadataAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            protocol_path=args.protocol,
            result_path=args.result,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 source audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1 source audit: {args.output}")
    audit = build_audit(
        protocol_path=args.protocol,
        result_path=args.result,
        audited_at=datetime.now(UTC),
    )
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
