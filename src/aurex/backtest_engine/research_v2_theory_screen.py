from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_THEORY_SCREEN_SCHEMA_VERSION = (
    "aurex-v2-lower-directional-risk-theory-screen-v1"
)
V2_THEORY_PROPOSAL_IDS = [
    "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY",
    "P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS",
    "P03_NEGATIVE_FUNDING_REVERSE_CARRY",
]
V2_THEORY_SELECTION_RULES = [
    "ASSESS_THEORY_DATA_EXECUTION_INDEPENDENCE_AND_COMPLEXITY_WITHOUT_RETURNS",
    "DO_NOT_DEFINE_OR_COMPARE_PARAMETER_SETS",
    "DO_NOT_INSPECT_AUREX_MARKET_VALUES_SIGNALS_TRADES_OR_STRATEGY_OUTCOMES",
    "PREFER_LOWER_FIRST_ORDER_DIRECTIONAL_EXPOSURE",
    "PREFER_THE_FEWEST_UNMODELED_EXECUTION_AND_FINANCING_DEPENDENCIES",
    "RELATED_PREMISES_CANNOT_BECOME_A_SECOND_SELECTABLE_PRIMARY",
    "REJECT_A_PRIMARY_THAT_REQUIRES_POINT_IN_TIME_SPOT_BORROW_HISTORY",
    "REQUIRE_AT_LEAST_TWO_ALLOWED_PRIMARY_OR_PEER_REVIEWED_SOURCES",
    "REQUIRE_SOURCE_FEASIBILITY_ACROSS_THE_FROZEN_COMPLETE_SYMBOL_SET",
    "REQUIRE_THE_SELECTED_DIRECTION_TO_FIT_THE_SYNTHETIC_PAIRED_LEG_FOUNDATION",
    "SELECTION_AUTHORIZES_PROTOCOL_DESIGN_ONLY",
    "TIE_BREAK_BY_PROPOSAL_ID",
]
V2_THEORY_NEXT_DECISION = (
    "FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
)


