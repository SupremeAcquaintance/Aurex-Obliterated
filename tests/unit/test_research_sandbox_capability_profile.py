from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_sandbox_capability_profile import (
    SANDBOX_PROFILE_GATE_IDS,
    SANDBOX_PROFILE_PASS_DECISION,
    BinanceSpotTestnetSandboxInput,
    BinanceSpotTestnetSandboxProfile,
    audit_binance_spot_testnet_sandbox_profile,
    build_binance_spot_testnet_sandbox_profile,
)
from aurex.backtest_engine.sandbox_profile_workflow import (
    SANDBOX_PROFILE_LIMITATIONS,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def valid_input_payload() -> dict:
    return {
        "schema_version": "aurex-binance-spot-testnet-input-v1",
        "attested_at": NOW,
        "operator_identifier": "aurex_operator_primary",
        "attestation_statement": (
            "I_ATTEST_BINANCE_SPOT_TESTNET_ACCESS_IS_AUTHENTICATED_AND_"
            "NO_CREDENTIALS_ARE_INCLUDED"
        ),
        "jurisdiction": "Zimbabwe",
        "sandbox_venue": "Binance Spot Test Network",
        "sandbox_environment": "TESTNET",
        "account_identifier_alias": "aurex_binance_spot_testnet",
        "authentication_method": "GITHUB_OAUTH",
        "testnet_access_status": "AUTHENTICATED",
        "api_credential_path_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "testnet_rest_base_url": "https://testnet.binance.vision/api",
        "testnet_ws_api_url": (
            "wss://ws-api.testnet.binance.vision/ws-api/v3"
        ),
        "testnet_stream_url": "wss://stream.testnet.binance.vision/ws",
        "permitted_product_scope": "SPOT_ONLY",
        "permitted_symbols": ["BTCUSDT"],
        "maximum_effective_leverage": "1",
        "simulated_starting_equity": "100",
        "equity_currency": "USD",
        "maximum_total_loss": "10",
        "maximum_daily_loss": "1",
        "maximum_per_trade_loss": "0.5",
        "one_time_data_budget": "0",
        "monthly_data_budget": "0",
        "data_budget_currency": "USD",
        "paid_data_permitted": False,
        "testnet_funds_are_virtual_acknowledged": True,
        "testnet_monthly_reset_behavior_acknowledged": True,
        "testnet_performance_is_not_edge_evidence_acknowledged": True,
        "production_account_verified": False,
        "production_api_authorized": False,
        "real_capital_authorized": False,
        "live_trading_authorized": False,
        "testnet_documentation_reference": "https://testnet.binance.vision/",
        "api_documentation_reference": (
            "https://developers.binance.com/en/docs/products/spot/rest-api"
        ),
        "fee_schedule_reference": "https://www.binance.com/en/fee/trading",
        "access_attestation_reference": (
            "operator-attestation:testnet-authenticated"
        ),
        "risk_attestation_reference": (
            "operator-attestation:100-usd-simulated-risk-boundary"
        ),
        "data_budget_attestation_reference": (
            "operator-attestation:zero-usd-initial-data-budget"
        ),
        "credentials_stored_or_embedded": False,
    }


def profile_for(
    value: BinanceSpotTestnetSandboxInput,
) -> BinanceSpotTestnetSandboxProfile:
    return build_binance_spot_testnet_sandbox_profile(
        frozen_at=NOW,
        post_v4_capability_review_evidence_hash="1" * 64,
        post_v4_capability_review_builder_hash="2" * 64,
        builder_contract_hash="3" * 64,
        operator_input=value,
        limitations=SANDBOX_PROFILE_LIMITATIONS,
    )


def test_valid_profile_authorizes_only_sandbox_implementation_and_charter() -> None:
    value = BinanceSpotTestnetSandboxInput.model_validate(valid_input_payload())
    profile = profile_for(value)

    assert [item.gate_id for item in profile.gate_results] == (
        SANDBOX_PROFILE_GATE_IDS
    )
    assert all(item.status == "PASS" for item in profile.gate_results)
    assert profile.decision == SANDBOX_PROFILE_PASS_DECISION
    assert profile.sandbox_adapter_implementation_authorized is True
    assert profile.successor_charter_design_authorized is True
    assert profile.testnet_network_requests_authorized is True
    assert profile.testnet_virtual_order_entry_authorized is True
    assert profile.sandbox_qualified is False
    assert profile.creates_sandbox_qualification is False
    assert profile.successor_alpha_discovery_authorized is False
    assert profile.return_testing_authorized is False
    assert profile.creates_candidate is False
    assert profile.creates_paper_eligibility is False
    assert profile.production_account_authorized is False
    assert profile.production_api_authorized is False
    assert profile.creates_live_eligibility is False
    assert profile.real_capital_authorized is False
    assert audit_binance_spot_testnet_sandbox_profile(profile)


@pytest.mark.parametrize(
    ("field", "value", "failed_gate"),
    [
        (
            "testnet_monthly_reset_behavior_acknowledged",
            False,
            "TESTNET_LIMITATIONS_ACKNOWLEDGED",
        ),
        (
            "maximum_per_trade_loss",
            "0.51",
            "SIMULATED_RISK_LIMITS_PROTECTIVE",
        ),
        (
            "maximum_daily_loss",
            "1.01",
            "SIMULATED_RISK_LIMITS_PROTECTIVE",
        ),
        (
            "maximum_total_loss",
            "10.01",
            "SIMULATED_RISK_LIMITS_PROTECTIVE",
        ),
    ],
)
def test_unsafe_sandbox_input_blocks_authority(
    field: str,
    value: object,
    failed_gate: str,
) -> None:
    payload = valid_input_payload()
    payload[field] = value
    profile = profile_for(BinanceSpotTestnetSandboxInput.model_validate(payload))

    assert profile.sandbox_adapter_implementation_authorized is False
    assert profile.testnet_virtual_order_entry_authorized is False
    assert failed_gate in profile.failed_gate_ids


def test_profile_rejects_symbol_expansion_and_production_authority() -> None:
    symbol_payload = valid_input_payload()
    symbol_payload["permitted_symbols"] = ["BTCUSDT", "ETHUSDT"]
    production_payload = valid_input_payload()
    production_payload["production_api_authorized"] = True

    with pytest.raises(ValidationError, match="exactly BTCUSDT"):
        BinanceSpotTestnetSandboxInput.model_validate(symbol_payload)
    with pytest.raises(ValidationError, match="Input should be False"):
        BinanceSpotTestnetSandboxInput.model_validate(production_payload)


def test_profile_rejects_credential_material() -> None:
    payload = valid_input_payload()
    payload["access_attestation_reference"] = "api_key=must-not-be-recorded"

    with pytest.raises(ValidationError, match="credential material"):
        BinanceSpotTestnetSandboxInput.model_validate(payload)


def test_profile_detects_tampering() -> None:
    profile = profile_for(
        BinanceSpotTestnetSandboxInput.model_validate(valid_input_payload())
    )
    payload = profile.model_dump(mode="json")
    payload["maximum_total_loss_ratio"] = "0.05"

    with pytest.raises(ValidationError, match="derived ratios changed"):
        BinanceSpotTestnetSandboxProfile.model_validate(payload)


def test_cli_preflight_freeze_and_check_are_reproducible(
    tmp_path: Path,
) -> None:
    payload = valid_input_payload()
    payload["attested_at"] = NOW.isoformat()
    input_path = tmp_path / "sandbox-input.json"
    output_path = tmp_path / "sandbox-profile.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    command = [
        sys.executable,
        "scripts/freeze_binance_spot_testnet_profile.py",
    ]

    preflight = subprocess.run(
        [*command, "--preflight", "--input", str(input_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    freeze = subprocess.run(
        [
            *command,
            "--freeze",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    check = subprocess.run(
        [*command, "--check", "--output", str(output_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert preflight.returncode == 0, preflight.stderr
    assert "adapter_implementation=True" in preflight.stdout
    assert "sandbox_qualified=False" in preflight.stdout
    assert freeze.returncode == 0, freeze.stderr
    assert output_path.exists()
    assert check.returncode == 0, check.stderr
    assert "PASS decision=" in check.stdout
