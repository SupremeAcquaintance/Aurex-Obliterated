"""Pure, bounded Jam proposals. No ledger writes, risk approval, or fill authority.

Inputs must eventually be reconstructed from audited receipts and resolved in the
same transaction as the paper ledger. Hashes here bind content, not market origin.
Historical windows are not native schedules: the caller supplies entry permission.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from aurex.backtest_engine.jam_reversal_reference import (
    JamOpenPosition,
    jam_market_exit,
    jam_quantity,
    jam_take_profit,
    long_jam_pattern,
    parse_jam_reversal_spot_parameters,
    resolve_jam_bracket_exit,
)
from aurex.domain.enums import Direction
from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    MAX_STREAM_BARS,
    NativeBarError,
    aware_utc,
    content_hash,
)
from aurex.signal_gateway.native_jam_features import (
    STEP,
    FeatureModel,
    JamFeatureState,
    Positive,
    jam_feature_frame,
)
from aurex.signal_gateway.native_jam_history import bind_jam_feature_parameters
from aurex.signal_gateway.native_processing import NativeStreamSpec

ZERO = Decimal("0")
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class JamDecisionTerms(FeatureModel):
    tick_size: Positive
    minimum_contract: Positive
    point_value: Positive = Decimal("1")
    slippage_ticks: int = Field(strict=True, ge=0, le=10000)

    @field_validator("point_value")
    @classmethod
    def spot_units(cls, value: Decimal) -> Decimal:
        if value != 1:
            raise ValueError("jam_decisions_require_spot_units")
        return value


def _aligned(value: datetime) -> datetime:
    value = aware_utc(value)
    if value.microsecond or int(value.timestamp()) % BASE_SECONDS:
        raise ValueError("jam_decision_time_unaligned")
    return value


class JamPendingSetup(FeatureModel):
    armed_open: datetime
    trigger: Positive
    stop_loss: Positive
    failure_level: Positive

    _time = field_validator("armed_open")(_aligned)


class JamEntryCandidate(FeatureModel):
    bar_open: datetime
    signal_price: Positive
    expected_entry: Positive
    stop_loss: Positive
    take_profit: Positive
    failure_level: Positive

    _time = field_validator("bar_open")(_aligned)

    @model_validator(mode="after")
    def geometry(self) -> "JamEntryCandidate":
        if not self.stop_loss < self.expected_entry < self.take_profit:
            raise ValueError("jam_entry_geometry_invalid")
        return self


class JamBoundState(FeatureModel):
    first_open: datetime
    bar_count: int = Field(strict=True, ge=1, le=MAX_STREAM_BARS)
    context_hash: Hash
    feature_hash: Hash
    source_origin_verified: Literal[False] = False
    execution_authority: Literal[False] = False
    forward_qualifying: Literal[False] = False

    _time = field_validator("first_open")(_aligned)

    @property
    def last_open(self) -> datetime:
        return self.first_open + STEP * (self.bar_count - 1)


class JamSetupState(JamBoundState):
    schema_version: Literal["native_jam_setup_v1"] = "native_jam_setup_v1"
    pending: JamPendingSetup | None = None
    awaiting_entry: JamEntryCandidate | None = None
    last_entry_open: datetime | None = None

    @field_validator("last_entry_open")
    @classmethod
    def entry_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aligned(value)

    @model_validator(mode="after")
    def span(self) -> "JamSetupState":
        for when in (self.pending.armed_open if self.pending else None, self.last_entry_open):
            if when is not None and not self.first_open <= when <= self.last_open:
                raise ValueError("jam_setup_span_invalid")
        if self.awaiting_entry is not None and (
            self.pending is not None or self.awaiting_entry.bar_open != self.last_open
        ):
            raise ValueError("jam_entry_resolution_state_invalid")
        return self

    @property
    def proposal_hash(self) -> str | None:
        if self.awaiting_entry is None:
            return None
        return content_hash(self.model_dump(mode="json"))


class JamSetupDecision(FeatureModel):
    state: JamSetupState
    status: Literal["NOT_READY", "IDLE", "ARMED", "PENDING", "ENTRY_CANDIDATE"]
    cancellations: tuple[Literal["EXPIRED", "MIDPOINT", "WINDOW_CLOSED", "POSITION_OPEN"], ...]


def _inputs(
    features: JamFeatureState,
    scope: NativeStreamSpec,
    parameters: dict,
    terms: JamDecisionTerms,
) -> tuple[JamFeatureState, dict, JamDecisionTerms, str]:
    features = JamFeatureState.model_validate(features.model_dump())
    scope = NativeStreamSpec.model_validate(scope.model_dump())
    terms = JamDecisionTerms.model_validate(terms.model_dump())
    parameters = json.loads(json.dumps(parameters, allow_nan=False))
    if bind_jam_feature_parameters(scope, parameters) != features.parameters:
        raise NativeBarError("jam_decision_feature_parameters_mismatch")
    context = content_hash(
        {"scope": scope.model_dump(mode="json"), "terms": terms.model_dump(mode="json")}
    )
    return features, parse_jam_reversal_spot_parameters(parameters), terms, context


def _anchor(features: JamFeatureState, context: str) -> dict:
    return {
        "first_open": features.first_open,
        "bar_count": features.bar_count,
        "context_hash": context,
        "feature_hash": content_hash(features.model_dump(mode="json")),
    }


def _next(state: JamBoundState, features: JamFeatureState, context: str) -> dict:
    if state.context_hash != context:
        raise NativeBarError("jam_decision_context_changed")
    if features.first_open != state.first_open or features.bar_count != state.bar_count + 1:
        raise NativeBarError("jam_decision_requires_next_contiguous_bar")
    return {**state.model_dump(), **_anchor(features, context)}


def initialize_jam_setup(
    *,
    features: JamFeatureState,
    scope: NativeStreamSpec,
    parameters: dict,
    terms: JamDecisionTerms,
) -> JamSetupState:
    """Anchor at the warmup head; do not invent prior setups, fills, or cooldowns."""
    features, _, _, context = _inputs(features, scope, parameters, terms)
    return JamSetupState(**_anchor(features, context))


def evaluate_jam_setup(
    state: JamSetupState,
    *,
    features: JamFeatureState,
    scope: NativeStreamSpec,
    parameters: dict,
    terms: JamDecisionTerms,
    equity: Decimal,
    entry_window: bool,
    position_open: bool,
) -> JamSetupDecision:
    state = JamSetupState.model_validate(state.model_dump())
    features, p, terms, context = _inputs(features, scope, parameters, terms)
    if type(entry_window) is not bool or type(position_open) is not bool:
        raise NativeBarError("jam_decision_explicit_policy_required")
    if not isinstance(equity, Decimal) or not equity.is_finite() or equity < 0:
        raise NativeBarError("jam_decision_equity_invalid")
    if state.awaiting_entry is not None:
        raise NativeBarError("jam_entry_resolution_required")
    updated = _next(state, features, context)
    f = jam_feature_frame(features)
    bar = f.bar
    pending = state.pending
    adaptive = p["use_timeframe_adaptive_confirmation"]
    window = 10 if adaptive else p["confirm_window_bars"]
    cancellations = []
    if pending is not None:
        for condition, reason in (
            ((bar.timestamp - pending.armed_open) // STEP > window, "EXPIRED"),
            (
                p["cancel_pending_on_midpoint_failure"] and bar.close < pending.failure_level,
                "MIDPOINT",
            ),
            (not entry_window, "WINDOW_CLOSED"),
            (position_open, "POSITION_OPEN"),
        ):
            if condition:
                cancellations.append(reason)
        if cancellations:
            pending = None

    def result(status: str, candidate: JamEntryCandidate | None = None) -> JamSetupDecision:
        return JamSetupDecision(
            state=JamSetupState.model_validate(
                {**updated, "pending": pending, "awaiting_entry": candidate}
            ),
            status=status,
            cancellations=tuple(cancellations),
        )

    if not f.warmup_ready:
        return result("NOT_READY")
    cooldown = (
        state.last_entry_open is None
        or (bar.timestamp - state.last_entry_open) // STEP >= p["trade_cooldown_bars"]
    )
    allowed = entry_window and not position_open and cooldown
    entry = bar.close + terms.tick_size * terms.slippage_ticks

    def geometry(stop: Decimal) -> tuple[Decimal, bool]:
        target, target_ok = jam_take_profit(
            entry=entry, stop_loss=stop, atr=f.atr, tick_size=terms.tick_size, parameters=p
        )
        # Historical sizing is only a feasibility filter. Native risk must size again
        # with its own costs, affordability and loss limits before any paper fill.
        feasible = (
            stop > 0
            and entry - stop > terms.tick_size
            and target > entry
            and target_ok
            and jam_quantity(
                equity=equity,
                entry=entry,
                risk=entry - stop,
                point_value=terms.point_value,
                minimum_contract=terms.minimum_contract,
                parameters=p,
            )
            > 0
        )
        return target, feasible

    if pending is not None and bar.timestamp > pending.armed_open:
        spread = max(bar.high - bar.low, terms.tick_size)
        confirmed = (
            bar.close > pending.trigger + f.atr * p["confirm_atr_buffer"]
            and bar.close > bar.open
            and bar.close
            <= pending.trigger
            + f.atr * (Decimal("1.25") if adaptive else p["max_confirm_distance_atr"])
            and spread <= f.atr * p["max_confirm_range_atr"]
            and (bar.close - bar.low) / spread
            >= (Decimal("0.85") if adaptive else p["min_confirm_close_position"])
        )
        target, feasible = geometry(pending.stop_loss)
        if (
            allowed
            and confirmed
            and feasible
            and p["enable_long"]
            and p["direction_mode"] == "Long only"
        ):
            candidate = JamEntryCandidate(
                bar_open=bar.timestamp,
                signal_price=bar.close,
                expected_entry=entry,
                stop_loss=pending.stop_loss,
                take_profit=target,
                failure_level=pending.failure_level,
            )
            pending = None
            return result("ENTRY_CANDIDATE", candidate)

    if allowed and pending is None:
        pattern = long_jam_pattern(
            list(features.recent),
            len(features.recent) - 1,
            current_atr=f.atr,
            previous_atr=f.previous_atr,
            tick_size=terms.tick_size,
            slippage_ticks=terms.slippage_ticks,
            parameters=p,
        )
        htf = not p["use_higher_timeframe_bias"] or f.higher_fast >= f.higher_slow
        pullback = f.previous_bar.close <= f.previous_pullback_ema or bar.low <= f.pullback_ema
        mode = p["context_mode"]
        context_ok = {
            "None": True,
            "HTF trend": htf and pullback,
            "Local reversal": f.local_reversal,
            "Hybrid": (htf and pullback) or f.local_reversal,
        }[mode]
        counter = (
            p["block_strong_counter_trend"]
            and bar.close < f.trend_ema
            and f.higher_fast < f.higher_slow
            and f.dmi_minus > f.dmi_plus
            and f.adx >= p["counter_trend_adx"]
        )
        context_ok &= (
            not p["use_current_trend_filter"] or bar.close >= f.trend_ema
        ) and not counter
        volume_ok = not p["use_volume_filter"] or (
            f.volume_average > 0
            and bar.volume
            >= f.volume_average * (Decimal("1.15") if adaptive else p["volume_expansion"])
        )
        if pattern is not None and context_ok and volume_ok and geometry(pattern.stop_loss)[1]:
            pending = JamPendingSetup(
                armed_open=bar.timestamp,
                trigger=pattern.trigger,
                stop_loss=pattern.stop_loss,
                failure_level=pattern.failure_level,
            )
            return result("ARMED")
    return result("PENDING" if pending is not None else "IDLE")


def resolve_jam_entry(state: JamSetupState, *, proposal_hash: str, filled: bool) -> JamSetupState:
    """Pure acknowledgment, not proof of a fill. Future ledger integration owns it.

    A rejected proposal is consumed without cooldown. Never retry it as a new bar.
    """
    state = JamSetupState.model_validate(state.model_dump())
    if (
        type(filled) is not bool
        or state.awaiting_entry is None
        or proposal_hash != state.proposal_hash
    ):
        raise NativeBarError("jam_entry_resolution_mismatch")
    return JamSetupState.model_validate(
        {
            **state.model_dump(),
            "awaiting_entry": None,
            "last_entry_open": state.last_open if filled else state.last_entry_open,
        }
    )


class JamExitCandidate(FeatureModel):
    phase: Literal["BRACKET", "CLOSE"]
    price: Positive
    reason: str
    slippage: Decimal = Field(ge=0)
    intrabar_ambiguous: bool


class JamManagedPosition(JamBoundState):
    schema_version: Literal["native_jam_management_v1"] = "native_jam_management_v1"
    entry_open: datetime
    entry_price: Positive
    quantity: Positive
    initial_stop: Positive
    stop_loss: Positive
    take_profit: Positive
    failure_level: Positive
    best_price: Positive
    exit_candidate: JamExitCandidate | None = None

    _entry_time = field_validator("entry_open")(_aligned)

    @model_validator(mode="after")
    def geometry(self) -> "JamManagedPosition":
        if not self.first_open <= self.entry_open <= self.last_open:
            raise ValueError("jam_position_span_invalid")
        if (
            not self.initial_stop < self.entry_price < self.take_profit
            or self.stop_loss < self.initial_stop
            or self.best_price < self.entry_price
        ):
            raise ValueError("jam_position_geometry_invalid")
        return self


def initialize_jam_position(
    *,
    features: JamFeatureState,
    scope: NativeStreamSpec,
    parameters: dict,
    terms: JamDecisionTerms,
    filled_at: datetime,
    entry_price: Decimal,
    quantity: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    failure_level: Decimal,
) -> JamManagedPosition:
    features, _, _, context = _inputs(features, scope, parameters, terms)
    if aware_utc(filled_at) != features.recent[-1].timestamp + STEP:
        raise NativeBarError("jam_management_requires_boundary_fill")
    # The signal candle high predates the fill. Do not use it to activate a trail.
    return JamManagedPosition(
        **_anchor(features, context),
        entry_open=features.recent[-1].timestamp,
        entry_price=entry_price,
        quantity=quantity,
        initial_stop=stop_loss,
        stop_loss=stop_loss,
        take_profit=take_profit,
        failure_level=failure_level,
        best_price=entry_price,
    )


def plan_jam_exit(
    state: JamManagedPosition,
    *,
    features: JamFeatureState,
    scope: NativeStreamSpec,
    parameters: dict,
    terms: JamDecisionTerms,
) -> JamManagedPosition:
    """Propose old-bracket-first exits and next-bar stops; never close a ledger trade.

    Partial entry candles are deliberately unsupported. The execution adapter must
    retain existing conservative partial-bar bounds. A proposed exit blocks advance
    until a future ledger-backed coordinator resolves it. CLOSE exits must not make
    the position appear flat to this candle's setup evaluation; BRACKET exits may.
    """
    state = JamManagedPosition.model_validate(state.model_dump())
    features, p, terms, context = _inputs(features, scope, parameters, terms)
    if state.exit_candidate is not None:
        raise NativeBarError("jam_exit_resolution_required")
    updated = _next(state, features, context)
    f = jam_feature_frame(features)
    risk = state.entry_price - state.initial_stop
    position = JamOpenPosition(
        direction=Direction.LONG,
        entry_index=0,
        entry_at=state.entry_open,
        signal_price=state.entry_price,
        entry_price=state.entry_price,
        initial_stop_loss=state.initial_stop,
        stop_loss=state.stop_loss,
        take_profit=state.take_profit,
        quantity=state.quantity,
        entry_fee=ZERO,
        entry_slippage=ZERO,
        initial_risk_per_unit=risk,
        initial_risk=risk * state.quantity,
        point_value=terms.point_value,
        market_regime="BREAKOUT_EXPANSION",
        failure_level=state.failure_level,
        best_price=state.best_price,
    )
    fill = resolve_jam_bracket_exit(
        f.bar, position, tick_size=terms.tick_size, slippage_ticks=terms.slippage_ticks
    )
    phase = "BRACKET"
    if fill is None and f.warmup_ready:
        best = max(state.best_price, f.bar.high)
        stop = state.stop_loss
        if p["use_breakeven_stop"] and best >= state.entry_price + risk * p["breakeven_at_r"]:
            stop = max(stop, state.entry_price + terms.tick_size * p["breakeven_offset_ticks"])
        if p["use_atr_trail"] and best >= state.entry_price + risk * p["trail_start_r"]:
            stop = max(stop, best - f.atr * p["trail_atr_multiplier"])
        updated.update(best_price=best, stop_loss=stop)
        reason = None
        if p["use_midpoint_failure_exit"] and f.bar.close < state.failure_level:
            reason = "MIDPOINT_FAILURE"
        elif (
            p["use_pullback_failure_exit"]
            and f.bar.close < f.pullback_ema
            and f.bar.close < state.entry_price
        ):
            reason = "PULLBACK_FAILURE"
        elif (f.bar.timestamp - state.entry_open) // STEP >= p["max_bars_in_trade"]:
            reason = "TIME_EXIT"
        if reason is not None:
            phase = "CLOSE"
            fill = jam_market_exit(
                f.bar.close,
                tick_size=terms.tick_size,
                slippage_ticks=terms.slippage_ticks,
                reason=reason,
                quantity=state.quantity,
                point_value=terms.point_value,
            )
    if fill is not None:
        updated["exit_candidate"] = JamExitCandidate(
            phase=phase,
            price=fill.price,
            reason=fill.reason,
            slippage=fill.slippage,
            intrabar_ambiguous=fill.intrabar_ambiguous,
        )
    return JamManagedPosition.model_validate(updated)
