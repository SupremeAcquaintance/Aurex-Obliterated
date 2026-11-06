from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_NFCI_NORMALIZATION_RUN = "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUN"
S1_NFCI_NORMALIZATION_PASS = "PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION"
S1_NFCI_NORMALIZATION_RESULT_NEXT = (
    "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY"
)


class S1NfciNormalizedRow(BaseModel):
    sequence: int = Field(ge=1, le=281)
    target_id: str = Field(min_length=10)
    source_vintage_date: date
    selected_observation_date: date
    release_lag_days: int = Field(ge=0, le=21)
    nfci_value_source_text: str = Field(min_length=1, max_length=64)
    source_raw_path: str = Field(min_length=20)
    source_raw_sha256: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("source_raw_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("nfci_value_source_text")
    @classmethod
    def validate_decimal_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("NFCI source decimal text contains surrounding whitespace")
        try:
            parsed = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("NFCI source text is not a decimal") from error
        if not parsed.is_finite():
            raise ValueError("NFCI source decimal must be finite")
        return value

    @model_validator(mode="after")
    def validate_row(self) -> S1NfciNormalizedRow:
        if self.selected_observation_date > self.source_vintage_date:
            raise ValueError("Selected NFCI observation is after its source vintage")
        expected_lag = (
            self.source_vintage_date - self.selected_observation_date
        ).days
        if self.release_lag_days != expected_lag:
            raise ValueError("NFCI normalized release lag changed")
        return self


class S1NfciNormalizationExecutionAddendum(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-execution-addendum-v1"] = (
        "aurex-s1-nfci-normalization-execution-addendum-v1"
    )
    addendum_id: Literal["s1-nfci-normalization-execution-addendum-v1"] = (
        "s1-nfci-normalization-execution-addendum-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    acquisition_result_evidence_hash: str
    acquisition_audit_evidence_hash: str
    input_manifest_evidence_hash: str
    runner_contract_hash: str
    output_path: Literal[
        "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    result_path: Literal[
        "data/evidence/s1_nfci_normalization_result_v1.json"
    ] = "data/evidence/s1_nfci_normalization_result_v1.json"
    output_was_absent: Literal[True] = True
    result_was_absent: Literal[True] = True
    input_vintage_count: Literal[281] = 281
    synthetic_test_ids: tuple[str, ...] = Field(min_length=5)
    authorizes_single_normalization_run: Literal[True] = True
    authorizes_macro_source_values_only: Literal[True] = True
    authorizes_derived_features: Literal[False] = False
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
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUN"
    ] = S1_NFCI_NORMALIZATION_RUN
    addendum_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "acquisition_result_evidence_hash",
        "acquisition_audit_evidence_hash",
        "input_manifest_evidence_hash",
        "runner_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_addendum(self) -> S1NfciNormalizationExecutionAddendum:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization execution hash changed")
        return self


class S1NfciNormalizationExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-execution-audit-v1"] = (
        "aurex-s1-nfci-normalization-execution-audit-v1"
    )
    audit_id: Literal["s1-nfci-normalization-execution-audit-v1"] = (
        "s1-nfci-normalization-execution-audit-v1"
    )
    audited_at: datetime
    addendum_file_sha256: str
    addendum_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    raw_csv_files_opened: Literal[0] = 0
    source_value_rows_read: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_NORMALIZATION_EXECUTION_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_NORMALIZATION_EXECUTION_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_RUN"
    ] = S1_NFCI_NORMALIZATION_RUN
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "addendum_file_sha256",
        "addendum_evidence_hash",
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciNormalizationExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization execution audit hash changed")
        return self


class S1NfciNormalizationResult(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-result-v1"] = (
        "aurex-s1-nfci-normalization-result-v1"
    )
    result_id: Literal["s1-nfci-normalization-result-v1"] = (
        "s1-nfci-normalization-result-v1"
    )
    completed_at: datetime
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_addendum_file_sha256: str
    execution_addendum_evidence_hash: str
    runner_contract_hash: str
    acquisition_result_evidence_hash: str
    acquisition_audit_evidence_hash: str
    input_manifest_evidence_hash: str
    dataset_path: Literal[
        "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_normalized_v1.jsonl"
    dataset_file_sha256: str
    dataset_bytes: int = Field(ge=1)
    row_count: Literal[281] = 281
    row_evidence_hashes: tuple[str, ...] = Field(min_length=281, max_length=281)
    first_source_vintage_date: Literal["2017-08-17"] = "2017-08-17"
    last_source_vintage_date: Literal["2022-12-29"] = "2022-12-29"
    minimum_release_lag_days: int = Field(ge=0, le=21)
    maximum_release_lag_days: int = Field(ge=0, le=21)
    raw_files_rehashed: Literal[281] = 281
    aggregate_raw_bytes_rehashed: int = Field(ge=1)
    gates: tuple[S1SourceGate, ...] = Field(min_length=10, max_length=10)
    derived_feature_count: Literal[0] = 0
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION"] = (
        S1_NFCI_NORMALIZATION_PASS
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY"
    ] = S1_NFCI_NORMALIZATION_RESULT_NEXT
    authorizes_feature_definition_now: Literal[False] = False
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
    real_net_profit_usd: Literal["0"] = "0"
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("completed_at")
    @classmethod
    def normalize_completed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_addendum_file_sha256",
        "execution_addendum_evidence_hash",
        "runner_contract_hash",
        "acquisition_result_evidence_hash",
        "acquisition_audit_evidence_hash",
        "input_manifest_evidence_hash",
        "dataset_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("row_evidence_hashes")
    @classmethod
    def normalize_row_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_result(self) -> S1NfciNormalizationResult:
        if any(gate.status != "PASS" for gate in self.gates):
            raise ValueError("S1 NFCI normalization result contains a failed gate")
        if self.minimum_release_lag_days > self.maximum_release_lag_days:
            raise ValueError("S1 NFCI normalization lag bounds changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 NFCI normalization cannot contain BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization result hash changed")
        return self


class S1NfciNormalizationResultAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-normalization-result-audit-v1"] = (
        "aurex-s1-nfci-normalization-result-audit-v1"
    )
    audit_id: Literal["s1-nfci-normalization-result-audit-v1"] = (
        "s1-nfci-normalization-result-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    dataset_file_sha256: str
    runner_contract_hash: str
    auditor_source_sha256: str
    raw_file_count: Literal[281] = 281
    raw_manifest_evidence_hash: str
    aggregate_raw_bytes: int = Field(ge=1)
    row_count: Literal[281] = 281
    row_manifest_evidence_hash: str
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_NORMALIZATION_RESULT_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_NORMALIZATION_RESULT_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY"
    ] = S1_NFCI_NORMALIZATION_RESULT_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "dataset_file_sha256",
        "runner_contract_hash",
        "auditor_source_sha256",
        "raw_manifest_evidence_hash",
        "row_manifest_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciNormalizationResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI normalization result audit hash changed")
        return self
