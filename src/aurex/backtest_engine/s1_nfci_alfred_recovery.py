from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s1_nfci_raw_pilot import (
    S1NfciPilotDownload,
    S1NfciVintageComparison,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S1_ALFRED_PASS = "PASS_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY"
S1_ALFRED_STOP = "STOP_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY_FAILED"
S1_ALFRED_NEXT = "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY"


class S1NfciAlfredTarget(BaseModel):
    target_id: Literal["01-nfci-vintage-2020", "02-nfci-vintage-2021"]
    vintage_date: date
    url: str = Field(min_length=20)
    expected_final_host: Literal["alfred.stlouisfed.org"] = "alfred.stlouisfed.org"
    expected_value_column: str = Field(pattern=r"^NFCI_[0-9]{8}$")
    raw_path: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S1NfciAlfredRecoveryProtocol(BaseModel):
    schema_version: Literal["aurex-s1-nfci-alfred-recovery-protocol-v1"] = (
        "aurex-s1-nfci-alfred-recovery-protocol-v1"
    )
    protocol_id: Literal["s1-nfci-alfred-recovery-protocol-v1"] = (
        "s1-nfci-alfred-recovery-protocol-v1"
    )
    frozen_at: datetime
    builder_contract_hash: str
    failed_pilot_protocol_file_sha256: str
    failed_pilot_protocol_evidence_hash: str
    failed_pilot_result_file_sha256: str
    failed_pilot_result_evidence_hash: str
    failed_pilot_audit_file_sha256: str
    failed_pilot_audit_evidence_hash: str
    failed_pilot_decision: Literal["STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED"]
    failure_classification: Literal[
        "FREDGRAPH_IGNORED_VINTAGE_DATE_AND_RETURNED_IDENTICAL_CURRENT_DATA"
    ]
    remediation_scope: Literal[
        "REPLACE_FREDGRAPH_CURRENT_TRANSPORT_WITH_ALFREDGRAPH_VINTAGE_TRANSPORT_ONLY"
    ]
    source_documentation_urls: tuple[str, ...] = Field(min_length=3)
    targets: tuple[S1NfciAlfredTarget, ...] = Field(min_length=2, max_length=2)
    request_budget: Literal[2] = 2
    retry_budget: Literal[0] = 0
    maximum_payload_bytes_per_target: Literal[1000000] = 1_000_000
    maximum_total_payload_bytes: Literal[2000000] = 2_000_000
    connect_timeout_seconds: Literal[60] = 60
    chunk_size_bytes: Literal[65536] = 65_536
    earliest_required_observation_date: Literal["2017-08-17"] = "2017-08-17"
    maximum_release_lag_days: Literal[21] = 21
    minimum_valid_rows_per_target: Literal[100] = 100
    feasibility_gates: tuple[str, ...] = Field(min_length=1)
    macro_numeric_fields_inspected: tuple[Literal["NFCI"], ...] = ("NFCI",)
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    authorizes_exactly_two_payload_gets: Literal[True] = True
    authorizes_raw_payload_persistence: Literal[True] = True
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_candidate: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "failed_pilot_protocol_file_sha256",
        "failed_pilot_protocol_evidence_hash",
        "failed_pilot_result_file_sha256",
        "failed_pilot_result_evidence_hash",
        "failed_pilot_audit_file_sha256",
        "failed_pilot_audit_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S1NfciAlfredRecoveryProtocol:
        ids = tuple(target.target_id for target in self.targets)
        vintages = tuple(target.vintage_date for target in self.targets)
        if ids != ("01-nfci-vintage-2020", "02-nfci-vintage-2021"):
            raise ValueError("S1 ALFRED target identities changed")
        if vintages != (date(2020, 1, 1), date(2021, 1, 1)):
            raise ValueError("S1 ALFRED vintage dates changed")
        if self.maximum_total_payload_bytes != (
            self.maximum_payload_bytes_per_target * self.request_budget
        ):
            raise ValueError("S1 ALFRED byte budget changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 ALFRED recovery cannot inspect BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("S1 ALFRED protocol evidence hash changed")
        return self


class S1NfciAlfredRecoveryResult(BaseModel):
    schema_version: Literal["aurex-s1-nfci-alfred-recovery-result-v1"] = (
        "aurex-s1-nfci-alfred-recovery-result-v1"
    )
    result_id: Literal["s1-nfci-alfred-recovery-result-v1"] = (
        "s1-nfci-alfred-recovery-result-v1"
    )
    completed_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    runner_source_sha256: str
    downloads: tuple[S1NfciPilotDownload, ...] = Field(min_length=2, max_length=2)
    comparison: S1NfciVintageComparison
    gates: tuple[S1SourceGate, ...] = Field(min_length=1)
    request_count: Literal[2] = 2
    retry_count: Literal[0] = 0
    total_payload_bytes: int = Field(ge=0)
    macro_numeric_fields_inspected: tuple[Literal["NFCI"], ...] = ("NFCI",)
    btc_market_fields_inspected: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    decision: Literal[
        "PASS_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY",
        "STOP_S1_ALFRED_POINT_IN_TIME_SOURCE_RECOVERY_FAILED",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY",
        "NONE_S1_ALFRED_SOURCE_RECOVERY_FAILED",
    ]
    authorizes_parameter_definition: Literal[False] = False
    authorizes_btc_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
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
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "runner_source_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S1NfciAlfredRecoveryResult:
        ids = tuple(download.target_id for download in self.downloads)
        if ids != ("01-nfci-vintage-2020", "02-nfci-vintage-2021"):
            raise ValueError("S1 ALFRED result download identity changed")
        if self.total_payload_bytes != sum(item.payload_bytes for item in self.downloads):
            raise ValueError("S1 ALFRED result payload bytes do not reconcile")
        failed = any(gate.status == "FAIL" for gate in self.gates)
        if self.decision != (S1_ALFRED_STOP if failed else S1_ALFRED_PASS):
            raise ValueError("S1 ALFRED decision does not match gates")
        expected_next = (
            "NONE_S1_ALFRED_SOURCE_RECOVERY_FAILED" if failed else S1_ALFRED_NEXT
        )
        if self.next_authorization != expected_next:
            raise ValueError("S1 ALFRED next authorization changed")
        if self.btc_market_fields_inspected or self.return_metrics_calculated:
            raise ValueError("S1 ALFRED result cannot contain BTC outcomes")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S1 ALFRED result evidence hash changed")
        return self


class S1NfciAlfredRecoveryAudit(BaseModel):
    schema_version: Literal["aurex-s1-nfci-alfred-recovery-audit-v1"] = (
        "aurex-s1-nfci-alfred-recovery-audit-v1"
    )
    audit_id: Literal["s1-nfci-alfred-recovery-audit-v1"] = (
        "s1-nfci-alfred-recovery-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_file_sha256: str
    result_evidence_hash: str
    runner_source_sha256: str
    auditor_source_sha256: str
    raw_file_sha256: dict[str, str]
    raw_file_bytes: dict[str, int]
    raw_file_count: Literal[2] = 2
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S1_ALFRED_SOURCE_RECOVERY_RECONSTRUCTED"] = (
        "PASS_S1_ALFRED_SOURCE_RECOVERY_RECONSTRUCTED"
    )
    next_authorization: Literal[
        "AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY"
    ] = S1_ALFRED_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "runner_source_sha256",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("raw_file_sha256")
    @classmethod
    def normalize_raw_hashes(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: normalize_sha256(digest) for key, digest in sorted(value.items())}

    @model_validator(mode="after")
    def validate_audit(self) -> S1NfciAlfredRecoveryAudit:
        if (
            len(self.raw_file_sha256) != self.raw_file_count
            or set(self.raw_file_sha256) != set(self.raw_file_bytes)
        ):
            raise ValueError("S1 ALFRED audit raw-file maps changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S1 ALFRED audit evidence hash changed")
        return self
