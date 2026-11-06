from __future__ import annotations

import base64
from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.s5_release_tag_source_remediation import (
    S5_RELEASE_REMEDIATION_GATES,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_RELEASE_REMEDIATION_RUN = "RUN_S5_RELEASE_TAG_SOURCE_REMEDIATION_ONCE"
S5_RELEASE_REMEDIATION_PASS = "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION"
S5_RELEASE_REMEDIATION_STOP = "STOP_S5_RELEASE_TAG_SOURCE_REMEDIATION"
S5_RELEASE_REMEDIATION_RESULT_NEXT = "FREEZE_S5_AMENDED_MEASUREMENT_PROTOCOL_ONLY"
S5_RELEASE_REMEDIATION_FAILURE_NEXT = (
    "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_FAILURE_ADJUDICATION_ONLY"
)


class S5ReleaseTagDiscoveryRecord(BaseModel):
    ref_name: str = Field(pattern=r"^refs/tags/")
    object_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    peeled_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    tag_type: Literal["ANNOTATED", "LIGHTWEIGHT"]
    fetch_refspec: str = Field(min_length=20)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_record(self) -> S5ReleaseTagDiscoveryRecord:
        if self.fetch_refspec != f"+{self.ref_name}:{self.ref_name}":
            raise ValueError("S5 release remediation refspec changed")
        if self.tag_type == "LIGHTWEIGHT" and (
            self.object_sha != self.peeled_commit_sha
        ):
            raise ValueError("S5 lightweight release discovery changed")
        return self


class S5ReleaseTagProcessTranscript(BaseModel):
    schema_version: Literal["aurex-s5-release-tag-process-transcript-v1"] = (
        "aurex-s5-release-tag-process-transcript-v1"
    )
    sequence: int = Field(ge=1, le=4)
    process_role: Literal[
        "REMOTE_TAG_DISCOVERY",
        "LOCAL_REACHABLE_COMMITS",
        "REMOTE_EXACT_TAG_FETCH",
        "LOCAL_TAG_VERIFICATION",
    ]
    started_at: datetime
    completed_at: datetime
    command: tuple[str, ...] = Field(min_length=4)
    network_process: bool
    return_code: int
    stdout_byte_count: int = Field(ge=0, le=16_777_216)
    stderr_byte_count: int = Field(ge=0, le=16_777_216)
    stdout_sha256: str
    stderr_sha256: str
    stdout_base64: str
    stderr_base64: str
    transcript_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("stdout_sha256", "stderr_sha256", "transcript_evidence_hash")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_transcript(self) -> S5ReleaseTagProcessTranscript:
        if self.completed_at < self.started_at:
            raise ValueError("S5 release process completion precedes start")
        try:
            stdout = base64.b64decode(self.stdout_base64, validate=True)
            stderr = base64.b64decode(self.stderr_base64, validate=True)
        except ValueError as exc:
            raise ValueError("S5 release process transcript base64 changed") from exc
        if self.stdout_byte_count != len(stdout):
            raise ValueError("S5 release process stdout framing changed")
        if self.stderr_byte_count != len(stderr):
            raise ValueError("S5 release process stderr framing changed")
        if self.stdout_sha256 != sha256(stdout).hexdigest():
            raise ValueError("S5 release process stdout hash changed")
        if self.stderr_sha256 != sha256(stderr).hexdigest():
            raise ValueError("S5 release process stderr hash changed")
        expected_roles = (
            (1, "REMOTE_TAG_DISCOVERY", True),
            (2, "LOCAL_REACHABLE_COMMITS", False),
            (3, "REMOTE_EXACT_TAG_FETCH", True),
            (4, "LOCAL_TAG_VERIFICATION", False),
        )
        if (self.sequence, self.process_role, self.network_process) not in expected_roles:
            raise ValueError("S5 release process sequence or network role changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"transcript_evidence_hash"})
        )
        if self.transcript_evidence_hash != expected_hash:
            raise ValueError("S5 release process transcript hash changed")
        return self


class S5ReleaseRemediationGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5ReleaseTagSourceRemediationExecutionContractV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-execution-contract-v1"
    ] = "aurex-s5-release-tag-source-remediation-execution-contract-v1"
    contract_id: Literal[
        "s5-release-tag-source-remediation-execution-contract-v1"
    ] = "s5-release-tag-source-remediation-execution-contract-v1"
    frozen_at: datetime
    status: Literal["FROZEN_EXECUTION_CONTRACT_ZERO_DISCOVERY_COPY_OR_FETCH"] = (
        "FROZEN_EXECUTION_CONTRACT_ZERO_DISCOVERY_COPY_OR_FETCH"
    )
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=2, max_length=2)
    source_binding_manifest_evidence_hash: str
    implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    implementation_binding_manifest_evidence_hash: str
    runner_contract_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    authorizes_single_remediation_run: Literal[True] = True
    expected_process_roles: tuple[str, ...] = (
        "REMOTE_TAG_DISCOVERY",
        "LOCAL_REACHABLE_COMMITS",
        "REMOTE_EXACT_TAG_FETCH",
        "LOCAL_TAG_VERIFICATION",
    )
    transcript_write_policy: Literal[
        "WRITE_ATOMIC_IMMEDIATELY_AFTER_EACH_PROCESS_BEFORE_INTERPRETATION"
    ] = "WRITE_ATOMIC_IMMEDIATELY_AFTER_EACH_PROCESS_BEFORE_INTERPRETATION"
    source_copy_policy: Literal[
        "PYTHON_COPYTREE_NO_SYMLINKS_THEN_EXACT_DIRECTORY_HASH"
    ] = "PYTHON_COPYTREE_NO_SYMLINKS_THEN_EXACT_DIRECTORY_HASH"
    shell_execution_permitted: Literal[False] = False
    environment_proxy_use_permitted: Literal[False] = False
    credential_helper_use_permitted: Literal[False] = False
    token_environment_access_permitted: Literal[False] = False
    original_repository_mutation_permitted: Literal[False] = False
    destination_overwrite_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    parameters_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    signals_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    result_path: Literal[
        "data/evidence/s5_release_tag_source_remediation_result_v1.json"
    ] = "data/evidence/s5_release_tag_source_remediation_result_v1.json"
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
        "runner_contract_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> S5ReleaseTagSourceRemediationExecutionContractV1:
        if self.expected_process_roles != (
            "REMOTE_TAG_DISCOVERY",
            "LOCAL_REACHABLE_COMMITS",
            "REMOTE_EXACT_TAG_FETCH",
            "LOCAL_TAG_VERIFICATION",
        ):
            raise ValueError("S5 release remediation process roles changed")
        for bindings in (self.source_bindings, self.implementation_bindings):
            paths = tuple(item.path for item in bindings)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 release remediation execution bindings changed")
        source_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        )
        runner_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.implementation_bindings)
        )
        if self.source_binding_manifest_evidence_hash != source_hash:
            raise ValueError("S5 release remediation execution source hash changed")
        if (
            self.implementation_binding_manifest_evidence_hash != runner_hash
            or self.runner_contract_hash != runner_hash
        ):
            raise ValueError("S5 release remediation runner contract changed")
        if any(
            (
                self.shell_execution_permitted,
                self.environment_proxy_use_permitted,
                self.credential_helper_use_permitted,
                self.token_environment_access_permitted,
                self.original_repository_mutation_permitted,
                self.destination_overwrite_permitted,
                self.market_values_permitted,
                self.returns_permitted,
                self.parameters_permitted,
                self.candidates_permitted,
                self.signals_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 release remediation execution grants forbidden authority")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("S5 release remediation execution contract hash changed")
        return self


class S5ReleaseTagSourceRemediationExecutionContractAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-execution-contract-audit-v1"
    ] = "aurex-s5-release-tag-source-remediation-execution-contract-audit-v1"
    audit_id: Literal[
        "s5-release-tag-source-remediation-execution-contract-audit-v1"
    ] = "s5-release-tag-source-remediation-execution-contract-audit-v1"
    audited_at: datetime
    contract_file_sha256: str
    contract_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    source_binding_manifest_evidence_hash: str
    implementation_binding_manifest_evidence_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    discovery_processes_executed: Literal[0] = 0
    repository_copies_executed: Literal[0] = 0
    fetch_processes_executed: Literal[0] = 0
    network_processes_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION_EXECUTION_CONTRACT_AUDIT"
    ] = "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION_EXECUTION_CONTRACT_AUDIT"
    next_authorization: Literal[
        "RUN_S5_RELEASE_TAG_SOURCE_REMEDIATION_ONCE"
    ] = S5_RELEASE_REMEDIATION_RUN
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
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(
        self,
    ) -> S5ReleaseTagSourceRemediationExecutionContractAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 release remediation execution auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 release remediation execution auditor hash changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 release remediation execution audit hash changed")
        return self


