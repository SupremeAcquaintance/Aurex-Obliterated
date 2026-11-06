import argparse
import hashlib
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from aurex.backtest_engine.research_v2_source_census import (
    parse_v2_checksum_text,
)
from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3_P03_REQUIRED_L2_COLUMNS,
    V3P03BookDepthSchemaEvidence,
    V3P03RequirementFinding,
    V3P03SourceArtifact,
    V3P03SourceAuditContract,
    V3P03SourceAuditResult,
    V3P03SourceTarget,
    audit_v3_p03_source_audit_contract,
    audit_v3_p03_source_audit_result,
    build_v3_p03_source_audit_result,
)
from aurex.backtest_engine.research_v3_p03_transport_amendment import (
    V3P03TransportAmendment,
    audit_v3_p03_transport_amendment,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = Path(
    "data/evidence/v3_p03_source_audit_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/v3_p03_source_audit_result_v1.json"
)
DEFAULT_TRANSPORT_AMENDMENT = Path(
    "data/evidence/v3_p03_transport_amendment_v1.json"
)
DEFAULT_SOURCE_DIR = Path(
    "data/evidence/source_snapshots/v3_p03_source_audit_v1"
)
SOURCE_FILENAMES = {
    "BINANCE_PUBLIC_DATA_README": "binance_public_data_readme.md",
    "BINANCE_USDM_ACCOUNT_REST_SCHEMA": "binance_usdm_account_schema.yaml",
    "BINANCE_USDM_LOCAL_ORDER_BOOK_DOC": "binance_local_order_book.html",
    "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_CHECKSUM": (
        "BTCUSDT-bookDepth-2023-01-01.zip.CHECKSUM"
    ),
    "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE": (
        "BTCUSDT-bookDepth-2023-01-01.zip"
    ),
}
SOURCE_MARKERS = {
    "BINANCE_PUBLIC_DATA_README": [
        "# Binance Public Data",
        "### FUTURES",
        "#### AggTrades",
    ],
    "BINANCE_USDM_ACCOUNT_REST_SCHEMA": [
        "/fapi/v1/commissionRate",
        "/fapi/v1/depth",
        "/fapi/v1/order/asyn",
        "makerCommissionRate",
    ],
    "BINANCE_USDM_LOCAL_ORDER_BOOK_DOC": [
        "firstUpdateId",
        "fstream.binance.com",
        "lastUpdateId",
    ],
}


@dataclass(frozen=True, slots=True)
class HttpPayload:
    source_id: str
    observed_at: datetime
    status: int
    content_type: str | None
    payload: bytes
    request_attempt_count: int


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
            / "freeze_v3_p03_source_audit_contract.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def runner_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "run_v3_p03_source_audit.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_source_audit.py",
        ]
    )


def transport_amendment_builder_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT
            / "scripts"
            / "freeze_v3_p03_transport_amendment.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_v3_p03_transport_amendment.py",
        ]
    )


def load_contract(path: Path) -> V3P03SourceAuditContract:
    contract = V3P03SourceAuditContract.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_source_audit_contract(contract)
        or contract.builder_contract_hash != contract_builder_hash()
    ):
        raise ValueError("Frozen V3P03 source audit contract failed audit")
    return contract


def load_transport_amendment(
    path: Path,
    contract: V3P03SourceAuditContract,
) -> V3P03TransportAmendment:
    amendment = V3P03TransportAmendment.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_v3_p03_transport_amendment(amendment)
        or amendment.builder_contract_hash
        != transport_amendment_builder_hash()
        or amendment.original_contract_evidence_hash
        != contract.contract_evidence_hash
    ):
        raise ValueError("Frozen V3P03 transport amendment failed audit")
    return amendment


