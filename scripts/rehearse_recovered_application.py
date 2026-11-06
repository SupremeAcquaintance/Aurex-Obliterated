"""Run only inside a restored Aurex source tree with a separately rebuilt environment.

Uses the restored files, configuration, evidence and database. Never starts the
native supervisor, acquires market data, restores credentials or enables live orders.
"""

import argparse
import json
import os
import re
import secrets
import sys
from contextlib import closing
from pathlib import Path
from time import monotonic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-environment", type=Path, required=True)
    parser.add_argument("--report-directory", type=Path, required=True)
    args = parser.parse_args()
    report_directory = args.report_directory.resolve()
    root = Path(__file__).resolve().parents[1]
    try:
        if (
            Path(sys.prefix).resolve() != args.expected_environment.resolve(strict=True)
            or sys.prefix == sys.base_prefix
        ):
            raise ValueError("isolated_recovery_environment_required")
        restore = json.loads((root / "_recovery/restore.json").read_bytes())
        if (
            restore.get("schema_version") != "aurex_application_restore_v2"
            or restore.get("readback_verified") is not True
            or restore["status"] != "RESTORED_FILES_AND_DATABASE"
            or restore["live_authority"] is not False
        ):
            raise ValueError("restored_tree_receipt_required")
        sys.path.insert(0, str(root))
        sys.path.insert(0, str(root / "src"))
        import aurex
        from aurex.db.recovery_bundle import configuration, runtime_inventory
        from aurex.db.recovery_environment import clean_environment

        if Path(aurex.__file__).resolve() != root / "src/aurex/__init__.py":
            raise ValueError("recovered_source_import_mismatch")
        expected_runtime = json.loads((root / "_recovery/runtime.json").read_bytes())
        if runtime_inventory() != expected_runtime:
            raise ValueError("recovered_runtime_inventory_mismatch")
        config = json.loads((root / "_recovery/configuration.json").read_bytes())
        from aurex.config.settings import Settings, get_settings

        if configuration(Settings(_env_file=None, **config)) != config:
            raise ValueError("recovered_configuration_mismatch")
        environment = clean_environment()
        environment["PYTHONPATH"] = os.pathsep.join([str(root / "src"), str(root)])
        environment.update(
            {
                "AUREX_" + key.upper(): json.dumps(value) if isinstance(value, bool) else str(value)
                for key, value in config.items()
            }
        )
        database = root / "data/aurex.db"
        environment["AUREX_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        environment["AUREX_WEBHOOK_SECRET"] = secrets.token_urlsafe(48)
        os.environ.clear()
        os.environ.update(environment)
        os.chdir(root)
        get_settings.cache_clear()
        from fastapi.testclient import TestClient

        from aurex.api.private_runtime import ROOT, create_private_app
        from aurex.db.backup import file_hash, read_connection, snapshot
        from scripts.rehearse_private_operator import service_cycle

        if ROOT != root:
            raise ValueError("recovered_application_root_mismatch")
        report_directory.mkdir(parents=True, exist_ok=False)
        with closing(read_connection(database, monotonic() + 120)) as connection:
            before = snapshot(connection, monotonic() + 120)
        with TestClient(
            create_private_app(8917), base_url="http://127.0.0.1:8917", client=("127.0.0.1", 51000)
        ) as client:
            response = client.get("/system/readiness")
            if response.status_code != 200:
                raise ValueError("recovered_readiness_request_failed")
            readiness = response.json()
            if (
                readiness["source_integrity_verified"] is not True
                or readiness["research_checkpoint_verified"] is not True
                or readiness["live_ready"] is not False
                or readiness["production_ready"] is not False
            ):
                raise ValueError("recovered_readiness_evidence_failed")
        cycles = [
            service_cycle(database, report_directory / f"service-{index}", index)
            for index in (1, 2)
        ]
        with closing(read_connection(database, monotonic() + 120)) as connection:
            after = snapshot(connection, monotonic() + 120)
        names = (
            "paper_orders",
            "paper_trades",
            "positions",
            "signals",
            "native_bar_outcomes",
            "native_history_seeds",
        )
        if any(before.table_hashes[name] != after.table_hashes[name] for name in names):
            raise ValueError("recovered_service_changed_trading_ledger")
        result = {
            "status": "PASS_RESTORED_APPLICATION_REHEARSAL",
            "scope": restore["scope"],
            "omitted_archives": restore["omitted_archives"],
            "full_historical_evidence_restored": restore["full_historical_evidence_restored"],
            "restored_source_import_verified": True,
            "isolated_runtime_versions_verified": True,
            "readiness_source_and_checkpoint_verified": True,
            "trading_ledger_table_hashes_unchanged": True,
            "restore_receipt_sha256": file_hash(root / "_recovery/restore.json"),
            "source_database_logical_hash": before.logical_hash,
            "service_cycles": cycles,
            "credentials_restored": False,
            "starts_native_supervisor": False,
            "production_acceptance": False,
            "live_authority": False,
        }
        with (report_directory / "rehearsal.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as output:
            json.dump(result, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        code = str(exc) if re.fullmatch(r"[a-z_]+", str(exc)) else type(exc).__name__
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error_type": type(exc).__name__,
                    "reason": code,
                    "live_authority": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
