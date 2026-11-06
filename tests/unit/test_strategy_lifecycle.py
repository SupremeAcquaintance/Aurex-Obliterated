from dataclasses import replace

from aurex.strategy_engine.registry import (
    REGISTERED_STRATEGIES,
    STRATEGY_FACTORY_CONTRACT_VERSION,
    StrategyLifecycleStatus,
    strategy_lifecycle_allows_enable,
    strategy_lifecycle_reason,
    strategy_lifecycle_status,
)


def test_current_registry_contains_no_enable_eligible_strategy() -> None:
    assert REGISTERED_STRATEGIES
    assert all(
        definition.lifecycle_status != StrategyLifecycleStatus.ACTIVE
        for definition in REGISTERED_STRATEGIES.values()
    )
    assert all(
        strategy_lifecycle_allows_enable(strategy) is False
        for strategy in REGISTERED_STRATEGIES
    )


def test_unknown_strategy_fails_closed() -> None:
    assert strategy_lifecycle_status("unknown_v1") == StrategyLifecycleStatus.UNREGISTERED
    assert strategy_lifecycle_allows_enable("unknown_v1") is False
    assert strategy_lifecycle_reason("unknown_v1") == (
        "Unregistered strategies cannot be enabled."
    )


def test_only_active_lifecycle_allows_enable(monkeypatch) -> None:
    strategy = "range_mean_reversion_v1"
    definition = REGISTERED_STRATEGIES[strategy]
    monkeypatch.setitem(
        REGISTERED_STRATEGIES,
        strategy,
        replace(
            definition,
            lifecycle_status=StrategyLifecycleStatus.ACTIVE,
            lifecycle_reason="Test-only active lifecycle.",
            qualification_contract_version=STRATEGY_FACTORY_CONTRACT_VERSION,
            qualification_evidence_hash="f" * 64,
        ),
    )

    assert strategy_lifecycle_allows_enable(strategy) is True
