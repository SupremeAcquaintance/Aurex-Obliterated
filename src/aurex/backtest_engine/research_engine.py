from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, localcontext
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_RESEARCH_ENGINE_VERSION = "r3-cross-sectional-momentum-engine-v1.0.0"
R3_REPLAY_SCHEMA_VERSION = "aurex-r3-research-replay-v1"
ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")


class R3Candle(BaseModel):
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("timestamp")
    @classmethod
    def normalize_candle_timestamp(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_prices(self) -> R3Candle:
        if self.high < max(self.open, self.close) or self.low > min(
            self.open, self.close
        ):
            raise ValueError("R3 candle OHLC values are inconsistent")
        if self.low > self.high:
            raise ValueError("R3 candle low cannot exceed high")
        return self


@dataclass(frozen=True)
class R3PreparedMarketData:
    symbols: tuple[str, ...]
    timestamps: tuple[datetime, ...]
    candles_by_symbol: dict[str, tuple[R3Candle, ...]]
    series_evidence_hashes: dict[str, str]
    market_data_evidence_hash: str


class R3ResearchReplayConfig(BaseModel):
    variant_id: str = Field(min_length=1, max_length=128)
    variant_role: Literal["PRIMARY", "FALSIFICATION"]
    timeframe_hours: Literal[4] = 4
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    lookback_bars: int = Field(gt=0)
    rebalance_bars: int = Field(gt=0)
    volatility_lookback_bars: int = Field(gt=1)
    atr_lookback_bars: int = Field(gt=0)
    catastrophe_stop_atr_multiple: Decimal = Field(gt=0)
    selected_fraction: Decimal = Field(gt=0, le=1)
    fixed_selected_count: int = Field(gt=0)
    evaluation_start: datetime
    evaluation_end: datetime
    baseline_decision_symbols: list[str] = Field(min_length=1)
    omitted_symbols: list[str] = Field(default_factory=list)
    initial_capital: Decimal = Field(gt=0)
    risk_per_position_percent: Decimal = Field(gt=0, le=100)
    max_symbol_exposure_percent: Decimal = Field(gt=0, le=100)
    max_gross_exposure_percent: Decimal = Field(gt=0, le=100)
    max_open_positions: int = Field(gt=0)
    minimum_ranked_positions: int = Field(gt=0)
    quantity_increment: Decimal = Field(gt=0)
    price_increment: Decimal = Field(gt=0)
    commission_percent_per_side: Decimal = Field(ge=0)
    adverse_slippage_percent_per_side: Decimal = Field(ge=0)
    cost_multiplier: Decimal = Field(gt=0)
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    protocol_evidence_hash: str
    execution_specification_evidence_hash: str
    market_data_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluation_start", "evaluation_end")
    @classmethod
    def normalize_config_timestamp(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("baseline_decision_symbols", "omitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({symbol.strip().upper() for symbol in value if symbol.strip()})

    @field_validator(
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "market_data_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_config(self) -> R3ResearchReplayConfig:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R3 evaluation end must follow its start")
        if not set(self.omitted_symbols).issubset(self.baseline_decision_symbols):
            raise ValueError("R3 omitted symbols must belong to the baseline universe")
        active_count = len(self.baseline_decision_symbols) - len(self.omitted_symbols)
        if active_count < self.minimum_ranked_positions:
            raise ValueError("R3 active universe cannot satisfy its minimum breadth")
        if self.fixed_selected_count > self.max_open_positions:
            raise ValueError("R3 fixed selection exceeds its position limit")
        if self.minimum_ranked_positions > self.fixed_selected_count:
            raise ValueError("R3 minimum breadth exceeds its fixed selection count")
        if self.max_symbol_exposure_percent > self.max_gross_exposure_percent:
            raise ValueError("R3 symbol cap exceeds its gross exposure cap")
        return self

    @property
    def active_symbols(self) -> list[str]:
        omitted = set(self.omitted_symbols)
        return [
            symbol for symbol in self.baseline_decision_symbols if symbol not in omitted
        ]


OpportunityReason = Literal[
    "ENTRY_ACCEPTED",
    "NON_POSITIVE_MOMENTUM",
    "RANK_BELOW_SELECTION",
    "INSUFFICIENT_POSITIVE_MARKETS",
    "NON_POSITIVE_STOP_PRICE",
    "ZERO_QUANTITY_AFTER_ROUNDING",
]


class R3OpportunityRecord(BaseModel):
    rebalance_at: datetime
    symbol: str
    score: Decimal
    rank: int | None
    signal_at: datetime
    reference_at: datetime
    signal_close: Decimal
    reference_close: Decimal
    signal_atr: Decimal
    signal_volatility: Decimal
    selected_by_rank: bool
    accepted_entry: bool
    reason: OpportunityReason

    model_config = ConfigDict(extra="forbid")


class R3ResearchTrade(BaseModel):
    sequence: int = Field(gt=0)
    symbol: str
    entry_at: datetime
    exit_at: datetime
    entry_bar_timestamp: datetime
    exit_bar_timestamp: datetime
    exit_reason: Literal["REBALANCE", "FIXED_STOP", "END_OF_WINDOW"]
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    raw_exit_price: Decimal
    exit_fill_price: Decimal
    stop_price: Decimal
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


class R3EquitySnapshot(BaseModel):
    timestamp: datetime
    cash: Decimal
    marked_position_value: Decimal
    equity: Decimal
    gross_exposure_percent: Decimal
    open_positions: int = Field(ge=0)
    drawdown: Decimal = Field(ge=0)
    drawdown_percent: Decimal = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class R3ReplayMetrics(BaseModel):
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
    symbol_positive_raw_profit: dict[str, Decimal]
    maximum_single_symbol_gross_profit_fraction: Decimal | None
    top_five_gross_profit_fraction: Decimal | None

    model_config = ConfigDict(extra="forbid")


class R3ResearchReplayResult(BaseModel):
    schema_version: Literal["aurex-r3-research-replay-v1"] = R3_REPLAY_SCHEMA_VERSION
    engine_version: Literal["r3-cross-sectional-momentum-engine-v1.0.0"] = (
        R3_RESEARCH_ENGINE_VERSION
    )
    config: R3ResearchReplayConfig
    request_evidence_hash: str
    result_evidence_hash: str
    metrics: R3ReplayMetrics
    trades: list[R3ResearchTrade]
    opportunities: list[R3OpportunityRecord]
    equity_curve: list[R3EquitySnapshot]

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash")
    @classmethod
    def validate_result_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result_hash(self) -> R3ResearchReplayResult:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("R3 replay result hash does not match its evidence")
        return self


class R3ResearchReplayAudit(BaseModel):
    status: Literal["PASS", "BLOCKED"]
    stored_result_hash_matches: bool
    deterministic_replay_matches: bool
    replayed_result_evidence_hash: str
    reasons: list[str]

    model_config = ConfigDict(extra="forbid")


@dataclass
class _OpenPosition:
    symbol: str
    entry_at: datetime
    entry_bar_timestamp: datetime
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    stop_price: Decimal
    quantity: Decimal
    entry_notional: Decimal
    entry_fee: Decimal


@dataclass
class _Candidate:
    symbol: str
    score: Decimal
    rank: int
    signal_at: datetime
    reference_at: datetime
    signal_close: Decimal
    reference_close: Decimal
    signal_atr: Decimal
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    stop_price: Decimal
    desired_quantity: Decimal


@dataclass
class _OpportunityState:
    rebalance_at: datetime
    symbol: str
    score: Decimal
    rank: int | None
    signal_at: datetime
    reference_at: datetime
    signal_close: Decimal
    reference_close: Decimal
    signal_atr: Decimal
    signal_volatility: Decimal
    selected_by_rank: bool
    accepted_entry: bool
    reason: OpportunityReason


def prepare_r3_market_data(
    candles_by_symbol: dict[str, list[R3Candle] | tuple[R3Candle, ...]],
) -> R3PreparedMarketData:
    if not candles_by_symbol:
        raise ValueError("R3 market data cannot be empty")
    normalized: dict[str, tuple[R3Candle, ...]] = {}
    for raw_symbol, raw_candles in candles_by_symbol.items():
        symbol = raw_symbol.strip().upper()
        if not symbol or symbol != raw_symbol:
            raise ValueError("R3 market-data symbols must be normalized uppercase")
        if symbol in normalized:
            raise ValueError("R3 market-data symbols must be unique")
        candles = tuple(raw_candles)
        if not candles:
            raise ValueError(f"R3 market data is empty for {symbol}")
        timestamps = [candle.timestamp for candle in candles]
        if timestamps != sorted(timestamps) or len(timestamps) != len(set(timestamps)):
            raise ValueError(f"R3 candle timestamps are not uniquely sorted for {symbol}")
        for previous, current in zip(timestamps, timestamps[1:], strict=False):
            if current - previous != timedelta(hours=4):
                raise ValueError(f"R3 candle continuity failed for {symbol}")
        normalized[symbol] = candles

    symbols = tuple(sorted(normalized))
    baseline_timestamps = tuple(candle.timestamp for candle in normalized[symbols[0]])
    for symbol in symbols[1:]:
        timestamps = tuple(candle.timestamp for candle in normalized[symbol])
        if timestamps != baseline_timestamps:
            raise ValueError("R3 requires exact timestamp alignment across all markets")

    series_hashes = {
        symbol: universe_evidence_hash(
            {
                "symbol": symbol,
                "timeframe": "4h",
                "candles": normalized[symbol],
            }
        )
        for symbol in symbols
    }
    market_data_hash = universe_evidence_hash(
        {
            "symbols": symbols,
            "series_evidence_hashes": series_hashes,
        }
    )
    return R3PreparedMarketData(
        symbols=symbols,
        timestamps=baseline_timestamps,
        candles_by_symbol=normalized,
        series_evidence_hashes=series_hashes,
        market_data_evidence_hash=market_data_hash,
    )


def wilder_atr(
    candles: tuple[R3Candle, ...],
    period: int,
) -> tuple[Decimal | None, ...]:
    if period <= 0:
        raise ValueError("R3 ATR period must be positive")
    true_ranges: list[Decimal] = []
    for index, candle in enumerate(candles):
        if index == 0:
            true_range = candle.high - candle.low
        else:
            previous_close = candles[index - 1].close
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        true_ranges.append(true_range)

    values: list[Decimal | None] = [None] * len(candles)
    if len(candles) < period:
        return tuple(values)
    current = sum(true_ranges[:period], ZERO) / Decimal(period)
    values[period - 1] = current
    for index in range(period, len(candles)):
        current = (
            current * Decimal(period - 1) + true_ranges[index]
        ) / Decimal(period)
        values[index] = current
    return tuple(values)


def sample_log_return_stddev(
    candles: tuple[R3Candle, ...],
    signal_index: int,
    lookback_returns: int,
) -> Decimal:
    if lookback_returns <= 1:
        raise ValueError("R3 volatility lookback must contain at least two returns")
    first_return_index = signal_index - lookback_returns + 1
    if first_return_index < 1:
        raise ValueError("R3 volatility diagnostic has insufficient warmup")
    returns = [
        (candles[index].close / candles[index - 1].close).ln()
        for index in range(first_return_index, signal_index + 1)
    ]
    average = sum(returns, ZERO) / Decimal(len(returns))
    sample_variance = sum(
        ((value - average) ** 2 for value in returns), ZERO
    ) / Decimal(len(returns) - 1)
    return sample_variance.sqrt()


def run_r3_research_replay(
    config: R3ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> R3ResearchReplayResult:
    with localcontext() as context:
        context.prec = config.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_r3_research_replay(config, market_data)


def _run_r3_research_replay(
    config: R3ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> R3ResearchReplayResult:
    validate_replay_inputs(config, market_data)
    timestamp_to_index = {
        timestamp: index for index, timestamp in enumerate(market_data.timestamps)
    }
    start_index = timestamp_to_index[config.evaluation_start]
    end_index = timestamp_to_index.get(config.evaluation_end, len(market_data.timestamps))
    if end_index == len(market_data.timestamps):
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R3 evaluation end is not aligned to the market data")
    if end_index <= start_index:
        raise ValueError("R3 evaluation contains no complete candle")
    if start_index <= config.lookback_bars:
        raise ValueError("R3 evaluation has insufficient momentum warmup")

    active_symbols = config.active_symbols
    atr_by_symbol = {
        symbol: wilder_atr(
            market_data.candles_by_symbol[symbol], config.atr_lookback_bars
        )
        for symbol in active_symbols
    }
    request_hash = universe_evidence_hash(
        {
            "schema_version": R3_REPLAY_SCHEMA_VERSION,
            "engine_version": R3_RESEARCH_ENGINE_VERSION,
            "config": config,
            "series_evidence_hashes": market_data.series_evidence_hashes,
        }
    )

    cash = config.initial_capital
    positions: dict[str, _OpenPosition] = {}
    trades: list[R3ResearchTrade] = []
    opportunity_states: list[_OpportunityState] = []
    equity_curve: list[R3EquitySnapshot] = []
    peak_equity = config.initial_capital
    max_drawdown = ZERO
    max_drawdown_percent = ZERO

    for index in range(start_index, end_index):
        timestamp = market_data.timestamps[index]
        is_rebalance = (index - start_index) % config.rebalance_bars == 0
        if is_rebalance:
            for symbol in sorted(list(positions)):
                candle = market_data.candles_by_symbol[symbol][index]
                cash = close_position(
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
            cash = allocate_rebalance_entries(
                config=config,
                market_data=market_data,
                atr_by_symbol=atr_by_symbol,
                index=index,
                positions=positions,
                opportunity_states=opportunity_states,
                cash=cash,
            )
        else:
            for symbol in sorted(list(positions)):
                candle = market_data.candles_by_symbol[symbol][index]
                position = positions[symbol]
                if candle.low <= position.stop_price:
                    raw_exit_price = (
                        candle.open
                        if candle.open <= position.stop_price
                        else position.stop_price
                    )
                    cash = close_position(
                        config=config,
                        positions=positions,
                        trades=trades,
                        symbol=symbol,
                        raw_exit_price=raw_exit_price,
                        exit_at=timestamp,
                        exit_bar_timestamp=timestamp,
                        exit_reason="FIXED_STOP",
                        cash=cash,
                    )

        candle_close_at = timestamp + timedelta(hours=config.timeframe_hours)
        marked_value = sum(
            (
                position.quantity
                * market_data.candles_by_symbol[symbol][index].close
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
        max_drawdown = max(max_drawdown, drawdown)
        max_drawdown_percent = max(max_drawdown_percent, drawdown_percent)
        exposure = marked_value / equity * ONE_HUNDRED if equity > ZERO else ZERO
        equity_curve.append(
            R3EquitySnapshot(
                timestamp=candle_close_at,
                cash=cash,
                marked_position_value=marked_value,
                equity=equity,
                gross_exposure_percent=exposure,
                open_positions=len(positions),
                drawdown=drawdown,
                drawdown_percent=drawdown_percent,
            )
        )

    final_bar_index = end_index - 1
    final_bar_timestamp = market_data.timestamps[final_bar_index]
    for symbol in sorted(list(positions)):
        final_close = market_data.candles_by_symbol[symbol][final_bar_index].close
        cash = close_position(
            config=config,
            positions=positions,
            trades=trades,
            symbol=symbol,
            raw_exit_price=final_close,
            exit_at=config.evaluation_end,
            exit_bar_timestamp=final_bar_timestamp,
            exit_reason="END_OF_WINDOW",
            cash=cash,
        )
    if positions:
        raise ValueError("R3 replay ended with open positions")

    opportunities = [
        R3OpportunityRecord(**state.__dict__) for state in opportunity_states
    ]
    metrics = build_replay_metrics(
        config=config,
        final_equity=cash,
        trades=trades,
        opportunities=opportunities,
        equity_curve=equity_curve,
        maximum_drawdown=max_drawdown,
        maximum_drawdown_percent=max_drawdown_percent,
    )
    result_payload = {
        "schema_version": R3_REPLAY_SCHEMA_VERSION,
        "engine_version": R3_RESEARCH_ENGINE_VERSION,
        "config": config,
        "request_evidence_hash": request_hash,
        "metrics": metrics,
        "trades": trades,
        "opportunities": opportunities,
        "equity_curve": equity_curve,
    }
    return R3ResearchReplayResult(
        **result_payload,
        result_evidence_hash=universe_evidence_hash(result_payload),
    )


def validate_replay_inputs(
    config: R3ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> None:
    if tuple(config.baseline_decision_symbols) != market_data.symbols:
        raise ValueError("R3 config baseline symbols do not match prepared market data")
    if config.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R3 market-data evidence hash does not match the config")
    timestamp_set = set(market_data.timestamps)
    if config.evaluation_start not in timestamp_set:
        raise ValueError("R3 evaluation start is not a candle-open timestamp")
    if config.evaluation_end not in timestamp_set:
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R3 evaluation end is not a valid exclusive boundary")


def allocate_rebalance_entries(
    *,
    config: R3ResearchReplayConfig,
    market_data: R3PreparedMarketData,
    atr_by_symbol: dict[str, tuple[Decimal | None, ...]],
    index: int,
    positions: dict[str, _OpenPosition],
    opportunity_states: list[_OpportunityState],
    cash: Decimal,
) -> Decimal:
    if positions:
        raise ValueError("R3 rebalance allocation requires all prior positions exited")
    signal_index = index - 1
    reference_index = signal_index - config.lookback_bars
    ranked: list[
        tuple[str, Decimal, datetime, datetime, Decimal, Decimal, Decimal, Decimal]
    ] = []
    for symbol in config.active_symbols:
        candles = market_data.candles_by_symbol[symbol]
        signal = candles[signal_index]
        reference = candles[reference_index]
        signal_atr = atr_by_symbol[symbol][signal_index]
        if signal_atr is None:
            raise ValueError("R3 signal ATR is unavailable after required warmup")
        signal_volatility = sample_log_return_stddev(
            candles,
            signal_index,
            config.volatility_lookback_bars,
        )
        score = signal.close / reference.close - ONE
        ranked.append(
            (
                symbol,
                score,
                signal.timestamp,
                reference.timestamp,
                signal.close,
                reference.close,
                signal_atr,
                signal_volatility,
            )
        )
    ranked.sort(key=lambda item: (-item[1], item[0]))
    positive = [item for item in ranked if item[1] > ZERO]
    rank_by_symbol = {
        item[0]: rank for rank, item in enumerate(positive, start=1)
    }
    sufficient_breadth = len(positive) >= config.minimum_ranked_positions
    selected_symbols = (
        {item[0] for item in positive[: config.fixed_selected_count]}
        if sufficient_breadth
        else set()
    )
    state_by_symbol: dict[str, _OpportunityState] = {}
    for item in ranked:
        (
            symbol,
            score,
            signal_at,
            reference_at,
            signal_close,
            reference_close,
            atr,
            volatility,
        ) = item
        if score <= ZERO:
            reason: OpportunityReason = "NON_POSITIVE_MOMENTUM"
        elif not sufficient_breadth:
            reason = "INSUFFICIENT_POSITIVE_MARKETS"
        elif symbol not in selected_symbols:
            reason = "RANK_BELOW_SELECTION"
        else:
            reason = "ZERO_QUANTITY_AFTER_ROUNDING"
        state = _OpportunityState(
            rebalance_at=market_data.timestamps[index],
            symbol=symbol,
            score=score,
            rank=rank_by_symbol.get(symbol),
            signal_at=signal_at,
            reference_at=reference_at,
            signal_close=signal_close,
            reference_close=reference_close,
            signal_atr=atr,
            signal_volatility=volatility,
            selected_by_rank=symbol in selected_symbols,
            accepted_entry=False,
            reason=reason,
        )
        opportunity_states.append(state)
        state_by_symbol[symbol] = state
    if not selected_symbols:
        return cash

    commission_rate = cost_rate(
        config.commission_percent_per_side, config.cost_multiplier
    )
    slippage_rate = cost_rate(
        config.adverse_slippage_percent_per_side, config.cost_multiplier
    )
    equity = cash
    risk_budget = equity * percent_rate(config.risk_per_position_percent)
    symbol_cap = equity * percent_rate(config.max_symbol_exposure_percent)
    candidates: list[_Candidate] = []
    for item in positive[: config.fixed_selected_count]:
        (
            symbol,
            score,
            signal_at,
            reference_at,
            signal_close,
            reference_close,
            atr,
            _,
        ) = item
        raw_entry = market_data.candles_by_symbol[symbol][index].open
        entry_fill = raw_entry * (ONE + slippage_rate)
        stop_distance = config.catastrophe_stop_atr_multiple * atr
        stop_price = round_down_to_increment(
            raw_entry - stop_distance,
            config.price_increment,
        )
        if stop_price <= ZERO:
            state_by_symbol[symbol].reason = "NON_POSITIVE_STOP_PRICE"
            continue
        risk_quantity = risk_budget / stop_distance
        symbol_cap_quantity = symbol_cap / entry_fill
        desired_quantity = min(risk_quantity, symbol_cap_quantity)
        candidates.append(
            _Candidate(
                symbol=symbol,
                score=score,
                rank=rank_by_symbol[symbol],
                signal_at=signal_at,
                reference_at=reference_at,
                signal_close=signal_close,
                reference_close=reference_close,
                signal_atr=atr,
                raw_entry_price=raw_entry,
                entry_fill_price=entry_fill,
                stop_price=stop_price,
                desired_quantity=desired_quantity,
            )
        )
    if not candidates:
        return cash

    desired_notional = sum(
        (
            candidate.desired_quantity * candidate.entry_fill_price
            for candidate in candidates
        ),
        ZERO,
    )
    entry_capacity = min(
        cash,
        equity * percent_rate(config.max_gross_exposure_percent),
    ) / (ONE + commission_rate)
    scale = min(
        ONE,
        entry_capacity / desired_notional if desired_notional > ZERO else ZERO,
    )
    for candidate in candidates:
        quantity = round_down_to_increment(
            candidate.desired_quantity * scale,
            config.quantity_increment,
        )
        state = state_by_symbol[candidate.symbol]
        if quantity <= ZERO:
            state.reason = "ZERO_QUANTITY_AFTER_ROUNDING"
            continue
        entry_notional = quantity * candidate.entry_fill_price
        entry_fee = entry_notional * commission_rate
        required_cash = entry_notional + entry_fee
        if required_cash > cash:
            raise ValueError("R3 deterministic capacity scaling exceeded available cash")
        cash -= required_cash
        positions[candidate.symbol] = _OpenPosition(
            symbol=candidate.symbol,
            entry_at=market_data.timestamps[index],
            entry_bar_timestamp=market_data.timestamps[index],
            raw_entry_price=candidate.raw_entry_price,
            entry_fill_price=candidate.entry_fill_price,
            stop_price=candidate.stop_price,
            quantity=quantity,
            entry_notional=entry_notional,
            entry_fee=entry_fee,
        )
        state.accepted_entry = True
        state.reason = "ENTRY_ACCEPTED"
    return cash


def close_position(
    *,
    config: R3ResearchReplayConfig,
    positions: dict[str, _OpenPosition],
    trades: list[R3ResearchTrade],
    symbol: str,
    raw_exit_price: Decimal,
    exit_at: datetime,
    exit_bar_timestamp: datetime,
    exit_reason: Literal["REBALANCE", "FIXED_STOP", "END_OF_WINDOW"],
    cash: Decimal,
) -> Decimal:
    position = positions.pop(symbol)
    commission_rate = cost_rate(
        config.commission_percent_per_side, config.cost_multiplier
    )
    slippage_rate = cost_rate(
        config.adverse_slippage_percent_per_side, config.cost_multiplier
    )
    exit_fill = raw_exit_price * (ONE - slippage_rate)
    if exit_fill <= ZERO:
        raise ValueError("R3 adverse slippage produced a non-positive exit fill")
    exit_notional = position.quantity * exit_fill
    exit_fee = exit_notional * commission_rate
    cash += exit_notional - exit_fee
    entry_slippage = (
        position.entry_fill_price - position.raw_entry_price
    ) * position.quantity
    exit_slippage = (raw_exit_price - exit_fill) * position.quantity
    raw_price_pl = (raw_exit_price - position.raw_entry_price) * position.quantity
    net_pl = (
        raw_price_pl
        - entry_slippage
        - exit_slippage
        - position.entry_fee
        - exit_fee
    )
    trades.append(
        R3ResearchTrade(
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
            stop_price=position.stop_price,
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


def build_replay_metrics(
    *,
    config: R3ResearchReplayConfig,
    final_equity: Decimal,
    trades: list[R3ResearchTrade],
    opportunities: list[R3OpportunityRecord],
    equity_curve: list[R3EquitySnapshot],
    maximum_drawdown: Decimal,
    maximum_drawdown_percent: Decimal,
) -> R3ReplayMetrics:
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
    total_fill_notional = sum(
        (trade.entry_notional + trade.exit_notional for trade in trades), ZERO
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
    exposure_values = [item.gross_exposure_percent for item in equity_curve]
    active_dates = {
        item.timestamp.date() for item in equity_curve if item.open_positions > 0
    }
    return R3ReplayMetrics(
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
        turnover=total_fill_notional / config.initial_capital,
        active_days=len(active_dates),
        average_gross_exposure_percent=(
            Decimal(str(mean(exposure_values))) if exposure_values else ZERO
        ),
        maximum_gross_exposure_percent=max(exposure_values, default=ZERO),
        symbol_positive_raw_profit=dict(sorted(positive_raw_by_symbol.items())),
        maximum_single_symbol_gross_profit_fraction=max_single,
        top_five_gross_profit_fraction=top_five,
    )


def audit_r3_research_replay(
    config: R3ResearchReplayConfig,
    market_data: R3PreparedMarketData,
    stored: R3ResearchReplayResult,
) -> R3ResearchReplayAudit:
    stored_hash_matches = stored.result_evidence_hash == universe_evidence_hash(
        stored.model_dump(exclude={"result_evidence_hash"})
    )
    replayed = run_r3_research_replay(config, market_data)
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


def percent_rate(percent: Decimal) -> Decimal:
    return percent / ONE_HUNDRED


def cost_rate(percent: Decimal, multiplier: Decimal) -> Decimal:
    return percent_rate(percent) * multiplier


def round_down_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    return (value / increment).to_integral_value(rounding=ROUND_FLOOR) * increment
