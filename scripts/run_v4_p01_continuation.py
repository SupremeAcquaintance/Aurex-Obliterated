import argparse
import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402

from aurex.backtest_engine.research_v4_p01_continuation_contract import (  # noqa: E402
    V4P01ContinuationContract,
    audit_v4_p01_continuation_contract,
)
from aurex.backtest_engine.research_v4_p01_feasibility_contract import (  # noqa: E402
    V4P01_PERMITTED_OBSERVATION_FIELDS,
    V4P01_PROHIBITED_PARSED_FIELDS,
    V4P01_REQUIRED_GATE_IDS,
)
from aurex.backtest_engine.research_v4_p01_feasibility_runner import (  # noqa: E402
    EMPTY_SHA256,
    V4P01ExecutionGateResult,
    V4P01JournalRecord,
    V4P01MetadataGateResult,
    V4P01SourceObservation,
    V4P01TerminalResult,
    build_v4_p01_metadata_gate_result,
    build_v4_p01_terminal_result,
    unresolved_execution_gates,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_p01_continuation_contract import (  # noqa: E402
    DEFAULT_CHARTER,
    DEFAULT_ORIGINAL_CONTRACT,
    DEFAULT_OUTPUT,
    DEFAULT_REGISTER,
    authoritative_contract,
    load_original_evidence,
)
from scripts.run_v4_p01_feasibility import (  # noqa: E402
    SELECTION_PERMISSION_BOUNDARY,
    EvidenceIntegrityError,
    HttpxTransport,
    _observation_for_response,
    _resource_totals,
    append_observation,
    atomic_write,
    close_unreconciled_intent,
    evaluate_execution_gates,
    execute_request,
    file_sha256,
    load_ndjson,
    request_hashes,
    safe_project_path,
)


@dataclass(frozen=True)
class ContinuationRuntimeBudget:
    total_attempt_budget: int
    total_response_byte_budget: int
    storage_budget_bytes: int
    protocol_wall_clock_budget_seconds: int


@dataclass(frozen=True)
class ContinuationRuntimeContract:
    contract_evidence_hash: str
    requests: list
    transport_budget: ContinuationRuntimeBudget
    venue_product_bindings: dict[str, str]
    raw_payload_directory: str
    metadata_observation_path: str
    payload_observation_path: str
    terminal_artifacts: object


def runtime_contract(
    contract: V4P01ContinuationContract,
) -> ContinuationRuntimeContract:
    budget = contract.transport_budget
    return ContinuationRuntimeContract(
        contract_evidence_hash=contract.contract_evidence_hash,
        requests=contract.requests,
        transport_budget=ContinuationRuntimeBudget(
            total_attempt_budget=budget.continuation_attempt_budget,
            total_response_byte_budget=budget.payload_response_byte_budget,
            storage_budget_bytes=budget.continuation_storage_budget_bytes,
            protocol_wall_clock_budget_seconds=(
                budget.continuation_wall_clock_budget_seconds
            ),
        ),
        venue_product_bindings=contract.venue_product_bindings,
        raw_payload_directory=contract.raw_payload_directory,
        metadata_observation_path=contract.corrected_metadata_gate_path,
        payload_observation_path=contract.payload_observation_path,
        terminal_artifacts=contract.terminal_artifacts,
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
            PROJECT_ROOT / "scripts" / "run_v4_p01_continuation.py",
            PROJECT_ROOT / "scripts" / "run_v4_p01_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_feasibility_runner.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_continuation_contract.py",
        ]
    )


