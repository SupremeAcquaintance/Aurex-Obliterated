"""Private service checks on migrated, disposable databases, not the operator ledger."""

import json
import os
import socket
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aurex.api import private_runtime as runtime
from aurex.config.settings import Settings, get_settings
from aurex.db.backup import create_backup, file_hash, restore_copy


@pytest.fixture(scope="module")
def migrated_template(tmp_path_factory):
    path = tmp_path_factory.mktemp("private-runtime-schema") / "template.db"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=runtime.ROOT,
        env={**os.environ, "AUREX_DATABASE_URL": f"sqlite:///{path.as_posix()}"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return path


@pytest.fixture
def private_database(tmp_path, migrated_template, monkeypatch):
    path = tmp_path / "private.db"
    with closing(sqlite3.connect(migrated_template.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(path)) as target:
            source.backup(target)
    monkeypatch.setenv("AUREX_DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.setenv("AUREX_LIVE_TRADING_ENABLED", "false")
    monkeypatch.setenv("AUREX_LIVE_EXECUTION_ADAPTER", "disabled")
    monkeypatch.setenv("AUREX_ENVIRONMENT", "local")
    get_settings.cache_clear()
    yield path
    get_settings.cache_clear()


def local_client(port=8917, **kwargs):
    return TestClient(
        runtime.create_private_app(port),
        base_url=f"http://127.0.0.1:{port}",
        client=("127.0.0.1", 51000),
        **kwargs,
    )


def test_preflight_and_service_reads_do_not_mutate_database(private_database):
    before = file_hash(private_database)
    report = runtime.runtime_check(get_settings(), 8917)
    assert report["status"] == "PRIVATE_CONFIG_READY" and report["blockers"] == []
    assert report["database_revisions"] == ["20261004_0031"]
    assert not report["operational_acceptance"] and not report["starts_native_supervisor"]
    with local_client() as client:
        for path in [
            "/health",
            "/dashboard",
            "/dashboard/assets/app.js",
            "/dashboard/assets/styles.css",
            "/system/private-runtime",
            "/trades",
        ]:
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-frame-options"] == "DENY"
        assert client.get("/trades").json() == []
    assert file_hash(private_database) == before


@pytest.mark.parametrize(
    "change,blocker",
    [
        ({"live_trading_enabled": True}, "LIVE_EXECUTION_MUST_BE_DISABLED"),
        ({"live_execution_adapter": "anything"}, "LIVE_EXECUTION_MUST_BE_DISABLED"),
        ({"environment": "production"}, "PRODUCTION_ENVIRONMENT_NOT_AUTHORIZED"),
        ({"database_url": "sqlite://"}, "EXISTING_FILE_SQLITE_REQUIRED"),
        ({"database_url": "postgresql://localhost/no_connect"}, "EXISTING_FILE_SQLITE_REQUIRED"),
        ({"database_url": "sqlite:///not-created.db?mode=rwc"}, "EXISTING_FILE_SQLITE_REQUIRED"),
    ],
)
def test_unsafe_configuration_blocks(private_database, change, blocker):
    settings = get_settings().model_copy(update=change)
    assert blocker in runtime.runtime_check(settings, 8917)["blockers"]


def test_missing_path_is_not_created(tmp_path):
    missing = tmp_path / "missing.db"
    settings = Settings(_env_file=None, database_url=f"sqlite:///{missing.as_posix()}")
    assert runtime.runtime_check(settings, 8917)["status"] == "BLOCKED"
    assert not missing.exists()


@pytest.mark.parametrize("port", [0, 80, 65536, True])
def test_port_is_bounded(private_database, port):
    assert "PORT_OUT_OF_RANGE" in runtime.runtime_check(get_settings(), port)["blockers"]


@pytest.mark.parametrize(
    "sql,reason",
    [
        ("UPDATE alembic_version SET version_num='20260718_0029'", "CURRENT_SCHEMA_REQUIRED"),
        ("DROP TABLE native_bar_outcomes", "REQUIRED_TABLES_MISSING"),
        (
            "ALTER TABLE accounts RENAME COLUMN current_equity TO missing_equity",
            "REQUIRED_COLUMNS_MISSING",
        ),
    ],
)
def test_schema_mismatch_blocks_without_upgrade(private_database, sql, reason):
    with sqlite3.connect(private_database) as db:
        db.execute(sql)
    before = file_hash(private_database)
    assert reason in runtime.runtime_check(get_settings(), 8917)["blockers"]
    with pytest.raises(runtime.PrivateRuntimeError, match=reason):
        runtime.create_private_app(8917)
    assert file_hash(private_database) == before


def test_integrity_check_deadline_blocks(private_database, monkeypatch):
    monkeypatch.setattr(runtime, "CHECK_TIMEOUT_SECONDS", -1)
    assert "DATABASE_CHECK_FAILED" in runtime.runtime_check(get_settings(), 8917)["blockers"]


@pytest.mark.parametrize(
    "headers",
    [
        {"host": "attacker.example:8917"},
        {"host": "127.0.0.1:8918"},
        {"origin": "https://attacker.example"},
        {"origin": "null"},
        {"origin": "http://127.0.0.1:8918"},
        {"sec-fetch-site": "cross-site"},
        {"sec-fetch-site": "same-site"},
        [("host", "127.0.0.1:8917"), ("host", "attacker.example")],
        [("origin", "http://127.0.0.1:8917"), ("origin", "http://127.0.0.1:8917")],
    ],
)
def test_cross_origin_and_rebinding_requests_refused_before_side_effects(private_database, headers):
    before = file_hash(private_database)
    with local_client() as client:
        assert client.get("/risk/status", headers=headers).status_code == 403
        assert client.post("/risk/kill-switch", headers=headers).status_code == 403
    assert file_hash(private_database) == before


def test_remote_peer_rejected_even_with_forwarded_loopback(private_database):
    app = runtime.create_private_app(8917)
    with TestClient(app, base_url="http://127.0.0.1:8917", client=("192.0.2.1", 51000)) as client:
        assert client.get("/health", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 403


def test_cli_writes_require_explicit_local_header_and_browser_same_origin_works(private_database):
    with local_client() as client:
        assert client.post("/risk/kill-switch").status_code == 403
        response = client.post("/risk/kill-switch", headers={"X-Aurex-Local-Request": "1"})
        assert response.status_code == 200 and response.json()["kill_switch_enabled"]
        response = client.post(
            "/risk/kill-switch/reset", headers={"Origin": "http://127.0.0.1:8917"}
        )
        assert response.status_code == 200 and not response.json()["kill_switch_enabled"]


def test_settings_drift_blocks_requests(private_database):
    with local_client() as client:
        settings = get_settings()
        settings.live_trading_enabled = True
        try:
            response = client.get("/health")
            assert response.status_code == 503
            assert response.json()["detail"] == "RUNTIME_SETTINGS_CHANGED"
        finally:
            settings.live_trading_enabled = False


def test_instance_mismatch_blocks_before_mutation(private_database):
    before = file_hash(private_database)
    with local_client() as client:
        instance = client.get("/system/private-runtime").json()["instance_id"]
        response = client.post(
            "/risk/kill-switch",
            headers={
                "X-Aurex-Local-Request": "1",
                "X-Aurex-Instance": "different-instance",
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "RUNTIME_INSTANCE_MISMATCH"
        assert client.get("/health", headers={"X-Aurex-Instance": instance}).status_code == 200
    assert file_hash(private_database) == before


def test_startup_rechecks_after_app_construction(private_database):
    app = runtime.create_private_app(8917)
    with sqlite3.connect(private_database) as db:
        db.execute("UPDATE alembic_version SET version_num='stale'")
    with pytest.raises(runtime.PrivateRuntimeError, match="PRIVATE_STARTUP_RECHECK_FAILED"):
        with TestClient(app):
            pass


def test_disappeared_database_is_not_recreated(private_database):
    with local_client(raise_server_exceptions=False) as client:
        moved = private_database.with_suffix(".moved")
        private_database.rename(moved)
        assert client.get("/trades").status_code == 500
        assert not private_database.exists()
        assert client.get("/system/private-runtime").status_code == 503


def test_server_configuration_cannot_expose_or_trust_proxies():
    from scripts.run_private_operator import server_config

    config = server_config(lambda: None, 8917)
    assert config.host == "127.0.0.1" and config.workers == 1
    assert not config.proxy_headers and config.forwarded_allow_ips == ""
    assert not config.access_log and not config.server_header


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port, path, data=None, headers=None):
    opener = build_opener(ProxyHandler({}))
    req = Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers or {})
    with opener.open(req, timeout=10) as response:
        return response.status, response.read()


@contextmanager
def running_service(database, directory, port, *, max_seconds=30):
    instance = uuid4().hex
    with (directory.parent / (directory.name + ".log")).open("x", encoding="utf-8") as log:
        child = subprocess.Popen(
            [
                sys.executable,
                "scripts/run_private_operator.py",
                "--serve",
                "--database",
                str(database),
                "--run-directory",
                str(directory),
                "--port",
                str(port),
                "--max-runtime-seconds",
                str(max_seconds),
                "--instance-id",
                instance,
            ],
            cwd=runtime.ROOT,
            env={
                **os.environ,
                "AUREX_LIVE_TRADING_ENABLED": "false",
                "AUREX_LIVE_EXECUTION_ADAPTER": "disabled",
                "AUREX_ENVIRONMENT": "local",
            },
            stdout=log,
            stderr=log,
        )
        try:
            deadline = monotonic() + 60
            while monotonic() < deadline:
                if child.poll() is not None:
                    pytest.fail(f"service exited during startup: {child.returncode}")
                try:
                    status, body = request(
                        port, "/system/private-runtime", headers={"X-Aurex-Instance": instance}
                    )
                    if status == 200 and json.loads(body).get("instance_id") == instance:
                        break
                except (URLError, TimeoutError, OSError):
                    sleep(0.1)
            else:
                pytest.fail("service startup deadline expired")
            child.aurex_instance_id = instance
            yield child
        finally:
            if child.poll() is None:
                (directory / "STOP").touch(exist_ok=False)
                try:
                    child.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
                    pytest.fail("private service did not stop gracefully")


def test_real_process_restore_stop_restart_preserves_kill_control(private_database, tmp_path):
    original = file_hash(private_database)
    package = tmp_path / "backup"
    create_backup(private_database, package)
    restored = tmp_path / "restored.db"
    restore_copy(package, restored)
    port = free_port()
    for index in (1, 2):
        directory = tmp_path / f"service-{index}"
        with running_service(restored, directory, port) as child:
            headers = {"X-Aurex-Instance": child.aurex_instance_id, "X-Aurex-Local-Request": "1"}
            for path in [
                "/dashboard",
                "/dashboard/assets/app.js",
                "/system/private-runtime",
                "/trades",
            ]:
                assert request(port, path, headers=headers)[0] == 200
            with pytest.raises(HTTPError) as cross_site:
                request(
                    port,
                    "/risk/kill-switch",
                    b"",
                    {**headers, "Origin": "https://attacker.example"},
                )
            assert cross_site.value.code == 403
            if index == 1:
                _, payload = request(port, "/risk/kill-switch", b"", headers)
                assert json.loads(payload)["kill_switch_enabled"]
            else:
                _, payload = request(port, "/risk/status", headers=headers)
                assert json.loads(payload)["kill_switch_enabled"]
        assert child.returncode == 0
        events = [
            json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()
        ]
        assert [item["kind"] for item in events] == ["STARTING", "LISTENING", "STOPPED"]
        assert events[-1]["reason"] == "stop_file"
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0
    assert file_hash(private_database) == original
    with sqlite3.connect(restored) as db:
        assert db.execute("SELECT COUNT(*) FROM paper_orders").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 0


def test_real_process_runtime_budget_stops(private_database, tmp_path):
    directory = tmp_path / "budget-service"
    with running_service(private_database, directory, free_port(), max_seconds=2) as child:
        child.wait(timeout=30)
        assert child.returncode == 0
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert events[-1]["kind"] == "STOPPED" and events[-1]["reason"] == "runtime_budget"


def test_real_process_occupied_port_reports_blocked(private_database, tmp_path):
    directory = tmp_path / "occupied-service"
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        result = subprocess.run(
            [
                sys.executable,
                "scripts/run_private_operator.py",
                "--serve",
                "--database",
                str(private_database),
                "--port",
                str(other.getsockname()[1]),
                "--run-directory",
                str(directory),
                "--max-runtime-seconds",
                "2",
            ],
            cwd=runtime.ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
    assert result.returncode == 1
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert [item["kind"] for item in events] == ["STARTING", "BLOCKED"]
    assert not events[-1]["listener_started"]


def test_full_private_rehearsal_preserves_source_and_ledger(private_database, tmp_path):
    from scripts.rehearse_private_operator import rehearse

    before = file_hash(private_database)
    work = tmp_path / "rehearsal"
    result = rehearse(private_database, work)
    assert result["status"] == "PASS"
    assert len(result["service_cycles"]) == 2
    assert result["trading_ledger_table_hashes_unchanged"]
    assert not result["external_files_recovered"] and not result["production_acceptance"]
    assert not result["source_database_modified"] and file_hash(private_database) == before
    assert json.loads((work / "rehearsal.json").read_text()) == result
