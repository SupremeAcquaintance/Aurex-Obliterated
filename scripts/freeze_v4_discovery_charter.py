import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.contamination import (
    StrategyContaminationLedger,
    audit_contamination_ledger,
)
from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_feasibility_screen import (
    V3_FEASIBILITY_DECISION,
    V3MechanismFeasibilityScreen,
    audit_v3_mechanism_feasibility_screen,
)
from aurex.backtest_engine.research_v3_p01_execution_feasibility import (
    V3P01ExecutionFeasibilityResult,
    audit_v3_p01_execution_feasibility_result,
)
from aurex.backtest_engine.research_v3_p02_stop_result import (
    V3P02PayloadPilotStopResult,
    audit_v3_p02_payload_pilot_stop_result,
)
from aurex.backtest_engine.research_v3_p03_stop_result import (
    V3P03SourceAuditStopResult,
    audit_v3_p03_source_audit_stop_result,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
    audit_v3_mechanism_proposal_register,
)
from aurex.backtest_engine.research_v4_discovery_charter import (
    V4_ALLOWED_NEXT_DECISIONS,
    V4_DISCOVERY_STAGES,
    V4_EXECUTION_FEASIBILITY_POLICY,
    V4_FORBIDDEN_DERIVATIONS,
    V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES,
    V4_PERMITTED_FEASIBILITY_FIELDS,
    V4_REQUIRED_SUCCESSOR_BINDINGS,
    V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE,
    V4_SOURCE_DATA_POLICY,
    V4_SOURCE_TRANSPORT_POLICY,
    V4_STOP_CONDITIONS,
    V4_THEORY_SOURCE_POLICY,
    V4DiscoveryPartitionBoundary,
    V4MechanismDiscoveryCharter,
    audit_v4_mechanism_discovery_charter,
    build_v4_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_V3_CHARTER = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)
DEFAULT_V3_REGISTER = Path(
    "data/evidence/v3_mechanism_proposal_register_v1.json"
)
DEFAULT_V3_SCREEN = Path(
    "data/evidence/v3_mechanism_feasibility_screen_v1.json"
)
DEFAULT_V3P01_RESULT = Path(
    "data/evidence/v3_p01_execution_feasibility_result_v1.json"
)
DEFAULT_V3P02_STOP = Path(
    "data/evidence/v3_p02_payload_pilot_stop_result_v1.json"
)
DEFAULT_V3P03_STOP = Path(
    "data/evidence/v3_p03_source_audit_stop_result_v1.json"
)
DEFAULT_CONTAMINATION_LEDGER = Path(
    "data/evidence/strategy_contamination_ledger_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
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
            PROJECT_ROOT / "scripts" / "freeze_v4_discovery_charter.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_discovery_charter.py",
        ]
    )


def v3_charter_builder_hash() -> str:
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


def v3_register_builder_hash() -> str:
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


def v3_screen_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_v3_feasibility_screen.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_feasibility_screen.py",
        ]
    )


def v3p01_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "run_v3_p01_execution_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p01_execution_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "derivatives_foundation.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v2_derivatives_foundation_protocol.py",
        ]
    )


def v3p02_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p02_payload_pilot.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_payload_pilot.py",
        ]
    )


def v3p02_finalizer_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "finalize_v3_p02_payload_pilot_stop.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_stop_result.py",
        ]
    )


def v3p03_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p03_source_audit.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def v3p03_finalizer_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "finalize_v3_p03_source_audit_stop.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_stop_result.py",
        ]
    )


