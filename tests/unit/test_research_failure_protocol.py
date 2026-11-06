import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_diagnostic_addendum import (
    R3MonthlyDiagnosticAddendum,
)
from aurex.backtest_engine.research_failure_protocol import (
    R3_FAILURE_ANALYSIS_DIMENSIONS,
    R3_FAILURE_PROHIBITIONS,
    R3FailureAnalysisProtocol,
    audit_r3_failure_analysis_protocol,
)
from aurex.backtest_engine.research_result import R3StudyResultLedger
from aurex.backtest_engine.research_run_package import R3RunPackage
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_r3_failure_analysis import authoritative_protocol


def protocol() -> R3FailureAnalysisProtocol:
    package = R3RunPackage.model_validate_json(
        Path(
            "data/evidence/r3_cross_sectional_momentum_run_package_v1.json"
        ).read_text(encoding="utf-8")
    )
    ledger = R3StudyResultLedger.model_validate_json(
        Path("data/evidence/r3_cross_sectional_momentum_result_v1.json").read_text(
            encoding="utf-8"
        )
    )
    addendum = R3MonthlyDiagnosticAddendum.model_validate_json(
        Path(
            "data/evidence/r3_cross_sectional_momentum_monthly_addendum_v1.json"
        ).read_text(encoding="utf-8")
    )
    return authoritative_protocol(
        registered_at=datetime(2026, 7, 22, 21, tzinfo=UTC),
        package=package,
        ledger=ledger,
        addendum=addendum,
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


def test_failure_protocol_is_explicitly_post_outcome_and_descriptive_only() -> None:
    frozen = protocol()

    assert frozen.status == "FROZEN_POST_OUTCOME_PRE_ANALYSIS"
    assert frozen.known_outcome_boundary.verdict == "NO_CANDIDATE"
    assert frozen.known_outcome_boundary.observed_positive_folds == 3
    assert frozen.known_outcome_boundary.required_positive_folds == 4
    assert len(frozen.replay_result_evidence_hashes) == 62
    assert frozen.analysis_dimensions == R3_FAILURE_ANALYSIS_DIMENSIONS
    assert frozen.prohibited_actions == R3_FAILURE_PROHIBITIONS
    assert frozen.analysis_is_descriptive_only is True
    assert frozen.creates_candidate is False
    assert frozen.opens_sealed_partition is False
    assert frozen.preexisting_analysis_artifacts == []
    assert audit_r3_failure_analysis_protocol(frozen) is True
    assert R3FailureAnalysisProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_failure_protocol_refuses_missing_prohibition() -> None:
    payload = protocol().model_dump()
    payload["prohibited_actions"].pop()

    with pytest.raises(ValidationError, match="prohibitions are fixed"):
        R3FailureAnalysisProtocol.model_validate(rehash(payload))


def test_failure_protocol_refuses_preexisting_analysis() -> None:
    payload = protocol().model_dump()
    payload["preexisting_analysis_artifacts"] = ["analysis.json"]

    with pytest.raises(ValidationError, match="predate its analysis artifact"):
        R3FailureAnalysisProtocol.model_validate(rehash(payload))


def test_failure_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r3_failure_analysis.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_authoritative_frozen_failure_protocol_matches_rebuild() -> None:
    stored = R3FailureAnalysisProtocol.model_validate_json(
        Path("data/evidence/r3_failure_analysis_protocol_v1.json").read_text(
            encoding="utf-8"
        )
    )
    rebuilt = protocol().model_copy(update={"registered_at": stored.registered_at})
    rebuilt_payload = rebuilt.model_dump(exclude={"protocol_evidence_hash"})
    rebuilt = R3FailureAnalysisProtocol.model_validate(
        {
            **rebuilt_payload,
            "protocol_evidence_hash": universe_evidence_hash(rebuilt_payload),
        }
    )

    assert stored == rebuilt
    assert stored.protocol_evidence_hash == (
        "62ec8d11920cc4634f624ca7ce11fa93a7dc3bebd9871122984aff21e1da7725"
    )
