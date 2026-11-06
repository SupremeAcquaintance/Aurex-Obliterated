"""Back up a current-schema DB and demonstrate private service recovery on a NEW copy."""

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from aurex.api.private_runtime import ROOT, runtime_check
from aurex.config.settings import Settings
from aurex.db.backup import create_backup, file_hash, read_connection, restore_copy, snapshot


def request(port: int, instance: str, path: str, *, post: bool = False, origin=None):
    headers = {"X-Aurex-Instance": instance, "X-Aurex-Local-Request": "1"}
    if origin is not None:
        headers["Origin"] = origin
    req = Request(f"http://127.0.0.1:{port}{path}", headers=headers, data=b"" if post else None)
    opener = build_opener(ProxyHandler({}))
    try:
        response = opener.open(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise ValueError("service_response_limit")
        return response.status, body


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def service_cycle(database: Path, directory: Path, index: int) -> dict:
    port, instance = unused_port(), uuid4().hex
    results = {}
    with (directory.parent / f"service-{index}.log").open("x", encoding="utf-8") as log:
        child = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_private_operator.py"),
                "--serve",
                "--database",
                str(database),
                "--port",
                str(port),
                "--run-directory",
                str(directory),
                "--max-runtime-seconds",
                "180",
                "--instance-id",
                instance,
            ],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = monotonic() + 90
            while monotonic() < deadline:
                if child.poll() is not None:
                    raise ValueError("service_exited_before_ready")
                try:
                    status, body = request(port, instance, "/system/private-runtime")
                    if status == 200 and json.loads(body).get("instance_id") == instance:
                        break
                except (URLError, TimeoutError, OSError):
                    pass
                sleep(0.2)
            else:
                raise ValueError("service_startup_timeout")
            for path in (
                "/health",
                "/dashboard",
                "/dashboard/assets/app.js",
                "/dashboard/assets/styles.css",
                "/system/private-runtime",
                "/trades",
            ):
                status, body = request(port, instance, path)
                if status != 200:
                    raise ValueError("service_endpoint_failed")
                results[path] = {"status": status, "body_sha256": sha256(body).hexdigest()}
            status, _ = request(
                port, instance, "/risk/kill-switch", post=True, origin="https://untrusted.invalid"
            )
            if status != 403:
                raise ValueError("service_cross_origin_guard_failed")
            if index == 1:
                status, body = request(port, instance, "/risk/kill-switch", post=True)
            else:
                status, body = request(port, instance, "/risk/status")
            if status != 200 or json.loads(body).get("kill_switch_enabled") is not True:
                raise ValueError("service_kill_state_not_preserved")
        finally:
            if child.poll() is None:
                if directory.is_dir():
                    with (directory / "STOP").open("x", encoding="ascii") as stop:
                        stop.write("recovery rehearsal stop\n")
                try:
                    child.wait(timeout=45)
                except subprocess.TimeoutExpired as exc:
                    child.kill()
                    child.wait(timeout=10)
                    raise ValueError("service_graceful_stop_failed") from exc
        if child.returncode != 0:
            raise ValueError("service_nonzero_exit")
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    if (
        [item["kind"] for item in events] != ["STARTING", "LISTENING", "STOPPED"]
        or events[0].get("instance_id") != instance
        or events[-1]["reason"] != "stop_file"
    ):
        raise ValueError("service_lifecycle_journal_mismatch")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise ValueError("service_port_still_listening")
    return {
        "instance_id": instance,
        "port": port,
        "requests": results,
        "cross_origin_rejected": True,
        "kill_switch_preserved": True,
        "graceful_exit": True,
        "port_closed": True,
        "journal_sha256": file_hash(directory / "events.jsonl"),
    }


def rehearse(database: Path, work_directory: Path) -> dict:
    database = database.resolve(strict=True)
    settings = Settings(database_url=f"sqlite:///{database.as_posix()}")
    check = runtime_check(settings, 8917)
    if check["blockers"]:
        raise ValueError("private_runtime_preflight_blocked")
    work_directory = work_directory.resolve()
    work_directory.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "BLOCKED",
        "source_database_sha256_before": file_hash(database),
        "source_database_modified": None,
        "live_authority": False,
        "starts_native_supervisor": False,
        "external_files_recovered": False,
        "production_acceptance": False,
        "service_cycles": [],
    }
    try:
        backup = work_directory / "backup"
        manifest = create_backup(database, backup)
        restored = work_directory / "service-copy.db"
        report["restore"] = restore_copy(backup, restored)
        for index in (1, 2):
            report["service_cycles"].append(
                service_cycle(restored, work_directory / f"service-{index}", index)
            )
        with closing(sqlite3.connect(restored.as_uri() + "?mode=ro", uri=True)) as db:
            report["paper_order_count"] = db.execute(
                "SELECT COUNT(*) FROM paper_orders"
            ).fetchone()[0]
            report["paper_trade_count"] = db.execute(
                "SELECT COUNT(*) FROM paper_trades"
            ).fetchone()[0]
        deadline = monotonic() + 120
        with closing(read_connection(restored, deadline)) as db:
            after = snapshot(db, deadline)
        ledger_tables = (
            "paper_orders",
            "paper_trades",
            "positions",
            "signals",
            "native_bar_outcomes",
            "native_history_seeds",
        )
        if any(
            manifest.snapshot.table_hashes[name] != after.table_hashes[name]
            for name in ledger_tables
        ):
            raise ValueError("service_rehearsal_changed_trading_ledger")
        report["trading_ledger_table_hashes_unchanged"] = True
        report["source_database_sha256_after"] = file_hash(database)
        report["source_database_modified"] = (
            report["source_database_sha256_before"] != report["source_database_sha256_after"]
        )
        if report["source_database_modified"]:
            raise ValueError("source_changed_during_rehearsal")
        report["service_copy_sha256_after"] = file_hash(restored)
        report["status"] = "PASS"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        raise
    finally:
        with (work_directory / "rehearsal.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as output:
            output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
            output.flush()
            os.fsync(output.fileno())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--work-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.database, args.work_directory), indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(exc).__name__, "live_authority": False}
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
