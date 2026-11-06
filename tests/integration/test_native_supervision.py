"""Bounded supervisor fixtures, not public-feed operation or qualifying paper evidence."""

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from aurex.signal_gateway import native_supervision as supervision
from aurex.signal_gateway.native_bars import NativeBarError, content_hash
from aurex.signal_gateway.native_market_data import PublicDataError
from aurex.signal_gateway.native_supervision import (
    NativeSupervisorConfig,
    audit_run_journal,
    exclusive_runner,
    run_native_supervisor,
)
from tests.integration.test_native_bar_processing import counts
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_observation import acquisition, scope
from tests.integration.test_native_signal_intake import NOW
from tests.integration.test_native_signal_intake import settings as settings


def configuration(**changes):
    return NativeSupervisorConfig(
        mode="OBSERVE", scope=scope(), seed_count=17, max_processed_bars=1, **changes
    )


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(seconds=0)
    monkeypatch.setattr(supervision, "monotonic", lambda: clock.seconds)
    monkeypatch.setattr(supervision, "utc_now", lambda: NOW + timedelta(seconds=5 + clock.seconds))
    return clock


class VirtualStop:
    def __init__(self, clock, stop_after=None):
        self.clock, self.stop_after = clock, stop_after
        self.stopped = False
        self.waits = []

    def is_set(self):
        return self.stopped

    def wait(self, delay):
        self.waits.append(delay)
        self.clock.seconds += delay
        if self.stop_after is not None and self.clock.seconds >= self.stop_after:
            self.stopped = True
        return self.stopped


def events(directory):
    records = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    previous = None
    for index, item in enumerate(records, 1):
        assert item["hash"] == content_hash(item["evidence"])
        assert item["evidence"]["previous_hash"] == previous
        assert item["evidence"]["sequence"] == index
        previous = item["hash"]
    return [item["evidence"] for item in records]


def run(engine, settings, tmp_path, config=None, stop=None, name="run"):
    return run_native_supervisor(
        engine,
        settings,
        config or configuration(),
        run_directory=tmp_path / name,
        stop=stop or Event(),
    )


def test_real_observer_fixture_commits_and_stops_without_authority(
    engine, settings, tmp_path, monkeypatch, clock
):
    acquisition(monkeypatch)
    result = run(engine, settings, tmp_path)
    assert result.status == "STOPPED" and result.reason == "processed_bar_limit_reached"
    assert result.processed_bars == result.attempts == 1
    assert not result.forward_qualifying and not result.live_authority
    assert counts(engine)["native_bar_outcomes"] == 1 and counts(engine)["paper_orders"] == 0
    log = events(tmp_path / "run")
    assert [e["kind"] for e in log] == ["STARTED", "BAR_COMMITTED", "TERMINAL"]
    assert log[-1]["payload"] == result.model_dump(mode="json")


def test_restart_uses_receipts_and_cooperative_stop_does_not_refetch(
    engine, settings, tmp_path, monkeypatch, clock
):
    source = acquisition(monkeypatch)
    run(engine, settings, tmp_path)
    result = run(engine, settings, tmp_path, name="restart", stop=VirtualStop(clock, stop_after=2))
    assert result.reason == "operator_stop" and result.processed_bars == 0
    assert len(source.calls) == 1
    assert counts(engine)["native_bar_outcomes"] == 1
    assert events(tmp_path / "restart")[1]["kind"] == "WAITING_FOR_CLOSE"


def test_existing_journal_never_overwritten(engine, settings, tmp_path, monkeypatch, clock):
    acquisition(monkeypatch)
    run(engine, settings, tmp_path)
    before = (tmp_path / "run" / "events.jsonl").read_bytes()
    with pytest.raises(FileExistsError):
        run(engine, settings, tmp_path)
    assert (tmp_path / "run" / "events.jsonl").read_bytes() == before


def test_os_lock_refuses_second_owner_and_allows_release(
    engine, settings, tmp_path, monkeypatch, clock
):
    source = acquisition(monkeypatch)
    with exclusive_runner(Path(engine.url.database)):
        with pytest.raises(NativeBarError, match="already_running"):
            run(engine, settings, tmp_path)
    assert source.calls == []
    assert run(engine, settings, tmp_path).processed_bars == 1


def test_missing_schema_never_migrates_or_fetches(tmp_path, settings, monkeypatch, clock):
    import sqlite3

    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        source = acquisition(monkeypatch)
        with pytest.raises(NativeBarError, match="existing_native_schema"):
            run(engine, settings, tmp_path)
        assert source.calls == [] and not (tmp_path / "run").exists()
    finally:
        engine.dispose()


