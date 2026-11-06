import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.strategy_factory_contract import (
    StrategyFactoryContract,
    StrategyFactoryContractSource,
    audit_strategy_factory_contract,
    build_strategy_factory_contract,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "data/evidence/aurex_strategy_factory_contract_v1.json"


def source() -> StrategyFactoryContractSource:
    return StrategyFactoryContractSource(
        path="src/aurex/backtest_engine/service.py",
        file_sha256="a" * 64,
        byte_count=1,
    )


def test_contract_grants_no_execution_authority() -> None:
    contract = build_strategy_factory_contract(
        frozen_at=datetime(2026, 8, 6, tzinfo=UTC),
        source_evidence=[source()],
    )

    assert audit_strategy_factory_contract(contract) is True
    assert contract.required_partition_order == ["DEVELOPMENT", "VALIDATION", "HOLDOUT"]
    assert contract.paper_authority_granted is False
    assert contract.live_authority_granted is False
    assert contract.strategy_candidates_created == 0


def test_contract_rejects_requirement_tampering() -> None:
    contract = build_strategy_factory_contract(
        frozen_at=datetime(2026, 8, 6, tzinfo=UTC),
        source_evidence=[source()],
    )
    payload = contract.model_dump()
    payload["default_acceptance_criteria"]["require_cost_stress"] = False

    with pytest.raises(ValidationError, match="universal requirements changed"):
        StrategyFactoryContract.model_validate(payload)


def test_frozen_contract_artifact_validates() -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    contract = StrategyFactoryContract.model_validate(payload)

    assert audit_strategy_factory_contract(contract) is True
