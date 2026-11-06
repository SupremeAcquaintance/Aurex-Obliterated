from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_METADATA_SOURCE_CONTRACT_SCHEMA_VERSION = (
    "aurex-v2-p01-metadata-source-contract-v1"
)
V2_METADATA_REQUIREMENT_IDS = [
    "HISTORICAL_SETTLED_FUNDING_AND_INTERVALS",
    "HISTORICAL_SPOT_PERPETUAL_MARK_INDEX_PREMIUM_SERIES",
    "HISTORICAL_FUTURES_CONTRACT_LIFECYCLE",
    "HISTORICAL_FUTURES_ORDER_FILTERS",
    "HISTORICAL_SPOT_ORDER_FILTERS",
    "HISTORICAL_ACCOUNT_FEE_TIER",
    "HISTORICAL_LEVERAGE_AND_MAINTENANCE_BRACKETS",
    "HISTORICAL_COLLATERAL_LIQUIDATION_AND_ADL_RULES",
]
V2_METADATA_SOURCE_IDS = [
    "BINANCE_PUBLIC_DATA_README",
    "BINANCE_USD_M_MARKET_DATA_DOCS",
    "BINANCE_USD_M_ACCOUNT_DOCS",
    "BINANCE_SPOT_API_DOCS",
]
V2_METADATA_CLASSIFICATION_POLICY = [
    "ARCHIVE_EVIDENCE_MAY_SATISFY_HISTORICAL_MARKET_AND_FUNDING_INPUTS",
    "CONSERVATIVE_OVERRIDE_REQUIRES_A_SEPARATELY_FROZEN_PROTOCOL",
    "CURRENT_ONLY_SURFACE_CANNOT_PROVE_A_HISTORICAL_RULE",
    "DOCUMENT_REACHABILITY_DOES_NOT_PROVE_HISTORICAL_EXECUTABILITY",
    "NO_CREDENTIAL_ACCOUNT_OR_PRIVATE_ENDPOINT_ACCESS",
    "NO_MARKET_VALUES_RETURNS_SIGNALS_OR_STRATEGY_OUTCOMES",
    "SIGNED_CURRENT_ENDPOINT_CANNOT_SATISFY_HISTORICAL_ACCOUNT_STATE",
    "UNRESOLVED_HISTORICAL_RULES_MUST_FAIL_CLOSED_OR_REMAIN_EXPLICIT_LIMITATIONS",
]
V2_METADATA_ALLOWED_NEXT_DECISIONS = [
    "PERMIT_P01_PROTOCOL_DESIGN_WITH_MANDATORY_METADATA_OVERRIDES",
    "STOP_P01_PROTOCOL_DESIGN_METADATA_SOURCES_INSUFFICIENT",
]


