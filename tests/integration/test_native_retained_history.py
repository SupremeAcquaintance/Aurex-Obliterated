"""Retained synthetic inputs, never the operator database or a live feed."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, NativeHistorySeed
from aurex.signal_gateway.native_bars import ClosedBar, NativeBarError, history_hash
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    retained_history,
    validate_chain,
)
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP, bars


def following_bar():
    return {**bars()[-1], "timestamp": NOW}


def advance(engine, settings, candle=None, signal=None):
    return NativeBarProcessor(engine, settings).process_next(
        following_bar() if candle is None else candle, scope=spec(), signal=signal
    )


def test_retained_seed_and_receipts_reproduce_every_committed_prefix(engine, settings, monkeypatch):
    first = process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    second = advance(engine, settings)
    with Session(engine) as session:
        chain = validate_chain(session)
        history = retained_history(session, chain)
        assert history_hash(history) == second.checkpoint.history_sha256
        assert history_hash(history[:-1]) == first.checkpoint.history_sha256
        assert history == [ClosedBar.model_validate(item) for item in bars() + [following_bar()]]
        seed = session.scalars(select(NativeHistorySeed)).one()
        assert len(seed.evidence["candles"]) == 17
    assert counts(engine)["native_bar_outcomes"] == 2
    assert counts(engine)["native_history_seeds"] == 1


def test_restart_does_not_need_caller_seed_and_old_retry_does_not_rewind(
    engine, settings, monkeypatch
):
    first = process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    independent_engine = create_engine(engine.url)
    try:
        second = advance(independent_engine, settings)
        retry = advance(independent_engine, settings, bars()[-1])
        assert retry.is_duplicate and retry.receipt_id == first.receipt_id
        assert advance(independent_engine, settings).receipt_id == second.receipt_id
    finally:
        independent_engine.dispose()
    assert counts(engine)["native_bar_outcomes"] == 2


def test_fresh_subprocess_resumes_using_only_the_new_candle(engine, settings):
    process(engine, settings)
    script = """
import sys
from sqlalchemy import create_engine
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, STEP, bars
native.utc_now = lambda: NOW + STEP
engine = create_engine(sys.argv[1])
result = native.NativeBarProcessor(engine, Settings(
    _env_file=None, live_trading_enabled=False, live_execution_adapter='disabled'
)).process_next({**bars()[-1], 'timestamp': NOW}, scope=spec(), signal=None)
assert result.outcome == 'NO_SIGNAL' and not result.is_duplicate
assert result.checkpoint.bar_count == 18
engine.dispose()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(engine.url)],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    assert counts(engine)["native_bar_outcomes"] == 2


def test_uninitialized_stream_cannot_be_seeded_by_one_bar(engine, settings):
    with pytest.raises(NativeBarError, match="not_initialized"):
        advance(engine, settings)
    assert all(value == 0 for value in counts(engine).values())


def test_two_resume_workers_append_one_receipt(engine, settings, monkeypatch):
    process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    barrier = Barrier(2)

    def worker(_):
        barrier.wait(timeout=10)
        return advance(engine, settings)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert results[0].receipt_id == results[1].receipt_id
    assert sorted(result.is_duplicate for result in results) == [False, True]
    assert counts(engine)["native_bar_outcomes"] == 2
    assert counts(engine)["native_history_seeds"] == 1


@pytest.mark.parametrize("damage", ["missing", "hash", "changed_values", "orphan", "checkpoint"])
def test_missing_or_corrupted_seed_or_checkpoint_blocks_without_repair(engine, settings, damage):
    from aurex.signal_gateway.native_bars import content_hash

    process(engine, settings)
    with Session(engine) as session, session.begin():
        seed = session.scalars(select(NativeHistorySeed)).one()
        if damage == "missing":
            session.delete(seed)
        elif damage == "hash":
            seed.evidence_hash = "0" * 64
        elif damage == "changed_values":
            data = {**seed.evidence, "candles": [dict(bar) for bar in seed.evidence["candles"]]}
            data["candles"][0]["volume"] = "2"
            seed.evidence = data
            seed.evidence_hash = content_hash(data)
        elif damage == "orphan":
            session.execute(delete(NativeBarOutcome))
        else:
            row = session.scalars(select(NativeBarOutcome)).one()
            row.evidence = {
                **row.evidence,
                "checkpoint": {**row.evidence["checkpoint"], "history_sha256": "0" * 64},
            }
            row.evidence_hash = content_hash(row.evidence)
    before = counts(engine)
    with pytest.raises(NativeBarError):
        process(engine, settings)
    assert counts(engine) == before


def test_changed_retry_and_unprocessed_seed_candle_cannot_be_reinterpreted(engine, settings):
    process(engine, settings)
    for candle in ({**bars()[-1], "volume": "2"}, bars()[0]):
        with pytest.raises(NativeBarError):
            advance(engine, settings, candle)
    assert counts(engine)["native_bar_outcomes"] == 1


@pytest.mark.parametrize("kind", ["gap", "stale", "future"])
def test_retained_history_does_not_relax_timing_or_continuity(engine, settings, monkeypatch, kind):
    process(engine, settings)
    candle = following_bar()
    now = NOW + STEP
    if kind == "gap":
        candle["timestamp"] += STEP
        now += STEP
    elif kind == "stale":
        now += timedelta(seconds=181)
    else:
        now -= timedelta(seconds=1)
    clock(monkeypatch, now)
    with pytest.raises(NativeBarError):
        advance(engine, settings, candle)
    assert counts(engine)["native_bar_outcomes"] == 1


def test_full_window_continues_with_versioned_state_and_accepts_legacy_retry(
    engine, settings, monkeypatch
):
    history = bars(4096)
    first = process(engine, settings, history)
    clock(monkeypatch, NOW + STEP)
    next_result = advance(engine, settings)
    assert next_result.checkpoint.bar_count == 4097
    assert next_result.checkpoint.schema_version == "native_closed_bar_continuation_v1"
    retry = advance(engine, settings, history[-1])
    assert retry.is_duplicate and retry.receipt_id == first.receipt_id
    assert counts(engine)["native_bar_outcomes"] == 2


def test_seed_flush_failure_rolls_back_signal_effects(engine, settings, qualified_fixture):
    before = counts(engine)

    def fail_seed(session, *_):
        if any(isinstance(row, NativeHistorySeed) for row in session.new):
            raise RuntimeError("injected seed failure")

    event.listen(Session, "before_flush", fail_seed)
    try:
        with pytest.raises(RuntimeError, match="seed failure"):
            process(engine, settings, signal=native_payload())
    finally:
        event.remove(Session, "before_flush", fail_seed)
    assert counts(engine) == before


def test_signal_from_restored_history_still_uses_retirement_gate(engine, settings, monkeypatch):
    process(engine, settings)
    clock(monkeypatch, NOW + STEP)
    signal = native_payload(timestamp=NOW + STEP)
    result = advance(engine, settings, signal=signal)
    assert result.outcome == "RISK_REJECTED"
    assert advance(engine, settings, signal=signal).is_duplicate
    assert counts(engine)["paper_orders"] == 0
    assert counts(engine)["signals"] == 1
