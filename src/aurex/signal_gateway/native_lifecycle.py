"""Private ownership of a bounded native child, never live execution authority."""

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aurex.config.settings import Settings
from aurex.db.backup import file_hash
from aurex.db.recovery_bundle import CONFIG_FIELDS, configuration, regular
from aurex.db.recovery_environment import clean_environment
from aurex.signal_gateway.native_bars import content_hash
from aurex.signal_gateway.native_market_data import MAX_BATCH_SECONDS
from aurex.signal_gateway.native_supervision import NativeSupervisorConfig, audit_run_journal
from aurex.strategy_engine.registry import strategy_lifecycle_allows_enable

ROOT = Path(__file__).resolve().parents[3]
SHUTDOWN_SECONDS = MAX_BATCH_SECONDS + 30
MAX_MANAGED_RUNS = 32


class NativeLifecycleError(ValueError):
    pass


def source_hash() -> str:
    paths = sorted((ROOT / "src/aurex").rglob("*.py")) + [ROOT / "scripts/run_native_supervisor.py"]
    if not 1 <= len(paths) <= 2048:
        raise NativeLifecycleError("managed_source_inventory_invalid")
    digest = sha256()
    total = 0
    for path in paths:
        regular(path)
        total += path.stat().st_size
        if total > 64 * 1024 * 1024:
            raise NativeLifecycleError("managed_source_inventory_too_large")
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
        digest.update(file_hash(path).encode() + b"\n")
    return digest.hexdigest()


class ManagedNativeLaunch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["native_managed_launch_v1"] = "native_managed_launch_v1"
    instance_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    database: str
    database_device: int = Field(strict=True)
    database_inode: int = Field(strict=True)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings: dict
    config: NativeSupervisorConfig
    live_authority: Literal[False] = False

    @model_validator(mode="after")
    def safe_settings(self):
        if set(self.settings) != CONFIG_FIELDS:
            raise ValueError("managed_settings_schema_invalid")
        if configuration(Settings(_env_file=None, **self.settings)) != self.settings:
            raise ValueError("managed_settings_invalid")
        if not Path(self.database).is_absolute():
            raise ValueError("managed_absolute_database_required")
        return self

    def check_current(self):
        database = Path(self.database)
        regular(database)
        if not database.is_file() or (database.stat().st_dev, database.stat().st_ino) != (
            self.database_device,
            self.database_inode,
        ):
            raise NativeLifecycleError("managed_database_identity_changed")
        if source_hash() != self.source_sha256:
            raise NativeLifecycleError("managed_source_changed")
        if self.config.mode == "JAM" and not strategy_lifecycle_allows_enable(
            self.config.scope.strategy
        ):
            raise NativeLifecycleError("managed_strategy_not_eligible")


class NativeControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_instance_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    expected_run_id: str | None = Field(pattern=r"^[0-9a-f]{32}$")
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")


def read_managed_launch(path: Path, expected_hash: str) -> ManagedNativeLaunch:
    regular(path)
    if not 0 < path.stat().st_size <= 262144 or file_hash(path) != expected_hash:
        raise NativeLifecycleError("managed_launch_hash_or_size_invalid")
    launch = ManagedNativeLaunch.model_validate_json(path.read_bytes())
    launch.check_current()
    return launch


def write_private_json(path: Path, value: dict):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, sort_keys=True, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


