from __future__ import annotations

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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_metadata_census import (  # noqa: E402
    PeriodicFlowMetadataCensusContract,
    PeriodicFlowMetadataCensusResult,
    PeriodicFlowMetadataRecord,
    PeriodicFlowMetadataTarget,
    audit_metadata_census_contract,
    audit_metadata_census_result,
    build_metadata_census_result,
)
from aurex.backtest_engine.research_v2_source_census import (  # noqa: E402
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_periodic_flow_metadata_census_contract import (  # noqa: E402
    MODULE_PATH,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_CONTRACT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
)
RUNNER_PATH = Path("scripts/run_periodic_flow_metadata_census.py")
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class ChecksumHttpObservation:
    status: int
    payload: bytes
    checked_at: datetime


FetchOnce = Callable[[str, int, int], ChecksumHttpObservation]
Sleep = Callable[[float], None]


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "source_files": {
                MODULE_PATH.as_posix(): file_sha256(PROJECT_ROOT / MODULE_PATH),
                RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
            }
        }
    )


def load_contract(path: Path) -> PeriodicFlowMetadataCensusContract:
    contract = PeriodicFlowMetadataCensusContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_metadata_census_contract(contract)
        or contract.builder_contract_hash != builder_contract_hash()
        or contract.archive_head_requests_permitted
        or contract.archive_payload_requests_permitted
        or contract.market_numeric_values_permitted
        or not contract.checksum_get_requests_permitted
    ):
        raise ValueError("Frozen Q1 metadata census contract audit failed")
    return contract


def urllib_fetch_checksum(
    url: str,
    timeout: int,
    maximum_bytes: int,
) -> ChecksumHttpObservation:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.binance.vision"
        or not parsed.path.endswith(".zip.CHECKSUM")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Q1 runner refused a non-checksum Binance URL")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain",
            "User-Agent": "Aurex-Q1-Periodic-Flow-Metadata-Census/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(maximum_bytes + 1)
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        return ChecksumHttpObservation(
            status=exc.code,
            payload=b"",
            checked_at=datetime.now(UTC),
        )
    if len(payload) > maximum_bytes:
        raise ValueError(
            f"Checksum response exceeds frozen {maximum_bytes}-byte limit"
        )
    return ChecksumHttpObservation(
        status=status,
        payload=payload,
        checked_at=datetime.now(UTC),
    )


def fetch_metadata_record(
    *,
    target: PeriodicFlowMetadataTarget,
    contract: PeriodicFlowMetadataCensusContract,
    fetch_once: FetchOnce = urllib_fetch_checksum,
    sleep: Sleep = time.sleep,
) -> PeriodicFlowMetadataRecord:
    allowed_urls = {item.checksum_url for item in contract.targets}
    if target.checksum_url not in allowed_urls:
        raise ValueError("Q1 runner refused a URL outside the frozen target matrix")
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
            attempt_count = attempt + 1
            if observation.status == 200:
                if not observation.payload:
                    raise ValueError(
                        f"Empty checksum response: {target.checksum_url}"
                    )
                try:
                    checksum_text = observation.payload.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise ValueError(
                        f"Non-UTF-8 checksum response: {target.checksum_url}"
                    ) from exc
                archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
                archive_hash = parse_v2_checksum_text(
                    checksum_text,
                    archive_name,
                )
                return PeriodicFlowMetadataRecord(
                    **target.model_dump(),
                    checked_at=observation.checked_at,
                    http_status=200,
                    checksum_response_bytes=len(observation.payload),
                    checksum_text=checksum_text,
                    checksum_text_sha256=hashlib.sha256(
                        checksum_text.encode("utf-8")
                    ).hexdigest(),
                    archive_sha256=archive_hash,
                    availability="PRESENT",
                    request_attempt_count=attempt_count,
                )
            if observation.status == 404:
                return PeriodicFlowMetadataRecord(
                    **target.model_dump(),
                    checked_at=observation.checked_at,
                    http_status=404,
                    checksum_response_bytes=0,
                    checksum_text=None,
                    checksum_text_sha256=None,
                    archive_sha256=None,
                    availability="MISSING",
                    request_attempt_count=attempt_count,
                )
            if observation.status not in TRANSIENT_HTTP_STATUS:
                raise RuntimeError(
                    f"Unexpected HTTP {observation.status}: {target.checksum_url}"
                )
            last_error = RuntimeError(
                f"Transient HTTP {observation.status}: {target.checksum_url}"
            )
        if attempt < contract.maximum_retries:
            sleep(contract.retry_backoff_seconds[attempt])
    raise RuntimeError(
        f"Q1 checksum request unresolved after {attempts} attempts: "
        f"{target.checksum_url}"
    ) from last_error


