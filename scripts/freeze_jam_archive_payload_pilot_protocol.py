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
)
from aurex.backtest_engine.jam_archive_payload_pilot import (
    JAM_PAYLOAD_PILOT_MONTH,
    JamPayloadPilotProtocol,
    audit_jam_payload_pilot_protocol,
    authoritative_payload_targets,
    build_jam_payload_pilot_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CENSUS_CONTRACT = Path(
    "data/evidence/jam_archive_metadata_census_contract_v1.json"
)
DEFAULT_CENSUS_RESULT = Path(
    "data/evidence/jam_archive_metadata_census_result_v1.json"
)
DEFAULT_CENSUS_AUDIT = Path(
    "data/evidence/jam_archive_metadata_census_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_payload_pilot_protocol_v1.json"
)
EXPECTED_CENSUS_CONTRACT_HASH = (
    "3670f121f303bf39a17dbc7b057bde913e30252687139046ae4785269f4e8302"
)
EXPECTED_CENSUS_RESULT_HASH = (
    "e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e"
)
EXPECTED_CENSUS_RESULT_FILE_SHA256 = (
    "5a998bc2ff7b778c7c6052a297114d0d490314bff1d47b779d24abf46aeb5102"
)
EXPECTED_CENSUS_AUDIT_HASH = (
    "3f57bd2fb843059606bf32a284db0cc15e58c436115a922073b0c862aaaabfcb"
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
            / "freeze_jam_archive_payload_pilot_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_payload_pilot.py",
        ]
    )


def load_inputs(
    *,
    census_contract_path: Path,
    census_result_path: Path,
    census_audit_path: Path,
) -> tuple[
    JamArchiveMetadataCensusContract,
    JamArchiveMetadataCensusResult,
    JamArchiveMetadataCensusAudit,
]:
    census_contract = JamArchiveMetadataCensusContract.model_validate_json(
        census_contract_path.read_text(encoding="utf-8")
    )
    census_result = JamArchiveMetadataCensusResult.model_validate_json(
        census_result_path.read_text(encoding="utf-8")
    )
    census_audit = JamArchiveMetadataCensusAudit.model_validate_json(
        census_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_archive_census_contract(census_contract)
        or not audit_jam_archive_census_result(census_result)
        or not audit_jam_archive_census_audit(census_audit)
        or census_contract.contract_evidence_hash
        != EXPECTED_CENSUS_CONTRACT_HASH
        or census_result.result_evidence_hash != EXPECTED_CENSUS_RESULT_HASH
        or hashlib.sha256(census_result_path.read_bytes()).hexdigest()
        != EXPECTED_CENSUS_RESULT_FILE_SHA256
        or census_audit.audit_evidence_hash != EXPECTED_CENSUS_AUDIT_HASH
        or census_result.contract_evidence_hash
        != census_contract.contract_evidence_hash
        or census_audit.result_evidence_hash != census_result.result_evidence_hash
        or census_result.decision
        != "PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION"
        or census_result.next_required_authorization
        != "AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT"
        or census_result.archive_payload_requests_made != 0
        or census_result.market_numeric_values_inspected
        or census_result.return_metrics_calculated
        or census_result.creates_candidate
        or census_result.creates_testnet_order_authority
        or census_result.creates_live_eligibility
    ):
        raise ValueError("Jam metadata census lineage or authority boundary changed")
    selected = {
        record.family: record
        for record in census_result.records
        if record.month == JAM_PAYLOAD_PILOT_MONTH
    }
    expected_targets = {
        target.family: target for target in authoritative_payload_targets()
    }
    if set(selected) != set(expected_targets) or any(
        selected[family].archive_url != target.archive_url
        or selected[family].published_archive_sha256
        != target.published_archive_sha256
        or selected[family].availability != "PRESENT"
        for family, target in expected_targets.items()
    ):
        raise ValueError("Jam payload pilot month does not match census metadata")
    return census_contract, census_result, census_audit


