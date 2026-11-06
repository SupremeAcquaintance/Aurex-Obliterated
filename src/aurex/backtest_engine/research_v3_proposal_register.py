from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_PROPOSAL_REGISTER_SCHEMA_VERSION = (
    "aurex-v3-independent-mechanism-proposal-register-v1"
)
V3_PROPOSAL_IDS = [
    "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
    "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
    "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
]
V3_REGISTER_DECISION = "FREEZE_THREE_PROPOSALS_FOR_NO_RETURN_FEASIBILITY_AUDIT"


class V3ProposalSource(BaseModel):
    source_id: str = Field(pattern=r"^[A-Z0-9_]{5,80}$")
    title: str = Field(min_length=10, max_length=300)
    authors_or_publisher: list[str] = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "PEER_REVIEWED_ARTICLE",
        "INSTITUTIONAL_WORKING_PAPER",
        "PREPRINT",
    ]
    url: str = Field(min_length=20, max_length=1000)
    supported_claims: list[str] = Field(min_length=2)
    aurex_market_values_used: list[str] = Field(default_factory=list)
    aurex_return_metrics_used: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("accessed_at")
    @classmethod
    def normalize_accessed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("publication_or_revision_date")
    @classmethod
    def validate_publication_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value

    @field_validator(
        "authors_or_publisher",
        "supported_claims",
        "aurex_market_values_used",
        "aurex_return_metrics_used",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_source(self) -> V3ProposalSource:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("V3 source URL must be public HTTPS")
        if self.aurex_market_values_used or self.aurex_return_metrics_used:
            raise ValueError("V3 source cannot be selected using Aurex outcomes")
        return self


class V3ProposalCoverageContract(BaseModel):
    required_archive_families: list[str]
    supplemental_historical_sources: list[str]
    timestamp_join_policy: str = Field(min_length=20, max_length=300)
    missing_row_policy: str = Field(min_length=20, max_length=500)
    minimum_total_coverage_fraction: Decimal = Field(gt=0, le=1)
    minimum_calendar_month_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_single_gap_minutes: int = Field(ge=0)
    minimum_qualified_symbols: int = Field(ge=1, le=35)
    required_timestamp_evidence: list[str]
    point_in_time_execution_dependencies: list[str]
    coverage_breach_action: Literal[
        "REJECT_PROPOSAL_BEFORE_PRIMARY_SELECTION"
    ] = "REJECT_PROPOSAL_BEFORE_PRIMARY_SELECTION"
    synthetic_rows_allowed: Literal[False] = False
    market_numeric_values_permitted_in_feasibility_audit: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "required_archive_families",
        "supplemental_historical_sources",
        "required_timestamp_evidence",
        "point_in_time_execution_dependencies",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V3MechanismProposal(BaseModel):
    proposal_id: Literal[
        "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
        "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
        "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
    ]
    mechanism_name: str = Field(min_length=10, max_length=200)
    economic_premise: str = Field(min_length=100, max_length=2000)
    ex_ante_payoff_direction: str = Field(min_length=80, max_length=1500)
    exact_point_in_time_data_requirements: list[str] = Field(min_length=3)
    historical_metadata_requirements: list[str] = Field(min_length=2)
    execution_path: str = Field(min_length=80, max_length=1500)
    principal_risks: list[str] = Field(min_length=3)
    pre_return_falsification_condition: str = Field(
        min_length=100,
        max_length=1500,
    )
    independence_from_blocked_lineages: list[str] = Field(min_length=2)
    coverage_contract: V3ProposalCoverageContract
    primary_sources: list[V3ProposalSource] = Field(min_length=3)
    preliminary_execution_fit: Literal[
        "REQUIRES_SEPARATE_CROSS_ASSET_PAIRED_FOUNDATION",
        "REQUIRES_AGGREGATE_TRADES_AND_DIRECTIONAL_FUTURES_FOUNDATION",
        "BLOCKED_PENDING_L2_QUEUE_FILL_AND_LATENCY_HISTORY",
    ]
    parameter_sets_defined: list[str] = Field(default_factory=list)
    market_numeric_fields_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    disposition: Literal["REGISTER_FOR_SEPARATE_NO_RETURN_FEASIBILITY_AUDIT"] = (
        "REGISTER_FOR_SEPARATE_NO_RETURN_FEASIBILITY_AUDIT"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "exact_point_in_time_data_requirements",
        "historical_metadata_requirements",
        "principal_risks",
        "independence_from_blocked_lineages",
        "parameter_sets_defined",
        "market_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_proposal(self) -> V3MechanismProposal:
        if (
            self.parameter_sets_defined
            or self.market_numeric_fields_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3 proposal register must predate parameters and outcomes")
        if len({source.source_id for source in self.primary_sources}) != len(
            self.primary_sources
        ):
            raise ValueError("V3 proposal source IDs are not unique")
        return self


class V3MechanismProposalRegister(BaseModel):
    schema_version: Literal[
        "aurex-v3-independent-mechanism-proposal-register-v1"
    ] = V3_PROPOSAL_REGISTER_SCHEMA_VERSION
    register_id: Literal["v3-independent-mechanism-proposals-v1"] = (
        "v3-independent-mechanism-proposals-v1"
    )
    register_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FEASIBILITY_OBSERVATION"] = (
        "FROZEN_PRE_FEASIBILITY_OBSERVATION"
    )
    discovery_charter_evidence_hash: str
    builder_contract_hash: str
    proposals: list[V3MechanismProposal] = Field(min_length=3, max_length=3)
    proposal_budget_consumed: Literal[3] = 3
    selected_primary_count: Literal[0] = 0
    parameter_set_count: Literal[0] = 0
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    decision: Literal[
        "FREEZE_THREE_PROPOSALS_FOR_NO_RETURN_FEASIBILITY_AUDIT"
    ] = V3_REGISTER_DECISION
    authorizes_timestamp_coverage_audit: Literal[True] = True
    authorizes_market_numeric_value_inspection: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    register_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "builder_contract_hash",
        "register_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_register(self) -> V3MechanismProposalRegister:
        if [proposal.proposal_id for proposal in self.proposals] != V3_PROPOSAL_IDS:
            raise ValueError("V3 proposal order or identity changed")
        if (
            self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3 proposal register must contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"register_evidence_hash"})
        )
        if self.register_evidence_hash != expected_hash:
            raise ValueError("V3 proposal register hash does not match")
        return self


def build_v3_mechanism_proposal_register(
    **values,
) -> V3MechanismProposalRegister:
    payload = {
        "schema_version": V3_PROPOSAL_REGISTER_SCHEMA_VERSION,
        "register_id": "v3-independent-mechanism-proposals-v1",
        "register_version": "1.0.0",
        "status": "FROZEN_PRE_FEASIBILITY_OBSERVATION",
        "proposal_budget_consumed": 3,
        "selected_primary_count": 0,
        "parameter_set_count": 0,
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        "decision": V3_REGISTER_DECISION,
        "authorizes_timestamp_coverage_audit": True,
        "authorizes_market_numeric_value_inspection": False,
        "authorizes_return_testing": False,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field_name in (
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V3MechanismProposalRegister(
        **payload,
        register_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_mechanism_proposal_register(
    register: V3MechanismProposalRegister,
) -> bool:
    return register.register_evidence_hash == universe_evidence_hash(
        register.model_dump(exclude={"register_evidence_hash"})
    )
