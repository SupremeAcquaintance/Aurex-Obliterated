from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3EquitySnapshot,
    R3PreparedMarketData,
    R3ReplayMetrics,
    R3ResearchReplayAudit,
    R3ResearchTrade,
    build_replay_metrics,
    close_position,
    cost_rate,
    percent_rate,
    round_down_to_increment,
    sample_log_return_stddev,
    wilder_atr,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R31_RESEARCH_ENGINE_VERSION = "r3.1-path-quality-engine-v1.0.0"
R31_REPLAY_SCHEMA_VERSION = "aurex-r3.1-research-replay-v1"
ZERO = Decimal("0")
ONE = Decimal("1")
ONE_HUNDRED = Decimal("100")
X_MEAN = Decimal("252")
SXX = Decimal("10732260")


class R31ResearchReplayConfig(BaseModel):
    variant_id: Literal["xsmom_path_quality_84d_14d_primary"] = (
        "xsmom_path_quality_84d_14d_primary"
    )
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
    adverse_slippage_percent_per_side: Decimal = Field(default=Decimal("0.05"), ge=0)
    cost_multiplier: Decimal = Field(gt=0)
    universe_manifest_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    protocol_evidence_hash: str
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
        "protocol_evidence_hash",
        "execution_specification_evidence_hash",
        "market_data_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_config(self) -> R31ResearchReplayConfig:
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("R3.1 evaluation end must follow its start")
        if not set(self.omitted_symbols).issubset(self.baseline_decision_symbols):
            raise ValueError("R3.1 omitted symbols must belong to the baseline universe")
        if len(self.active_symbols) < self.minimum_ranked_positions:
            raise ValueError("R3.1 active universe cannot satisfy minimum breadth")
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
            raise ValueError("R3.1 replay parameters differ from the frozen protocol")
        if self.cost_multiplier not in {
            Decimal("1"),
            Decimal("1.5"),
            Decimal("2"),
        }:
            raise ValueError("R3.1 cost multiplier is outside the frozen grid")
        return self

    @property
    def active_symbols(self) -> list[str]:
        omitted = set(self.omitted_symbols)
        return [
            symbol for symbol in self.baseline_decision_symbols if symbol not in omitted
        ]


R31OpportunityReason = Literal[
    "ENTRY_ACCEPTED",
    "NON_POSITIVE_TREND",
    "DEGENERATE_TREND_WINDOW",
    "RANK_BELOW_SELECTION",
    "INSUFFICIENT_POSITIVE_MARKETS",
    "NON_POSITIVE_STOP_PRICE",
    "ZERO_QUANTITY_AFTER_ROUNDING",
]


class R31PathQualitySignal(BaseModel):
    reference_at: datetime
    signal_at: datetime
    reference_close: Decimal
    signal_close: Decimal
    slope: Decimal
    intercept: Decimal
    r_squared: Decimal = Field(ge=0, le=1)
    score: Decimal
    degenerate: bool

    model_config = ConfigDict(extra="forbid", frozen=True)


class R31OpportunityRecord(BaseModel):
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


class R31ResearchReplayResult(BaseModel):
    schema_version: Literal["aurex-r3.1-research-replay-v1"] = (
        R31_REPLAY_SCHEMA_VERSION
    )
    engine_version: Literal["r3.1-path-quality-engine-v1.0.0"] = (
        R31_RESEARCH_ENGINE_VERSION
    )
    config: R31ResearchReplayConfig
    request_evidence_hash: str
    result_evidence_hash: str
    metrics: R3ReplayMetrics
    trades: list[R3ResearchTrade]
    opportunities: list[R31OpportunityRecord]
    equity_curve: list[R3EquitySnapshot]

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_evidence_hash", "result_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result_hash(self) -> R31ResearchReplayResult:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("R3.1 replay result hash does not match its evidence")
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
    rank: int
    raw_entry_price: Decimal
    entry_fill_price: Decimal
    stop_price: Decimal
    desired_quantity: Decimal


@dataclass
class _OpportunityState:
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


def calculate_path_quality_signal(
    candles: tuple[R3Candle, ...],
    *,
    signal_index: int,
) -> R31PathQualitySignal:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        return _calculate_path_quality_signal(candles, signal_index=signal_index)


def _calculate_path_quality_signal(
    candles: tuple[R3Candle, ...],
    *,
    signal_index: int,
) -> R31PathQualitySignal:
    start_index = signal_index - 504
    if start_index < 0:
        raise ValueError("R3.1 path-quality signal has insufficient warmup")
    window = candles[start_index : signal_index + 1]
    if len(window) != 505:
        raise ValueError("R3.1 path-quality signal requires exactly 505 closes")
    if all(candle.close == window[0].close for candle in window):
        intercept = window[0].close.ln()
        return R31PathQualitySignal(
            reference_at=window[0].timestamp,
            signal_at=window[-1].timestamp,
            reference_close=window[0].close,
            signal_close=window[-1].close,
            slope=ZERO,
            intercept=intercept,
            r_squared=ZERO,
            score=ZERO,
            degenerate=True,
        )
    log_closes = [candle.close.ln() for candle in window]
    y_mean = sum(log_closes, ZERO) / Decimal("505")
    sxy = sum(
        (
            (Decimal(index) - X_MEAN) * (value - y_mean)
            for index, value in enumerate(log_closes)
        ),
        ZERO,
    )
    slope = sxy / SXX
    intercept = y_mean - slope * X_MEAN
    sst = sum(((value - y_mean) ** 2 for value in log_closes), ZERO)
    if sst == ZERO:
        r_squared = ZERO
        degenerate = True
    else:
        sse = sum(
            (
                (
                    value
                    - (intercept + slope * Decimal(index))
                )
                ** 2
                for index, value in enumerate(log_closes)
            ),
            ZERO,
        )
        r_squared = max(ZERO, min(ONE, ONE - sse / sst))
        degenerate = False
    return R31PathQualitySignal(
        reference_at=window[0].timestamp,
        signal_at=window[-1].timestamp,
        reference_close=window[0].close,
        signal_close=window[-1].close,
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        score=slope * r_squared,
        degenerate=degenerate,
    )


