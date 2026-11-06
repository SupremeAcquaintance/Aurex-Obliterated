from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R3_FAILURE_PROTOCOL_SCHEMA_VERSION = "aurex-r3-failure-analysis-protocol-v1"
R3_FAILURE_ANALYSIS_DIMENSIONS = [
    "CORRECTED_MONTHLY_NET_RETURNS",
    "COST_AND_TURNOVER_DECOMPOSITION",
    "DIAGNOSTIC_BTC_ETH_SOL_QUARTERLY_RETURN_AND_VOLATILITY",
    "DRAWDOWN_EPISODES_AND_GROSS_EXPOSURE",
    "EXIT_REASON_BY_QUARTER",
    "MOMENTUM_HORIZON_COMPARISON",
    "POSITIVE_MARKET_BREADTH_AT_REBALANCE",
    "PRIMARY_QUARTERLY_FOLD_DECOMPOSITION",
    "SYMBOL_NET_AND_RAW_CONTRIBUTION_BY_QUARTER",
]
R3_FAILURE_PROHIBITIONS = [
    "DO_NOT_ALTER_R3_V1_ARTIFACTS_GATES_OR_VERDICT",
    "DO_NOT_CONVERT_DISCOVERED_BUCKETS_INTO_TRADING_RULES",
    "DO_NOT_OPEN_VALIDATION_HOLDOUT_OR_FORWARD_DATA",
    "DO_NOT_PROMOTE_A_FALSIFICATION_VARIANT",
    "DO_NOT_REGISTER_OR_ENABLE_A_STRATEGY_FROM_THIS_ANALYSIS",
    "DO_NOT_SELECT_PARAMETERS_BY_OBSERVED_PROFIT",
]


class R3KnownOutcomeBoundary(BaseModel):
    verdict: Literal["NO_CANDIDATE"] = "NO_CANDIDATE"
    passed_gates: Literal[9] = 9
    total_gates: Literal[10] = 10
    failed_gate_id: Literal["primary_positive_quarterly_folds"] = (
        "primary_positive_quarterly_folds"
    )
    observed_positive_folds: Literal[3] = 3
    required_positive_folds: Literal[4] = 4
    primary_net_pl: Decimal
    primary_profit_factor: Decimal
    primary_maximum_drawdown_percent: Decimal

    model_config = ConfigDict(extra="forbid")


class R3FailureAnalysisProtocol(BaseModel):
    schema_version: Literal["aurex-r3-failure-analysis-protocol-v1"] = (
        R3_FAILURE_PROTOCOL_SCHEMA_VERSION
    )
    protocol_id: str = Field(min_length=1, max_length=128)
    protocol_version: str = Field(min_length=1, max_length=64)
    registered_at: datetime
    status: Literal["FROZEN_POST_OUTCOME_PRE_ANALYSIS"] = (
        "FROZEN_POST_OUTCOME_PRE_ANALYSIS"
    )
    run_package_evidence_hash: str
    result_ledger_evidence_hash: str
    monthly_addendum_evidence_hash: str
    development_dataset_bundle_evidence_hash: str
    replay_result_evidence_hashes: dict[str, str] = Field(min_length=1)
    known_outcome_boundary: R3KnownOutcomeBoundary
    allowed_data_scopes: list[
        Literal[
            "R3_STORED_REPLAY_ARTIFACTS",
            "R3_DEVELOPMENT_DECISION_OHLC_2023_2024",
            "R3_DIAGNOSTIC_BTC_ETH_SOL_OHLC_2023_2024",
        ]
    ]
    analysis_dimensions: list[str]
    required_outputs: list[str]
    prohibited_actions: list[str]
    allowed_next_decisions: list[
        Literal["PROPOSE_BOUNDED_R3_1", "STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY"]
    ]
    analysis_is_descriptive_only: Literal[True] = True
    creates_candidate: Literal[False] = False
    opens_sealed_partition: Literal[False] = False
    preexisting_analysis_artifacts: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "run_package_evidence_hash",
        "result_ledger_evidence_hash",
        "monthly_addendum_evidence_hash",
        "development_dataset_bundle_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("replay_result_evidence_hashes")
    @classmethod
    def normalize_replay_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            run_id.strip(): normalize_sha256(evidence_hash)
            for run_id, evidence_hash in sorted(value.items())
            if run_id.strip()
        }

    @field_validator(
        "allowed_data_scopes",
        "analysis_dimensions",
        "required_outputs",
        "prohibited_actions",
        "allowed_next_decisions",
        "preexisting_analysis_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> "R3FailureAnalysisProtocol":
        if len(self.replay_result_evidence_hashes) != 62:
            raise ValueError("R3 failure analysis requires all 62 replay results")
        if self.analysis_dimensions != R3_FAILURE_ANALYSIS_DIMENSIONS:
            raise ValueError("R3 failure-analysis dimensions are fixed")
        if self.prohibited_actions != R3_FAILURE_PROHIBITIONS:
            raise ValueError("R3 failure-analysis prohibitions are fixed")
        if self.preexisting_analysis_artifacts:
            raise ValueError("R3 failure protocol must predate its analysis artifact")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("R3 failure protocol hash does not match its evidence")
        return self


def build_r3_failure_analysis_protocol(**values) -> R3FailureAnalysisProtocol:
    payload = {
        "schema_version": R3_FAILURE_PROTOCOL_SCHEMA_VERSION,
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["replay_result_evidence_hashes"] = dict(
        sorted(payload["replay_result_evidence_hashes"].items())
    )
    for field in (
        "allowed_data_scopes",
        "analysis_dimensions",
        "required_outputs",
        "prohibited_actions",
        "allowed_next_decisions",
        "preexisting_analysis_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return R3FailureAnalysisProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r3_failure_analysis_protocol(
    protocol: R3FailureAnalysisProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
