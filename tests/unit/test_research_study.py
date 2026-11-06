from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.research_study import (
    R3MechanismStudyProtocol,
    audit_r3_mechanism_study_protocol,
)
from aurex.backtest_engine.universe import MarketUniverseManifest, universe_evidence_hash
from scripts.freeze_r3_mechanism_study import (
    authoritative_protocol,
    builder_contract_hash,
    development_builder_contract_hash,
    find_result_artifacts,
)


def protocol() -> R3MechanismStudyProtocol:
    universe = MarketUniverseManifest.model_validate_json(
        Path("data/evidence/market_universe_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    bundle = DevelopmentDatasetBundle.model_validate_json(
        Path("data/evidence/development_4h_dataset_bundle_v1.json").read_text(
            encoding="utf-8"
        )
    )
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 22, 18, tzinfo=UTC),
        universe=universe,
        bundle=bundle,
    )


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {key: value for key, value in payload.items() if key != "protocol_evidence_hash"}
    )
    return payload


def test_authoritative_r3_protocol_has_one_non_selectable_primary() -> None:
    frozen = protocol()
    primary = [variant for variant in frozen.variants if variant.role == "PRIMARY"]

    assert [variant.variant_id for variant in primary] == ["xsmom_84d_14d_primary"]
    assert len(frozen.variants) == 3
    assert len(frozen.folds) == 6
    assert len(frozen.decision_symbols) == 35
    assert frozen.diagnostic_only_symbols == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert frozen.gates.primary_is_never_replaced_by_best_variant is True
    assert frozen.outcome_fields_inspected == []
    assert frozen.preexisting_result_artifacts == []
    assert audit_r3_mechanism_study_protocol(frozen) is True
    assert R3MechanismStudyProtocol.model_validate_json(frozen.model_dump_json()) == frozen


def test_r3_protocol_refuses_any_pre_freeze_outcome() -> None:
    payload = protocol().model_dump()
    payload["outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="before any study outcome exists"):
        R3MechanismStudyProtocol.model_validate(rehash(payload))


def test_r3_protocol_refuses_a_second_primary_even_with_recomputed_hash() -> None:
    payload = protocol().model_dump()
    payload["variants"][0]["role"] = "PRIMARY"

    with pytest.raises(ValidationError, match="exactly one primary"):
        R3MechanismStudyProtocol.model_validate(rehash(payload))


def test_r3_protocol_refuses_noncontiguous_folds() -> None:
    payload = protocol().model_dump()
    payload["folds"][1]["evaluation_start"] = datetime(2023, 10, 2, tzinfo=UTC)

    with pytest.raises(ValidationError, match="folds must be contiguous"):
        R3MechanismStudyProtocol.model_validate(rehash(payload))


def test_r3_freeze_predates_the_result_and_matches_data_builder() -> None:
    bundle = DevelopmentDatasetBundle.model_validate_json(
        Path("data/evidence/development_4h_dataset_bundle_v1.json").read_text(
            encoding="utf-8"
        )
    )
    frozen_protocol = protocol()
    result = R3StudyResultLedger.model_validate_json(
        Path("data/evidence/r3_cross_sectional_momentum_result_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert frozen_protocol.preexisting_result_artifacts == []
    assert frozen_protocol.outcome_fields_inspected == []
    assert find_result_artifacts(Path("data/evidence")) == [
        "r3_cross_sectional_momentum_result_v1.json"
    ]
    assert result.generated_at > frozen_protocol.registered_at
    assert bundle.builder_contract_hash == development_builder_contract_hash()
    assert len(builder_contract_hash()) == 64


def test_authoritative_frozen_r3_protocol_matches_offline_rebuild() -> None:
    stored = R3MechanismStudyProtocol.model_validate_json(
        Path("data/evidence/r3_cross_sectional_momentum_study_v1.json").read_text(
            encoding="utf-8"
        )
    )
    universe = MarketUniverseManifest.model_validate_json(
        Path("data/evidence/market_universe_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    bundle = DevelopmentDatasetBundle.model_validate_json(
        Path("data/evidence/development_4h_dataset_bundle_v1.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = authoritative_protocol(
        registered_at=stored.registered_at,
        universe=universe,
        bundle=bundle,
    )

    assert stored == rebuilt
    assert stored.protocol_evidence_hash == (
        "8af37e15ca08bcbbdd82c457927d5a4b5039e70f173ff735c16c91a3bed4f893"
    )
