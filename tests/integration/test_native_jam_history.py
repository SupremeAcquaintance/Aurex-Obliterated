"""Synthetic ledgers only: settings-bound reconstruction, never strategy activation."""

import json
import subprocess
import sys
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, create_mock_engine, delete, event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from aurex.backtest_engine.service import strategy_parameter_fingerprint
from aurex.db.models import NativeBarOutcome, NativeHistorySeed
from aurex.signal_gateway.native_bars import ClosedBar, NativeBarError, content_hash
from aurex.signal_gateway.native_jam_features import advance_jam_features, initialize_jam_features
from aurex.signal_gateway.native_jam_history import (
    NativeJamHistoryReader,
    bind_jam_feature_parameters,
)
from aurex.signal_gateway.native_observation import NativePublicObserver
from aurex.signal_gateway.native_processing import NativeBarProcessor, NativeStreamSpec
from tests.integration.test_jam_reversal_spot_replay import jam_parameters
from tests.integration.test_native_bar_processing import clock, counts, process, spec
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_observation import acquisition
from tests.integration.test_native_signal_intake import NOW
from tests.integration.test_native_signal_intake import settings as settings
from tests.integration.test_native_source_binding import packet
from tests.unit.test_native_closed_bars import STEP, bars


def jam_scope(parameters=None, **changes):
    parameters = jam_parameters() if parameters is None else parameters
    return spec(
        strategy="jam_reversal_spot_v1",
        strategy_version="1.0.1",
        settings_fingerprint=strategy_parameter_fingerprint("jam_reversal_spot_v1", parameters),
        **changes,
    )


def snapshot(engine, settings, **changes):
    return NativeJamHistoryReader(engine, settings).snapshot(
        **{"scope": jam_scope(), "strategy_parameters": jam_parameters(), **changes}
    )


def advance(engine, settings, monkeypatch, offset=0, scope=None):
    clock(monkeypatch, NOW + (offset + 1) * STEP)
    bar = {**bars()[-1], "timestamp": NOW + offset * STEP, "volume": str(offset + 2)}
    result = NativeBarProcessor(engine, settings).process_next(
        bar, scope=scope or jam_scope(), signal=None
    )
    return result, ClosedBar.model_validate(bar)


def test_canonical_jam_fingerprint_preserves_internal_spaces_and_exact_bytes():
    scope = jam_scope()
    assert "direction_mode=Long only" in scope.settings_fingerprint
    assert NativeStreamSpec.model_validate_json(scope.model_dump_json()) == scope
    assert bind_jam_feature_parameters(scope, jam_parameters()).trend_ema == 5


@pytest.mark.parametrize("value", ["", " ", " a", "a ", "a\tb", "a\nb", "a\x00b", "x" * 2001])
def test_stream_fingerprint_rejects_blank_outer_whitespace_controls_and_excess_length(value):
    with pytest.raises(ValidationError):
        spec(settings_fingerprint=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trend_ema", 7),
        ("use_atr_trail", True),
        ("risk_per_trade_percent", "0.4"),
        ("backtest_end", "2026-01-02T00:00:00Z"),
    ],
)
def test_entire_settings_contract_is_bound_not_just_feature_lengths(field, value):
    with pytest.raises(NativeBarError, match="fingerprint_mismatch"):
        bind_jam_feature_parameters(jam_scope(), {**jam_parameters(), field: value})


@pytest.mark.parametrize("change", ["missing", "extra", "fraction", "bool", "infinite", "enum"])
def test_invalid_full_settings_fail_closed(change):
    parameters = jam_parameters()
    if change == "missing":
        parameters.pop("use_atr_trail")
    elif change == "extra":
        parameters["undocumented_override"] = True
    elif change == "fraction":
        parameters["confirm_window_bars"] = 2.5
    elif change == "bool":
        parameters["trend_ema"] = True
    elif change == "infinite":
        parameters["reward_risk"] = float("inf")
    else:
        parameters["stop_mode"] = "invented"
    with pytest.raises(NativeBarError, match="settings_(keys_)?invalid"):
        bind_jam_feature_parameters(jam_scope(), parameters)


@pytest.mark.parametrize("field,value", [("higher_timeframe", "240"), ("trend_ema", 501)])
def test_unsupported_native_feature_scope_is_not_silently_coerced(field, value):
    parameters = {**jam_parameters(), field: value}
    with pytest.raises(ValidationError):
        bind_jam_feature_parameters(jam_scope(parameters), parameters)


def test_wrong_strategy_or_version_is_not_reinterpreted_as_jam():
    for scope in (spec(), jam_scope().model_copy(update={"strategy_version": "1.0.2"})):
        with pytest.raises(NativeBarError, match="contract_unsupported"):
            bind_jam_feature_parameters(scope, jam_parameters())