def run_r31_research_replay(
    config: R31ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> R31ResearchReplayResult:
    with localcontext() as context:
        context.prec = config.decimal_precision
        context.rounding = ROUND_HALF_EVEN
        return _run_r31_research_replay(config, market_data)


def _run_r31_research_replay(
    config: R31ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> R31ResearchReplayResult:
    validate_replay_inputs(config, market_data)
    timestamp_to_index = {
        timestamp: index for index, timestamp in enumerate(market_data.timestamps)
    }
    start_index = timestamp_to_index[config.evaluation_start]
    end_index = timestamp_to_index.get(config.evaluation_end, len(market_data.timestamps))
    if end_index == len(market_data.timestamps):
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R3.1 evaluation end is not aligned to market data")
    if end_index <= start_index:
        raise ValueError("R3.1 evaluation contains no complete candle")
    if start_index <= config.lookback_bars:
        raise ValueError("R3.1 evaluation has insufficient signal warmup")

    atr_by_symbol = {
        symbol: wilder_atr(
            market_data.candles_by_symbol[symbol], config.atr_lookback_bars
        )
        for symbol in config.active_symbols
    }
    request_hash = universe_evidence_hash(
        {
            "schema_version": R31_REPLAY_SCHEMA_VERSION,
            "engine_version": R31_RESEARCH_ENGINE_VERSION,
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
        raise ValueError("R3.1 replay ended with open positions")

    opportunities = [
        R31OpportunityRecord(**state.__dict__) for state in opportunity_states
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
        "schema_version": R31_REPLAY_SCHEMA_VERSION,
        "engine_version": R31_RESEARCH_ENGINE_VERSION,
        "config": config,
        "request_evidence_hash": request_hash,
        "metrics": metrics,
        "trades": trades,
        "opportunities": opportunities,
        "equity_curve": equity_curve,
    }
    return R31ResearchReplayResult(
        **result_payload,
        result_evidence_hash=universe_evidence_hash(result_payload),
    )


def validate_replay_inputs(
    config: R31ResearchReplayConfig,
    market_data: R3PreparedMarketData,
) -> None:
    if tuple(config.baseline_decision_symbols) != market_data.symbols:
        raise ValueError("R3.1 baseline symbols do not match prepared market data")
    if config.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R3.1 market-data hash does not match the config")
    timestamp_set = set(market_data.timestamps)
    if config.evaluation_start not in timestamp_set:
        raise ValueError("R3.1 evaluation start is not a candle-open timestamp")
    if config.evaluation_end not in timestamp_set:
        expected_end = market_data.timestamps[-1] + timedelta(hours=4)
        if config.evaluation_end != expected_end:
            raise ValueError("R3.1 evaluation end is not a valid exclusive boundary")


def allocate_rebalance_entries(
    *,
    config: R31ResearchReplayConfig,
    market_data: R3PreparedMarketData,
    atr_by_symbol: dict[str, tuple[Decimal | None, ...]],
    index: int,
    positions: dict[str, _OpenPosition],
    opportunity_states: list[_OpportunityState],
    cash: Decimal,
) -> Decimal:
    if positions:
        raise ValueError("R3.1 allocation requires prior positions exited")
    signal_index = index - 1
    ranked: list[_RankedSignal] = []
    for symbol in config.active_symbols:
        candles = market_data.candles_by_symbol[symbol]
        signal = _calculate_path_quality_signal(candles, signal_index=signal_index)
        signal_atr = atr_by_symbol[symbol][signal_index]
        if signal_atr is None:
            raise ValueError("R3.1 signal ATR is unavailable after warmup")
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
    state_by_symbol: dict[str, _OpportunityState] = {}
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
        state = _OpportunityState(
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
        opportunity_states.append(state)
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
        raw_entry = market_data.candles_by_symbol[item.symbol][index].open
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
                rank=rank_by_symbol[item.symbol],
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
            raise ValueError("R3.1 capacity scaling exceeded available cash")
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


def audit_r31_research_replay(
    config: R31ResearchReplayConfig,
    market_data: R3PreparedMarketData,
    stored: R31ResearchReplayResult,
) -> R3ResearchReplayAudit:
    stored_hash_matches = stored.result_evidence_hash == universe_evidence_hash(
        stored.model_dump(exclude={"result_evidence_hash"})
    )
    replayed = run_r31_research_replay(config, market_data)
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
