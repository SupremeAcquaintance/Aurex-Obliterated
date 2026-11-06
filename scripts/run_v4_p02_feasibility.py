import argparse
import gzip
import hashlib
import ipaddress
import json
import os
import socket
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx  # noqa: E402

from aurex.backtest_engine.research_v4_p02_feasibility_contract import (  # noqa: E402
    V4P02_DATASET_PRODUCTS,
    V4P02_PERMITTED_OBSERVATION_FIELDS,
    V4P02_PROHIBITED_PARSED_FIELDS,
    V4P02_REQUIRED_GATE_IDS,
    V4P02FeasibilityContract,
    V4P02SourceRequest,
    audit_v4_p02_feasibility_contract,
)
from aurex.backtest_engine.research_v4_p02_feasibility_runner import (  # noqa: E402
    EMPTY_SHA256,
    V4P02DatasetStorageProjection,
    V4P02ExecutionGateResult,
    V4P02HeaderObservation,
    V4P02JournalRecord,
    V4P02MetadataGateResult,
    V4P02MetadataObservation,
    V4P02RedirectHop,
    V4P02ResourceTotals,
    V4P02StorageProjection,
    V4P02TerminalResult,
    build_v4_p02_header_observation,
    build_v4_p02_journal_record,
    build_v4_p02_metadata_gate_result,
    build_v4_p02_metadata_observation,
    build_v4_p02_terminal_result,
    unresolved_execution_gates,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_v4_p02_feasibility_contract import (  # noqa: E402
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
    "data/evidence/v4_p02_feasibility_contract_v1.json"
)
METADATA_GATE_FILENAME = "metadata_gate_v1.json"
RAW_METADATA_FILENAME = "metadata_response_v1.body"
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RESPONSE_HEADER_NAMES = {
    "cache-control",
    "content-disposition",
    "content-encoding",
    "content-length",
    "content-md5",
    "content-type",
    "date",
    "etag",
    "last-modified",
    "location",
    "x-amz-version-id",
    "x-goog-generation",
    "x-md5",
    "x-request-id",
}
SELECTION_PERMISSION_BOUNDARY = {
    "selects_primary": False,
    "authorizes_dataset_payload_gets": False,
    "authorizes_raw_replay_requests": False,
    "authorizes_deribit_api_requests": False,
    "authorizes_returns": False,
    "creates_candidate": False,
    "opens_validation": False,
    "opens_holdout": False,
    "opens_forward": False,
    "creates_paper_eligibility": False,
    "creates_sandbox_eligibility": False,
    "creates_live_eligibility": False,
}


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
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
    ) -> AbstractContextManager[ResponseStream]: ...


class HttpxTransport:
    @contextmanager
    def open(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
    ) -> Iterator[ResponseStream]:
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        with httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            with client.stream(method, url, headers=headers) as response:
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
            PROJECT_ROOT / "scripts" / "run_v4_p02_feasibility.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v4_p02_feasibility_runner.py",
        ]
    )


def safe_project_path(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise EvidenceIntegrityError("V4P02 evidence path escaped project root")
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
        raise EvidenceIntegrityError(f"Stale V4P02 part file: {temporary}")
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
) -> V4P02FeasibilityContract:
    charter, register = load_inputs(charter_path, register_path)
    contract = V4P02FeasibilityContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    expected = authoritative_contract(
        frozen_at=contract.frozen_at,
        charter=charter,
        register=register,
    )
    if contract != expected or not audit_v4_p02_feasibility_contract(contract):
        raise EvidenceIntegrityError("Frozen V4P02 lineage audit failed")
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
                f"Blank V4P02 NDJSON line at {path}:{line_number}"
            )
        try:
            models.append(model_type.model_validate_json(line))
        except Exception as exc:
            raise EvidenceIntegrityError(
                f"Invalid V4P02 NDJSON at {path}:{line_number}"
            ) from exc
    return models


def request_hashes(request: V4P02SourceRequest) -> tuple[str, str]:
    return (
        universe_evidence_hash({"url": request.url}),
        universe_evidence_hash({"headers": request.request_headers}),
    )


def _response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key.lower(): str(value).strip()
        for key, value in headers.items()
        if key.lower() in RESPONSE_HEADER_NAMES
    }


def _url_hash(url: str) -> str:
    return universe_evidence_hash({"url": url})


def _public_ip(address: str) -> bool:
    return ipaddress.ip_address(address).is_global


def validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme.lower() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
    ):
        raise ValueError(
            "redirect/request target must be public HTTPS without credentials"
        )
    if parsed.port not in {None, 443}:
        raise ValueError("redirect/request target uses a non-HTTPS port")
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                443,
                type=socket.SOCK_STREAM,
            )
        }
        if not addresses or any(not _public_ip(item) for item in addresses):
            raise ValueError(
                "redirect/request DNS includes a nonpublic address"
            ) from None
    else:
        if not _public_ip(str(literal)):
            raise ValueError("redirect/request target IP is not public")


def reconstruct_journal(
    contract: V4P02FeasibilityContract,
    path: Path,
) -> list[V4P02JournalRecord]:
    records = load_ndjson(path, V4P02JournalRecord)
    requests = {item.request_id: item for item in contract.requests}
    open_intent: V4P02JournalRecord | None = None
    seen_intents: set[str] = set()
    failure_seen = False
    for index, record in enumerate(records, start=1):
        if record.record_sequence != index:
            raise EvidenceIntegrityError("V4P02 journal sequence is not contiguous")
        expected_previous = (
            records[index - 2].record_evidence_hash if index > 1 else None
        )
        if record.previous_record_hash != expected_previous:
            raise EvidenceIntegrityError("V4P02 journal hash chain is broken")
        if record.contract_evidence_hash != contract.contract_evidence_hash:
            raise EvidenceIntegrityError("V4P02 journal contract hash changed")
        request = requests.get(record.request_id)
        if (
            request is None
            or record.request_sequence != request.sequence
            or record.request_method != request.method
        ):
            raise EvidenceIntegrityError("V4P02 journal request identity changed")
        url_hash, headers_hash = request_hashes(request)
        if (
            record.initial_url_hash != url_hash
            or record.request_headers_hash != headers_hash
        ):
            raise EvidenceIntegrityError("V4P02 journal request binding changed")
        if len(record.redirect_chain) > request.maximum_redirects:
            raise EvidenceIntegrityError("V4P02 journal redirect budget exceeded")
        if record.record_type == "REQUEST_INTENT":
            if (
                open_intent is not None
                or record.request_id in seen_intents
                or failure_seen
                or request.sequence != len(seen_intents) + 1
            ):
                raise EvidenceIntegrityError(
                    "Duplicate, overlapping, or out-of-order V4P02 intent"
                )
            open_intent = record
            seen_intents.add(record.request_id)
        else:
            if open_intent is None or open_intent.request_id != record.request_id:
                raise EvidenceIntegrityError(
                    "V4P02 outcome has no matching request intent"
                )
            failure_seen = record.record_type == "FAILURE"
            open_intent = None
    if len(seen_intents) > contract.transport_budget.total_attempt_budget:
        raise EvidenceIntegrityError("V4P02 attempt budget exceeded")
    if (
        sum(item.http_hop_count for item in records)
        > contract.transport_budget.total_http_hop_budget
    ):
        raise EvidenceIntegrityError("V4P02 HTTP hop budget exceeded")
    return records


