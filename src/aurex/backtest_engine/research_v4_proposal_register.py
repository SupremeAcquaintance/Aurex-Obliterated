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

V4_PROPOSAL_REGISTER_SCHEMA_VERSION = (
    "aurex-v4-independent-mechanism-proposal-register-v1"
)
V4_PROPOSAL_IDS = [
    "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE",
    "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
]
V4_REGISTER_DECISION = (
    "FREEZE_TWO_PROPOSALS_LEAVE_ONE_SLOT_UNUSED_FOR_NO_RETURN_FEASIBILITY"
)


class V4ProposalSource(BaseModel):
    source_id: str = Field(pattern=r"^[A-Z0-9_]{5,100}$")
    title: str = Field(min_length=10, max_length=400)
    authors_or_publisher: list[str] = Field(min_length=1)
    publication_or_revision_date: str | None
    accessed_at: datetime
    source_kind: Literal[
        "PEER_REVIEWED_ARTICLE",
        "OFFICIAL_EXCHANGE_DOCUMENTATION",
        "OFFICIAL_EXCHANGE_DATA_ARCHIVE",
        "INDEPENDENT_MARKET_DATA_DOCUMENTATION",
    ]
    url: str = Field(min_length=20, max_length=1200)
    supported_claims: list[str] = Field(min_length=2)
    explicit_limitations: list[str] = Field(min_length=1)
    historical_truth_scope: Literal[
        "DATED_RESEARCH_EVIDENCE",
        "CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF",
        "VERSIONED_ARCHIVE_OR_CAPTURE_DOCUMENTATION",
    ]
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
        "explicit_limitations",
        "aurex_market_values_used",
        "aurex_return_metrics_used",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_source(self) -> V4ProposalSource:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("V4 source URL must be public HTTPS")
        if self.aurex_market_values_used or self.aurex_return_metrics_used:
            raise ValueError("V4 source cannot be selected using Aurex outcomes")
        if (
            self.publication_or_revision_date is None
            and self.historical_truth_scope
            != "CURRENT_DOCUMENTATION_NOT_HISTORICAL_PROOF"
        ):
            raise ValueError("Undated V4 source cannot establish historical truth")
        return self


