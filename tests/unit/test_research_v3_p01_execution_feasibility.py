from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_p01_execution_feasibility import (
    V3_P01_EXECUTION_FAIL_DECISION,
    V3_P01_EXECUTION_REQUIREMENT_IDS,
    V3P01ExecutionFeasibilityProtocol,
    V3P01ExecutionFeasibilityResult,
    audit_v3_p01_execution_feasibility_protocol,
    audit_v3_p01_execution_feasibility_result,
)
from scripts.freeze_v3_p01_execution_feasibility_protocol import (
    DEFAULT_CHARTER,
    DEFAULT_COVERAGE_RESULT,
    DEFAULT_FOUNDATION_PROTOCOL,
    DEFAULT_FOUNDATION_RESULT,
    DEFAULT_METADATA_CONTRACT,
    DEFAULT_METADATA_RESULT,
    DEFAULT_METADATA_SUPERSEDED_CONTRACT,
    DEFAULT_REGISTER,
    authoritative_protocol,
    load_inputs,
)
from scripts.run_v3_p01_execution_feasibility import (
    authoritative_result,
)

FROZEN_AT = datetime(2026, 7, 28, 15, 0, tzinfo=UTC)


class Args:
    charter = DEFAULT_CHARTER
    register = DEFAULT_REGISTER
    coverage_result = DEFAULT_COVERAGE_RESULT
    metadata_contract = DEFAULT_METADATA_CONTRACT
    metadata_superseded_contract = DEFAULT_METADATA_SUPERSEDED_CONTRACT
    metadata_result = DEFAULT_METADATA_RESULT
    foundation_protocol = DEFAULT_FOUNDATION_PROTOCOL
    foundation_result = DEFAULT_FOUNDATION_RESULT


def protocol() -> V3P01ExecutionFeasibilityProtocol:
    charter, register, coverage, metadata, foundation = load_inputs(Args())
    return authoritative_protocol(
        frozen_at=FROZEN_AT,
        charter=charter,
        register=register,
        coverage=coverage,
        metadata=metadata,
        foundation=foundation,
    )


def test_v3p01_execution_protocol_is_all_required_and_no_outcome() -> None:
    frozen = protocol()

    assert frozen.requirement_ids == V3_P01_EXECUTION_REQUIREMENT_IDS
    assert frozen.qualification_rule.startswith("ALL_ELEVEN")
    assert frozen.conservative_historical_overrides_permitted is False
    assert (
        frozen.same_asset_base_quantity_netting_qualifies_cross_asset_risk
        is False
    )
    assert frozen.market_numeric_value_inspection_permitted is False
    assert frozen.return_calculation_permitted is False
    assert frozen.selection_permitted is False
    assert audit_v3_p01_execution_feasibility_protocol(frozen)


def test_v3p01_execution_protocol_refuses_requirement_tampering() -> None:
    payload = protocol().model_dump()
    payload["requirement_ids"] = payload["requirement_ids"][:-1]

    with pytest.raises(ValidationError):
        V3P01ExecutionFeasibilityProtocol.model_validate(payload)


def test_v3p01_execution_result_rejects_seven_unmet_requirements() -> None:
    frozen = protocol()
    result = authoritative_result(
        generated_at=FROZEN_AT,
        args=Args(),
        protocol=frozen,
    )

    assert result.decision == V3_P01_EXECUTION_FAIL_DECISION
    assert result.passed_requirement_count == 4
    assert result.failed_requirement_count == 7
    assert "SYNCHRONIZED_SOURCE_COVERAGE_25_SYMBOLS" in (
        result.passed_requirement_ids
    )
    assert "CROSS_ASSET_IDENTITY_HEDGE_AND_RESIDUAL_RISK_FOUNDATION" in (
        result.failed_requirement_ids
    )
    assert "HISTORICAL_ACCOUNT_FEE_TIER" in result.failed_requirement_ids
    assert result.selects_primary is False
    assert result.creates_candidate is False
    assert result.opens_development is False
    assert result.opens_validation is False
    assert result.opens_holdout is False
    assert result.opens_forward is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert result.market_numeric_values_inspected == []
    assert result.return_metrics_calculated == []
    assert audit_v3_p01_execution_feasibility_result(result)


def test_v3p01_execution_result_refuses_false_pass_count() -> None:
    result = authoritative_result(
        generated_at=FROZEN_AT,
        args=Args(),
        protocol=protocol(),
    )
    payload = result.model_dump()
    payload["passed_requirement_count"] = 11

    with pytest.raises(ValidationError, match="assessment counts changed"):
        V3P01ExecutionFeasibilityResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_v3_p01_execution_feasibility_protocol.py",
        "scripts/run_v3_p01_execution_feasibility.py",
    ],
)
def test_v3p01_execution_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
