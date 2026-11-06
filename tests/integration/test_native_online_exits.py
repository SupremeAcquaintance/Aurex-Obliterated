"""Mocked public acquisition and disposable paper ledgers, not forward qualification."""

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

from aurex.db.models import NativeBarOutcome, PaperOrder, PaperTrade, Position
from aurex.domain.enums import TradeStatus
from aurex.execution_engine.paper import (
    EVIDENCE_GRADE_PAPER_FILL_MODELS,
    PaperExecutionEngine,
    paper_execution_evidence_hash,
)
from aurex.live_deployment.service import paper_execution_quality_violation
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_market_data import PublicDataError
from aurex.signal_gateway.native_observation import NativePublicObserver
from aurex.signal_gateway.native_processing import NativeBarProcessor
from aurex.signal_gateway.native_recovery import ONLINE_EXIT_FILL_MODEL, RECOVERY_FILL_MODEL
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.test_native_bar_processing import counts, process
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_observation import acquisition, chain, scope, seed, set_clock
from tests.integration.test_native_recovery import candle, ledger
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP, bars


def open_fixture(engine, settings, monkeypatch, *, delay=0, count=17):
    set_clock(monkeypatch, NOW + timedelta(seconds=delay))
    result = process(engine, settings, bars(count), scope=scope(), signal=native_payload())
    assert result.outcome == "PAPER_EXECUTED"
    return result


def source(monkeypatch, *, offset=0, seconds=5, **changes):
    return acquisition(
        monkeypatch,
        [candle(offset, **changes)],
        NOW + STEP * (offset + 1) + timedelta(seconds=seconds),
    )


def manage(engine, settings):
    return NativePublicObserver(engine, settings).manage_exits(scope=scope())


def retry_receipt(engine, settings):
    receipt = chain(engine)[-1][1]
    return NativeBarProcessor(engine, settings)._process(
        None,
        next_bar=receipt.bar,
        scope=scope(),
        signal=None,
        public_source=receipt.public_source,
        public_observation=receipt.public_observation,
        online_exit=True,
    )


def test_management_cannot_seed_or_accept_an_import(engine, settings, monkeypatch):
    state = source(monkeypatch)
    with pytest.raises(NativeBarError, match="requires_initialized_stream"):
        manage(engine, settings)
    assert state.calls == [] and not any(counts(engine).values())
    with pytest.raises(TypeError):
        NativePublicObserver(engine, settings).manage_exits(scope=scope(), evidence=state.evidence)


def test_flat_step_records_source_admission_and_no_orders(engine, settings, monkeypatch):
    _, first = seed(engine, settings, monkeypatch)
    state = source(monkeypatch)
    result = manage(engine, settings)
    assert result.status == "EXITS_MANAGED_NO_ENTRY"
    assert result.processing.outcome == "ONLINE_EXIT_NO_ENTRY"
    assert result.processing.online_exit_disposition == "FLAT"
    receipt = chain(engine)[-1][1]
    assert receipt.schema_version == "native_bar_processing_v6"
    assert (
        receipt.public_observation.expected_previous_evidence_hash == first.processing.evidence_hash
    )
    assert receipt.public_source.acquisition == state.evidence
    assert receipt.online_exit.source_acquisition_sha256 == receipt.public_source.acquisition_sha256
    assert receipt.online_exit.fill_model == ONLINE_EXIT_FILL_MODEL
    assert not receipt.online_exit.forward_qualifying and not receipt.online_exit.entry_authority
    assert not receipt.source_origin_verified and receipt.recovery is None
    assert counts(engine)["paper_orders"] == counts(engine)["signals"] == 0


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
def test_costed_online_close_is_atomic_idempotent_and_nonqualifying(
    engine, settings, monkeypatch, qualified_fixture, changes, price, reason
):
    first = open_fixture(engine, settings, monkeypatch)
    with Session(engine) as session:
        original_entry = copy.deepcopy(session.get(NativeBarOutcome, first.receipt_id).evidence)
    state = source(monkeypatch, **changes)
    result = manage(engine, settings)
    after = ledger(engine)
    assert result.processing.online_exit_disposition == "CLOSED"
    assert after["exit"] == Decimal(price) and after["reason"] == reason
    assert after["status"] == TradeStatus.CLOSED
    assert after["equity"] == Decimal("100") + after["pl"]
    assert after["fees"] > 0 and after["slippage"] > 0
    assert after["closed_at"].replace(tzinfo=NOW.tzinfo) == NOW + STEP + timedelta(seconds=5)
    assert after["fill_model"] == ONLINE_EXIT_FILL_MODEL
    assert ONLINE_EXIT_FILL_MODEL not in EVIDENCE_GRADE_PAPER_FILL_MODELS
    assert retry_receipt(engine, settings).is_duplicate
    assert manage(engine, settings).status == "WAITING_FOR_CLOSE"
    assert len(state.calls) == 1 and ledger(engine) == after
    with Session(engine) as session:
        trade = session.scalars(select(PaperTrade)).one()
        violation = paper_execution_quality_violation(
            trade=trade,
            order=trade.paper_order,
            signal=trade.paper_order.signal,
            import_violation=None,
        )
        assert violation["reason"] == "non_evidence_grade_fill_model"
        assert session.get(NativeBarOutcome, first.receipt_id).evidence == original_entry
    assert chain(engine)[-1][1].online_exit.position.entry_receipt_hash == first.evidence_hash