def load_continuation_contract(
    *,
    charter_path: Path,
    register_path: Path,
    original_contract_path: Path,
    continuation_contract_path: Path,
) -> tuple[
    V4P01ContinuationContract,
    object,
    V4P01TerminalResult,
    list[V4P01SourceObservation],
    V4P01MetadataGateResult,
]:
    original, terminal, metadata_observations, original_gate = (
        load_original_evidence(
            charter_path=charter_path,
            register_path=register_path,
            contract_path=original_contract_path,
        )
    )
    continuation = V4P01ContinuationContract.model_validate_json(
        continuation_contract_path.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=continuation.frozen_at,
        source_reviewed_at=continuation.source_reviewed_at,
        original=original,
        terminal=terminal,
        observations=metadata_observations,
        metadata_gate=original_gate,
    )
    if (
        continuation != expected
        or not audit_v4_p01_continuation_contract(continuation)
    ):
        raise EvidenceIntegrityError("V4P01 continuation lineage audit failed")
    return (
        continuation,
        original,
        terminal,
        metadata_observations,
        original_gate,
    )


def corrected_metadata_gate(
    *,
    contract: V4P01ContinuationContract,
    metadata_observations: list[V4P01SourceObservation],
) -> V4P01MetadataGateResult:
    if len(metadata_observations) != 2:
        raise EvidenceIntegrityError(
            "V4P01 continuation requires two inherited metadata observations"
        )
    for observation in metadata_observations:
        if (
            not observation.product_identity_matches
            or observation.source_available_since is None
            or observation.source_available_since > contract.development_start
            or observation.source_available_to is None
            or observation.source_available_to < contract.development_end
            or observation.symbol_available_since is None
            or observation.symbol_available_since > contract.development_start
            or (
                observation.symbol_available_to is not None
                and observation.symbol_available_to < contract.development_end
            )
        ):
            raise EvidenceIntegrityError(
                "Inherited metadata does not pass corrected V4P01 semantics"
            )
    return build_v4_p01_metadata_gate_result(
        evaluated_at=contract.frozen_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        observation_hashes=[
            item.observation_evidence_hash for item in metadata_observations
        ],
        request_ids=[item.request_id for item in metadata_observations],
        status="PASS",
        reasons=[
            (
                "Both exact products cover the development start; each optional "
                "symbol end is absent while its enclosing exchange source end "
                "covers the development period under the frozen documented "
                "Tardis semantic."
            )
        ],
        payload_phase_authorized=True,
    )


