from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

PREFLIGHT_PASS_DECISION = "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN"
PREFLIGHT_BLOCK_DECISION = "BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK"


class PeriodicFlowReusePreflightEvidence(BaseModel):
    month: str
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    family: Literal["aggTrades", "trades"]
    local_path: str
    archive_bytes: int = Field(gt=0, le=5_000_000_000)
    archive_sha256: str
    published_sha256: str
    zip_member_names: tuple[str, ...] = Field(min_length=1, max_length=2)
    zip_compressed_bytes_total: int = Field(gt=0)
    zip_uncompressed_bytes_total: int = Field(gt=0, le=60_000_000_000)
    member_policy: Literal[
        "EXACT_EXPECTED_MEMBER_ONLY",
        "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL",
    ]
    checksum_verified: Literal[True] = True
    zip_policy_verified: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("archive_sha256", "published_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> PeriodicFlowReusePreflightEvidence:
        special = self.month == "2021-12" and self.product == "SPOT"
        if (
            self.archive_sha256 != self.published_sha256
            or self.zip_member_names != tuple(sorted(set(self.zip_member_names)))
            or self.zip_compressed_bytes_total > self.archive_bytes
            or (len(self.zip_member_names) == 2) != special
            or (
                self.member_policy
                == "TOP_LEVEL_ONLY_IF_EXTRA_MEMBER_IS_BYTE_IDENTICAL"
            )
            != special
        ):
            raise ValueError("Q1 reuse preflight evidence changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.month, self.product


class PeriodicFlowAcquisitionPreflightResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-preflight-result-v1"
    ] = "aurex-q1-periodic-flow-full-development-preflight-result-v1"
    result_id: Literal[
        "q1-periodic-flow-full-development-preflight-result-v1"
    ] = "q1-periodic-flow-full-development-preflight-result-v1"
    generated_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    execution_contract_file_sha256: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    preflight_builder_contract_hash: str
    reuse_evidence: tuple[PeriodicFlowReusePreflightEvidence, ...] = Field(
        min_length=37,
        max_length=37,
    )
    reuse_manifest_hash: str
    reuse_candidate_count: Literal[37] = 37
    reuse_candidate_bytes: int = Field(gt=0)
    network_target_count: Literal[59] = 59
    network_requests_made: Literal[0] = 0
    payload_bytes_received: Literal[0] = 0
    free_disk_bytes: int = Field(ge=0)
    required_free_disk_bytes: Literal[120_000_000_000] = 120_000_000_000
    additional_free_disk_bytes_required: int = Field(ge=0)
    decision: Literal[
        "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN",
        "BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN",
        "NONE_UNTIL_DISK_PREFLIGHT_PASSES",
    ]
    price_or_quantity_values_parsed: tuple[str, ...] = ()
    features_calculated: tuple[str, ...] = ()
    outcomes_accessed: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=8)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "execution_contract_file_sha256",
        "execution_contract_evidence_hash",
        "runner_source_hash",
        "preflight_builder_contract_hash",
        "reuse_manifest_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowAcquisitionPreflightResult:
        keys = [item.key for item in self.reuse_evidence]
        passed = self.free_disk_bytes >= self.required_free_disk_bytes
        expected_decision = (
            PREFLIGHT_PASS_DECISION if passed else PREFLIGHT_BLOCK_DECISION
        )
        expected_authorization = (
            "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN"
            if passed
            else "NONE_UNTIL_DISK_PREFLIGHT_PASSES"
        )
        if (
            keys != sorted(keys)
            or len(keys) != len(set(keys))
            or self.reuse_candidate_bytes
            != sum(item.archive_bytes for item in self.reuse_evidence)
            or self.reuse_manifest_hash
            != universe_evidence_hash(
                {"reuse_evidence": [item.model_dump() for item in self.reuse_evidence]}
            )
            or self.additional_free_disk_bytes_required
            != max(0, self.required_free_disk_bytes - self.free_disk_bytes)
            or self.decision != expected_decision
            or self.next_authorization != expected_authorization
            or self.price_or_quantity_values_parsed
            or self.features_calculated
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 acquisition preflight result changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 acquisition preflight result hash changed")
        return self


class PeriodicFlowAcquisitionPreflightAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-full-development-preflight-audit-v1"
    ] = "aurex-q1-periodic-flow-full-development-preflight-audit-v1"
    audit_id: Literal[
        "q1-periodic-flow-full-development-preflight-audit-v1"
    ] = "q1-periodic-flow-full-development-preflight-audit-v1"
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    execution_contract_evidence_hash: str
    runner_source_hash: str
    auditor_contract_hash: str
    reuse_manifest_hash: str
    reuse_candidate_count: Literal[37] = 37
    reuse_checksums_and_zip_policy_reconstructed: Literal[True] = True
    disk_decision_arithmetic_verified: Literal[True] = True
    point_in_time_free_disk_observation_replayed: Literal[False] = False
    network_requests_made: Literal[0] = 0
    outcomes_accessed: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN",
        "BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "execution_contract_evidence_hash",
        "runner_source_hash",
        "auditor_contract_hash",
        "reuse_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowAcquisitionPreflightAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 acquisition preflight audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_preflight_result(**values) -> PeriodicFlowAcquisitionPreflightResult:
    payload = dict(values)
    payload["reuse_evidence"] = tuple(
        sorted(payload["reuse_evidence"], key=lambda item: item.key)
    )
    payload["reuse_manifest_hash"] = universe_evidence_hash(
        {"reuse_evidence": [item.model_dump() for item in payload["reuse_evidence"]]}
    )
    passed = payload["free_disk_bytes"] >= 120_000_000_000
    payload["additional_free_disk_bytes_required"] = max(
        0,
        120_000_000_000 - payload["free_disk_bytes"],
    )
    payload["decision"] = (
        PREFLIGHT_PASS_DECISION if passed else PREFLIGHT_BLOCK_DECISION
    )
    payload["next_authorization"] = (
        "AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_RUN"
        if passed
        else "NONE_UNTIL_DISK_PREFLIGHT_PASSES"
    )
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(
        PeriodicFlowAcquisitionPreflightResult,
        "result_evidence_hash",
        payload,
    )


def build_preflight_audit(**values) -> PeriodicFlowAcquisitionPreflightAudit:
    return _build(
        PeriodicFlowAcquisitionPreflightAudit,
        "audit_evidence_hash",
        values,
    )


def audit_preflight_result(result: PeriodicFlowAcquisitionPreflightResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_preflight_audit(audit: PeriodicFlowAcquisitionPreflightAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
