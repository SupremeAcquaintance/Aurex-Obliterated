import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v3_feasibility_screen import (
    V3FeasibilityDisposition,
    V3MechanismFeasibilityScreen,
    audit_v3_mechanism_feasibility_screen,
    build_v3_mechanism_feasibility_screen,
)
from aurex.backtest_engine.research_v3_p01_execution_feasibility import (
    V3_P01_EXECUTION_FAIL_DECISION,
    V3P01ExecutionFeasibilityProtocol,
    V3P01ExecutionFeasibilityResult,
    audit_v3_p01_execution_feasibility_protocol,
    audit_v3_p01_execution_feasibility_result,
)
from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3P02PayloadPilotProtocol,
    audit_v3_p02_payload_pilot_protocol,
)
from aurex.backtest_engine.research_v3_p02_stop_result import (
    V3_P02_STOP_DECISION,
    V3P02PayloadPilotStopResult,
    audit_v3_p02_payload_pilot_stop_result,
)
from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3_P03_FAIL_DECISION,
)
from aurex.backtest_engine.research_v3_p03_stop_result import (
    V3P03SourceAuditStopResult,
    audit_v3_p03_source_audit_stop_result,
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
DEFAULT_P01_PROTOCOL = Path(
    "data/evidence/v3_p01_execution_feasibility_protocol_v1.json"
)
DEFAULT_P01_RESULT = Path(
    "data/evidence/v3_p01_execution_feasibility_result_v1.json"
)
DEFAULT_P02_PROTOCOL = Path(
    "data/evidence/v3_p02_payload_pilot_protocol_v1.json"
)
DEFAULT_P02_STOP = Path(
    "data/evidence/v3_p02_payload_pilot_stop_result_v1.json"
)
DEFAULT_P03_STOP = Path(
    "data/evidence/v3_p03_source_audit_stop_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_mechanism_feasibility_screen_v1.json"
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
            PROJECT_ROOT / "scripts" / "freeze_v3_feasibility_screen.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_feasibility_screen.py",
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


def p01_protocol_builder_hash() -> str:
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


def p01_runner_hash() -> str:
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


def p02_protocol_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p02_payload_pilot_protocol.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_payload_pilot.py",
        ]
    )


def p02_runner_hash() -> str:
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


def p02_finalizer_hash() -> str:
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


def p03_runner_hash() -> str:
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


def p03_finalizer_hash() -> str:
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
        args.charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_hash()
    ):
        raise ValueError("V3 discovery charter audit failed")
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

    p01_protocol = V3P01ExecutionFeasibilityProtocol.model_validate_json(
        args.p01_protocol.read_text(encoding="utf-8")
    )
    p01 = V3P01ExecutionFeasibilityResult.model_validate_json(
        args.p01_result.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p01_execution_feasibility_protocol(p01_protocol)
        or p01_protocol.builder_contract_hash != p01_protocol_builder_hash()
        or not audit_v3_p01_execution_feasibility_result(p01)
        or p01.protocol_evidence_hash != p01_protocol.protocol_evidence_hash
        or p01.runner_contract_hash != p01_runner_hash()
        or p01.decision != V3_P01_EXECUTION_FAIL_DECISION
        or p01.passed_requirement_count != 4
        or p01.failed_requirement_count != 7
        or p01.selects_primary
        or p01.return_metrics_calculated
    ):
        raise ValueError("V3P01 terminal evidence audit failed")

    p02_protocol = V3P02PayloadPilotProtocol.model_validate_json(
        args.p02_protocol.read_text(encoding="utf-8")
    )
    p02 = V3P02PayloadPilotStopResult.model_validate_json(
        args.p02_stop.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_payload_pilot_protocol(p02_protocol)
        or p02_protocol.builder_contract_hash != p02_protocol_builder_hash()
        or not audit_v3_p02_payload_pilot_stop_result(p02)
        or p02.payload_pilot_protocol_evidence_hash
        != p02_protocol.protocol_evidence_hash
        or p02.failed_runner_contract_hash != p02_runner_hash()
        or p02.finalizer_contract_hash != p02_finalizer_hash()
        or p02.decision != V3_P02_STOP_DECISION
        or p02.verified_sample_count != 2
        or p02.failed_sample_count != 1
        or p02.authorizes_retry
        or p02.selects_primary
        or p02.return_metrics_calculated
    ):
        raise ValueError("V3P02 terminal evidence audit failed")

    p03 = V3P03SourceAuditStopResult.model_validate_json(
        args.p03_stop.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_source_audit_stop_result(p03)
        or p03.source_runner_contract_hash != p03_runner_hash()
        or p03.finalizer_contract_hash != p03_finalizer_hash()
        or p03.decision != V3_P03_FAIL_DECISION
        or p03.evaluated_requirement_ids
        or p03.qualified_requirement_ids
        or p03.selects_primary
        or p03.return_metrics_calculated
    ):
        raise ValueError("V3P03 terminal evidence audit failed")
    return charter, register, p01, p02, p03


