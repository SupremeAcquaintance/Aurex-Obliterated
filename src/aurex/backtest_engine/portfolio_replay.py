import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PORTFOLIO_REPLAY_ENGINE_VERSION = "shared-capital-spot-portfolio-v1.0.0"
PORTFOLIO_REPLAY_SCHEMA_VERSION = "aurex-shared-capital-spot-portfolio-v1"
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


class PortfolioReplayConfig(BaseModel):
    initial_capital: Decimal = Field(gt=0)
    commission_percent: Decimal = Field(default=Decimal("0.05"), ge=0)
    slippage_ticks: int = Field(default=2, ge=0)
    risk_per_trade_percent: Decimal = Field(gt=0, le=100)
    max_gross_exposure_percent: Decimal = Field(gt=0, le=100)
    max_symbol_exposure_percent: Decimal = Field(gt=0, le=100)
    max_open_positions: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_exposure_limits(self) -> "PortfolioReplayConfig":
        if self.max_symbol_exposure_percent > self.max_gross_exposure_percent:
            raise ValueError(
                "Symbol exposure cannot exceed the portfolio gross exposure limit"
            )
        return self


class PortfolioPriceMark(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    price: Decimal = Field(gt=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class PortfolioLongSpotOpportunity(BaseModel):
    opportunity_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=64)
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    entry_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    tick_size: Decimal = Field(gt=0)
    point_value: Decimal = Field(default=Decimal("1"), gt=0)
    minimum_contract: Decimal = Field(gt=0)
    priority: Decimal = Decimal("0")
    exit_reason: str = Field(min_length=1, max_length=100)
    market_regime: str = Field(default="UNKNOWN", min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("signal_at", "entry_at", "exit_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def validate_timing_and_risk(self) -> "PortfolioLongSpotOpportunity":
        if self.entry_at < self.signal_at:
            raise ValueError("Portfolio entry cannot precede its signal")
        if self.exit_at <= self.entry_at:
            raise ValueError("Portfolio exit must be later than entry")
        if self.stop_loss >= self.entry_price:
            raise ValueError("Long spot stop must be below the raw entry price")
        return self


class PortfolioReplayRequest(BaseModel):
    config: PortfolioReplayConfig
    opportunities: list[PortfolioLongSpotOpportunity] = Field(min_length=1)
    marks: list[PortfolioPriceMark] = Field(min_length=1)
    source_evidence_hashes: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_evidence_hashes")
    @classmethod
    def validate_source_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, evidence_hash in value.items():
            label = key.strip()
            candidate = evidence_hash.strip().lower()
            if not label:
                raise ValueError("Source evidence hash labels cannot be blank")
            if len(candidate) != 64 or any(char not in "0123456789abcdef" for char in candidate):
                raise ValueError("Source evidence hashes must be SHA-256 hexadecimal values")
            normalized[label] = candidate
        return normalized

    @model_validator(mode="after")
    def validate_replay_inputs(self) -> "PortfolioReplayRequest":
        opportunity_ids = [item.opportunity_id for item in self.opportunities]
        if len(opportunity_ids) != len(set(opportunity_ids)):
            raise ValueError("Portfolio opportunity IDs must be unique")

        mark_keys = [(item.symbol, item.timestamp) for item in self.marks]
        if len(mark_keys) != len(set(mark_keys)):
            raise ValueError("Portfolio price marks must be unique by symbol and timestamp")

        mark_key_set = set(mark_keys)
        event_times = {
            timestamp
            for item in self.opportunities
            for timestamp in (item.entry_at, item.exit_at)
        } | {mark.timestamp for mark in self.marks}
        for timestamp in event_times:
            active_symbols = {
                item.symbol
                for item in self.opportunities
                if item.entry_at <= timestamp <= item.exit_at
            }
            missing = sorted(
                symbol
                for symbol in active_symbols
                if (symbol, timestamp) not in mark_key_set
            )
            if missing:
                raise ValueError(
                    "Aligned portfolio marks are required for active symbols at "
                    f"{timestamp.isoformat()}: {','.join(missing)}"
                )
        return self


class PortfolioReplayTrade(BaseModel):
    sequence: int
    opportunity_id: str
    symbol: str
    signal_at: datetime
    entry_at: datetime
    exit_at: datetime
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    raw_exit_price: Decimal
    exit_fill_price: Decimal
    stop_loss: Decimal
    quantity: Decimal
    entry_notional: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    slippage: Decimal
    gross_pl: Decimal
    realized_pl: Decimal
    exit_reason: str
    market_regime: str

    model_config = ConfigDict(extra="forbid")


class PortfolioReplayRejection(BaseModel):
    opportunity_id: str
    symbol: str
    entry_at: datetime
    reason: str

    model_config = ConfigDict(extra="forbid")


class PortfolioEquitySnapshot(BaseModel):
    timestamp: datetime
    cash: Decimal
    marked_position_value: Decimal
    equity: Decimal
    gross_exposure_percent: Decimal
    open_positions: int
    drawdown: Decimal

    model_config = ConfigDict(extra="forbid")


class PortfolioReplayResult(BaseModel):
    schema_version: Literal["aurex-shared-capital-spot-portfolio-v1"] = (
        PORTFOLIO_REPLAY_SCHEMA_VERSION
    )
    engine_version: Literal["shared-capital-spot-portfolio-v1.0.0"] = (
        PORTFOLIO_REPLAY_ENGINE_VERSION
    )
    request_evidence_hash: str
    result_evidence_hash: str
    initial_capital: Decimal
    final_equity: Decimal
    total_net_pl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    accepted_trades: int
    rejected_opportunities: int
    trades: list[PortfolioReplayTrade]
    rejections: list[PortfolioReplayRejection]
    equity_curve: list[PortfolioEquitySnapshot]

    model_config = ConfigDict(extra="forbid")


class PortfolioReplayAudit(BaseModel):
    status: Literal["PASS", "BLOCKED"]
    request_evidence_hash_matches: bool
    stored_result_evidence_hash_matches: bool
    deterministic_replay_matches: bool
    replayed_result_evidence_hash: str
    reasons: list[str]

    model_config = ConfigDict(extra="forbid")


@dataclass
class _OpenPosition:
    opportunity: PortfolioLongSpotOpportunity
    quantity: Decimal
    entry_fill_price: Decimal
    entry_notional: Decimal
    entry_fee: Decimal


@dataclass
class _EntryCandidate:
    opportunity: PortfolioLongSpotOpportunity
    entry_fill_price: Decimal
    desired_quantity: Decimal
    desired_notional: Decimal


def run_shared_capital_spot_portfolio(
    request: PortfolioReplayRequest,
) -> PortfolioReplayResult:
    opportunities = sorted(
        request.opportunities,
        key=lambda item: (item.entry_at, -item.priority, item.symbol, item.opportunity_id),
    )
    marks = sorted(request.marks, key=lambda item: (item.timestamp, item.symbol))
    request_hash = portfolio_evidence_hash(
        {
            "schema_version": PORTFOLIO_REPLAY_SCHEMA_VERSION,
            "engine_version": PORTFOLIO_REPLAY_ENGINE_VERSION,
            "config": request.config,
            "opportunities": opportunities,
            "marks": marks,
            "source_evidence_hashes": dict(sorted(request.source_evidence_hashes.items())),
        }
    )

    entries_by_time = group_opportunities(opportunities, "entry_at")
    exits_by_time = group_opportunities(opportunities, "exit_at")
    marks_by_time: dict[datetime, list[PortfolioPriceMark]] = {}
    for mark in marks:
        marks_by_time.setdefault(mark.timestamp, []).append(mark)
    event_times = sorted(set(entries_by_time) | set(exits_by_time) | set(marks_by_time))

    cash = request.config.initial_capital
    peak_equity = request.config.initial_capital
    max_drawdown = ZERO
    latest_marks: dict[str, Decimal] = {}
    positions: dict[str, _OpenPosition] = {}
    trades: list[PortfolioReplayTrade] = []
    rejections: list[PortfolioReplayRejection] = []
    equity_curve: list[PortfolioEquitySnapshot] = []

    for timestamp in event_times:
        for mark in marks_by_time.get(timestamp, []):
            latest_marks[mark.symbol] = mark.price

        for opportunity in sorted(
            exits_by_time.get(timestamp, []),
            key=lambda item: (item.symbol, item.opportunity_id),
        ):
            position = positions.get(opportunity.symbol)
            if (
                position is None
                or position.opportunity.opportunity_id != opportunity.opportunity_id
            ):
                continue
            positions.pop(opportunity.symbol)
            exit_fill = round_down_to_increment(
                opportunity.exit_price
                - Decimal(request.config.slippage_ticks) * opportunity.tick_size,
                opportunity.tick_size,
            )
            if exit_fill <= ZERO:
                raise ValueError("Adverse slippage produced a non-positive exit fill")
            exit_notional = exit_fill * position.quantity * opportunity.point_value
            exit_fee = exit_notional * percent_rate(request.config.commission_percent)
            cash += exit_notional - exit_fee
            gross_pl = (
                (exit_fill - position.entry_fill_price)
                * position.quantity
                * opportunity.point_value
            )
            realized_pl = gross_pl - position.entry_fee - exit_fee
            slippage = (
                (position.entry_fill_price - opportunity.entry_price)
                + (opportunity.exit_price - exit_fill)
            ) * position.quantity * opportunity.point_value
            trades.append(
                PortfolioReplayTrade(
                    sequence=len(trades) + 1,
                    opportunity_id=opportunity.opportunity_id,
                    symbol=opportunity.symbol,
                    signal_at=opportunity.signal_at,
                    entry_at=opportunity.entry_at,
                    exit_at=opportunity.exit_at,
                    raw_entry_price=opportunity.entry_price,
                    entry_fill_price=position.entry_fill_price,
                    raw_exit_price=opportunity.exit_price,
                    exit_fill_price=exit_fill,
                    stop_loss=opportunity.stop_loss,
                    quantity=position.quantity,
                    entry_notional=position.entry_notional,
                    entry_fee=position.entry_fee,
                    exit_fee=exit_fee,
                    slippage=slippage,
                    gross_pl=gross_pl,
                    realized_pl=realized_pl,
                    exit_reason=opportunity.exit_reason,
                    market_regime=opportunity.market_regime,
                )
            )

        cash = allocate_entries(
            request.config,
            entries_by_time.get(timestamp, []),
            latest_marks,
            positions,
            rejections,
            cash,
            timestamp,
        )
        marked_value = marked_position_value(positions, latest_marks)
        equity = cash + marked_value
        peak_equity = max(peak_equity, equity)
        drawdown = peak_equity - equity
        max_drawdown = max(max_drawdown, drawdown)
        exposure_percent = (
            marked_value / equity * ONE_HUNDRED if equity > ZERO else ONE_HUNDRED
        )
        equity_curve.append(
            PortfolioEquitySnapshot(
                timestamp=timestamp,
                cash=cash,
                marked_position_value=marked_value,
                equity=equity,
                gross_exposure_percent=exposure_percent,
                open_positions=len(positions),
                drawdown=drawdown,
            )
        )

    if positions:
        raise ValueError("Portfolio replay ended with open positions")

    final_equity = cash
    realized_values = [trade.realized_pl for trade in trades]
    gross_profit = sum((value for value in realized_values if value > ZERO), ZERO)
    gross_loss = abs(sum((value for value in realized_values if value < ZERO), ZERO))
    profit_factor = gross_profit / gross_loss if gross_loss > ZERO else None
    result_payload = {
        "schema_version": PORTFOLIO_REPLAY_SCHEMA_VERSION,
        "engine_version": PORTFOLIO_REPLAY_ENGINE_VERSION,
        "request_evidence_hash": request_hash,
        "initial_capital": request.config.initial_capital,
        "final_equity": final_equity,
        "total_net_pl": final_equity - request.config.initial_capital,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
        "accepted_trades": len(trades),
        "rejected_opportunities": len(rejections),
        "trades": trades,
        "rejections": rejections,
        "equity_curve": equity_curve,
    }
    return PortfolioReplayResult(
        **result_payload,
        result_evidence_hash=portfolio_evidence_hash(result_payload),
    )


def audit_shared_capital_spot_portfolio(
    request: PortfolioReplayRequest,
    stored: PortfolioReplayResult,
) -> PortfolioReplayAudit:
    replayed = run_shared_capital_spot_portfolio(request)
    request_hash_matches = (
        stored.request_evidence_hash == replayed.request_evidence_hash
    )
    stored_payload = stored.model_dump(exclude={"result_evidence_hash"})
    stored_hash_matches = (
        stored.result_evidence_hash == portfolio_evidence_hash(stored_payload)
    )
    replay_matches = stored.model_dump() == replayed.model_dump()
    reasons: list[str] = []
    if not request_hash_matches:
        reasons.append("request_evidence_hash_mismatch")
    if not stored_hash_matches:
        reasons.append("stored_result_evidence_hash_mismatch")
    if not replay_matches:
        reasons.append("deterministic_replay_mismatch")
    return PortfolioReplayAudit(
        status="PASS" if not reasons else "BLOCKED",
        request_evidence_hash_matches=request_hash_matches,
        stored_result_evidence_hash_matches=stored_hash_matches,
        deterministic_replay_matches=replay_matches,
        replayed_result_evidence_hash=replayed.result_evidence_hash,
        reasons=reasons,
    )


def allocate_entries(
    config: PortfolioReplayConfig,
    opportunities: list[PortfolioLongSpotOpportunity],
    latest_marks: dict[str, Decimal],
    positions: dict[str, _OpenPosition],
    rejections: list[PortfolioReplayRejection],
    cash: Decimal,
    timestamp: datetime,
) -> Decimal:
    ordered = sorted(
        opportunities,
        key=lambda item: (-item.priority, item.symbol, item.opportunity_id),
    )
    eligible: list[PortfolioLongSpotOpportunity] = []
    selected_symbols = set(positions)
    for opportunity in ordered:
        if opportunity.symbol in selected_symbols:
            reason = (
                "symbol_position_already_open"
                if opportunity.symbol in positions
                else "duplicate_symbol_entry_batch"
            )
            reject(rejections, opportunity, reason)
            continue
        selected_symbols.add(opportunity.symbol)
        eligible.append(opportunity)

    available_slots = max(0, config.max_open_positions - len(positions))
    selected = eligible[:available_slots]
    for opportunity in eligible[available_slots:]:
        reject(rejections, opportunity, "max_open_positions_priority_rejection")
    if not selected:
        return cash

    current_marked_value = marked_position_value(positions, latest_marks)
    equity = cash + current_marked_value
    if equity <= ZERO:
        for opportunity in selected:
            reject(rejections, opportunity, "non_positive_portfolio_equity")
        return cash

    candidates: list[_EntryCandidate] = []
    risk_budget = equity * percent_rate(config.risk_per_trade_percent)
    symbol_cap = equity * percent_rate(config.max_symbol_exposure_percent)
    for opportunity in selected:
        entry_fill = round_up_to_increment(
            opportunity.entry_price
            + Decimal(config.slippage_ticks) * opportunity.tick_size,
            opportunity.tick_size,
        )
        risk_per_contract = (
            entry_fill - opportunity.stop_loss
        ) * opportunity.point_value
        if risk_per_contract <= ZERO:
            reject(rejections, opportunity, "non_positive_fill_adjusted_risk")
            continue
        risk_quantity = risk_budget / risk_per_contract
        symbol_cap_quantity = symbol_cap / (
            entry_fill * opportunity.point_value
        )
        desired_quantity = min(risk_quantity, symbol_cap_quantity)
        desired_notional = (
            desired_quantity * entry_fill * opportunity.point_value
        )
        candidates.append(
            _EntryCandidate(
                opportunity=opportunity,
                entry_fill_price=entry_fill,
                desired_quantity=desired_quantity,
                desired_notional=desired_notional,
            )
        )

    if not candidates:
        return cash

    gross_cap = equity * percent_rate(config.max_gross_exposure_percent)
    gross_capacity = max(ZERO, gross_cap - current_marked_value)
    desired_notional_total = sum(
        (candidate.desired_notional for candidate in candidates), ZERO
    )
    commission_rate = percent_rate(config.commission_percent)
    desired_cash_total = desired_notional_total * (Decimal("1") + commission_rate)
    scale = min(
        Decimal("1"),
        gross_capacity / desired_notional_total if desired_notional_total > ZERO else ZERO,
        cash / desired_cash_total if desired_cash_total > ZERO else ZERO,
    )

    for candidate in candidates:
        opportunity = candidate.opportunity
        quantity = round_down_to_increment(
            candidate.desired_quantity * scale,
            opportunity.minimum_contract,
        )
        if quantity <= ZERO:
            reject(rejections, opportunity, "shared_capital_or_rounding_rejection")
            continue
        entry_notional = (
            quantity * candidate.entry_fill_price * opportunity.point_value
        )
        entry_fee = entry_notional * commission_rate
        required_cash = entry_notional + entry_fee
        if required_cash > cash:
            reject(rejections, opportunity, "insufficient_cash_after_rounding")
            continue
        cash -= required_cash
        positions[opportunity.symbol] = _OpenPosition(
            opportunity=opportunity,
            quantity=quantity,
            entry_fill_price=candidate.entry_fill_price,
            entry_notional=entry_notional,
            entry_fee=entry_fee,
        )
    return cash


def reject(
    rejections: list[PortfolioReplayRejection],
    opportunity: PortfolioLongSpotOpportunity,
    reason: str,
) -> None:
    rejections.append(
        PortfolioReplayRejection(
            opportunity_id=opportunity.opportunity_id,
            symbol=opportunity.symbol,
            entry_at=opportunity.entry_at,
            reason=reason,
        )
    )


def group_opportunities(
    opportunities: list[PortfolioLongSpotOpportunity],
    field: Literal["entry_at", "exit_at"],
) -> dict[datetime, list[PortfolioLongSpotOpportunity]]:
    grouped: dict[datetime, list[PortfolioLongSpotOpportunity]] = {}
    for opportunity in opportunities:
        grouped.setdefault(getattr(opportunity, field), []).append(opportunity)
    return grouped


def marked_position_value(
    positions: dict[str, _OpenPosition],
    latest_marks: dict[str, Decimal],
) -> Decimal:
    missing = sorted(symbol for symbol in positions if symbol not in latest_marks)
    if missing:
        raise ValueError(f"Missing marks for open positions: {','.join(missing)}")
    return sum(
        (
            position.quantity
            * latest_marks[symbol]
            * position.opportunity.point_value
            for symbol, position in positions.items()
        ),
        ZERO,
    )


def percent_rate(value: Decimal) -> Decimal:
    return value / ONE_HUNDRED


def round_down_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_FLOOR) * increment


def round_up_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_CEILING) * increment


def ensure_utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("Portfolio replay timestamps must include a timezone")
    return value.astimezone(UTC)


def portfolio_evidence_hash(payload: object) -> str:
    serialized = json.dumps(
        canonical_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


def canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump())
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, datetime):
        return ensure_utc(value).isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value