def fetch_source(
    target: V3P03SourceTarget,
    timeout_seconds: int,
    amendment: V3P03TransportAmendment,
    sleep: Sleep = time.sleep,
) -> HttpPayload:
    maximum_attempts = (
        1 + amendment.maximum_pending_polls
        if target.source_id == amendment.trigger_source_id
        else 1
    )
    for attempt in range(maximum_attempts):
        request = urllib.request.Request(
            target.url,
            headers={
                "Accept": "*/*",
                "User-Agent": "Aurex-V3P03-Source-Audit/1.0",
            },
            method="GET",
        )
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname
            if final_host not in {
                "data.binance.vision",
                "developers.binance.com",
                "raw.githubusercontent.com",
            }:
                raise ValueError(
                    "V3P03 source redirected outside approved domains: "
                    f"{final_url}"
                )
            payload = response.read(target.maximum_response_bytes + 1)
            status = response.getcode()
            content_type = response.headers.get("Content-Type")
        if status == amendment.terminal_success_http_status:
            if not payload:
                raise ValueError(f"Empty V3P03 source response: {target.url}")
            if len(payload) > target.maximum_response_bytes:
                raise ValueError(
                    "V3P03 source exceeds frozen byte limit: "
                    f"{target.source_id}"
                )
            return HttpPayload(
                source_id=target.source_id,
                observed_at=datetime.now(UTC),
                status=status,
                content_type=content_type,
                payload=payload,
                request_attempt_count=attempt + 1,
            )
        pending_allowed = (
            target.source_id == amendment.trigger_source_id
            and status == 202
            and attempt < amendment.maximum_pending_polls
        )
        if not pending_allowed:
            raise RuntimeError(f"Unexpected HTTP {status}: {target.url}")
        sleep(amendment.pending_poll_backoff_seconds[attempt])
    raise RuntimeError(
        f"V3P03 pending source exhausted without HTTP 200: {target.url}"
    )


def matched_markers(source_id: str, payload: bytes) -> list[str]:
    required = SOURCE_MARKERS.get(source_id, [])
    if not required:
        return []
    text = payload.decode("utf-8", errors="replace")
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise ValueError(
            f"V3P03 source markers absent for {source_id}: {missing}"
        )
    return required


def stage_sources(
    *,
    contract: V3P03SourceAuditContract,
    amendment: V3P03TransportAmendment,
    staging_dir: Path,
    final_source_dir: Path,
) -> tuple[list[V3P03SourceArtifact], dict[str, HttpPayload]]:
    staging_dir.mkdir(parents=True, exist_ok=False)
    artifacts = []
    payloads = {}
    total_request_attempts = 0
    for index, target in enumerate(contract.source_targets, start=1):
        observed = fetch_source(
            target,
            contract.request_timeout_seconds,
            amendment,
        )
        total_request_attempts += observed.request_attempt_count
        payloads[target.source_id] = observed
        markers = matched_markers(target.source_id, observed.payload)
        markers.append(
            f"HTTP_REQUEST_ATTEMPTS={observed.request_attempt_count}"
        )
        if target.source_id == amendment.trigger_source_id:
            markers.append(
                "TRANSPORT_AMENDMENT="
                f"{amendment.amendment_evidence_hash}"
            )
        filename = SOURCE_FILENAMES[target.source_id]
        staged_path = staging_dir / filename
        staged_path.write_bytes(observed.payload)
        local_path = (final_source_dir / filename).as_posix()
        artifacts.append(
            V3P03SourceArtifact(
                source_id=target.source_id,
                url=target.url,
                local_path=local_path,
                observed_at=observed.observed_at,
                http_status=200,
                response_bytes=len(observed.payload),
                content_sha256=hashlib.sha256(observed.payload).hexdigest(),
                content_type=observed.content_type,
                matched_markers=markers,
            )
        )
        print(
            f"V3P03 source observations: {index}/{len(contract.source_targets)} "
            f"{target.source_id} bytes={len(observed.payload)} "
            f"attempts={observed.request_attempt_count}",
            flush=True,
        )
    if total_request_attempts > amendment.amended_maximum_http_requests:
        raise ValueError("V3P03 amended HTTP request budget was exceeded")
    return artifacts, payloads