def authoritative_screen(
    *,
    frozen_at: datetime,
    charter: V3MechanismDiscoveryCharter,
    register: V3MechanismProposalRegister,
    p01: V3P01ExecutionFeasibilityResult,
    p02: V3P02PayloadPilotStopResult,
    p03: V3P03SourceAuditStopResult,
) -> V3MechanismFeasibilityScreen:
    proposal_names = {
        item.proposal_id: item.mechanism_name for item in register.proposals
    }
    dispositions = [
        V3FeasibilityDisposition(
            proposal_id="V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
            mechanism_name=proposal_names[
                "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE"
            ],
            terminal_evidence_artifact=(
                "data/evidence/"
                "v3_p01_execution_feasibility_result_v1.json"
            ),
            terminal_evidence_hash=p01.result_evidence_hash,
            formal_status="REJECTED_EXECUTION_AND_METADATA_FEASIBILITY",
            reason_codes=[
                "CROSS_ASSET_IDENTITY_HEDGE_FOUNDATION_ABSENT",
                "HISTORICAL_EXECUTION_METADATA_INCOMPLETE",
                "SEVEN_OF_ELEVEN_REQUIREMENTS_FAILED",
            ],
        ),
        V3FeasibilityDisposition(
            proposal_id="V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
            mechanism_name=proposal_names[
                "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY"
            ],
            terminal_evidence_artifact=(
                "data/evidence/v3_p02_payload_pilot_stop_result_v1.json"
            ),
            terminal_evidence_hash=p02.result_evidence_hash,
            formal_status="STOPPED_TRANSPORT_UNRESOLVED",
            reason_codes=[
                "AUTHORITATIVE_THREE_SAMPLE_PILOT_RESULT_ABSENT",
                "DOGE_RESPONSE_TRUNCATED_BEFORE_DECLARED_SIZE",
                "NO_RETRY_PER_FROZEN_REQUEST_BUDGET",
                "TWO_OF_THREE_SAMPLES_VERIFIED",
            ],
        ),
        V3FeasibilityDisposition(
            proposal_id="V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
            mechanism_name=proposal_names[
                "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION"
            ],
            terminal_evidence_artifact=(
                "data/evidence/v3_p03_source_audit_stop_result_v1.json"
            ),
            terminal_evidence_hash=p03.result_evidence_hash,
            formal_status="REJECTED_HISTORICAL_EVIDENCE_UNAVAILABLE",
            reason_codes=[
                "FORMAL_SOURCE_AUDIT_INCOMPLETE",
                "HISTORICAL_L2_QUEUE_EVIDENCE_UNAVAILABLE",
                "HTTP_202_POLL_BUDGET_EXHAUSTED",
            ],
        ),
    ]
    return build_v3_mechanism_feasibility_screen(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        v3p01_terminal_evidence_hash=p01.result_evidence_hash,
        v3p02_terminal_evidence_hash=p02.result_evidence_hash,
        v3p03_terminal_evidence_hash=p03.result_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        dispositions=dispositions,
        limitations=[
            (
                "The screen evaluates only the three predeclared V3 feasibility "
                "paths and selects none because no path completed every gate."
            ),
            (
                "V3P01 is formally rejected for this charter because seven required "
                "execution or historical-metadata conditions failed."
            ),
            (
                "V3P02 is stopped for unresolved transport under its frozen "
                "three-request budget; this is not a profitability rejection."
            ),
            (
                "V3P03 is rejected for this charter because required historical "
                "order-book and queue evidence was not qualified."
            ),
            (
                "No V3 mechanism parameter set, market numeric value, strategy "
                "outcome, trade, PnL, or return was compared in this screen."
            ),
            (
                "Two verified V3P02 sample archives remain reusable evidence but do "
                "not authorize a full payload acquisition."
            ),
            (
                "Closing V3 prevents after-the-fact retries, amendments, or threshold "
                "changes from turning an incomplete path into a selected primary."
            ),
            (
                "A future V4 effort requires a separately versioned discovery charter "
                "with new pre-observation source and transport rules."
            ),
            (
                "This screen grants no candidate, development, validation, holdout, "
                "forward, Pine, paper, sandbox, live, or capital permission."
            ),
        ],
    )


def write_screen(path: Path, screen: V3MechanismFeasibilityScreen) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = screen.model_dump_json(indent=2) + "\n"
    if V3MechanismFeasibilityScreen.model_validate_json(serialized) != screen:
        raise ValueError("V3 feasibility screen JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_freeze(args) -> V3MechanismFeasibilityScreen:
    if args.output.exists():
        raise ValueError("Frozen V3 feasibility screen exists; use --check")
    charter, register, p01, p02, p03 = load_inputs(args)
    screen = authoritative_screen(
        frozen_at=datetime.now(UTC),
        charter=charter,
        register=register,
        p01=p01,
        p02=p02,
        p03=p03,
    )
    write_screen(args.output, screen)
    print(
        f"WROTE {args.output} {screen.screen_evidence_hash} "
        f"selected={screen.selected_primary_count} "
        f"decision={screen.decision}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V3MechanismFeasibilityScreen:
    charter, register, p01, p02, p03 = load_inputs(args)
    screen = V3MechanismFeasibilityScreen.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_screen(
        frozen_at=screen.frozen_at,
        charter=charter,
        register=register,
        p01=p01,
        p02=p02,
        p03=p03,
    )
    if (
        screen != expected
        or not audit_v3_mechanism_feasibility_screen(screen)
    ):
        raise ValueError("V3 feasibility screen is not reproducible")
    print(
        "PASS "
        f"v3_screen={screen.screen_evidence_hash} "
        f"selected={screen.selected_primary_count} "
        f"decision={screen.decision} "
        f"returns={screen.return_metrics_calculated}",
        flush=True,
    )
    return screen


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or verify the terminal no-return V3 feasibility screen."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--p01-protocol",
        type=Path,
        default=DEFAULT_P01_PROTOCOL,
    )
    parser.add_argument("--p01-result", type=Path, default=DEFAULT_P01_RESULT)
    parser.add_argument(
        "--p02-protocol",
        type=Path,
        default=DEFAULT_P02_PROTOCOL,
    )
    parser.add_argument("--p02-stop", type=Path, default=DEFAULT_P02_STOP)
    parser.add_argument("--p03-stop", type=Path, default=DEFAULT_P03_STOP)
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
