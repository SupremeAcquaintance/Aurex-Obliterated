from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_p01_continuation_contract import (
    TARDIS_EXCHANGE_DETAILS_URL,
    TARDIS_INSTRUMENT_METADATA_URL,
    V4P01ContinuationContract,
    audit_v4_p01_continuation_contract,
)
from scripts.freeze_v4_p01_continuation_contract import (
    DEFAULT_CHARTER,
    DEFAULT_ORIGINAL_CONTRACT,
    DEFAULT_REGISTER,
    authoritative_contract,
    load_original_evidence,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FROZEN_AT = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


def frozen_contract() -> V4P01ContinuationContract:
    original, terminal, observations, metadata_gate = load_original_evidence(
        charter_path=PROJECT_ROOT / DEFAULT_CHARTER,
        register_path=PROJECT_ROOT / DEFAULT_REGISTER,
        contract_path=PROJECT_ROOT / DEFAULT_ORIGINAL_CONTRACT,
    )
    return authoritative_contract(
        frozen_at=FROZEN_AT,
        source_reviewed_at=FROZEN_AT,
        original=original,
        terminal=terminal,
        observations=observations,
        metadata_gate=metadata_gate,
    )


def test_continuation_binds_original_reject_without_rewriting_it() -> None:
    contract = frozen_contract()

    assert contract.correction_class == (
        "RUNNER_INTERPRETATION_DEFECT_NOT_MARKET_OR_STRATEGY_EVIDENCE"
    )
    assert contract.original_reject_is_deleted_or_rewritten is False
    assert contract.original_terminal_reject_evidence_hash == (
        "198d69b4358d7c980357201a7dbb2b209ccf4c8f2186009a9cc8a4c3cf7b8df2"
    )
    assert contract.transport_budget.inherited_attempts_consumed == 2
    assert contract.transport_budget.inherited_response_bytes_consumed == 74_788
    assert audit_v4_p01_continuation_contract(contract)


def test_continuation_authorizes_only_six_unconsumed_payload_requests() -> None:
    contract = frozen_contract()

    assert [item.sequence for item in contract.requests] == list(range(3, 9))
    assert all(
        item.phase == "PAYLOAD_SCHEMA_PILOT" for item in contract.requests
    )
    assert contract.transport_budget.metadata_attempt_budget == 0
    assert contract.transport_budget.metadata_repeat_permitted is False
    assert contract.transport_budget.continuation_attempt_budget == 6
    assert contract.transport_budget.continuation_retry_budget == 0
    assert contract.authorized_network_scope == (
        "EXACT_SIX_UNCONSUMED_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    )


def test_continuation_binds_documented_optional_end_semantic() -> None:
    contract = frozen_contract()

    assert contract.official_source_urls == sorted(
        [TARDIS_EXCHANGE_DETAILS_URL, TARDIS_INSTRUMENT_METADATA_URL]
    )
    assert "optional" in contract.documented_semantic
    assert "ongoing collection" in contract.documented_semantic
    assert "symbol availableTo is absent" in (
        contract.corrected_metadata_condition
    )
    assert len(contract.inherited_metadata_observation_hashes) == 2


def test_continuation_grants_no_outcome_or_trading_permission() -> None:
    contract = frozen_contract()

    assert contract.market_numeric_value_inspection_permitted is False
    assert contract.signal_trade_pnl_or_return_calculation_permitted is False
    assert contract.strategy_outcome_fields_inspected == []
    assert contract.return_metrics_calculated == []
    assert contract.selects_primary is False
    assert contract.creates_candidate is False
    assert contract.creates_paper_eligibility is False
    assert contract.creates_sandbox_eligibility is False
    assert contract.creates_live_eligibility is False


def test_continuation_rejects_repeated_metadata_or_permission_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["requests"][0]["phase"] = "METADATA_CENSUS"
    payload["metadata_requests_authorized"] = True
    payload["selects_primary"] = True
    payload["contract_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P01ContinuationContract.model_validate(payload)


def test_continuation_freeze_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_p01_continuation_contract.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "six-request continuation contract" in completed.stdout
