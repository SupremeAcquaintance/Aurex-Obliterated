import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_u1_discovery_charter import (
    U1_FORBIDDEN_DERIVATIONS,
    U1_MINIMUM_ADVANCEMENT_GATES,
    U1MechanismDiscoveryCharter,
    audit_u1_mechanism_discovery_charter,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_u1_mechanism_discovery_charter import (
    authoritative_charter,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    r4_failure_result = evidence_root / "r4_failure_analysis_result_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    development = evidence_root / "development_4h_dataset_bundle_v1.json"
    validation = evidence_root / "validation_2025_4h_bundle_v1.json"


@lru_cache(maxsize=1)
def charter() -> U1MechanismDiscoveryCharter:
    inputs = load_inputs(Args())
    return authoritative_charter(
        registered_at=datetime(2026, 7, 27, 14, tzinfo=UTC),
        failure=inputs[0],
        contamination=inputs[1],
        universe=inputs[2],
        development=inputs[3],
        validation=inputs[4],
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


def test_u1_charter_binds_evidence_and_keeps_capital_closed() -> None:
    frozen = charter()

    assert [item.partition for item in frozen.partition_boundaries] == [
        "DEVELOPMENT",
        "VALIDATION",
        "HOLDOUT",
        "FORWARD",
    ]
    assert frozen.maximum_theory_proposals == 3
    assert frozen.maximum_return_tested_mechanisms == 1
    assert frozen.maximum_selectable_parameter_sets == 1
    assert frozen.theory_screen_may_read_market_returns is False
    assert frozen.holdout_is_required_for_eligibility is True
    assert frozen.opens_2026_or_forward_partition is False
    assert frozen.permits_pine_parity is False
    assert frozen.creates_paper_eligibility is False
    assert frozen.creates_live_eligibility is False
    assert frozen.forbidden_derivations == U1_FORBIDDEN_DERIVATIONS
    assert frozen.minimum_advancement_gates == U1_MINIMUM_ADVANCEMENT_GATES
    assert audit_u1_mechanism_discovery_charter(frozen) is True
    assert U1MechanismDiscoveryCharter.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_u1_charter_refuses_return_selected_primary() -> None:
    payload = charter().model_dump()
    payload["theory_screen_may_read_market_returns"] = True

    with pytest.raises(ValidationError, match="Input should be False"):
        U1MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_u1_charter_refuses_a_second_return_tested_mechanism() -> None:
    payload = charter().model_dump()
    payload["maximum_return_tested_mechanisms"] = 2

    with pytest.raises(ValidationError, match="Input should be 1"):
        U1MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_u1_charter_refuses_opening_the_final_holdout() -> None:
    payload = charter().model_dump()
    payload["partition_boundaries"][2]["access"] = "OPEN"

    with pytest.raises(ValidationError, match="HOLDOUT discovery boundary is fixed"):
        U1MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_u1_charter_refuses_removing_failure_stop_rule() -> None:
    payload = charter().model_dump()
    payload["stop_conditions"].remove("ANY_PREDECLARED_ADVANCEMENT_GATE_FAILS")

    with pytest.raises(ValidationError, match="stop_conditions is fixed"):
        U1MechanismDiscoveryCharter.model_validate(rehash(payload))


def test_u1_charter_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_u1_mechanism_discovery_charter.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