@pytest.mark.parametrize(
    "changes,disposition,reason",
    [
        ({"low": "90", "high": "114"}, "CLOSED", "PARTIAL_ENTRY_STOP_BOUND"),
        ({"high": "114"}, "HELD", None),
        ({"high": "114", "close": "113"}, "CLOSED", "PARTIAL_ENTRY_TARGET_AT_CLOSE"),
    ],
)
def test_partial_entry_does_not_invent_preentry_target_fills(
    engine, settings, monkeypatch, qualified_fixture, changes, disposition, reason
):
    open_fixture(engine, settings, monkeypatch, delay=30)
    source(monkeypatch, **changes)
    result = manage(engine, settings)
    assert result.processing.online_exit_disposition == disposition
    assert ledger(engine)["reason"] == reason
    evidence = chain(engine)[-1][1].online_exit
    assert evidence.partial_entry_bar
    if reason == "PARTIAL_ENTRY_STOP_BOUND":
        assert evidence.exit_price == Decimal("90")


def test_held_then_closed_uses_frozen_costs_with_entry_locks_enabled(
    engine, settings, monkeypatch, qualified_fixture
):
    open_fixture(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        RiskEngine(session).set_kill_switch(True)
        StrategyPortfolioService(session).get_config("trend_pullback_v1").is_enabled = False
    source(monkeypatch)
    assert manage(engine, settings).processing.online_exit_disposition == "HELD"
    frozen = ledger(engine)["snapshot"]["assumptions"]
    assert ledger(engine)["fill_model"] == ONLINE_EXIT_FILL_MODEL
    source(monkeypatch, offset=1, low="94")
    changed = settings.model_copy(update={"paper_commission_bps": Decimal("1000")})
    assert manage(engine, changed).processing.online_exit_disposition == "CLOSED"
    assert ledger(engine)["snapshot"]["assumptions"] == frozen
    assert len(chain(engine)) == 3 and counts(engine)["paper_orders"] == 1


@pytest.mark.parametrize("order", ["online_then_recovery", "recovery_then_online"])
def test_recovery_quarantine_cannot_be_upgraded_by_later_online_management(
    engine, settings, monkeypatch, qualified_fixture, order
):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch)
    processor = NativeBarProcessor(engine, settings)
    if order == "online_then_recovery":
        manage(engine, settings)
        state = source(monkeypatch, offset=1, low="94")
        processor.process_sourced(state.evidence, scope=scope(), purpose="RECOVERY")
    else:
        processor.process_sourced(state.evidence, scope=scope(), purpose="RECOVERY")
        source(monkeypatch, offset=1)
        assert manage(engine, settings).processing.online_exit_disposition == "HELD"
        source(monkeypatch, offset=2, low="94")
        manage(engine, settings)
        assert chain(engine)[-1][1].online_exit.fill_model == RECOVERY_FILL_MODEL
    assert ledger(engine)["fill_model"] == RECOVERY_FILL_MODEL
    assert len(chain(engine)) >= 3


