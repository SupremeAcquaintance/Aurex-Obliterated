"""Owned-process lifecycle fixtures; no exchange requests or qualifying observations."""

import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aurex.api.private_runtime import create_private_app
from aurex.config.settings import get_settings
from aurex.db.backup import file_hash
from aurex.db.recovery_bundle import configuration as safe_configuration
from aurex.db.recovery_environment import clean_environment
from aurex.signal_gateway import native_lifecycle as lifecycle
from aurex.signal_gateway.native_bars import content_hash
from aurex.signal_gateway.native_supervision import NativeSupervisorResult, RunJournal
from tests.integration.test_native_jam_history import jam_scope
from tests.integration.test_native_jam_runtime import config as jam_config
from tests.integration.test_native_supervision import configuration
from tests.integration.test_private_runtime import migrated_template as migrated_template
from tests.integration.test_private_runtime import private_database as private_database


class ChildFixture:
    def __init__(self, command, **kwargs):
        self.launch_path = Path(command[command.index("--managed-launch") + 1])
        self.launch = lifecycle.ManagedNativeLaunch.model_validate_json(
            self.launch_path.read_bytes()
        )
        self.kwargs = kwargs
        self.stdin = io.BytesIO()
        self.pid = 9876
        self.returncode = None
        self.cooperative = True
        self.killed = False

    def poll(self):
        return self.returncode

    def finish(self, *, status="STOPPED", reason="operator_stop"):
        config = self.launch.config
        digest = content_hash(config.model_dump(mode="json"))
        journal = RunJournal(self.launch_path.parent / "run")
        journal.append("STARTED", {"config": config.model_dump(mode="json"), "config_hash": digest})
        journal.append(
            "TERMINAL",
            NativeSupervisorResult(
                status=status, reason=reason, processed_bars=0, attempts=0, config_hash=digest
            ).model_dump(mode="json"),
        )
        journal.close()
        self.returncode = 0 if status == "STOPPED" else 1

    def wait(self, timeout):
        if self.returncode is None:
            if not self.cooperative:
                raise subprocess.TimeoutExpired("fixture-child", timeout)
            assert self.stdin.closed
            self.finish()
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.fixture
def children(monkeypatch):
    children = []

    def spawn(*args, **kwargs):
        child = ChildFixture(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(lifecycle.subprocess, "Popen", spawn)
    return children


@pytest.fixture
def controller(private_database, tmp_path, children):
    ctl = lifecycle.NativeSupervisorController(
        private_database,
        get_settings(),
        configuration(),
        tmp_path / "native",
        uuid4().hex,
        recheck=lambda: None,
    )
    yield ctl
    ctl.close()


def request(ctl, **changes):
    return lifecycle.NativeControlRequest(
        **{
            "expected_instance_id": ctl.instance_id,
            "expected_run_id": ctl.status()["run_id"],
            "request_id": uuid4().hex,
            **changes,
        }
    )


def test_launch_is_secret_free_bound_and_idempotent(controller, children, monkeypatch):
    monkeypatch.setenv("BINANCE_API_SECRET", "must-not-reach-child")
    monkeypatch.setenv("AUREX_WEBHOOK_SECRET", "must-not-reach-child")
    req = request(controller)
    first = controller.start(req)
    assert first["state"] == "PROCESS_RUNNING" and first["process_alive"]
    assert not first["forward_qualifying"] and not first["live_authority"]
    assert not first["journal_verified"]
    assert controller.start(req)["run_id"] == first["run_id"]
    assert len(children) == 1
    child = children[0]
    assert child.stdin.getvalue() == b"G"
    assert "BINANCE_API_SECRET" not in child.kwargs["env"]
    assert "AUREX_WEBHOOK_SECRET" not in child.kwargs["env"]
    assert "webhook_secret" not in child.launch.settings
    assert child.launch.database == str(controller.database)
    assert child.launch.source_sha256 == lifecycle.source_hash()
    assert child.kwargs["stdout"] == subprocess.DEVNULL
    assert child.kwargs["stderr"] == subprocess.DEVNULL


def test_stop_is_pending_until_actual_exit_and_restart_is_explicit(controller, children):
    original = request(controller)
    controller.start(original)
    assert controller.stop(request(controller))["state"] == "STOP_REQUESTED"
    assert controller.status()["process_alive"]
    assert not controller.status()["can_start"]
    children[0].finish()
    terminal = controller.status()
    assert terminal["state"] == "STOPPED" and terminal["journal_verified"]
    assert not terminal["process_alive"] and terminal["can_start"]
    restarted = controller.start(request(controller))
    assert restarted["run_id"] != terminal["run_id"] and len(children) == 2
    assert controller.start(original)["run_id"] == restarted["run_id"]
    assert len(children) == 2


def test_stale_and_conflicting_controls_never_start_another_child(controller, children):
    initial = request(controller)
    controller.start(initial)
    with pytest.raises(lifecycle.NativeLifecycleError, match="run_mismatch"):
        controller.stop(request(controller, expected_run_id=uuid4().hex))
    with pytest.raises(lifecycle.NativeLifecycleError, match="instance_mismatch"):
        controller.stop(request(controller, expected_instance_id=uuid4().hex))
    with pytest.raises(lifecycle.NativeLifecycleError, match="request_id_conflict"):
        controller.start(request(controller, request_id=initial.request_id))
    with pytest.raises(lifecycle.NativeLifecycleError, match="start_not_allowed"):
        controller.start(request(controller))
    assert len(children) == 1


def test_concurrent_duplicate_starts_own_exactly_one_process(controller, children):
    req = request(controller)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: controller.start(req), range(8)))
    assert len({value["run_id"] for value in results}) == 1
    assert len(children) == 1


