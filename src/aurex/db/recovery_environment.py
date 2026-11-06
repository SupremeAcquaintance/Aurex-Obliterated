"""Pinned binary dependency escrow and isolated, offline environment reconstruction."""

import json
import os
import re
import shutil
import subprocess
import sys
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path

from aurex.db.backup import file_hash
from aurex.db.recovery_bundle import RecoveryError, encoded, regular, runtime_inventory

MINIMUM_FREE_BYTES = 2 * 1024**3


def clean_environment() -> dict[str, str]:
    allowed = {
        "SYSTEMROOT",
        "WINDIR",
        "PATH",
        "TEMP",
        "TMP",
        "COMSPEC",
        "PATHEXT",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "LANG",
        "LC_ALL",
    }
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result["PIP_CONFIG_FILE"] = os.devnull
    result["PYTHONNOUSERSITE"] = "1"
    return result


def validate_runtime(runtime: dict) -> None:
    if set(runtime) != {
        "python",
        "implementation",
        "platform",
        "sqlite",
        "packages",
        "aurex_recovered_from_source",
    }:
        raise RecoveryError("recovery_runtime_shape_invalid")
    if runtime["aurex_recovered_from_source"] is not True or not isinstance(
        runtime["packages"], dict
    ):
        raise RecoveryError("recovery_runtime_source_invalid")
    if not 1 <= len(runtime["packages"]) <= 256:
        raise RecoveryError("recovery_runtime_package_limit")
    for name, version in runtime["packages"].items():
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name)
            or name == "aurex"
            or not isinstance(version, str)
            or not re.fullmatch(r"[A-Za-z0-9.+!-]+", version)
        ):
            raise RecoveryError("recovery_runtime_requirement_invalid")


def wheel_record(path: Path) -> dict:
    regular(path)
    if path.is_symlink() or path.suffix != ".whl" or not 0 < path.stat().st_size <= 256 * 1024**2:
        raise RecoveryError("recovery_wheel_file_invalid")
    with zipfile.ZipFile(path) as wheel:
        metadata = [
            item for item in wheel.infolist() if item.filename.endswith(".dist-info/METADATA")
        ]
        if len(metadata) != 1 or metadata[0].file_size > 1024**2:
            raise RecoveryError("recovery_wheel_metadata_invalid")
        message = BytesParser().parsebytes(wheel.read(metadata[0]), headersonly=True)
        if len(message.get_all("Name", [])) != 1 or len(message.get_all("Version", [])) != 1:
            raise RecoveryError("recovery_wheel_identity_invalid")
        name = re.sub(r"[-_.]+", "-", message["Name"]).lower()
        version = message["Version"]
    return {
        "name": name,
        "version": version,
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": file_hash(path),
    }


def lock_text(records: list[dict]) -> str:
    return "".join(
        f"{item['name']}=={item['version']} --hash=sha256:{item['sha256']}\n"
        for item in sorted(records, key=lambda item: item["name"])
    )


def prepare_wheelhouse(directory: Path) -> dict:
    directory = directory.resolve()
    runtime = runtime_inventory()
    validate_runtime(runtime)
    if shutil.disk_usage(directory.parent).free < MINIMUM_FREE_BYTES:
        raise RecoveryError("recovery_wheelhouse_disk_limit")
    directory.mkdir(exist_ok=False)
    requirements = directory / "requested.txt"
    with requirements.open("x", encoding="ascii", newline="\n") as output:
        output.write(
            "".join(f"{name}=={version}\n" for name, version in runtime["packages"].items())
        )
    wheels = directory / "wheels"
    wheels.mkdir()
    with (directory / "download.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--disable-pip-version-check",
                "download",
                "--index-url",
                "https://pypi.org/simple",
                "--no-cache-dir",
                "--no-deps",
                "--only-binary=:all:",
                "--timeout",
                "20",
                "--retries",
                "2",
                "--dest",
                str(wheels),
                "--requirement",
                str(requirements),
            ],
            env=clean_environment(),
            stdout=log,
            stderr=log,
            timeout=1200,
        )
    if result.returncode:
        raise RecoveryError("recovery_wheel_download_failed")
    records = [wheel_record(path) for path in sorted(wheels.iterdir())]
    versions = {item["name"]: item["version"] for item in records}
    if len(versions) != len(records) or versions != runtime["packages"]:
        raise RecoveryError("recovery_wheelhouse_package_mismatch")
    with (directory / "requirements.lock").open("x", encoding="ascii", newline="\n") as output:
        output.write(lock_text(records))
    manifest = {
        "schema_version": "aurex_recovery_wheelhouse_v1",
        "runtime": runtime,
        "wheels": records,
        "lock_sha256": file_hash(directory / "requirements.lock"),
        "index": "https://pypi.org/simple",
        "offline_install_verified": False,
        "interpreter_included": False,
        "live_authority": False,
    }
    with (directory / "manifest.json").open("xb") as output:
        output.write(encoded(manifest))
        output.flush()
        os.fsync(output.fileno())
    verify_wheelhouse(directory)
    return manifest


