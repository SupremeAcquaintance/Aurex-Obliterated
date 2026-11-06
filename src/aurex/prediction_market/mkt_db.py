import json
import sqlite3
from dataclasses import replace
from pathlib import Path

from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.prediction_market.contract_csv import (
    ParsedContractSnapshotRow,
    analysis_summary,
    build_import_hash,
    count_status,
    import_status,
    parse_mkt_markets_row,
    preflight_status,
    ready_row_result,
    required_headers_for_format,
)
from aurex.prediction_market.paper import PredictionMarketPaperEngine
from aurex.prediction_market.schemas import (
    PredictionContractSnapshotCsvRequest,
    PredictionContractSnapshotMktDbRequest,
)

MKT_MARKETS_COLUMNS = [
    "ticker",
    "event_ticker",
    "series_ticker",
    "title",
    "yes_sub_title",
    "category",
    "status",
    "close_time",
    "volume",
    "volume_24h",
    "open_interest",
    "yes_bid",
    "yes_ask",
    "last_price",
    "result",
    "settlement_value",
    "last_updated",
]

class PredictionContractSnapshotMktDbImporter:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight_db(
        self,
        payload: PredictionContractSnapshotMktDbRequest,
    ) -> dict[str, object]:
        db_path, rows = load_mkt_markets_rows(payload)
        parser_payload = parser_payload_from_mkt_db_request(payload, db_path, rows)
        row_results, parsed_rows = prepare_mkt_db_rows(parser_payload, db_path, rows)
        row_results.extend(ready_row_result(parsed) for parsed in parsed_rows)
        row_results.sort(key=lambda item: int(item["row_number"]))
        importable_count = count_status(row_results, "READY")
        rejected_count = count_status(row_results, "REJECTED")
        return {
            "db_path": str(db_path),
            "source": payload.source.strip(),
            "source_reference": payload.source_reference.strip(),
            "csv_format": "mkt_markets",
            "import_hash": build_import_hash(parser_payload),
            "status": preflight_status(len(rows), importable_count, rejected_count),
            "rows_received": len(rows),
            "importable_count": importable_count,
            "rejected_count": rejected_count,
            "required_headers": required_headers_for_format("mkt_markets"),
            "row_results": row_results,
            "analysis_summary": analysis_summary(row_results, parsed_rows),
            "query_summary": mkt_db_query_summary(payload),
            "checked_at": utc_now(),
        }

    def import_db(
        self,
        payload: PredictionContractSnapshotMktDbRequest,
    ) -> dict[str, object]:
        db_path, rows = load_mkt_markets_rows(payload)
        parser_payload = parser_payload_from_mkt_db_request(payload, db_path, rows)
        row_results, parsed_rows = prepare_mkt_db_rows(parser_payload, db_path, rows)

        contract_ids: list[str] = []
        engine = PredictionMarketPaperEngine(self.session)
        for parsed in sorted(parsed_rows, key=lambda item: (item.observed_at, item.row_number)):
            contract = engine.upsert_contract_snapshot(parsed.snapshot, now=parsed.observed_at)
            contract_ids.append(contract.id)

        row_results.extend(ready_row_result(parsed) for parsed in parsed_rows)
        row_results.sort(key=lambda item: int(item["row_number"]))
        imported_count = len(parsed_rows)
        rejected_count = count_status(row_results, "REJECTED")
        return {
            "db_path": str(db_path),
            "source": payload.source.strip(),
            "source_reference": payload.source_reference.strip(),
            "csv_format": "mkt_markets",
            "import_hash": build_import_hash(parser_payload),
            "status": import_status(len(rows), imported_count, rejected_count),
            "rows_received": len(rows),
            "imported_count": imported_count,
            "rejected_count": rejected_count,
            "contract_ids": contract_ids,
            "row_results": row_results,
            "analysis_summary": analysis_summary(row_results, parsed_rows),
            "query_summary": mkt_db_query_summary(payload),
            "imported_at": utc_now(),
        }


