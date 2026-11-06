"""Run a bounded private native observer/Jam paper supervisor on an EXISTING database."""

import argparse
import json
import os
import signal
import sqlite3
import sys
from pathlib import Path
from threading import Event, Thread

from sqlalchemy import create_engine

from aurex.config.settings import Settings
from aurex.signal_gateway.native_supervision import (
    NativeSupervisorConfig,
    error_code,
    run_native_supervisor,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument("--managed-launch", type=Path)
    parser.add_argument("--managed-launch-sha256")
    args = parser.parse_args(argv)
    engine = None
    handlers = {}
    stop = Event()
    try:
        launch = None
        if args.managed_launch is not None:
            from aurex.signal_gateway.native_lifecycle import read_managed_launch

            if any((args.database, args.config, args.run_directory)):
                raise ValueError("managed_and_standalone_arguments_are_exclusive")
            launch = read_managed_launch(args.managed_launch, args.managed_launch_sha256)
            database = Path(launch.database)
            config = launch.config
            settings = Settings(
                _env_file=None, database_url=f"sqlite:///{database.as_posix()}", **launch.settings
            )
            directory = args.managed_launch.resolve(strict=True).parent / "run"
            parent_pipe = sys.stdin.fileno()
            if os.read(parent_pipe, 1) != b"G":
                stop.set()
            else:

                def watch_parent():
                    # EOF after stop/parent death requests cooperative shutdown, not liquidation.
                    try:
                        # Avoid holding stdin's buffered-reader lock during interpreter shutdown.
                        os.read(parent_pipe, 1)
                    finally:
                        stop.set()

                Thread(target=watch_parent, name="aurex-parent-lifetime", daemon=True).start()
        else:
            if args.managed_launch_sha256 or not all(
                (args.database, args.config, args.run_directory)
            ):
                raise ValueError("explicit_standalone_arguments_required")
            database = args.database.resolve(strict=True)
            if not database.is_file() or args.config.stat().st_size > 262144:
                raise ValueError("Existing database and bounded JSON configuration required")
            config = NativeSupervisorConfig.model_validate_json(args.config.read_bytes())
            settings = Settings()
            directory = args.run_directory

        def connect():
            if launch is not None and (database.stat().st_dev, database.stat().st_ino) != (
                launch.database_device,
                launch.database_inode,
            ):
                raise ValueError("managed_database_identity_changed")
            connection = sqlite3.connect(
                database.as_uri() + "?mode=rw", uri=True, check_same_thread=False, timeout=5
            )
            connection.execute("PRAGMA foreign_keys=ON")
            return connection

        # mode=rw refuses implicit creation even if the file disappears after preflight.
        engine = create_engine(
            f"sqlite:///{database.as_posix()}",
            creator=connect,
        )
        for name in (signal.SIGINT, signal.SIGTERM):
            handlers[name] = signal.signal(name, lambda signum, frame: stop.set())
        result = run_native_supervisor(engine, settings, config, run_directory=directory, stop=stop)
        print(result.model_dump_json(indent=2))
        return 0 if result.status == "STOPPED" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": error_code(exc),
                    "live_authority": False,
                    "forward_qualifying": False,
                }
            )
        )
        return 1
    finally:
        for name, previous in handlers.items():
            signal.signal(name, previous)
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
