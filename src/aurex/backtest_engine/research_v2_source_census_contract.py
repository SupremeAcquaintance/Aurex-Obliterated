from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_r4_protocol import R4_DECISION_SYMBOLS
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_SOURCE_CENSUS_CONTRACT_SCHEMA_VERSION = (
    "aurex-v2-derivatives-source-census-contract-v1"
)
V2_REQUIRED_FAMILY_IDS = [
    "spot_klines_1m",
    "um_contract_klines_1m",
    "um_funding_rate_events",
    "um_index_price_klines_1m",
    "um_mark_price_klines_1m",
    "um_premium_index_klines_1m",
]
V2_ALLOWED_CENSUS_FIELDS = [
    "archive_content_length",
    "archive_http_status",
    "archive_last_modified",
    "archive_url",
    "checked_at",
    "checksum_http_status",
    "checksum_sha256",
    "checksum_text",
    "checksum_url",
    "family_id",
    "month",
    "symbol",
]
V2_MONTHS = [
    f"{year}-{month:02d}"
    for year in (2023, 2024)
    for month in range(1, 13)
]


class V2ArchiveFamilyContract(BaseModel):
    family_id: str = Field(min_length=1, max_length=128)
    venue: Literal["BINANCE"] = "BINANCE"
    market: Literal["SPOT", "USD_M_FUTURES"]
    data_type: Literal[
        "KLINES",
        "FUNDING_RATE_EVENTS",
        "INDEX_PRICE_KLINES",
        "MARK_PRICE_KLINES",
        "PREMIUM_INDEX_KLINES",
    ]
    interval: Literal["1m", "EVENT"]
    archive_url_template: str = Field(min_length=50, max_length=1000)
    checksum_url_template: str = Field(min_length=50, max_length=1100)
    payload_download_authorized: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_family(self) -> V2ArchiveFamilyContract:
        for placeholder in ("{symbol}", "{month}"):
            if placeholder not in self.archive_url_template:
                raise ValueError("V2 archive template is missing a placeholder")
        if self.checksum_url_template != f"{self.archive_url_template}.CHECKSUM":
            raise ValueError("V2 checksum URL must append .CHECKSUM exactly")
        if not self.archive_url_template.startswith(
            "https://data.binance.vision/data/"
        ):
            raise ValueError("V2 census accepts only the official archive host")
        if self.interval == "1m" and "/1m/" not in self.archive_url_template:
            raise ValueError("V2 one-minute family URL must contain /1m/")
        if self.interval == "EVENT" and "/fundingRate/" not in (
            self.archive_url_template
        ):
            raise ValueError("V2 event family must be the funding archive")
        return self


