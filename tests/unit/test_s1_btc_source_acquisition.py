from pathlib import Path

from aurex.backtest_engine.s1_btc_source_acquisition import (
    S1_BTC_SOURCE_GATES,
    S1BtcSourceAcquisitionProtocol,
    S1BtcSourceAcquisitionProtocolAudit,
)
from scripts.audit_s1_btc_source_acquisition_protocol import build_audit
from scripts.freeze_s1_btc_source_acquisition_protocol import build_protocol

PROTOCOL_PATH = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
AUDIT_PATH = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v1.json"
)


def test_s1_btc_source_protocol_and_audit_reconstruct() -> None:
    protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1BtcSourceAcquisitionProtocolAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=audit.audited_at,
    )
    assert len(protocol.targets) == 277
    assert protocol.targets[0].activation_date.isoformat() == "2017-09-15"
    assert protocol.targets[-1].activation_date.isoformat() == "2022-12-30"
    assert all(item.activation_date.weekday() == 4 for item in protocol.targets)
    assert protocol.quality_gates == S1_BTC_SOURCE_GATES


def test_s1_btc_source_protocol_has_no_network_or_outcome_authority() -> None:
    protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert protocol.btc_market_values_read_during_protocol_freeze == 0
    assert protocol.return_metrics_calculated == ()
    assert protocol.authorizes_network_acquisition_now is False
    assert protocol.authorizes_return_testing is False
    assert protocol.authorizes_validation_access is False
    assert protocol.authorizes_holdout_access is False
    assert protocol.authorizes_candidate_outcome is False
    assert protocol.authorizes_paper is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_production is False
    assert protocol.authorizes_live is False
