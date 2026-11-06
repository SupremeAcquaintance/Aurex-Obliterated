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
    V2DerivativesFoundationResult,
    audit_v2_derivatives_foundation_result,
)
from aurex.backtest_engine.research_v2_metadata_source_audit import (
    V2P01MetadataSourceAuditResult,
    audit_v2_p01_metadata_source_audit_result,
)
from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2P01MetadataSourceContract,
)
from aurex.backtest_engine.research_v2_metadata_source_contract_v1_1 import (
    V2P01MetadataSourceContractV1_1,
    audit_v2_p01_metadata_source_contract_v1_1,
)
from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_p01_coverage_result import (
    V3P01TimestampCoverageResult,
    audit_v3_p01_timestamp_coverage_result,
)
from aurex.backtest_engine.research_v3_p01_execution_feasibility import (
    V3P01ExecutionFeasibilityProtocol,
    audit_v3_p01_execution_feasibility_protocol,
    build_v3_p01_execution_feasibility_protocol,
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
DEFAULT_COVERAGE_RESULT = Path(
    "data/evidence/v3_p01_timestamp_coverage_result_v1.json"
)
DEFAULT_METADATA_CONTRACT = Path(
    "data/evidence/v2_p01_metadata_source_contract_v1_1.json"
)
DEFAULT_METADATA_SUPERSEDED_CONTRACT = Path(
    "data/evidence/v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_METADATA_RESULT = Path(
    "data/evidence/v2_p01_metadata_source_audit_v1_1.json"
)
DEFAULT_FOUNDATION_PROTOCOL = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = Path(
    "data/evidence/v2_derivatives_foundation_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p01_execution_feasibility_protocol_v1.json"
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
            / "freeze_v3_p01_execution_feasibility_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p01_execution_feasibility.py",
        ]
    )


def charter_builder_hash() -> str:
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


def register_builder_hash() -> str:
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


def coverage_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p01_timestamp_coverage.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p01_coverage_result.py",
        ]
    )


def metadata_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "run_v2_p01_metadata_source_audit.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v2_metadata_source_audit.py",
        ]
    )


def foundation_runner_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v2_derivatives_foundation.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "derivatives_foundation.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v2_derivatives_foundation_result.py",
        ]
    )


def load_inputs(args):
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_hash()
    ):
        raise ValueError("V3 charter audit failed")
    register = V3MechanismProposalRegister.model_validate_json(
        args.register.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V3 proposal register audit failed")

    coverage = V3P01TimestampCoverageResult.model_validate_json(
        args.coverage_result.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_timestamp_coverage_result(coverage)
        or coverage.runner_contract_hash != coverage_runner_hash()
        or coverage.summary.qualified_symbol_count != 25
        or not coverage.authorizes_execution_foundation_and_metadata_protocol
        or coverage.return_metrics_calculated
    ):
        raise ValueError("V3P01 timestamp coverage result audit failed")

    metadata_contract = V2P01MetadataSourceContractV1_1.model_validate_json(
        args.metadata_contract.read_text(encoding="utf-8")
    )
    superseded_metadata_contract = V2P01MetadataSourceContract.model_validate_json(
        args.metadata_superseded_contract.read_text(encoding="utf-8")
    )
    metadata_contract_audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=metadata_contract,
        superseded_contract=superseded_metadata_contract,
    )
    if metadata_contract_audit["status"] != "PASS":
        raise ValueError("V2 metadata contract audit failed")
    metadata = V2P01MetadataSourceAuditResult.model_validate_json(
        args.metadata_result.read_text(encoding="utf-8")
    )
    metadata_audit = audit_v2_p01_metadata_source_audit_result(
        result=metadata,
        contract=metadata_contract,
        current_runner_contract_hash=metadata_runner_hash(),
    )
    if (
        metadata_audit["status"] != "PASS"
        or metadata.unresolved_historical_requirement_count != 6
        or metadata.return_metrics_calculated
    ):
        raise ValueError("V2 metadata result audit failed")

    foundation_protocol = V2DerivativesFoundationProtocol.model_validate_json(
        args.foundation_protocol.read_text(encoding="utf-8")
    )
    if not audit_v2_derivatives_foundation_protocol(foundation_protocol):
        raise ValueError("V2 foundation protocol audit failed")
    foundation = V2DerivativesFoundationResult.model_validate_json(
        args.foundation_result.read_text(encoding="utf-8")
    )
    foundation_audit = audit_v2_derivatives_foundation_result(
        result=foundation,
        protocol=foundation_protocol,
        current_runner_contract_hash=foundation_runner_hash(),
    )
    if (
        foundation_audit["status"] != "PASS"
        or foundation.passed_scenario_count != 14
        or foundation.strategy_outcome_fields_inspected
    ):
        raise ValueError("V2 foundation result audit failed")
    return charter, register, coverage, metadata, foundation


