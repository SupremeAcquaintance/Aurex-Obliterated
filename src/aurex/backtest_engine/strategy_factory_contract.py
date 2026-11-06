from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aurex.backtest_engine.service import strict_strategy_factory_acceptance_criteria
from aurex.backtest_engine.universe import universe_evidence_hash

STRATEGY_FACTORY_CONTRACT_SCHEMA_VERSION = "aurex-strategy-factory-contract-v1"


class StrategyFactoryContractSource(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class StrategyFactoryContract(BaseModel):
    schema_version: Literal["aurex-strategy-factory-contract-v1"] = (
        STRATEGY_FACTORY_CONTRACT_SCHEMA_VERSION
    )
    contract_id: Literal["aurex-strategy-factory-contract-v1"] = (
        "aurex-strategy-factory-contract-v1"
    )
    status: Literal["FROZEN_PRE_CANDIDATE"] = "FROZEN_PRE_CANDIDATE"
    frozen_at: datetime
    authority_scope: Literal["FUTURE_STRATEGY_RESEARCH_ONLY"] = (
        "FUTURE_STRATEGY_RESEARCH_ONLY"
    )
    required_partition_order: list[Literal["DEVELOPMENT", "VALIDATION", "HOLDOUT"]]
    require_cost_stress: Literal[True] = True
    require_uncertainty_bound: Literal[True] = True
    require_multiple_testing_control: Literal[True] = True
    require_holdout_decision: Literal[True] = True
    partial_requirement_activation_allowed: Literal[False] = False
    validation_must_pass_before_holdout_open: Literal[True] = True
    holdout_may_be_opened_once: Literal[True] = True
    paper_authority_granted: Literal[False] = False
    sandbox_strategy_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    live_authority_granted: Literal[False] = False
    default_acceptance_criteria: dict
    source_evidence: list[StrategyFactoryContractSource] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    real_market_values_opened: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    real_net_profit_usd: Literal["0"] = "0"
    contract_evidence_hash: str = Field(pattern="^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_contract(self) -> "StrategyFactoryContract":
        if self.frozen_at.utcoffset() is None:
            raise ValueError("Strategy-factory contract timestamp must include a timezone")
        self.frozen_at = self.frozen_at.astimezone(UTC)
        if self.required_partition_order != ["DEVELOPMENT", "VALIDATION", "HOLDOUT"]:
            raise ValueError("Strategy-factory partition order changed")
        criteria = self.default_acceptance_criteria
        required = (
            "require_cost_stress",
            "require_uncertainty_bound",
            "require_multiple_testing_control",
            "require_holdout_decision",
        )
        if any(criteria.get(name) is not True for name in required):
            raise ValueError("Strategy-factory universal requirements changed")
        payload = self.model_dump(exclude={"contract_evidence_hash"})
        if universe_evidence_hash(payload) != self.contract_evidence_hash:
            raise ValueError("Strategy-factory contract evidence hash changed")
        return self


def build_strategy_factory_contract(
    *,
    frozen_at: datetime,
    source_evidence: list[StrategyFactoryContractSource],
) -> StrategyFactoryContract:
    payload = {
        "schema_version": STRATEGY_FACTORY_CONTRACT_SCHEMA_VERSION,
        "contract_id": "aurex-strategy-factory-contract-v1",
        "status": "FROZEN_PRE_CANDIDATE",
        "frozen_at": frozen_at,
        "authority_scope": "FUTURE_STRATEGY_RESEARCH_ONLY",
        "required_partition_order": ["DEVELOPMENT", "VALIDATION", "HOLDOUT"],
        "require_cost_stress": True,
        "require_uncertainty_bound": True,
        "require_multiple_testing_control": True,
        "require_holdout_decision": True,
        "partial_requirement_activation_allowed": False,
        "validation_must_pass_before_holdout_open": True,
        "holdout_may_be_opened_once": True,
        "paper_authority_granted": False,
        "sandbox_strategy_authority_granted": False,
        "production_authority_granted": False,
        "live_authority_granted": False,
        "default_acceptance_criteria": (
            strict_strategy_factory_acceptance_criteria().model_dump(mode="json")
        ),
        "source_evidence": source_evidence,
        "limitations": [
            "This contract evaluates future candidates; it does not create a strategy.",
            "Passing historical gates cannot establish future profitability.",
            "Paper, sandbox-strategy, production, and live authority remain separate gates.",
        ],
        "real_market_values_opened": 0,
        "strategy_candidates_created": 0,
        "strategy_executions": 0,
        "orders_submitted": 0,
        "real_net_profit_usd": "0",
    }
    return StrategyFactoryContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_strategy_factory_contract(contract: StrategyFactoryContract) -> bool:
    try:
        StrategyFactoryContract.model_validate(contract.model_dump())
    except ValueError:
        return False
    return True
