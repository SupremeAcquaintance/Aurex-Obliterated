from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_CAPABILITY_AUDIT_SCHEMA_VERSION = (
    "aurex-v2-independent-mechanism-capability-audit-v1"
)
V2_REQUIRED_LOCAL_CAPABILITIES = [
    "audited_spot_ohlcv",
    "collateral_and_margin_state_model",
    "derivatives_fee_schedule_history",
    "funding_settlement_engine",
    "historical_perpetual_funding",
    "liquidation_and_adl_model",
    "paired_spot_perpetual_execution",
    "perpetual_contract_metadata_history",
    "perpetual_mark_and_index_history",
    "point_in_time_spot_perpetual_basis",
    "production_derivatives_adapter",
    "spot_perpetual_reconciliation",
]
V2_FOUNDATION_EXIT_CRITERIA = [
    "canonical_checksummed_point_in_time_dataset_bundle",
    "contract_listing_delisting_and_rule_history",
    "deterministic_collateral_margin_and_liquidation_engine",
    "deterministic_funding_cashflow_engine",
    "explicit_fee_borrow_slippage_and_basis_costs",
    "missing_stale_and_dislocated_leg_failure_semantics",
    "paired_leg_order_partial_fill_cancel_and_rollback_semantics",
    "research_only_adapter_boundary_with_live_submission_disabled",
    "spot_perpetual_symbol_and_timestamp_alignment_audit",
    "venue_adl_insurance_and_default_risk_register",
]


class V2CapabilityFinding(BaseModel):
    capability_id: str = Field(min_length=1, max_length=128)
    status: Literal["READY", "PARTIAL", "ABSENT", "INTENTIONALLY_DISABLED"]
    evidence: str = Field(min_length=20, max_length=2000)
    blocking_reason: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_finding(self) -> V2CapabilityFinding:
        if self.status == "READY" and self.blocking_reason is not None:
            raise ValueError("Ready V2 capability cannot carry a blocking reason")
        if self.status != "READY" and self.blocking_reason is None:
            raise ValueError("Unready V2 capability requires a blocking reason")
        return self


