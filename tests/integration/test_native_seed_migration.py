from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from aurex.db.models import NativeBarOutcome, NativeHistorySeed
from tests.integration.test_native_signal_intake import settings as settings

ROOT = Path(__file__).resolve().parents[2]


def test_seed_migration_preserves_existing_receipts_and_does_not_invent_seed(
    tmp_path, monkeypatch, settings
):
    url = f"sqlite:///{(tmp_path / 'seed-migration.db').as_posix()}"
    monkeypatch.setattr(
        "aurex.config.settings.get_settings",
        lambda: settings.model_copy(update={"database_url": url}),
    )
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "infra" / "alembic"))
    command.upgrade(config, "20260930_0030")
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                NativeBarOutcome(
                    stream_key="native-spot-main",
                    sequence=1,
                    candle_id="1" * 64,
                    outcome="NO_SIGNAL",
                    evidence={"fixture": "preserve only"},
                    evidence_hash="2" * 64,
                )
            )
        command.upgrade(config, "head")
        assert {c["name"] for c in inspect(engine).get_columns("native_history_seeds")} == {
            c.name for c in NativeHistorySeed.__table__.columns
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20261004_0031"
            )
            assert connection.scalar(text("SELECT count(*) FROM native_history_seeds")) == 0
        command.downgrade(config, "20260930_0030")
        assert "native_history_seeds" not in inspect(engine).get_table_names()
        with Session(engine) as session:
            assert session.scalars(select(NativeBarOutcome)).one().evidence == {
                "fixture": "preserve only"
            }
    finally:
        engine.dispose()
