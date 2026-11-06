from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    audit_development_dataset_bundle,
)
from scripts.build_development_dataset_bundle import (
    builder_contract_hash,
    development_partition,
    expected_universe_roles,
    load_universe_manifest,
)


def test_authoritative_universe_yields_exact_development_bundle_scope() -> None:
    manifest = load_universe_manifest(
        Path("data/evidence/market_universe_manifest_v1.json")
    )
    roles = expected_universe_roles(manifest)
    partition = development_partition(manifest)

    assert len(roles) == 38
    assert Counter(roles.values()) == {
        "DECISION_CANDIDATE": 35,
        "DEVELOPMENT_ONLY": 3,
    }
    assert roles["BTCUSDT"] == "DEVELOPMENT_ONLY"
    assert roles["ETHUSDT"] == "DEVELOPMENT_ONLY"
    assert roles["SOLUSDT"] == "DEVELOPMENT_ONLY"
    assert partition.start == datetime(2023, 1, 1, tzinfo=UTC)
    assert partition.end == datetime(2025, 1, 1, tzinfo=UTC)
    assert partition.access == "OPEN_DEVELOPMENT"


def test_development_bundle_builder_contract_hash_is_stable() -> None:
    first = builder_contract_hash()
    second = builder_contract_hash()

    assert first == second
    assert len(first) == 64


def test_authoritative_development_bundle_rebuilds_without_network() -> None:
    manifest = load_universe_manifest(
        Path("data/evidence/market_universe_manifest_v1.json")
    )
    bundle = DevelopmentDatasetBundle.model_validate_json(
        Path("data/evidence/development_4h_dataset_bundle_v1.json").read_text(
            encoding="utf-8"
        )
    )

    audit = audit_development_dataset_bundle(
        bundle,
        evidence_root=Path("data/evidence"),
        expected_roles=expected_universe_roles(manifest),
        current_builder_contract_hash=builder_contract_hash(),
    )

    assert audit["status"] == "PASS"
    assert bundle.bundle_evidence_hash == (
        "fba63b8e237220c760daf902f2c999e9b01121357a4cc583c9fa5cb50b83d341"
    )
    assert bundle.universe_manifest_evidence_hash == manifest.manifest_evidence_hash
    assert bundle.status == "READY"
    assert bundle.summary.dataset_count == 38
    assert bundle.summary.ready_dataset_count == 38
    assert bundle.summary.blocked_dataset_count == 0
    assert bundle.summary.total_rows == 166668
    assert all(entry.archive_count == 24 for entry in bundle.entries)
    assert all(entry.row_count == 4386 for entry in bundle.entries)
    assert all(not entry.missing_timestamps for entry in bundle.entries)
    assert all(not entry.strategy_outcome_fields_inspected for entry in bundle.entries)
