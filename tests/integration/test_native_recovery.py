"""Disposable recovery simulations: never evidence of a qualified strategy or real fills."""

import copy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from aurex.db.models import (
    EquityCurvePoint,
    NativeBarOutcome,
    PaperTrade,
    Position,
)
from aurex.domain.enums import PositionStatus, TradeStatus
from aurex.execution_engine.paper import EVIDENCE_GRADE_PAPER_FILL_MODELS, PaperExecutionEngine
from aurex.live_deployment.service import paper_execution_quality_violation
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_processing import NativeBarProcessor, validate_chain
from aurex.signal_gateway.native_recovery import RECOVERY_FILL_MODEL
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP, bars


def candle(offset=0, **changes):
    return {**bars()[-1], "timestamp": NOW + STEP * offset, **changes}


def recover(engine, settings, bar=None):
    return NativeBarProcessor(engine, settings).recover_next(
        candle() if bar is None else bar, scope=spec()
    )


def open_trade(engine, settings, monkeypatch, *, size=17, delay=0):
    clock(monkeypatch, NOW + timedelta(seconds=delay))
    result = process(engine, settings, bars(size), signal=native_payload())
    assert result.outcome == "PAPER_EXECUTED"
    clock(monkeypatch, NOW + timedelta(days=1))
    return result


def ledger(engine):
    with Session(engine) as session:
        trade = session.scalars(select(PaperTrade)).one()
        position = session.scalars(select(Position)).one()
        order = trade.paper_order
        return {
            "status": trade.status,
            "position_status": position.status,
            "exit": trade.exit_price,
            "reason": trade.close_reason,
            "closed_at": trade.closed_at,
            "pl": trade.realized_pl,
            "fees": trade.fees,
            "slippage": trade.slippage,
            "equity": trade.account.current_equity,
            "fill_model": order.fill_model,
            "snapshot": copy.deepcopy(order.execution_assumptions),
            "snapshot_hash": order.execution_assumptions_hash,
            "equity_points": len(list(session.scalars(select(EquityCurvePoint)))),
        }


@pytest.mark.parametrize("size", [17, 4096])
def test_stale_flat_backlog_advances_without_signals_and_preserves_legacy_evidence(
    engine, settings, monkeypatch, size
):
    first = process(engine, settings, bars(size))
    with Session(engine) as session:
        before = copy.deepcopy(session.get(NativeBarOutcome, first.receipt_id).evidence)
    clock(monkeypatch, NOW + STEP * 4)
    processor = NativeBarProcessor(engine, settings)
    for offset in range(3):
        result = recover(engine, settings, candle(offset))
        assert result.recovery_disposition == "FLAT" and result.outcome == "RECOVERY_NO_ENTRY"
        assert recover(engine, settings, candle(offset)).receipt_id == result.receipt_id
    fresh = processor.process_next(candle(3), scope=spec(), signal=None)
    assert fresh.outcome == "NO_SIGNAL" and fresh.checkpoint.bar_count == size + 4
    assert counts(engine)["signals"] == counts(engine)["paper_orders"] == 0
    with Session(engine) as session:
        chain = validate_chain(session)
        assert chain[0][0].evidence == before
        assert "recovery" not in before
        assert chain[1][1].schema_version == "native_bar_processing_v3"
        assert not chain[1][1].recovery.forward_qualifying


