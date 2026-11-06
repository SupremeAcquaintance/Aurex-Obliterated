from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import urlsplit

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2AcquisitionTarget,
    V2DerivativesAcquisitionProtocol,
    audit_v2_derivatives_acquisition_protocol,
)
from aurex.backtest_engine.research_v2_pilot_acquisition import (
    V2PilotAcquisitionResult,
    V2PilotArchiveEvidence,
    audit_v2_pilot_acquisition_result,
    build_v2_pilot_acquisition_result,
    inspect_v2_pilot_archive,
)
from aurex.backtest_engine.research_v2_source_census import (
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_PROTOCOL = Path(
    "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
)
DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_OUTPUT = Path(
    "data/evidence/v2_derivatives_pilot_acquisition_result_v1.json"
)
MAX_CHECKSUM_BYTES = 4096
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class V2PilotPreflight:
    target: V2AcquisitionTarget
    checksum_checked_at: datetime
    preflight_checked_at: datetime
    content_length: int
    last_modified: str | None
    etag: str | None


def runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_acquisition_pilot.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_pilot_acquisition.py",
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


def load_protocol(path: Path) -> V2DerivativesAcquisitionProtocol:
    protocol = V2DerivativesAcquisitionProtocol.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_v2_derivatives_acquisition_protocol(protocol):
        raise ValueError("V2 pilot acquisition protocol audit failed")
    return protocol


def _request(
    *,
    url: str,
    method: str,
    timeout: int,
):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Aurex-V2-Acquisition-Pilot/1.0"},
        method=method,
    )
    return urllib.request.urlopen(request, timeout=timeout)


def _retry_delay(protocol: V2DerivativesAcquisitionProtocol, attempt: int) -> None:
    time.sleep(protocol.resource_limits.retry_backoff_seconds[attempt])


def _fetch_refreshed_checksum(
    *,
    target: V2AcquisitionTarget,
    protocol: V2DerivativesAcquisitionProtocol,
) -> datetime:
    last_error: Exception | None = None
    attempts = protocol.resource_limits.maximum_retries + 1
    for attempt in range(attempts):
        try:
            with _request(
                url=target.checksum_url,
                method="GET",
                timeout=protocol.resource_limits.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                payload = response.read(MAX_CHECKSUM_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"V2 pilot checksum HTTP {exc.code}: {target.checksum_url}"
                ) from exc
            last_error = exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            if status != 200:
                raise RuntimeError(
                    f"V2 pilot checksum HTTP {status}: {target.checksum_url}"
                )
            if len(payload) > MAX_CHECKSUM_BYTES:
                raise ValueError("V2 pilot checksum exceeds 4096 bytes")
            try:
                checksum_text = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("V2 pilot checksum is not UTF-8") from exc
            archive_name = PurePosixPath(
                urlsplit(target.archive_url).path
            ).name
            refreshed = parse_v2_checksum_text(checksum_text, archive_name)
            if refreshed != target.census_checksum_sha256:
                raise ValueError(
                    "V2 pilot checksum changed after the source census: "
                    f"{target.key}"
                )
            return datetime.now(UTC)
        if attempt < protocol.resource_limits.maximum_retries:
            _retry_delay(protocol, attempt)
    raise RuntimeError(
        f"V2 pilot checksum unresolved after {attempts} attempts: {target.key}"
    ) from last_error


def _fetch_archive_head(
    *,
    target: V2AcquisitionTarget,
    protocol: V2DerivativesAcquisitionProtocol,
) -> tuple[datetime, int, str | None, str | None]:
    last_error: Exception | None = None
    attempts = protocol.resource_limits.maximum_retries + 1
    for attempt in range(attempts):
        try:
            with _request(
                url=target.archive_url,
                method="HEAD",
                timeout=protocol.resource_limits.request_timeout_seconds,
            ) as response:
                status = response.getcode()
                content_length_text = response.headers.get("Content-Length")
                last_modified = response.headers.get("Last-Modified")
                etag = response.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"V2 pilot archive HEAD HTTP {exc.code}: {target.archive_url}"
                ) from exc
            last_error = exc
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            if status != 200:
                raise RuntimeError(
                    f"V2 pilot archive HEAD HTTP {status}: {target.archive_url}"
                )
            if content_length_text is None:
                raise ValueError(
                    f"V2 pilot archive has no Content-Length: {target.key}"
                )
            try:
                content_length = int(content_length_text)
            except ValueError as exc:
                raise ValueError(
                    f"V2 pilot archive Content-Length is invalid: {target.key}"
                ) from exc
            if content_length <= 0:
                raise ValueError(
                    f"V2 pilot archive Content-Length is not positive: {target.key}"
                )
            return datetime.now(UTC), content_length, last_modified, etag
        if attempt < protocol.resource_limits.maximum_retries:
            _retry_delay(protocol, attempt)
    raise RuntimeError(
        f"V2 pilot archive HEAD unresolved after {attempts} attempts: {target.key}"
    ) from last_error


