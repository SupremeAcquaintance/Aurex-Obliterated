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

from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    RawTradesMetadataCensusProtocol,
    RawTradesMetadataCensusResult,
    RawTradesMetadataProtocolAudit,
    RawTradesMetadataRecord,
    RawTradesMetadataTarget,
    audit_raw_trades_protocol,
    audit_raw_trades_protocol_audit,
    audit_raw_trades_result,
    build_raw_trades_result,
)
from aurex.backtest_engine.research_v2_source_census import (  # noqa: E402
    parse_v2_checksum_text,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.audit_periodic_flow_raw_trades_metadata_protocol import (  # noqa: E402
    DEFAULT_AUDIT as DEFAULT_PROTOCOL_AUDIT,
)
from scripts.audit_periodic_flow_raw_trades_metadata_protocol import (  # noqa: E402
    auditor_contract_hash as protocol_auditor_contract_hash,
)
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (  # noqa: E402
    MODULE_PATH,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_result_v1.json"
)
RUNNER_PATH = Path("scripts/run_periodic_flow_raw_trades_metadata_census.py")
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


def load_protocol(
    protocol_path: Path,
    protocol_audit_path: Path,
) -> tuple[RawTradesMetadataCensusProtocol, RawTradesMetadataProtocolAudit]:
    protocol = RawTradesMetadataCensusProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = RawTradesMetadataProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_raw_trades_protocol(protocol)
        or not audit_raw_trades_protocol_audit(audit)
        or protocol.builder_contract_hash != builder_contract_hash()
        or audit.protocol_file_sha256 != file_sha256(protocol_path)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.builder_contract_hash != protocol.builder_contract_hash
        or audit.auditor_contract_hash != protocol_auditor_contract_hash()
        or not audit.authorizes_checksum_census
        or audit.authorizes_payload
        or audit.authorizes_outcomes
        or audit.authorizes_trading
        or protocol.archive_head_requests_permitted
        or protocol.archive_payload_requests_permitted
        or protocol.market_numeric_values_permitted
        or not protocol.checksum_get_requests_permitted
    ):
        raise ValueError("Frozen Q1 raw-trades protocol or audit is not intact")
    return protocol, audit


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
        or "/futures/um/monthly/trades/BTCUSDT/" not in parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Raw-trades runner refused a non-frozen checksum URL")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/plain",
            "User-Agent": "Aurex-Q1-USD-M-Raw-Trades-Metadata-Census/1.0",
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


def fetch_raw_trades_metadata_record(
    *,
    target: RawTradesMetadataTarget,
    protocol: RawTradesMetadataCensusProtocol,
    fetch_once: FetchOnce = urllib_fetch_checksum,
    sleep: Sleep = time.sleep,
) -> RawTradesMetadataRecord:
    if target.checksum_url not in {item.checksum_url for item in protocol.targets}:
        raise ValueError("Raw-trades runner refused a target outside the protocol")
    last_error: Exception | None = None
    attempts = protocol.maximum_retries + 1
    for attempt in range(attempts):
        try:
            observation = fetch_once(
                target.checksum_url,
                protocol.request_timeout_seconds,
                protocol.maximum_checksum_response_bytes,
            )
        except (OSError, TimeoutError) as exc:
            last_error = exc
        else:
            attempt_count = attempt + 1
            if observation.status == 200:
                if not observation.payload:
                    raise ValueError(f"Empty checksum response: {target.checksum_url}")
                try:
                    checksum_text = observation.payload.decode("utf-8").strip()
                except UnicodeDecodeError as exc:
                    raise ValueError(
                        f"Non-UTF-8 checksum response: {target.checksum_url}"
                    ) from exc
                archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
                archive_hash = parse_v2_checksum_text(checksum_text, archive_name)
                return RawTradesMetadataRecord(
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
                return RawTradesMetadataRecord(
                    **target.model_dump(),
                    checked_at=observation.checked_at,
                    http_status=404,
                    checksum_response_bytes=0,
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
        if attempt < protocol.maximum_retries:
            sleep(protocol.retry_backoff_seconds[attempt])
    raise RuntimeError(
        f"Raw-trades checksum unresolved after {attempts} attempts: "
        f"{target.checksum_url}"
    ) from last_error


def collect_records(
    *,
    protocol: RawTradesMetadataCensusProtocol,
    workers: int,
) -> tuple[RawTradesMetadataRecord, ...]:
    if not 1 <= workers <= protocol.maximum_concurrency:
        raise ValueError("Raw-trades worker count exceeds the frozen limit")
    records: list[RawTradesMetadataRecord] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                fetch_raw_trades_metadata_record,
                target=target,
                protocol=protocol,
            ): target
            for target in protocol.targets
        }
        for future in as_completed(futures):
            records.append(future.result())
    return tuple(sorted(records, key=lambda item: item.month))


def authoritative_result(
    *,
    generated_at: datetime,
    protocol_path: Path,
    protocol_audit_path: Path,
    protocol: RawTradesMetadataCensusProtocol,
    protocol_audit: RawTradesMetadataProtocolAudit,
    records: tuple[RawTradesMetadataRecord, ...],
) -> RawTradesMetadataCensusResult:
    return build_raw_trades_result(
        generated_at=generated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(protocol_audit_path),
        protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        target_manifest_hash=protocol.target_manifest_hash,
        runner_contract_hash=runner_contract_hash(),
        records=records,
        limitations=(
            "Checksum presence establishes archive publication coverage only.",
            "No ZIP, archive member, market row, price, or quantity was requested.",
            "Raw-trade schema, timestamps, continuity, and side semantics remain untested.",
            "Development and validation outcomes remain unopened.",
            "No parameter, threshold, horizon, signal, or strategy was created.",
            "A pass permits only a separately frozen one-month payload protocol.",
            "Paper and Testnet strategy-order authority remain false.",
            "Production, live, real-capital authority, and profit remain false.",
        ),
    )


def write_result(path: Path, result: RawTradesMetadataCensusResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if RawTradesMetadataCensusResult.model_validate_json(serialized) != result:
        raise ValueError("Q1 raw-trades result did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale result transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or verify the frozen Q1 USD-M raw-trades checksum census."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--run", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        protocol, protocol_audit = load_protocol(
            args.protocol, args.protocol_audit
        )
        if args.check:
            stored = RawTradesMetadataCensusResult.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_result(
                generated_at=stored.generated_at,
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
                protocol=protocol,
                protocol_audit=protocol_audit,
                records=stored.records,
            )
            if stored != expected or not audit_raw_trades_result(stored):
                raise ValueError("Stored Q1 raw-trades census result changed")
            print(
                f"PASS {args.output} {stored.result_evidence_hash} "
                f"present={stored.summary.present_count}/72 payloads=0 outcomes=0",
                flush=True,
            )
            return 0

        if args.output.exists():
            raise ValueError(f"Refusing to overwrite census result: {args.output}")
        records = collect_records(protocol=protocol, workers=args.workers)
        result = authoritative_result(
            generated_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            protocol=protocol,
            protocol_audit=protocol_audit,
            records=records,
        )
        write_result(args.output, result)
        print(
            f"WROTE {args.output} {result.result_evidence_hash} "
            f"present={result.summary.present_count}/72 "
            f"development={result.summary.development_present_count}/48 "
            f"validation_metadata={result.summary.validation_metadata_present_count}/24 "
            f"decision={result.decision} payloads=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
