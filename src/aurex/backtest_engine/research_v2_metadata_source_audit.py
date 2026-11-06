from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2_METADATA_REQUIREMENT_IDS,
    V2_METADATA_SOURCE_IDS,
)
from aurex.backtest_engine.research_v2_metadata_source_contract_v1_1 import (
    V2P01MetadataSourceContractV1_1,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_METADATA_AUDIT_SCHEMA_VERSION = (
    "aurex-v2-p01-metadata-source-audit-v1.1"
)
V2_METADATA_PASS_DECISION = (
    "PERMIT_P01_PROTOCOL_DESIGN_WITH_MANDATORY_METADATA_OVERRIDES"
)
V2_METADATA_REQUIREMENT_STATUS = {
    "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS": "READY_HISTORICAL_ARCHIVE",
    "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES": (
        "READY_HISTORICAL_ARCHIVE"
    ),
    "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE": (
        "PARTIAL_ARCHIVE_COVERAGE_REQUIRES_CONTINUITY_GATE"
    ),
    "HISTORICAL_FUTURES_ORDER_FILTERS": "CURRENT_ONLY_NOT_HISTORICAL",
    "HISTORICAL_SPOT_ORDER_FILTERS": "CURRENT_ONLY_NOT_HISTORICAL",
    "HISTORICAL_ACCOUNT_FEE_TIER": (
        "CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL"
    ),
    "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS": (
        "CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL"
    ),
    "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES": (
        "CURRENT_OR_UNAVAILABLE_NOT_HISTORICAL"
    ),
}
V2_METADATA_MANDATORY_PROTOCOL_REQUIREMENTS = [
    "CAPTURE_CURRENT_SPOT_AND_FUTURES_FILTER_SNAPSHOTS_AS_PROXIES_ONLY",
    "FAIL_CLOSED_ON_ANY_ARCHIVE_LIFECYCLE_OR_CONTINUITY_GAP",
    "FIX_CONSERVATIVE_FEES_SLIPPAGE_AND_AT_LEAST_DOUBLE_COST_STRESS",
    "FIX_CONSERVATIVE_MARGIN_COLLATERAL_LIQUIDATION_AND_ADL_OVERRIDES",
    "MARK_CURRENT_FILTERS_FEES_AND_BRACKETS_AS_NON_HISTORICAL",
    "MODEL_QUANTITIES_AGAINST_BOTH_CURRENT_SPOT_AND_FUTURES_FILTERS",
    "PRESERVE_ZERO_LIQUIDATION_ZERO_ADL_AND_RECONCILIATION_GATES",
    "PROHIBIT_DEVELOPMENT_RESULT_FROM_CREATING_ELIGIBILITY",
    "REQUIRE_SEPARATE_2025_VALIDATION_AND_2026_HOLDOUT_IF_DEVELOPMENT_PASSES",
]

MetadataRequirementStatus = Literal[
    "READY_HISTORICAL_ARCHIVE",
    "PARTIAL_ARCHIVE_COVERAGE_REQUIRES_CONTINUITY_GATE",
    "CURRENT_ONLY_NOT_HISTORICAL",
    "CURRENT_SIGNED_ACCOUNT_ONLY_NOT_HISTORICAL",
    "CURRENT_OR_UNAVAILABLE_NOT_HISTORICAL",
]


class V2MetadataSourceObservation(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    requested_url: str = Field(min_length=10, max_length=1000)
    final_url: str = Field(min_length=10, max_length=1000)
    checked_at: datetime
    http_status: Literal[200, 202]
    content_type: str = Field(min_length=1, max_length=300)
    response_bytes: int = Field(gt=0)
    response_sha256: str
    required_markers: list[str] = Field(min_length=2)
    found_markers: list[str] = Field(min_length=2)
    missing_markers: list[str] = Field(default_factory=list)
    response_body_persisted: Literal[False] = False
    observation_status: Literal["PASS"] = "PASS"

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "source_id",
        "requested_url",
        "final_url",
        "content_type",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("response_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "required_markers",
        "found_markers",
        "missing_markers",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_observation(self) -> V2MetadataSourceObservation:
        if self.source_id not in V2_METADATA_SOURCE_IDS:
            raise ValueError("Unknown V2 metadata observation source")
        for value in (self.requested_url, self.final_url):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("Metadata observations require HTTPS URLs")
        if self.found_markers != self.required_markers or self.missing_markers:
            raise ValueError("Metadata source observation is missing markers")
        return self


class V2MetadataRequirementAssessment(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=128)
    status: MetadataRequirementStatus
    source_ids: list[str] = Field(min_length=1)
    existing_evidence_hashes: list[str] = Field(default_factory=list)
    blocks_direct_historical_replay: bool
    conservative_research_override_permitted: bool
    required_protocol_treatment: Literal[
        "USE_IMMUTABLE_ARCHIVE_AND_AUDIT",
        "FAIL_CLOSED_ON_ANY_LIFECYCLE_OR_CONTINUITY_GAP",
        "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_NON_ELIGIBILITY_LIMITATION",
    ]
    rationale: str = Field(min_length=30, max_length=1500)

    model_config = ConfigDict(extra="forbid")

    @field_validator("requirement_id", "rationale")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_ids")
    @classmethod
    def normalize_source_ids(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @field_validator("existing_evidence_hashes")
    @classmethod
    def normalize_hashes(cls, value: list[str]) -> list[str]:
        return sorted({normalize_sha256(item) for item in value})

    @model_validator(mode="after")
    def validate_assessment(self) -> V2MetadataRequirementAssessment:
        expected_status = V2_METADATA_REQUIREMENT_STATUS.get(self.requirement_id)
        if self.status != expected_status:
            raise ValueError("V2 metadata requirement status changed")
        if not set(self.source_ids).issubset(V2_METADATA_SOURCE_IDS):
            raise ValueError("Metadata assessment references unknown source")
        ready = self.status == "READY_HISTORICAL_ARCHIVE"
        if ready:
            if (
                self.blocks_direct_historical_replay
                or self.conservative_research_override_permitted
                or self.required_protocol_treatment
                != "USE_IMMUTABLE_ARCHIVE_AND_AUDIT"
            ):
                raise ValueError("Ready metadata requirement treatment changed")
        elif self.status == (
            "PARTIAL_ARCHIVE_COVERAGE_REQUIRES_CONTINUITY_GATE"
        ):
            if (
                not self.blocks_direct_historical_replay
                or self.conservative_research_override_permitted
                or self.required_protocol_treatment
                != "FAIL_CLOSED_ON_ANY_LIFECYCLE_OR_CONTINUITY_GAP"
            ):
                raise ValueError("Partial lifecycle treatment changed")
        elif (
            not self.blocks_direct_historical_replay
            or not self.conservative_research_override_permitted
            or self.required_protocol_treatment
            != (
                "FREEZE_CONSERVATIVE_OVERRIDE_AND_RETAIN_"
                "NON_ELIGIBILITY_LIMITATION"
            )
        ):
            raise ValueError("Current-only metadata treatment changed")
        return self


class V2P01MetadataSourceAuditResult(BaseModel):
    schema_version: Literal[
        "aurex-v2-p01-metadata-source-audit-v1.1"
    ] = V2_METADATA_AUDIT_SCHEMA_VERSION
    result_id: Literal["v2-p01-metadata-source-audit-v1.1"] = (
        "v2-p01-metadata-source-audit-v1.1"
    )
    result_version: Literal["1.1.0"] = "1.1.0"
    generated_at: datetime
    status: Literal["COMPLETE_NO_RETURN_METADATA_AUDIT"] = (
        "COMPLETE_NO_RETURN_METADATA_AUDIT"
    )
    metadata_source_contract_evidence_hash: str
    theory_screen_evidence_hash: str
    discovery_charter_evidence_hash: str
    source_census_result_evidence_hash: str
    derivatives_foundation_result_evidence_hash: str
    runner_contract_hash: str
    observations: list[V2MetadataSourceObservation] = Field(
        min_length=4, max_length=4
    )
    requirement_assessments: list[V2MetadataRequirementAssessment] = Field(
        min_length=8, max_length=8
    )
    source_observation_count: Literal[4] = 4
    passed_source_observation_count: Literal[4] = 4
    failed_source_observation_count: Literal[0] = 0
    ready_historical_requirement_count: Literal[2] = 2
    unresolved_historical_requirement_count: Literal[6] = 6
    conservative_override_requirement_count: Literal[5] = 5
    decision: Literal[
        "PERMIT_P01_PROTOCOL_DESIGN_WITH_MANDATORY_METADATA_OVERRIDES"
    ] = V2_METADATA_PASS_DECISION
    mandatory_next_protocol_requirements: list[str]
    credentials_used: Literal[False] = False
    private_endpoint_calls_made: Literal[False] = False
    response_bodies_persisted: Literal[False] = False
    market_data_numeric_values_inspected: Literal[False] = False
    strategy_outcomes_inspected: Literal[False] = False
    return_metrics_calculated: list[str] = Field(default_factory=list)
    authorizes_full_archive_acquisition: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=5)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "metadata_source_contract_evidence_hash",
        "theory_screen_evidence_hash",
        "discovery_charter_evidence_hash",
        "source_census_result_evidence_hash",
        "derivatives_foundation_result_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "mandatory_next_protocol_requirements",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V2P01MetadataSourceAuditResult:
        if [item.source_id for item in self.observations] != (
            V2_METADATA_SOURCE_IDS
        ):
            raise ValueError("V2 metadata observations changed")
        if [item.requirement_id for item in self.requirement_assessments] != (
            V2_METADATA_REQUIREMENT_IDS
        ):
            raise ValueError("V2 metadata requirement assessments changed")
        if self.mandatory_next_protocol_requirements != sorted(
            V2_METADATA_MANDATORY_PROTOCOL_REQUIREMENTS
        ):
            raise ValueError("V2 mandatory protocol requirements changed")
        expected_ready = sum(
            item.status == "READY_HISTORICAL_ARCHIVE"
            for item in self.requirement_assessments
        )
        expected_unresolved = sum(
            item.blocks_direct_historical_replay
            for item in self.requirement_assessments
        )
        expected_overrides = sum(
            item.conservative_research_override_permitted
            for item in self.requirement_assessments
        )
        if (
            expected_ready != self.ready_historical_requirement_count
            or expected_unresolved
            != self.unresolved_historical_requirement_count
            or expected_overrides
            != self.conservative_override_requirement_count
        ):
            raise ValueError("V2 metadata requirement counts changed")
        if self.return_metrics_calculated:
            raise ValueError("Metadata audit cannot calculate returns")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V2 metadata audit result hash does not match")
        return self


def build_v2_p01_metadata_source_audit_result(
    **values,
) -> V2P01MetadataSourceAuditResult:
    payload = {
        "schema_version": V2_METADATA_AUDIT_SCHEMA_VERSION,
        "result_id": "v2-p01-metadata-source-audit-v1.1",
        "result_version": "1.1.0",
        "status": "COMPLETE_NO_RETURN_METADATA_AUDIT",
        "source_observation_count": 4,
        "passed_source_observation_count": 4,
        "failed_source_observation_count": 0,
        "ready_historical_requirement_count": 2,
        "unresolved_historical_requirement_count": 6,
        "conservative_override_requirement_count": 5,
        "decision": V2_METADATA_PASS_DECISION,
        "credentials_used": False,
        "private_endpoint_calls_made": False,
        "response_bodies_persisted": False,
        "market_data_numeric_values_inspected": False,
        "strategy_outcomes_inspected": False,
        "return_metrics_calculated": [],
        "authorizes_full_archive_acquisition": False,
        "authorizes_market_data_import": False,
        "authorizes_return_testing": False,
        "creates_candidate": False,
        "opens_development": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["generated_at"] = normalize_timestamp(payload["generated_at"])
    for field_name in (
        "mandatory_next_protocol_requirements",
        "return_metrics_calculated",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V2P01MetadataSourceAuditResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_p01_metadata_source_audit_result(
    *,
    result: V2P01MetadataSourceAuditResult,
    contract: V2P01MetadataSourceContractV1_1,
    current_runner_contract_hash: str,
) -> dict[str, object]:
    reasons: list[str] = []
    if result.metadata_source_contract_evidence_hash != (
        contract.contract_evidence_hash
    ):
        reasons.append("METADATA_CONTRACT_HASH_MISMATCH")
    if result.theory_screen_evidence_hash != contract.theory_screen_evidence_hash:
        reasons.append("THEORY_SCREEN_HASH_MISMATCH")
    if result.runner_contract_hash != normalize_sha256(
        current_runner_contract_hash
    ):
        reasons.append("RUNNER_CONTRACT_HASH_MISMATCH")
    if result.result_evidence_hash != universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    ):
        reasons.append("RESULT_HASH_MISMATCH")
    for observation, target in zip(
        result.observations,
        contract.source_targets,
        strict=True,
    ):
        if (
            observation.source_id != target.source_id
            or observation.requested_url != target.requested_url
            or observation.required_markers != target.required_markers
            or observation.response_bytes > target.maximum_response_bytes
        ):
            reasons.append(f"SOURCE_BINDING_MISMATCH:{target.source_id}")
        final_domain = (urlparse(observation.final_url).hostname or "").lower()
        if final_domain not in target.allowed_final_domains:
            reasons.append(f"FINAL_DOMAIN_MISMATCH:{target.source_id}")
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "result_evidence_hash": result.result_evidence_hash,
    }
