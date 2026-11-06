from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (
    S5_TARGETED_CORRECTION_GATE_IDS,
    S5_TARGETED_CORRECTION_RUN,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_TARGETED_CORRECTION_PASS = "PASS_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
S5_TARGETED_CORRECTION_STOP = (
    "STOP_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_REQUIRES_FAILURE_ADJUDICATION"
)
S5_TARGETED_CORRECTION_NEXT = (
    "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_ONLY"
)
S5_TARGETED_CORRECTION_FAILURE_NEXT = (
    "FREEZE_S5_GITHUB_TARGETED_ACQUISITION_FAILURE_ADJUDICATION_ONLY"
)


class S5TargetedCorrectionExecutionContract(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-execution-contract-v1"
    ] = "aurex-s5-targeted-correction-execution-contract-v1"
    contract_id: Literal["s5-targeted-correction-execution-contract-v1"] = (
        "s5-targeted-correction-execution-contract-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_EXECUTION_CONTRACT_ZERO_REQUESTS"] = (
        "FROZEN_EXECUTION_CONTRACT_ZERO_REQUESTS"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=2, max_length=2)
    source_binding_manifest_evidence_hash: str
    implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=3, max_length=3
    )
    implementation_binding_manifest_evidence_hash: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    target_manifest_evidence_hash: str
    target_count: Literal[194] = 194
    maximum_github_request_count: Literal[194] = 194
    maximum_local_git_process_count: Literal[2] = 2
    crash_marker_required_before_request: Literal[True] = True
    incomplete_attempt_retry_forbidden: Literal[True] = True
    completed_response_resume_permitted: Literal[True] = True
    credentials_permitted: Literal[False] = False
    environment_proxy_permitted: Literal[False] = False
    redirects_permitted: Literal[False] = False
    concurrency_permitted: Literal[False] = False
    mapping_rule_change_permitted: Literal[False] = False
    accepted_event_creation_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    orders_permitted: Literal[False] = False
    result_path: Literal[
        "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
    ] = "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
    runner_contract_hash: str
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
    ] = S5_TARGETED_CORRECTION_RUN
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "target_manifest_evidence_hash",
        "runner_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5TargetedCorrectionExecutionContract:
        for bindings in (self.source_bindings, self.implementation_bindings):
            paths = tuple(binding.path for binding in bindings)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 targeted execution bindings changed")
        source_hash = universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in self.source_bindings)
        )
        implementation_hash = universe_evidence_hash(
            tuple(
                binding.model_dump(mode="json")
                for binding in self.implementation_bindings
            )
        )
        if (
            self.source_binding_manifest_evidence_hash != source_hash
            or self.implementation_binding_manifest_evidence_hash
            != implementation_hash
        ):
            raise ValueError("S5 targeted execution binding hash changed")
        forbidden = (
            self.credentials_permitted,
            self.environment_proxy_permitted,
            self.redirects_permitted,
            self.concurrency_permitted,
            self.mapping_rule_change_permitted,
            self.accepted_event_creation_permitted,
            self.market_values_permitted,
            self.returns_permitted,
            self.orders_permitted,
        )
        if any(forbidden):
            raise ValueError("S5 targeted execution contract grants forbidden authority")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("S5 targeted execution contract hash changed")
        return self


