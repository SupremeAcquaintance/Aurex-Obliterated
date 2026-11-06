from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

POST_V4_CAPABILITY_REVIEW_SCHEMA_VERSION = (
    "aurex-post-v4-capability-gap-review-v1"
)
POST_V4_DECISION = (
    "DO_NOT_START_SUCCESSOR_ALPHA_DISCOVERY_UNTIL_ACCESS_PROFILE_IS_FROZEN"
)
POST_V4_CAPABILITY_IDS = [
    "AUTHENTICATED_EXTERNAL_TRADINGVIEW_DELIVERY",
    "DETERMINISTIC_PRODUCTION_EXCHANGE_ADAPTER",
    "EVIDENCE_GRADE_BAR_REPLAY",
    "EXECUTION_GRADE_HISTORICAL_TICK_OR_L2",
    "FORWARD_PAPER_ENGINE_AND_RISK_CONTROLS",
    "OPERATOR_CAPITAL_AND_LOSS_BUDGET",
    "OPERATOR_JURISDICTION_ACCOUNT_AND_PRODUCT_ACCESS",
    "PINE_TO_AUREX_TRADE_LEVEL_PARITY",
    "POINT_IN_TIME_FEES_FILTERS_AND_VENUE_RULES",
    "PROVEN_POSITIVE_NET_STRATEGY_EDGE",
    "QUALIFIED_EXCHANGE_SANDBOX_OPERATION",
]
POST_V4_REQUIRED_OPERATOR_DECISION_IDS = [
    "ACCOUNT_AND_API_ACCESS",
    "DATA_ACQUISITION_BUDGET",
    "INTENDED_EXECUTION_VENUE",
    "MAXIMUM_ACCEPTABLE_LOSS",
    "PERMITTED_PRODUCT_SCOPE",
    "STARTING_TRADING_CAPITAL",
]
POST_V4_ALLOWED_NEXT_TRACKS = [
    "FREEZE_OPERATOR_ACCESS_CAPITAL_AND_DATA_PROFILE",
    "PRESERVE_READ_ONLY_REJECTED_V1_3_PARITY_TRACK",
    "RUN_ONE_GENUINE_WEBHOOK_DELIVERY_TO_PAPER_SAFE_REJECTION",
]


