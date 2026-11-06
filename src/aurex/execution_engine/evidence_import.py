import csv
import io
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.db.models import (
    Account,
    EquityCurvePoint,
    PaperEvidenceImportBatch,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    SignalEvent,
    Symbol,
    TradeJournalEntry,
)
from aurex.domain.enums import (
    Direction,
    MarketRegime,
    OrderStatus,
    PositionStatus,
    SignalStatus,
    TradeStatus,
)
from aurex.execution_engine.paper import (
    calculate_trade_pl,
    imported_execution_assumptions_snapshot,
    paper_execution_evidence_hash,
)
from aurex.execution_engine.schemas import PaperEvidenceCsvImportRequest
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.calculations import calculate_reward_risk, calculate_stop_risk_amount
from aurex.risk_engine.service import RiskEngine

RISK_TOLERANCE = Decimal("0.00000001")

REQUIRED_HEADERS = [
    "external_trade_id",
    "strategy",
    "symbol",
    "timeframe",
    "direction",
    "opened_at",
    "closed_at",
    "entry_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "quantity",
    "risk_amount",
    "fees",
    "slippage",
    "close_reason",
    "journal_author",
    "journal_thesis",
    "rule_followed",
    "emotional_override",
]


@dataclass(frozen=True)
class ParsedPaperEvidenceRow:
    row_number: int
    external_trade_id: str
    strategy: str
    symbol: str
    timeframe: str
    direction: Direction
    opened_at: datetime
    closed_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    quantity: Decimal
    risk_amount: Decimal
    fees: Decimal
    slippage: Decimal
    realized_pl: Decimal
    reward_risk: Decimal
    close_reason: str
    journal_author: str
    journal_thesis: str
    journal_execution_notes: str | None
    journal_outcome_notes: str | None
    rule_followed: bool
    emotional_override: bool
    market_regime: MarketRegime
    raw_row: dict[str, str]


