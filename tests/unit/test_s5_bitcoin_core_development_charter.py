from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_development_charter import (
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
    audit_s5_charter,
    audit_s5_charter_audit,
)
from scripts.audit_s5_bitcoin_core_development_charter import build_audit
from scripts.freeze_s5_bitcoin_core_development_charter import build_charter

CHARTER_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_v1.json")
AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_development_charter_audit_v1.json")
FIXED_TIME = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)


def built_charter() -> S5BitcoinCoreDevelopmentCharter:
    return build_charter(frozen_at=FIXED_TIME)


def stored_charter() -> S5BitcoinCoreDevelopmentCharter:
    return S5BitcoinCoreDevelopmentCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def test_s5_binds_complete_terminal_s4_lineage() -> None:
    charter = built_charter()
    assert audit_s5_charter(charter) is True
    assert len(charter.predecessor_bindings) == 28
    assert charter.familywise_predecessor_count == 12
    paths = tuple(item.path for item in charter.predecessor_bindings)
    assert "data/evidence/s4_spot_bitcoin_etp_charter_v1.json" in paths
    assert "data/evidence/s4_etp_source_feasibility_protocol_v1.json" in paths
    assert "data/evidence/s4_etp_source_feasibility_viability_review_v1.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v27.json" in paths


def test_s5_selects_one_distinct_accepted_development_mechanism() -> None:
    charter = built_charter()
    assert charter.mechanism_id == ("S5-BITCOIN-CORE-ACCEPTED-DEVELOPMENT-BREADTH")
    assert charter.prospective_signal_frequency == "MONTHLY"
    assert charter.prospective_measurement_families == (
        "ACCEPTED_MASTER_MERGE_CADENCE",
        "ACCEPTED_CONTRIBUTOR_IDENTITY_BREADTH",
        "ACCEPTED_SOURCE_COMPONENT_BREADTH",
        "MERGED_PULL_REQUEST_REVIEW_AND_INTEGRATION_CONTINUITY",
        "OFFICIAL_RELEASE_TAG_CONTINUITY",
    )
    assert "NO_BITCOIN_ONCHAIN_TRANSACTION_FEE_OR_SETTLEMENT_DEMAND_INPUT" in (
        charter.independence_exclusions
    )
    assert "NO_ETP_PRIMARY_OR_SECONDARY_MARKET_INPUT" in (charter.independence_exclusions)


def test_s5_rejects_corporate_treasury_before_selection() -> None:
    charter = built_charter()
    assert (
        "PUBLIC_COMPANY_BITCOIN_TREASURY_XBRL_REJECTED_FOR_SHORT_STANDARDIZED_HISTORY_AND_QUARTERLY_SAMPLE"
        in charter.rejected_candidate_families
    )
    source_ids = tuple(item.source_id for item in charter.research_sources)
    assert "FASB-ASU-2023-08-CRYPTO-ASSETS" in source_ids
    assert "SEC-2025-XBRL-TAXONOMIES" in source_ids


def test_s5_records_probe_without_consuming_repository_history() -> None:
    charter = built_charter()
    assert charter.pre_freeze_public_git_probe_executed is True
    assert charter.pre_freeze_public_git_probe_request_count == 1
    assert charter.pre_freeze_probe_used_credentials is False
    assert len(charter.pre_freeze_git_ref_records) == 3
    assert charter.pre_freeze_git_ref_records[0].ref == "HEAD"
    assert charter.repository_commit_history_records_parsed == 0
    assert charter.github_historical_api_records_parsed == 0
    assert charter.repository_history_payload_bytes_acquired == 0
    assert charter.incidental_repository_exact_numeric_values_persisted is False


def test_s5_metadata_gate_is_reachable_and_payload_gate_is_separate() -> None:
    charter = built_charter()
    assert charter.metadata_protocol_pass_condition_reachable_by_allowed_sources is True
    assert "PUBLIC_GIT_SMART_HTTP_REF_DISCOVERY_REACHABLE_WITHOUT_CREDENTIALS" in (
        charter.metadata_feasibility_gates
    )
    assert "COMPLETE_CANONICAL_REPOSITORY_CLONE_PINNED_TO_AN_EXACT_MASTER_OBJECT" in (
        charter.downstream_payload_requirements
    )
    assert charter.authorizes_public_git_metadata_requests is True
    assert charter.authorizes_github_api_metadata_requests is True
    assert charter.authorizes_repository_clone is False
    assert charter.authorizes_repository_history_access is False


def test_s5_freezes_causal_timing_and_future_partitions() -> None:
    charter = built_charter()
    assert "NEVER_USE_AUTHOR_DATE_AS_PUBLIC_AVAILABILITY_TIME" in (
        charter.causal_observation_policy
    )
    assert (
        "MATCH_ACCEPTED_MERGES_TO_GITHUB_PULL_REQUEST_MERGED_AT_WHERE_AVAILABLE"
        in charter.causal_observation_policy
    )
    validation = next(item for item in charter.partitions if item.role == "PROSPECTIVE_VALIDATION")
    holdout = next(item for item in charter.partitions if item.role == "FUTURE_HOLDOUT")
    assert validation.start.isoformat() == "2026-11-07T00:00:00+00:00"
    assert holdout.end is not None
    assert holdout.end.isoformat() == "2027-11-07T00:00:00+00:00"
    assert all(item.outcome_access_permitted is False for item in charter.partitions)


def test_s5_authorizes_metadata_only() -> None:
    charter = built_charter()
    assert charter.authorizes_market_value_access is False
    assert charter.authorizes_parameter_definition is False
    assert charter.authorizes_return_testing is False
    assert charter.authorizes_paper is False
    assert charter.authorizes_testnet_strategy_orders is False
    assert charter.authorizes_production is False
    assert charter.authorizes_live is False
    assert charter.btc_market_numeric_fields_inspected == ()
    assert charter.exact_parameters_defined == ()
    assert charter.return_metrics_calculated == ()
    assert charter.strategy_candidates_created == 0
    assert charter.orders_submitted == 0
    assert charter.real_net_profit_usd == "0"


def test_s5_rejects_repository_history_authority_tampering() -> None:
    payload = json.loads(built_charter().model_dump_json())
    payload["authorizes_repository_history_access"] = True
    with pytest.raises(ValidationError, match="Input should be False|cannot grant payload"):
        S5BitcoinCoreDevelopmentCharter.model_validate(payload)


def test_s5_rejects_partition_boundary_tampering() -> None:
    payload = json.loads(built_charter().model_dump_json())
    payload["partitions"][2]["start"] = "2023-02-01T00:00:00Z"
    payload["charter_evidence_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="partitions must be contiguous"):
        S5BitcoinCoreDevelopmentCharter.model_validate(payload)


def test_s5_frozen_charter_and_audit_reconstruct_exactly() -> None:
    charter = stored_charter()
    audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert charter == build_charter(frozen_at=charter.frozen_at)
    assert audit == build_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s5_charter(charter) is True
    assert audit_s5_charter_audit(audit) is True
