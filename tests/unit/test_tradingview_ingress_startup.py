import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("overrides,blocker", [
    ({"AUREX_WEBHOOK_SECRET": "fixture-too-short"}, "INVALID_SETTINGS"),
    ({"AUREX_LIVE_TRADING_ENABLED": "not-a-boolean"}, "INVALID_SETTINGS"),
    ({"AUREX_DATABASE_URL": "invalid database fixture"},
     "CURRENT_LOCAL_SQLITE_MIGRATION_REQUIRED"),
])
def test_invalid_startup_is_sanitized_in_a_fresh_process(overrides, blocker):
    secret = "startup-fixture-only-" + "a" * 40
    environment = {key: value for key, value in os.environ.items() if not key.startswith("AUREX_")}
    environment.update({
        "AUREX_ENVIRONMENT": "production",
        "AUREX_WEBHOOK_SECRET": secret,
        "AUREX_DATABASE_URL": "sqlite:///:memory:",
    } | overrides)
    result = subprocess.run(
        [sys.executable, "scripts/run_tradingview_ingress.py", "--check"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 2
    assert result.stderr == ""
    body = json.loads(result.stdout)
    assert body["status"] == "BLOCKED"
    assert blocker in body["blockers"]
    assert environment["AUREX_WEBHOOK_SECRET"] not in result.stdout
    assert environment["AUREX_DATABASE_URL"] not in result.stdout
