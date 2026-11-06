from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (
    S5_HISTORY_NEXT,
    S5_HISTORY_PASS,
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadResult,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (
    S5_VERIFIER_FAILURE_ADJUDICATION,
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_s5_history_result_audit_v2,
    audit_s5_history_result_v2,
    audit_verifier_amendment,
    audit_verifier_amendment_audit,
    audit_verifier_failure,
)

PRIOR_RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v1.json")
FAILURE_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_verifier_failure_audit_v1.json")
AMENDMENT_PATH = Path("data/evidence/s5_bitcoin_core_history_local_verifier_amendment_v2.json")
AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_history_local_verifier_amendment_audit_v2.json"
)
RESULT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_v2.json")
RESULT_AUDIT_PATH = Path("data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json")


def load_artifacts() -> tuple[
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryPayloadResultAuditV2,
]:
    return (
        S5BitcoinCoreHistoryPayloadResult.model_validate_json(
            PRIOR_RESULT_PATH.read_text(encoding="utf-8")
        ),
        S5BitcoinCoreHistoryVerifierFailureAudit.model_validate_json(
            FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
        ),
        S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate_json(
            AMENDMENT_PATH.read_text(encoding="utf-8")
        ),
        S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2.model_validate_json(
            AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
        ),
        S5BitcoinCoreHistoryPayloadResultV2.model_validate_json(
            RESULT_PATH.read_text(encoding="utf-8")
        ),
        S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate_json(
            RESULT_AUDIT_PATH.read_text(encoding="utf-8")
        ),
    )


def test_s5_v1_stop_is_preserved_and_failure_is_narrowly_adjudicated() -> None:
    prior, failure, _, _, _, _ = load_artifacts()
    assert prior.decision == S5_HISTORY_STOP
    assert prior.failed_gate_count == 8
    assert prior.attempt.succeeded is True
    assert prior.attempt.exit_code == 0
    assert audit_verifier_failure(failure) is True
    assert failure.adjudication == S5_VERIFIER_FAILURE_ADJUDICATION
    assert failure.successful_clone_process_count == 1
    assert failure.additional_network_process_count == 0
    assert failure.repository_is_bare is True
    assert failure.repository_is_shallow is False
    assert failure.remote_promisor is True
    assert failure.remote_partial_clone_filter == "blob:none"
    assert failure.cutoff_commit_count == 50_395


def test_s5_amendment_changes_only_missing_blob_aware_local_verification() -> None:
    _, failure, amendment, amendment_audit, _, _ = load_artifacts()
    assert audit_verifier_amendment(amendment) is True
    assert audit_verifier_amendment_audit(amendment_audit) is True
    assert amendment.failure_audit_evidence_hash == failure.audit_evidence_hash
    assert amendment.additional_network_process_count == 0
    assert amendment.network_access_permitted is False
    assert amendment.protocol_source_cutoff_unchanged is True
    assert amendment.protocol_gate_ids_unchanged is True
    assert amendment.original_object_enumeration.endswith("<cutoff>")
    assert amendment.corrected_object_enumeration.endswith("--missing=print <cutoff>")
    assert amendment.market_values_permitted is False
    assert amendment.parameters_permitted is False
    assert amendment.live_permitted is False


def test_s5_corrected_result_passes_all_gates_without_new_network_or_outcomes() -> None:
    prior, failure, amendment, amendment_audit, result, result_audit = load_artifacts()
    assert audit_s5_history_result_v2(result) is True
    assert audit_s5_history_result_audit_v2(result_audit) is True
    assert result.prior_result_evidence_hash == prior.result_evidence_hash
    assert result.failure_audit_evidence_hash == failure.audit_evidence_hash
    assert result.verifier_amendment_evidence_hash == amendment.amendment_evidence_hash
    assert result.verifier_amendment_audit_evidence_hash == amendment_audit.audit_evidence_hash
    assert result.decision == S5_HISTORY_PASS
    assert result.next_authorization == S5_HISTORY_NEXT
    assert result.passed_gate_count == 14
    assert result.failed_gate_count == 0
    assert result.dataset_file_count == 23
    assert result.dataset_byte_count == 77_762_990
    assert result.cutoff_commit_count == 50_395
    assert result.reachable_object_id_count == 320_247
    assert result.missing_promised_object_count == 116_360
    assert result.additional_network_process_count == 0
    assert result.btc_market_values_read == 0
    assert result.returns_calculated == 0
    assert result.orders_submitted == 0


def test_s5_corrected_result_rejects_market_authority_tampering() -> None:
    _, _, _, _, result, _ = load_artifacts()
    payload = json.loads(result.model_dump_json())
    payload["authorizes_market_values"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        S5BitcoinCoreHistoryPayloadResultV2.model_validate(payload)
