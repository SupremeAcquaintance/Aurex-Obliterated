from pathlib import Path

from aurex.backtest_engine.s1_strategy_preregistration import (
    S1StrategyPreregistration,
    S1StrategyPreregistrationAudit,
)
from scripts.audit_s1_strategy_preregistration import build_audit
from scripts.freeze_s1_strategy_preregistration import build_protocol

PROTOCOL_PATH = Path("data/evidence/s1_strategy_preregistration_v1.json")
AUDIT_PATH = Path("data/evidence/s1_strategy_preregistration_audit_v1.json")


def test_s1_strategy_preregistration_and_audit_reconstruct() -> None:
    protocol = S1StrategyPreregistration.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S1StrategyPreregistrationAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        audited_at=audit.audited_at,
    )
    assert len(protocol.candidates) == 4
    assert sum(item.may_be_promoted for item in protocol.candidates) == 1
    assert len(protocol.development_gates) == 12
    assert protocol.expected_weekly_interval_count == 276


def test_s1_strategy_preregistration_is_outcome_blind_and_fail_closed() -> None:
    protocol = S1StrategyPreregistration.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )

    assert protocol.feature_value_rows_parsed_during_freeze == 0
    assert protocol.diagnostic_rescue_permitted is False
    assert protocol.missing_execution_price_policy == "STOP_NO_SUBSTITUTION"
    assert protocol.authorizes_btc_source_acquisition_now is False
    assert protocol.authorizes_btc_market_value_access is False
    assert protocol.authorizes_return_testing is False
    assert protocol.authorizes_validation_access is False
    assert protocol.authorizes_holdout_access is False
    assert protocol.authorizes_paper is False
    assert protocol.authorizes_testnet_strategy_orders is False
    assert protocol.authorizes_production is False
    assert protocol.authorizes_live is False
