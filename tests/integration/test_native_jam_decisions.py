from datetime import datetime, timedelta
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.service import strategy_parameter_fingerprint
from aurex.signal_gateway.native_bars import ClosedBar, NativeBarError
from aurex.signal_gateway.native_jam_decisions import (
    JamDecisionTerms,
    JamManagedPosition,
    JamPendingSetup,
    JamSetupState,
    evaluate_jam_setup,
    initialize_jam_position,
    initialize_jam_setup,
    plan_jam_exit,
    resolve_jam_entry,
)
from aurex.signal_gateway.native_jam_features import (
    STEP,
    advance_jam_features,
    initialize_jam_features,
)
from aurex.signal_gateway.native_jam_history import bind_jam_feature_parameters
from aurex.signal_gateway.native_processing import NativeStreamSpec
from tests.integration.test_jam_reversal_spot_replay import (
    import_jam_dataset,
    jam_candles,
    jam_client,
    jam_parameters,
    jam_payload,
)

D = Decimal


def scope_for(parameters):
    return NativeStreamSpec(
        feed_id="fixture",
        strategy="jam_reversal_spot_v1",
        strategy_version="1.0.1",
        settings_fingerprint=strategy_parameter_fingerprint("jam_reversal_spot_v1", parameters),
    )


class Harness:
    def __init__(self, changes=None, seed_count=30):
        self.parameters = {**jam_parameters(), **(changes or {})}
        self.scope = scope_for(self.parameters)
        self.terms = JamDecisionTerms(
            tick_size=D("0.01"), minimum_contract=D("0.00001"), slippage_ticks=2
        )
        self.bars = [ClosedBar.model_validate(c.model_dump()) for c in jam_candles()]
        self.features = initialize_jam_features(
            self.bars[:seed_count], bind_jam_feature_parameters(self.scope, self.parameters)
        )
        self.state = initialize_jam_setup(**self.args())

    def args(self):
        return dict(
            features=self.features, scope=self.scope, parameters=self.parameters, terms=self.terms
        )

    def step(self, *, bar=None, **policy):
        self.features = advance_jam_features(
            self.features, bar or self.bars[self.features.bar_count]
        )
        result = evaluate_jam_setup(
            self.state,
            **self.args(),
            **{"equity": D("100"), "entry_window": True, "position_open": False, **policy},
        )
        self.state = JamSetupState.model_validate_json(result.state.model_dump_json())
        return result

    def candidate(self):
        assert self.step().status == "IDLE"
        assert self.step().status == "ARMED"
        assert self.step().status == "ENTRY_CANDIDATE"
        return self.state.awaiting_entry

    def position(self, **values):
        return initialize_jam_position(
            **self.args(),
            **{
                "filled_at": self.features.recent[-1].timestamp + STEP,
                "entry_price": D("100"),
                "quantity": D("0.5"),
                "stop_loss": D("98"),
                "take_profit": D("150"),
                "failure_level": D("99"),
                **values,
            },
        )

    def exit_step(self, position, bar=None):
        self.features = advance_jam_features(
            self.features, bar or self.bars[self.features.bar_count]
        )
        return plan_jam_exit(position, **self.args())


