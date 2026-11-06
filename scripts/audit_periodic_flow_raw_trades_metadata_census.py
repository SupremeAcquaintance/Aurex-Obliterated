from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RawTradesMetadataCensusAudit,
    RawTradesMetadataCensusResult,
    audit_raw_trades_audit,
    audit_raw_trades_result,
    build_raw_trades_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    MODULE_PATH,
    file_sha256,
)
from scripts.run_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_RESULT,
)
from scripts.run_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    authoritative_result,
    load_protocol,
    runner_contract_hash,
)

DEFAULT_AUDIT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_raw_trades_metadata_census.py"
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
) -> RawTradesMetadataCensusResult:
    protocol, protocol_audit = load_protocol(protocol_path, protocol_audit_path)
    stored = RawTradesMetadataCensusResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    expected = authoritative_result(
        generated_at=stored.generated_at,
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        protocol=protocol,
        protocol_audit=protocol_audit,
        records=stored.records,
    )
    if (
        stored != expected
        or not audit_raw_trades_result(stored)
        or stored.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Q1 raw-trades census failed independent reconstruction")
    return stored


def authoritative_audit(
    *,
    audited_at: datetime,
    protocol_path: Path,
    protocol_audit_path: Path,
    result_path: Path,
) -> RawTradesMetadataCensusAudit:
    result = reconstruct_result(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        result_path=result_path,
    )
    return build_raw_trades_audit(
        audited_at=audited_at,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        protocol_evidence_hash=result.protocol_evidence_hash,
        runner_contract_hash=result.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        present_count=result.summary.present_count,
        development_present_count=result.summary.development_present_count,
        validation_metadata_present_count=(
            result.summary.validation_metadata_present_count
        ),
        checksum_get_requests_made=result.checksum_get_requests_made,
        decision=result.decision,
        next_authorization=result.next_authorization,
    )


def write_audit(path: Path, audit: RawTradesMetadataCensusAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if RawTradesMetadataCensusAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 raw-trades census audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale census-audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 USD-M raw-trades checksum census."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = RawTradesMetadataCensusAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                audited_at=stored.audited_at,
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                result_path=args.result,
            )
            if stored != expected or not audit_raw_trades_audit(stored):
                raise ValueError("Stored Q1 raw-trades census audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite census audit: {args.output}")
        audit = authoritative_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            result_path=args.result,
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"present={audit.present_count}/72 decision={audit.decision} "
            "payloads=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