@pytest.mark.parametrize("code", [0, 1, -9])
def test_exit_without_journal_never_claims_clean_stop(controller, children, code):
    controller.start(request(controller))
    children[0].returncode = code
    status = controller.status()
    assert not status["process_alive"]
    assert status["state"] == "BLOCKED" and not status["journal_verified"]
    assert not status["can_start"]
    assert controller.close() is False


def test_corrupt_journal_blocks_restart(controller, children):
    controller.start(request(controller))
    children[0].finish()
    journal = children[0].launch_path.parent / "run/events.jsonl"
    journal.write_bytes(journal.read_bytes().replace(b'"STOPPED"', b'"BLOCKED"'))
    assert not controller.status()["can_start"]


def test_audited_blocked_result_is_not_feed_readiness(controller, children):
    controller.start(request(controller))
    children[0].finish(status="BLOCKED", reason="public_server_clock_skew")
    status = controller.status()
    assert status["reason"] == "public_server_clock_skew" and status["journal_verified"]
    assert not status["process_alive"] and not status["forward_qualifying"]


def test_forced_shutdown_is_recorded_as_failure(controller, children):
    controller.start(request(controller))
    children[0].cooperative = False
    assert controller.close() is False
    assert children[0].killed
    status = controller.status()
    assert status["forced_shutdown"] and not status["journal_verified"]
    assert status["reason"] == "managed_forced_shutdown" and not status["can_start"]


def test_settings_and_source_changes_reject_before_launch(controller, children, monkeypatch):
    monkeypatch.setattr(lifecycle, "source_hash", lambda: "0" * 64)
    with pytest.raises(lifecycle.NativeLifecycleError, match="source_changed"):
        controller.start(request(controller))
    assert not children and controller.status()["run_id"] is None


def test_database_replacement_rejects_before_launch(controller, children):
    original = controller.database
    original.rename(original.with_suffix(".saved"))
    original.write_bytes(b"not the same database")
    with pytest.raises(lifecycle.NativeLifecycleError, match="identity_changed"):
        controller.start(request(controller))
    assert not children


