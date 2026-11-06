from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aurex.api.app import create_app
from aurex.api.routes import sandbox_profile as sandbox_profile_route


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_sandbox_profile_template_and_status_are_no_store(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "missing-sandbox-profile.json"
    monkeypatch.setattr(sandbox_profile_route, "OUTPUT_PATH", output)

    status_response = client.get("/sandbox-profile/status")
    template_response = client.get("/sandbox-profile/template")

    assert status_response.status_code == 200
    assert status_response.headers["cache-control"] == "no-store"
    assert status_response.json()["workflow_status"] == "INPUT_REQUIRED"
    assert status_response.json()["creates_live_eligibility"] is False
    assert status_response.json()["real_capital_authorized"] is False
    assert template_response.status_code == 200
    assert template_response.headers["cache-control"] == "no-store"
    assert len(template_response.json()["gate_ids"]) == 9
    assert template_response.json()["writes_performed"] is False
    assert template_response.json()["input_template"]["permitted_symbols"] == [
        "BTCUSDT"
    ]


def test_sandbox_profile_preflight_passes_without_writing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(sandbox_profile_route, "OUTPUT_PATH", output)
    payload = client.get("/sandbox-profile/template").json()["input_template"]

    response = client.post("/sandbox-profile/preflight", json=payload)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["status"] == "PASS"
    assert result["passed_gate_count"] == 9
    assert result["failed_gate_ids"] == []
    assert result["sandbox_adapter_implementation_authorized"] is True
    assert result["successor_charter_design_authorized"] is True
    assert result["testnet_network_requests_authorized"] is True
    assert result["testnet_virtual_order_entry_authorized"] is True
    assert result["sandbox_qualified"] is False
    assert result["creates_live_eligibility"] is False
    assert result["real_capital_authorized"] is False
    assert result["writes_performed"] is False
    assert result["next_action"] == "RUN_INDEPENDENT_CLI_FREEZE"
    assert not output.exists()


def test_sandbox_profile_preflight_blocks_unsafe_limits_without_writing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(sandbox_profile_route, "OUTPUT_PATH", output)
    payload = client.get("/sandbox-profile/template").json()["input_template"]
    payload["maximum_per_trade_loss"] = "1"

    response = client.post("/sandbox-profile/preflight", json=payload)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "BLOCKED"
    assert "SIMULATED_RISK_LIMITS_PROTECTIVE" in result["failed_gate_ids"]
    assert result["testnet_virtual_order_entry_authorized"] is False
    assert result["creates_live_eligibility"] is False
    assert not output.exists()


def test_sandbox_profile_rejects_secret_without_echoing_it(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setattr(sandbox_profile_route, "OUTPUT_PATH", output)
    payload = client.get("/sandbox-profile/template").json()["input_template"]
    secret = "api_key=must-not-appear-in-response"
    payload["access_attestation_reference"] = secret

    response = client.post(
        "/sandbox-profile/preflight",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert "credential material" in response.text
    assert secret not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not output.exists()


def test_sandbox_profile_status_hides_tampered_artifact_details(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "sandbox-profile.json"
    output.write_text('{"api_key":"not-returned"}', encoding="utf-8")
    monkeypatch.setattr(sandbox_profile_route, "OUTPUT_PATH", output)

    response = client.get("/sandbox-profile/status")

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "FROZEN_INVALID"
    assert response.json()["artifact_verified"] is False
    assert "api_key" not in response.text
