"""Synthetic source packets and disposable ledgers only; never forward evidence."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, NativeHistorySeed, PaperOrder, PaperTrade
from aurex.domain.enums import TradeStatus
from aurex.signal_gateway.native_bars import ClosedBar, NativeBarError, content_hash, history_hash
from aurex.signal_gateway.native_market_data import (
    TIME_URL,
    PublicCandleClient,
    PublicResponse,
    milliseconds,
    write_public_evidence,
)
from aurex.signal_gateway.native_processing import (
    NativeBarProcessor,
    NativeBarReceipt,
    receipt_evidence,
    retained_history,
    validate_chain,
)
from aurex.signal_gateway.native_recovery import RECOVERY_FILL_MODEL
from aurex.signal_gateway.native_source import bind_public_source
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import qualified_fixture as qualified_fixture
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import STEP, bars


def packet(history=None, *, observed_at=None):
    candles = [ClosedBar.model_validate(bar) for bar in (bars() if history is None else history)]
    observed_at = observed_at or candles[-1].timestamp + STEP + timedelta(seconds=5)
    by_open = {milliseconds(bar.timestamp): bar for bar in candles}

    def fetch(url):
        if url == TIME_URL:
            payload = {"serverTime": milliseconds(observed_at)}
        else:
            query = parse_qs(urlsplit(url).query)
            first = int(query["startTime"][0])
            count = int(query["limit"][0])
            payload = []
            for index in range(count):
                opened = first + index * 900000
                bar = by_open[opened]
                payload.append(
                    [
                        opened,
                        *[
                            format(getattr(bar, name), "f")
                            for name in ("open", "high", "low", "close", "volume")
                        ],
                        opened + 899999,
                        "1000",
                        1,
                        "0",
                        "0",
                        "0",
                    ]
                )
        return PublicResponse(200, json.dumps(payload, separators=(",", ":")).encode())

    return PublicCandleClient(
        transport=fetch, now=lambda: observed_at, monotonic=lambda: 0
    ).acquire(count=len(candles), first_open=candles[0].timestamp)


def submit(engine, settings, evidence, *, purpose="SEED", scope=None):
    return NativeBarProcessor(engine, settings).process_sourced(
        evidence, scope=scope or spec(), purpose=purpose
    )


def initialize(engine, settings, monkeypatch, count=17):
    evidence = packet(bars(count))
    clock(monkeypatch, NOW + timedelta(seconds=5))
    return evidence, submit(engine, settings, evidence)


def next_packet(offset=0, **changes):
    return packet([{**bars()[-1], "timestamp": NOW + STEP * offset, **changes}])


def audit(engine):
    with Session(engine) as session:
        return [(row.evidence_hash, receipt) for row, receipt in validate_chain(session)]


def test_seed_retains_exact_source_and_warmup_in_one_observation_only_receipt(
    engine, settings, monkeypatch
):
    evidence, result = initialize(engine, settings, monkeypatch)
    assert result.outcome == "SOURCE_OBSERVED_NO_ENTRY"
    assert result.signal_id is None and result.source_purpose == "SEED"
    assert result.source_evidence_hash == content_hash(evidence.model_dump(mode="json"))
    with Session(engine) as session:
        chain = validate_chain(session)
        receipt = chain[0][1]
        assert receipt.schema_version == "native_bar_processing_v4"
        assert receipt.public_source.acquisition == evidence
        assert receipt.public_source.forward_qualifying is False
        assert receipt.public_source.execution_authority is False
        assert receipt.source_origin_verified is False
        assert receipt_evidence(receipt) == chain[0][0].evidence
        assert history_hash(retained_history(session, chain)) == evidence.candles_sha256
        assert session.scalars(select(NativeHistorySeed)).one().evidence["schema_version"] == (
            "native_history_seed_v1"
        )
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


def test_closed_bar_restart_retries_are_exact_and_do_not_rewind(engine, settings, monkeypatch):
    seed, first = initialize(engine, settings, monkeypatch)
    evidence = next_packet()
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    second = submit(engine, settings, evidence, purpose="CLOSED_BAR")
    clock(monkeypatch, NOW + timedelta(days=2))
    retry = submit(engine, settings, evidence, purpose="CLOSED_BAR")
    assert retry.is_duplicate and retry.receipt_id == second.receipt_id
    assert retry.evidence_hash == second.evidence_hash
    assert submit(engine, settings, seed).receipt_id == first.receipt_id
    assert counts(engine)["native_bar_outcomes"] == 2
    assert counts(engine)["signals"] == 0


@pytest.mark.parametrize("kind", ["new_observation", "raw_retry", "changed_purpose", "changed_bar"])
def test_processed_source_cannot_be_replaced_on_retry(engine, settings, monkeypatch, kind):
    evidence, _ = initialize(engine, settings, monkeypatch)
    before = counts(engine)
    with pytest.raises(ValueError):
        if kind == "raw_retry":
            process(engine, settings)
        elif kind == "changed_purpose":
            submit(engine, settings, packet([bars()[-1]]), purpose="CLOSED_BAR")
        elif kind == "changed_bar":
            changed = bars()
            changed[-1]["high"] = "102"
            submit(engine, settings, packet(changed))
        else:
            revised = packet(observed_at=NOW + timedelta(seconds=6))
            clock(monkeypatch, NOW + timedelta(seconds=6))
            assert revised.candles_sha256 == evidence.candles_sha256
            submit(engine, settings, revised)
    assert counts(engine) == before


@pytest.mark.parametrize("mode", ["normal", "recovery"])
def test_raw_processing_cannot_drop_source_binding(engine, settings, monkeypatch, mode):
    initialize(engine, settings, monkeypatch)
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    processor = NativeBarProcessor(engine, settings)
    bar = {**bars()[-1], "timestamp": NOW}
    with pytest.raises(NativeBarError, match="source_binding_dropped"):
        if mode == "normal":
            processor.process_next(bar, scope=spec(), signal=None)
        else:
            processor.recover_next(bar, scope=spec())
    assert counts(engine)["native_bar_outcomes"] == 1


@pytest.mark.parametrize("purpose", ["CLOSED_BAR", "RECOVERY"])
def test_resume_cannot_initialize_a_stream(engine, settings, monkeypatch, purpose):
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    with pytest.raises(NativeBarError, match="source_seed_or_resume"):
        submit(engine, settings, next_packet(), purpose=purpose)
    assert not any(counts(engine).values())


@pytest.mark.parametrize("purpose", ["CLOSED_BAR", "RECOVERY"])
def test_resume_cannot_consume_a_multi_candle_batch(engine, settings, monkeypatch, purpose):
    initialize(engine, settings, monkeypatch)
    before = counts(engine)
    with pytest.raises(NativeBarError, match="source_resume_requires_one"):
        submit(engine, settings, packet(), purpose=purpose)
    assert counts(engine) == before


def test_seed_cannot_reset_an_existing_stream(engine, settings, monkeypatch):
    initialize(engine, settings, monkeypatch)
    history = bars() + [{**bars()[-1], "timestamp": NOW}]
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    with pytest.raises(NativeBarError, match="source_seed_or_resume"):
        submit(engine, settings, packet(history))
    assert counts(engine)["native_bar_outcomes"] == 1


@pytest.mark.parametrize("kind", ["future_receipt", "stale", "gap", "warmup", "scope"])
def test_timing_scope_continuity_and_warmup_guards_are_not_relaxed(
    engine, settings, monkeypatch, kind
):
    evidence = packet()
    now = NOW + timedelta(seconds=5)
    purpose = "SEED"
    scope = spec()
    if kind == "future_receipt":
        now = NOW
    elif kind == "stale":
        now = NOW + timedelta(seconds=181)
    elif kind == "scope":
        scope = spec(feed_id="binance_spot_public")
    elif kind == "warmup":
        evidence = packet([bars()[-1]])
    else:
        initialize(engine, settings, monkeypatch)
        evidence = next_packet(1)
        now = NOW + STEP * 2 + timedelta(seconds=5)
        purpose = "CLOSED_BAR"
    clock(monkeypatch, now)
    before = counts(engine)
    with pytest.raises(ValueError):
        submit(engine, settings, evidence, purpose=purpose, scope=scope)
    assert counts(engine) == before


def test_transport_label_does_not_authorize_forward_evidence_or_entries(
    engine, settings, monkeypatch
):
    evidence = packet().model_copy(update={"transport": "public_https"})
    clock(monkeypatch, NOW + timedelta(seconds=5))
    result = submit(engine, settings, evidence, scope=spec(feed_id="binance_spot_public"))
    receipt = audit(engine)[0][1]
    assert result.outcome == "SOURCE_OBSERVED_NO_ENTRY"
    assert receipt.source_origin_verified is False
    assert receipt.public_source.forward_qualifying is False
    assert counts(engine)["paper_orders"] == 0


def test_private_transaction_entry_guard_cannot_be_bypassed_with_source_packet(
    engine, settings, monkeypatch
):
    clock(monkeypatch, NOW + timedelta(seconds=5))
    binding = bind_public_source(packet(), "SEED")
    with pytest.raises(NativeBarError, match="prohibits_entry"):
        NativeBarProcessor(engine, settings)._process(
            bars(), next_bar=None, scope=spec(), signal=native_payload(), public_source=binding
        )
    assert not any(counts(engine).values())


def test_late_clock_recheck_rolls_back_source_and_seed(engine, settings, monkeypatch):
    times = iter(
        [NOW + timedelta(seconds=5), NOW + timedelta(seconds=5), NOW + timedelta(seconds=181)]
    )
    monkeypatch.setattr("aurex.signal_gateway.native_processing.utc_now", lambda: next(times))
    with pytest.raises(ValueError, match="source_observation_is_stale"):
        submit(engine, settings, packet())
    assert not any(counts(engine).values())


@pytest.mark.parametrize("fault", ["receipt_flush", "outer_commit", "acknowledgement"])
def test_source_seed_and_receipt_are_atomic_across_failure_and_retry(
    engine, settings, monkeypatch, fault
):
    evidence = packet()
    clock(monkeypatch, NOW + timedelta(seconds=5))

    def fail(session, *_):
        if not session.in_nested_transaction():
            raise RuntimeError("injected transaction fault")

    event_name = {
        "receipt_flush": "before_flush",
        "outer_commit": "before_commit",
        "acknowledgement": "after_commit",
    }[fault]
    event.listen(Session, event_name, fail)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            submit(engine, settings, evidence)
    finally:
        event.remove(Session, event_name, fail)
    expected = int(fault == "acknowledgement")
    assert counts(engine)["native_bar_outcomes"] == expected
    assert counts(engine)["native_history_seeds"] == expected
    result = submit(engine, settings, evidence)
    assert result.is_duplicate == bool(expected)
    assert audit(engine)[0][1].public_source.acquisition == evidence


@pytest.mark.parametrize("different_witness", [False, True])
def test_competing_workers_do_not_replace_a_committed_source(
    engine, settings, monkeypatch, different_witness
):
    evidence = packet()
    other = packet(observed_at=NOW + timedelta(seconds=6)) if different_witness else evidence
    clock(monkeypatch, NOW + timedelta(seconds=7))
    barrier = Barrier(2)

    def worker(packet):
        barrier.wait(timeout=10)
        try:
            return submit(engine, settings, packet)
        except NativeBarError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [evidence, other]))
    assert counts(engine)["native_bar_outcomes"] == 1
    if different_witness:
        assert results.count("processed_bar_source_changed") == 1
    else:
        assert sorted(result.is_duplicate for result in results) == [False, True]
        assert results[0].evidence_hash == results[1].evidence_hash


@pytest.mark.parametrize(
    "damage",
    [
        "raw_body",
        "acquisition_hash",
        "normalized_hash",
        "purpose",
        "missing_source",
        "scope",
        "origin_claim",
        "entry_outcome",
        "future_observation",
        "rehashed_warmup",
    ],
)
def test_rehashed_source_corruption_is_reconstructed_not_trusted(
    engine, settings, monkeypatch, damage
):
    evidence, _ = initialize(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeBarOutcome)).one()
        data = json.loads(json.dumps(row.evidence))
        source = data["public_source"]
        acquisition = source["acquisition"]
        if damage == "raw_body":
            acquisition["pages"][0]["body"] += " "
        elif damage == "acquisition_hash":
            source["acquisition_sha256"] = "0" * 64
        elif damage == "normalized_hash":
            acquisition["candles_sha256"] = "0" * 64
        elif damage == "purpose":
            source["purpose"] = "CLOSED_BAR"
        elif damage == "missing_source":
            data.pop("public_source")
        elif damage == "scope":
            acquisition["symbol"] = "ETHUSDT"
        elif damage == "origin_claim":
            data["source_origin_verified"] = True
        elif damage == "entry_outcome":
            data["outcome"] = row.outcome = "PAPER_EXECUTED"
        elif damage == "future_observation":
            later = packet(observed_at=NOW + timedelta(seconds=6))
            source["acquisition"] = acquisition = later.model_dump(mode="json")
        else:
            changed = bars()
            changed[0]["high"] = "102"
            revised = packet(changed)
            source["acquisition"] = acquisition = revised.model_dump(mode="json")
        if damage != "acquisition_hash":
            source["acquisition_sha256"] = content_hash(acquisition)
        row.evidence = data
        row.evidence_hash = content_hash(data)
    before = counts(engine)
    with pytest.raises(ValueError):
        submit(engine, settings, evidence)
    assert counts(engine) == before


def test_receipt_and_retained_seed_cannot_disagree_on_warmup(engine, settings, monkeypatch):
    evidence, _ = initialize(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeHistorySeed)).one()
        data = json.loads(json.dumps(row.evidence))
        data["candles"][0]["high"] = "102"
        row.evidence = data
        row.evidence_hash = content_hash(data)
    with pytest.raises(NativeBarError, match="checkpoint_mismatch"):
        submit(engine, settings, evidence)


def test_paged_audit_rejects_a_rehashed_downgrade_to_legacy_receipts(engine, settings, monkeypatch):
    monkeypatch.setattr("aurex.signal_gateway.native_processing.CHAIN_PAGE_SIZE", 2)
    initialize(engine, settings, monkeypatch)
    for offset in range(4):
        clock(monkeypatch, NOW + STEP * (offset + 1) + timedelta(seconds=5))
        submit(engine, settings, next_packet(offset), purpose="CLOSED_BAR")
    assert len(audit(engine)) == 5
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeBarOutcome).where(NativeBarOutcome.sequence == 5)).one()
        data = {
            **row.evidence,
            "schema_version": "native_bar_processing_v1",
            "outcome": "NO_SIGNAL",
        }
        data.pop("public_source")
        row.evidence = data
        row.outcome = "NO_SIGNAL"
        row.evidence_hash = content_hash(data)
    with pytest.raises(NativeBarError, match="source_binding_dropped"):
        audit(engine)


def test_legacy_history_is_not_rewritten_when_source_is_attached_later(
    engine, settings, monkeypatch
):
    first = process(engine, settings)
    with Session(engine) as session:
        original = session.get(NativeBarOutcome, first.receipt_id).evidence
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    second = submit(engine, settings, next_packet(), purpose="CLOSED_BAR")
    with Session(engine) as session:
        chain = validate_chain(session)
        assert chain[0][0].evidence == original
        assert chain[0][0].evidence_hash == first.evidence_hash
        assert chain[0][1].public_source is None
        assert receipt_evidence(NativeBarReceipt.model_validate(original)) == original
        assert chain[1][1].public_source is not None
        assert chain[1][1].source_origin_verified is False
    assert second.source_purpose == "CLOSED_BAR"
    assert process(engine, settings).receipt_id == first.receipt_id


def test_source_recovery_closes_existing_legacy_position_without_forward_promotion(
    engine, settings, monkeypatch, qualified_fixture
):
    process(engine, settings, signal=native_payload())
    now = NOW + timedelta(days=1)
    clock(monkeypatch, now)
    evidence = packet([{**bars()[-1], "timestamp": NOW, "low": "90"}], observed_at=now)
    result = submit(engine, settings, evidence, purpose="RECOVERY")
    assert result.recovery_disposition == "CLOSED"
    assert result.outcome == "RECOVERY_NO_ENTRY"
    with Session(engine) as session:
        receipt = validate_chain(session)[-1][1]
        assert receipt.public_source.purpose == "RECOVERY"
        assert receipt.recovery.forward_qualifying is False
        assert session.scalars(select(PaperTrade)).one().status == TradeStatus.CLOSED
        assert session.scalars(select(PaperOrder)).one().fill_model == RECOVERY_FILL_MODEL
    assert submit(engine, settings, evidence, purpose="RECOVERY").is_duplicate
    assert counts(engine)["paper_trades"] == 1


def test_observation_cannot_skip_exit_management_for_an_open_position(
    engine, settings, monkeypatch, qualified_fixture
):
    process(engine, settings, signal=native_payload())
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    before = counts(engine)
    with pytest.raises(NativeBarError, match="requires_exit_only"):
        submit(engine, settings, next_packet(), purpose="CLOSED_BAR")
    assert counts(engine) == before


@pytest.mark.parametrize("fault", ["before_flush", "before_commit"])
def test_recovery_source_and_close_rollback_together(
    engine, settings, monkeypatch, qualified_fixture, fault
):
    process(engine, settings, signal=native_payload())
    now = NOW + timedelta(days=1)
    clock(monkeypatch, now)
    evidence = packet([{**bars()[-1], "timestamp": NOW, "low": "90"}], observed_at=now)

    def fail(session, *_):
        if fault == "before_commit" or any(
            isinstance(row, NativeBarOutcome) for row in session.new
        ):
            raise RuntimeError("injected close rollback")

    event.listen(Session, fault, fail)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            submit(engine, settings, evidence, purpose="RECOVERY")
    finally:
        event.remove(Session, fault, fail)
    assert counts(engine)["native_bar_outcomes"] == 1
    with Session(engine) as session:
        trade = session.scalars(select(PaperTrade)).one()
        assert trade.status == TradeStatus.OPEN and trade.closed_at is None
    assert submit(engine, settings, evidence, purpose="RECOVERY").recovery_disposition == "CLOSED"


def test_source_receipts_continue_past_legacy_window_without_reseeding(
    engine, settings, monkeypatch
):
    seed, first = initialize(engine, settings, monkeypatch, count=4096)
    clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
    second = submit(engine, settings, next_packet(), purpose="CLOSED_BAR")
    receipt = audit(engine)[-1][1]
    assert receipt.continuation.bar_count == 4097
    assert receipt.schema_version == "native_bar_processing_v4"
    assert second.checkpoint.schema_version == "native_closed_bar_continuation_v1"
    assert submit(engine, settings, seed).evidence_hash == first.evidence_hash


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_subprocess_death_keeps_source_seed_and_outcome_atomic(
    engine, settings, monkeypatch, tmp_path, phase
):
    evidence = packet()
    clock(monkeypatch, NOW + timedelta(seconds=5))
    path = tmp_path / "fixture-source.json"
    write_public_evidence(evidence, path)
    script = """
import os, sys
from datetime import timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from aurex.config.settings import Settings
from aurex.signal_gateway.native_market_data import read_public_evidence
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW
from pathlib import Path
native.utc_now = lambda: NOW + timedelta(seconds=5)
engine = create_engine(sys.argv[1])
event.listen(Session, sys.argv[3], lambda *args: os._exit(73))
native.NativeBarProcessor(engine, Settings(_env_file=None, live_trading_enabled=False,
    live_execution_adapter='disabled')).process_sourced(
    read_public_evidence(Path(sys.argv[2])), scope=spec(), purpose='SEED')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(engine.url), str(path), phase],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 73, result.stderr
    expected = int(phase == "after_commit")
    assert counts(engine)["native_bar_outcomes"] == expected
    assert counts(engine)["native_history_seeds"] == expected
    retry = submit(engine, settings, evidence)
    assert retry.is_duplicate == bool(expected)
    assert audit(engine)[0][1].public_source.acquisition == evidence


@pytest.mark.parametrize(
    "setting,value", [("live_trading_enabled", True), ("live_execution_adapter", "paper")]
)
def test_source_path_keeps_live_configuration_guard(engine, settings, setting, value):
    with pytest.raises(ValueError, match="live execution"):
        submit(engine, settings.model_copy(update={setting: value}), packet())
    assert not any(counts(engine).values())


def test_input_snapshot_cannot_change_while_waiting_for_the_transaction(
    engine, settings, monkeypatch
):
    evidence = packet()
    original = evidence.model_dump(mode="json")
    clock(monkeypatch, NOW + timedelta(seconds=5))

    def change_caller_object(connection, cursor, statement, *args):
        if statement == "BEGIN IMMEDIATE":
            object.__setattr__(evidence, "candles_sha256", "0" * 64)

    event.listen(engine, "before_cursor_execute", change_caller_object)
    try:
        submit(engine, settings, evidence)
    finally:
        event.remove(engine, "before_cursor_execute", change_caller_object)
    receipt = audit(engine)[0][1]
    assert receipt.public_source.acquisition.model_dump(mode="json") == original
    assert receipt.public_source.acquisition_sha256 == content_hash(original)


def test_fresh_process_resumes_from_retained_source_without_original_files(
    engine, settings, monkeypatch
):
    initialize(engine, settings, monkeypatch)
    script = """
import sys
from datetime import timedelta
from sqlalchemy import create_engine
from aurex.config.settings import Settings
import aurex.signal_gateway.native_processing as native
from tests.integration.test_native_source_binding import next_packet
from tests.integration.test_native_bar_processing import spec
from tests.unit.test_native_closed_bars import NOW, STEP
native.utc_now = lambda: NOW + STEP + timedelta(seconds=5)
engine = create_engine(sys.argv[1])
processor = native.NativeBarProcessor(engine, Settings(_env_file=None,
    live_trading_enabled=False, live_execution_adapter='disabled'))
result = processor.process_sourced(next_packet(), scope=spec(), purpose='CLOSED_BAR')
assert result.outcome == 'SOURCE_OBSERVED_NO_ENTRY' and not result.is_duplicate
assert result.checkpoint.bar_count == 18
assert processor.process_sourced(next_packet(), scope=spec(), purpose='CLOSED_BAR').is_duplicate
engine.dispose()
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(engine.url)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert counts(engine)["native_bar_outcomes"] == 2
    assert audit(engine)[1][1].public_source.purpose == "CLOSED_BAR"


@pytest.mark.parametrize("damage", ["explicit_null", "source_on_legacy", "mode"])
def test_receipt_shape_and_legacy_bytes_remain_strict(engine, settings, monkeypatch, damage):
    evidence, _ = initialize(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        row = session.scalars(select(NativeBarOutcome)).one()
        data = json.loads(json.dumps(row.evidence))
        if damage == "explicit_null":
            data["continuation"] = None
        elif damage == "source_on_legacy":
            data["schema_version"] = "native_bar_processing_v1"
        else:
            data["public_source"]["purpose"] = "RECOVERY"
        row.evidence = data
        row.evidence_hash = content_hash(data)
    with pytest.raises(ValueError):
        submit(engine, settings, evidence)


def test_source_recovery_can_hold_then_close_under_entry_kill_switch(
    engine, settings, monkeypatch, qualified_fixture
):
    from aurex.risk_engine.service import RiskEngine

    process(engine, settings, signal=native_payload())
    with Session(engine) as session, session.begin():
        RiskEngine(session).get_or_create_default_profile()[1].kill_switch_enabled = True
    now = NOW + timedelta(days=1)
    clock(monkeypatch, now)
    held = packet([{**bars()[-1], "timestamp": NOW}], observed_at=now)
    assert submit(engine, settings, held, purpose="RECOVERY").recovery_disposition == "HELD"
    second = packet([{**bars()[-1], "timestamp": NOW + STEP, "low": "90"}], observed_at=now)
    assert submit(engine, settings, second, purpose="RECOVERY").recovery_disposition == "CLOSED"
    assert submit(engine, settings, held, purpose="RECOVERY").is_duplicate
    receipts = audit(engine)
    assert receipts[-1][1].public_source.acquisition == second
    assert counts(engine)["paper_orders"] == 1
