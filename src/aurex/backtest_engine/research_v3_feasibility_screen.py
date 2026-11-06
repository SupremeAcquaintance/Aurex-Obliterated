from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_FEASIBILITY_SCREEN_SCHEMA_VERSION = (
    "aurex-v3-mechanism-feasibility-screen-v1"
)
V3_FEASIBILITY_PROPOSAL_IDS = [
    "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
    "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
    "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
]
V3_FEASIBILITY_DECISION = "SELECT_ZERO_V3_PRIMARY_MECHANISMS"
V3_FEASIBILITY_NEXT_DECISION = (
    "CLOSE_V3_AND_REQUIRE_SEPARATELY_FROZEN_V4_DISCOVERY_CHARTER"
)


class V3FeasibilityDisposition(BaseModel):
    proposal_id: Literal[
        "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE",
        "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY",
        "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION",
    ]
    mechanism_name: str = Field(min_length=5, max_length=200)
    terminal_evidence_artifact: str = Field(min_length=20, max_length=500)
    terminal_evidence_hash: str
    formal_status: Literal[
        "REJECTED_EXECUTION_AND_METADATA_FEASIBILITY",
        "STOPPED_TRANSPORT_UNRESOLVED",
        "REJECTED_HISTORICAL_EVIDENCE_UNAVAILABLE",
    ]
    qualified_for_primary_selection: Literal[False] = False
    reason_codes: list[str] = Field(min_length=2)
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
    def validate_disposition(self) -> V3FeasibilityDisposition:
        expected = {
            "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE": (
                "REJECTED_EXECUTION_AND_METADATA_FEASIBILITY",
                "data/evidence/v3_p01_execution_feasibility_result_v1.json",
            ),
            "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY": (
                "STOPPED_TRANSPORT_UNRESOLVED",
                "data/evidence/v3_p02_payload_pilot_stop_result_v1.json",
            ),
            "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION": (
                "REJECTED_HISTORICAL_EVIDENCE_UNAVAILABLE",
                "data/evidence/v3_p03_source_audit_stop_result_v1.json",
            ),
        }[self.proposal_id]
        if (
            self.formal_status != expected[0]
            or self.terminal_evidence_artifact != expected[1]
        ):
            raise ValueError("V3 feasibility disposition lineage changed")
        if (
            self.parameter_sets_defined
            or self.market_numeric_values_inspected
            or self.strategy_outcomes_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3 feasibility disposition may contain no outcomes")
        return self


class V3MechanismFeasibilityScreen(BaseModel):
    schema_version: Literal[
        "aurex-v3-mechanism-feasibility-screen-v1"
    ] = V3_FEASIBILITY_SCREEN_SCHEMA_VERSION
    screen_id: Literal["v3-mechanism-feasibility-screen-v1"] = (
        "v3-mechanism-feasibility-screen-v1"
    )
    screen_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION"] = (
        "FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    v3p01_terminal_evidence_hash: str
    v3p02_terminal_evidence_hash: str
    v3p03_terminal_evidence_hash: str
    builder_contract_hash: str
    dispositions: list[V3FeasibilityDisposition] = Field(
        min_length=3,
        max_length=3,
    )
    selection_rule: Literal[
        "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_PRIMARY_SELECTION"
    ] = "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_PRIMARY_SELECTION"
    selected_primary_proposal_id: None = None
    selected_primary_count: Literal[0] = 0
    decision: Literal[
        "SELECT_ZERO_V3_PRIMARY_MECHANISMS"
    ] = V3_FEASIBILITY_DECISION
    next_decision: Literal[
        "CLOSE_V3_AND_REQUIRE_SEPARATELY_FROZEN_V4_DISCOVERY_CHARTER"
    ] = V3_FEASIBILITY_NEXT_DECISION
    v3_closed: Literal[True] = True
    authorizes_v3_retry_or_amendment: Literal[False] = False
    authorizes_full_payload_acquisition: Literal[False] = False
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
    limitations: list[str] = Field(min_length=8)
    screen_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "v3p01_terminal_evidence_hash",
        "v3p02_terminal_evidence_hash",
        "v3p03_terminal_evidence_hash",
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
    def validate_screen(self) -> V3MechanismFeasibilityScreen:
        if [item.proposal_id for item in self.dispositions] != (
            V3_FEASIBILITY_PROPOSAL_IDS
        ):
            raise ValueError("V3 feasibility proposal set or order changed")
        if any(
            item.qualified_for_primary_selection for item in self.dispositions
        ):
            raise ValueError("V3 zero-selection screen contains a qualified primary")
        terminal_hashes = {
            "V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE": (
                self.v3p01_terminal_evidence_hash
            ),
            "V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY": (
                self.v3p02_terminal_evidence_hash
            ),
            "V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION": (
                self.v3p03_terminal_evidence_hash
            ),
        }
        if any(
            item.terminal_evidence_hash
            != terminal_hashes[item.proposal_id]
            for item in self.dispositions
        ):
            raise ValueError("V3 feasibility terminal hashes do not reconcile")
        if (
            self.market_numeric_values_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V3 feasibility screen may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"screen_evidence_hash"})
        )
        if self.screen_evidence_hash != expected_hash:
            raise ValueError("V3 feasibility screen hash does not match")
        return self


def build_v3_mechanism_feasibility_screen(
    **values,
) -> V3MechanismFeasibilityScreen:
    payload = {
        "schema_version": V3_FEASIBILITY_SCREEN_SCHEMA_VERSION,
        "screen_id": "v3-mechanism-feasibility-screen-v1",
        "screen_version": "1.0.0",
        "status": "FROZEN_COMPLETE_NO_RETURN_ZERO_SELECTION",
        "selection_rule": (
            "EVERY_PREDECLARED_FEASIBILITY_GATE_MUST_PASS_BEFORE_"
            "PRIMARY_SELECTION"
        ),
        "selected_primary_proposal_id": None,
        "selected_primary_count": 0,
        "decision": V3_FEASIBILITY_DECISION,
        "next_decision": V3_FEASIBILITY_NEXT_DECISION,
        "v3_closed": True,
        "authorizes_v3_retry_or_amendment": False,
        "authorizes_full_payload_acquisition": False,
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
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3MechanismFeasibilityScreen(
        **payload,
        screen_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_mechanism_feasibility_screen(
    screen: V3MechanismFeasibilityScreen,
) -> bool:
    return screen.screen_evidence_hash == universe_evidence_hash(
        screen.model_dump(exclude={"screen_evidence_hash"})
    )
