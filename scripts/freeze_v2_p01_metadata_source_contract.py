import argparse
import hashlib
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2_METADATA_ALLOWED_NEXT_DECISIONS,
    V2_METADATA_CLASSIFICATION_POLICY,
    V2_METADATA_REQUIREMENT_IDS,
    V2MetadataSourceTarget,
    V2P01MetadataSourceContract,
    audit_v2_p01_metadata_source_contract,
    build_v2_p01_metadata_source_contract,
)
from aurex.backtest_engine.research_v2_theory_screen import (
    V2MechanismTheoryScreen,
    audit_v2_mechanism_theory_screen,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_theory_module = import_module("scripts.freeze_v2_theory_screen")

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_FOUNDATION_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_result_v1.json"
)
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_discovery_charter_v1.json"
DEFAULT_THEORY_SCREEN = (
    DEFAULT_EVIDENCE_ROOT / "v2_mechanism_theory_screen_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_SUCCESSOR_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_audit_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_p01_primary_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_full_acquisition_protocol_v1.json",
    DEFAULT_EVIDENCE_ROOT / "v2_primary_development_result_v1.json",
)


def builder_contract_hash() -> str:
    paths = [
        PROJECT_ROOT
        / "scripts"
        / "freeze_v2_p01_metadata_source_contract.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_metadata_source_contract.py",
    ]
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


