from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.strategy_factory_readiness import (
    READINESS_PASS_DECISION,
    StrategyFactoryReadinessProtocol,
    StrategyFactoryReadinessResult,
    audit_readiness_protocol,
    audit_readiness_result,
)
from scripts.run_strategy_factory_readiness import build_result

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = (
    ROOT / "data/evidence/aurex_strategy_factory_readiness_protocol_v1.json"
)


def canonical_protocol() -> StrategyFactoryReadinessProtocol:
    return StrategyFactoryReadinessProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def test_canonical_readiness_protocol_is_frozen_before_scoring():
    protocol = canonical_protocol()
    assert audit_readiness_protocol(protocol)
    assert protocol.protocol_evidence_hash == (
        "bf0392dfe2876bbb0a8b798880651ab89af887e1e16dd70e4631c2ddacc73b90"
    )
    assert len(protocol.gate_specs) == 15
    assert protocol.no_strategy_design_permitted
    assert protocol.no_market_outcome_access_permitted
    assert protocol.no_paper_campaign_permitted
    assert protocol.no_testnet_strategy_order_permitted
    assert protocol.no_production_or_live_permitted


def test_current_readiness_scoring_is_research_ready_and_no_execution_authority():
    result = build_result(
        protocol=canonical_protocol(),
        evaluated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )
    statuses = {item.gate_id: item.status for item in result.gate_results}
    assert result.passed_gate_count == 14
    assert result.partial_gate_count == 1
    assert result.failed_gate_count == 0
    assert statuses["UNIVERSAL_COST_STRESS_AND_INFERENCE"] == "PASS"
    assert statuses["CANDIDATE_LIFECYCLE_AND_RETIREMENT"] == "PASS"
    assert statuses["AUTHENTICATED_SIGNAL_DELIVERY"] == "PARTIAL"
    assert statuses["OPERATOR_READINESS_VISIBILITY"] == "PASS"
    operator_gate = next(
        item for item in result.gate_results if item.gate_id == "OPERATOR_READINESS_VISIBILITY"
    )
    assert {
        "src/aurex/db/backup.py",
        "scripts/manage_database_backup.py",
        "scripts/rehearse_native_database_upgrade.py",
        "tests/integration/test_database_backup.py",
        "src/aurex/api/private_runtime.py",
        "scripts/run_private_operator.py",
        "scripts/rehearse_private_operator.py",
        "tests/integration/test_private_runtime.py",
        "src/aurex/signal_gateway/native_lifecycle.py",
        "tests/integration/test_native_lifecycle.py",
        "tests/fixtures/native_managed_wait_child.py",
        "tests/fixtures/private_native_wait_service.py",
        "src/aurex/db/recovery_bundle.py",
        "src/aurex/db/recovery_environment.py",
        "scripts/manage_recovery_bundle.py",
        "scripts/manage_recovery_environment.py",
        "scripts/rehearse_recovered_application.py",
        "tests/integration/test_recovery_bundle.py",
        "tests/unit/test_recovery_environment.py",
    } <= {item.path for item in operator_gate.source_evidence}
    data_gate = next(
        item for item in result.gate_results if item.gate_id == "MARKET_DATA_LINEAGE_AND_QUALITY"
    )
    data_sources = {item.path for item in data_gate.source_evidence}
    assert "src/aurex/signal_gateway/native_bars.py" in data_sources
    assert "src/aurex/signal_gateway/native_market_data.py" in data_sources
    assert "scripts/check_native_public_data.py" in data_sources
    assert "tests/unit/test_native_market_data.py" in data_sources
    assert "tests/unit/test_native_closed_bars.py" in data_sources
    assert "tests/integration/test_native_closed_bar_intake.py" in data_sources
    paper_gate = next(
        item for item in result.gate_results if item.gate_id == "EVIDENCE_GRADE_PAPER_EXECUTION"
    )
    paper_sources = {item.path for item in paper_gate.source_evidence}
    assert "src/aurex/signal_gateway/native_processing.py" in paper_sources
    assert "src/aurex/signal_gateway/native_continuation.py" in paper_sources
    assert "src/aurex/signal_gateway/native_recovery.py" in paper_sources
    assert "src/aurex/signal_gateway/native_source.py" in paper_sources
    assert "src/aurex/signal_gateway/native_observation.py" in paper_sources
    assert "src/aurex/signal_gateway/native_exits.py" in paper_sources
    assert "src/aurex/signal_gateway/native_jam_features.py" in paper_sources
    assert "tests/unit/test_native_jam_features.py" in paper_sources
    assert "src/aurex/signal_gateway/native_jam_history.py" in paper_sources
    assert "tests/integration/test_native_jam_history.py" in paper_sources
    assert "src/aurex/signal_gateway/native_jam_decisions.py" in paper_sources
    assert "tests/integration/test_native_jam_decisions.py" in paper_sources
    assert "src/aurex/signal_gateway/native_jam_runtime.py" in paper_sources
    assert "tests/integration/test_native_jam_runtime.py" in paper_sources
    assert "src/aurex/signal_gateway/native_supervision.py" in paper_sources
    assert "scripts/run_native_supervisor.py" in paper_sources
    assert "scripts/audit_native_supervisor.py" in paper_sources
    assert "tests/integration/test_native_supervision.py" in paper_sources
    assert "tests/integration/test_native_online_exits.py" in paper_sources
    assert "tests/integration/test_native_observation.py" in paper_sources
    assert "tests/integration/test_native_source_binding.py" in paper_sources
    assert "tests/integration/test_native_recovery.py" in paper_sources
    assert "src/aurex/live_deployment/service.py" in paper_sources
    assert "tests/integration/test_native_continuation_processing.py" in paper_sources
    assert "tests/unit/test_native_continuation.py" in paper_sources
    assert "tests/integration/test_native_bar_processing.py" in paper_sources
    assert "infra/alembic/versions/20260930_0030_native_bar_outcomes.py" in paper_sources
    assert "infra/alembic/versions/20261004_0031_native_history_seed.py" in paper_sources
    assert "tests/integration/test_native_retained_history.py" in paper_sources
    assert result.research_blocking_gate_ids == []
    assert result.strategy_research_ready
    assert result.decision == READINESS_PASS_DECISION
    assert not result.paper_operation_ready
    assert not result.sandbox_strategy_use_ready
    assert not result.production_ready
    assert not result.live_ready
    assert result.qualified_strategy_count == 0
    assert result.real_market_values_opened == 0
    assert result.strategy_candidates_created == 0
    assert result.strategy_executions == 0
    assert result.orders_submitted == 0
    assert result.real_net_profit_usd == "0"
    assert audit_readiness_result(result)


def test_readiness_result_rejects_false_promotion_and_hash_tamper():
    result = build_result(
        protocol=canonical_protocol(),
        evaluated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )
    false_promotion = result.model_dump()
    false_promotion["paper_operation_ready"] = True
    with pytest.raises(ValidationError):
        StrategyFactoryReadinessResult.model_validate(false_promotion)

    tampered = result.model_dump()
    tampered["limitations"] = ["Profit is guaranteed."]
    with pytest.raises(ValidationError, match="result hash changed"):
        StrategyFactoryReadinessResult.model_validate(tampered)
