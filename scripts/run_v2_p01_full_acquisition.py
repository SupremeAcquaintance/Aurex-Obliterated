import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from importlib import import_module
from itertools import chain
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, urlsplit

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v2_p01_acquisition_result import (
    P01CurrentMetadataSnapshotEvidence,
    P01FullArchiveEvidence,
    P01SymbolQualification,
    V2P01FullAcquisitionResult,
    audit_v2_p01_full_acquisition_result,
    build_v2_p01_full_acquisition_result,
)
from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
    audit_v2_p01_primary_protocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import (
    FUNDING_HEADER_SCHEMAS,
    KLINE_HEADER_FIRST_FIELDS,
    V2PilotAcquisitionResult,
    month_bounds,
)
from aurex.backtest_engine.research_v2_source_census import (
    V2SourceCensusResult,
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_protocol_module = import_module("scripts.freeze_v2_p01_protocol")

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_FOUNDATION_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_protocol_v1.json"
)
DEFAULT_FOUNDATION_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_foundation_result_v1.json"
)
DEFAULT_CHARTER = DEFAULT_EVIDENCE_ROOT / "v2_mechanism_discovery_charter_v1.json"
DEFAULT_THEORY_SCREEN = (
    DEFAULT_EVIDENCE_ROOT / "v2_mechanism_theory_screen_v1.json"
)
DEFAULT_SUPERSEDED_METADATA_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1.json"
)
DEFAULT_METADATA_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_contract_v1_1.json"
)
DEFAULT_METADATA_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_metadata_source_audit_v1_1.json"
)
DEFAULT_SOURCE_CENSUS_CONTRACT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_contract_v1.json"
)
DEFAULT_SOURCE_CENSUS_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_source_census_result_v1.json"
)
DEFAULT_PILOT_PROTOCOL = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_acquisition_protocol_v1.json"
)
DEFAULT_PILOT_RESULT = (
    DEFAULT_EVIDENCE_ROOT / "v2_derivatives_pilot_acquisition_result_v1.json"
)
DEFAULT_PROTOCOL = DEFAULT_EVIDENCE_ROOT / "v2_p01_primary_protocol_v1.json"
DEFAULT_OUTPUT = (
    DEFAULT_EVIDENCE_ROOT / "v2_p01_full_acquisition_result_v1.json"
)
MAX_CHECKSUM_BYTES = 4096
MAX_METADATA_SNAPSHOT_BYTES = 32 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}
NUMERIC_TEXT = re.compile(
    rb"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)


@dataclass(frozen=True, slots=True)
class P01FullTarget:
    symbol: str
    month: str
    family_id: str
    archive_url: str
    checksum_url: str
    census_checksum_sha256: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


@dataclass(frozen=True, slots=True)
class P01Preflight:
    target: P01FullTarget
    checksum_checked_at: datetime
    preflight_checked_at: datetime
    content_length: int
    last_modified: str | None
    etag: str | None


def runner_contract_hash() -> str:
    paths = [
        PROJECT_ROOT / "scripts" / "run_v2_p01_full_acquisition.py",
        PROJECT_ROOT
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_p01_acquisition_result.py",
    ]
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


def load_protocol_inputs(args):
    inputs = _protocol_module.load_inputs(args)
    stored = V2P01PrimaryProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    expected = _protocol_module.authoritative_protocol(
        frozen_at=stored.frozen_at,
        inputs=inputs,
    )
    if (
        stored != expected
        or not audit_v2_p01_primary_protocol(stored)
        or stored.builder_contract_hash
        != _protocol_module.builder_contract_hash()
    ):
        raise ValueError("Frozen P01 protocol is not reproducible")
    return stored, inputs


def render_targets(
    *,
    protocol: V2P01PrimaryProtocol,
    census_result: V2SourceCensusResult,
) -> list[P01FullTarget]:
    allowed_symbols = set(protocol.acquisition.complete_source_symbols)
    targets = [
        P01FullTarget(
            symbol=record.symbol,
            month=record.month,
            family_id=record.family_id,
            archive_url=record.archive_url,
            checksum_url=record.checksum_url,
            census_checksum_sha256=record.checksum_sha256 or "",
        )
        for record in census_result.records
        if record.symbol in allowed_symbols
    ]
    targets.sort(key=lambda item: item.key)
    if len(targets) != protocol.acquisition.source_target_count:
        raise ValueError("P01 acquisition target count changed")
    manifest_hash = universe_evidence_hash(
        {
            "targets": [
                {
                    "symbol": target.symbol,
                    "month": target.month,
                    "family_id": target.family_id,
                    "archive_url": target.archive_url,
                    "checksum_url": target.checksum_url,
                    "checksum_sha256": target.census_checksum_sha256,
                }
                for target in targets
            ]
        }
    )
    if manifest_hash != protocol.acquisition.source_target_manifest_hash:
        raise ValueError("P01 acquisition source-target manifest changed")
    return targets


def _request(
    *,
    url: str,
    method: str,
    timeout: int,
    accept: str = "*/*",
):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Accept-Encoding": "identity",
            "User-Agent": "Aurex-P01-Full-Acquisition/1.0",
        },
        method=method,
    )
    return urllib.request.urlopen(request, timeout=timeout)


