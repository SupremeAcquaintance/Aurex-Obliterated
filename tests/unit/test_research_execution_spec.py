import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.development_bundle import DevelopmentDatasetBundle
from aurex.backtest_engine.research_execution_spec import (
    R3ExecutionSpecification,
    audit_r3_execution_specification,
)
from aurex.backtest_engine.research_study import R3MechanismStudyProtocol
from aurex.backtest_engine.universe import MarketUniverseManifest, universe_evidence_hash
from scripts.freeze_r3_execution_spec import (
    authoritative_execution_specification,
    builder_contract_hash,
    load_verified_protocol,
    selected_count,
)


def frozen_inputs() -> tuple[
    MarketUniverseManifest,
    DevelopmentDatasetBundle,
    R3MechanismStudyProtocol,
]:
    universe = MarketUniverseManifest.model_validate_json(
        Path("data/evidence/market_universe_manifest_v1.json").read_text(
            encoding="utf-8"
        )
    )
    bundle = DevelopmentDatasetBundle.model_validate_json(
        Path("data/evidence/development_4h_dataset_bundle_v1.json").read_text(
            encoding="utf-8"
        )
    )
    protocol = load_verified_protocol(
        Path("data/evidence/r3_cross_sectional_momentum_study_v1.json"),
        universe=universe,
        bundle=bundle,
    )
    return universe, bundle, protocol


def specification() -> R3ExecutionSpecification:
    universe, bundle, protocol = frozen_inputs()
    return authoritative_execution_specification(
        registered_at=datetime(2026, 7, 22, 19, tzinfo=UTC),
        protocol=protocol,
        universe=universe,
        bundle=bundle,
    )


def rehash(payload: dict) -> dict:
    payload["specification_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "specification_evidence_hash"
        }
    )
    return payload


def test_authoritative_execution_specification_is_exact_and_round_trips() -> None:
    frozen = specification()

    assert frozen.inputs.decision_symbol_count == 35
    assert frozen.signals.fixed_selected_count == 7
    assert frozen.signals.selected_count_is_fixed_in_leave_one_out is True
    assert frozen.orders.rebalance_event_order == [
        "EXIT_EXISTING_AT_OPEN",
        "RANK_FROM_PRIOR_CLOSE",
        "ALLOCATE_NEW_AT_OPEN",
        "DISABLE_NEW_POSITION_SAME_BAR_STOP",
        "MARK_ALL_POSITIONS_AT_CLOSE",
    ]
    assert frozen.orders.stop_checked_on_entry_bar is False
    assert frozen.orders.rebalance_exit_precedes_stop_check is True
    assert frozen.orders.same_symbol_reentry_on_rebalance is True
    assert frozen.orders.final_bar_processing == (
        "PROCESS_NORMAL_EVENTS_THEN_LIQUIDATE_SURVIVORS_AT_CLOSE"
    )
    assert frozen.metrics.profit_factor_zero_loss_policy == "NULL_AND_GATE_FAIL"
    assert frozen.preexisting_result_artifacts == []
    assert frozen.outcome_fields_inspected == []
    assert audit_r3_execution_specification(frozen) is True
    assert R3ExecutionSpecification.model_validate_json(frozen.model_dump_json()) == frozen


def test_execution_specification_refuses_any_pre_freeze_outcome() -> None:
    payload = specification().model_dump()
    payload["outcome_fields_inspected"] = ["primary.net_pl"]

    with pytest.raises(ValidationError, match="predate every study outcome"):
        R3ExecutionSpecification.model_validate(rehash(payload))


def test_execution_specification_refuses_changed_event_order() -> None:
    payload = specification().model_dump()
    payload["orders"]["rebalance_event_order"][0:2] = [
        "RANK_FROM_PRIOR_CLOSE",
        "EXIT_EXISTING_AT_OPEN",
    ]

    with pytest.raises(ValidationError, match="rebalance event order is fixed"):
        R3ExecutionSpecification.model_validate(rehash(payload))


def test_execution_specification_refuses_changed_sizing_order() -> None:
    payload = specification().model_dump()
    payload["allocation"]["candidate_quantity_order"][0:2] = [
        "APPLY_SYMBOL_CAP",
        "COMPUTE_RISK_QUANTITY",
    ]

    with pytest.raises(ValidationError, match="candidate quantity order is fixed"):
        R3ExecutionSpecification.model_validate(rehash(payload))


def test_execution_specification_is_bound_to_frozen_protocol_and_data() -> None:
    universe, bundle, protocol = frozen_inputs()
    frozen = specification()

    assert selected_count(protocol) == 7
    assert frozen.protocol_evidence_hash == protocol.protocol_evidence_hash
    assert frozen.universe_manifest_evidence_hash == universe.manifest_evidence_hash
    assert (
        frozen.development_dataset_bundle_evidence_hash == bundle.bundle_evidence_hash
    )
    assert frozen.builder_contract_hash == builder_contract_hash()
    assert len(frozen.builder_contract_hash) == 64


def test_execution_specification_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/freeze_r3_execution_spec.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Freeze or offline-verify exact pre-outcome" in completed.stdout


def test_authoritative_frozen_execution_spec_matches_offline_rebuild() -> None:
    stored = R3ExecutionSpecification.model_validate_json(
        Path(
            "data/evidence/r3_cross_sectional_momentum_execution_spec_v1.json"
        ).read_text(encoding="utf-8")
    )
    universe, bundle, protocol = frozen_inputs()
    rebuilt = authoritative_execution_specification(
        registered_at=stored.registered_at,
        protocol=protocol,
        universe=universe,
        bundle=bundle,
    )

    assert stored == rebuilt
    assert stored.specification_evidence_hash == (
        "7125758ab4b4672576db8de49d8f67f5988f02dc5c39e2d94d36ae2e7edb6eb6"
    )
