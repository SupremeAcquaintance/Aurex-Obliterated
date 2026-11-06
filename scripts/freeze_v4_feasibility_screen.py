import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_v4_discovery_charter import (  # noqa: E402
    V4MechanismDiscoveryCharter,
    audit_v4_mechanism_discovery_charter,
)
from aurex.backtest_engine.research_v4_feasibility_screen import (  # noqa: E402
    V4FeasibilityDisposition,
    V4MechanismFeasibilityScreen,
    audit_v4_mechanism_feasibility_screen,
    build_v4_mechanism_feasibility_screen,
)
from aurex.backtest_engine.research_v4_p01_terminal_addendum import (  # noqa: E402
    V4P01TerminalAuditAddendum,
    audit_v4_p01_terminal_audit_addendum,
)
from aurex.backtest_engine.research_v4_proposal_register import (  # noqa: E402
    V4MechanismProposalRegister,
    audit_v4_mechanism_proposal_register,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_discovery_charter import (  # noqa: E402
    builder_contract_hash as charter_builder_hash,
)
from scripts.freeze_v4_p01_terminal_addendum import (  # noqa: E402
    authoritative_addendum,
)
from scripts.freeze_v4_p01_terminal_addendum import (  # noqa: E402
    builder_contract_hash as p01_addendum_builder_hash,
)
from scripts.freeze_v4_p01_terminal_addendum import (  # noqa: E402
    load_evidence as load_p01_evidence,
)
from scripts.freeze_v4_proposal_register import (  # noqa: E402
    builder_contract_hash as register_builder_hash,
)
from scripts.run_v4_p02_feasibility import (  # noqa: E402
    audit_terminal as audit_p02_terminal,
)
from scripts.run_v4_p02_feasibility import (  # noqa: E402
    load_contract as load_p02_contract,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_P01_ADDENDUM = Path(
    "data/evidence/v4_p01_terminal_audit_addendum_v1.json"
)
DEFAULT_P02_CONTRACT = Path(
    "data/evidence/v4_p02_feasibility_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_mechanism_feasibility_screen_v1.json"
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
            PROJECT_ROOT / "scripts" / "freeze_v4_feasibility_screen.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_feasibility_screen.py",
        ]
    )


def load_inputs(args):
    charter = V4MechanismDiscoveryCharter.model_validate_json(
        args.charter.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_mechanism_discovery_charter(charter)
        or charter.builder_contract_hash != charter_builder_hash()
    ):
        raise ValueError("V4 discovery charter audit failed")
    register = V4MechanismProposalRegister.model_validate_json(
        args.register.read_text(encoding="utf-8")
    )
    if (
        not audit_v4_mechanism_proposal_register(register)
        or register.builder_contract_hash != register_builder_hash()
        or register.discovery_charter_evidence_hash
        != charter.charter_evidence_hash
    ):
        raise ValueError("V4 proposal register audit failed")

    p01_evidence = load_p01_evidence()
    p01 = V4P01TerminalAuditAddendum.model_validate_json(
        args.p01_addendum.read_text(encoding="utf-8")
    )
    expected_p01 = authoritative_addendum(
        audited_at=p01.audited_at,
        continuation=p01_evidence[0],
        original=p01_evidence[1],
        original_terminal=p01_evidence[2],
        corrected_gate=p01_evidence[3],
        terminal=p01_evidence[4],
        payload_observations=p01_evidence[5],
    )
    if (
        p01 != expected_p01
        or not audit_v4_p01_terminal_audit_addendum(p01)
        or p01.builder_contract_hash != p01_addendum_builder_hash()
        or p01.invariant_decision
        != "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
        or p01.selects_primary
    ):
        raise ValueError("V4P01 terminal addendum audit failed")

    p02_contract = load_p02_contract(
        charter_path=args.charter,
        register_path=args.register,
        contract_path=args.p02_contract,
    )
    p02 = audit_p02_terminal(
        contract=p02_contract,
        project_root=PROJECT_ROOT,
    )
    expected_failed_id = "V4P02_META_DERIBIT_EXCHANGE_DETAILS"
    if (
        p02.terminal_kind != "TRANSPORT_STOP"
        or p02.decision != "STOP_V4P02_TRANSPORT_NO_RETRY"
        or p02.failed_request_id_and_attempt
        != {"request_id": expected_failed_id, "attempt": 1}
        or p02.failure_class_and_message
        != {
            "failure_class": "ValueError",
            "failure_message": "V4P02 metadata body budget exceeded",
        }
        or p02.response_headers_if_received.get("content-length")
        != "203310405"
        or p02.resource_totals.attempts_used != 1
        or p02.resource_totals.http_hops_used != 1
        or p02.resource_totals.response_body_bytes != 0
        or p02.header_observation_hashes
        or p02.authorizes_dataset_payload_gets
        or p02.selects_primary
    ):
        raise ValueError("V4P02 terminal transport evidence audit failed")
    return charter, register, p01, p02_contract, p02


def authoritative_screen(
    *,
    frozen_at: datetime,
    charter: V4MechanismDiscoveryCharter,
    register: V4MechanismProposalRegister,
    p01,
    p02_contract,
    p02,
) -> V4MechanismFeasibilityScreen:
    names = {
        item.proposal_id: item.mechanism_name for item in register.proposals
    }
    dispositions = [
        V4FeasibilityDisposition(
            proposal_id=(
                "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
            ),
            mechanism_name=names[
                "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
            ],
            terminal_evidence_artifact=(
                "data/evidence/v4_p01_terminal_audit_addendum_v1.json"
            ),
            terminal_evidence_hash=p01.addendum_evidence_hash,
            formal_status="REJECTED_SOURCE_AND_EXECUTION_FEASIBILITY",
            reason_codes=[
                "POINT_IN_TIME_FEES_AND_FEE_CURRENCY_FAILED",
                "POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE_FAILED",
                "RECOVERY_SNAPSHOT_SCHEMA_FAILED",
                "SOURCE_REVISION_IDENTITY_FAILED",
            ],
        ),
        V4FeasibilityDisposition(
            proposal_id=(
                "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
            ),
            mechanism_name=names[
                "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
            ],
            terminal_evidence_artifact=(
                "data/evidence/v4_p02_source_census_transport_stop_v1.json"
            ),
            terminal_evidence_hash=p02.result_evidence_hash,
            formal_status="STOPPED_METADATA_TRANSPORT_BUDGET",
            reason_codes=[
                "DECLARED_METADATA_BODY_EXCEEDED_FROZEN_BUDGET",
                "NO_DATASET_HEAD_ATTEMPT_CONSUMED",
                "NO_RETRY_OR_BUDGET_EXPANSION_PERMITTED",
                "NO_SOURCE_CENSUS_GATE_COMPLETED",
            ],
            transport_observation_manifest={
                "accepted_response_body_bytes": 0,
                "attempts_used": 1,
                "dataset_head_attempts_used": 0,
                "declared_metadata_content_length_bytes": 203_310_405,
                "http_hops_used": 1,
                "metadata_body_budget_bytes": (
                    p02_contract.transport_budget.maximum_metadata_body_bytes
                ),
            },
        ),
    ]
    return build_v4_mechanism_feasibility_screen(
        frozen_at=frozen_at,
        discovery_charter_evidence_hash=charter.charter_evidence_hash,
        proposal_register_evidence_hash=register.register_evidence_hash,
        v4p01_terminal_addendum_evidence_hash=p01.addendum_evidence_hash,
        v4p02_contract_evidence_hash=p02_contract.contract_evidence_hash,
        v4p02_terminal_stop_evidence_hash=p02.result_evidence_hash,
        v4p02_request_journal_hash=p02.request_journal_hash,
        builder_contract_hash=builder_contract_hash(),
        dispositions=dispositions,
        limitations=[
            (
                "The screen evaluates only the two predeclared V4 mechanisms "
                "and selects neither because neither completed every gate."
            ),
            (
                "V4P01 is rejected before returns on four independent source "
                "and point-in-time execution-rule failures."
            ),
            (
                "V4P02 is stopped for unresolved transport under its frozen "
                "one-attempt metadata budget; this is not a profitability result."
            ),
            (
                "The V4P02 endpoint declared a 203310405-byte body against an "
                "8388608-byte limit; Aurex accepted zero body bytes."
            ),
            (
                "No V4P02 dataset HEAD, dataset payload, raw replay, credential, "
                "market numeric value, signal, trade, PnL, or return was used."
            ),
            (
                "Closing V4 prohibits after-the-fact retries, request-budget "
                "expansion, metadata alternatives, or proposal amendments."
            ),
            (
                "A successor discovery round cannot begin until a separately "
                "frozen capability-gap review defines realistically accessible "
                "data, metadata, venue, account, and execution foundations."
            ),
            (
                "The capability-gap review may not create a strategy candidate "
                "or inspect outcomes."
            ),
            (
                "This screen grants no network, payload, candidate, development, "
                "validation, holdout, forward, Pine, paper, sandbox, live, or "
                "capital permission."
            ),
        ],
    )


def write_screen(path: Path, screen: V4MechanismFeasibilityScreen) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (screen.model_dump_json(indent=2) + "\n").encode("utf-8")
    if V4MechanismFeasibilityScreen.model_validate_json(serialized) != screen:
        raise ValueError("V4 feasibility screen JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V4 feasibility output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def run_freeze(args) -> V4MechanismFeasibilityScreen:
    if args.output.exists():
        raise ValueError("Frozen V4 feasibility screen exists; use --check")
    evidence = load_inputs(args)
    screen = authoritative_screen(
        frozen_at=datetime.now(UTC),
        charter=evidence[0],
        register=evidence[1],
        p01=evidence[2],
        p02_contract=evidence[3],
        p02=evidence[4],
    )
    write_screen(args.output, screen)
    print(
        f"WROTE {args.output} {screen.screen_evidence_hash} "
        f"selected={screen.selected_primary_count} "
        f"decision={screen.decision}",
        flush=True,
    )
    return run_check(args)


def run_check(args) -> V4MechanismFeasibilityScreen:
    evidence = load_inputs(args)
    screen = V4MechanismFeasibilityScreen.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_screen(
        frozen_at=screen.frozen_at,
        charter=evidence[0],
        register=evidence[1],
        p01=evidence[2],
        p02_contract=evidence[3],
        p02=evidence[4],
    )
    if (
        screen != expected
        or not audit_v4_mechanism_feasibility_screen(screen)
    ):
        raise ValueError("V4 feasibility screen is not reproducible")
    print(
        f"PASS v4_screen={screen.screen_evidence_hash} "
        f"selected={screen.selected_primary_count} "
        f"decision={screen.decision} "
        f"returns={screen.return_metrics_calculated}",
        flush=True,
    )
    return screen


def parse_args():
    parser = argparse.ArgumentParser(
        description="Freeze or verify the terminal no-return V4 screen."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--p01-addendum",
        type=Path,
        default=DEFAULT_P01_ADDENDUM,
    )
    parser.add_argument(
        "--p02-contract",
        type=Path,
        default=DEFAULT_P02_CONTRACT,
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
