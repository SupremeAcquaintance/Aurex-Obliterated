from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V4_FEASIBILITY_SCREEN_SCHEMA_VERSION = (
    "aurex-v4-mechanism-feasibility-screen-v1"
)
V4_FEASIBILITY_PROPOSAL_IDS = [
    "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE",
    "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
]
V4_FEASIBILITY_DECISION = "SELECT_ZERO_V4_PRIMARY_MECHANISMS"
V4_FEASIBILITY_NEXT_DECISION = (
    "CLOSE_V4_AND_REQUIRE_CAPABILITY_GAP_REVIEW_BEFORE_SUCCESSOR_DISCOVERY"
)


class V4FeasibilityDisposition(BaseModel):
    proposal_id: Literal[
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE",
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM",
    ]
    mechanism_name: str = Field(min_length=5, max_length=240)
    terminal_evidence_artifact: str = Field(min_length=20, max_length=500)
    terminal_evidence_hash: str
    formal_status: Literal[
        "REJECTED_SOURCE_AND_EXECUTION_FEASIBILITY",
        "STOPPED_METADATA_TRANSPORT_BUDGET",
    ]
    qualified_for_primary_selection: Literal[False] = False
    reason_codes: list[str] = Field(min_length=3)
    transport_observation_manifest: dict[str, int] = Field(
        default_factory=dict
    )
    parameter_sets_defined: list[str] = Field(default_factory=list)
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcomes_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("terminal_evidence_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "reason_codes",
        "parameter_sets_defined",
        "market_numeric_values_inspected",
        "strategy_outcomes_inspected",
        "return_metrics_calculated",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_disposition(self) -> V4FeasibilityDisposition:
        expected = {
            "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE": (
                "REJECTED_SOURCE_AND_EXECUTION_FEASIBILITY",
                "data/evidence/v4_p01_terminal_audit_addendum_v1.json",
                {},
            ),
            "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM": (
                "STOPPED_METADATA_TRANSPORT_BUDGET",
                "data/evidence/v4_p02_source_census_transport_stop_v1.json",
                {
                    "accepted_response_body_bytes": 0,
                    "attempts_used": 1,
                    "dataset_head_attempts_used": 0,
                    "declared_metadata_content_length_bytes": 203_310_405,
                    "http_hops_used": 1,
                    "metadata_body_budget_bytes": 8_388_608,
                },
            ),
        }[self.proposal_id]
        if (
            self.formal_status != expected[0]
            or self.terminal_evidence_artifact != expected[1]
            or self.transport_observation_manifest != expected[2]
        ):
            raise ValueError("V4 feasibility disposition lineage changed")
        if (
            self.parameter_sets_defined
            or self.market_numeric_values_inspected
            or self.strategy_outcomes_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V4 feasibility disposition may contain no outcomes")
        return self


class V4MechanismFeasibilityScreen(BaseModel):
    schema_version: Literal[
        "aurex-v4-mechanism-feasibility-screen-v1"
    ] = V4_FEASIBILITY_SCREEN_SCHEMA_VERSION
    screen_id: Literal["v4-mechanism-feasibility-screen-v1"] = (
        "v4-mechanism-feasibility-screen-v1"
    )
    screen_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION"] = (
        "FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    v4p01_terminal_addendum_evidence_hash: str
    v4p02_contract_evidence_hash: str
    v4p02_terminal_stop_evidence_hash: str
    v4p02_request_journal_hash: str
    builder_contract_hash: str
    dispositions: list[V4FeasibilityDisposition] = Field(
        min_length=2,
        max_length=2,
    )
    selection_rule: Literal[
        "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_PRIMARY_SELECTION"
    ] = "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_PRIMARY_SELECTION"
    selected_primary_proposal_id: None = None
    selected_primary_count: Literal[0] = 0
    decision: Literal[
        "SELECT_ZERO_V4_PRIMARY_MECHANISMS"
    ] = V4_FEASIBILITY_DECISION
    next_decision: Literal[
        "CLOSE_V4_AND_REQUIRE_CAPABILITY_GAP_REVIEW_BEFORE_SUCCESSOR_DISCOVERY"
    ] = V4_FEASIBILITY_NEXT_DECISION
    v4_closed: Literal[True] = True
    authorizes_v4_retry_continuation_or_amendment: Literal[False] = False
    authorizes_network_requests: Literal[False] = False
    authorizes_payload_acquisition: Literal[False] = False
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
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=9)
    screen_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "v4p01_terminal_addendum_evidence_hash",
        "v4p02_contract_evidence_hash",
        "v4p02_terminal_stop_evidence_hash",
        "v4p02_request_journal_hash",
        "builder_contract_hash",
        "screen_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "market_numeric_values_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_screen(self) -> V4MechanismFeasibilityScreen:
        if [item.proposal_id for item in self.dispositions] != (
            V4_FEASIBILITY_PROPOSAL_IDS
        ):
            raise ValueError("V4 feasibility proposal set or order changed")
        if any(
            item.qualified_for_primary_selection for item in self.dispositions
        ):
            raise ValueError("V4 zero-selection screen contains a qualified primary")
        terminal_hashes = {
            "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE": (
                self.v4p01_terminal_addendum_evidence_hash
            ),
            "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM": (
                self.v4p02_terminal_stop_evidence_hash
            ),
        }
        if any(
            item.terminal_evidence_hash
            != terminal_hashes[item.proposal_id]
            for item in self.dispositions
        ):
            raise ValueError("V4 feasibility terminal hashes do not reconcile")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V4 feasibility screen may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"screen_evidence_hash"})
        )
        if self.screen_evidence_hash != expected_hash:
            raise ValueError("V4 feasibility screen hash does not match")
        return self


def build_v4_mechanism_feasibility_screen(
    **values,
) -> V4MechanismFeasibilityScreen:
    payload = {
        "schema_version": V4_FEASIBILITY_SCREEN_SCHEMA_VERSION,
        "screen_id": "v4-mechanism-feasibility-screen-v1",
        "screen_version": "1.0.0",
        "status": "FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION",
        "selection_rule": (
            "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_"
            "PRIMARY_SELECTION"
        ),
        "selected_primary_proposal_id": None,
        "selected_primary_count": 0,
        "decision": V4_FEASIBILITY_DECISION,
        "next_decision": V4_FEASIBILITY_NEXT_DECISION,
        "v4_closed": True,
        "authorizes_v4_retry_continuation_or_amendment": False,
        "authorizes_network_requests": False,
        "authorizes_payload_acquisition": False,
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
        "market_numeric_values_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V4MechanismFeasibilityScreen(
        **payload,
        screen_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_mechanism_feasibility_screen(
    screen: V4MechanismFeasibilityScreen,
) -> bool:
    return screen.screen_evidence_hash == universe_evidence_hash(
        screen.model_dump(exclude={"screen_evidence_hash"})
    )