def _append_journal(
    path: Path,
    records: list[V4P02JournalRecord],
    **values,
) -> V4P02JournalRecord:
    record = build_v4_p02_journal_record(
        record_sequence=len(records) + 1,
        previous_record_hash=(
            records[-1].record_evidence_hash if records else None
        ),
        **values,
    )
    append_durable_line(path, record.model_dump(mode="json"))
    records.append(record)
    return record


def _active_elapsed_milliseconds(
    records: list[V4P02JournalRecord],
) -> int:
    return sum(
        item.elapsed_milliseconds or 0
        for item in records
        if item.record_type in {"RESPONSE", "FAILURE"}
    )


def _response_body_bytes(records: list[V4P02JournalRecord]) -> int:
    return sum(
        item.byte_count
        for item in records
        if item.record_type in {"RESPONSE", "FAILURE"}
    )


def _http_hops(records: list[V4P02JournalRecord]) -> int:
    return sum(
        item.http_hop_count
        for item in records
        if item.record_type in {"RESPONSE", "FAILURE"}
    )


def _storage_bytes(paths: list[Path]) -> int:
    return sum(path.stat().st_size for path in paths if path.is_file())


def _census_directory(
    contract: V4P02FeasibilityContract,
    project_root: Path,
) -> Path:
    return safe_project_path(
        project_root,
        str(Path(contract.journal_path).parent),
    )


def _raw_metadata_path(
    contract: V4P02FeasibilityContract,
    project_root: Path,
) -> Path:
    return _census_directory(contract, project_root) / RAW_METADATA_FILENAME


def execute_request(
    *,
    contract: V4P02FeasibilityContract,
    request: V4P02SourceRequest,
    project_root: Path,
    journal_path: Path,
    records: list[V4P02JournalRecord],
    transport: Transport,
    host_validator: Callable[[str], None],
    clock: Callable[[], datetime],
    monotonic: Callable[[], float],
) -> V4P02JournalRecord:
    if any(
        item.record_type == "REQUEST_INTENT"
        and item.request_id == request.request_id
        for item in records
    ):
        raise EvidenceIntegrityError("V4P02 request attempt already consumed")
    used_bytes = _response_body_bytes(records)
    used_elapsed = _active_elapsed_milliseconds(records)
    used_hops = _http_hops(records)
    census_directory = _census_directory(contract, project_root)
    durable_paths = (
        list(census_directory.glob("*")) if census_directory.exists() else []
    )
    used_storage = _storage_bytes(durable_paths)
    if (
        used_bytes + request.maximum_response_body_bytes
        > contract.transport_budget.total_response_body_byte_budget
        or used_storage + request.maximum_response_body_bytes
        > contract.transport_budget.evidence_storage_budget_bytes
        or used_elapsed
        >= contract.transport_budget.protocol_wall_clock_budget_seconds * 1000
        or used_hops >= contract.transport_budget.total_http_hop_budget
    ):
        raise EvidenceIntegrityError("V4P02 cumulative request budget unavailable")
    raw_path = _raw_metadata_path(contract, project_root)
    part_path = raw_path.with_name(f"{raw_path.name}.part")
    if request.method == "GET" and (raw_path.exists() or part_path.exists()):
        raise EvidenceIntegrityError("Stale V4P02 metadata response path exists")
    url_hash, headers_hash = request_hashes(request)
    intent = _append_journal(
        journal_path,
        records,
        record_type="REQUEST_INTENT",
        recorded_at=clock(),
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        request_method=request.method,
        initial_url_hash=url_hash,
        request_headers_hash=headers_hash,
    )

    started = monotonic()
    current_url = request.url
    redirect_chain: list[V4P02RedirectHop] = []
    latest_headers: dict[str, str] = {}
    status: int | None = None
    byte_count = 0
    digest = hashlib.sha256()
    hop_count = 0
    raw_handle = None
    try:
        if request.method == "GET":
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_handle = part_path.open("xb")
        while True:
            elapsed = monotonic() - started
            if (
                elapsed > request.total_wall_clock_timeout_seconds
                or used_elapsed + round(elapsed * 1000)
                > (
                    contract.transport_budget.protocol_wall_clock_budget_seconds
                    * 1000
                )
            ):
                raise TimeoutError("V4P02 logical request timeout exceeded")
            if hop_count >= request.maximum_redirects + 1:
                raise ValueError("V4P02 redirect budget exceeded")
            if (
                used_hops + hop_count + 1
                > contract.transport_budget.total_http_hop_budget
            ):
                raise ValueError("V4P02 HTTP hop budget exceeded")
            host_validator(current_url)
            hop_count += 1
            with transport.open(
                method=request.method,
                url=current_url,
                headers=request.request_headers,
                connect_timeout_seconds=request.connect_timeout_seconds,
                read_timeout_seconds=request.read_inactivity_timeout_seconds,
            ) as response:
                status = response.status_code
                latest_headers = _response_headers(response.headers)
                declared = latest_headers.get("content-length")
                if request.method == "GET" and declared is not None:
                    try:
                        declared_length = int(declared)
                    except ValueError as exc:
                        raise ValueError(
                            "V4P02 metadata Content-Length is invalid"
                        ) from exc
                    if declared_length > request.maximum_response_body_bytes:
                        raise ValueError(
                            "V4P02 metadata body budget exceeded"
                        )
                hop_bytes = 0
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
                        raise TimeoutError(
                            "V4P02 logical request timeout exceeded"
                        )
                    if not chunk:
                        continue
                    hop_bytes += len(chunk)
                    byte_count += len(chunk)
                    if request.method == "HEAD":
                        raise ValueError("V4P02 HEAD response contained body bytes")
                    if (
                        byte_count > request.maximum_response_body_bytes
                        or used_bytes + byte_count
                        > (
                            contract.transport_budget
                            .total_response_body_byte_budget
                        )
                        or used_storage + byte_count
                        > contract.transport_budget.evidence_storage_budget_bytes
                    ):
                        raise ValueError("V4P02 metadata body budget exceeded")
                    raw_handle.write(chunk)
                    raw_handle.flush()
                    os.fsync(raw_handle.fileno())
                    digest.update(chunk)
            if status in REDIRECT_STATUSES:
                if request.method != "HEAD" or not request.redirects_permitted:
                    raise ValueError("V4P02 request received a forbidden redirect")
                if hop_bytes:
                    raise ValueError("V4P02 redirect response contained body bytes")
                location = latest_headers.get("location")
                if not location:
                    raise ValueError("V4P02 redirect lacks Location")
                target = urljoin(current_url, location)
                host_validator(target)
                redirect_chain.append(
                    V4P02RedirectHop(
                        hop_sequence=len(redirect_chain) + 1,
                        request_url=current_url,
                        http_status=status,
                        location=location,
                        resolved_target_url=target,
                        response_header_subset=latest_headers,
                    )
                )
                current_url = target
                continue
            if status != 200:
                raise ValueError(f"unexpected HTTP status {status}")
            break
        elapsed_ms = round((monotonic() - started) * 1000)
        if request.method == "GET":
            if byte_count == 0:
                raise ValueError("V4P02 metadata response body is empty")
            declared = latest_headers.get("content-length")
            if declared is not None:
                try:
                    declared_length = int(declared)
                except ValueError as exc:
                    raise ValueError(
                        "V4P02 metadata Content-Length is invalid"
                    ) from exc
                if declared_length != byte_count:
                    raise ValueError(
                        "V4P02 metadata Content-Length differs from raw bytes"
                    )
            raw_handle.close()
            raw_handle = None
            os.replace(part_path, raw_path)
            _fsync_parent(raw_path)
            payload_hash = digest.hexdigest()
            raw_relative_path = raw_path.relative_to(project_root).as_posix()
        else:
            payload_hash = EMPTY_SHA256
            raw_relative_path = None
        response_record = _append_journal(
            journal_path,
            records,
            record_type="RESPONSE",
            recorded_at=clock(),
            contract_evidence_hash=contract.contract_evidence_hash,
            request_id=request.request_id,
            request_sequence=request.sequence,
            request_method=request.method,
            initial_url_hash=url_hash,
            request_headers_hash=headers_hash,
            redirect_chain=redirect_chain,
            final_url_hash=_url_hash(current_url),
            final_host=urlparse(current_url).hostname,
            http_status=status,
            response_headers=latest_headers,
            elapsed_milliseconds=elapsed_ms,
            http_hop_count=hop_count,
            byte_count=byte_count,
            payload_sha256=payload_hash,
            raw_relative_path=raw_relative_path,
        )
        if response_record.previous_record_hash != intent.record_evidence_hash:
            raise EvidenceIntegrityError("V4P02 response did not close intent")
        return response_record
    except Exception as exc:
        elapsed_ms = round((monotonic() - started) * 1000)
        if raw_handle is not None:
            raw_handle.close()
        if part_path.exists():
            byte_count = part_path.stat().st_size
            partial_hash = file_sha256(part_path)
        elif raw_path.exists() and request.method == "GET":
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
            request_method=request.method,
            initial_url_hash=url_hash,
            request_headers_hash=headers_hash,
            redirect_chain=redirect_chain,
            final_url_hash=_url_hash(current_url),
            final_host=urlparse(current_url).hostname,
            http_status=status,
            response_headers=latest_headers,
            elapsed_milliseconds=elapsed_ms,
            http_hop_count=hop_count,
            byte_count=byte_count,
            payload_sha256=partial_hash,
            failure_class=type(exc).__name__,
            failure_message=str(exc)[:1200] or type(exc).__name__,
        )
        if part_path.exists():
            part_path.unlink()
        if raw_path.exists() and request.method == "GET":
            raw_path.unlink()
        if failure.previous_record_hash != intent.record_evidence_hash:
            raise EvidenceIntegrityError("V4P02 failure did not close intent") from exc
        return failure


