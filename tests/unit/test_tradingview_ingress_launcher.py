import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

from aurex.api.webhook_ingress import create_webhook_ingress, ingress_configuration_blockers
from aurex.config.settings import Settings
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES, StrategyLifecycleStatus
from scripts.run_tradingview_ingress import database_schema_check, deployment_check, server_config

SECRET = "launcher-fixture-only-" + "a" * 40


@pytest.fixture(autouse=True)
def migrated_database(monkeypatch, tmp_path):
    path = tmp_path / "fixture.db"
    migrations = Path(__file__).resolve().parents[2] / "infra" / "alembic"
    with sqlite3.connect(path) as connection:
        connection.execute("create table alembic_version (version_num text)")
        connection.executemany(
            "insert into alembic_version values (?)",
            [(head,) for head in ScriptDirectory(str(migrations)).get_heads()],
        )
    monkeypatch.setenv("AUREX_DATABASE_URL", "sqlite:///" + path.as_posix())


def test_preflight_is_sanitized_and_does_not_confuse_local_config_with_delivery():
    settings = Settings(_env_file=None, webhook_secret=SECRET)
    report = deployment_check(settings, None, None)
    assert report["status"] == "BLOCKED"
    assert report["blockers"] == ["TLS_CERTIFICATE_AND_PRIVATE_KEY_REQUIRED"]
    assert report["external_delivery_proven"] is False
    assert report["public_reachability_verified"] is False
    assert report["live_authority"] is False
    assert SECRET not in json.dumps(report)


@pytest.mark.parametrize("changes,blocker", [
    ({"webhook_secret": "local-dev-secret"}, "DEDICATED_HIGH_ENTROPY_WEBHOOK_SECRET_REQUIRED"),
    ({"webhook_secret": " x" + "a" * 40}, "DEDICATED_HIGH_ENTROPY_WEBHOOK_SECRET_REQUIRED"),
    ({"live_trading_enabled": True}, "LIVE_EXECUTION_MUST_BE_DISABLED"),
    ({"live_execution_adapter": "testnet"}, "LIVE_EXECUTION_MUST_BE_DISABLED"),
    ({"tradingview_webhook_source_networks": "0.0.0.0/0"}, "REVIEWED_EXACT_SENDER_IPS_REQUIRED"),
])
def test_unsafe_launch_is_blocked(changes, blocker):
    settings = Settings(_env_file=None, **({"webhook_secret": SECRET} | changes))
    assert blocker in ingress_configuration_blockers(settings)
    with pytest.raises(ValueError, match=blocker):
        create_webhook_ingress(settings)


def test_nonretired_campaign_is_blocked(monkeypatch):
    definition = REGISTERED_STRATEGIES["trend_pullback_v1"]
    monkeypatch.setitem(REGISTERED_STRATEGIES, "trend_pullback_v1", replace(
        definition, lifecycle_status=StrategyLifecycleStatus.RESEARCH_ONLY
    ))
    assert "SAFE_REJECTION_CANDIDATE_MUST_REMAIN_RETIRED" in ingress_configuration_blockers(
        Settings(_env_file=None, webhook_secret=SECRET)
    )


def test_unusable_tls_paths_do_not_leak_paths_or_secret():
    settings = Settings(_env_file=None, webhook_secret=SECRET)
    report = deployment_check(settings, "not-present-sensitive-cert", "not-present-sensitive-key")
    assert report["blockers"] == ["TLS_CERTIFICATE_OR_KEY_UNUSABLE"]
    assert "not-present-sensitive" not in json.dumps(report)


def test_uvicorn_settings_ignore_environment_proxy_trust(monkeypatch):
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    settings = Settings(_env_file=None, webhook_secret=SECRET)
    config = server_config(settings, "fixture.crt", "fixture.key", "127.0.0.1")
    assert config.proxy_headers is False
    assert config.forwarded_allow_ips == ""
    assert config.access_log is False
    assert config.port == 443
    assert config.workers == 1
    assert config.ssl_keyfile_password == ""


def test_database_check_does_not_create_missing_file(tmp_path):
    missing = tmp_path / "missing.db"
    settings = Settings(_env_file=None, database_url="sqlite:///" + missing.as_posix())
    assert database_schema_check(settings) is False
    assert not missing.exists()


def test_stale_schema_is_blocked(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table alembic_version (version_num text)")
        connection.execute("insert into alembic_version values ('obsolete')")
    settings = Settings(_env_file=None, database_url="sqlite:///" + path.as_posix())
    assert database_schema_check(settings) is False
    assert "CURRENT_LOCAL_SQLITE_MIGRATION_REQUIRED" in deployment_check(
        settings, None, None
    )["blockers"]


def test_nonlocal_database_is_not_contacted():
    settings = Settings(_env_file=None, database_url="postgresql://example.invalid/aurex")
    assert database_schema_check(settings) is False
