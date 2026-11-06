import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from aurex.backtest_engine.jam_archive_metadata_census import (
    JamArchiveMetadataCensusContract,
    JamArchiveMetadataCensusResult,
    JamArchiveMetadataCheckpoint,
    JamArchiveMetadataRecord,
    JamArchiveMetadataTarget,
    audit_jam_archive_census_contract,
    audit_jam_archive_census_result,
    audit_jam_archive_checkpoint,
    build_jam_archive_census_result,
    build_jam_archive_checkpoint,
)
from aurex.backtest_engine.research_v2_source_census import (
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "data/evidence/jam_archive_metadata_census_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_archive_metadata_census_result_v1.json"
)
DEFAULT_CHECKPOINT = Path(
    "data/evidence/jam_archive_metadata_census_checkpoint_v1.json"
)
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


class RedirectRejectedError(RuntimeError):
    pass


class RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRejectedError(
            f"Jam archive census rejected HTTP redirect {code}: {newurl}"
        )


@dataclass(frozen=True, slots=True)
class ChecksumHttpObservation:
    status: int
    payload: bytes
    checked_at: datetime
    final_url: str


FetchOnce = Callable[[str, int, int], ChecksumHttpObservation]
Sleep = Callable[[float], None]


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


def contract_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_jam_archive_metadata_census_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_metadata_census.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_jam_archive_metadata_census.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_archive_metadata_census.py",
        ]
    )


def load_contract(path: Path) -> JamArchiveMetadataCensusContract:
    contract = JamArchiveMetadataCensusContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_archive_census_contract(contract)
        or contract.builder_contract_hash != contract_builder_hash()
    ):
        raise ValueError("Frozen Jam archive census contract audit failed")
    return contract


def validate_checksum_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/data/spot/monthly/")
        or not parsed.path.endswith(".zip.CHECKSUM")
    ):
        raise ValueError("Jam archive census refused a non-contract checksum URL")