def _decode_metadata(path: Path, headers: dict[str, str]) -> bytes:
    payload = path.read_bytes()
    if headers.get("content-encoding", "").lower() == "gzip":
        return gzip.decompress(payload)
    return payload


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
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
            UTC
        )
    except ValueError:
        return None


def _first_timestamp(value: object, names: set[str]) -> datetime | None:
    for candidate in _values_for_keys(value, names):
        parsed = _parse_timestamp(candidate)
        if parsed is not None:
            return parsed
    return None


def _direct_timestamp(value: dict, names: tuple[str, ...]) -> datetime | None:
    for name in names:
        parsed = _parse_timestamp(value.get(name))
        if parsed is not None:
            return parsed
    return None


def _identity_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        return [str(key) for key in value]
    return []


def _available_channels(value: object) -> list[str]:
    channels: set[str] = set()
    for item in _values_for_keys(
        value,
        {"availableChannels", "available_channels", "channels"},
    ):
        if isinstance(item, list):
            for entry in item:
                if isinstance(entry, str):
                    channels.add(entry)
                elif isinstance(entry, dict):
                    for key in ("id", "name", "channel", "dataType"):
                        identity = entry.get(key)
                        if isinstance(identity, str):
                            channels.add(identity)
        else:
            channels.update(_identity_strings(item))
    return sorted(channels)


def _record_with_identity(value: object, identity: str) -> dict | None:
    if isinstance(value, dict):
        identities = [
            value[key]
            for key in (
                "id",
                "symbol",
                "instrument",
                "instrumentId",
                "instrument_id",
            )
            if key in value and isinstance(value[key], str)
        ]
        if identity in identities:
            return value
        for item in value.values():
            found = _record_with_identity(item, identity)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _record_with_identity(item, identity)
            if found is not None:
                return found
    return None


def _data_types(value: object) -> list[str]:
    types: set[str] = set()
    for item in _values_for_keys(
        value,
        {"dataTypes", "data_types", "datasetTypes", "dataset_types"},
    ):
        types.update(_identity_strings(item))
    return sorted(types)


def _incident_identities(value: object) -> list[str]:
    incidents: set[str] = set()
    for item in _values_for_keys(
        value,
        {"incidentReports", "incident_reports", "incidents"},
    ):
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            identity = {
                key: entry[key]
                for key in (
                    "id",
                    "type",
                    "status",
                    "from",
                    "to",
                    "start",
                    "end",
                )
                if key in entry and isinstance(entry[key], str)
            }
            incidents.add(
                json.dumps(identity, sort_keys=True, separators=(",", ":"))
            )
    return sorted(incidents)


def _source_revision_identity(
    headers: dict[str, str],
    payload_sha256: str,
) -> list[str]:
    identities = []
    if payload_sha256 != EMPTY_SHA256:
        identities.append(f"payload_sha256={payload_sha256}")
    for key in (
        "etag",
        "last-modified",
        "content-md5",
        "x-md5",
        "x-amz-version-id",
        "x-goog-generation",
    ):
        if value := headers.get(key):
            identities.append(f"{key}={value}")
    return sorted(identities)