def preflight_target(
    *,
    target: V2AcquisitionTarget,
    protocol: V2DerivativesAcquisitionProtocol,
) -> V2PilotPreflight:
    checksum_checked_at = _fetch_refreshed_checksum(
        target=target,
        protocol=protocol,
    )
    checked_at, content_length, last_modified, etag = _fetch_archive_head(
        target=target,
        protocol=protocol,
    )
    if content_length > (
        protocol.resource_limits.maximum_single_archive_compressed_bytes
    ):
        raise ValueError(f"V2 pilot archive exceeds its byte ceiling: {target.key}")
    return V2PilotPreflight(
        target=target,
        checksum_checked_at=checksum_checked_at,
        preflight_checked_at=checked_at,
        content_length=content_length,
        last_modified=last_modified,
        etag=etag,
    )


def collect_preflight(
    *,
    protocol: V2DerivativesAcquisitionProtocol,
    workers: int,
) -> list[V2PilotPreflight]:
    observations = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            preflight_target,
            target=target,
            protocol=protocol,
        ): target
        for target in protocol.targets
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
                    "V2 pilot preflight aborted without result at "
                    f"{target.key}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 9 == 0 or completed == len(futures):
                print(
                    f"V2 pilot preflight: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(observations, key=lambda item: item.target.key)


def enforce_aggregate_resource_gates(
    *,
    protocol: V2DerivativesAcquisitionProtocol,
    preflight: list[V2PilotPreflight],
    storage_root: Path,
) -> None:
    if len(preflight) != protocol.pilot_target_count:
        raise ValueError("V2 pilot preflight matrix is incomplete")
    total_bytes = sum(item.content_length for item in preflight)
    if total_bytes > protocol.resource_limits.maximum_pilot_compressed_bytes:
        raise ValueError("V2 pilot preflight exceeds the compressed-byte ceiling")
    storage_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(storage_root).free
    if free_bytes < (
        protocol.resource_limits.minimum_free_disk_bytes_before_download
    ):
        raise ValueError("V2 pilot free disk is below the pre-download floor")
    if free_bytes - total_bytes < (
        protocol.resource_limits.minimum_free_disk_bytes_after_processing
    ):
        raise ValueError("V2 pilot projected free disk is below the final floor")
    print(
        "V2 pilot resource gate PASS "
        f"compressed_bytes={total_bytes} free_bytes={free_bytes}",
        flush=True,
    )


def target_paths(
    *,
    evidence_root: Path,
    protocol: V2DerivativesAcquisitionProtocol,
    target: V2AcquisitionTarget,
) -> tuple[Path, Path]:
    archive_name = PurePosixPath(urlsplit(target.archive_url).path).name
    directory = (
        evidence_root
        / protocol.storage_root_relative_path
        / "archives"
        / target.family_id
        / target.symbol
    )
    archive_path = directory / archive_name
    return archive_path, Path(f"{archive_path}.CHECKSUM")


def _stream_response_to_file(
    response: BinaryIO,
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
            if downloaded > maximum_bytes or downloaded > expected_bytes:
                raise ValueError("V2 pilot archive exceeded its preflight size")
            destination.write(chunk)
            digest.update(chunk)
    if downloaded != expected_bytes:
        raise ValueError("V2 pilot archive size differs from preflight")
    return digest.hexdigest()


def _download_archive_once(
    *,
    preflight: V2PilotPreflight,
    protocol: V2DerivativesAcquisitionProtocol,
    archive_path: Path,
) -> None:
    temporary = archive_path.with_name(f"{archive_path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale V2 pilot download exists: {temporary}")
    try:
        with _request(
            url=preflight.target.archive_url,
            method="GET",
            timeout=protocol.resource_limits.request_timeout_seconds,
        ) as response:
            if response.getcode() != 200:
                raise RuntimeError(
                    f"V2 pilot archive GET HTTP {response.getcode()}: "
                    f"{preflight.target.key}"
                )
            observed_length = response.headers.get("Content-Length")
            if observed_length is None or int(observed_length) != (
                preflight.content_length
            ):
                raise ValueError(
                    "V2 pilot GET Content-Length changed after preflight"
                )
            observed_sha256 = _stream_response_to_file(
                response,
                temporary=temporary,
                expected_bytes=preflight.content_length,
                maximum_bytes=(
                    protocol.resource_limits.maximum_single_archive_compressed_bytes
                ),
            )
        if observed_sha256 != preflight.target.census_checksum_sha256:
            raise ValueError("V2 pilot archive checksum does not match the census")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(archive_path)


def ensure_verified_archive(
    *,
    preflight: V2PilotPreflight,
    protocol: V2DerivativesAcquisitionProtocol,
    archive_path: Path,
    checksum_path: Path,
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_bytes = (
        f"{preflight.target.census_checksum_sha256}  {archive_path.name}\n".encode()
    )
    if archive_path.exists():
        if (
            archive_path.stat().st_size != preflight.content_length
            or file_sha256(archive_path)
            != preflight.target.census_checksum_sha256
        ):
            raise ValueError(
                f"Existing V2 pilot archive conflicts: {preflight.target.key}"
            )
    else:
        last_error: Exception | None = None
        attempts = protocol.resource_limits.maximum_retries + 1
        for attempt in range(attempts):
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
            if attempt < protocol.resource_limits.maximum_retries:
                _retry_delay(protocol, attempt)
        else:
            raise RuntimeError(
                f"V2 pilot archive GET unresolved: {preflight.target.key}"
            ) from last_error
    if checksum_path.exists():
        if checksum_path.read_bytes() != checksum_bytes:
            raise ValueError(
                f"Existing V2 pilot checksum conflicts: {preflight.target.key}"
            )
    else:
        checksum_temporary = checksum_path.with_name(
            f"{checksum_path.name}.part"
        )
        if checksum_temporary.exists():
            raise ValueError(
                f"Stale V2 pilot checksum exists: {checksum_temporary}"
            )
        checksum_temporary.write_bytes(checksum_bytes)
        checksum_temporary.replace(checksum_path)


def acquire_and_inspect_target(
    *,
    preflight: V2PilotPreflight,
    protocol: V2DerivativesAcquisitionProtocol,
    evidence_root: Path,
) -> V2PilotArchiveEvidence:
    archive_path, checksum_path = target_paths(
        evidence_root=evidence_root,
        protocol=protocol,
        target=preflight.target,
    )
    ensure_verified_archive(
        preflight=preflight,
        protocol=protocol,
        archive_path=archive_path,
        checksum_path=checksum_path,
    )
    return inspect_v2_pilot_archive(
        target=preflight.target,
        archive_path=archive_path,
        checksum_path=checksum_path,
        evidence_root=evidence_root,
        checksum_checked_at=preflight.checksum_checked_at,
        preflight_checked_at=preflight.preflight_checked_at,
        archive_content_length=preflight.content_length,
        archive_last_modified=preflight.last_modified,
        archive_etag=preflight.etag,
        protocol=protocol,
    )


def collect_archive_evidence(
    *,
    protocol: V2DerivativesAcquisitionProtocol,
    preflight: list[V2PilotPreflight],
    evidence_root: Path,
    workers: int,
) -> list[V2PilotArchiveEvidence]:
    records = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            acquire_and_inspect_target,
            preflight=observation,
            protocol=protocol,
            evidence_root=evidence_root,
        ): observation.target
        for observation in preflight
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
                    "V2 pilot acquisition aborted without result at "
                    f"{target.key}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 6 == 0 or completed == len(futures):
                print(
                    f"V2 pilot archives verified: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return sorted(records, key=lambda item: item.key)


def authoritative_result(
    *,
    generated_at: datetime,
    protocol: V2DerivativesAcquisitionProtocol,
    records: list[V2PilotArchiveEvidence],
) -> V2PilotAcquisitionResult:
    return build_v2_pilot_acquisition_result(
        generated_at=generated_at,
        protocol=protocol,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=[
            (
                "The pilot covers only three deterministic symbols and three "
                "deterministic months; it is a schema/resource sample, not a "
                "complete derivatives dataset."
            ),
            (
                "Checksum and ZIP integrity do not establish point-in-time contract "
                "metadata, fee schedules, executable spread, slippage, or liquidity."
            ),
            (
                "Structural inspection validates files, schemas, timestamps, and "
                "finite values but calculates no return, signal, trade, or outcome."
            ),
            (
                "A passing pilot permits only a separately frozen full-acquisition "
                "protocol and does not authorize any additional archive automatically."
            ),
            (
                "The pilot does not establish funding settlement, paired execution, "
                "collateral, margin, liquidation, ADL, or reconciliation correctness."
            ),
            (
                "No pilot result creates candidate, backtest, paper, sandbox, "
                "micro-live, live, or capital eligibility."
            ),
        ],
    )


def write_result(path: Path, result: V2PilotAcquisitionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V2PilotAcquisitionResult.model_validate_json(serialized) != result:
        raise ValueError("V2 pilot result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional result exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def run_pilot(args) -> V2PilotAcquisitionResult:
    if args.output.exists():
        raise ValueError("Frozen V2 pilot result exists; use --audit")
    protocol = load_protocol(args.protocol)
    if args.workers > protocol.resource_limits.maximum_concurrency:
        raise ValueError("Worker count exceeds the V2 pilot protocol")
    storage_root = args.evidence_root / protocol.storage_root_relative_path
    preflight = collect_preflight(protocol=protocol, workers=args.workers)
    enforce_aggregate_resource_gates(
        protocol=protocol,
        preflight=preflight,
        storage_root=storage_root,
    )
    records = collect_archive_evidence(
        protocol=protocol,
        preflight=preflight,
        evidence_root=args.evidence_root,
        workers=args.workers,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        protocol=protocol,
        records=records,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"archive_bytes={result.summary.total_archive_bytes} "
        f"rows={result.summary.total_rows}",
        flush=True,
    )
    return audit_result(args)


def run_preflight_only(args) -> list[V2PilotPreflight]:
    protocol = load_protocol(args.protocol)
    if args.workers > protocol.resource_limits.maximum_concurrency:
        raise ValueError("Worker count exceeds the V2 pilot protocol")
    storage_root = args.evidence_root / protocol.storage_root_relative_path
    preflight = collect_preflight(protocol=protocol, workers=args.workers)
    enforce_aggregate_resource_gates(
        protocol=protocol,
        preflight=preflight,
        storage_root=storage_root,
    )
    print(
        "PASS V2 pilot preflight only; no archive payload requested "
        f"targets={len(preflight)} "
        f"compressed_bytes={sum(item.content_length for item in preflight)}",
        flush=True,
    )
    return preflight


def audit_result(args) -> V2PilotAcquisitionResult:
    protocol = load_protocol(args.protocol)
    result = V2PilotAcquisitionResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    audit = audit_v2_pilot_acquisition_result(
        result=result,
        protocol=protocol,
        current_runner_contract_hash=runner_contract_hash(),
        evidence_root=args.evidence_root,
        inspect_local_archives=True,
    )
    if audit["status"] != "PASS":
        raise ValueError(f"V2 pilot result audit failed: {audit['reasons']}")
    print(
        "PASS "
        f"v2_pilot={result.result_evidence_hash} "
        f"targets={result.summary.target_count} "
        f"archive_bytes={result.summary.total_archive_bytes} "
        f"rows={result.summary.total_rows} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen 54-target V2 derivatives acquisition pilot."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
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
            run_preflight_only(args)
        elif args.run:
            run_pilot(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
