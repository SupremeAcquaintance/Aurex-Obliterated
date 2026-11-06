from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_nfci_full_execution import S1_NFCI_EXECUTION_NEXT
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)


class S1NfciAcquisitionExecutionAmendmentV2(BaseModel):
    schema_version: Literal["aurex-s1-nfci-acquisition-execution-amendment-v2"] = (
        "aurex-s1-nfci-acquisition-execution-amendment-v2"
    )
    addendum_id: Literal["s1-nfci-acquisition-execution-amendment-v2"] = (
        "s1-nfci-acquisition-execution-amendment-v2"
    )
    frozen_at: datetime
    builder_contract_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    v1_addendum_file_sha256: str
    v1_addendum_evidence_hash: str
    v1_audit_file_sha256: str
    v1_audit_evidence_hash: str
    v1_runner_contract_hash: str
    failure_classification: Literal[
        "PRE_NETWORK_ATOMIC_RENAME_RESPONSE_MARKER_RESTART_DEFECT"
    ] = "PRE_NETWORK_ATOMIC_RENAME_RESPONSE_MARKER_RESTART_DEFECT"
    correction_scope: tuple[str, ...] = Field(min_length=2)
    runner_contract_hash: str
    evidence_root: Literal[
        "data/evidence/source_snapshots/s1_nfci_full_acquisition_v1"
    ] = "data/evidence/source_snapshots/s1_nfci_full_acquisition_v1"
    evidence_root_was_absent_or_empty: Literal[True] = True
    free_disk_bytes_observed: int = Field(ge=250000000)
    target_count: Literal[281] = 281
    maximum_get_attempts: Literal[843] = 843
    maximum_total_payload_bytes: Literal[56200000] = 56_200_000
    pre_correction_network_requests: Literal[0] = 0
    pre_correction_payload_bytes: Literal[0] = 0
    synthetic_test_ids: tuple[str, ...] = Field(min_length=1)
    authorizes_network_acquisition: Literal[True] = True
    authorizes_macro_source_values_only: Literal[True] = True
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
    ] = S1_NFCI_EXECUTION_NEXT
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
        "v1_addendum_file_sha256",
        "v1_addendum_evidence_hash",
        "v1_audit_file_sha256",
        "v1_audit_evidence_hash",
        "v1_runner_contract_hash",
        "runner_contract_hash",
        "addendum_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> S1NfciAcquisitionExecutionAmendmentV2:
        if self.v1_runner_contract_hash == self.runner_contract_hash:
            raise ValueError("S1 NFCI v2 runner hash did not change")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"addendum_evidence_hash"})
        )
        if self.addendum_evidence_hash != expected:
            raise ValueError("S1 NFCI v2 execution amendment hash changed")
        return self


class S1NfciAcquisitionExecutionAuditV2(BaseModel):
    schema_version: Literal["aurex-s1-nfci-acquisition-execution-audit-v2"] = (
        "aurex-s1-nfci-acquisition-execution-audit-v2"
    )
    audit_id: Literal["s1-nfci-acquisition-execution-audit-v2"] = (
        "s1-nfci-acquisition-execution-audit-v2"
    )
    audited_at: datetime
    addendum_file_sha256: str
    addendum_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_source_sha256: str
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    payload_bytes_observed: Literal[0] = 0
    decision: Literal["PASS_S1_NFCI_EXECUTION_V2_RECONSTRUCTED"] = (
        "PASS_S1_NFCI_EXECUTION_V2_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION"
    ] = S1_NFCI_EXECUTION_NEXT
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
    def validate_audit(self) -> S1NfciAcquisitionExecutionAuditV2:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 NFCI v2 execution audit hash changed")
        return self