class S5TargetedCorrectionExecutionContractAudit(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-correction-execution-contract-audit-v1"
    ] = "aurex-s5-targeted-correction-execution-contract-audit-v1"
    audit_id: Literal["s5-targeted-correction-execution-contract-audit-v1"] = (
        "s5-targeted-correction-execution-contract-audit-v1"
    )
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    source_binding_manifest_evidence_hash: str
    implementation_binding_manifest_evidence_hash: str
    auditor_source_sha256: str
    source_binding_count: Literal[2] = 2
    implementation_binding_count: Literal[3] = 3
    requests_executed: Literal[0] = 0
    local_git_processes_executed: Literal[0] = 0
    reconstructed_exactly: Literal[True] = True
    decision: Literal["PASS_S5_TARGETED_CORRECTION_EXECUTION_CONTRACT_AUDIT"] = (
        "PASS_S5_TARGETED_CORRECTION_EXECUTION_CONTRACT_AUDIT"
    )
    next_authorization: Literal[
        "RUN_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION"
    ] = S5_TARGETED_CORRECTION_RUN
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "builder_contract_hash",
        "runner_contract_hash",
        "source_binding_manifest_evidence_hash",
        "implementation_binding_manifest_evidence_hash",
        "auditor_source_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5TargetedCorrectionExecutionContractAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 targeted execution contract audit hash changed")
        return self


