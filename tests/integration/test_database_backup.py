"""Disposable backup/restore fixtures; never overwrite or migrate the operator DB."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.db import backup
from aurex.db.backup import BackupError, create_backup, restore_copy, verify_backup
from aurex.db.models import PaperTrade
from aurex.domain.enums import TradeStatus
from aurex.signal_gateway.native_processing import validate_chain
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import template_database as template_database
from tests.integration.test_native_jam_runtime import bar_prices, filled_run
from tests.integration.test_native_signal_intake import settings as settings


@pytest.fixture
def database(engine):
    # Metadata fixture, explicitly not a migration proof. Real migrations are
    # separately exercised on the diagnostic DB and in migration regressions.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('fixture_revision')")
    return Path(engine.url.database)


def test_snapshot_and_restore_preserve_closed_native_ledger(
    engine, database, settings, tmp_path, monkeypatch
):
    run, entry = filled_run(engine, settings, monkeypatch)
    bar_prices(
        run,
        33,
        opened=entry.entry_price,
        high=entry.entry_price,
        low=entry.stop_loss - 1,
        close=entry.stop_loss,
    )
    run.step(33)
    original = database.read_bytes()
    package = tmp_path / "backup"
    manifest = create_backup(database, package)
    assert verify_backup(package) == manifest
    assert manifest.snapshot.row_counts["paper_trades"] == 1
    assert manifest.snapshot.row_counts["native_bar_outcomes"] == 5
    assert not manifest.includes_external_files and not manifest.live_authority
    restored = tmp_path / "restored.db"
    result = restore_copy(package, restored)
    assert result["status"] == "PASS" and not result["replaces_operator_database"]
    from sqlalchemy import create_engine

    restored_engine = create_engine(f"sqlite:///{restored.as_posix()}")
    try:
        with Session(restored_engine) as session:
            assert len(validate_chain(session)) == 5
            assert session.scalar(select(PaperTrade)).status == TradeStatus.CLOSED
    finally:
        restored_engine.dispose()
    assert database.read_bytes() == original


def test_backup_includes_committed_wal_and_isolated_from_later_writes(database, tmp_path):
    with sqlite3.connect(database) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE backup_wal_fixture (value TEXT)")
        writer.execute("INSERT INTO backup_wal_fixture VALUES ('committed in WAL')")
        writer.commit()
        assert Path(str(database) + "-wal").stat().st_size > 0
        manifest = create_backup(database, tmp_path / "backup")
        writer.execute("INSERT INTO backup_wal_fixture VALUES ('after snapshot')")
        writer.commit()
        assert verify_backup(tmp_path / "backup") == manifest
        with sqlite3.connect(tmp_path / "backup" / "database.db") as copy:
            assert copy.execute("SELECT value FROM backup_wal_fixture").fetchall() == [
                ("committed in WAL",)
            ]
    assert manifest.snapshot.row_counts["backup_wal_fixture"] == 1


def test_no_overwrite_of_source_backup_or_restore_target(database, tmp_path):
    package = tmp_path / "backup"
    create_backup(database, package)
    before = database.read_bytes()
    with pytest.raises(FileExistsError):
        create_backup(database, package)
    with pytest.raises(FileExistsError):
        restore_copy(package, database)
    assert database.read_bytes() == before


@pytest.mark.parametrize("kind", ["bytes", "logical", "manifest"])
def test_corrupt_backup_never_restores(database, tmp_path, kind):
    package = tmp_path / "backup"
    create_backup(database, package)
    path = package / "database.db"
    manifest_path = package / "manifest.json"
    if kind == "bytes":
        with path.open("ab") as handle:
            handle.write(b"corruption")
    elif kind == "logical":
        with sqlite3.connect(path) as writer:
            writer.execute("UPDATE accounts SET current_equity = current_equity + 1")
        manifest = json.loads(manifest_path.read_text())
        manifest["database_sha256"] = backup.file_hash(path)
        manifest["database_bytes"] = path.stat().st_size
        manifest_path.write_text(json.dumps(manifest))
    else:
        manifest = json.loads(manifest_path.read_text())
        manifest["live_authority"] = True
        manifest_path.write_text(json.dumps(manifest))
    target = tmp_path / "restored.db"
    with pytest.raises(ValueError):
        restore_copy(package, target)
    assert not target.exists()


def test_disk_budget_refuses_before_creating_package(database, tmp_path, monkeypatch):
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(BackupError, match="insufficient_free_disk"):
        create_backup(database, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        create_backup(missing, tmp_path / "backup")
    assert not missing.exists() and not (tmp_path / "backup").exists()


def test_deadline_failure_never_publishes_manifest(database, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "TIME_BUDGET_SECONDS", -1)
    with pytest.raises((BackupError, sqlite3.OperationalError)):
        create_backup(database, tmp_path / "backup")
    assert not (tmp_path / "backup" / "manifest.json").exists()


def test_foreign_key_corruption_rejects_backup(database, tmp_path):
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE backup_fk_fixture (account_id TEXT REFERENCES accounts(id))")
        writer.execute("INSERT INTO backup_fk_fixture VALUES ('nonexistent-account')")
    with pytest.raises(BackupError, match="foreign_key_check_failed"):
        create_backup(database, tmp_path / "backup")
    assert not (tmp_path / "backup" / "manifest.json").exists()


def test_real_0029_upgrade_and_rollback_rehearsal_only_touch_copies(tmp_path):
    from scripts.rehearse_native_database_upgrade import ROOT, rehearse

    source = tmp_path / "operator-fixture.db"
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "20260718_0029"],
        cwd=ROOT,
        env={**os.environ, "AUREX_DATABASE_URL": f"sqlite:///{source.as_posix()}"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    before = source.read_bytes()
    result = rehearse(source, tmp_path / "rehearsal")
    assert result["status"] == "PASS" and result["to_revision"] == "20261004_0031"
    assert result["from_revision"] == "20260718_0029"
    assert result["added_empty_tables"] == ["native_bar_outcomes", "native_history_seeds"]
    assert result["existing_table_hashes_preserved"] and not result["operator_database_upgraded"]
    assert result["rollback_copy"]["revisions"] == ["20260718_0029"]
    assert result["original_database_sha256_before"] == result["original_database_sha256_after"]
    assert source.read_bytes() == before


def test_upgrade_rehearsal_rejects_unsupported_revision(database, tmp_path):
    from scripts.rehearse_native_database_upgrade import rehearse

    with pytest.raises(BackupError, match="revision_unsupported"):
        rehearse(database, tmp_path / "rehearsal")
    assert not (tmp_path / "rehearsal" / "upgraded.db").exists()


def test_rehashed_backup_constraint_change_is_not_hidden_by_unchanged_values(database, tmp_path):
    package = tmp_path / "backup"
    create_backup(database, package)
    with sqlite3.connect(package / "database.db") as connection:
        connection.execute("CREATE INDEX backup_modified_index ON accounts(name)")
    path = package / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["database_sha256"] = backup.file_hash(package / "database.db")
    manifest["database_bytes"] = (package / "database.db").stat().st_size
    path.write_text(json.dumps(manifest))
    with pytest.raises(BackupError, match="logical_snapshot_mismatch"):
        verify_backup(package)