class PaperEvidenceCsvImporter:
    def __init__(self, session: Session) -> None:
        self.session = session

    def preflight_csv(
        self,
        payload: PaperEvidenceCsvImportRequest,
        *,
        strategy_scope: str | None = None,
        symbol_scope: list[str] | None = None,
    ) -> dict[str, object]:
        source = payload.source.strip()
        source_reference = payload.source_reference.strip()
        headers, rows = read_csv_rows(payload.csv_text)
        validate_required_headers(headers)
        row_results, parsed_rows = self._prepare_rows_for_import(source, rows)
        row_results.extend(
            {
                "row_number": parsed.row_number,
                "external_trade_id": parsed.external_trade_id,
                "status": "READY",
                "strategy": parsed.strategy,
                "symbol": parsed.symbol,
                "realized_pl": str(parsed.realized_pl),
                "closed_at": parsed.closed_at.isoformat(),
                "evidence_hash": imported_paper_trade_evidence_hash(
                    imported_paper_trade_evidence_payload_from_parsed(
                        source,
                        source_reference,
                        parsed,
                    ),
                ),
            }
            for parsed in parsed_rows
        )
        row_results.sort(key=lambda item: int(item["row_number"]))
        importable_count = sum(1 for result in row_results if result["status"] == "READY")
        skipped_count = sum(1 for result in row_results if result["status"] == "SKIPPED")
        rejected_count = sum(1 for result in row_results if result["status"] == "REJECTED")
        analysis_summary = build_analysis_summary(row_results, parsed_rows)
        scope_preview = paper_evidence_preflight_scope_preview(
            parsed_rows,
            strategy_scope=strategy_scope,
            symbol_scope=symbol_scope,
        )
        return {
            "source": source,
            "source_reference": source_reference,
            "import_hash": build_import_hash(source, source_reference, payload.csv_text),
            "status": preflight_status(
                rows_received=len(rows),
                importable_count=importable_count,
                skipped_count=skipped_count,
                rejected_count=rejected_count,
            ),
            "rows_received": len(rows),
            "importable_count": importable_count,
            "skipped_count": skipped_count,
            "rejected_count": rejected_count,
            "required_headers": REQUIRED_HEADERS,
            "row_results": row_results,
            "analysis_summary": analysis_summary,
            **scope_preview,
            "checked_at": utc_now(),
        }

    def import_csv(self, payload: PaperEvidenceCsvImportRequest) -> PaperEvidenceImportBatch:
        source = payload.source.strip()
        source_reference = payload.source_reference.strip()
        headers, rows = read_csv_rows(payload.csv_text)
        validate_required_headers(headers)

        account, _ = RiskEngine(self.session).get_or_create_default_profile()
        imported_at = utc_now()
        batch = PaperEvidenceImportBatch(
            account=account,
            source=source,
            source_reference=source_reference,
            import_hash=build_import_hash(source, source_reference, payload.csv_text),
            status="PENDING",
            rows_received=len(rows),
            imported_count=0,
            skipped_count=0,
            rejected_count=0,
            required_headers=REQUIRED_HEADERS,
            row_results=[],
            evidence_snapshot={
                "source": source,
                "source_reference": source_reference,
                "headers": headers,
                "required_headers": REQUIRED_HEADERS,
            },
            imported_at=imported_at,
        )
        self.session.add(batch)
        self.session.flush()

        row_results, parsed_rows = self._prepare_rows_for_import(source, rows)
        imported_trade_ids: list[str] = []
        imported_trade_hashes: dict[str, str] = {}
        imported_external_trade_hashes: dict[str, str] = {}
        for parsed in sorted(parsed_rows, key=lambda item: item.closed_at):
            trade = self._persist_imported_trade(
                parsed,
                batch=batch,
                account=account,
                source=source,
                imported_at=imported_at,
            )
            evidence_payload = imported_paper_trade_evidence_payload_from_parsed(
                source,
                source_reference,
                parsed,
            )
            evidence_hash = imported_paper_trade_evidence_hash(evidence_payload)
            imported_trade_ids.append(trade.id)
            imported_trade_hashes[trade.id] = evidence_hash
            imported_external_trade_hashes[parsed.external_trade_id] = evidence_hash
            row_results.append(
                {
                    "row_number": parsed.row_number,
                    "external_trade_id": parsed.external_trade_id,
                    "status": "IMPORTED",
                    "paper_trade_id": trade.id,
                    "realized_pl": str(parsed.realized_pl),
                    "closed_at": parsed.closed_at.isoformat(),
                    "evidence_hash": evidence_hash,
                }
            )

        row_results.sort(key=lambda item: int(item["row_number"]))
        batch.row_results = row_results
        batch.imported_count = len(imported_trade_ids)
        batch.skipped_count = sum(1 for result in row_results if result["status"] == "SKIPPED")
        batch.rejected_count = sum(1 for result in row_results if result["status"] == "REJECTED")
        batch.status = import_status(
            rows_received=batch.rows_received,
            imported_count=batch.imported_count,
            skipped_count=batch.skipped_count,
            rejected_count=batch.rejected_count,
        )
        batch.evidence_snapshot = {
            **batch.evidence_snapshot,
            "paper_trade_ids": imported_trade_ids,
            "imported_count": batch.imported_count,
            "skipped_count": batch.skipped_count,
            "rejected_count": batch.rejected_count,
            "status": batch.status,
            "imported_trade_hashes": imported_trade_hashes,
            "imported_external_trade_hashes": imported_external_trade_hashes,
            "analysis_summary": build_analysis_summary(row_results, parsed_rows),
        }
        SystemEventRecorder(self.session).info(
            "paper_evidence_import",
            "Paper evidence CSV import recorded",
            {
                "batch_id": batch.id,
                "source": source,
                "source_reference": source_reference,
                "rows_received": batch.rows_received,
                "imported_count": batch.imported_count,
                "skipped_count": batch.skipped_count,
                "rejected_count": batch.rejected_count,
                "status": batch.status,
            },
            occurred_at=imported_at,
        )
        self.session.flush()
        return batch

    def list_batches(self, limit: int = 100) -> list[PaperEvidenceImportBatch]:
        return list(
            self.session.execute(
                select(PaperEvidenceImportBatch)
                .order_by(PaperEvidenceImportBatch.imported_at.desc())
                .limit(limit)
            ).scalars()
        )

    def get_batch(self, batch_id: str) -> PaperEvidenceImportBatch | None:
        return self.session.get(PaperEvidenceImportBatch, batch_id)

    def _prepare_rows_for_import(
        self,
        source: str,
        rows: list[dict[str, str]],
    ) -> tuple[list[dict[str, object]], list[ParsedPaperEvidenceRow]]:
        row_results: list[dict[str, object]] = []
        parsed_rows: list[ParsedPaperEvidenceRow] = []
        seen_external_trade_ids: set[str] = set()
        for row_number, row in enumerate(rows, start=2):
            external_trade_id = text_value(row, "external_trade_id")
            if not external_trade_id:
                row_results.append(rejected_row(row_number, "", "external_trade_id_required"))
                continue
            if external_trade_id in seen_external_trade_ids:
                row_results.append(
                    rejected_row(
                        row_number,
                        external_trade_id,
                        "duplicate_external_trade_id_in_csv",
                    )
                )
                continue
            seen_external_trade_ids.add(external_trade_id)

            existing_trade_id = self._existing_trade_id(source, external_trade_id)
            if existing_trade_id is not None:
                row_results.append(
                    {
                        "row_number": row_number,
                        "external_trade_id": external_trade_id,
                        "status": "SKIPPED",
                        "reason": "duplicate_external_trade_id",
                        "paper_trade_id": existing_trade_id,
                    }
                )
                continue

            try:
                parsed_rows.append(parse_paper_evidence_row(row_number, row))
            except ValueError as exc:
                row_results.append(rejected_row(row_number, external_trade_id, str(exc)))
        return row_results, parsed_rows

    def _persist_imported_trade(
        self,
        parsed: ParsedPaperEvidenceRow,
        batch: PaperEvidenceImportBatch,
        account: Account,
        source: str,
        imported_at: datetime,
    ) -> PaperTrade:
        symbol = self._get_or_create_symbol(parsed.symbol, source)
        account_equity_before = account.current_equity
        idempotency_key = import_idempotency_key(source, parsed.external_trade_id)
        evidence_payload = imported_paper_trade_evidence_payload_from_parsed(
            source,
            batch.source_reference,
            parsed,
        )
        evidence_hash = imported_paper_trade_evidence_hash(evidence_payload)

        signal = Signal(
            source=source,
            strategy=parsed.strategy,
            symbol_ref=symbol,
            symbol=parsed.symbol,
            timeframe=parsed.timeframe,
            direction=parsed.direction,
            entry_price=parsed.entry_price,
            stop_loss=parsed.stop_loss,
            take_profit=parsed.take_profit,
            market_regime=parsed.market_regime,
            status=SignalStatus.CLOSED,
            idempotency_key=idempotency_key,
            raw_payload={
                "import_batch_id": batch.id,
                "source_reference": batch.source_reference,
                "external_trade_id": parsed.external_trade_id,
                "row": parsed.raw_row,
                "import_evidence_hash": evidence_hash,
                "import_evidence_payload": evidence_payload,
            },
            normalized_payload={
                "source": source,
                "external_trade_id": parsed.external_trade_id,
                "symbol": parsed.symbol,
                "strategy": parsed.strategy,
                "timeframe": parsed.timeframe,
                "direction": parsed.direction.value,
                "opened_at": parsed.opened_at.isoformat(),
                "closed_at": parsed.closed_at.isoformat(),
            },
            source_timestamp=parsed.opened_at,
            received_at=imported_at,
            processed_at=parsed.closed_at,
        )
        self.session.add(signal)
        self.session.flush()

        risk_decision = RiskDecision(
            signal=signal,
            approved=True,
            reason="Imported paper evidence row with complete risk lineage.",
            reward_risk=parsed.reward_risk,
            risk_amount=parsed.risk_amount,
            position_size=parsed.quantity,
            account_equity=account_equity_before,
            rules_snapshot={
                "source": "paper_evidence_import",
                "import_batch_id": batch.id,
                "source_reference": batch.source_reference,
                "external_trade_id": parsed.external_trade_id,
                "approved_risk_amount": str(parsed.risk_amount),
                "approved_position_size": str(parsed.quantity),
                "import_evidence_hash": evidence_hash,
            },
        )
        self.session.add(risk_decision)
        self.session.flush()

        execution_assumptions = imported_execution_assumptions_snapshot(
            source_reference=batch.source_reference,
            import_evidence_hash=evidence_hash,
            entry_price=parsed.entry_price,
            exit_price=parsed.exit_price,
            quantity=parsed.quantity,
            opened_at=parsed.opened_at,
            closed_at=parsed.closed_at,
            fees=parsed.fees,
            slippage=parsed.slippage,
        )
        order = PaperOrder(
            signal=signal,
            risk_decision_id=risk_decision.id,
            symbol_id=symbol.id,
            symbol=parsed.symbol,
            direction=parsed.direction,
            order_type="market",
            status=OrderStatus.FILLED,
            requested_price=parsed.entry_price,
            filled_price=parsed.entry_price,
            quantity=parsed.quantity,
            fees=Decimal("0"),
            slippage=Decimal("0"),
            fill_model="paper_evidence_import",
            execution_assumptions=execution_assumptions,
            execution_assumptions_hash=paper_execution_evidence_hash(
                execution_assumptions
            ),
            created_order_at=parsed.opened_at,
            filled_at=parsed.opened_at,
        )
        self.session.add(order)
        self.session.flush()

        trade = PaperTrade(
            account=account,
            paper_order=order,
            strategy=parsed.strategy,
            symbol_id=symbol.id,
            symbol=parsed.symbol,
            timeframe=parsed.timeframe,
            direction=parsed.direction,
            status=TradeStatus.CLOSED,
            market_regime=parsed.market_regime,
            entry_price=parsed.entry_price,
            stop_loss=parsed.stop_loss,
            take_profit=parsed.take_profit,
            quantity=parsed.quantity,
            risk_amount=parsed.risk_amount,
            opened_at=parsed.opened_at,
            exit_price=parsed.exit_price,
            closed_at=parsed.closed_at,
            realized_pl=parsed.realized_pl,
            r_multiple=parsed.realized_pl / parsed.risk_amount,
            fees=parsed.fees,
            slippage=parsed.slippage,
            close_reason=parsed.close_reason,
        )
        position = Position(
            account=account,
            symbol_id=symbol.id,
            symbol=parsed.symbol,
            direction=parsed.direction,
            status=PositionStatus.CLOSED,
            quantity=parsed.quantity,
            average_entry_price=parsed.entry_price,
            opened_at=parsed.opened_at,
            closed_at=parsed.closed_at,
        )
        journal = TradeJournalEntry(
            paper_trade=trade,
            author=parsed.journal_author,
            thesis=parsed.journal_thesis,
            execution_notes=parsed.journal_execution_notes,
            outcome_notes=parsed.journal_outcome_notes,
            rule_followed=parsed.rule_followed,
            emotional_override=parsed.emotional_override,
            evidence_snapshot={
                "source": "paper_evidence_import",
                "import_batch_id": batch.id,
                "source_reference": batch.source_reference,
                "external_trade_id": parsed.external_trade_id,
                "row_number": parsed.row_number,
                "import_evidence_hash": evidence_hash,
            },
            journaled_at=parsed.closed_at,
        )
        self.session.add_all([trade, position, journal])
        account.current_equity = account.current_equity + parsed.realized_pl
        self._record_equity_point(account, parsed.closed_at, parsed.realized_pl)
        self._add_signal_events(signal, parsed, imported_at)
        self.session.flush()
        return trade

    def _get_or_create_symbol(self, symbol_name: str, source: str) -> Symbol:
        symbol = self.session.execute(
            select(Symbol).where(Symbol.symbol == symbol_name)
        ).scalar_one_or_none()
        if symbol is not None:
            return symbol
        symbol = Symbol(
            symbol=symbol_name,
            asset_class="paper",
            exchange=source,
            is_active=True,
        )
        self.session.add(symbol)
        self.session.flush()
        return symbol

    def _existing_trade_id(self, source: str, external_trade_id: str) -> str | None:
        signal_id = self.session.execute(
            select(Signal.id).where(
                Signal.idempotency_key == import_idempotency_key(source, external_trade_id)
            )
        ).scalar_one_or_none()
        if signal_id is None:
            return None
        return self.session.execute(
            select(PaperTrade.id)
            .join(PaperOrder, PaperTrade.paper_order_id == PaperOrder.id)
            .where(PaperOrder.signal_id == signal_id)
            .limit(1)
        ).scalar_one_or_none()

    def _record_equity_point(
        self,
        account: Account,
        recorded_at: datetime,
        realized_pl: Decimal,
    ) -> None:
        previous_high = self.session.execute(
            select(func.max(EquityCurvePoint.equity)).where(
                EquityCurvePoint.account_id == account.id
            )
        ).scalar_one()
        high_water = max(previous_high or account.current_equity, account.current_equity)
        drawdown = max(Decimal("0"), high_water - account.current_equity)
        self.session.add(
            EquityCurvePoint(
                account_id=account.id,
                equity=account.current_equity,
                realized_pl=realized_pl,
                drawdown=drawdown,
                recorded_at=recorded_at,
            )
        )

    def _add_signal_events(
        self,
        signal: Signal,
        parsed: ParsedPaperEvidenceRow,
        imported_at: datetime,
    ) -> None:
        metadata = {
            "source": "paper_evidence_import",
            "external_trade_id": parsed.external_trade_id,
        }
        for status, message in [
            (SignalStatus.RECEIVED, "Imported paper evidence row received"),
            (SignalStatus.RISK_APPROVED, "Imported paper evidence risk approved"),
            (SignalStatus.PAPER_EXECUTED, "Imported paper trade reconstructed"),
            (SignalStatus.CLOSED, "Imported paper trade closed"),
        ]:
            self.session.add(
                SignalEvent(
                    signal=signal,
                    status=status,
                    message=message,
                    metadata_json={**metadata, "imported_at": imported_at.isoformat()},
                )
            )


