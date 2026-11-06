"""Private SQLite backup/restore copies; never migrate or replace an operator database."""

import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aurex.db.base import utc_now

MAX_DATABASE_BYTES = 512 * 1024 * 1024
TIME_BUDGET_SECONDS = 120


class BackupError(ValueError):
    pass


class DatabaseSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revisions: tuple[str, ...]
    row_counts: dict[str, int]
    table_hashes: dict[str, str]
    schema_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    logical_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class BackupManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal["aurex_sqlite_backup_v1"] = "aurex_sqlite_backup_v1"
    created_at: datetime
    snapshot: DatabaseSnapshot
    database_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_bytes: int = Field(gt=0, le=MAX_DATABASE_BYTES)
    includes_external_files: Literal[False] = False
    live_authority: Literal[False] = False


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def existing_database(path: Path) -> Path:
    path = path.resolve(strict=True)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_DATABASE_BYTES:
        raise BackupError("backup_database_size_or_type_invalid")
    return path


def read_connection(path: Path, deadline: float) -> sqlite3.Connection:
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.execute("PRAGMA query_only=ON")
    connection.set_progress_handler(lambda: int(monotonic() > deadline), 10000)
    connection.execute("BEGIN")
    return connection


def snapshot(connection: sqlite3.Connection, deadline: float) -> DatabaseSnapshot:
    if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise BackupError("backup_integrity_check_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise BackupError("backup_foreign_key_check_failed")
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
        )
    ]
    if not {"accounts", "paper_orders", "paper_trades", "alembic_version"} <= set(tables):
        raise BackupError("backup_requires_aurex_schema")
    counts, table_hashes = {}, {}
    for name in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        counts[name] = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        table_digest = sha256()
        columns = list(connection.execute(f"PRAGMA table_info({quoted})"))
        table_digest.update(json.dumps(columns, separators=(",", ":")).encode())
        table_schema = list(
            connection.execute(
                "SELECT type,name,sql FROM sqlite_schema WHERE tbl_name=? ORDER BY type,name",
                (name,),
            )
        )
        table_digest.update(json.dumps(table_schema, separators=(",", ":")).encode())
        for row in connection.execute(f"SELECT * FROM {quoted}"):
            if monotonic() > deadline:
                raise BackupError("backup_time_budget_exceeded")
            values = [
                (type(value).__name__, value.hex() if isinstance(value, bytes) else value)
                for value in row
            ]
            encoded = json.dumps(values, separators=(",", ":")).encode()
            table_digest.update(len(encoded).to_bytes(8, "big"))
            table_digest.update(encoded)
        table_hashes[name] = table_digest.hexdigest()
    schema = list(
        connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")
    )
    digest = sha256()
    # SQLite's logical dump includes every persisted value, not just row counts.
    # The per-line hash avoids retaining a second full database image in memory.
    for line in connection.iterdump():
        if monotonic() > deadline:
            raise BackupError("backup_time_budget_exceeded")
        encoded = line.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return DatabaseSnapshot(
        revisions=tuple(
            row[0]
            for row in connection.execute(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            )
        ),
        row_counts=counts,
        table_hashes=table_hashes,
        schema_hash=sha256(json.dumps(schema, separators=(",", ":")).encode()).hexdigest(),
        logical_hash=digest.hexdigest(),
    )


def copy_snapshot(source: sqlite3.Connection, destination: Path, deadline: float) -> None:
    page_size = source.execute("PRAGMA page_size").fetchone()[0]

    def progress(status, remaining, total):
        if monotonic() > deadline:
            raise BackupError("backup_time_budget_exceeded")
        if total * page_size > MAX_DATABASE_BYTES:
            raise BackupError("backup_page_budget_exceeded")

    # Reservation prevents any overwrite, even between a preflight and connection open.
    with destination.open("xb"):
        pass
    with closing(sqlite3.connect(destination.as_uri() + "?mode=rw", uri=True)) as target:
        source.backup(target, pages=128, progress=progress, sleep=0.01)
    with destination.open("r+b") as handle:
        os.fsync(handle.fileno())


def require_space(source: Path, destination_parent: Path) -> None:
    wal = Path(str(source) + "-wal")
    size = source.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
    if size > MAX_DATABASE_BYTES:
        raise BackupError("backup_database_capacity_exceeded")
    if shutil.disk_usage(destination_parent).free < 2 * size + 128 * 1024 * 1024:
        raise BackupError("backup_insufficient_free_disk")


def create_backup(source: Path, directory: Path) -> BackupManifest:
    source = existing_database(source)
    directory = directory.resolve()
    require_space(source, directory.parent)
    directory.mkdir(parents=False, exist_ok=False)
    target = directory / "database.db"
    deadline = monotonic() + TIME_BUDGET_SECONDS
    with closing(read_connection(source, deadline)) as reader:
        before = snapshot(reader, deadline)
        copy_snapshot(reader, target, deadline)
    with closing(read_connection(target, deadline)) as reader:
        if snapshot(reader, deadline) != before:
            raise BackupError("backup_snapshot_copy_mismatch")
    manifest = BackupManifest(
        created_at=utc_now(),
        snapshot=before,
        database_sha256=file_hash(target),
        database_bytes=target.stat().st_size,
    )
    with (directory / "manifest.json").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(manifest.model_dump_json(indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    if verify_backup(directory) != manifest:
        raise BackupError("backup_manifest_readback_mismatch")
    return manifest


def verify_backup(directory: Path) -> BackupManifest:
    manifest_path = directory / "manifest.json"
    if not 0 < manifest_path.stat().st_size <= 1024 * 1024:
        raise BackupError("backup_manifest_size_invalid")
    manifest = BackupManifest.model_validate_json(manifest_path.read_bytes())
    database = existing_database(directory / "database.db")
    if (
        database.stat().st_size != manifest.database_bytes
        or file_hash(database) != manifest.database_sha256
    ):
        raise BackupError("backup_file_hash_mismatch")
    with closing(read_connection(database, monotonic() + TIME_BUDGET_SECONDS)) as reader:
        if snapshot(reader, monotonic() + TIME_BUDGET_SECONDS) != manifest.snapshot:
            raise BackupError("backup_logical_snapshot_mismatch")
    if file_hash(database) != manifest.database_sha256:
        raise BackupError("backup_changed_during_verification")
    return manifest


def restore_copy(directory: Path, destination: Path) -> dict:
    manifest = verify_backup(directory)
    source = existing_database(directory / "database.db")
    destination = destination.resolve()
    require_space(source, destination.parent)
    deadline = monotonic() + TIME_BUDGET_SECONDS
    with closing(read_connection(source, deadline)) as reader:
        if snapshot(reader, deadline) != manifest.snapshot:
            raise BackupError("backup_changed_before_restore")
        copy_snapshot(reader, destination, deadline)
    with closing(read_connection(destination, deadline)) as reader:
        if snapshot(reader, deadline) != manifest.snapshot:
            raise BackupError("restored_snapshot_mismatch")
    return {
        "schema_version": "aurex_sqlite_restore_copy_v1",
        "status": "PASS",
        "source_database_sha256": manifest.database_sha256,
        "restored_database_sha256": file_hash(destination),
        "logical_hash": manifest.snapshot.logical_hash,
        "revisions": list(manifest.snapshot.revisions),
        "replaces_operator_database": False,
        "includes_external_files": False,
        "live_authority": False,
    }