def _retry_delay(protocol: V2P01PrimaryProtocol, attempt: int) -> None:
    time.sleep(protocol.acquisition.retry_backoff_seconds[attempt])


def _fetch_bytes_with_retries(
    *,
    url: str,
    timeout: int,
    retries: int,
    backoff: list[int],
    maximum_bytes: int,
    accept: str,
) -> tuple[datetime, int, str, str, bytes]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with _request(
                url=url,
                method="GET",
                timeout=timeout,
                accept=accept,
            ) as response:
                status = int(response.getcode())
                final_url = response.geturl()
                content_type = response.headers.get(
                    "Content-Type", "application/octet-stream"
                )
                payload = response.read(maximum_bytes + 1)
            if status != 200:
                raise ValueError(f"HTTP {status}: {url}")
            if len(payload) > maximum_bytes:
                raise ValueError(f"Response exceeded byte cap: {url}")
            return datetime.now(UTC), status, final_url, content_type, payload
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise
            last_error = exc
        except (OSError, TimeoutError, ValueError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(backoff[attempt])
    raise RuntimeError(f"GET failed after {retries + 1} attempts: {url}") from (
        last_error
    )


def _positive_numeric(value) -> bool:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite() and number > 0


def _filters_by_type(symbol_payload: dict) -> dict[str, dict]:
    filters = symbol_payload.get("filters")
    if not isinstance(filters, list):
        return {}
    return {
        item.get("filterType"): item
        for item in filters
        if isinstance(item, dict) and isinstance(item.get("filterType"), str)
    }


def _spot_filter_proxy_complete(symbol_payload: dict) -> bool:
    filters = _filters_by_type(symbol_payload)
    notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
    return bool(
        symbol_payload.get("status") == "TRADING"
        and _positive_numeric(filters.get("PRICE_FILTER", {}).get("tickSize"))
        and _positive_numeric(filters.get("LOT_SIZE", {}).get("minQty"))
        and _positive_numeric(filters.get("LOT_SIZE", {}).get("stepSize"))
        and _positive_numeric(filters.get("MARKET_LOT_SIZE", {}).get("maxQty"))
        and _positive_numeric((notional or {}).get("minNotional"))
    )


def _futures_filter_proxy_complete(symbol_payload: dict) -> bool:
    filters = _filters_by_type(symbol_payload)
    notional = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL")
    return bool(
        symbol_payload.get("status") == "TRADING"
        and symbol_payload.get("contractType") == "PERPETUAL"
        and _positive_numeric(filters.get("PRICE_FILTER", {}).get("tickSize"))
        and _positive_numeric(filters.get("LOT_SIZE", {}).get("minQty"))
        and _positive_numeric(filters.get("LOT_SIZE", {}).get("stepSize"))
        and _positive_numeric(filters.get("MARKET_LOT_SIZE", {}).get("maxQty"))
        and _positive_numeric(
            (notional or {}).get("notional")
            or (notional or {}).get("minNotional")
        )
    )


def classify_snapshot_payload(
    *,
    snapshot_kind: str,
    requested_url: str,
    final_url: str,
    checked_at: datetime,
    content_type: str,
    payload: bytes,
    evidence_root: Path,
    storage_root: Path,
) -> P01CurrentMetadataSnapshotEvidence:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("P01 metadata snapshot is not valid JSON") from exc
    if not isinstance(decoded, dict) or not isinstance(
        decoded.get("symbols"), list
    ):
        raise ValueError("P01 metadata snapshot has no symbol list")
    by_symbol = {
        item.get("symbol"): item
        for item in decoded["symbols"]
        if isinstance(item, dict) and isinstance(item.get("symbol"), str)
    }
    required = set(V2_COMPLETE_SYMBOLS)
    present = sorted(required & by_symbol.keys())
    missing = sorted(required - by_symbol.keys())
    complete_function = (
        _spot_filter_proxy_complete
        if snapshot_kind == "SPOT_EXCHANGE_INFO"
        else _futures_filter_proxy_complete
    )
    complete = sorted(
        symbol
        for symbol in present
        if complete_function(by_symbol[symbol])
    )
    incomplete = sorted(required - set(complete))
    digest = hashlib.sha256(payload).hexdigest()
    snapshot_path = (
        storage_root
        / "metadata"
        / f"{snapshot_kind.lower()}-{digest}.json"
    )
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_path.exists():
        if snapshot_path.read_bytes() != payload:
            raise ValueError("P01 metadata snapshot hash-path collision")
    else:
        temporary = snapshot_path.with_name(f"{snapshot_path.name}.part")
        if temporary.exists():
            raise ValueError(f"Stale P01 metadata snapshot exists: {temporary}")
        temporary.write_bytes(payload)
        temporary.replace(snapshot_path)
    return P01CurrentMetadataSnapshotEvidence(
        snapshot_kind=snapshot_kind,
        requested_url=requested_url,
        final_url=final_url,
        checked_at=checked_at,
        content_type=content_type,
        response_bytes=len(payload),
        response_sha256=digest,
        snapshot_relative_path=(
            snapshot_path.relative_to(evidence_root).as_posix()
        ),
        present_required_symbols=present,
        missing_required_symbols=missing,
        complete_filter_symbols=complete,
        incomplete_filter_symbols=incomplete,
    )


def collect_metadata_snapshots(
    *,
    protocol: V2P01PrimaryProtocol,
    evidence_root: Path,
) -> list[P01CurrentMetadataSnapshotEvidence]:
    storage_root = evidence_root / protocol.acquisition.storage_root_relative_path
    specs = [
        (
            "SPOT_EXCHANGE_INFO",
            "https://api.binance.com/api/v3/exchangeInfo",
        ),
        (
            "USD_M_EXCHANGE_INFO",
            "https://fapi.binance.com/fapi/v1/exchangeInfo",
        ),
    ]
    snapshots = []
    for kind, url in specs:
        checked_at, _, final_url, content_type, payload = (
            _fetch_bytes_with_retries(
                url=url,
                timeout=protocol.acquisition.request_timeout_seconds,
                retries=protocol.acquisition.maximum_retries,
                backoff=protocol.acquisition.retry_backoff_seconds,
                maximum_bytes=MAX_METADATA_SNAPSHOT_BYTES,
                accept="application/json",
            )
        )
        expected_domain = urlparse(url).hostname
        if (urlparse(final_url).hostname or "").lower() != expected_domain:
            raise ValueError(f"P01 metadata redirected off-domain: {kind}")
        snapshots.append(
            classify_snapshot_payload(
                snapshot_kind=kind,
                requested_url=url,
                final_url=final_url,
                checked_at=checked_at,
                content_type=content_type,
                payload=payload,
                evidence_root=evidence_root,
                storage_root=storage_root,
            )
        )
    return sorted(snapshots, key=lambda item: item.snapshot_kind)


def _fetch_refreshed_checksum(
    *,
    target: P01FullTarget,
    protocol: V2P01PrimaryProtocol,
) -> datetime:
    checked_at, _, _, _, payload = _fetch_bytes_with_retries(
        url=target.checksum_url,
        timeout=protocol.acquisition.request_timeout_seconds,
        retries=protocol.acquisition.maximum_retries,
        backoff=protocol.acquisition.retry_backoff_seconds,
        maximum_bytes=MAX_CHECKSUM_BYTES,
        accept="text/plain",
    )
    try:
        checksum_text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("P01 checksum is not UTF-8") from exc
    archive_name = PurePosixPath(urlsplit(target.archive_url).path).name
    refreshed = parse_v2_checksum_text(checksum_text, archive_name)
    if refreshed != target.census_checksum_sha256:
        raise ValueError(f"P01 checksum changed after census: {target.key}")
    return checked_at


def _fetch_archive_head(
    *,
    target: P01FullTarget,
    protocol: V2P01PrimaryProtocol,
) -> tuple[datetime, int, str | None, str | None]:
    last_error: Exception | None = None
    for attempt in range(protocol.acquisition.maximum_retries + 1):
        try:
            with _request(
                url=target.archive_url,
                method="HEAD",
                timeout=protocol.acquisition.request_timeout_seconds,
            ) as response:
                status = int(response.getcode())
                length_text = response.headers.get("Content-Length")
                last_modified = response.headers.get("Last-Modified")
                etag = response.headers.get("ETag")
            if status != 200 or length_text is None:
                raise ValueError(f"P01 archive HEAD incomplete: {target.key}")
            content_length = int(length_text)
            if (
                content_length <= 0
                or content_length
                > protocol.acquisition.maximum_single_archive_compressed_bytes
            ):
                raise ValueError(
                    f"P01 archive violates compressed-byte cap: {target.key}"
                )
            return datetime.now(UTC), content_length, last_modified, etag
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise
            last_error = exc
        except (OSError, TimeoutError, ValueError) as exc:
            last_error = exc
        if attempt < protocol.acquisition.maximum_retries:
            _retry_delay(protocol, attempt)
    raise RuntimeError(f"P01 archive HEAD failed: {target.key}") from last_error


def preflight_target(
    *,
    target: P01FullTarget,
    protocol: V2P01PrimaryProtocol,
) -> P01Preflight:
    checksum_checked_at = _fetch_refreshed_checksum(
        target=target,
        protocol=protocol,
    )
    checked_at, content_length, last_modified, etag = _fetch_archive_head(
        target=target,
        protocol=protocol,
    )
    return P01Preflight(
        target=target,
        checksum_checked_at=checksum_checked_at,
        preflight_checked_at=checked_at,
        content_length=content_length,
        last_modified=last_modified,
        etag=etag,
    )


def collect_preflight(
    *,
    targets: list[P01FullTarget],
    protocol: V2P01PrimaryProtocol,
    workers: int,
) -> list[P01Preflight]:
    observations = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            preflight_target,
            target=target,
            protocol=protocol,
        ): target
        for target in targets
    }
    try:
        for completed, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            try:
                observations.append(future.result())
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "P01 preflight aborted without result at "
                    f"{target.key}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 100 == 0 or completed == len(futures):
                print(
                    f"P01 preflight: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(observations, key=lambda item: item.target.key)


def enforce_resource_gates(
    *,
    protocol: V2P01PrimaryProtocol,
    preflight: list[P01Preflight],
    evidence_root: Path,
) -> None:
    if len(preflight) != protocol.acquisition.source_target_count:
        raise ValueError("P01 preflight target matrix is incomplete")
    total_bytes = sum(item.content_length for item in preflight)
    if total_bytes > protocol.acquisition.maximum_total_compressed_bytes:
        raise ValueError("P01 preflight exceeds total compressed-byte cap")
    storage_root = (
        evidence_root / protocol.acquisition.storage_root_relative_path
    )
    storage_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(storage_root).free
    if free_bytes < protocol.acquisition.minimum_free_disk_bytes_before_download:
        raise ValueError("P01 free disk is below the pre-download floor")
    existing_bytes = 0
    for item in preflight:
        archive_path, _ = target_paths(
            evidence_root=evidence_root,
            protocol=protocol,
            target=item.target,
        )
        if archive_path.is_file():
            existing_bytes += archive_path.stat().st_size
    projected_new_bytes = max(total_bytes - existing_bytes, 0)
    if free_bytes - projected_new_bytes < (
        protocol.acquisition.minimum_free_disk_bytes_after_processing
    ):
        raise ValueError("P01 projected free disk is below the final floor")
    print(
        "P01 resource gate PASS "
        f"compressed_bytes={total_bytes} existing_bytes={existing_bytes} "
        f"free_bytes={free_bytes}",
        flush=True,
    )


def target_paths(
    *,
    evidence_root: Path,
    protocol: V2P01PrimaryProtocol,
    target: P01FullTarget,
) -> tuple[Path, Path]:
    archive_name = PurePosixPath(urlsplit(target.archive_url).path).name
    directory = (
        evidence_root
        / protocol.acquisition.storage_root_relative_path
        / "archives"
        / target.family_id
        / target.symbol
    )
    archive_path = directory / archive_name
    return archive_path, Path(f"{archive_path}.CHECKSUM")


def _stream_response_to_file(
    response,
    *,
    temporary: Path,
    expected_bytes: int,
    maximum_bytes: int,
) -> str:
    digest = hashlib.sha256()
    downloaded = 0
    with temporary.open("xb") as destination:
        while True:
            chunk = response.read(DOWNLOAD_CHUNK_BYTES)
            if not chunk:
                break
            downloaded += len(chunk)
            if downloaded > expected_bytes or downloaded > maximum_bytes:
                raise ValueError("P01 archive exceeded its preflight size")
            destination.write(chunk)
            digest.update(chunk)
    if downloaded != expected_bytes:
        raise ValueError("P01 archive size differs from preflight")
    return digest.hexdigest()


def _download_archive_once(
    *,
    preflight: P01Preflight,
    protocol: V2P01PrimaryProtocol,
    archive_path: Path,
) -> None:
    temporary = archive_path.with_name(f"{archive_path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale P01 archive download exists: {temporary}")
    try:
        with _request(
            url=preflight.target.archive_url,
            method="GET",
            timeout=protocol.acquisition.request_timeout_seconds,
        ) as response:
            if int(response.getcode()) != 200:
                raise RuntimeError(
                    f"P01 archive GET failed: {preflight.target.key}"
                )
            observed_length = response.headers.get("Content-Length")
            if (
                observed_length is None
                or int(observed_length) != preflight.content_length
            ):
                raise ValueError("P01 GET length changed after preflight")
            observed_hash = _stream_response_to_file(
                response,
                temporary=temporary,
                expected_bytes=preflight.content_length,
                maximum_bytes=(
                    protocol.acquisition.maximum_single_archive_compressed_bytes
                ),
            )
        if observed_hash != preflight.target.census_checksum_sha256:
            raise ValueError("P01 archive checksum does not match census")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(archive_path)


def _copy_pilot_archive(
    *,
    source: Path,
    destination: Path,
    expected_hash: str,
    expected_bytes: int,
) -> bool:
    if (
        not source.is_file()
        or source.stat().st_size != expected_bytes
        or file_sha256(source) != expected_hash
    ):
        return False
    temporary = destination.with_name(f"{destination.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale P01 pilot copy exists: {temporary}")
    shutil.copyfile(source, temporary)
    if (
        temporary.stat().st_size != expected_bytes
        or file_sha256(temporary) != expected_hash
    ):
        temporary.unlink(missing_ok=True)
        raise ValueError("P01 copied pilot archive failed verification")
    temporary.replace(destination)
    return True


def ensure_verified_archive(
    *,
    preflight: P01Preflight,
    protocol: V2P01PrimaryProtocol,
    evidence_root: Path,
    pilot_sources: dict[tuple[str, str, str], Path],
) -> str:
    archive_path, checksum_path = target_paths(
        evidence_root=evidence_root,
        protocol=protocol,
        target=preflight.target,
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    source = "existing"
    if archive_path.exists():
        if (
            archive_path.stat().st_size != preflight.content_length
            or file_sha256(archive_path)
            != preflight.target.census_checksum_sha256
        ):
            raise ValueError(
                f"Existing P01 archive conflicts: {preflight.target.key}"
            )
    else:
        pilot_source = pilot_sources.get(preflight.target.key)
        if pilot_source is not None and _copy_pilot_archive(
            source=pilot_source,
            destination=archive_path,
            expected_hash=preflight.target.census_checksum_sha256,
            expected_bytes=preflight.content_length,
        ):
            source = "pilot"
        else:
            source = "download"
            last_error: Exception | None = None
            for attempt in range(protocol.acquisition.maximum_retries + 1):
                try:
                    _download_archive_once(
                        preflight=preflight,
                        protocol=protocol,
                        archive_path=archive_path,
                    )
                except urllib.error.HTTPError as exc:
                    if exc.code not in TRANSIENT_HTTP_STATUS:
                        raise
                    last_error = exc
                except (OSError, TimeoutError) as exc:
                    last_error = exc
                else:
                    break
                if attempt < protocol.acquisition.maximum_retries:
                    _retry_delay(protocol, attempt)
            else:
                raise RuntimeError(
                    f"P01 archive GET unresolved: {preflight.target.key}"
                ) from last_error
    checksum_bytes = (
        f"{preflight.target.census_checksum_sha256}  {archive_path.name}\n"
    ).encode("ascii")
    if checksum_path.exists():
        if checksum_path.read_bytes() != checksum_bytes:
            raise ValueError(
                f"Existing P01 checksum conflicts: {preflight.target.key}"
            )
    else:
        temporary = checksum_path.with_name(f"{checksum_path.name}.part")
        if temporary.exists():
            raise ValueError(f"Stale P01 checksum exists: {temporary}")
        temporary.write_bytes(checksum_bytes)
        temporary.replace(checksum_path)
    return source


def collect_downloads(
    *,
    preflight: list[P01Preflight],
    protocol: V2P01PrimaryProtocol,
    evidence_root: Path,
    pilot_result: V2PilotAcquisitionResult,
    workers: int,
) -> dict[str, int]:
    pilot_sources = {
        record.key: evidence_root / record.archive_relative_path
        for record in pilot_result.records
    }
    counts = {"existing": 0, "pilot": 0, "download": 0}
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            ensure_verified_archive,
            preflight=item,
            protocol=protocol,
            evidence_root=evidence_root,
            pilot_sources=pilot_sources,
        ): item.target
        for item in preflight
    }
    try:
        for completed, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            try:
                counts[future.result()] += 1
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "P01 download aborted without result at "
                    f"{target.key}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 50 == 0 or completed == len(futures):
                print(
                    f"P01 archives ready: {completed}/{len(futures)} "
                    f"downloaded={counts['download']} pilot={counts['pilot']} "
                    f"existing={counts['existing']}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return counts


def _validate_zip_member(
    *,
    archive: zipfile.ZipFile,
    protocol: V2P01PrimaryProtocol,
) -> tuple[zipfile.ZipInfo, int, int]:
    files = [member for member in archive.infolist() if not member.is_dir()]
    if len(files) != 1 or not files[0].filename.lower().endswith(".csv"):
        raise ValueError("P01 archive must contain exactly one CSV")
    member = files[0]
    member_path = PurePosixPath(member.filename)
    if (
        member_path.is_absolute()
        or len(member_path.parts) != 1
        or ".." in member_path.parts
        or "\\" in member.filename
        or member.flag_bits & 0x1
        or ((member.external_attr >> 16) & 0o170000) == stat.S_IFLNK
    ):
        raise ValueError("P01 archive contains an unsafe member")
    compressed = sum(item.compress_size for item in files)
    uncompressed = sum(item.file_size for item in files)
    if (
        compressed <= 0
        or uncompressed <= 0
        or uncompressed
        > protocol.acquisition.maximum_single_archive_uncompressed_bytes
        or uncompressed
        > compressed * protocol.acquisition.maximum_zip_expansion_ratio
    ):
        raise ValueError("P01 archive violates uncompressed resource limits")
    return member, compressed, uncompressed


def _normalize_header(parts: list[bytes]) -> tuple[str, ...]:
    try:
        return tuple(
            item.decode("utf-8").strip().lower().replace(" ", "_")
            for item in parts
        )
    except UnicodeDecodeError as exc:
        raise ValueError("P01 CSV header is not UTF-8") from exc


def _validate_numeric_fields(parts: list[bytes], indexes: tuple[int, ...]) -> None:
    for index in indexes:
        value = parts[index].strip()
        if not NUMERIC_TEXT.fullmatch(value):
            raise ValueError("P01 normalized numeric field is invalid")


def _inspect_csv(
    *,
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    target: P01FullTarget,
) -> dict[str, object]:
    start, end = month_bounds(target.month)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    expected_minutes = int((end - start).total_seconds() // 60)
    is_funding = target.family_id == "um_funding_rate_events"
    header: list[str] = []
    row_count = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    previous_timestamp_ms: int | None = None
    gap_count = 0

    with archive.open(member) as source:
        try:
            first_line = next(source)
        except StopIteration as exc:
            raise ValueError("P01 CSV is empty") from exc
        first_parts = first_line.rstrip(b"\r\n").split(b",")
        try:
            int(first_parts[0])
        except (ValueError, IndexError):
            first_is_header = True
        else:
            first_is_header = False

        if is_funding:
            normalized = _normalize_header(first_parts)
            if not first_is_header or normalized not in FUNDING_HEADER_SCHEMAS:
                raise ValueError("P01 funding schema is unknown")
            timestamp_index, numeric_indexes = FUNDING_HEADER_SCHEMAS[normalized]
            expected_columns = len(first_parts)
            header = [item.decode("utf-8").strip() for item in first_parts]
            data_rows = source
            schema_id = "BINANCE_FUNDING_RATE_EVENT_V1"
        else:
            expected_columns = 12
            timestamp_index = 0
            numeric_indexes = tuple(range(1, expected_columns))
            schema_id = "BINANCE_POSITIONAL_KLINE_12_COLUMNS_V1"
            if first_is_header:
                normalized = _normalize_header(first_parts)
                if (
                    len(first_parts) != expected_columns
                    or normalized[0] not in KLINE_HEADER_FIRST_FIELDS
                ):
                    raise ValueError("P01 kline header is unknown")
                header = [item.decode("utf-8").strip() for item in first_parts]
                data_rows = source
            else:
                data_rows = chain((first_line,), source)

        for raw_line in data_rows:
            parts = raw_line.rstrip(b"\r\n").split(b",")
            if len(parts) != expected_columns:
                raise ValueError("P01 CSV column count changed")
            try:
                timestamp_ms = int(parts[timestamp_index])
            except (ValueError, IndexError) as exc:
                raise ValueError("P01 CSV timestamp is invalid") from exc
            if timestamp_ms < start_ms or timestamp_ms >= end_ms:
                raise ValueError("P01 CSV row is outside target month")
            if (
                previous_timestamp_ms is not None
                and timestamp_ms <= previous_timestamp_ms
            ):
                raise ValueError("P01 CSV timestamps are not strictly increasing")
            _validate_numeric_fields(parts, numeric_indexes)
            if (
                not is_funding
                and previous_timestamp_ms is not None
                and timestamp_ms - previous_timestamp_ms != 60_000
            ):
                gap_count += 1
            if first_timestamp_ms is None:
                first_timestamp_ms = timestamp_ms
            last_timestamp_ms = timestamp_ms
            previous_timestamp_ms = timestamp_ms
            row_count += 1
    if row_count == 0 or first_timestamp_ms is None or last_timestamp_ms is None:
        raise ValueError("P01 CSV has no data rows")
    first_timestamp = datetime.fromtimestamp(
        first_timestamp_ms / 1000, tz=UTC
    )
    last_timestamp = datetime.fromtimestamp(last_timestamp_ms / 1000, tz=UTC)
    if is_funding:
        return {
            "schema_id": schema_id,
            "csv_header": header,
            "csv_column_count": expected_columns,
            "row_count": row_count,
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "expected_minute_count": None,
            "missing_minute_count": None,
            "continuity_gap_count": None,
            "boundary_complete": True,
            "continuity_pass": True,
        }
    missing_minutes = expected_minutes - row_count
    boundary_complete = (
        first_timestamp_ms == start_ms and last_timestamp_ms == end_ms - 60_000
    )
    continuity_pass = (
        boundary_complete and missing_minutes == 0 and gap_count == 0
    )
    return {
        "schema_id": schema_id,
        "csv_header": header,
        "csv_column_count": expected_columns,
        "row_count": row_count,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "expected_minute_count": expected_minutes,
        "missing_minute_count": missing_minutes,
        "continuity_gap_count": gap_count,
        "boundary_complete": boundary_complete,
        "continuity_pass": continuity_pass,
    }


def _receipt_path(
    *,
    evidence_root: Path,
    protocol: V2P01PrimaryProtocol,
    target: P01FullTarget,
) -> Path:
    return (
        evidence_root
        / protocol.acquisition.storage_root_relative_path
        / "qualification_receipts"
        / target.family_id
        / target.symbol
        / f"{target.month}.json"
    )


def _load_receipt(
    *,
    path: Path,
    protocol: V2P01PrimaryProtocol,
    expected_archive_hash: str,
) -> P01FullArchiveEvidence | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        receipt_hash = payload.pop("receipt_evidence_hash")
        if (
            receipt_hash != universe_evidence_hash(payload)
            or payload["runner_contract_hash"] != runner_contract_hash()
            or payload["protocol_evidence_hash"]
            != protocol.protocol_evidence_hash
        ):
            return None
        record = P01FullArchiveEvidence.model_validate(payload["record"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if record.archive_sha256 != expected_archive_hash:
        return None
    return record


def _write_receipt(
    *,
    path: Path,
    protocol: V2P01PrimaryProtocol,
    record: P01FullArchiveEvidence,
) -> None:
    payload = {
        "schema_version": "aurex-v2-p01-qualification-cache-v1",
        "runner_contract_hash": runner_contract_hash(),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "record": record.model_dump(mode="json"),
    }
    payload["receipt_evidence_hash"] = universe_evidence_hash(payload)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale P01 qualification receipt exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def inspect_target(
    *,
    preflight: P01Preflight,
    protocol: V2P01PrimaryProtocol,
    evidence_root: Path,
) -> P01FullArchiveEvidence:
    archive_path, checksum_path = target_paths(
        evidence_root=evidence_root,
        protocol=protocol,
        target=preflight.target,
    )
    if (
        not archive_path.is_file()
        or archive_path.stat().st_size != preflight.content_length
        or file_sha256(archive_path)
        != preflight.target.census_checksum_sha256
    ):
        raise ValueError(f"P01 local archive failed verification: {preflight.target.key}")
    receipt_path = _receipt_path(
        evidence_root=evidence_root,
        protocol=protocol,
        target=preflight.target,
    )
    cached = _load_receipt(
        path=receipt_path,
        protocol=protocol,
        expected_archive_hash=preflight.target.census_checksum_sha256,
    )
    if cached is not None:
        return cached.model_copy(
            update={
                "checksum_checked_at": preflight.checksum_checked_at,
                "preflight_checked_at": preflight.preflight_checked_at,
                "archive_content_length": preflight.content_length,
                "archive_last_modified": preflight.last_modified,
                "archive_etag": preflight.etag,
            }
        )
    checksum_file_hash = file_sha256(checksum_path)
    with zipfile.ZipFile(archive_path) as archive:
        member, compressed, uncompressed = _validate_zip_member(
            archive=archive,
            protocol=protocol,
        )
        row_evidence = _inspect_csv(
            archive=archive,
            member=member,
            target=preflight.target,
        )
    record = P01FullArchiveEvidence(
        symbol=preflight.target.symbol,
        month=preflight.target.month,
        family_id=preflight.target.family_id,
        archive_url=preflight.target.archive_url,
        checksum_url=preflight.target.checksum_url,
        census_checksum_sha256=preflight.target.census_checksum_sha256,
        refreshed_checksum_sha256=preflight.target.census_checksum_sha256,
        checksum_checked_at=preflight.checksum_checked_at,
        preflight_checked_at=preflight.preflight_checked_at,
        inspected_at=datetime.now(UTC),
        archive_content_length=preflight.content_length,
        archive_last_modified=preflight.last_modified,
        archive_etag=preflight.etag,
        archive_relative_path=archive_path.relative_to(
            evidence_root
        ).as_posix(),
        checksum_relative_path=checksum_path.relative_to(
            evidence_root
        ).as_posix(),
        archive_sha256=preflight.target.census_checksum_sha256,
        checksum_file_sha256=checksum_file_hash,
        archive_size_bytes=archive_path.stat().st_size,
        zip_compressed_bytes=compressed,
        zip_uncompressed_bytes=uncompressed,
        csv_member_name=member.filename,
        **row_evidence,
    )
    _write_receipt(path=receipt_path, protocol=protocol, record=record)
    return record


def collect_inspections(
    *,
    preflight: list[P01Preflight],
    protocol: V2P01PrimaryProtocol,
    evidence_root: Path,
    workers: int,
) -> list[P01FullArchiveEvidence]:
    records = []
    executor = ProcessPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            inspect_target,
            preflight=item,
            protocol=protocol,
            evidence_root=evidence_root,
        ): item.target
        for item in preflight
    }
    try:
        for completed, future in enumerate(as_completed(futures), start=1):
            target = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "P01 qualification aborted without result at "
                    f"{target.key}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 50 == 0 or completed == len(futures):
                print(
                    f"P01 archives qualified: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(records, key=lambda item: item.key)


def build_symbol_qualifications(
    *,
    records: list[P01FullArchiveEvidence],
    snapshots: list[P01CurrentMetadataSnapshotEvidence],
) -> list[P01SymbolQualification]:
    by_kind = {item.snapshot_kind: item for item in snapshots}
    spot_complete = set(
        by_kind["SPOT_EXCHANGE_INFO"].complete_filter_symbols
    )
    futures_complete = set(
        by_kind["USD_M_EXCHANGE_INFO"].complete_filter_symbols
    )
    qualifications = []
    for symbol in V2_COMPLETE_SYMBOLS:
        symbol_records = [item for item in records if item.symbol == symbol]
        archive_pass = (
            len(symbol_records) == 144
            and all(item.continuity_pass for item in symbol_records)
        )
        spot_pass = symbol in spot_complete
        futures_pass = symbol in futures_complete
        reasons = []
        if not archive_pass:
            reasons.append("ARCHIVE_CONTINUITY_GAP")
        if not spot_pass:
            reasons.append("MISSING_SPOT_FILTER_PROXY")
        if not futures_pass:
            reasons.append("MISSING_FUTURES_FILTER_PROXY")
        qualifications.append(
            P01SymbolQualification(
                symbol=symbol,
                archive_continuity_pass=archive_pass,
                current_spot_filter_proxy_pass=spot_pass,
                current_futures_filter_proxy_pass=futures_pass,
                qualification_pass=not reasons,
                reason_codes=reasons,
            )
        )
    return qualifications


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: V2P01PrimaryProtocol,
    records: list[P01FullArchiveEvidence],
    snapshots: list[P01CurrentMetadataSnapshotEvidence],
) -> V2P01FullAcquisitionResult:
    qualifications = build_symbol_qualifications(
        records=records,
        snapshots=snapshots,
    )
    return build_v2_p01_full_acquisition_result(
        generated_at=generated_at,
        protocol=protocol,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        metadata_snapshots=snapshots,
        symbol_qualifications=qualifications,
        limitations=[
            (
                "Current spot and futures exchangeInfo snapshots are nonhistorical "
                "filter proxies and cannot prove 2023-2024 order acceptance."
            ),
            (
                "Historical account fee tiers are unavailable and remain fixed "
                "conservative research overrides in the P01 protocol."
            ),
            (
                "Historical leverage, maintenance margin, collateral, liquidation, "
                "and ADL rules remain explicit nonhistorical overrides."
            ),
            (
                "Archive continuity proves only observed source continuity and does "
                "not prove every listing, suspension, or venue-operability state."
            ),
            (
                "One-minute OHLCV does not contain order-book depth or real fills; "
                "execution remains a modeled proxy in the later development run."
            ),
            (
                "This result calculates no signal, trade, P/L, return, expectancy, "
                "profit factor, drawdown, or strategy outcome."
            ),
            (
                "A pass authorizes only the already-frozen 2023-2024 P01 development "
                "run; validation, holdout, Pine, paper, sandbox, and live stay closed."
            ),
        ],
    )


def write_result(
    path: Path,
    result: V2P01FullAcquisitionResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V2P01FullAcquisitionResult.model_validate_json(serialized) != result:
        raise ValueError("P01 acquisition result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale P01 result exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def prepare(args):
    protocol, inputs = load_protocol_inputs(args)
    census_result = inputs[3]
    pilot_result = inputs[5]
    targets = render_targets(
        protocol=protocol,
        census_result=census_result,
    )
    snapshots = collect_metadata_snapshots(
        protocol=protocol,
        evidence_root=args.evidence_root,
    )
    preflight = collect_preflight(
        targets=targets,
        protocol=protocol,
        workers=args.workers,
    )
    enforce_resource_gates(
        protocol=protocol,
        preflight=preflight,
        evidence_root=args.evidence_root,
    )
    return protocol, pilot_result, snapshots, preflight


def run_preflight(args) -> None:
    protocol, _, snapshots, preflight = prepare(args)
    print(
        "PASS P01 preflight only; no archive GET or return calculated "
        f"targets={len(preflight)} "
        f"compressed_bytes={sum(item.content_length for item in preflight)} "
        f"spot_filters={len(snapshots[0].complete_filter_symbols)} "
        f"futures_filters={len(snapshots[1].complete_filter_symbols)} "
        f"protocol={protocol.protocol_evidence_hash}",
        flush=True,
    )


def run_download(args) -> None:
    protocol, pilot_result, _, preflight = prepare(args)
    counts = collect_downloads(
        preflight=preflight,
        protocol=protocol,
        evidence_root=args.evidence_root,
        pilot_result=pilot_result,
        workers=args.workers,
    )
    free_bytes = shutil.disk_usage(
        args.evidence_root / protocol.acquisition.storage_root_relative_path
    ).free
    if free_bytes < protocol.acquisition.minimum_free_disk_bytes_after_processing:
        raise ValueError("P01 free disk fell below the final floor")
    print(
        "PASS P01 download stage; no authoritative result or return written "
        f"counts={counts}",
        flush=True,
    )


def run_full(args) -> V2P01FullAcquisitionResult:
    if args.output.exists():
        raise ValueError("Frozen P01 acquisition result exists; use --audit")
    protocol, pilot_result, snapshots, preflight = prepare(args)
    collect_downloads(
        preflight=preflight,
        protocol=protocol,
        evidence_root=args.evidence_root,
        pilot_result=pilot_result,
        workers=args.workers,
    )
    records = collect_inspections(
        preflight=preflight,
        protocol=protocol,
        evidence_root=args.evidence_root,
        workers=args.workers,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        records=records,
        snapshots=snapshots,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"qualified={result.summary.qualified_symbol_count} "
        f"rows={result.summary.total_rows}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V2P01FullAcquisitionResult:
    protocol, _ = load_protocol_inputs(args)
    result = V2P01FullAcquisitionResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    audit = audit_v2_p01_full_acquisition_result(
        result=result,
        protocol=protocol,
        current_runner_contract_hash=runner_contract_hash(),
        evidence_root=args.evidence_root,
        inspect_local_files=True,
    )
    if audit["status"] != "PASS":
        raise ValueError(f"P01 acquisition audit failed: {audit['reasons']}")
    print(
        "PASS "
        f"v2_p01_acquisition={result.result_evidence_hash} "
        f"qualified={result.summary.qualified_symbol_count} "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Preflight, download, run, or audit the frozen P01 full acquisition."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
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
    parser.add_argument("--charter", type=Path, default=DEFAULT_CHARTER)
    parser.add_argument(
        "--theory-screen",
        type=Path,
        default=DEFAULT_THEORY_SCREEN,
    )
    parser.add_argument(
        "--superseded-contract",
        type=Path,
        default=DEFAULT_SUPERSEDED_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--metadata-contract",
        type=Path,
        default=DEFAULT_METADATA_CONTRACT,
    )
    parser.add_argument(
        "--metadata-result",
        type=Path,
        default=DEFAULT_METADATA_RESULT,
    )
    parser.add_argument(
        "--source-census-contract",
        type=Path,
        default=DEFAULT_SOURCE_CENSUS_CONTRACT,
    )
    parser.add_argument(
        "--source-census-result",
        type=Path,
        default=DEFAULT_SOURCE_CENSUS_RESULT,
    )
    parser.add_argument(
        "--pilot-protocol",
        type=Path,
        default=DEFAULT_PILOT_PROTOCOL,
    )
    parser.add_argument(
        "--pilot-result",
        type=Path,
        default=DEFAULT_PILOT_RESULT,
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.preflight:
            run_preflight(args)
        elif args.download:
            run_download(args)
        elif args.run:
            run_full(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
