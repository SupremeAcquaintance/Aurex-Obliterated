from pathlib import Path

from aurex.backtest_engine.s1_nfci_feature_protocol import (
    S1_NFCI_FEATURE_GATES,
    S1NfciFeatureProtocol,
    S1NfciFeatureProtocolAudit,
)
from scripts.audit_s1_nfci_feature_protocol import build_audit
from scripts.freeze_s1_nfci_feature_protocol import build_protocol

PROTOCOL_PATH = Path("data/evidence/s1_nfci_feature_protocol_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_feature_protocol_audit_v1.json")


def test_s1_nfci_feature_protocol_and_audit_reconstruct() -> None:
    protocol = S1NfciFeatureProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFeatureProtocolAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=audit.audited_at,
    )
    assert protocol.quality_gates == S1_NFCI_FEATURE_GATES
    assert tuple(item.required_lag_vintages for item in protocol.feature_definitions) == (
        0,
        1,
        4,
    )
    assert protocol.expected_feature_row_count == 277


def test_s1_nfci_feature_protocol_has_no_market_or_strategy_authority() -> None:
    protocol = S1NfciFeatureProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert protocol.normalized_value_rows_parsed_during_freeze == 0
    assert protocol.strategy_candidates_defined == 0
    assert protocol.authorizes_feature_calculation_now is False
    assert protocol.authorizes_strategy_rule_definition is False
    assert protocol.authorizes_btc_market_value_access is False
    assert protocol.authorizes_return_testing is False
    assert protocol.authorizes_validation_access is False
    assert protocol.authorizes_holdout_access is False
    assert protocol.authorizes_paper is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_production is False
    assert protocol.authorizes_live is False