@pytest.mark.parametrize("kind", ["stale", "future", "gap", "transport", "injected"])
def test_invalid_acquisition_never_changes_the_open_position(
    engine, settings, monkeypatch, qualified_fixture, kind
):
    open_fixture(engine, settings, monkeypatch)
    before = ledger(engine)
    state = source(monkeypatch, low="94", seconds=181 if kind == "stale" else 5)
    if kind == "future":
        set_clock(monkeypatch, NOW + STEP + timedelta(seconds=4))
    elif kind == "gap":
        state = source(monkeypatch, offset=1, low="94")
    elif kind == "transport":

        def fail():
            raise PublicDataError("public_transport_failed")

        state.effect = fail
    elif kind == "injected":
        state.evidence = state.evidence.model_copy(update={"transport": "injected"})
    with pytest.raises(ValueError):
        manage(engine, settings)
    assert ledger(engine) == before and counts(engine)["native_bar_outcomes"] == 1


@pytest.mark.parametrize("event_name", ["before_flush", "before_commit"])
def test_failed_commit_rolls_back_close_equity_and_receipt(
    engine, settings, monkeypatch, qualified_fixture, event_name
):
    open_fixture(engine, settings, monkeypatch)
    before = ledger(engine)
    source(monkeypatch, low="94")

    def fail(*args):
        raise RuntimeError("fixture write failure")

    event.listen(Session, event_name, fail)
    try:
        with pytest.raises(RuntimeError, match="fixture write failure"):
            manage(engine, settings)
    finally:
        event.remove(Session, event_name, fail)
    assert ledger(engine) == before and counts(engine)["native_bar_outcomes"] == 1


def test_lost_ack_does_not_double_book_a_close(engine, settings, monkeypatch, qualified_fixture):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch, low="94")

    def lost_ack(*args):
        raise RuntimeError("fixture lost acknowledgement")

    event.listen(Session, "after_commit", lost_ack)
    try:
        with pytest.raises(RuntimeError, match="fixture lost acknowledgement"):
            manage(engine, settings)
    finally:
        event.remove(Session, "after_commit", lost_ack)
    after = ledger(engine)
    assert after["status"] == TradeStatus.CLOSED
    assert manage(engine, settings).status == "WAITING_FOR_CLOSE"
    assert len(state.calls) == 1 and ledger(engine) == after
    assert len(chain(engine)) == 2


def test_two_workers_cannot_double_close(engine, settings, monkeypatch, qualified_fixture):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch, low="94")
    barrier = Barrier(2)
    state.effect = lambda: barrier.wait(timeout=15)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: manage(engine, settings), range(2)))
    assert len({item.processing.receipt_id for item in results}) == 1
    assert sorted(item.processing.is_duplicate for item in results) == [False, True]
    assert counts(engine)["native_bar_outcomes"] == 2
    assert ledger(engine)["equity_points"] == 2


@pytest.mark.parametrize(
    "kind",
    ["missing", "source_hash", "admission", "outcome", "price", "pnl", "authority", "legacy"],
)
def test_rehashed_exit_corruption_rejects(engine, settings, monkeypatch, qualified_fixture, kind):
    open_fixture(engine, settings, monkeypatch)
    source(monkeypatch, low="94")
    manage(engine, settings)
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome).where(NativeBarOutcome.sequence == 2))
        data = copy.deepcopy(row.evidence)
        if kind == "missing":
            del data["online_exit"]
        elif kind == "source_hash":
            data["online_exit"]["source_acquisition_sha256"] = "a" * 64
        elif kind == "admission":
            del data["public_observation"]
        elif kind == "outcome":
            data["outcome"] = row.outcome = "SOURCE_OBSERVED_NO_ENTRY"
        elif kind == "price":
            data["online_exit"]["exit_price"] = "96"
        elif kind == "pnl":
            data["online_exit"]["realized_pl"] = "100"
        elif kind == "authority":
            data["online_exit"]["forward_qualifying"] = True
        else:
            data["schema_version"] = "native_bar_processing_v5"
        row.evidence, row.evidence_hash = data, content_hash(data)
    with pytest.raises(ValueError):
        chain(engine)