class PostV4CapabilityAssessment(BaseModel):
    capability_id: Literal[
        "AUTHENTICATED_EXTERNAL_TRADINGVIEW_DELIVERY",
        "DETERMINISTIC_PRODUCTION_EXCHANGE_ADAPTER",
        "EVIDENCE_GRADE_BAR_REPLAY",
        "EXECUTION_GRADE_HISTORICAL_TICK_OR_L2",
        "FORWARD_PAPER_ENGINE_AND_RISK_CONTROLS",
        "OPERATOR_CAPITAL_AND_LOSS_BUDGET",
        "OPERATOR_JURISDICTION_ACCOUNT_AND_PRODUCT_ACCESS",
        "PINE_TO_AUREX_TRADE_LEVEL_PARITY",
        "POINT_IN_TIME_FEES_FILTERS_AND_VENUE_RULES",
        "PROVEN_POSITIVE_NET_STRATEGY_EDGE",
        "QUALIFIED_EXCHANGE_SANDBOX_OPERATION",
    ]
    status: Literal[
        "PROVEN",
        "IMPLEMENTED_NOT_EXTERNALLY_PROVEN",
        "PARTIAL",
        "ABSENT",
        "OPERATOR_INPUT_REQUIRED",
    ]
    evidence_artifacts: list[str]
    implication: str = Field(min_length=60, max_length=1400)

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_artifacts")
    @classmethod
    def normalize_evidence(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class PostV4OperatorDecision(BaseModel):
    decision_id: Literal[
        "ACCOUNT_AND_API_ACCESS",
        "DATA_ACQUISITION_BUDGET",
        "INTENDED_EXECUTION_VENUE",
        "MAXIMUM_ACCEPTABLE_LOSS",
        "PERMITTED_PRODUCT_SCOPE",
        "STARTING_TRADING_CAPITAL",
    ]
    status: Literal["REQUIRED_UNRESOLVED"] = "REQUIRED_UNRESOLVED"
    required_value: str = Field(min_length=40, max_length=900)
    why_it_blocks_successor_discovery: str = Field(
        min_length=60,
        max_length=1200,
    )

    model_config = ConfigDict(extra="forbid")


class PostV4CapabilityGapReview(BaseModel):
    schema_version: Literal[
        "aurex-post-v4-capability-gap-review-v1"
    ] = POST_V4_CAPABILITY_REVIEW_SCHEMA_VERSION
    review_id: Literal["post-v4-capability-gap-review-v1"] = (
        "post-v4-capability-gap-review-v1"
    )
    review_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_POST_V4_PRE_SUCCESSOR_NO_CANDIDATE"] = (
        "FROZEN_POST_V4_PRE_SUCCESSOR_NO_CANDIDATE"
    )
    v4_discovery_charter_evidence_hash: str
    v4_proposal_register_evidence_hash: str
    v4_feasibility_screen_evidence_hash: str
    builder_contract_hash: str
    capability_assessments: list[PostV4CapabilityAssessment] = Field(
        min_length=11,
        max_length=11,
    )
    required_operator_decisions: list[PostV4OperatorDecision] = Field(
        min_length=6,
        max_length=6,
    )
    allowed_next_tracks: list[str] = Field(min_length=3, max_length=3)
    recommended_sequence: list[str] = Field(min_length=6)
    decision: Literal[
        "DO_NOT_START_SUCCESSOR_ALPHA_DISCOVERY_UNTIL_ACCESS_PROFILE_IS_FROZEN"
    ] = POST_V4_DECISION
    recommended_lane: Literal[
        "ENGINE_PROOF_AND_OPERATOR_ACCESS_FREEZE_BEFORE_NEW_ALPHA_DISCOVERY"
    ] = "ENGINE_PROOF_AND_OPERATOR_ACCESS_FREEZE_BEFORE_NEW_ALPHA_DISCOVERY"
    successor_discovery_authorized: Literal[False] = False
    network_requests_authorized: Literal[False] = False
    market_data_import_authorized: Literal[False] = False
    parameter_definition_authorized: Literal[False] = False
    return_testing_authorized: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=8)
    review_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "v4_discovery_charter_evidence_hash",
        "v4_proposal_register_evidence_hash",
        "v4_feasibility_screen_evidence_hash",
        "builder_contract_hash",
        "review_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "allowed_next_tracks",
        "recommended_sequence",
        "market_numeric_values_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_review(self) -> PostV4CapabilityGapReview:
        if [
            item.capability_id for item in self.capability_assessments
        ] != POST_V4_CAPABILITY_IDS:
            raise ValueError("Post-V4 capability set or order changed")
        if [
            item.decision_id for item in self.required_operator_decisions
        ] != POST_V4_REQUIRED_OPERATOR_DECISION_IDS:
            raise ValueError("Post-V4 operator decision set or order changed")
        if self.allowed_next_tracks != POST_V4_ALLOWED_NEXT_TRACKS:
            raise ValueError("Post-V4 allowed next tracks changed")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("Post-V4 capability review may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"review_evidence_hash"})
        )
        if self.review_evidence_hash != expected_hash:
            raise ValueError("Post-V4 capability review hash does not match")
        return self


def build_post_v4_capability_gap_review(
    **values,
) -> PostV4CapabilityGapReview:
    payload = {
        "schema_version": POST_V4_CAPABILITY_REVIEW_SCHEMA_VERSION,
        "review_id": "post-v4-capability-gap-review-v1",
        "review_version": "1.0.0",
        "status": "FROZEN_POST_V4_PRE_SUCCESSOR_NO_CANDIDATE",
        "decision": POST_V4_DECISION,
        "recommended_lane": (
            "ENGINE_PROOF_AND_OPERATOR_ACCESS_FREEZE_BEFORE_NEW_ALPHA_DISCOVERY"
        ),
        "successor_discovery_authorized": False,
        "network_requests_authorized": False,
        "market_data_import_authorized": False,
        "parameter_definition_authorized": False,
        "return_testing_authorized": False,
        "creates_candidate": False,
        "opens_development": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field_name in (
        "allowed_next_tracks",
        "recommended_sequence",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return PostV4CapabilityGapReview(
        **payload,
        review_evidence_hash=universe_evidence_hash(payload),
    )


def audit_post_v4_capability_gap_review(
    review: PostV4CapabilityGapReview,
) -> bool:
    return review.review_evidence_hash == universe_evidence_hash(
        review.model_dump(exclude={"review_evidence_hash"})
    )