@pytest.mark.parametrize(
    "changes,price,reason",
    [
        ({"low": "94"}, "95", "STOP_LOSS"),
        ({"open": "90", "low": "88", "high": "94", "close": "92"}, "90", "STOP_GAP"),
        ({"high": "114"}, "112", "TAKE_PROFIT"),
        ({"open": "115", "low": "113", "high": "116", "close": "114"}, "112", "TAKE_PROFIT_GAP"),
        ({"low": "94", "high": "114"}, "95", "STOP_AND_TARGET_AMBIGUOUS"),
    ],
)
def test_recovery_costed_bracket_close_and_no_second_exit(
    engine, settings, monkeypatch, qualified_fixture, changes, price, reason
):
    open_trade(engine, settings, monkeypatch)
    bar = candle(**changes)
    result = recover(engine, settings, bar)
    after = ledger(engine)
    assert result.recovery_disposition == "CLOSED"
    assert after["exit"] == Decimal(price) and after["reason"] == reason
    assert after["status"] == TradeStatus.CLOSED
    assert after["position_status"] == PositionStatus.CLOSED
    assert after["equity"] == Decimal("100") + after["pl"]
    assert after["fees"] > 0 and after["slippage"] > 0
    assert after["closed_at"].replace(tzinfo=NOW.tzinfo) == NOW + timedelta(days=1)
    assert after["fill_model"] == RECOVERY_FILL_MODEL
    assert RECOVERY_FILL_MODEL not in EVIDENCE_GRADE_PAPER_FILL_MODELS
    assert recover(engine, settings, bar).is_duplicate
    assert ledger(engine) == after
    with Session(engine) as session:
        trade = session.scalars(select(PaperTrade)).one()
        violation = paper_execution_quality_violation(
            trade=trade,
            order=trade.paper_order,
            signal=trade.paper_order.signal,
            import_violation=None,
        )
        assert violation["reason"] == "non_evidence_grade_fill_model"
        validate_chain(session)


@pytest.mark.parametrize(
    "changes,disposition,reason",
    [
        ({"low": "90", "high": "114"}, "CLOSED", "PARTIAL_ENTRY_STOP_BOUND"),
        ({"high": "114"}, "HELD", None),
        ({"high": "114", "close": "113"}, "CLOSED", "PARTIAL_ENTRY_TARGET_AT_CLOSE"),
    ],
)
def test_partial_entry_candle_does_not_claim_preentry_target_fill(
    engine, settings, monkeypatch, qualified_fixture, changes, disposition, reason
):
    open_trade(engine, settings, monkeypatch, delay=30)
    result = recover(engine, settings, candle(**changes))
    assert result.recovery_disposition == disposition
    assert ledger(engine)["reason"] == reason
    with Session(engine) as session:
        receipt = validate_chain(session)[-1][1]
        assert receipt.recovery.partial_entry_bar
        if reason == "PARTIAL_ENTRY_STOP_BOUND":
            assert receipt.recovery.exit_price == Decimal("90")


def test_held_then_closed_across_restart_uses_frozen_costs_even_with_kill_switch(
    engine, settings, monkeypatch, qualified_fixture
):
    open_trade(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        RiskEngine(session).set_kill_switch(True)
        StrategyPortfolioService(session).get_config("trend_pullback_v1").is_enabled = False
    held = recover(engine, settings)
    assert held.recovery_disposition == "HELD"
    with pytest.raises(NativeBarError, match="requires_exit_only_recovery"):
        NativeBarProcessor(engine, settings).process_next(candle(1), scope=spec(), signal=None)
    changed_settings = settings.model_copy(update={"paper_commission_bps": Decimal("90")})
    result = recover(engine, changed_settings, candle(1, low="94"))
    assert result.recovery_disposition == "CLOSED"
    assert recover(engine, settings).receipt_id == held.receipt_id
    assert ledger(engine)["snapshot"]["assumptions"]["commission_bps"] == "10"
    assert counts(engine)["signals"] == 1


@pytest.mark.parametrize("kind", ["gap", "future", "revised", "mode", "scope", "uninitialized"])
def test_recovery_rejects_invalid_input_without_advancement(engine, settings, monkeypatch, kind):
    if kind != "uninitialized":
        process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    bar = candle()
    scope = spec()
    if kind == "gap":
        bar = candle(1)
        clock(monkeypatch, NOW + STEP * 2)
    elif kind == "future":
        clock(monkeypatch, NOW + STEP - timedelta(seconds=1))
    elif kind == "revised":
        recover(engine, settings)
        bar["volume"] = "2"
    elif kind == "mode":
        bar = bars()[-1]
    elif kind == "scope":
        scope = spec(settings_fingerprint="changed")
    before = counts(engine)
    with pytest.raises(NativeBarError):
        NativeBarProcessor(engine, settings).recover_next(bar, scope=scope)
    assert counts(engine) == before


def test_recovery_cannot_be_reinterpreted_as_fresh_signal(engine, settings, monkeypatch):
    process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    recover(engine, settings)
    with pytest.raises(NativeBarError, match="mode_changed"):
        NativeBarProcessor(engine, settings).process_next(
            candle(), scope=spec(), signal=native_payload(timestamp=NOW + STEP)
        )
    assert counts(engine)["signals"] == 0


@pytest.mark.parametrize("fault", ["before_flush", "before_commit", "after_commit"])
def test_recovery_close_and_receipt_are_one_transaction(
    engine, settings, monkeypatch, qualified_fixture, fault
):
    open_trade(engine, settings, monkeypatch)
    before, before_counts = ledger(engine), counts(engine)

    def fail(session, *_):
        if fault != "before_flush" and session.in_nested_transaction():
            return
        if fault != "before_flush" or any(isinstance(row, NativeBarOutcome) for row in session.new):
            raise RuntimeError("injected recovery fault")

    event.listen(Session, fault, fail)
    try:
        with pytest.raises(RuntimeError, match="recovery fault"):
            recover(engine, settings, candle(low="94"))
    finally:
        event.remove(Session, fault, fail)
    if fault != "after_commit":
        assert ledger(engine) == before and counts(engine) == before_counts
    result = recover(engine, settings, candle(low="94"))
    assert result.is_duplicate == (fault == "after_commit")
    assert result.recovery_disposition == "CLOSED"
    assert counts(engine)["paper_trades"] == 1
    assert ledger(engine)["equity_points"] == 2


def test_concurrent_recovery_workers_close_once(engine, settings, monkeypatch, qualified_fixture):
    open_trade(engine, settings, monkeypatch)
    barrier = Barrier(2)

    def worker(_):
        barrier.wait(timeout=10)
        return recover(engine, settings, candle(low="94"))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert results[0].receipt_id == results[1].receipt_id
    assert sorted(result.is_duplicate for result in results) == [False, True]
    assert ledger(engine)["equity_points"] == 2


@pytest.mark.parametrize(
    "damage",
    [
        "position",
        "quantity",
        "equity",
        "hash",
        "costs",
        "scope",
        "close_fields",
        "latency",
        "null",
    ],
)
def test_unreconciled_position_is_not_guessed_or_closed(
    engine, settings, monkeypatch, qualified_fixture, damage
):
    open_trade(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        trade = session.scalars(select(PaperTrade)).one()
        position = session.scalars(select(Position)).one()
        if damage == "position":
            session.delete(position)
        elif damage == "quantity":
            position.quantity += Decimal("1")
        elif damage == "equity":
            trade.account.current_equity += Decimal("1")
        elif damage == "hash":
            trade.paper_order.execution_assumptions_hash = "0" * 64
        elif damage == "scope":
            trade.strategy = "wrong"
        elif damage == "close_fields":
            trade.realized_pl = Decimal("1")
        else:
            data = copy.deepcopy(trade.paper_order.execution_assumptions)
            if damage == "latency":
                data["assumptions"]["latency_ms"] = True
            elif damage == "null":
                data = None
            else:
                del data["assumptions"]["commission_bps"]
            trade.paper_order.execution_assumptions = data
            trade.paper_order.execution_assumptions_hash = content_hash(data)
    before = counts(engine)
    with pytest.raises(NativeBarError):
        recover(engine, settings, candle(low="94"))
    assert counts(engine) == before
    with Session(engine) as session:
        assert session.scalars(select(PaperTrade)).one().status == TradeStatus.OPEN


@pytest.mark.parametrize("damage", ["flat", "price", "fees", "timestamp", "pl"])
def test_rehashed_recovery_receipt_or_ledger_corruption_blocks_retry(
    engine, settings, monkeypatch, qualified_fixture, damage
):
    open_trade(engine, settings, monkeypatch)
    result = recover(engine, settings, candle(low="94"))
    with Session(engine) as session, session.begin():
        row = session.get(NativeBarOutcome, result.receipt_id)
        data = copy.deepcopy(row.evidence)
        if damage == "flat":
            from aurex.signal_gateway.native_recovery import NativeRecoveryEvidence

            data["recovery"] = NativeRecoveryEvidence(disposition="FLAT").model_dump(mode="json")
        elif damage == "price":
            data["recovery"]["exit_price"] = "96"
        elif damage == "fees":
            data["recovery"]["total_fees"] = "0"
        elif damage == "timestamp":
            data["recovery"]["recognized_at"] = NOW.isoformat()
        else:
            session.scalars(select(PaperTrade)).one().realized_pl = Decimal("1")
        row.evidence, row.evidence_hash = data, content_hash(data)
    with pytest.raises(NativeBarError):
        recover(engine, settings, candle(low="94"))


def test_fresh_process_recovers_held_position_and_retries_close(
    engine, settings, monkeypatch, qualified_fixture
):
    open_trade(engine, settings, monkeypatch)
    recover(engine, settings)
    script = """
import sys
from datetime import timedelta
from sqlalchemy import create_engine
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, STEP, bars
native.utc_now = lambda: NOW + timedelta(days=1)
engine = create_engine(sys.argv[1])
p = native.NativeBarProcessor(engine, Settings(
    _env_file=None, live_trading_enabled=False, live_execution_adapter='disabled'))
bar = {**bars()[-1], 'timestamp': NOW + STEP, 'low': '94'}
result = p.recover_next(bar, scope=spec())
assert result.recovery_disposition == 'CLOSED' and not result.is_duplicate
assert p.recover_next(bar, scope=spec()).is_duplicate
engine.dispose()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(engine.url)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert ledger(engine)["status"] == TradeStatus.CLOSED


@pytest.mark.parametrize("side_effect", ["manual_close", "equity", "reclassify"])
def test_retry_refuses_unrecorded_changes_after_held_recovery(
    engine, settings, monkeypatch, qualified_fixture, side_effect
):
    open_trade(engine, settings, monkeypatch)
    recover(engine, settings)
    with Session(engine) as session, session.begin():
        trade = session.scalars(select(PaperTrade)).one()
        if side_effect == "manual_close":
            PaperExecutionEngine(session, settings).close_trade(
                trade.id, Decimal("100"), "manual fixture close", now=NOW + timedelta(days=1)
            )
        elif side_effect == "equity":
            trade.account.current_equity += Decimal("1")
        else:
            from aurex.execution_engine.paper import DETERMINISTIC_PAPER_FILL_MODEL

            trade.paper_order.fill_model = DETERMINISTIC_PAPER_FILL_MODEL
            data = {
                **trade.paper_order.execution_assumptions,
                "fill_model": DETERMINISTIC_PAPER_FILL_MODEL,
            }
            trade.paper_order.execution_assumptions = data
            trade.paper_order.execution_assumptions_hash = content_hash(data)
    with pytest.raises(NativeBarError):
        recover(engine, settings)


@pytest.mark.parametrize(
    "live_config",
    [
        {"live_trading_enabled": True},
        {"live_execution_adapter": "binance_spot"},
    ],
)
def test_recovery_has_no_live_authority(engine, settings, monkeypatch, live_config):
    process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    with pytest.raises(ValueError, match="live execution"):
        recover(engine, settings.model_copy(update=live_config))
    assert counts(engine)["native_bar_outcomes"] == 1


def test_recovery_helper_requires_real_sqlite_transaction(engine, settings):
    from aurex.signal_gateway.native_bars import ClosedBar
    from aurex.signal_gateway.native_recovery import manage_recovery

    with Session(engine) as session:
        with pytest.raises(NativeBarError, match="database_transaction"):
            manage_recovery(
                session,
                settings,
                spec().model_dump(mode="json"),
                ClosedBar.model_validate(candle()),
                NOW + STEP,
            )
        with session.begin():
            with pytest.raises(NativeBarError, match="database_transaction"):
                manage_recovery(
                    session,
                    settings,
                    spec().model_dump(mode="json"),
                    ClosedBar.model_validate(candle()),
                    NOW + STEP,
                )


@pytest.mark.parametrize("phase,expected_receipts", [("before_commit", 1), ("after_commit", 2)])
def test_process_death_preserves_atomic_recovery_state(
    engine, settings, monkeypatch, qualified_fixture, phase, expected_receipts
):
    open_trade(engine, settings, monkeypatch)
    script = """
import os, sys
from datetime import timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, bars
native.utc_now = lambda: NOW + timedelta(days=1)
engine = create_engine(sys.argv[1])
def die(session):
    if not session.in_nested_transaction():
        os._exit(73)
event.listen(Session, sys.argv[2], die)
p = native.NativeBarProcessor(engine, Settings(
    _env_file=None, live_trading_enabled=False, live_execution_adapter='disabled'))
p.recover_next({**bars()[-1], 'timestamp': NOW, 'low': '94'}, scope=spec())
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), phase],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 73, completed.stderr
    assert counts(engine)["native_bar_outcomes"] == expected_receipts
    result = recover(engine, settings, candle(low="94"))
    assert result.is_duplicate == (phase == "after_commit")
    assert ledger(engine)["equity_points"] == 2