class V2TheorySource(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=5, max_length=300)
    authors_or_publisher: list[str] = Field(min_length=1)
    publication_or_revision_date: str | None = Field(
        default=None, min_length=10, max_length=10
    )
    accessed_at: datetime
    source_kind: Literal[
        "OFFICIAL_EXCHANGE_DOCUMENTATION",
        "PEER_REVIEWED_ARTICLE",
        "INSTITUTIONAL_WORKING_PAPER",
    ]
    url: str = Field(min_length=10, max_length=1000)
    supported_claims: list[str] = Field(min_length=1)
    aurex_return_metrics_used: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_id", "title", "url")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("accessed_at")
    @classmethod
    def normalize_accessed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("publication_or_revision_date")
    @classmethod
    def validate_publication_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        date.fromisoformat(normalized)
        return normalized

    @field_validator(
        "authors_or_publisher",
        "supported_claims",
        "aurex_return_metrics_used",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("V2 theory source lists must contain unique values")
        return normalized

    @model_validator(mode="after")
    def validate_source(self) -> V2TheorySource:
        if not self.url.startswith("https://"):
            raise ValueError("V2 theory source URL must use HTTPS")
        if self.aurex_return_metrics_used:
            raise ValueError("V2 theory sources cannot use Aurex return metrics")
        return self


class V2TheoryFeasibility(BaseModel):
    theory_support: Literal["SUPPORTED", "INSUFFICIENT"]
    point_in_time_data: Literal[
        "FEASIBLE_PENDING_FROZEN_FULL_ACQUISITION",
        "BLOCKED_BY_POINT_IN_TIME_BORROW_HISTORY",
    ]
    execution_fit: Literal[
        "SYNTHETICALLY_PROVEN_RESEARCH_ONLY",
        "UNMODELED_REVERSE_CARRY_AND_SPOT_BORROW",
    ]
    first_order_directional_risk: Literal[
        "LOWER_THAN_UNHEDGED_SPOT_BUT_NOT_ZERO"
    ]
    fits_synthetic_long_spot_short_perp_foundation: bool
    requires_spot_borrowing: bool
    related_to_selected_primary: bool

    model_config = ConfigDict(extra="forbid")


class V2MechanismTheoryProposal(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=128)
    mechanism_name: str = Field(min_length=5, max_length=200)
    economic_premise: str = Field(min_length=50, max_length=2500)
    ex_ante_payoff_direction: str = Field(min_length=30, max_length=1500)
    exact_point_in_time_data_requirements: list[str] = Field(min_length=1)
    historical_metadata_requirements: list[str] = Field(min_length=1)
    paired_execution_path: str = Field(min_length=30, max_length=1500)
    principal_risks: list[str] = Field(min_length=1)
    falsification_condition: str = Field(min_length=30, max_length=1500)
    primary_sources: list[V2TheorySource] = Field(min_length=2)
    feasibility: V2TheoryFeasibility
    independent_of_retired_aurex_lineages: Literal[True] = True
    parameter_sets_defined: list[str] = Field(default_factory=list)
    market_data_numeric_fields_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    nonselection_reasons: list[str] = Field(default_factory=list)
    disposition: Literal[
        "SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN",
        "DEFER_AS_NONSELECTABLE_RELATED_DIAGNOSTIC",
        "REJECT_CURRENT_CHARTER_BORROW_AND_EXECUTION_INFEASIBLE",
    ]
    decision_rationale: str = Field(min_length=30, max_length=1500)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "proposal_id",
        "mechanism_name",
        "economic_premise",
        "ex_ante_payoff_direction",
        "paired_execution_path",
        "falsification_condition",
        "decision_rationale",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "exact_point_in_time_data_requirements",
        "historical_metadata_requirements",
        "principal_risks",
        "parameter_sets_defined",
        "market_data_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "nonselection_reasons",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_proposal(self) -> V2MechanismTheoryProposal:
        source_ids = [source.source_id for source in self.primary_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("V2 proposal source IDs must be unique")
        if (
            self.parameter_sets_defined
            or self.market_data_numeric_fields_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V2 theory proposal cannot contain data outcomes")

        selected = self.disposition == "SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
        if selected:
            if (
                self.proposal_id
                != "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
                or not self.feasibility.fits_synthetic_long_spot_short_perp_foundation
                or self.feasibility.requires_spot_borrowing
                or self.feasibility.related_to_selected_primary
                or self.nonselection_reasons
            ):
                raise ValueError(
                    "Selected V2 proposal must fit the frozen paired-leg foundation"
                )
        elif not self.nonselection_reasons:
            raise ValueError("Nonselected V2 proposals require explicit reasons")

        if (
            self.proposal_id == "P03_NEGATIVE_FUNDING_REVERSE_CARRY"
            and (
                not self.feasibility.requires_spot_borrowing
                or self.feasibility.fits_synthetic_long_spot_short_perp_foundation
                or self.disposition
                != "REJECT_CURRENT_CHARTER_BORROW_AND_EXECUTION_INFEASIBLE"
            )
        ):
            raise ValueError("Reverse carry must remain borrow/execution blocked")
        return self


class V2MechanismTheoryScreen(BaseModel):
    schema_version: Literal[
        "aurex-v2-lower-directional-risk-theory-screen-v1"
    ] = V2_THEORY_SCREEN_SCHEMA_VERSION
    screen_id: Literal["v2-lower-directional-risk-theory-screen-v1"] = (
        "v2-lower-directional-risk-theory-screen-v1"
    )
    screen_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_NO_RETURN_EVIDENCE"] = "FROZEN_NO_RETURN_EVIDENCE"
    discovery_charter_evidence_hash: str
    capability_audit_evidence_hash: str
    source_census_result_evidence_hash: str
    acquisition_protocol_evidence_hash: str
    pilot_result_evidence_hash: str
    derivatives_foundation_protocol_evidence_hash: str
    derivatives_foundation_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    proposals: list[V2MechanismTheoryProposal] = Field(min_length=3, max_length=3)
    selection_rules: list[str]
    selected_proposal_id: Literal[
        "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    ] = "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    next_decision: Literal[
        "FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
    ] = V2_THEORY_NEXT_DECISION
    proposal_budget_consumed: Literal[3] = 3
    selected_primary_count: Literal[1] = 1
    return_tested_mechanism_count: Literal[0] = 0
    parameter_set_count: Literal[0] = 0
    market_data_numeric_fields_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    preexisting_successor_artifacts: list[str] = Field(default_factory=list)
    authorizes_full_acquisition: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=5)
    screen_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "capability_audit_evidence_hash",
        "source_census_result_evidence_hash",
        "acquisition_protocol_evidence_hash",
        "pilot_result_evidence_hash",
        "derivatives_foundation_protocol_evidence_hash",
        "derivatives_foundation_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "screen_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "selection_rules",
        "market_data_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_successor_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_screen(self) -> V2MechanismTheoryScreen:
        if [proposal.proposal_id for proposal in self.proposals] != (
            V2_THEORY_PROPOSAL_IDS
        ):
            raise ValueError("V2 theory proposal set or order changed")
        selected = [
            proposal
            for proposal in self.proposals
            if proposal.disposition == "SELECT_FOR_FULL_DATA_AND_PROTOCOL_DESIGN"
        ]
        if len(selected) != 1 or selected[0].proposal_id != self.selected_proposal_id:
            raise ValueError("V2 theory screen must select exactly the fixed primary")
        if self.selection_rules != sorted(V2_THEORY_SELECTION_RULES):
            raise ValueError("V2 theory selection rules changed")
        if (
            self.market_data_numeric_fields_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
            or self.preexisting_successor_artifacts
        ):
            raise ValueError("V2 theory screen cannot contain data outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"screen_evidence_hash"})
        )
        if self.screen_evidence_hash != expected_hash:
            raise ValueError("V2 theory screen hash does not match")
        return self


def build_v2_mechanism_theory_screen(**values) -> V2MechanismTheoryScreen:
    payload = {
        "schema_version": V2_THEORY_SCREEN_SCHEMA_VERSION,
        "screen_id": "v2-lower-directional-risk-theory-screen-v1",
        "screen_version": "1.0.0",
        "status": "FROZEN_NO_RETURN_EVIDENCE",
        "selected_proposal_id": "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY",
        "next_decision": V2_THEORY_NEXT_DECISION,
        "proposal_budget_consumed": 3,
        "selected_primary_count": 1,
        "return_tested_mechanism_count": 0,
        "parameter_set_count": 0,
        "market_data_numeric_fields_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        "preexisting_successor_artifacts": [],
        "authorizes_full_acquisition": False,
        "authorizes_market_data_import": False,
        "authorizes_return_testing": False,
        "creates_candidate": False,
        "opens_development": False,
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
        "selection_rules",
        "market_data_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_successor_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V2MechanismTheoryScreen(
        **payload,
        screen_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_mechanism_theory_screen(
    screen: V2MechanismTheoryScreen,
) -> bool:
    return screen.screen_evidence_hash == universe_evidence_hash(
        screen.model_dump(exclude={"screen_evidence_hash"})
    )
