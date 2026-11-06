"""Continuation mechanics in disposable SQLite databases, not forward trading evidence."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, NativeHistorySeed
from aurex.risk_engine.service import RiskEngine
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    NativeBarReceipt,
    receipt_evidence,
    validate_chain,
    verified_native_history,
)
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_retained_history import advance, following_bar
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP, bars


def seed_boundary(engine, settings, monkeypatch):
    result = process(engine, settings, bars(4096))
    clock(monkeypatch, NOW + STEP)
    return result


def test_legacy_bytes_and_hash_survive_continuation_and_old_retries(engine, settings, monkeypatch):
    seed_boundary(engine, settings, monkeypatch)
    with Session(engine) as session:
        first = session.scalars(select(NativeBarOutcome)).one()
        original, original_hash = first.evidence, first.evidence_hash
        assert "continuation" not in original
        assert receipt_evidence(NativeBarReceipt.model_validate(original)) == original
    second = advance(engine, settings)
    clock(monkeypatch, NOW + STEP * 2)
    third = advance(engine, settings, {**following_bar(), "timestamp": NOW + STEP})
    assert third.checkpoint.bar_count == 4098
    assert advance(engine, settings).receipt_id == second.receipt_id
    assert process(engine, settings, bars(4096)).is_duplicate
    with Session(engine) as session:
        chain = validate_chain(session)
        assert chain[0][0].evidence == original
        assert chain[0][0].evidence_hash == original_hash
        assert chain[-1][1].continuation.bar_count == 4098
        assert chain[-1][1].schema_version == "native_bar_processing_v2"
        verified = verified_native_history(session, NOW)
        assert verified.retry[0].id == second.receipt_id
        assert verified.head[0].id == third.receipt_id
        assert len(verified.legacy_prefix) == 4096


@pytest.mark.parametrize("after_transition", [False, True])
def test_fresh_process_recovers_indicator_state_from_retained_evidence(
    engine, settings, monkeypatch, after_transition
):
    seed_boundary(engine, settings, monkeypatch)
    if after_transition:
        advance(engine, settings)
    script = """
import sys
from sqlalchemy import create_engine
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, STEP, bars
offset = int(sys.argv[2])
native.utc_now = lambda: NOW + STEP * (offset + 1)
engine = create_engine(sys.argv[1])
processor = native.NativeBarProcessor(engine, Settings(
    _env_file=None, live_trading_enabled=False, live_execution_adapter='disabled'))
bar = {**bars()[-1], 'timestamp': NOW + STEP * offset}
result = processor.process_next(bar, scope=spec(), signal=None)
assert result.checkpoint.bar_count == 4097 + offset
assert not result.is_duplicate
assert processor.process_next(bar, scope=spec(), signal=None).is_duplicate
engine.dispose()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), str(int(after_transition))],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    assert counts(engine)["native_bar_outcomes"] == 2 + int(after_transition)


@pytest.mark.parametrize("damage", ["arithmetic", "chain_hash", "state_missing", "legacy_field"])
def test_rehashed_corruption_is_not_a_trusted_state_cache(engine, settings, monkeypatch, damage):
    seed_boundary(engine, settings, monkeypatch)
    advance(engine, settings)
    with Session(engine) as session, session.begin():
        row = session.scalars(
            select(NativeBarOutcome).order_by(NativeBarOutcome.sequence.desc())
        ).first()
        data = row.evidence
        if damage == "arithmetic":
            data = {**data, "continuation": {**data["continuation"], "ema_fast": "99"}}
        elif damage == "chain_hash":
            data = {**data, "checkpoint": {**data["checkpoint"], "history_sha256": "0" * 64}}
        elif damage == "state_missing":
            data = {**data, "continuation": None}
        else:
            row = session.scalars(
                select(NativeBarOutcome).order_by(NativeBarOutcome.sequence)
            ).first()
            data = {**row.evidence, "continuation": None}
        row.evidence = data
        row.evidence_hash = content_hash(data)
    before = counts(engine)
    with pytest.raises(ValueError):
        advance(engine, settings)
    assert counts(engine) == before


@pytest.mark.parametrize("kind", ["stale", "future", "gap", "changed", "clock", "scope"])
def test_continuation_does_not_relax_admission_guards(engine, settings, monkeypatch, kind):
    seed_boundary(engine, settings, monkeypatch)
    second = advance(engine, settings)
    next_bar = {**following_bar(), "timestamp": NOW + STEP}
    now = NOW + STEP * 2
    scope = spec()
    if kind == "stale":
        now += timedelta(seconds=181)
    elif kind == "future":
        now -= timedelta(seconds=1)
    elif kind == "gap":
        next_bar["timestamp"] += STEP
        now += STEP
    elif kind == "changed":
        next_bar = {**following_bar(), "volume": "2"}
    elif kind == "clock":
        now = NOW
    else:
        scope = spec(settings_fingerprint="changed")
    clock(monkeypatch, now)
    with pytest.raises(NativeBarError):
        NativeBarProcessor(engine, settings).process_next(next_bar, scope=scope, signal=None)
    clock(monkeypatch, NOW + STEP * 3)
    assert advance(engine, settings).receipt_id == second.receipt_id
    assert counts(engine)["native_bar_outcomes"] == 2


