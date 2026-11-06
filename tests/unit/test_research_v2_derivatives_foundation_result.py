import subprocess
import sys
from pathlib import Path

from aurex.backtest_engine.research_v2_derivatives_foundation_protocol import (
    V2DerivativesFoundationProtocol,
)
from aurex.backtest_engine.research_v2_derivatives_foundation_result import (
    audit_v2_derivatives_foundation_result,
)
from scripts.run_v2_derivatives_foundation import (
    authoritative_result,
    execute_campaign,
    runner_contract_hash,
)

PROTOCOL_PATH = Path(
    "data/evidence/v2_derivatives_foundation_protocol_v1.json"
)


def protocol() -> V2DerivativesFoundationProtocol:
    return V2DerivativesFoundationProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def test_all_frozen_v2_derivatives_scenarios_pass() -> None:
    frozen = protocol()
    results = execute_campaign(frozen)

    assert len(results) == 14
    assert all(result.passed for result in results)
    assert all(
        result.final_reconciliation_status == "MATCHED" for result in results
    )
    assert all(all(result.assertions.values()) for result in results)


def test_v2_foundation_result_rebuilds_without_permissions() -> None:
    frozen = protocol()
    result = authoritative_result(
        generated_at=frozen.frozen_at,
        protocol=frozen,
        scenario_results=execute_campaign(frozen),
    )

    assert result.passed_scenario_count == 14
    assert result.failed_scenario_count == 0
    assert result.authorizes_real_market_data_import is False
    assert result.authorizes_strategy_return_calculation is False
    assert result.pass_creates_strategy_candidate is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert (
        audit_v2_derivatives_foundation_result(
            result=result,
            protocol=frozen,
            current_runner_contract_hash=runner_contract_hash(),
        )["status"]
        == "PASS"
    )


def test_v2_foundation_runner_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v2_derivatives_foundation.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
