from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    RawTradesPayloadPilotProtocol,
    RawTradesPayloadProtocolAudit,
    audit_raw_payload_protocol,
    audit_raw_payload_protocol_audit,
    build_raw_payload_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    DEFAULT_RAW_CENSUS_AUDIT,
    DEFAULT_RAW_CENSUS_RESULT,
    DEFAULT_SOURCE_AUDIT,
    DEFAULT_SOURCE_RESULT,
    DEFAULT_SPOT_AUDIT,
    DEFAULT_SPOT_RESULT,
    MODULE_PATH,
    authoritative_protocol,
    file_sha256,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_audit_v1.json"
)
AUDIT_SCRIPT_PATH = Path(
    "scripts/audit_periodic_flow_raw_trades_payload_protocol.py"
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
    raw_census_result_path: Path,
    raw_census_audit_path: Path,
    source_result_path: Path,
    source_audit_path: Path,
    spot_result_path: Path,
    spot_audit_path: Path,
) -> RawTradesPayloadProtocolAudit:
    stored = RawTradesPayloadPilotProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=stored.frozen_at,
        raw_census_result_path=raw_census_result_path,
        raw_census_audit_path=raw_census_audit_path,
        source_result_path=source_result_path,
        source_audit_path=source_audit_path,
        spot_result_path=spot_result_path,
        spot_audit_path=spot_audit_path,
    )
    if stored != expected or not audit_raw_payload_protocol(stored):
        raise ValueError("Q1 raw payload protocol failed independent reconstruction")
    return build_raw_payload_protocol_audit(
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=stored.protocol_evidence_hash,
        builder_contract_hash=stored.builder_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
    )


def write_audit(path: Path, audit: RawTradesPayloadProtocolAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite raw payload protocol audit: {path}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if RawTradesPayloadProtocolAudit.model_validate_json(serialized) != audit:
        raise ValueError("Q1 raw payload protocol audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale raw payload protocol-audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the Q1 raw-trades payload protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--raw-census-result", type=Path, default=DEFAULT_RAW_CENSUS_RESULT
    )
    parser.add_argument(
        "--raw-census-audit", type=Path, default=DEFAULT_RAW_CENSUS_AUDIT
    )
    parser.add_argument("--source-result", type=Path, default=DEFAULT_SOURCE_RESULT)
    parser.add_argument("--source-audit", type=Path, default=DEFAULT_SOURCE_AUDIT)
    parser.add_argument("--spot-result", type=Path, default=DEFAULT_SPOT_RESULT)
    parser.add_argument("--spot-audit", type=Path, default=DEFAULT_SPOT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = RawTradesPayloadProtocolAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(
                audited_at=stored.audited_at,
                protocol_path=args.protocol,
                raw_census_result_path=args.raw_census_result,
                raw_census_audit_path=args.raw_census_audit,
                source_result_path=args.source_result,
                source_audit_path=args.source_audit,
                spot_result_path=args.spot_result,
                spot_audit_path=args.spot_audit,
            )
            if stored != expected or not audit_raw_payload_protocol_audit(stored):
                raise ValueError("Stored Q1 raw payload protocol audit changed")
            print(
                f"PASS {args.output} {stored.audit_evidence_hash} requests=0",
                flush=True,
            )
            return 0
        audit = authoritative_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol,
            raw_census_result_path=args.raw_census_result,
            raw_census_audit_path=args.raw_census_audit,
            source_result_path=args.source_result,
            source_audit_path=args.source_audit,
            spot_result_path=args.spot_result,
            spot_audit_path=args.spot_audit,
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "targets=1 requests=0 payloads=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
