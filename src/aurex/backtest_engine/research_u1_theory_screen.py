from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

U1_THEORY_SCREEN_SCHEMA_VERSION = "aurex-u1-mechanism-theory-screen-v1"

U1_THEORY_SELECTION_RULES = [
    "REJECT_IF_CURRENT_POINT_IN_TIME_DATA_CANNOT_REPRODUCE_THE_MECHANISM",
    "REJECT_IF_CURRENT_SPOT_EXECUTION_CANNOT_EXPRESS_THE_MECHANISM",
    "REJECT_IF_DERIVED_FROM_A_RETIRED_OR_QUARANTINED_LINEAGE",
    "REJECT_IF_FEWER_THAN_TWO_PRIMARY_RESEARCH_SOURCES",
    "REJECT_IF_SELECTED_USING_AUREX_RETURN_OUTCOMES",
    "PREFER_FEWER_NEW_DATA_AND_EXECUTION_DEPENDENCIES",
    "PREFER_LOWER_EXPECTED_TURNOVER_AND_MODEL_COMPLEXITY",
    "TIE_BREAK_BY_PROPOSAL_ID",
]

U1_THEORY_PROPOSAL_IDS = [
    "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA",
    "P02_SIGNED_JUMP_RISK_PREMIUM",
    "P03_DELTA_NEUTRAL_FUNDING_CARRY",
]