class V4ProposalSourceFeasibilityContract(BaseModel):
    required_source_products: list[str] = Field(min_length=2)
    exact_non_value_fields: list[str] = Field(min_length=4)
    required_cross_source_bindings: list[str] = Field(min_length=2)
    metadata_census_required: Literal[True] = True
    payload_requests_require_separate_transport_contract: Literal[True] = True
    minimum_complete_calendar_day_fraction: Decimal = Field(gt=0, le=1)
    minimum_complete_calendar_month_fraction: Decimal = Field(gt=0, le=1)
    maximum_unexplained_sequence_gap_events: Literal[0] = 0
    missing_event_policy: str = Field(min_length=80, max_length=1000)
    source_revision_policy: str = Field(min_length=80, max_length=1000)
    prohibited_substitutions: list[str] = Field(min_length=2)
    pre_return_source_stop: str = Field(min_length=100, max_length=1600)
    synthetic_rows_allowed: Literal[False] = False
    market_numeric_values_permitted: Literal[False] = False
    strategy_outcomes_permitted: Literal[False] = False
    return_metrics_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "required_source_products",
        "exact_non_value_fields",
        "required_cross_source_bindings",
        "prohibited_substitutions",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V4ProposalExecutionFeasibilityContract(BaseModel):
    required_venues_or_instruments: list[str] = Field(min_length=1)
    jurisdiction_and_account_requirements: list[str] = Field(min_length=2)
    point_in_time_metadata_requirements: list[str] = Field(min_length=3)
    order_lifecycle_requirements: list[str] = Field(min_length=4)
    financing_and_collateral_requirements: list[str] = Field(min_length=2)
    multi_leg_failure_requirements: list[str] = Field(min_length=3)
    capacity_requirements: list[str] = Field(min_length=2)
    mandatory_risk_controls: list[str] = Field(min_length=3)
    pre_return_execution_stop: str = Field(min_length=100, max_length=1800)
    credentials_permitted_during_feasibility: Literal[False] = False
    private_endpoints_permitted_during_feasibility: Literal[False] = False
    real_orders_permitted_during_feasibility: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "required_venues_or_instruments",
        "jurisdiction_and_account_requirements",
        "point_in_time_metadata_requirements",
        "order_lifecycle_requirements",
        "financing_and_collateral_requirements",
        "multi_leg_failure_requirements",
        "capacity_requirements",
        "mandatory_risk_controls",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V4MechanismProposal(BaseModel):
    proposal_id: Literal[
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE",
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
    ]
    mechanism_name: str = Field(min_length=10, max_length=240)
    economic_premise: str = Field(min_length=120, max_length=2400)
    ex_ante_payoff_direction: str = Field(min_length=100, max_length=1800)
    economic_reason_edge_might_persist: list[str] = Field(min_length=2)
    exact_point_in_time_data_requirements: list[str] = Field(min_length=5)
    execution_path: str = Field(min_length=120, max_length=2200)
    principal_risks: list[str] = Field(min_length=5)
    pre_return_falsification_condition: str = Field(
        min_length=120,
        max_length=1800,
    )
    independence_from_blocked_lineages: list[str] = Field(min_length=3)
    primary_sources: list[V4ProposalSource] = Field(min_length=3)
    source_feasibility_contract: V4ProposalSourceFeasibilityContract
    execution_feasibility_contract: V4ProposalExecutionFeasibilityContract
    preliminary_fit: Literal[
        "REQUIRES_SYNCHRONIZED_MULTI_VENUE_BBO_AND_INVENTORY_FOUNDATION",
        "REQUIRES_OPTION_CHAIN_QUOTE_HEDGE_MARGIN_AND_SETTLEMENT_FOUNDATION",
    ]
    parameter_sets_defined: list[str] = Field(default_factory=list)
    market_numeric_fields_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    disposition: Literal[
        "REGISTER_FOR_SEPARATE_CRASH_SAFE_NO_RETURN_FEASIBILITY"
    ] = "REGISTER_FOR_SEPARATE_CRASH_SAFE_NO_RETURN_FEASIBILITY"

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "economic_reason_edge_might_persist",
        "exact_point_in_time_data_requirements",
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
    def validate_proposal(self) -> V4MechanismProposal:
        if (
            self.parameter_sets_defined
            or self.market_numeric_fields_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V4 proposal must predate parameters and outcomes")
        source_ids = {source.source_id for source in self.primary_sources}
        if len(source_ids) != len(self.primary_sources):
            raise ValueError("V4 proposal source IDs are not unique")
        if not any(
            source.source_kind == "PEER_REVIEWED_ARTICLE"
            for source in self.primary_sources
        ):
            raise ValueError("V4 proposal requires peer-reviewed support")
        if not any(
            source.source_kind
            in {
                "OFFICIAL_EXCHANGE_DOCUMENTATION",
                "OFFICIAL_EXCHANGE_DATA_ARCHIVE",
            }
            for source in self.primary_sources
        ):
            raise ValueError("V4 proposal requires an official exchange source")
        if len({urlparse(source.url).hostname for source in self.primary_sources}) < 3:
            raise ValueError("V4 proposal requires three independent source hosts")
        return self


class V4ScreenedOutTheory(BaseModel):
    theory_id: str = Field(pattern=r"^[A-Z0-9_]{5,100}$")
    disposition: Literal[
        "NOT_REGISTERED_RELATED_TO_REGISTERED_PROPOSAL",
        "NOT_REGISTERED_EXECUTION_ACCESS_NOT_CREDIBLE",
        "NOT_REGISTERED_RETIRED_LINEAGE_OVERLAP",
    ]
    reason: str = Field(min_length=80, max_length=1000)
    return_metrics_calculated: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("return_metrics_calculated")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def reject_outcomes(self) -> V4ScreenedOutTheory:
        if self.return_metrics_calculated:
            raise ValueError("Screened-out V4 theory cannot contain outcomes")
        return self


class V4MechanismProposalRegister(BaseModel):
    schema_version: Literal[
        "aurex-v4-independent-mechanism-proposal-register-v1"
    ] = V4_PROPOSAL_REGISTER_SCHEMA_VERSION
    register_id: Literal["v4-independent-mechanism-proposals-v1"] = (
        "v4-independent-mechanism-proposals-v1"
    )
    register_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_FEASIBILITY_OBSERVATION"] = (
        "FROZEN_PRE_FEASIBILITY_OBSERVATION"
    )
    discovery_charter_evidence_hash: str
    builder_contract_hash: str
    proposals: list[V4MechanismProposal] = Field(min_length=2, max_length=2)
    screened_out_theories: list[V4ScreenedOutTheory] = Field(min_length=3)
    maximum_proposal_budget: Literal[3] = 3
    proposal_budget_consumed: Literal[2] = 2
    proposal_budget_unused: Literal[1] = 1
    selected_primary_count: Literal[0] = 0
    parameter_set_count: Literal[0] = 0
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    decision: Literal[
        "FREEZE_TWO_PROPOSALS_LEAVE_ONE_SLOT_UNUSED_FOR_NO_RETURN_FEASIBILITY"
    ] = V4_REGISTER_DECISION
    authorizes_network_requests: Literal[False] = False
    requires_separate_transport_contract_before_network: Literal[True] = True
    authorizes_market_numeric_value_inspection: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development_outcomes: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=8)
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
    def validate_register(self) -> V4MechanismProposalRegister:
        if [proposal.proposal_id for proposal in self.proposals] != V4_PROPOSAL_IDS:
            raise ValueError("V4 proposal order or identity changed")
        if (
            self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V4 register must contain no outcomes")
        screened_ids = {
            theory.theory_id for theory in self.screened_out_theories
        }
        if len(screened_ids) != len(self.screened_out_theories):
            raise ValueError("V4 screened-out theory IDs are not unique")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"register_evidence_hash"})
        )
        if self.register_evidence_hash != expected_hash:
            raise ValueError("V4 proposal register hash does not match")
        return self


def build_v4_mechanism_proposal_register(
    **values,
) -> V4MechanismProposalRegister:
    payload = {
        "schema_version": V4_PROPOSAL_REGISTER_SCHEMA_VERSION,
        "register_id": "v4-independent-mechanism-proposals-v1",
        "register_version": "1.0.0",
        "status": "FROZEN_PRE_FEASIBILITY_OBSERVATION",
        "maximum_proposal_budget": 3,
        "proposal_budget_consumed": 2,
        "proposal_budget_unused": 1,
        "selected_primary_count": 0,
        "parameter_set_count": 0,
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        "decision": V4_REGISTER_DECISION,
        "authorizes_network_requests": False,
        "requires_separate_transport_contract_before_network": True,
        "authorizes_market_numeric_value_inspection": False,
        "authorizes_return_testing": False,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_development_outcomes": False,
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
    return V4MechanismProposalRegister(
        **payload,
        register_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_mechanism_proposal_register(
    register: V4MechanismProposalRegister,
) -> bool:
    return register.register_evidence_hash == universe_evidence_hash(
        register.model_dump(exclude={"register_evidence_hash"})
    )