def inspect_bookdepth_schema(
    payloads: dict[str, HttpPayload],
    staging_dir: Path,
) -> V3P03BookDepthSchemaEvidence:
    checksum_id = (
        "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_CHECKSUM"
    )
    archive_id = "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE"
    archive_name = SOURCE_FILENAMES[archive_id]
    checksum_text = payloads[checksum_id].payload.decode("utf-8").strip()
    published_checksum = parse_v2_checksum_text(checksum_text, archive_name)
    archive_path = staging_dir / archive_name
    archive_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if archive_sha256 != published_checksum:
        raise ValueError("V3P03 bookDepth archive checksum verification failed")

    with zipfile.ZipFile(archive_path) as archive:
        members = sorted(
            item.filename
            for item in archive.infolist()
            if not item.is_dir()
        )
        csv_members = [item for item in members if item.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError("V3P03 bookDepth ZIP must contain exactly one CSV")
        selected = csv_members[0]
        with archive.open(selected) as source:
            header_line = source.readline()
            try:
                header_columns = [
                    item.strip()
                    for item in header_line.decode("utf-8-sig").strip().split(",")
                ]
            except UnicodeDecodeError as exc:
                raise ValueError("V3P03 bookDepth header is not UTF-8") from exc
            data_row_count = sum(1 for line in source if line.strip())
    if not header_columns or data_row_count < 1:
        raise ValueError("V3P03 bookDepth schema probe is empty")
    normalized_header = sorted(
        {
            item.strip().lower().replace(" ", "_")
            for item in header_columns
            if item.strip()
        }
    )
    present = sorted(set(normalized_header) & set(V3_P03_REQUIRED_L2_COLUMNS))
    missing = sorted(set(V3_P03_REQUIRED_L2_COLUMNS) - set(normalized_header))
    return V3P03BookDepthSchemaEvidence(
        archive_sha256=archive_sha256,
        published_checksum_sha256=published_checksum,
        archive_member_names=members,
        selected_member_name=selected,
        header_columns=normalized_header,
        data_row_count=data_row_count,
        required_l2_columns_present=present,
        required_l2_columns_missing=missing,
        numeric_market_fields_inspected=[],
    )


def requirement_findings(
    schema: V3P03BookDepthSchemaEvidence,
) -> list[V3P03RequirementFinding]:
    archive = "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE"
    local_book = "BINANCE_USDM_LOCAL_ORDER_BOOK_DOC"
    account_schema = "BINANCE_USDM_ACCOUNT_REST_SCHEMA"
    return [
        V3P03RequirementFinding(
            requirement_id="AGGREGATE_TRADES_2023_2024",
            status="SOURCE_AVAILABLE_PENDING_PAYLOAD_QUALIFICATION",
            qualified=False,
            evidence_source_ids=["V3P02_AGGTRADES_CENSUS_RESULT"],
            finding=(
                "All 744 aggregate-trade checksum targets were published for 31 "
                "symbols, but no aggregate-trade payload has yet passed a separately "
                "frozen schema, timestamp, continuity, and coverage qualification."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id=(
                "DATED_MAKER_TAKER_FEES_AND_REBATES_2023_2024"
            ),
            status="CURRENT_ONLY_NOT_DATED",
            qualified=False,
            evidence_source_ids=[account_schema],
            finding=(
                "The official signed commissionRate endpoint exposes a current "
                "account-and-symbol rate. The frozen schema provides no historical "
                "effective-time query or immutable 2023-2024 fee schedule."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id=(
                "HISTORICAL_MATCHING_QUEUE_STP_RULES_2023_2024"
            ),
            status="CURRENT_ONLY_NOT_DATED",
            qualified=False,
            evidence_source_ids=[account_schema, local_book],
            finding=(
                "The captured documentation describes current stream sequencing and "
                "current API behavior, not a dated immutable history of matching, "
                "price-time priority, queue, and self-trade-prevention rules."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id=(
                "HISTORICAL_TICK_LOT_NOTIONAL_ORDER_LIMITS_2023_2024"
            ),
            status="CURRENT_ONLY_NOT_DATED",
            qualified=False,
            evidence_source_ids=[account_schema],
            finding=(
                "The official schema exposes current exchange information and order "
                "filters but no immutable point-in-time 2023-2024 filter archive."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id="MEASURED_ACK_CANCEL_LATENCY_AND_CLOCK_SYNC",
            status="MISSING_MEASURED_EVIDENCE",
            qualified=False,
            evidence_source_ids=[account_schema, local_book],
            finding=(
                "Protocol documentation cannot supply Aurex-specific historical "
                "network, acknowledgement, cancellation, rejection, and clock-offset "
                "measurements. No immutable measured latency corpus is available."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id="OWN_ORDER_EQUIVALENT_ACK_FILL_CANCEL_REJECT",
            status="OWN_ACCOUNT_ONLY_NOT_COUNTERFACTUAL",
            qualified=False,
            evidence_source_ids=[account_schema],
            finding=(
                "Authenticated order-history endpoints can return actual orders from "
                "an account. They cannot provide acknowledgements, queue positions, "
                "fills, cancels, or rejects for hypothetical historical orders that "
                "Aurex never submitted."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id="QUEUE_RECONSTRUCTION_PRICE_TIME_PRIORITY",
            status="INSUFFICIENT_AGGREGATED_SNAPSHOT",
            qualified=False,
            evidence_source_ids=[archive, local_book],
            finding=(
                "The frozen bookDepth schema probe lacks "
                f"{', '.join(schema.required_l2_columns_missing)}. Aggregated "
                "percentage-band snapshots cannot reconstruct order-level queue "
                "priority or counterfactual position."
            ),
        ),
        V3P03RequirementFinding(
            requirement_id="SEQUENCE_COMPLETE_SUBSECOND_L2_2023_2024",
            status="LIVE_ONLY_NOT_HISTORICAL",
            qualified=False,
            evidence_source_ids=[archive, local_book],
            finding=(
                "The official local-book procedure obtains sequence-aware updates "
                "from a live WebSocket and a current REST snapshot. The historical "
                "bookDepth archive probe contains no first, final, or previous update "
                "IDs and is not sequence-complete subsecond L2."
            ),
        ),
    ]


def authoritative_result(
    *,
    generated_at: datetime,
    contract: V3P03SourceAuditContract,
    source_artifacts: list[V3P03SourceArtifact],
    bookdepth_schema_evidence: V3P03BookDepthSchemaEvidence,
) -> V3P03SourceAuditResult:
    return build_v3_p03_source_audit_result(
        generated_at=generated_at,
        contract_evidence_hash=contract.contract_evidence_hash,
        v3p02_census_result_evidence_hash=(
            contract.v3p02_census_result_evidence_hash
        ),
        runner_contract_hash=runner_contract_hash(),
        source_artifacts=source_artifacts,
        bookdepth_schema_evidence=bookdepth_schema_evidence,
        requirement_findings=requirement_findings(
            bookdepth_schema_evidence
        ),
        limitations=[
            (
                "This audit is a source-and-schema falsification result, not a "
                "backtest and not evidence about passive-market-making returns."
            ),
            (
                "The single bookDepth archive was inspected only for source identity, "
                "checksum, ZIP members, CSV header, and row count."
            ),
            (
                "No price, quantity, percentage depth, notional, signal, fill, trade "
                "outcome, PnL, or return value was parsed or calculated."
            ),
            (
                "A public aggregate depth snapshot cannot substitute for "
                "sequence-complete L2 or market-by-order queue history."
            ),
            (
                "Current documentation and endpoints cannot reconstruct dated "
                "2023-2024 fee, filter, matching, queue, or STP state."
            ),
            (
                "Historical actual account orders cannot reveal counterfactual fills "
                "for orders that did not exist."
            ),
            (
                "Measured latency and clock synchronization are deployment-specific "
                "evidence and are absent from the historical source set."
            ),
            (
                "The rejection selects no alternative primary and grants no "
                "candidate, validation, holdout, forward, Pine, paper, sandbox, live, "
                "or capital permission."
            ),
        ],
    )


def serialized_result(result: V3P03SourceAuditResult) -> str:
    content = result.model_dump_json(indent=2) + "\n"
    if V3P03SourceAuditResult.model_validate_json(content) != result:
        raise ValueError("V3P03 source audit result JSON did not round-trip")
    return content


def run_audit(args) -> V3P03SourceAuditResult:
    if args.output.exists() or args.source_dir.exists():
        raise ValueError("Frozen V3P03 source audit evidence exists; use --audit")
    staging_dir = args.source_dir.with_name(f"{args.source_dir.name}.part")
    result_part = args.output.with_name(f"{args.output.name}.part")
    if staging_dir.exists() or result_part.exists():
        raise ValueError("Stale V3P03 transactional output exists")

    contract = load_contract(args.contract)
    amendment = load_transport_amendment(
        args.transport_amendment,
        contract,
    )
    artifacts, payloads = stage_sources(
        contract=contract,
        amendment=amendment,
        staging_dir=staging_dir,
        final_source_dir=args.source_dir,
    )
    schema = inspect_bookdepth_schema(payloads, staging_dir)
    result = authoritative_result(
        generated_at=datetime.now(UTC),
        contract=contract,
        source_artifacts=artifacts,
        bookdepth_schema_evidence=schema,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result_part.write_text(serialized_result(result), encoding="utf-8")
    staging_dir.replace(args.source_dir)
    result_part.replace(args.output)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"qualified={result.summary.qualified_requirement_count}/8 "
        f"decision={result.decision}",
        flush=True,
    )
    return audit_result(args)


def audit_result(args) -> V3P03SourceAuditResult:
    contract = load_contract(args.contract)
    amendment = load_transport_amendment(
        args.transport_amendment,
        contract,
    )
    result = V3P03SourceAuditResult.model_validate_json(
        args.output.read_text(encoding="utf-8")
    )
    if not audit_v3_p03_source_audit_result(result):
        raise ValueError("V3P03 source audit result hash audit failed")
    if (
        result.contract_evidence_hash != contract.contract_evidence_hash
        or result.v3p02_census_result_evidence_hash
        != contract.v3p02_census_result_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("V3P03 source audit result lineage failed")
    trigger_artifact = next(
        item
        for item in result.source_artifacts
        if item.source_id == amendment.trigger_source_id
    )
    amendment_marker = (
        f"TRANSPORT_AMENDMENT={amendment.amendment_evidence_hash}"
    )
    if amendment_marker not in trigger_artifact.matched_markers:
        raise ValueError("V3P03 transport amendment result binding is absent")
    for artifact in result.source_artifacts:
        path = Path(artifact.local_path)
        if not path.is_file():
            raise ValueError(f"V3P03 source artifact is absent: {path}")
        payload = path.read_bytes()
        if (
            len(payload) != artifact.response_bytes
            or hashlib.sha256(payload).hexdigest()
            != artifact.content_sha256
        ):
            raise ValueError(f"V3P03 source artifact audit failed: {path}")
    rebuilt = authoritative_result(
        generated_at=result.generated_at,
        contract=contract,
        source_artifacts=result.source_artifacts,
        bookdepth_schema_evidence=result.bookdepth_schema_evidence,
    )
    if rebuilt != result:
        raise ValueError("V3P03 source audit result is not reproducible")
    print(
        "PASS "
        f"v3p03_source_audit={result.result_evidence_hash} "
        f"qualified={result.summary.qualified_requirement_count}/8 "
        f"failed={result.summary.failed_requirement_count}/8 "
        f"decision={result.decision} "
        f"returns={result.return_metrics_calculated}",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run or audit the frozen no-return V3P03 historical "
            "microstructure source audit."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--transport-amendment",
        type=Path,
        default=DEFAULT_TRANSPORT_AMENDMENT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.run:
            run_audit(args)
        else:
            audit_result(args)
    except Exception as exc:
        print(f"BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
