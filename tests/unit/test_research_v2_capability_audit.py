import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_capability_audit import (
    V2CapabilityAudit,
    audit_v2_capability_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_capability_audit import (
    authoritative_audit,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    u1_result = evidence_root / "u1_primary_mechanism_result_v1.json"
    u1_screen = evidence_root / "u1_mechanism_theory_screen_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"


def audit() -> V2CapabilityAudit:
    inputs = load_inputs(Args())
    return authoritative_audit(
        frozen_at=datetime(2026, 7, 27, 15, tzinfo=UTC),
        u1_result=inputs[0],
        u1_screen=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )


def rehash(payload: dict) -> dict:
    payload["audit_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "audit_evidence_hash"
        }
    )
    return payload


def test_v2_capability_audit_blocks_mechanism_selection_and_returns() -> None:
    frozen = audit()

    assert frozen.ready_capability_count == 1
    assert frozen.blocked_capability_count == 11
    assert frozen.decision == (
        "BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER"
    )
    assert frozen.authorizes_data_contract_design is True
    assert frozen.authorizes_market_data_acquisition is False
    assert frozen.authorizes_mechanism_selection is False
    assert frozen.authorizes_strategy_return_calculation is False
    assert frozen.creates_candidate is False
    assert frozen.return_tested_mechanisms == 0
    assert audit_v2_capability_audit(frozen) is True
    assert V2CapabilityAudit.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_v2_capability_audit_refuses_forged_ready_count() -> None:
    payload = audit().model_dump()
    payload["ready_capability_count"] = 12
    payload["blocked_capability_count"] = 0

    with pytest.raises(ValidationError, match="counts do not match"):
        V2CapabilityAudit.model_validate(rehash(payload))


def test_v2_capability_audit_refuses_outcome_inspection() -> None:
    payload = audit().model_dump()
    payload["strategy_outcome_fields_inspected"] = ["net_pl"]

    with pytest.raises(ValidationError, match="cannot inspect strategy outcomes"):
        V2CapabilityAudit.model_validate(rehash(payload))


def test_v2_capability_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_v2_capability_audit.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
