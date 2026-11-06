import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesFoundationProtocol,
    audit_v2_derivatives_foundation_protocol,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_result import (
    V2_FOUNDATION_PASS_DECISION,
    V2DerivativesFoundationResult,
    audit_v2_derivatives_foundation_result,
)
from aurex.backtest_engine.research_v2_discovery_charter import (
    V2_ALLOWED_NEXT_DECISIONS,
    V2_DISCOVERY_STAGES,
    V2_FORBIDDEN_DERIVATIONS,
    V2_REQUIRED_NEXT_PROTOCOL_BINDINGS,
    V2_REQUIRED_THEORY_EVIDENCE,
    V2_STOP_CONDITIONS,
    V2_THEORY_SOURCE_POLICY,
    V2DiscoveryPartitionBoundary,
    V2MechanismDiscoveryCharter,
    audit_v2_mechanism_discovery_charter,
    build_v2_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_FOUNDATION_PROTOCOL = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = Path(
    "data/evidence/v2_derivatives_foundation_result_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/v2_mechanism_discovery_charter_v1.json")


def builder_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "freeze_v2_discovery_charter.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_discovery_charter.py",
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


def foundation_runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_derivatives_foundation.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "derivatives_foundation.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_derivatives_foundation_result.py",
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


def load_inputs(
    args,
) -> tuple[V2DerivativesFoundationProtocol, V2DerivativesFoundationResult]:
    protocol = V2DerivativesFoundationProtocol.model_validate_json(
        args.foundation_protocol.read_text(encoding="utf-8")
    )
    if not audit_v2_derivatives_foundation_protocol(protocol):
        raise ValueError("V2 foundation protocol audit failed")
    result = V2DerivativesFoundationResult.model_validate_json(
        args.foundation_result.read_text(encoding="utf-8")
    )
    result_audit = audit_v2_derivatives_foundation_result(
        result=result,
        protocol=protocol,
        current_runner_contract_hash=foundation_runner_contract_hash(),
    )
    if result_audit["status"] != "PASS":
        raise ValueError(
            f"V2 foundation result audit failed: {result_audit['reasons']}"
        )
    if result.decision != V2_FOUNDATION_PASS_DECISION:
        raise ValueError("V2 foundation did not authorize discovery")
    return protocol, result


def boundaries() -> list[V2DiscoveryPartitionBoundary]:
    return [
        V2DiscoveryPartitionBoundary(
            partition="DEVELOPMENT",
            start=datetime(2023, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 1, tzinfo=UTC),
            role="FUTURE_DEVELOPMENT_FALSIFICATION",
            access="CLOSED_PENDING_FULL_ACQUISITION_PROTOCOL",
        ),
        V2DiscoveryPartitionBoundary(
            partition="VALIDATION",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 1, tzinfo=UTC),
            role="FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
            access="SEALED_FOR_UNRELATED_MECHANISM",
        ),
        V2DiscoveryPartitionBoundary(
            partition="HOLDOUT",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 7, 1, tzinfo=UTC),
            role="FINAL_ELIGIBILITY_HOLDOUT",
            access="SEALED_AND_NOT_IMPORTED",
        ),
        V2DiscoveryPartitionBoundary(
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
    protocol: V2DerivativesFoundationProtocol,
    result: V2DerivativesFoundationResult,
) -> V2MechanismDiscoveryCharter:
    return build_v2_mechanism_discovery_charter(
        registered_at=registered_at,
        capability_audit_evidence_hash=protocol.capability_audit_evidence_hash,
        source_census_result_evidence_hash=(
            protocol.source_census_result_evidence_hash
        ),
        acquisition_protocol_evidence_hash=(
            protocol.acquisition_protocol_evidence_hash
        ),
        pilot_result_evidence_hash=protocol.pilot_result_evidence_hash,
        derivatives_foundation_protocol_evidence_hash=(
            protocol.protocol_evidence_hash
        ),
        derivatives_foundation_result_evidence_hash=(
            result.result_evidence_hash
        ),
        contamination_ledger_evidence_hash=(
            protocol.contamination_ledger_evidence_hash
        ),
        builder_contract_hash=builder_contract_hash(),
        complete_source_symbols=[
            "AAVEUSDT",
            "ADAUSDT",
            "APEUSDT",
            "APTUSDT",
            "ATOMUSDT",
            "AVAXUSDT",
            "BCHUSDT",
            "BNBUSDT",
            "CRVUSDT",
            "DOGEUSDT",
            "DOTUSDT",
            "DYDXUSDT",
            "ETCUSDT",
            "FETUSDT",
            "FILUSDT",
            "FTMUSDT",
            "GALAUSDT",
            "GRTUSDT",
            "ICPUSDT",
            "INJUSDT",
            "LDOUSDT",
            "LINKUSDT",
            "LTCUSDT",
            "MKRUSDT",
            "NEARUSDT",
            "OPUSDT",
            "RUNEUSDT",
            "SANDUSDT",
            "TRXUSDT",
            "UNIUSDT",
            "XRPUSDT",
        ],
        excluded_incomplete_symbols=[
            "CFXUSDT",
            "LUNCUSDT",
            "SHIBUSDT",
            "STXUSDT",
        ],
        partition_boundaries=boundaries(),
        required_theory_evidence=V2_REQUIRED_THEORY_EVIDENCE,
        theory_source_policy=V2_THEORY_SOURCE_POLICY,
        forbidden_derivations=V2_FORBIDDEN_DERIVATIONS,
        required_next_protocol_bindings=V2_REQUIRED_NEXT_PROTOCOL_BINDINGS,
        discovery_stages=V2_DISCOVERY_STAGES,
        stop_conditions=V2_STOP_CONDITIONS,
        allowed_next_decisions=V2_ALLOWED_NEXT_DECISIONS,
        limitations=[
            (
                "The charter permits a no-return theory screen only and does not "
                "authorize full archive acquisition or development replay."
            ),
            (
                "The synthetic foundation is internal arithmetic evidence and not "
                "proof of exchange margin, liquidation, ADL, or execution behavior."
            ),
            (
                "Historical contract metadata, dated fees, collateral policy, and "
                "borrow requirements remain unresolved data dependencies."
            ),
            (
                "The 31-symbol source-complete set is a feasibility set, not a "
                "selected portfolio or profitable universe."
            ),
            (
                "Any selected theory still requires separate full-acquisition, "
                "execution, cost, gate, and one-shot development protocols."
            ),
            (
                "No charter decision creates candidate, Pine, paper, sandbox, "
                "micro-live, live, or capital eligibility."
            ),
        ],
    )


