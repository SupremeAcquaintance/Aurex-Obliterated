from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_FEATURE_NEXT = (
    "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUNNER_IMPLEMENTATION_ONLY"
)

S1_NFCI_FEATURE_GATES = (
    "INPUT_DATASET_HASH_AND_281_ROW_MANIFEST_MATCH",
    "INPUT_ROWS_ARE_STRICTLY_ORDERED_BY_SOURCE_VINTAGE",
    "ONLY_CURRENT_LAG_1_AND_LAG_4_ROWS_ARE_ACCESSED",
    "ALL_FEATURE_ARITHMETIC_USES_EXACT_DECIMAL_NEVER_FLOAT",
    "FOUR_ROW_WARMUP_PRODUCES_EXACTLY_277_FEATURE_ROWS",
    "SOURCE_VINTAGE_OBSERVATION_LAG_AND_ROW_HASH_LINEAGE_RETAINED",
    "NO_MISSING_OR_NONFINITE_FEATURE_VALUE_AFTER_WARMUP",
    "JSONL_SERIALIZATION_REPRODUCES_BYTE_FOR_BYTE",
    "NO_STRATEGY_RULE_SIGNAL_POSITION_OR_CANDIDATE_IS_CREATED",
    "ZERO_BTC_VALUES_RETURNS_VALIDATION_HOLDOUT_AND_ORDERS",
)


class S1NfciFeatureDefinition(BaseModel):
    feature_id: Literal["nfci_level", "nfci_change_1v", "nfci_change_4v"]
    formula: Literal[
        "CURRENT_NFCI_SOURCE_DECIMAL",
        "CURRENT_NFCI_MINUS_LAG_1_VINTAGE_NFCI",
        "CURRENT_NFCI_MINUS_LAG_4_VINTAGE_NFCI",
    ]
    required_lag_vintages: Literal[0, 1, 4]

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1NfciFeatureProtocol(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-protocol-v1"] = (
        "aurex-s1-nfci-feature-protocol-v1"
    )
    protocol_id: Literal["s1-nfci-feature-protocol-v1"] = (
        "s1-nfci-feature-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    normalization_result_file_sha256: str
    normalization_result_evidence_hash: str
    normalization_audit_file_sha256: str
    normalization_audit_evidence_hash: str
    normalized_dataset_file_sha256: str
    normalized_dataset_bytes: Literal[107885] = 107_885
    input_row_manifest_evidence_hash: str
    normalization_decision: Literal["PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION"]
    normalization_next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY"
    ]
    normalized_dataset_payload_bytes_hashed_during_freeze: Literal[107885] = 107_885
    normalized_value_rows_parsed_during_freeze: Literal[0] = 0
    input_row_count: Literal[281] = 281
    feature_definitions: tuple[S1NfciFeatureDefinition, ...] = Field(
        min_length=3,
        max_length=3,
    )
    feature_count: Literal[3] = 3
    maximum_required_lag_vintages: Literal[4] = 4
    warmup_input_rows: Literal[4] = 4
    expected_feature_row_count: Literal[277] = 277
    arithmetic_policy: Literal["PYTHON_DECIMAL_EXACT_NO_FLOAT_NO_QUANTIZATION"] = (
        "PYTHON_DECIMAL_EXACT_NO_FLOAT_NO_QUANTIZATION"
    )
    decimal_serialization: Literal["FIXED_POINT_TEXT_PRESERVE_LEVEL_SOURCE_TEXT"] = (
        "FIXED_POINT_TEXT_PRESERVE_LEVEL_SOURCE_TEXT"
    )
    missing_value_policy: Literal["REJECT_AFTER_FROZEN_WARMUP"] = (
        "REJECT_AFTER_FROZEN_WARMUP"
    )
    output_path: Literal[
        "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    output_fields: tuple[str, ...] = (
        "sequence",
        "target_id",
        "source_vintage_date",
        "selected_observation_date",
        "release_lag_days",
        "source_normalized_row_sha256",
        "nfci_level",
        "nfci_change_1v",
        "nfci_change_4v",
    )
    forbidden_features: tuple[str, ...] = (
        "rolling_mean",
        "rolling_std",
        "rolling_zscore",
        "expanding_zscore",
        "percentile_rank",
        "easing_streak",
        "future_nfci",
        "btc_price",
        "btc_return",
        "signal",
        "position",
        "pnl",
    )
    quality_gates: tuple[str, ...] = Field(min_length=10, max_length=10)
    maximum_future_strategy_candidates: Literal[4] = 4
    strategy_candidates_defined: Literal[0] = 0
    strategy_rules_defined: tuple[str, ...] = ()
    authorizes_protocol_only: Literal[True] = True
    authorizes_runner_implementation: Literal[True] = True
    authorizes_feature_calculation_now: Literal[False] = False
    authorizes_strategy_rule_definition: Literal[False] = False
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
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_FEATURE_NEXT
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "normalization_result_file_sha256",
        "normalization_result_evidence_hash",
        "normalization_audit_file_sha256",
        "normalization_audit_evidence_hash",
        "normalized_dataset_file_sha256",
        "input_row_manifest_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1NfciFeatureProtocol:
        expected_definitions = (
            (
                "nfci_level",
                "CURRENT_NFCI_SOURCE_DECIMAL",
                0,
            ),
            (
                "nfci_change_1v",
                "CURRENT_NFCI_MINUS_LAG_1_VINTAGE_NFCI",
                1,
            ),
            (
                "nfci_change_4v",
                "CURRENT_NFCI_MINUS_LAG_4_VINTAGE_NFCI",
                4,
            ),
        )
        actual_definitions = tuple(
            (item.feature_id, item.formula, item.required_lag_vintages)
            for item in self.feature_definitions
        )
        if actual_definitions != expected_definitions:
            raise ValueError("S1 NFCI feature family changed")
        if self.quality_gates != S1_NFCI_FEATURE_GATES:
            raise ValueError("S1 NFCI feature gates changed")
        if self.expected_feature_row_count != (
            self.input_row_count - self.warmup_input_rows
        ):
            raise ValueError("S1 NFCI feature warmup changed")
        if set(self.output_fields) & set(self.forbidden_features):
            raise ValueError("S1 NFCI output includes a forbidden feature")
        if self.strategy_candidates_defined or self.strategy_rules_defined:
            raise ValueError("S1 NFCI feature protocol cannot define a strategy")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 NFCI feature protocol hash changed")
        return self


class S1NfciFeatureProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-protocol-audit-v1"] = (
        "aurex-s1-nfci-feature-protocol-audit-v1"
    )
    audit_id: Literal["s1-nfci-feature-protocol-audit-v1"] = (
        "s1-nfci-feature-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    normalization_result_evidence_hash: str
    normalization_audit_evidence_hash: str
    normalized_dataset_file_sha256: str
    input_row_manifest_evidence_hash: str
    auditor_source_sha256: str
    normalized_dataset_payload_bytes_hashed: Literal[107885] = 107_885
    normalized_value_rows_parsed: Literal[0] = 0
    feature_count: Literal[3] = 3
    expected_feature_row_count: Literal[277] = 277
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_FEATURE_PROTOCOL_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_FEATURE_PROTOCOL_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUNNER_IMPLEMENTATION_ONLY"
    ] = S1_NFCI_FEATURE_NEXT
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
        "normalization_result_evidence_hash",
        "normalization_audit_evidence_hash",
        "normalized_dataset_file_sha256",
        "input_row_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciFeatureProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI feature protocol audit hash changed")
        return self
