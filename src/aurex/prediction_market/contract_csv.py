import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.domain.enums import PredictionMarketStatus, PredictionMarketVenue
from aurex.prediction_market.paper import (
    PredictionContractSnapshot,
    PredictionMarketPaperEngine,
)
from aurex.prediction_market.schemas import PredictionContractSnapshotCsvRequest

AUREX_CONTRACT_SNAPSHOT_HEADERS = [
    "venue",
    "event_ticker",
    "market_title",
    "contract_ticker",
    "contract_title",
    "category",
    "status",
    "yes_bid_price",
    "yes_ask_price",
    "no_bid_price",
    "no_ask_price",
    "settlement_value",
    "closes_at",
    "expiration_at",
    "observed_at",
]

MKT_MARKETS_HEADERS = [
    "ticker",
    "event_ticker",
    "title",
    "yes_sub_title",
    "category",
    "status",
    "close_time",
    "yes_bid",
    "yes_ask",
    "result",
    "settlement_value",
    "last_updated",
]


@dataclass(frozen=True)
class ParsedContractSnapshotRow:
    row_number: int
    observed_at: datetime
    snapshot: PredictionContractSnapshot


class PredictionContractSnapshotCsvImporter:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight_csv(self, payload: PredictionContractSnapshotCsvRequest) -> dict[str, object]:
        headers, rows = read_csv_rows(payload.csv_text)
        csv_format = resolve_csv_format(headers, payload.csv_format)
        validate_headers(headers, csv_format)
        row_results, parsed_rows = prepare_rows(payload, csv_format, rows)
        row_results.extend(ready_row_result(parsed) for parsed in parsed_rows)
        row_results.sort(key=lambda item: int(item["row_number"]))
        importable_count = count_status(row_results, "READY")
        rejected_count = count_status(row_results, "REJECTED")
        return {
            "source": payload.source.strip(),
            "source_reference": payload.source_reference.strip(),
            "csv_format": csv_format,
            "import_hash": build_import_hash(payload),
            "status": preflight_status(len(rows), importable_count, rejected_count),
            "rows_received": len(rows),
            "importable_count": importable_count,
            "rejected_count": rejected_count,
            "required_headers": required_headers_for_format(csv_format),
            "row_results": row_results,
            "analysis_summary": analysis_summary(row_results, parsed_rows),
            "checked_at": utc_now(),
        }

    def import_csv(self, payload: PredictionContractSnapshotCsvRequest) -> dict[str, object]:
        headers, rows = read_csv_rows(payload.csv_text)
        csv_format = resolve_csv_format(headers, payload.csv_format)
        validate_headers(headers, csv_format)
        row_results, parsed_rows = prepare_rows(payload, csv_format, rows)

        imported_contract_ids: list[str] = []
        engine = PredictionMarketPaperEngine(self.session)
        for parsed in sorted(parsed_rows, key=lambda item: (item.observed_at, item.row_number)):
            contract = engine.upsert_contract_snapshot(parsed.snapshot, now=parsed.observed_at)
            imported_contract_ids.append(contract.id)

        row_results.extend(ready_row_result(parsed) for parsed in parsed_rows)
        row_results.sort(key=lambda item: int(item["row_number"]))
        imported_count = len(parsed_rows)
        rejected_count = count_status(row_results, "REJECTED")
        status = import_status(len(rows), imported_count, rejected_count)
        return {
            "source": payload.source.strip(),
            "source_reference": payload.source_reference.strip(),
            "csv_format": csv_format,
            "import_hash": build_import_hash(payload),
            "status": status,
            "rows_received": len(rows),
            "imported_count": imported_count,
            "rejected_count": rejected_count,
            "contract_ids": imported_contract_ids,
            "row_results": row_results,
            "analysis_summary": analysis_summary(row_results, parsed_rows),
            "imported_at": utc_now(),
        }


