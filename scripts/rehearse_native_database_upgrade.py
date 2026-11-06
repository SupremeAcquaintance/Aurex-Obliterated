"""Rehearse native-schema upgrade and rollback on NEW copies, never the operator DB."""

import argparse
import json
import os
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from time import monotonic

from alembic.script import ScriptDirectory

from aurex.db.backup import (
    TIME_BUDGET_SECONDS,
    BackupError,
    create_backup,
    existing_database,
    file_hash,
    read_connection,
    restore_copy,
    snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
TARGET = "20261004_0031"
SUPPORTED = {"20260718_0029", "20260930_0030", TARGET}


def rehearse(source: Path, directory: Path) -> dict:
    source = existing_database(source)
    directory = directory.resolve()
    if set(ScriptDirectory(str(ROOT / "infra/alembic")).get_heads()) != {TARGET}:
        raise BackupError("upgrade_rehearsal_contract_requires_review_for_new_head")
    directory.mkdir(parents=False, exist_ok=False)
    original_hash = file_hash(source)
    package = directory / "backup"
    manifest = create_backup(source, package)
    if len(manifest.snapshot.revisions) != 1 or manifest.snapshot.revisions[0] not in SUPPORTED:
        raise BackupError("upgrade_rehearsal_revision_unsupported")
    upgraded = directory / "upgraded.db"
    restore_copy(package, upgraded)
    environment = {**os.environ, "AUREX_DATABASE_URL": f"sqlite:///{upgraded.as_posix()}"}
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", TARGET],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=TIME_BUDGET_SECONDS,
    )
    # Migration output is local diagnostic data, not instructions or trading authority.
    with (directory / "migration.log").open("x", encoding="utf-8") as handle:
        handle.write(completed.stdout + completed.stderr)
    if completed.returncode != 0:
        raise BackupError("upgrade_rehearsal_migration_failed")
    deadline = monotonic() + TIME_BUDGET_SECONDS
    with closing(read_connection(upgraded, deadline)) as reader:
        after = snapshot(reader, deadline)
    if after.revisions != (TARGET,):
        raise BackupError("upgrade_rehearsal_target_revision_mismatch")
    for table, digest in manifest.snapshot.table_hashes.items():
        if table != "alembic_version" and after.table_hashes.get(table) != digest:
            raise BackupError("upgrade_rehearsal_existing_table_changed")
    added = set(after.row_counts) - set(manifest.snapshot.row_counts)
    if not added <= {"native_bar_outcomes", "native_history_seeds"} or any(
        after.row_counts[t] for t in added
    ):
        raise BackupError("upgrade_rehearsal_unexpected_new_data")
    rollback = restore_copy(package, directory / "rollback.db")
    report = {
        "schema_version": "aurex_native_upgrade_rehearsal_v1",
        "status": "PASS",
        "from_revision": manifest.snapshot.revisions[0],
        "to_revision": TARGET,
        "original_database_sha256_before": original_hash,
        "original_database_sha256_after": file_hash(source),
        "backup_database_sha256": manifest.database_sha256,
        "upgraded_database_sha256": file_hash(upgraded),
        "existing_table_hashes_preserved": True,
        "added_empty_tables": sorted(added),
        "rollback_copy": rollback,
        "migration_source_hashes": {
            name: file_hash(ROOT / "infra/alembic/versions" / name)
            for name in (
                "20260930_0030_native_bar_outcomes.py",
                "20261004_0031_native_history_seed.py",
            )
        },
        "operator_database_upgraded": False,
        "runtime_resume_verified": False,
        "includes_external_files": False,
        "live_authority": False,
    }
    with (directory / "rehearsal.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--work-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(rehearse(args.database, args.work_directory), indent=2))
        return 0
    except Exception as exc:
        reason = str(exc) if isinstance(exc, BackupError) else type(exc).__name__
        print(
            json.dumps({"status": "BLOCKED", "reason": reason, "operator_database_upgraded": False})
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
