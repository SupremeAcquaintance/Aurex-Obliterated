from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_NORMALIZATION_NEXT = (
    "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUNNER_IMPLEMENTATION_ONLY"
)

S1_NFCI_NORMALIZED_ROW_FIELDS = (
    "sequence",
    "target_id",
    "source_vintage_date",
    "selected_observation_date",
    "release_lag_days",
    "nfci_value_source_text",
    "source_raw_path",
    "source_raw_sha256",
)

S1_NFCI_NORMALIZATION_GATES = (
    "EXACTLY_281_ROWS_IN_PROTOCOL_TARGET_ORDER",
    "ONE_ROW_PER_SOURCE_VINTAGE",
    "EVERY_SOURCE_FILE_REHASHES_TO_ACQUISITION_EVIDENCE",
    "EXACT_VINTAGE_SUFFIXED_HEADER_PER_SOURCE",
    "SELECTED_OBSERVATION_IS_LATEST_AVAILABLE_VALID_DECIMAL",
    "SELECTED_OBSERVATION_NEVER_AFTER_SOURCE_VINTAGE",
    "RELEASE_LAG_IS_ZERO_THROUGH_21_DAYS",
    "SOURCE_DECIMAL_TEXT_IS_PRESERVED_WITHOUT_ROUNDING",
    "JSONL_SERIALIZATION_REPRODUCES_BYTE_FOR_BYTE",
    "ZERO_DERIVED_FEATURES_BTC_VALUES_RETURNS_CANDIDATES_AND_ORDERS",
)


class S1NfciNormalizationProtocol(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-protocol-v1"] = (
        "aurex-s1-nfci-normalization-protocol-v1"
    )
    protocol_id: Literal["s1-nfci-normalization-protocol-v1"] = (
        "s1-nfci-normalization-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    acquisition_result_file_sha256: str
    acquisition_result_evidence_hash: str
    acquisition_audit_file_sha256: str
    acquisition_audit_evidence_hash: str
    acquisition_checkpoint_evidence_hash: str
    acquisition_runner_contract_hash: str
    acquisition_decision: Literal[
        "PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
    ]
    acquisition_next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY"
    ]
    input_manifest_evidence_hash: str
    input_manifest_fields: tuple[Literal[
        "sequence",
        "target_id",
        "vintage_date",
        "expected_value_column",
        "raw_path",
        "raw_file_sha256",
        "raw_file_bytes",
        "row_count",
        "last_observation_date",
        "release_lag_days",
    ], ...] = (
        "sequence",
        "target_id",
        "vintage_date",
        "expected_value_column",
        "raw_path",
        "raw_file_sha256",
        "raw_file_bytes",
        "row_count",
        "last_observation_date",
        "release_lag_days",
    )
    input_vintage_count: Literal[281] = 281
    first_source_vintage_date: Literal["2017-08-17"] = "2017-08-17"
    last_source_vintage_date: Literal["2022-12-29"] = "2022-12-29"
    source_values_read_during_protocol_freeze: Literal[0] = 0
    normalization_scope: Literal["DEVELOPMENT_MACRO_SOURCE_ONLY"] = (
        "DEVELOPMENT_MACRO_SOURCE_ONLY"
    )
    row_selection_rule: Literal[
        "FOR_EACH_VINTAGE_SELECT_MAX_OBSERVATION_DATE_WITH_VALID_NFCI_DECIMAL_NOT_AFTER_VINTAGE"
    ] = (
        "FOR_EACH_VINTAGE_SELECT_MAX_OBSERVATION_DATE_WITH_VALID_NFCI_DECIMAL_NOT_AFTER_VINTAGE"
    )
    value_policy: Literal[
        "PRESERVE_EXACT_SOURCE_DECIMAL_TEXT_PARSE_FINITE_DECIMAL_NO_ROUNDING"
    ] = "PRESERVE_EXACT_SOURCE_DECIMAL_TEXT_PARSE_FINITE_DECIMAL_NO_ROUNDING"
    duplicate_policy: Literal["REJECT_DUPLICATE_OBSERVATION_DATE"] = (
        "REJECT_DUPLICATE_OBSERVATION_DATE"
    )
    missing_value_policy: Literal["REJECT_SELECTED_MISSING_VALUE"] = (
        "REJECT_SELECTED_MISSING_VALUE"
    )
    release_lag_minimum_days: Literal[0] = 0
    release_lag_maximum_days: Literal[21] = 21
    output_path: Literal[
        "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    serialization: Literal[
        "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    ] = "UTF8_JSONL_SORTED_KEYS_COMPACT_SEPARATORS_LF_FINAL_NEWLINE"
    normalized_row_fields: tuple[str, ...] = S1_NFCI_NORMALIZED_ROW_FIELDS
    forbidden_derived_fields: tuple[str, ...] = (
        "nfci_change",
        "nfci_delta",
        "rolling_mean",
        "rolling_zscore",
        "signal",
        "position",
        "btc_price",
        "btc_return",
        "strategy_return",
        "pnl",
    )
    quality_gates: tuple[str, ...] = Field(min_length=10, max_length=10)
    authorizes_protocol_only: Literal[True] = True
    authorizes_runner_implementation: Literal[True] = True
    authorizes_value_transformation_now: Literal[False] = False
    authorizes_feature_construction: Literal[False] = False
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_NORMALIZATION_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "acquisition_result_file_sha256",
        "acquisition_result_evidence_hash",
        "acquisition_audit_file_sha256",
        "acquisition_audit_evidence_hash",
        "acquisition_checkpoint_evidence_hash",
        "acquisition_runner_contract_hash",
        "input_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1NfciNormalizationProtocol:
        if self.normalized_row_fields != S1_NFCI_NORMALIZED_ROW_FIELDS:
            raise ValueError("S1 NFCI normalized row schema changed")
        if self.quality_gates != S1_NFCI_NORMALIZATION_GATES:
            raise ValueError("S1 NFCI normalization gates changed")
        if set(self.normalized_row_fields) & set(self.forbidden_derived_fields):
            raise ValueError("S1 NFCI normalization includes a derived field")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization protocol hash changed")
        return self


class S1NfciNormalizationProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-protocol-audit-v1"] = (
        "aurex-s1-nfci-normalization-protocol-audit-v1"
    )
    audit_id: Literal["s1-nfci-normalization-protocol-audit-v1"] = (
        "s1-nfci-normalization-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    acquisition_result_evidence_hash: str
    acquisition_audit_evidence_hash: str
    input_manifest_evidence_hash: str
    auditor_source_sha256: str
    input_vintage_count: Literal[281] = 281
    raw_csv_files_opened: Literal[0] = 0
    source_value_rows_read: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_NORMALIZATION_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_NORMALIZATION_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_NORMALIZATION_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "acquisition_result_evidence_hash",
        "acquisition_audit_evidence_hash",
        "input_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciNormalizationProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization protocol audit hash changed")
        return self
