"""Offline packets and disposable ledgers only. Positive eligibility is mocked."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from aurex.backtest_engine.eligibility import PaperBacktestEligibility
from aurex.db.models import (
    Account,
    NativeBarOutcome,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
)
from aurex.domain.enums import PositionStatus, TradeStatus
from aurex.execution_engine.paper import paper_execution_evidence_hash
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_jam_runtime import JamDecisionReceipt, JamRuntimeConfig
from aurex.signal_gateway.native_observation import NativePublicObserver
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    validate_chain,
    verified_native_history,
)
from aurex.strategy_engine.registry import (
    REGISTERED_STRATEGIES,
    STRATEGY_FACTORY_CONTRACT_VERSION,
    StrategyLifecycleStatus,
)
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.test_jam_reversal_spot_replay import jam_candles, jam_parameters
from tests.integration.test_native_bar_processing import counts
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_jam_history import jam_scope
from tests.integration.test_native_observation import acquisition, set_clock
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP

D = Decimal


def config(**changes):
    return JamRuntimeConfig(
        parameters={**jam_parameters(), "reward_risk": "3", **changes},
        terms={"tick_size": "0.01", "minimum_contract": "0.00001", "slippage_ticks": 0},
    )


class Run:
    def __init__(self, engine, settings, monkeypatch, configuration=None):
        self.engine, self.settings, self.monkeypatch = engine, settings, monkeypatch
        self.config = configuration or config()
        self.scope = jam_scope(self.config.parameters, feed_id="binance_spot_public")
        self.bars = [c.model_dump() for c in jam_candles()]
        self.observer = NativePublicObserver(engine, settings)

    def step(self, index=29):
        bars = self.bars[:30] if index == 29 else [self.bars[index]]
        now = self.bars[index]["timestamp"] + STEP + timedelta(seconds=5)
        source = acquisition(self.monkeypatch, bars, now)
        result = self.observer.evaluate_jam(
            scope=self.scope, config=self.config.model_dump(mode="json"), seed_count=30
        )
        assert len(source.calls) == 1
        return result

    def armed(self):
        self.step()
        self.step(30)
        return self.step(31)

    def receipts(self):
        with Session(self.engine) as session:
            return [receipt for _, receipt in validate_chain(session)]


def eligible_fixture(run):
    """Mock only strategy qualification, never sizing, costs, risk or execution."""
    strategy = run.scope.strategy
    run.monkeypatch.setitem(
        REGISTERED_STRATEGIES,
        strategy,
        replace(
            REGISTERED_STRATEGIES[strategy],
            lifecycle_status=StrategyLifecycleStatus.ACTIVE,
            lifecycle_reason="Synthetic runtime fixture only",
            qualification_contract_version=STRATEGY_FACTORY_CONTRACT_VERSION,
            qualification_evidence_hash="f" * 64,
        ),
    )
    run.monkeypatch.setattr(
        "aurex.risk_engine.service.paper_backtest_eligibility",
        lambda *a, **kw: PaperBacktestEligibility(
            True,
            "Synthetic test only",
            None,
            {
                "strategy_parameter_evidence": {"known_strategy": True},
                "strategy_version": run.scope.strategy_version,
                "strategy_parameter_fingerprint": run.scope.settings_fingerprint,
            },
        ),
    )
    with Session(run.engine) as session, session.begin():
        strategy_config = StrategyPortfolioService(session).get_config(strategy)
        strategy_config.is_enabled = True


def test_retired_jam_is_rejected_and_resolution_is_atomic(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    run.armed()
    result = run.step(32)
    assert result.processing.outcome == "RISK_REJECTED"
    receipt = run.receipts()[-1]
    evidence = JamDecisionReceipt.model_validate(receipt.jam_decision)
    assert evidence.decision.status == "ENTRY_CANDIDATE"
    assert evidence.resolved_state.awaiting_entry is None
    assert evidence.resolved_state.last_entry_open is None
    assert evidence.risk.approved is False and "lifecycle" in evidence.risk.reason
    assert evidence.entry is None and evidence.forward_qualifying is False
    assert counts(engine)["paper_orders"] == 0
    run.observer = NativePublicObserver(engine, settings)
    assert run.step(33).processing.outcome == "JAM_NO_SIGNAL"
    assert len(run.receipts()) == 5


def test_seed_and_armed_state_are_reconstructed_not_trusted(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    run.armed()
    receipts = run.receipts()
    assert all(r.schema_version == "native_bar_processing_v7" for r in receipts)
    assert receipts[0].jam_decision["decision"] is None
    assert receipts[-1].jam_decision["decision"]["status"] == "ARMED"
    with Session(engine) as session:
        audit = verified_native_history(session, run.bars[31]["timestamp"])
        assert (
            audit.jam_runtime.state
            == JamDecisionReceipt.model_validate(receipts[-1].jam_decision).resolved_state
        )
        assert audit.jam_runtime.features.bar_count == 32
    assert counts(engine)["signals"] == 0


def test_paper_fill_uses_existing_cost_aware_risk_and_is_nonqualifying(
    engine, settings, monkeypatch
):
    run = Run(engine, settings, monkeypatch)
    eligible_fixture(run)
    run.armed()
    result = run.step(32)
    receipt = run.receipts()[-1]
    assert result.processing.outcome == "PAPER_EXECUTED", receipt.jam_decision["risk"]
    e = JamDecisionReceipt.model_validate(receipt.jam_decision)
    assert e.entry is not None and e.risk.approved
    assert e.entry.quantity == e.risk.position_size
    assert e.entry.entry_price == receipt.bar.close
    assert e.entry.risk_amount <= D("0.5")
    assert e.resolved_state.last_entry_open == receipt.bar.timestamp
    with Session(engine) as session:
        order = session.get(PaperOrder, e.entry.order_id)
        assert order.fill_model == "native_ohlc_online_exit_v1"
        assert order.fees > 0 and order.slippage > 0
        assert (
            e.risk.rules_snapshot["native_spot_budget"]["policy_version"]
            == "native_btcusdt_spot_paper_v1"
        )


@pytest.mark.parametrize("positive", [False, True])
def test_receipt_insert_failure_rolls_back_every_effect(engine, settings, monkeypatch, positive):
    run = Run(engine, settings, monkeypatch)
    if positive:
        eligible_fixture(run)
    run.armed()
    before = counts(engine)

    def fail(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO native_bar_outcomes"):
            raise RuntimeError("simulated crash after decision effects")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            run.step(32)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert counts(engine) == before
    assert run.receipts()[-1].jam_decision["decision"]["status"] == "ARMED"
    assert run.step(32).processing.outcome == ("PAPER_EXECUTED" if positive else "RISK_REJECTED")


@pytest.mark.parametrize("change", ["trigger", "cooldown", "equity", "risk", "resolution"])
def test_rehashed_decision_tampering_is_rejected(engine, settings, monkeypatch, change):
    run = Run(engine, settings, monkeypatch)
    run.armed()
    if change in {"risk", "resolution"}:
        run.step(32)
    with Session(engine) as session, session.begin():
        row = session.scalar(
            select(NativeBarOutcome).order_by(NativeBarOutcome.sequence.desc()).limit(1)
        )
        evidence = deepcopy(row.evidence)
        jam = evidence["jam_decision"]
        if change == "trigger":
            jam["resolved_state"]["pending"]["trigger"] = "200"
        elif change == "cooldown":
            jam["resolved_state"]["last_entry_open"] = evidence["bar"]["timestamp"]
        elif change == "equity":
            jam["equity_before"] = "99"
        elif change == "risk":
            jam["risk"]["reason"] = "forged reason"
        else:
            jam["resolved_state"]["last_entry_open"] = evidence["bar"]["timestamp"]
        row.evidence, row.evidence_hash = evidence, content_hash(evidence)
    with pytest.raises(NativeBarError, match="jam_runtime_"):
        run.receipts()


def test_owned_head_changed_during_acquisition_rejects_without_effects(
    engine, settings, monkeypatch
):
    run = Run(engine, settings, monkeypatch)
    run.step()
    before = counts(engine)
    original = run.observer._processor._process

    def changed(*args, **kwargs):
        kwargs["expected_jam_head"] = "f" * 64
        return original(*args, **kwargs)

    monkeypatch.setattr(run.observer._processor, "_process", changed)
    with pytest.raises(NativeBarError, match="expected_head_changed"):
        run.step(30)
    assert counts(engine) == before


def test_exact_packet_retry_returns_original_without_reingesting(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    captured = []
    original = run.observer._processor._process

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(run.observer._processor, "_process", capture)
    run.armed()
    result = run.step(32)
    before = counts(engine)
    args, kwargs = captured[-1]
    retry = NativeBarProcessor(engine, settings)._process(*args, **kwargs)
    assert retry.is_duplicate and retry.evidence_hash == result.processing.evidence_hash
    assert counts(engine) == before


@pytest.mark.parametrize("mode", ["observe", "manage_exits"])
def test_other_modes_cannot_drop_decision_state(engine, settings, monkeypatch, mode):
    run = Run(engine, settings, monkeypatch)
    run.step()
    state = acquisition(
        monkeypatch, [run.bars[30]], run.bars[30]["timestamp"] + STEP + timedelta(seconds=5)
    )
    with pytest.raises(NativeBarError, match="stream_mode_changed"):
        getattr(run.observer, mode)(scope=run.scope)
    assert state.calls == []


def test_configuration_change_is_rejected_before_fetch(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    run.step()
    state = acquisition(
        monkeypatch, [run.bars[30]], run.bars[30]["timestamp"] + STEP + timedelta(seconds=5)
    )
    changed = run.config.model_dump(mode="json")
    changed["terms"]["tick_size"] = "0.02"
    with pytest.raises(NativeBarError, match="config_changed"):
        run.observer.evaluate_jam(scope=run.scope, config=changed, seed_count=30)
    assert state.calls == []


def test_wait_does_not_refetch_or_write(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    result = run.step()
    before = counts(engine)
    set_clock(monkeypatch, run.bars[29]["timestamp"] + STEP + timedelta(seconds=60))
    waiting = run.observer.evaluate_jam(
        scope=run.scope, config=run.config.model_dump(mode="json"), seed_count=30
    )
    assert waiting.status == "WAITING_FOR_CLOSE" and waiting.processing is None
    assert waiting.next_observation_at == result.next_observation_at
    assert counts(engine) == before


@pytest.mark.parametrize("field,value", [("starting_equity", "1000"), ("current_equity", "99")])
def test_wrong_or_unreconciled_account_rejects_without_reset(
    engine, settings, monkeypatch, field, value
):
    with Session(engine) as session, session.begin():
        account = session.scalar(select(Account))
        setattr(account, field, D(value))
    with pytest.raises(NativeBarError):
        Run(engine, settings, monkeypatch).step()
    assert counts(engine)["native_bar_outcomes"] == 0
    with Session(engine) as session:
        assert getattr(session.scalar(select(Account)), field) == D(value)


@pytest.mark.parametrize("change", [{"slippage_ticks": 1}, {"tick_size": "0.000000001"}])
def test_native_cost_contract_cannot_double_charge_price_slippage(change):
    data = config().model_dump(mode="json")
    data["terms"].update(change)
    with pytest.raises(ValidationError):
        JamRuntimeConfig.model_validate(data)


def test_modified_risk_ledger_is_not_hidden_by_unchanged_receipt(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    run.armed()
    run.step(32)
    with Session(engine) as session, session.begin():
        session.scalar(select(RiskDecision)).reason = "modified outside native transaction"
    with pytest.raises(NativeBarError, match="risk_evidence_mismatch"):
        run.receipts()


def test_signal_matches_the_generated_candidate_and_no_external_delivery_is_claimed(
    engine, settings, monkeypatch
):
    run = Run(engine, settings, monkeypatch)
    run.armed()
    run.step(32)
    receipt = run.receipts()[-1]
    assert receipt.public_observation is not None and receipt.public_source is not None
    assert not receipt.source_origin_verified
    with Session(engine) as session:
        signal = session.scalar(select(Signal))
        assert signal.source == "aurex_native"
        assert signal.raw_payload == receipt.signal_request.model_dump(mode="json")


def filled_run(engine, settings, monkeypatch, configuration=None):
    run = Run(engine, settings, monkeypatch, configuration)
    eligible_fixture(run)
    run.armed()
    assert run.step(32).processing.outcome == "PAPER_EXECUTED"
    entry = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision).entry
    return run, entry


def bar_prices(run, index, *, opened, high, low, close):
    run.bars[index].update(open=opened, high=high, low=low, close=close)


def held_partial(run, entry):
    bar_prices(
        run,
        33,
        opened=entry.entry_price,
        high=entry.take_profit + 1,
        low=entry.entry_price,
        close=entry.entry_price + D("0.1"),
    )
    run.step(33)
    return JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision)


def test_partial_bar_high_cannot_activate_target_or_trail(engine, settings, monkeypatch):
    run, entry = filled_run(engine, settings, monkeypatch, config(use_breakeven_stop=True))
    e = held_partial(run, entry)
    assert e.management.disposition == "HELD" and e.management.partial_entry_bar
    assert e.managed_state.best_price == entry.entry_price
    assert e.managed_state.stop_loss == entry.stop_loss
    assert e.equity_before == e.equity_after == D("100")
    assert e.entry is None and e.managed_state.bar_count == 34
    # Restart must recover the original entry and the management cursor, not a cache.
    run.observer = NativePublicObserver(engine, settings)
    bar_prices(
        run,
        34,
        opened=entry.entry_price,
        high=entry.entry_price + D("0.2"),
        low=entry.entry_price,
        close=entry.entry_price + D("0.1"),
    )
    run.step(34)
    assert not JamDecisionReceipt.model_validate(
        run.receipts()[-1].jam_decision
    ).management.partial_entry_bar


@pytest.mark.parametrize("kind", ["stop", "target"])
def test_partial_entry_exit_uses_explicit_bounds_and_correct_phase(
    engine, settings, monkeypatch, kind
):
    run, entry = filled_run(engine, settings, monkeypatch)
    bar_prices(
        run,
        33,
        opened=entry.entry_price,
        high=entry.take_profit + 1,
        low=entry.stop_loss - 1 if kind == "stop" else entry.entry_price,
        close=entry.take_profit + D("0.1"),
    )
    run.step(33)
    e = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision)
    exit_ = e.management
    assert exit_.disposition == "CLOSED" and exit_.partial_entry_bar
    assert exit_.exit_price == (entry.stop_loss - 1 if kind == "stop" else entry.take_profit)
    assert exit_.exit_reason == (
        "PARTIAL_ENTRY_STOP_BOUND" if kind == "stop" else "PARTIAL_ENTRY_TARGET_AT_CLOSE"
    )
    assert exit_.plan.exit_candidate.phase == ("BRACKET" if kind == "stop" else "CLOSE")
    assert exit_.plan.exit_candidate.intrabar_ambiguous == (kind == "stop")
    assert e.equity_for_decision == (e.equity_after if kind == "stop" else e.equity_before)
    assert e.equity_after == D("100") + exit_.realized_pl
    assert e.managed_state is None and e.entry is None
    with Session(engine) as session:
        trade = session.get(PaperTrade, entry.trade_id)
        assert trade.status == TradeStatus.CLOSED
        assert trade.stop_loss == entry.stop_loss
        assert session.get(Position, entry.position_id).status == PositionStatus.CLOSED
        assert session.get(Account, entry.account_id).current_equity == e.equity_after
    # Historical entry verification must work after its ledger trade has closed.
    assert len(run.receipts()) == 5


@pytest.mark.parametrize("kind", ["stop_first", "target", "time"])
def test_full_bar_exit_ordering_costs_and_reconstruction(engine, settings, monkeypatch, kind):
    run, entry = filled_run(engine, settings, monkeypatch, config(max_bars_in_trade=2))
    held_partial(run, entry)
    if kind == "time":
        high, low, close = entry.entry_price + 1, entry.entry_price, entry.entry_price + D("0.2")
    else:
        high, low, close = (
            entry.take_profit + 1,
            entry.stop_loss - 1 if kind == "stop_first" else entry.entry_price,
            entry.entry_price,
        )
    bar_prices(run, 34, opened=entry.entry_price, high=high, low=low, close=close)
    from aurex.signal_gateway import native_jam_runtime as runtime

    original = runtime.evaluate_jam_setup
    evaluated = []

    def spy(*a, **kw):
        if kw["features"].bar_count == 35:
            evaluated.append((kw["position_open"], kw["equity"]))
        return original(*a, **kw)

    monkeypatch.setattr(runtime, "evaluate_jam_setup", spy)
    run.step(34)
    e = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision)
    assert e.management.disposition == "CLOSED"
    assert e.management.total_fees > 0 and e.management.total_slippage > 0
    assert e.equity_after == D("100") + e.management.realized_pl
    assert evaluated and all(opened == (kind == "time") for opened, _ in evaluated)
    assert all(equity == e.equity_for_decision for _, equity in evaluated)
    if kind == "time":
        assert e.management.exit_reason == "TIME_EXIT"
        assert e.equity_for_decision == e.equity_before
    else:
        assert e.management.exit_price == (
            entry.stop_loss if kind == "stop_first" else entry.take_profit
        )
        assert e.equity_for_decision == e.equity_after
    run.observer = NativePublicObserver(engine, settings)
    run.step(35)
    assert (
        JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision).equity_before
        == e.equity_after
    )


def test_updated_stop_is_next_bar_only_and_does_not_rewrite_entry(engine, settings, monkeypatch):
    run, entry = filled_run(
        engine,
        settings,
        monkeypatch,
        config(
            use_breakeven_stop=True,
            breakeven_at_r="0.5",
            breakeven_offset_ticks=0,
        ),
    )
    held_partial(run, entry)
    risk = entry.entry_price - entry.stop_loss
    bar_prices(
        run,
        34,
        opened=entry.entry_price,
        high=entry.entry_price + risk,
        low=entry.entry_price - D("0.1"),
        close=entry.entry_price + D("0.1"),
    )
    run.step(34)
    e = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision)
    assert e.management.disposition == "HELD"
    assert e.managed_state.stop_loss == entry.entry_price
    bar_prices(
        run,
        35,
        opened=entry.entry_price + D("0.1"),
        high=entry.take_profit + 1,
        low=entry.entry_price - D("0.1"),
        close=entry.entry_price,
    )
    run.step(35)
    exit_ = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision).management
    assert exit_.exit_price == entry.entry_price
    assert exit_.plan.exit_candidate.intrabar_ambiguous
    with Session(engine) as session:
        assert session.get(PaperTrade, entry.trade_id).stop_loss == entry.stop_loss


@pytest.mark.parametrize("close", [False, True])
def test_management_receipt_failure_rolls_back_exit_equity_and_cursor(
    engine, settings, monkeypatch, close
):
    run, entry = filled_run(engine, settings, monkeypatch)
    bar_prices(
        run,
        33,
        opened=entry.entry_price,
        high=entry.take_profit + 1,
        low=entry.stop_loss - 1 if close else entry.entry_price,
        close=entry.entry_price,
    )
    before = counts(engine)
    before_hash = run.receipts()[-1].jam_decision

    def fail(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO native_bar_outcomes"):
            raise RuntimeError("simulated management receipt crash")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="simulated management"):
            run.step(33)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert counts(engine) == before
    assert run.receipts()[-1].jam_decision == before_hash
    with Session(engine) as session:
        assert session.get(Account, entry.account_id).current_equity == D("100")
        assert session.get(PaperTrade, entry.trade_id).status == TradeStatus.OPEN
        assert session.get(Position, entry.position_id).status == PositionStatus.OPEN
    run.step(33)
    assert JamDecisionReceipt.model_validate(
        run.receipts()[-1].jam_decision
    ).management.disposition == ("CLOSED" if close else "HELD")


@pytest.mark.parametrize("change", ["stop", "best", "phase", "exit", "equity", "cost"])
def test_rehashed_managed_receipt_cannot_fabricate_state_or_exit(
    engine, settings, monkeypatch, change
):
    run, entry = filled_run(engine, settings, monkeypatch)
    if change in {"stop", "best"}:
        held_partial(run, entry)
    else:
        bar_prices(
            run,
            33,
            opened=entry.entry_price,
            high=entry.take_profit + 1,
            low=entry.entry_price,
            close=entry.take_profit,
        )
        run.step(33)
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome).order_by(NativeBarOutcome.sequence.desc()))
        evidence = deepcopy(row.evidence)
        jam = evidence["jam_decision"]
        if change in {"stop", "best"}:
            key = "stop_loss" if change == "stop" else "best_price"
            jam["managed_state"][key] = str(D(jam["managed_state"][key]) + 1)
        elif change == "phase":
            jam["management"]["plan"]["exit_candidate"]["phase"] = "BRACKET"
        elif change == "exit":
            jam["management"]["exit_price"] = str(entry.take_profit + 1)
        elif change == "equity":
            jam["equity_after"] = "110"
        else:
            jam["management"]["total_fees"] = "0"
        row.evidence, row.evidence_hash = evidence, content_hash(evidence)
    with pytest.raises(NativeBarError, match="jam_runtime_"):
        run.receipts()


def test_unreceipted_manual_close_blocks_instead_of_resetting(engine, settings, monkeypatch):
    from aurex.execution_engine.paper import PaperExecutionEngine

    run, entry = filled_run(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        PaperExecutionEngine(session, settings).close_trade(
            entry.trade_id,
            entry.entry_price,
            "manual unreceipted close",
            now=entry.opened_at + STEP,
        )
    with pytest.raises(NativeBarError, match="jam_runtime_open_ledger_unreconciled"):
        run.receipts()


def test_exits_ignore_entry_kill_and_use_frozen_costs(engine, settings, monkeypatch):
    run, entry = filled_run(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        RiskEngine(session).set_kill_switch(True)
        StrategyPortfolioService(session).get_config(run.scope.strategy).is_enabled = False
        frozen = deepcopy(
            session.get(PaperOrder, entry.order_id).execution_assumptions["assumptions"]
        )
    # Retirement and entry kill controls must not disable protective exits.
    monkeypatch.setitem(
        REGISTERED_STRATEGIES,
        run.scope.strategy,
        replace(
            REGISTERED_STRATEGIES[run.scope.strategy],
            lifecycle_status=StrategyLifecycleStatus.RETIRED,
        ),
    )
    run.observer = NativePublicObserver(
        engine, settings.model_copy(update={"paper_commission_bps": D("1000")})
    )
    held_partial(run, entry)
    bar_prices(
        run,
        34,
        opened=entry.entry_price,
        high=entry.entry_price,
        low=entry.stop_loss - 1,
        close=entry.stop_loss,
    )
    run.step(34)
    with Session(engine) as session:
        order = session.get(PaperOrder, entry.order_id)
        assert order.execution_assumptions["assumptions"] == frozen
        assert order.execution_assumptions["cost_floor_enforced"] is True
        assert session.get(PaperTrade, entry.trade_id).status == TradeStatus.CLOSED
    assert counts(engine)["paper_orders"] == 1


@pytest.mark.parametrize("mode", ["entry", "exit"])
def test_two_workers_have_one_atomic_effect(engine, settings, monkeypatch, mode):
    if mode == "entry":
        run = Run(engine, settings, monkeypatch)
        eligible_fixture(run)
        run.armed()
        index = 32
    else:
        run, entry = filled_run(engine, settings, monkeypatch)
        index = 33
        bar_prices(
            run,
            index,
            opened=entry.entry_price,
            high=entry.entry_price,
            low=entry.stop_loss - 1,
            close=entry.stop_loss,
        )
    source = acquisition(
        monkeypatch, [run.bars[index]], run.bars[index]["timestamp"] + STEP + timedelta(seconds=5)
    )
    barrier = Barrier(2)
    source.effect = lambda: barrier.wait(timeout=30)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: NativePublicObserver(engine, settings).evaluate_jam(
                    scope=run.scope,
                    config=run.config.model_dump(mode="json"),
                    seed_count=30,
                ),
                range(2),
            )
        )
    assert len({r.processing.receipt_id for r in results}) == 1
    assert sorted(r.processing.is_duplicate for r in results) == [False, True]
    assert counts(engine)["paper_orders"] == 1
    assert len(run.receipts()) == (4 if mode == "entry" else 5)


@pytest.mark.parametrize("mode", ["entry", "exit"])
def test_lost_ack_restart_never_reexecutes_committed_effect(engine, settings, monkeypatch, mode):
    if mode == "entry":
        run = Run(engine, settings, monkeypatch)
        eligible_fixture(run)
        run.armed()
        index = 32
    else:
        run, entry = filled_run(engine, settings, monkeypatch)
        index = 33
        bar_prices(
            run,
            index,
            opened=entry.entry_price,
            high=entry.entry_price,
            low=entry.stop_loss - 1,
            close=entry.stop_loss,
        )

    def lost_ack(session):
        if not session.in_nested_transaction():
            raise RuntimeError("lost native Jam acknowledgement")

    event.listen(Session, "after_commit", lost_ack)
    try:
        with pytest.raises(RuntimeError, match="lost native Jam"):
            run.step(index)
    finally:
        event.remove(Session, "after_commit", lost_ack)
    before = counts(engine)
    run.observer = NativePublicObserver(engine, settings)
    result = run.observer.evaluate_jam(
        scope=run.scope, config=run.config.model_dump(mode="json"), seed_count=30
    )
    assert result.status == "WAITING_FOR_CLOSE"
    assert counts(engine) == before and before["paper_orders"] == 1
    run.receipts()


def test_fresh_process_reconstructs_closed_trade_without_fixture_qualification(
    engine, settings, monkeypatch
):
    run, entry = filled_run(engine, settings, monkeypatch)
    held_partial(run, entry)
    bar_prices(
        run,
        34,
        opened=entry.entry_price,
        high=entry.take_profit + 1,
        low=entry.entry_price,
        close=entry.take_profit,
    )
    run.step(34)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from aurex.signal_gateway.native_processing import validate_chain
with Session(create_engine(sys.argv[1])) as session:
    chain = validate_chain(session)
    assert len(chain) == 6
    assert chain[-1][1].jam_decision['management']['disposition'] == 'CLOSED'
    assert chain[-1][1].jam_decision['forward_qualifying'] is False
print('reconstructed')
""",
            str(engine.url),
        ],
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "reconstructed"


def test_v7_cannot_drop_owned_acquisition_admission(engine, settings, monkeypatch):
    run = Run(engine, settings, monkeypatch)
    run.step()
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome))
        evidence = deepcopy(row.evidence)
        del evidence["public_observation"]
        row.evidence, row.evidence_hash = evidence, content_hash(evidence)
    with pytest.raises(ValueError, match="jam_receipt_binding_missing"):
        run.receipts()


def test_rehashed_closed_execution_metadata_is_reconstructed(engine, settings, monkeypatch):
    run, entry = filled_run(engine, settings, monkeypatch)
    bar_prices(
        run,
        33,
        opened=entry.entry_price,
        high=entry.entry_price,
        low=entry.stop_loss - 1,
        close=entry.stop_loss,
    )
    run.step(33)
    with Session(engine) as session, session.begin():
        order = session.get(PaperOrder, entry.order_id)
        execution = deepcopy(order.execution_assumptions)
        execution["exit"]["cost_source"] = "fabricated"
        order.execution_assumptions = execution
        order.execution_assumptions_hash = paper_execution_evidence_hash(execution)
        row = session.scalar(select(NativeBarOutcome).order_by(NativeBarOutcome.sequence.desc()))
        evidence = deepcopy(row.evidence)
        evidence["jam_decision"]["management"]["execution_hash_after"] = (
            order.execution_assumptions_hash
        )
        row.evidence, row.evidence_hash = evidence, content_hash(evidence)
    with pytest.raises(NativeBarError, match="jam_runtime_close_ledger_mismatch"):
        run.receipts()


