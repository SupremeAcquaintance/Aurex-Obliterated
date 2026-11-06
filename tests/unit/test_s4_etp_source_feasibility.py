from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (
    S4_FEASIBILITY_GATE_IDS,
    S4_STATIC_ENDPOINT_IDS,
    S4EtpSourceFeasibilityProtocol,
    S4EtpSourceFeasibilityResult,
    S4FeasibilityGateResult,
    S4MetadataAttempt,
    audit_s4_feasibility_protocol,
    audit_s4_feasibility_result,
    build_hashed,
)
from scripts.freeze_s4_etp_source_feasibility import build_protocol

FIXED_TIME = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)


def built_protocol() -> S4EtpSourceFeasibilityProtocol:
    return build_protocol(frozen_at=FIXED_TIME)


def failed_attempt(sequence: int, endpoint_id: str) -> S4MetadataAttempt:
    return S4MetadataAttempt(
        sequence=sequence,
        request_id=f"static-{sequence}",
        endpoint_id=endpoint_id,
        requested_at=FIXED_TIME,
        completed_at=FIXED_TIME,
        http_status=0,
        response_bytes=0,
        response_sha256=None,
        response_path=None,
        error_class="NETWORK_ERROR",
        request_succeeded=False,
        etp_identity_rows_parsed=0,
    )


def synthetic_transport_failure_result() -> S4EtpSourceFeasibilityResult:
    attempts = tuple(
        failed_attempt(sequence, endpoint_id)
        for sequence, endpoint_id in enumerate(S4_STATIC_ENDPOINT_IDS, start=1)
    )
    passing = {
        "ALL_REQUEST_ATTEMPTS_DURABLY_RECORDED",
        "OFFICIAL_SEC_AUTHORITY_ONLY",
        "ZERO_ETP_NUMERIC_VALUES_ACCESSED",
        "ZERO_BTC_MARKET_VALUES_OR_OUTCOMES_ACCESSED",
        "ZERO_PARAMETERS_RETURNS_CANDIDATES_OR_ORDERS",
    }
    gates = tuple(
        S4FeasibilityGateResult(
            gate_id=gate_id,
            status="PASS" if gate_id in passing else "FAIL",
            detail=f"synthetic {gate_id.lower()}",
        )
        for gate_id in S4_FEASIBILITY_GATE_IDS
    )
    return build_hashed(
        S4EtpSourceFeasibilityResult,
        "result_evidence_hash",
        {
            "generated_at": FIXED_TIME,
            "protocol_file_sha256": "1" * 64,
            "protocol_evidence_hash": "2" * 64,
            "protocol_audit_file_sha256": "3" * 64,
            "protocol_audit_evidence_hash": "4" * 64,
            "runner_contract_hash": "5" * 64,
            "metadata_attempts": attempts,
            "gate_results": gates,
            "planned_request_count": 5,
            "attempted_request_count": 5,
            "successful_request_count": 0,
            "failed_request_count": 5,
            "persisted_response_artifact_count": 0,
            "passed_gate_count": 5,
            "failed_gate_count": 10,
            "static_endpoint_ids_attempted": S4_STATIC_ENDPOINT_IDS,
            "dynamic_submission_request_count": 0,
            "universe_candidate_count": 0,
            "classified_spot_bitcoin_etp_count": 0,
            "complete_universe_reconstructable": False,
            "lifecycle_history_reconstructable": False,
            "issuer_data_endpoint_catalog_complete": False,
            "daily_shares_history_descriptor_complete": False,
            "daily_bitcoin_history_descriptor_complete": False,
            "actual_publication_timing_reconstructable": False,
            "per_fund_regime_dates_reconstructable": False,
            "non_creation_change_reconciliation_reconstructable": False,
            "zero_dollar_public_access_observed": False,
            "reuse_rights_explicit": False,
            "etp_identity_rows_parsed": 0,
            "blockers": ("metadata_transport_failed",),
            "decision": "STOP_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4",
            "next_authorization": "NONE_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4",
            "limitations": tuple(f"synthetic limitation {index}" for index in range(8)),
        },
    )


