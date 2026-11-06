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

from aurex.backtest_engine.research_v2_source_census import (
    parse_v2_checksum_text,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3P02AggTradesCensusContract,
    V3P02AggTradesCensusRecord,
    V3P02AggTradesCensusResult,
    V3P02AggTradesTarget,
    audit_v3_p02_census_contract,
    audit_v3_p02_census_result,
    build_v3_p02_census_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "data/evidence/v3_p02_aggtrades_census_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p02_aggtrades_census_result_v1.json"
)
TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class ChecksumHttpObservation:
    status: int
    payload: bytes
    checked_at: datetime


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
            / "freeze_v3_p02_aggtrades_census_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p02_aggtrades_census.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p02_aggtrades_census.py",
        ]
    )


def load_contract(path: Path) -> V3P02AggTradesCensusContract:
    contract = V3P02AggTradesCensusContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p02_census_contract(contract)
        or contract.builder_contract_hash != contract_builder_hash()
    ):
        raise ValueError("Frozen V3P02 census contract audit failed")
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
    ):
        raise ValueError("V3P02 runner refused a non-contract checksum URL")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain",
            "User-Agent": "Aurex-V3P02-Checksum-Census/1.0",
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


def fetch_census_record(
    *,
    target: V3P02AggTradesTarget,
    contract: V3P02AggTradesCensusContract,
    fetch_once: FetchOnce = urllib_fetch_checksum,
    sleep: Sleep = time.sleep,
) -> V3P02AggTradesCensusRecord:
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
                archive_name = Path(urlparse(target.archive_url).path).name
                checksum_sha256 = parse_v2_checksum_text(
                    checksum_text,
                    archive_name,
                )
                return V3P02AggTradesCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=observation.checked_at,
                    http_status=200,
                    checksum_response_bytes=len(observation.payload),
                    checksum_sha256=checksum_sha256,
                    availability="PRESENT",
                    request_attempt_count=request_attempt_count,
                )
            if observation.status == 404:
                return V3P02AggTradesCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=observation.checked_at,
                    http_status=404,
                    checksum_response_bytes=0,
                    checksum_sha256=None,
                    availability="MISSING",
                    request_attempt_count=request_attempt_count,
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
        f"V3P02 checksum request unresolved after {attempts} attempts: "
        f"{target.checksum_url}"
    ) from last_error


def authoritative_result(
    *,
    generated_at: datetime,
    contract: V3P02AggTradesCensusContract,
    records: list[V3P02AggTradesCensusRecord],
) -> V3P02AggTradesCensusResult:
    return build_v3_p02_census_result(
        generated_at=generated_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        target_manifest_hash=contract.target_manifest_hash,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=[
            (
                "This metadata-only census requested checksum text and did not request "
                "or inspect any aggregate-trade archive payload."
            ),
            (
                "A valid checksum is publication evidence for the named archive at "
                "observation time; payload bytes, schema, rows, timestamp continuity, "
                "and numeric values remain unverified."
            ),
            (
                "HTTP 404 preserves observed source absence without establishing the "
                "reason for that absence."
            ),
            (
                "Historical archive availability does not establish point-in-time "
                "metadata completeness, execution feasibility, predictive edge, "
                "capacity, or profitability."
            ),
            (
                "The census calculated no signal, trade, PnL, strategy, or return "
                "metric and did not inspect price, quantity, or buyer-maker values."
            ),
            (
                "A passing decision permits only a separately frozen payload pilot "
                "protocol and grants no primary selection, candidate, validation, "
                "holdout, forward, Pine, paper, sandbox, live, or capital permission."
            ),
        ],
    )


def write_result(path: Path, result: V3P02AggTradesCensusResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if V3P02AggTradesCensusResult.model_validate_json(serialized) != result:
        raise ValueError("V3P02 census result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional output exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def collect_census_records(
    *,
    contract: V3P02AggTradesCensusContract,
    workers: int,
) -> list[V3P02AggTradesCensusRecord]:
    if not 1 <= workers <= contract.maximum_concurrency:
        raise ValueError("Worker count exceeds the frozen concurrency limit")
    records: list[V3P02AggTradesCensusRecord] = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(
            fetch_census_record,
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
                    "V3P02 census aborted without authoritative result at "
                    f"{target.symbol}/{target.month}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            if completed % 100 == 0 or completed == len(futures):
                print(
                    f"V3P02 checksum observations: "
                    f"{completed}/{len(futures)}",
                    flush=True,
                )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return records


def run_census(args) -> V3P02AggTradesCensusResult:
    if args.output.exists():
        raise ValueError("Frozen V3P02 census result exists; use --audit")
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
        f"present={result.summary.present_count} "
        f"complete_symbols={result.summary.complete_symbol_count} "
        f"attempts={result.summary.http_attempt_count} "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V3P02AggTradesCensusResult:
    contract = load_contract(args.contract)
    result = V3P02AggTradesCensusResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if not audit_v3_p02_census_result(result):
        raise ValueError("V3P02 census result hash audit failed")
    if (
        result.contract_evidence_hash != contract.contract_evidence_hash
        or result.target_manifest_hash != contract.target_manifest_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("V3P02 census result lineage audit failed")
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        contract=contract,
        records=result.records,
    )
    if rebuilt != result:
        raise ValueError("V3P02 census result is not reproducible")
    if (
        result.summary.http_attempt_count > contract.maximum_http_attempts
        or len(result.records) > contract.maximum_unique_checksum_urls
    ):
        raise ValueError("V3P02 census request budget was exceeded")
    print(
        "PASS "
        f"v3p02_census={result.result_evidence_hash} "
        f"present={result.summary.present_count} "
        f"missing={result.summary.missing_count} "
        f"complete_symbols={result.summary.complete_symbol_count} "
        f"attempts={result.summary.http_attempt_count} "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen metadata-only V3P02 aggregate-trade census."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
