from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_archive_quality_remediation import (  # noqa: E402
    JamArchiveQualityAudit,
    JamArchiveQualityResult,
    audit_jam_archive_quality_audit,
    audit_jam_archive_quality_result,
    build_jam_archive_quality_audit,
)
from scripts.run_jam_archive_quality_remediation import (  # noqa: E402
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_PARENT_AUDIT,
    DEFAULT_PARENT_PROTOCOL,
    DEFAULT_PARENT_RESULT,
    DEFAULT_PROTOCOL,
    DEFAULT_TEMP_ROOT,
    _validated_temp_root,
    authoritative_result,
    load_inputs,
    reconstruct,
    runner_contract_hash,
)

DEFAULT_RESULT = Path(
    "data/evidence/jam_archive_quality_remediation_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_quality_remediation_audit_v1.json"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def authoritative_audit(
    *,
    audited_at: datetime,
    protocol_path: Path,
    result_path: Path,
    result: JamArchiveQualityResult,
    mismatch_month_count: int,
) -> JamArchiveQualityAudit:
    return build_jam_archive_quality_audit(
        audited_at=audited_at,
        protocol_path=protocol_path.as_posix(),
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=result.protocol_evidence_hash,
        result_path=result_path.as_posix(),
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        mismatch_month_count_reconstructed=mismatch_month_count,
        issue_manifest_hash=result.issue_manifest_hash,
        quarantined_minute_manifest_hash=(
            result.quarantined_minute_manifest_hash
        ),
        decision=result.decision,
    )


def reconstruct_and_verify(args):
    protocol, parent_protocol, parent_result, parent_audit = load_inputs(
        protocol_path=args.protocol,
        parent_protocol_path=args.parent_protocol,
        parent_result_path=args.parent_result,
        parent_audit_path=args.parent_audit,
    )
    result = JamArchiveQualityResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_archive_quality_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.parent_result_evidence_hash
        != parent_result.result_evidence_hash
        or result.parent_audit_evidence_hash != parent_audit.audit_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.feature_fields_created
        or result.parameters_defined
        or result.thresholds_defined
        or result.return_metrics_calculated
        or result.strategy_executions
        or result.creates_candidate
        or result.creates_paper_eligibility
        or result.creates_testnet_order_authority
        or result.creates_production_authority
        or result.creates_live_eligibility
    ):
        raise ValueError("Jam quality result lineage or authority changed")
    duplicate, gaps, row_defects, mismatches, mismatch_month_count = reconstruct(
        parent_protocol=parent_protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        evidence_root=args.evidence_root,
        temp_root=_validated_temp_root(args.temp_root),
    )
    expected = authoritative_result(
        generated_at=result.generated_at,
        protocol=protocol,
        parent_result=parent_result,
        parent_audit=parent_audit,
        duplicate=duplicate,
        gaps=gaps,
        row_defects=row_defects,
        mismatches=mismatches,
    )
    if result != expected:
        raise ValueError("Jam quality raw-file reconstruction changed")
    return result, mismatch_month_count


def write_audit(path: Path, audit: JamArchiveQualityAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamArchiveQualityAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam quality audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamArchiveQualityAudit:
    if args.output.exists():
        raise ValueError("Jam quality audit exists; use --check")
    result, mismatch_month_count = reconstruct_and_verify(args)
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        protocol_path=args.protocol,
        result_path=args.result,
        result=result,
        mismatch_month_count=mismatch_month_count,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"mismatch_months={audit.mismatch_month_count_reconstructed} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def run_check(args) -> JamArchiveQualityAudit:
    result, mismatch_month_count = reconstruct_and_verify(args)
    audit = JamArchiveQualityAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        protocol_path=args.protocol,
        result_path=args.result,
        result=result,
        mismatch_month_count=mismatch_month_count,
    )
    if audit != expected or not audit_jam_archive_quality_audit(audit):
        raise ValueError("Jam quality audit is not reproducible")
    print(
        "PASS "
        f"jam_quality_audit={audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} "
        f"issue_manifest={audit.issue_manifest_hash} "
        f"returns={audit.return_metrics_calculated} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Independently audit Jam archive quality remediation."
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-result",
        type=Path,
        default=DEFAULT_PARENT_RESULT,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_check(args) if args.check else run_write(args)
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