def verify_wheelhouse(directory: Path) -> dict:
    regular(directory)
    regular(directory / "wheels")
    path = directory / "manifest.json"
    if not 0 < path.stat().st_size <= 1024**2:
        raise RecoveryError("recovery_wheelhouse_manifest_limit")
    manifest = json.loads(path.read_bytes())
    if (
        set(manifest)
        != {
            "schema_version",
            "runtime",
            "wheels",
            "lock_sha256",
            "index",
            "offline_install_verified",
            "interpreter_included",
            "live_authority",
        }
        or manifest["schema_version"] != "aurex_recovery_wheelhouse_v1"
        or manifest["index"] != "https://pypi.org/simple"
        or any(
            manifest[key] is not False
            for key in ("offline_install_verified", "interpreter_included", "live_authority")
        )
    ):
        raise RecoveryError("recovery_wheelhouse_manifest_invalid")
    validate_runtime(manifest["runtime"])
    actual = [wheel_record(path) for path in sorted((directory / "wheels").iterdir())]
    if (
        actual != manifest["wheels"]
        or {item["name"]: item["version"] for item in actual} != manifest["runtime"]["packages"]
    ):
        raise RecoveryError("recovery_wheelhouse_content_mismatch")
    lock = directory / "requirements.lock"
    if file_hash(lock) != manifest["lock_sha256"] or lock.read_text(encoding="ascii") != lock_text(
        actual
    ):
        raise RecoveryError("recovery_dependency_lock_mismatch")
    return manifest


def create_environment(wheelhouse: Path, destination: Path) -> dict:
    manifest = verify_wheelhouse(wheelhouse)
    runtime = manifest["runtime"]
    current = runtime_inventory()
    if any(
        runtime[key] != current[key] for key in ("python", "implementation", "platform", "sqlite")
    ):
        raise RecoveryError("recovery_interpreter_platform_mismatch")
    destination = destination.resolve()
    if shutil.disk_usage(destination.parent).free < MINIMUM_FREE_BYTES:
        raise RecoveryError("recovery_environment_disk_limit")
    destination.mkdir(exist_ok=False)
    venv.EnvBuilder(with_pip=True, system_site_packages=False, clear=False).create(destination)
    python = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    with (destination / "install.log").open("x", encoding="utf-8") as log:
        for arguments in (
            [
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "--no-index",
                "--no-deps",
                "--require-hashes",
                "--find-links",
                str((wheelhouse / "wheels").resolve()),
                "--requirement",
                str((wheelhouse / "requirements.lock").resolve()),
            ],
            ["-m", "pip", "--disable-pip-version-check", "check"],
        ):
            result = subprocess.run(
                [str(python), *arguments],
                env=clean_environment(),
                stdout=log,
                stderr=log,
                timeout=300,
            )
            if result.returncode:
                raise RecoveryError("recovery_offline_install_failed")
    probe = subprocess.run(
        [
            str(python),
            "-c",
            "import importlib.metadata as m,json,re; "
            "print(json.dumps({re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version "
            "for d in m.distributions()}))",
        ],
        env=clean_environment(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if probe.returncode or json.loads(probe.stdout) != runtime["packages"]:
        raise RecoveryError("recovery_installed_versions_mismatch")
    result = {
        "status": "VERIFIED_OFFLINE_ENVIRONMENT",
        "package_count": len(runtime["packages"]),
        "wheelhouse_manifest_sha256": file_hash(wheelhouse / "manifest.json"),
        "python": runtime["python"],
        "platform": runtime["platform"],
        "system_site_packages": False,
        "application_start_verified": False,
        "interpreter_included": False,
        "live_authority": False,
    }
    with (destination / "recovery-environment.json").open("xb") as output:
        output.write(encoded(result))
        output.flush()
        os.fsync(output.fileno())
    return result
