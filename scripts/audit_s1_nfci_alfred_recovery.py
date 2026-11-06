from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_nfci_alfred_recovery import (  # noqa: E402
    S1_ALFRED_PASS,
    S1NfciAlfredRecoveryAudit,
    S1NfciAlfredRecoveryProtocol,
    S1NfciAlfredRecoveryResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_nfci_alfred_recovery_protocol import build_protocol  # noqa: E402
from scripts.freeze_s1_successor_lineage import file_sha256  # noqa: E402
from scripts.run_s1_nfci_alfred_recovery import (  # noqa: E402
    RUNNER_PATH,
    build_result,
)
from scripts.run_s1_nfci_raw_pilot import build_comparison, parse_snapshot  # noqa: E402

DEFAULT_PROTOCOL = Path("data/evidence/s1_nfci_alfred_recovery_protocol_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_nfci_alfred_recovery_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_nfci_alfred_recovery_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_nfci_alfred_recovery.py")


def build_audit(
    *,
    protocol_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S1NfciAlfredRecoveryAudit:
    protocol = S1NfciAlfredRecoveryProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    if protocol != build_protocol(frozen_at=protocol.frozen_at):
        raise ValueError("S1 ALFRED protocol differs from reconstruction")
    result = S1NfciAlfredRecoveryResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if result.decision != S1_ALFRED_PASS:
        raise ValueError("S1 ALFRED recovery did not pass; no pass audit may be written")
    runner_hash = file_sha256(PROJECT_ROOT / RUNNER_PATH)
    if result.runner_source_sha256 != runner_hash:
        raise ValueError("S1 ALFRED runner source changed")
    raw_hashes: dict[str, str] = {}
    raw_bytes: dict[str, int] = {}
    for download in result.downloads:
        if download.raw_path is None or download.summary is None:
            raise ValueError("S1 ALFRED completed result lost raw evidence")
        if (
            file_sha256(Path(download.request_marker_path))
            != download.request_marker_sha256
            or file_sha256(Path(download.response_marker_path))
            != download.response_marker_sha256
        ):
            raise ValueError("S1 ALFRED request or response marker changed")
        raw_path = Path(download.raw_path)
        digest = file_sha256(raw_path)
        summary, _ = parse_snapshot(raw_path, vintage_date=download.vintage_date)
        if (
            digest != download.payload_sha256
            or raw_path.stat().st_size != download.payload_bytes
            or summary != download.summary
        ):
            raise ValueError("S1 ALFRED raw snapshot reconstruction changed")
        raw_hashes[download.target_id] = digest
        raw_bytes[download.target_id] = raw_path.stat().st_size
    expected_result = build_result(
        protocol_path=protocol_path,
        protocol=protocol,
        downloads=result.downloads,
        comparison=build_comparison(result.downloads),
        completed_at=result.completed_at,
    )
    if result != expected_result:
        raise ValueError("S1 ALFRED result differs from reconstruction")
    payload = {
        "audited_at": audited_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "runner_source_sha256": runner_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "raw_file_sha256": raw_hashes,
        "raw_file_bytes": raw_bytes,
    }
    provisional = S1NfciAlfredRecoveryAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1NfciAlfredRecoveryAudit.model_validate(complete)


def write_atomic(path: Path, audit: S1NfciAlfredRecoveryAudit) -> None:
    if path.exists():
        raise ValueError(f"S1 ALFRED audit exists; use --check: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1 ALFRED audit transaction exists: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S1NfciAlfredRecoveryAudit.model_validate_json(serialized) != audit:
        raise ValueError("S1 ALFRED audit did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the S1 ALFRED recovery.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S1NfciAlfredRecoveryAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(
            protocol_path=args.protocol,
            result_path=args.result,
            audited_at=stored.audited_at,
        )
        if stored != expected:
            raise SystemExit("Stored S1 ALFRED audit differs from reconstruction")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
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
