import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.research_v4_p01_continuation_contract import (  # noqa: E402
    TARDIS_EXCHANGE_DETAILS_URL,
    TARDIS_INSTRUMENT_METADATA_URL,
    V4P01_CONSUMED_REQUEST_IDS,
    V4P01ContinuationBudget,
    V4P01ContinuationContract,
    audit_v4_p01_continuation_contract,
    build_v4_p01_continuation_contract,
)
from aurex.backtest_engine.research_v4_p01_feasibility_contract import (  # noqa: E402
    V4P01TerminalArtifactContract,
)
from aurex.backtest_engine.research_v4_p01_feasibility_runner import (  # noqa: E402
    V4P01MetadataGateResult,
    V4P01SourceObservation,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_v4_p01_feasibility import (  # noqa: E402
    METADATA_GATE_FILENAME,
    audit_terminal,
    load_contract,
    load_ndjson,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_ORIGINAL_CONTRACT = Path(
    "data/evidence/v4_p01_feasibility_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v4_p01_feasibility_continuation_contract_v1.json"
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
            / "freeze_v4_p01_continuation_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_continuation_contract.py",
        ]
    )


def load_original_evidence(
    *,
    charter_path: Path,
    register_path: Path,
    contract_path: Path,
):
    original = load_contract(
        charter_path=charter_path,
        register_path=register_path,
        contract_path=contract_path,
    )
    terminal = audit_terminal(
        contract=original,
        project_root=PROJECT_ROOT,
    )
    metadata_path = PROJECT_ROOT / original.metadata_observation_path
    observations = load_ndjson(metadata_path, V4P01SourceObservation)
    metadata_gate = V4P01MetadataGateResult.model_validate_json(
        metadata_path.with_name(METADATA_GATE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    expected_reasons = sorted(
        [
            (
                "V4P01_META_BINANCE_EXCHANGE_DETAILS: product end does not "
                "cover development"
            ),
            (
                "V4P01_META_COINBASE_EXCHANGE_DETAILS: product end does not "
                "cover development"
            ),
        ]
    )
    if (
        terminal.terminal_kind != "REJECT"
        or terminal.decision != "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
        or terminal.resource_totals.attempts_used != 2
        or terminal.resource_totals.response_bytes != 74_788
        or terminal.completed_and_failed_request_ids
        != {"completed": V4P01_CONSUMED_REQUEST_IDS, "failed": []}
        or len(observations) != 2
        or any(
            not item.product_identity_matches
            or item.source_available_since is None
            or item.source_available_since > original.development_start
            or item.source_available_to is None
            or item.source_available_to < original.development_end
            or item.symbol_available_since is None
            or item.symbol_available_since > original.development_start
            or item.symbol_available_to is not None
            for item in observations
        )
        or metadata_gate.status != "FAIL"
        or metadata_gate.reasons != expected_reasons
        or metadata_gate.payload_phase_authorized
    ):
        raise ValueError("V4P01 continuation original evidence audit failed")
    return original, terminal, observations, metadata_gate


def terminal_artifacts() -> V4P01TerminalArtifactContract:
    return V4P01TerminalArtifactContract(
        complete_artifact=(
            "data/evidence/v4_p01_feasibility_continuation_complete_v1.json"
        ),
        reject_artifact=(
            "data/evidence/v4_p01_feasibility_continuation_reject_v1.json"
        ),
        transport_stop_artifact=(
            "data/evidence/"
            "v4_p01_feasibility_continuation_transport_stop_v1.json"
        ),
        required_common_fields=[
            "builder_and_contract_hashes",
            "completed_and_failed_request_ids",
            "decision",
            "execution_gate_results",
            "metadata_and_payload_observation_hashes",
            "parsed_and_prohibited_field_manifest",
            "request_journal_hash",
            "resource_totals",
            "selection_and_permission_boundary",
            "terminal_timestamp",
        ],
        required_transport_stop_fields=[
            "failed_request_id_and_attempt",
            "failure_class_and_message",
            "partial_byte_count_and_sha256",
            "request_intent_record_hash",
            "response_headers_if_received",
            "unconsumed_request_and_byte_budgets",
            "unreconciled_intent_status",
        ],
    )


def authoritative_contract(
    *,
    frozen_at: datetime,
    source_reviewed_at: datetime,
    original,
    terminal,
    observations,
    metadata_gate,
) -> V4P01ContinuationContract:
    return build_v4_p01_continuation_contract(
        frozen_at=frozen_at,
        original_contract_evidence_hash=original.contract_evidence_hash,
        original_terminal_reject_evidence_hash=terminal.result_evidence_hash,
        original_runner_contract_hash=terminal.builder_and_contract_hashes[
            "runner_contract_hash"
        ],
        original_metadata_gate_evidence_hash=(
            metadata_gate.result_evidence_hash
        ),
        inherited_metadata_observation_hashes=[
            item.observation_evidence_hash for item in observations
        ],
        builder_contract_hash=builder_contract_hash(),
        incorrect_interpretation=(
            "The original runner required each exact symbol to have a non-null "
            "availableTo timestamp at or after the development end."
        ),
        documented_semantic=(
            "Tardis documents availableTo as optional and set when collection "
            "stops for an instrument; absence is compatible with ongoing "
            "collection when the exchange source boundary remains current."
        ),
        corrected_metadata_condition=(
            "For an exact matched product, symbol availableSince must cover the "
            "development start and either symbol availableTo covers the "
            "development end or symbol availableTo is absent while the enclosing "
            "exchange source availableTo covers the development end."
        ),
        official_source_urls=[
            TARDIS_INSTRUMENT_METADATA_URL,
            TARDIS_EXCHANGE_DETAILS_URL,
        ],
        source_reviewed_at=source_reviewed_at,
        consumed_request_ids=V4P01_CONSUMED_REQUEST_IDS,
        requests=original.requests[2:],
        transport_budget=V4P01ContinuationBudget(),
        venue_product_bindings=original.venue_product_bindings,
        development_start=original.development_start,
        development_end=original.development_end,
        execution_gates=original.execution_gates,
        journal_path=(
            "data/evidence/v4_p01_continuation/transport_journal_v1.ndjson"
        ),
        corrected_metadata_gate_path=(
            "data/evidence/v4_p01_continuation/"
            "corrected_metadata_gate_v1.json"
        ),
        payload_observation_path=(
            "data/evidence/v4_p01_continuation/"
            "payload_observations_v1.ndjson"
        ),
        raw_payload_directory="data/evidence/v4_p01_continuation/raw",
        terminal_artifacts=terminal_artifacts(),
        limitations=[
            (
                "The original reject artifact remains immutable and is neither "
                "deleted, rewritten, nor represented as valid market evidence."
            ),
            (
                "This continuation corrects one documented optional-field "
                "interpretation before payload outcomes are observed."
            ),
            (
                "The two metadata requests are inherited and cannot be repeated."
            ),
            (
                "Only the six original unconsumed payload URLs are authorized, "
                "with one attempt each and zero retries."
            ),
            (
                "No additional date, venue, product, channel, offset, credential, "
                "request method, or transport budget is introduced."
            ),
            (
                "Raw market values remain opaque; only hashes, schema keys, "
                "identity, timestamps, sequences, disconnects, and resources may "
                "be observed."
            ),
            (
                "The correction does not establish historical fees, filters, "
                "account access, two-leg execution, capacity, or profitability."
            ),
            (
                "No signal, trade, P/L, return, candidate, validation, paper, "
                "sandbox, live, or capital permission exists."
            ),
            (
                "Any payload transport failure consumes that request's only "
                "attempt and terminally stops the continuation."
            ),
            (
                "Passing the payload pilots still cannot select V4P01 unless "
                "every independent hard execution gate passes."
            ),
        ],
    )


def write_contract(path: Path, contract: V4P01ContinuationContract) -> None:
    serialized = (contract.model_dump_json(indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale continuation output exists: {temporary}")
    temporary.write_bytes(serialized)
    temporary.replace(path)


def run_check(args) -> V4P01ContinuationContract:
    original, terminal, observations, metadata_gate = load_original_evidence(
        charter_path=args.charter,
        register_path=args.register,
        contract_path=args.original_contract,
    )
    stored = V4P01ContinuationContract.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        source_reviewed_at=stored.source_reviewed_at,
        original=original,
        terminal=terminal,
        observations=observations,
        metadata_gate=metadata_gate,
    )
    if stored != expected or not audit_v4_p01_continuation_contract(stored):
        raise ValueError("Frozen V4P01 continuation contract audit failed")
    print(
        f"PASS v4p01_continuation={stored.contract_evidence_hash} "
        f"requests={len(stored.requests)} metadata_repeats=0 "
        f"selected={stored.selects_primary} returns={stored.return_metrics_calculated}",
        flush=True,
    )
    return stored


def run_freeze(args) -> V4P01ContinuationContract:
    if args.output.exists():
        raise ValueError("V4P01 continuation contract exists; use --check")
    original, terminal, observations, metadata_gate = load_original_evidence(
        charter_path=args.charter,
        register_path=args.register,
        contract_path=args.original_contract,
    )
    now = datetime.now(UTC)
    contract = authoritative_contract(
        frozen_at=now,
        source_reviewed_at=now,
        original=original,
        terminal=terminal,
        observations=observations,
        metadata_gate=metadata_gate,
    )
    write_contract(args.output, contract)
    return run_check(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Freeze or audit the V4P01 optional-availableTo interpretation "
            "correction and six-request continuation contract."
        )
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--original-contract",
        type=Path,
        default=DEFAULT_ORIGINAL_CONTRACT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            run_check(args)
        else:
            run_freeze(args)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
