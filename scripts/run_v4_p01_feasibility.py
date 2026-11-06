import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (  # noqa: E402
    V4P01_PERMITTED_OBSERVATION_FIELDS,
    V4P01_PROHIBITED_PARSED_FIELDS,
    V4P01_REQUIRED_GATE_IDS,
    V4P01FeasibilityContract,
    V4P01SourceRequest,
    audit_v4_p01_feasibility_contract,
)
from aurex.backtest_engine.research_v4_p01_feasibility_runner import (  # noqa: E402
    EMPTY_SHA256,
    V4P01ExecutionGateResult,
    V4P01JournalRecord,
    V4P01MetadataGateResult,
    V4P01ResourceTotals,
    V4P01SourceObservation,
    V4P01TerminalResult,
    build_v4_p01_journal_record,
    build_v4_p01_metadata_gate_result,
    build_v4_p01_source_observation,
    build_v4_p01_terminal_result,
    unresolved_execution_gates,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_p01_feasibility_contract import (  # noqa: E402
    authoritative_contract,
    load_inputs,
)

DEFAULT_CHARTER = Path(
    "data/evidence/v4_mechanism_discovery_charter_v1.json"
)
DEFAULT_REGISTER = Path(
    "data/evidence/v4_mechanism_proposal_register_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/v4_p01_feasibility_contract_v1.json"
)
RESPONSE_HEADER_NAMES = {
    "cache-control",
    "content-encoding",
    "content-length",
    "content-type",
    "date",
    "etag",
    "last-modified",
    "x-request-id",
}
SELECTION_PERMISSION_BOUNDARY = {
    "selects_primary": False,
    "authorizes_returns": False,
    "creates_candidate": False,
    "opens_validation": False,
    "opens_holdout": False,
    "opens_forward": False,
    "permits_pine_parity": False,
    "creates_paper_eligibility": False,
    "creates_sandbox_eligibility": False,
    "creates_live_eligibility": False,
}
METADATA_GATE_FILENAME = "metadata_census_gate_v1.json"


class EvidenceIntegrityError(ValueError):
    pass


@dataclass
class ResponseStream:
    status_code: int
    headers: dict[str, str]
    chunks: Iterator[bytes]


class Transport(Protocol):
    def open(
        self,
        request: V4P01SourceRequest,
    ) -> AbstractContextManager[ResponseStream]: ...


class HttpxTransport:
    @contextmanager
    def open(
        self,
        request: V4P01SourceRequest,
    ) -> Iterator[ResponseStream]:
        timeout = httpx.Timeout(
            connect=request.connect_timeout_seconds,
            read=request.read_inactivity_timeout_seconds,
            write=request.read_inactivity_timeout_seconds,
            pool=request.connect_timeout_seconds,
        )
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(
                request.method,
                request.url,
                headers=request.request_headers,
            ) as response:
                yield ResponseStream(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    chunks=response.iter_raw(chunk_size=65_536),
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
            PROJECT_ROOT / "scripts" / "run_v4_p01_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p01_feasibility_runner.py",
        ]
    )


def safe_project_path(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise EvidenceIntegrityError("V4P01 evidence path escaped project root")
    return candidate


def _fsync_parent(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise EvidenceIntegrityError(f"Stale V4P01 part file: {temporary}")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    _fsync_parent(path)


def append_durable_line(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        + "\n"
    ).encode("utf-8")
    with path.open("ab") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1_048_576):
            digest.update(chunk)
    return digest.hexdigest()


def load_contract(
    *,
    charter_path: Path,
    register_path: Path,
    contract_path: Path,
) -> V4P01FeasibilityContract:
    charter, register = load_inputs(charter_path, register_path)
    contract = V4P01FeasibilityContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
        register=register,
    )
    if contract != expected or not audit_v4_p01_feasibility_contract(contract):
        raise EvidenceIntegrityError("Frozen V4P01 lineage audit failed")
    return contract


def load_ndjson(path: Path, model_type) -> list:
    if not path.exists():
        return []
    models = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line:
            raise EvidenceIntegrityError(
                f"Blank V4P01 NDJSON line at {path}:{line_number}"
            )
        try:
            models.append(model_type.model_validate_json(line))
        except Exception as exc:
            raise EvidenceIntegrityError(
                f"Invalid V4P01 NDJSON at {path}:{line_number}"
            ) from exc
    return models


def request_hashes(request: V4P01SourceRequest) -> tuple[str, str]:
    return (
        universe_evidence_hash({"url": request.url}),
        universe_evidence_hash({"headers": request.request_headers}),
    )


def reconstruct_journal(
    contract: V4P01FeasibilityContract,
    path: Path,
) -> list[V4P01JournalRecord]:
    records = load_ndjson(path, V4P01JournalRecord)
    requests = {item.request_id: item for item in contract.requests}
    open_intent: V4P01JournalRecord | None = None
    seen_intents: set[str] = set()
    completed_sequences: list[int] = []
    failure_seen = False
    for index, record in enumerate(records, start=1):
        if record.record_sequence != index:
            raise EvidenceIntegrityError("V4P01 journal sequence is not contiguous")
        expected_previous = (
            records[index - 2].record_evidence_hash if index > 1 else None
        )
        if record.previous_record_hash != expected_previous:
            raise EvidenceIntegrityError("V4P01 journal hash chain is broken")
        if record.contract_evidence_hash != contract.contract_evidence_hash:
            raise EvidenceIntegrityError("V4P01 journal contract hash changed")
        request = requests.get(record.request_id)
        if request is None or record.request_sequence != request.sequence:
            raise EvidenceIntegrityError("V4P01 journal request identity changed")
        url_hash, headers_hash = request_hashes(request)
        if (
            record.request_url_hash != url_hash
            or record.request_headers_hash != headers_hash
        ):
            raise EvidenceIntegrityError("V4P01 journal request binding changed")
        if record.record_type == "REQUEST_INTENT":
            if (
                open_intent is not None
                or record.request_id in seen_intents
                or failure_seen
            ):
                raise EvidenceIntegrityError(
                    "Duplicate or overlapping V4P01 request intent"
                )
            expected_sequence = len(seen_intents) + 1
            if request.sequence != expected_sequence:
                raise EvidenceIntegrityError(
                    "V4P01 requests were not attempted in frozen order"
                )
            open_intent = record
            seen_intents.add(record.request_id)
        else:
            if open_intent is None or open_intent.request_id != record.request_id:
                raise EvidenceIntegrityError(
                    "V4P01 outcome has no matching request intent"
                )
            completed_sequences.append(request.sequence)
            failure_seen = record.record_type == "FAILURE"
            open_intent = None
    if len(seen_intents) > contract.transport_budget.total_attempt_budget:
        raise EvidenceIntegrityError("V4P01 attempt budget exceeded")
    if completed_sequences != sorted(completed_sequences):
        raise EvidenceIntegrityError("V4P01 journal outcome order changed")
    return records