@pytest.mark.parametrize("stop", ["Pattern", "ATR", "Wider", "Tighter"])
@pytest.mark.parametrize("target", ["Fixed R", "ATR capped R"])
def test_proposal_geometry_and_exit_match_synthetic_reference(stop, target):
    h = Harness({"stop_mode": stop, "target_mode": target})
    candidate = h.candidate()
    with jam_client() as client:
        payload = jam_payload(import_jam_dataset(client))
        payload["parameters"] = h.parameters
        response = client.post("/backtests/reference-replay/preflight", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "READY"
    assert body["metrics"]["total_trades"] == 1
    trade = body["trades"][0]
    for native, replay in (
        ("expected_entry", "entry_price"),
        ("stop_loss", "stop_loss"),
        ("take_profit", "take_profit"),
        ("signal_price", "signal_price"),
    ):
        assert getattr(candidate, native) == D(trade[replay])
    position = h.position(
        entry_price=candidate.expected_entry,
        quantity=D(trade["quantity"]),
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        failure_level=candidate.failure_level,
    )
    result = h.exit_step(position)
    assert result.exit_candidate.price == D(trade["exit_price"])
    assert result.exit_candidate.reason == trade["exit_reason"]
    assert result.exit_candidate.phase == "BRACKET"
    assert not result.execution_authority and not result.forward_qualifying
    assert not h.state.execution_authority
    assert "quantity" not in type(candidate).model_fields
    assert h.state.last_entry_open is None


@pytest.mark.parametrize("filled", [True, False])
def test_candidate_requires_explicit_resolution_and_only_fill_starts_cooldown(filled):
    h = Harness()
    candidate = h.candidate()
    following = advance_jam_features(h.features, h.bars[33])
    with pytest.raises(NativeBarError, match="resolution_required"):
        evaluate_jam_setup(
            h.state,
            **{**h.args(), "features": following},
            equity=D("100"),
            entry_window=True,
            position_open=False,
        )
    resolved = resolve_jam_entry(h.state, proposal_hash=h.state.proposal_hash, filled=filled)
    assert resolved.last_entry_open == (candidate.bar_open if filled else None)
    assert resolved.awaiting_entry is None and resolved.pending is None
    h.state = resolved
    assert h.step(position_open=filled).state.bar_count == 34
    with pytest.raises(NativeBarError, match="resolution_mismatch"):
        resolve_jam_entry(resolved, proposal_hash=h.state.proposal_hash, filled=filled)


@pytest.mark.parametrize(
    "hash_value,filled", [("0" * 64, True), (None, True), ("current", 1), ("current", "true")]
)
def test_wrong_or_coerced_resolution_rejected(hash_value, filled):
    h = Harness()
    h.candidate()
    with pytest.raises(NativeBarError, match="resolution_mismatch"):
        resolve_jam_entry(
            h.state,
            proposal_hash=h.state.proposal_hash if hash_value == "current" else hash_value,
            filled=filled,
        )


@pytest.mark.parametrize(
    "policy,reason",
    [({"entry_window": False}, "WINDOW_CLOSED"), ({"position_open": True}, "POSITION_OPEN")],
)
def test_pending_cancellation(policy, reason):
    h = Harness()
    h.step()
    armed = h.step()
    assert armed.state.awaiting_entry is None
    result = h.step(**policy)
    assert result.cancellations == (reason,)
    assert result.state.pending is None and result.state.awaiting_entry is None


def test_pending_midpoint_and_expiry_are_inclusive_and_causal():
    h = Harness({"confirm_window_bars": 1})
    h.candidate()  # A confirmation at exactly age=1 remains valid.
    h = Harness({"confirm_window_bars": 1})
    h.step()
    h.step()
    dull = h.bars[32].model_copy(update={"close": D("101.5")})
    assert h.step(bar=dull).status == "PENDING"
    result = h.step()
    assert "EXPIRED" in result.cancellations
    assert result.state.awaiting_entry is None
    h = Harness({"cancel_pending_on_midpoint_failure": True})
    h.step()
    h.step()
    bar = h.bars[32].model_copy(update={"open": D("100"), "low": D("99.5"), "close": D("100")})
    assert h.step(bar=bar).cancellations == ("MIDPOINT",)


@pytest.mark.parametrize(
    "changes,equity",
    [
        ({"use_volume_filter": True, "volume_expansion": "10"}, D("100")),
        ({"use_cost_aware_filter": True, "min_net_reward_risk": "100"}, D("100")),
        ({"stop_atr_buffer": "1000"}, D("100")),
        ({}, D("0")),
    ],
)
def test_infeasible_setup_does_not_arm(changes, equity):
    h = Harness(changes)
    h.step(equity=equity)
    assert h.step(equity=equity).status == "IDLE"


@pytest.mark.parametrize("mode", ["None", "HTF trend", "Local reversal", "Hybrid"])
def test_context_modes_and_restart_determinism(mode):
    h = Harness({"context_mode": mode})
    h.candidate()
    other = Harness({"context_mode": mode})
    other.candidate()
    assert h.state == other.state
    assert h.state.proposal_hash == other.state.proposal_hash


def test_adaptive_confirmation_uses_fixed_15m_thresholds():
    h = Harness(
        {
            "use_timeframe_adaptive_confirmation": True,
            "min_confirm_close_position": "0.99",
            "confirm_window_bars": 1,
        }
    )
    h.candidate()  # 0.888... close position clears adaptive 0.85, not configured 0.99.
    h = Harness(
        {"use_timeframe_adaptive_confirmation": False, "min_confirm_close_position": "0.99"}
    )
    h.step()
    h.step()
    assert h.step().status == "PENDING"


def test_cooldown_counts_from_entry_not_exit():
    h = Harness({"trade_cooldown_bars": 2}, seed_count=31)
    h.state = JamSetupState.model_validate(
        {**h.state.model_dump(), "last_entry_open": h.state.last_open}
    )
    assert h.step().status == "IDLE"


@pytest.mark.parametrize("equity", [D("NaN"), D("Infinity"), D("-1"), 100, True])
def test_equity_must_be_explicit_finite_decimal(equity):
    with pytest.raises(NativeBarError, match="equity_invalid"):
        Harness().step(equity=equity)


@pytest.mark.parametrize("field", ["entry_window", "position_open"])
def test_policy_is_not_coerced(field):
    with pytest.raises(NativeBarError, match="explicit_policy"):
        Harness().step(**{field: 1})


def test_warmup_emits_no_decision():
    h = Harness(seed_count=5)
    assert h.step().status == "NOT_READY"


@pytest.mark.parametrize("change", ["settings", "terms", "scope", "features", "gap", "repeat"])
def test_state_binding_rejects_changed_context_and_span(change):
    h = Harness()
    if change == "settings":
        h.parameters["reward_risk"] = "2"
        h.scope = scope_for(h.parameters)
    elif change == "terms":
        h.terms = h.terms.model_copy(update={"slippage_ticks": 3})
    elif change == "scope":
        h.scope = h.scope.model_copy(update={"feed_id": "binance_spot_public"})
    elif change == "features":
        h.parameters["trend_ema"] = 6
        h.scope = scope_for(h.parameters)
    if change == "gap":
        h.features = advance_jam_features(h.features, h.bars[30])
    if change == "repeat":
        with pytest.raises(NativeBarError, match="contiguous"):
            evaluate_jam_setup(
                h.state, **h.args(), equity=D("100"), entry_window=True, position_open=False
            )
    else:
        with pytest.raises(NativeBarError, match="context_changed|parameters_mismatch|contiguous"):
            h.step()


def test_arithmetic_context_and_unvalidated_copies_rejected():
    h = Harness()
    with localcontext() as ctx:
        ctx.prec = 12
        with pytest.raises(NativeBarError):
            initialize_jam_setup(**h.args())
    h.state = h.state.model_copy(update={"execution_authority": True})
    with pytest.raises(ValidationError):
        h.step()


@pytest.mark.parametrize(
    "name,value",
    [
        ("tick_size", "0"),
        ("minimum_contract", "NaN"),
        ("slippage_ticks", True),
        ("slippage_ticks", -1),
        ("point_value", "2"),
    ],
)
def test_invalid_execution_terms(name, value):
    with pytest.raises(ValidationError):
        JamDecisionTerms.model_validate(
            {"tick_size": "0.01", "minimum_contract": "0.00001", "slippage_ticks": 2, name: value}
        )


@pytest.mark.parametrize("offset", [-1, 1, 900])
def test_partial_or_wrong_entry_candle_is_not_treated_as_fully_observed(offset):
    h = Harness()
    with pytest.raises(NativeBarError, match="boundary_fill"):
        h.position(filled_at=h.features.recent[-1].timestamp + STEP + timedelta(seconds=offset))


@pytest.mark.parametrize(
    "ohlc,reason,price,ambiguous",
    [
        ((97, 99, 96, 98), "STOP_GAP", "96.98", False),
        ((151, 152, 149, 150), "TAKE_PROFIT_GAP", "150", False),
        ((100, 151, 97, 101), "STOP_AND_TARGET_AMBIGUOUS", "97.98", True),
        ((100, 101, 97, 100), "STOP_LOSS", "97.98", False),
        ((100, 151, 99, 101), "TAKE_PROFIT", "150", False),
    ],
)
def test_bracket_ordering_and_unresolved_exit_block(ohlc, reason, price, ambiguous):
    h = Harness({"use_atr_trail": True, "trail_start_r": "0.1", "trail_atr_multiplier": "0.1"})
    position = h.position()
    bar = h.bars[30].model_copy(
        update=dict(zip(("open", "high", "low", "close"), map(D, ohlc), strict=True))
    )
    result = h.exit_step(position, bar)
    assert result.exit_candidate.reason == reason
    assert result.exit_candidate.price == D(price)
    assert result.exit_candidate.intrabar_ambiguous == ambiguous
    assert result.stop_loss == position.stop_loss
    assert result.exit_candidate.phase == "BRACKET"
    restored = JamManagedPosition.model_validate_json(result.model_dump_json())
    with pytest.raises(NativeBarError, match="exit_resolution_required"):
        h.exit_step(restored)


def test_breakeven_is_next_bar_only_and_never_uses_signal_bar_high():
    h = Harness(
        {"use_breakeven_stop": True, "breakeven_at_r": "0.5", "breakeven_offset_ticks": 0},
        seed_count=32,
    )
    position = h.position()
    assert position.best_price == D("100") < h.features.recent[-1].high
    # The new stop (100) is above this bar's low, but must not exit retroactively.
    bar = h.bars[32].model_copy(update={"open": D("100"), "low": D("99"), "close": D("101")})
    result = h.exit_step(position, bar)
    assert result.exit_candidate is None and result.stop_loss == D("100")
    bar = h.bars[33].model_copy(update={"open": D("99.5"), "low": D("99"), "close": D("100")})
    result = h.exit_step(result, bar)
    assert result.exit_candidate.reason == "STOP_GAP"
    assert result.exit_candidate.price == D("99.48")


def test_atr_trail_never_loosens_or_acts_on_same_bar():
    h = Harness({"use_atr_trail": True, "trail_start_r": "0.1", "trail_atr_multiplier": "0.1"})
    position = h.position()
    result = h.exit_step(position)
    assert result.exit_candidate is None and result.stop_loss > D("98")
    old_stop = result.stop_loss
    # Hold the next candle entirely above the old stop, with wider ATR.
    bar = h.bars[31].model_copy(
        update={"open": D("102"), "low": D("102"), "high": D("102.1"), "close": D("102.05")}
    )
    result = h.exit_step(result, bar)
    assert result.stop_loss >= old_stop


@pytest.mark.parametrize(
    "midpoint,pullback,expected",
    [
        (True, True, "MIDPOINT_FAILURE"),
        (False, True, "PULLBACK_FAILURE"),
        (False, False, "TIME_EXIT"),
    ],
)
def test_close_exit_priority_and_slippage(midpoint, pullback, expected):
    h = Harness(
        {
            "use_midpoint_failure_exit": midpoint,
            "use_pullback_failure_exit": pullback,
            "max_bars_in_trade": 1,
        }
    )
    position = h.position(failure_level=D("99.5"))
    bar = h.bars[30].model_copy(
        update={"open": D("100"), "high": D("100"), "low": D("98.5"), "close": D("99")}
    )
    result = h.exit_step(position, bar)
    assert result.exit_candidate.reason == expected
    assert result.exit_candidate.phase == "CLOSE"
    assert result.exit_candidate.price == D("98.98")
    assert result.exit_candidate.slippage == D("0.01")


def test_native_planner_does_not_liquidate_on_historical_window_end():
    h = Harness(seed_count=35)
    result = h.exit_step(h.position(stop_loss=D("90")))
    assert h.features.recent[-1].timestamp + STEP == datetime.fromisoformat(
        h.parameters["backtest_end"]
    )
    assert result.exit_candidate is None


def test_old_bracket_still_runs_when_features_are_not_ready():
    h = Harness(seed_count=5)
    position = h.position(stop_loss=D("99.5"))
    result = h.exit_step(position)
    assert result.exit_candidate.reason == "STOP_LOSS"


@pytest.mark.parametrize(
    "changes", [{"entry_price": "98"}, {"stop_loss": "0"}, {"take_profit": "99"}, {"quantity": "0"}]
)
def test_invalid_position_geometry(changes):
    with pytest.raises(ValidationError):
        Harness().position(**{key: D(value) for key, value in changes.items()})


def test_terms_and_held_position_survive_json_restart():
    h = Harness()
    assert JamDecisionTerms.model_validate_json(h.terms.model_dump_json()) == h.terms
    position = h.position()
    held = h.exit_step(position)
    restored = JamManagedPosition.model_validate_json(held.model_dump_json())
    features = advance_jam_features(h.features, h.bars[31])
    assert plan_jam_exit(held, **{**h.args(), "features": features}) == plan_jam_exit(
        restored, **{**h.args(), "features": features}
    )


@pytest.mark.parametrize("change", ["terms", "settings", "repeat", "authority"])
def test_managed_position_rejects_changed_inputs(change):
    h = Harness()
    position = h.position()
    if change == "terms":
        h.terms = h.terms.model_copy(update={"slippage_ticks": 3})
    elif change == "settings":
        h.parameters["use_atr_trail"] = True
        h.scope = scope_for(h.parameters)
    elif change == "authority":
        position = position.model_copy(update={"execution_authority": True})
    if change == "repeat":
        with pytest.raises(NativeBarError, match="contiguous"):
            plan_jam_exit(position, **h.args())
    else:
        with pytest.raises((NativeBarError, ValidationError)):
            h.exit_step(position)


def test_confirmation_does_not_reapply_the_arming_volume_filter():
    h = Harness({"use_volume_filter": True, "volume_expansion": "1.1"})
    h.step()
    assert h.step().status == "ARMED"
    result = h.step(bar=h.bars[32].model_copy(update={"volume": D("0")}))
    assert result.status == "ENTRY_CANDIDATE"


@pytest.mark.parametrize(
    "fields",
    [
        {"close": D("101.6")},  # Exactly at the trigger does not confirm.
        {"open": D("102.1")},  # Bullish close required.
        {"high": D("110")},  # Excessive range / poor close location.
    ],
)
def test_confirmation_boundaries(fields):
    h = Harness()
    h.step()
    h.step()
    assert h.step(bar=h.bars[32].model_copy(update=fields)).status == "PENDING"


def test_adaptive_expiry_does_not_use_configured_short_window():
    h = Harness({"confirm_window_bars": 1, "use_timeframe_adaptive_confirmation": True})
    h.step()
    h.step()
    for index in (32, 33):
        dull = h.bars[index].model_copy(
            update={"open": D("101.5"), "high": D("101.6"), "low": D("101.3"), "close": D("101.5")}
        )
        result = h.step(bar=dull)
        assert result.status == "PENDING"
        assert result.cancellations == ()


def test_cancellation_runs_even_during_feature_warmup():
    h = Harness(seed_count=5)
    h.state = JamSetupState.model_validate(
        {
            **h.state.model_dump(),
            "pending": {
                "armed_open": h.state.last_open,
                "trigger": D("101"),
                "stop_loss": D("98"),
                "failure_level": D("99"),
            },
        }
    )
    result = h.step(entry_window=False)
    assert result.status == "NOT_READY" and result.cancellations == ("WINDOW_CLOSED",)
    assert result.state.pending is None


@pytest.mark.parametrize("field", ["last_entry_open", "pending"])
def test_future_pending_or_cooldown_rejected(field):
    h = Harness()
    future = h.state.last_open + STEP
    value = (
        future
        if field == "last_entry_open"
        else {"armed_open": future, "trigger": "101", "stop_loss": "98", "failure_level": "99"}
    )
    if field == "pending":
        value = JamPendingSetup.model_validate(value)
    h.state = h.state.model_copy(update={field: value})
    with pytest.raises(ValidationError, match="span_invalid"):
        h.step()


def test_impossible_slippage_price_fails_closed():
    h = Harness()
    h.terms = h.terms.model_copy(update={"tick_size": D("100"), "slippage_ticks": 2})
    with pytest.raises(ValidationError):
        h.exit_step(h.position(stop_loss=D("99.9")))
