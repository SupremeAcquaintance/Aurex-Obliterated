import csv
import io
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from aurex.db.base import utc_now
from aurex.live_deployment.schemas import (
    BrokerStatementCsvReconciliationRequest,
    BrokerStatementReconciliationRequest,
)

BROKER_STATEMENT_REQUIRED_HEADERS = [
    "external_trade_id",
    "closed_at",
    "net_pl",
    "fees",
    "slippage",
]


@dataclass(frozen=True)
class ParsedBrokerStatementRow:
    row_number: int
    external_trade_id: str
    closed_at: datetime
    net_pl: Decimal
    fees: Decimal
    slippage: Decimal


@dataclass(frozen=True)
class BrokerStatementCsvSummary:
    status: str
    rows_received: int
    importable_count: int
    rejected_count: int
    broker_trade_count: int
    broker_net_pl: Decimal
    broker_fees: Decimal
    broker_slippage: Decimal
    statement_start_at: datetime | None
    statement_end_at: datetime | None
    row_results: list[dict[str, object]]
    analysis_summary: dict[str, object]


def preflight_broker_statement_csv(
    payload: BrokerStatementCsvReconciliationRequest,
) -> dict[str, object]:
    summary = summarize_broker_statement_csv(payload)
    return {
        "statement_reference": payload.statement_reference.strip(),
        "status": summary.status,
        "rows_received": summary.rows_received,
        "importable_count": summary.importable_count,
        "rejected_count": summary.rejected_count,
        "broker_trade_count": summary.broker_trade_count,
        "broker_net_pl": summary.broker_net_pl,
        "broker_fees": summary.broker_fees,
        "broker_slippage": summary.broker_slippage,
        "statement_start_at": summary.statement_start_at,
        "statement_end_at": summary.statement_end_at,
        "required_headers": BROKER_STATEMENT_REQUIRED_HEADERS,
        "row_results": summary.row_results,
        "analysis_summary": summary.analysis_summary,
        "checked_at": utc_now(),
    }


def summarize_broker_statement_csv(
    payload: BrokerStatementCsvReconciliationRequest,
) -> BrokerStatementCsvSummary:
    headers, rows = read_statement_csv_rows(payload.csv_text)
    validate_statement_headers(headers)
    row_results, parsed_rows = parse_statement_rows(rows)
    row_results.extend(
        {
            "row_number": row.row_number,
            "external_trade_id": row.external_trade_id,
            "status": "READY",
            "closed_at": row.closed_at.isoformat(),
            "net_pl": str(row.net_pl),
            "fees": str(row.fees),
            "slippage": str(row.slippage),
        }
        for row in parsed_rows
    )
    row_results.sort(key=lambda item: int(item["row_number"]))

    importable_count = len(parsed_rows)
    rejected_count = sum(1 for result in row_results if result["status"] == "REJECTED")
    first_closed_at = min((row.closed_at for row in parsed_rows), default=None)
    latest_closed_at = max((row.closed_at for row in parsed_rows), default=None)
    statement_start_at = payload.statement_start_at or first_closed_at
    statement_end_at = payload.statement_end_at or latest_closed_at
    broker_net_pl = sum((row.net_pl for row in parsed_rows), Decimal("0"))
    broker_fees = sum((row.fees for row in parsed_rows), Decimal("0"))
    broker_slippage = sum((row.slippage for row in parsed_rows), Decimal("0"))

    return BrokerStatementCsvSummary(
        status=statement_csv_status(len(rows), importable_count, rejected_count),
        rows_received=len(rows),
        importable_count=importable_count,
        rejected_count=rejected_count,
        broker_trade_count=len(parsed_rows),
        broker_net_pl=broker_net_pl,
        broker_fees=broker_fees,
        broker_slippage=broker_slippage,
        statement_start_at=statement_start_at,
        statement_end_at=statement_end_at,
        row_results=row_results,
        analysis_summary=build_statement_analysis_summary(
            row_results,
            parsed_rows,
            broker_net_pl,
            broker_fees,
            broker_slippage,
            statement_start_at,
            statement_end_at,
        ),
    )


def statement_payload_from_csv_summary(
    payload: BrokerStatementCsvReconciliationRequest,
    summary: BrokerStatementCsvSummary,
) -> BrokerStatementReconciliationRequest:
    if summary.status != "READY":
        raise ValueError("Broker statement CSV must be READY before reconciliation")
    return BrokerStatementReconciliationRequest(
        statement_reference=payload.statement_reference,
        statement_start_at=summary.statement_start_at,
        statement_end_at=summary.statement_end_at,
        broker_trade_count=summary.broker_trade_count,
        broker_net_pl=summary.broker_net_pl,
        broker_fees=summary.broker_fees,
        broker_slippage=summary.broker_slippage,
        notes=payload.notes,
    )


