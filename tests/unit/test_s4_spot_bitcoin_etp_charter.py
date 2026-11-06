from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (
    S4SpotBitcoinEtpCharter,
    S4SpotBitcoinEtpCharterAudit,
    audit_s4_charter,
    audit_s4_charter_audit,
)
from scripts.audit_s4_spot_bitcoin_etp_charter import build_audit
from scripts.freeze_s4_spot_bitcoin_etp_charter import build_charter

CHARTER_PATH = Path("data/evidence/s4_spot_bitcoin_etp_charter_v1.json")
AUDIT_PATH = Path("data/evidence/s4_spot_bitcoin_etp_charter_audit_v1.json")
FIXED_TIME = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def built_charter() -> S4SpotBitcoinEtpCharter:
    return build_charter(frozen_at=FIXED_TIME)


def stored_charter() -> S4SpotBitcoinEtpCharter:
    return S4SpotBitcoinEtpCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def test_s4_charter_binds_complete_terminal_s3_lineage() -> None:
    charter = built_charter()
    assert audit_s4_charter(charter) is True
    assert len(charter.predecessor_bindings) == 20
    assert charter.familywise_predecessor_count == 11
    paths = tuple(item.path for item in charter.predecessor_bindings)
    assert "data/evidence/s3_cftc_metadata_transport_execution_receipt_v2.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v25.json" in paths


def test_s4_selects_one_distinct_etp_primary_market_mechanism() -> None:
    charter = built_charter()
    assert charter.mechanism_id == "S4-US-SPOT-BITCOIN-ETP-NET-CREATION-PRESSURE"
    assert charter.universe_policy == (
        "ALL_SEC_APPROVED_US_SPOT_BITCOIN_ETPS_FROM_EACH_FIRST_TRADING_DATE"
    )
    assert charter.prospective_measurement_families == (
        "SHARES_OUTSTANDING_CHANGE",
        "BITCOIN_PER_SHARE",
        "ESTIMATED_NET_BITCOIN_CREATION_REDEMPTION",
        "CROSS_FUND_NET_CREATION_BREADTH",
        "CASH_VERSUS_IN_KIND_CREATION_REGIME",
    )
    assert "NO_CFTC_POSITION_OPEN_INTEREST_VOLUME_OR_FUTURES_RETURN_INPUT" in (
        charter.independence_exclusions
    )
    assert "NO_BITCOIN_ONCHAIN_TRANSACTION_FEE_OR_SETTLEMENT_DEMAND_INPUT" in (
        charter.independence_exclusions
    )


def test_s4_freezes_regime_change_and_future_partitions() -> None:
    charter = built_charter()
    assert charter.cash_only_regime_start.isoformat() == "2024-01-11T00:00:00+00:00"
    assert charter.sec_in_kind_authorization_date.isoformat() == (
        "2025-07-29T00:00:00+00:00"
    )
    validation = next(
        item for item in charter.partitions if item.role == "PROSPECTIVE_VALIDATION"
    )
    holdout = next(
        item for item in charter.partitions if item.role == "FUTURE_HOLDOUT"
    )
    assert validation.start.isoformat() == "2026-11-07T00:00:00+00:00"
    assert holdout.end is not None
    assert holdout.end.isoformat() == "2027-11-07T00:00:00+00:00"
    assert all(item.outcome_access_permitted is False for item in charter.partitions)


def test_s4_truthfully_declares_incidental_numeric_field_exposure() -> None:
    charter = built_charter()
    assert charter.incidental_source_numeric_fields_observed == (
        "BITCOIN_QUANTITY_HELD",
        "NET_ASSET_VALUE",
        "SHARES_CREATED_OR_REDEEMED_ANNUAL_TOTAL",
        "SHARES_OUTSTANDING",
    )
    assert charter.etp_time_series_rows_parsed == 0
    assert charter.etp_numeric_payloads_acquired == 0
    assert charter.btc_market_numeric_fields_inspected == ()
    assert charter.historical_etp_results_cannot_qualify_s4 is True


def test_s4_authorizes_metadata_feasibility_only() -> None:
    charter = built_charter()
    assert charter.authorizes_source_metadata_requests is True
    assert charter.authorizes_sec_filing_metadata_requests is True
    assert charter.authorizes_etp_numeric_value_access is False
    assert charter.authorizes_market_value_access is False
    assert charter.authorizes_payload_acquisition is False
    assert charter.authorizes_return_testing is False
    assert charter.authorizes_paper is False
    assert charter.authorizes_testnet_strategy_orders is False
    assert charter.authorizes_production is False
    assert charter.authorizes_live is False
    assert charter.strategy_candidates_created == 0
    assert charter.orders_submitted == 0
    assert charter.real_net_profit_usd == "0"


def test_s4_rejects_numeric_value_authority_tampering() -> None:
    payload = json.loads(built_charter().model_dump_json())
    payload["authorizes_etp_numeric_value_access"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant value"):
        S4SpotBitcoinEtpCharter.model_validate(payload)


def test_s4_rejects_partition_boundary_tampering() -> None:
    payload = json.loads(built_charter().model_dump_json())
    payload["partitions"][2]["start"] = "2025-08-01T00:00:00Z"
    payload["charter_evidence_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="partitions must be contiguous"):
        S4SpotBitcoinEtpCharter.model_validate(payload)


def test_s4_frozen_charter_and_audit_reconstruct_exactly() -> None:
    charter = stored_charter()
    audit = S4SpotBitcoinEtpCharterAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert charter == build_charter(frozen_at=charter.frozen_at)
    assert audit == build_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s4_charter(charter) is True
    assert audit_s4_charter_audit(audit) is True