def _response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key.lower(): str(value).strip()
        for key, value in headers.items()
        if key.lower() in RESPONSE_HEADER_NAMES
    }


def _raw_relative_path(request: V4P01SourceRequest) -> str:
    return f"{request.sequence:02d}_{request.request_id.lower()}.response"


def _active_elapsed_milliseconds(records: list[V4P01JournalRecord]) -> int:
    return sum(
        record.elapsed_milliseconds or 0
        for record in records
        if record.record_type in {"RESPONSE", "FAILURE"}
    )


def _response_bytes(records: list[V4P01JournalRecord]) -> int:
    return sum(
        record.byte_count
        for record in records
        if record.record_type in {"RESPONSE", "FAILURE"}
    )


def _storage_bytes(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.is_file())


def _append_journal(
    path: Path,
    records: list[V4P01JournalRecord],
    **values,
) -> V4P01JournalRecord:
    record = build_v4_p01_journal_record(
        record_sequence=len(records) + 1,
        previous_record_hash=(
            records[-1].record_evidence_hash if records else None
        ),
        **values,
    )
    append_durable_line(path, record.model_dump(mode="json"))
    records.append(record)
    return record


def execute_request(
    *,
    contract: V4P01FeasibilityContract,
    request: V4P01SourceRequest,
    project_root: Path,
    journal_path: Path,
    records: list[V4P01JournalRecord],
    transport: Transport,
    clock: Callable[[], datetime],
    monotonic: Callable[[], float],
) -> V4P01JournalRecord:
    if any(
        record.request_id == request.request_id
        and record.record_type == "REQUEST_INTENT"
        for record in records
    ):
        raise EvidenceIntegrityError("V4P01 request attempt already consumed")
    used_bytes = _response_bytes(records)
    used_elapsed = _active_elapsed_milliseconds(records)
    evidence_paths = [
        journal_path,
        safe_project_path(project_root, contract.metadata_observation_path),
        safe_project_path(project_root, contract.payload_observation_path),
    ]
    raw_directory = safe_project_path(project_root, contract.raw_payload_directory)
    if raw_directory.exists():
        evidence_paths.extend(raw_directory.glob("*"))
    used_storage = _storage_bytes(evidence_paths)
    if (
        used_bytes + request.maximum_response_bytes
        > contract.transport_budget.total_response_byte_budget
        or used_storage + request.maximum_response_bytes
        > contract.transport_budget.storage_budget_bytes
        or used_elapsed
        >= contract.transport_budget.protocol_wall_clock_budget_seconds * 1000
    ):
        raise EvidenceIntegrityError("V4P01 cumulative request budget unavailable")
    raw_path = raw_directory / _raw_relative_path(request)
    part_path = raw_path.with_name(f"{raw_path.name}.part")
    if raw_path.exists() or part_path.exists():
        raise EvidenceIntegrityError("Stale V4P01 raw response path exists")
    url_hash, headers_hash = request_hashes(request)
    intent = _append_journal(
        journal_path,
        records,
        record_type="REQUEST_INTENT",
        recorded_at=clock(),
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        request_url_hash=url_hash,
        request_headers_hash=headers_hash,
    )
    raw_directory.mkdir(parents=True, exist_ok=True)
    started = monotonic()
    digest = hashlib.sha256()
    byte_count = 0
    status: int | None = None
    headers: dict[str, str] = {}
    try:
        with part_path.open("xb") as handle:
            with transport.open(request) as response:
                status = response.status_code
                headers = _response_headers(response.headers)
                declared_length = headers.get("content-length")
                if (
                    declared_length is not None
                    and int(declared_length) > request.maximum_response_bytes
                ):
                    raise ValueError("response byte budget exceeded")
                for chunk in response.chunks:
                    elapsed = monotonic() - started
                    if (
                        elapsed > request.total_wall_clock_timeout_seconds
                        or used_elapsed + round(elapsed * 1000)
                        > (
                            contract.transport_budget
                            .protocol_wall_clock_budget_seconds
                            * 1000
                        )
                    ):
                        raise TimeoutError("request wall-clock budget exceeded")
                    if not chunk:
                        continue
                    byte_count += len(chunk)
                    if (
                        byte_count > request.maximum_response_bytes
                        or used_bytes + byte_count
                        > contract.transport_budget.total_response_byte_budget
                        or used_storage + byte_count
                        > contract.transport_budget.storage_budget_bytes
                    ):
                        raise ValueError("response byte budget exceeded")
                    handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                    digest.update(chunk)
            if status != 200:
                raise ValueError(f"unexpected HTTP status {status}")
            if byte_count == 0:
                raise ValueError("empty response body")
            if declared_length is not None and int(declared_length) != byte_count:
                raise ValueError("Content-Length differs from captured raw bytes")
        os.replace(part_path, raw_path)
        _fsync_parent(raw_path)
        elapsed_ms = round((monotonic() - started) * 1000)
        return _append_journal(
            journal_path,
            records,
            record_type="RESPONSE",
            recorded_at=clock(),
            contract_evidence_hash=contract.contract_evidence_hash,
            request_id=request.request_id,
            request_sequence=request.sequence,
            request_url_hash=url_hash,
            request_headers_hash=headers_hash,
            http_status=status,
            response_headers=headers,
            elapsed_milliseconds=elapsed_ms,
            byte_count=byte_count,
            payload_sha256=digest.hexdigest(),
            raw_relative_path=(
                Path(contract.raw_payload_directory)
                / _raw_relative_path(request)
            ).as_posix(),
        )
    except Exception as exc:
        elapsed_ms = round((monotonic() - started) * 1000)
        if part_path.exists():
            byte_count = part_path.stat().st_size
            partial_hash = file_sha256(part_path)
        elif raw_path.exists():
            byte_count = raw_path.stat().st_size
            partial_hash = file_sha256(raw_path)
        else:
            byte_count = 0
            partial_hash = EMPTY_SHA256
        failure = _append_journal(
            journal_path,
            records,
            record_type="FAILURE",
            recorded_at=clock(),
            contract_evidence_hash=contract.contract_evidence_hash,
            request_id=request.request_id,
            request_sequence=request.sequence,
            request_url_hash=url_hash,
            request_headers_hash=headers_hash,
            http_status=status,
            response_headers=headers,
            elapsed_milliseconds=elapsed_ms,
            byte_count=byte_count,
            payload_sha256=partial_hash,
            failure_class=type(exc).__name__,
            failure_message=str(exc)[:1200] or type(exc).__name__,
        )
        if part_path.exists():
            part_path.unlink()
        if raw_path.exists():
            raw_path.unlink()
        if failure.previous_record_hash != intent.record_evidence_hash:
            raise EvidenceIntegrityError("V4P01 failure did not close intent") from exc
        return failure


