from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RawTradesMetadataCensusProtocol,
    RawTradesMetadataProtocolAudit,
    audit_raw_trades_protocol,
    audit_raw_trades_protocol_audit,
    build_raw_trades_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (  # noqa: E402  # noqa: E402
    DEFAULT_PARENT_AUDIT,
    DEFAULT_PARENT_RESULT,
    DEFAULT_READINESS_AUDIT,
    DEFAULT_READINESS_RESULT,
    MODULE_PATH,
    authoritative_protocol,
    file_sha256,
)

DEFAULT_AUDIT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_protocol_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_raw_trades_metadata_protocol.py"
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


def authoritative_audit(
    *,
    audited_at: datetime,
    protocol_path: Path,
    parent_result_path: Path,
    parent_audit_path: Path,
    readiness_result_path: Path,
    readiness_audit_path: Path,
) -> RawTradesMetadataProtocolAudit:
    stored = RawTradesMetadataCensusProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=stored.frozen_at,
        parent_result_path=parent_result_path,
        parent_audit_path=parent_audit_path,
        readiness_result_path=readiness_result_path,
        readiness_audit_path=readiness_audit_path,
    )
    if stored != expected or not audit_raw_trades_protocol(stored):
        raise ValueError("Q1 raw-trades protocol failed independent reconstruction")
    return build_raw_trades_protocol_audit(
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=stored.protocol_evidence_hash,
        builder_contract_hash=stored.builder_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def write_audit(path: Path, audit: RawTradesMetadataProtocolAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if RawTradesMetadataProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 raw-trades protocol audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale protocol-audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the frozen Q1 raw-trades census protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--parent-result", type=Path, default=DEFAULT_PARENT_RESULT)
    parser.add_argument("--parent-audit", type=Path, default=DEFAULT_PARENT_AUDIT)
    parser.add_argument(
        "--readiness-result", type=Path, default=DEFAULT_READINESS_RESULT
    )
    parser.add_argument(
        "--readiness-audit", type=Path, default=DEFAULT_READINESS_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = RawTradesMetadataProtocolAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                audited_at=stored.audited_at,
                protocol_path=args.protocol,
                parent_result_path=args.parent_result,
                parent_audit_path=args.parent_audit,
                readiness_result_path=args.readiness_result,
                readiness_audit_path=args.readiness_audit,
            )
            if stored != expected or not audit_raw_trades_protocol_audit(stored):
                raise ValueError("Stored raw-trades protocol audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} requests=0",
                flush=True,
            )
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite protocol audit: {args.output}")
        audit = authoritative_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol,
            parent_result_path=args.parent_result,
            parent_audit_path=args.parent_audit,
            readiness_result_path=args.readiness_result,
            readiness_audit_path=args.readiness_audit,
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "targets=72 requests=0 payloads=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