def test_open_position_cannot_be_skipped_by_normal_processing(
    engine, settings, monkeypatch, qualified_fixture
):
    open_trade(engine, settings, monkeypatch)
    clock(monkeypatch, NOW + STEP)
    with pytest.raises(NativeBarError, match="requires_exit_only_recovery"):
        NativeBarProcessor(engine, settings).process_next(candle(), scope=spec(), signal=None)
    assert counts(engine)["native_bar_outcomes"] == 1


def test_recovery_after_v2_entry_crosses_pages_without_changing_entry_receipt(
    engine, settings, monkeypatch, qualified_fixture
):
    process(engine, settings, bars(4096))
    clock(monkeypatch, NOW + STEP)
    first = NativeBarProcessor(engine, settings).process_next(
        candle(), scope=spec(), signal=native_payload(timestamp=NOW + STEP)
    )
    assert first.outcome == "PAPER_EXECUTED"
    with Session(engine) as session:
        original = copy.deepcopy(session.get(NativeBarOutcome, first.receipt_id).evidence)
        assert original["schema_version"] == "native_bar_processing_v2"
        assert "recovery" not in original
    monkeypatch.setattr("aurex.signal_gateway.native_processing.CHAIN_PAGE_SIZE", 2)
    clock(monkeypatch, NOW + timedelta(days=1))
    for offset in range(1, 5):
        assert recover(engine, settings, candle(offset)).recovery_disposition == "HELD"
    result = recover(engine, settings, candle(5, low="94"))
    assert result.recovery_disposition == "CLOSED"
    assert result.checkpoint.bar_count == 4102
    assert recover(engine, settings, candle(2)).is_duplicate
    with Session(engine) as session:
        chain = validate_chain(session)
        assert chain[1][0].evidence == original
        assert chain[1][0].evidence_hash == first.evidence_hash
    assert counts(engine)["paper_orders"] == 1


