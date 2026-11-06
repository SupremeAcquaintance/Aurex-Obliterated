import hashlib
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.binance_vision import (
    prepare_binance_vision_dataset,
    write_prepared_dataset,
)
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetEntry,
    audit_development_dataset_bundle,
    build_development_dataset_bundle,
    build_development_dataset_entry,
    inspect_canonical_ohlcv_csv,
)

START = datetime(2023, 1, 1, tzinfo=UTC)
END = datetime(2023, 2, 1, tzinfo=UTC)


def prepared_fixture(
    root: Path,
    symbol: str,
    *,
    missing_index: int | None = None,
) -> tuple[str, str, str]:
    archive_relative = f"development_bundle/archives/{symbol}"
    csv_relative = f"development_bundle/datasets/{symbol}.csv"
    manifest_relative = f"development_bundle/datasets/{symbol}.manifest.json"
    archive_directory = root / archive_relative
    archive_directory.mkdir(parents=True, exist_ok=True)
    archive_name = f"{symbol}-4h-2023-01.zip"
    archive_path = archive_directory / archive_name
    rows: list[str] = []
    cursor = START
    index = 0
    while cursor < END:
        if index != missing_index:
            timestamp_ms = int(cursor.timestamp() * 1000)
            rows.append(
                f"{timestamp_ms},100,102,99,101,10,{timestamp_ms + 14399999},"
                "1000,1,5,500,0\n"
            )
        cursor += timedelta(hours=4)
        index += 1
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(archive_name.replace(".zip", ".csv"), "".join(rows))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    Path(f"{archive_path}.CHECKSUM").write_text(
        f"{digest}  {archive_name}\n",
        encoding="utf-8",
    )
    prepared = prepare_binance_vision_dataset(
        archive_paths=[archive_path],
        symbol=symbol,
        timeframe="4h",
        data_start=START,
        data_end=END,
    )
    csv_path = root / csv_relative
    manifest_path = root / manifest_relative
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_prepared_dataset(
        prepared,
        csv_path=csv_path,
        manifest_path=manifest_path,
    )
    return archive_relative, csv_relative, manifest_relative


def entry(
    root: Path,
    symbol: str,
    *,
    role: str = "DECISION_CANDIDATE",
    missing_index: int | None = None,
):
    archive_relative, csv_relative, manifest_relative = prepared_fixture(
        root,
        symbol,
        missing_index=missing_index,
    )
    return build_development_dataset_entry(
        evidence_root=root,
        symbol=symbol,
        universe_role=role,
        partition_start=START,
        partition_end=END,
        archive_directory_relative_path=archive_relative,
        csv_relative_path=csv_relative,
        source_manifest_relative_path=manifest_relative,
    )


def test_ready_entry_binds_csv_manifest_archives_and_continuity(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")

    assert dataset.status == "READY"
    assert dataset.row_count == 186
    assert dataset.expected_row_count == 186
    assert dataset.archive_count == 1
    assert dataset.missing_timestamps == []
    assert dataset.first_timestamp == START
    assert dataset.last_timestamp == END - timedelta(hours=4)
    assert dataset.strategy_outcome_fields_inspected == []


def test_missing_candle_is_preserved_and_blocks_bundle(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT", missing_index=12)
    bundle = build_development_dataset_bundle(
        generated_at=datetime(2026, 7, 22, 16, tzinfo=UTC),
        universe_manifest_evidence_hash="a" * 64,
        contamination_ledger_hash="b" * 64,
        builder_contract_hash="c" * 64,
        partition_start=START,
        partition_end=END,
        expected_roles={"ADAUSDT": "DECISION_CANDIDATE"},
        entries=[dataset],
        limitations=["Fixture limitation."],
    )

    assert dataset.status == "BLOCKED"
    assert dataset.row_count == 185
    assert dataset.missing_timestamps == [START + timedelta(hours=48)]
    assert bundle.status == "BLOCKED"
    assert bundle.summary.blocked_symbols == ["ADAUSDT"]


def test_bundle_is_deterministic_and_rebuilds_from_files(tmp_path: Path) -> None:
    ada = entry(tmp_path, "ADAUSDT")
    btc = entry(tmp_path, "BTCUSDT", role="DEVELOPMENT_ONLY")
    expected_roles = {
        "ADAUSDT": "DECISION_CANDIDATE",
        "BTCUSDT": "DEVELOPMENT_ONLY",
    }
    bundle = build_development_dataset_bundle(
        generated_at=datetime(2026, 7, 22, 16, tzinfo=UTC),
        universe_manifest_evidence_hash="a" * 64,
        contamination_ledger_hash="b" * 64,
        builder_contract_hash="c" * 64,
        partition_start=START,
        partition_end=END,
        expected_roles=expected_roles,
        entries=[btc, ada],
        limitations=["Fixture limitation."],
    )

    audit = audit_development_dataset_bundle(
        bundle,
        evidence_root=tmp_path,
        expected_roles=expected_roles,
        current_builder_contract_hash="c" * 64,
    )

    assert bundle.status == "READY"
    assert bundle.summary.dataset_count == 2
    assert bundle.summary.total_rows == 372
    assert audit["status"] == "PASS"
    assert audit["deterministic_bundle_rebuild_matches"] is True


def test_audit_detects_csv_tampering(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")
    bundle = build_development_dataset_bundle(
        generated_at=datetime(2026, 7, 22, 16, tzinfo=UTC),
        universe_manifest_evidence_hash="a" * 64,
        contamination_ledger_hash="b" * 64,
        builder_contract_hash="c" * 64,
        partition_start=START,
        partition_end=END,
        expected_roles={"ADAUSDT": "DECISION_CANDIDATE"},
        entries=[dataset],
        limitations=["Fixture limitation."],
    )
    csv_path = tmp_path / dataset.csv_relative_path
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    audit = audit_development_dataset_bundle(
        bundle,
        evidence_root=tmp_path,
        expected_roles={"ADAUSDT": "DECISION_CANDIDATE"},
        current_builder_contract_hash="c" * 64,
    )

    assert audit["status"] == "BLOCKED"
    assert any(reason.startswith("entry_rebuild_failed:ADAUSDT") for reason in audit["reasons"])


def test_archive_tampering_is_rejected(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")
    archive = next((tmp_path / dataset.archive_directory_relative_path).glob("*.zip"))
    archive.write_bytes(archive.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="checksum mismatch"):
        build_development_dataset_entry(
            evidence_root=tmp_path,
            symbol=dataset.symbol,
            universe_role=dataset.universe_role,
            partition_start=START,
            partition_end=END,
            archive_directory_relative_path=dataset.archive_directory_relative_path,
            csv_relative_path=dataset.csv_relative_path,
            source_manifest_relative_path=dataset.source_manifest_relative_path,
        )


def test_post_development_candle_is_rejected(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")
    csv_path = tmp_path / dataset.csv_relative_path
    with csv_path.open("a", encoding="utf-8", newline="") as target:
        target.write("2023-02-01T00:00:00Z,100,102,99,101,10\n")

    with pytest.raises(ValueError, match="outside development"):
        inspect_canonical_ohlcv_csv(
            csv_path,
            partition_start=START,
            partition_end=END,
        )


def test_bundle_refuses_missing_or_relabelled_universe_market(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")

    with pytest.raises(ValueError, match="frozen universe roles"):
        build_development_dataset_bundle(
            generated_at=datetime(2026, 7, 22, 16, tzinfo=UTC),
            universe_manifest_evidence_hash="a" * 64,
            contamination_ledger_hash="b" * 64,
            builder_contract_hash="c" * 64,
            partition_start=START,
            partition_end=END,
            expected_roles={"ADAUSDT": "DEVELOPMENT_ONLY"},
            entries=[dataset],
            limitations=["Fixture limitation."],
        )


def test_entry_refuses_strategy_outcome_fields(tmp_path: Path) -> None:
    dataset = entry(tmp_path, "ADAUSDT")
    payload = dataset.model_dump()
    payload["strategy_outcome_fields_inspected"] = ["strategy_return"]

    with pytest.raises(ValidationError, match="cannot inspect strategy outcomes"):
        DevelopmentDatasetEntry.model_validate(payload)