def load_mkt_markets_rows(
    payload: PredictionContractSnapshotMktDbRequest,
) -> tuple[Path, list[dict[str, str]]]:
    db_path = Path(payload.db_path).expanduser()
    if not db_path.exists():
        raise ValueError(f"My-Krypt-Trader database not found: {db_path}")

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if not sqlite_table_exists(conn, "markets"):
                raise ValueError("My-Krypt-Trader markets table not found.")
            rows = fetch_mkt_market_rows(conn, payload)
    except sqlite3.Error as exc:
        raise ValueError(f"My-Krypt-Trader database could not be read: {exc}") from exc
    return db_path, rows


def fetch_mkt_market_rows(
    conn: sqlite3.Connection,
    payload: PredictionContractSnapshotMktDbRequest,
) -> list[dict[str, str]]:
    where: list[str] = []
    params: list[object] = []

    if payload.status_filter == "open":
        where.append("lower(coalesce(status, '')) in ('open', 'active', 'opened')")
    elif payload.status_filter == "resolved":
        where.append(
            "("
            "lower(coalesce(status, '')) not in ('', 'open', 'active', 'opened') "
            "or lower(coalesce(result, '')) in "
            "('yes', 'no', 'y', 'n', 'true', 'false', '1', '0') "
            "or settlement_value is not null"
            ")"
        )

    if payload.require_settlement_value:
        where.append(
            "("
            "settlement_value is not null "
            "or lower(coalesce(result, '')) in "
            "('yes', 'no', 'y', 'n', 'true', 'false', '1', '0')"
            ")"
        )

    if payload.min_volume is not None:
        where.append("(coalesce(volume, 0) >= ? or coalesce(volume_24h, 0) >= ?)")
        volume = float(payload.min_volume)
        params.extend([volume, volume])

    sql = f"select {', '.join(MKT_MARKETS_COLUMNS)} from markets"
    if where:
        sql = f"{sql} where {' and '.join(where)}"
    sql = f"{sql} order by datetime(nullif(last_updated, '')) desc, ticker asc limit ?"
    params.append(payload.limit)
    return [stringify_sqlite_row(row) for row in conn.execute(sql, params).fetchall()]


def prepare_mkt_db_rows(
    parser_payload: PredictionContractSnapshotCsvRequest,
    db_path: Path,
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[ParsedContractSnapshotRow]]:
    row_results: list[dict[str, object]] = []
    parsed_rows: list[ParsedContractSnapshotRow] = []
    for index, row in enumerate(rows, start=1):
        try:
            parsed = parse_mkt_markets_row(parser_payload, row, index)
            raw_payload = {
                **parsed.snapshot.raw_payload,
                "db_path": str(db_path),
                "sqlite_table": "markets",
                "direct_db_import": True,
            }
            parsed_rows.append(
                ParsedContractSnapshotRow(
                    row_number=parsed.row_number,
                    observed_at=parsed.observed_at,
                    snapshot=replace(parsed.snapshot, raw_payload=raw_payload),
                )
            )
        except ValueError as exc:
            row_results.append(
                {
                    "row_number": index,
                    "status": "REJECTED",
                    "contract_ticker": row.get("ticker") or None,
                    "event_ticker": row.get("event_ticker") or None,
                    "reasons": [str(exc)],
                }
            )
    return row_results, parsed_rows


def parser_payload_from_mkt_db_request(
    payload: PredictionContractSnapshotMktDbRequest,
    db_path: Path,
    rows: list[dict[str, str]],
) -> PredictionContractSnapshotCsvRequest:
    return PredictionContractSnapshotCsvRequest(
        source=payload.source,
        source_reference=payload.source_reference,
        csv_format="mkt_markets",
        csv_text=json.dumps(
            {
                "db_path": str(db_path),
                "query": mkt_db_query_summary(payload),
                "rows": rows,
            },
            sort_keys=True,
            default=str,
        ),
    )


def mkt_db_query_summary(payload: PredictionContractSnapshotMktDbRequest) -> dict[str, object]:
    return {
        "table": "markets",
        "status_filter": payload.status_filter,
        "limit": payload.limit,
        "min_volume": str(payload.min_volume) if payload.min_volume is not None else None,
        "require_settlement_value": payload.require_settlement_value,
    }


def sqlite_table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select name from sqlite_master where type = 'table' and name = ?",
        (table,),
    ).fetchone()
    return row is not None


def stringify_sqlite_row(row: sqlite3.Row) -> dict[str, str]:
    return {key: "" if row[key] is None else str(row[key]) for key in row.keys()}
