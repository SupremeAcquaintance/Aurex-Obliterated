"""Private application recovery bundles with explicit, verifiable evidence coverage.

This is local integrity verification, not a signature or off-device disaster backup.
An operational bundle declares each omitted ZIP/partial acquisition; it is never a
full historical-evidence backup. Secrets and the Python interpreter are not included.
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import stat
import sys
import sysconfig
import zipfile
from contextlib import closing
from hashlib import sha256
from importlib.metadata import distributions
from pathlib import Path, PurePosixPath
from time import monotonic
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.config.settings import Settings
from aurex.db.backup import (
    create_backup,
    file_hash,
    read_connection,
    restore_copy,
    snapshot,
    verify_backup,
)

SOURCE_DIRECTORIES = ("apps", "docs", "infra", "pine", "scripts", "src", "tests", "data/evidence")
SOURCE_FILES = ("README.md", "pyproject.toml", "alembic.ini", ".env.example", "docker-compose.yml")
CONFIG_FIELDS = {
    "app_name",
    "environment",
    "log_level",
    "live_trading_enabled",
    "live_execution_adapter",
    "tradingview_webhook_source_networks",
    "duplicate_cooldown_minutes",
    "webhook_processing_budget_ms",
    "paper_commission_bps",
    "paper_half_spread_bps",
    "paper_market_impact_bps",
    "paper_latency_ms",
}
GENERATED_FILES = {"_recovery/configuration.json", "_recovery/runtime.json"}
MAX_FILES = 50000
MAX_FILE_BYTES = 64 * 1024**3
MAX_TOTAL_BYTES = 128 * 1024**3
MAX_MANIFEST_BYTES = 32 * 1024**2
MIN_FREE_BYTES = 2 * 1024**3
TIME_LIMIT_SECONDS = 7200
CHUNK_BYTES = 1024**2
Scope = Literal["FULL_EVIDENCE", "OPERATIONAL_WITHOUT_RAW_ARCHIVES"]


class RecoveryError(ValueError):
    pass


def relative_name(value: str) -> str:
    parts = PurePosixPath(value).parts
    if (
        not parts
        or PurePosixPath(value).is_absolute()
        or "/".join(parts) != value
        or any(
            part in {".", ".."}
            or part.endswith((".", " "))
            or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
            or part.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
            for part in parts
        )
    ):
        raise RecoveryError("recovery_relative_path_invalid")
    return value


def allowed_name(value: str) -> str:
    relative_name(value)
    if (
        value not in SOURCE_FILES
        and value not in GENERATED_FILES
        and not any(value.startswith(directory + "/") for directory in SOURCE_DIRECTORIES)
    ):
        raise RecoveryError("recovery_path_outside_scope")
    name = PurePosixPath(value).name.lower()
    if (
        (name.startswith(".env") and name != ".env.example")
        or name.endswith((".pem", ".key", ".p12", ".pfx"))
        or name in {"credentials", "credentials.json", "credentials.toml"}
    ):
        raise RecoveryError("recovery_sensitive_filename_in_scope")
    return value


class FrozenRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecoveryFile(FrozenRecord):
    path: str
    size: int = Field(ge=0, le=MAX_FILE_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    _path = field_validator("path")(allowed_name)


class OmittedArchive(FrozenRecord):
    path: str
    size: int = Field(ge=0, le=MAX_FILE_BYTES)
    reason: Literal["RAW_ARCHIVE_NOT_INCLUDED"] = "RAW_ARCHIVE_NOT_INCLUDED"

    _path = field_validator("path")(allowed_name)

    @model_validator(mode="after")
    def archive_only(self):
        if not self.path.startswith("data/evidence/") or not self.path.lower().endswith(
            (".zip", ".part")
        ):
            raise RecoveryError("recovery_omission_not_raw_archive")
        return self


class RecoveryManifest(FrozenRecord):
    schema_version: Literal["aurex_recovery_bundle_v1"] = "aurex_recovery_bundle_v1"
    scope: Scope
    files: tuple[RecoveryFile, ...] = Field(min_length=1, max_length=MAX_FILES)
    omitted_archives: tuple[OmittedArchive, ...] = Field(max_length=MAX_FILES)
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_bytes: int = Field(gt=0, le=MAX_TOTAL_BYTES)
    database_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    credentials_included: Literal[False] = False
    interpreter_included: Literal[False] = False
    dependency_wheels_included: Literal[False] = False
    off_device_backup_verified: Literal[False] = False
    application_start_verified: Literal[False] = False
    live_authority: Literal[False] = False

    @model_validator(mode="after")
    def coverage(self):
        names = [item.path.casefold() for item in (*self.files, *self.omitted_archives)]
        if len(names) != len(set(names)) or sum(item.size for item in self.files) > MAX_TOTAL_BYTES:
            raise RecoveryError("recovery_file_inventory_invalid")
        if self.scope == "FULL_EVIDENCE" and self.omitted_archives:
            raise RecoveryError("recovery_full_scope_cannot_omit_archives")
        if not GENERATED_FILES <= {item.path for item in self.files}:
            raise RecoveryError("recovery_configuration_or_runtime_missing")
        paths = {item.path for item in self.files}
        if not set(SOURCE_FILES) <= paths or any(
            not any(path.startswith(folder + "/") for path in paths)
            for folder in SOURCE_DIRECTORIES
            if folder != "data/evidence"
        ):
            raise RecoveryError("recovery_required_application_files_missing")
        return self


def regular(path: Path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise RecoveryError("recovery_links_or_reparse_points_not_supported")
    return info


def inventory(root: Path) -> dict[str, tuple[int, int, int]]:
    root = root.resolve(strict=True)
    result = {}
    folded = set()

    def visit(path: Path):
        info = regular(path)
        if stat.S_ISDIR(info.st_mode):
            if path.name == "__pycache__" or path.name.endswith(".egg-info"):
                return
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            if path.suffix in {".pyc", ".pyo"}:
                return
            name = allowed_name(path.relative_to(root).as_posix())
            if name.casefold() in folded:
                raise RecoveryError("recovery_case_colliding_paths")
            folded.add(name.casefold())
            result[name] = (info.st_size, info.st_mtime_ns, info.st_ino)
            if len(result) > MAX_FILES or info.st_size > MAX_FILE_BYTES:
                raise RecoveryError("recovery_inventory_limit")
        else:
            raise RecoveryError("recovery_special_file_not_supported")

    for name in (*SOURCE_DIRECTORIES, *SOURCE_FILES):
        path = root / name
        for parent in path.parents:
            if parent == root:
                break
            regular(parent)
        if not path.exists():
            raise RecoveryError("recovery_required_source_missing")
        visit(path)
    if sum(value[0] for value in result.values()) > MAX_TOTAL_BYTES:
        raise RecoveryError("recovery_total_size_limit")
    return dict(sorted(result.items()))


def configuration(settings: Settings) -> dict:
    if set(Settings.model_fields) != CONFIG_FIELDS | {"database_url", "webhook_secret"}:
        raise RecoveryError("recovery_settings_schema_requires_review")
    if (
        settings.live_trading_enabled
        or settings.live_execution_adapter != "disabled"
        or settings.environment.strip().lower() in {"prod", "production"}
    ):
        raise RecoveryError("recovery_requires_private_non_live_settings")
    return settings.model_dump(mode="json", include=CONFIG_FIELDS)


def runtime_inventory() -> dict:
    packages = {}
    for dist in distributions():
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        if name == "aurex":
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or name in packages:
            raise RecoveryError("recovery_runtime_distribution_invalid")
        if not re.fullmatch(r"[A-Za-z0-9.+!-]+", dist.version):
            raise RecoveryError("recovery_runtime_version_invalid")
        packages[name] = dist.version
    return {
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "platform": sysconfig.get_platform(),
        "sqlite": sqlite3.sqlite_version,
        "packages": dict(sorted(packages.items())),
        "aurex_recovered_from_source": True,
    }


def split_inventory(items, scope: Scope):
    if scope not in {"FULL_EVIDENCE", "OPERATIONAL_WITHOUT_RAW_ARCHIVES"}:
        raise RecoveryError("recovery_scope_invalid")
    included, omitted = {}, []
    for name, info in items.items():
        if (
            scope == "OPERATIONAL_WITHOUT_RAW_ARCHIVES"
            and name.startswith("data/evidence/")
            and name.lower().endswith((".zip", ".part"))
        ):
            omitted.append(OmittedArchive(path=name, size=info[0]))
        else:
            included[name] = info
    return included, omitted


def recovery_plan(root: Path, database: Path, destination_parent: Path, scope: Scope) -> dict:
    items = inventory(root)
    included, omitted = split_inventory(items, scope)
    # Reserve room for a separately restored tree as well as a worst-case stored archive.
    needed = (
        2 * sum(item[0] for item in included.values())
        + 3 * database.stat().st_size
        + MIN_FREE_BYTES
    )
    free = shutil.disk_usage(destination_parent).free
    return {
        "scope": scope,
        "included_files": len(included),
        "included_bytes": sum(item[0] for item in included.values()),
        "omitted_archives": len(omitted),
        "omitted_bytes": sum(item.size for item in omitted),
        "required_free_bytes": needed,
        "free_bytes": free,
        "status": "CAPACITY_READY" if free >= needed else "BLOCKED_INSUFFICIENT_RECOVERY_SPACE",
        "live_authority": False,
        "application_recovery_verified": False,
    }


def check_budget(directory: Path, deadline: float):
    if monotonic() > deadline:
        raise RecoveryError("recovery_time_budget_exceeded")
    if shutil.disk_usage(directory).free < MIN_FREE_BYTES:
        raise RecoveryError("recovery_disk_reserve_exhausted")


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def create_bundle(root: Path, database: Path, directory: Path, scope: Scope, settings: Settings):
    root, database = root.resolve(strict=True), database.resolve(strict=True)
    directory = directory.resolve()
    config = configuration(settings)
    plan = recovery_plan(root, database, directory.parent, scope)
    if plan["status"] != "CAPACITY_READY":
        raise RecoveryError("recovery_insufficient_space_for_backup_and_restore")
    before = inventory(root)
    included, omitted = split_inventory(before, scope)
    directory.mkdir(exist_ok=False)
    create_backup(database, directory / "database")
    deadline = monotonic() + TIME_LIMIT_SECONDS
    generated = {
        "_recovery/configuration.json": encoded(config),
        "_recovery/runtime.json": encoded(runtime_inventory()),
    }
    records = []
    archive_path = directory / "tree.zip"
    with (
        archive_path.open("xb") as output,
        zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True
        ) as archive,
    ):
        for name in sorted((*included, *generated)):
            check_budget(directory, deadline)
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o100600 << 16
            info.compress_type = (
                zipfile.ZIP_STORED
                if name.lower().endswith((".zip", ".part", ".pack"))
                else zipfile.ZIP_DEFLATED
            )
            digest, size = sha256(), 0
            with archive.open(info, "w", force_zip64=True) as target:
                if name in generated:
                    content = generated[name]
                    target.write(content)
                    digest.update(content)
                    size = len(content)
                else:
                    with (root / name).open("rb") as source:
                        while block := source.read(CHUNK_BYTES):
                            check_budget(directory, deadline)
                            size += len(block)
                            if size > included[name][0]:
                                raise RecoveryError("recovery_source_changed_during_copy")
                            digest.update(block)
                            target.write(block)
                    if size != included[name][0]:
                        raise RecoveryError("recovery_source_changed_during_copy")
            records.append(RecoveryFile(path=name, size=size, sha256=digest.hexdigest()))
    with archive_path.open("r+b") as output:
        os.fsync(output.fileno())
    if inventory(root) != before:
        raise RecoveryError("recovery_source_tree_changed_during_copy")
    manifest = RecoveryManifest(
        scope=scope,
        files=tuple(records),
        omitted_archives=tuple(omitted),
        archive_sha256=file_hash(archive_path),
        archive_bytes=archive_path.stat().st_size,
        database_manifest_sha256=file_hash(directory / "database" / "manifest.json"),
    )
    # A completed manifest is published only after verifying every archived byte.
    verify_payload(directory, manifest)
    with (directory / "manifest.json").open("xb") as output:
        output.write(manifest.model_dump_json(indent=2).encode() + b"\n")
        output.flush()
        os.fsync(output.fileno())
    return manifest


def verify_payload(directory: Path, manifest: RecoveryManifest):
    archive_path = directory / "tree.zip"
    regular(archive_path)
    if (
        archive_path.stat().st_size != manifest.archive_bytes
        or file_hash(archive_path) != manifest.archive_sha256
    ):
        raise RecoveryError("recovery_archive_hash_mismatch")
    if file_hash(directory / "database" / "manifest.json") != manifest.database_manifest_sha256:
        raise RecoveryError("recovery_database_manifest_mismatch")
    verify_backup(directory / "database")
    deadline = monotonic() + TIME_LIMIT_SECONDS
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if [item.filename for item in members] != [item.path for item in manifest.files]:
            raise RecoveryError("recovery_archive_inventory_mismatch")
        for item, expected in zip(members, manifest.files, strict=True):
            if (
                item.file_size != expected.size
                or item.flag_bits & 1
                or item.is_dir()
                or stat.S_IFMT(item.external_attr >> 16) != stat.S_IFREG
                or item.compress_type not in {zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED}
            ):
                raise RecoveryError("recovery_archive_member_invalid")
            digest, size = sha256(), 0
            with archive.open(item) as content:
                while block := content.read(CHUNK_BYTES):
                    if monotonic() > deadline:
                        raise RecoveryError("recovery_time_budget_exceeded")
                    size += len(block)
                    if size > expected.size:
                        raise RecoveryError("recovery_archive_member_size_mismatch")
                    digest.update(block)
            if size != expected.size or digest.hexdigest() != expected.sha256:
                raise RecoveryError("recovery_archive_member_hash_mismatch")
        config = json.loads(archive.read("_recovery/configuration.json"))
        if (
            set(config) != CONFIG_FIELDS
            or configuration(Settings(_env_file=None, **config)) != config
        ):
            raise RecoveryError("recovery_configuration_invalid")
    if file_hash(archive_path) != manifest.archive_sha256:
        raise RecoveryError("recovery_archive_changed_during_verification")


def verify_bundle(directory: Path) -> RecoveryManifest:
    path = directory / "manifest.json"
    regular(path)
    if not 0 < path.stat().st_size <= MAX_MANIFEST_BYTES:
        raise RecoveryError("recovery_manifest_size_invalid")
    manifest = RecoveryManifest.model_validate_json(path.read_bytes())
    verify_payload(directory, manifest)
    return manifest


def restore_bundle(directory: Path, destination: Path) -> dict:
    manifest = verify_bundle(directory)
    destination = destination.resolve()
    database = verify_backup(directory / "database")
    required = (
        sum(item.size for item in manifest.files) + 2 * database.database_bytes + MIN_FREE_BYTES
    )
    if shutil.disk_usage(destination.parent).free < required:
        raise RecoveryError("recovery_restore_capacity_insufficient")
    destination.mkdir(exist_ok=False)
    deadline = monotonic() + TIME_LIMIT_SECONDS
    with zipfile.ZipFile(directory / "tree.zip") as archive:
        for item in manifest.files:
            target = destination / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.resolve().is_relative_to(destination):
                raise RecoveryError("recovery_restore_path_escape")
            digest, size = sha256(), 0
            with archive.open(item.path) as source, target.open("xb") as output:
                while block := source.read(CHUNK_BYTES):
                    check_budget(destination, deadline)
                    size += len(block)
                    if size > item.size:
                        raise RecoveryError("recovery_restore_size_mismatch")
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if size != item.size or digest.hexdigest() != item.sha256:
                raise RecoveryError("recovery_restore_hash_mismatch")
    (destination / "data").mkdir(exist_ok=True)
    db_result = restore_copy(directory / "database", destination / "data" / "aurex.db")
    result = {
        "schema_version": "aurex_application_restore_v2",
        "status": "RESTORED_FILES_AND_DATABASE",
        "readback_verified": True,
        "scope": manifest.scope,
        "manifest_sha256": file_hash(directory / "manifest.json"),
        "included_files": len(manifest.files),
        "omitted_archives": len(manifest.omitted_archives),
        "omitted_bytes": sum(item.size for item in manifest.omitted_archives),
        "database": db_result,
        "credentials_restored": False,
        "dependency_installation_verified": False,
        "application_start_verified": False,
        "full_historical_evidence_restored": manifest.scope == "FULL_EVIDENCE",
        "live_authority": False,
    }
    verify_restored(directory, destination)
    with (destination / "_recovery" / "restore.json").open("xb") as output:
        output.write(encoded(result))
        output.flush()
        os.fsync(output.fileno())
    return result


def verify_restored(directory: Path, destination: Path) -> dict:
    manifest = verify_bundle(directory)
    destination = destination.resolve(strict=True)
    for item in manifest.files:
        path = destination / item.path
        for candidate in (path, *path.parents):
            if candidate == destination:
                break
            regular(candidate)
        if path.stat().st_size != item.size or file_hash(path) != item.sha256:
            raise RecoveryError("recovery_restored_file_changed")
    expected = verify_backup(directory / "database")
    deadline = monotonic() + 120
    with closing(read_connection(destination / "data" / "aurex.db", deadline)) as db:
        if snapshot(db, deadline) != expected.snapshot:
            raise RecoveryError("recovery_restored_database_changed")
    return {
        "status": "VERIFIED_RESTORED_CONTENT",
        "scope": manifest.scope,
        "application_start_verified": False,
        "live_authority": False,
    }