def test_recovered_loss_counts_against_same_day_native_risk(
    engine, settings, monkeypatch, qualified_fixture
):
    open_trade(engine, settings, monkeypatch)
    # An adverse opening gap can exceed the modeled stop-risk admission limit.
    recover(engine, settings, candle(open="1", low="1", high="2", close="1"))
    assert ledger(engine)["pl"] < Decimal("-1")
    from aurex.domain.enums import SignalStatus
    from aurex.signal_gateway.service import SignalIntakeService

    recognized = NOW + timedelta(days=1)
    clock(monkeypatch, recognized + STEP * 2)
    with Session(engine) as session:
        trade = session.scalars(select(PaperTrade)).one()
        assert trade.closed_at.replace(tzinfo=NOW.tzinfo).date() == recognized.date()
        result = SignalIntakeService(session, settings).ingest_native(
            native_payload(timestamp=recognized + STEP * 2)
        )
        assert result.signal.status == SignalStatus.RISK_REJECTED
        assert "loss" in result.signal.rejection_reason.lower()
    assert counts(engine)["paper_orders"] == 1


def test_unrecorded_manual_close_requires_reconciliation_before_flat_recovery(
    engine, settings, monkeypatch, qualified_fixture
):
    open_trade(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        trade = session.scalars(select(PaperTrade)).one()
        PaperExecutionEngine(session, settings).close_trade(
            trade.id, Decimal("100"), "untracked fixture close", now=NOW + timedelta(days=1)
        )
    with pytest.raises(NativeBarError, match="entry_chain_mismatch"):
        recover(engine, settings)
    assert counts(engine)["native_bar_outcomes"] == 1
