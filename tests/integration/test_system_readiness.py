from fastapi.testclient import TestClient

from aurex.api.app import create_app


def test_system_readiness_exposes_canonical_research_truth() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/system/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == (
        "S5_MEASUREMENTS_AUDITED_RESEARCH_ONLY"
    )
    assert body["strategy_research_ready"] is True
    assert body["source_integrity_verified"] is True
    assert body["active_research_checkpoint"] == (
        "S5_MEASUREMENTS_AUDITED_RESEARCH_ONLY"
    )
    assert body["research_checkpoint_verified"] is True
    assert body["acquisition_preflight_ready"] is False
    assert body["acquisition_preflight_decision"] == ("BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK")
    assert body["acquisition_free_disk_bytes_observed"] == 48_036_913_152
    assert body["acquisition_required_free_disk_bytes"] == 120_000_000_000
    assert body["acquisition_additional_free_disk_bytes_required"] == 71_963_086_848
    assert body["passed_gate_count"] == 14
    assert body["partial_gate_count"] == 1
    assert body["failed_gate_count"] == 0
    assert body["research_blocking_gate_ids"] == []
    assert body["downstream_partial_gate_ids"] == ["AUTHENTICATED_SIGNAL_DELIVERY"]
    assert body["qualified_strategy_count"] == 0
    assert body["enable_eligible_strategy_count"] == 0
    assert body["paper_operation_ready"] is False
    assert body["sandbox_strategy_use_ready"] is False
    assert body["production_ready"] is False
    assert body["live_ready"] is False
    assert body["real_net_profit_usd"] == "0"
    assert body["next_action"] == (
        "RECONCILE_PLATFORM_READINESS_AND_EXECUTION_EVIDENCE"
    )
    assert all(strategy["enable_eligible"] is False for strategy in body["strategy_lifecycle"])


def test_readiness_blocks_when_latest_measurement_cannot_be_verified(monkeypatch) -> None:
    from aurex.api.routes import system

    monkeypatch.setattr(system, "verify_measurement_checkpoint", lambda root: False)
    response = system.strategy_factory_readiness()
    assert response.status == "STRATEGY_FACTORY_BLOCKED"
    assert not response.strategy_research_ready
    assert not response.research_checkpoint_verified
    assert response.active_research_checkpoint == "S5_MEASUREMENT_EVIDENCE_UNVERIFIED"
    assert not response.live_ready
