from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3EquitySnapshot,
    R3ReplayMetrics,
    R3ResearchReplayAudit,
    build_replay_metrics,
    cost_rate,
    percent_rate,
    prepare_r3_market_data,
    round_down_to_increment,
    sample_log_return_stddev,
    wilder_atr,
)
from aurex.backtest_engine.research_r31_engine import (
    R31OpportunityReason,
    R31PathQualitySignal,
    calculate_path_quality_signal,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_RESEARCH_ENGINE_VERSION = "r4-path-quality-validation-engine-v1.0.0"
R4_REPLAY_SCHEMA_VERSION = "aurex-r4-validation-replay-v1"
ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class R4PreparedMarketData:
    symbols: tuple[str, ...]
    timestamps: tuple[datetime, ...]
    candles_by_symbol: dict[str, tuple[R3Candle | None, ...]]
    first_missing_by_symbol: dict[str, datetime | None]
    actual_validation_rows_by_symbol: dict[str, int]
    series_evidence_hashes: dict[str, str]
    market_data_evidence_hash: str
    validation_start: datetime
    validation_end: datetime


class R4ResearchReplayConfig(BaseModel):
    variant_id: Literal["path_quality_spot_v1"] = "path_quality_spot_v1"
    variant_version: Literal["1.0.0"] = "1.0.0"
    variant_role: Literal["PRIMARY"] = "PRIMARY"
    timeframe_hours: Literal[4] = 4
    decimal_precision: Literal[50] = 50
    decimal_rounding: Literal["ROUND_HALF_EVEN"] = "ROUND_HALF_EVEN"
    lookback_bars: Literal[504] = 504
    close_observations: Literal[505] = 505
    rebalance_bars: Literal[84] = 84
    volatility_lookback_bars: Literal[168] = 168
    atr_lookback_bars: Literal[84] = 84
    catastrophe_stop_atr_multiple: Decimal = Field(default=Decimal("3"), gt=0)
    selected_fraction: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    fixed_selected_count: Literal[7] = 7
    evaluation_start: datetime
    evaluation_end: datetime
    baseline_decision_symbols: list[str] = Field(min_length=3)
    omitted_symbols: list[str] = Field(default_factory=list)
    initial_capital: Decimal = Field(default=Decimal("1000"), gt=0)
    risk_per_position_percent: Decimal = Field(default=Decimal("0.50"), gt=0)
    max_symbol_exposure_percent: Decimal = Field(default=Decimal("20"), gt=0)
    max_gross_exposure_percent: Decimal = Field(default=Decimal("100"), gt=0)
    max_open_positions: Literal[7] = 7
    minimum_ranked_positions: Literal[3] = 3
    quantity_increment: Decimal = Field(default=Decimal("0.00000001"), gt=0)
    price_increment: Decimal = Field(default=Decimal("0.00000001"), gt=0)
    commission_percent_per_side: Decimal = Field(default=Decimal("0.10"), ge=0)
    adverse_slippage_percent_per_side: Decimal = Field(
        default=Decimal("0.05"), ge=0
    )
    cost_multiplier: Decimal = Field(gt=0)
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    candidate_protocol_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    execution_specification_evidence_hash: str
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
        "universe_manifest_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "candidate_protocol_evidence_hash",
        "validation_dataset_bundle_evidence_hash",
        "execution_specification_evidence_hash",
        "market_data_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_config(self) -> R4ResearchReplayConfig:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R4 evaluation end must follow its start")
        if not set(self.omitted_symbols).issubset(self.baseline_decision_symbols):
            raise ValueError("R4 omitted symbols must belong to the baseline universe")
        if len(self.active_symbols) < self.minimum_ranked_positions:
            raise ValueError("R4 active universe cannot satisfy minimum breadth")
        expected = {
            "catastrophe_stop_atr_multiple": Decimal("3"),
            "selected_fraction": Decimal("0.20"),
            "initial_capital": Decimal("1000"),
            "risk_per_position_percent": Decimal("0.50"),
            "max_symbol_exposure_percent": Decimal("20"),
            "max_gross_exposure_percent": Decimal("100"),
            "quantity_increment": Decimal("0.00000001"),
            "price_increment": Decimal("0.00000001"),
            "commission_percent_per_side": Decimal("0.10"),
            "adverse_slippage_percent_per_side": Decimal("0.05"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("R4 replay parameters differ from the frozen protocol")
        if self.cost_multiplier not in {
            Decimal("1"),
            Decimal("1.5"),
            Decimal("2"),
        }:
            raise ValueError("R4 cost multiplier is outside the frozen grid")
        return self

    @property
    def active_symbols(self) -> list[str]:
        omitted = set(self.omitted_symbols)
        return [
            symbol for symbol in self.baseline_decision_symbols if symbol not in omitted
        ]


class R4ResearchTrade(BaseModel):
    sequence: int = Field(gt=0)
    symbol: str
    entry_at: datetime
    exit_at: datetime
    entry_bar_timestamp: datetime
    exit_bar_timestamp: datetime
    exit_reason: Literal[
        "REBALANCE",
        "FIXED_STOP",
        "END_OF_WINDOW",
        "MARKET_TERMINATION_WRITE_OFF",
    ]
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


class R4OpportunityRecord(BaseModel):
    rebalance_at: datetime
    symbol: str
    score: Decimal
    slope: Decimal
    intercept: Decimal
    r_squared: Decimal
    rank: int | None
    signal_at: datetime
    reference_at: datetime
    signal_close: Decimal
    reference_close: Decimal
    signal_atr: Decimal
    signal_volatility: Decimal
    selected_by_rank: bool
    accepted_entry: bool
    reason: R31OpportunityReason

    model_config = ConfigDict(extra="forbid")


class R4AvailabilityEvent(BaseModel):
    timestamp: datetime
    symbol: str
    event: Literal["TERMINAL_MARKET_UNAVAILABLE"] = "TERMINAL_MARKET_UNAVAILABLE"
    held_position_written_off: bool
    permanently_removed_from_ranking: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class R4RebalanceBreadth(BaseModel):
    rebalance_at: datetime
    active_symbol_count: int = Field(ge=0)
    positive_market_count: int = Field(ge=0)
    selected_market_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class R4ReplayMetrics(R3ReplayMetrics):
    termination_writeoff_count: int = Field(ge=0)
    termination_writeoff_net_pl: Decimal
    minimum_active_symbol_count_at_rebalance: int = Field(ge=0)
    average_active_symbol_count_at_rebalance: Decimal = Field(ge=0)


class R4ResearchReplayResult(BaseModel):
    schema_version: Literal["aurex-r4-validation-replay-v1"] = (
        R4_REPLAY_SCHEMA_VERSION
    )
    engine_version: Literal["r4-path-quality-validation-engine-v1.0.0"] = (
        R4_RESEARCH_ENGINE_VERSION
    )
    config: R4ResearchReplayConfig
    request_evidence_hash: str
    result_evidence_hash: str
    metrics: R4ReplayMetrics
    trades: list[R4ResearchTrade]
    opportunities: list[R4OpportunityRecord]
    equity_curve: list[R3EquitySnapshot]
    availability_events: list[R4AvailabilityEvent]
    rebalance_breadth: list[R4RebalanceBreadth]

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result_hash(self) -> R4ResearchReplayResult:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("R4 replay result hash does not match its evidence")
        return self


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


@dataclass(frozen=True)
class _RankedSignal:
    symbol: str
    signal: R31PathQualitySignal
    signal_atr: Decimal
    signal_volatility: Decimal


@dataclass
class _Candidate:
    ranked: _RankedSignal
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    stop_price: Decimal
    desired_quantity: Decimal


def prepare_r4_market_data(
    *,
    development_by_symbol: dict[
        str, list[R3Candle] | tuple[R3Candle, ...]
    ],
    validation_by_symbol: dict[
        str, list[R3Candle] | tuple[R3Candle, ...]
    ],
    validation_start: datetime,
    validation_end: datetime,
) -> R4PreparedMarketData:
    validation_start = normalize_timestamp(validation_start)
    validation_end = normalize_timestamp(validation_end)
    if validation_end <= validation_start:
        raise ValueError("R4 validation end must follow its start")
    duration = validation_end - validation_start
    interval = timedelta(hours=4)
    if duration % interval:
        raise ValueError("R4 validation window must align to the 4h grid")
    expected_validation_rows = duration // interval

    development = prepare_r3_market_data(development_by_symbol)
    normalized_validation_keys = {
        symbol.strip().upper() for symbol in validation_by_symbol
    }
    if normalized_validation_keys != set(development.symbols):
        raise ValueError("R4 validation symbols must match the development universe")
    if any(symbol != symbol.strip().upper() for symbol in validation_by_symbol):
        raise ValueError("R4 validation symbols must be normalized uppercase")
    if development.timestamps[-1] + interval != validation_start:
        raise ValueError("R4 development warmup must end at validation start")

    validation_grid = tuple(
        validation_start + index * interval
        for index in range(expected_validation_rows)
    )
    timestamps = development.timestamps + validation_grid
    combined_by_symbol: dict[str, tuple[R3Candle | None, ...]] = {}
    first_missing_by_symbol: dict[str, datetime | None] = {}
    actual_rows_by_symbol: dict[str, int] = {}
    series_hashes: dict[str, str] = {}
    for symbol in development.symbols:
        validation_candles = tuple(validation_by_symbol[symbol])
        if not validation_candles:
            raise ValueError(f"R4 validation data has leading missing candles: {symbol}")
        if len(validation_candles) > expected_validation_rows:
            raise ValueError(f"R4 validation data extends past its partition: {symbol}")
        actual_timestamps = tuple(candle.timestamp for candle in validation_candles)
        expected_prefix = validation_grid[: len(validation_candles)]
        if actual_timestamps != expected_prefix:
            raise ValueError(
                f"R4 validation data has an internal, duplicate, or resumed gap: {symbol}"
            )
        missing_count = expected_validation_rows - len(validation_candles)
        padded_validation: tuple[R3Candle | None, ...] = validation_candles + (
            (None,) * missing_count
        )
        combined = cast(
            tuple[R3Candle | None, ...],
            development.candles_by_symbol[symbol] + padded_validation,
        )
        combined_by_symbol[symbol] = combined
        first_missing_by_symbol[symbol] = (
            validation_grid[len(validation_candles)] if missing_count else None
        )
        actual_rows_by_symbol[symbol] = len(validation_candles)
        series_hashes[symbol] = universe_evidence_hash(
            {
                "symbol": symbol,
                "timeframe": "4h",
                "development_series_evidence_hash": (
                    development.series_evidence_hashes[symbol]
                ),
                "validation_candles": validation_candles,
                "first_missing_at": first_missing_by_symbol[symbol],
                "synthetic_candles": [],
            }
        )
    market_data_hash = universe_evidence_hash(
        {
            "symbols": development.symbols,
            "validation_start": validation_start,
            "validation_end": validation_end,
            "series_evidence_hashes": series_hashes,
        }
    )
    return R4PreparedMarketData(
        symbols=development.symbols,
        timestamps=timestamps,
        candles_by_symbol=combined_by_symbol,
        first_missing_by_symbol=first_missing_by_symbol,
        actual_validation_rows_by_symbol=actual_rows_by_symbol,
        series_evidence_hashes=series_hashes,
        market_data_evidence_hash=market_data_hash,
        validation_start=validation_start,
        validation_end=validation_end,
    )


def run_r4_research_replay(
    config: R4ResearchReplayConfig,
    market_data: R4PreparedMarketData,
) -> R4ResearchReplayResult:
    with localcontext() as context:
        context.prec = config.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_r4_research_replay(config, market_data)


def _run_r4_research_replay(
    config: R4ResearchReplayConfig,
    market_data: R4PreparedMarketData,
) -> R4ResearchReplayResult:
    validate_replay_inputs(config, market_data)
    timestamp_to_index = {
        timestamp: index for index, timestamp in enumerate(market_data.timestamps)
    }
    start_index = timestamp_to_index[config.evaluation_start]
    end_index = timestamp_to_index.get(config.evaluation_end, len(market_data.timestamps))
    if end_index == len(market_data.timestamps):
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R4 evaluation end is not aligned to market data")
    if end_index <= start_index:
        raise ValueError("R4 evaluation contains no complete candle")
    if start_index <= config.lookback_bars:
        raise ValueError("R4 evaluation has insufficient signal warmup")

    atr_by_symbol = {
        symbol: _availability_aware_atr(
            market_data.candles_by_symbol[symbol],
            period=config.atr_lookback_bars,
        )
        for symbol in config.active_symbols
    }
    request_hash = universe_evidence_hash(
        {
            "schema_version": R4_REPLAY_SCHEMA_VERSION,
            "engine_version": R4_RESEARCH_ENGINE_VERSION,
            "config": config,
            "series_evidence_hashes": market_data.series_evidence_hashes,
        }
    )
    cash = config.initial_capital
    positions: dict[str, _OpenPosition] = {}
    trades: list[R4ResearchTrade] = []
    opportunities: list[R4OpportunityRecord] = []
    equity_curve: list[R3EquitySnapshot] = []
    availability_events: list[R4AvailabilityEvent] = []
    rebalance_breadth: list[R4RebalanceBreadth] = []
    terminated = {
        symbol
        for symbol in config.active_symbols
        if market_data.first_missing_by_symbol[symbol] is not None
        and cast(datetime, market_data.first_missing_by_symbol[symbol])
        < config.evaluation_start
    }
    peak_equity = config.initial_capital
    max_drawdown = ZERO
    max_drawdown_percent = ZERO

    for index in range(start_index, end_index):
        timestamp = market_data.timestamps[index]
        terminating_now = [
            symbol
            for symbol in config.active_symbols
            if symbol not in terminated
            and market_data.first_missing_by_symbol[symbol] == timestamp
        ]
        for symbol in sorted(terminating_now):
            was_held = symbol in positions
            if was_held:
                cash = _close_position(
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
                R4AvailabilityEvent(
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
                    raise ValueError("R4 available position has no rebalance candle")
                cash = _close_position(
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
            cash = _allocate_rebalance_entries(
                config=config,
                market_data=market_data,
                atr_by_symbol=atr_by_symbol,
                index=index,
                terminated=terminated,
                positions=positions,
                opportunities=opportunities,
                breadth=rebalance_breadth,
                cash=cash,
            )
        else:
            for symbol in sorted(list(positions)):
                candle = market_data.candles_by_symbol[symbol][index]
                if candle is None:
                    raise ValueError("R4 available position has no stop candle")
                position = positions[symbol]
                if candle.low <= position.stop_price:
                    raw_exit_price = (
                        candle.open
                        if candle.open <= position.stop_price
                        else position.stop_price
                    )
                    cash = _close_position(
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
        marked_value = ZERO
        for symbol, position in positions.items():
            candle = market_data.candles_by_symbol[symbol][index]
            if candle is None:
                raise ValueError("R4 cannot mark a position with a synthetic candle")
            marked_value += position.quantity * candle.close
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
        final_candle = market_data.candles_by_symbol[symbol][final_bar_index]
        if final_candle is None:
            raise ValueError("R4 end-of-window close has no actual candle")
        cash = _close_position(
            config=config,
            positions=positions,
            trades=trades,
            symbol=symbol,
            raw_exit_price=final_candle.close,
            exit_at=config.evaluation_end,
            exit_bar_timestamp=final_bar_timestamp,
            exit_reason="END_OF_WINDOW",
            cash=cash,
        )
    if positions:
        raise ValueError("R4 replay ended with open positions")

    base_metrics = build_replay_metrics(
        config=config,
        final_equity=cash,
        trades=trades,
        opportunities=opportunities,
        equity_curve=equity_curve,
        maximum_drawdown=max_drawdown,
        maximum_drawdown_percent=max_drawdown_percent,
    )
    writeoffs = [
        trade
        for trade in trades
        if trade.exit_reason == "MARKET_TERMINATION_WRITE_OFF"
    ]
    breadth_values = [item.active_symbol_count for item in rebalance_breadth]
    metrics = R4ReplayMetrics(
        **base_metrics.model_dump(),
        termination_writeoff_count=len(writeoffs),
        termination_writeoff_net_pl=sum(
            (trade.net_pl for trade in writeoffs), ZERO
        ),
        minimum_active_symbol_count_at_rebalance=min(breadth_values, default=0),
        average_active_symbol_count_at_rebalance=(
            sum((Decimal(value) for value in breadth_values), ZERO)
            / Decimal(len(breadth_values))
            if breadth_values
            else ZERO
        ),
    )
    result_payload = {
        "schema_version": R4_REPLAY_SCHEMA_VERSION,
        "engine_version": R4_RESEARCH_ENGINE_VERSION,
        "config": config,
        "request_evidence_hash": request_hash,
        "metrics": metrics,
        "trades": trades,
        "opportunities": opportunities,
        "equity_curve": equity_curve,
        "availability_events": availability_events,
        "rebalance_breadth": rebalance_breadth,
    }
    return R4ResearchReplayResult(
        **result_payload,
        result_evidence_hash=universe_evidence_hash(result_payload),
    )


def validate_replay_inputs(
    config: R4ResearchReplayConfig,
    market_data: R4PreparedMarketData,
) -> None:
    if tuple(config.baseline_decision_symbols) != market_data.symbols:
        raise ValueError("R4 baseline symbols do not match prepared market data")
    if config.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R4 market-data hash does not match the config")
    timestamp_set = set(market_data.timestamps)
    if config.evaluation_start not in timestamp_set:
        raise ValueError("R4 evaluation start is not a candle-open timestamp")
    if config.evaluation_end not in timestamp_set:
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R4 evaluation end is not a valid exclusive boundary")
    if not (
        market_data.validation_start
        <= config.evaluation_start
        < config.evaluation_end
        <= market_data.validation_end
    ):
        raise ValueError("R4 replay must remain inside the validation partition")


def _availability_aware_atr(
    candles: tuple[R3Candle | None, ...],
    *,
    period: int,
) -> tuple[Decimal | None, ...]:
    first_missing = next(
        (index for index, candle in enumerate(candles) if candle is None),
        len(candles),
    )
    if any(candle is not None for candle in candles[first_missing:]):
        raise ValueError("R4 market data resumes after a missing candle")
    actual = cast(tuple[R3Candle, ...], candles[:first_missing])
    return wilder_atr(actual, period) + ((None,) * (len(candles) - first_missing))


def _allocate_rebalance_entries(
    *,
    config: R4ResearchReplayConfig,
    market_data: R4PreparedMarketData,
    atr_by_symbol: dict[str, tuple[Decimal | None, ...]],
    index: int,
    terminated: set[str],
    positions: dict[str, _OpenPosition],
    opportunities: list[R4OpportunityRecord],
    breadth: list[R4RebalanceBreadth],
    cash: Decimal,
) -> Decimal:
    if positions:
        raise ValueError("R4 allocation requires prior positions exited")
    signal_index = index - 1
    ranked: list[_RankedSignal] = []
    for symbol in config.active_symbols:
        if symbol in terminated:
            continue
        entry_candle = market_data.candles_by_symbol[symbol][index]
        signal_window = market_data.candles_by_symbol[symbol][
            signal_index - config.lookback_bars : signal_index + 1
        ]
        if (
            entry_candle is None
            or len(signal_window) != config.close_observations
            or any(candle is None for candle in signal_window)
        ):
            continue
        candles = cast(
            tuple[R3Candle, ...],
            market_data.candles_by_symbol[symbol][: signal_index + 1],
        )
        signal = calculate_path_quality_signal(candles, signal_index=signal_index)
        signal_atr = atr_by_symbol[symbol][signal_index]
        if signal_atr is None:
            continue
        ranked.append(
            _RankedSignal(
                symbol=symbol,
                signal=signal,
                signal_atr=signal_atr,
                signal_volatility=sample_log_return_stddev(
                    candles,
                    signal_index,
                    config.volatility_lookback_bars,
                ),
            )
        )
    ranked.sort(key=lambda item: (-item.signal.score, item.symbol))
    positive = [
        item
        for item in ranked
        if not item.signal.degenerate and item.signal.slope > ZERO
    ]
    rank_by_symbol = {
        item.symbol: rank for rank, item in enumerate(positive, start=1)
    }
    sufficient_breadth = len(positive) >= config.minimum_ranked_positions
    selected_symbols = (
        {item.symbol for item in positive[: config.fixed_selected_count]}
        if sufficient_breadth
        else set()
    )
    breadth.append(
        R4RebalanceBreadth(
            rebalance_at=market_data.timestamps[index],
            active_symbol_count=len(ranked),
            positive_market_count=len(positive),
            selected_market_count=len(selected_symbols),
        )
    )
    state_by_symbol: dict[str, R4OpportunityRecord] = {}
    for item in ranked:
        if item.signal.degenerate:
            reason: R31OpportunityReason = "DEGENERATE_TREND_WINDOW"
        elif item.signal.slope <= ZERO:
            reason = "NON_POSITIVE_TREND"
        elif not sufficient_breadth:
            reason = "INSUFFICIENT_POSITIVE_MARKETS"
        elif item.symbol not in selected_symbols:
            reason = "RANK_BELOW_SELECTION"
        else:
            reason = "ZERO_QUANTITY_AFTER_ROUNDING"
        state = R4OpportunityRecord(
            rebalance_at=market_data.timestamps[index],
            symbol=item.symbol,
            score=item.signal.score,
            slope=item.signal.slope,
            intercept=item.signal.intercept,
            r_squared=item.signal.r_squared,
            rank=rank_by_symbol.get(item.symbol),
            signal_at=item.signal.signal_at,
            reference_at=item.signal.reference_at,
            signal_close=item.signal.signal_close,
            reference_close=item.signal.reference_close,
            signal_atr=item.signal_atr,
            signal_volatility=item.signal_volatility,
            selected_by_rank=item.symbol in selected_symbols,
            accepted_entry=False,
            reason=reason,
        )
        opportunities.append(state)
        state_by_symbol[item.symbol] = state
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
        entry_candle = market_data.candles_by_symbol[item.symbol][index]
        if entry_candle is None:
            raise ValueError("R4 selected market has no actual entry candle")
        raw_entry = entry_candle.open
        entry_fill = raw_entry * (ONE + slippage_rate)
        stop_distance = config.catastrophe_stop_atr_multiple * item.signal_atr
        stop_price = round_down_to_increment(
            raw_entry - stop_distance,
            config.price_increment,
        )
        if stop_price <= ZERO:
            state_by_symbol[item.symbol].reason = "NON_POSITIVE_STOP_PRICE"
            continue
        risk_quantity = risk_budget / stop_distance
        symbol_cap_quantity = symbol_cap / entry_fill
        candidates.append(
            _Candidate(
                ranked=item,
                raw_entry_price=raw_entry,
                entry_fill_price=entry_fill,
                stop_price=stop_price,
                desired_quantity=min(risk_quantity, symbol_cap_quantity),
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
        state = state_by_symbol[candidate.ranked.symbol]
        if quantity <= ZERO:
            state.reason = "ZERO_QUANTITY_AFTER_ROUNDING"
            continue
        entry_notional = quantity * candidate.entry_fill_price
        entry_fee = entry_notional * commission_rate
        required_cash = entry_notional + entry_fee
        if required_cash > cash:
            raise ValueError("R4 capacity scaling exceeded available cash")
        cash -= required_cash
        positions[candidate.ranked.symbol] = _OpenPosition(
            symbol=candidate.ranked.symbol,
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


def _close_position(
    *,
    config: R4ResearchReplayConfig,
    positions: dict[str, _OpenPosition],
    trades: list[R4ResearchTrade],
    symbol: str,
    raw_exit_price: Decimal,
    exit_at: datetime,
    exit_bar_timestamp: datetime,
    exit_reason: Literal[
        "REBALANCE",
        "FIXED_STOP",
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
            raise ValueError("R4 market termination must write the position off at zero")
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
            raise ValueError("R4 adverse slippage produced a non-positive exit fill")
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
        R4ResearchTrade(
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


def audit_r4_research_replay(
    config: R4ResearchReplayConfig,
    market_data: R4PreparedMarketData,
    stored: R4ResearchReplayResult,
) -> R3ResearchReplayAudit:
    stored_hash_matches = stored.result_evidence_hash == universe_evidence_hash(
        stored.model_dump(exclude={"result_evidence_hash"})
    )
    replayed = run_r4_research_replay(config, market_data)
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
