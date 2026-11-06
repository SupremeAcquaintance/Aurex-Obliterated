from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_operator_access_profile import (
    OPERATOR_PROFILE_FAIL_DECISION,
    OPERATOR_PROFILE_GATE_IDS,
    OPERATOR_PROFILE_PASS_DECISION,
    OperatorAccessCapitalDataInput,
    PostV4OperatorAccessProfile,
    audit_post_v4_operator_access_profile,
    build_post_v4_operator_access_profile,
)
from scripts.freeze_post_v4_operator_profile import (
    PROFILE_LIMITATIONS,
    template_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
REVIEW_HASH = "1" * 64
REVIEW_BUILDER_HASH = "2" * 64
BUILDER_HASH = "3" * 64


def valid_input_payload() -> dict:
    return {
        "schema_version": "aurex-post-v4-operator-access-input-v1",
        "attested_at": NOW,
        "operator_identifier": "test-operator",
        "attestation_statement": (
            "I_ATTEST_THIS_PROFILE_IS_ACCURATE_AND_CONTAINS_NO_CREDENTIALS"
        ),
        "jurisdiction": "South Africa",
        "intended_execution_venue": "Example Exchange",
        "account_identifier_alias": "primary-test-account",
        "account_status": "VERIFIED",
        "api_access_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "sandbox_access_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "permitted_product_scope": "SPOT_ONLY",
        "other_product_scope": None,
        "derivatives_access_confirmed": False,
        "derivatives_suitability_acknowledged": False,
        "maximum_effective_leverage": "1",
        "legal_and_tax_obligations_acknowledged": True,
        "starting_trading_capital": "1000",
        "capital_currency": "USD",
        "capital_is_borrowed": False,
        "capital_excludes_emergency_funds": True,
        "maximum_total_loss": "100",
        "maximum_daily_loss": "10",
        "maximum_per_trade_loss": "5",
        "one_time_data_budget": "0",
        "monthly_data_budget": "0",
        "data_budget_currency": "USD",
        "paid_data_permitted": False,
        "venue_terms_reference": "https://example.test/terms",
        "fee_schedule_reference": "https://example.test/fees",
        "api_documentation_reference": "https://example.test/api",
        "product_access_evidence_reference": "operator-note:product-access",
        "sandbox_evidence_reference": "https://example.test/sandbox",
        "capital_source_attestation_reference": "operator-note:capital-source",
        "data_budget_attestation_reference": "operator-note:data-budget",
        "credentials_stored_or_embedded": False,
    }


def operator_input(**changes) -> OperatorAccessCapitalDataInput:
    payload = valid_input_payload()
    payload.update(changes)
    return OperatorAccessCapitalDataInput.model_validate(payload)


def profile_for(
    value: OperatorAccessCapitalDataInput,
) -> PostV4OperatorAccessProfile:
    return build_post_v4_operator_access_profile(
        frozen_at=NOW,
        post_v4_capability_review_evidence_hash=REVIEW_HASH,
        post_v4_capability_review_builder_hash=REVIEW_BUILDER_HASH,
        builder_contract_hash=BUILDER_HASH,
        operator_input=value,
        limitations=PROFILE_LIMITATIONS,
    )


def test_valid_profile_authorizes_only_successor_charter_design() -> None:
    profile = profile_for(operator_input())

    assert [item.gate_id for item in profile.gate_results] == (
        OPERATOR_PROFILE_GATE_IDS
    )
    assert all(item.status == "PASS" for item in profile.gate_results)
    assert profile.failed_gate_ids == []
    assert profile.decision == OPERATOR_PROFILE_PASS_DECISION
    assert profile.successor_charter_design_authorized is True
    assert profile.successor_alpha_discovery_authorized is False
    assert profile.network_requests_authorized is False
    assert profile.return_testing_authorized is False
    assert profile.creates_candidate is False
    assert profile.creates_live_eligibility is False
    assert profile.first_profit_milestone == Decimal("100")
    assert profile.first_profit_milestone_to_capital_ratio == Decimal("0.1")
    assert audit_post_v4_operator_access_profile(profile)


@pytest.mark.parametrize(
    ("changes", "failed_gate"),
    [
        (
            {"account_status": "UNVERIFIED"},
            "ACCOUNT_AND_API_ACCESS_PROVEN",
        ),
        (
            {"api_access_status": "UNKNOWN"},
            "ACCOUNT_AND_API_ACCESS_PROVEN",
        ),
        (
            {"sandbox_access_status": "UNAVAILABLE"},
            "SANDBOX_PATH_AVAILABLE",
        ),
        (
            {"capital_excludes_emergency_funds": False},
            "CAPITAL_SOURCE_AND_RESERVE_SAFE",
        ),
        (
            {"maximum_per_trade_loss": "6"},
            "LOSS_LIMITS_CAPITAL_PROTECTIVE",
        ),
        (
            {"maximum_daily_loss": "11"},
            "LOSS_LIMITS_CAPITAL_PROTECTIVE",
        ),
        (
            {"maximum_total_loss": "101"},
            "LOSS_LIMITS_CAPITAL_PROTECTIVE",
        ),
        (
            {"maximum_effective_leverage": "1.01"},
            "PRODUCT_SCOPE_AND_LEVERAGE_SAFE",
        ),
        (
            {"legal_and_tax_obligations_acknowledged": False},
            "VENUE_AND_JURISDICTION_BOUND",
        ),
    ],
)
def test_unsafe_or_unproven_profile_blocks_charter_design(
    changes: dict,
    failed_gate: str,
) -> None:
    profile = profile_for(operator_input(**changes))

    assert profile.decision == OPERATOR_PROFILE_FAIL_DECISION
    assert profile.successor_charter_design_authorized is False
    assert failed_gate in profile.failed_gate_ids


def test_borrowed_capital_is_structurally_rejected() -> None:
    with pytest.raises(ValidationError, match="capital_is_borrowed"):
        operator_input(capital_is_borrowed=True)


def test_derivative_scope_requires_access_and_suitability() -> None:
    with pytest.raises(ValidationError, match="Derivative scope requires"):
        operator_input(permitted_product_scope="SPOT_AND_PERPETUALS")


def test_spot_only_scope_refuses_derivative_attestations() -> None:
    with pytest.raises(ValidationError, match="Spot-only scope"):
        operator_input(derivatives_access_confirmed=True)


def test_nonzero_data_budget_requires_paid_data_permission() -> None:
    with pytest.raises(ValidationError, match="paid_data_permitted"):
        operator_input(one_time_data_budget="100")


@pytest.mark.parametrize(
    "value",
    [
        "api_key=do-not-store-this",
        "Authorization: Bearer do-not-store-this",
        "-----BEGIN PRIVATE KEY-----",
        "password=do-not-store-this",
        "client_secret=do-not-store-this",
        "seed phrase do not store these words",
    ],
)
def test_credential_patterns_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError, match="credential material"):
        operator_input(product_access_evidence_reference=value)