@pytest.mark.parametrize("kind", ["disk", "database", "receipts", "clock"])
def test_resource_and_clock_failures_stop_before_fetch(
    engine, settings, tmp_path, monkeypatch, clock, kind
):
    source = acquisition(monkeypatch)
    config = configuration()
    if kind == "disk":
        monkeypatch.setattr(supervision.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    elif kind == "database":
        config = configuration(max_database_bytes=1_048_576)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE supervisor_capacity_fixture (padding BLOB)")
            connection.exec_driver_sql(
                "INSERT INTO supervisor_capacity_fixture VALUES (zeroblob(1048576))"
            )
    elif kind == "receipts":
        run(engine, settings, tmp_path, name="seed")
        source.calls.clear()
        config = configuration(max_receipts=1)
    else:
        times = iter([NOW, NOW + timedelta(seconds=20), NOW + timedelta(seconds=20)])
        monkeypatch.setattr(
            supervision, "utc_now", lambda: next(times, NOW + timedelta(seconds=20))
        )
    result = run(engine, settings, tmp_path, config)
    assert result.status == "BLOCKED" and source.calls == []


@pytest.mark.parametrize(
    "status,retry_after,expected_calls,reason",
    [
        (429, 30, 2, "processed_bar_limit_reached"),
        (503, None, 2, "processed_bar_limit_reached"),
        (418, None, 1, "public_http_rejected"),
        (429, 100000, 1, "retry_exceeds_run_deadline"),
    ],
)
def test_retry_policy_honors_server_delay_without_busy_loop(
    engine, settings, tmp_path, monkeypatch, clock, status, retry_after, expected_calls, reason
):
    calls = []

    def observe(*a, **kw):
        calls.append(clock.seconds)
        if len(calls) == 1:
            raise PublicDataError("public_http_rejected", status=status, retry_after=retry_after)
        return SimpleNamespace(
            next_observation_at=NOW + timedelta(hours=1),
            processing=SimpleNamespace(
                evidence_hash="a" * 64,
                receipt_id="fixture",
                is_duplicate=False,
                outcome="SOURCE_OBSERVED_NO_ENTRY",
            ),
        )

    monkeypatch.setattr(supervision.NativePublicObserver, "observe", observe)
    result = run(engine, settings, tmp_path, stop=VirtualStop(clock))
    assert len(calls) == expected_calls and result.reason == reason
    if expected_calls == 2:
        assert calls[1] >= (retry_after or 5)
    events(tmp_path / "run")


def test_unexpected_failure_is_blocked_not_reported_as_clean_stop(
    engine, settings, tmp_path, monkeypatch, clock
):
    def fail(*a, **kw):
        raise RuntimeError("secret-like exception contents must not enter the journal")

    monkeypatch.setattr(supervision.NativePublicObserver, "observe", fail)
    result = run(engine, settings, tmp_path)
    assert result.status == "BLOCKED" and result.reason == "RuntimeError"
    assert "secret-like" not in (tmp_path / "run" / "events.jsonl").read_text()


@pytest.mark.parametrize(
    "changes", [{"max_run_seconds": 0}, {"max_receipts": True}, {"mode": "JAM"}]
)
def test_invalid_supervisor_config_cannot_relax_bounds(changes):
    data = configuration().model_dump(mode="json")
    data.update(changes)
    with pytest.raises(ValidationError):
        NativeSupervisorConfig.model_validate(data)


def test_journal_independent_audit_and_interrupted_prefix(
    engine, settings, tmp_path, monkeypatch, clock
):
    acquisition(monkeypatch)
    result = run(engine, settings, tmp_path)
    audit = audit_run_journal(tmp_path / "run")
    assert audit.status == "TERMINAL" and audit.terminal == result
    assert not audit.database_reconciled and not audit.source_origin_verified
    journal = tmp_path / "run" / "events.jsonl"
    lines = journal.read_bytes().splitlines(keepends=True)
    journal.write_bytes(b"".join(lines[:-1]))
    incomplete = audit_run_journal(tmp_path / "run")
    assert incomplete.status == "INCOMPLETE" and incomplete.terminal is None
    # A partial write is corruption/incomplete data, never a terminal success.
    journal.write_bytes(b"".join(lines[:-1]) + lines[-1][:20])
    with pytest.raises(NativeBarError, match="incomplete_line"):
        audit_run_journal(tmp_path / "run")


def test_rehashed_terminal_cannot_invent_committed_bars(
    engine, settings, tmp_path, monkeypatch, clock
):
    acquisition(monkeypatch)
    run(engine, settings, tmp_path)
    journal = tmp_path / "run" / "events.jsonl"
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    records[-1]["evidence"]["payload"]["processed_bars"] = 10
    records[-1]["hash"] = content_hash(records[-1]["evidence"])
    journal.write_text("".join(json.dumps(row) + "\n" for row in records))
    with pytest.raises(NativeBarError, match="terminal_mismatch"):
        audit_run_journal(tmp_path / "run")


@pytest.mark.parametrize("kind", ["stop_file", "interrupt", "stale", "retry_exhausted"])
def test_shutdown_and_nonretryable_failure_paths(
    engine, settings, tmp_path, monkeypatch, clock, kind
):
    calls = []

    def observe(*a, **kw):
        calls.append(clock.seconds)
        if kind == "interrupt":
            raise KeyboardInterrupt
        if kind == "stale":
            raise NativeBarError("observation_window_missed_requires_reconciliation")
        if kind == "retry_exhausted":
            raise PublicDataError("public_transport_failed")
        (tmp_path / "run" / "STOP").touch()
        return SimpleNamespace(next_observation_at=NOW + timedelta(hours=1), processing=None)

    monkeypatch.setattr(supervision.NativePublicObserver, "observe", observe)
    result = run(engine, settings, tmp_path, stop=VirtualStop(clock))
    assert result.status == ("STOPPED" if kind in {"stop_file", "interrupt"} else "BLOCKED")
    assert len(calls) == (4 if kind == "retry_exhausted" else 1)
    assert counts(engine)["native_bar_outcomes"] == 0
    assert audit_run_journal(tmp_path / "run").terminal == result


def test_cross_process_lock_is_held_by_os_not_stale_file(engine):
    database = Path(engine.url.database)
    command = [
        sys.executable,
        "-c",
        """
import sys
from pathlib import Path
from aurex.signal_gateway.native_supervision import exclusive_runner
with exclusive_runner(Path(sys.argv[1])):
    print('acquired')
""",
        str(database),
    ]
    with exclusive_runner(database):
        blocked = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert blocked.returncode != 0 and "already_running_or_lock_unavailable" in blocked.stderr
    acquired = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert acquired.returncode == 0 and acquired.stdout.strip() == "acquired"


def test_live_settings_refused_before_new_run_directory(engine, settings, tmp_path):
    with pytest.raises(NativeBarError, match="requires_live_disabled"):
        run(engine, settings.model_copy(update={"live_trading_enabled": True}), tmp_path)
    assert not (tmp_path / "run").exists()


def test_readonly_database_audit_reconciles_journal_without_writing(
    engine, settings, tmp_path, monkeypatch, clock
):
    from scripts.audit_native_supervisor import audit_database

    acquisition(monkeypatch)
    run(engine, settings, tmp_path)
    database = Path(engine.url.database)
    before = database.read_bytes()
    result = audit_database(database, tmp_path / "run")
    assert result["status"] == "PASS" and result["database_reconciled"]
    assert result["run_status"] == "STOPPED"
    assert result["run_new_receipt_count"] == result["database_receipt_count"] == 1
    assert result["database_counts"] == {"signals": 0, "paper_orders": 0, "paper_trades": 0}
    assert not result["platform_acceptance"] and not result["forward_qualifying"]
    assert database.read_bytes() == before


def test_readonly_audit_rejects_rehashed_journal_reference_not_in_database(
    engine, settings, tmp_path, monkeypatch, clock
):
    from scripts.audit_native_supervisor import audit_database

    acquisition(monkeypatch)
    run(engine, settings, tmp_path)
    journal = tmp_path / "run" / "events.jsonl"
    records = [json.loads(line) for line in journal.read_text().splitlines()]
    records[1]["evidence"]["payload"]["receipt_id"] = "not-in-database"
    previous = None
    for row in records:
        row["evidence"]["previous_hash"] = previous
        row["hash"] = content_hash(row["evidence"])
        previous = row["hash"]
    journal.write_text("".join(json.dumps(row) + "\n" for row in records))
    assert audit_run_journal(tmp_path / "run").status == "TERMINAL"
    with pytest.raises(NativeBarError, match="journal_database_mismatch"):
        audit_database(Path(engine.url.database), tmp_path / "run")


def test_clock_rejection_retains_diagnostic_without_retry(
    engine, settings, tmp_path, monkeypatch, clock
):
    packet = acquisition(monkeypatch).evidence

    def reject(*a, **kw):
        raise PublicDataError("public_server_clock_skew", clock=packet.clock)

    monkeypatch.setattr(supervision.NativePublicObserver, "observe", reject)
    result = run(engine, settings, tmp_path)
    assert result.status == "BLOCKED" and result.attempts == 1
    log = events(tmp_path / "run")
    assert log[1]["kind"] == "PUBLIC_DATA_FAILURE"
    assert log[1]["payload"]["clock_observation"] == packet.clock.model_dump(mode="json")
    assert audit_run_journal(tmp_path / "run").terminal == result