def write_charter(path: Path, charter: V2MechanismDiscoveryCharter) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = charter.model_dump_json(indent=2) + "\n"
    if V2MechanismDiscoveryCharter.model_validate_json(serialized) != charter:
        raise ValueError("V2 discovery charter JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V2MechanismDiscoveryCharter:
    if args.output.exists():
        raise ValueError("Frozen V2 discovery charter exists; use --check")
    protocol, result = load_inputs(args)
    charter = authoritative_charter(
        registered_at=datetime.now(UTC),
        protocol=protocol,
        result=result,
    )
    write_charter(args.output, charter)
    print(
        f"WROTE {args.output} {charter.charter_evidence_hash} "
        f"proposal_budget={charter.maximum_theory_proposals}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V2MechanismDiscoveryCharter:
    protocol, result = load_inputs(args)
    charter = V2MechanismDiscoveryCharter.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_charter(
        registered_at=charter.registered_at,
        protocol=protocol,
        result=result,
    )
    if charter != expected:
        raise ValueError("V2 discovery charter is not reproducible")
    if not audit_v2_mechanism_discovery_charter(charter):
        raise ValueError("V2 discovery charter hash audit failed")
    print(
        "PASS "
        f"v2_discovery_charter={charter.charter_evidence_hash} "
        f"proposals={charter.maximum_theory_proposals} "
        f"return_tests={charter.maximum_return_tested_mechanisms_under_charter}",
        flush=True,
    )
    return charter


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the V2 no-return mechanism-discovery charter."
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
