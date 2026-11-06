import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_p01_protocol import (
    V2P01PrimaryProtocol,
    audit_v2_p01_primary_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_p01_protocol import (
    authoritative_protocol,
    full_source_target_manifest_hash,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    foundation_protocol = Path(
        "data/evidence/v2_derivatives_foundation_protocol_v1.json"
    )
    foundation_result = Path(
        "data/evidence/v2_derivatives_foundation_result_v1.json"
    )
    charter = Path("data/evidence/v2_mechanism_discovery_charter_v1.json")
    theory_screen = Path("data/evidence/v2_mechanism_theory_screen_v1.json")
    superseded_contract = Path(
        "data/evidence/v2_p01_metadata_source_contract_v1.json"
    )
    metadata_contract = Path(
        "data/evidence/v2_p01_metadata_source_contract_v1_1.json"
    )
    metadata_result = Path(
        "data/evidence/v2_p01_metadata_source_audit_v1_1.json"
    )
    source_census_contract = Path(
        "data/evidence/v2_derivatives_source_census_contract_v1.json"
    )
    source_census_result = Path(
        "data/evidence/v2_derivatives_source_census_result_v1.json"
    )
    pilot_protocol = Path(
        "data/evidence/v2_derivatives_acquisition_protocol_v1.json"
    )
    pilot_result = Path(
        "data/evidence/v2_derivatives_pilot_acquisition_result_v1.json"
    )


def protocol() -> V2P01PrimaryProtocol:
    return authoritative_protocol(
        frozen_at=datetime(2026, 7, 28, 16, tzinfo=UTC),
        inputs=load_inputs(Args()),
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


def test_p01_protocol_is_exact_pre_return_and_noneligible() -> None:
    frozen = protocol()

    assert frozen.acquisition.source_target_count == 4464
    assert len(frozen.acquisition.complete_source_symbols) == 31
    assert len(frozen.run_matrix) == 35
    assert sum(run.selectable for run in frozen.run_matrix) == 1
    assert frozen.signal.parameter_search_allowed is False
    assert (
        frozen.return_calculation_permitted_before_acquisition_pass is False
    )
    assert frozen.authorizes_development_return_after_acquisition_pass is True
    assert frozen.creates_candidate is False
    assert frozen.permits_validation is False
    assert frozen.permits_holdout_or_forward is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert audit_v2_p01_primary_protocol(frozen)


def test_p01_protocol_manifest_binds_all_complete_census_targets() -> None:
    inputs = load_inputs(Args())
    census_result = inputs[3]
    frozen = authoritative_protocol(
        frozen_at=datetime(2026, 7, 28, 16, tzinfo=UTC),
        inputs=inputs,
    )

    assert frozen.acquisition.source_target_manifest_hash == (
        full_source_target_manifest_hash(census_result)
    )


def test_p01_protocol_refuses_threshold_permission_or_run_drift() -> None:
    payload = protocol().model_dump()
    payload["signal"]["entry_minimum_trailing_annualized_funding"] = "0.20"
    with pytest.raises(ValidationError):
        V2P01PrimaryProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["creates_live_eligibility"] = True
    with pytest.raises(ValidationError):
        V2P01PrimaryProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["run_matrix"][1]["selectable"] = True
    with pytest.raises(ValidationError):
        V2P01PrimaryProtocol.model_validate(rehash(payload))


def test_p01_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_p01_protocol.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
