import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.jam_archive_metadata_census import (
    JamArchiveMetadataCensusContract,
    audit_jam_archive_census_contract,
    build_jam_archive_census_contract,
)
from aurex.backtest_engine.jam_successor_charter import (
    JamSuccessorHypothesisCharter,
    audit_jam_successor_hypothesis_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTER = Path(
    "data/evidence/jam_successor_hypothesis_charter_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_metadata_census_contract_v1.json"
)
EXPECTED_CHARTER_EVIDENCE_HASH = (
    "426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019"
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
            / "freeze_jam_archive_metadata_census_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_metadata_census.py",
        ]
    )


def load_charter(path: Path) -> JamSuccessorHypothesisCharter:
    charter = JamSuccessorHypothesisCharter.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_successor_hypothesis_charter(charter)
        or charter.charter_evidence_hash != EXPECTED_CHARTER_EVIDENCE_HASH
        or charter.next_required_authorization
        != "AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
        or charter.selected_proposal_id
        != "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
        or charter.authorizes_market_data_import
        or charter.authorizes_parameter_definition
        or charter.authorizes_return_testing
        or charter.authorizes_candidate
        or charter.authorizes_testnet_strategy_orders
        or charter.authorizes_production
        or charter.authorizes_live
    ):
        raise ValueError("Jam successor charter authorization boundary changed")
    return charter


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter: JamSuccessorHypothesisCharter,
) -> JamArchiveMetadataCensusContract:
    return build_jam_archive_census_contract(
        frozen_at=frozen_at,
        successor_charter_evidence_hash=charter.charter_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "This contract permits GET requests for checksum text only; archive "
                "HEAD requests, archive ZIP requests, and redirects are forbidden."
            ),
            (
                "The exact request matrix is BTCUSDT spot monthly aggregate trades "
                "and one-minute klines for January 2019 through December 2022: "
                "ninety-six unique checksum URLs."
            ),
            (
                "Each checksum response is capped at 4,096 bytes and the total "
                "checksum-text response budget is 393,216 bytes."
            ),
            (
                "HTTP 200 records a strictly parsed published archive checksum; "
                "HTTP 404 records observed source absence without inferring cause."
            ),
            (
                "A checksum proves publication identity at observation time only; "
                "archive bytes, CSV schema, rows, continuity, and market values "
                "remain uninspected."
            ),
            (
                "The census may inspect URL identity, HTTP status, response byte "
                "count, checksum text, and SHA-256 metadata only."
            ),
            (
                "No price, quantity, trade side, feature, parameter, signal, return, "
                "PnL, strategy execution, or order may be inspected or calculated."
            ),
            (
                "All ninety-six checksum targets must be present to pass the coverage "
                "gate; a pass still requires separate authorization before one "
                "archive payload pilot may be frozen or run."
            ),
            (
                "This contract creates no candidate, paper eligibility, Testnet "
                "strategy-order authority, production authority, live eligibility, "
                "or capital permission."
            ),
        ],
    )


def write_contract(
    path: Path,
    contract: JamArchiveMetadataCensusContract,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if (
        JamArchiveMetadataCensusContract.model_validate_json(serialized)
        != contract
    ):
        raise ValueError("Jam archive census contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> JamArchiveMetadataCensusContract:
    if args.output.exists():
        raise ValueError("Frozen Jam archive census contract exists; use --check")
    charter = load_charter(args.charter)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        charter=charter,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"targets={len(contract.targets)} "
        f"max_attempts={contract.maximum_http_attempts}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> JamArchiveMetadataCensusContract:
    charter = load_charter(args.charter)
    contract = JamArchiveMetadataCensusContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
    )
    if contract != expected:
        raise ValueError("Jam archive census contract is not reproducible")
    if not audit_jam_archive_census_contract(contract):
        raise ValueError("Jam archive census contract hash audit failed")
    print(
        "PASS "
        f"jam_archive_census_contract={contract.contract_evidence_hash} "
        f"targets={len(contract.targets)} "
        f"payloads={contract.archive_payload_requests_permitted} "
        f"returns={contract.return_calculation_permitted}",
        flush=True,
    )
    return contract


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the Jam successor metadata-only Binance archive "
            "census contract."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
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
