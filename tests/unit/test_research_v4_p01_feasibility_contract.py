from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (
    V4P01_REQUIRED_GATE_IDS,
    V4P01FeasibilityContract,
    audit_v4_p01_feasibility_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v4_p01_feasibility_contract import (
    authoritative_contract,
    load_inputs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = PROJECT_ROOT / "data" / "evidence"
FROZEN_AT = datetime(2026, 7, 29, 7, 0, tzinfo=UTC)


def frozen_contract() -> V4P01FeasibilityContract:
    charter, register = load_inputs(
        EVIDENCE / "v4_mechanism_discovery_charter_v1.json",
        EVIDENCE / "v4_mechanism_proposal_register_v1.json",
    )
    return authoritative_contract(
        frozen_at=FROZEN_AT,
        charter=charter,
        register=register,
    )


def test_v4p01_contract_binds_charter_register_and_exact_proposal() -> None:
    charter, register = load_inputs(
        EVIDENCE / "v4_mechanism_discovery_charter_v1.json",
        EVIDENCE / "v4_mechanism_proposal_register_v1.json",
    )
    contract = authoritative_contract(
        frozen_at=FROZEN_AT,
        charter=charter,
        register=register,
    )

    assert (
        contract.discovery_charter_evidence_hash
        == charter.charter_evidence_hash
    )
    assert (
        contract.proposal_register_evidence_hash
        == register.register_evidence_hash
    )
    assert contract.proposal_evidence_hash == universe_evidence_hash(
        register.proposals[0].model_dump()
    )
    assert contract.proposal_id == (
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
    )
    assert audit_v4_p01_feasibility_contract(contract)


def test_v4p01_contract_freezes_exact_eth_btc_venue_identity() -> None:
    contract = frozen_contract()

    assert contract.exact_common_product == "ETH_BTC"
    assert contract.venue_product_bindings == {
        "binance": "ethbtc",
        "coinbase": "ETH-BTC",
    }
    assert contract.development_start.isoformat() == (
        "2023-01-01T00:00:00+00:00"
    )
    assert contract.development_end.isoformat() == (
        "2025-01-01T00:00:00+00:00"
    )


def test_v4p01_contract_freezes_metadata_before_six_payload_requests() -> None:
    requests = frozen_contract().requests

    assert [request.sequence for request in requests] == list(range(1, 9))
    assert [request.phase for request in requests[:2]] == [
        "METADATA_CENSUS",
        "METADATA_CENSUS",
    ]
    assert all(
        request.phase == "PAYLOAD_SCHEMA_PILOT"
        for request in requests[2:]
    )
    assert [request.exchange_id for request in requests] == [
        "binance",
        "coinbase",
        "binance",
        "coinbase",
        "binance",
        "coinbase",
        "binance",
        "coinbase",
    ]

    sample_times = [
        request.sample_at.isoformat()
        for request in requests[2:]
        if request.sample_at is not None
    ]
    assert sample_times == [
        "2023-01-01T00:00:00+00:00",
        "2023-01-01T00:00:00+00:00",
        "2023-12-01T12:00:00+00:00",
        "2023-12-01T12:00:00+00:00",
        "2024-12-01T23:59:00+00:00",
        "2024-12-01T23:59:00+00:00",
    ]

    for request in requests[2:]:
        query = parse_qs(urlparse(request.url).query)
        assert query["offset"] == [str(request.offset_minutes)]
        assert query["from"] == [request.sample_at.date().isoformat()]


def test_v4p01_contract_freezes_crash_safe_zero_retry_budgets() -> None:
    contract = frozen_contract()
    budget = contract.transport_budget

    assert budget.metadata_unique_url_budget == 2
    assert budget.payload_unique_url_budget == 6
    assert budget.total_unique_url_budget == 8
    assert budget.total_attempt_budget == 8
    assert budget.total_retry_budget == 0
    assert budget.maximum_concurrency == 1
    assert budget.total_response_byte_budget == 117_440_512
    assert budget.storage_budget_bytes == 268_435_456
    assert budget.protocol_wall_clock_budget_seconds == 1200
    assert budget.automatic_retry_permitted is False
    assert budget.range_or_resume_permitted is False
    assert budget.budget_expansion_after_observation_permitted is False

    assert all(request.maximum_attempts == 1 for request in contract.requests)
    assert all(request.maximum_retries == 0 for request in contract.requests)
    assert all(
        request.range_or_resume_permitted is False
        for request in contract.requests
    )


def test_v4p01_contract_permits_schema_but_not_market_values_or_outcomes() -> None:
    contract = frozen_contract()

    assert contract.authorizes_network_requests is True
    assert contract.authorized_network_scope == (
        "EXACT_EIGHT_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    )
    assert contract.credentials_permitted is False
    assert contract.private_endpoints_permitted is False
    assert contract.market_numeric_value_inspection_permitted is False
    assert contract.signal_trade_pnl_or_return_calculation_permitted is False
    assert contract.selects_primary is False
    assert contract.creates_candidate is False
    assert contract.return_metrics_calculated == []
    assert "schema_key_presence" in contract.permitted_observation_fields
    assert "bid_price_value" in contract.prohibited_parsed_fields
    assert "return_metric" in contract.prohibited_parsed_fields
    assert all(
        request.market_value_parsing_permitted is False
        for request in contract.requests
    )


def test_v4p01_contract_freezes_all_hard_execution_gates() -> None:
    gates = frozen_contract().execution_gates

    assert [gate.gate_id for gate in gates] == V4P01_REQUIRED_GATE_IDS
    assert all(
        gate.failure_action == "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
        for gate in gates
    )
    assert all(gate.conservative_override_permitted is False for gate in gates)
    assert all(
        gate.observed_status == "NOT_OBSERVED_PRE_EXECUTION"
        for gate in gates
    )
    assert "POINT_IN_TIME_FEES_AND_FEE_CURRENCY" in {
        gate.gate_id for gate in gates
    }
    assert "DETERMINISTIC_TWO_LEG_STATE_MACHINE" in {
        gate.gate_id for gate in gates
    }


def test_v4p01_contract_refuses_url_or_retry_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["requests"][2]["url"] = (
        "https://example.com/v1/data-feeds/binance"
    )
    payload["requests"][2]["maximum_retries"] = 1
    payload["contract_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P01FeasibilityContract.model_validate(payload)


def test_v4p01_contract_refuses_pair_gate_or_permission_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["venue_product_bindings"]["coinbase"] = "ETH-USD"
    payload["execution_gates"] = payload["execution_gates"][:-1]
    payload["market_numeric_value_inspection_permitted"] = True
    payload["contract_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P01FeasibilityContract.model_validate(payload)


def test_v4p01_contract_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_p01_feasibility_contract.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "V4P01" in completed.stdout