def write_or_audit_corrected_gate(
    path: Path,
    gate: V4P01MetadataGateResult,
) -> None:
    if path.exists():
        stored = V4P01MetadataGateResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if stored != gate:
            raise EvidenceIntegrityError(
                "V4P01 corrected metadata gate artifact changed"
            )
        return
    atomic_write(
        path,
        (gate.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )


def reconstruct_continuation_journal(
    contract: V4P01ContinuationContract,
    path: Path,
) -> list[V4P01JournalRecord]:
    records = load_ndjson(path, V4P01JournalRecord)
    requests = {item.request_id: item for item in contract.requests}
    open_intent: V4P01JournalRecord | None = None
    seen_intents: list[str] = []
    failure_seen = False
    for index, record in enumerate(records, start=1):
        if record.record_sequence != index:
            raise EvidenceIntegrityError(
                "V4P01 continuation journal sequence is not contiguous"
            )
        expected_previous = (
            records[index - 2].record_evidence_hash if index > 1 else None
        )
        if record.previous_record_hash != expected_previous:
            raise EvidenceIntegrityError(
                "V4P01 continuation journal hash chain is broken"
            )
        if record.contract_evidence_hash != contract.contract_evidence_hash:
            raise EvidenceIntegrityError(
                "V4P01 continuation journal contract hash changed"
            )
        request = requests.get(record.request_id)
        if request is None or record.request_sequence != request.sequence:
            raise EvidenceIntegrityError(
                "V4P01 continuation journal request identity changed"
            )
        url_hash, headers_hash = request_hashes(request)
        if (
            record.request_url_hash != url_hash
            or record.request_headers_hash != headers_hash
        ):
            raise EvidenceIntegrityError(
                "V4P01 continuation journal request binding changed"
            )
        if record.record_type == "REQUEST_INTENT":
            expected_request_id = contract.requests[len(seen_intents)].request_id
            if (
                open_intent is not None
                or failure_seen
                or record.request_id in seen_intents
                or record.request_id != expected_request_id
            ):
                raise EvidenceIntegrityError(
                    "V4P01 continuation request order or uniqueness changed"
                )
            open_intent = record
            seen_intents.append(record.request_id)
        else:
            if open_intent is None or open_intent.request_id != record.request_id:
                raise EvidenceIntegrityError(
                    "V4P01 continuation outcome has no matching intent"
                )
            failure_seen = record.record_type == "FAILURE"
            open_intent = None
    if len(seen_intents) > contract.transport_budget.continuation_attempt_budget:
        raise EvidenceIntegrityError(
            "V4P01 continuation attempt budget exceeded"
        )
    return records


def terminal_paths(
    contract: V4P01ContinuationContract,
    project_root: Path,
) -> dict[str, Path]:
    return {
        "COMPLETE": safe_project_path(
            project_root,
            contract.terminal_artifacts.complete_artifact,
        ),
        "REJECT": safe_project_path(
            project_root,
            contract.terminal_artifacts.reject_artifact,
        ),
        "TRANSPORT_STOP": safe_project_path(
            project_root,
            contract.terminal_artifacts.transport_stop_artifact,
        ),
    }


def assert_terminal_exclusivity(paths: dict[str, Path]) -> None:
    if sum(path.exists() for path in paths.values()) > 1:
        raise EvidenceIntegrityError(
            "Multiple V4P01 continuation terminal artifacts exist"
        )


def write_continuation_terminal(
    *,
    kind: str,
    contract: V4P01ContinuationContract,
    project_root: Path,
    records: list[V4P01JournalRecord],
    metadata_observations: list[V4P01SourceObservation],
    payload_observations: list[V4P01SourceObservation],
    execution_gates: list[V4P01ExecutionGateResult],
    clock,
    failure: V4P01JournalRecord | None = None,
) -> V4P01TerminalResult:
    paths = terminal_paths(contract, project_root)
    assert_terminal_exclusivity(paths)
    if any(path.exists() for path in paths.values()):
        raise EvidenceIntegrityError(
            "V4P01 continuation already has a terminal artifact"
        )
    runtime = runtime_contract(contract)
    journal_path = safe_project_path(project_root, contract.journal_path)
    gate_path = safe_project_path(
        project_root,
        contract.corrected_metadata_gate_path,
    )
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    raw_paths = list(raw_directory.glob("*")) if raw_directory.exists() else []
    resources = _resource_totals(
        contract=runtime,
        records=records,
        durable_paths=[journal_path, gate_path, payload_path, *raw_paths],
    )
    common = {
        "terminal_kind": kind,
        "terminal_timestamp": clock(),
        "builder_and_contract_hashes": {
            "continuation_contract_evidence_hash": (
                contract.contract_evidence_hash
            ),
            "continuation_builder_contract_hash": (
                contract.builder_contract_hash
            ),
            "continuation_runner_contract_hash": runner_contract_hash(),
            "original_contract_evidence_hash": (
                contract.original_contract_evidence_hash
            ),
            "original_terminal_reject_evidence_hash": (
                contract.original_terminal_reject_evidence_hash
            ),
            "original_metadata_gate_evidence_hash": (
                contract.original_metadata_gate_evidence_hash
            ),
        },
        "completed_and_failed_request_ids": {
            "completed": [
                item.request_id
                for item in records
                if item.record_type == "RESPONSE"
            ],
            "failed": [
                item.request_id
                for item in records
                if item.record_type == "FAILURE"
            ],
        },
        "decision": (
            "FEASIBILITY_FOUNDATION_COMPLETE_NO_SELECTION"
            if kind == "COMPLETE"
            else (
                "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
                if kind == "REJECT"
                else "STOP_V4P01_CONTINUATION_TRANSPORT_NO_RETRY"
            )
        ),
        "execution_gate_results": execution_gates,
        "metadata_and_payload_observation_hashes": {
            "metadata": [
                item.observation_evidence_hash
                for item in metadata_observations
            ],
            "payload": [
                item.observation_evidence_hash for item in payload_observations
            ],
        },
        "parsed_and_prohibited_field_manifest": {
            "permitted_observation_fields": (
                V4P01_PERMITTED_OBSERVATION_FIELDS
            ),
            "prohibited_parsed_fields": V4P01_PROHIBITED_PARSED_FIELDS,
        },
        "request_journal_hash": (
            file_sha256(journal_path) if journal_path.exists() else EMPTY_SHA256
        ),
        "resource_totals": resources,
        "selection_and_permission_boundary": SELECTION_PERMISSION_BOUNDARY,
    }
    if kind == "TRANSPORT_STOP":
        if failure is None:
            raise EvidenceIntegrityError(
                "V4P01 continuation transport stop lacks failure"
            )
        intent = next(
            item
            for item in reversed(records)
            if item.record_type == "REQUEST_INTENT"
            and item.request_id == failure.request_id
        )
        common.update(
            {
                "failed_request_id_and_attempt": {
                    "request_id": failure.request_id,
                    "attempt": failure.attempt,
                },
                "failure_class_and_message": {
                    "failure_class": failure.failure_class,
                    "failure_message": failure.failure_message,
                },
                "partial_byte_count_and_sha256": {
                    "byte_count": failure.byte_count,
                    "payload_sha256": failure.payload_sha256,
                },
                "request_intent_record_hash": intent.record_evidence_hash,
                "response_headers_if_received": failure.response_headers,
                "unconsumed_request_and_byte_budgets": {
                    "requests": (
                        contract.transport_budget.continuation_attempt_budget
                        - resources.attempts_used
                    ),
                    "response_bytes": (
                        contract.transport_budget.payload_response_byte_budget
                        - resources.response_bytes
                    ),
                },
                "unreconciled_intent_status": (
                    "CLOSED_BY_DURABLE_FAILURE_NO_RETRY_PERMITTED"
                ),
            }
        )
    result = build_v4_p01_terminal_result(**common)
    atomic_write(
        paths[kind],
        (result.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return result


def run_continuation(
    *,
    contract: V4P01ContinuationContract,
    metadata_observations: list[V4P01SourceObservation],
    project_root: Path,
    transport,
    clock=lambda: datetime.now(UTC),
    monotonic=time.monotonic,
) -> V4P01TerminalResult:
    paths = terminal_paths(contract, project_root)
    assert_terminal_exclusivity(paths)
    if any(path.exists() for path in paths.values()):
        raise EvidenceIntegrityError(
            "V4P01 continuation terminal exists; use --check"
        )
    runtime = runtime_contract(contract)
    gate = corrected_metadata_gate(
        contract=contract,
        metadata_observations=metadata_observations,
    )
    gate_path = safe_project_path(
        project_root,
        contract.corrected_metadata_gate_path,
    )
    write_or_audit_corrected_gate(gate_path, gate)
    journal_path = safe_project_path(project_root, contract.journal_path)
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    records = reconstruct_continuation_journal(contract, journal_path)
    payload_observations = load_ndjson(
        payload_path,
        V4P01SourceObservation,
    )
    if records and records[-1].record_type == "REQUEST_INTENT":
        failure = close_unreconciled_intent(
            contract=runtime,
            project_root=project_root,
            journal_path=journal_path,
            records=records,
            clock=clock,
        )
        return write_continuation_terminal(
            kind="TRANSPORT_STOP",
            contract=contract,
            project_root=project_root,
            records=records,
            metadata_observations=metadata_observations,
            payload_observations=payload_observations,
            execution_gates=unresolved_execution_gates(),
            clock=clock,
            failure=failure,
        )
    if raw_directory.exists() and list(raw_directory.glob("*.part")):
        raise EvidenceIntegrityError(
            "Stale continuation part file has no matching intent"
        )
    observations_by_request = {
        item.request_id: item for item in payload_observations
    }
    responses_by_request = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    failure = next(
        (item for item in records if item.record_type == "FAILURE"),
        None,
    )
    if failure is not None:
        return write_continuation_terminal(
            kind="TRANSPORT_STOP",
            contract=contract,
            project_root=project_root,
            records=records,
            metadata_observations=metadata_observations,
            payload_observations=payload_observations,
            execution_gates=unresolved_execution_gates(),
            clock=clock,
            failure=failure,
        )
    for request in contract.requests:
        response = responses_by_request.get(request.request_id)
        if response is None:
            response = execute_request(
                contract=runtime,
                request=request,
                project_root=project_root,
                journal_path=journal_path,
                records=records,
                transport=transport,
                clock=clock,
                monotonic=monotonic,
            )
            if response.record_type == "FAILURE":
                return write_continuation_terminal(
                    kind="TRANSPORT_STOP",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observations=metadata_observations,
                    payload_observations=payload_observations,
                    execution_gates=unresolved_execution_gates(),
                    clock=clock,
                    failure=response,
                )
            responses_by_request[request.request_id] = response
        observation = observations_by_request.get(request.request_id)
        if observation is None:
            try:
                observation = _observation_for_response(
                    contract=runtime,
                    request=request,
                    response=response,
                    project_root=project_root,
                    observed_at=clock(),
                )
            except Exception as exc:
                gates = unresolved_execution_gates()
                gate_index = V4P01_REQUIRED_GATE_IDS.index(
                    "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"
                )
                gates[gate_index] = V4P01ExecutionGateResult(
                    gate_id="RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
                    status="FAIL",
                    evidence_hashes=[response.payload_sha256],
                    reason=(
                        "The frozen continuation response could not be parsed "
                        f"under the non-value schema policy: "
                        f"{type(exc).__name__}: {str(exc)[:800]}"
                    ),
                )
                return write_continuation_terminal(
                    kind="REJECT",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observations=metadata_observations,
                    payload_observations=payload_observations,
                    execution_gates=gates,
                    clock=clock,
                )
            append_observation(payload_path, observation)
            payload_observations.append(observation)
            observations_by_request[request.request_id] = observation
    gates = evaluate_execution_gates(
        contract=runtime,
        metadata_gate=gate,
        observations=[*metadata_observations, *payload_observations],
    )
    kind = "COMPLETE" if all(item.status == "PASS" for item in gates) else "REJECT"
    return write_continuation_terminal(
        kind=kind,
        contract=contract,
        project_root=project_root,
        records=records,
        metadata_observations=metadata_observations,
        payload_observations=payload_observations,
        execution_gates=gates,
        clock=clock,
    )


def audit_continuation_terminal(
    *,
    contract: V4P01ContinuationContract,
    metadata_observations: list[V4P01SourceObservation],
    project_root: Path,
) -> V4P01TerminalResult:
    paths = terminal_paths(contract, project_root)
    assert_terminal_exclusivity(paths)
    existing = [path for path in paths.values() if path.exists()]
    if len(existing) != 1:
        raise EvidenceIntegrityError(
            "Exactly one continuation terminal artifact required"
        )
    result = V4P01TerminalResult.model_validate_json(
        existing[0].read_text(encoding="utf-8")
    )
    if (
        result.builder_and_contract_hashes[
            "continuation_contract_evidence_hash"
        ]
        != contract.contract_evidence_hash
        or result.builder_and_contract_hashes[
            "continuation_runner_contract_hash"
        ]
        != runner_contract_hash()
    ):
        raise EvidenceIntegrityError(
            "V4P01 continuation terminal lineage changed"
        )
    runtime = runtime_contract(contract)
    gate_path = safe_project_path(
        project_root,
        contract.corrected_metadata_gate_path,
    )
    gate = V4P01MetadataGateResult.model_validate_json(
        gate_path.read_text(encoding="utf-8")
    )
    if gate != corrected_metadata_gate(
        contract=contract,
        metadata_observations=metadata_observations,
    ):
        raise EvidenceIntegrityError(
            "V4P01 continuation corrected metadata gate changed"
        )
    journal_path = safe_project_path(project_root, contract.journal_path)
    records = reconstruct_continuation_journal(contract, journal_path)
    if result.request_journal_hash != file_sha256(journal_path):
        raise EvidenceIntegrityError(
            "V4P01 continuation journal bytes changed"
        )
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    payload_observations = load_ndjson(
        payload_path,
        V4P01SourceObservation,
    )
    if result.metadata_and_payload_observation_hashes != {
        "metadata": [
            item.observation_evidence_hash for item in metadata_observations
        ],
        "payload": [
            item.observation_evidence_hash for item in payload_observations
        ],
    }:
        raise EvidenceIntegrityError(
            "V4P01 continuation observation hash list changed"
        )
    responses = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    for observation in payload_observations:
        response = responses.get(observation.request_id)
        if (
            response is None
            or response.raw_relative_path is None
            or observation.payload_sha256 != response.payload_sha256
            or observation.byte_count != response.byte_count
        ):
            raise EvidenceIntegrityError(
                "V4P01 continuation observation binding changed"
            )
        raw_path = safe_project_path(
            project_root,
            response.raw_relative_path,
        )
        if (
            not raw_path.is_file()
            or raw_path.stat().st_size != response.byte_count
            or file_sha256(raw_path) != response.payload_sha256
        ):
            raise EvidenceIntegrityError(
                "V4P01 continuation raw response changed"
            )
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    raw_paths = list(raw_directory.glob("*")) if raw_directory.exists() else []
    expected_resources = _resource_totals(
        contract=runtime,
        records=records,
        durable_paths=[journal_path, gate_path, payload_path, *raw_paths],
    )
    if result.resource_totals != expected_resources:
        raise EvidenceIntegrityError(
            "V4P01 continuation resource totals changed"
        )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen six-request V4P01 feasibility "
            "continuation. Network requires explicit --execute."
        )
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument(
        "--original-contract",
        type=Path,
        default=DEFAULT_ORIGINAL_CONTRACT,
    )
    parser.add_argument(
        "--continuation-contract",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        (
            contract,
            _,
            _,
            metadata_observations,
            _,
        ) = load_continuation_contract(
            charter_path=args.charter,
            register_path=args.register,
            original_contract_path=args.original_contract,
            continuation_contract_path=args.continuation_contract,
        )
        if args.dry_run:
            print(
                f"V4P01 CONTINUATION DRY RUN "
                f"contract={contract.contract_evidence_hash} "
                f"requests={len(contract.requests)} metadata_repeats=0 "
                f"retries=0 values=PROHIBITED",
                flush=True,
            )
            for request in contract.requests:
                print(
                    f"{request.sequence} {request.request_id} "
                    f"{request.exchange_id}",
                    flush=True,
                )
            return 0
        if args.check:
            result = audit_continuation_terminal(
                contract=contract,
                metadata_observations=metadata_observations,
                project_root=PROJECT_ROOT,
            )
        else:
            result = run_continuation(
                contract=contract,
                metadata_observations=metadata_observations,
                project_root=PROJECT_ROOT,
                transport=HttpxTransport(),
            )
        print(
            f"V4P01 CONTINUATION {result.terminal_kind} {result.decision} "
            f"attempts={result.resource_totals.attempts_used} "
            f"bytes={result.resource_totals.response_bytes} "
            f"selected={result.selects_primary}",
            flush=True,
        )
        return 0
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
