import argparse
import hashlib
import sys
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2MetadataSourceTarget,
    V2P01MetadataSourceContract,
    audit_v2_p01_metadata_source_contract,
)
from aurex.backtest_engine.research_v2_metadata_source_contract_v1_1 import (
    V2_METADATA_REPLACED_SOURCE_IDS,
    V2P01MetadataSourceContractV1_1,
    audit_v2_p01_metadata_source_contract_v1_1,
    build_v2_p01_metadata_source_contract_v1_1,
)
from aurex.backtest_engine.research_v2_theory_screen import (
    V2MechanismTheoryScreen,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_v1_module = import_module(
    "scripts.freeze_v2_p01_metadata_source_contract"
)

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
DEFAULT_SUPERSEDED_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1_1.json"
)
DEFAULT_SUCCESSOR_ARTIFACTS = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_audit_v1_1.json",
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
        / "scripts"
        / "freeze_v2_p01_metadata_source_contract_v1_1.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_metadata_source_contract.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_metadata_source_contract_v1_1.py",
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


def load_inputs(
    args,
) -> tuple[V2P01MetadataSourceContract, V2MechanismTheoryScreen]:
    screen = _v1_module.load_theory_screen(args)
    superseded = V2P01MetadataSourceContract.model_validate_json(
        args.superseded_contract.read_text(encoding="utf-8")
    )
    expected = _v1_module.authoritative_contract(
        frozen_at=superseded.frozen_at,
        screen=screen,
    )
    if (
        superseded != expected
        or not audit_v2_p01_metadata_source_contract(superseded)
    ):
        raise ValueError("Superseded V2 metadata source contract is not reproducible")
    return superseded, screen


def revised_source_targets(
    superseded: V2P01MetadataSourceContract,
) -> list[V2MetadataSourceTarget]:
    replacement_values = {
        "BINANCE_USD_M_MARKET_DATA_DOCS": {
            "source_kind": "OFFICIAL_BINANCE_GITHUB_DOCUMENTATION",
            "requested_url": (
                "https://raw.githubusercontent.com/binance/"
                "binance-futures-connector-python/main/binance/"
                "um_futures/market.py"
            ),
            "allowed_final_domains": ["raw.githubusercontent.com"],
        },
        "BINANCE_USD_M_ACCOUNT_DOCS": {
            "source_kind": "OFFICIAL_BINANCE_GITHUB_DOCUMENTATION",
            "requested_url": (
                "https://raw.githubusercontent.com/binance/"
                "binance-connector-python/master/clients/"
                "derivatives_trading_usds_futures/src/"
                "binance_sdk_derivatives_trading_usds_futures/"
                "rest_api/api/account_api.py"
            ),
            "allowed_final_domains": ["raw.githubusercontent.com"],
        },
    }
    targets: list[V2MetadataSourceTarget] = []
    for target in superseded.source_targets:
        payload = target.model_dump()
        payload.update(replacement_values.get(target.source_id, {}))
        targets.append(V2MetadataSourceTarget.model_validate(payload))
    return targets


def authoritative_contract(
    *,
    frozen_at: datetime,
    superseded: V2P01MetadataSourceContract,
    screen: V2MechanismTheoryScreen,
) -> V2P01MetadataSourceContractV1_1:
    return build_v2_p01_metadata_source_contract_v1_1(
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
        requirement_ids=superseded.requirement_ids,
        source_targets=revised_source_targets(superseded),
        classification_policy=superseded.classification_policy,
        allowed_next_decisions=superseded.allowed_next_decisions,
        limitations=superseded.limitations,
        supersedes_contract_evidence_hash=(
            superseded.contract_evidence_hash
        ),
        replaced_source_ids=V2_METADATA_REPLACED_SOURCE_IDS,
        supersession_notes=[
            (
                "The deterministic v1 runner received HTTP 202 with an empty body "
                "from the Binance USD-M market documentation catalog URL."
            ),
            (
                "The empty response contained none of the frozen markers, so the "
                "v1 runner failed before writing an audit result."
            ),
            (
                "Only the two Binance catalog URLs are replaced by official Binance "
                "GitHub source files with the same endpoint and temporal markers."
            ),
            (
                "The eight requirements, classification policy, permissions, "
                "limitations, and no-return boundary are unchanged from v1."
            ),
        ],
    )


def write_contract(
    path: Path,
    contract: V2P01MetadataSourceContractV1_1,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if (
        V2P01MetadataSourceContractV1_1.model_validate_json(serialized)
        != contract
    ):
        raise ValueError("V2 metadata source contract v1.1 did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2P01MetadataSourceContractV1_1:
    if args.output.exists():
        raise ValueError("Frozen V2 metadata contract v1.1 exists; use --check")
    preexisting = [
        path.as_posix() for path in args.successor_artifact if path.exists()
    ]
    if preexisting:
        raise ValueError(
            f"Successor artifact predates metadata contract v1.1: {preexisting}"
        )
    superseded, screen = load_inputs(args)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        superseded=superseded,
        screen=screen,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"replaced={len(contract.replaced_source_ids)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2P01MetadataSourceContractV1_1:
    superseded, screen = load_inputs(args)
    stored = V2P01MetadataSourceContractV1_1.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        superseded=superseded,
        screen=screen,
    )
    audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=stored,
        superseded_contract=superseded,
    )
    if stored != expected or audit["status"] != "PASS":
        raise ValueError(
            f"Stored V2 metadata contract v1.1 differs: {audit['reasons']}"
        )
    print(
        "PASS "
        f"v2_metadata_contract_v1_1={stored.contract_evidence_hash} "
        f"supersedes={stored.supersedes_contract_evidence_hash}",
        flush=True,
    )
    return stored


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the source-only P01 metadata contract v1.1."
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
    parser.add_argument(
        "--superseded-contract",
        type=Path,
        default=DEFAULT_SUPERSEDED_CONTRACT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--successor-artifact",
        type=Path,
        action="append",
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