def authoritative_protocol(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
    coverage: V3P01TimestampCoverageResult,
    metadata: V2P01MetadataSourceAuditResult,
    foundation: V2DerivativesFoundationResult,
) -> V3P01ExecutionFeasibilityProtocol:
    return build_v3_p01_execution_feasibility_protocol(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        v3p01_coverage_result_evidence_hash=coverage.result_evidence_hash,
        v2_metadata_audit_result_evidence_hash=metadata.result_evidence_hash,
        v2_foundation_result_evidence_hash=foundation.result_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        limitations=[
            (
                "All eleven requirements must pass; V2 research overrides cannot "
                "qualify V3 point-in-time execution before primary selection."
            ),
            (
                "The protocol reuses immutable prior source evidence and reads no "
                "market numeric value, strategy outcome, trade, PnL, or return."
            ),
            (
                "Timestamp coverage and synthetic arithmetic are necessary but not "
                "sufficient execution feasibility."
            ),
            (
                "The V2 engine models long spot and short perpetual quantities in one "
                "base asset and cannot prove cross-asset hedge or residual risk."
            ),
            (
                "Current exchange filters, account fees, leverage brackets, and "
                "liquidation rules cannot be projected backward as 2023-2024 truth."
            ),
            (
                "Any failed requirement rejects V3P01 before selection and cannot be "
                "repaired by parameterization or return inspection."
            ),
            (
                "A pass would still create no candidate, validation, holdout, "
                "forward, Pine, paper, sandbox, live, or capital permission."
            ),
        ],
    )


def write_protocol(
    path: Path,
    protocol: V3P01ExecutionFeasibilityProtocol,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if V3P01ExecutionFeasibilityProtocol.model_validate_json(
        serialized
    ) != protocol:
        raise ValueError("V3P01 execution protocol JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args):
    if args.output.exists():
        raise ValueError("Frozen V3P01 execution protocol exists; use --check")
    charter, register, coverage, metadata, foundation = load_inputs(args)
    protocol = authoritative_protocol(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
        coverage=coverage,
        metadata=metadata,
        foundation=foundation,
    )
    write_protocol(args.output, protocol)
    print(
        f"WROTE {args.output} {protocol.protocol_evidence_hash} "
        f"requirements={len(protocol.requirement_ids)}",
        flush=True,
    )
    return run_check(args)


def run_check(args):
    charter, register, coverage, metadata, foundation = load_inputs(args)
    protocol = V3P01ExecutionFeasibilityProtocol.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        charter=charter,
        register=register,
        coverage=coverage,
        metadata=metadata,
        foundation=foundation,
    )
    if protocol != expected:
        raise ValueError("V3P01 execution protocol is not reproducible")
    if not audit_v3_p01_execution_feasibility_protocol(protocol):
        raise ValueError("V3P01 execution protocol hash audit failed")
    print(
        "PASS "
        f"v3p01_execution_protocol={protocol.protocol_evidence_hash} "
        f"requirements={len(protocol.requirement_ids)} "
        f"overrides={protocol.conservative_historical_overrides_permitted} "
        f"returns={protocol.return_calculation_permitted}",
        flush=True,
    )
    return protocol


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the V3P01 cross-asset execution and metadata "
            "feasibility protocol."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--coverage-result",
        type=Path,
        default=DEFAULT_COVERAGE_RESULT,
    )
    parser.add_argument(
        "--metadata-contract",
        type=Path,
        default=DEFAULT_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--metadata-superseded-contract",
        type=Path,
        default=DEFAULT_METADATA_SUPERSEDED_CONTRACT,
    )
    parser.add_argument(
        "--metadata-result",
        type=Path,
        default=DEFAULT_METADATA_RESULT,
    )
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