class S5ReleaseTagSourceRemediationResultV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-release-tag-source-remediation-result-v1"
    ] = "aurex-s5-release-tag-source-remediation-result-v1"
    result_id: Literal[
        "s5-release-tag-source-remediation-result-v1"
    ] = "s5-release-tag-source-remediation-result-v1"
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0, le=86_400)
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    original_history_dataset_directory_sha256: str
    original_history_dataset_unchanged: bool
    destination_copy_completed: bool
    destination_prefetch_directory_sha256: str | None
    destination_final_directory_sha256: str | None
    destination_initial_byte_count: int | None = Field(default=None, ge=0)
    destination_final_byte_count: int | None = Field(default=None, ge=0)
    destination_growth_bytes: int | None = Field(default=None, ge=0, le=536_870_912)
    transcript_paths: tuple[str, ...] = Field(max_length=4)
    transcript_file_sha256s: tuple[str, ...] = Field(max_length=4)
    process_count: int = Field(ge=0, le=4)
    local_process_count: int = Field(ge=0, le=2)
    network_process_count: int = Field(ge=0, le=2)
    remote_tag_ref_record_count: int | None = Field(default=None, ge=0)
    reachable_commit_count: int | None = Field(default=None, ge=0, le=50_395)
    selected_stable_tag_count: int | None = Field(default=None, ge=0, le=500)
    selected_annotated_tag_count: int | None = Field(default=None, ge=0, le=500)
    selected_lightweight_tag_count: int | None = Field(default=None, ge=0, le=500)
    selected_tag_manifest_evidence_hash: str | None
    verified_tag_count: int | None = Field(default=None, ge=0, le=500)
    remote_ref_drift_count: int | None = Field(default=None, ge=0, le=500)
    gate_results: tuple[S5ReleaseRemediationGateResult, ...] = Field(
        min_length=16,
        max_length=16,
    )
    passed_gate_count: int = Field(ge=0, le=16)
    failed_gate_count: int = Field(ge=0, le=16)
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_RELEASE_TAG_SOURCE_REMEDIATION",
        "STOP_S5_RELEASE_TAG_SOURCE_REMEDIATION",
    ]
    next_authorization: Literal[
        "FREEZE_S5_AMENDED_MEASUREMENT_PROTOCOL_ONLY",
        "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_FAILURE_ADJUDICATION_ONLY",
    ]
    authorizes_amended_measurement_protocol: bool
    authorizes_market_values: Literal[False] = False
    authorizes_returns: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_signals: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    failure_type: str | None
    failure_message: str | None = Field(default=None, max_length=2_000)
    limitations: tuple[str, ...] = Field(min_length=8)
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
        "original_history_dataset_directory_sha256",
        "destination_prefetch_directory_sha256",
        "destination_final_directory_sha256",
        "selected_tag_manifest_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @field_validator("transcript_file_sha256s")
    @classmethod
    def normalize_hash_set(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_result(self) -> S5ReleaseTagSourceRemediationResultV1:
        if self.completed_at < self.started_at:
            raise ValueError("S5 release remediation completion precedes start")
        if tuple(item.gate_id for item in self.gate_results) != S5_RELEASE_REMEDIATION_GATES:
            raise ValueError("S5 release remediation result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (
            passed,
            len(self.gate_results) - passed,
        ):
            raise ValueError("S5 release remediation gate accounting changed")
        if self.process_count != self.local_process_count + self.network_process_count:
            raise ValueError("S5 release remediation process accounting changed")
        if len(self.transcript_paths) != self.process_count or len(
            self.transcript_file_sha256s
        ) != self.process_count:
            raise ValueError("S5 release remediation transcript accounting changed")
        successful = self.failed_gate_count == 0
        bound_hashes = (
            self.protocol_evidence_hash,
            self.protocol_audit_evidence_hash,
            self.execution_contract_evidence_hash,
            self.execution_contract_audit_evidence_hash,
            self.runner_contract_hash,
            self.original_history_dataset_directory_sha256,
            self.destination_prefetch_directory_sha256,
            self.destination_final_directory_sha256,
            self.selected_tag_manifest_evidence_hash,
            *self.transcript_file_sha256s,
        )
        exact_pass = (
            self.elapsed_seconds <= 1_800
            and all(value is not None and value != "0" * 64 for value in bound_hashes)
            and self.original_history_dataset_unchanged
            and self.destination_copy_completed
            and self.destination_prefetch_directory_sha256
            == self.original_history_dataset_directory_sha256
            and self.destination_final_directory_sha256 is not None
            and self.destination_initial_byte_count is not None
            and self.destination_final_byte_count is not None
            and self.destination_growth_bytes is not None
            and self.process_count == 4
            and self.local_process_count == 2
            and self.network_process_count == 2
            and self.remote_tag_ref_record_count is not None
            and self.reachable_commit_count == 50_395
            and self.selected_stable_tag_count is not None
            and self.selected_stable_tag_count > 0
            and self.selected_annotated_tag_count is not None
            and self.selected_lightweight_tag_count is not None
            and self.selected_annotated_tag_count + self.selected_lightweight_tag_count
            == self.selected_stable_tag_count
            and self.selected_tag_manifest_evidence_hash is not None
            and self.verified_tag_count == self.selected_stable_tag_count
            and self.remote_ref_drift_count == 0
            and self.failure_type is None
            and self.failure_message is None
        )
        if successful != exact_pass:
            raise ValueError("S5 release remediation pass accounting changed")
        if successful != (
            self.decision == S5_RELEASE_REMEDIATION_PASS
            and self.next_authorization == S5_RELEASE_REMEDIATION_RESULT_NEXT
            and self.authorizes_amended_measurement_protocol
        ):
            raise ValueError("S5 release remediation pass decision changed")
        if not successful and (
            self.decision != S5_RELEASE_REMEDIATION_STOP
            or self.next_authorization != S5_RELEASE_REMEDIATION_FAILURE_NEXT
            or self.authorizes_amended_measurement_protocol
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("S5 release remediation stop evidence changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("S5 release remediation result hash changed")
        return self