def collect_records(
    *,
    contract: PeriodicFlowMetadataCensusContract,
    workers: int,
) -> tuple[PeriodicFlowMetadataRecord, ...]:
    if not 1 <= workers <= contract.maximum_concurrency:
        raise ValueError("Q1 worker count exceeds the frozen limit")
    records: list[PeriodicFlowMetadataRecord] = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            fetch_metadata_record,
            target=target,
            contract=contract,
        ): target
        for target in contract.targets
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
                    "Q1 metadata census aborted without a result at "
                    f"{target.month}/{target.product}: {type(exc).__name__}: {exc}"
                ) from exc
            if completed % 24 == 0 or completed == len(futures):
                print(
                    f"Q1 checksum observations: {completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return tuple(sorted(records, key=lambda item: item.key))


def authoritative_result(
    *,
    generated_at: datetime,
    contract_path: Path,
    contract: PeriodicFlowMetadataCensusContract,
    records: tuple[PeriodicFlowMetadataRecord, ...],
) -> PeriodicFlowMetadataCensusResult:
    return build_metadata_census_result(
        generated_at=generated_at,
        contract_file_sha256=file_sha256(contract_path),
        contract_evidence_hash=contract.contract_evidence_hash,
        target_manifest_hash=contract.target_manifest_hash,
        schema_register_hash=contract.schema_register_hash,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=(
            "Only frozen Binance .zip.CHECKSUM URLs received GET requests.",
            "No archive HEAD or ZIP payload request was made.",
            "Checksum text proves publication identity, not payload quality or edge.",
            "Documented schemas and timestamp units remain unverified against payloads.",
            "No price, quantity, side, signal, trade, PnL, or return was inspected.",
            "A passing result permits only a separate one-month payload protocol.",
            "No parameter, candidate, Pine, paper, Testnet strategy-order, production, "
            "or live authority is created.",
        ),
    )


def write_result(
    path: Path,
    result: PeriodicFlowMetadataCensusResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if PeriodicFlowMetadataCensusResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 metadata census result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale Q1 metadata result transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_census(args: argparse.Namespace) -> PeriodicFlowMetadataCensusResult:
    if args.output.exists():
        raise ValueError(f"Refusing to overwrite Q1 census result: {args.output}")
    contract = load_contract(args.contract)
    records = collect_records(contract=contract, workers=args.workers)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        contract_path=args.contract,
        contract=contract,
        records=records,
    )
    write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"present={result.summary.present_count}/144 "
        f"paired={result.summary.paired_present_month_count}/72 "
        f"decision={result.decision} payload_requests=0 outcomes=0 orders=0",
        flush=True,
    )
    return result


def check_result(args: argparse.Namespace) -> PeriodicFlowMetadataCensusResult:
    contract = load_contract(args.contract)
    result = PeriodicFlowMetadataCensusResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    expected = authoritative_result(
        generated_at=result.generated_at,
        contract_path=args.contract,
        contract=contract,
        records=result.records,
    )
    if (
        result != expected
        or not audit_metadata_census_result(result)
        or result.contract_file_sha256 != file_sha256(args.contract)
        or result.contract_evidence_hash != contract.contract_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
        or result.unique_checksum_urls_requested
        > contract.maximum_unique_checksum_urls
        or result.checksum_get_requests_made > contract.maximum_http_attempts
        or result.archive_payload_requests_made != 0
        or result.archive_payload_bytes != 0
    ):
        raise ValueError("Stored Q1 census result failed exact reconstruction")
    print(
        f"PASS {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} payload_requests=0 outcomes=0 orders=0",
        flush=True,
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or verify the frozen Q1 checksum-only metadata census."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            check_result(args)
        else:
            run_census(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
