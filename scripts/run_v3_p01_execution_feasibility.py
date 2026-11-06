import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_v3_p01_execution_feasibility import (  # noqa: E402
    V3P01ExecutionFeasibilityProtocol,
    V3P01ExecutionFeasibilityResult,
    V3P01ExecutionRequirementAssessment,
    audit_v3_p01_execution_feasibility_protocol,
    audit_v3_p01_execution_feasibility_result,
    build_v3_p01_execution_feasibility_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v3_p01_execution_feasibility_protocol import (  # noqa: E402
    DEFAULT_CHARTER,
    DEFAULT_COVERAGE_RESULT,
    DEFAULT_FOUNDATION_PROTOCOL,
    DEFAULT_FOUNDATION_RESULT,
    DEFAULT_METADATA_CONTRACT,
    DEFAULT_METADATA_RESULT,
    DEFAULT_METADATA_SUPERSEDED_CONTRACT,
    DEFAULT_REGISTER,
    builder_contract_hash,
    load_inputs,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/v3_p01_execution_feasibility_protocol_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p01_execution_feasibility_result_v1.json"
)
FOUNDATION_SOURCE = (
    PROJECT_ROOT
    / "src"
    / "aurex"
    / "backtest_engine"
    / "derivatives_foundation.py"
)
FOUNDATION_PROTOCOL_SOURCE = (
    PROJECT_ROOT
    / "src"
    / "aurex"
    / "backtest_engine"
    / "research_v2_derivatives_foundation_protocol.py"
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


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p01_execution_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p01_execution_feasibility.py",
            FOUNDATION_SOURCE,
            FOUNDATION_PROTOCOL_SOURCE,
        ]
    )


def cross_asset_foundation_source_hash() -> str:
    return source_contract_hash(
        [FOUNDATION_SOURCE, FOUNDATION_PROTOCOL_SOURCE]
    )


def load_protocol(args) -> V3P01ExecutionFeasibilityProtocol:
    _, _, coverage, metadata, foundation = load_inputs(args)
    protocol = V3P01ExecutionFeasibilityProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_execution_feasibility_protocol(protocol)
        or protocol.builder_contract_hash != builder_contract_hash()
        or protocol.v3p01_coverage_result_evidence_hash
        != coverage.result_evidence_hash
        or protocol.v2_metadata_audit_result_evidence_hash
        != metadata.result_evidence_hash
        or protocol.v2_foundation_result_evidence_hash
        != foundation.result_evidence_hash
    ):
        raise ValueError("Frozen V3P01 execution protocol audit failed")
    return protocol


