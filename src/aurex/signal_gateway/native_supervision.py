"""Bounded, cooperative local supervision. No migrations, live orders or qualification.

The database receipts are authoritative after restart. Run journals describe process
operation only; a missing terminal event must never be interpreted as a clean stop.
"""

import json
import os
import re
import shutil
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Literal

from pydantic import Field, model_validator
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import NativeBarOutcome
from aurex.signal_gateway.native_bars import NativeBarError, aware_utc, content_hash
from aurex.signal_gateway.native_jam_features import FeatureModel
from aurex.signal_gateway.native_jam_runtime import JamRuntimeConfig
from aurex.signal_gateway.native_market_data import MAX_BATCH_SECONDS, PublicDataError
from aurex.signal_gateway.native_observation import NativePublicObserver
from aurex.signal_gateway.native_processing import NativeStreamSpec

MINIMUM_FREE_BYTES = 1_073_741_824
MAX_JOURNAL_BYTES = 16 * 1024 * 1024


class NativeSupervisorConfig(FeatureModel):
    mode: Literal["OBSERVE", "JAM", "EXIT_ONLY"]
    scope: NativeStreamSpec
    jam: JamRuntimeConfig | None = None
    seed_count: int = Field(default=1000, strict=True, ge=1, le=4096)
    max_run_seconds: int = Field(default=3600, strict=True, ge=120, le=86400)
    max_processed_bars: int = Field(default=96, strict=True, ge=1, le=10000)
    max_receipts: int = Field(default=4096, strict=True, ge=1, le=10000)
    max_database_bytes: int = Field(
        default=268_435_456, strict=True, ge=1_048_576, le=2_147_483_648
    )
    max_consecutive_retries: int = Field(default=3, strict=True, ge=0, le=5)

    @model_validator(mode="after")
    def mode_binding(self):
        if self.scope.feed_id != "binance_spot_public":
            raise ValueError("supervisor_requires_public_feed")
        if (self.mode == "JAM") != (self.jam is not None):
            raise ValueError("supervisor_jam_config_mode_mismatch")
        if self.jam is not None:
            self.jam.bind(self.scope)
        return self


class NativeSupervisorResult(FeatureModel):
    schema_version: Literal["native_supervisor_run_v1"] = "native_supervisor_run_v1"
    status: Literal["STOPPED", "BLOCKED"]
    reason: str
    processed_bars: int = Field(ge=0)
    attempts: int = Field(ge=0)
    last_receipt_hash: str | None = None
    config_hash: str
    source_origin_verified: Literal[False] = False
    forward_qualifying: Literal[False] = False
    live_authority: Literal[False] = False


class NativeRunJournalAudit(FeatureModel):
    status: Literal["TERMINAL", "INCOMPLETE"]
    event_count: int
    config_hash: str
    terminal: NativeSupervisorResult | None
    database_reconciled: Literal[False] = False
    source_origin_verified: Literal[False] = False
    forward_qualifying: Literal[False] = False
    live_authority: Literal[False] = False


def audit_run_journal(directory: Path) -> NativeRunJournalAudit:
    """Read-only structural audit, not database reconciliation or proof of process death."""
    path = directory / "events.jsonl"
    if not 0 < path.stat().st_size <= MAX_JOURNAL_BYTES:
        raise NativeBarError("supervisor_journal_size_invalid")
    previous = terminal = digest = last_receipt = None
    processed = count = observations = 0
    total_bytes = 0
    with path.open("rb") as handle:
        while line := handle.readline(262145):
            total_bytes += len(line)
            count += 1
            if total_bytes > MAX_JOURNAL_BYTES or len(line) > 262144 or not line.endswith(b"\n"):
                raise NativeBarError("supervisor_journal_incomplete_line")
            item = json.loads(line)
            if not isinstance(item, dict) or set(item) != {"evidence", "hash"}:
                raise NativeBarError("supervisor_journal_shape_invalid")
            evidence = item["evidence"]
            if (
                not isinstance(evidence, dict)
                or set(evidence)
                != {"schema_version", "sequence", "previous_hash", "recorded_at", "kind", "payload"}
                or evidence["schema_version"] != "native_supervisor_event_v1"
                or type(evidence["sequence"]) is not int
                or evidence["sequence"] != count
                or evidence["previous_hash"] != previous
                or item["hash"] != content_hash(evidence)
                or terminal is not None
            ):
                raise NativeBarError("supervisor_journal_chain_invalid")
            previous = item["hash"]
            aware_utc(datetime.fromisoformat(evidence["recorded_at"]))
            kind, payload = evidence["kind"], evidence["payload"]
            if count == 1:
                if kind != "STARTED":
                    raise NativeBarError("supervisor_journal_start_missing")
                config = NativeSupervisorConfig.model_validate(payload["config"])
                digest = content_hash(config.model_dump(mode="json"))
                if payload["config_hash"] != digest:
                    raise NativeBarError("supervisor_journal_config_mismatch")
            elif kind == "BAR_COMMITTED":
                if (
                    type(payload.get("duplicate")) is not bool
                    or payload.get("forward_qualifying") is not False
                ):
                    raise NativeBarError("supervisor_journal_bar_invalid")
                last_receipt = payload["receipt_hash"]
                if not re.fullmatch(r"[0-9a-f]{64}", last_receipt):
                    raise NativeBarError("supervisor_journal_receipt_hash_invalid")
                processed += not payload["duplicate"]
                observations += 1
            elif kind in {"WAITING_FOR_CLOSE", "RETRY_WAIT"}:
                observations += 1
            elif kind == "PUBLIC_DATA_FAILURE":
                if not isinstance(payload, dict) or "reason" not in payload:
                    raise NativeBarError("supervisor_journal_failure_invalid")
            elif kind == "TERMINAL":
                terminal = NativeSupervisorResult.model_validate(payload)
                if (
                    terminal.config_hash != digest
                    or terminal.processed_bars != processed
                    or terminal.last_receipt_hash != last_receipt
                    or not observations <= terminal.attempts <= observations + 1
                ):
                    raise NativeBarError("supervisor_journal_terminal_mismatch")
            else:
                raise NativeBarError("supervisor_journal_event_invalid")
    return NativeRunJournalAudit(
        status="TERMINAL" if terminal else "INCOMPLETE",
        event_count=count,
        config_hash=digest,
        terminal=terminal,
    )