def parse_metadata_observation(
    *,
    contract: V4P02FeasibilityContract,
    request: V4P02SourceRequest,
    response: V4P02JournalRecord,
    raw_path: Path,
    observed_at: datetime,
) -> V4P02MetadataObservation:
    decoded = _decode_metadata(raw_path, response.response_headers)
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise ValueError("V4P02 metadata response is not a JSON object")
    exchange_id = next(
        (
            item
            for key in ("id", "exchange", "exchangeId", "exchange_id")
            if isinstance((item := payload.get(key)), str)
        ),
        None,
    )
    datasets = payload.get("datasets")
    dataset_scope = datasets if isinstance(datasets, (dict, list)) else payload
    global_types = _data_types(dataset_scope)
    symbol_data_types: dict[str, list[str]] = {}
    symbol_boundaries: dict[str, dict[str, datetime | None]] = {}
    for symbol in ("BTC-PERPETUAL", "OPTIONS"):
        record = _record_with_identity(dataset_scope, symbol)
        if record is None:
            continue
        symbol_data_types[symbol] = _data_types(record) or global_types
        symbol_boundaries[symbol] = {
            "available_since": _first_timestamp(
                record,
                {"availableSince", "available_since"},
            ),
            "available_to": _first_timestamp(
                record,
                {"availableTo", "available_to"},
            ),
        }
    exported_until = _first_timestamp(
        dataset_scope,
        {"exportedUntil", "exported_until"},
    )
    return build_v4_p02_metadata_observation(
        observed_at=observed_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        exchange_id=exchange_id,
        http_status=response.http_status,
        response_header_subset=response.response_headers,
        elapsed_milliseconds=response.elapsed_milliseconds,
        byte_count=response.byte_count,
        payload_sha256=response.payload_sha256,
        exchange_available_since=_direct_timestamp(
            payload,
            ("availableSince", "available_since"),
        ),
        exchange_available_to=_direct_timestamp(
            payload,
            ("availableTo", "available_to"),
        ),
        available_channel_identity=_available_channels(payload),
        dataset_exported_until=exported_until,
        dataset_symbol_data_types=symbol_data_types,
        symbol_available_since_and_to=symbol_boundaries,
        incident_identity_and_time_boundary=_incident_identities(payload),
        source_revision_identity=_source_revision_identity(
            response.response_headers,
            response.payload_sha256,
        ),
    )


def write_metadata_observation(
    path: Path,
    observation: V4P02MetadataObservation,
) -> None:
    serialized = (observation.model_dump_json(indent=2) + "\n").encode("utf-8")
    if path.exists():
        existing = V4P02MetadataObservation.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if existing != observation:
            raise EvidenceIntegrityError("V4P02 metadata observation changed")
        return
    atomic_write(path, serialized)


def evaluate_metadata_gate(
    *,
    contract: V4P02FeasibilityContract,
    observation: V4P02MetadataObservation,
    evaluated_at: datetime,
) -> V4P02MetadataGateResult:
    reasons: list[str] = []
    if observation.exchange_id != "deribit":
        reasons.append("Metadata does not identify the Deribit exchange.")
    if (
        observation.exchange_available_since is None
        or observation.exchange_available_since > contract.development_start
    ):
        reasons.append("Exchange availability does not begin by 2023-01-01.")
    if (
        observation.exchange_available_to is not None
        and observation.exchange_available_to < contract.development_end
    ):
        reasons.append("Exchange availability ended before 2025-01-01.")
    if (
        observation.dataset_exported_until is None
        or observation.dataset_exported_until < contract.development_end
    ):
        reasons.append("Dataset export boundary does not cover 2023-2024.")
    required_by_symbol: dict[str, set[str]] = {
        symbol: {
            data_type
            for data_type, product_symbol, _role in V4P02_DATASET_PRODUCTS
            if product_symbol == symbol
        }
        for symbol in ("BTC-PERPETUAL", "OPTIONS")
    }
    for symbol, required_types in required_by_symbol.items():
        actual_types = set(
            observation.dataset_symbol_data_types.get(symbol, [])
        )
        if not required_types.issubset(actual_types):
            reasons.append(
                f"{symbol} metadata lacks frozen dataset types: "
                f"{','.join(sorted(required_types - actual_types)) or 'symbol'}."
            )
        boundaries = observation.symbol_available_since_and_to.get(symbol)
        if (
            boundaries is None
            or boundaries["available_since"] is None
            or boundaries["available_since"] > contract.development_start
        ):
            reasons.append(
                f"{symbol} availability does not begin by 2023-01-01."
            )
        elif (
            boundaries["available_to"] is not None
            and boundaries["available_to"] < contract.development_end
        ):
            reasons.append(f"{symbol} availability ended before 2025-01-01.")
    status = "FAIL" if reasons else "PASS"
    return build_v4_p02_metadata_gate_result(
        evaluated_at=evaluated_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        metadata_observation_hash=observation.observation_evidence_hash,
        status=status,
        reasons=reasons
        or [
            "Deribit metadata exposes the exact grouped option and hedge "
            "dataset matrix with development-period source boundaries."
        ],
        dataset_header_phase_authorized=status == "PASS",
    )


def write_metadata_gate(path: Path, gate: V4P02MetadataGateResult) -> None:
    serialized = (gate.model_dump_json(indent=2) + "\n").encode("utf-8")
    if path.exists():
        existing = V4P02MetadataGateResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if existing != gate:
            raise EvidenceIntegrityError("V4P02 metadata gate changed")
        return
    atomic_write(path, serialized)


def parse_header_observation(
    *,
    contract: V4P02FeasibilityContract,
    request: V4P02SourceRequest,
    response: V4P02JournalRecord,
    observed_at: datetime,
) -> V4P02HeaderObservation:
    declared = response.response_headers.get("content-length")
    try:
        content_length = int(declared) if declared is not None else None
    except ValueError:
        content_length = None
    revisions = _source_revision_identity(
        response.response_headers,
        response.payload_sha256,
    )
    return build_v4_p02_header_observation(
        observation_sequence=request.sequence - 1,
        observed_at=observed_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        dataset_data_type=request.dataset_data_type,
        dataset_symbol=request.dataset_symbol,
        dataset_role=request.dataset_role,
        sample_date=request.sample_date,
        redirect_chain=response.redirect_chain,
        final_url_hash=response.final_url_hash,
        final_host=response.final_host,
        http_status=response.http_status,
        response_header_subset=response.response_headers,
        content_type=response.response_headers.get("content-type"),
        content_encoding=response.response_headers.get("content-encoding"),
        content_length=content_length,
        source_revision_identity=revisions,
        elapsed_milliseconds=response.elapsed_milliseconds,
    )


def append_header_observation(
    path: Path,
    observation: V4P02HeaderObservation,
) -> None:
    existing = load_ndjson(path, V4P02HeaderObservation)
    if any(item.request_id == observation.request_id for item in existing):
        raise EvidenceIntegrityError("Duplicate V4P02 header observation")
    if observation.observation_sequence != len(existing) + 1:
        raise EvidenceIntegrityError("V4P02 header observation order changed")
    append_durable_line(path, observation.model_dump(mode="json"))


def build_storage_projection(
    observations: list[V4P02HeaderObservation],
) -> V4P02StorageProjection | None:
    by_product: dict[tuple[str, str], list[V4P02HeaderObservation]] = {}
    for observation in observations:
        by_product.setdefault(
            (observation.dataset_data_type, observation.dataset_symbol),
            [],
        ).append(observation)
    products: list[V4P02DatasetStorageProjection] = []
    for data_type, symbol, _role in V4P02_DATASET_PRODUCTS:
        items = sorted(
            by_product.get((data_type, symbol), []),
            key=lambda item: item.sample_date,
        )
        if (
            len(items) != 3
            or any(
                item.content_length is None or item.content_length <= 0
                for item in items
            )
        ):
            return None
        lengths = [int(item.content_length) for item in items]
        average = round(sum(lengths) / 3)
        products.append(
            V4P02DatasetStorageProjection(
                data_type=data_type,
                dataset_symbol=symbol,
                sample_content_lengths=lengths,
                average_daily_bytes=average,
                projected_storage_bytes=average * 731,
            )
        )
    total = sum(item.projected_storage_bytes for item in products)
    return V4P02StorageProjection(
        products=products,
        total_projected_storage_bytes=total,
        status="PASS" if total <= 2_199_023_255_552 else "FAIL",
    )


