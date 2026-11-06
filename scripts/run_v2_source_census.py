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

from aurex.backtest_engine.research_v2_source_census import (
    V2SourceCensusRecord,
    V2SourceCensusResult,
    V2SourceCensusTarget,
    audit_v2_source_census_result,
    build_v2_source_census_result,
    parse_v2_checksum_text,
    render_v2_source_census_targets,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2SourceCensusContract,
    audit_v2_source_census_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash

DEFAULT_CONTRACT = Path(
    "data/evidence/v2_derivatives_source_census_contract_v1.json"
)
DEFAULT_OUTPUT = Path("data/evidence/v2_derivatives_source_census_result_v1.json")
MAX_CHECKSUM_BYTES = 4096
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class ChecksumHttpObservation:
    status: int
    payload: bytes
    checked_at: datetime


FetchOnce = Callable[[str, int], ChecksumHttpObservation]
Sleep = Callable[[float], None]


def runner_contract_hash() -> str:
    project_root = Path(__file__).resolve().parents[1]
    paths = [
        project_root / "scripts" / "run_v2_source_census.py",
        project_root
        / "src"
        / "aurex"
        / "backtest_engine"
        / "research_v2_source_census.py",
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


def load_contract(path: Path) -> V2SourceCensusContract:
    contract = V2SourceCensusContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if not audit_v2_source_census_contract(contract):
        raise ValueError("Frozen V2 source census contract audit failed")
    return contract


def urllib_fetch_checksum(url: str, timeout: int) -> ChecksumHttpObservation:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain",
            "User-Agent": "Aurex-V2-Source-Census/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_CHECKSUM_BYTES + 1)
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        return ChecksumHttpObservation(
            status=exc.code,
            payload=b"",
            checked_at=datetime.now(UTC),
        )
    if len(payload) > MAX_CHECKSUM_BYTES:
        raise ValueError(f"Checksum response exceeds {MAX_CHECKSUM_BYTES} bytes")
    return ChecksumHttpObservation(
        status=status,
        payload=payload,
        checked_at=datetime.now(UTC),
    )


def fetch_census_record(
    *,
    target: V2SourceCensusTarget,
    contract: V2SourceCensusContract,
    fetch_once: FetchOnce = urllib_fetch_checksum,
    sleep: Sleep = time.sleep,
) -> V2SourceCensusRecord:
    attempts = contract.maximum_retries + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            observation = fetch_once(
                target.checksum_url,
                contract.request_timeout_seconds,
            )
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            if observation.status == 200:
                try:
                    checksum_text = observation.payload.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise ValueError(
                        f"Non-UTF-8 checksum response: {target.checksum_url}"
                    ) from exc
                checksum_sha256 = parse_v2_checksum_text(
                    checksum_text,
                    target.archive_name,
                )
                return V2SourceCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    family_id=target.family_id,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=observation.checked_at,
                    checksum_http_status=200,
                    checksum_text=f"{checksum_sha256}  {target.archive_name}",
                    checksum_sha256=checksum_sha256,
                )
            if observation.status == 404:
                return V2SourceCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    family_id=target.family_id,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=observation.checked_at,
                    checksum_http_status=404,
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
        f"V2 checksum request unresolved after {attempts} attempts: "
        f"{target.checksum_url}"
    ) from last_error


def authoritative_result(
    *,
    generated_at: datetime,
    contract: V2SourceCensusContract,
    records: list[V2SourceCensusRecord],
) -> V2SourceCensusResult:
    return build_v2_source_census_result(
        generated_at=generated_at,
        contract=contract,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=[
            (
                "A valid checksum file is evidence that the named official archive "
                "was published at observation time; this census does not verify ZIP "
                "bytes or numeric contents."
            ),
            (
                "An HTTP 404 preserves observed source unavailability but does not "
                "establish why an archive is absent."
            ),
            (
                "Historical archive coverage does not establish data correctness, "
                "future availability, liquidity, execution quality, or profitability."
            ),
            (
                "The census downloads checksum text only and makes no archive-payload "
                "request, market-data import, return calculation, or strategy choice."
            ),
            (
                "A passing census permits only a separately frozen acquisition "
                "protocol; it creates no strategy, paper, sandbox, or live eligibility."
            ),
        ],
    )


def write_result(path: Path, result: V2SourceCensusResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V2SourceCensusResult.model_validate_json(serialized) != result:
        raise ValueError("V2 source census result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def collect_census_records(
    *,
    contract: V2SourceCensusContract,
    workers: int,
) -> list[V2SourceCensusRecord]:
    if workers > contract.maximum_concurrency:
        raise ValueError("Worker count exceeds the frozen concurrency limit")
    targets = render_v2_source_census_targets(contract)
    records: list[V2SourceCensusRecord] = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            fetch_census_record,
            target=target,
            contract=contract,
        ): target
        for target in targets
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
                    "V2 census aborted without result at "
                    f"{target.symbol}/{target.month}/{target.family_id}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            if completed % 250 == 0 or completed == len(targets):
                print(
                    f"V2 checksum observations: {completed}/{len(targets)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return records


def run_census(args) -> V2SourceCensusResult:
    if args.output.exists():
        raise ValueError("Frozen V2 source census result exists; use --audit")
    contract = load_contract(args.contract)
    records = collect_census_records(
        contract=contract,
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
        f"complete_symbols={result.summary.complete_symbol_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V2SourceCensusResult:
    contract = load_contract(args.contract)
    result = V2SourceCensusResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    audit = audit_v2_source_census_result(
        result=result,
        contract=contract,
        current_runner_contract_hash=runner_contract_hash(),
    )
    if audit["status"] != "PASS":
        raise ValueError(f"V2 source census audit failed: {audit['reasons']}")
    print(
        "PASS "
        f"v2_source_census={result.result_evidence_hash} "
        f"present={result.summary.present_observations} "
        f"missing={result.summary.missing_observations} "
        f"complete_symbols={result.summary.complete_symbol_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen metadata-only V2 derivatives source census."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
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
