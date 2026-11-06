from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

R4_FAILURE_PROTOCOL_SCHEMA_VERSION = "aurex-r4-failure-analysis-protocol-v1"
R4_FAILURE_ANALYSIS_DIMENSIONS = [
    "ACTIVE_BREADTH_AND_MARKET_TERMINATION",
    "DRAWDOWN_AND_GROSS_EXPOSURE",
    "EXIT_REASON_AND_HOLDING_DURATION",
    "GROSS_NET_COST_RECONCILIATION",
    "QUARTERLY_AND_MONTHLY_STABILITY",
    "REBALANCE_COHORT_OUTCOMES",
    "SYMBOL_CONTRIBUTION_AND_LEAVE_ONE_MARKET_OUT",
]
R4_FAILURE_REQUIRED_OUTPUTS = [
    "BROAD_FAILURE_CLASSIFICATION",
    "COST_ATTRIBUTION",
    "DRAWDOWN_EPISODES",
    "EXIT_REASON_SUMMARY",
    "HOLDING_DURATION_SUMMARY",
    "MARKET_AVAILABILITY_SUMMARY",
    "MONTHLY_AND_QUARTERLY_SUMMARY",
    "REBALANCE_COHORT_SUMMARY",
    "SYMBOL_CONTRIBUTION_SUMMARY",
]
R4_FAILURE_PROHIBITIONS = [
    "DO_NOT_ALTER_R4_ARTIFACTS_GATES_OR_VERDICT",
    "DO_NOT_CONVERT_DISCOVERED_BUCKETS_INTO_TRADING_RULES",
    "DO_NOT_CREATE_REGISTER_OR_ENABLE_A_CANDIDATE",
    "DO_NOT_INVERT_OR_REPARAMETERIZE_PATH_QUALITY",
    "DO_NOT_OPEN_2026_HOLDOUT_OR_FORWARD_DATA",
    "DO_NOT_SELECT_MARKETS_MONTHS_QUARTERS_OR_EXITS_BY_OBSERVED_PROFIT",
    "DO_NOT_SELECT_PARAMETERS_BY_OBSERVED_2025_OUTCOMES",
]
R4_KNOWN_INSPECTED_OUTCOME_FIELDS = [
    "availability_metrics",
    "base_cost_metrics",
    "double_cost_metrics",
    "frozen_gate_results",
    "leave_one_market_out_net_pl",
    "monthly_net_returns",
    "quarterly_fold_metrics",
]
R4_FAILED_GATE_IDS = [
    "base_cost_net_pl",
    "base_cost_profit_factor",
    "double_cost_net_pl",
    "leave_one_market_out_positive_fraction",
    "positive_quarterly_folds",
]


