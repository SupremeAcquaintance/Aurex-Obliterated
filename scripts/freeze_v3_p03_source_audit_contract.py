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
    V3P02AggTradesCensusResult,
    audit_v3_p02_census_result,
)
from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3P03SourceAuditContract,
    audit_v3_p03_source_audit_contract,
    build_v3_p03_source_audit_contract,
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
DEFAULT_V3P02_RESULT = Path(
    "data/evidence/v3_p02_aggtrades_census_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p03_source_audit_contract_v1.json"
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
            / "freeze_v3_p03_source_audit_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
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


def v3p02_runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p02_aggtrades_census.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def load_inputs(
    *,
    charter_path: Path,
    register_path: Path,
    v3p02_result_path: Path,
) -> tuple[
    V3MechanismDiscoveryCharter,
    V3MechanismProposalRegister,
    V3P02AggTradesCensusResult,
]:
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
            == "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION"
        ),
        None,
    )
    if proposal is None:
        raise ValueError("Frozen V3P03 proposal is absent")
    if (
        proposal.coverage_contract.minimum_qualified_symbols != 1
        or proposal.coverage_contract.maximum_single_gap_minutes != 0
        or proposal.preliminary_execution_fit
        != "BLOCKED_PENDING_L2_QUEUE_FILL_AND_LATENCY_HISTORY"
        or proposal.parameter_sets_defined
        or proposal.market_numeric_fields_inspected
        or proposal.strategy_outcome_fields_inspected
        or proposal.return_metrics_calculated
    ):
        raise ValueError("Frozen V3P03 no-outcome feasibility boundary changed")

    v3p02_result = V3P02AggTradesCensusResult.model_validate_json(
        v3p02_result_path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_census_result(v3p02_result)
        or v3p02_result.runner_contract_hash
        != v3p02_runner_contract_hash()
        or v3p02_result.summary.complete_symbol_count != 31
        or v3p02_result.return_metrics_calculated
    ):
        raise ValueError("V3P02 aggregate-trade source evidence audit failed")
    return charter, register, v3p02_result


def authoritative_contract(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
    v3p02_result: V3P02AggTradesCensusResult,
) -> V3P03SourceAuditContract:
    return build_v3_p03_source_audit_contract(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        v3p02_census_result_evidence_hash=v3p02_result.result_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "The formal audit captures five exact public source targets and "
                "permits no target substitution after observation."
            ),
            (
                "Only official documentation, API schema, checksum text, ZIP "
                "identity, CSV header, member names, and row count may be inspected."
            ),
            (
                "The single bookDepth archive is a schema probe, not a coverage "
                "sample and not evidence of sequence-complete L2 availability."
            ),
            (
                "No credentialed endpoint, user account, price, quantity, depth, "
                "notional, signal, trade outcome, PnL, or return may be inspected."
            ),
            (
                "All eight historical microstructure requirements must independently "
                "qualify; one absence or insufficiency rejects V3P03 before selection."
            ),
            (
                "Current or live-only documentation cannot substitute for immutable "
                "2023-2024 source bytes, dated rules, or measured latency."
            ),
            (
                "A hypothetical passive order cannot inherit historical account "
                "events from orders that were never submitted."
            ),
            (
                "Even a passing source audit would permit only feasibility "
                "consideration and would create no candidate or trading eligibility."
            ),
        ],
    )


def write_contract(path: Path, contract: V3P03SourceAuditContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if V3P03SourceAuditContract.model_validate_json(serialized) != contract:
        raise ValueError("V3P03 source audit contract JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3P03SourceAuditContract:
    if args.output.exists():
        raise ValueError("Frozen V3P03 source audit contract exists; use --check")
    charter, register, v3p02_result = load_inputs(
        charter_path=args.charter,
        register_path=args.register,
        v3p02_result_path=args.v3p02_result,
    )
    contract = authoritative_contract(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
        v3p02_result=v3p02_result,
    )
    write_contract(args.output, contract)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"requirements={len(contract.requirement_ids)} "
        f"targets={len(contract.source_targets)}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3P03SourceAuditContract:
    charter, register, v3p02_result = load_inputs(
        charter_path=args.charter,
        register_path=args.register,
        v3p02_result_path=args.v3p02_result,
    )
    contract = V3P03SourceAuditContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
        register=register,
        v3p02_result=v3p02_result,
    )
    if contract != expected:
        raise ValueError("V3P03 source audit contract is not reproducible")
    if not audit_v3_p03_source_audit_contract(contract):
        raise ValueError("V3P03 source audit contract hash audit failed")
    print(
        "PASS "
        f"v3p03_source_contract={contract.contract_evidence_hash} "
        f"requirements={len(contract.requirement_ids)} "
        f"targets={len(contract.source_targets)} "
        f"market_values={contract.market_numeric_value_inspection_permitted} "
        f"selection={contract.selection_permitted}",
        flush=True,
    )
    return contract


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the no-return V3P03 historical microstructure "
            "source audit contract."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--v3p02-result",
        type=Path,
        default=DEFAULT_V3P02_RESULT,
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