def evidence_by_requirement(
    args,
    protocol: V3P01ExecutionFeasibilityProtocol,
):
    _, _, coverage, metadata, foundation = load_inputs(args)
    metadata_by_id = {
        item.requirement_id: item for item in metadata.requirement_assessments
    }
    expected_metadata_statuses = {
        "HISTORICAL_ACCOUNT_FEE_TIER": (
            "CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL"
        ),
        "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES": (
            "CURRENT_OR_UNAVAILABLE_NOT_HISTORICAL"
        ),
        "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE": (
            "PARTIAL_ARCHIVE_COVERAGE_REQUIRES_CONTINUITY_GATE"
        ),
        "HISTORICAL_FUTURES_ORDER_FILTERS": "CURRENT_ONLY_NOT_HISTORICAL",
        "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS": (
            "CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL"
        ),
        "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS": (
            "READY_HISTORICAL_ARCHIVE"
        ),
        "HISTORICAL_SPOT_ORDER_FILTERS": "CURRENT_ONLY_NOT_HISTORICAL",
        "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES": (
            "READY_HISTORICAL_ARCHIVE"
        ),
    }
    for requirement_id, expected_status in expected_metadata_statuses.items():
        if metadata_by_id[requirement_id].status != expected_status:
            raise ValueError(
                f"V3P01 bound metadata status changed: {requirement_id}"
            )

    foundation_text = FOUNDATION_SOURCE.read_text(encoding="utf-8")
    protocol_text = FOUNDATION_PROTOCOL_SOURCE.read_text(encoding="utf-8")
    same_asset_markers = [
        "return self.spot_quantity + self.perp_quantity",
        "target_base_quantity",
        "LONG_SPOT_SHORT_USD_M_PERPETUAL",
    ]
    if not all(
        marker in foundation_text or marker in protocol_text
        for marker in same_asset_markers
    ):
        raise ValueError("V2 same-asset foundation evidence markers changed")

    source_hash = cross_asset_foundation_source_hash()
    common_metadata = [metadata.result_evidence_hash]
    return [
        V3P01ExecutionRequirementAssessment(
            requirement_id=(
                "CROSS_ASSET_IDENTITY_HEDGE_AND_RESIDUAL_RISK_FOUNDATION"
            ),
            status="FAIL",
            evidence_hashes=[foundation.result_evidence_hash, source_hash],
            rationale=(
                "The audited V2 engine adds spot and perpetual base quantities to "
                "measure delta and targets one base quantity. That is valid only when "
                "both legs reference the same asset; it cannot net different assets, "
                "apply a cross-asset hedge ratio, or bound residual value risk."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="HISTORICAL_ACCOUNT_FEE_TIER",
            status="FAIL",
            evidence_hashes=common_metadata,
            rationale=(
                "The immutable metadata audit found only a current signed account "
                "commission surface and no complete historical 2023-2024 account-tier "
                "fee series."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id=(
                "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES"
            ),
            status="FAIL",
            evidence_hashes=[metadata.result_evidence_hash, foundation.result_evidence_hash],
            rationale=(
                "Current documentation and synthetic declared rules do not establish "
                "the complete point-in-time 2023-2024 collateral, liquidation, fee, "
                "and ADL rule history."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="HISTORICAL_FUTURES_CONTRACT_LIFECYCLE",
            status="FAIL",
            evidence_hashes=common_metadata,
            rationale=(
                "Archive boundaries and current exchange information do not prove a "
                "complete point-in-time listing, suspension, status, and delisting "
                "history; the frozen policy requires fail-closed continuity."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="HISTORICAL_FUTURES_ORDER_FILTERS",
            status="FAIL",
            evidence_hashes=common_metadata,
            rationale=(
                "Current futures tick, step, notional, and market-order filters cannot "
                "prove the rules that governed hypothetical 2023-2024 orders."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id=(
                "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS"
            ),
            status="FAIL",
            evidence_hashes=[metadata.result_evidence_hash, foundation.result_evidence_hash],
            rationale=(
                "The signed endpoint exposes current leverage brackets, while the "
                "synthetic engine uses invented fixed rates; neither is immutable "
                "historical Binance bracket evidence."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
            status="PASS",
            evidence_hashes=common_metadata,
            rationale=(
                "The immutable metadata audit qualified settled funding timestamps, "
                "interval hours, and rates from official historical archives."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="HISTORICAL_SPOT_ORDER_FILTERS",
            status="FAIL",
            evidence_hashes=common_metadata,
            rationale=(
                "Current spot exchange information cannot prove the point-in-time "
                "tick, lot, notional, and order constraints in 2023-2024."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id=(
                "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES"
            ),
            status="PASS",
            evidence_hashes=common_metadata,
            rationale=(
                "The immutable source census, pilot, and acquisition evidence qualify "
                "the required historical spot, perpetual, mark, index, and premium "
                "series source families."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id="SYNCHRONIZED_SOURCE_COVERAGE_25_SYMBOLS",
            status="PASS",
            evidence_hashes=[coverage.result_evidence_hash],
            rationale=(
                "The frozen timestamp-only V3P01 audit qualified 25 of 31 symbols "
                "against all predeclared synchronized coverage gates."
            ),
        ),
        V3P01ExecutionRequirementAssessment(
            requirement_id=(
                "SYNTHETIC_PARTIAL_FILL_ROLLBACK_IDEMPOTENCY_RECONCILIATION"
            ),
            status="PASS",
            evidence_hashes=[foundation.result_evidence_hash, source_hash],
            rationale=(
                "All 14 frozen same-asset synthetic scenarios passed for accounting, "
                "partial fills, rollback, idempotency, kill switch, and reconciliation; "
                "this pass does not cure the separate cross-asset risk failure."
            ),
        ),
    ]


def authoritative_result(
    *,
    generated_at: datetime,
    args,
    protocol: V3P01ExecutionFeasibilityProtocol,
) -> V3P01ExecutionFeasibilityResult:
    return build_v3_p01_execution_feasibility_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        cross_asset_foundation_source_hash=cross_asset_foundation_source_hash(),
        assessments=evidence_by_requirement(args, protocol),
        limitations=[
            (
                "Four requirements pass and seven fail; the all-required protocol "
                "therefore rejects V3P01 before primary selection."
            ),
            (
                "The 25-symbol timestamp qualification remains valid source evidence "
                "but cannot cure historical execution-state gaps."
            ),
            (
                "The same-asset synthetic foundation proves useful lifecycle "
                "mechanics but not cross-asset identity, hedge, or residual risk."
            ),
            (
                "V2 conservative metadata overrides were permitted only for protocol "
                "design and are explicitly insufficient for V3 primary selection."
            ),
            (
                "No market numeric value, parameter, signal, trade, PnL, return, "
                "validation, holdout, or forward datum was inspected."
            ),
            (
                "The rejection does not claim cointegration is impossible or "
                "universally unprofitable; it records that Aurex cannot execute a "
                "qualified historical test from the frozen evidence."
            ),
            (
                "The result selects no primary and grants no candidate, Pine, paper, "
                "sandbox, live, or capital permission."
            ),
        ],
    )


def write_result(path: Path, result: V3P01ExecutionFeasibilityResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P01ExecutionFeasibilityResult.model_validate_json(serialized) != result:
        raise ValueError("V3P01 execution result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_result(args):
    if args.output.exists():
        raise ValueError("Frozen V3P01 execution result exists; use --audit")
    protocol = load_protocol(args)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        args=args,
        protocol=protocol,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"passed={result.passed_requirement_count}/11 "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args):
    protocol = load_protocol(args)
    result = V3P01ExecutionFeasibilityResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_execution_feasibility_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("V3P01 execution result lineage audit failed")
    expected = authoritative_result(
        generated_at=result.generated_at,
        args=args,
        protocol=protocol,
    )
    if result != expected:
        raise ValueError("V3P01 execution result is not reproducible")
    print(
        "PASS "
        f"v3p01_execution={result.result_evidence_hash} "
        f"passed={result.passed_requirement_count}/11 "
        f"failed={result.failed_requirement_count}/11 "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen no-return V3P01 cross-asset execution "
            "and metadata feasibility result."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
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
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_result(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