@pytest.mark.parametrize(
    "value",
    [
        "1234567890123456",
        "account-123456789",
        "acct-123456-78",
    ],
)
def test_account_alias_rejects_account_number_shapes(value: str) -> None:
    with pytest.raises(ValidationError, match="must not contain an account number"):
        operator_input(account_identifier_alias=value)


def test_profile_refuses_permission_and_hash_tampering() -> None:
    profile = profile_for(operator_input())
    payload = profile.model_dump()
    payload["network_requests_authorized"] = True

    with pytest.raises(ValidationError):
        PostV4OperatorAccessProfile.model_validate(payload)

    payload = profile.model_dump()
    payload["maximum_total_loss_ratio"] = Decimal("0.09")
    with pytest.raises(ValidationError, match="derived ratios changed"):
        PostV4OperatorAccessProfile.model_validate(payload)


def test_template_is_incomplete_and_contains_no_secret_fields() -> None:
    template = template_payload()

    assert template["starting_trading_capital"] == "0.00"
    assert template["capital_is_borrowed"] is False
    assert template["credentials_stored_or_embedded"] is False
    lowered_keys = " ".join(template).casefold()
    assert "api_key" not in lowered_keys
    assert "password" not in lowered_keys
    assert "private_key" not in lowered_keys


def test_cli_preflight_blocked_profile_writes_no_artifact(
    tmp_path: Path,
) -> None:
    payload = valid_input_payload()
    payload["account_status"] = "UNVERIFIED"
    payload["attested_at"] = NOW.isoformat()
    input_path = tmp_path / "blocked_input.json"
    output_path = tmp_path / "must_not_exist.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_post_v4_operator_profile.py",
            "--preflight",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "BLOCK_SUCCESSOR_DISCOVERY" in completed.stdout
    assert not output_path.exists()


def test_cli_freezes_and_checks_passing_profile(tmp_path: Path) -> None:
    payload = valid_input_payload()
    payload["attested_at"] = NOW.isoformat()
    input_path = tmp_path / "valid_input.json"
    output_path = tmp_path / "frozen_profile.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    freeze = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_post_v4_operator_profile.py",
            "--freeze",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert freeze.returncode == 0, freeze.stderr
    assert "AUTHORIZE_SUCCESSOR_CHARTER_DESIGN_ONLY" in freeze.stdout
    assert output_path.is_file()

    check = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_post_v4_operator_profile.py",
            "--check",
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr
    assert "charter_design=True" in check.stdout
