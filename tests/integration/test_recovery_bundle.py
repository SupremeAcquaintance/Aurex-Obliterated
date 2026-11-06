"""Recovery copies only; fixture files are not a claim of working application restore."""

import json
import shutil
import subprocess
import sys
import zipfile
from types import SimpleNamespace

import pytest

from aurex.config.settings import Settings
from aurex.db import recovery_bundle as recovery
from aurex.db.backup import file_hash
from tests.integration.test_database_backup import database as database
from tests.integration.test_native_bar_processing import engine as engine
from tests.integration.test_native_bar_processing import template_database as template_database


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "application"
    root.mkdir()
    for folder in recovery.SOURCE_DIRECTORIES:
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "fixture.txt").write_bytes(b"retained fixture\n")
    for name in recovery.SOURCE_FILES:
        (root / name).write_text("non-secret fixture\n")
    (root / "data/evidence/archive.zip").write_bytes(b"raw historical archive bytes")
    (root / "data/evidence/incomplete.part").write_bytes(b"retained failed attempt")
    (root / ".env").write_text("TOP_LEVEL_SECRET=must-not-be-bundled\n")
    return root


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        live_trading_enabled=False,
        live_execution_adapter="disabled",
        environment="local",
        webhook_secret="must-not-be-bundled",
        paper_commission_bps="11",
        paper_latency_ms=700,
    )


def make(root, database, tmp_path, settings, scope="FULL_EVIDENCE"):
    bundle = tmp_path / "bundle"
    manifest = recovery.create_bundle(root, database, bundle, scope, settings)
    return bundle, manifest


def test_complete_fixture_bundle_roundtrip(root, database, tmp_path, settings):
    original = file_hash(database)
    bundle, manifest = make(root, database, tmp_path, settings)
    assert recovery.verify_bundle(bundle) == manifest
    assert manifest.scope == "FULL_EVIDENCE" and not manifest.omitted_archives
    assert not manifest.credentials_included and not manifest.application_start_verified
    target = tmp_path / "restored"
    result = recovery.restore_bundle(bundle, target)
    assert result["schema_version"] == "aurex_application_restore_v2"
    assert result["readback_verified"] is True
    assert json.loads((target / "_recovery/restore.json").read_bytes()) == result
    assert result["full_historical_evidence_restored"]
    assert recovery.verify_restored(bundle, target)["status"] == "VERIFIED_RESTORED_CONTENT"
    for name in recovery.inventory(root):
        assert (target / name).read_bytes() == (root / name).read_bytes()
    assert not (target / ".env").exists()
    config = json.loads((target / "_recovery/configuration.json").read_bytes())
    assert config["paper_commission_bps"] == "11" and config["paper_latency_ms"] == 700
    assert set(config) == recovery.CONFIG_FIELDS
    assert "must-not-be-bundled" not in json.dumps(config)
    assert "database_url" not in config and "webhook_secret" not in config
    assert file_hash(database) == original


def test_operational_scope_records_every_omitted_raw_archive(root, database, tmp_path, settings):
    bundle, manifest = make(root, database, tmp_path, settings, "OPERATIONAL_WITHOUT_RAW_ARCHIVES")
    assert {item.path for item in manifest.omitted_archives} == {
        "data/evidence/archive.zip",
        "data/evidence/incomplete.part",
    }
    result = recovery.restore_bundle(bundle, tmp_path / "restored")
    assert not result["full_historical_evidence_restored"] and result["omitted_archives"] == 2
    assert not (tmp_path / "restored/data/evidence/archive.zip").exists()
    assert (root / "data/evidence/archive.zip").exists()
    with pytest.raises(ValueError, match="full_scope"):
        recovery.RecoveryManifest.model_validate(
            {**manifest.model_dump(), "scope": "FULL_EVIDENCE"}
        )


def test_cannot_overwrite_bundle_or_destination(root, database, tmp_path, settings):
    bundle, _ = make(root, database, tmp_path, settings)
    with pytest.raises(FileExistsError):
        recovery.create_bundle(root, database, bundle, "FULL_EVIDENCE", settings)
    with pytest.raises(FileExistsError):
        recovery.restore_bundle(bundle, root)


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/tmp/escape",
        "C:/escape",
        "src/../../escape",
        "src\\escape",
        "src/CON.txt",
        "src/file:stream",
        "src/file.",
        "src//file",
        "src/./file",
        "data/aurex.db",
        ".env",
    ],
)
def test_unsafe_or_unscoped_paths_rejected(path):
    with pytest.raises(ValueError):
        recovery.RecoveryFile(path=path, size=1, sha256="0" * 64)


def test_nested_secret_filename_blocks_capture(root, database, tmp_path, settings):
    (root / "src/.env").write_text("SECRET=do-not-copy")
    with pytest.raises(recovery.RecoveryError, match="sensitive_filename"):
        make(root, database, tmp_path, settings)
    assert not (tmp_path / "bundle").exists()


def test_capacity_failure_creates_nothing(root, database, tmp_path, settings, monkeypatch):
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    plan = recovery.recovery_plan(root, database, tmp_path, "FULL_EVIDENCE")
    assert plan["status"] == "BLOCKED_INSUFFICIENT_RECOVERY_SPACE"
    with pytest.raises(recovery.RecoveryError, match="insufficient_space"):
        make(root, database, tmp_path, settings)
    assert not (tmp_path / "bundle").exists()


def test_no_valid_manifest_after_time_budget_failure(
    root, database, tmp_path, settings, monkeypatch
):
    monkeypatch.setattr(recovery, "TIME_LIMIT_SECONDS", -1)
    with pytest.raises(recovery.RecoveryError, match="time_budget"):
        make(root, database, tmp_path, settings)
    assert not (tmp_path / "bundle/manifest.json").exists()


