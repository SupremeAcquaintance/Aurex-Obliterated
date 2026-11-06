from pathlib import Path

from aurex.backtest_engine import s5_measurement_readiness as readiness


def test_current_measurement_checkpoint_verifies():
    assert readiness.verify_measurement_checkpoint(Path.cwd())


def test_missing_measurement_checkpoint_blocks(tmp_path):
    assert not readiness.verify_measurement_checkpoint(tmp_path)


def test_changed_measurement_output_blocks(monkeypatch):
    digest = readiness.file_digest

    def changed(path):
        return "0" * 64 if path.name.endswith("monthly_measurements_v2.jsonl") else digest(path)

    monkeypatch.setattr(readiness, "file_digest", changed)
    assert not readiness.verify_measurement_checkpoint(Path.cwd())


def test_changed_measurement_implementation_blocks(monkeypatch):
    digest = readiness.file_digest

    def changed(path):
        return "0" * 64 if path.name == "s5_amended_measurement.py" else digest(path)

    monkeypatch.setattr(readiness, "file_digest", changed)
    assert not readiness.verify_measurement_checkpoint(Path.cwd())