def test_launch_failure_is_latched_not_retried(controller, children, monkeypatch):
    monkeypatch.setattr(
        lifecycle.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError())
    )
    req = request(controller)
    with pytest.raises(lifecycle.NativeLifecycleError, match="launch_failed"):
        controller.start(req)
    assert controller.start(req)["state"] == "BLOCKED"
    assert not controller.status()["can_start"] and not children


def test_run_budget_is_finite(controller, children, monkeypatch):
    monkeypatch.setattr(lifecycle, "MAX_MANAGED_RUNS", 1)
    controller.start(request(controller))
    children[0].finish()
    assert controller.status()["remaining_starts"] == 0
    assert not controller.status()["can_start"]


def test_launch_model_rejects_live_or_secret_settings(private_database):
    settings = safe_configuration(get_settings())
    args = dict(
        instance_id=uuid4().hex,
        run_id=uuid4().hex,
        database=str(private_database),
        database_device=private_database.stat().st_dev,
        database_inode=private_database.stat().st_ino,
        source_sha256=lifecycle.source_hash(),
        config=configuration(),
    )
    for change in ({"live_trading_enabled": True}, {"webhook_secret": "secret"}):
        with pytest.raises(ValueError):
            lifecycle.ManagedNativeLaunch(**args, settings={**settings, **change})


def test_private_api_control_boundary_and_shutdown(private_database, tmp_path, children):
    app = create_private_app(
        8917, native_config=configuration(), native_directory=tmp_path / "api-native"
    )
    with TestClient(app, base_url="http://127.0.0.1:8917", client=("127.0.0.1", 50000)) as client:
        status = client.get("/system/native-supervisor").json()
        body = {
            "expected_instance_id": status["instance_id"],
            "expected_run_id": None,
            "request_id": uuid4().hex,
        }
        assert status["state"] == "IDLE" and not children
        assert client.post("/system/native-supervisor/start", json=body).status_code == 403
        headers = {"Origin": "http://127.0.0.1:8917"}
        assert (
            client.post(
                "/system/native-supervisor/start", json={**body, "mode": "JAM"}, headers=headers
            ).status_code
            == 422
        )
        response = client.post("/system/native-supervisor/start", json=body, headers=headers)
        assert response.status_code == 200 and response.json()["process_alive"]
        assert (
            client.post("/system/native-supervisor/start", json=body, headers=headers).json()[
                "run_id"
            ]
            == response.json()["run_id"]
        )
        assert len(children) == 1
    assert children[0].poll() == 0 and app.state.native_shutdown_clean


def test_private_api_unconfigured_cannot_start(private_database):
    app = create_private_app(8917)
    with TestClient(app, base_url="http://127.0.0.1:8917", client=("127.0.0.1", 50000)) as client:
        status = client.get("/system/native-supervisor").json()
        assert status["state"] == "UNCONFIGURED" and not status["can_start"]
        body = {
            "expected_instance_id": status["instance_id"],
            "expected_run_id": None,
            "request_id": uuid4().hex,
        }
        assert (
            client.post(
                "/system/native-supervisor/start", json=body, headers={"X-Aurex-Local-Request": "1"}
            ).status_code
            == 409
        )


def test_runtime_drift_still_allows_owned_status_and_protective_stop(
    private_database, tmp_path, children
):
    app = create_private_app(
        8917, native_config=configuration(), native_directory=tmp_path / "drift-native"
    )
    with TestClient(app, base_url="http://127.0.0.1:8917", client=("127.0.0.1", 50000)) as client:
        headers = {"X-Aurex-Local-Request": "1"}
        ctl = app.state.native_supervisor_controller
        body = request(ctl).model_dump(mode="json")
        assert (
            client.post("/system/native-supervisor/start", json=body, headers=headers).status_code
            == 200
        )
        settings = get_settings()
        settings.live_trading_enabled = True
        try:
            assert client.get("/system/private-runtime").status_code == 503
            assert (
                client.post(
                    "/system/native-supervisor/start", json=body, headers=headers
                ).status_code
                == 503
            )
            status = client.get("/system/native-supervisor").json()
            assert status["can_stop"] and not status["live_authority"]
            body = request(ctl).model_dump(mode="json")
            assert (
                client.post(
                    "/system/native-supervisor/stop",
                    json=body,
                    headers={**headers, "Origin": "https://attacker.example"},
                ).status_code
                == 403
            )
            assert not children[0].stdin.closed
            response = client.post("/system/native-supervisor/stop", json=body, headers=headers)
            assert response.status_code == 200 and children[0].stdin.closed
        finally:
            settings.live_trading_enabled = False
    assert app.state.native_shutdown_clean


