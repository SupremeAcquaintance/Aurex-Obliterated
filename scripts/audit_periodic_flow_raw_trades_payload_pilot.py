from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_raw_trades_payload_evidence_v2 import (  # noqa: E402
    RawTradesPayloadPilotAuditV2,
    RawTradesPayloadPilotResultV2,
    audit_raw_payload_audit_v2,
    audit_raw_payload_result_v2,
    build_raw_payload_audit_v2,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    MODULE_PATH,
    file_sha256,
)
from scripts.run_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    authoritative_result,
    inspect_pilot,
    load_protocol,
    raw_archive_path,
    request_marker_manifest,
    runner_contract_hash,
    spot_archive_path,
)
from scripts.run_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RESULT,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_audit_v2.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_raw_trades_payload_pilot.py"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                MODULE_PATH.as_posix(): file_sha256(PROJECT_ROOT / MODULE_PATH),
                AUDIT_SCRIPT_PATH.as_posix(): file_sha256(
                    PROJECT_ROOT / AUDIT_SCRIPT_PATH
                ),
            }
        }
    )


def reconstruct_result(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    evidence_root: Path,
) -> RawTradesPayloadPilotResultV2:
    protocol, protocol_audit = load_protocol(protocol_path, protocol_audit_path)
    stored = RawTradesPayloadPilotResultV2.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    raw_evidence, clock = inspect_pilot(
        protocol=protocol,
        evidence_root=evidence_root,
        payload_get_attempt_count=stored.payload_get_attempt_count,
    )
    marker_hash, marker_count, marker_records = request_marker_manifest(
        evidence_root=evidence_root,
        protocol=protocol,
    )
    if int(marker_records[-1]["bytes_received"]) != raw_evidence.archive_bytes:
        raise ValueError("Q1 raw payload marker byte count changed")
    expected = authoritative_result(
        generated_at=stored.generated_at,
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        protocol=protocol,
        protocol_audit=protocol_audit,
        raw_evidence=raw_evidence,
        clock=clock,
        request_marker_manifest_hash=marker_hash,
        request_marker_count=marker_count,
    )
    if (
        stored != expected
        or not audit_raw_payload_result_v2(stored)
        or stored.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Q1 raw payload result failed independent reconstruction")
    return stored


def authoritative_audit(
    *,
    audited_at: datetime,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
    evidence_root: Path,
) -> RawTradesPayloadPilotAuditV2:
    result = reconstruct_result(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        result_path=result_path,
        evidence_root=evidence_root,
    )
    return build_raw_payload_audit_v2(
        audited_at=audited_at,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        raw_archive_file_sha256=file_sha256(raw_archive_path(evidence_root)),
        spot_archive_file_sha256=file_sha256(spot_archive_path(evidence_root)),
        request_marker_manifest_hash=result.request_marker_manifest_hash,
        request_marker_count=result.request_marker_count,
        runner_contract_hash=result.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        decision=result.decision,
    )


def write_audit(path: Path, audit: RawTradesPayloadPilotAuditV2) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite raw payload audit: {path}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if RawTradesPayloadPilotAuditV2.model_validate_json(serialized) != audit:
        raise ValueError("Q1 raw payload audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale raw payload audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 raw-trades payload pilot."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = RawTradesPayloadPilotAuditV2.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                audited_at=stored.audited_at,
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                result_path=args.result,
                evidence_root=args.evidence_root,
            )
            if stored != expected or not audit_raw_payload_audit_v2(stored):
                raise ValueError("Stored Q1 raw payload audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = authoritative_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            result_path=args.result,
            evidence_root=args.evidence_root,
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"decision={audit.decision} outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
