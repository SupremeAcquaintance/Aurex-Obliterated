from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_full_acquisition import (  # noqa: E402
    JAM_FULL_MONTHS,
    JamFullAcquisitionAudit,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    audit_jam_full_acquisition_audit,
    audit_jam_full_acquisition_protocol,
    audit_jam_full_acquisition_result,
    build_jam_full_acquisition_audit,
)
from aurex.backtest_engine.universe import (  # noqa: E402
    universe_evidence_hash,
)
from scripts.run_jam_archive_full_acquisition import (  # noqa: E402
    HeadObservation,
    file_sha256,
    inspect_month,
    load_protocol,
    target_archive_path,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/jam_archive_full_acquisition_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_full_acquisition_audit_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")


def load_inputs(
    *,
    protocol_path: Path,
    result_path: Path,
) -> tuple[JamFullAcquisitionProtocol, JamFullAcquisitionResult]:
    protocol = load_protocol(protocol_path)
    result = JamFullAcquisitionResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_full_acquisition_protocol(protocol)
        or not audit_jam_full_acquisition_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.return_metrics_calculated
        or result.feature_fields_created
        or result.parameters_defined
        or result.strategy_executions
        or result.creates_candidate
        or result.creates_paper_eligibility
        or result.creates_testnet_order_authority
        or result.creates_production_authority
        or result.creates_live_eligibility
    ):
        raise ValueError("Jam full acquisition lineage or authority boundary failed")
    return protocol, result


def reconstruct(
    *,
    protocol: JamFullAcquisitionProtocol,
    result: JamFullAcquisitionResult,
    evidence_root: Path,
) -> str:
    archive_evidence = {
        archive.key: archive
        for month in result.months
        for archive in (month.aggregate_trades, month.klines_1m)
    }
    heads = {
        target.key: HeadObservation(
            content_length_bytes=archive_evidence[target.key].archive_bytes,
            request_count=archive_evidence[target.key].head_request_count,
            accept_ranges="",
        )
        for target in protocol.targets
        if not target.reuse_verified_pilot_file
    }
    get_counts = {
        target.key: archive_evidence[target.key].payload_get_request_count
        for target in protocol.targets
    }
    rebuilt_months = [
        inspect_month(
            month=month,
            protocol=protocol,
            evidence_root=evidence_root,
            heads=heads,
            get_counts=get_counts,
        )
        for month in JAM_FULL_MONTHS
    ]
    if rebuilt_months != result.months:
        raise ValueError("Jam full acquisition raw-file reconstruction changed")

    manifest = []
    for target in protocol.targets:
        path = target_archive_path(evidence_root, target)
        digest = file_sha256(path)
        if digest != target.published_archive_sha256:
            raise ValueError(f"Jam full raw hash changed: {target.key}")
        manifest.append(
            {
                "family": target.family,
                "month": target.month,
                "path": path.relative_to(evidence_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    return universe_evidence_hash({"archives": manifest})


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: JamFullAcquisitionResult,
    raw_manifest_hash: str,
) -> JamFullAcquisitionAudit:
    return build_jam_full_acquisition_audit(
        audited_at=audited_at,
        result_path=result_path.as_posix(),
        result_file_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        raw_manifest_hash=raw_manifest_hash,
        decision=result.decision,
    )


def write_audit(path: Path, audit: JamFullAcquisitionAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamFullAcquisitionAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam full acquisition audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamFullAcquisitionAudit:
    if args.output.exists():
        raise ValueError("Jam full acquisition audit exists; use --check")
    protocol, result = load_inputs(
        protocol_path=args.protocol,
        result_path=args.result,
    )
    raw_manifest_hash = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
        raw_manifest_hash=raw_manifest_hash,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"archives={audit.raw_archive_count} decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> JamFullAcquisitionAudit:
    protocol, result = load_inputs(
        protocol_path=args.protocol,
        result_path=args.result,
    )
    raw_manifest_hash = reconstruct(
        protocol=protocol,
        result=result,
        evidence_root=args.evidence_root,
    )
    audit = JamFullAcquisitionAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
        raw_manifest_hash=raw_manifest_hash,
    )
    if audit != expected or not audit_jam_full_acquisition_audit(audit):
        raise ValueError("Jam full acquisition audit is not reproducible")
    print(
        "PASS "
        f"jam_full_audit={audit.audit_evidence_hash} "
        f"result_file={audit.result_file_sha256} "
        f"archives={audit.raw_archive_count} "
        f"reconstructed={audit.reconstructed_month_count} "
        f"returns={audit.return_metrics_calculated} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently rebuild and audit the full Jam archive acquisition."
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
