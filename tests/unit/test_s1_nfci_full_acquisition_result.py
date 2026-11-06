from pathlib import Path

from aurex.backtest_engine.s1_nfci_full_acquisition import (
    S1NfciFullAcquisitionProtocol,
)
from aurex.backtest_engine.s1_nfci_full_execution import (
    S1NfciAcquisitionCheckpoint,
    S1NfciFullAcquisitionAudit,
    S1NfciFullAcquisitionResult,
)
from scripts.audit_s1_nfci_full_acquisition import build_audit
from scripts.run_s1_nfci_full_acquisition import build_result

PROTOCOL_PATH = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
ADDENDUM_PATH = Path("data/evidence/s1_nfci_acquisition_execution_amendment_v2.json")
CHECKPOINT_PATH = Path("data/evidence/s1_nfci_full_acquisition_checkpoint_v1.json")
RESULT_PATH = Path("data/evidence/s1_nfci_full_acquisition_result_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_full_acquisition_audit_v1.json")


def test_s1_full_acquisition_result_and_audit_reconstruct() -> None:
    protocol = S1NfciFullAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    checkpoint = S1NfciAcquisitionCheckpoint.model_validate_json(
        CHECKPOINT_PATH.read_text(encoding="utf-8")
    )
    result = S1NfciFullAcquisitionResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFullAcquisitionAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert result == build_result(
        checkpoint_path=CHECKPOINT_PATH,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=result.completed_at,
    )
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        addendum_path=ADDENDUM_PATH,
        checkpoint_path=CHECKPOINT_PATH,
        result_path=RESULT_PATH,
        audited_at=audit.audited_at,
    )
    assert result.classified_target_count == 281
    assert result.complete_target_count == 281
    assert result.get_attempt_count == 281
    assert result.authorizes_btc_market_value_access is False
    assert result.authorizes_return_testing is False