def test_real_managed_child_eof_stops_before_any_acquisition(private_database, tmp_path):
    before = file_hash(private_database)
    launch = lifecycle.ManagedNativeLaunch(
        instance_id=uuid4().hex,
        run_id=uuid4().hex,
        database=str(private_database),
        database_device=private_database.stat().st_dev,
        database_inode=private_database.stat().st_ino,
        source_sha256=lifecycle.source_hash(),
        config=configuration(),
        settings=safe_configuration(get_settings()),
    )
    launch_path = tmp_path / "launch.json"
    lifecycle.write_private_json(launch_path, launch.model_dump(mode="json"))
    environment = clean_environment()
    environment["PYTHONPATH"] = str(lifecycle.ROOT / "src")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_native_supervisor.py",
            "--managed-launch",
            str(launch_path),
            "--managed-launch-sha256",
            file_hash(launch_path),
        ],
        cwd=lifecycle.ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["attempts"] == 0 and payload["status"] == "STOPPED"
    assert payload["processed_bars"] == 0 and not payload["live_authority"]
    assert file_hash(private_database) == before
    assert lifecycle.audit_run_journal(tmp_path / "run").terminal.attempts == 0


def test_retired_jam_cannot_be_started(private_database, tmp_path, children):
    jam = jam_config()
    config = lifecycle.NativeSupervisorConfig(
        mode="JAM", scope=jam_scope(jam.parameters, feed_id="binance_spot_public"), jam=jam
    )
    ctl = lifecycle.NativeSupervisorController(
        private_database,
        get_settings(),
        config,
        tmp_path / "jam",
        uuid4().hex,
        recheck=lambda: None,
    )
    assert not ctl.status()["can_start"]
    assert ctl.status()["reason"] == "managed_strategy_not_eligible"
    with pytest.raises(lifecycle.NativeLifecycleError, match="start_not_allowed"):
        ctl.start(request(ctl))
    assert not children and not ctl.directory.exists()
    assert ctl.close()


@pytest.mark.parametrize("during", ["start", "stop", "close"])
def test_log_failure_blocks_starts_but_never_prevents_stop(
    controller, children, monkeypatch, during
):
    original_open = Path.open
    if during != "start":
        controller.start(request(controller))

    def fail_control_log(path, *args, **kwargs):
        if path == controller.directory / "control.jsonl":
            raise OSError("fixture full disk")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_control_log)
    if during == "start":
        with pytest.raises(lifecycle.NativeLifecycleError, match="control_journal_unavailable"):
            controller.start(request(controller))
        assert not children
    elif during == "stop":
        assert controller.stop(request(controller))["state"] == "STOP_REQUESTED"
        assert children[0].stdin.closed
        children[0].finish()
    assert controller.close() is False
    assert controller.status()["control_journal_failed"]
    assert not controller.status()["can_start"]
    assert not controller.status()["process_alive"]


def test_failed_recheck_prevents_spawn(controller, children):
    def fail():
        raise lifecycle.NativeLifecycleError("managed_runtime_preflight_failed")

    controller.recheck = fail
    with pytest.raises(lifecycle.NativeLifecycleError, match="preflight_failed"):
        controller.start(request(controller))
    assert not children and controller.status()["run_id"] is None