class V2MetadataSourceTarget(BaseModel):
    source_id: str = Field(min_length=1, max_length=128)
    source_kind: Literal[
        "OFFICIAL_BINANCE_DOCUMENTATION",
        "OFFICIAL_BINANCE_GITHUB_DOCUMENTATION",
    ]
    requested_url: str = Field(min_length=10, max_length=1000)
    allowed_final_domains: list[str] = Field(min_length=1)
    declared_temporal_scope: Literal[
        "HISTORICAL_ARCHIVE_DOCUMENTATION",
        "CURRENT_MARKET_AND_CONTRACT_API_DOCUMENTATION",
        "CURRENT_SIGNED_ACCOUNT_API_DOCUMENTATION",
        "CURRENT_SPOT_API_DOCUMENTATION",
    ]
    required_markers: list[str] = Field(min_length=2)
    supports_requirement_ids: list[str] = Field(min_length=1)
    maximum_response_bytes: int = Field(gt=0, le=8 * 1024 * 1024)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_id", "requested_url")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "allowed_final_domains",
        "required_markers",
        "supports_requirement_ids",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_target(self) -> V2MetadataSourceTarget:
        parsed = urlparse(self.requested_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("V2 metadata sources must use absolute HTTPS URLs")
        if self.source_id not in V2_METADATA_SOURCE_IDS:
            raise ValueError("Unknown V2 metadata source ID")
        if not set(self.supports_requirement_ids).issubset(
            V2_METADATA_REQUIREMENT_IDS
        ):
            raise ValueError("Metadata source references unknown requirements")
        return self


class V2P01MetadataSourceContract(BaseModel):
    schema_version: Literal[
        "aurex-v2-p01-metadata-source-contract-v1"
    ] = V2_METADATA_SOURCE_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v2-p01-metadata-source-contract-v1"] = (
        "v2-p01-metadata-source-contract-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_METADATA_OBSERVATION"] = (
        "FROZEN_PRE_METADATA_OBSERVATION"
    )
    theory_screen_evidence_hash: str
    discovery_charter_evidence_hash: str
    capability_audit_evidence_hash: str
    source_census_result_evidence_hash: str
    pilot_result_evidence_hash: str
    derivatives_foundation_result_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    selected_proposal_id: Literal[
        "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    ] = "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY"
    requirement_ids: list[str]
    source_targets: list[V2MetadataSourceTarget] = Field(
        min_length=4, max_length=4
    )
    classification_policy: list[str]
    allowed_next_decisions: list[str]
    maximum_http_requests: Literal[4] = 4
    retry_attempts_per_source: Literal[3] = 3
    request_timeout_seconds: Literal[30] = 30
    response_bodies_persisted: Literal[False] = False
    credentials_permitted: Literal[False] = False
    private_endpoint_calls_permitted: Literal[False] = False
    market_data_numeric_values_permitted: Literal[False] = False
    strategy_outcomes_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    authorizes_full_archive_acquisition: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_data_numeric_fields_inspected: list[str] = Field(default_factory=list)
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    preexisting_result_artifacts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=5)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "theory_screen_evidence_hash",
        "discovery_charter_evidence_hash",
        "capability_audit_evidence_hash",
        "source_census_result_evidence_hash",
        "pilot_result_evidence_hash",
        "derivatives_foundation_result_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "requirement_ids",
        "classification_policy",
        "allowed_next_decisions",
        "market_data_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_result_artifacts",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V2P01MetadataSourceContract:
        if self.requirement_ids != sorted(V2_METADATA_REQUIREMENT_IDS):
            raise ValueError("V2 metadata requirement set changed")
        if [target.source_id for target in self.source_targets] != (
            V2_METADATA_SOURCE_IDS
        ):
            raise ValueError("V2 metadata source target set or order changed")
        if self.classification_policy != sorted(
            V2_METADATA_CLASSIFICATION_POLICY
        ):
            raise ValueError("V2 metadata classification policy changed")
        if self.allowed_next_decisions != sorted(
            V2_METADATA_ALLOWED_NEXT_DECISIONS
        ):
            raise ValueError("V2 metadata next decisions changed")
        if (
            self.market_data_numeric_fields_inspected
            or self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
            or self.preexisting_result_artifacts
        ):
            raise ValueError("Metadata source contract must predate observations")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V2 metadata source contract hash does not match")
        return self


def build_v2_p01_metadata_source_contract(
    **values,
) -> V2P01MetadataSourceContract:
    payload = {
        "schema_version": V2_METADATA_SOURCE_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v2-p01-metadata-source-contract-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_METADATA_OBSERVATION",
        "selected_proposal_id": "P01_POSITIVE_FUNDING_SPOT_PERP_CARRY",
        "maximum_http_requests": 4,
        "retry_attempts_per_source": 3,
        "request_timeout_seconds": 30,
        "response_bodies_persisted": False,
        "credentials_permitted": False,
        "private_endpoint_calls_permitted": False,
        "market_data_numeric_values_permitted": False,
        "strategy_outcomes_permitted": False,
        "return_calculation_permitted": False,
        "authorizes_full_archive_acquisition": False,
        "authorizes_market_data_import": False,
        "creates_candidate": False,
        "opens_development": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "market_data_numeric_fields_inspected": [],
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        "preexisting_result_artifacts": [],
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field_name in (
        "requirement_ids",
        "classification_policy",
        "allowed_next_decisions",
        "market_data_numeric_fields_inspected",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "preexisting_result_artifacts",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V2P01MetadataSourceContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_p01_metadata_source_contract(
    contract: V2P01MetadataSourceContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )
