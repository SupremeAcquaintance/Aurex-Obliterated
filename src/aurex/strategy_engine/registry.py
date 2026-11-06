from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from aurex.domain.enums import Direction, MarketRegime

STRATEGY_FACTORY_CONTRACT_VERSION = "aurex-strategy-factory-contract-v1"


class StrategyLifecycleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    RETIRED = "RETIRED"
    QUARANTINED = "QUARANTINED"
    UNREGISTERED = "UNREGISTERED"


@dataclass(frozen=True)
class StrategyDefinition:
    strategy: str
    version: str
    display_name: str
    description: str
    allowed_regimes: tuple[MarketRegime, ...]
    default_risk_per_trade: Decimal
    default_minimum_reward_risk: Decimal
    default_max_open_positions: int
    pine_path: str
    docs_path: str
    lifecycle_status: StrategyLifecycleStatus
    lifecycle_reason: str
    qualification_contract_version: str | None = None
    qualification_evidence_hash: str | None = None
    default_enabled: bool = False

    def __post_init__(self) -> None:
        if self.default_enabled and self.lifecycle_status != StrategyLifecycleStatus.ACTIVE:
            raise ValueError("Only ACTIVE strategies may default to enabled")
        if self.lifecycle_status == StrategyLifecycleStatus.ACTIVE and (
            self.qualification_contract_version != STRATEGY_FACTORY_CONTRACT_VERSION
            or self.qualification_evidence_hash is None
            or len(self.qualification_evidence_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.qualification_evidence_hash
            )
        ):
            raise ValueError(
                "ACTIVE strategies require a hash-bound Aurex strategy-factory "
                "qualification"
            )


REGISTERED_STRATEGIES: dict[str, StrategyDefinition] = {
    "trend_pullback_v1": StrategyDefinition(
        strategy="trend_pullback_v1",
        version="1.3.0",
        display_name="Trend Pullback V1",
        description="Trades confirmed pullbacks only in directional trend regimes.",
        allowed_regimes=(MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN),
        default_risk_per_trade=Decimal("0.005"),
        default_minimum_reward_risk=Decimal("1.5"),
        default_max_open_positions=1,
        pine_path="pine/strategies/trend_pullback_v1.pine",
        docs_path="docs/pine/trend_pullback_v1.md",
        lifecycle_status=StrategyLifecycleStatus.RETIRED,
        lifecycle_reason=(
            "Version 1.3.0 failed the authoritative validation and is permanently "
            "ineligible for paper or live execution."
        ),
    ),
    "volatility_breakout_v1": StrategyDefinition(
        strategy="volatility_breakout_v1",
        version="1.1.0",
        display_name="Volatility Breakout V1",
        description="Trades breakouts after compression and volume confirmation.",
        allowed_regimes=(MarketRegime.LOW_VOLATILITY, MarketRegime.BREAKOUT_EXPANSION),
        default_risk_per_trade=Decimal("0.003"),
        default_minimum_reward_risk=Decimal("2.0"),
        default_max_open_positions=1,
        pine_path="pine/strategies/volatility_breakout_v1.pine",
        docs_path="docs/pine/volatility_breakout_v1.md",
        lifecycle_status=StrategyLifecycleStatus.RETIRED,
        lifecycle_reason=(
            "Version 1.1.0 failed diagnostic validation and is retired from advancement."
        ),
        default_enabled=False,
    ),
    "slow_breakout_spot_v1": StrategyDefinition(
        strategy="slow_breakout_spot_v1",
        version="1.0.0",
        display_name="Slow Breakout Spot V1",
        description=(
            "Trades long-only 4-hour channel breakouts with a slower channel exit."
        ),
        allowed_regimes=(MarketRegime.TRENDING_UP,),
        default_risk_per_trade=Decimal("0.0025"),
        default_minimum_reward_risk=Decimal("0"),
        default_max_open_positions=1,
        pine_path="pine/strategies/slow_breakout_spot_v1.pine",
        docs_path="docs/pine/slow_breakout_spot_v1.md",
        lifecycle_status=StrategyLifecycleStatus.RETIRED,
        lifecycle_reason=(
            "Version 1.0.0 failed its held-out cross-market decision and is retired."
        ),
        default_enabled=False,
    ),
    "range_mean_reversion_v1": StrategyDefinition(
        strategy="range_mean_reversion_v1",
        version="1.0.0",
        display_name="Range Mean Reversion V1",
        description="Trades rejected range extremes back toward the range midpoint.",
        allowed_regimes=(MarketRegime.RANGING,),
        default_risk_per_trade=Decimal("0.0025"),
        default_minimum_reward_risk=Decimal("1.2"),
        default_max_open_positions=1,
        pine_path="pine/strategies/range_mean_reversion_v1.pine",
        docs_path="docs/pine/range_mean_reversion_v1.md",
        lifecycle_status=StrategyLifecycleStatus.RESEARCH_ONLY,
        lifecycle_reason=(
            "Exploratory mechanism only; no frozen evidence package has qualified it."
        ),
    ),
    "jam_reversal_v1": StrategyDefinition(
        strategy="jam_reversal_v1",
        version="1.14.0",
        display_name="Jam Reversal V1",
        description="Trades confirmed two-candle Jam reversals after range sweeps.",
        allowed_regimes=(MarketRegime.BREAKOUT_EXPANSION,),
        default_risk_per_trade=Decimal("0.005"),
        default_minimum_reward_risk=Decimal("0.8"),
        default_max_open_positions=1,
        pine_path="pine/strategies/jam_reversal_v1.pine",
        docs_path="docs/pine/jam_reversal_v1.md",
        lifecycle_status=StrategyLifecycleStatus.QUARANTINED,
        lifecycle_reason=(
            "Legacy Jam lineage is not an execution-qualified strategy and remains "
            "quarantined from enablement."
        ),
        default_enabled=False,
    ),
    "jam_reversal_spot_v1": StrategyDefinition(
        strategy="jam_reversal_spot_v1",
        version="1.0.1",
        display_name="Jam Reversal Spot V1",
        description=(
            "Trades long-only BTCUSDT 15-minute Jam reversals under spot constraints."
        ),
        allowed_regimes=(MarketRegime.BREAKOUT_EXPANSION,),
        default_risk_per_trade=Decimal("0.005"),
        default_minimum_reward_risk=Decimal("0.8"),
        default_max_open_positions=1,
        pine_path="pine/strategies/jam_reversal_spot_v1.pine",
        docs_path="docs/pine/jam_reversal_spot_v1.md",
        lifecycle_status=StrategyLifecycleStatus.RETIRED,
        lifecycle_reason=(
            "Version 1.0.1 failed its historical decision and is retired."
        ),
        default_enabled=False,
    ),
}


