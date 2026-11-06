from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_onchain_settlement_charter import (
    S2OnchainSettlementCharter,
    S2OnchainSettlementCharterAudit,
    audit_s2_charter,
    audit_s2_charter_audit,
)
from scripts.audit_s2_onchain_settlement_charter import build_audit
from scripts.freeze_s2_onchain_settlement_charter import build_charter

CHARTER_PATH = Path("data/evidence/s2_onchain_settlement_charter_v1.json")
AUDIT_PATH = Path("data/evidence/s2_onchain_settlement_charter_audit_v1.json")


def charter() -> S2OnchainSettlementCharter:
    return S2OnchainSettlementCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def test_s2_charter_reconstructs_and_binds_all_predecessors() -> None:
    stored = charter()
    assert stored == build_charter(frozen_at=stored.frozen_at)
    assert audit_s2_charter(stored) is True
    assert len(stored.predecessor_bindings) == 8
    assert stored.familywise_predecessor_count == 9


def test_s2_is_distinct_onchain_settlement_demand_only() -> None:
    stored = charter()
    assert stored.mechanism_id == "S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT"
    assert stored.source_dataset == "crypto_bitcoin"
    assert stored.source_tables == ("blocks", "transactions")
    assert "NO_HASHRATE_AS_PRIMARY_PREDICTIVE_INPUT" in stored.independence_exclusions
    assert "NO_NFCI_MONETARY_FINANCIAL_CONDITIONS_OR_OTHER_MACRO_INPUT" in (
        stored.independence_exclusions
    )


def test_s2_discloses_prior_metadata_and_excludes_coin_metrics_values() -> None:
    stored = charter()
    assert stored.prior_coin_metrics_catalog_metadata_request_count_declared == 2
    assert stored.prior_catalog_market_values_read_declared == 0
    assert stored.coin_metrics_community_data_permitted_as_trading_input is False
    assert stored.blockchain_numeric_fields_inspected == ()
    assert stored.market_numeric_fields_inspected == ()


def test_s2_preserves_prospective_validation_and_holdout() -> None:
    stored = charter()
    validation = next(item for item in stored.partitions if item.role == "PROSPECTIVE_VALIDATION")
    holdout = next(item for item in stored.partitions if item.role == "FUTURE_HOLDOUT")
    assert validation.start.isoformat() == "2026-11-07T00:00:00+00:00"
    assert validation.end is not None
    assert validation.end.isoformat() == "2027-05-07T00:00:00+00:00"
    assert holdout.end is not None
    assert holdout.end.isoformat() == "2027-11-07T00:00:00+00:00"
    assert all(item.outcome_access_permitted is False for item in stored.partitions)


def test_s2_charter_authorizes_metadata_and_dry_run_only() -> None:
    stored = charter()
    assert stored.authorizes_source_metadata_requests is True
    assert stored.authorizes_bigquery_dry_runs is True
    assert stored.authorizes_bigquery_numeric_queries is False
    assert stored.authorizes_market_value_access is False
    assert stored.authorizes_return_testing is False
    assert stored.authorizes_paper is False
    assert stored.authorizes_testnet_strategy_orders is False
    assert stored.authorizes_live is False


def test_s2_charter_rejects_numeric_query_authority_tampering() -> None:
    payload = json.loads(charter().model_dump_json())
    payload["authorizes_bigquery_numeric_queries"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant outcome"):
        S2OnchainSettlementCharter.model_validate(payload)


def test_s2_charter_audit_reconstructs_exactly() -> None:
    audit = S2OnchainSettlementCharterAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert audit == build_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s2_charter_audit(audit) is True