class NativeSupervisorController:
    """Only a Popen handle establishes child liveness; journals establish evidence."""

    def __init__(self, database, settings, config, directory, instance_id, *, recheck):
        self.database = database.resolve(strict=True)
        self.settings = settings.model_copy(deep=True)
        self.config = NativeSupervisorConfig.model_validate_json(config.model_dump_json())
        self.directory = directory.resolve()
        self.instance_id = instance_id
        self.recheck = recheck
        self._source_hash = source_hash()
        self._identity = (self.database.stat().st_dev, self.database.stat().st_ino)
        self._lock = RLock()
        self._child = None
        self._run_id = None
        self._requests = {}
        self._run_count = 0
        self._state = "IDLE"
        self._reason = "not_started_by_this_service"
        self._result = None
        self._closed = False
        self._forced = False
        self._journal_verified = False
        self._initialized = False
        self._control_log_failed = False

    def _launch(self):
        return ManagedNativeLaunch(
            instance_id=self.instance_id,
            run_id=self._run_id,
            database=str(self.database),
            database_device=self._identity[0],
            database_inode=self._identity[1],
            source_sha256=self._source_hash,
            settings=configuration(self.settings),
            config=self.config,
        )

    def _record(self, kind, **payload):
        try:
            with (self.directory / "control.jsonl").open(
                "a", encoding="utf-8", newline="\n"
            ) as log:
                log.write(
                    json.dumps(
                        {
                            "kind": kind,
                            "instance_id": self.instance_id,
                            "run_id": self._run_id,
                            "live_authority": False,
                            **payload,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                log.flush()
                os.fsync(log.fileno())
        except OSError:
            # Logging failures forbid more starts, but must not suppress a protective stop.
            self._control_log_failed = True
            return False
        return True

    def _refresh(self):
        if self._child is None or self._state not in {"PROCESS_RUNNING", "STOP_REQUESTED"}:
            return
        code = self._child.poll()
        if code is None:
            return
        self._close_pipe()
        self._state, self._reason = "BLOCKED", "managed_exit_evidence_unverified"
        self._journal_verified = False
        try:
            audit = audit_run_journal(self.directory / self._run_id / "run")
            result = audit.terminal
            expected = content_hash(self.config.model_dump(mode="json"))
            if (
                not self._forced
                and result is not None
                and audit.config_hash == expected
                and code == (0 if result.status == "STOPPED" else 1)
            ):
                self._journal_verified = True
                self._result = result.model_dump(mode="json")
                self._state, self._reason = result.status, result.reason
        except Exception:
            pass
        if self._forced:
            self._reason = "managed_forced_shutdown"
        self._record(
            "EXITED",
            exit_code=code,
            state=self._state,
            reason=self._reason,
            journal_verified=self._journal_verified,
            forced=self._forced,
        )

    def status(self):
        with self._lock:
            self._refresh()
            alive = self._child is not None and self._child.poll() is None
            eligible = self.config.mode != "JAM" or strategy_lifecycle_allows_enable(
                self.config.scope.strategy
            )
            return {
                "configured": True,
                "instance_id": self.instance_id,
                "run_id": self._run_id,
                "state": self._state,
                "reason": self._reason if eligible else "managed_strategy_not_eligible",
                "mode": self.config.mode,
                "config_hash": content_hash(self.config.model_dump(mode="json")),
                "process_alive": alive,
                "pid": self._child.pid if alive else None,
                "can_start": (
                    not self._closed
                    and not self._control_log_failed
                    and not alive
                    and eligible
                    and self._run_count < MAX_MANAGED_RUNS
                    and (self._state == "IDLE" or self._journal_verified)
                ),
                "can_stop": alive and not self._closed,
                "journal_verified": self._journal_verified,
                "last_result": self._result,
                "forced_shutdown": self._forced,
                "control_journal_failed": self._control_log_failed,
                "external_process_status": "NOT_OBSERVED",
                "forward_qualifying": False,
                "live_authority": False,
                "max_run_seconds": self.config.max_run_seconds,
                "max_processed_bars": self.config.max_processed_bars,
                "shutdown_grace_seconds": SHUTDOWN_SECONDS,
                "remaining_starts": MAX_MANAGED_RUNS - self._run_count,
            }

    def _check_request(self, request):
        if request.expected_instance_id != self.instance_id:
            raise NativeLifecycleError("managed_instance_mismatch")
        if self._closed:
            raise NativeLifecycleError("managed_service_shutting_down")

    def start(self, request: NativeControlRequest):
        with self._lock:
            self._check_request(request)
            self._refresh()
            identity = request.model_dump(mode="json")
            if request.request_id in self._requests:
                if self._requests[request.request_id] != identity:
                    raise NativeLifecycleError("managed_request_id_conflict")
                return self.status()
            if request.expected_run_id != self._run_id:
                raise NativeLifecycleError("managed_run_mismatch")
            if not self.status()["can_start"]:
                raise NativeLifecycleError("managed_start_not_allowed")
            self.recheck()
            previous_run_id = self._run_id
            self._run_id = uuid4().hex
            try:
                launch = self._launch()
                launch.check_current()
            except Exception:
                self._run_id = previous_run_id
                raise
            if not self._initialized:
                self.directory.mkdir(parents=False, exist_ok=False)
                self._initialized = True
            regular(self.directory)
            operation = self.directory / self._run_id
            operation.mkdir(exist_ok=False)
            launch_path = operation / "launch.json"
            write_private_json(launch_path, launch.model_dump(mode="json"))
            self._requests[request.request_id] = identity
            self._run_count += 1
            self._journal_verified = False
            self._result = None
            self._forced = False
            if not self._record(
                "START_REQUESTED", config_hash=content_hash(self.config.model_dump(mode="json"))
            ):
                self._state, self._reason = "BLOCKED", "managed_control_journal_unavailable"
                raise NativeLifecycleError(self._reason)
            environment = clean_environment()
            environment["PYTHONPATH"] = str(ROOT / "src")
            self._child = None
            try:
                self._child = subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "scripts/run_native_supervisor.py"),
                        "--managed-launch",
                        str(launch_path),
                        "--managed-launch-sha256",
                        file_hash(launch_path),
                    ],
                    cwd=ROOT,
                    env=environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                self._state, self._reason = "PROCESS_RUNNING", "child_started_feed_unverified"
                self._child.stdin.write(b"G")
                self._child.stdin.flush()
            except Exception:
                self._close_pipe()
                if self._child is not None and self._child.poll() is None:
                    self._state, self._reason = "STOP_REQUESTED", "managed_start_delivery_failed"
                else:
                    self._state, self._reason = "BLOCKED", "managed_launch_failed"
                self._record("START_FAILED", state=self._state)
                raise NativeLifecycleError("managed_launch_failed") from None
            return self.status()

    def _close_pipe(self):
        if self._child is not None and self._child.stdin is not None:
            try:
                self._child.stdin.close()
            except OSError:
                pass

    def stop(self, request: NativeControlRequest):
        with self._lock:
            self._check_request(request)
            self._refresh()
            if request.expected_run_id != self._run_id or self._run_id is None:
                raise NativeLifecycleError("managed_run_mismatch")
            if self._child is not None and self._child.poll() is None:
                self._close_pipe()
                if self._state != "STOP_REQUESTED":
                    self._record("STOP_REQUESTED")
                self._state, self._reason = "STOP_REQUESTED", "cooperative_stop_pending"
            return self.status()

    def close(self) -> bool:
        with self._lock:
            self._closed = True
            self._refresh()
            child = self._child
            if child is None or child.poll() is not None:
                return (
                    not self._forced
                    and not self._control_log_failed
                    and (child is None or self._journal_verified)
                )
            self._close_pipe()
            self._state, self._reason = "STOP_REQUESTED", "service_shutdown"
            self._record("SERVICE_SHUTDOWN_REQUESTED")
        try:
            child.wait(timeout=SHUTDOWN_SECONDS)
        except subprocess.TimeoutExpired:
            with self._lock:
                self._forced = True
                self._record("FORCED_SHUTDOWN_REQUESTED")
            child.kill()
            child.wait(timeout=10)
        with self._lock:
            self._refresh()
            return not self._forced and not self._control_log_failed and self._journal_verified


def unconfigured_status(instance_id):
    return {
        "configured": False,
        "instance_id": instance_id,
        "run_id": None,
        "state": "UNCONFIGURED",
        "reason": "launch_time_configuration_required",
        "mode": None,
        "can_start": False,
        "can_stop": False,
        "process_alive": False,
        "external_process_status": "NOT_OBSERVED",
        "forward_qualifying": False,
        "live_authority": False,
    }