def urllib_fetch_checksum(
    url: str,
    timeout: int,
    maximum_bytes: int,
) -> ChecksumHttpObservation:
    validate_checksum_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain",
            "Accept-Encoding": "identity",
            "User-Agent": "Aurex-Jam-Archive-Metadata-Census/1.0",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(RejectRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            if final_url != url:
                raise RedirectRejectedError(
                    f"Jam archive census final URL changed: {final_url}"
                )
            content_encoding = response.headers.get("Content-Encoding", "")
            if content_encoding.lower() not in {"", "identity"}:
                raise ValueError(
                    "Jam archive census rejected encoded checksum response"
                )
            content_length = response.headers.get("Content-Length")
            if (
                content_length is not None
                and int(content_length) > maximum_bytes
            ):
                raise ValueError(
                    "Jam checksum Content-Length exceeds frozen byte limit"
                )
            payload = response.read(maximum_bytes + 1)
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        final_url = exc.geturl()
        if final_url != url:
            raise RedirectRejectedError(
                f"Jam archive census HTTP error URL changed: {final_url}"
            ) from exc
        return ChecksumHttpObservation(
            status=exc.code,
            payload=b"",
            checked_at=datetime.now(UTC),
            final_url=final_url,
        )
    if len(payload) > maximum_bytes:
        raise ValueError(
            f"Checksum response exceeds frozen {maximum_bytes}-byte limit"
        )
    if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        raise ValueError("Jam archive census rejected ZIP payload bytes")
    return ChecksumHttpObservation(
        status=status,
        payload=payload,
        checked_at=datetime.now(UTC),
        final_url=final_url,
    )


def fetch_census_record(
    *,
    target: JamArchiveMetadataTarget,
    contract: JamArchiveMetadataCensusContract,
    fetch_once: FetchOnce = urllib_fetch_checksum,
    sleep: Sleep = time.sleep,
) -> JamArchiveMetadataRecord:
    attempts = contract.maximum_retries + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            observation = fetch_once(
                target.checksum_url,
                contract.request_timeout_seconds,
                contract.maximum_checksum_response_bytes,
            )
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            request_attempt_count = attempt + 1
            if observation.final_url != target.checksum_url:
                raise RedirectRejectedError(
                    "Jam archive census observation URL changed"
                )
            if observation.status == 200:
                if not observation.payload:
                    raise ValueError(
                        f"Empty checksum response: {target.checksum_url}"
                    )
                if observation.payload.startswith(
                    (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
                ):
                    raise ValueError("Jam archive census rejected ZIP payload bytes")
                try:
                    checksum_text = observation.payload.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError(
                        f"Non-UTF-8 checksum response: {target.checksum_url}"
                    ) from exc
                published_archive_sha256 = parse_v2_checksum_text(
                    checksum_text,
                    target.archive_name,
                )
                return JamArchiveMetadataRecord(
                    family=target.family,
                    month=target.month,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    final_url=observation.final_url,
                    checked_at=observation.checked_at,
                    http_status=200,
                    checksum_response_bytes=len(observation.payload),
                    checksum_text=checksum_text,
                    checksum_response_sha256=hashlib.sha256(
                        observation.payload
                    ).hexdigest(),
                    published_archive_sha256=published_archive_sha256,
                    availability="PRESENT",
                    request_attempt_count=request_attempt_count,
                    redirect_count=0,
                )
            if observation.status == 404:
                return JamArchiveMetadataRecord(
                    family=target.family,
                    month=target.month,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    final_url=observation.final_url,
                    checked_at=observation.checked_at,
                    http_status=404,
                    checksum_response_bytes=0,
                    checksum_text=None,
                    checksum_response_sha256=None,
                    published_archive_sha256=None,
                    availability="MISSING",
                    request_attempt_count=request_attempt_count,
                    redirect_count=0,
                )
            if observation.status not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Unexpected HTTP {observation.status}: "
                    f"{target.checksum_url}"
                )
            last_error = RuntimeError(
                f"Transient HTTP {observation.status}: {target.checksum_url}"
            )
        if attempt < contract.maximum_retries:
            sleep(contract.retry_backoff_seconds[attempt])
    raise RuntimeError(
        f"Jam checksum request unresolved after {attempts} attempts: "
        f"{target.checksum_url}"
    ) from last_error


def write_transactional(path: Path, serialized: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def write_checkpoint(
    *,
    path: Path,
    contract: JamArchiveMetadataCensusContract,
    records: list[JamArchiveMetadataRecord],
) -> JamArchiveMetadataCheckpoint:
    checkpoint = build_jam_archive_checkpoint(
        updated_at=datetime.now(UTC),
        contract_evidence_hash=contract.contract_evidence_hash,
        target_manifest_hash=contract.target_manifest_hash,
        runner_contract_hash=runner_contract_hash(),
        records=records,
    )
    serialized = checkpoint.model_dump_json(indent=2) + "\n"
    if JamArchiveMetadataCheckpoint.model_validate_json(serialized) != checkpoint:
        raise ValueError("Jam archive census checkpoint did not round-trip")
    write_transactional(path, serialized)
    return checkpoint


def load_checkpoint(
    *,
    path: Path,
    contract: JamArchiveMetadataCensusContract,
) -> list[JamArchiveMetadataRecord]:
    if not path.exists():
        return []
    checkpoint = JamArchiveMetadataCheckpoint.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_jam_archive_checkpoint(checkpoint)
        or checkpoint.contract_evidence_hash != contract.contract_evidence_hash
        or checkpoint.target_manifest_hash != contract.target_manifest_hash
        or checkpoint.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Jam archive census checkpoint lineage audit failed")
    return checkpoint.records


def collect_census_records(
    *,
    contract: JamArchiveMetadataCensusContract,
    checkpoint_path: Path,
    workers: int,
) -> list[JamArchiveMetadataRecord]:
    if not 1 <= workers <= contract.maximum_concurrency:
        raise ValueError("Worker count exceeds the frozen concurrency limit")
    records = load_checkpoint(path=checkpoint_path, contract=contract)
    record_keys = {record.key for record in records}
    pending_targets = [
        target for target in contract.targets if target.key not in record_keys
    ]
    if records:
        print(
            f"RESUME Jam checksum observations: "
            f"{len(records)}/{len(contract.targets)}",
            flush=True,
        )
    if not pending_targets:
        return records
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            fetch_census_record,
            target=target,
            contract=contract,
        ): target
        for target in pending_targets
    }
    try:
        for future in as_completed(futures):
            target = futures[future]
            try:
                records.append(future.result())
            except Exception as exc:
                for pending in futures:
                    pending.cancel()
                raise RuntimeError(
                    "Jam archive census aborted without authoritative result at "
                    f"{target.family}/{target.month}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            records.sort(key=lambda item: item.key)
            write_checkpoint(
                path=checkpoint_path,
                contract=contract,
                records=records,
            )
            completed = len(records)
            if completed % 12 == 0 or completed == len(contract.targets):
                print(
                    f"Jam checksum observations: "
                    f"{completed}/{len(contract.targets)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return records


def authoritative_result(
    *,
    generated_at: datetime,
    contract: JamArchiveMetadataCensusContract,
    records: list[JamArchiveMetadataRecord],
) -> JamArchiveMetadataCensusResult:
    return build_jam_archive_census_result(
        generated_at=generated_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        target_manifest_hash=contract.target_manifest_hash,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=[
            (
                "This census requested checksum text only and made zero archive "
                "HEAD or archive payload requests."
            ),
            (
                "Redirects and ZIP signatures were rejected; every accepted final "
                "URL exactly matched its frozen checksum URL."
            ),
            (
                "Published checksums prove archive identity at observation time only; "
                "archive bytes, CSV schema, rows, continuity, and market values "
                "remain uninspected."
            ),
            (
                "HTTP 404 records observed source absence without establishing why "
                "the named monthly archive was unavailable."
            ),
            (
                "No price, quantity, side, feature, parameter, signal, trade, PnL, "
                "return, or strategy outcome was inspected or calculated."
            ),
            (
                "A complete coverage result permits only a request for separate "
                "authorization to freeze a one-month archive payload pilot."
            ),
            (
                "This result creates no candidate, paper eligibility, Testnet "
                "strategy-order authority, production authority, live eligibility, "
                "or capital permission."
            ),
        ],
    )


def write_result(
    path: Path,
    result: JamArchiveMetadataCensusResult,
) -> None:
    serialized = result.model_dump_json(indent=2) + "\n"
    if JamArchiveMetadataCensusResult.model_validate_json(serialized) != result:
        raise ValueError("Jam archive census result JSON did not round-trip")
    write_transactional(path, serialized)


def run_census(args) -> JamArchiveMetadataCensusResult:
    if args.output.exists():
        raise ValueError("Frozen Jam archive census result exists; use --audit")
    contract = load_contract(args.contract)
    records = collect_census_records(
        contract=contract,
        checkpoint_path=args.checkpoint,
        workers=args.workers,
    )
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        contract=contract,
        records=records,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"present={result.summary.present_count} "
        f"attempts={result.summary.checksum_http_attempt_count} "
        f"payload_requests={result.archive_payload_requests_made} "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> JamArchiveMetadataCensusResult:
    contract = load_contract(args.contract)
    result = JamArchiveMetadataCensusResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if not audit_jam_archive_census_result(result):
        raise ValueError("Jam archive census result hash audit failed")
    if (
        result.contract_evidence_hash != contract.contract_evidence_hash
        or result.target_manifest_hash != contract.target_manifest_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Jam archive census result lineage audit failed")
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        contract=contract,
        records=result.records,
    )
    if rebuilt != result:
        raise ValueError("Jam archive census result is not reproducible")
    if (
        result.summary.checksum_http_attempt_count
        > contract.maximum_http_attempts
        or result.summary.checksum_response_bytes
        > contract.maximum_total_checksum_response_bytes
        or result.archive_head_requests_made
        or result.archive_payload_requests_made
        or result.archive_payload_bytes_received
        or result.redirects_followed
    ):
        raise ValueError("Jam archive census exceeded its frozen network boundary")
    print(
        "PASS "
        f"jam_archive_census={result.result_evidence_hash} "
        f"present={result.summary.present_count} "
        f"missing={result.summary.missing_count} "
        f"attempts={result.summary.checksum_http_attempt_count} "
        f"payload_requests={result.archive_payload_requests_made} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen metadata-only Jam successor Binance archive "
            "census."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_census(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
