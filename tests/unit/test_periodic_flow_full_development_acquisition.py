from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    FULL_DEVELOPMENT_AUTHORIZATION,
    FULL_DEVELOPMENT_MONTHS,
    PeriodicFlowFullDevelopmentProtocol,
    audit_full_development_protocol,
    audit_full_development_protocol_audit,
    build_full_development_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_periodic_flow_full_development_acquisition import (
    authoritative_protocol,
)


def protocol() -> PeriodicFlowFullDevelopmentProtocol:
    return authoritative_protocol(frozen_at=datetime(2026, 8, 7, 15, tzinfo=UTC))


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "protocol_evidence_hash"
        }
    )
    return payload


def test_full_development_protocol_has_exact_paired_matrix() -> None:
    frozen = protocol()

    assert audit_full_development_protocol(frozen)
    assert len(frozen.targets) == 96
    assert {target.month for target in frozen.targets} == set(
        FULL_DEVELOPMENT_MONTHS
    )
    assert sum(target.product == "SPOT" for target in frozen.targets) == 48
    assert sum(target.product == "USD_M_PERPETUAL" for target in frozen.targets) == 48
    assert sum(target.reuse_candidate_path is not None for target in frozen.targets) == 37
    assert frozen.network_target_count == 59
    assert frozen.maximum_payload_get_attempts == 177


def test_full_development_protocol_reuses_only_bound_local_archives() -> None:
    frozen = protocol()
    targets = {(target.month, target.product): target for target in frozen.targets}

    spot_january = targets[("2020-01", "SPOT")]
    raw_january = targets[("2020-01", "USD_M_PERPETUAL")]
    spot_2023 = targets[("2023-01", "SPOT")]
    raw_february = targets[("2020-02", "USD_M_PERPETUAL")]
    assert "q1_periodic_flow_payload_pilot_v1" in spot_january.reuse_candidate_path
    assert "q1_periodic_flow_raw_trades_payload_pilot_v1" in (
        raw_january.reuse_candidate_path
    )
    assert spot_january.reuse_candidate_file_sha256 == (
        "ea2f0aa850fb08b5c8124d2f8080c03689c30cdadf797363fc74b506b92a8d8b"
    )
    assert raw_january.reuse_candidate_file_sha256 == (
        "5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939"
    )
    assert spot_2023.reuse_candidate_path is None
    assert raw_february.reuse_candidate_path is None


def test_full_development_protocol_binds_duplicate_member_exception_exactly() -> None:
    frozen = protocol()
    target = next(
        target
        for target in frozen.targets
        if target.month == "2021-12" and target.product == "SPOT"
    )

    assert target.published_archive_sha256 == (
        "2ff67048929833d8db2ec32df829d2594052c31799d694486d997bc85b89d42c"
    )
    assert target.member_policy == (
        "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL"
    )
    assert target.reuse_revalidation_required is True


def test_full_development_protocol_is_no_outcome_and_no_trading() -> None:
    frozen = protocol()

    assert frozen.next_authorization == FULL_DEVELOPMENT_AUTHORIZATION
    assert frozen.price_or_quantity_parsing_permitted is False
    assert frozen.feature_calculation_permitted is False
    assert frozen.parameter_definition_permitted is False
    assert frozen.return_calculation_permitted is False
    assert frozen.validation_access_permitted is False
    assert frozen.holdout_access_permitted is False
    assert frozen.candidate_creation_permitted is False
    assert frozen.pine_deployment_permitted is False
    assert frozen.paper_operation_permitted is False
    assert frozen.testnet_strategy_orders_permitted is False
    assert frozen.production_permitted is False
    assert frozen.live_permitted is False


def test_full_development_protocol_rejects_rehashed_authority_or_target_drift() -> None:
    frozen = protocol()
    payload = frozen.model_dump()
    payload["return_calculation_permitted"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowFullDevelopmentProtocol.model_validate(rehash(payload))

    payload = frozen.model_dump()
    payload["network_target_count"] = 60
    with pytest.raises(ValidationError):
        PeriodicFlowFullDevelopmentProtocol.model_validate(rehash(payload))


def test_full_development_protocol_audit_grants_only_acquisition() -> None:
    frozen = protocol()
    audit = build_full_development_protocol_audit(
        audited_at=datetime(2026, 8, 7, 15, 1, tzinfo=UTC),
        protocol_file_sha256="1" * 64,
        protocol_evidence_hash=frozen.protocol_evidence_hash,
        builder_contract_hash=frozen.builder_contract_hash,
        auditor_contract_hash="2" * 64,
    )

    assert audit_full_development_protocol_audit(audit)
    assert audit.network_requests_made == 0
    assert audit.archive_payload_requests_made == 0
    assert audit.authorizes_full_development_archive_acquisition is True
    assert audit.authorizes_features_or_outcomes is False
    assert audit.authorizes_trading is False
