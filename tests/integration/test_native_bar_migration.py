from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from aurex.db.models import Account, NativeBarOutcome
from tests.integration.test_native_signal_intake import settings as settings

ROOT = Path(__file__).resolve().parents[2]


def test_native_outcome_migration_preserves_existing_account_and_roundtrips(
    tmp_path, monkeypatch, settings
):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    settings = settings.model_copy(update={"database_url": url})
    monkeypatch.setattr("aurex.config.settings.get_settings", lambda: settings)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "infra" / "alembic"))
    command.upgrade(config, "20260718_0029")
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                Account(
                    name="fixture-account",
                    mode="paper",
                    currency="USD",
                    starting_equity=Decimal("100"),
                    current_equity=Decimal("99.25"),
                )
            )
        for _ in range(2):
            command.upgrade(config, "20260930_0030")
            inspector = inspect(engine)
            assert {column["name"] for column in inspector.get_columns("native_bar_outcomes")} == {
                column.name for column in NativeBarOutcome.__table__.columns
            }
            assert {index["name"] for index in inspector.get_indexes("native_bar_outcomes")} == {
                "uq_native_bar_stream_sequence",
                "uq_native_bar_stream_candle",
            }
            assert all(index["unique"] for index in inspector.get_indexes("native_bar_outcomes"))
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "20260930_0030"
                )
                assert connection.scalar(text("SELECT count(*) FROM native_bar_outcomes")) == 0
            command.downgrade(config, "20260718_0029")
            assert "native_bar_outcomes" not in inspect(engine).get_table_names()
        with Session(engine) as session:
            account = session.query(Account).one()
            assert account.name == "fixture-account"
            assert account.current_equity == Decimal("99.25")
    finally:
        engine.dispose()
