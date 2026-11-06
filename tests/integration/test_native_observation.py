"""Mocked acquisition and disposable SQLite only, never genuine forward evidence."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, NativeHistorySeed
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_market_data import PublicDataError
from aurex.signal_gateway.native_observation import NativePublicObserver
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    NativeBarReceipt,
    receipt_evidence,
    validate_chain,
)
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.integration.test_native_source_binding import packet
from tests.unit.test_native_closed_bars import STEP, bars

MODULE = "aurex.signal_gateway.native_observation"


def set_clock(monkeypatch, now):
    clock(monkeypatch, now)
    monkeypatch.setattr(f"{MODULE}.utc_now", lambda: now)


def scope(**changes):
    return spec(feed_id="binance_spot_public", **changes)


def acquisition(monkeypatch, history=None, observed_at=None):
    observed_at = observed_at or NOW + timedelta(seconds=5)
    set_clock(monkeypatch, observed_at)
    # This label exercises the trusted-code branch under a mock. The packet and
    # every receipt produced here are synthetic test artifacts, not source proof.
    state = SimpleNamespace(
        evidence=packet(history, observed_at=observed_at).model_copy(
            update={"transport": "public_https"}
        ),
        calls=[],
        effect=None,
    )

    def acquire(**kwargs):
        state.calls.append(kwargs)
        if state.effect:
            state.effect()
        return state.evidence

    monkeypatch.setattr(f"{MODULE}.PublicCandleClient", lambda: SimpleNamespace(acquire=acquire))
    return state


def observe(engine, settings, **kwargs):
    return NativePublicObserver(engine, settings).observe(scope=scope(), seed_count=17, **kwargs)


def chain(engine):
    with Session(engine) as session:
        return [(row.evidence_hash, receipt) for row, receipt in validate_chain(session)]


def seed(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    return state, observe(engine, settings)


def next_acquisition(monkeypatch, *, seconds=5):
    return acquisition(
        monkeypatch,
        [{**bars()[-1], "timestamp": NOW}],
        NOW + STEP + timedelta(seconds=seconds),
    )


def test_owned_seed_commits_v5_without_entry_authority(engine, settings, monkeypatch):
    state, result = seed(engine, settings, monkeypatch)
    assert state.calls == [{"count": 17, "first_open": bars()[0]["timestamp"]}]
    assert result.status == "OBSERVED_NO_ENTRY"
    assert result.next_observation_at == NOW + STEP + timedelta(seconds=2)
    assert result.processing.outcome == "SOURCE_OBSERVED_NO_ENTRY"
    receipt = chain(engine)[0][1]
    assert receipt.schema_version == "native_bar_processing_v5"
    assert receipt.public_observation.admission == "acquisition_owned_public_https"
    assert receipt.public_observation.started_at == NOW + timedelta(seconds=5)
    assert receipt.public_observation.expected_previous_evidence_hash is None
    assert receipt.public_observation.forward_qualifying is False
    assert receipt.public_observation.execution_authority is False
    assert receipt.source_origin_verified is False
    assert receipt.public_source.acquisition == state.evidence
    assert counts(engine) == {
        "native_bar_outcomes": 1,
        "native_history_seeds": 1,
        "signals": 0,
        "signal_events": 0,
        "risk_decisions": 0,
        "paper_orders": 0,
        "paper_trades": 0,
        "positions": 0,
    }


@pytest.mark.parametrize("seconds", [5, 179, 899, 900, 901])
def test_repeated_poll_waits_without_refetching_or_writing(engine, settings, monkeypatch, seconds):
    state, first = seed(engine, settings, monkeypatch)
    before = counts(engine)
    set_clock(monkeypatch, NOW + timedelta(seconds=seconds))
    result = observe(engine, settings)
    assert result.status == "WAITING_FOR_CLOSE" and result.processing is None
    assert result.next_observation_at == first.next_observation_at
    assert len(state.calls) == 1 and counts(engine) == before


@pytest.mark.parametrize("seconds", [181, 800, 900, 901])
def test_bootstrap_waits_for_fresh_window_without_network(engine, settings, monkeypatch, seconds):
    state = acquisition(monkeypatch)
    set_clock(monkeypatch, NOW + timedelta(seconds=seconds))
    result = observe(engine, settings)
    assert result.status == "WAITING_FOR_CLOSE"
    assert result.next_observation_at == NOW + STEP + timedelta(seconds=2)
    assert state.calls == [] and not any(counts(engine).values())


def test_new_instance_resumes_exact_next_candle(engine, settings, monkeypatch):
    _, first = seed(engine, settings, monkeypatch)
    state = next_acquisition(monkeypatch)
    second = observe(engine, settings)
    assert state.calls == [{"count": 1, "first_open": NOW}]
    assert second.processing.checkpoint.bar_count == 18
    receipts = chain(engine)
    assert receipts[1][1].public_observation.expected_previous_evidence_hash == (
        first.processing.evidence_hash
    )
    assert receipts[1][1].public_source.purpose == "CLOSED_BAR"
    assert counts(engine)["paper_orders"] == 0


@pytest.mark.parametrize("late", [181, 1000, 86400])
def test_missed_window_stops_without_backfill_or_recovery(engine, settings, monkeypatch, late):
    state, _ = seed(engine, settings, monkeypatch)
    before = counts(engine)
    state.calls.clear()
    set_clock(monkeypatch, NOW + STEP + timedelta(seconds=late))
    with pytest.raises(NativeBarError, match="window_missed_requires_reconciliation"):
        observe(engine, settings)
    assert state.calls == [] and counts(engine) == before


@pytest.mark.parametrize(
    "changes", [{"live_trading_enabled": True}, {"live_execution_adapter": "binance_spot_testnet"}]
)
def test_live_settings_block_before_network(engine, settings, monkeypatch, changes):
    state = acquisition(monkeypatch)
    with pytest.raises(NativeBarError, match="requires_live_disabled"):
        observe(engine, settings.model_copy(update=changes))
    assert not state.calls and not any(counts(engine).values())


@pytest.mark.parametrize("count", [True, 0, -1, 4097, 1.5])
def test_invalid_seed_count_never_fetches(engine, settings, monkeypatch, count):
    state = acquisition(monkeypatch)
    with pytest.raises(NativeBarError, match="seed_size_invalid"):
        NativePublicObserver(engine, settings).observe(scope=scope(), seed_count=count)
    assert not state.calls


def test_fixture_scope_never_fetches(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    with pytest.raises(NativeBarError, match="requires_public_stream"):
        NativePublicObserver(engine, settings).observe(scope=spec())
    assert not state.calls


def test_changed_stream_scope_never_fetches(engine, settings, monkeypatch):
    state, _ = seed(engine, settings, monkeypatch)
    state.calls.clear()
    with pytest.raises(NativeBarError, match="stream_scope_changed"):
        NativePublicObserver(engine, settings).observe(scope=scope(strategy_version="different"))
    assert not state.calls


def test_unbound_history_is_not_silently_promoted(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    process(engine, settings, scope=scope())
    with pytest.raises(NativeBarError, match="requires_source_bound_history"):
        observe(engine, settings)
    assert not state.calls and counts(engine)["native_bar_outcomes"] == 1


def test_imported_source_can_supply_history_but_never_retroactive_online_claim(
    engine, settings, monkeypatch
):
    state = acquisition(monkeypatch)
    first = NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="SEED"
    )
    next_acquisition(monkeypatch)
    observe(engine, settings)
    receipts = chain(engine)
    assert receipts[0][0] == first.evidence_hash
    assert receipts[0][1].public_observation is None
    assert receipts[1][1].public_observation is not None
    assert all(not receipt.source_origin_verified for _, receipt in receipts)


@pytest.mark.parametrize("failure", ["clock", "transport", "rate_limit", "disk"])
def test_acquisition_failures_never_commit(engine, settings, monkeypatch, failure):
    state = acquisition(monkeypatch)
    error = {
        "clock": PublicDataError("public_server_clock_skew"),
        "transport": PublicDataError("public_transport_failed"),
        "rate_limit": PublicDataError("public_http_rejected", status=429, retry_after=30),
        "disk": OSError("fixture disk failure"),
    }[failure]

    def fail():
        raise error

    state.effect = fail
    with pytest.raises(type(error)) as raised:
        observe(engine, settings)
    assert raised.value is error
    assert len(state.calls) == 1 and not any(counts(engine).values())


@pytest.mark.parametrize("kind", ["injected", "window", "corrupt", "future", "deadline"])
def test_acquired_packet_and_admission_are_rechecked(engine, settings, monkeypatch, kind):
    state = acquisition(monkeypatch)
    if kind == "injected":
        state.evidence = state.evidence.model_copy(update={"transport": "injected"})
    elif kind == "window":
        state.evidence = packet(bars(18)).model_copy(update={"transport": "public_https"})
    elif kind == "corrupt":
        state.evidence = state.evidence.model_copy(update={"candles_sha256": "a" * 64})
    elif kind == "future":
        state.evidence = packet(observed_at=NOW + timedelta(seconds=6)).model_copy(
            update={"transport": "public_https"}
        )
    else:
        state.effect = lambda: set_clock(monkeypatch, NOW + timedelta(seconds=96))
    with pytest.raises(ValueError):
        observe(engine, settings)
    assert not any(counts(engine).values())


def test_head_race_rejects_different_witness_without_holding_network_lock(
    engine, settings, monkeypatch
):
    state = acquisition(monkeypatch)

    def other_writer():
        NativeBarProcessor(engine, settings).process_sourced(
            state.evidence, scope=scope(), purpose="SEED"
        )

    state.effect = other_writer
    with pytest.raises(NativeBarError, match="processed_bar_observation_changed"):
        observe(engine, settings)
    assert counts(engine)["native_bar_outcomes"] == 1
    assert chain(engine)[0][1].public_observation is None


@pytest.mark.parametrize("event_name", ["before_flush", "before_commit"])
def test_commit_failure_rolls_back_seed_source_and_observation(
    engine, settings, monkeypatch, event_name
):
    acquisition(monkeypatch)

    def fail(*args):
        if args[0].new:
            raise RuntimeError("fixture commit failure")
        if event_name == "before_commit":
            raise RuntimeError("fixture commit failure")

    event.listen(Session, event_name, fail)
    try:
        with pytest.raises(RuntimeError, match="fixture commit failure"):
            observe(engine, settings)
    finally:
        event.remove(Session, event_name, fail)
    assert not any(counts(engine).values())


def test_lost_ack_is_resolved_by_retained_head_without_refetch(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)

    def lost_ack(session):
        raise RuntimeError("fixture lost acknowledgement")

    event.listen(Session, "after_commit", lost_ack)
    try:
        with pytest.raises(RuntimeError, match="lost acknowledgement"):
            observe(engine, settings)
    finally:
        event.remove(Session, "after_commit", lost_ack)
    assert len(chain(engine)) == 1
    result = observe(engine, settings)
    assert result.status == "WAITING_FOR_CLOSE" and len(state.calls) == 1
    assert counts(engine)["native_history_seeds"] == 1


def test_imported_call_cannot_retry_or_drop_online_admission(engine, settings, monkeypatch):
    state, first = seed(engine, settings, monkeypatch)
    processor = NativeBarProcessor(engine, settings)
    with pytest.raises(NativeBarError, match="processed_bar_observation_changed"):
        processor.process_sourced(state.evidence, scope=scope(), purpose="SEED")
    state = next_acquisition(monkeypatch)
    with pytest.raises(NativeBarError, match="observation_admission_dropped"):
        processor.process_sourced(state.evidence, scope=scope(), purpose="CLOSED_BAR")
    assert chain(engine)[0][0] == first.processing.evidence_hash


def test_explicit_recovery_does_not_erase_online_admission_requirement(
    engine, settings, monkeypatch
):
    seed(engine, settings, monkeypatch)
    state = next_acquisition(monkeypatch)
    processor = NativeBarProcessor(engine, settings)
    processor.process_sourced(state.evidence, scope=scope(), purpose="RECOVERY")
    state = acquisition(
        monkeypatch,
        [{**bars()[-1], "timestamp": NOW + STEP}],
        NOW + STEP * 2 + timedelta(seconds=5),
    )
    with pytest.raises(NativeBarError, match="observation_admission_dropped"):
        processor.process_sourced(state.evidence, scope=scope(), purpose="CLOSED_BAR")
    observe(engine, settings)
    assert len(chain(engine)) == 3


@pytest.mark.parametrize("kind", ["missing", "hash", "time", "authority", "legacy"])
def test_rehashed_observation_corruption_rejects(engine, settings, monkeypatch, kind):
    seed(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeBarOutcome)).one()
        evidence = dict(row.evidence)
        admission = dict(evidence["public_observation"])
        if kind == "missing":
            del evidence["public_observation"]
        elif kind == "hash":
            admission["expected_previous_evidence_hash"] = "a" * 64
        elif kind == "time":
            admission["started_at"] = (NOW + timedelta(seconds=6)).isoformat()
        elif kind == "authority":
            admission["forward_qualifying"] = True
        else:
            evidence["schema_version"] = "native_bar_processing_v4"
        if kind != "missing":
            evidence["public_observation"] = admission
        row.evidence = evidence
        row.evidence_hash = content_hash(evidence)
    with pytest.raises(ValueError):
        chain(engine)


def test_rehashed_downgrade_after_recovery_rejects(engine, settings, monkeypatch):
    seed(engine, settings, monkeypatch)
    state = next_acquisition(monkeypatch)
    NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="RECOVERY"
    )
    acquisition(
        monkeypatch,
        [{**bars()[-1], "timestamp": NOW + STEP}],
        NOW + STEP * 2 + timedelta(seconds=5),
    )
    observe(engine, settings)
    with Session(engine) as session, session.begin():
        row = session.scalar(select(NativeBarOutcome).where(NativeBarOutcome.sequence == 3))
        evidence = dict(row.evidence)
        del evidence["public_observation"]
        evidence["schema_version"] = "native_bar_processing_v4"
        row.evidence = evidence
        row.evidence_hash = content_hash(evidence)
    with pytest.raises(NativeBarError, match="observation_admission_dropped"):
        chain(engine)


def test_v4_canonical_serialization_is_unchanged(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="SEED"
    )
    with Session(engine) as session:
        row = session.scalars(select(NativeBarOutcome)).one()
        assert "public_observation" not in row.evidence
        assert receipt_evidence(NativeBarReceipt.model_validate(row.evidence)) == row.evidence


def test_open_position_blocks_before_acquisition(engine, settings, monkeypatch, qualified_fixture):
    state = acquisition(monkeypatch)
    process(engine, settings, scope=scope(), signal=native_payload())
    # Attach retained source via exit-only recovery, without pretending entry was online.
    state = next_acquisition(monkeypatch)
    NativeBarProcessor(engine, settings).process_sourced(
        state.evidence, scope=scope(), purpose="RECOVERY"
    )
    with pytest.raises(NativeBarError, match="open_position_requires_online_exit_monitor"):
        observe(engine, settings)
    assert state.calls == []


@pytest.mark.parametrize(
    "kind", ["before_plan", "before_request", "after_request", "before_commit"]
)
def test_clock_and_commit_freshness_rechecked(engine, settings, monkeypatch, kind):
    state, _ = seed(engine, settings, monkeypatch)
    state.calls.clear()
    before = counts(engine)
    if kind == "before_plan":
        set_clock(monkeypatch, NOW + timedelta(seconds=4))
    else:
        state = next_acquisition(monkeypatch)
        if kind == "before_request":
            times = iter([NOW + STEP + timedelta(seconds=5), NOW + STEP])
            monkeypatch.setattr(f"{MODULE}.utc_now", lambda: next(times))
        elif kind == "after_request":
            state.effect = lambda: set_clock(monkeypatch, NOW + STEP + timedelta(seconds=4))
        else:
            times = iter(
                [NOW + STEP + timedelta(seconds=5)] * 2 + [NOW + STEP + timedelta(seconds=181)]
            )
            monkeypatch.setattr(
                "aurex.signal_gateway.native_processing.utc_now", lambda: next(times)
            )
    with pytest.raises(ValueError):
        observe(engine, settings)
    assert counts(engine) == before
    if kind in {"before_plan", "before_request"}:
        assert not state.calls


def test_no_public_packet_or_transport_argument_exists(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    observer = NativePublicObserver(engine, settings)
    for kwargs in ({"evidence": state.evidence}, {"transport": lambda _: state.evidence}):
        with pytest.raises(TypeError):
            observer.observe(scope=scope(), **kwargs)
    assert not state.calls


def test_concurrent_identical_observations_commit_once(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    barrier = Barrier(2)
    state.effect = lambda: barrier.wait(timeout=10)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: observe(engine, settings), range(2)))
    assert len(state.calls) == 2
    assert len({item.processing.receipt_id for item in results}) == 1
    assert sorted(item.processing.is_duplicate for item in results) == [False, True]
    assert counts(engine)["native_bar_outcomes"] == 1


def test_expected_head_recheck_detects_external_reset(engine, settings, monkeypatch):
    seed(engine, settings, monkeypatch)
    state = next_acquisition(monkeypatch)

    def reset_fixture():
        with Session(engine) as session, session.begin():
            session.execute(delete(NativeBarOutcome))
            session.execute(delete(NativeHistorySeed))

    state.effect = reset_fixture
    with pytest.raises(NativeBarError, match="observation_expected_head_changed"):
        observe(engine, settings)
    assert not any(counts(engine).values())


def test_live_toggle_during_acquisition_blocks_commit(engine, settings, monkeypatch):
    state = acquisition(monkeypatch)
    state.effect = lambda: setattr(settings, "live_trading_enabled", True)
    with pytest.raises(ValueError, match="live execution"):
        observe(engine, settings)
    assert not any(counts(engine).values())


def test_v5_continues_beyond_4096_without_reseeding(engine, settings, monkeypatch):
    acquisition(monkeypatch, bars(4096))
    first = NativePublicObserver(engine, settings).observe(scope=scope(), seed_count=4096)
    next_acquisition(monkeypatch)
    second = observe(engine, settings)
    assert first.processing.checkpoint.bar_count == 4096
    assert second.processing.checkpoint.bar_count == 4097
    receipt = chain(engine)[-1][1]
    assert receipt.schema_version == "native_bar_processing_v5"
    assert receipt.continuation.bar_count == 4097
    assert counts(engine)["native_history_seeds"] == 1


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_process_death_and_restart_keep_observation_atomic(engine, settings, monkeypatch, phase):
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
from tests.unit.test_native_closed_bars import NOW
observation.utc_now = native.utc_now = lambda: NOW + timedelta(seconds=5)
evidence = packet().model_copy(update={'transport': 'public_https'})
observation.PublicCandleClient = lambda: SimpleNamespace(acquire=lambda **_: evidence)
engine = create_engine(sys.argv[1])
event.listen(Session, sys.argv[2], lambda *args: os._exit(73))
observation.NativePublicObserver(engine, Settings(_env_file=None,
    live_trading_enabled=False, live_execution_adapter='disabled')).observe(
    scope=scope(), seed_count=17)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), phase],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 73, result.stderr
    expected = int(phase == "after_commit")
    assert counts(engine)["native_bar_outcomes"] == expected
    assert counts(engine)["native_history_seeds"] == expected
    state = acquisition(monkeypatch)
    resumed = observe(engine, settings)
    assert resumed.status == ("WAITING_FOR_CLOSE" if expected else "OBSERVED_NO_ENTRY")
    assert len(state.calls) == 1 - expected
    assert chain(engine)[0][1].public_observation is not None
