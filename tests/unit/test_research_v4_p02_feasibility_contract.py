from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v4_p02_feasibility_contract import (
    V4P02_DATASET_PRODUCTS,
    V4P02_REQUIRED_GATE_IDS,
    V4P02_SAMPLE_DATES,
    V4P02FeasibilityContract,
    audit_v4_p02_feasibility_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v4_p02_feasibility_contract import (
    authoritative_contract,
    load_inputs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = PROJECT_ROOT / "data" / "evidence"
FROZEN_AT = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def frozen_contract() -> V4P02FeasibilityContract:
    charter, register = load_inputs(
        EVIDENCE / "v4_mechanism_discovery_charter_v1.json",
        EVIDENCE / "v4_mechanism_proposal_register_v1.json",
    )
    return authoritative_contract(
        frozen_at=FROZEN_AT,
        charter=charter,
        register=register,
    )


def test_v4p02_contract_binds_exact_charter_register_and_proposal() -> None:
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
        register.proposals[1].model_dump()
    )
    assert contract.proposal_id == (
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
    )
    assert audit_v4_p02_feasibility_contract(contract)


def test_v4p02_contract_freezes_one_metadata_get_then_27_heads() -> None:
    requests = frozen_contract().requests

    assert len(requests) == 28
    assert [item.sequence for item in requests] == list(range(1, 29))
    assert requests[0].method == "GET"
    assert requests[0].phase == "EXCHANGE_METADATA"
    assert requests[0].url == "https://api.tardis.dev/v1/exchanges/deribit"
    assert all(item.method == "HEAD" for item in requests[1:])
    assert all(
        item.phase == "DATASET_HEADER_CENSUS" for item in requests[1:]
    )
    assert all(
        item.expected_host == "datasets.tardis.dev" for item in requests[1:]
    )
    assert all(
        urlparse(item.url).path.endswith(".csv.gz") for item in requests[1:]
    )


def test_v4p02_contract_freezes_complete_date_product_matrix() -> None:
    contract = frozen_contract()
    matrix = [
        (
            item.dataset_data_type,
            item.dataset_symbol,
            item.dataset_role,
            item.sample_date,
        )
        for item in contract.requests[1:]
    ]
    expected = [
        (data_type, symbol, role, sample_date)
        for sample_date in V4P02_SAMPLE_DATES
        for data_type, symbol, role in V4P02_DATASET_PRODUCTS
    ]

    assert matrix == expected
    assert contract.option_currency == "BTC"
    assert contract.grouped_option_symbol == "OPTIONS"
    assert contract.hedge_instrument == "BTC-PERPETUAL"


def test_v4p02_contract_heads_are_zero_body_zero_retry_and_safe_redirect() -> None:
    contract = frozen_contract()

    assert all(item.maximum_attempts == 1 for item in contract.requests)
    assert all(item.maximum_retries == 0 for item in contract.requests)
    assert contract.requests[0].redirects_permitted is False
    assert contract.requests[0].maximum_redirects == 0
    assert all(item.redirects_permitted is True for item in contract.requests[1:])
    assert all(item.maximum_redirects == 3 for item in contract.requests[1:])
    assert all(
        item.range_or_resume_permitted is False for item in contract.requests
    )
    assert all(
        item.maximum_response_body_bytes == 0 for item in contract.requests[1:]
    )
    assert contract.dataset_payload_gets_permitted is False
    assert contract.raw_replay_requests_permitted is False
    assert contract.deribit_api_requests_permitted is False


def test_v4p02_contract_freezes_transport_and_projection_budgets() -> None:
    budget = frozen_contract().transport_budget

    assert budget.metadata_get_budget == 1
    assert budget.dataset_head_budget == 27
    assert budget.total_unique_url_budget == 28
    assert budget.total_attempt_budget == 28
    assert budget.total_retry_budget == 0
    assert budget.dataset_redirect_budget == 81
    assert budget.total_http_hop_budget == 109
    assert budget.maximum_concurrency == 1
    assert budget.total_response_body_byte_budget == 8_388_608
    assert budget.evidence_storage_budget_bytes == 33_554_432
    assert budget.projected_dataset_storage_ceiling_bytes == 2_199_023_255_552
    assert budget.protocol_wall_clock_budget_seconds == 1260


def test_v4p02_contract_freezes_all_hard_source_and_execution_gates() -> None:
    gates = frozen_contract().execution_gates

    assert [item.gate_id for item in gates] == V4P02_REQUIRED_GATE_IDS
    assert all(
        item.failure_action == "REJECT_V4P02_BEFORE_PRIMARY_SELECTION"
        for item in gates
    )
    assert all(item.conservative_override_permitted is False for item in gates)
    assert "POINT_IN_TIME_FEES_CAPS_AND_DELIVERY_FEES" in {
        item.gate_id for item in gates
    }
    assert "DETERMINISTIC_MULTI_LEG_ORDER_LIFECYCLE" in {
        item.gate_id for item in gates
    }
    assert "TAIL_LOSS_CAPACITY_CONCENTRATION_AND_KILL_SWITCHES" in {
        item.gate_id for item in gates
    }


def test_v4p02_contract_permits_no_market_values_or_outcomes() -> None:
    contract = frozen_contract()

    assert contract.authorizes_network_requests is True
    assert contract.market_numeric_value_inspection_permitted is False
    assert contract.signal_trade_pnl_or_return_calculation_permitted is False
    assert contract.strategy_outcome_fields_inspected == []
    assert contract.return_metrics_calculated == []
    assert "bid_price_value" in contract.prohibited_parsed_fields
    assert "implied_volatility_value" in contract.prohibited_parsed_fields
    assert "margin_amount_value" in contract.prohibited_parsed_fields
    assert contract.selects_primary is False
    assert contract.creates_candidate is False
    assert contract.creates_paper_eligibility is False
    assert contract.creates_sandbox_eligibility is False
    assert contract.creates_live_eligibility is False


def test_v4p02_contract_rejects_url_method_or_payload_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["requests"][1]["method"] = "GET"
    payload["requests"][1]["url"] = (
        "https://example.com/v1/deribit/options_chain.csv.gz"
    )
    payload["dataset_payload_gets_permitted"] = True
    payload["contract_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P02FeasibilityContract.model_validate(payload)


def test_v4p02_contract_rejects_gate_or_permission_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["execution_gates"] = payload["execution_gates"][:-1]
    payload["market_numeric_value_inspection_permitted"] = True
    payload["selects_primary"] = True
    payload["contract_evidence_hash"] = "f" * 64

    with pytest.raises(ValidationError):
        V4P02FeasibilityContract.model_validate(payload)


def test_v4p02_contract_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v4_p02_feasibility_contract.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "pre-network V4P02 Deribit metadata" in completed.stdout