def read_csv_rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    headers = [str(header or "").strip() for header in (reader.fieldnames or [])]
    rows = [
        {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        for row in reader
    ]
    if not headers:
        raise ValueError("CSV header row is required.")
    return headers, rows


def resolve_csv_format(headers: list[str], requested: str) -> str:
    requested = requested.strip().lower()
    if requested != "auto":
        return requested
    normalized = {header.lower() for header in headers}
    if "contract_ticker" in normalized:
        return "aurex"
    if "ticker" in normalized:
        return "mkt_markets"
    return "aurex"


def validate_headers(headers: list[str], csv_format: str) -> None:
    normalized = {header.lower() for header in headers}
    missing = [
        header for header in required_headers_for_format(csv_format) if header not in normalized
    ]
    if missing:
        raise ValueError(f"CSV missing required header(s): {', '.join(missing)}")


def required_headers_for_format(csv_format: str) -> list[str]:
    if csv_format == "aurex":
        return AUREX_CONTRACT_SNAPSHOT_HEADERS[:5]
    if csv_format == "mkt_markets":
        return ["ticker", "event_ticker", "title", "status", "yes_bid", "yes_ask"]
    raise ValueError("csv_format must be one of: auto, aurex, mkt_markets")


def prepare_rows(
    payload: PredictionContractSnapshotCsvRequest,
    csv_format: str,
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[ParsedContractSnapshotRow]]:
    row_results: list[dict[str, object]] = []
    parsed_rows: list[ParsedContractSnapshotRow] = []
    for index, row in enumerate(rows, start=2):
        try:
            parsed_rows.append(parse_row(payload, csv_format, row, index))
        except ValueError as exc:
            row_results.append(
                {
                    "row_number": index,
                    "status": "REJECTED",
                    "contract_ticker": first_value(row, "contract_ticker", "ticker") or None,
                    "event_ticker": first_value(row, "event_ticker") or None,
                    "reasons": [str(exc)],
                }
            )
    return row_results, parsed_rows


def parse_row(
    payload: PredictionContractSnapshotCsvRequest,
    csv_format: str,
    row: dict[str, str],
    row_number: int,
) -> ParsedContractSnapshotRow:
    if csv_format == "aurex":
        return parse_aurex_row(payload, row, row_number)
    if csv_format == "mkt_markets":
        return parse_mkt_markets_row(payload, row, row_number)
    raise ValueError("csv_format must be one of: auto, aurex, mkt_markets")


def parse_aurex_row(
    payload: PredictionContractSnapshotCsvRequest,
    row: dict[str, str],
    row_number: int,
) -> ParsedContractSnapshotRow:
    observed_at = parse_datetime(first_value(row, "observed_at"), "observed_at") or utc_now()
    snapshot = PredictionContractSnapshot(
        venue=parse_venue(first_value(row, "venue")),
        event_ticker=required_text(row, "event_ticker"),
        market_title=required_text(row, "market_title"),
        contract_ticker=required_text(row, "contract_ticker"),
        contract_title=required_text(row, "contract_title"),
        category=optional_text(row, "category"),
        status=parse_status(first_value(row, "status")),
        yes_bid_price=parse_probability(first_value(row, "yes_bid_price"), "yes_bid_price"),
        yes_ask_price=parse_probability(first_value(row, "yes_ask_price"), "yes_ask_price"),
        no_bid_price=parse_probability(first_value(row, "no_bid_price"), "no_bid_price"),
        no_ask_price=parse_probability(first_value(row, "no_ask_price"), "no_ask_price"),
        closes_at=parse_datetime(first_value(row, "closes_at"), "closes_at"),
        expiration_at=parse_datetime(first_value(row, "expiration_at"), "expiration_at"),
        raw_payload=raw_payload(payload, "aurex", row, row_number),
        settlement_value=parse_settlement_value(row),
    )
    return ParsedContractSnapshotRow(row_number, observed_at, snapshot)


def parse_mkt_markets_row(
    payload: PredictionContractSnapshotCsvRequest,
    row: dict[str, str],
    row_number: int,
) -> ParsedContractSnapshotRow:
    yes_bid = parse_probability(first_value(row, "yes_bid"), "yes_bid")
    yes_ask = parse_probability(first_value(row, "yes_ask"), "yes_ask")
    observed_at = (
        parse_datetime(first_value(row, "last_updated"), "last_updated")
        or parse_datetime(first_value(row, "snapshot_at"), "snapshot_at")
        or utc_now()
    )
    raw = raw_payload(payload, "mkt_markets", row, row_number)
    raw["derived_no_quotes"] = True
    settlement_value = parse_settlement_value(row)
    if settlement_value is not None:
        raw["imported_settlement_value"] = str(settlement_value)
    snapshot = PredictionContractSnapshot(
        venue=PredictionMarketVenue.KALSHI,
        event_ticker=required_text(row, "event_ticker"),
        market_title=required_text(row, "title"),
        contract_ticker=required_text(row, "ticker"),
        contract_title=optional_text(row, "yes_sub_title") or required_text(row, "title"),
        category=optional_text(row, "category"),
        status=parse_status(first_value(row, "status")),
        yes_bid_price=yes_bid,
        yes_ask_price=yes_ask,
        no_bid_price=(Decimal("1") - yes_ask) if yes_ask is not None else None,
        no_ask_price=(Decimal("1") - yes_bid) if yes_bid is not None else None,
        closes_at=parse_datetime(first_value(row, "close_time"), "close_time"),
        expiration_at=parse_datetime(first_value(row, "close_time"), "close_time"),
        raw_payload=raw,
        settlement_value=settlement_value,
    )
    return ParsedContractSnapshotRow(row_number, observed_at, snapshot)


def required_text(row: dict[str, str], name: str) -> str:
    value = first_value(row, name)
    if not value:
        raise ValueError(f"{name} is required")
    return value[:240]


def optional_text(row: dict[str, str], name: str) -> str | None:
    value = first_value(row, name)
    return value[:240] if value else None


def first_value(row: dict[str, str], *names: str) -> str:
    normalized = {key.lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower(), "")
        if value != "":
            return value
    return ""


def parse_venue(value: str) -> PredictionMarketVenue:
    normalized = (value or "KALSHI").strip().upper()
    try:
        return PredictionMarketVenue(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported venue: {value}") from exc


def parse_status(value: str) -> PredictionMarketStatus:
    normalized = (value or "OPEN").strip().upper()
    aliases = {
        "ACTIVE": "OPEN",
        "OPENED": "OPEN",
        "RESOLVED": "SETTLED",
        "DETERMINED": "SETTLED",
        "FINALIZED": "SETTLED",
        "FINAL": "SETTLED",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return PredictionMarketStatus(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported status: {value}") from exc


def parse_probability(value: str, field_name: str) -> Decimal | None:
    if value == "":
        return None
    try:
        probability = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if probability > Decimal("1") and probability <= Decimal("100"):
        probability = probability / Decimal("100")
    if probability < Decimal("0") or probability > Decimal("1"):
        raise ValueError(f"{field_name} must be between 0 and 1")
    return probability


def parse_settlement_value(row: dict[str, str]) -> Decimal | None:
    explicit = first_value(row, "settlement_value", "settlement_value_dollars")
    if explicit:
        return parse_probability(explicit, "settlement_value")
    result = first_value(row, "result").strip().lower()
    if result in {"yes", "y", "true", "1"}:
        return Decimal("1")
    if result in {"no", "n", "false", "0"}:
        return Decimal("0")
    return None


def parse_datetime(value: str, field_name: str) -> datetime | None:
    if value == "":
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def raw_payload(
    payload: PredictionContractSnapshotCsvRequest,
    csv_format: str,
    row: dict[str, str],
    row_number: int,
) -> dict[str, object]:
    return {
        "source": payload.source.strip(),
        "source_reference": payload.source_reference.strip(),
        "csv_format": csv_format,
        "row_number": row_number,
        "raw_row": row,
    }


def ready_row_result(parsed: ParsedContractSnapshotRow) -> dict[str, object]:
    snapshot = parsed.snapshot
    return {
        "row_number": parsed.row_number,
        "status": "READY",
        "contract_ticker": snapshot.contract_ticker,
        "event_ticker": snapshot.event_ticker,
        "observed_at": parsed.observed_at.isoformat(),
        "reasons": [],
    }


def count_status(row_results: list[dict[str, object]], status: str) -> int:
    return sum(1 for result in row_results if result.get("status") == status)


def preflight_status(rows_received: int, importable_count: int, rejected_count: int) -> str:
    if rows_received == 0:
        return "EMPTY"
    if importable_count == 0:
        return "REJECTED"
    if rejected_count:
        return "READY_WITH_REJECTIONS"
    return "READY"


def import_status(rows_received: int, imported_count: int, rejected_count: int) -> str:
    if rows_received == 0:
        return "EMPTY"
    if imported_count == 0:
        return "REJECTED"
    if rejected_count:
        return "IMPORTED_WITH_REJECTIONS"
    return "IMPORTED"


def analysis_summary(
    row_results: list[dict[str, object]],
    parsed_rows: list[ParsedContractSnapshotRow],
) -> dict[str, object]:
    actionable_yes_rows = sum(1 for row in parsed_rows if row.snapshot.yes_ask_price is not None)
    actionable_no_rows = sum(1 for row in parsed_rows if row.snapshot.no_ask_price is not None)
    rejected_reasons: dict[str, int] = {}
    for result in row_results:
        if result.get("status") != "REJECTED":
            continue
        for reason in result.get("reasons", []):
            reason_text = str(reason)
            rejected_reasons[reason_text] = rejected_reasons.get(reason_text, 0) + 1
    return {
        "unique_contracts": len({row.snapshot.contract_ticker for row in parsed_rows}),
        "actionable_yes_rows": actionable_yes_rows,
        "actionable_no_rows": actionable_no_rows,
        "rejected_reasons": rejected_reasons,
    }


def build_import_hash(payload: PredictionContractSnapshotCsvRequest) -> str:
    content = "\n".join(
        [
            payload.source.strip(),
            payload.source_reference.strip(),
            payload.csv_format.strip().lower(),
            payload.csv_text,
        ]
    )
    return sha256(content.encode()).hexdigest()


def prediction_contract_snapshot_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(AUREX_CONTRACT_SNAPSHOT_HEADERS)
    writer.writerow(
        [
            "KALSHI",
            "KXBTCD-26JUN25",
            "Bitcoin above test level on Jun 25",
            "KXBTCD-26JUN25-B62500",
            "Bitcoin above 62500",
            "crypto",
            "OPEN",
            "0.59",
            "0.60",
            "0.40",
            "0.41",
            "",
            "2026-06-25T20:00:00Z",
            "2026-06-25T20:00:00Z",
            "2026-06-25T19:30:00Z",
        ]
    )
    return output.getvalue()