class S5TargetedCorrectionResponseBinding(BaseModel):
    sequence: int = Field(ge=1, le=194)
    pull_number: int = Field(gt=0)
    path: str = Field(min_length=1)
    file_sha256: str
    file_byte_count: int = Field(gt=0)
    response_body_sha256: str
    response_body_byte_count: int = Field(gt=0, le=2_097_152)
    http_status: Literal[200, 404]
    rate_limit: Literal[60] = 60
    rate_remaining: int = Field(ge=0, le=59)
    rate_reset: int = Field(gt=0)
    response_identity_verified: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("file_sha256", "response_body_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)


class S5TargetedCorrectionCommitDiagnostic(BaseModel):
    sequence: int = Field(ge=1, le=83)
    pull_number: int = Field(gt=0)
    census_merge_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    parent_count: int = Field(ge=2)
    first_line: str = Field(max_length=300)
    first_line_sha256: str
    census_first_line_sha256: str
    first_line_hash_matches_census: Literal[True] = True

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("first_line_sha256", "census_first_line_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_diagnostic(self) -> S5TargetedCorrectionCommitDiagnostic:
        if self.first_line_sha256 != self.census_first_line_sha256:
            raise ValueError("S5 targeted commit diagnostic changed")
        return self


class S5TargetedCorrectionGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5TargetedCompletenessCorrectionResult(BaseModel):
    schema_version: Literal[
        "aurex-s5-targeted-completeness-correction-result-v1"
    ] = "aurex-s5-targeted-completeness-correction-result-v1"
    result_id: Literal["s5-targeted-completeness-correction-result-v1"] = (
        "s5-targeted-completeness-correction-result-v1"
    )
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0, le=21_600)
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    target_manifest_evidence_hash: str
    history_dataset_directory_sha256: str
    full_graph_stream_sha256: str | None
    full_graph_commit_count: int = Field(ge=0, le=100_000)
    first_parent_commit_count: int = Field(ge=0, le=20_000)
    first_parent_merge_count: int = Field(ge=0, le=20_000)
    recognized_target_reachable_count: int = Field(ge=0, le=83)
    commit_diagnostics: tuple[S5TargetedCorrectionCommitDiagnostic, ...] = Field(
        max_length=83
    )
    raw_response_directory: str = Field(min_length=1)
    response_bindings: tuple[S5TargetedCorrectionResponseBinding, ...] = Field(
        max_length=194
    )
    request_attempt_marker_count: int = Field(ge=0, le=194)
    logical_request_attempt_count: int = Field(ge=0, le=194)
    new_request_attempt_count: int = Field(ge=0, le=194)
    resumed_response_count: int = Field(ge=0, le=194)
    http_200_count: int = Field(ge=0, le=194)
    http_404_count: int = Field(ge=0, le=194)
    total_response_bytes: int = Field(ge=0, le=268_435_456)
    rate_limit_wait_count: int = Field(ge=0, le=194)
    rate_limit_wait_seconds: float = Field(ge=0, le=21_600)
    local_git_process_count: int = Field(ge=0, le=2)
    gate_results: tuple[S5TargetedCorrectionGateResult, ...] = Field(
        min_length=11, max_length=11
    )
    passed_gate_count: int = Field(ge=0, le=11)
    failed_gate_count: int = Field(ge=0, le=11)
    btc_market_values_read: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    mapping_rules_changed: Literal[False] = False
    accepted_events_created: Literal[0] = 0
    original_normalization_stop_upheld: Literal[True] = True
    decision: Literal[
        "PASS_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION",
        "STOP_S5_GITHUB_TARGETED_COMPLETENESS_ACQUISITION_REQUIRES_FAILURE_ADJUDICATION",
    ]
    next_authorization: Literal[
        "FREEZE_S5_GITHUB_CORRECTED_NORMALIZATION_PROTOCOL_ONLY",
        "FREEZE_S5_GITHUB_TARGETED_ACQUISITION_FAILURE_ADJUDICATION_ONLY",
    ]
    failure_type: str | None
    failure_message: str | None = Field(max_length=2000)
    failure_artifact_path: str | None
    failure_artifact_sha256: str | None
    limitations: tuple[str, ...] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "runner_contract_hash",
        "target_manifest_evidence_hash",
        "history_dataset_directory_sha256",
        "full_graph_stream_sha256",
        "failure_artifact_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> S5TargetedCompletenessCorrectionResult:
        if self.completed_at < self.started_at:
            raise ValueError("S5 targeted correction completion precedes start")
        if tuple(gate.gate_id for gate in self.gate_results) != (
            S5_TARGETED_CORRECTION_GATE_IDS
        ):
            raise ValueError("S5 targeted correction result gates changed")
        passed = sum(gate.status == "PASS" for gate in self.gate_results)
        failed = len(self.gate_results) - passed
        if (self.passed_gate_count, self.failed_gate_count) != (passed, failed):
            raise ValueError("S5 targeted correction gate accounting changed")
        response_sequences = tuple(row.sequence for row in self.response_bindings)
        response_numbers = tuple(row.pull_number for row in self.response_bindings)
        if (
            response_sequences != tuple(range(1, len(response_sequences) + 1))
            or len(set(response_numbers)) != len(response_numbers)
        ):
            raise ValueError("S5 targeted response bindings changed")
        diagnostic_sequences = tuple(row.sequence for row in self.commit_diagnostics)
        diagnostic_numbers = tuple(row.pull_number for row in self.commit_diagnostics)
        if (
            diagnostic_sequences != tuple(range(1, len(diagnostic_sequences) + 1))
            or len(set(diagnostic_numbers)) != len(diagnostic_numbers)
        ):
            raise ValueError("S5 targeted commit diagnostics changed")
        if self.http_200_count + self.http_404_count != len(self.response_bindings):
            raise ValueError("S5 targeted HTTP accounting changed")
        if self.logical_request_attempt_count != (
            self.new_request_attempt_count + self.resumed_response_count
        ):
            raise ValueError("S5 targeted request accounting changed")
        successful = self.failed_gate_count == 0
        exact_pass = (
            len(self.response_bindings) == 194
            and self.request_attempt_marker_count == 194
            and self.logical_request_attempt_count == 194
            and len(self.commit_diagnostics) == 83
            and self.recognized_target_reachable_count == 83
            and self.local_git_process_count == 2
            and self.full_graph_stream_sha256 is not None
            and self.failure_type is None
            and self.failure_message is None
            and self.failure_artifact_path is None
            and self.failure_artifact_sha256 is None
        )
        if successful != exact_pass:
            raise ValueError("S5 targeted correction pass accounting changed")
        if successful != (
            self.decision == S5_TARGETED_CORRECTION_PASS
            and self.next_authorization == S5_TARGETED_CORRECTION_NEXT
        ):
            raise ValueError("S5 targeted correction pass decision changed")
        if not successful and (
            self.decision != S5_TARGETED_CORRECTION_STOP
            or self.next_authorization != S5_TARGETED_CORRECTION_FAILURE_NEXT
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("Failed S5 targeted correction lacks stop evidence")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("S5 targeted correction result hash changed")
        return self
