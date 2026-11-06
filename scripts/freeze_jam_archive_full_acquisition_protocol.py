import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.jam_archive_full_acquisition import (
    JamFullAcquisitionProtocol,
    JamFullAcquisitionTarget,
    audit_jam_full_acquisition_protocol,
    build_jam_full_acquisition_protocol,
)
from aurex.backtest_engine.jam_archive_metadata_census import (
    JamArchiveMetadataCensusResult,
    audit_jam_archive_census_result,
)
from aurex.backtest_engine.jam_archive_payload_pilot import (
    JamPayloadPilotAudit,
    JamPayloadPilotProtocol,
    JamPayloadPilotResult,
    audit_jam_payload_pilot_audit,
    audit_jam_payload_pilot_protocol,
    audit_jam_payload_pilot_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/jam_archive_metadata_census_result_v1.json"
)
DEFAULT_PILOT_PROTOCOL = Path(
    "data/evidence/jam_archive_payload_pilot_protocol_v1.json"
)
DEFAULT_PILOT_RESULT = Path(
    "data/evidence/jam_archive_payload_pilot_result_v1.json"
)
DEFAULT_PILOT_AUDIT = Path(
    "data/evidence/jam_archive_payload_pilot_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_full_acquisition_protocol_v1.json"
)
EXPECTED_CENSUS_RESULT_HASH = (
    "e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e"
)
EXPECTED_CENSUS_RESULT_FILE_SHA256 = (
    "5a998bc2ff7b778c7c6052a297114d0d490314bff1d47b779d24abf46aeb5102"
)
EXPECTED_PILOT_PROTOCOL_HASH = (
    "1e9a6ef48ac06353f933d21cb193bf0b1489f03f79e6a4562062a0ddddbba24e"
)
EXPECTED_PILOT_RESULT_HASH = (
    "f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974"
)
EXPECTED_PILOT_AUDIT_HASH = (
    "bc8880252f50215be1fbb46803e1325d5e40c2b34101ad02bad0d4284ad710bf"
)


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_jam_archive_full_acquisition_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_full_acquisition.py",
        ]
    )


def load_inputs(
    *,
    census_result_path: Path,
    pilot_protocol_path: Path,
    pilot_result_path: Path,
    pilot_audit_path: Path,
) -> tuple[
    JamArchiveMetadataCensusResult,
    JamPayloadPilotProtocol,
    JamPayloadPilotResult,
    JamPayloadPilotAudit,
]:
    census = JamArchiveMetadataCensusResult.model_validate_json(
        census_result_path.read_text(encoding="utf-8")
    )
    pilot_protocol = JamPayloadPilotProtocol.model_validate_json(
        pilot_protocol_path.read_text(encoding="utf-8")
    )
    pilot_result = JamPayloadPilotResult.model_validate_json(
        pilot_result_path.read_text(encoding="utf-8")
    )
    pilot_audit = JamPayloadPilotAudit.model_validate_json(
        pilot_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_archive_census_result(census)
        or not audit_jam_payload_pilot_protocol(pilot_protocol)
        or not audit_jam_payload_pilot_result(pilot_result)
        or not audit_jam_payload_pilot_audit(pilot_audit)
        or census.result_evidence_hash != EXPECTED_CENSUS_RESULT_HASH
        or hashlib.sha256(census_result_path.read_bytes()).hexdigest()
        != EXPECTED_CENSUS_RESULT_FILE_SHA256
        or pilot_protocol.protocol_evidence_hash
        != EXPECTED_PILOT_PROTOCOL_HASH
        or pilot_result.result_evidence_hash != EXPECTED_PILOT_RESULT_HASH
        or pilot_audit.audit_evidence_hash != EXPECTED_PILOT_AUDIT_HASH
        or pilot_result.protocol_evidence_hash
        != pilot_protocol.protocol_evidence_hash
        or pilot_audit.result_evidence_hash != pilot_result.result_evidence_hash
        or pilot_result.decision
        != "PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION"
        or pilot_result.next_required_authorization
        != "AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION"
        or pilot_result.return_metrics_calculated
        or pilot_result.creates_candidate
        or pilot_result.creates_testnet_order_authority
        or pilot_result.creates_live_eligibility
    ):
        raise ValueError("Jam full acquisition input lineage changed")
    return census, pilot_protocol, pilot_result, pilot_audit


def acquisition_targets(
    census: JamArchiveMetadataCensusResult,
) -> list[JamFullAcquisitionTarget]:
    targets = []
    for record in census.records:
        if (
            record.availability != "PRESENT"
            or record.published_archive_sha256 is None
        ):
            raise ValueError(f"Jam full target lacks checksum: {record.key}")
        targets.append(
            JamFullAcquisitionTarget(
                family=record.family,
                month=record.month,
                archive_url=record.archive_url,
                published_archive_sha256=record.published_archive_sha256,
                expected_csv_member=(
                    f"BTCUSDT-aggTrades-{record.month}.csv"
                    if record.family == "aggTrades"
                    else f"BTCUSDT-1m-{record.month}.csv"
                ),
                expected_column_count=(
                    8 if record.family == "aggTrades" else 12
                ),
                reuse_verified_pilot_file=record.month == "2019-01",
            )
        )
    return sorted(targets, key=lambda item: item.key)