class V2SourceCensusDecisionRule(BaseModel):
    minimum_complete_symbols: Literal[20] = 20
    required_complete_months_per_family: Literal[24] = 24
    required_family_count: Literal[6] = 6
    complete_symbol_rule: Literal[
        "ALL_24_MONTHS_PRESENT_FOR_ALL_6_FAMILIES"
    ] = "ALL_24_MONTHS_PRESENT_FOR_ALL_6_FAMILIES"
    pass_decision: Literal[
        "PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL"
    ] = "PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL"
    fail_decision: Literal[
        "STOP_BINANCE_ARCHIVE_DERIVATIVES_FOUNDATION"
    ] = "STOP_BINANCE_ARCHIVE_DERIVATIVES_FOUNDATION"
    exact_threshold_no_override: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class V2SourceCensusContract(BaseModel):
    schema_version: Literal[
        "aurex-v2-derivatives-source-census-contract-v1"
    ] = V2_SOURCE_CENSUS_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v2-derivatives-source-census-v1"] = (
        "v2-derivatives-source-census-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_CENSUS"] = "FROZEN_PRE_CENSUS"
    capability_audit_evidence_hash: str
    predecessor_u1_result_evidence_hash: str
    universe_manifest_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    official_documentation_urls: list[str] = Field(min_length=2)
    archive_base_url: Literal["https://data.binance.vision/data/"] = (
        "https://data.binance.vision/data/"
    )
    census_start: datetime
    census_end: datetime
    months: list[str] = Field(min_length=24, max_length=24)
    symbols: list[str] = Field(min_length=35, max_length=35)
    families: list[V2ArchiveFamilyContract] = Field(min_length=6, max_length=6)
    expected_checksum_checks: Literal[5040] = 5040
    allowed_census_fields: list[str]
    decision_rule: V2SourceCensusDecisionRule
    missing_archive_action: Literal[
        "PRESERVE_MISSING_WITHOUT_SUBSTITUTION"
    ] = "PRESERVE_MISSING_WITHOUT_SUBSTITUTION"
    checksum_parse_rule: Literal[
        "EXACT_64_HEX_AND_EXPECTED_ZIP_FILENAME"
    ] = "EXACT_64_HEX_AND_EXPECTED_ZIP_FILENAME"
    redirects_allowed: Literal[True] = True
    maximum_concurrency: Literal[16] = 16
    request_timeout_seconds: Literal[30] = 30
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(min_length=2, max_length=2)
    authorizes_archive_listing_and_checksum_census: Literal[True] = True
    authorizes_archive_payload_download: Literal[False] = False
    authorizes_market_data_import: Literal[False] = False
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
    preexisting_census_artifacts: list[str] = Field(default_factory=list)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at", "census_start", "census_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "capability_audit_evidence_hash",
        "predecessor_u1_result_evidence_hash",
        "universe_manifest_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "official_documentation_urls",
        "months",
        "symbols",
        "allowed_census_fields",
        "strategy_outcome_fields_inspected",
        "preexisting_census_artifacts",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V2SourceCensusContract:
        if self.census_start.isoformat() != "2023-01-01T00:00:00+00:00":
            raise ValueError("V2 census start is fixed")
        if self.census_end.isoformat() != "2025-01-01T00:00:00+00:00":
            raise ValueError("V2 census end is fixed")
        if self.months != V2_MONTHS:
            raise ValueError("V2 census requires the exact 24 months")
        if tuple(self.symbols) != R4_DECISION_SYMBOLS:
            raise ValueError("V2 census requires the frozen 35-symbol universe")
        family_ids = [family.family_id for family in self.families]
        if (
            family_ids != V2_REQUIRED_FAMILY_IDS
            or len(family_ids) != len(set(family_ids))
        ):
            raise ValueError("V2 census requires the exact six archive families")
        if self.expected_checksum_checks != (
            len(self.symbols) * len(self.months) * len(self.families)
        ):
            raise ValueError("V2 expected checksum count is inconsistent")
        if self.allowed_census_fields != V2_ALLOWED_CENSUS_FIELDS:
            raise ValueError("V2 allowed census fields are fixed")
        if self.retry_backoff_seconds != [1, 3]:
            raise ValueError("V2 retry backoff is fixed")
        if (
            self.strategy_outcome_fields_inspected
            or self.preexisting_census_artifacts
        ):
            raise ValueError("V2 source contract must predate census and outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V2 source-contract hash does not match its evidence")
        return self


def build_v2_source_census_contract(**values) -> V2SourceCensusContract:
    payload = {
        "schema_version": V2_SOURCE_CENSUS_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v2-derivatives-source-census-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_CENSUS",
        "archive_base_url": "https://data.binance.vision/data/",
        "expected_checksum_checks": 5040,
        "missing_archive_action": "PRESERVE_MISSING_WITHOUT_SUBSTITUTION",
        "checksum_parse_rule": "EXACT_64_HEX_AND_EXPECTED_ZIP_FILENAME",
        "redirects_allowed": True,
        "maximum_concurrency": 16,
        "request_timeout_seconds": 30,
        "maximum_retries": 2,
        "retry_backoff_seconds": [1, 3],
        "authorizes_archive_listing_and_checksum_census": True,
        "authorizes_archive_payload_download": False,
        "authorizes_market_data_import": False,
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
        "preexisting_census_artifacts": [],
        **values,
    }
    for field in ("frozen_at", "census_start", "census_end"):
        payload[field] = normalize_timestamp(payload[field])
    for field in (
        "official_documentation_urls",
        "months",
        "symbols",
        "allowed_census_fields",
        "strategy_outcome_fields_inspected",
        "preexisting_census_artifacts",
    ):
        payload[field] = sorted(set(payload[field]))
    payload["families"] = sorted(
        payload["families"], key=lambda family: family.family_id
    )
    return V2SourceCensusContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_source_census_contract(
    contract: V2SourceCensusContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )
