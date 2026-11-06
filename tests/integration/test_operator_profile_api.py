from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aurex.api.app import create_app
from aurex.api.dependencies import get_db
from aurex.api.routes import operator_profile as operator_profile_route
from aurex.db.base import Base


@pytest.fixture()
def client() -> Generator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = create_app()

    def override_get_db() -> Generator[Session]:
        with session_factory() as db_session:
            yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def valid_operator_payload() -> dict:
    return {
        "schema_version": "aurex-post-v4-operator-access-input-v1",
        "attested_at": "2026-07-29T11:00:00+00:00",
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


def test_operator_profile_status_and_template_are_no_store(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)

    status_response = client.get("/operator-profile/status")
    template_response = client.get("/operator-profile/template")

    assert status_response.status_code == 200
    assert status_response.headers["cache-control"] == "no-store"
    assert status_response.json()["workflow_status"] == "INPUT_REQUIRED"
    assert status_response.json()["artifact_exists"] is False
    assert status_response.json()["live_trading_authorized"] is False

    assert template_response.status_code == 200
    assert template_response.headers["cache-control"] == "no-store"
    template = template_response.json()
    assert template["writes_performed"] is False
    assert template["maximum_per_trade_loss_ratio"] == "0.005"
    assert template["maximum_daily_loss_ratio"] == "0.01"
    assert template["maximum_total_loss_ratio"] == "0.10"
    assert len(template["gate_ids"]) == 9
    assert not output.exists()


def test_operator_profile_preflight_passes_without_writing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)

    first = client.post(
        "/operator-profile/preflight",
        json=valid_operator_payload(),
    )
    second = client.post(
        "/operator-profile/preflight",
        json=valid_operator_payload(),
    )

    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    result = first.json()
    assert result["status"] == "PASS"
    assert result["passed_gate_count"] == result["total_gate_count"] == 9
    assert result["next_action"] == "RUN_INDEPENDENT_CLI_FREEZE"
    assert result["writes_performed"] is False
    assert result["successor_charter_design_authorized"] is True
    assert result["successor_alpha_discovery_authorized"] is False
    assert result["network_requests_authorized"] is False
    assert result["return_testing_authorized"] is False
    assert result["creates_paper_eligibility"] is False
    assert result["creates_live_eligibility"] is False
    assert second.json()["profile_evidence_hash"] == result["profile_evidence_hash"]
    assert not output.exists()


def test_operator_profile_preflight_preserves_failed_gates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)
    payload = valid_operator_payload()
    payload["maximum_per_trade_loss"] = "6"

    response = client.post("/operator-profile/preflight", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "BLOCKED"
    assert result["decision"] == "BLOCK_SUCCESSOR_DISCOVERY"
    assert "LOSS_LIMITS_CAPITAL_PROTECTIVE" in result["failed_gate_ids"]
    assert result["next_action"] == "CORRECT_OPERATOR_INPUT"
    assert not output.exists()


def test_operator_profile_validation_never_echoes_rejected_secret(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)
    payload = valid_operator_payload()
    secret = "api_key=must-never-be-echoed"
    payload["product_access_evidence_reference"] = secret

    response = client.post("/operator-profile/preflight", json=payload)

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "credential material" in response.text
    assert secret not in response.text
    assert not output.exists()


def test_operator_profile_rejects_account_number_and_oversized_input(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)
    payload = valid_operator_payload()
    account_number = "1234567890123456"
    payload["account_identifier_alias"] = account_number

    account_response = client.post("/operator-profile/preflight", json=payload)
    oversized_response = client.post(
        "/operator-profile/preflight",
        content=b"{" + (b"x" * 65_536) + b"}",
        headers={"content-type": "application/json"},
    )

    assert account_response.status_code == 400
    assert "must not contain an account number" in account_response.text
    assert account_number not in account_response.text
    assert oversized_response.status_code == 413
    assert oversized_response.headers["cache-control"] == "no-store"
    assert not output.exists()


def test_operator_profile_status_reports_tampered_artifact_without_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "operator-profile.json"
    output.write_text('{"operator_input":{"api_key":"not-returned"}}', encoding="utf-8")
    monkeypatch.setattr(operator_profile_route, "OUTPUT_PATH", output)

    response = client.get("/operator-profile/status")

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "FROZEN_INVALID"
    assert response.json()["artifact_verified"] is False
    assert "api_key" not in response.text