def registered_strategy_names() -> list[str]:
    return sorted(REGISTERED_STRATEGIES)


def strategy_lifecycle_status(strategy: str) -> StrategyLifecycleStatus:
    definition = REGISTERED_STRATEGIES.get(strategy)
    if definition is None:
        return StrategyLifecycleStatus.UNREGISTERED
    return definition.lifecycle_status


def strategy_lifecycle_reason(strategy: str) -> str:
    definition = REGISTERED_STRATEGIES.get(strategy)
    if definition is None:
        return "Unregistered strategies cannot be enabled."
    return definition.lifecycle_reason


def strategy_lifecycle_allows_enable(strategy: str) -> bool:
    definition = REGISTERED_STRATEGIES.get(strategy)
    return bool(
        definition is not None
        and definition.lifecycle_status == StrategyLifecycleStatus.ACTIVE
        and definition.qualification_contract_version
        == STRATEGY_FACTORY_CONTRACT_VERSION
        and definition.qualification_evidence_hash
    )


def default_allowed_regime_values(definition: StrategyDefinition) -> list[str]:
    return [regime.value for regime in definition.allowed_regimes]


def strategy_regime_compatible(
    strategy: str,
    direction: Direction,
    regime: MarketRegime,
    allowed_regimes: list[str] | None = None,
) -> bool:
    if regime == MarketRegime.UNKNOWN:
        return True

    if allowed_regimes is None:
        definition = REGISTERED_STRATEGIES.get(strategy)
        if definition is None:
            return False
        allowed_regimes = default_allowed_regime_values(definition)

    if regime.value not in allowed_regimes:
        return False

    if strategy == "trend_pullback_v1":
        return (
            direction == Direction.LONG
            and regime == MarketRegime.TRENDING_UP
            or direction == Direction.SHORT
            and regime == MarketRegime.TRENDING_DOWN
        )

    return True
