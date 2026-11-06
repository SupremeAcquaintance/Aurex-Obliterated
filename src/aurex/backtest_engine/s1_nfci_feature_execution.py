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

S1_NFCI_FEATURE_RUN = "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUN"
S1_NFCI_FEATURE_PASS = "PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION"
S1_NFCI_FEATURE_RESULT_NEXT = (
    "AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
)


def validate_decimal_text(value: str) -> str:
    if value != value.strip():
        raise ValueError("S1 NFCI feature decimal has surrounding whitespace")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("S1 NFCI feature text is not a decimal") from error
    if not parsed.is_finite():
        raise ValueError("S1 NFCI feature decimal must be finite")
    return value


class S1NfciFeatureRow(BaseModel):
    sequence: int = Field(ge=5, le=281)
    target_id: str = Field(min_length=10)
    source_vintage_date: date
    selected_observation_date: date
    release_lag_days: int = Field(ge=0, le=21)
    source_normalized_row_sha256: str
    nfci_level: str = Field(min_length=1, max_length=64)
    nfci_change_1v: str = Field(min_length=1, max_length=64)
    nfci_change_4v: str = Field(min_length=1, max_length=64)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("source_normalized_row_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("nfci_level", "nfci_change_1v", "nfci_change_4v")
    @classmethod
    def validate_feature_decimal(cls, value: str) -> str:
        return validate_decimal_text(value)

    @model_validator(mode="after")
    def validate_row(self) -> S1NfciFeatureRow:
        if self.selected_observation_date > self.source_vintage_date:
            raise ValueError("S1 NFCI feature row is post-vintage")
        if (
            self.source_vintage_date - self.selected_observation_date
        ).days != self.release_lag_days:
            raise ValueError("S1 NFCI feature release lag changed")
        return self


class S1NfciFeatureExecutionAddendum(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-execution-addendum-v1"] = (
        "aurex-s1-nfci-feature-execution-addendum-v1"
    )
    addendum_id: Literal["s1-nfci-feature-execution-addendum-v1"] = (
        "s1-nfci-feature-execution-addendum-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    normalization_result_evidence_hash: str
    normalization_audit_evidence_hash: str
    normalized_dataset_file_sha256: str
    input_row_manifest_evidence_hash: str
    runner_contract_hash: str
    output_path: Literal[
        "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    result_path: Literal["data/evidence/s1_nfci_feature_result_v1.json"] = (
        "data/evidence/s1_nfci_feature_result_v1.json"
    )
    output_was_absent: Literal[True] = True
    result_was_absent: Literal[True] = True
    synthetic_test_ids: tuple[str, ...] = Field(min_length=5)
    authorizes_single_feature_run: Literal[True] = True
    authorizes_macro_source_values_only: Literal[True] = True
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
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUN"
    ] = S1_NFCI_FEATURE_RUN
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
        "normalization_result_evidence_hash",
        "normalization_audit_evidence_hash",
        "normalized_dataset_file_sha256",
        "input_row_manifest_evidence_hash",
        "runner_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_addendum(self) -> S1NfciFeatureExecutionAddendum:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected:
            raise ValueError("S1 NFCI feature execution hash changed")
        return self


class S1NfciFeatureExecutionAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-execution-audit-v1"] = (
        "aurex-s1-nfci-feature-execution-audit-v1"
    )
    audit_id: Literal["s1-nfci-feature-execution-audit-v1"] = (
        "s1-nfci-feature-execution-audit-v1"
    )
    audited_at: datetime
    addendum_file_sha256: str
    addendum_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    normalized_value_rows_parsed: Literal[0] = 0
    feature_rows_calculated: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_FEATURE_EXECUTION_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_FEATURE_EXECUTION_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_RUN"
    ] = S1_NFCI_FEATURE_RUN
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
    def validate_audit(self) -> S1NfciFeatureExecutionAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI feature execution audit hash changed")
        return self


class S1NfciFeatureResult(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-result-v1"] = (
        "aurex-s1-nfci-feature-result-v1"
    )
    result_id: Literal["s1-nfci-feature-result-v1"] = (
        "s1-nfci-feature-result-v1"
    )
    completed_at: datetime
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_addendum_file_sha256: str
    execution_addendum_evidence_hash: str
    runner_contract_hash: str
    normalization_result_evidence_hash: str
    normalization_audit_evidence_hash: str
    normalized_dataset_file_sha256: str
    input_row_manifest_evidence_hash: str
    feature_dataset_path: Literal[
        "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    ] = "data/evidence/datasets/s1_nfci_development_features_v1.jsonl"
    feature_dataset_file_sha256: str
    feature_dataset_bytes: int = Field(ge=1)
    input_row_count: Literal[281] = 281
    feature_row_count: Literal[277] = 277
    first_feature_sequence: Literal[5] = 5
    last_feature_sequence: Literal[281] = 281
    feature_count: Literal[3] = 3
    row_evidence_hashes: tuple[str, ...] = Field(min_length=277, max_length=277)
    gates: tuple[S1SourceGate, ...] = Field(min_length=10, max_length=10)
    strategy_candidates_created: Literal[0] = 0
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION"] = (
        S1_NFCI_FEATURE_PASS
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
    ] = S1_NFCI_FEATURE_RESULT_NEXT
    authorizes_strategy_rule_definition_now: Literal[False] = False
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
        "normalization_result_evidence_hash",
        "normalization_audit_evidence_hash",
        "normalized_dataset_file_sha256",
        "input_row_manifest_evidence_hash",
        "feature_dataset_file_sha256",
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
    def validate_result(self) -> S1NfciFeatureResult:
        if any(gate.status != "PASS" for gate in self.gates):
            raise ValueError("S1 NFCI feature result contains a failed gate")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 NFCI feature result cannot contain BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 NFCI feature result hash changed")
        return self


class S1NfciFeatureResultAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-feature-result-audit-v1"] = (
        "aurex-s1-nfci-feature-result-audit-v1"
    )
    audit_id: Literal["s1-nfci-feature-result-audit-v1"] = (
        "s1-nfci-feature-result-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    feature_dataset_file_sha256: str
    runner_contract_hash: str
    auditor_source_sha256: str
    input_row_count: Literal[281] = 281
    input_row_manifest_evidence_hash: str
    feature_row_count: Literal[277] = 277
    feature_row_manifest_evidence_hash: str
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_NFCI_FEATURE_RESULT_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_FEATURE_RESULT_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY"
    ] = S1_NFCI_FEATURE_RESULT_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "feature_dataset_file_sha256",
        "runner_contract_hash",
        "auditor_source_sha256",
        "input_row_manifest_evidence_hash",
        "feature_row_manifest_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciFeatureResultAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI feature result audit hash changed")
        return self