def test_snapshot_matches_replayable_history_without_any_write(engine, settings, monkeypatch):
    first = process(engine, settings, scope=jam_scope())
    latest, bar = advance(engine, settings, monkeypatch)
    before = counts(engine)
    statements = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())

    event.listen(Engine, "before_cursor_execute", record_sql)
    try:
        result = snapshot(engine, settings, expected_head_hash=latest.evidence_hash)
    finally:
        event.remove(Engine, "before_cursor_execute", record_sql)
    expected = initialize_jam_features(
        [*(ClosedBar.model_validate(b) for b in bars()), bar],
        bind_jam_feature_parameters(jam_scope(), jam_parameters()),
    )
    assert result.feature_state == expected
    assert result.head_receipt_id == latest.receipt_id != first.receipt_id
    assert result.head_evidence_hash == latest.evidence_hash
    assert result.checkpoint == latest.checkpoint
    assert result.settings_sha256 == content_hash(jam_scope().settings_fingerprint)
    assert not result.source_bound_from_seed and not result.observed_online_from_seed
    assert not result.source_origin_verified and not result.execution_authority
    assert not result.forward_qualifying
    assert statements[:2] == ["PRAGMA", "BEGIN"]
    assert set(statements) <= {"PRAGMA", "BEGIN", "SELECT"}
    assert counts(engine) == before
    assert before["signals"] == before["paper_orders"] == before["paper_trades"] == 0
    assert snapshot(engine, settings) == result


def test_missing_stream_and_changed_scope_or_expected_head_reject(engine, settings):
    with pytest.raises(NativeBarError, match="requires_initialized"):
        snapshot(engine, settings)
    process(engine, settings, scope=jam_scope())
    with pytest.raises(NativeBarError, match="expected_head_changed"):
        snapshot(engine, settings, expected_head_hash="0" * 64)
    changed = {**jam_parameters(), "trend_ema": 6}
    with pytest.raises(NativeBarError, match="stream_scope_mismatch"):
        snapshot(engine, settings, scope=jam_scope(changed), strategy_parameters=changed)
    with pytest.raises(NativeBarError, match="stream_scope_mismatch"):
        snapshot(engine, settings, scope=jam_scope(feed_id="binance_spot_public"))


def test_paged_continuation_rebuilds_from_seed_without_changing_old_receipts(
    engine, settings, monkeypatch
):
    first = process(engine, settings, bars(4096), scope=jam_scope())
    with Session(engine) as session:
        old_bytes = session.scalar(select(NativeBarOutcome)).evidence
    expected = initialize_jam_features(
        [ClosedBar.model_validate(b) for b in bars(4096)],
        bind_jam_feature_parameters(jam_scope(), jam_parameters()),
    )
    monkeypatch.setattr("aurex.signal_gateway.native_processing.CHAIN_PAGE_SIZE", 2)
    for offset in range(5):
        latest, bar = advance(engine, settings, monkeypatch, offset)
        expected = advance_jam_features(expected, bar)
    result = snapshot(engine, settings)
    assert result.feature_state == expected
    assert result.feature_state.bar_count == 4101
    assert len(result.feature_state.recent) <= 501
    assert result.head_evidence_hash == latest.evidence_hash
    with Session(engine) as session:
        old = session.get(NativeBarOutcome, first.receipt_id)
        assert old.evidence == old_bytes and old.evidence_hash == first.evidence_hash


@pytest.mark.parametrize("damage", ["missing_seed", "rehashed_seed", "middle_gap", "head_hash"])
def test_corrupt_history_rejects_without_ledger_effects(engine, settings, monkeypatch, damage):
    process(engine, settings, scope=jam_scope())
    advance(engine, settings, monkeypatch)
    latest, _ = advance(engine, settings, monkeypatch, 1)
    with Session(engine) as session, session.begin():
        seed = session.scalar(select(NativeHistorySeed))
        if damage == "missing_seed":
            session.delete(seed)
        elif damage == "rehashed_seed":
            data = json.loads(json.dumps(seed.evidence))
            data["candles"][0]["volume"] = "9"
            seed.evidence = {**data}
            seed.evidence_hash = content_hash(data)
        elif damage == "middle_gap":
            session.execute(delete(NativeBarOutcome).where(NativeBarOutcome.sequence == 2))
        else:
            session.get(NativeBarOutcome, latest.receipt_id).evidence_hash = "0" * 64
    before = counts(engine)
    with pytest.raises(ValueError):
        snapshot(engine, settings)
    assert counts(engine) == before


def test_rehashed_generic_indicator_cache_is_reconstructed_before_jam(
    engine, settings, monkeypatch
):
    process(engine, settings, bars(4096), scope=jam_scope())
    latest, _ = advance(engine, settings, monkeypatch)
    with Session(engine) as session, session.begin():
        row = session.get(NativeBarOutcome, latest.receipt_id)
        data = {**row.evidence, "continuation": {**row.evidence["continuation"], "atr": "3"}}
        row.evidence = data
        row.evidence_hash = content_hash(data)
    with pytest.raises(NativeBarError, match="continuation_reconstruction_mismatch"):
        snapshot(engine, settings)


