from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_daily_cross_source import (  # noqa: E402
    Q1_DAILY_CROSS_PASS_DECISION,
    PeriodicFlowDailyCrossSourceAudit,
    PeriodicFlowDailyCrossSourceResult,
    audit_daily_cross_audit,
    audit_daily_cross_result,
)
from aurex.backtest_engine.periodic_flow_payload_pilot import (  # noqa: E402
    PeriodicFlowPayloadPilotAudit,
    PeriodicFlowPayloadPilotResult,
    audit_periodic_flow_payload_audit,
    audit_periodic_flow_payload_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RAW_TRADES_PASS_DECISION,
    RawTradesMetadataCensusAudit,
    RawTradesMetadataCensusResult,
    audit_raw_trades_audit,
    audit_raw_trades_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (  # noqa: E402
    RAW_PAYLOAD_ARCHIVE_SHA256,
    QualifiedSpotPayloadReference,
    RawTradesPayloadPilotProtocol,
    RawTradesPayloadTarget,
    audit_raw_payload_protocol,
    build_raw_payload_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_RAW_CENSUS_RESULT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_result_v1.json"
)
DEFAULT_RAW_CENSUS_AUDIT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_audit_v1.json"
)
DEFAULT_SOURCE_RESULT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_result_v1.json"
)
DEFAULT_SOURCE_AUDIT = Path(
    "data/evidence/q1_periodic_flow_daily_cross_source_audit_v1.json"
)
DEFAULT_SPOT_RESULT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_result_v1.json"
)
DEFAULT_SPOT_AUDIT = Path(
    "data/evidence/q1_periodic_flow_payload_pilot_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_raw_trades_payload_pilot.py"
)
SCRIPT_PATH = Path("scripts/freeze_periodic_flow_raw_trades_payload_pilot.py")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_contract_hash(paths: tuple[Path, ...]) -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                path.as_posix(): file_sha256(PROJECT_ROOT / path)
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash((MODULE_PATH, SCRIPT_PATH))


def load_inputs(
    *,
    raw_census_result_path: Path,
    raw_census_audit_path: Path,
    source_result_path: Path,
    source_audit_path: Path,
    spot_result_path: Path,
    spot_audit_path: Path,
) -> tuple[
    RawTradesMetadataCensusResult,
    RawTradesMetadataCensusAudit,
    PeriodicFlowDailyCrossSourceResult,
    PeriodicFlowDailyCrossSourceAudit,
    PeriodicFlowPayloadPilotResult,
    PeriodicFlowPayloadPilotAudit,
]:
    raw_census = RawTradesMetadataCensusResult.model_validate_json(
        raw_census_result_path.read_text(encoding="utf-8")
    )
    raw_census_audit = RawTradesMetadataCensusAudit.model_validate_json(
        raw_census_audit_path.read_text(encoding="utf-8")
    )
    source = PeriodicFlowDailyCrossSourceResult.model_validate_json(
        source_result_path.read_text(encoding="utf-8")
    )
    source_audit = PeriodicFlowDailyCrossSourceAudit.model_validate_json(
        source_audit_path.read_text(encoding="utf-8")
    )
    spot_result = PeriodicFlowPayloadPilotResult.model_validate_json(
        spot_result_path.read_text(encoding="utf-8")
    )
    spot_audit = PeriodicFlowPayloadPilotAudit.model_validate_json(
        spot_audit_path.read_text(encoding="utf-8")
    )
    raw_record = next(
        (item for item in raw_census.records if item.month == "2020-01"),
        None,
    )
    spot = next(
        (item for item in spot_result.archive_evidence if item.product == "SPOT"),
        None,
    )
    if (
        not audit_raw_trades_result(raw_census)
        or not audit_raw_trades_audit(raw_census_audit)
        or raw_census_audit.result_file_sha256
        != file_sha256(raw_census_result_path)
        or raw_census_audit.result_evidence_hash != raw_census.result_evidence_hash
        or raw_census.decision != RAW_TRADES_PASS_DECISION
        or not raw_census.authorizes_one_month_payload_protocol
        or raw_record is None
        or raw_record.archive_sha256 != RAW_PAYLOAD_ARCHIVE_SHA256
        or not audit_daily_cross_result(source)
        or not audit_daily_cross_audit(source_audit)
        or source_audit.result_file_sha256 != file_sha256(source_result_path)
        or source_audit.result_evidence_hash != source.result_evidence_hash
        or source.decision != Q1_DAILY_CROSS_PASS_DECISION
        or not source.authorizes_usdm_raw_trades_metadata_census_protocol
        or not audit_periodic_flow_payload_result(spot_result)
        or not audit_periodic_flow_payload_audit(spot_audit)
        or spot_audit.result_file_sha256 != file_sha256(spot_result_path)
        or spot_audit.result_evidence_hash != spot_result.result_evidence_hash
        or spot is None
        or not spot.archive_pass
        or spot.unique_minute_count != 44_640
        or spot_audit.archive_file_sha256.get("SPOT") != spot.archive_sha256
        or raw_census.archive_payload_requests_made
        or raw_census.return_metrics_calculated
        or source.return_metrics_calculated
        or spot_result.return_metrics_calculated
    ):
        raise ValueError("Q1 raw payload parent lineage is not intact")
    return (
        raw_census,
        raw_census_audit,
        source,
        source_audit,
        spot_result,
        spot_audit,
    )


