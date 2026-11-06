"""Synthetic disposable ledgers only; no market acquisition or operator DB access."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from sqlalchemy import create_engine, create_mock_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from aurex.db.base import Base
from aurex.db.models import (
    NativeBarOutcome,
    NativeHistorySeed,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
    Signal,
    SignalEvent,
)
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.native_bars import NativeBarError
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    NativeBarReceipt,
    NativeStreamSpec,
    validate_chain,
)
from aurex.signal_gateway.service import SignalIntakeService
from aurex.strategy_engine.service import StrategyPortfolioService
from tests.integration.backtest_helpers import seed_accepted_backtest
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import SMALL, STEP, bars


def spec(**changes):
    payload = native_payload()
    values = {
        "feed_id": "fixture",
        "strategy": payload.strategy,
        "strategy_version": payload.strategy_version,
        "settings_fingerprint": payload.settings_fingerprint,
        "parameters": SMALL,
    }
    values.update(changes)
    return NativeStreamSpec.model_validate(values)


def clock(monkeypatch, now):
    monkeypatch.setattr("aurex.signal_gateway.service.utc_now", lambda: now)
    monkeypatch.setattr("aurex.signal_gateway.native_processing.utc_now", lambda: now)


@pytest.fixture(scope="module")
def template_database(tmp_path_factory):
    path = tmp_path_factory.mktemp("native-schema") / "template.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        account, profile = RiskEngine(session).get_or_create_default_profile()
        account.starting_equity = account.current_equity = Decimal("100")
        profile.max_open_positions = 1
    engine.dispose()
    return path


@pytest.fixture()
def engine(tmp_path, monkeypatch, template_database):
    clock(monkeypatch, NOW)
    path = tmp_path / "native.db"
    # Clone only the empty fixture schema/profile; each test still uses its own real file.
    with closing(sqlite3.connect(template_database.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(path)) as target:
            source.backup(target)
    engine = create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def qualified_fixture(engine, active_trend_pipeline):
    with Session(engine) as session, session.begin():
        StrategyPortfolioService(session).get_config("trend_pullback_v1").is_enabled = True
        seed_accepted_backtest(session)


def process(engine, settings, history=None, *, signal=None, scope=None):
    return NativeBarProcessor(engine, settings).process(
        bars() if history is None else history,
        scope=spec() if scope is None else scope,
        signal=signal,
    )


def counts(engine):
    with Session(engine) as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                NativeBarOutcome,
                NativeHistorySeed,
                Signal,
                SignalEvent,
                RiskDecision,
                PaperOrder,
                PaperTrade,
                Position,
            )
        }


def next_history():
    history = bars()
    return history + [{**history[-1], "timestamp": NOW}]


def test_no_signal_is_a_durable_outcome_and_restart_retry_is_a_noop(engine, settings, monkeypatch):
    first = process(engine, settings)
    assert first.outcome == "NO_SIGNAL" and first.signal_id is None
    assert not first.is_duplicate
    clock(monkeypatch, NOW + timedelta(days=1))
    retry = process(engine, settings)
    assert retry.is_duplicate and retry.receipt_id == first.receipt_id
    assert retry.evidence_hash == first.evidence_hash
    assert counts(engine)["native_bar_outcomes"] == 1
    assert counts(engine)["signals"] == 0
    with Session(engine) as session:
        chain = validate_chain(session)
        assert chain[0][1].checkpoint == first.checkpoint
        assert chain[0][1].source_origin_verified is False


def test_rejected_strategy_outcome_and_cursor_commit_together(engine, settings):
    first = process(engine, settings, signal=native_payload())
    assert first.outcome == "RISK_REJECTED"
    assert process(engine, settings, signal=native_payload()).is_duplicate
    assert counts(engine)["native_bar_outcomes"] == 1
    assert counts(engine)["signals"] == 1
    assert counts(engine)["paper_orders"] == 0


def test_paper_effects_and_receipt_commit_together(engine, settings, qualified_fixture):
    first = process(engine, settings, signal=native_payload())
    assert first.outcome == "PAPER_EXECUTED"
    assert process(engine, settings, signal=native_payload()).signal_id == first.signal_id
    assert counts(engine)["signals"] == 1
    assert counts(engine)["paper_orders"] == 1
    assert counts(engine)["paper_trades"] == 1
    with Session(engine) as session:
        assert len(validate_chain(session)) == 1


def test_new_bar_advances_once_and_an_older_retry_never_moves_the_head(
    engine, settings, monkeypatch
):
    first = process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    second = process(engine, settings, next_history())
    assert second.checkpoint.bar_count == first.checkpoint.bar_count + 1
    assert process(engine, settings).receipt_id == first.receipt_id
    assert process(engine, settings, next_history()).receipt_id == second.receipt_id
    with Session(engine) as session:
        chain = validate_chain(session)
        assert len(chain) == 2
        assert chain[-1][1].previous_evidence_hash == first.evidence_hash


@pytest.mark.parametrize("first_signal, retry_signal", [(False, True), (True, False), (True, True)])
def test_changed_decision_on_a_processed_bar_is_rejected(
    engine, settings, first_signal, retry_signal
):
    process(engine, settings, signal=native_payload() if first_signal else None)
    before = counts(engine)
    retry = native_payload(take_profit="113") if retry_signal else None
    with pytest.raises(NativeBarError, match="request_changed"):
        process(engine, settings, signal=retry)
    assert counts(engine) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"feed_id": "binance_spot_public"},
        {"strategy_version": "different"},
        {"settings_fingerprint": "different"},
        {"parameters": SMALL.model_copy(update={"ema_fast": 3})},
    ],
)
def test_scope_cannot_be_changed_on_restart(engine, settings, changes):
    process(engine, settings)
    with pytest.raises(NativeBarError, match="scope_changed"):
        process(engine, settings, scope=spec(**changes))
    assert counts(engine)["native_bar_outcomes"] == 1


def test_signal_provenance_and_bar_binding_mismatch_leave_no_receipt(engine, settings):
    for payload in (native_payload(strategy_version="wrong"), native_payload(entry_price="101")):
        with pytest.raises(NativeBarError):
            process(engine, settings, signal=payload)
    assert all(count == 0 for count in counts(engine).values())


@pytest.mark.parametrize("bad_input", ["changed", "gap", "stale", "future", "clock_back"])
def test_bad_next_input_never_advances_a_committed_checkpoint(
    engine, settings, monkeypatch, bad_input
):
    first = process(engine, settings)
    history = next_history()
    now = NOW + STEP
    if bad_input == "changed":
        history[1] = {**history[1], "volume": "2"}
    elif bad_input == "gap":
        history.append({**history[-1], "timestamp": NOW + STEP})
        now += STEP
    elif bad_input == "stale":
        now += timedelta(seconds=181)
    elif bad_input == "future":
        now -= timedelta(seconds=1)
    else:
        now = NOW - timedelta(seconds=1)
    clock(monkeypatch, now)
    with pytest.raises(NativeBarError):
        process(engine, settings, history)
    with Session(engine) as session:
        assert validate_chain(session)[-1][0].evidence_hash == first.evidence_hash


@pytest.mark.parametrize("fault", ["receipt_flush", "outer_commit"])
def test_failure_rolls_back_paper_signal_and_checkpoint(engine, settings, qualified_fixture, fault):
    before = counts(engine)

    def fail_flush(session, *_):
        if any(isinstance(row, NativeBarOutcome) for row in session.new):
            raise RuntimeError("injected receipt flush failure")

    def fail_commit(session):
        if not session.in_nested_transaction():
            raise RuntimeError("injected outer commit failure")

    event_name, callback = (
        ("before_flush", fail_flush) if fault == "receipt_flush" else ("before_commit", fail_commit)
    )
    event.listen(Session, event_name, callback)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            process(engine, settings, signal=native_payload())
    finally:
        event.remove(Session, event_name, callback)
    assert counts(engine) == before
    assert process(engine, settings, signal=native_payload()).outcome == "PAPER_EXECUTED"


def test_lost_ack_after_commit_replays_receipt_without_second_order(
    engine, settings, qualified_fixture
):
    def lose_ack(session):
        if not session.in_nested_transaction():
            raise RuntimeError("injected acknowledgement loss")

    event.listen(Session, "after_commit", lose_ack)
    try:
        with pytest.raises(RuntimeError, match="acknowledgement"):
            process(engine, settings, signal=native_payload())
    finally:
        event.remove(Session, "after_commit", lose_ack)
    retry = process(engine, settings, signal=native_payload())
    assert retry.is_duplicate and retry.outcome == "PAPER_EXECUTED"
    assert counts(engine)["paper_orders"] == 1
    assert counts(engine)["native_bar_outcomes"] == 1


def test_two_workers_cannot_process_the_same_bar_twice(engine, settings, qualified_fixture):
    barrier = Barrier(2)

    def worker(_):
        barrier.wait(timeout=10)
        return process(engine, settings, signal=native_payload())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert sorted(result.is_duplicate for result in results) == [False, True]
    assert results[0].receipt_id == results[1].receipt_id
    assert counts(engine)["paper_orders"] == 1
    assert counts(engine)["signals"] == 1


def test_locked_database_fails_without_advancing(engine, settings):
    impatient = create_engine(engine.url, connect_args={"timeout": 0})
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with pytest.raises(OperationalError, match="locked"):
                process(impatient, settings)
            connection.rollback()
    finally:
        impatient.dispose()
    assert counts(engine)["native_bar_outcomes"] == 0
    assert process(engine, settings).outcome == "NO_SIGNAL"


@pytest.mark.parametrize("damage", ["hash", "sequence", "signal_link"])
def test_damaged_receipt_or_signal_blocks_resume(engine, settings, damage):
    process(engine, settings, signal=native_payload())
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeBarOutcome)).one()
        if damage == "hash":
            row.evidence_hash = "0" * 64
        elif damage == "sequence":
            row.sequence = 2
        else:
            signal = session.get(Signal, row.signal_id)
            signal.raw_payload = {**signal.raw_payload, "entry_price": "200"}
    with pytest.raises(NativeBarError):
        process(engine, settings, signal=native_payload())
    assert counts(engine)["native_bar_outcomes"] == 1


def test_duplicate_signal_outcome_also_obeys_the_outer_transaction(engine, settings, monkeypatch):
    process(engine, settings, signal=native_payload())
    clock(monkeypatch, NOW + STEP)
    second = process(engine, settings, next_history(), signal=native_payload(timestamp=NOW + STEP))
    assert second.outcome == "DUPLICATE_REJECTED"
    assert counts(engine)["signals"] == 2
    assert counts(engine)["native_bar_outcomes"] == 2
    with Session(engine) as session:
        assert len(validate_chain(session)) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"live_trading_enabled": True},
        {"live_execution_adapter": "binance"},
    ],
)
def test_live_configuration_is_blocked_before_processing(engine, settings, changes):
    with pytest.raises(ValueError, match="live execution"):
        process(engine, settings.model_copy(update=changes))
    assert counts(engine)["native_bar_outcomes"] == 0


def test_unsupported_database_is_not_silently_treated_as_sqlite(settings):
    engine = create_mock_engine("postgresql://", executor=lambda *a, **k: None)
    with pytest.raises(ValueError, match="requires SQLite"):
        NativeBarProcessor(engine, settings)


def test_duplicate_intake_does_not_commit_before_its_bar_receipt(engine, settings, monkeypatch):
    process(engine, settings, signal=native_payload())
    clock(monkeypatch, NOW + STEP)
    before = counts(engine)

    def fail_flush(session, *_):
        if any(isinstance(row, NativeBarOutcome) for row in session.new):
            raise RuntimeError("injected duplicate receipt failure")

    event.listen(Session, "before_flush", fail_flush)
    try:
        with pytest.raises(RuntimeError, match="duplicate receipt"):
            process(engine, settings, next_history(), signal=native_payload(timestamp=NOW + STEP))
    finally:
        event.remove(Session, "before_flush", fail_flush)
    assert counts(engine) == before


def test_atomic_processor_preserves_kill_switch_rejection(engine, settings, qualified_fixture):
    with Session(engine) as session, session.begin():
        RiskEngine(session).set_kill_switch(True)
    assert process(engine, settings, signal=native_payload()).outcome == "RISK_REJECTED"
    assert counts(engine)["paper_orders"] == 0
    assert counts(engine)["native_bar_outcomes"] == 1


@pytest.mark.parametrize("collision", ["sequence", "candle"])
def test_database_uniqueness_enforces_stream_sequence_and_candle(engine, settings, collision):
    process(engine, settings)
    with Session(engine) as session:
        original = session.scalars(select(NativeBarOutcome)).one()
        duplicate = NativeBarOutcome(
            stream_key=original.stream_key,
            sequence=original.sequence if collision == "sequence" else 2,
            candle_id=original.candle_id if collision == "candle" else "0" * 64,
            signal_id=None,
            outcome=original.outcome,
            evidence=original.evidence,
            evidence_hash=original.evidence_hash,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
    assert counts(engine)["native_bar_outcomes"] == 1


def test_caller_managed_intake_requires_an_actual_database_transaction(engine, settings):
    with Session(engine) as session:
        service = SignalIntakeService(session, settings)
        with pytest.raises(ValueError, match="active transaction"):
            service.ingest_native(native_payload(), commit=False)
        session.execute(text("SELECT 1"))
        with pytest.raises(ValueError, match="database transaction"):
            service.ingest_native(native_payload(), commit=False)
        session.rollback()
        session.execute(text("BEGIN IMMEDIATE"))
        service.ingest_native(native_payload(), commit=False)
        session.rollback()
    assert counts(engine)["signals"] == 0


@pytest.mark.parametrize("event_name, durable_count", [("before_commit", 0), ("after_commit", 1)])
def test_process_death_before_or_after_commit_is_restart_safe(
    engine, settings, event_name, durable_count
):
    script = """
import os, sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, bars
native.utc_now = lambda: NOW
def crash(session):
    if not session.in_nested_transaction():
        os._exit(73)
event.listen(Session, sys.argv[2], crash)
native.NativeBarProcessor(create_engine(sys.argv[1]), Settings(
    _env_file=None, live_trading_enabled=False, live_execution_adapter='disabled'
)).process(bars(), scope=spec(), signal=None)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), event_name],
        capture_output=True,
        text=True,
        timeout=40,
        check=False,
    )
    assert result.returncode == 73, result.stderr
    assert counts(engine)["native_bar_outcomes"] == durable_count
    retry = process(engine, settings)
    assert retry.is_duplicate is bool(durable_count)
    assert counts(engine)["native_bar_outcomes"] == 1
    with Session(engine) as session:
        NativeBarReceipt.model_validate(session.scalars(select(NativeBarOutcome)).one().evidence)