def test_second_lifecycle_uses_reconciled_equity_and_keeps_first_entry_auditable(
    engine, settings, monkeypatch
):
    run, first = filled_run(engine, settings, monkeypatch)
    bar_prices(
        run,
        33,
        opened=first.entry_price,
        high=first.take_profit + 1,
        low=first.entry_price,
        close=first.take_profit,
    )
    run.step(33)
    equity = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision).equity_after
    assert equity > D("100")
    for target, source in ((34, 30), (35, 31), (36, 32)):
        run.bars[target] = {**run.bars[source], "timestamp": run.bars[target]["timestamp"]}
        run.step(target)
    evidence = JamDecisionReceipt.model_validate(run.receipts()[-1].jam_decision)
    assert evidence.entry is not None, evidence.model_dump(mode="json")
    second = evidence.entry
    assert evidence.risk.account_equity == equity and evidence.equity_before == equity
    assert second.trade_id != first.trade_id and second.risk_amount <= D("0.5")
    bar_prices(
        run,
        37,
        opened=second.entry_price,
        high=second.entry_price,
        low=second.stop_loss - 1,
        close=second.stop_loss,
    )
    run.step(37)
    assert len(run.receipts()) == 9
    with Session(engine) as session:
        assert all(
            trade.status == TradeStatus.CLOSED for trade in session.scalars(select(PaperTrade))
        )
    assert counts(engine)["paper_orders"] == 2