def load_theory_screen(args) -> V2MechanismTheoryScreen:
    charter = _theory_module.load_charter(args)
    screen = V2MechanismTheoryScreen.model_validate_json(
        args.theory_screen.read_text(encoding="utf-8")
    )
    expected = _theory_module.authoritative_screen(
        frozen_at=screen.frozen_at,
        charter=charter,
    )
    if screen != expected or not audit_v2_mechanism_theory_screen(screen):
        raise ValueError("V2 theory screen is not reproducible")
    if screen.selected_proposal_id != (
        "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    ):
        raise ValueError("V2 metadata contract requires selected P01")
    if screen.authorizes_full_acquisition or screen.authorizes_return_testing:
        raise ValueError("V2 theory screen boundary changed")
    return screen


def source_targets() -> list[V2MetadataSourceTarget]:
    historical_market_requirements = [
        "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
        "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES",
    ]
    return [
        V2MetadataSourceTarget(
            source_id="BINANCE_PUBLIC_DATA_README",
            source_kind="OFFICIAL_BINANCE_GITHUB_DOCUMENTATION",
            requested_url=(
                "https://raw.githubusercontent.com/binance/"
                "binance-public-data/master/README.md"
            ),
            allowed_final_domains=["raw.githubusercontent.com"],
            declared_temporal_scope="HISTORICAL_ARCHIVE_DOCUMENTATION",
            required_markers=[
                "Archived files may be updated",
                "Binance Public Data",
                "CHECKSUM",
                "USD-M Futures",
            ],
            supports_requirement_ids=historical_market_requirements,
            maximum_response_bytes=2 * 1024 * 1024,
        ),
        V2MetadataSourceTarget(
            source_id="BINANCE_USD_M_MARKET_DATA_DOCS",
            source_kind="OFFICIAL_BINANCE_DOCUMENTATION",
            requested_url=(
                "https://developers.binance.com/docs/derivatives/"
                "usds-margined-futures/market-data/rest-api/"
                "Exchange-Information"
            ),
            allowed_final_domains=["developers.binance.com"],
            declared_temporal_scope=(
                "CURRENT_MARKET_AND_CONTRACT_API_DOCUMENTATION"
            ),
            required_markers=[
                "/fapi/v1/exchangeInfo",
                "/fapi/v1/fundingInfo",
                "/fapi/v1/fundingRate",
                "Current exchange trading rules and symbol information",
            ],
            supports_requirement_ids=[
                "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES",
                "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE",
                "HISTORICAL_FUTURES_ORDER_FILTERS",
                *historical_market_requirements,
            ],
            maximum_response_bytes=8 * 1024 * 1024,
        ),
        V2MetadataSourceTarget(
            source_id="BINANCE_USD_M_ACCOUNT_DOCS",
            source_kind="OFFICIAL_BINANCE_DOCUMENTATION",
            requested_url=(
                "https://developers.binance.com/docs/derivatives/"
                "usds-margined-futures/account/rest-api/"
                "Notional-and-Leverage-Brackets"
            ),
            allowed_final_domains=["developers.binance.com"],
            declared_temporal_scope="CURRENT_SIGNED_ACCOUNT_API_DOCUMENTATION",
            required_markers=[
                "/fapi/v1/commissionRate",
                "/fapi/v1/leverageBracket",
                "Notional and Leverage Brackets",
                "User Commission Rate",
            ],
            supports_requirement_ids=[
                "HISTORICAL_ACCOUNT_FEE_TIER",
                "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES",
                "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS",
            ],
            maximum_response_bytes=6 * 1024 * 1024,
        ),
        V2MetadataSourceTarget(
            source_id="BINANCE_SPOT_API_DOCS",
            source_kind="OFFICIAL_BINANCE_GITHUB_DOCUMENTATION",
            requested_url=(
                "https://raw.githubusercontent.com/binance/"
                "binance-spot-api-docs/master/rest-api.md"
            ),
            allowed_final_domains=["raw.githubusercontent.com"],
            declared_temporal_scope="CURRENT_SPOT_API_DOCUMENTATION",
            required_markers=[
                "/api/v3/exchangeInfo",
                "Current exchange trading rules and symbol information",
                "Exchange information",
            ],
            supports_requirement_ids=["HISTORICAL_SPOT_ORDER_FILTERS"],
            maximum_response_bytes=6 * 1024 * 1024,
        ),
    ]


def authoritative_contract(
    *,
    frozen_at: datetime,
    screen: V2MechanismTheoryScreen,
) -> V2P01MetadataSourceContract:
    return build_v2_p01_metadata_source_contract(
        frozen_at=frozen_at,
        theory_screen_evidence_hash=screen.screen_evidence_hash,
        discovery_charter_evidence_hash=(
            screen.discovery_charter_evidence_hash
        ),
        capability_audit_evidence_hash=(
            screen.capability_audit_evidence_hash
        ),
        source_census_result_evidence_hash=(
            screen.source_census_result_evidence_hash
        ),
        pilot_result_evidence_hash=screen.pilot_result_evidence_hash,
        derivatives_foundation_result_evidence_hash=(
            screen.derivatives_foundation_result_evidence_hash
        ),
        contamination_ledger_evidence_hash=(
            screen.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        requirement_ids=V2_METADATA_REQUIREMENT_IDS,
        source_targets=source_targets(),
        classification_policy=V2_METADATA_CLASSIFICATION_POLICY,
        allowed_next_decisions=V2_METADATA_ALLOWED_NEXT_DECISIONS,
        limitations=[
            (
                "Document reachability establishes only the declared source surface "
                "and does not establish complete historical metadata."
            ),
            (
                "Current exchangeInfo cannot be projected backward to 2023-2024 "
                "quantity, price, notional, status, or liquidation rules."
            ),
            (
                "Current signed account endpoints cannot reconstruct historical "
                "commission tiers or maintenance-margin brackets."
            ),
            (
                "The existing archive census proves market-family availability but "
                "not historical contract or account rules."
            ),
            (
                "A later protocol may use conservative research overrides only when "
                "the assumption and its non-eligibility limitation are explicit."
            ),
            (
                "No result from this contract authorizes archive expansion, return "
                "testing, candidate creation, paper, sandbox, live, or capital."
            ),
        ],
    )


def write_contract(path: Path, contract: V2P01MetadataSourceContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if V2P01MetadataSourceContract.model_validate_json(serialized) != contract:
        raise ValueError("V2 metadata source contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2P01MetadataSourceContract:
    if args.output.exists():
        raise ValueError("Frozen V2 metadata source contract exists; use --check")
    preexisting = [
        path.as_posix() for path in args.successor_artifact if path.exists()
    ]
    if preexisting:
        raise ValueError(
            f"Successor artifact predates metadata contract: {preexisting}"
        )
    screen = load_theory_screen(args)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        screen=screen,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"sources={len(contract.source_targets)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2P01MetadataSourceContract:
    screen = load_theory_screen(args)
    stored = V2P01MetadataSourceContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        screen=screen,
    )
    if stored != expected or not audit_v2_p01_metadata_source_contract(stored):
        raise ValueError("Stored V2 metadata source contract differs from rebuild")
    print(
        "PASS "
        f"v2_metadata_contract={stored.contract_evidence_hash} "
        f"sources={len(stored.source_targets)} "
        f"credentials={stored.credentials_permitted}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the P01 no-return metadata-source contract."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--foundation-protocol",
        type=Path,
        default=DEFAULT_FOUNDATION_PROTOCOL,
    )
    parser.add_argument(
        "--foundation-result",
        type=Path,
        default=DEFAULT_FOUNDATION_RESULT,
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--theory-screen",
        type=Path,
        default=DEFAULT_THEORY_SCREEN,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--successor-artifact",
        type=Path,
        nargs="*",
        default=list(DEFAULT_SUCCESSOR_ARTIFACTS),
    )
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