@contextmanager
def exclusive_runner(database: Path):
    """OS-held advisory lock survives stale lock files, never inferred PID liveness."""
    path = database.with_name(database.name + ".native-runner.lock")
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise NativeBarError("supervisor_already_running_or_lock_unavailable") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RunJournal:
    def __init__(self, directory: Path):
        # Never truncate a previous run, including an interrupted run's evidence.
        directory.mkdir(parents=False, exist_ok=False)
        self.handle = (directory / "events.jsonl").open("xb")
        self.previous_hash = None
        self.sequence = 0

    def append(self, kind: str, payload: dict):
        evidence = {
            "schema_version": "native_supervisor_event_v1",
            "sequence": self.sequence + 1,
            "previous_hash": self.previous_hash,
            "recorded_at": aware_utc(utc_now()).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        digest = content_hash(evidence)
        rendered = (
            json.dumps({"evidence": evidence, "hash": digest}, sort_keys=True) + "\n"
        ).encode()
        if self.handle.tell() + len(rendered) > MAX_JOURNAL_BYTES:
            raise NativeBarError("supervisor_journal_capacity_reached")
        self.handle.write(rendered)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.sequence += 1
        self.previous_hash = digest

    def close(self):
        self.handle.close()


def database_path(engine: Engine) -> Path:
    if (
        engine.dialect.name != "sqlite"
        or engine.url.query
        or not engine.url.database
        or engine.url.database == ":memory:"
    ):
        raise NativeBarError("supervisor_requires_existing_file_database")
    path = Path(engine.url.database).resolve(strict=True)
    if not path.is_file():
        raise NativeBarError("supervisor_requires_existing_file_database")
    return path


def resource_check(engine: Engine, database: Path, directory: Path, config: NativeSupervisorConfig):
    for parent in {database.parent, directory.parent}:
        if shutil.disk_usage(parent).free < MINIMUM_FREE_BYTES:
            raise NativeBarError("supervisor_insufficient_free_disk")
    size = sum(
        path.stat().st_size
        for path in (
            database,
            Path(str(database) + "-wal"),
            Path(str(database) + "-journal"),
            Path(str(database) + "-shm"),
        )
        if path.exists()
    )
    if size >= config.max_database_bytes:
        raise NativeBarError("supervisor_database_capacity_reached")
    with Session(engine) as session:
        count = session.scalar(select(func.count()).select_from(NativeBarOutcome))
    if count >= config.max_receipts:
        raise NativeBarError("supervisor_receipt_capacity_reached")


def retry_delay(exc: PublicDataError, retries: int) -> float | None:
    transient = str(exc) in {"public_transport_failed", "public_request_deadline_exceeded"}
    transient |= exc.status == 429 or (exc.status is not None and 500 <= exc.status <= 599)
    if not transient:
        return None
    # A server's Retry-After is a lower bound, never shortened to fit our run.
    return float(max(5 * 2 ** (retries - 1), exc.retry_after or 0))


def error_code(exc: Exception) -> str:
    code = str(exc)
    if isinstance(exc, NativeBarError) and re.fullmatch(r"[a-z0-9_]{1,160}", code):
        return code
    return type(exc).__name__


def run_native_supervisor(
    engine: Engine,
    settings: Settings,
    config: NativeSupervisorConfig,
    *,
    run_directory: Path,
    stop: Event,
) -> NativeSupervisorResult:
    """Stop cooperatively between bounded acquisitions; never liquidate on shutdown.

    A stop request does not abort an in-flight atomic transaction. Public acquisition
    retains its 90-second batch bound, and shutdown follows its success/failure.
    """
    config = NativeSupervisorConfig.model_validate_json(config.model_dump_json())
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        raise NativeBarError("supervisor_requires_live_disabled")
    database = database_path(engine)
    tables = set(inspect(engine).get_table_names())
    if not {"native_bar_outcomes", "native_history_seeds"} <= tables:
        raise NativeBarError("supervisor_requires_existing_native_schema")
    directory = run_directory.resolve()
    digest = content_hash(config.model_dump(mode="json"))
    observer = NativePublicObserver(engine, settings)
    processed = attempts = retries = 0
    last_hash = None
    started = monotonic()
    wall_start = aware_utc(utc_now())
    next_poll = wall_start
    status, reason = "STOPPED", "operator_stop"
    with exclusive_runner(database):
        journal = RunJournal(directory)
        try:
            journal.append(
                "STARTED", {"config": config.model_dump(mode="json"), "config_hash": digest}
            )
            while not stop.is_set() and not (directory / "STOP").exists():
                elapsed = monotonic() - started
                now = aware_utc(utc_now())
                if elapsed < 0 or abs((now - wall_start).total_seconds() - elapsed) > 2:
                    raise NativeBarError("supervisor_wall_clock_changed")
                if elapsed >= config.max_run_seconds:
                    reason = "run_duration_reached"
                    break
                resource_check(engine, database, directory, config)
                if now < next_poll:
                    stop.wait(
                        min(
                            2.0, (next_poll - now).total_seconds(), config.max_run_seconds - elapsed
                        )
                    )
                    continue
                if config.max_run_seconds - elapsed < MAX_BATCH_SECONDS + 5:
                    reason = "insufficient_run_time_for_acquisition"
                    break
                attempts += 1
                try:
                    if config.mode == "JAM":
                        outcome = observer.evaluate_jam(
                            scope=config.scope,
                            config=config.jam.model_dump(mode="json"),
                            seed_count=config.seed_count,
                        )
                    elif config.mode == "EXIT_ONLY":
                        outcome = observer.manage_exits(scope=config.scope)
                    else:
                        outcome = observer.observe(scope=config.scope, seed_count=config.seed_count)
                except PublicDataError as exc:
                    clock_evidence = exc.clock.model_dump(mode="json") if exc.clock else None
                    # Retain normal time responses; never let diagnostic text exhaust the journal.
                    if clock_evidence is not None and len(clock_evidence["body"]) > 4096:
                        clock_evidence = {
                            key: value for key, value in clock_evidence.items() if key != "body"
                        }
                        clock_evidence["body_omitted_for_size"] = True
                    journal.append(
                        "PUBLIC_DATA_FAILURE",
                        {
                            "reason": error_code(exc),
                            "http_status": exc.status,
                            "retry_after_seconds": exc.retry_after,
                            "clock_observation": clock_evidence,
                        },
                    )
                    retries += 1
                    delay = retry_delay(exc, retries)
                    if delay is None or retries > config.max_consecutive_retries:
                        raise
                    journal.append(
                        "RETRY_WAIT",
                        {
                            "reason": error_code(exc),
                            "http_status": exc.status,
                            "delay_seconds": delay,
                            "consecutive_retries": retries,
                        },
                    )
                    if (
                        monotonic() - started + delay + MAX_BATCH_SECONDS + 5
                        > config.max_run_seconds
                    ):
                        status, reason = "BLOCKED", "retry_exceeds_run_deadline"
                        break
                    next_poll = aware_utc(utc_now()) + timedelta(seconds=delay)
                    continue
                retries = 0
                next_poll = outcome.next_observation_at
                if outcome.processing is not None:
                    last_hash = outcome.processing.evidence_hash
                    if not outcome.processing.is_duplicate:
                        processed += 1
                    journal.append(
                        "BAR_COMMITTED",
                        {
                            "receipt_id": outcome.processing.receipt_id,
                            "receipt_hash": last_hash,
                            "duplicate": outcome.processing.is_duplicate,
                            "outcome": outcome.processing.outcome,
                            "forward_qualifying": False,
                        },
                    )
                else:
                    journal.append(
                        "WAITING_FOR_CLOSE", {"next_observation_at": next_poll.isoformat()}
                    )
                if processed >= config.max_processed_bars:
                    reason = "processed_bar_limit_reached"
                    break
        except (NativeBarError, ValueError, OSError, SQLAlchemyError) as exc:
            status, reason = "BLOCKED", error_code(exc)
        except KeyboardInterrupt:
            reason = "operator_interrupt"
        except Exception as exc:
            # Unexpected failures are terminal, not a license to retry unknown effects.
            status, reason = "BLOCKED", error_code(exc)
        finally:
            result = NativeSupervisorResult(
                status=status,
                reason=reason,
                processed_bars=processed,
                attempts=attempts,
                last_receipt_hash=last_hash,
                config_hash=digest,
            )
            try:
                journal.append("TERMINAL", result.model_dump(mode="json"))
            finally:
                journal.close()
    return result
