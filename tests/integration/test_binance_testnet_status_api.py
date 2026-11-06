import pytest
from fastapi.testclient import TestClient

from aurex.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_binance_testnet_status_is_read_only_and_live_disabled(client: TestClient) -> None:
    response = client.get("/broker/binance-testnet/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_status"] == "SANDBOX_QUALIFIED"
    assert payload["production_authority"] is False
    assert payload["live_authority"] is False
    assert payload["sandbox_qualified"] is True
    assert payload["fill_fee_contract_frozen"] is True
    assert payload["fill_fee_campaign_recorded"] is True
    assert payload["fill_fee_reconciliation_verified"] is True
    assert payload["user_stream_contract_frozen"] is True
    assert payload["user_stream_contract_sha256"] == (
        "ddf06d9d596812c9dcb45c4c6654e8e50a0b5a3ae2928b15fdbf487fad2f8c2d"
    )
    assert payload["user_stream_campaign_recorded"] is True
    assert payload["user_stream_reconciliation_verified"] is True
    assert payload["restart_soak_contract_frozen"] is True
    assert payload["restart_soak_contract_sha256"] == (
        "5e5f1f22a014fa087c44a13341f862fe6d64ea441db280fabae677bf2af820d8"
    )
    assert payload["restart_soak_campaign_recorded"] is True
    assert payload["restart_soak_reconciliation_verified"] is True