def test_slow_reconstruction_cannot_admit_a_now_stale_bar(engine, settings, monkeypatch):
    seed_boundary(engine, settings, monkeypatch)
    times = iter([NOW + STEP, NOW + STEP + timedelta(seconds=181)])
    monkeypatch.setattr("aurex.signal_gateway.native_processing.utc_now", lambda: next(times))
    with pytest.raises(NativeBarError, match="stale"):
        advance(engine, settings)
    assert counts(engine)["native_bar_outcomes"] == 1


def test_keyset_pages_validate_all_receipts_and_signal_links(engine, settings, monkeypatch):
    seed_boundary(engine, settings, monkeypatch)
    monkeypatch.setattr("aurex.signal_gateway.native_processing.CHAIN_PAGE_SIZE", 2)
    for offset in range(6):
        clock(monkeypatch, NOW + STEP * (offset + 1))
        advance(
            engine,
            settings,
            {**following_bar(), "timestamp": NOW + STEP * offset},
            signal=native_payload(timestamp=NOW + STEP * (offset + 1)),
        )
    with Session(engine) as session:
        verified = verified_native_history(session, NOW)
        assert verified.head[1].sequence == 7
        assert verified.continuation.bar_count == 4102
        assert verified.retry[1].sequence == 2
    assert counts(engine)["signals"] == 6
    assert counts(engine)["paper_orders"] == 0


@pytest.mark.parametrize("sequence", [0, -1])
def test_paged_audit_cannot_skip_nonpositive_sequence_rows(engine, settings, monkeypatch, sequence):
    seed_boundary(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        original = session.scalars(select(NativeBarOutcome)).one()
        session.add(
            NativeBarOutcome(
                stream_key=original.stream_key,
                sequence=sequence,
                candle_id="0" * 64,
                outcome=original.outcome,
                evidence=original.evidence,
                evidence_hash=original.evidence_hash,
            )
        )
    before = counts(engine)
    with pytest.raises(NativeBarError, match="integrity_failed"):
        advance(engine, settings)
    assert counts(engine) == before


def test_full_prefix_is_snapshotted_before_caller_can_change_seed(engine, settings, monkeypatch):
    history = bars()
    calls = 0

    def mutate_after_preflight():
        nonlocal calls
        calls += 1
        if calls == 2:
            history[0]["volume"] = "2"
        return NOW

    monkeypatch.setattr("aurex.signal_gateway.native_processing.utc_now", mutate_after_preflight)
    result = process(engine, settings, history)
    with Session(engine) as session:
        seed = session.scalars(select(NativeHistorySeed)).one()
        assert seed.evidence["candles"][0]["volume"] == "1"
    assert history[0]["volume"] == "2"
    assert process(engine, settings, bars()).receipt_id == result.receipt_id


def test_concurrent_boundary_workers_create_one_paper_order(
    engine, settings, monkeypatch, qualified_fixture
):
    seed_boundary(engine, settings, monkeypatch)
    signal = native_payload(timestamp=NOW + STEP)
    barrier = Barrier(2)

    def worker(_):
        barrier.wait(timeout=10)
        return advance(engine, settings, signal=signal)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    assert results[0].receipt_id == results[1].receipt_id
    assert results[0].outcome == "PAPER_EXECUTED"
    assert sorted(result.is_duplicate for result in results) == [False, True]
    assert counts(engine)["native_bar_outcomes"] == 2
    assert counts(engine)["paper_orders"] == counts(engine)["paper_trades"] == 1


@pytest.mark.parametrize("fault", ["before_flush", "before_commit", "after_commit"])
def test_failure_rolls_back_or_recovers_original_continuation_order(
    engine, settings, monkeypatch, qualified_fixture, fault
):
    seed_boundary(engine, settings, monkeypatch)
    signal = native_payload(timestamp=NOW + STEP)
    before = counts(engine)

    def fail(session, *_):
        if fault != "before_flush" and session.in_nested_transaction():
            return
        if fault != "before_flush" or any(isinstance(row, NativeBarOutcome) for row in session.new):
            raise RuntimeError("injected continuation failure")

    event.listen(Session, fault, fail)
    try:
        with pytest.raises(RuntimeError, match="continuation failure"):
            advance(engine, settings, signal=signal)
    finally:
        event.remove(Session, fault, fail)
    if fault != "after_commit":
        assert counts(engine) == before
    result = advance(engine, settings, signal=signal)
    assert result.is_duplicate == (fault == "after_commit")
    assert result.outcome == "PAPER_EXECUTED"
    assert counts(engine)["paper_orders"] == counts(engine)["paper_trades"] == 1
    assert counts(engine)["native_bar_outcomes"] == 2


def test_kill_switch_still_rejects_a_continuation_signal(
    engine, settings, monkeypatch, qualified_fixture
):
    seed_boundary(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        RiskEngine(session).set_kill_switch(True)
    result = advance(engine, settings, signal=native_payload(timestamp=NOW + STEP))
    assert result.outcome == "RISK_REJECTED"
    assert counts(engine)["paper_orders"] == 0
