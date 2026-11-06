"""Dependency escrow contracts; mocked installs are not offline-install evidence."""

import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from aurex.db import recovery_environment as recovery
from aurex.db.recovery_bundle import RecoveryError


def fixture_runtime():
    return {
        "python": "3.12.14",
        "implementation": "cpython",
        "platform": "win-amd64",
        "sqlite": "3.45.3",
        "packages": {"fixture-dep": "1.2.3"},
        "aurex_recovered_from_source": True,
    }


def wheel(path):
    with zipfile.ZipFile(path, "w") as writer:
        writer.writestr(
            "fixture_dep-1.2.3.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: fixture-dep\nVersion: 1.2.3\n",
        )


@pytest.fixture
def wheelhouse(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "runtime_inventory", fixture_runtime)

    def download(command, **kwargs):
        destination = Path(command[command.index("--dest") + 1])
        wheel(destination / "fixture_dep-1.2.3-py3-none-any.whl")
        assert "--only-binary=:all:" in command and "--no-deps" in command
        assert command[command.index("--index-url") + 1] == "https://pypi.org/simple"
        assert kwargs["env"]["PIP_CONFIG_FILE"] == os.devnull
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(recovery.subprocess, "run", download)
    directory = tmp_path / "wheelhouse"
    recovery.prepare_wheelhouse(directory)
    return directory


def test_clean_environment_never_forwards_credentials_or_pip_configuration(monkeypatch):
    for name in ("AUREX_WEBHOOK_SECRET", "BINANCE_API_KEY", "PIP_EXTRA_INDEX_URL", "PYTHONPATH"):
        monkeypatch.setenv(name, "private-sentinel")
    result = recovery.clean_environment()
    assert "private-sentinel" not in result.values()
    assert result["PIP_CONFIG_FILE"] == os.devnull and result["PYTHONNOUSERSITE"] == "1"


def test_wheelhouse_identity_hashes_and_lock_are_bound(wheelhouse):
    result = recovery.verify_wheelhouse(wheelhouse)
    assert result["runtime"]["packages"] == {"fixture-dep": "1.2.3"}
    assert not result["offline_install_verified"]
    assert (
        (wheelhouse / "requirements.lock")
        .read_text()
        .startswith("fixture-dep==1.2.3 --hash=sha256:")
    )


@pytest.mark.parametrize("target", ["wheel", "lock", "manifest"])
def test_modified_escrow_is_rejected(wheelhouse, target):
    if target == "wheel":
        with next((wheelhouse / "wheels").iterdir()).open("ab") as output:
            output.write(b"changed")
    elif target == "lock":
        (wheelhouse / "requirements.lock").write_text("fixture-dep>=0\n")
    else:
        path = wheelhouse / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["offline_install_verified"] = True
        path.write_text(json.dumps(manifest))
    with pytest.raises(RecoveryError):
        recovery.verify_wheelhouse(wheelhouse)


@pytest.mark.parametrize(
    "name,version", [("bad\n--index-url", "1"), ("valid", "1\n--editable ."), ("aurex", "0.1.0")]
)
def test_requirement_injection_or_editable_aurex_cannot_enter_lock(name, version):
    runtime = fixture_runtime()
    runtime["packages"] = {name: version}
    with pytest.raises(RecoveryError):
        recovery.validate_runtime(runtime)


def test_offline_environment_contract_is_new_isolated_and_exact(wheelhouse, tmp_path, monkeypatch):
    calls = []

    class Builder:
        def __init__(self, **kwargs):
            assert kwargs == {"with_pip": True, "system_site_packages": False, "clear": False}

        def create(self, destination):
            assert destination.exists() and list(destination.iterdir()) == []

    def run(command, **kwargs):
        calls.append(command)
        if "-c" in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"fixture-dep": "1.2.3"}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(recovery.venv, "EnvBuilder", Builder)
    monkeypatch.setattr(recovery.subprocess, "run", run)
    destination = tmp_path / "new-environment"
    result = recovery.create_environment(wheelhouse, destination)
    assert result["status"] == "VERIFIED_OFFLINE_ENVIRONMENT"
    assert all(flag in calls[0] for flag in ("--no-index", "--no-deps", "--require-hashes"))
    assert "check" in calls[1]
    assert not result["application_start_verified"] and not result["system_site_packages"]
    with pytest.raises(FileExistsError):
        recovery.create_environment(wheelhouse, destination)


def test_different_interpreter_refuses_before_creating_destination(
    wheelhouse, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        recovery, "runtime_inventory", lambda: {**fixture_runtime(), "python": "3.13.0"}
    )
    with pytest.raises(RecoveryError, match="interpreter_platform"):
        recovery.create_environment(wheelhouse, tmp_path / "environment")
    assert not (tmp_path / "environment").exists()


def test_download_failure_does_not_publish_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "runtime_inventory", fixture_runtime)
    monkeypatch.setattr(recovery.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(RecoveryError, match="download_failed"):
        recovery.prepare_wheelhouse(tmp_path / "failed")
    assert not (tmp_path / "failed/manifest.json").exists()
