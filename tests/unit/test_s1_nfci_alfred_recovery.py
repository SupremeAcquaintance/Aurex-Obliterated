from pathlib import Path

from aurex.backtest_engine.s1_nfci_alfred_recovery import (
    S1NfciAlfredRecoveryAudit,
    S1NfciAlfredRecoveryProtocol,
    S1NfciAlfredRecoveryResult,
)
from scripts.audit_s1_nfci_alfred_recovery import build_audit
from scripts.freeze_s1_nfci_alfred_recovery_protocol import build_protocol
from scripts.run_s1_nfci_alfred_recovery import build_result
from scripts.run_s1_nfci_raw_pilot import build_comparison

PROTOCOL_PATH = Path("data/evidence/s1_nfci_alfred_recovery_protocol_v1.json")
RESULT_PATH = Path("data/evidence/s1_nfci_alfred_recovery_result_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_alfred_recovery_audit_v1.json")


def test_s1_alfred_recovery_reconstructs_without_btc_outcomes() -> None:
    protocol = S1NfciAlfredRecoveryProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    result = S1NfciAlfredRecoveryResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciAlfredRecoveryAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert result == build_result(
        protocol_path=PROTOCOL_PATH,
        protocol=protocol,
        downloads=result.downloads,
        comparison=build_comparison(result.downloads),
        completed_at=result.completed_at,
    )
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        result_path=RESULT_PATH,
        audited_at=audit.audited_at,
    )
    assert result.btc_market_fields_inspected == ()
    assert result.return_metrics_calculated == ()
    assert result.authorizes_live is False