def test_source_tree_change_prevents_completed_manifest(
    root, database, tmp_path, settings, monkeypatch
):
    original = recovery.runtime_inventory

    def changed():
        (root / "src/fixture.txt").write_text("changed after source inventory")
        return original()

    monkeypatch.setattr(recovery, "runtime_inventory", changed)
    with pytest.raises(recovery.RecoveryError, match="source_.*changed"):
        make(root, database, tmp_path, settings)
    assert not (tmp_path / "bundle/manifest.json").exists()


def test_archive_corruption_prevents_any_restore(root, database, tmp_path, settings):
    bundle, _ = make(root, database, tmp_path, settings)
    with (bundle / "tree.zip").open("ab") as target:
        target.write(b"tampered")
    with pytest.raises(recovery.RecoveryError, match="archive_hash"):
        recovery.restore_bundle(bundle, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_rehashed_member_change_still_rejected(root, database, tmp_path, settings):
    bundle, _ = make(root, database, tmp_path, settings)
    archive = bundle / "tree.zip"
    with zipfile.ZipFile(archive, "a") as writer:
        writer.writestr("src/unexpected.py", "print('extra')")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["archive_sha256"] = file_hash(archive)
    manifest["archive_bytes"] = archive.stat().st_size
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(recovery.RecoveryError, match="inventory_mismatch"):
        recovery.restore_bundle(bundle, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_restored_file_corruption_is_detected(root, database, tmp_path, settings):
    bundle, _ = make(root, database, tmp_path, settings)
    target = tmp_path / "restored"
    recovery.restore_bundle(bundle, target)
    (target / "src/fixture.txt").write_bytes(b"corrupt")
    with pytest.raises(recovery.RecoveryError, match="restored_file_changed"):
        recovery.verify_restored(bundle, target)


def test_live_settings_never_captured(root, database, tmp_path, settings):
    with pytest.raises(recovery.RecoveryError, match="non_live"):
        make(root, database, tmp_path, settings.model_copy(update={"live_trading_enabled": True}))


def test_manifest_cannot_drop_source_roots_or_duplicate_case(root, database, tmp_path, settings):
    _, manifest = make(root, database, tmp_path, settings)
    data = manifest.model_dump()
    data["files"] = [item for item in data["files"] if not item["path"].startswith("src/")]
    with pytest.raises(ValueError, match="required_application"):
        recovery.RecoveryManifest.model_validate(data)
    data = manifest.model_dump()
    data["files"] = list(data["files"])
    data["files"].append({**data["files"][0], "path": data["files"][0]["path"].upper()})
    with pytest.raises(ValueError):
        recovery.RecoveryManifest.model_validate(data)


def test_operational_archive_matching_is_case_insensitive(root, database, tmp_path, settings):
    (root / "data/evidence/UPPER.ZIP").write_bytes(b"retained uppercase archive")
    _, manifest = make(root, database, tmp_path, settings, "OPERATIONAL_WITHOUT_RAW_ARCHIVES")
    assert len(manifest.omitted_archives) == 3
    assert any(item.path.endswith("UPPER.ZIP") for item in manifest.omitted_archives)


def test_recovered_application_script_refuses_original_tree(tmp_path):
    from aurex.api.private_runtime import ROOT

    for environment in (tmp_path / "wrong-environment", sys.prefix):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/rehearse_recovered_application.py",
                "--expected-environment",
                str(environment),
                "--report-directory",
                str(tmp_path / "report"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
        assert json.loads(result.stdout)["status"] == "BLOCKED"
        assert not (tmp_path / "report").exists()


def test_failed_final_readback_never_publishes_launchable_restore_receipt(
    root, database, tmp_path, settings, monkeypatch
):
    bundle, _ = make(root, database, tmp_path, settings)

    def failed(*args):
        raise recovery.RecoveryError("simulated_final_readback_failure")

    monkeypatch.setattr(recovery, "verify_restored", failed)
    target = tmp_path / "restored"
    with pytest.raises(recovery.RecoveryError, match="final_readback_failure"):
        recovery.restore_bundle(bundle, target)
    assert (target / "data/aurex.db").is_file()
    assert not (target / "_recovery/restore.json").exists()


@pytest.mark.parametrize(
    "receipt_fields",
    [
        {},
        {"schema_version": "aurex_application_restore_v1", "readback_verified": True},
        {"schema_version": "aurex_application_restore_v2"},
        {"schema_version": "aurex_application_restore_v2", "readback_verified": False},
        {"schema_version": "aurex_application_restore_v2", "readback_verified": "true"},
        {"schema_version": "aurex_application_restore_v2", "readback_verified": 1},
    ],
)
def test_restored_launcher_rejects_unverified_or_legacy_receipts(tmp_path, receipt_fields):
    from aurex.api.private_runtime import ROOT

    root = tmp_path / "restored"
    (root / "scripts").mkdir(parents=True)
    (root / "_recovery").mkdir()
    script = root / "scripts/rehearse_recovered_application.py"
    shutil.copyfile(ROOT / "scripts/rehearse_recovered_application.py", script)
    receipt = {"status": "RESTORED_FILES_AND_DATABASE", "live_authority": False, **receipt_fields}
    (root / "_recovery/restore.json").write_text(json.dumps(receipt))
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--expected-environment",
            sys.prefix,
            "--report-directory",
            str(tmp_path / "report"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["reason"] == "restored_tree_receipt_required"
    assert not (tmp_path / "report").exists()