def load_inputs(args):
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        args.v3_charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != v3_charter_builder_hash()
    ):
        raise ValueError("V3 discovery charter audit failed")

    register = V3MechanismProposalRegister.model_validate_json(
        args.v3_register.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_proposal_register(register)
        or register.builder_contract_hash != v3_register_builder_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V3 proposal register audit failed")

    screen = V3MechanismFeasibilityScreen.model_validate_json(
        args.v3_screen.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_feasibility_screen(screen)
        or screen.builder_contract_hash != v3_screen_builder_hash()
        or screen.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
        or screen.proposal_register_evidence_hash
        != register.register_evidence_hash
        or screen.decision != V3_FEASIBILITY_DECISION
        or screen.selected_primary_count != 0
        or not screen.v3_closed
        or screen.return_metrics_calculated
    ):
        raise ValueError("V3 terminal screen audit failed")

    p01 = V3P01ExecutionFeasibilityResult.model_validate_json(
        args.v3p01_result.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_execution_feasibility_result(p01)
        or p01.runner_contract_hash != v3p01_runner_hash()
        or p01.result_evidence_hash
        != screen.v3p01_terminal_evidence_hash
        or p01.selects_primary
        or p01.return_metrics_calculated
    ):
        raise ValueError("V3P01 terminal evidence audit failed")

    p02 = V3P02PayloadPilotStopResult.model_validate_json(
        args.v3p02_stop.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_payload_pilot_stop_result(p02)
        or p02.failed_runner_contract_hash != v3p02_runner_hash()
        or p02.finalizer_contract_hash != v3p02_finalizer_hash()
        or p02.result_evidence_hash
        != screen.v3p02_terminal_evidence_hash
        or p02.authorizes_retry
        or p02.selects_primary
        or p02.return_metrics_calculated
    ):
        raise ValueError("V3P02 terminal evidence audit failed")

    p03 = V3P03SourceAuditStopResult.model_validate_json(
        args.v3p03_stop.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_source_audit_stop_result(p03)
        or p03.source_runner_contract_hash != v3p03_runner_hash()
        or p03.finalizer_contract_hash != v3p03_finalizer_hash()
        or p03.result_evidence_hash
        != screen.v3p03_terminal_evidence_hash
        or p03.selects_primary
        or p03.return_metrics_calculated
    ):
        raise ValueError("V3P03 terminal evidence audit failed")

    contamination = StrategyContaminationLedger.model_validate_json(
        args.contamination_ledger.read_text(encoding="utf-8")
    )
    if (
        not audit_contamination_ledger(contamination)
        or contamination.ledger_evidence_hash
        != charter.contamination_ledger_evidence_hash
    ):
        raise ValueError("Contamination ledger audit failed")
    return charter, register, screen, p01, p02, p03, contamination


def boundaries() -> list[V4DiscoveryPartitionBoundary]:
    return [
        V4DiscoveryPartitionBoundary(
            partition="DEVELOPMENT",
            start=datetime(2023, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 1, tzinfo=UTC),
            role="SOURCE_FEASIBILITY_ONLY_NO_MARKET_VALUES_OR_OUTCOMES",
            access="SOURCE_METADATA_TIMESTAMP_SCHEMA_ONLY",
        ),
        V4DiscoveryPartitionBoundary(
            partition="VALIDATION",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
            role="FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
            access="SEALED_FOR_INDEPENDENT_MECHANISM",
        ),
        V4DiscoveryPartitionBoundary(
            partition="HOLDOUT",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 7, 1, tzinfo=UTC),
            role="FINAL_ELIGIBILITY_HOLDOUT",
            access="SEALED_AND_NOT_IMPORTED",
        ),
        V4DiscoveryPartitionBoundary(
            partition="FORWARD",
            start=datetime(2026, 7, 1, tzinfo=UTC),
            end=None,
            role="LOCKED_FORWARD_EVIDENCE",
            access="LOCKED",
        ),
    ]