def test_s4_protocol_binds_charter_and_readiness_v26() -> None:
    protocol = built_protocol()
    assert audit_s4_feasibility_protocol(protocol) is True
    assert len(protocol.source_bindings) == 4
    paths = tuple(item.path for item in protocol.source_bindings)
    assert "data/evidence/s4_spot_bitcoin_etp_charter_v1.json" in paths
    assert "data/evidence/aurex_strategy_factory_readiness_current_result_v26.json" in paths


def test_s4_protocol_allows_only_sec_identity_metadata() -> None:
    protocol = built_protocol()
    assert tuple(
        item.endpoint_id for item in protocol.static_metadata_endpoints
    ) == S4_STATIC_ENDPOINT_IDS
    assert all(
        item.url.startswith("https://www.sec.gov/")
        for item in protocol.static_metadata_endpoints
    )
    assert protocol.sec_submissions_url_template.startswith("https://data.sec.gov/")
    assert protocol.issuer_page_response_bodies_permitted is False
    assert protocol.sec_filing_document_bodies_permitted is False
    assert protocol.xbrl_fact_endpoints_permitted is False


def test_s4_protocol_fixes_durable_partial_failure_evidence() -> None:
    protocol = built_protocol()
    assert protocol.result_artifact_required_on_every_exit is True
    assert protocol.attempt_record_required_for_every_planned_request is True
    assert protocol.partial_response_artifacts_must_be_preserved is True
    assert protocol.all_or_nothing_response_persistence_forbidden is True
    assert protocol.unknown_attempt_or_success_counts_forbidden is True
    assert protocol.maximum_run_count == 1
    assert protocol.rerun_after_result_forbidden is True


def test_s4_protocol_records_incidental_numeric_context_honestly() -> None:
    protocol = built_protocol()
    assert protocol.pre_freeze_incidental_current_numeric_context_observed is True
    assert protocol.incidental_exact_numeric_values_persisted_by_aurex is False
    assert protocol.incidental_context_is_outcome_aware_nonqualifying is True
    assert "CURRENT_BITCOIN_QUANTITY" in protocol.incidental_context_categories
    assert protocol.etp_numeric_values_permitted is False


def test_s4_protocol_keeps_all_research_and_execution_authority_locked() -> None:
    protocol = built_protocol()
    assert protocol.payload_acquisition_permitted is False
    assert protocol.parameters_permitted is False
    assert protocol.returns_permitted is False
    assert protocol.historical_screen_permitted is False
    assert protocol.validation_permitted is False
    assert protocol.holdout_permitted is False
    assert protocol.pine_permitted is False
    assert protocol.paper_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.production_permitted is False
    assert protocol.live_permitted is False


def test_s4_protocol_rejects_issuer_response_body_authority() -> None:
    payload = json.loads(built_protocol().model_dump_json())
    payload["issuer_page_response_bodies_permitted"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        S4EtpSourceFeasibilityProtocol.model_validate(payload)


def test_s4_result_contract_preserves_exact_transport_failure_counts() -> None:
    result = synthetic_transport_failure_result()
    assert audit_s4_feasibility_result(result) is True
    assert result.attempted_request_count == 5
    assert result.successful_request_count == 0
    assert result.failed_request_count == 5
    assert result.persisted_response_artifact_count == 0
    assert result.decision == "STOP_S4_ETP_SOURCE_FEASIBILITY_FAILED_RETIRE_S4"
    assert result.etp_numeric_values_read == 0
    assert result.orders_submitted == 0


def test_s4_result_rejects_unknown_or_inexact_attempt_counts() -> None:
    payload = json.loads(synthetic_transport_failure_result().model_dump_json())
    payload["attempted_request_count"] = 6
    payload["result_evidence_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="exact attempt or gate counts"):
        S4EtpSourceFeasibilityResult.model_validate(payload)