def read_csv_rows(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Paper evidence CSV must include a header row")
    headers = [header.strip() for header in reader.fieldnames]
    rows = [
        {
            (key or "").strip(): (value or "").strip()
            for key, value in raw_row.items()
        }
        for raw_row in reader
    ]
    return headers, rows


def validate_required_headers(headers: list[str]) -> None:
    missing_headers = sorted(set(REQUIRED_HEADERS) - set(headers))
    if missing_headers:
        raise ValueError(
            "Paper evidence CSV missing required columns: "
            + ", ".join(missing_headers)
        )


def parse_paper_evidence_row(
    row_number: int,
    row: dict[str, str],
) -> ParsedPaperEvidenceRow:
    direction = parse_direction(required_text(row, "direction"))
    opened_at = parse_datetime_field(row, "opened_at")
    closed_at = parse_datetime_field(row, "closed_at")
    if closed_at < opened_at:
        raise ValueError("closed_at_before_opened_at")

    entry_price = positive_decimal(row, "entry_price")
    exit_price = positive_decimal(row, "exit_price")
    stop_loss = positive_decimal(row, "stop_loss")
    take_profit = positive_decimal(row, "take_profit")
    quantity = positive_decimal(row, "quantity")
    risk_amount = positive_decimal(row, "risk_amount")
    fees = non_negative_decimal(row, "fees")
    slippage = non_negative_decimal(row, "slippage")
    reward_risk = calculate_reward_risk(direction, entry_price, stop_loss, take_profit)
    stop_risk_amount = calculate_stop_risk_amount(entry_price, stop_loss, quantity)
    if abs(risk_amount - stop_risk_amount) > RISK_TOLERANCE:
        raise ValueError("risk_amount_does_not_match_entry_stop_and_quantity")
    realized_pl = calculate_trade_pl(direction, entry_price, exit_price, quantity) - fees - slippage
    provided_realized_pl = optional_decimal(row, "realized_pl")
    if provided_realized_pl is not None and provided_realized_pl != realized_pl:
        raise ValueError("realized_pl_does_not_match_prices_fees_and_slippage")

    return ParsedPaperEvidenceRow(
        row_number=row_number,
        external_trade_id=required_text(row, "external_trade_id"),
        strategy=required_text(row, "strategy"),
        symbol=required_text(row, "symbol").upper(),
        timeframe=required_text(row, "timeframe"),
        direction=direction,
        opened_at=opened_at,
        closed_at=closed_at,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        quantity=quantity,
        risk_amount=risk_amount,
        fees=fees,
        slippage=slippage,
        realized_pl=realized_pl,
        reward_risk=reward_risk,
        close_reason=required_text(row, "close_reason"),
        journal_author=required_text(row, "journal_author"),
        journal_thesis=required_text(row, "journal_thesis"),
        journal_execution_notes=optional_text(row, "journal_execution_notes"),
        journal_outcome_notes=optional_text(row, "journal_outcome_notes"),
        rule_followed=parse_bool(required_text(row, "rule_followed")),
        emotional_override=parse_bool(required_text(row, "emotional_override")),
        market_regime=parse_market_regime(optional_text(row, "market_regime")),
        raw_row=dict(row),
    )


def required_text(row: dict[str, str], field: str) -> str:
    value = text_value(row, field)
    if not value:
        raise ValueError(f"{field}_required")
    return value


def optional_text(row: dict[str, str], field: str) -> str | None:
    value = text_value(row, field)
    return value or None


def text_value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def parse_direction(value: str) -> Direction:
    try:
        return Direction(value.upper())
    except ValueError as exc:
        raise ValueError("direction_must_be_LONG_or_SHORT") from exc


def parse_market_regime(value: str | None) -> MarketRegime:
    if value is None:
        return MarketRegime.UNKNOWN
    try:
        return MarketRegime(value.upper())
    except ValueError as exc:
        raise ValueError("market_regime_unknown") from exc


def parse_datetime_field(row: dict[str, str], field: str) -> datetime:
    value = required_text(row, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}_must_be_iso_datetime") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def positive_decimal(row: dict[str, str], field: str) -> Decimal:
    value = parse_decimal(required_text(row, field), field)
    if value <= 0:
        raise ValueError(f"{field}_must_be_positive")
    return value


def non_negative_decimal(row: dict[str, str], field: str) -> Decimal:
    value = parse_decimal(required_text(row, field), field)
    if value < 0:
        raise ValueError(f"{field}_cannot_be_negative")
    return value


def optional_decimal(row: dict[str, str], field: str) -> Decimal | None:
    value = optional_text(row, field)
    if value is None:
        return None
    return parse_decimal(value, field)


def parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field}_must_be_decimal") from exc


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError("boolean_fields_must_use_true_or_false")