def authoritative_protocol(
    *,
    frozen_at: datetime,
    census_contract: JamArchiveMetadataCensusContract,
    census_result: JamArchiveMetadataCensusResult,
    census_audit: JamArchiveMetadataCensusAudit,
    census_result_path: Path,
) -> JamPayloadPilotProtocol:
    return build_jam_payload_pilot_protocol(
        frozen_at=frozen_at,
        census_contract_evidence_hash=(
            census_contract.contract_evidence_hash
        ),
        census_result_file_sha256=hashlib.sha256(
            census_result_path.read_bytes()
        ).hexdigest(),
        census_result_evidence_hash=census_result.result_evidence_hash,
        census_audit_evidence_hash=census_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "The pilot month is the earliest month in the provisional pool, "
                "selected before payload access without inspecting market outcomes."
            ),
            (
                "Only the frozen BTCUSDT January 2019 aggregate-trade and one-minute "
                "kline ZIP archives may be requested."
            ),
            (
                "At most six HEAD and six payload GET attempts are permitted; "
                "redirects and any non-frozen URL are forbidden."
            ),
            (
                "Each archive is capped at 750,000,000 compressed bytes and both "
                "archives together are capped at 800,000,000 bytes."
            ),
            (
                "ZIPs must contain exactly one expected, non-encrypted, non-link CSV "
                "member within the frozen expansion and uncompressed-byte limits."
            ),
            (
                "The pilot may inspect raw market fields only to validate schema, "
                "ordering, continuity, internal arithmetic, and cross-family source "
                "reconciliation."
            ),
            (
                "Aggregate trades must have monotonic contiguous IDs and valid "
                "timestamps, prices, quantities, raw-trade spans, and booleans."
            ),
            (
                "One-minute klines must contain exactly 44,640 aligned January 2019 "
                "rows with valid OHLC, volume, trade-count, and close-time invariants."
            ),
            (
                "Per-minute raw-trade count, OHLC, base and quote volume, and taker "
                "buy base and quote volume must reconcile within 0.00000001."
            ),
            (
                "No Jam feature, threshold, signal, return, PnL, candidate, paper "
                "eligibility, Testnet strategy order, production, live, or capital "
                "authority is permitted."
            ),
            (
                "A pass permits only a separately authorized and frozen acquisition "
                "protocol for the remaining 2019-2022 provisional archive pool."
            ),
        ],
    )


def write_protocol(path: Path, protocol: JamPayloadPilotProtocol) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if JamPayloadPilotProtocol.model_validate_json(serialized) != protocol:
        raise ValueError("Jam payload pilot protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamPayloadPilotProtocol:
    if args.output.exists():
        raise ValueError("Frozen Jam payload pilot protocol exists; use --check")
    census_contract, census_result, census_audit = load_inputs(
        census_contract_path=args.census_contract,
        census_result_path=args.census_result,
        census_audit_path=args.census_audit,
    )
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        census_contract=census_contract,
        census_result=census_result,
        census_audit=census_audit,
        census_result_path=args.census_result,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"month={protocol.pilot_month} targets={len(protocol.targets)} "
        f"max_bytes={protocol.maximum_total_archive_bytes}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamPayloadPilotProtocol:
    census_contract, census_result, census_audit = load_inputs(
        census_contract_path=args.census_contract,
        census_result_path=args.census_result,
        census_audit_path=args.census_audit,
    )
    protocol = JamPayloadPilotProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        census_contract=census_contract,
        census_result=census_result,
        census_audit=census_audit,
        census_result_path=args.census_result,
    )
    if protocol != expected or not audit_jam_payload_pilot_protocol(protocol):
        raise ValueError("Jam payload pilot protocol is not reproducible")
    print(
        "PASS "
        f"jam_payload_protocol={protocol.protocol_evidence_hash} "
        f"month={protocol.pilot_month} targets={len(protocol.targets)} "
        f"returns={protocol.return_calculation_permitted} "
        f"live={protocol.live_permitted}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the one-month Jam archive data-capability pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--census-contract",
        type=Path,
        default=DEFAULT_CENSUS_CONTRACT,
    )
    parser.add_argument(
        "--census-result",
        type=Path,
        default=DEFAULT_CENSUS_RESULT,
    )
    parser.add_argument(
        "--census-audit",
        type=Path,
        default=DEFAULT_CENSUS_AUDIT,
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