@pytest.mark.parametrize("kind", ["quantity", "cost", "equity", "orphan_position", "manual_close"])
def test_unreconciled_ledger_is_not_repaired_by_management(
    engine, settings, monkeypatch, qualified_fixture, kind
):
    open_fixture(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        trade = session.scalars(select(PaperTrade)).one()
        position = session.scalars(select(Position)).one()
        if kind == "quantity":
            position.quantity += Decimal("0.01")
        elif kind == "cost":
            trade.paper_order.fees += Decimal("1")
        elif kind == "equity":
            trade.account.current_equity += Decimal("1")
        elif kind == "orphan_position":
            session.delete(position)
        else:
            PaperExecutionEngine(session, settings).close_trade(
                trade.id, Decimal("100"), "untracked", now=NOW + timedelta(seconds=30)
            )
    source(monkeypatch, low="94")
    with pytest.raises(ValueError):
        manage(engine, settings)
    assert counts(engine)["native_bar_outcomes"] == 1


def test_unrecorded_held_model_change_rejects(engine, settings, monkeypatch, qualified_fixture):
    open_fixture(engine, settings, monkeypatch)
    source(monkeypatch)
    manage(engine, settings)
    with Session(engine) as session, session.begin():
        order = session.scalars(select(PaperOrder)).one()
        order.fill_model = RECOVERY_FILL_MODEL
        order.execution_assumptions = {
            **order.execution_assumptions,
            "fill_model": RECOVERY_FILL_MODEL,
        }
        order.execution_assumptions_hash = paper_execution_evidence_hash(
            order.execution_assumptions
        )
    with pytest.raises(NativeBarError, match="held_position_changed_without_receipt"):
        chain(engine)


def test_no_entry_argument_or_imported_retry(engine, settings, monkeypatch, qualified_fixture):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch, low="94")
    with pytest.raises(TypeError):
        NativePublicObserver(engine, settings).manage_exits(scope=scope(), signal=native_payload())
    manage(engine, settings)
    with pytest.raises(NativeBarError, match="processed_bar_mode_changed"):
        NativeBarProcessor(engine, settings).process_sourced(
            state.evidence, scope=scope(), purpose="CLOSED_BAR"
        )
    receipt = chain(engine)[-1][1]
    with pytest.raises(NativeBarError, match="without_entry"):
        NativeBarProcessor(engine, settings)._process(
            None,
            next_bar=receipt.bar,
            scope=scope(),
            signal=native_payload(),
            public_source=receipt.public_source,
            public_observation=receipt.public_observation,
            online_exit=True,
        )


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_process_death_and_restart_keep_close_and_receipt_atomic(
    engine, settings, monkeypatch, qualified_fixture, phase
):
    open_fixture(engine, settings, monkeypatch)
    script = """
import os, sys
from datetime import timedelta
from types import SimpleNamespace
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from aurex.config.settings import Settings
import aurex.signal_gateway.native_observation as observation
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_source_binding import packet
from tests.integration.test_native_observation import scope
from tests.integration.test_native_recovery import candle
from tests.unit.test_native_closed_bars import NOW, STEP
observation.utc_now = native.utc_now = lambda: NOW + STEP + timedelta(seconds=5)
evidence = packet([candle(low='94')]).model_copy(update={'transport': 'public_https'})
observation.PublicCandleClient = lambda: SimpleNamespace(acquire=lambda **_: evidence)
engine = create_engine(sys.argv[1])
event.listen(Session, sys.argv[2], lambda *args: os._exit(73))
observation.NativePublicObserver(engine, Settings(_env_file=None,
    live_trading_enabled=False, live_execution_adapter='disabled')).manage_exits(scope=scope())
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), phase],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 73, result.stderr
    committed = phase == "after_commit"
    assert counts(engine)["native_bar_outcomes"] == 1 + committed
    assert (ledger(engine)["status"] == TradeStatus.CLOSED) == committed
    source(monkeypatch, low="94")
    result = manage(engine, settings)
    assert result.status == ("WAITING_FOR_CLOSE" if committed else "EXITS_MANAGED_NO_ENTRY")
    assert counts(engine)["native_bar_outcomes"] == 2
    assert ledger(engine)["status"] == TradeStatus.CLOSED
    chain(engine)


def test_online_exit_continues_past_4096(engine, settings, monkeypatch, qualified_fixture):
    open_fixture(engine, settings, monkeypatch, count=4096)
    source(monkeypatch, low="94")
    result = manage(engine, settings)
    assert result.processing.checkpoint.bar_count == 4097
    assert chain(engine)[-1][1].continuation.bar_count == 4097
    assert counts(engine)["native_history_seeds"] == 1


@pytest.mark.parametrize("kind", ["live_toggle", "late_receipt", "clock_regression"])
def test_runtime_authority_and_final_freshness_failure_roll_back_exit(
    engine, settings, monkeypatch, qualified_fixture, kind
):
    open_fixture(engine, settings, monkeypatch)
    before = ledger(engine)
    state = source(monkeypatch, low="94")
    if kind == "live_toggle":
        state.effect = lambda: setattr(settings, "live_trading_enabled", True)
    else:
        moments = iter(
            [NOW + STEP + timedelta(seconds=5)] * 2
            + [NOW + STEP + timedelta(seconds=181 if kind == "late_receipt" else 4)]
        )
        monkeypatch.setattr("aurex.signal_gateway.native_processing.utc_now", lambda: next(moments))
    with pytest.raises(ValueError):
        manage(engine, settings)
    assert ledger(engine) == before and counts(engine)["native_bar_outcomes"] == 1


def test_observation_and_management_cannot_reinterpret_the_same_candle(
    engine, settings, monkeypatch
):
    seed(engine, settings, monkeypatch)
    state = source(monkeypatch)
    observed = NativePublicObserver(engine, settings).observe(scope=scope())
    receipt = chain(engine)[-1][1]
    with pytest.raises(NativeBarError, match="processed_bar_mode_changed"):
        NativeBarProcessor(engine, settings)._process(
            None,
            next_bar=receipt.bar,
            scope=scope(),
            signal=None,
            public_source=receipt.public_source,
            public_observation=receipt.public_observation,
            online_exit=True,
        )
    assert chain(engine)[-1][0] == observed.processing.evidence_hash
    assert len(state.calls) == 1


def test_recovery_marker_cannot_be_removed_from_online_receipt(
    engine, settings, monkeypatch, qualified_fixture
):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch)
    NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="RECOVERY"
    )
    source(monkeypatch, offset=1)
    manage(engine, settings)
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome).where(NativeBarOutcome.sequence == 3))
        data = copy.deepcopy(row.evidence)
        data["online_exit"]["fill_model"] = ONLINE_EXIT_FILL_MODEL
        opening = data["online_exit"]["position"]["opening_assumptions"]
        data["online_exit"]["execution_hash_after"] = paper_execution_evidence_hash(
            {**opening, "fill_model": ONLINE_EXIT_FILL_MODEL}
        )
        row.evidence, row.evidence_hash = data, content_hash(data)
    with pytest.raises(NativeBarError, match="online_exit_fill_model_transition_invalid"):
        chain(engine)


def test_acquisition_head_race_cannot_reclassify_a_recovery_close(
    engine, settings, monkeypatch, qualified_fixture
):
    open_fixture(engine, settings, monkeypatch)
    state = source(monkeypatch, low="94")
    state.effect = lambda: NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="RECOVERY"
    )
    with pytest.raises(NativeBarError, match="processed_bar_mode_changed"):
        manage(engine, settings)
    assert ledger(engine)["fill_model"] == RECOVERY_FILL_MODEL
    assert counts(engine)["native_bar_outcomes"] == 2
    assert chain(engine)[-1][1].online_exit is None


def test_unmanaged_history_blocks_exit_without_inventing_missing_interval(
    engine, settings, monkeypatch, qualified_fixture
):
    open_fixture(engine, settings, monkeypatch)
    source(monkeypatch)
    manage(engine, settings)
    # Convert the held step into a validly hashed observation-only receipt, as an
    # attempted omission of its management evidence. The ledger stays untouched.
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome).where(NativeBarOutcome.sequence == 2))
        data = copy.deepcopy(row.evidence)
        del data["online_exit"]
        data["schema_version"] = "native_bar_processing_v5"
        data["outcome"] = row.outcome = "SOURCE_OBSERVED_NO_ENTRY"
        row.evidence, row.evidence_hash = data, content_hash(data)
    before = ledger(engine)
    source(monkeypatch, offset=1, low="94")
    with pytest.raises(NativeBarError, match="recovery_entry_chain_mismatch"):
        manage(engine, settings)
    assert ledger(engine) == before and counts(engine)["native_bar_outcomes"] == 2