def rejected_row(row_number: int, external_trade_id: str, reason: str) -> dict[str, object]:
    return {
        "row_number": row_number,
        "external_trade_id": external_trade_id,
        "status": "REJECTED",
        "reason": reason,
    }


def build_analysis_summary(
    row_results: list[dict[str, object]],
    parsed_rows: list[ParsedPaperEvidenceRow],
) -> dict[str, object]:
    status_counts = Counter(str(result.get("status", "UNKNOWN")) for result in row_results)
    rejected_rows = [result for result in row_results if result.get("status") == "REJECTED"]
    skipped_rows = [result for result in row_results if result.get("status") == "SKIPPED"]
    rejected_reasons = Counter(str(row.get("reason", "unknown")) for row in rejected_rows)
    skipped_reasons = Counter(str(row.get("reason", "unknown")) for row in skipped_rows)
    active_dates = sorted({row.closed_at.date().isoformat() for row in parsed_rows})
    first_closed_at = min((row.closed_at for row in parsed_rows), default=None)
    latest_closed_at = max((row.closed_at for row in parsed_rows), default=None)
    strategy_counts = Counter(row.strategy for row in parsed_rows)
    symbol_counts = Counter(row.symbol for row in parsed_rows)
    direction_counts = Counter(row.direction.value for row in parsed_rows)
    net_realized_pl = sum((row.realized_pl for row in parsed_rows), Decimal("0"))
    total_fees = sum((row.fees for row in parsed_rows), Decimal("0"))
    total_slippage = sum((row.slippage for row in parsed_rows), Decimal("0"))
    calendar_day_span = 0
    if first_closed_at is not None and latest_closed_at is not None:
        calendar_day_span = (latest_closed_at.date() - first_closed_at.date()).days + 1

    return {
        "status_counts": dict(sorted(status_counts.items())),
        "rejected_reasons": dict(sorted(rejected_reasons.items())),
        "skipped_reasons": dict(sorted(skipped_reasons.items())),
        "fix_queue": build_fix_queue(rejected_rows),
        "ready_or_imported_count": len(parsed_rows),
        "active_trading_days": len(active_dates),
        "calendar_day_span": calendar_day_span,
        "first_closed_at": first_closed_at.isoformat() if first_closed_at else None,
        "latest_closed_at": latest_closed_at.isoformat() if latest_closed_at else None,
        "net_realized_pl": str(net_realized_pl),
        "total_fees": str(total_fees),
        "total_slippage": str(total_slippage),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "symbol_counts": dict(sorted(symbol_counts.items())),
        "direction_counts": dict(sorted(direction_counts.items())),
        "next_actions": build_analysis_next_actions(
            rows_received=len(row_results),
            ready_or_imported_count=len(parsed_rows),
            rejected_count=len(rejected_rows),
            skipped_count=len(skipped_rows),
            active_trading_days=len(active_dates),
            calendar_day_span=calendar_day_span,
        ),
    }


