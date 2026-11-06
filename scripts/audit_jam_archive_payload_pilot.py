import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_payload_pilot import (  # noqa: E402
    JAM_PAYLOAD_PILOT_FAIL_DECISION,
    JAM_PAYLOAD_PILOT_PASS_DECISION,
    JamPayloadPilotAudit,
    JamPayloadPilotProtocol,
    JamPayloadPilotResult,
    audit_jam_payload_pilot_audit,
    audit_jam_payload_pilot_protocol,
    audit_jam_payload_pilot_result,
    build_jam_payload_pilot_audit,
)
from scripts.run_jam_archive_payload_pilot import (  # noqa: E402
    inspect_and_reconcile,
    target_archive_path,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_payload_pilot_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/jam_archive_payload_pilot_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_payload_pilot_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")


def load_inputs(
    *,
    protocol_path: Path,
    result_path: Path,
) -> tuple[JamPayloadPilotProtocol, JamPayloadPilotResult]:
    protocol = JamPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    result = JamPayloadPilotResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_payload_pilot_protocol(protocol)
        or not audit_jam_payload_pilot_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.total_head_request_count > protocol.maximum_head_requests
        or result.total_payload_get_request_count
        > protocol.maximum_payload_get_requests
        or result.total_head_request_count
        + result.total_payload_get_request_count
        > protocol.maximum_requests_total
        or result.return_metrics_calculated
        or result.feature_fields_created
        or result.parameters_defined
        or result.strategy_executions
        or result.creates_candidate
        or result.creates_testnet_order_authority
        or result.creates_live_eligibility
    ):
        raise ValueError("Jam payload pilot lineage or authority boundary failed")
    return protocol, result


def reconstruct(
    *,
    protocol: JamPayloadPilotProtocol,
    result: JamPayloadPilotResult,
    evidence_root: Path,
) -> tuple[dict[str, str], dict[str, int]]:
    request_counts = {
        evidence.family: evidence.payload_get_request_count
        for evidence in result.archive_evidence
    }
    rebuilt_evidence, rebuilt_reconciliation = inspect_and_reconcile(
        protocol=protocol,
        evidence_root=evidence_root,
        request_counts=request_counts,
    )
    if (
        rebuilt_evidence != result.archive_evidence
        or rebuilt_reconciliation != result.reconciliation
    ):
        raise ValueError("Jam payload pilot raw-file reconstruction changed")
    rebuilt_pass = (
        all(item.archive_pass for item in rebuilt_evidence)
        and rebuilt_reconciliation.reconciliation_pass
    )
    expected_decision = (
        JAM_PAYLOAD_PILOT_PASS_DECISION
        if rebuilt_pass
        else JAM_PAYLOAD_PILOT_FAIL_DECISION
    )
    if result.decision != expected_decision:
        raise ValueError("Jam payload pilot reconstructed decision changed")
    archive_hashes = {}
    archive_bytes = {}
    for target in protocol.targets:
        path = target_archive_path(evidence_root, target)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != target.published_archive_sha256:
            raise ValueError(
                f"Jam payload pilot raw hash changed: {target.family}"
            )
        archive_hashes[target.family] = digest
        archive_bytes[target.family] = path.stat().st_size
    return archive_hashes, archive_bytes


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: JamPayloadPilotResult,
    archive_hashes: dict[str, str],
    archive_bytes: dict[str, int],
) -> JamPayloadPilotAudit:
    return build_jam_payload_pilot_audit(
        audited_at=audited_at,
        result_path=result_path.as_posix(),
        result_file_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        archive_file_sha256=archive_hashes,
        archive_file_bytes=archive_bytes,
        decision=result.decision,
    )


def write_audit(path: Path, audit: JamPayloadPilotAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamPayloadPilotAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam payload pilot audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamPayloadPilotAudit:
    if args.output.exists():
        raise ValueError("Jam payload pilot audit exists; use --check")
    protocol, result = load_inputs(
        protocol_path=args.protocol,
        result_path=args.result,
    )
    archive_hashes, archive_bytes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
        archive_hashes=archive_hashes,
        archive_bytes=archive_bytes,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"archives={audit.archive_count} decision={audit.decision}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamPayloadPilotAudit:
    protocol, result = load_inputs(
        protocol_path=args.protocol,
        result_path=args.result,
    )
    archive_hashes, archive_bytes = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = JamPayloadPilotAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
        archive_hashes=archive_hashes,
        archive_bytes=archive_bytes,
    )
    if audit != expected or not audit_jam_payload_pilot_audit(audit):
        raise ValueError("Jam payload pilot audit is not reproducible")
    print(
        "PASS "
        f"jam_payload_audit={audit.audit_evidence_hash} "
        f"result_file={audit.result_file_sha256} "
        f"archives={audit.archive_count} "
        f"reconciled={audit.reconciliation_rebuilt} "
        f"returns={audit.return_metrics_calculated} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently rebuild and audit the one-month Jam payload pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.write:
            run_write(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
