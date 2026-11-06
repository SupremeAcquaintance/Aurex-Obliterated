from dataclasses import replace

import pytest

from aurex.strategy_engine.registry import (
    REGISTERED_STRATEGIES,
    STRATEGY_FACTORY_CONTRACT_VERSION,
    StrategyLifecycleStatus,
)


@pytest.fixture()
def active_trend_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Permit legacy pipeline mechanics tests without changing production truth."""
    strategy = "trend_pullback_v1"
    definition = REGISTERED_STRATEGIES[strategy]
    monkeypatch.setitem(
        REGISTERED_STRATEGIES,
        strategy,
        replace(
            definition,
            lifecycle_status=StrategyLifecycleStatus.ACTIVE,
            lifecycle_reason="Integration-test pipeline fixture only.",
            qualification_contract_version=STRATEGY_FACTORY_CONTRACT_VERSION,
            qualification_evidence_hash="f" * 64,
        ),
    )
