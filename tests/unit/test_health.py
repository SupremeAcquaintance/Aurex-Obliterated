from fastapi.testclient import TestClient

from aurex.api.app import create_app


def test_health_endpoint_reports_safe_stage_one_defaults() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Aurex",
        "environment": "local",
        "live_trading_enabled": False,
    }