def _decode_raw_payload(path: Path, headers: dict[str, str]) -> bytes:
    payload = path.read_bytes()
    if headers.get("content-encoding", "").lower() == "gzip":
        return gzip.decompress(payload)
    return payload


def _all_schema_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_all_schema_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_all_schema_keys(item))
    return keys


def _values_for_keys(value: object, names: set[str]) -> list[object]:
    values: list[object] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in names:
                values.append(item)
            if isinstance(item, (dict, list)):
                values.extend(_values_for_keys(item, names))
    elif isinstance(value, list):
        for item in value:
            values.extend(_values_for_keys(item, names))
    return values


def _parse_timestamp(value: object) -> datetime | None:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
                UTC
            )
        except ValueError:
            try:
                value = int(text)
            except ValueError:
                return None
    if isinstance(value, (int, float)):
        magnitude = abs(float(value))
        divisor = 1.0
        if magnitude >= 1e18:
            divisor = 1e9
        elif magnitude >= 1e15:
            divisor = 1e6
        elif magnitude >= 1e12:
            divisor = 1e3
        try:
            return datetime.fromtimestamp(float(value) / divisor, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _timestamp_bounds(values: list[object]) -> tuple[datetime | None, datetime | None]:
    parsed = sorted(
        item for item in (_parse_timestamp(value) for value in values) if item
    )
    return (parsed[0], parsed[-1]) if parsed else (None, None)


def _metadata_symbol_record(
    value: object,
    product_id: str,
) -> dict | None:
    if isinstance(value, dict):
        identities = [
            value[key]
            for key in ("id", "symbol", "instrumentId", "product_id")
            if key in value and isinstance(value[key], str)
        ]
        if product_id in identities:
            return value
        for item in value.values():
            match = _metadata_symbol_record(item, product_id)
            if match is not None:
                return match
    elif isinstance(value, list):
        for item in value:
            match = _metadata_symbol_record(item, product_id)
            if match is not None:
                return match
    return None


def _metadata_channels(value: object) -> list[str]:
    found: set[str] = set()
    for item in _values_for_keys(
        value,
        {"channel", "channels", "dataTypes", "data_types", "datasets"},
    ):
        if isinstance(item, str):
            found.add(item)
        elif isinstance(item, list):
            found.update(str(entry) for entry in item if isinstance(entry, str))
        elif isinstance(item, dict):
            found.update(str(key) for key in item)
    return sorted(found)


def _metadata_revisions(value: object) -> list[str]:
    revisions: list[str] = []
    for key in (
        "checksum",
        "etag",
        "lastModified",
        "revision",
        "updatedAt",
        "version",
    ):
        for item in _values_for_keys(value, {key}):
            if isinstance(item, (str, int)):
                revisions.append(f"{key}={item}")
    return sorted(set(revisions))


def _metadata_incidents(value: object) -> list[str]:
    incidents: list[str] = []
    for item in _values_for_keys(
        value,
        {"incidentReports", "incidents", "incident_reports"},
    ):
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            allowed = {}
            for key in ("id", "type", "status", "from", "to", "start", "end"):
                if key in entry and isinstance(entry[key], (str, int)):
                    allowed[key] = entry[key]
            incidents.append(
                json.dumps(allowed, sort_keys=True, separators=(",", ":"))
            )
    return sorted(set(incidents))


def parse_metadata_observation(
    *,
    contract: V4P01FeasibilityContract,
    request: V4P01SourceRequest,
    response: V4P01JournalRecord,
    raw_path: Path,
    observed_at: datetime,
) -> V4P01SourceObservation:
    decoded = _decode_raw_payload(raw_path, response.response_headers)
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("V4P01 metadata response is not a JSON object")
    product_id = contract.venue_product_bindings[request.exchange_id]
    symbol_record = _metadata_symbol_record(payload, product_id)
    source_since, _ = _timestamp_bounds(
        _values_for_keys(payload, {"availableSince", "available_since"})
    )
    _, source_to = _timestamp_bounds(
        _values_for_keys(payload, {"availableTo", "available_to"})
    )
    symbol_since, _ = _timestamp_bounds(
        _values_for_keys(
            symbol_record or {},
            {"availableSince", "available_since"},
        )
    )
    _, symbol_to = _timestamp_bounds(
        _values_for_keys(
            symbol_record or {},
            {"availableTo", "available_to"},
        )
    )
    return build_v4_p01_source_observation(
        observation_sequence=request.sequence,
        observed_at=observed_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        phase=request.phase,
        exchange_id=request.exchange_id,
        product_identity=product_id if symbol_record is not None else None,
        product_identity_matches=symbol_record is not None,
        http_status=response.http_status,
        response_header_subset=response.response_headers,
        content_type=response.response_headers.get("content-type"),
        content_encoding=response.response_headers.get("content-encoding"),
        content_length=(
            int(response.response_headers["content-length"])
            if "content-length" in response.response_headers
            else None
        ),
        elapsed_milliseconds=response.elapsed_milliseconds,
        byte_count=response.byte_count,
        payload_sha256=response.payload_sha256,
        row_count=1,
        capture_line_count=0,
        channel_identity=_metadata_channels(symbol_record or payload),
        schema_key_presence=sorted(_all_schema_keys(payload)),
        missing_required_schema_keys={},
        local_timestamp_presence_count=0,
        exchange_timestamp_presence_count=0,
        sequence_or_update_id_presence_count=0,
        disconnect_marker_count=0,
        reconnect_snapshot_count=0,
        duplicate_local_timestamp_count=0,
        first_local_timestamp=None,
        last_local_timestamp=None,
        first_exchange_timestamp=None,
        last_exchange_timestamp=None,
        source_available_since=source_since,
        source_available_to=source_to,
        symbol_available_since=symbol_since,
        symbol_available_to=symbol_to,
        source_revision_identity=_metadata_revisions(payload),
        incident_identity_and_time_boundary=_metadata_incidents(payload),
        boundary_completeness="NOT_APPLICABLE",
    )


def _payload_channel(
    exchange_id: str,
    payload: dict,
) -> str | None:
    candidates = [
        item
        for item in _values_for_keys(
            payload,
            {"channel", "e", "event", "stream", "type"},
        )
        if isinstance(item, str)
    ]
    for candidate in candidates:
        lowered = candidate.lower()
        if exchange_id == "binance":
            if "bookticker" in lowered:
                return "bookTicker"
            if "depthsnapshot" in lowered or lowered == "snapshot":
                return "depthSnapshot"
            if "depth" in lowered:
                return "depth"
        else:
            if lowered == "l2update":
                return "l2update"
            if lowered == "snapshot":
                return "snapshot"
    return None


def _payload_product_id(payload: dict) -> str | None:
    candidates = _values_for_keys(
        payload,
        {"product_id", "productId", "s", "symbol"},
    )
    return next((item for item in candidates if isinstance(item, str)), None)


def _required_schema_keys(exchange_id: str) -> dict[str, set[str]]:
    if exchange_id == "binance":
        return {
            "bookTicker": {"A", "B", "a", "b", "s", "u"},
            "depth": {"U", "a", "b", "s", "u"},
            "depthSnapshot": {"asks", "bids", "lastUpdateId"},
        }
    return {
        "l2update": {"changes", "product_id", "time", "type"},
        "snapshot": {"asks", "bids", "product_id", "type"},
    }


def parse_payload_observation(
    *,
    contract: V4P01FeasibilityContract,
    request: V4P01SourceRequest,
    response: V4P01JournalRecord,
    raw_path: Path,
    observed_at: datetime,
) -> V4P01SourceObservation:
    decoded = _decode_raw_payload(raw_path, response.response_headers)
    lines = decoded.decode("utf-8").splitlines()
    all_keys: set[str] = set()
    channels: set[str] = set()
    channel_keys: dict[str, set[str]] = {}
    local_timestamps: list[datetime] = []
    exchange_timestamps: list[datetime] = []
    exchange_timestamp_presence_count = 0
    products: list[str] = []
    sequence_presence_count = 0
    disconnect_count = 0
    reconnect_snapshot_count = 0
    waiting_for_snapshot = False
    row_count = 0
    for line in lines:
        if not line.strip():
            continue
        timestamp_text, separator, json_text = line.partition(" ")
        if not separator:
            raise ValueError("V4P01 raw capture line lacks local timestamp")
        local_timestamp = _parse_timestamp(timestamp_text)
        if local_timestamp is None:
            raise ValueError("V4P01 raw capture local timestamp is invalid")
        message = json.loads(json_text)
        if not isinstance(message, dict):
            raise ValueError("V4P01 raw capture message is not an object")
        row_count += 1
        local_timestamps.append(local_timestamp)
        keys = _all_schema_keys(message)
        all_keys.update(keys)
        channel = _payload_channel(request.exchange_id, message)
        type_values = [
            str(item).lower()
            for item in _values_for_keys(message, {"event", "type"})
            if isinstance(item, str)
        ]
        if any(item in {"disconnect", "disconnected"} for item in type_values):
            disconnect_count += 1
            waiting_for_snapshot = True
        if channel is not None:
            channels.add(channel)
            channel_keys.setdefault(channel, set()).update(keys)
            if waiting_for_snapshot and channel in {"depthSnapshot", "snapshot"}:
                reconnect_snapshot_count += 1
                waiting_for_snapshot = False
        product = _payload_product_id(message)
        if product is not None:
            products.append(product)
        exchange_values = _values_for_keys(
            message,
            {"E", "T", "event_time", "time", "timestamp"},
        )
        row_exchange_timestamps = [
            item
            for item in (_parse_timestamp(value) for value in exchange_values)
            if item is not None
        ]
        exchange_timestamps.extend(row_exchange_timestamps)
        if row_exchange_timestamps:
            exchange_timestamp_presence_count += 1
        if _values_for_keys(
            message,
            {
                "U",
                "u",
                "lastUpdateId",
                "sequence",
                "sequence_id",
                "update_id",
            },
        ):
            sequence_presence_count += 1
    if row_count == 0:
        raise ValueError("V4P01 raw capture contains no message rows")
    expected_product = request.product_id or ""
    product_matches = bool(products) and all(
        item == expected_product for item in products
    )
    required = _required_schema_keys(request.exchange_id)
    missing = {
        channel: sorted(keys - channel_keys.get(channel, set()))
        for channel, keys in required.items()
        if keys - channel_keys.get(channel, set())
    }
    start = request.sample_at
    end = start + timedelta(minutes=1) if start is not None else None
    boundary_passes = bool(
        start is not None
        and end is not None
        and all(start <= item < end for item in local_timestamps)
    )
    unique_local = len(set(local_timestamps))
    return build_v4_p01_source_observation(
        observation_sequence=request.sequence,
        observed_at=observed_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        phase=request.phase,
        exchange_id=request.exchange_id,
        product_identity=expected_product if product_matches else None,
        product_identity_matches=product_matches,
        http_status=response.http_status,
        response_header_subset=response.response_headers,
        content_type=response.response_headers.get("content-type"),
        content_encoding=response.response_headers.get("content-encoding"),
        content_length=(
            int(response.response_headers["content-length"])
            if "content-length" in response.response_headers
            else None
        ),
        elapsed_milliseconds=response.elapsed_milliseconds,
        byte_count=response.byte_count,
        payload_sha256=response.payload_sha256,
        row_count=row_count,
        capture_line_count=row_count,
        channel_identity=sorted(channels),
        schema_key_presence=sorted(all_keys),
        missing_required_schema_keys=missing,
        local_timestamp_presence_count=len(local_timestamps),
        exchange_timestamp_presence_count=exchange_timestamp_presence_count,
        sequence_or_update_id_presence_count=sequence_presence_count,
        disconnect_marker_count=disconnect_count,
        reconnect_snapshot_count=reconnect_snapshot_count,
        duplicate_local_timestamp_count=len(local_timestamps) - unique_local,
        first_local_timestamp=min(local_timestamps),
        last_local_timestamp=max(local_timestamps),
        first_exchange_timestamp=(
            min(exchange_timestamps) if exchange_timestamps else None
        ),
        last_exchange_timestamp=(
            max(exchange_timestamps) if exchange_timestamps else None
        ),
        source_available_since=None,
        source_available_to=None,
        symbol_available_since=None,
        symbol_available_to=None,
        source_revision_identity=[
            item
            for key in ("etag", "last-modified")
            if (item := response.response_headers.get(key)) is not None
        ],
        incident_identity_and_time_boundary=[],
        boundary_completeness="PASS" if boundary_passes else "FAIL",
    )


def append_observation(path: Path, observation: V4P01SourceObservation) -> None:
    existing = load_ndjson(path, V4P01SourceObservation)
    if any(item.request_id == observation.request_id for item in existing):
        raise EvidenceIntegrityError("Duplicate V4P01 source observation")
    expected_sequence = (
        len(existing) + 1
        if observation.phase == "METADATA_CENSUS"
        else len(existing) + 3
    )
    if observation.observation_sequence != expected_sequence:
        raise EvidenceIntegrityError("V4P01 observation sequence changed")
    append_durable_line(path, observation.model_dump(mode="json"))


def evaluate_metadata_gate(
    *,
    contract: V4P01FeasibilityContract,
    observations: list[V4P01SourceObservation],
    evaluated_at: datetime,
) -> V4P01MetadataGateResult:
    if len(observations) != 2:
        raise EvidenceIntegrityError("V4P01 metadata gate requires two observations")
    reasons: list[str] = []
    for observation in observations:
        if observation.phase != "METADATA_CENSUS":
            reasons.append(f"{observation.request_id}: wrong phase")
        if observation.http_status != 200:
            reasons.append(f"{observation.request_id}: HTTP status is not 200")
        if not observation.product_identity_matches:
            reasons.append(f"{observation.request_id}: ETH/BTC product is absent")
        if (
            observation.source_available_since is None
            or observation.source_available_since > contract.development_start
        ):
            reasons.append(
                f"{observation.request_id}: source start does not cover development"
            )
        if (
            observation.source_available_to is None
            or observation.source_available_to < contract.development_end
        ):
            reasons.append(
                f"{observation.request_id}: source end does not cover development"
            )
        if (
            observation.symbol_available_since is None
            or observation.symbol_available_since > contract.development_start
        ):
            reasons.append(
                f"{observation.request_id}: product start does not cover development"
            )
        if (
            observation.symbol_available_to is None
            or observation.symbol_available_to < contract.development_end
        ):
            reasons.append(
                f"{observation.request_id}: product end does not cover development"
            )
    status = "FAIL" if reasons else "PASS"
    return build_v4_p01_metadata_gate_result(
        evaluated_at=evaluated_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        observation_hashes=[
            item.observation_evidence_hash for item in observations
        ],
        request_ids=[item.request_id for item in observations],
        status=status,
        reasons=reasons or [
            "Both exact ETH/BTC products and source date boundaries are present."
        ],
        payload_phase_authorized=status == "PASS",
    )


def write_metadata_gate(
    path: Path,
    result: V4P01MetadataGateResult,
) -> None:
    serialized = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    if path.exists():
        stored = V4P01MetadataGateResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if stored != result:
            raise EvidenceIntegrityError("V4P01 metadata gate result changed")
        return
    atomic_write(path, serialized)


def evaluate_execution_gates(
    *,
    contract: V4P01FeasibilityContract,
    metadata_gate: V4P01MetadataGateResult,
    observations: list[V4P01SourceObservation],
) -> list[V4P01ExecutionGateResult]:
    results = {
        item.gate_id: item for item in unresolved_execution_gates()
    }
    all_hashes = [item.observation_evidence_hash for item in observations]
    metadata_hash = metadata_gate.result_evidence_hash

    def set_gate(gate_id: str, status: str, reason: str, hashes: list[str]):
        results[gate_id] = V4P01ExecutionGateResult(
            gate_id=gate_id,
            status=status,
            evidence_hashes=hashes,
            reason=reason,
        )

    if metadata_gate.status == "FAIL":
        set_gate(
            "COMMON_ETH_BTC_PRODUCT_IDENTITY",
            "FAIL",
            "The frozen metadata census did not prove both exact ETH/BTC products "
            "and complete development boundaries.",
            [metadata_hash],
        )
        return [results[gate_id] for gate_id in V4P01_REQUIRED_GATE_IDS]

    payloads = [
        item for item in observations if item.phase == "PAYLOAD_SCHEMA_PILOT"
    ]
    set_gate(
        "COMMON_ETH_BTC_PRODUCT_IDENTITY",
        "PASS",
        "Both metadata records and every captured payload identify the frozen "
        "Binance ethbtc and Coinbase ETH-BTC products.",
        [metadata_hash, *all_hashes],
    )
    schema_passes = len(payloads) == 6 and all(
        item.product_identity_matches
        and not item.missing_required_schema_keys
        and set(item.channel_identity)
        == set(
            next(
                request.required_channels
                for request in contract.requests
                if request.request_id == item.request_id
            )
        )
        for item in payloads
    )
    set_gate(
        "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
        "PASS" if schema_passes else "FAIL",
        (
            "All six frozen raw pilots expose the required BBO or L2 channel "
            "identities and price/quantity key presence without parsing values."
            if schema_passes
            else "At least one frozen raw pilot did not expose every required "
            "channel and BBO/L2 price/quantity schema key."
        ),
        [item.observation_evidence_hash for item in payloads],
    )
    timestamp_passes = len(payloads) == 6 and all(
        item.boundary_completeness == "PASS"
        and item.local_timestamp_presence_count == item.row_count
        and item.exchange_timestamp_presence_count > 0
        for item in payloads
    )
    set_gate(
        "EXCHANGE_AND_LOCAL_TIMESTAMP_IDENTITY",
        "PASS" if timestamp_passes else "FAIL",
        (
            "Every frozen payload row has a bounded local timestamp and each "
            "pilot includes exchange timestamp identity."
            if timestamp_passes
            else "A frozen payload pilot lacks complete local boundary or "
            "exchange timestamp evidence."
        ),
        [item.observation_evidence_hash for item in payloads],
    )
    integrity_passes = len(payloads) == 6 and all(
        item.payload_sha256 != EMPTY_SHA256
        and bool(item.source_revision_identity)
        for item in payloads
    )
    set_gate(
        "SOURCE_REVISION_AND_BYTE_INTEGRITY",
        "PASS" if integrity_passes else "FAIL",
        (
            "Every payload has a local byte hash and an upstream ETag or "
            "Last-Modified revision identity."
            if integrity_passes
            else "Local byte hashes exist, but at least one payload lacks an "
            "upstream revision identity; source revisions cannot be bounded."
        ),
        [item.observation_evidence_hash for item in payloads],
    )
    set_gate(
        "POINT_IN_TIME_FEES_AND_FEE_CURRENCY",
        "FAIL",
        "The bounded Tardis census and raw schema pilot do not provide verified "
        "point-in-time 2023-2024 account-tier fees or fee-currency rules.",
        all_hashes,
    )
    set_gate(
        "POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE",
        "FAIL",
        "The bounded source evidence does not prove every historical filter, "
        "product status, maintenance state, or venue rule for both exchanges.",
        all_hashes,
    )
    set_gate(
        "TRANSPORT_RESOURCE_AND_STORAGE_FEASIBILITY",
        "PASS",
        "The frozen source requests completed inside the immutable attempt, byte, "
        "time, and local storage budgets.",
        all_hashes,
    )
    return [results[gate_id] for gate_id in V4P01_REQUIRED_GATE_IDS]


def _terminal_paths(
    contract: V4P01FeasibilityContract,
    project_root: Path,
) -> dict[str, Path]:
    terminal = contract.terminal_artifacts
    return {
        "COMPLETE": safe_project_path(project_root, terminal.complete_artifact),
        "REJECT": safe_project_path(project_root, terminal.reject_artifact),
        "TRANSPORT_STOP": safe_project_path(
            project_root,
            terminal.transport_stop_artifact,
        ),
    }


def _assert_terminal_exclusivity(paths: dict[str, Path]) -> None:
    existing = [kind for kind, path in paths.items() if path.exists()]
    if len(existing) > 1:
        raise EvidenceIntegrityError("Multiple V4P01 terminal artifacts exist")


def _resource_totals(
    *,
    contract: V4P01FeasibilityContract,
    records: list[V4P01JournalRecord],
    durable_paths: list[Path],
) -> V4P01ResourceTotals:
    return V4P01ResourceTotals(
        attempts_used=sum(
            item.record_type == "REQUEST_INTENT" for item in records
        ),
        responses_completed=sum(
            item.record_type == "RESPONSE" for item in records
        ),
        failures_recorded=sum(
            item.record_type == "FAILURE" for item in records
        ),
        response_bytes=_response_bytes(records),
        active_elapsed_milliseconds=_active_elapsed_milliseconds(records),
        durable_storage_bytes=_storage_bytes(durable_paths),
    )


def write_terminal_result(
    *,
    kind: str,
    contract: V4P01FeasibilityContract,
    project_root: Path,
    records: list[V4P01JournalRecord],
    metadata_observations: list[V4P01SourceObservation],
    payload_observations: list[V4P01SourceObservation],
    execution_gates: list[V4P01ExecutionGateResult],
    clock: Callable[[], datetime],
    failure: V4P01JournalRecord | None = None,
) -> V4P01TerminalResult:
    paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(paths)
    if any(path.exists() for path in paths.values()):
        raise EvidenceIntegrityError("V4P01 already has a terminal artifact")
    journal_path = safe_project_path(project_root, contract.journal_path)
    metadata_path = safe_project_path(
        project_root,
        contract.metadata_observation_path,
    )
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    gate_path = metadata_path.with_name(METADATA_GATE_FILENAME)
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    raw_paths = list(raw_directory.glob("*")) if raw_directory.exists() else []
    durable_paths = [
        journal_path,
        metadata_path,
        payload_path,
        gate_path,
        *raw_paths,
    ]
    completed = [
        item.request_id for item in records if item.record_type == "RESPONSE"
    ]
    failed = [
        item.request_id for item in records if item.record_type == "FAILURE"
    ]
    resource_totals = _resource_totals(
        contract=contract,
        records=records,
        durable_paths=durable_paths,
    )
    common = {
        "terminal_kind": kind,
        "terminal_timestamp": clock(),
        "builder_and_contract_hashes": {
            "contract_evidence_hash": contract.contract_evidence_hash,
            "contract_builder_hash": contract.builder_contract_hash,
            "runner_contract_hash": runner_contract_hash(),
            "discovery_charter_evidence_hash": (
                contract.discovery_charter_evidence_hash
            ),
            "proposal_register_evidence_hash": (
                contract.proposal_register_evidence_hash
            ),
            "proposal_evidence_hash": contract.proposal_evidence_hash,
        },
        "completed_and_failed_request_ids": {
            "completed": completed,
            "failed": failed,
        },
        "decision": (
            "FEASIBILITY_FOUNDATION_COMPLETE_NO_SELECTION"
            if kind == "COMPLETE"
            else (
                "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
                if kind == "REJECT"
                else "STOP_V4P01_TRANSPORT_NO_RETRY"
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
        "resource_totals": resource_totals,
        "selection_and_permission_boundary": SELECTION_PERMISSION_BOUNDARY,
    }
    if kind == "TRANSPORT_STOP":
        if failure is None or failure.record_type != "FAILURE":
            raise EvidenceIntegrityError("V4P01 transport stop lacks failure")
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
                        contract.transport_budget.total_attempt_budget
                        - resource_totals.attempts_used
                    ),
                    "response_bytes": (
                        contract.transport_budget.total_response_byte_budget
                        - resource_totals.response_bytes
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


def _observation_for_response(
    *,
    contract: V4P01FeasibilityContract,
    request: V4P01SourceRequest,
    response: V4P01JournalRecord,
    project_root: Path,
    observed_at: datetime,
) -> V4P01SourceObservation:
    if response.raw_relative_path is None:
        raise EvidenceIntegrityError("V4P01 response raw path is absent")
    raw_path = safe_project_path(project_root, response.raw_relative_path)
    if (
        not raw_path.is_file()
        or raw_path.stat().st_size != response.byte_count
        or file_sha256(raw_path) != response.payload_sha256
    ):
        raise EvidenceIntegrityError("V4P01 stored raw response failed audit")
    if request.phase == "METADATA_CENSUS":
        return parse_metadata_observation(
            contract=contract,
            request=request,
            response=response,
            raw_path=raw_path,
            observed_at=observed_at,
        )
    return parse_payload_observation(
        contract=contract,
        request=request,
        response=response,
        raw_path=raw_path,
        observed_at=observed_at,
    )


def close_unreconciled_intent(
    *,
    contract: V4P01FeasibilityContract,
    project_root: Path,
    journal_path: Path,
    records: list[V4P01JournalRecord],
    clock: Callable[[], datetime],
) -> V4P01JournalRecord:
    if not records or records[-1].record_type != "REQUEST_INTENT":
        raise EvidenceIntegrityError("No V4P01 intent is available to reconcile")
    intent = records[-1]
    request = next(
        item for item in contract.requests if item.request_id == intent.request_id
    )
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    raw_path = raw_directory / _raw_relative_path(request)
    part_path = raw_path.with_name(f"{raw_path.name}.part")
    evidence_path = (
        part_path if part_path.exists() else raw_path if raw_path.exists() else None
    )
    byte_count = evidence_path.stat().st_size if evidence_path else 0
    payload_sha256 = file_sha256(evidence_path) if evidence_path else EMPTY_SHA256
    url_hash, headers_hash = request_hashes(request)
    failure = _append_journal(
        journal_path,
        records,
        record_type="FAILURE",
        recorded_at=clock(),
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        request_url_hash=url_hash,
        request_headers_hash=headers_hash,
        response_headers={},
        elapsed_milliseconds=0,
        byte_count=byte_count,
        payload_sha256=payload_sha256,
        failure_class="UnreconciledRequestIntent",
        failure_message=(
            "A durable request intent had no durable outcome after restart; "
            "the frozen zero-retry contract requires a terminal transport stop."
        ),
    )
    if part_path.exists():
        part_path.unlink()
    if raw_path.exists():
        raw_path.unlink()
    return failure


def run_feasibility(
    *,
    contract: V4P01FeasibilityContract,
    project_root: Path,
    transport: Transport,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
) -> V4P01TerminalResult:
    terminal_paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(terminal_paths)
    existing_terminal = next(
        (path for path in terminal_paths.values() if path.exists()),
        None,
    )
    if existing_terminal is not None:
        raise EvidenceIntegrityError(
            "V4P01 terminal artifact exists; use --check"
        )
    journal_path = safe_project_path(project_root, contract.journal_path)
    metadata_path = safe_project_path(
        project_root,
        contract.metadata_observation_path,
    )
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    records = reconstruct_journal(contract, journal_path)
    metadata_observations = load_ndjson(
        metadata_path,
        V4P01SourceObservation,
    )
    payload_observations = load_ndjson(
        payload_path,
        V4P01SourceObservation,
    )
    if records and records[-1].record_type == "REQUEST_INTENT":
        failure = close_unreconciled_intent(
            contract=contract,
            project_root=project_root,
            journal_path=journal_path,
            records=records,
            clock=clock,
        )
        return write_terminal_result(
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
    stale_parts = (
        list(raw_directory.glob("*.part")) if raw_directory.exists() else []
    )
    if stale_parts:
        raise EvidenceIntegrityError(
            "Stale V4P01 raw part file has no matching intent"
        )
    observations_by_request = {
        item.request_id: item
        for item in [*metadata_observations, *payload_observations]
    }
    responses_by_request = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    for request_id in observations_by_request:
        if request_id not in responses_by_request:
            raise EvidenceIntegrityError(
                "V4P01 observation has no durable response"
            )
    failure = next(
        (item for item in records if item.record_type == "FAILURE"),
        None,
    )
    if failure is not None:
        return write_terminal_result(
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
    metadata_gate_path = metadata_path.with_name(METADATA_GATE_FILENAME)
    metadata_gate: V4P01MetadataGateResult | None = None
    for request in contract.requests:
        response = responses_by_request.get(request.request_id)
        if response is None:
            response = execute_request(
                contract=contract,
                request=request,
                project_root=project_root,
                journal_path=journal_path,
                records=records,
                transport=transport,
                clock=clock,
                monotonic=monotonic,
            )
            if response.record_type == "FAILURE":
                return write_terminal_result(
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
                    contract=contract,
                    request=request,
                    response=response,
                    project_root=project_root,
                    observed_at=clock(),
                )
            except Exception as exc:
                gates = unresolved_execution_gates()
                failed_gate = (
                    "COMMON_ETH_BTC_PRODUCT_IDENTITY"
                    if request.phase == "METADATA_CENSUS"
                    else "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"
                )
                gates[V4P01_REQUIRED_GATE_IDS.index(failed_gate)] = (
                    V4P01ExecutionGateResult(
                        gate_id=failed_gate,
                        status="FAIL",
                        evidence_hashes=[response.payload_sha256],
                        reason=(
                            "The frozen source response could not be parsed under "
                            f"the non-value schema policy: {type(exc).__name__}: "
                            f"{str(exc)[:800]}"
                        ),
                    )
                )
                return write_terminal_result(
                    kind="REJECT",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observations=metadata_observations,
                    payload_observations=payload_observations,
                    execution_gates=gates,
                    clock=clock,
                )
            target_path = (
                metadata_path
                if request.phase == "METADATA_CENSUS"
                else payload_path
            )
            append_observation(target_path, observation)
            observations_by_request[request.request_id] = observation
            if request.phase == "METADATA_CENSUS":
                metadata_observations.append(observation)
            else:
                payload_observations.append(observation)
        if request.sequence == 2:
            metadata_gate = evaluate_metadata_gate(
                contract=contract,
                observations=metadata_observations,
                evaluated_at=clock(),
            )
            write_metadata_gate(metadata_gate_path, metadata_gate)
            if metadata_gate.status == "FAIL":
                return write_terminal_result(
                    kind="REJECT",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observations=metadata_observations,
                    payload_observations=payload_observations,
                    execution_gates=evaluate_execution_gates(
                        contract=contract,
                        metadata_gate=metadata_gate,
                        observations=metadata_observations,
                    ),
                    clock=clock,
                )
    if metadata_gate is None:
        if not metadata_gate_path.exists():
            raise EvidenceIntegrityError("V4P01 metadata gate artifact is absent")
        metadata_gate = V4P01MetadataGateResult.model_validate_json(
            metadata_gate_path.read_text(encoding="utf-8")
        )
    gates = evaluate_execution_gates(
        contract=contract,
        metadata_gate=metadata_gate,
        observations=[*metadata_observations, *payload_observations],
    )
    kind = "COMPLETE" if all(item.status == "PASS" for item in gates) else "REJECT"
    return write_terminal_result(
        kind=kind,
        contract=contract,
        project_root=project_root,
        records=records,
        metadata_observations=metadata_observations,
        payload_observations=payload_observations,
        execution_gates=gates,
        clock=clock,
    )


def audit_terminal(
    *,
    contract: V4P01FeasibilityContract,
    project_root: Path,
) -> V4P01TerminalResult:
    paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(paths)
    existing = [path for path in paths.values() if path.exists()]
    if len(existing) != 1:
        raise EvidenceIntegrityError("Exactly one V4P01 terminal artifact required")
    result = V4P01TerminalResult.model_validate_json(
        existing[0].read_text(encoding="utf-8")
    )
    if (
        result.builder_and_contract_hashes["contract_evidence_hash"]
        != contract.contract_evidence_hash
        or result.builder_and_contract_hashes["runner_contract_hash"]
        != runner_contract_hash()
    ):
        raise EvidenceIntegrityError("V4P01 terminal lineage audit failed")
    journal_path = safe_project_path(project_root, contract.journal_path)
    records = reconstruct_journal(contract, journal_path)
    if result.request_journal_hash != file_sha256(journal_path):
        raise EvidenceIntegrityError("V4P01 terminal journal hash changed")
    completed = [
        item.request_id for item in records if item.record_type == "RESPONSE"
    ]
    failed = [
        item.request_id for item in records if item.record_type == "FAILURE"
    ]
    if result.completed_and_failed_request_ids != {
        "completed": completed,
        "failed": failed,
    }:
        raise EvidenceIntegrityError("V4P01 terminal request outcome list changed")
    metadata_path = safe_project_path(
        project_root,
        contract.metadata_observation_path,
    )
    payload_path = safe_project_path(
        project_root,
        contract.payload_observation_path,
    )
    metadata_observations = load_ndjson(
        metadata_path,
        V4P01SourceObservation,
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
        raise EvidenceIntegrityError("V4P01 terminal observation hashes changed")
    requests = {item.request_id: item for item in contract.requests}
    responses = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    for observation in [*metadata_observations, *payload_observations]:
        response = responses.get(observation.request_id)
        request = requests.get(observation.request_id)
        if (
            response is None
            or request is None
            or observation.contract_evidence_hash
            != contract.contract_evidence_hash
            or observation.payload_sha256 != response.payload_sha256
            or observation.byte_count != response.byte_count
            or observation.phase != request.phase
        ):
            raise EvidenceIntegrityError(
                "V4P01 observation-to-response binding changed"
            )
        if response.raw_relative_path is None:
            raise EvidenceIntegrityError("V4P01 response raw path is absent")
        raw_path = safe_project_path(
            project_root,
            response.raw_relative_path,
        )
        if (
            not raw_path.is_file()
            or raw_path.stat().st_size != response.byte_count
            or file_sha256(raw_path) != response.payload_sha256
        ):
            raise EvidenceIntegrityError("V4P01 raw response bytes changed")
    gate_path = metadata_path.with_name(METADATA_GATE_FILENAME)
    raw_directory = safe_project_path(
        project_root,
        contract.raw_payload_directory,
    )
    durable_paths = [
        journal_path,
        metadata_path,
        payload_path,
        gate_path,
        *(
            list(raw_directory.glob("*"))
            if raw_directory.exists()
            else []
        ),
    ]
    expected_resources = _resource_totals(
        contract=contract,
        records=records,
        durable_paths=durable_paths,
    )
    if result.resource_totals != expected_resources:
        raise EvidenceIntegrityError("V4P01 terminal resource totals changed")
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen V4P01 metadata and raw-schema feasibility "
            "protocol. Network access requires explicit --execute."
        )
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Consume the frozen zero-retry network request budget.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Audit an existing terminal result without network access.",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit lineage and print the frozen request plan without network.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(
            charter_path=args.charter,
            register_path=args.register,
            contract_path=args.contract,
        )
        if args.dry_run:
            print(
                f"V4P01 DRY RUN contract={contract.contract_evidence_hash} "
                f"requests={len(contract.requests)} retries=0 values=PROHIBITED",
                flush=True,
            )
            for request in contract.requests:
                print(
                    f"{request.sequence} {request.request_id} "
                    f"{request.phase} {request.exchange_id}",
                    flush=True,
                )
            return 0
        if args.check:
            result = audit_terminal(
                contract=contract,
                project_root=PROJECT_ROOT,
            )
        else:
            result = run_feasibility(
                contract=contract,
                project_root=PROJECT_ROOT,
                transport=HttpxTransport(),
            )
        print(
            f"V4P01 {result.terminal_kind} {result.decision} "
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
