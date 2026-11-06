from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s3_cftc_source_feasibility import (
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    audit_s3_feasibility_protocol,
    audit_s3_feasibility_protocol_audit,
    audit_s3_feasibility_result,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceTransportFailureAudit,
    audit_transport_amendment,
    audit_transport_amendment_audit,
    audit_transport_failure,
)
from aurex.backtest_engine.s3_cftc_source_transport_outcome import (
    S3_DISTINCT_SUCCESSOR_AUTHORIZATION,
    S3_TRANSPORT_V2_RETIREMENT,
    S3CftcMetadataTransportExecutionReceiptAuditV2,
    S3CftcMetadataTransportExecutionReceiptV2,
    audit_transport_execution_receipt,
    audit_transport_execution_receipt_audit,
)
from scripts.audit_s3_cftc_metadata_transport_amendment_v2 import (
    build_audit as build_amendment_audit,
)
from scripts.audit_s3_cftc_metadata_transport_outcome_v2 import (
    build_audit as build_outcome_audit,
)
from scripts.audit_s3_cftc_source_feasibility_protocol import (
    build_audit as build_protocol_audit,
)
from scripts.audit_s3_cftc_source_transport_failure import (
    build_audit as build_failure_audit,
)
from scripts.freeze_s3_cftc_metadata_transport_amendment_v2 import build_amendment
from scripts.freeze_s3_cftc_source_feasibility import build_protocol
from scripts.record_s3_cftc_metadata_transport_outcome_v2 import build_receipt
from scripts.run_s3_cftc_source_feasibility import build_result

PROTOCOL_PATH = Path("data/evidence/s3_cftc_source_feasibility_protocol_v1.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_feasibility_protocol_audit_v1.json"
)
RESULT_PATH = Path("data/evidence/s3_cftc_source_feasibility_result_v1.json")
FAILURE_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_source_transport_failure_audit_v1.json"
)
AMENDMENT_PATH = Path("data/evidence/s3_cftc_metadata_transport_amendment_v2.json")
AMENDMENT_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_amendment_audit_v2.json"
)
RECEIPT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_v2.json"
)
RECEIPT_AUDIT_PATH = Path(
    "data/evidence/s3_cftc_metadata_transport_execution_receipt_audit_v2.json"
)


def protocol() -> S3CftcSourceFeasibilityProtocol:
    return S3CftcSourceFeasibilityProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def result() -> S3CftcSourceFeasibilityResult:
    return S3CftcSourceFeasibilityResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )


def test_s3_feasibility_protocol_reconstructs_before_requests() -> None:
    stored = protocol()
    assert stored == build_protocol(frozen_at=stored.frozen_at)
    assert audit_s3_feasibility_protocol(stored) is True
    assert len(stored.source_bindings) == 4
    assert len(stored.metadata_endpoints) == 3
    assert stored.target_position_values_permitted is False
    assert stored.btc_market_values_permitted is False
    assert stored.returns_permitted is False
    assert stored.paper_permitted is False
    assert stored.testnet_strategy_orders_permitted is False
    assert stored.production_permitted is False
    assert stored.live_permitted is False


def test_s3_feasibility_protocol_audit_reconstructs() -> None:
    stored = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert stored == build_protocol_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=stored.audited_at,
    )
    assert audit_s3_feasibility_protocol_audit(stored) is True
    assert stored.network_requests_observed == 0


def test_s3_v1_result_is_exactly_a_zero_response_transport_failure() -> None:
    stored = result()
    protocol_value = protocol()
    protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert stored == build_result(
        generated_at=stored.generated_at,
        protocol=protocol_value,
        protocol_path=PROTOCOL_PATH,
        protocol_audit=protocol_audit,
        protocol_audit_path=PROTOCOL_AUDIT_PATH,
        attempts=stored.metadata_attempts,
    )
    assert audit_s3_feasibility_result(stored) is True
    assert len(stored.metadata_attempts) == 3
    assert all(
        attempt.error_class == "NETWORK_ERROR" for attempt in stored.metadata_attempts
    )
    assert all(attempt.response_path is None for attempt in stored.metadata_attempts)
    assert stored.cftc_target_position_values_read == 0
    assert stored.btc_market_values_read == 0
    assert stored.orders_submitted == 0


def test_s3_v1_terminal_interpretation_is_rejected_as_transport_only() -> None:
    stored = S3CftcSourceTransportFailureAudit.model_validate_json(
        FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert stored == build_failure_audit(
        protocol_path=PROTOCOL_PATH,
        protocol_audit_path=PROTOCOL_AUDIT_PATH,
        result_path=RESULT_PATH,
        audited_at=stored.audited_at,
    )
    assert audit_transport_failure(stored) is True
    assert stored.successful_response_count == 0
    assert stored.response_artifact_count == 0
    assert stored.adjudication == (
        "REJECT_TERMINAL_SOURCE_INTERPRETATION_TRANSPORT_FAILED_BEFORE_CFTC_RESPONSE"
    )


def test_s3_one_run_transport_amendment_and_audit_reconstruct() -> None:
    amendment = S3CftcMetadataTransportAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    audit = S3CftcMetadataTransportAmendmentAuditV2.model_validate_json(
        AMENDMENT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert amendment == build_amendment(frozen_at=amendment.frozen_at)
    assert audit == build_amendment_audit(
        amendment_path=AMENDMENT_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_transport_amendment(amendment) is True
    assert audit_transport_amendment_audit(audit) is True
    assert amendment.maximum_rerun_count == 1
    assert amendment.maximum_metadata_requests == 3
    assert amendment.target_position_values_permitted is False
    assert amendment.testnet_strategy_orders_permitted is False


def test_s3_exhausted_transport_outcome_and_audit_reconstruct() -> None:
    receipt = S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
        RECEIPT_PATH.read_text(encoding="utf-8")
    )
    audit = S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate_json(
        RECEIPT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    assert receipt == build_receipt(recorded_at=receipt.recorded_at)
    assert audit == build_outcome_audit(
        receipt_path=RECEIPT_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_transport_execution_receipt(receipt) is True
    assert audit_transport_execution_receipt_audit(audit) is True
    assert receipt.successful_response_count_observed == "UNKNOWN_NOT_PERSISTED"
    assert receipt.result_artifact_created is False
    assert receipt.persisted_response_artifact_count == 0
    assert receipt.rerun_authority_exhausted is True
    assert receipt.decision == S3_TRANSPORT_V2_RETIREMENT
    assert receipt.next_authorization == S3_DISTINCT_SUCCESSOR_AUTHORIZATION
    assert receipt.cftc_target_position_values_read == 0
    assert receipt.btc_market_values_read == 0
    assert receipt.orders_submitted == 0


def test_s3_transport_receipt_rejects_live_authority_tampering() -> None:
    receipt = S3CftcMetadataTransportExecutionReceiptV2.model_validate_json(
        RECEIPT_PATH.read_text(encoding="utf-8")
    )
    payload = json.loads(receipt.model_dump_json())
    payload["live_authority"] = True
    with pytest.raises(ValidationError, match="Input should be False"):
        S3CftcMetadataTransportExecutionReceiptV2.model_validate(payload)