def read_statement_csv_rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Broker statement CSV must include a header row")
    headers = [header.strip() for header in reader.fieldnames]
    rows = [
        {
            (key or "").strip(): (value or "").strip()
            for key, value in raw_row.items()
        }
        for raw_row in reader
    ]
    return headers, rows


def validate_statement_headers(headers: list[str]) -> None:
    missing_headers = sorted(set(BROKER_STATEMENT_REQUIRED_HEADERS) - set(headers))
    if missing_headers:
        raise ValueError(
            "Broker statement CSV missing required columns: " + ", ".join(missing_headers)
        )


def parse_statement_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[ParsedBrokerStatementRow]]:
    row_results: list[dict[str, object]] = []
    parsed_rows: list[ParsedBrokerStatementRow] = []
    seen_external_trade_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        external_trade_id = text_value(row, "external_trade_id")
        if not external_trade_id:
            row_results.append(statement_rejected_row(row_number, "", "external_trade_id_required"))
            continue
        if external_trade_id in seen_external_trade_ids:
            row_results.append(
                statement_rejected_row(
                    row_number,
                    external_trade_id,
                    "duplicate_external_trade_id_in_csv",
                )
            )
            continue
        seen_external_trade_ids.add(external_trade_id)
        try:
            parsed_rows.append(parse_statement_row(row_number, row))
        except ValueError as exc:
            row_results.append(statement_rejected_row(row_number, external_trade_id, str(exc)))
    return row_results, parsed_rows


def parse_statement_row(
    row_number: int,
    row: dict[str, str],
) -> ParsedBrokerStatementRow:
    return ParsedBrokerStatementRow(
        row_number=row_number,
        external_trade_id=required_text(row, "external_trade_id"),
        closed_at=parse_datetime_field(row, "closed_at"),
        net_pl=parse_decimal(required_text(row, "net_pl"), "net_pl"),
        fees=non_negative_decimal(row, "fees"),
        slippage=non_negative_decimal(row, "slippage"),
    )


def build_statement_analysis_summary(
    row_results: list[dict[str, object]],
    parsed_rows: list[ParsedBrokerStatementRow],
    broker_net_pl: Decimal,
    broker_fees: Decimal,
    broker_slippage: Decimal,
    statement_start_at: datetime | None,
    statement_end_at: datetime | None,
) -> dict[str, object]:
    rejected_rows = [result for result in row_results if result.get("status") == "REJECTED"]
    rejected_reasons = Counter(str(row.get("reason", "unknown")) for row in rejected_rows)
    active_dates = sorted({row.closed_at.date().isoformat() for row in parsed_rows})
    return {
        "status_counts": dict(
            sorted(Counter(str(result.get("status", "UNKNOWN")) for result in row_results).items())
        ),
        "rejected_reasons": dict(sorted(rejected_reasons.items())),
        "fix_queue": build_statement_fix_queue(rejected_rows),
        "ready_count": len(parsed_rows),
        "active_trading_days": len(active_dates),
        "statement_start_at": statement_start_at.isoformat() if statement_start_at else None,
        "statement_end_at": statement_end_at.isoformat() if statement_end_at else None,
        "broker_net_pl": str(broker_net_pl),
        "broker_fees": str(broker_fees),
        "broker_slippage": str(broker_slippage),
    }


def build_statement_fix_queue(
    rejected_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows_by_reason: dict[str, list[int]] = {}
    for row in rejected_rows:
        reason = str(row.get("reason", "unknown"))
        rows_by_reason.setdefault(reason, []).append(int(row["row_number"]))
    return [
        {"reason": reason, "count": len(row_numbers), "rows": row_numbers}
        for reason, row_numbers in sorted(rows_by_reason.items())
    ]


def statement_csv_status(
    rows_received: int,
    importable_count: int,
    rejected_count: int,
) -> str:
    if rows_received == 0:
        return "EMPTY"
    if importable_count == rows_received:
        return "READY"
    if importable_count > 0 and rejected_count > 0:
        return "PARTIAL"
    if rejected_count == rows_received:
        return "REJECTED"
    return "PARTIAL"


def statement_rejected_row(
    row_number: int,
    external_trade_id: str,
    reason: str,
) -> dict[str, object]:
    return {
        "row_number": row_number,
        "external_trade_id": external_trade_id,
        "status": "REJECTED",
        "reason": reason,
    }


def required_text(row: dict[str, str], field: str) -> str:
    value = text_value(row, field)
    if not value:
        raise ValueError(f"{field}_required")
    return value


def text_value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def parse_datetime_field(row: dict[str, str], field: str) -> datetime:
    value = required_text(row, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}_must_be_iso_datetime") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def non_negative_decimal(row: dict[str, str], field: str) -> Decimal:
    value = parse_decimal(required_text(row, field), field)
    if value < 0:
        raise ValueError(f"{field}_cannot_be_negative")
    return value


def parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field}_must_be_decimal") from exc