def build_fix_queue(rejected_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows_by_reason: dict[str, list[int]] = {}
    for row in rejected_rows:
        reason = str(row.get("reason", "unknown"))
        rows_by_reason.setdefault(reason, []).append(int(row["row_number"]))
    return [
        {"reason": reason, "count": len(row_numbers), "rows": row_numbers}
        for reason, row_numbers in sorted(rows_by_reason.items())
    ]


def build_analysis_next_actions(
    *,
    rows_received: int,
    ready_or_imported_count: int,
    rejected_count: int,
    skipped_count: int,
    active_trading_days: int,
    calendar_day_span: int,
) -> list[str]:
    if rows_received == 0:
        return [
            "Export contains no data rows; generate a closed-trades export from the paper "
            "platform."
        ]

    actions: list[str] = []
    if rejected_count:
        actions.append(f"Fix {rejected_count} rejected row(s) before relying on this export.")
    if skipped_count:
        actions.append(
            f"Review {skipped_count} skipped row(s) to confirm they were already imported."
        )
    if ready_or_imported_count:
        actions.append(
            f"Use the {ready_or_imported_count} ready/imported row(s) only if the source "
            "reference matches the paper-platform export."
        )
    if active_trading_days < 15:
        actions.append(
            "Continue collecting evidence until at least 15 active trading days are present."
        )
    if calendar_day_span < 30:
        actions.append(
            "Continue collecting evidence until the evidence window spans at least 30 "
            "calendar days."
        )
    if not actions:
        actions.append(
            "Preflight is clean; import the export and run the Stage 14 paper-evidence "
            "report."
        )
    return actions


def paper_evidence_preflight_scope_preview(
    parsed_rows: list[ParsedPaperEvidenceRow],
    *,
    strategy_scope: str | None,
    symbol_scope: list[str] | None,
) -> dict[str, object]:
    symbols = normalized_symbol_scope(symbol_scope or [])
    scoped_rows = [
        row
        for row in parsed_rows
        if row_in_deployment_scope(row, strategy_scope=strategy_scope, symbols=symbols)
    ]
    out_of_scope_rows = [
        row
        for row in parsed_rows
        if not row_in_deployment_scope(row, strategy_scope=strategy_scope, symbols=symbols)
    ]
    return {
        "deployment_strategy": strategy_scope,
        "deployment_symbols": symbols,
        "scope_status": preflight_scope_status(
            importable_count=len(parsed_rows),
            scoped_count=len(scoped_rows),
            out_of_scope_count=len(out_of_scope_rows),
        ),
        "scoped_importable_count": len(scoped_rows),
        "out_of_scope_importable_count": len(out_of_scope_rows),
        "out_of_scope_import_summary": out_of_scope_import_summary(out_of_scope_rows),
        "scope_next_action": preflight_scope_next_action(
            strategy_scope=strategy_scope,
            symbols=symbols,
            importable_count=len(parsed_rows),
            scoped_count=len(scoped_rows),
            out_of_scope_count=len(out_of_scope_rows),
        ),
    }


def normalized_symbol_scope(symbols: list[str]) -> list[str]:
    return [symbol.strip().upper() for symbol in symbols if symbol.strip()]


def row_in_deployment_scope(
    row: ParsedPaperEvidenceRow,
    *,
    strategy_scope: str | None,
    symbols: list[str],
) -> bool:
    strategy_matches = strategy_scope is None or row.strategy == strategy_scope
    symbol_matches = not symbols or row.symbol in symbols
    return strategy_matches and symbol_matches


def preflight_scope_status(
    *,
    importable_count: int,
    scoped_count: int,
    out_of_scope_count: int,
) -> str:
    if importable_count == 0:
        return "NO_IMPORTABLE_ROWS"
    if scoped_count == importable_count:
        return "IN_SCOPE"
    if out_of_scope_count == importable_count:
        return "OUT_OF_SCOPE"
    return "MIXED_SCOPE"


def out_of_scope_import_summary(
    rows: list[ParsedPaperEvidenceRow],
) -> list[dict[str, object]]:
    counts = Counter((row.strategy, row.symbol) for row in rows)
    return [
        {
            "strategy": strategy,
            "symbol": symbol,
            "count": count,
        }
        for (strategy, symbol), count in counts.most_common(10)
    ]


def preflight_scope_next_action(
    *,
    strategy_scope: str | None,
    symbols: list[str],
    importable_count: int,
    scoped_count: int,
    out_of_scope_count: int,
) -> str:
    symbol_text = ", ".join(symbols) if symbols else "the selected symbols"
    strategy_text = strategy_scope or "the selected strategy"
    if importable_count == 0:
        return "Fix rejected rows before checking deployment scope."
    if scoped_count == importable_count:
        return "CSV importable rows match the current deployment scope."
    if out_of_scope_count == importable_count:
        return (
            f"This CSV has no importable rows for {strategy_text} covering {symbol_text}; "
            "use a paper export for the active deployment scope."
        )
    return (
        f"Only {scoped_count}/{importable_count} importable rows match {strategy_text} "
        f"covering {symbol_text}; split or replace the wrong-scope rows before relying "
        "on this export."
    )


def import_status(
    rows_received: int,
    imported_count: int,
    skipped_count: int,
    rejected_count: int,
) -> str:
    if rows_received == 0:
        return "EMPTY"
    if imported_count == rows_received:
        return "IMPORTED"
    if imported_count > 0:
        return "PARTIAL"
    if skipped_count == rows_received:
        return "SKIPPED"
    if rejected_count == rows_received:
        return "REJECTED"
    return "PARTIAL"


def preflight_status(
    rows_received: int,
    importable_count: int,
    skipped_count: int,
    rejected_count: int,
) -> str:
    if rows_received == 0:
        return "EMPTY"
    if importable_count == rows_received:
        return "READY"
    if importable_count > 0:
        return "PARTIAL"
    if skipped_count == rows_received:
        return "SKIPPED"
    if rejected_count == rows_received:
        return "REJECTED"
    return "PARTIAL"


def imported_paper_trade_evidence_payload_from_parsed(
    source: str,
    source_reference: str,
    parsed: ParsedPaperEvidenceRow,
) -> dict[str, object]:
    return {
        "source": source,
        "source_reference": source_reference,
        "external_trade_id": parsed.external_trade_id,
        "trade": {
            "strategy": parsed.strategy,
            "symbol": parsed.symbol,
            "timeframe": parsed.timeframe,
            "direction": parsed.direction.value,
            "market_regime": parsed.market_regime.value,
            "entry_price": normalized_decimal_text(parsed.entry_price),
            "exit_price": normalized_decimal_text(parsed.exit_price),
            "stop_loss": normalized_decimal_text(parsed.stop_loss),
            "take_profit": normalized_decimal_text(parsed.take_profit),
            "quantity": normalized_decimal_text(parsed.quantity),
            "risk_amount": normalized_decimal_text(parsed.risk_amount),
            "opened_at": normalized_datetime_text(parsed.opened_at),
            "closed_at": normalized_datetime_text(parsed.closed_at),
            "realized_pl": normalized_decimal_text(parsed.realized_pl),
            "r_multiple": normalized_decimal_text(
                parsed.realized_pl / parsed.risk_amount,
            ),
            "fees": normalized_decimal_text(parsed.fees),
            "slippage": normalized_decimal_text(parsed.slippage),
            "close_reason": parsed.close_reason,
        },
        "order": {
            "status": OrderStatus.FILLED.value,
            "requested_price": normalized_decimal_text(parsed.entry_price),
            "filled_price": normalized_decimal_text(parsed.entry_price),
            "quantity": normalized_decimal_text(parsed.quantity),
            "fees": normalized_decimal_text(Decimal("0")),
            "slippage": normalized_decimal_text(Decimal("0")),
            "fill_model": "paper_evidence_import",
        },
        "risk": {
            "approved": True,
            "reward_risk": normalized_decimal_text(parsed.reward_risk),
            "risk_amount": normalized_decimal_text(parsed.risk_amount),
            "position_size": normalized_decimal_text(parsed.quantity),
        },
        "journal": {
            "author": parsed.journal_author,
            "thesis": parsed.journal_thesis,
            "execution_notes": parsed.journal_execution_notes,
            "outcome_notes": parsed.journal_outcome_notes,
            "rule_followed": parsed.rule_followed,
            "emotional_override": parsed.emotional_override,
            "journaled_at": normalized_datetime_text(parsed.closed_at),
        },
    }


def imported_paper_trade_evidence_payload_from_models(
    *,
    trade: PaperTrade,
    order: PaperOrder,
    decision: RiskDecision,
    signal: Signal,
    journal: TradeJournalEntry,
) -> dict[str, object]:
    raw_payload = signal.raw_payload if isinstance(signal.raw_payload, dict) else {}
    return {
        "source": signal.source,
        "source_reference": raw_payload.get("source_reference"),
        "external_trade_id": raw_payload.get("external_trade_id"),
        "trade": {
            "strategy": trade.strategy,
            "symbol": trade.symbol,
            "timeframe": trade.timeframe,
            "direction": trade.direction.value,
            "market_regime": trade.market_regime.value,
            "entry_price": normalized_decimal_text(trade.entry_price),
            "exit_price": normalized_optional_decimal_text(trade.exit_price),
            "stop_loss": normalized_decimal_text(trade.stop_loss),
            "take_profit": normalized_decimal_text(trade.take_profit),
            "quantity": normalized_decimal_text(trade.quantity),
            "risk_amount": normalized_decimal_text(trade.risk_amount),
            "opened_at": normalized_datetime_text(trade.opened_at),
            "closed_at": normalized_datetime_text(trade.closed_at),
            "realized_pl": normalized_optional_decimal_text(trade.realized_pl),
            "r_multiple": normalized_optional_decimal_text(trade.r_multiple),
            "fees": normalized_decimal_text(trade.fees),
            "slippage": normalized_decimal_text(trade.slippage),
            "close_reason": trade.close_reason,
        },
        "order": {
            "status": order.status.value,
            "requested_price": normalized_decimal_text(order.requested_price),
            "filled_price": normalized_optional_decimal_text(order.filled_price),
            "quantity": normalized_decimal_text(order.quantity),
            "fees": normalized_decimal_text(order.fees),
            "slippage": normalized_decimal_text(order.slippage),
            "fill_model": order.fill_model,
        },
        "risk": {
            "approved": decision.approved,
            "reward_risk": normalized_optional_decimal_text(decision.reward_risk),
            "risk_amount": normalized_optional_decimal_text(decision.risk_amount),
            "position_size": normalized_optional_decimal_text(decision.position_size),
        },
        "journal": {
            "author": journal.author,
            "thesis": journal.thesis,
            "execution_notes": journal.execution_notes,
            "outcome_notes": journal.outcome_notes,
            "rule_followed": journal.rule_followed,
            "emotional_override": journal.emotional_override,
            "journaled_at": normalized_datetime_text(journal.journaled_at),
        },
    }


def imported_paper_trade_evidence_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        canonical_import_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def canonical_import_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): canonical_import_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_import_value(item) for item in value]
    if isinstance(value, Decimal):
        return normalized_decimal_text(value)
    if isinstance(value, datetime):
        return normalized_datetime_text(value)
    if isinstance(value, Enum):
        return value.value
    return value


