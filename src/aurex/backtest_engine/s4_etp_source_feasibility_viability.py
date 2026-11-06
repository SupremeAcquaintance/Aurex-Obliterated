from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S4_UNREACHABLE_GATE_IDS = (
    "ACTUAL_PUBLICATION_TIMING_RECONSTRUCTABLE",
    "DAILY_BITCOIN_HOLDINGS_HISTORY_DESCRIPTOR_COMPLETE",
    "DAILY_SHARES_OUTSTANDING_HISTORY_DESCRIPTOR_COMPLETE",
    "FEES_SPLITS_MERGERS_AND_NON_CREATION_CHANGES_RECONSTRUCTABLE",
    "OFFICIAL_ISSUER_DATA_ENDPOINT_CATALOG_COMPLETE",
    "PER_FUND_CASH_IN_KIND_REGIME_DATES_RECONSTRUCTABLE",
)
S4_VIABILITY_STOP = "BLOCK_S4_RUN_PROTOCOL_PASS_CONDITION_UNREACHABLE"
S4_VIABILITY_NEXT = "FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY"


class S4ViabilityBinding(BaseModel):
    path: str = Field(min_length=1)
    file_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class S4EtpSourceFeasibilityViabilityReview(BaseModel):
    schema_version: Literal[
        "aurex-s4-etp-source-feasibility-viability-review-v1"
    ] = "aurex-s4-etp-source-feasibility-viability-review-v1"
    review_id: Literal["s4-etp-source-feasibility-viability-review-v1"] = (
        "s4-etp-source-feasibility-viability-review-v1"
    )
    reviewed_at: datetime
    reviewer_contract_hash: str
    source_bindings: tuple[S4ViabilityBinding, ...] = Field(
        min_length=2, max_length=2
    )
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    protocol_reconstructed_before_review: Literal[True] = True
    network_requests_executed: Literal[0] = 0
    run_authority_consumed: Literal[False] = False
    unreachable_gate_ids: tuple[str, ...] = Field(min_length=6, max_length=6)
    unreachable_gate_count: Literal[6] = 6
    allowed_sec_submission_keys_insufficient: Literal[True] = True
    issuer_page_bodies_forbidden: Literal[True] = True
    sec_filing_bodies_forbidden: Literal[True] = True
    xbrl_fact_endpoints_forbidden: Literal[True] = True
    permitted_sources_cannot_prove_daily_history_descriptors: Literal[True] = True
    permitted_sources_cannot_prove_per_fund_regime_dates: Literal[True] = True
    permitted_sources_cannot_prove_actual_issuer_publication_timing: Literal[True] = (
        True
    )
    protocol_pass_condition_reachable: Literal[False] = False
    protocol_run_permitted_after_review: Literal[False] = False
    etp_time_series_rows_parsed: Literal[0] = 0
    etp_numeric_values_read: Literal[0] = 0
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    source_feasibility_conclusion: Literal[
        "NOT_EVALUATED_PROTOCOL_STOPPED_BEFORE_NETWORK"
    ] = "NOT_EVALUATED_PROTOCOL_STOPPED_BEFORE_NETWORK"
    predictive_edge_conclusion: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    decision: Literal[
        "BLOCK_S4_RUN_PROTOCOL_PASS_CONDITION_UNREACHABLE"
    ] = S4_VIABILITY_STOP
    next_authorization: Literal[
        "FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY"
    ] = S4_VIABILITY_NEXT
    authorizes_protocol_run: Literal[False] = False
    authorizes_protocol_amendment: Literal[False] = False
    authorizes_etp_numeric_payload: Literal[False] = False
    authorizes_market_values: Literal[False] = False
    authorizes_parameters: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    proof: tuple[str, ...] = Field(min_length=7)
    limitations: tuple[str, ...] = Field(min_length=6)
    review_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("reviewed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "reviewer_contract_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "review_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_review(self) -> S4EtpSourceFeasibilityViabilityReview:
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S4 viability bindings must be unique and sorted")
        if self.unreachable_gate_ids != S4_UNREACHABLE_GATE_IDS:
            raise ValueError("S4 unreachable gate proof changed")
        if self.proof != tuple(sorted(set(self.proof))):
            raise ValueError("S4 viability proof must be unique and sorted")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S4 viability limitations must be unique and sorted")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"review_evidence_hash"})
        )
        if self.review_evidence_hash != expected:
            raise ValueError("S4 viability review hash changed")
        return self


class S4EtpSourceFeasibilityViabilityReviewAudit(BaseModel):
    schema_version: Literal[
        "aurex-s4-etp-source-feasibility-viability-review-audit-v1"
    ] = "aurex-s4-etp-source-feasibility-viability-review-audit-v1"
    audit_id: Literal[
        "s4-etp-source-feasibility-viability-review-audit-v1"
    ] = "s4-etp-source-feasibility-viability-review-audit-v1"
    audited_at: datetime
    review_path: Literal[
        "data/evidence/s4_etp_source_feasibility_viability_review_v1.json"
    ] = "data/evidence/s4_etp_source_feasibility_viability_review_v1.json"
    review_file_sha256: str
    review_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    reviewer_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    unreachable_gate_count: Literal[6] = 6
    network_requests_observed: Literal[0] = 0
    run_authority_consumed: Literal[False] = False
    etp_numeric_values_observed: Literal[0] = 0
    btc_market_values_observed: Literal[0] = 0
    returns_observed: Literal[0] = 0
    orders_observed: Literal[0] = 0
    source_feasibility_not_inferred: Literal[True] = True
    predictive_edge_not_inferred: Literal[True] = True
    decision: Literal[
        "CONFIRM_S4_RUN_BLOCKED_PROTOCOL_PASS_CONDITION_UNREACHABLE"
    ] = "CONFIRM_S4_RUN_BLOCKED_PROTOCOL_PASS_CONDITION_UNREACHABLE"
    next_authorization: Literal[
        "FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY"
    ] = S4_VIABILITY_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "review_file_sha256",
        "review_evidence_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "reviewer_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S4EtpSourceFeasibilityViabilityReviewAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S4 viability audit hash changed")
        return self


def build_hashed(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump(mode="json")
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def audit_s4_viability_review(
    review: S4EtpSourceFeasibilityViabilityReview,
) -> bool:
    try:
        S4EtpSourceFeasibilityViabilityReview.model_validate(
            review.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s4_viability_review_audit(
    audit: S4EtpSourceFeasibilityViabilityReviewAudit,
) -> bool:
    try:
        S4EtpSourceFeasibilityViabilityReviewAudit.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True