def authoritative_protocol(
    *,
    frozen_at: datetime,
    raw_census_result_path: Path,
    raw_census_audit_path: Path,
    source_result_path: Path,
    source_audit_path: Path,
    spot_result_path: Path,
    spot_audit_path: Path,
) -> RawTradesPayloadPilotProtocol:
    (
        raw_census,
        raw_census_audit,
        source,
        source_audit,
        spot_result,
        spot_audit,
    ) = load_inputs(
        raw_census_result_path=raw_census_result_path,
        raw_census_audit_path=raw_census_audit_path,
        source_result_path=source_result_path,
        source_audit_path=source_audit_path,
        spot_result_path=spot_result_path,
        spot_audit_path=spot_audit_path,
    )
    spot = next(
        item for item in spot_result.archive_evidence if item.product == "SPOT"
    )
    raw_record = next(item for item in raw_census.records if item.month == "2020-01")
    spot_reference = QualifiedSpotPayloadReference(
        source_result_file_sha256=file_sha256(spot_result_path),
        source_result_evidence_hash=spot_result.result_evidence_hash,
        source_audit_file_sha256=file_sha256(spot_audit_path),
        source_audit_evidence_hash=spot_audit.audit_evidence_hash,
        row_count=spot.row_count,
        first_timestamp_ms=spot.first_timestamp_ms,
        last_timestamp_ms=spot.last_timestamp_ms,
        unique_minute_count=spot.unique_minute_count,
    )
    target = RawTradesPayloadTarget(
        archive_url=raw_record.archive_url,
        published_archive_sha256=raw_record.archive_sha256,
    )
    return build_raw_payload_protocol(
        frozen_at=frozen_at,
        raw_census_result_file_sha256=file_sha256(raw_census_result_path),
        raw_census_result_evidence_hash=raw_census.result_evidence_hash,
        raw_census_audit_file_sha256=file_sha256(raw_census_audit_path),
        raw_census_audit_evidence_hash=raw_census_audit.audit_evidence_hash,
        source_adjudication_result_file_sha256=file_sha256(source_result_path),
        source_adjudication_result_evidence_hash=source.result_evidence_hash,
        source_adjudication_audit_file_sha256=file_sha256(source_audit_path),
        source_adjudication_audit_evidence_hash=source_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        qualified_spot_reference=spot_reference,
        target=target,
        target_manifest_hash=universe_evidence_hash(
            {
                "qualified_spot_reference": spot_reference.model_dump(),
                "target": target.model_dump(),
            }
        ),
        limitations=(
            "Only the checksum-pinned 2020-01 USD-M raw-trades ZIP may be requested.",
            "The qualified Spot archive is local reference evidence and is not re-requested.",
            "Raw IDs and timestamps may be parsed; price and quantity fields remain forbidden.",
            "Forward raw-ID gaps are bounded but cannot be silently discarded.",
            "Validation, holdout, and forward outcomes remain unopened.",
            "No feature, threshold, horizon, signal, strategy, or return is calculated.",
            "A pass permits only a separate paired full-development acquisition protocol.",
            "Paper and Testnet strategy-order authority remain false.",
            "Production, live, real-capital authority, and profit remain false.",
        ),
    )


def write_protocol(path: Path, protocol: RawTradesPayloadPilotProtocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite raw payload protocol: {path}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if RawTradesPayloadPilotProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Q1 raw payload protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale raw payload protocol transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Q1 one-month raw-trades payload protocol."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
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
            stored = RawTradesPayloadPilotProtocol.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_protocol(
                frozen_at=stored.frozen_at,
                raw_census_result_path=args.raw_census_result,
                raw_census_audit_path=args.raw_census_audit,
                source_result_path=args.source_result,
                source_audit_path=args.source_audit,
                spot_result_path=args.spot_result,
                spot_audit_path=args.spot_audit,
            )
            if stored != expected or not audit_raw_payload_protocol(stored):
                raise ValueError("Stored Q1 raw payload protocol changed")
            print(
                f"PASS {args.output} {stored.protocol_evidence_hash} "
                "payload_requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        protocol = authoritative_protocol(
            frozen_at=datetime.now(UTC),
            raw_census_result_path=args.raw_census_result,
            raw_census_audit_path=args.raw_census_audit,
            source_result_path=args.source_result,
            source_audit_path=args.source_audit,
            spot_result_path=args.spot_result,
            spot_audit_path=args.spot_audit,
        )
        write_protocol(args.output, protocol)
        print(
            f"FROZEN {args.output} {protocol.protocol_evidence_hash} "
            "targets=1 payload_requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