def normalized_decimal_text(value: Decimal) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def normalized_optional_decimal_text(value: Decimal | None) -> str | None:
    return normalized_decimal_text(value) if value is not None else None


def normalized_datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def build_import_hash(source: str, source_reference: str, csv_text: str) -> str:
    return sha256(f"{source}\n{source_reference}\n{csv_text}".encode()).hexdigest()


def import_idempotency_key(source: str, external_trade_id: str) -> str:
    digest = sha256(f"{source}:{external_trade_id}".encode()).hexdigest()
    return f"paper-import:{digest}"


def paper_evidence_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            *REQUIRED_HEADERS,
            "market_regime",
            "journal_execution_notes",
            "journal_outcome_notes",
            "realized_pl",
        ]
    )
    writer.writerow(
        [
            "paper-001",
            "trend_pullback_v1",
            "BTCUSDT",
            "15m",
            "LONG",
            "2026-01-01T10:00:00Z",
            "2026-01-01T11:00:00Z",
            "100",
            "102",
            "98",
            "104",
            "1",
            "2",
            "0.50",
            "0",
            "target_hit",
            "Adonis",
            "Trend pullback followed the plan.",
            "true",
            "false",
            "TRENDING_UP",
            "Paper fill matched planned entry.",
            "Closed at planned target.",
            "1.50",
        ]
    )
    return output.getvalue()