def authoritative_protocol(
    *,
    frozen_at: datetime,
    census: JamArchiveMetadataCensusResult,
    pilot_protocol: JamPayloadPilotProtocol,
    pilot_result: JamPayloadPilotResult,
    pilot_audit: JamPayloadPilotAudit,
    census_result_path: Path,
) -> JamFullAcquisitionProtocol:
    return build_jam_full_acquisition_protocol(
        frozen_at=frozen_at,
        census_result_file_sha256=hashlib.sha256(
            census_result_path.read_bytes()
        ).hexdigest(),
        census_result_evidence_hash=census.result_evidence_hash,
        payload_pilot_protocol_evidence_hash=(
            pilot_protocol.protocol_evidence_hash
        ),
        payload_pilot_result_evidence_hash=pilot_result.result_evidence_hash,
        payload_pilot_audit_evidence_hash=pilot_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        targets=acquisition_targets(census),
        limitations=[
            (
                "The manifest is exactly the ninety-six BTCUSDT spot monthly "
                "aggregate-trade and one-minute-kline archives from January 2019 "
                "through December 2022."
            ),
            (
                "The two independently verified January 2019 pilot files must be "
                "reused in place and may not be downloaded again."
            ),
            (
                "Only the remaining ninety-four exact archive URLs may receive HEAD "
                "or resumable GET requests."
            ),
            (
                "No archive may exceed 2.5 GB compressed and all archives together "
                "may not exceed 60 GB compressed."
            ),
            (
                "At least 20 GB free disk must remain after all observed compressed "
                "archives are accounted for."
            ),
            (
                "Every file must match its published SHA-256 and contain exactly one "
                "safe expected CSV member within frozen ZIP expansion limits."
            ),
            (
                "Every aggregate-trade month must have valid ordered contiguous "
                "aggregate IDs, raw-trade spans, timestamps, prices, quantities, and "
                "maker flags."
            ),
            (
                "Every kline month must contain exactly every aligned one-minute row "
                "with valid close times, OHLC, volumes, and trade counts."
            ),
            (
                "Each month must reconcile raw-trade count, OHLC, base and quote "
                "volume, and taker-buy base and quote volume within 0.00000001."
            ),
            (
                "Market values may be inspected only for source-quality validation; "
                "no Jam feature, threshold, signal, return, PnL, or ranking may be "
                "calculated."
            ),
            (
                "The acquired pool remains provisional no-return evidence until a "
                "separate evidence-partition and feature-specification gate passes."
            ),
            (
                "This protocol grants no candidate, paper, Testnet strategy-order, "
                "production, live, capital, or profit authority."
            ),
        ],
    )


def write_protocol(path: Path, protocol: JamFullAcquisitionProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if JamFullAcquisitionProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Jam full acquisition protocol did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamFullAcquisitionProtocol:
    if args.output.exists():
        raise ValueError("Jam full acquisition protocol exists; use --check")
    census, pilot_protocol, pilot_result, pilot_audit = load_inputs(
        census_result_path=args.census_result,
        pilot_protocol_path=args.pilot_protocol,
        pilot_result_path=args.pilot_result,
        pilot_audit_path=args.pilot_audit,
    )
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        census=census,
        pilot_protocol=pilot_protocol,
        pilot_result=pilot_result,
        pilot_audit=pilot_audit,
        census_result_path=args.census_result,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"targets={len(protocol.targets)} network={protocol.network_target_count} "
        f"max_bytes={protocol.maximum_total_archive_bytes}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamFullAcquisitionProtocol:
    census, pilot_protocol, pilot_result, pilot_audit = load_inputs(
        census_result_path=args.census_result,
        pilot_protocol_path=args.pilot_protocol,
        pilot_result_path=args.pilot_result,
        pilot_audit_path=args.pilot_audit,
    )
    protocol = JamFullAcquisitionProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        census=census,
        pilot_protocol=pilot_protocol,
        pilot_result=pilot_result,
        pilot_audit=pilot_audit,
        census_result_path=args.census_result,
    )
    if protocol != expected or not audit_jam_full_acquisition_protocol(protocol):
        raise ValueError("Jam full acquisition protocol is not reproducible")
    print(
        "PASS "
        f"jam_full_protocol={protocol.protocol_evidence_hash} "
        f"targets={len(protocol.targets)} network={protocol.network_target_count} "
        f"returns={protocol.return_calculation_permitted} "
        f"live={protocol.live_permitted}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the Jam 2019-2022 archive acquisition."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--census-result",
        type=Path,
        default=DEFAULT_CENSUS_RESULT,
    )
    parser.add_argument(
        "--pilot-protocol",
        type=Path,
        default=DEFAULT_PILOT_PROTOCOL,
    )
    parser.add_argument(
        "--pilot-result",
        type=Path,
        default=DEFAULT_PILOT_RESULT,
    )
    parser.add_argument(
        "--pilot-audit",
        type=Path,
        default=DEFAULT_PILOT_AUDIT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.freeze:
            run_freeze(args)
        else:
            run_check(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
