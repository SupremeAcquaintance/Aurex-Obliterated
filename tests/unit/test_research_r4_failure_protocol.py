import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_r4_failure_protocol import (
    R4_FAILURE_ANALYSIS_DIMENSIONS,
    R4_FAILURE_PROHIBITIONS,
    R4FailureAnalysisProtocol,
    audit_r4_failure_analysis_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r4_failure_analysis import (
    authoritative_protocol,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    candidate = evidence_root / "r4_path_quality_candidate_v1.json"
    validation_bundle = evidence_root / "validation_2025_4h_bundle_v1.json"
    execution = evidence_root / "r4_path_quality_execution_spec_v1.json"
    run_package = evidence_root / "r4_path_quality_run_package_v1.json"
    result = evidence_root / "r4_path_quality_result_v1.json"


@lru_cache(maxsize=1)
def protocol() -> R4FailureAnalysisProtocol:
    inputs = load_inputs(Args())
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        candidate=inputs[0],
        validation_bundle=inputs[1],
        execution=inputs[2],
        run_package=inputs[3],
        result=inputs[4],
    )


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "protocol_evidence_hash"
        }
    )
    return payload


def test_r4_failure_protocol_binds_all_evidence_and_forbids_rescue() -> None:
    frozen = protocol()

    assert len(frozen.replay_result_evidence_hashes) == 42
    assert frozen.known_outcome_boundary.verdict == "RETIRE_R4_CANDIDATE"
    assert frozen.known_outcome_boundary.passed_gates == 4
    assert frozen.known_outcome_boundary.base_cost_net_pl < 0
    assert frozen.known_outcome_boundary.base_cost_raw_profit_factor < 1
    assert frozen.analysis_dimensions == R4_FAILURE_ANALYSIS_DIMENSIONS
    assert frozen.prohibited_actions == R4_FAILURE_PROHIBITIONS
    assert frozen.creates_candidate is False
    assert frozen.changes_r4_verdict is False
    assert frozen.opens_2026_or_forward_partition is False
    assert frozen.preexisting_analysis_artifacts == []
    assert audit_r4_failure_analysis_protocol(frozen) is True
    assert R4FailureAnalysisProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_r4_failure_protocol_refuses_changed_known_result() -> None:
    payload = protocol().model_dump()
    payload["known_outcome_boundary"]["base_cost_net_pl"] = "1"

    with pytest.raises(ValidationError, match="frozen ledger"):
        R4FailureAnalysisProtocol.model_validate(rehash(payload))


def test_r4_failure_protocol_refuses_added_analysis_dimension() -> None:
    payload = protocol().model_dump()
    payload["analysis_dimensions"].append("SEARCH_FOR_PROFITABLE_PARAMETERS")

    with pytest.raises(ValidationError, match="dimensions are fixed"):
        R4FailureAnalysisProtocol.model_validate(rehash(payload))


def test_r4_failure_protocol_refuses_preexisting_analysis() -> None:
    payload = protocol().model_dump()
    payload["preexisting_analysis_artifacts"] = [
        "r4_failure_analysis_result_v1.json"
    ]

    with pytest.raises(ValidationError, match="predate its analysis"):
        R4FailureAnalysisProtocol.model_validate(rehash(payload))


def test_r4_failure_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r4_failure_analysis.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