class R4KnownOutcomeBoundary(BaseModel):
    verdict: Literal["RETIRE_R4_CANDIDATE"] = "RETIRE_R4_CANDIDATE"
    passed_gates: Literal[4] = 4
    total_gates: Literal[9] = 9
    failed_gate_ids: list[str]
    base_cost_net_pl: Decimal
    base_cost_profit_factor: Decimal
    base_cost_raw_profit_factor: Decimal
    base_cost_maximum_drawdown_percent: Decimal
    base_cost_completed_trades: Literal[112] = 112
    double_cost_net_pl: Decimal
    positive_quarterly_folds: Literal[1] = 1
    total_quarterly_folds: Literal[4] = 4
    leave_one_market_out_positive_fraction: Literal["0"] = "0"
    base_cost_termination_writeoff_count: Literal[0] = 0
    permits_pine_parity_review: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("failed_gate_ids")
    @classmethod
    def normalize_failed_gates(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_boundary(self) -> R4KnownOutcomeBoundary:
        if self.failed_gate_ids != R4_FAILED_GATE_IDS:
            raise ValueError("R4 failure boundary must preserve the exact failed gates")
        expected = {
            "base_cost_net_pl": Decimal("-73.83400610082014763776880"),
            "base_cost_profit_factor": Decimal(
                "0.79907381400099427184162898918243564040590006172326"
            ),
            "base_cost_raw_profit_factor": Decimal(
                "0.85299208718220210265491630524154560128327097165946"
            ),
            "base_cost_maximum_drawdown_percent": Decimal(
                "14.930840107747523224115030032760231425948842383500"
            ),
            "double_cost_net_pl": Decimal("-94.18049028824977929602280"),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValueError("R4 failure boundary differs from the frozen ledger")
        return self


class R4FailureAnalysisProtocol(BaseModel):
    schema_version: Literal["aurex-r4-failure-analysis-protocol-v1"] = (
        R4_FAILURE_PROTOCOL_SCHEMA_VERSION
    )
    protocol_id: Literal["r4-path-quality-failure-analysis-v1"] = (
        "r4-path-quality-failure-analysis-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    registered_at: datetime
    status: Literal["FROZEN_POST_OUTCOME_PRE_ANALYSIS"] = (
        "FROZEN_POST_OUTCOME_PRE_ANALYSIS"
    )
    candidate_protocol_evidence_hash: str
    validation_dataset_bundle_evidence_hash: str
    execution_specification_evidence_hash: str
    run_package_evidence_hash: str
    result_ledger_evidence_hash: str
    replay_result_evidence_hashes: dict[str, str] = Field(min_length=42, max_length=42)
    known_outcome_boundary: R4KnownOutcomeBoundary
    known_outcome_fields_inspected: list[str]
    allowed_data_scopes: list[
        Literal[
            "R4_RESULT_LEDGER",
            "R4_STORED_REPLAY_ARTIFACTS",
            "R4_VALIDATION_BUNDLE_METADATA",
        ]
    ]
    analysis_dimensions: list[str]
    required_outputs: list[str]
    prohibited_actions: list[str]
    allowed_next_decisions: list[
        Literal[
            "STOP_ALL_STRATEGY_RESEARCH_BRANCH",
            "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY",
        ]
    ]
    analysis_is_descriptive_only: Literal[True] = True
    creates_candidate: Literal[False] = False
    changes_r4_verdict: Literal[False] = False
    opens_2026_or_forward_partition: Literal[False] = False
    preexisting_analysis_artifacts: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("registered_at")
    @classmethod
    def normalize_registered_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "candidate_protocol_evidence_hash",
        "validation_dataset_bundle_evidence_hash",
        "execution_specification_evidence_hash",
        "run_package_evidence_hash",
        "result_ledger_evidence_hash",
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
        "known_outcome_fields_inspected",
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
    def validate_protocol(self) -> R4FailureAnalysisProtocol:
        if len(self.replay_result_evidence_hashes) != 42:
            raise ValueError("R4 failure analysis requires all 42 replay results")
        if self.known_outcome_fields_inspected != R4_KNOWN_INSPECTED_OUTCOME_FIELDS:
            raise ValueError("R4 known inspected outcome fields are fixed")
        if self.analysis_dimensions != R4_FAILURE_ANALYSIS_DIMENSIONS:
            raise ValueError("R4 failure-analysis dimensions are fixed")
        if self.required_outputs != R4_FAILURE_REQUIRED_OUTPUTS:
            raise ValueError("R4 failure-analysis outputs are fixed")
        if self.prohibited_actions != R4_FAILURE_PROHIBITIONS:
            raise ValueError("R4 failure-analysis prohibitions are fixed")
        if self.allowed_next_decisions != [
            "STOP_ALL_STRATEGY_RESEARCH_BRANCH",
            "STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY",
        ]:
            raise ValueError("R4 failure-analysis next decisions are fixed")
        if self.preexisting_analysis_artifacts:
            raise ValueError("R4 failure protocol must predate its analysis artifacts")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("R4 failure protocol hash does not match its evidence")
        return self


def build_r4_failure_analysis_protocol(**values) -> R4FailureAnalysisProtocol:
    payload = {
        "schema_version": R4_FAILURE_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "r4-path-quality-failure-analysis-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_POST_OUTCOME_PRE_ANALYSIS",
        "analysis_is_descriptive_only": True,
        "creates_candidate": False,
        "changes_r4_verdict": False,
        "opens_2026_or_forward_partition": False,
        **values,
    }
    payload["registered_at"] = normalize_timestamp(payload["registered_at"])
    payload["replay_result_evidence_hashes"] = dict(
        sorted(payload["replay_result_evidence_hashes"].items())
    )
    for field in (
        "known_outcome_fields_inspected",
        "allowed_data_scopes",
        "analysis_dimensions",
        "required_outputs",
        "prohibited_actions",
        "allowed_next_decisions",
        "preexisting_analysis_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return R4FailureAnalysisProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_r4_failure_analysis_protocol(
    protocol: R4FailureAnalysisProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
