import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.jam_archive_metadata_census import (
    JamArchiveMetadataCensusAudit,
    JamArchiveMetadataCensusContract,
    JamArchiveMetadataCensusResult,
    audit_jam_archive_census_audit,
    audit_jam_archive_census_contract,
    audit_jam_archive_census_result,
    build_jam_archive_census_audit,
)

DEFAULT_CONTRACT = Path(
    "data/evidence/jam_archive_metadata_census_contract_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/jam_archive_metadata_census_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_metadata_census_audit_v1.json"
)


def load_inputs(
    contract_path: Path,
    result_path: Path,
) -> tuple[
    JamArchiveMetadataCensusContract,
    JamArchiveMetadataCensusResult,
]:
    contract = JamArchiveMetadataCensusContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    result = JamArchiveMetadataCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if not audit_jam_archive_census_contract(contract):
        raise ValueError("Jam archive census contract audit failed")
    if not audit_jam_archive_census_result(result):
        raise ValueError("Jam archive census result audit failed")
    if (
        result.contract_evidence_hash != contract.contract_evidence_hash
        or result.target_manifest_hash != contract.target_manifest_hash
        or len({record.checksum_url for record in result.records}) != 96
        or any(record.final_url != record.checksum_url for record in result.records)
        or result.archive_head_requests_made
        or result.archive_payload_requests_made
        or result.archive_payload_bytes_received
        or result.redirects_followed
        or result.market_numeric_values_inspected
        or result.features_calculated
        or result.parameters_defined
        or result.return_metrics_calculated
        or result.strategy_executions
    ):
        raise ValueError("Jam archive census authority or lineage boundary failed")
    return contract, result


def authoritative_audit(
    *,
    audited_at: datetime,
    result_path: Path,
    result: JamArchiveMetadataCensusResult,
) -> JamArchiveMetadataCensusAudit:
    return build_jam_archive_census_audit(
        audited_at=audited_at,
        result_path=result_path.as_posix(),
        result_file_sha256=hashlib.sha256(result_path.read_bytes()).hexdigest(),
        result_evidence_hash=result.result_evidence_hash,
        contract_evidence_hash=result.contract_evidence_hash,
        target_manifest_hash=result.target_manifest_hash,
        checksum_get_attempt_count=(
            result.summary.checksum_http_attempt_count
        ),
        checksum_response_bytes=result.summary.checksum_response_bytes,
        coverage_complete=result.summary.complete,
        decision=result.decision,
    )


def write_audit(path: Path, audit: JamArchiveMetadataCensusAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if JamArchiveMetadataCensusAudit.model_validate_json(serialized) != audit:
        raise ValueError("Jam archive census audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_write(args) -> JamArchiveMetadataCensusAudit:
    if args.output.exists():
        raise ValueError("Jam archive census audit exists; use --check")
    _, result = load_inputs(args.contract, args.result)
    audit = authoritative_audit(
        audited_at=datetime.now(UTC),
        result_path=args.result,
        result=result,
    )
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"coverage={audit.coverage_complete} "
        f"payload_requests={audit.archive_payload_requests_made}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamArchiveMetadataCensusAudit:
    _, result = load_inputs(args.contract, args.result)
    audit = JamArchiveMetadataCensusAudit.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_audit(
        audited_at=audit.audited_at,
        result_path=args.result,
        result=result,
    )
    if audit != expected or not audit_jam_archive_census_audit(audit):
        raise ValueError("Jam archive census audit is not reproducible")
    print(
        "PASS "
        f"jam_archive_census_audit={audit.audit_evidence_hash} "
        f"result_file={audit.result_file_sha256} "
        f"coverage={audit.coverage_complete} "
        f"payload_requests={audit.archive_payload_requests_made} "
        f"decision={audit.decision}",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently write or verify the Jam archive metadata census audit."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
