from pathlib import Path

from aurex.backtest_engine.s1_nfci_normalization import (
    S1_NFCI_NORMALIZATION_GATES,
    S1_NFCI_NORMALIZED_ROW_FIELDS,
    S1NfciNormalizationProtocol,
    S1NfciNormalizationProtocolAudit,
)
from scripts.audit_s1_nfci_normalization_protocol import build_audit
from scripts.freeze_s1_nfci_normalization_protocol import build_protocol

PROTOCOL_PATH = Path("data/evidence/s1_nfci_normalization_protocol_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_normalization_protocol_audit_v1.json")


def test_s1_nfci_normalization_protocol_and_audit_reconstruct() -> None:
    protocol = S1NfciNormalizationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciNormalizationProtocolAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=audit.audited_at,
    )
    assert protocol.normalized_row_fields == S1_NFCI_NORMALIZED_ROW_FIELDS
    assert protocol.quality_gates == S1_NFCI_NORMALIZATION_GATES
    assert protocol.source_values_read_during_protocol_freeze == 0


def test_s1_nfci_normalization_protocol_has_no_strategy_authority() -> None:
    protocol = S1NfciNormalizationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert protocol.authorizes_value_transformation_now is False
    assert protocol.authorizes_feature_construction is False
    assert protocol.authorizes_parameter_definition is False
    assert protocol.authorizes_btc_market_value_access is False
    assert protocol.authorizes_return_testing is False
    assert protocol.authorizes_validation_access is False
    assert protocol.authorizes_holdout_access is False
    assert protocol.authorizes_paper is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_production is False
    assert protocol.authorizes_live is False