class U1TheorySource(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=5, max_length=300)
    authors: list[str] = Field(min_length=1)
    publication_date: str = Field(min_length=10, max_length=10)
    source_kind: Literal[
        "PEER_REVIEWED_ARTICLE",
        "INSTITUTIONAL_WORKING_PAPER",
    ]
    url: str = Field(min_length=10, max_length=1000)
    relevance: str = Field(min_length=20, max_length=1000)
    aurex_return_metrics_used: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("authors")
    @classmethod
    def normalize_authors(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Theory source authors must be unique")
        return normalized

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("https://"):
            raise ValueError("Theory source URL must use HTTPS")
        return normalized

    @field_validator("publication_date")
    @classmethod
    def validate_publication_date(cls, value: str) -> str:
        normalized = value.strip()
        date.fromisoformat(normalized)
        return normalized

    @model_validator(mode="after")
    def validate_source(self) -> U1TheorySource:
        if self.aurex_return_metrics_used:
            raise ValueError("Theory sources cannot use Aurex return metrics")
        return self


class U1MechanismProposal(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=128)
    mechanism_name: str = Field(min_length=5, max_length=200)
    economic_premise: str = Field(min_length=50, max_length=2000)
    expected_payoff_source: str = Field(min_length=30, max_length=1000)
    ex_ante_directional_prediction: str = Field(min_length=30, max_length=1000)
    primary_sources: list[U1TheorySource] = Field(min_length=2)
    current_required_fields: list[str] = Field(min_length=1)
    additional_required_fields: list[str] = Field(default_factory=list)
    current_data_reproducible: bool
    current_long_only_spot_execution_supported: bool
    requires_shorting_or_leverage: bool
    expected_turnover: Literal["LOW", "MEDIUM", "HIGH"]
    model_complexity: Literal["LOW", "MEDIUM", "HIGH"]
    independent_of_retired_lineages: bool
    uses_post_r4_outcome_rules: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    disposition: Literal[
        "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN",
        "DEFER_UNTIL_DATA_FOUNDATION_EXISTS",
        "DEFER_UNTIL_EXECUTION_FOUNDATION_EXISTS",
    ]
    decision_rationale: str = Field(min_length=30, max_length=1500)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "proposal_id",
        "mechanism_name",
        "economic_premise",
        "expected_payoff_source",
        "ex_ante_directional_prediction",
        "decision_rationale",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "current_required_fields",
        "additional_required_fields",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "blocking_reasons",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_proposal(self) -> U1MechanismProposal:
        source_ids = [source.source_id for source in self.primary_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Theory proposal source IDs must be unique")
        if not self.independent_of_retired_lineages:
            raise ValueError("U1 theory proposals must be independent")
        if self.strategy_outcome_fields_inspected or self.return_metrics_calculated:
            raise ValueError("Theory proposals cannot contain strategy outcomes")
        if self.disposition == "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN":
            if (
                not self.current_data_reproducible
                or not self.current_long_only_spot_execution_supported
                or self.requires_shorting_or_leverage
                or self.additional_required_fields
                or self.blocking_reasons
            ):
                raise ValueError("Selected U1 proposal must be currently executable")
        elif not self.blocking_reasons:
            raise ValueError("Deferred U1 proposals require blocking reasons")
        return self


class U1MechanismTheoryScreen(BaseModel):
    schema_version: Literal["aurex-u1-mechanism-theory-screen-v1"] = (
        U1_THEORY_SCREEN_SCHEMA_VERSION
    )
    screen_id: Literal["u1-unrelated-mechanism-theory-screen-v1"] = (
        "u1-unrelated-mechanism-theory-screen-v1"
    )
    screen_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_NO_RETURN_METRICS"] = "FROZEN_NO_RETURN_METRICS"
    discovery_charter_evidence_hash: str
    proposals: list[U1MechanismProposal] = Field(min_length=3, max_length=3)
    selection_rules: list[str]
    selected_proposal_id: Literal[
        "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    ] = "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA"
    next_decision: Literal["FREEZE_ONE_PRIMARY_MECHANISM_FOR_DEVELOPMENT"] = (
        "FREEZE_ONE_PRIMARY_MECHANISM_FOR_DEVELOPMENT"
    )
    theory_proposals_considered: Literal[3] = 3
    return_tested_mechanisms: Literal[0] = 0
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout_or_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    preexisting_primary_artifacts: list[str] = Field(default_factory=list)
    builder_contract_hash: str
    screen_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "builder_contract_hash",
        "screen_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "selection_rules",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_primary_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_screen(self) -> U1MechanismTheoryScreen:
        if [proposal.proposal_id for proposal in self.proposals] != U1_THEORY_PROPOSAL_IDS:
            raise ValueError("U1 theory proposal order and IDs are fixed")
        selected = [
            proposal
            for proposal in self.proposals
            if proposal.disposition == "SELECT_FOR_PRIMARY_PROTOCOL_DESIGN"
        ]
        if len(selected) != 1 or selected[0].proposal_id != self.selected_proposal_id:
            raise ValueError("U1 theory screen must select exactly its declared primary")
        if self.selection_rules != sorted(U1_THEORY_SELECTION_RULES):
            raise ValueError("U1 theory selection rules are fixed")
        if self.strategy_outcome_fields_inspected or self.return_metrics_calculated:
            raise ValueError("U1 theory screen cannot contain strategy outcomes")
        if self.preexisting_primary_artifacts:
            raise ValueError("U1 theory screen must predate primary artifacts")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"screen_evidence_hash"})
        )
        if self.screen_evidence_hash != expected_hash:
            raise ValueError("U1 theory screen hash does not match its evidence")
        return self


def build_u1_mechanism_theory_screen(**values) -> U1MechanismTheoryScreen:
    payload = {
        "schema_version": U1_THEORY_SCREEN_SCHEMA_VERSION,
        "screen_id": "u1-unrelated-mechanism-theory-screen-v1",
        "screen_version": "1.0.0",
        "status": "FROZEN_NO_RETURN_METRICS",
        "selected_proposal_id": "P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA",
        "next_decision": "FREEZE_ONE_PRIMARY_MECHANISM_FOR_DEVELOPMENT",
        "theory_proposals_considered": 3,
        "return_tested_mechanisms": 0,
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout_or_forward": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field in (
        "selection_rules",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_primary_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    return U1MechanismTheoryScreen(
        **payload,
        screen_evidence_hash=universe_evidence_hash(payload),
    )


def audit_u1_mechanism_theory_screen(
    screen: U1MechanismTheoryScreen,
) -> bool:
    return screen.screen_evidence_hash == universe_evidence_hash(
        screen.model_dump(exclude={"screen_evidence_hash"})
    )
