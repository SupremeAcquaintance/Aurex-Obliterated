from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_event_outcome_protocol import (  # noqa: E402
    JamSuccessorEventOutcomeProtocol,
    JamSuccessorEventOutcomeProtocolAudit,
    audit_jam_successor_event_outcome_audit,
    audit_jam_successor_event_outcome_protocol,
    build_jam_successor_event_outcome_audit,
)
from scripts.freeze_jam_successor_event_outcome_protocol import (  # noqa: E402
    DEFAULT_DISTRIBUTION_AUDIT,
    DEFAULT_DISTRIBUTION_PROTOCOL,
    DEFAULT_DISTRIBUTION_RESULT,
    DEFAULT_FEATURE_ROWS,
    DEFAULT_FEATURE_SPECIFICATION,
    DEFAULT_OUTPUT,
    authoritative_protocol,
    file_sha256,
    load_inputs,
)

DEFAULT_AUDIT_OUTPUT = Path("data/evidence/jam_successor_event_outcome_protocol_audit_v1.json")


def write_audit(
    path: Path,
    audit: JamSuccessorEventOutcomeProtocolAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamSuccessorEventOutcomeProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam event/outcome audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_audit(args) -> JamSuccessorEventOutcomeProtocolAudit:
    if args.output.exists():
        raise ValueError(f"Jam event/outcome audit already exists: {args.output}")
    inputs = load_inputs(
        distribution_protocol_path=args.distribution_protocol,
        distribution_result_path=args.distribution_result,
        distribution_audit_path=args.distribution_audit,
        feature_rows_path=args.feature_rows,
        feature_specification_path=args.feature_specification,
    )
    protocol = JamSuccessorEventOutcomeProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    reconstructed = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=inputs,
        distribution_protocol_path=args.distribution_protocol,
        distribution_result_path=args.distribution_result,
        distribution_audit_path=args.distribution_audit,
        feature_rows_path=args.feature_rows,
    )
    if protocol != reconstructed or not audit_jam_successor_event_outcome_protocol(protocol):
        raise ValueError("Jam event/outcome protocol reconstruction changed")
    audit = build_jam_successor_event_outcome_audit(
        audited_at=datetime.now(UTC),
        protocol_path=args.protocol.as_posix(),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        distribution_result_evidence_hash=(protocol.distribution_result_evidence_hash),
        distribution_audit_evidence_hash=(protocol.distribution_audit_evidence_hash),
        feature_rows_file_sha256=protocol.feature_rows_file_sha256,
    )
    if not audit_jam_successor_event_outcome_audit(audit):
        raise ValueError("Jam event/outcome audit failed internal audit")
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"protocol={audit.protocol_evidence_hash} "
        "conditions=5 events=0 labels=0 returns=0",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently reconstruct the Jam successor event/outcome protocol "
            "without calculating an event, label, or return."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--distribution-protocol",
        type=Path,
        default=DEFAULT_DISTRIBUTION_PROTOCOL,
    )
    parser.add_argument(
        "--distribution-result",
        type=Path,
        default=DEFAULT_DISTRIBUTION_RESULT,
    )
    parser.add_argument(
        "--distribution-audit",
        type=Path,
        default=DEFAULT_DISTRIBUTION_AUDIT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--feature-specification",
        type=Path,
        default=DEFAULT_FEATURE_SPECIFICATION,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        run_audit(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
