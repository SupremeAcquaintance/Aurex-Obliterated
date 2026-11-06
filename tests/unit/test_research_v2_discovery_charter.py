import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_discovery_charter import (
    V2MechanismDiscoveryCharter,
    audit_v2_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_discovery_charter import (
    authoritative_charter,
    load_inputs,
)


class Args:
    foundation_protocol = Path(
        "data/evidence/v2_derivatives_foundation_protocol_v1.json"
    )
    foundation_result = Path(
        "data/evidence/v2_derivatives_foundation_result_v1.json"
    )


def charter() -> V2MechanismDiscoveryCharter:
    protocol, result = load_inputs(Args())
    return authoritative_charter(
        registered_at=datetime(2026, 7, 28, 5, tzinfo=UTC),
        protocol=protocol,
        result=result,
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


def test_v2_discovery_charter_permits_no_returns_or_full_data() -> None:
    frozen = charter()

    assert frozen.maximum_theory_proposals == 3
    assert frozen.maximum_selected_primary_mechanisms == 1
    assert frozen.maximum_return_tested_mechanisms_under_charter == 0
    assert frozen.theory_screen_may_read_market_returns is False
    assert frozen.theory_screen_may_download_full_dataset is False
    assert frozen.development_data_open is False
    assert frozen.validation_data_open is False
    assert frozen.holdout_data_open is False
    assert frozen.selection_creates_candidate is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert len(frozen.complete_source_symbols) == 31
    assert len(frozen.excluded_incomplete_symbols) == 4
    assert audit_v2_mechanism_discovery_charter(frozen)


def test_v2_discovery_charter_refuses_return_or_partition_access() -> None:
    payload = charter().model_dump()
    payload["maximum_return_tested_mechanisms_under_charter"] = 1
    with pytest.raises(ValidationError):
        V2MechanismDiscoveryCharter.model_validate(rehash(payload))

    payload = charter().model_dump()
    payload["development_data_open"] = True
    with pytest.raises(ValidationError):
        V2MechanismDiscoveryCharter.model_validate(rehash(payload))

    payload = charter().model_dump()
    payload["complete_source_symbols"][-1] = "CFXUSDT"
    with pytest.raises(ValidationError, match="complete_source_symbols changed"):
        V2MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_v2_discovery_charter_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_discovery_charter.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