def authoritative_charter(
    *,
    registered_at: datetime,
    inputs,
) -> V4MechanismDiscoveryCharter:
    charter, register, screen, p01, p02, p03, contamination = inputs
    return build_v4_mechanism_discovery_charter(
        registered_at=registered_at,
        v3_discovery_charter_evidence_hash=charter.charter_evidence_hash,
        v3_proposal_register_evidence_hash=register.register_evidence_hash,
        v3_feasibility_screen_evidence_hash=screen.screen_evidence_hash,
        v3p01_terminal_evidence_hash=p01.result_evidence_hash,
        v3p02_terminal_evidence_hash=p02.result_evidence_hash,
        v3p03_terminal_evidence_hash=p03.result_evidence_hash,
        contamination_ledger_evidence_hash=(
            contamination.ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        v3_final_decision=screen.decision,
        partition_boundaries=boundaries(),
        required_theory_and_feasibility_evidence=(
            V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE
        ),
        theory_source_policy=V4_THEORY_SOURCE_POLICY,
        source_data_policy=V4_SOURCE_DATA_POLICY,
        source_transport_policy=V4_SOURCE_TRANSPORT_POLICY,
        execution_feasibility_policy=V4_EXECUTION_FEASIBILITY_POLICY,
        forbidden_derivations=V4_FORBIDDEN_DERIVATIONS,
        known_blocked_or_retired_lineages=(
            V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES
        ),
        required_successor_bindings=V4_REQUIRED_SUCCESSOR_BINDINGS,
        discovery_stages=V4_DISCOVERY_STAGES,
        stop_conditions=V4_STOP_CONDITIONS,
        allowed_next_decisions=V4_ALLOWED_NEXT_DECISIONS,
        permitted_feasibility_fields=V4_PERMITTED_FEASIBILITY_FIELDS,
        limitations=[
            (
                "V3 is final zero-selection evidence and no V3 proposal may be "
                "retried, renamed, amended, parameterized, or return tested in V4."
            ),
            (
                "Verified prior source artifacts may support identity, checksum, "
                "schema, timestamp, row-count, and transport feasibility only."
            ),
            (
                "The V4 charter authorizes no network request; each proposal requires "
                "a separately frozen crash-safe source and transport contract."
            ),
            (
                "Every network attempt must remain cumulatively reconstructable "
                "across crashes, restarts, retries, partial files, and final stops."
            ),
            (
                "The V4 proposal screen may inspect no price value, signal, trade, "
                "P/L, return, strategy outcome, or outcome-selected source."
            ),
            (
                "Any proposal lacking point-in-time source, execution, financing, "
                "capacity, or deterministic failure evidence stops before selection."
            ),
            (
                "Selecting a primary permits only separate source acquisition and "
                "one-shot protocol design and does not create a candidate."
            ),
            (
                "2025 validation, 2026 H1 holdout, forward evidence, Pine, paper, "
                "sandbox, live trading, and capital remain closed."
            ),
            (
                "V4 searches honestly for a durable net edge but cannot promise that "
                "one exists in available evidence or future markets."
            ),
        ],
    )


def write_charter(path: Path, charter: V4MechanismDiscoveryCharter) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = charter.model_dump_json(indent=2) + "\n"
    if V4MechanismDiscoveryCharter.model_validate_json(serialized) != charter:
        raise ValueError("V4 discovery charter JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V4MechanismDiscoveryCharter:
    if args.output.exists():
        raise ValueError("Frozen V4 discovery charter exists; use --check")
    preexisting = sorted(
        path.as_posix()
        for path in args.output.parent.glob("v4_*.json")
        if path != args.output
    )
    if preexisting:
        raise ValueError(
            f"V4 successor artifact predates charter: {preexisting}"
        )
    charter = authoritative_charter(
        registered_at=datetime.now(UTC),
        inputs=load_inputs(args),
    )
    write_charter(args.output, charter)
    print(
        f"WROTE {args.output} {charter.charter_evidence_hash} "
        f"proposal_budget={charter.maximum_theory_proposals} "
        f"network={charter.charter_authorizes_network_requests}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V4MechanismDiscoveryCharter:
    inputs = load_inputs(args)
    charter = V4MechanismDiscoveryCharter.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_charter(
        registered_at=charter.registered_at,
        inputs=inputs,
    )
    if (
        charter != expected
        or not audit_v4_mechanism_discovery_charter(charter)
    ):
        raise ValueError("V4 discovery charter is not reproducible")
    print(
        "PASS "
        f"v4_discovery_charter={charter.charter_evidence_hash} "
        f"proposals={charter.maximum_theory_proposals} "
        f"return_tests={charter.maximum_return_tested_mechanisms_under_charter} "
        f"network={charter.charter_authorizes_network_requests}",
        flush=True,
    )
    return charter


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the V4 crash-safe no-return discovery charter."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--v3-charter",
        type=Path,
        default=DEFAULT_V3_CHARTER,
    )
    parser.add_argument(
        "--v3-register",
        type=Path,
        default=DEFAULT_V3_REGISTER,
    )
    parser.add_argument(
        "--v3-screen",
        type=Path,
        default=DEFAULT_V3_SCREEN,
    )
    parser.add_argument(
        "--v3p01-result",
        type=Path,
        default=DEFAULT_V3P01_RESULT,
    )
    parser.add_argument(
        "--v3p02-stop",
        type=Path,
        default=DEFAULT_V3P02_STOP,
    )
    parser.add_argument(
        "--v3p03-stop",
        type=Path,
        default=DEFAULT_V3P03_STOP,
    )
    parser.add_argument(
        "--contamination-ledger",
        type=Path,
        default=DEFAULT_CONTAMINATION_LEDGER,
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
