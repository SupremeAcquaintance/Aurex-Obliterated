import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3P02AggTradesCensusContract,
    audit_v3_p02_census_contract,
    build_v3_p02_census_contract,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
    audit_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHARTER = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v3_mechanism_proposal_register_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p02_aggtrades_census_contract_v1.json"
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
            / "freeze_v3_p02_aggtrades_census_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def charter_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_discovery_charter.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_discovery_charter.py",
        ]
    )


def register_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_proposal_register.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_proposal_register.py",
        ]
    )


def load_inputs(
    charter_path: Path,
    register_path: Path,
) -> tuple[V3MechanismDiscoveryCharter, V3MechanismProposalRegister]:
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        charter_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_contract_hash()
    ):
        raise ValueError("V3 discovery charter audit failed")

    register = V3MechanismProposalRegister.model_validate_json(
        register_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_contract_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V3 proposal register audit failed")

    proposal = next(
        (
            item
            for item in register.proposals
            if item.proposal_id
            == "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"
        ),
        None,
    )
    if proposal is None:
        raise ValueError("Frozen V3P02 proposal is absent")
    if (
        proposal.coverage_contract.minimum_qualified_symbols != 10
        or proposal.parameter_sets_defined
        or proposal.market_numeric_fields_inspected
        or proposal.strategy_outcome_fields_inspected
        or proposal.return_metrics_calculated
    ):
        raise ValueError("Frozen V3P02 no-outcome feasibility boundary changed")
    return charter, register


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
) -> V3P02AggTradesCensusContract:
    return build_v3_p02_census_contract(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "This contract permits checksum-text requests only; no aggregate-trade "
                "archive payload may be requested or inspected."
            ),
            (
                "A published checksum proves only that the named official archive was "
                "available at observation time, not that its payload is complete or "
                "economically usable."
            ),
            (
                "HTTP 404 records observed source absence without inferring why the "
                "archive is absent."
            ),
            (
                "The census may inspect URL identity, HTTP status, checksum response "
                "size, and checksum digest only; price, quantity, side, signal, trade, "
                "PnL, and return fields remain forbidden."
            ),
            (
                "At least ten symbols must expose all twenty-four monthly archives to "
                "permit a separately frozen payload pilot protocol."
            ),
            (
                "A passing census selects no primary, creates no strategy candidate, "
                "and grants no validation, holdout, forward, Pine, paper, sandbox, "
                "live, or capital permission."
            ),
            (
                "The request budget covers 744 unique checksum URLs and at most 2,232 "
                "HTTP attempts under the frozen retry policy."
            ),
        ],
    )


def write_contract(path: Path, contract: V3P02AggTradesCensusContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if V3P02AggTradesCensusContract.model_validate_json(serialized) != contract:
        raise ValueError("V3P02 census contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3P02AggTradesCensusContract:
    if args.output.exists():
        raise ValueError("Frozen V3P02 census contract exists; use --check")
    charter, register = load_inputs(args.charter, args.register)
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"targets={len(contract.targets)} max_attempts="
        f"{contract.maximum_http_attempts}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3P02AggTradesCensusContract:
    charter, register = load_inputs(args.charter, args.register)
    contract = V3P02AggTradesCensusContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
        register=register,
    )
    if contract != expected:
        raise ValueError("V3P02 census contract is not reproducible")
    if not audit_v3_p02_census_contract(contract):
        raise ValueError("V3P02 census contract hash audit failed")
    print(
        "PASS "
        f"v3p02_census_contract={contract.contract_evidence_hash} "
        f"targets={len(contract.targets)} "
        f"payloads={contract.archive_payload_requests_permitted} "
        f"returns={contract.strategy_outcomes_permitted}",
        flush=True,
    )
    return contract


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the metadata-only V3P02 aggregate-trade census "
            "contract."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
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
