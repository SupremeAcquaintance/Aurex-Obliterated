"""Git export boundaries and byte preservation, without changing the real index."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, capture_output=True)
    for name in (".gitignore", ".gitattributes"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    return tmp_path


@pytest.mark.parametrize(
    "path,ignored",
    [
        ("src/aurex/api/app.py", False),
        ("docs/01_IMPLEMENTATION_LOG.md", False),
        ("docs/10_PROJECT_CONTROL.md", False),
        ("docs/46_AUREX_DELIVERY_REBASELINE.md", False),
        ("tests/fixtures/candles.csv", False),
        ("migration/donor-patches/My-Krypt-Trader.patch", False),
        (".gitmodules", False),
        (".env.example", False),
        ("deploy/worker/.dev.vars.example", False),
        ("data/evidence/aurex_strategy_factory_readiness_current_result_v64.json", False),
        ("data/evidence/jam_successor_development_event_ledger_v1.jsonl", False),
        ("data/evidence/research-notes.md", False),
        (".env.production", True),
        ("deploy/worker/.dev.vars", True),
        ("credentials/private.pem", True),
        (".venv/Lib/site-packages/example.py", True),
        ("deploy/worker/node_modules/example/index.js", True),
        (".tmp/verification.json", True),
        (".aurex-demo-userdata/Network/Cookies", True),
        ("data/aurex.db", True),
        ("data/aurex.db-wal", True),
        ("data/backups/recovery/source.py", True),
        ("data/evidence/native_supervisor_public_20261009_v1/diagnostic.db", True),
        ("data/evidence/source_snapshots/snapshot.json", True),
        ("data/evidence/download/BTCUSDT.zip", True),
        ("data/evidence/mirror.git/objects/pack/example.pack", True),
        ("data/evidence/feature_rows.parquet", True),
        ("data/raw/candles.csv", True),
    ],
)
def test_transfer_boundary(repository, path, ignored):
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", path], cwd=repository
    )
    assert result.returncode == (0 if ignored else 1)


def test_autocrlf_cannot_change_evidence_bound_bytes(repository):
    payload = b"line one\r\nline two\n"
    command = ["git", "-c", "core.autocrlf=true", "hash-object", "--stdin"]
    raw = subprocess.run(command, cwd=repository, input=payload, capture_output=True, check=True)
    for path in ("src/aurex/sample.py", "data/evidence/sample.json"):
        filtered = subprocess.run(
            [*command, f"--path={path}"],
            cwd=repository,
            input=payload,
            capture_output=True,
            check=True,
        )
        assert filtered.stdout == raw.stdout
        assert not filtered.stderr