def evaluate_execution_gates(
    *,
    metadata_gate: V4P02MetadataGateResult,
    metadata_observation: V4P02MetadataObservation,
    header_observations: list[V4P02HeaderObservation],
    projection: V4P02StorageProjection | None,
) -> list[V4P02ExecutionGateResult]:
    results = {
        item.gate_id: item for item in unresolved_execution_gates()
    }
    metadata_hash = metadata_observation.observation_evidence_hash
    header_hashes = [
        item.observation_evidence_hash for item in header_observations
    ]
    all_hashes = [metadata_hash, *header_hashes]

    def set_gate(
        gate_id: str,
        status: str,
        reason: str,
        evidence_hashes: list[str],
    ) -> None:
        results[gate_id] = V4P02ExecutionGateResult(
            gate_id=gate_id,
            status=status,
            evidence_hashes=evidence_hashes,
            reason=reason,
        )

    matrix_pass = (
        metadata_gate.status == "PASS"
        and len(header_observations) == 27
        and all(
            item.http_status == 200
            and item.body_byte_count == 0
            and item.content_length is not None
            and item.content_length > 0
            for item in header_observations
        )
    )
    set_gate(
        "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE",
        "PASS" if matrix_pass else "FAIL",
        (
            "Deribit metadata and all 27 zero-body HEAD observations bind the "
            "frozen OPTIONS and BTC-PERPETUAL dataset matrix with nonzero "
            "Content-Length identities."
            if matrix_pass
            else "The frozen metadata and 27-header census did not prove every "
            "required OPTIONS and BTC-PERPETUAL dataset identity with a nonzero "
            "Content-Length."
        ),
        [metadata_gate.result_evidence_hash, *all_hashes],
    )
    set_gate(
        "ARCHIVE_CALENDAR_INCIDENT_AND_EXPORT_COVERAGE",
        "FAIL",
        "Three first-of-month probes cannot prove the predeclared 95 percent "
        "daily and 90 percent monthly calendar coverage or bound every missing "
        "day and incident across 2023-2024.",
        all_hashes,
    )
    set_gate(
        "DISCONNECT_SEQUENCE_AND_SOURCE_REVISION_INTEGRITY",
        "FAIL",
        "The downloadable CSV census omits disconnect events and no payload was "
        "authorized, so sequence recovery, fresh post-reconnect snapshots, gzip "
        "integrity, and complete upstream revision binding remain unproven.",
        all_hashes,
    )
    set_gate(
        "POINT_IN_TIME_CONTRACT_EXPIRY_AND_SETTLEMENT_RULES",
        "FAIL",
        "Public metadata and HEAD responses do not establish dated 2023-2024 "
        "contract, expiry, exercise, delivery-price, index, or settlement rules.",
        all_hashes,
    )
    set_gate(
        "POINT_IN_TIME_FEES_CAPS_AND_DELIVERY_FEES",
        "FAIL",
        "Public metadata and HEAD responses do not establish dated 2023-2024 "
        "option and hedge fees, option caps, delivery or liquidation fees, "
        "account tier, or fee currency.",
        all_hashes,
    )
    set_gate(
        "POINT_IN_TIME_MARGIN_LIQUIDATION_AND_ACCOUNT_MODE",
        "FAIL",
        "Public metadata and HEAD responses do not establish dated 2023-2024 "
        "margin, collateral, liquidation, insurance, or account-mode rules.",
        all_hashes,
    )
    if projection is None:
        transport_reason = (
            "At least one dataset HEAD lacks a positive reconstructable "
            "Content-Length, so the frozen storage projection cannot be built; "
            "commercial entitlement and payload transport also remain unapproved."
        )
    elif projection.status == "FAIL":
        transport_reason = (
            "The deterministic 731-day storage projection exceeds the frozen "
            "2 TiB ceiling, and no commercial payload plan is approved."
        )
    else:
        transport_reason = (
            "The bounded census fits the storage ceiling, but subscription "
            "entitlement, transfer, checksum, storage, and replay operations are "
            "not approved; this complete gate therefore remains failed."
        )
    set_gate(
        "TRANSPORT_STORAGE_COMMERCIAL_AND_RESOURCE_FEASIBILITY",
        "FAIL",
        transport_reason,
        all_hashes,
    )
    return [results[gate_id] for gate_id in V4P02_REQUIRED_GATE_IDS]


