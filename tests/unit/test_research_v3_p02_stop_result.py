from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_p02_stop_result import (
    V3_P02_STOP_DECISION,
    V3P02PayloadPilotStopResult,
    audit_v3_p02_payload_pilot_stop_result,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STOP_RESULT = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "v3_p02_payload_pilot_stop_result_v1.json"
)


def frozen_stop_result() -> V3P02PayloadPilotStopResult:
    return V3P02PayloadPilotStopResult.model_validate_json(
        STOP_RESULT.read_text(encoding="utf-8")
    )


def test_v3p02_stop_preserves_exact_conservative_outcome() -> None:
    result = frozen_stop_result()

    assert result.head_matrix_completed_before_failure is True
    assert result.head_observation_count == 744
    assert result.exact_head_attempt_count_preserved is False
    assert result.verified_sample_count == 2
    assert result.failed_sample_count == 1
    assert result.sample_request_marker_count == 3
    assert result.failed_sample.symbol == "DOGEUSDT"
    assert result.failed_sample.month == "2024-12"
    assert result.authoritative_payload_pilot_result_created is False
    assert result.decision == V3_P02_STOP_DECISION
    assert result.authorizes_retry is False
    assert result.authorizes_full_payload_protocol is False
    assert result.selects_primary is False
    assert result.market_numeric_values_inspected == []
    assert result.return_metrics_calculated == []
    assert audit_v3_p02_payload_pilot_stop_result(result)


def test_v3p02_stop_refuses_retry_or_selection_tampering() -> None:
    result = frozen_stop_result()
    payload = result.model_dump()
    payload["authorizes_retry"] = True
    payload["selects_primary"] = True

    with pytest.raises(ValidationError):
        V3P02PayloadPilotStopResult.model_validate(payload)


def test_v3p02_stop_refuses_failed_target_tampering() -> None:
    result = frozen_stop_result()
    payload = result.model_dump()
    payload["failed_sample"]["symbol"] = "AAVEUSDT"

    with pytest.raises(ValidationError):
        V3P02PayloadPilotStopResult.model_validate(payload)


def test_v3p02_stop_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/finalize_v3_p02_payload_pilot_stop.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "V3P02" in completed.stdout