@pytest.mark.parametrize("mode", ["import", "owned", "late_source"])
def test_source_metadata_does_not_promote_origin_or_forward_authority(
    engine, settings, monkeypatch, mode
):
    scope = jam_scope(feed_id="binance_spot_public")
    if mode == "owned":
        acquisition(monkeypatch)
        NativePublicObserver(engine, settings).observe(scope=scope, seed_count=17)
    elif mode == "import":
        clock(monkeypatch, NOW + timedelta(seconds=5))
        NativeBarProcessor(engine, settings).process_sourced(
            packet().model_copy(update={"transport": "public_https"}), scope=scope, purpose="SEED"
        )
    else:
        process(engine, settings, scope=scope)
        clock(monkeypatch, NOW + STEP + timedelta(seconds=5))
        NativeBarProcessor(engine, settings).process_sourced(
            packet([{**bars()[-1], "timestamp": NOW}]).model_copy(
                update={"transport": "public_https"}
            ),
            scope=scope,
            purpose="CLOSED_BAR",
        )
    result = snapshot(engine, settings, scope=scope)
    assert result.source_bound_from_seed == (mode != "late_source")
    assert result.observed_online_from_seed == (mode == "owned")
    assert not result.source_origin_verified and not result.forward_qualifying
    assert not result.execution_authority


def test_one_snapshot_is_pinned_across_a_concurrent_wal_append(engine, settings, monkeypatch):
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
    first = process(engine, settings, scope=jam_scope())
    import aurex.signal_gateway.native_jam_history as module

    original = module.verified_native_history
    appended = []

    def append_after_first_audit(session, requested_open):
        result = original(session, requested_open)
        if not appended:
            appended.append(advance(engine, settings, monkeypatch)[0])
        return result

    monkeypatch.setattr(module, "verified_native_history", append_after_first_audit)
    pinned = snapshot(engine, settings, expected_head_hash=first.evidence_hash)
    assert pinned.head_evidence_hash == first.evidence_hash
    assert pinned.feature_state.bar_count == 17
    assert snapshot(engine, settings).head_evidence_hash == appended[0].evidence_hash
    with pytest.raises(NativeBarError, match="expected_head_changed"):
        snapshot(engine, settings, expected_head_hash=first.evidence_hash)


def test_new_process_reconstructs_without_caller_state_cache(engine, settings):
    process(engine, settings, scope=jam_scope())
    expected = snapshot(engine, settings)
    script = """
import sys
from sqlalchemy import create_engine
from aurex.config.settings import Settings
from tests.integration.test_native_jam_history import snapshot
engine = create_engine(sys.argv[1])
settings = Settings(_env_file=None, live_trading_enabled=False, live_execution_adapter='disabled')
result = snapshot(engine, settings)
assert not result.execution_authority
print(result.feature_state.model_dump_json())
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
    assert completed.stdout.strip() == expected.feature_state.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        {"live_trading_enabled": True},
        {"live_execution_adapter": "anything_else"},
    ],
)
def test_live_configuration_rejects_before_reading(engine, settings, change):
    with pytest.raises(NativeBarError, match="requires_live_disabled"):
        snapshot(engine, settings.model_copy(update=change))


def test_read_is_not_postgresql_support(settings):
    with pytest.raises(ValueError, match="SQLite"):
        NativeJamHistoryReader(create_mock_engine("postgresql://", lambda *args: None), settings)


@pytest.mark.parametrize("clear_query_only", [False, True])
def test_storage_enforces_read_only_even_if_an_audit_helper_attempts_a_write(
    engine, settings, monkeypatch, clear_query_only
):
    process(engine, settings, scope=jam_scope())
    before = counts(engine)

    def attempt_write(session, requested_open):
        if clear_query_only:
            session.execute(text("PRAGMA query_only=OFF"))
        session.execute(delete(NativeBarOutcome))
        pytest.fail("a read-only history connection allowed a DELETE")

    monkeypatch.setattr(
        "aurex.signal_gateway.native_jam_history.verified_native_history", attempt_write
    )
    with pytest.raises(OperationalError, match="readonly"):
        snapshot(engine, settings)
    assert counts(engine) == before
    # The private read connection must not change the writer pool's permissions.
    advance(engine, settings, monkeypatch)
    assert counts(engine)["native_bar_outcomes"] == 2


def test_missing_database_is_not_created_and_memory_database_is_not_supported(tmp_path, settings):
    path = tmp_path / "absent.db"
    missing = create_engine(f"sqlite:///{path.as_posix()}")
    memory = create_engine("sqlite://")
    try:
        with pytest.raises(OperationalError):
            snapshot(missing, settings)
        assert not path.exists()
        with pytest.raises(NativeBarError, match="file_backed_sqlite"):
            snapshot(memory, settings)
    finally:
        missing.dispose()
        memory.dispose()