class V2ExternalSurface(BaseModel):
    surface_id: str = Field(min_length=1, max_length=128)
    official_source_url: str = Field(min_length=10, max_length=1000)
    observed_capability: str = Field(min_length=20, max_length=2000)
    local_integration_status: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    proves_strategy_viability: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V2CapabilityAudit(BaseModel):
    schema_version: Literal[
        "aurex-v2-independent-mechanism-capability-audit-v1"
    ] = V2_CAPABILITY_AUDIT_SCHEMA_VERSION
    audit_id: Literal["v2-independent-mechanism-capability-audit-v1"] = (
        "v2-independent-mechanism-capability-audit-v1"
    )
    audit_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NEW_CHARTER"] = "FROZEN_PRE_NEW_CHARTER"
    predecessor_u1_result_evidence_hash: str
    predecessor_u1_theory_screen_evidence_hash: str
    universe_manifest_evidence_hash: str
    contamination_ledger_evidence_hash: str
    local_source_sha256: dict[str, str] = Field(min_length=1)
    local_capabilities: list[V2CapabilityFinding] = Field(
        min_length=12, max_length=12
    )
    external_surfaces: list[V2ExternalSurface] = Field(min_length=3)
    donor_system_derivatives_capability: Literal["ABSENT"] = "ABSENT"
    donor_system_scope: Literal[
        "KALSHI_AND_SPOT_SIGNAL_WORKFLOWS_NOT_DERIVATIVES_FOUNDATION"
    ] = "KALSHI_AND_SPOT_SIGNAL_WORKFLOWS_NOT_DERIVATIVES_FOUNDATION"
    ready_capability_count: int = Field(ge=0)
    blocked_capability_count: int = Field(ge=0)
    decision: Literal[
        "BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER"
    ] = "BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER"
    preferred_mechanism_class: Literal[
        "LOWER_DIRECTIONAL_RISK_BUT_NOT_YET_SELECTED"
    ] = "LOWER_DIRECTIONAL_RISK_BUT_NOT_YET_SELECTED"
    foundation_exit_criteria: list[str]
    authorizes_data_contract_design: Literal[True] = True
    authorizes_market_data_acquisition: Literal[False] = False
    authorizes_strategy_return_calculation: Literal[False] = False
    authorizes_mechanism_selection: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_strategy_eligibility: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    validation_data_loaded: Literal[False] = False
    holdout_data_loaded: Literal[False] = False
    forward_data_loaded: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_tested_mechanisms: Literal[0] = 0
    builder_contract_hash: str
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "predecessor_u1_result_evidence_hash",
        "predecessor_u1_theory_screen_evidence_hash",
        "universe_manifest_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("local_source_sha256")
    @classmethod
    def normalize_source_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            path.strip().replace("\\", "/"): normalize_sha256(evidence_hash)
            for path, evidence_hash in sorted(value.items())
            if path.strip()
        }

    @field_validator(
        "foundation_exit_criteria",
        "strategy_outcome_fields_inspected",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_audit(self) -> V2CapabilityAudit:
        capability_ids = [
            finding.capability_id for finding in self.local_capabilities
        ]
        if (
            capability_ids != V2_REQUIRED_LOCAL_CAPABILITIES
            or len(capability_ids) != len(set(capability_ids))
        ):
            raise ValueError("V2 capability inventory is fixed and uniquely sorted")
        ready = sum(
            finding.status == "READY" for finding in self.local_capabilities
        )
        if (
            self.ready_capability_count != ready
            or self.blocked_capability_count != len(self.local_capabilities) - ready
        ):
            raise ValueError("V2 capability counts do not match findings")
        if self.foundation_exit_criteria != V2_FOUNDATION_EXIT_CRITERIA:
            raise ValueError("V2 foundation exit criteria are fixed")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 capability audit cannot inspect strategy outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("V2 capability-audit hash does not match its evidence")
        return self


def build_v2_capability_audit(**values) -> V2CapabilityAudit:
    payload = {
        "schema_version": V2_CAPABILITY_AUDIT_SCHEMA_VERSION,
        "audit_id": "v2-independent-mechanism-capability-audit-v1",
        "audit_version": "1.0.0",
        "status": "FROZEN_PRE_NEW_CHARTER",
        "donor_system_derivatives_capability": "ABSENT",
        "donor_system_scope": (
            "KALSHI_AND_SPOT_SIGNAL_WORKFLOWS_NOT_DERIVATIVES_FOUNDATION"
        ),
        "decision": (
            "BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER"
        ),
        "preferred_mechanism_class": (
            "LOWER_DIRECTIONAL_RISK_BUT_NOT_YET_SELECTED"
        ),
        "foundation_exit_criteria": V2_FOUNDATION_EXIT_CRITERIA,
        "authorizes_data_contract_design": True,
        "authorizes_market_data_acquisition": False,
        "authorizes_strategy_return_calculation": False,
        "authorizes_mechanism_selection": False,
        "creates_candidate": False,
        "creates_strategy_eligibility": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "validation_data_loaded": False,
        "holdout_data_loaded": False,
        "forward_data_loaded": False,
        "strategy_outcome_fields_inspected": [],
        "return_tested_mechanisms": 0,
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["local_source_sha256"] = dict(
        sorted(payload["local_source_sha256"].items())
    )
    payload["local_capabilities"] = sorted(
        payload["local_capabilities"], key=lambda finding: finding.capability_id
    )
    payload["external_surfaces"] = sorted(
        payload["external_surfaces"], key=lambda surface: surface.surface_id
    )
    payload["foundation_exit_criteria"] = sorted(
        set(payload["foundation_exit_criteria"])
    )
    payload["strategy_outcome_fields_inspected"] = sorted(
        set(payload["strategy_outcome_fields_inspected"])
    )
    ready = sum(
        finding.status == "READY" for finding in payload["local_capabilities"]
    )
    payload["ready_capability_count"] = ready
    payload["blocked_capability_count"] = (
        len(payload["local_capabilities"]) - ready
    )
    return V2CapabilityAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_capability_audit(audit: V2CapabilityAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
