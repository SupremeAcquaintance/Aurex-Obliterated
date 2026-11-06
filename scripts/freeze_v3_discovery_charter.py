import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v2_discovery_charter import (
    V2MechanismDiscoveryCharter,
    audit_v2_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v2_p01_acquisition_result import (
    V2_P01_ACQUISITION_FAIL_DECISION,
    V2P01FullAcquisitionResult,
    audit_v2_p01_full_acquisition_result,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
    audit_v2_p01_primary_protocol,
)
from aurex.backtest_engine.research_v2_theory_screen import (
    V2MechanismTheoryScreen,
    audit_v2_mechanism_theory_screen,
)
from aurex.backtest_engine.research_v3_discovery_charter import (
    V3_ALLOWED_NEXT_DECISIONS,
    V3_DISCOVERY_STAGES,
    V3_FORBIDDEN_DERIVATIONS,
    V3_KNOWN_BLOCKED_OR_RETIRED_LINEAGES,
    V3_PAYLOAD_FEASIBILITY_POLICY,
    V3_REQUIRED_SUCCESSOR_BINDINGS,
    V3_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE,
    V3_STOP_CONDITIONS,
    V3_THEORY_SOURCE_POLICY,
    V3_TIMESTAMP_COVERAGE_FIELDS,
    V3DiscoveryPartitionBoundary,
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
    build_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_V2_CHARTER = Path(
    "data/evidence/v2_mechanism_discovery_charter_v1.json"
)
DEFAULT_V2_SCREEN = Path(
    "data/evidence/v2_mechanism_theory_screen_v1.json"
)
DEFAULT_P01_PROTOCOL = Path(
    "data/evidence/v2_p01_primary_protocol_v1.json"
)
DEFAULT_P01_RESULT = Path(
    "data/evidence/v2_p01_full_acquisition_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_mechanism_discovery_charter_v1.json"
)


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v3_discovery_charter.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v3_discovery_charter.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def p01_runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_p01_full_acquisition.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_p01_acquisition_result.py",
    ]
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(project_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def load_inputs(args):
    v2_charter = V2MechanismDiscoveryCharter.model_validate_json(
        args.v2_charter.read_text(encoding="utf-8")
    )
    if not audit_v2_mechanism_discovery_charter(v2_charter):
        raise ValueError("V2 discovery charter audit failed")
    v2_screen = V2MechanismTheoryScreen.model_validate_json(
        args.v2_screen.read_text(encoding="utf-8")
    )
    if not audit_v2_mechanism_theory_screen(v2_screen):
        raise ValueError("V2 theory screen audit failed")
    if (
        v2_screen.discovery_charter_evidence_hash
        != v2_charter.charter_evidence_hash
    ):
        raise ValueError("V2 screen is not bound to the V2 charter")
    protocol = V2P01PrimaryProtocol.model_validate_json(
        args.p01_protocol.read_text(encoding="utf-8")
    )
    if not audit_v2_p01_primary_protocol(protocol):
        raise ValueError("P01 protocol audit failed")
    if (
        protocol.theory_screen_evidence_hash
        != v2_screen.screen_evidence_hash
    ):
        raise ValueError("P01 protocol is not bound to the V2 screen")
    result = V2P01FullAcquisitionResult.model_validate_json(
        args.p01_result.read_text(encoding="utf-8")
    )
    result_audit = audit_v2_p01_full_acquisition_result(
        result=result,
        protocol=protocol,
        current_runner_contract_hash=p01_runner_contract_hash(),
        evidence_root=args.p01_result.parent,
        inspect_local_files=False,
    )
    if result_audit["status"] != "PASS":
        raise ValueError(
            f"P01 acquisition result audit failed: {result_audit['reasons']}"
        )
    if (
        result.decision != V2_P01_ACQUISITION_FAIL_DECISION
        or result.summary.qualified_symbol_count != 0
        or result.return_metrics_calculated
        or result.authorizes_development_return_under_frozen_protocol
    ):
        raise ValueError("P01 did not stop cleanly before return calculation")
    return v2_charter, v2_screen, protocol, result


def boundaries() -> list[V3DiscoveryPartitionBoundary]:
    return [
        V3DiscoveryPartitionBoundary(
            partition="DEVELOPMENT",
            start=datetime(2023, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 1, tzinfo=UTC),
            role="SOURCE_FEASIBILITY_ONLY_NO_STRATEGY_OUTCOMES",
            access="TIMESTAMP_SCHEMA_COVERAGE_ONLY",
        ),
        V3DiscoveryPartitionBoundary(
            partition="VALIDATION",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
            role="FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
            access="SEALED_FOR_INDEPENDENT_MECHANISM",
        ),
        V3DiscoveryPartitionBoundary(
            partition="HOLDOUT",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 7, 1, tzinfo=UTC),
            role="FINAL_ELIGIBILITY_HOLDOUT",
            access="SEALED_AND_NOT_IMPORTED",
        ),
        V3DiscoveryPartitionBoundary(
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
) -> V3MechanismDiscoveryCharter:
    v2_charter, v2_screen, protocol, result = inputs
    return build_v3_mechanism_discovery_charter(
        registered_at=registered_at,
        v2_discovery_charter_evidence_hash=(
            v2_charter.charter_evidence_hash
        ),
        v2_theory_screen_evidence_hash=v2_screen.screen_evidence_hash,
        p01_protocol_evidence_hash=protocol.protocol_evidence_hash,
        p01_acquisition_result_evidence_hash=result.result_evidence_hash,
        contamination_ledger_evidence_hash=(
            v2_charter.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        p01_final_decision=result.decision,
        partition_boundaries=boundaries(),
        required_theory_and_feasibility_evidence=(
            V3_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE
        ),
        theory_source_policy=V3_THEORY_SOURCE_POLICY,
        payload_feasibility_policy=V3_PAYLOAD_FEASIBILITY_POLICY,
        forbidden_derivations=V3_FORBIDDEN_DERIVATIONS,
        known_blocked_or_retired_lineages=(
            V3_KNOWN_BLOCKED_OR_RETIRED_LINEAGES
        ),
        required_successor_bindings=V3_REQUIRED_SUCCESSOR_BINDINGS,
        discovery_stages=V3_DISCOVERY_STAGES,
        stop_conditions=V3_STOP_CONDITIONS,
        allowed_next_decisions=V3_ALLOWED_NEXT_DECISIONS,
        permitted_timestamp_coverage_fields=V3_TIMESTAMP_COVERAGE_FIELDS,
        limitations=[
            (
                "P01 is final negative pre-return evidence and cannot be rescued "
                "by changing continuity, symbols, thresholds, or related premise."
            ),
            (
                "The acquired P01 payload may support only source identity, schema, "
                "timestamp, row-count, and synchronized-coverage feasibility."
            ),
            (
                "The V3 proposal screen may inspect no price value, signal, trade, "
                "P/L, return, or strategy outcome."
            ),
            (
                "Any proposal requiring unavailable point-in-time execution, "
                "financing, borrow, or market-state history must stop before selection."
            ),
            (
                "Selecting a primary permits only separate source and protocol "
                "design and does not create a candidate or open development outcomes."
            ),
            (
                "2025 validation, 2026 H1 holdout, forward evidence, Pine, paper, "
                "sandbox, live trading, and capital remain closed."
            ),
            (
                "V3 searches honestly for a durable edge but cannot promise that "
                "one exists in the available evidence or future market."
            ),
        ],
    )


def write_charter(path: Path, charter: V3MechanismDiscoveryCharter) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = charter.model_dump_json(indent=2) + "\n"
    if V3MechanismDiscoveryCharter.model_validate_json(serialized) != charter:
        raise ValueError("V3 discovery charter JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3MechanismDiscoveryCharter:
    if args.output.exists():
        raise ValueError("Frozen V3 discovery charter exists; use --check")
    inputs = load_inputs(args)
    charter = authoritative_charter(
        registered_at=datetime.now(UTC),
        inputs=inputs,
    )
    write_charter(args.output, charter)
    print(
        f"WROTE {args.output} {charter.charter_evidence_hash} "
        f"proposal_budget={charter.maximum_theory_proposals}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3MechanismDiscoveryCharter:
    inputs = load_inputs(args)
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_charter(
        registered_at=charter.registered_at,
        inputs=inputs,
    )
    if charter != expected:
        raise ValueError("V3 discovery charter is not reproducible")
    if not audit_v3_mechanism_discovery_charter(charter):
        raise ValueError("V3 discovery charter hash audit failed")
    print(
        "PASS "
        f"v3_discovery_charter={charter.charter_evidence_hash} "
        f"proposals={charter.maximum_theory_proposals} "
        f"return_tests={charter.maximum_return_tested_mechanisms_under_charter}",
        flush=True,
    )
    return charter


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the V3 no-return independent discovery charter."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--v2-charter", type=Path, default=DEFAULT_V2_CHARTER)
    parser.add_argument("--v2-screen", type=Path, default=DEFAULT_V2_SCREEN)
    parser.add_argument("--p01-protocol", type=Path, default=DEFAULT_P01_PROTOCOL)
    parser.add_argument("--p01-result", type=Path, default=DEFAULT_P01_RESULT)
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