def _terminal_paths(
    contract: V4P02FeasibilityContract,
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
        raise EvidenceIntegrityError("Multiple V4P02 terminal artifacts exist")


def _durable_paths(
    contract: V4P02FeasibilityContract,
    project_root: Path,
) -> list[Path]:
    directory = _census_directory(contract, project_root)
    return list(directory.glob("*")) if directory.exists() else []


def _resource_totals(
    *,
    records: list[V4P02JournalRecord],
    durable_paths: list[Path],
) -> V4P02ResourceTotals:
    return V4P02ResourceTotals(
        attempts_used=sum(
            item.record_type == "REQUEST_INTENT" for item in records
        ),
        responses_completed=sum(
            item.record_type == "RESPONSE" for item in records
        ),
        failures_recorded=sum(
            item.record_type == "FAILURE" for item in records
        ),
        http_hops_used=_http_hops(records),
        response_body_bytes=_response_body_bytes(records),
        active_elapsed_milliseconds=_active_elapsed_milliseconds(records),
        durable_storage_bytes=_storage_bytes(durable_paths),
    )


def write_terminal_result(
    *,
    kind: str,
    contract: V4P02FeasibilityContract,
    project_root: Path,
    records: list[V4P02JournalRecord],
    metadata_observation: V4P02MetadataObservation | None,
    metadata_gate: V4P02MetadataGateResult | None,
    header_observations: list[V4P02HeaderObservation],
    execution_gates: list[V4P02ExecutionGateResult],
    projection: V4P02StorageProjection | None,
    clock: Callable[[], datetime],
    failure: V4P02JournalRecord | None = None,
) -> V4P02TerminalResult:
    paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(paths)
    if any(path.exists() for path in paths.values()):
        raise EvidenceIntegrityError("V4P02 already has a terminal artifact")
    journal_path = safe_project_path(project_root, contract.journal_path)
    resources = _resource_totals(
        records=records,
        durable_paths=_durable_paths(contract, project_root),
    )
    completed = [
        item.request_id for item in records if item.record_type == "RESPONSE"
    ]
    failed = [
        item.request_id for item in records if item.record_type == "FAILURE"
    ]
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
            "SOURCE_CENSUS_COMPLETE_NO_SELECTION"
            if kind == "COMPLETE"
            else (
                "REJECT_V4P02_BEFORE_PAYLOAD_OR_PRIMARY_SELECTION"
                if kind == "REJECT"
                else "STOP_V4P02_TRANSPORT_NO_RETRY"
            )
        ),
        "execution_gate_results": execution_gates,
        "metadata_observation_hashes": (
            [metadata_observation.observation_evidence_hash]
            if metadata_observation is not None
            else []
        ),
        "header_observation_hashes": [
            item.observation_evidence_hash for item in header_observations
        ],
        "metadata_gate_hash": (
            metadata_gate.result_evidence_hash
            if metadata_gate is not None
            else None
        ),
        "parsed_and_prohibited_field_manifest": {
            "permitted_observation_fields": (
                V4P02_PERMITTED_OBSERVATION_FIELDS
            ),
            "prohibited_parsed_fields": V4P02_PROHIBITED_PARSED_FIELDS,
        },
        "request_journal_hash": (
            file_sha256(journal_path) if journal_path.exists() else EMPTY_SHA256
        ),
        "storage_projection": projection,
        "resource_totals": resources,
        "selection_and_permission_boundary": SELECTION_PERMISSION_BOUNDARY,
    }
    if kind == "TRANSPORT_STOP":
        if failure is None or failure.record_type != "FAILURE":
            raise EvidenceIntegrityError("V4P02 transport stop lacks failure")
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
                "redirect_chain_if_received": failure.redirect_chain,
                "unconsumed_request_hop_and_byte_budgets": {
                    "logical_requests": (
                        contract.transport_budget.total_attempt_budget
                        - resources.attempts_used
                    ),
                    "http_hops": (
                        contract.transport_budget.total_http_hop_budget
                        - resources.http_hops_used
                    ),
                    "response_body_bytes": (
                        contract.transport_budget.total_response_body_byte_budget
                        - resources.response_body_bytes
                    ),
                },
                "unreconciled_intent_status": (
                    "CLOSED_BY_DURABLE_FAILURE_NO_RETRY_PERMITTED"
                ),
            }
        )
    result = build_v4_p02_terminal_result(**common)
    atomic_write(
        paths[kind],
        (result.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return result


def close_unreconciled_intent(
    *,
    contract: V4P02FeasibilityContract,
    project_root: Path,
    journal_path: Path,
    records: list[V4P02JournalRecord],
    clock: Callable[[], datetime],
) -> V4P02JournalRecord:
    if not records or records[-1].record_type != "REQUEST_INTENT":
        raise EvidenceIntegrityError("No V4P02 intent is available to reconcile")
    intent = records[-1]
    request = next(
        item for item in contract.requests if item.request_id == intent.request_id
    )
    raw_path = _raw_metadata_path(contract, project_root)
    part_path = raw_path.with_name(f"{raw_path.name}.part")
    evidence_path = (
        part_path if part_path.exists() else raw_path if raw_path.exists() else None
    )
    byte_count = evidence_path.stat().st_size if evidence_path else 0
    payload_hash = file_sha256(evidence_path) if evidence_path else EMPTY_SHA256
    url_hash, headers_hash = request_hashes(request)
    failure = _append_journal(
        journal_path,
        records,
        record_type="FAILURE",
        recorded_at=clock(),
        contract_evidence_hash=contract.contract_evidence_hash,
        request_id=request.request_id,
        request_sequence=request.sequence,
        request_method=request.method,
        initial_url_hash=url_hash,
        request_headers_hash=headers_hash,
        final_url_hash=_url_hash(request.url),
        final_host=urlparse(request.url).hostname,
        elapsed_milliseconds=0,
        http_hop_count=0,
        byte_count=byte_count,
        payload_sha256=payload_hash,
        failure_class="UnreconciledRequestIntent",
        failure_message=(
            "A durable request intent had no durable outcome after restart; "
            "the frozen zero-retry contract requires a terminal transport stop."
        ),
    )
    if part_path.exists():
        part_path.unlink()
    if raw_path.exists() and request.method == "GET":
        raw_path.unlink()
    return failure


def _single_failed_gate(
    gate_id: str,
    evidence_hash: str,
    reason: str,
) -> list[V4P02ExecutionGateResult]:
    gates = unresolved_execution_gates()
    gates[V4P02_REQUIRED_GATE_IDS.index(gate_id)] = V4P02ExecutionGateResult(
        gate_id=gate_id,
        status="FAIL",
        evidence_hashes=[evidence_hash],
        reason=reason,
    )
    return gates


def _load_metadata_observation(
    path: Path,
) -> V4P02MetadataObservation | None:
    if not path.exists():
        return None
    try:
        return V4P02MetadataObservation.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise EvidenceIntegrityError(
            "Invalid V4P02 metadata observation"
        ) from exc


def _load_metadata_gate(path: Path) -> V4P02MetadataGateResult | None:
    if not path.exists():
        return None
    try:
        return V4P02MetadataGateResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise EvidenceIntegrityError("Invalid V4P02 metadata gate") from exc


def _audit_observation_bindings(
    *,
    contract: V4P02FeasibilityContract,
    records: list[V4P02JournalRecord],
    metadata_observation: V4P02MetadataObservation | None,
    header_observations: list[V4P02HeaderObservation],
    project_root: Path,
) -> None:
    requests = {item.request_id: item for item in contract.requests}
    responses = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    if metadata_observation is not None:
        response = responses.get(metadata_observation.request_id)
        request = requests.get(metadata_observation.request_id)
        if (
            response is None
            or request is None
            or request.sequence != 1
            or metadata_observation.contract_evidence_hash
            != contract.contract_evidence_hash
            or metadata_observation.payload_sha256 != response.payload_sha256
            or metadata_observation.byte_count != response.byte_count
        ):
            raise EvidenceIntegrityError(
                "V4P02 metadata observation-to-response binding changed"
            )
        if response.raw_relative_path is None:
            raise EvidenceIntegrityError("V4P02 metadata raw path is absent")
        raw_path = safe_project_path(project_root, response.raw_relative_path)
        if (
            not raw_path.is_file()
            or raw_path.stat().st_size != response.byte_count
            or file_sha256(raw_path) != response.payload_sha256
        ):
            raise EvidenceIntegrityError("V4P02 metadata raw bytes changed")
        reconstructed = parse_metadata_observation(
            contract=contract,
            request=request,
            response=response,
            raw_path=raw_path,
            observed_at=metadata_observation.observed_at,
        )
        if reconstructed != metadata_observation:
            raise EvidenceIntegrityError(
                "V4P02 metadata-derived observation changed"
            )
    if [item.observation_sequence for item in header_observations] != list(
        range(1, len(header_observations) + 1)
    ):
        raise EvidenceIntegrityError("V4P02 header observation order changed")
    for observation in header_observations:
        response = responses.get(observation.request_id)
        request = requests.get(observation.request_id)
        if (
            response is None
            or request is None
            or request.sequence != observation.request_sequence
            or request.dataset_data_type != observation.dataset_data_type
            or request.dataset_symbol != observation.dataset_symbol
            or request.dataset_role != observation.dataset_role
            or request.sample_date != observation.sample_date
            or observation.contract_evidence_hash
            != contract.contract_evidence_hash
            or observation.final_url_hash != response.final_url_hash
            or observation.response_header_subset != response.response_headers
            or observation.redirect_chain != response.redirect_chain
            or observation.body_byte_count != response.byte_count
            or observation.payload_sha256 != response.payload_sha256
        ):
            raise EvidenceIntegrityError(
                "V4P02 header observation-to-response binding changed"
            )
        reconstructed = parse_header_observation(
            contract=contract,
            request=request,
            response=response,
            observed_at=observation.observed_at,
        )
        if reconstructed != observation:
            raise EvidenceIntegrityError(
                "V4P02 header-derived observation changed"
            )


def run_feasibility(
    *,
    contract: V4P02FeasibilityContract,
    project_root: Path,
    transport: Transport,
    host_validator: Callable[[str], None] = validate_public_https_url,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
) -> V4P02TerminalResult:
    terminal_paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(terminal_paths)
    if any(path.exists() for path in terminal_paths.values()):
        raise EvidenceIntegrityError(
            "V4P02 terminal artifact exists; use --check"
        )
    journal_path = safe_project_path(project_root, contract.journal_path)
    metadata_path = safe_project_path(
        project_root,
        contract.metadata_observation_path,
    )
    header_path = safe_project_path(
        project_root,
        contract.header_observation_path,
    )
    gate_path = metadata_path.with_name(METADATA_GATE_FILENAME)
    records = reconstruct_journal(contract, journal_path)
    metadata_observation = _load_metadata_observation(metadata_path)
    metadata_gate = _load_metadata_gate(gate_path)
    header_observations = load_ndjson(
        header_path,
        V4P02HeaderObservation,
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
            metadata_observation=metadata_observation,
            metadata_gate=metadata_gate,
            header_observations=header_observations,
            execution_gates=unresolved_execution_gates(),
            projection=build_storage_projection(header_observations),
            clock=clock,
            failure=failure,
        )
    census_directory = _census_directory(contract, project_root)
    stale_parts = (
        list(census_directory.glob("*.part"))
        if census_directory.exists()
        else []
    )
    if stale_parts:
        raise EvidenceIntegrityError(
            "Stale V4P02 part file has no matching request intent"
        )
    raw_metadata_path = _raw_metadata_path(contract, project_root)
    metadata_response_exists = any(
        item.record_type == "RESPONSE" and item.request_sequence == 1
        for item in records
    )
    if raw_metadata_path.exists() and not metadata_response_exists:
        raise EvidenceIntegrityError(
            "Stale V4P02 raw metadata has no durable response"
        )
    if metadata_gate is not None and metadata_observation is None:
        raise EvidenceIntegrityError(
            "V4P02 metadata gate has no metadata observation"
        )
    _audit_observation_bindings(
        contract=contract,
        records=records,
        metadata_observation=metadata_observation,
        header_observations=header_observations,
        project_root=project_root,
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
            metadata_observation=metadata_observation,
            metadata_gate=metadata_gate,
            header_observations=header_observations,
            execution_gates=unresolved_execution_gates(),
            projection=build_storage_projection(header_observations),
            clock=clock,
            failure=failure,
        )
    responses = {
        item.request_id: item
        for item in records
        if item.record_type == "RESPONSE"
    }
    headers_by_request = {
        item.request_id: item for item in header_observations
    }

    for request in contract.requests:
        response = responses.get(request.request_id)
        if response is None:
            response = execute_request(
                contract=contract,
                request=request,
                project_root=project_root,
                journal_path=journal_path,
                records=records,
                transport=transport,
                host_validator=host_validator,
                clock=clock,
                monotonic=monotonic,
            )
            if response.record_type == "FAILURE":
                return write_terminal_result(
                    kind="TRANSPORT_STOP",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observation=metadata_observation,
                    metadata_gate=metadata_gate,
                    header_observations=header_observations,
                    execution_gates=unresolved_execution_gates(),
                    projection=build_storage_projection(header_observations),
                    clock=clock,
                    failure=response,
                )
            responses[request.request_id] = response

        if request.sequence == 1:
            if metadata_observation is None:
                if response.raw_relative_path is None:
                    raise EvidenceIntegrityError(
                        "V4P02 metadata response lacks raw path"
                    )
                raw_path = safe_project_path(
                    project_root,
                    response.raw_relative_path,
                )
                try:
                    metadata_observation = parse_metadata_observation(
                        contract=contract,
                        request=request,
                        response=response,
                        raw_path=raw_path,
                        observed_at=clock(),
                    )
                except Exception as exc:
                    return write_terminal_result(
                        kind="REJECT",
                        contract=contract,
                        project_root=project_root,
                        records=records,
                        metadata_observation=None,
                        metadata_gate=None,
                        header_observations=header_observations,
                        execution_gates=_single_failed_gate(
                            "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE",
                            response.payload_sha256,
                            "The exact metadata response could not be parsed "
                            "under the identity-only policy: "
                            f"{type(exc).__name__}: {str(exc)[:900]}",
                        ),
                        projection=None,
                        clock=clock,
                    )
                write_metadata_observation(
                    metadata_path,
                    metadata_observation,
                )
            if metadata_gate is None:
                metadata_gate = evaluate_metadata_gate(
                    contract=contract,
                    observation=metadata_observation,
                    evaluated_at=clock(),
                )
                write_metadata_gate(gate_path, metadata_gate)
            elif (
                metadata_gate.metadata_observation_hash
                != metadata_observation.observation_evidence_hash
                or metadata_gate.contract_evidence_hash
                != contract.contract_evidence_hash
            ):
                raise EvidenceIntegrityError(
                    "V4P02 metadata gate binding changed"
                )
            if metadata_gate.status == "FAIL":
                return write_terminal_result(
                    kind="REJECT",
                    contract=contract,
                    project_root=project_root,
                    records=records,
                    metadata_observation=metadata_observation,
                    metadata_gate=metadata_gate,
                    header_observations=header_observations,
                    execution_gates=evaluate_execution_gates(
                        metadata_gate=metadata_gate,
                        metadata_observation=metadata_observation,
                        header_observations=header_observations,
                        projection=None,
                    ),
                    projection=None,
                    clock=clock,
                )
            continue

        if request.request_id not in headers_by_request:
            observation = parse_header_observation(
                contract=contract,
                request=request,
                response=response,
                observed_at=clock(),
            )
            append_header_observation(header_path, observation)
            header_observations.append(observation)
            headers_by_request[request.request_id] = observation

    if metadata_observation is None or metadata_gate is None:
        raise EvidenceIntegrityError("V4P02 metadata evidence is incomplete")
    projection = build_storage_projection(header_observations)
    gates = evaluate_execution_gates(
        metadata_gate=metadata_gate,
        metadata_observation=metadata_observation,
        header_observations=header_observations,
        projection=projection,
    )
    kind = "COMPLETE" if all(item.status == "PASS" for item in gates) else "REJECT"
    return write_terminal_result(
        kind=kind,
        contract=contract,
        project_root=project_root,
        records=records,
        metadata_observation=metadata_observation,
        metadata_gate=metadata_gate,
        header_observations=header_observations,
        execution_gates=gates,
        projection=projection,
        clock=clock,
    )


def audit_terminal(
    *,
    contract: V4P02FeasibilityContract,
    project_root: Path,
) -> V4P02TerminalResult:
    paths = _terminal_paths(contract, project_root)
    _assert_terminal_exclusivity(paths)
    existing = [path for path in paths.values() if path.exists()]
    if len(existing) != 1:
        raise EvidenceIntegrityError("Exactly one V4P02 terminal is required")
    existing_kind = next(
        kind for kind, path in paths.items() if path == existing[0]
    )
    result = V4P02TerminalResult.model_validate_json(
        existing[0].read_text(encoding="utf-8")
    )
    if result.terminal_kind != existing_kind:
        raise EvidenceIntegrityError("V4P02 terminal artifact kind changed")
    expected_lineage = {
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
    }
    if (
        result.builder_and_contract_hashes != expected_lineage
        or result.selection_and_permission_boundary
        != SELECTION_PERMISSION_BOUNDARY
    ):
        raise EvidenceIntegrityError("V4P02 terminal lineage audit failed")
    journal_path = safe_project_path(project_root, contract.journal_path)
    records = reconstruct_journal(contract, journal_path)
    if (
        not journal_path.exists()
        or result.request_journal_hash != file_sha256(journal_path)
    ):
        raise EvidenceIntegrityError("V4P02 terminal journal hash changed")
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
        raise EvidenceIntegrityError("V4P02 terminal request outcomes changed")
    metadata_path = safe_project_path(
        project_root,
        contract.metadata_observation_path,
    )
    header_path = safe_project_path(
        project_root,
        contract.header_observation_path,
    )
    gate_path = metadata_path.with_name(METADATA_GATE_FILENAME)
    metadata_observation = _load_metadata_observation(metadata_path)
    metadata_gate = _load_metadata_gate(gate_path)
    header_observations = load_ndjson(
        header_path,
        V4P02HeaderObservation,
    )
    _audit_observation_bindings(
        contract=contract,
        records=records,
        metadata_observation=metadata_observation,
        header_observations=header_observations,
        project_root=project_root,
    )
    if result.metadata_observation_hashes != (
        [metadata_observation.observation_evidence_hash]
        if metadata_observation is not None
        else []
    ):
        raise EvidenceIntegrityError(
            "V4P02 terminal metadata observation hash changed"
        )
    if result.header_observation_hashes != [
        item.observation_evidence_hash for item in header_observations
    ]:
        raise EvidenceIntegrityError(
            "V4P02 terminal header observation hashes changed"
        )
    if result.metadata_gate_hash != (
        metadata_gate.result_evidence_hash
        if metadata_gate is not None
        else None
    ):
        raise EvidenceIntegrityError("V4P02 terminal metadata gate hash changed")
    if (
        metadata_gate is not None
        and metadata_observation is not None
        and metadata_gate.metadata_observation_hash
        != metadata_observation.observation_evidence_hash
    ):
        raise EvidenceIntegrityError("V4P02 metadata gate binding changed")
    if metadata_gate is not None and metadata_observation is not None:
        reconstructed_gate = evaluate_metadata_gate(
            contract=contract,
            observation=metadata_observation,
            evaluated_at=metadata_gate.evaluated_at,
        )
        if reconstructed_gate != metadata_gate:
            raise EvidenceIntegrityError("V4P02 metadata gate result changed")
    expected_projection = build_storage_projection(header_observations)
    if result.storage_projection != expected_projection:
        raise EvidenceIntegrityError("V4P02 storage projection changed")
    expected_resources = _resource_totals(
        records=records,
        durable_paths=_durable_paths(contract, project_root),
    )
    if result.resource_totals != expected_resources:
        raise EvidenceIntegrityError("V4P02 terminal resource totals changed")
    expected_decision = (
        "SOURCE_CENSUS_COMPLETE_NO_SELECTION"
        if result.terminal_kind == "COMPLETE"
        else (
            "REJECT_V4P02_BEFORE_PAYLOAD_OR_PRIMARY_SELECTION"
            if result.terminal_kind == "REJECT"
            else "STOP_V4P02_TRANSPORT_NO_RETRY"
        )
    )
    if result.decision != expected_decision:
        raise EvidenceIntegrityError("V4P02 terminal decision changed")
    if result.terminal_kind == "TRANSPORT_STOP":
        failure = next(
            (item for item in records if item.record_type == "FAILURE"),
            None,
        )
        if failure is None:
            raise EvidenceIntegrityError("V4P02 terminal failure is absent")
        intent = next(
            item
            for item in records
            if item.record_type == "REQUEST_INTENT"
            and item.request_id == failure.request_id
        )
        expected_transport = {
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
            "redirect_chain_if_received": failure.redirect_chain,
            "unconsumed_request_hop_and_byte_budgets": {
                "logical_requests": (
                    contract.transport_budget.total_attempt_budget
                    - expected_resources.attempts_used
                ),
                "http_hops": (
                    contract.transport_budget.total_http_hop_budget
                    - expected_resources.http_hops_used
                ),
                "response_body_bytes": (
                    contract.transport_budget.total_response_body_byte_budget
                    - expected_resources.response_body_bytes
                ),
            },
            "unreconciled_intent_status": (
                "CLOSED_BY_DURABLE_FAILURE_NO_RETRY_PERMITTED"
            ),
        }
        for field_name, expected in expected_transport.items():
            if getattr(result, field_name) != expected:
                raise EvidenceIntegrityError(
                    f"V4P02 terminal {field_name} changed"
                )
        expected_gates = unresolved_execution_gates()
    elif metadata_gate is not None and metadata_observation is not None:
        expected_gates = evaluate_execution_gates(
            metadata_gate=metadata_gate,
            metadata_observation=metadata_observation,
            header_observations=header_observations,
            projection=expected_projection,
        )
    else:
        expected_gates = None
    if (
        expected_gates is not None
        and result.execution_gate_results != expected_gates
    ):
        raise EvidenceIntegrityError("V4P02 terminal gate results changed")
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen V4P02 Deribit metadata and zero-body "
            "dataset-header census. Network access requires explicit --execute."
        )
    )
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Consume the frozen zero-retry metadata and HEAD request budget.",
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
                f"V4P02 DRY RUN contract={contract.contract_evidence_hash} "
                f"requests={len(contract.requests)} metadata_gets=1 heads=27 "
                "retries=0 payload_gets=PROHIBITED values=PROHIBITED",
                flush=True,
            )
            for request in contract.requests:
                print(
                    f"{request.sequence} {request.request_id} {request.method} "
                    f"{request.phase} redirects={request.maximum_redirects}",
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
            f"V4P02 {result.terminal_kind} {result.decision} "
            f"attempts={result.resource_totals.attempts_used} "
            f"hops={result.resource_totals.http_hops_used} "
            f"bytes={result.resource_totals.response_body_bytes} "
            f"payload_gets={result.authorizes_dataset_payload_gets} "
            f"selected={result.selects_primary}",
            flush=True,
        )
        return 0
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