@pytest.mark.parametrize("payload,code", [("{}", 2), ("", 2), (None, 0)])
def test_cli_check_validates_native_config_without_starting(
    private_database, tmp_path, capsys, payload, code
):
    from scripts.run_private_operator import main

    path = tmp_path / "config.json"
    path.write_text(configuration().model_dump_json() if payload is None else payload)
    assert (
        main(["--check", "--database", str(private_database), "--native-config", str(path)]) == code
    )
    report = json.loads(capsys.readouterr().out)
    assert report["live_authority"] is False
    if code == 0:
        assert report["native_supervisor_configured"] and report["native_mode"] == "OBSERVE"
        assert not report["starts_native_supervisor"]
    else:
        assert report["status"] == "BLOCKED"


@pytest.fixture
def real_wait_controllers(private_database, tmp_path, monkeypatch):
    # The acquisition substitute exists only under tests. Process/pipe/lock/journal are real.
    spawn = subprocess.Popen
    controllers = []

    def waiting_child(command, **kwargs):
        command = list(command)
        assert command[1] == str(lifecycle.ROOT / "scripts/run_native_supervisor.py")
        command[1] = str(lifecycle.ROOT / "tests/fixtures/native_managed_wait_child.py")
        launch_path = Path(command[command.index("--managed-launch") + 1])
        with (launch_path.parent / "fixture-child.log").open("xb") as log:
            kwargs.update(stdout=log, stderr=log)
            return spawn(command, **kwargs)

    monkeypatch.setattr(lifecycle.subprocess, "Popen", waiting_child)

    def create():
        ctl = lifecycle.NativeSupervisorController(
            private_database,
            get_settings(),
            configuration(),
            tmp_path / f"real-native-{len(controllers)}",
            uuid4().hex,
            recheck=lambda: None,
        )
        controllers.append(ctl)
        return ctl

    yield create
    for ctl in controllers:
        ctl.close()


def wait_for_owned_wait(ctl):
    path = ctl.directory / ctl.status()["run_id"] / "run/events.jsonl"
    deadline = monotonic() + 30
    while monotonic() < deadline:
        assert ctl._child.poll() is None, ctl.status()
        if path.is_file() and b'"WAITING_FOR_CLOSE"' in path.read_bytes():
            return
        sleep(0.05)
    pytest.fail("real child did not reach a journaled no-data wait")


def test_real_owned_stop_restart_and_service_close(private_database, real_wait_controllers):
    before = file_hash(private_database)
    ctl = real_wait_controllers()
    first = ctl.start(request(ctl))
    wait_for_owned_wait(ctl)
    old_child = ctl._child
    assert ctl.stop(request(ctl))["state"] == "STOP_REQUESTED"
    assert old_child.wait(timeout=30) == 0
    terminal = ctl.status()
    assert terminal["state"] == "STOPPED" and terminal["journal_verified"]
    assert terminal["last_result"]["attempts"] == 1
    assert terminal["last_result"]["processed_bars"] == 0
    assert not terminal["forward_qualifying"]
    second = ctl.start(request(ctl))
    assert second["run_id"] != first["run_id"]
    wait_for_owned_wait(ctl)
    assert ctl.close()
    assert ctl._child.poll() == 0 and not ctl.status()["process_alive"]
    assert ctl.status()["journal_verified"] and not ctl.status()["can_start"]
    assert file_hash(private_database) == before


def test_real_second_owner_cannot_acquire_database(private_database, real_wait_controllers):
    before = file_hash(private_database)
    first = real_wait_controllers()
    first.start(request(first))
    wait_for_owned_wait(first)
    second = real_wait_controllers()
    second.start(request(second))
    assert second._child.wait(timeout=30) == 1
    assert second.status()["state"] == "BLOCKED" and not second.status()["can_start"]
    assert not second.status()["journal_verified"]
    assert first.status()["process_alive"]
    assert first.close()
    assert second.close() is False
    assert file_hash(private_database) == before
