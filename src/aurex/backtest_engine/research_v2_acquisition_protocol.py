from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_source_census import (
    V2_CENSUS_PASS_DECISION,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2_REQUIRED_FAMILY_IDS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V2_ACQUISITION_PROTOCOL_SCHEMA_VERSION = (
    "aurex-v2-derivatives-pilot-acquisition-protocol-v1"
)
V2_COMPLETE_SYMBOLS = [
    "AAVEUSDT",
    "ADAUSDT",
    "APEUSDT",
    "APTUSDT",
    "ATOMUSDT",
    "AVAXUSDT",
    "BCHUSDT",
    "BNBUSDT",
    "CRVUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "DYDXUSDT",
    "ETCUSDT",
    "FETUSDT",
    "FILUSDT",
    "FTMUSDT",
    "GALAUSDT",
    "GRTUSDT",
    "ICPUSDT",
    "INJUSDT",
    "LDOUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "MKRUSDT",
    "NEARUSDT",
    "OPUSDT",
    "RUNEUSDT",
    "SANDUSDT",
    "TRXUSDT",
    "UNIUSDT",
    "XRPUSDT",
]
V2_EXCLUDED_INCOMPLETE_SYMBOLS = [
    "CFXUSDT",
    "LUNCUSDT",
    "SHIBUSDT",
    "STXUSDT",
]
V2_PILOT_SYMBOLS = ["AAVEUSDT", "FTMUSDT", "XRPUSDT"]
V2_PILOT_MONTHS = ["2023-01", "2024-01", "2024-12"]
V2_ALLOWED_PILOT_INSPECTION_FIELDS = [
    "archive_content_length",
    "archive_sha256",
    "checksum_file_sha256",
    "csv_column_count",
    "csv_header",
    "csv_member_name",
    "duplicate_timestamp_count",
    "first_timestamp",
    "last_timestamp",
    "non_finite_numeric_count",
    "out_of_month_row_count",
    "row_count",
    "timestamp_unit",
    "unexpected_column_count",
    "zip_compressed_bytes",
    "zip_uncompressed_bytes",
]


class V2AcquisitionTarget(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    family_id: str
    archive_url: str = Field(min_length=50, max_length=1000)
    checksum_url: str = Field(min_length=50, max_length=1100)
    census_checksum_sha256: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("census_checksum_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> V2AcquisitionTarget:
        if self.symbol not in V2_PILOT_SYMBOLS:
            raise ValueError("V2 acquisition target is outside the pilot symbols")
        if self.month not in V2_PILOT_MONTHS:
            raise ValueError("V2 acquisition target is outside the pilot months")
        if self.family_id not in V2_REQUIRED_FAMILY_IDS:
            raise ValueError("V2 acquisition target family changed")
        if self.checksum_url != f"{self.archive_url}.CHECKSUM":
            raise ValueError("V2 acquisition checksum URL changed")
        if not self.archive_url.startswith("https://data.binance.vision/data/"):
            raise ValueError("V2 acquisition target must use the official archive")
        return self

    @property
    def key(self) -> tuple[str, str, str]:
        return self.symbol, self.month, self.family_id


class V2AcquisitionResourceLimits(BaseModel):
    maximum_concurrency: Literal[4] = 4
    request_timeout_seconds: Literal[60] = 60
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(min_length=2, max_length=2)
    required_content_length_before_download: Literal[True] = True
    maximum_single_archive_compressed_bytes: Literal[268435456] = 268435456
    maximum_pilot_compressed_bytes: Literal[4294967296] = 4294967296
    maximum_single_archive_uncompressed_bytes: Literal[1073741824] = 1073741824
    maximum_pilot_uncompressed_bytes: Literal[17179869184] = 17179869184
    maximum_zip_expansion_ratio: Literal[100] = 100
    minimum_free_disk_bytes_before_download: Literal[21474836480] = 21474836480
    minimum_free_disk_bytes_after_processing: Literal[5368709120] = 5368709120
    resource_limit_breach_action: Literal[
        "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"
    ] = "STOP_WITHOUT_PARTIAL_AUTHORITATIVE_RESULT"

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_limits(self) -> V2AcquisitionResourceLimits:
        if self.retry_backoff_seconds != [2, 5]:
            raise ValueError("V2 acquisition retry backoff changed")
        return self


class V2AcquisitionIntegrityProtocol(BaseModel):
    checksum_algorithm: Literal["SHA256"] = "SHA256"
    checksum_refresh_before_archive_get: Literal[True] = True
    refreshed_checksum_must_equal_census_checksum: Literal[True] = True
    checksum_revision_action: Literal[
        "BLOCK_AND_FREEZE_SOURCE_REVISION_DIVERGENCE"
    ] = "BLOCK_AND_FREEZE_SOURCE_REVISION_DIVERGENCE"
    archive_hash_must_equal_refreshed_checksum: Literal[True] = True
    write_download_to_part_file: Literal[True] = True
    rename_only_after_checksum_pass: Literal[True] = True
    exactly_one_csv_member_required: Literal[True] = True
    encrypted_zip_members_allowed: Literal[False] = False
    nested_archive_members_allowed: Literal[False] = False
    path_traversal_members_allowed: Literal[False] = False
    symlink_members_allowed: Literal[False] = False
    duplicate_archive_targets_allowed: Literal[False] = False
    symbol_or_month_substitution_allowed: Literal[False] = False
    preserve_raw_archive_and_checksum: Literal[True] = True
    upstream_archives_may_be_revised: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class V2AcquisitionInspectionProtocol(BaseModel):
    purpose: Literal[
        "RESOURCE_SCHEMA_AND_TIMESTAMP_QUALIFICATION_ONLY"
    ] = "RESOURCE_SCHEMA_AND_TIMESTAMP_QUALIFICATION_ONLY"
    allowed_inspection_fields: list[str]
    kline_expected_column_count: Literal[12] = 12
    funding_schema_must_be_classified_before_normalization: Literal[True] = True
    timestamp_unit_must_be_explicit: Literal[True] = True
    timestamps_must_be_utc: Literal[True] = True
    rows_must_belong_to_target_month: Literal[True] = True
    duplicate_timestamps_allowed: Literal[False] = False
    non_finite_numeric_values_allowed: Literal[False] = False
    unknown_schema_action: Literal[
        "STOP_AND_FREEZE_SCHEMA_DIVERGENCE_WITHOUT_PARSER_TUNING"
    ] = "STOP_AND_FREEZE_SCHEMA_DIVERGENCE_WITHOUT_PARSER_TUNING"
    return_or_signal_fields_allowed: Literal[False] = False
    strategy_outcome_fields_allowed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("allowed_inspection_fields")
    @classmethod
    def validate_fields(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(value))
        if normalized != V2_ALLOWED_PILOT_INSPECTION_FIELDS:
            raise ValueError("V2 pilot inspection fields changed")
        return normalized


class V2AcquisitionPilotDecisionRule(BaseModel):
    required_target_count: Literal[54] = 54
    required_checksum_matches: Literal[54] = 54
    required_verified_archives: Literal[54] = 54
    required_classified_schemas: Literal[6] = 6
    all_integrity_and_resource_gates_required: Literal[True] = True
    pass_decision: Literal[
        "PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL"
    ] = "PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL"
    fail_decision: Literal[
        "STOP_OR_REDESIGN_V2_ARCHIVE_ACQUISITION"
    ] = "STOP_OR_REDESIGN_V2_ARCHIVE_ACQUISITION"
    pass_authorizes_full_download_automatically: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V2DerivativesAcquisitionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-v2-derivatives-pilot-acquisition-protocol-v1"
    ] = V2_ACQUISITION_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["v2-derivatives-pilot-acquisition-v1"] = (
        "v2-derivatives-pilot-acquisition-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_PAYLOAD"] = "FROZEN_PRE_PAYLOAD"
    source_census_contract_evidence_hash: str
    source_census_result_evidence_hash: str
    capability_audit_evidence_hash: str
    universe_manifest_evidence_hash: str
    contamination_ledger_evidence_hash: str
    builder_contract_hash: str
    predecessor_census_decision: Literal[
        "PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL"
    ] = V2_CENSUS_PASS_DECISION
    official_documentation_urls: list[str] = Field(min_length=3)
    complete_source_symbols: list[str] = Field(min_length=31, max_length=31)
    excluded_incomplete_symbols: list[str] = Field(min_length=4, max_length=4)
    incomplete_symbol_action: Literal[
        "EXCLUDE_WITHOUT_SUBSTITUTION_OR_BACKFILL"
    ] = "EXCLUDE_WITHOUT_SUBSTITUTION_OR_BACKFILL"
    pilot_selection_rule: Literal[
        "FIRST_MEDIAN_LAST_SORTED_COMPLETE_SYMBOLS"
    ] = "FIRST_MEDIAN_LAST_SORTED_COMPLETE_SYMBOLS"
    pilot_month_selection_rule: Literal[
        "FIRST_MIDDLE_LAST_FROZEN_CENSUS_MONTHS"
    ] = "FIRST_MIDDLE_LAST_FROZEN_CENSUS_MONTHS"
    pilot_symbols: list[str] = Field(min_length=3, max_length=3)
    pilot_months: list[str] = Field(min_length=3, max_length=3)
    family_ids: list[str] = Field(min_length=6, max_length=6)
    pilot_target_count: Literal[54] = 54
    targets: list[V2AcquisitionTarget] = Field(min_length=54, max_length=54)
    storage_root_relative_path: Literal[
        "v2_derivatives_pilot_bundle_v1"
    ] = "v2_derivatives_pilot_bundle_v1"
    resource_limits: V2AcquisitionResourceLimits
    integrity: V2AcquisitionIntegrityProtocol
    inspection: V2AcquisitionInspectionProtocol
    decision_rule: V2AcquisitionPilotDecisionRule
    authorizes_archive_metadata_requests: Literal[True] = True
    authorizes_archive_payload_download: Literal[True] = True
    authorized_payload_scope: Literal[
        "EXACT_54_PILOT_TARGETS_ONLY"
    ] = "EXACT_54_PILOT_TARGETS_ONLY"
    authorizes_full_archive_payload_download: Literal[False] = False
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
    limitations: list[str] = Field(min_length=5)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "source_census_contract_evidence_hash",
        "source_census_result_evidence_hash",
        "capability_audit_evidence_hash",
        "universe_manifest_evidence_hash",
        "contamination_ledger_evidence_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "official_documentation_urls",
        "complete_source_symbols",
        "excluded_incomplete_symbols",
        "pilot_symbols",
        "pilot_months",
        "family_ids",
        "strategy_outcome_fields_inspected",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(self) -> V2DerivativesAcquisitionProtocol:
        if self.complete_source_symbols != V2_COMPLETE_SYMBOLS:
            raise ValueError("V2 acquisition complete-symbol set changed")
        if self.excluded_incomplete_symbols != V2_EXCLUDED_INCOMPLETE_SYMBOLS:
            raise ValueError("V2 acquisition exclusions changed")
        if self.pilot_symbols != V2_PILOT_SYMBOLS:
            raise ValueError("V2 acquisition pilot-symbol rule changed")
        if self.pilot_months != V2_PILOT_MONTHS:
            raise ValueError("V2 acquisition pilot-month rule changed")
        if self.family_ids != V2_REQUIRED_FAMILY_IDS:
            raise ValueError("V2 acquisition family set changed")
        if self.targets != sorted(self.targets, key=lambda item: item.key):
            raise ValueError("V2 acquisition targets are not canonical")
        if len({target.key for target in self.targets}) != 54:
            raise ValueError("V2 acquisition target matrix is incomplete")
        expected_keys = {
            (symbol, month, family_id)
            for symbol in V2_PILOT_SYMBOLS
            for month in V2_PILOT_MONTHS
            for family_id in V2_REQUIRED_FAMILY_IDS
        }
        if {target.key for target in self.targets} != expected_keys:
            raise ValueError("V2 acquisition target matrix changed")
        if self.strategy_outcome_fields_inspected:
            raise ValueError("V2 acquisition protocol must predate outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("V2 acquisition protocol hash does not match")
        return self


def build_v2_derivatives_acquisition_protocol(
    **values,
) -> V2DerivativesAcquisitionProtocol:
    payload = {
        "schema_version": V2_ACQUISITION_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "v2-derivatives-pilot-acquisition-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_PAYLOAD",
        "predecessor_census_decision": V2_CENSUS_PASS_DECISION,
        "incomplete_symbol_action": "EXCLUDE_WITHOUT_SUBSTITUTION_OR_BACKFILL",
        "pilot_selection_rule": "FIRST_MEDIAN_LAST_SORTED_COMPLETE_SYMBOLS",
        "pilot_month_selection_rule": "FIRST_MIDDLE_LAST_FROZEN_CENSUS_MONTHS",
        "pilot_target_count": 54,
        "storage_root_relative_path": "v2_derivatives_pilot_bundle_v1",
        "authorizes_archive_metadata_requests": True,
        "authorizes_archive_payload_download": True,
        "authorized_payload_scope": "EXACT_54_PILOT_TARGETS_ONLY",
        "authorizes_full_archive_payload_download": False,
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
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    for field in (
        "official_documentation_urls",
        "complete_source_symbols",
        "excluded_incomplete_symbols",
        "pilot_symbols",
        "pilot_months",
        "family_ids",
        "strategy_outcome_fields_inspected",
        "limitations",
    ):
        payload[field] = sorted(set(payload[field]))
    payload["targets"] = sorted(payload["targets"], key=lambda item: item.key)
    return V2DerivativesAcquisitionProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v2_derivatives_acquisition_protocol(
    protocol: V2DerivativesAcquisitionProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )
