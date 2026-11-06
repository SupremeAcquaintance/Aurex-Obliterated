from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s3_cftc_positioning_charter import (
    S3CftcPositioningCharter,
    S3CftcPositioningCharterAudit,
    audit_s3_charter,
    audit_s3_charter_audit,
)
from scripts.audit_s3_cftc_positioning_charter import build_audit
from scripts.freeze_s3_cftc_positioning_charter import build_charter

CHARTER_PATH = Path("data/evidence/s3_cftc_positioning_charter_v1.json")
AUDIT_PATH = Path("data/evidence/s3_cftc_positioning_charter_audit_v1.json")


def charter() -> S3CftcPositioningCharter:
    return S3CftcPositioningCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def test_s3_charter_reconstructs_and_binds_terminal_s2() -> None:
    stored = charter()
    assert stored == build_charter(frozen_at=stored.frozen_at)
    assert audit_s3_charter(stored) is True
    assert len(stored.predecessor_bindings) == 12
    assert stored.familywise_predecessor_count == 10
    paths = tuple(item.path for item in stored.predecessor_bindings)
    assert "data/evidence/s2_development_backtest_result_v1.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v23.json" in paths


def test_s3_is_distinct_regulated_positioning_only() -> None:
    stored = charter()
    assert stored.mechanism_id == "S3-CFTC-LEVERAGED-MONEY-POSITIONING-SPOT"
    assert stored.cftc_contract_market_code == "133741"
    assert stored.report_family == "TRADERS_IN_FINANCIAL_FUTURES_FUTURES_ONLY"
    assert stored.prospective_measurement_families == (
        "LEVERAGED_MONEY_LONG_CONTRACTS",
        "LEVERAGED_MONEY_SHORT_CONTRACTS",
        "LEVERAGED_MONEY_NET_POSITION",
        "WEEK_OVER_WEEK_NET_POSITION_CHANGE",
    )
    assert "NO_ONCHAIN_SETTLEMENT_TRANSACTION_FEE_OR_NETWORK_DEMAND_INPUT" in (
        stored.independence_exclusions
    )


def test_s3_declares_published_outcome_contamination() -> None:
    stored = charter()
    assert stored.published_rule_outcome_awareness_declared is True
    assert stored.published_study_results_cannot_qualify_s3 is True
    contaminated = stored.partitions[0]
    assert contaminated.role == "PUBLISHED_STUDY_CONTAMINATED_REFERENCE"
    assert contaminated.state == "PUBLISHED_OUTCOME_CONTAMINATED_NONQUALIFYING"
    assert contaminated.end is not None
    assert contaminated.end.isoformat() == "2022-01-01T00:00:00+00:00"


def test_s3_preserves_future_validation_and_holdout() -> None:
    stored = charter()
    validation = next(item for item in stored.partitions if item.role == "PROSPECTIVE_VALIDATION")
    holdout = next(item for item in stored.partitions if item.role == "FUTURE_HOLDOUT")
    assert validation.start.isoformat() == "2026-11-07T00:00:00+00:00"
    assert validation.end is not None
    assert validation.end.isoformat() == "2027-05-07T00:00:00+00:00"
    assert holdout.end is not None
    assert holdout.end.isoformat() == "2027-11-07T00:00:00+00:00"
    assert all(item.outcome_access_permitted is False for item in stored.partitions)


def test_s3_charter_authorizes_metadata_feasibility_only() -> None:
    stored = charter()
    assert stored.authorizes_source_metadata_requests is True
    assert stored.authorizes_release_calendar_metadata_requests is True
    assert stored.authorizes_cftc_position_value_access is False
    assert stored.authorizes_market_value_access is False
    assert stored.authorizes_payload_acquisition is False
    assert stored.authorizes_return_testing is False
    assert stored.authorizes_paper is False
    assert stored.authorizes_testnet_strategy_orders is False
    assert stored.authorizes_live is False
    assert stored.cftc_position_values_inspected == ()
    assert stored.btc_market_numeric_fields_inspected == ()


def test_s3_charter_rejects_position_value_authority_tampering() -> None:
    payload = json.loads(charter().model_dump_json())
    payload["authorizes_cftc_position_value_access"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant value"):
        S3CftcPositioningCharter.model_validate(payload)


def test_s3_charter_rejects_partition_boundary_tampering() -> None:
    payload = json.loads(charter().model_dump_json())
    payload["partitions"][1]["start"] = "2022-01-08T00:00:00Z"
    payload["charter_evidence_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="partitions must be contiguous"):
        S3CftcPositioningCharter.model_validate(payload)


def test_s3_charter_audit_reconstructs_exactly() -> None:
    audit = S3CftcPositioningCharterAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert audit == build_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s3_charter_audit(audit) is True
