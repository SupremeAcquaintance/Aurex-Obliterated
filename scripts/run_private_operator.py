"""Check or serve the private operator app. Never migrates or auto-starts trading."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic

import uvicorn

from aurex.config.settings import get_settings
from aurex.db.recovery_bundle import regular
from aurex.signal_gateway.native_lifecycle import SHUTDOWN_SECONDS
from aurex.signal_gateway.native_supervision import NativeSupervisorConfig


def server_config(app, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        proxy_headers=False,
        forwarded_allow_ips="",
        access_log=False,
        server_header=False,
        workers=1,
        ws="none",
        timeout_keep_alive=2,
        timeout_graceful_shutdown=SHUTDOWN_SECONDS + 15,
        limit_concurrency=16,
    )


def serve(app, port: int, directory: Path, max_seconds: int | None) -> int:
    directory.mkdir(parents=True, exist_ok=False)
    finished = Event()
    lock = Lock()
    server = uvicorn.Server(server_config(app, port))
    started = False
    reason = "server_shutdown"
    monitor_error = None
    with (directory / "events.jsonl").open("x", encoding="utf-8", newline="\n") as journal:

        def record(kind, **payload):
            with lock:
                journal.write(
                    json.dumps(
                        {
                            "recorded_at": datetime.now(UTC).isoformat(),
                            "kind": kind,
                            "live_authority": False,
                            **payload,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                journal.flush()
                os.fsync(journal.fileno())

        def monitor():
            nonlocal started, reason, monitor_error
            deadline = None
            try:
                while not finished.wait(0.1):
                    if server.started and not started:
                        started = True
                        deadline = monotonic() + max_seconds if max_seconds else None
                        record("LISTENING", host="127.0.0.1", port=port)
                    if (directory / "STOP").exists():
                        reason = "stop_file"
                        server.should_exit = True
                        return
                    if deadline is not None and monotonic() >= deadline:
                        reason = "runtime_budget"
                        server.should_exit = True
                        return
            except Exception as exc:
                monitor_error = type(exc).__name__
                server.should_exit = True

        record(
            "STARTING",
            instance_id=app.state.private_instance_id,
            port=port,
            max_runtime_seconds=max_seconds,
            journal_is_operational_diagnostic=True,
            starts_native_supervisor=False,
        )
        watcher = Thread(target=monitor, name="aurex-private-stop", daemon=True)
        watcher.start()
        failure = None
        try:
            server.run()
        except KeyboardInterrupt:
            reason = "interrupt"
        except (Exception, SystemExit) as exc:
            failure = type(exc).__name__
        finally:
            finished.set()
            watcher.join(timeout=5)
        failure = failure or monitor_error
        native_clean = getattr(app.state, "native_shutdown_clean", True)
        clean = server.started and not failure and not server.force_exit and native_clean
        record(
            "STOPPED" if clean else "BLOCKED",
            reason=failure or reason,
            listener_started=bool(server.started),
            forced_exit=bool(server.force_exit),
            native_shutdown_clean=native_clean,
        )
        return 0 if clean else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--serve", action="store_true")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8917)
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument("--max-runtime-seconds", type=int)
    parser.add_argument(
        "--native-config", type=Path, help="Pinned supervisor config; never autostarts"
    )
    parser.add_argument(
        "--instance-id", help="Optional diagnostic correlation ID, not a credential"
    )
    args = parser.parse_args(argv)
    if args.serve and args.run_directory is None:
        parser.error("--serve requires a new --run-directory")
    if args.max_runtime_seconds is not None and not 2 <= args.max_runtime_seconds <= 86400:
        parser.error("--max-runtime-seconds must be between 2 and 86400")
    try:
        database = args.database.resolve(strict=True)
        os.environ["AUREX_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        get_settings.cache_clear()
        from aurex.api.private_runtime import create_private_app, runtime_check

        native_config = None
        if args.native_config is not None:
            regular(args.native_config)
            if not 0 < args.native_config.stat().st_size <= 262144:
                raise ValueError("native_config_size_invalid")
            native_config = NativeSupervisorConfig.model_validate_json(
                args.native_config.read_bytes()
            )
        report = runtime_check(get_settings(), args.port)
        report["native_supervisor_configured"] = native_config is not None
        report["native_mode"] = native_config.mode if native_config else None
        print(json.dumps(report, indent=2), flush=True)
        if report["blockers"]:
            return 2
        if args.serve:
            return serve(
                create_private_app(
                    args.port,
                    args.instance_id,
                    native_config=native_config,
                    native_directory=args.run_directory.resolve() / "native"
                    if native_config
                    else None,
                ),
                args.port,
                args.run_directory.resolve(),
                args.max_runtime_seconds,
            )
        return 0
    except Exception as exc:
        # Never print exception messages that could include settings or credentials.
        print(
            json.dumps(
                {"status": "BLOCKED", "error_type": type(exc).__name__, "live_authority": False}
            ),
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
