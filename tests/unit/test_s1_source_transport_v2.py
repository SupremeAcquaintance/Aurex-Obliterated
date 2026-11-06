from pathlib import Path

from aurex.backtest_engine.s1_source_transport_v2 import (
    S1SourceTransportAmendmentV2,
    S1SourceTransportAuditV2,
    S1SourceTransportResultV2,
)
from scripts.audit_s1_source_transport_v2 import build_audit
from scripts.freeze_s1_source_transport_amendment_v2 import build_amendment
from scripts.run_s1_source_transport_v2 import build_requests, build_result

AMENDMENT_PATH = Path("data/evidence/s1_source_transport_amendment_v2.json")
RESULT_PATH = Path("data/evidence/s1_source_transport_result_v2.json")
AUDIT_PATH = Path("data/evidence/s1_source_transport_audit_v2.json")


def test_s1_v2_amendment_is_narrow_and_reconstructable() -> None:
    amendment = S1SourceTransportAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )

    assert amendment == build_amendment(frozen_at=amendment.frozen_at)
    assert amendment.amended_method == "GET_OPEN_HEADERS_CLOSE_WITHOUT_READ"
    assert amendment.retry_budget == 0
    assert amendment.application_body_byte_budget == 0
    assert amendment.authorizes_response_read_call is False
    assert amendment.authorizes_return_testing is False


def test_s1_v2_result_and_audit_reconstruct() -> None:
    amendment = S1SourceTransportAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )
    result = S1SourceTransportResultV2.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1SourceTransportAuditV2.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert result == build_result(
        amendment_path=AMENDMENT_PATH,
        amendment=amendment,
        requests=build_requests(amendment),
        responses=result.responses,
        completed_at=result.completed_at,
    )
    assert result.response_read_calls == 0
    assert result.application_body_bytes_read == 0
    assert result.persisted_payload_bytes == 0
    assert audit == build_audit(
        amendment_path=AMENDMENT_PATH,
        result_path=RESULT_PATH,
        audited_at=audit.audited_at,
    )
