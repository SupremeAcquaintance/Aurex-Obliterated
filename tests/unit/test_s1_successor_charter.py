from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s1_successor_charter import (
    S1MacroFinancialConditionsCharter,
    S1MacroFinancialConditionsCharterAudit,
    S1SuccessorLineageAudit,
    S1SuccessorLineageLedger,
    audit_s1_charter,
    audit_s1_charter_audit,
    audit_s1_lineage,
    audit_s1_lineage_audit,
)
from scripts.audit_s1_macro_financial_conditions_charter import (
    build_audit as build_charter_audit,
)
from scripts.audit_s1_successor_lineage import build_audit as build_lineage_audit
from scripts.freeze_s1_macro_financial_conditions_charter import build_charter
from scripts.freeze_s1_successor_lineage import build_ledger

LINEAGE_PATH = Path("data/evidence/s1_successor_lineage_ledger_v1.json")
LINEAGE_AUDIT_PATH = Path("data/evidence/s1_successor_lineage_audit_v1.json")
CHARTER_PATH = Path("data/evidence/s1_macro_financial_conditions_charter_v1.json")
CHARTER_AUDIT_PATH = Path(
    "data/evidence/s1_macro_financial_conditions_charter_audit_v1.json"
)


def stored_lineage() -> S1SuccessorLineageLedger:
    return S1SuccessorLineageLedger.model_validate_json(
        LINEAGE_PATH.read_text(encoding="utf-8")
    )


def stored_charter() -> S1MacroFinancialConditionsCharter:
    return S1MacroFinancialConditionsCharter.model_validate_json(
        CHARTER_PATH.read_text(encoding="utf-8")
    )


def test_s1_lineage_is_exact_append_only_closeout() -> None:
    lineage = stored_lineage()

    assert lineage == build_ledger(frozen_at=lineage.frozen_at)
    assert audit_s1_lineage(lineage) is True
    assert lineage.lineage_count == 8
    assert lineage.source_binding_count == 10
    assert all(record.reusable_for_s1_selection is False for record in lineage.records)
    assert lineage.new_market_numeric_fields_inspected == ()
    assert lineage.new_return_metrics_calculated == ()


def test_s1_lineage_audit_reconstructs_exactly() -> None:
    audit = S1SuccessorLineageAudit.model_validate_json(
        LINEAGE_AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit == build_lineage_audit(
        ledger_path=LINEAGE_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s1_lineage_audit(audit) is True


def test_s1_charter_is_independent_and_no_outcome() -> None:
    charter = stored_charter()

    assert charter == build_charter(frozen_at=charter.frozen_at)
    assert audit_s1_charter(charter) is True
    assert charter.mechanism_id == "S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE"
    assert charter.operator_scope.symbol == "BTCUSDT"
    assert charter.operator_scope.direction == "LONG_OR_CASH"
    assert charter.proposal_budget == 1
    assert charter.market_numeric_fields_inspected == ()
    assert charter.exact_parameters_defined == ()
    assert charter.return_metrics_calculated == ()
    assert charter.next_authorization == (
        "AUTHORIZE_S1_METADATA_ONLY_NFCI_VINTAGE_FEASIBILITY"
    )


def test_s1_charter_preserves_causal_vintages_and_future_holdout() -> None:
    charter = stored_charter()

    assert "NEVER_BACKFILL_A_REVISED_VALUE_INTO_AN_EARLIER_DECISION" in (
        charter.causal_observation_policy
    )
    assert "CURRENT_FINAL_REVISED_NFCI_IS_DIAGNOSTIC_ONLY_AND_NONSELECTABLE" in (
        charter.causal_observation_policy
    )
    holdout = next(
        partition
        for partition in charter.partitions
        if partition.role == "FUTURE_HOLDOUT"
    )
    assert holdout.start.isoformat() == "2026-11-07T00:00:00+00:00"
    assert holdout.end is not None
    assert holdout.end.isoformat() == "2027-05-07T00:00:00+00:00"
    assert all(
        partition.outcome_access_permitted is False
        for partition in charter.partitions
    )


def test_s1_charter_grants_no_trading_or_outcome_authority() -> None:
    charter = stored_charter()

    assert charter.authorizes_source_metadata_requests is True
    assert charter.authorizes_market_value_access is False
    assert charter.authorizes_payload_acquisition is False
    assert charter.authorizes_parameter_definition is False
    assert charter.authorizes_return_testing is False
    assert charter.authorizes_paper is False
    assert charter.authorizes_testnet_strategy_orders is False
    assert charter.authorizes_live is False
    assert charter.real_net_profit_usd == "0"


def test_s1_charter_rejects_authority_tampering() -> None:
    payload = json.loads(stored_charter().model_dump_json())
    payload["authorizes_return_testing"] = True

    with pytest.raises(ValidationError, match="Input should be False|cannot grant outcome"):
        S1MacroFinancialConditionsCharter.model_validate(payload)


def test_s1_charter_audit_reconstructs_exactly() -> None:
    audit = S1MacroFinancialConditionsCharterAudit.model_validate_json(
        CHARTER_AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit == build_charter_audit(
        charter_path=CHARTER_PATH,
        audited_at=audit.audited_at,
    )
    assert audit_s1_charter_audit(audit) is True
