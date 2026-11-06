import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_reversal_failure_analysis import (
    JAM_FAILURE_FINDINGS,
    JAM_SUCCESSOR_REQUIREMENTS,
    JamReversalFailureAnalysis,
    audit_jam_reversal_failure_analysis,
)
from scripts.build_jam_reversal_spot_failure_analysis import (
    build_analysis,
    load_inputs,
)


def authoritative_analysis() -> JamReversalFailureAnalysis:
    decision, ledger = load_inputs()
    return build_analysis(decision, ledger)


def test_failure_analysis_rebuilds_from_stored_evidence_only() -> None:
    analysis = authoritative_analysis()

    assert audit_jam_reversal_failure_analysis(analysis) is True
    assert analysis.analysis_boundary == (
        "STORED_DECISION_EVIDENCE_ONLY_NO_NEW_RETURN_INSPECTION"
    )
    assert analysis.findings == JAM_FAILURE_FINDINGS
    assert analysis.successor_requirements == JAM_SUCCESSOR_REQUIREMENTS
    assert analysis.facts.total_trades == 14
    assert analysis.facts.out_of_sample_trades == 4
    assert analysis.facts.walk_forward_passed_windows == 0
    assert analysis.facts.gross_before_modeled_costs > 0
    assert analysis.facts.base_net_pl < 0
    assert analysis.facts.out_of_sample_expectancy < 0


def test_failure_analysis_grants_no_trading_or_retuning_authority() -> None:
    analysis = authoritative_analysis()

    assert analysis.authorizes_parameter_retuning is False
    assert analysis.authorizes_new_candidate is False
    assert analysis.authorizes_forward_paper is False
    assert analysis.authorizes_testnet_strategy_orders is False
    assert analysis.authorizes_production is False
    assert analysis.authorizes_live is False


def test_failure_analysis_refuses_authority_tampering() -> None:
    payload = authoritative_analysis().model_dump(mode="json")
    payload["authorizes_forward_paper"] = True

    with pytest.raises(ValidationError, match="cannot grant trading authority"):
        JamReversalFailureAnalysis.model_validate(payload)


def test_stored_failure_analysis_matches_rebuild() -> None:
    stored = JamReversalFailureAnalysis.model_validate_json(
        Path(
            "data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json"
        ).read_text(encoding="utf-8")
    )

    assert stored == authoritative_analysis()
    assert audit_jam_reversal_failure_analysis(stored) is True


def test_failure_analysis_refuses_hash_tampering() -> None:
    payload = json.loads(authoritative_analysis().model_dump_json())
    payload["facts"]["total_trades"] = 15

    with pytest.raises(ValidationError):
        JamReversalFailureAnalysis.model_validate(payload)
