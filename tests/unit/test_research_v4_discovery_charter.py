from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_discovery_charter import (
    V4_ALLOWED_NEXT_DECISIONS,
    V4_DISCOVERY_STAGES,
    V4_EXECUTION_FEASIBILITY_POLICY,
    V4_FORBIDDEN_DERIVATIONS,
    V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES,
    V4_PERMITTED_FEASIBILITY_FIELDS,
    V4_REQUIRED_SUCCESSOR_BINDINGS,
    V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE,
    V4_SOURCE_DATA_POLICY,
    V4_SOURCE_TRANSPORT_POLICY,
    V4_STOP_CONDITIONS,
    V4_THEORY_SOURCE_POLICY,
    V4DiscoveryPartitionBoundary,
    V4MechanismDiscoveryCharter,
    audit_v4_mechanism_discovery_charter,
)
from scripts.freeze_v4_discovery_charter import (
    authoritative_charter,
    load_inputs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTERED_AT = datetime(2026, 7, 28, 18, 30, tzinfo=UTC)


def input_args() -> SimpleNamespace:
    evidence = PROJECT_ROOT / "data" / "evidence"
    return SimpleNamespace(
        v3_charter=evidence / "v3_mechanism_discovery_charter_v1.json",
        v3_register=evidence / "v3_mechanism_proposal_register_v1.json",
        v3_screen=evidence / "v3_mechanism_feasibility_screen_v1.json",
        v3p01_result=evidence
        / "v3_p01_execution_feasibility_result_v1.json",
        v3p02_stop=evidence
        / "v3_p02_payload_pilot_stop_result_v1.json",
        v3p03_stop=evidence / "v3_p03_source_audit_stop_result_v1.json",
        contamination_ledger=evidence
        / "strategy_contamination_ledger_v1.json",
    )


def frozen_charter() -> V4MechanismDiscoveryCharter:
    return authoritative_charter(
        registered_at=REGISTERED_AT,
        inputs=load_inputs(input_args()),
    )


def test_v4_charter_binds_terminal_v3_zero_selection() -> None:
    charter = frozen_charter()

    assert charter.v3_final_decision == "SELECT_ZERO_V3_PRIMARY_MECHANISMS"
    assert charter.v3_selected_primary_count == 0
    assert charter.v3_return_metrics_calculated == []
    assert charter.maximum_theory_proposals == 3
    assert charter.maximum_selected_primary_mechanisms == 1
    assert charter.maximum_return_tested_mechanisms_under_charter == 0
    assert charter.maximum_parameter_sets_under_charter == 0
    assert charter.successor_maximum_selectable_parameter_sets == 1
    assert charter.charter_authorizes_network_requests is False
    assert charter.successor_transport_contract_required_before_network is True
    assert charter.may_inspect_market_numeric_values is False
    assert charter.may_calculate_signals_trades_or_returns is False
    assert charter.selection_creates_candidate is False
    assert charter.preexisting_v4_successor_artifacts == []
    assert audit_v4_mechanism_discovery_charter(charter)


def test_v4_charter_freezes_all_policy_sets() -> None:
    charter = frozen_charter()

    assert charter.required_theory_and_feasibility_evidence == sorted(
        V4_REQUIRED_THEORY_AND_FEASIBILITY_EVIDENCE
    )
    assert charter.theory_source_policy == sorted(V4_THEORY_SOURCE_POLICY)
    assert charter.source_data_policy == sorted(V4_SOURCE_DATA_POLICY)
    assert charter.source_transport_policy == sorted(
        V4_SOURCE_TRANSPORT_POLICY
    )
    assert charter.execution_feasibility_policy == sorted(
        V4_EXECUTION_FEASIBILITY_POLICY
    )
    assert charter.forbidden_derivations == sorted(V4_FORBIDDEN_DERIVATIONS)
    assert charter.known_blocked_or_retired_lineages == sorted(
        V4_KNOWN_BLOCKED_OR_RETIRED_LINEAGES
    )
    assert charter.required_successor_bindings == sorted(
        V4_REQUIRED_SUCCESSOR_BINDINGS
    )
    assert charter.discovery_stages == sorted(V4_DISCOVERY_STAGES)
    assert charter.stop_conditions == sorted(V4_STOP_CONDITIONS)
    assert charter.allowed_next_decisions == sorted(V4_ALLOWED_NEXT_DECISIONS)
    assert charter.permitted_feasibility_fields == sorted(
        V4_PERMITTED_FEASIBILITY_FIELDS
    )


def test_v4_charter_freezes_partition_boundaries() -> None:
    charter = frozen_charter()

    assert [item.partition for item in charter.partition_boundaries] == [
        "DEVELOPMENT",
        "VALIDATION",
        "HOLDOUT",
        "FORWARD",
    ]
    assert charter.partition_boundaries[0].access == (
        "SOURCE_METADATA_TIMESTAMP_SCHEMA_ONLY"
    )
    assert charter.partition_boundaries[1].access == (
        "SEALED_FOR_INDEPENDENT_MECHANISM"
    )
    assert charter.partition_boundaries[2].access == "SEALED_AND_NOT_IMPORTED"
    assert charter.partition_boundaries[3].access == "LOCKED"

    with pytest.raises(ValidationError):
        V4DiscoveryPartitionBoundary(
            partition="VALIDATION",
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 2, tzinfo=UTC),
            role="FUTURE_INTERNAL_VALIDATION_NOT_ELIGIBILITY",
            access="SEALED_FOR_INDEPENDENT_MECHANISM",
        )


def test_v4_charter_refuses_network_permission_tampering() -> None:
    payload = frozen_charter().model_dump()
    payload["charter_authorizes_network_requests"] = True

    with pytest.raises(ValidationError):
        V4MechanismDiscoveryCharter.model_validate(payload)


def test_v4_charter_refuses_transport_policy_weakening() -> None:
    payload = frozen_charter().model_dump()
    payload["source_transport_policy"].remove(
        "COUNT_CUMULATIVE_ATTEMPTS_ACROSS_PROCESS_RESTARTS"
    )

    with pytest.raises(ValidationError):
        V4MechanismDiscoveryCharter.model_validate(payload)


def test_v4_charter_refuses_v3_lineage_or_successor_tampering() -> None:
    payload = frozen_charter().model_dump()
    payload["v3_feasibility_screen_evidence_hash"] = "f" * 64
    payload["preexisting_v4_successor_artifacts"] = [
        "data/evidence/v4_mechanism_proposal_register_v1.json"
    ]

    with pytest.raises(ValidationError):
        V4MechanismDiscoveryCharter.model_validate(payload)


def test_v4_charter_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_discovery_charter.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "V4" in completed.stdout
