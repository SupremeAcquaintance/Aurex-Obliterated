from pathlib import Path

from aurex.backtest_engine.s1_nfci_full_acquisition import (
    S1NfciFullAcquisitionProtocol,
    S1NfciFullAcquisitionProtocolAudit,
)
from scripts.audit_s1_nfci_full_acquisition_protocol import build_audit
from scripts.freeze_s1_nfci_full_acquisition_protocol import build_protocol

PROTOCOL_PATH = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_full_acquisition_protocol_audit_v1.json")


def test_s1_full_acquisition_manifest_and_audit_reconstruct() -> None:
    protocol = S1NfciFullAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciFullAcquisitionProtocolAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert len(protocol.targets) == 281
    assert protocol.targets[0].vintage_date.isoformat() == "2017-08-17"
    assert protocol.targets[-1].vintage_date.isoformat() == "2022-12-29"
    assert all(target.vintage_date.weekday() == 3 for target in protocol.targets)
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=audit.audited_at,
    )
    assert protocol.authorizes_network_acquisition_now is False
    assert protocol.authorizes_btc_market_value_access is False
    assert protocol.authorizes_return_testing is False
