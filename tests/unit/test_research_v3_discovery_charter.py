import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
    audit_v3_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v3_discovery_charter import (
    authoritative_charter,
    load_inputs,
)


class Args:
    v2_charter = Path(
        "data/evidence/v2_mechanism_discovery_charter_v1.json"
    )
    v2_screen = Path("data/evidence/v2_mechanism_theory_screen_v1.json")
    p01_protocol = Path("data/evidence/v2_p01_primary_protocol_v1.json")
    p01_result = Path(
        "data/evidence/v2_p01_full_acquisition_result_v1.json"
    )


def charter() -> V3MechanismDiscoveryCharter:
    return authoritative_charter(
        registered_at=datetime(2026, 7, 28, 11, tzinfo=UTC),
        inputs=load_inputs(Args()),
    )


def rehash(payload: dict) -> dict:
    payload["charter_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "charter_evidence_hash"
        }
    )
    return payload


def test_v3_charter_binds_p01_stop_and_permits_no_outcomes() -> None:
    frozen = charter()

    assert (
        frozen.p01_final_decision
        == "STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA"
    )
    assert frozen.p01_qualified_symbol_count == 0
    assert frozen.p01_return_metrics_calculated == []
    assert frozen.maximum_theory_proposals == 3
    assert frozen.maximum_selected_primary_mechanisms == 1
    assert frozen.maximum_return_tested_mechanisms_under_charter == 0
    assert frozen.maximum_parameter_sets_under_charter == 0
    assert frozen.may_reuse_p01_payload_for_coverage_only is True
    assert frozen.may_inspect_market_numeric_values is False
    assert frozen.may_calculate_signals_trades_or_returns is False
    assert frozen.development_outcomes_open is False
    assert frozen.validation_data_open is False
    assert frozen.holdout_data_open is False
    assert frozen.forward_data_open is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_sandbox_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert audit_v3_mechanism_discovery_charter(frozen)


def test_v3_charter_refuses_outcome_access_or_p01_rescue() -> None:
    payload = charter().model_dump()
    payload["may_inspect_market_numeric_values"] = True
    with pytest.raises(ValidationError):
        V3MechanismDiscoveryCharter.model_validate(rehash(payload))

    payload = charter().model_dump()
    payload["development_outcomes_open"] = True
    with pytest.raises(ValidationError):
        V3MechanismDiscoveryCharter.model_validate(rehash(payload))

    payload = charter().model_dump()
    payload["forbidden_derivations"].remove(
        "DO_NOT_RELAX_OR_REINTERPRET_P01_CONTINUITY_AFTER_FAILURE"
    )
    with pytest.raises(ValidationError, match="forbidden_derivations changed"):
        V3MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_v3_charter_refuses_partition_or_multiplicity_drift() -> None:
    payload = charter().model_dump()
    payload["maximum_selected_primary_mechanisms"] = 2
    with pytest.raises(ValidationError):
        V3MechanismDiscoveryCharter.model_validate(rehash(payload))

    payload = charter().model_dump()
    payload["partition_boundaries"][1]["access"] = (
        "TIMESTAMP_SCHEMA_COVERAGE_ONLY"
    )
    with pytest.raises(ValidationError):
        V3MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_v3_discovery_charter_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v3_discovery_charter.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
