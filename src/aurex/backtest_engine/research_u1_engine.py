from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3EquitySnapshot,
    R3ResearchReplayAudit,
    cost_rate,
    round_down_to_increment,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_RESEARCH_ENGINE_VERSION = "u1-volatility-managed-broad-spot-engine-v1.0.0"
U1_REPLAY_SCHEMA_VERSION = "aurex-u1-volatility-managed-broad-spot-replay-v1"
ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")

U1OpportunityReason = Literal["ENTRY_ACCEPTED", "ZERO_QUANTITY_AFTER_ROUNDING"]


@dataclass(frozen=True)
class U1PreparedMarketData:
    symbols: tuple[str, ...]
    timestamps: tuple[datetime, ...]
    candles_by_symbol: dict[str, tuple[R3Candle | None, ...]]
    first_missing_by_symbol: dict[str, datetime | None]
    actual_rows_by_symbol: dict[str, int]
    series_evidence_hashes: dict[str, str]
    market_data_evidence_hash: str
    data_start: datetime
    data_end: datetime


class U1ResearchReplayConfig(BaseModel):
    variant_id: Literal["volatility_managed_broad_spot_beta_v1"] = (
        "volatility_managed_broad_spot_beta_v1"
    )
    variant_version: Literal["1.0.0"] = "1.0.0"
    variant_role: Literal["PRIMARY", "BENCHMARK"]
    timeframe_hours: Literal[4] = 4
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    lookback_bars: Literal[168] = 168
    close_observations: Literal[169] = 169
    rebalance_bars: Literal[168] = 168
    annualization_intervals: Literal[2190] = 2190
    target_annualized_variance: Decimal = Field(default=Decimal("0.36"), gt=0)
    minimum_active_markets: Literal[20] = 20
    evaluation_start: datetime
    evaluation_end: datetime
    baseline_decision_symbols: list[str] = Field(min_length=20)
    omitted_symbols: list[str] = Field(default_factory=list, max_length=1)
    initial_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    max_gross_exposure_percent: Decimal = Field(default=Decimal("100"), gt=0)
    quantity_increment: Decimal = Field(default=Decimal("0.00000001"), gt=0)
    price_increment: Decimal = Field(default=Decimal("0.00000001"), gt=0)
    commission_percent_per_side: Decimal = Field(default=Decimal("0.10"), ge=0)
    adverse_slippage_percent_per_side: Decimal = Field(
        default=Decimal("0.05"), ge=0
    )
    cost_multiplier: Decimal = Field(gt=0)
    discovery_charter_evidence_hash: str
    theory_screen_evidence_hash: str
    primary_protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    market_data_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("baseline_decision_symbols", "omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})

    @field_validator(
        "discovery_charter_evidence_hash",
        "theory_screen_evidence_hash",
        "primary_protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "market_data_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_config(self) -> U1ResearchReplayConfig:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("U1 evaluation end must follow its start")
        if len(self.baseline_decision_symbols) != len(
            set(self.baseline_decision_symbols)
        ):
            raise ValueError("U1 baseline symbols must be unique")
        if not set(self.omitted_symbols).issubset(self.baseline_decision_symbols):
            raise ValueError("U1 omitted symbol must belong to the baseline universe")
        if len(self.active_symbols) < self.minimum_active_markets:
            raise ValueError("U1 active universe cannot satisfy minimum breadth")
        expected = {
            "target_annualized_variance": Decimal("0.36"),
            "initial_capital": Decimal("1000"),
            "max_gross_exposure_percent": Decimal("100"),
            "quantity_increment": Decimal("0.00000001"),
            "price_increment": Decimal("0.00000001"),
            "commission_percent_per_side": Decimal("0.10"),
            "adverse_slippage_percent_per_side": Decimal("0.05"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("U1 replay parameters differ from the frozen protocol")
        if self.cost_multiplier not in {
            Decimal("1"),
            Decimal("1.5"),
            Decimal("2"),
        }:
            raise ValueError("U1 cost multiplier is outside the frozen grid")
        return self

    @property
    def active_symbols(self) -> list[str]:
        omitted = set(self.omitted_symbols)
        return [
            symbol for symbol in self.baseline_decision_symbols if symbol not in omitted
        ]


class U1ResearchTrade(BaseModel):
    sequence: int = Field(gt=0)
    symbol: str
    entry_at: datetime
    exit_at: datetime
    entry_bar_timestamp: datetime
    exit_bar_timestamp: datetime
    exit_reason: Literal[
        "REBALANCE",
        "END_OF_WINDOW",
        "MARKET_TERMINATION_WRITE_OFF",
    ]
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    raw_exit_price: Decimal
    exit_fill_price: Decimal
    quantity: Decimal
    entry_notional: Decimal
    exit_notional: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    entry_slippage_cost: Decimal
    exit_slippage_cost: Decimal
    total_slippage_cost: Decimal
    raw_price_pl: Decimal
    net_pl: Decimal

    model_config = ConfigDict(extra="forbid")


class U1OpportunityRecord(BaseModel):
    rebalance_at: datetime
    symbol: str
    active_market_count: int = Field(gt=0)
    target_exposure: Decimal = Field(ge=0, le=1)
    target_fill_notional: Decimal = Field(ge=0)
    raw_entry_price: Decimal = Field(gt=0)
    entry_fill_price: Decimal = Field(gt=0)
    desired_quantity: Decimal = Field(ge=0)
    accepted_quantity: Decimal = Field(ge=0)
    accepted_entry: bool
    reason: U1OpportunityReason

    model_config = ConfigDict(extra="forbid")


class U1VolatilitySignalRecord(BaseModel):
    rebalance_at: datetime
    signal_at: datetime
    lookback_start_at: datetime
    active_market_count: int = Field(gt=0)
    lookback_intervals: Literal[168] = 168
    realized_annualized_variance: Decimal = Field(ge=0)
    target_annualized_variance: Literal["0.36"] = "0.36"
    target_exposure: Decimal = Field(ge=0, le=1)
    variant_role: Literal["PRIMARY", "BENCHMARK"]

    model_config = ConfigDict(extra="forbid")


class U1AvailabilityEvent(BaseModel):
    timestamp: datetime
    symbol: str
    event: Literal["TERMINAL_MARKET_UNAVAILABLE"] = "TERMINAL_MARKET_UNAVAILABLE"
    held_position_written_off: bool
    permanently_removed: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class U1RebalanceBreadth(BaseModel):
    rebalance_at: datetime
    active_symbol_count: int = Field(ge=0)
    accepted_symbol_count: int = Field(ge=0)
    target_exposure: Decimal = Field(ge=0, le=1)

    model_config = ConfigDict(extra="forbid")


class U1ReplayMetrics(BaseModel):
    initial_capital: Decimal
    final_equity: Decimal
    net_pl: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None
    raw_gross_profit: Decimal
    raw_gross_loss: Decimal
    raw_profit_factor: Decimal | None
    maximum_drawdown: Decimal
    maximum_drawdown_percent: Decimal
    completed_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    accepted_entries: int = Field(ge=0)
    rejected_opportunities: int = Field(ge=0)
    total_commission: Decimal = Field(ge=0)
    total_slippage: Decimal = Field(ge=0)
    turnover: Decimal = Field(ge=0)
    active_days: int = Field(ge=0)
    average_gross_exposure_percent: Decimal = Field(ge=0)
    maximum_gross_exposure_percent: Decimal = Field(ge=0)
    realized_equity_volatility: Decimal = Field(ge=0)
    return_to_drawdown: Decimal | None
    average_target_exposure: Decimal = Field(ge=0, le=1)
    minimum_target_exposure: Decimal = Field(ge=0, le=1)
    maximum_target_exposure: Decimal = Field(ge=0, le=1)
    symbol_positive_raw_profit: dict[str, Decimal]
    maximum_single_symbol_gross_profit_fraction: Decimal | None
    top_five_gross_profit_fraction: Decimal | None
    termination_writeoff_count: int = Field(ge=0)
    termination_writeoff_net_pl: Decimal
    minimum_active_symbol_count_at_rebalance: int = Field(ge=0)
    average_active_symbol_count_at_rebalance: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class U1ResearchReplayResult(BaseModel):
    schema_version: Literal["aurex-u1-volatility-managed-broad-spot-replay-v1"] = (
        U1_REPLAY_SCHEMA_VERSION
    )
    engine_version: Literal["u1-volatility-managed-broad-spot-engine-v1.0.0"] = (
        U1_RESEARCH_ENGINE_VERSION
    )
    config: U1ResearchReplayConfig
    request_evidence_hash: str
    result_evidence_hash: str
    metrics: U1ReplayMetrics
    trades: list[U1ResearchTrade]
    opportunities: list[U1OpportunityRecord]
    signals: list[U1VolatilitySignalRecord]
    equity_curve: list[R3EquitySnapshot]
    availability_events: list[U1AvailabilityEvent]
    rebalance_breadth: list[U1RebalanceBreadth]

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result_hash(self) -> U1ResearchReplayResult:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("U1 replay result hash does not match its evidence")
        return self


@dataclass
class _OpenPosition:
    symbol: str
    entry_at: datetime
    entry_bar_timestamp: datetime
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    quantity: Decimal
    entry_notional: Decimal
    entry_fee: Decimal


def prepare_u1_market_data(
    candles_by_symbol: dict[str, list[R3Candle] | tuple[R3Candle, ...]],
    *,
    data_start: datetime,
    data_end: datetime,
) -> U1PreparedMarketData:
    start = normalize_timestamp(data_start)
    end = normalize_timestamp(data_end)
    interval = timedelta(hours=4)
    if end <= start or (end - start) % interval:
        raise ValueError("U1 data window must be positive and align to the 4h grid")
    if not candles_by_symbol:
        raise ValueError("U1 market data requires at least one symbol")
    if any(symbol != symbol.strip().upper() for symbol in candles_by_symbol):
        raise ValueError("U1 market-data symbols must be normalized uppercase")
    symbols = tuple(sorted(candles_by_symbol))
    expected_rows = (end - start) // interval
    timestamps = tuple(start + index * interval for index in range(expected_rows))
    padded_by_symbol: dict[str, tuple[R3Candle | None, ...]] = {}
    first_missing_by_symbol: dict[str, datetime | None] = {}
    actual_rows_by_symbol: dict[str, int] = {}
    series_hashes: dict[str, str] = {}
    for symbol in symbols:
        actual = tuple(candles_by_symbol[symbol])
        if not actual:
            raise ValueError(f"U1 data has leading missing candles: {symbol}")
        if len(actual) > expected_rows:
            raise ValueError(f"U1 data extends past its partition: {symbol}")
        if tuple(candle.timestamp for candle in actual) != timestamps[: len(actual)]:
            raise ValueError(
                f"U1 data has an internal, duplicate, or resumed gap: {symbol}"
            )
        missing_count = expected_rows - len(actual)
        padded = cast(tuple[R3Candle | None, ...], actual + ((None,) * missing_count))
        first_missing = timestamps[len(actual)] if missing_count else None
        padded_by_symbol[symbol] = padded
        first_missing_by_symbol[symbol] = first_missing
        actual_rows_by_symbol[symbol] = len(actual)
        series_hashes[symbol] = universe_evidence_hash(
            {
                "symbol": symbol,
                "timeframe": "4h",
                "actual_candles": actual,
                "first_missing_at": first_missing,
                "synthetic_candles": [],
            }
        )
    market_data_hash = universe_evidence_hash(
        {
            "symbols": symbols,
            "data_start": start,
            "data_end": end,
            "series_evidence_hashes": series_hashes,
        }
    )
    return U1PreparedMarketData(
        symbols=symbols,
        timestamps=timestamps,
        candles_by_symbol=padded_by_symbol,
        first_missing_by_symbol=first_missing_by_symbol,
        actual_rows_by_symbol=actual_rows_by_symbol,
        series_evidence_hashes=series_hashes,
        market_data_evidence_hash=market_data_hash,
        data_start=start,
        data_end=end,
    )


def calculate_u1_exposure(
    market_data: U1PreparedMarketData,
    *,
    signal_index: int,
    active_symbols: list[str],
    target_annualized_variance: Decimal = Decimal("0.36"),
) -> tuple[Decimal, Decimal]:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        return _calculate_u1_exposure(
            market_data,
            signal_index=signal_index,
            active_symbols=active_symbols,
            target_annualized_variance=target_annualized_variance,
        )


def _calculate_u1_exposure(
    market_data: U1PreparedMarketData,
    *,
    signal_index: int,
    active_symbols: list[str],
    target_annualized_variance: Decimal,
) -> tuple[Decimal, Decimal]:
    if len(active_symbols) < 1:
        raise ValueError("U1 exposure requires an active market")
    lookback_start = signal_index - 168
    if lookback_start < 0:
        raise ValueError("U1 exposure has insufficient warmup")
    broad_returns: list[Decimal] = []
    for index in range(lookback_start + 1, signal_index + 1):
        constituent_returns: list[Decimal] = []
        for symbol in sorted(active_symbols):
            previous = market_data.candles_by_symbol[symbol][index - 1]
            current = market_data.candles_by_symbol[symbol][index]
            if previous is None or current is None:
                raise ValueError("U1 signal window contains missing market data")
            constituent_returns.append((current.close / previous.close).ln())
        broad_returns.append(
            sum(constituent_returns, ZERO) / Decimal(len(constituent_returns))
        )
    if len(broad_returns) != 168:
        raise ValueError("U1 signal must contain exactly 168 broad returns")
    realized_variance = (
        sum((item * item for item in broad_returns), ZERO)
        / Decimal(168)
        * Decimal(2190)
    )
    exposure = (
        ONE
        if realized_variance == ZERO
        else min(ONE, target_annualized_variance / realized_variance)
    )
    return realized_variance, exposure


def run_u1_research_replay(
    config: U1ResearchReplayConfig,
    market_data: U1PreparedMarketData,
) -> U1ResearchReplayResult:
    with localcontext() as context:
        context.prec = config.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_u1_research_replay(config, market_data)


def _run_u1_research_replay(
    config: U1ResearchReplayConfig,
    market_data: U1PreparedMarketData,
) -> U1ResearchReplayResult:
    validate_u1_replay_inputs(config, market_data)
    timestamp_to_index = {
        timestamp: index for index, timestamp in enumerate(market_data.timestamps)
    }
    start_index = timestamp_to_index[config.evaluation_start]
    end_index = timestamp_to_index.get(config.evaluation_end, len(market_data.timestamps))
    if end_index == len(market_data.timestamps):
        if config.evaluation_end != market_data.data_end:
            raise ValueError("U1 evaluation end is not aligned to market data")
    if end_index <= start_index:
        raise ValueError("U1 evaluation contains no complete candle")
    if start_index - 1 - config.lookback_bars < 0:
        raise ValueError("U1 evaluation has insufficient signal warmup")

    request_hash = universe_evidence_hash(
        {
            "schema_version": U1_REPLAY_SCHEMA_VERSION,
            "engine_version": U1_RESEARCH_ENGINE_VERSION,
            "config": config,
            "series_evidence_hashes": market_data.series_evidence_hashes,
        }
    )
    cash = config.initial_capital
    positions: dict[str, _OpenPosition] = {}
    trades: list[U1ResearchTrade] = []
    opportunities: list[U1OpportunityRecord] = []
    signals: list[U1VolatilitySignalRecord] = []
    equity_curve: list[R3EquitySnapshot] = []
    availability_events: list[U1AvailabilityEvent] = []
    rebalance_breadth: list[U1RebalanceBreadth] = []
    terminated = {
        symbol
        for symbol in config.active_symbols
        if market_data.first_missing_by_symbol[symbol] is not None
        and cast(datetime, market_data.first_missing_by_symbol[symbol])
        < config.evaluation_start
    }
    peak_equity = config.initial_capital
    maximum_drawdown = ZERO
    maximum_drawdown_percent = ZERO

    for index in range(start_index, end_index):
        timestamp = market_data.timestamps[index]
        for symbol in sorted(config.active_symbols):
            if (
                symbol not in terminated
                and market_data.first_missing_by_symbol[symbol] == timestamp
            ):
                was_held = symbol in positions
                if was_held:
                    cash = close_u1_position(
                        config=config,
                        positions=positions,
                        trades=trades,
                        symbol=symbol,
                        raw_exit_price=ZERO,
                        exit_at=timestamp,
                        exit_bar_timestamp=timestamp,
                        exit_reason="MARKET_TERMINATION_WRITE_OFF",
                        cash=cash,
                    )
                terminated.add(symbol)
                availability_events.append(
                    U1AvailabilityEvent(
                        timestamp=timestamp,
                        symbol=symbol,
                        held_position_written_off=was_held,
                    )
                )

        is_rebalance = (index - start_index) % config.rebalance_bars == 0
        if is_rebalance:
            for symbol in sorted(list(positions)):
                candle = market_data.candles_by_symbol[symbol][index]
                if candle is None:
                    raise ValueError("U1 held market disappeared without terminal event")
                cash = close_u1_position(
                    config=config,
                    positions=positions,
                    trades=trades,
                    symbol=symbol,
                    raw_exit_price=candle.open,
                    exit_at=timestamp,
                    exit_bar_timestamp=timestamp,
                    exit_reason="REBALANCE",
                    cash=cash,
                )
            active = [
                symbol
                for symbol in config.active_symbols
                if symbol not in terminated
            ]
            if len(active) < config.minimum_active_markets:
                raise ValueError("U1 active market breadth fell below its frozen floor")
            signal_index = index - 1
            variance, primary_exposure = calculate_u1_exposure(
                market_data,
                signal_index=signal_index,
                active_symbols=active,
                target_annualized_variance=config.target_annualized_variance,
            )
            target_exposure = (
                ONE if config.variant_role == "BENCHMARK" else primary_exposure
            )
            signals.append(
                U1VolatilitySignalRecord(
                    rebalance_at=timestamp,
                    signal_at=market_data.timestamps[signal_index] + timedelta(hours=4),
                    lookback_start_at=market_data.timestamps[
                        signal_index - config.lookback_bars
                    ]
                    + timedelta(hours=4),
                    active_market_count=len(active),
                    realized_annualized_variance=variance,
                    target_exposure=target_exposure,
                    variant_role=config.variant_role,
                )
            )
            cash, accepted_count = allocate_u1_entries(
                config=config,
                market_data=market_data,
                index=index,
                active_symbols=active,
                target_exposure=target_exposure,
                positions=positions,
                opportunities=opportunities,
                cash=cash,
            )
            rebalance_breadth.append(
                U1RebalanceBreadth(
                    rebalance_at=timestamp,
                    active_symbol_count=len(active),
                    accepted_symbol_count=accepted_count,
                    target_exposure=target_exposure,
                )
            )

        is_final_bar = index == end_index - 1
        if is_final_bar:
            for symbol in sorted(list(positions)):
                candle = market_data.candles_by_symbol[symbol][index]
                if candle is None:
                    raise ValueError("U1 final held market lacks a close")
                cash = close_u1_position(
                    config=config,
                    positions=positions,
                    trades=trades,
                    symbol=symbol,
                    raw_exit_price=candle.close,
                    exit_at=config.evaluation_end,
                    exit_bar_timestamp=timestamp,
                    exit_reason="END_OF_WINDOW",
                    cash=cash,
                )
            marked_value = ZERO
        else:
            marked_value = sum(
                (
                    position.quantity
                    * _required_candle(market_data, symbol, index).close
                    for symbol, position in positions.items()
                ),
                ZERO,
            )
        equity = cash + marked_value
        peak_equity = max(peak_equity, equity)
        drawdown = peak_equity - equity
        drawdown_percent = (
            drawdown / peak_equity * ONE_HUNDRED if peak_equity > ZERO else ZERO
        )
        maximum_drawdown = max(maximum_drawdown, drawdown)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent, drawdown_percent
        )
        exposure = marked_value / equity * ONE_HUNDRED if equity > ZERO else ZERO
        equity_curve.append(
            R3EquitySnapshot(
                timestamp=timestamp + timedelta(hours=4),
                cash=cash,
                marked_position_value=marked_value,
                equity=equity,
                gross_exposure_percent=exposure,
                open_positions=len(positions),
                drawdown=drawdown,
                drawdown_percent=drawdown_percent,
            )
        )

    if positions:
        raise ValueError("U1 replay ended with open positions")
    metrics = build_u1_metrics(
        config=config,
        final_equity=cash,
        trades=trades,
        opportunities=opportunities,
        signals=signals,
        equity_curve=equity_curve,
        availability_events=availability_events,
        rebalance_breadth=rebalance_breadth,
        maximum_drawdown=maximum_drawdown,
        maximum_drawdown_percent=maximum_drawdown_percent,
    )
    result_payload = {
        "schema_version": U1_REPLAY_SCHEMA_VERSION,
        "engine_version": U1_RESEARCH_ENGINE_VERSION,
        "config": config,
        "request_evidence_hash": request_hash,
        "metrics": metrics,
        "trades": trades,
        "opportunities": opportunities,
        "signals": signals,
        "equity_curve": equity_curve,
        "availability_events": availability_events,
        "rebalance_breadth": rebalance_breadth,
    }
    return U1ResearchReplayResult(
        **result_payload,
        result_evidence_hash=universe_evidence_hash(result_payload),
    )


def validate_u1_replay_inputs(
    config: U1ResearchReplayConfig,
    market_data: U1PreparedMarketData,
) -> None:
    if tuple(config.baseline_decision_symbols) != market_data.symbols:
        raise ValueError("U1 baseline symbols do not match prepared market data")
    if config.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("U1 market-data hash does not match the config")
    if not (
        market_data.data_start
        <= config.evaluation_start
        < config.evaluation_end
        <= market_data.data_end
    ):
        raise ValueError("U1 replay must remain inside its prepared partition")
    if config.evaluation_start not in set(market_data.timestamps):
        raise ValueError("U1 evaluation start is not a candle-open timestamp")
    if (
        config.evaluation_end not in set(market_data.timestamps)
        and config.evaluation_end != market_data.data_end
    ):
        raise ValueError("U1 evaluation end is not a valid exclusive boundary")


def allocate_u1_entries(
    *,
    config: U1ResearchReplayConfig,
    market_data: U1PreparedMarketData,
    index: int,
    active_symbols: list[str],
    target_exposure: Decimal,
    positions: dict[str, _OpenPosition],
    opportunities: list[U1OpportunityRecord],
    cash: Decimal,
) -> tuple[Decimal, int]:
    if positions:
        raise ValueError("U1 allocation requires all prior positions exited")
    if not ZERO <= target_exposure <= ONE:
        raise ValueError("U1 target exposure must be between zero and one")
    commission_rate = cost_rate(
        config.commission_percent_per_side, config.cost_multiplier
    )
    slippage_rate = cost_rate(
        config.adverse_slippage_percent_per_side, config.cost_multiplier
    )
    equity = cash
    target_cash = equity * target_exposure
    fee_reserved_notional = target_cash / (ONE + commission_rate)
    per_market_notional = fee_reserved_notional / Decimal(len(active_symbols))
    accepted_count = 0
    for symbol in sorted(active_symbols):
        candle = _required_candle(market_data, symbol, index)
        raw_entry = candle.open
        entry_fill = raw_entry * (ONE + slippage_rate)
        desired_quantity = per_market_notional / entry_fill
        quantity = round_down_to_increment(
            desired_quantity, config.quantity_increment
        )
        accepted = quantity > ZERO
        opportunities.append(
            U1OpportunityRecord(
                rebalance_at=market_data.timestamps[index],
                symbol=symbol,
                active_market_count=len(active_symbols),
                target_exposure=target_exposure,
                target_fill_notional=per_market_notional,
                raw_entry_price=raw_entry,
                entry_fill_price=entry_fill,
                desired_quantity=desired_quantity,
                accepted_quantity=quantity,
                accepted_entry=accepted,
                reason=(
                    "ENTRY_ACCEPTED"
                    if accepted
                    else "ZERO_QUANTITY_AFTER_ROUNDING"
                ),
            )
        )
        if not accepted:
            continue
        entry_notional = quantity * entry_fill
        entry_fee = entry_notional * commission_rate
        required_cash = entry_notional + entry_fee
        if required_cash > cash:
            raise ValueError("U1 fee-reserved allocation exceeded available cash")
        cash -= required_cash
        positions[symbol] = _OpenPosition(
            symbol=symbol,
            entry_at=market_data.timestamps[index],
            entry_bar_timestamp=market_data.timestamps[index],
            raw_entry_price=raw_entry,
            entry_fill_price=entry_fill,
            quantity=quantity,
            entry_notional=entry_notional,
            entry_fee=entry_fee,
        )
        accepted_count += 1
    return cash, accepted_count


def close_u1_position(
    *,
    config: U1ResearchReplayConfig,
    positions: dict[str, _OpenPosition],
    trades: list[U1ResearchTrade],
    symbol: str,
    raw_exit_price: Decimal,
    exit_at: datetime,
    exit_bar_timestamp: datetime,
    exit_reason: Literal[
        "REBALANCE",
        "END_OF_WINDOW",
        "MARKET_TERMINATION_WRITE_OFF",
    ],
    cash: Decimal,
) -> Decimal:
    position = positions.pop(symbol)
    entry_slippage = (
        position.entry_fill_price - position.raw_entry_price
    ) * position.quantity
    if exit_reason == "MARKET_TERMINATION_WRITE_OFF":
        if raw_exit_price != ZERO:
            raise ValueError("U1 termination must write the position off at zero")
        exit_fill = ZERO
        exit_notional = ZERO
        exit_fee = ZERO
        exit_slippage = ZERO
    else:
        commission_rate = cost_rate(
            config.commission_percent_per_side, config.cost_multiplier
        )
        slippage_rate = cost_rate(
            config.adverse_slippage_percent_per_side, config.cost_multiplier
        )
        exit_fill = raw_exit_price * (ONE - slippage_rate)
        if exit_fill <= ZERO:
            raise ValueError("U1 adverse slippage produced a non-positive exit fill")
        exit_notional = position.quantity * exit_fill
        exit_fee = exit_notional * commission_rate
        exit_slippage = (raw_exit_price - exit_fill) * position.quantity
        cash += exit_notional - exit_fee
    raw_price_pl = (raw_exit_price - position.raw_entry_price) * position.quantity
    net_pl = (
        raw_price_pl
        - entry_slippage
        - exit_slippage
        - position.entry_fee
        - exit_fee
    )
    trades.append(
        U1ResearchTrade(
            sequence=len(trades) + 1,
            symbol=symbol,
            entry_at=position.entry_at,
            exit_at=exit_at,
            entry_bar_timestamp=position.entry_bar_timestamp,
            exit_bar_timestamp=exit_bar_timestamp,
            exit_reason=exit_reason,
            raw_entry_price=position.raw_entry_price,
            entry_fill_price=position.entry_fill_price,
            raw_exit_price=raw_exit_price,
            exit_fill_price=exit_fill,
            quantity=position.quantity,
            entry_notional=position.entry_notional,
            exit_notional=exit_notional,
            entry_fee=position.entry_fee,
            exit_fee=exit_fee,
            entry_slippage_cost=entry_slippage,
            exit_slippage_cost=exit_slippage,
            total_slippage_cost=entry_slippage + exit_slippage,
            raw_price_pl=raw_price_pl,
            net_pl=net_pl,
        )
    )
    return cash


def build_u1_metrics(
    *,
    config: U1ResearchReplayConfig,
    final_equity: Decimal,
    trades: list[U1ResearchTrade],
    opportunities: list[U1OpportunityRecord],
    signals: list[U1VolatilitySignalRecord],
    equity_curve: list[R3EquitySnapshot],
    availability_events: list[U1AvailabilityEvent],
    rebalance_breadth: list[U1RebalanceBreadth],
    maximum_drawdown: Decimal,
    maximum_drawdown_percent: Decimal,
) -> U1ReplayMetrics:
    positive_net = [trade.net_pl for trade in trades if trade.net_pl > ZERO]
    negative_net = [trade.net_pl for trade in trades if trade.net_pl < ZERO]
    gross_profit = sum(positive_net, ZERO)
    gross_loss = abs(sum(negative_net, ZERO))
    profit_factor = gross_profit / gross_loss if gross_loss > ZERO else None
    positive_raw = [trade.raw_price_pl for trade in trades if trade.raw_price_pl > ZERO]
    negative_raw = [trade.raw_price_pl for trade in trades if trade.raw_price_pl < ZERO]
    raw_gross_profit = sum(positive_raw, ZERO)
    raw_gross_loss = abs(sum(negative_raw, ZERO))
    raw_profit_factor = (
        raw_gross_profit / raw_gross_loss if raw_gross_loss > ZERO else None
    )
    positive_raw_by_symbol: dict[str, Decimal] = {}
    for trade in trades:
        if trade.raw_price_pl > ZERO:
            positive_raw_by_symbol[trade.symbol] = (
                positive_raw_by_symbol.get(trade.symbol, ZERO) + trade.raw_price_pl
            )
    positive_raw_total = sum(positive_raw_by_symbol.values(), ZERO)
    ordered_positive_raw = sorted(positive_raw_by_symbol.values(), reverse=True)
    max_single = (
        ordered_positive_raw[0] / positive_raw_total
        if positive_raw_total > ZERO
        else None
    )
    top_five = (
        sum(ordered_positive_raw[:5], ZERO) / positive_raw_total
        if positive_raw_total > ZERO
        else None
    )
    previous_equity = config.initial_capital
    equity_returns: list[Decimal] = []
    for snapshot in equity_curve:
        if snapshot.equity <= ZERO or previous_equity <= ZERO:
            raise ValueError("U1 realized volatility requires positive equity")
        equity_returns.append((snapshot.equity / previous_equity).ln())
        previous_equity = snapshot.equity
    realized_equity_variance = (
        sum((item * item for item in equity_returns), ZERO)
        / Decimal(len(equity_returns))
        * Decimal(config.annualization_intervals)
        if equity_returns
        else ZERO
    )
    realized_equity_volatility = realized_equity_variance.sqrt()
    target_exposures = [signal.target_exposure for signal in signals]
    breadth_values = [item.active_symbol_count for item in rebalance_breadth]
    exposure_values = [item.gross_exposure_percent for item in equity_curve]
    active_dates = {
        item.timestamp.date() for item in equity_curve if item.open_positions > 0
    }
    writeoff_trades = [
        trade
        for trade in trades
        if trade.exit_reason == "MARKET_TERMINATION_WRITE_OFF"
    ]
    return U1ReplayMetrics(
        initial_capital=config.initial_capital,
        final_equity=final_equity,
        net_pl=final_equity - config.initial_capital,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        raw_gross_profit=raw_gross_profit,
        raw_gross_loss=raw_gross_loss,
        raw_profit_factor=raw_profit_factor,
        maximum_drawdown=maximum_drawdown,
        maximum_drawdown_percent=maximum_drawdown_percent,
        completed_trades=len(trades),
        winning_trades=len(positive_net),
        losing_trades=len(negative_net),
        accepted_entries=sum(item.accepted_entry for item in opportunities),
        rejected_opportunities=sum(
            item.reason != "ENTRY_ACCEPTED" for item in opportunities
        ),
        total_commission=sum(
            (trade.entry_fee + trade.exit_fee for trade in trades), ZERO
        ),
        total_slippage=sum((trade.total_slippage_cost for trade in trades), ZERO),
        turnover=sum(
            (trade.entry_notional + trade.exit_notional for trade in trades), ZERO
        )
        / config.initial_capital,
        active_days=len(active_dates),
        average_gross_exposure_percent=(
            sum(exposure_values, ZERO) / Decimal(len(exposure_values))
            if exposure_values
            else ZERO
        ),
        maximum_gross_exposure_percent=max(exposure_values, default=ZERO),
        realized_equity_volatility=realized_equity_volatility,
        return_to_drawdown=(
            (final_equity - config.initial_capital) / maximum_drawdown
            if maximum_drawdown > ZERO
            else None
        ),
        average_target_exposure=(
            sum(target_exposures, ZERO) / Decimal(len(target_exposures))
            if target_exposures
            else ZERO
        ),
        minimum_target_exposure=min(target_exposures, default=ZERO),
        maximum_target_exposure=max(target_exposures, default=ZERO),
        symbol_positive_raw_profit=dict(sorted(positive_raw_by_symbol.items())),
        maximum_single_symbol_gross_profit_fraction=max_single,
        top_five_gross_profit_fraction=top_five,
        termination_writeoff_count=len(writeoff_trades),
        termination_writeoff_net_pl=sum(
            (trade.net_pl for trade in writeoff_trades), ZERO
        ),
        minimum_active_symbol_count_at_rebalance=min(breadth_values, default=0),
        average_active_symbol_count_at_rebalance=(
            Decimal(sum(breadth_values)) / Decimal(len(breadth_values))
            if breadth_values
            else ZERO
        ),
    )


def audit_u1_research_replay(
    config: U1ResearchReplayConfig,
    market_data: U1PreparedMarketData,
    stored: U1ResearchReplayResult,
) -> R3ResearchReplayAudit:
    stored_hash_matches = stored.result_evidence_hash == universe_evidence_hash(
        stored.model_dump(exclude={"result_evidence_hash"})
    )
    replayed = run_u1_research_replay(config, market_data)
    deterministic_match = replayed.model_dump() == stored.model_dump()
    reasons: list[str] = []
    if not stored_hash_matches:
        reasons.append("stored_result_evidence_hash_mismatch")
    if not deterministic_match:
        reasons.append("deterministic_replay_mismatch")
    return R3ResearchReplayAudit(
        status="PASS" if not reasons else "BLOCKED",
        stored_result_hash_matches=stored_hash_matches,
        deterministic_replay_matches=deterministic_match,
        replayed_result_evidence_hash=replayed.result_evidence_hash,
        reasons=reasons,
    )


def _required_candle(
    market_data: U1PreparedMarketData,
    symbol: str,
    index: int,
) -> R3Candle:
    candle = market_data.candles_by_symbol[symbol][index]
    if candle is None:
        raise ValueError(f"U1 required candle is missing: {symbol}")
    return candle
