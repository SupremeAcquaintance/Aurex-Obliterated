from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_accepted_development_measurement_protocol import (
    S5_MEASUREMENT_GATES,
    S5_MEASUREMENT_OUTPUT_FIELDS,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_MEASUREMENT_RUN = "RUN_S5_ACCEPTED_DEVELOPMENT_MEASUREMENTS_ONCE"
S5_MEASUREMENT_PASS = "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_CONSTRUCTION"
S5_MEASUREMENT_STOP = "STOP_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_CONSTRUCTION"
S5_MEASUREMENT_RESULT_NEXT = (
    "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT_ONLY"
)
S5_MEASUREMENT_FAILURE_NEXT = (
    "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_FAILURE_ADJUDICATION_ONLY"
)


class S5AcceptedDevelopmentMonthlyMeasurementRow(BaseModel):
    sequence: int = Field(gt=0, le=212)
    month_start: date
    month_end_exclusive: date
    measurement_available_at: datetime
    primary_source_verified_accepted_pull_count: int = Field(ge=0)
    primary_distinct_local_source_commit_count: int = Field(ge=0)
    primary_many_to_one_excess_count: int = Field(ge=0)
    all_accepted_pull_count: int = Field(ge=0)
    source_unverified_accepted_pull_count: int = Field(ge=0)
    canonical_integration_count: int = Field(ge=0)
    canonical_github_time_count: int = Field(ge=0)
    canonical_git_fallback_time_count: int = Field(ge=0)
    known_human_or_unresolved_actor_count: int = Field(ge=0)
    unknown_actor_event_count: int = Field(ge=0)
    human_contributor_lower_bound: int = Field(ge=0)
    human_contributor_upper_bound: int = Field(ge=0)
    known_bot_actor_count: int = Field(ge=0)
    canonical_component_key_count: int = Field(ge=0)
    unresolved_git_merge_count: int = Field(ge=0)
    stable_release_tag_count: int = Field(ge=0)
    signed_annotated_stable_release_tag_count: int = Field(ge=0)
    primary_event_manifest_evidence_hash: str
    canonical_event_manifest_evidence_hash: str
    component_key_manifest_evidence_hash: str
    release_tag_manifest_evidence_hash: str
    source_normalization_result_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("measurement_available_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "primary_event_manifest_evidence_hash",
        "canonical_event_manifest_evidence_hash",
        "component_key_manifest_evidence_hash",
        "release_tag_manifest_evidence_hash",
        "source_normalization_result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_row(self) -> S5AcceptedDevelopmentMonthlyMeasurementRow:
        if tuple(type(self).model_fields) != S5_MEASUREMENT_OUTPUT_FIELDS:
            raise ValueError("S5 monthly measurement output schema changed")
        if self.month_end_exclusive <= self.month_start:
            raise ValueError("S5 monthly measurement interval changed")
        if self.month_start.day != 1 or self.month_end_exclusive.day != 1:
            raise ValueError("S5 monthly measurement boundary changed")
        expected_available = datetime.combine(
            self.month_end_exclusive + timedelta(days=7),
            datetime.min.time(),
            tzinfo=UTC,
        )
        if self.measurement_available_at != expected_available:
            raise ValueError("S5 monthly measurement availability lag changed")
        if self.primary_distinct_local_source_commit_count > (
            self.primary_source_verified_accepted_pull_count
        ):
            raise ValueError("S5 monthly primary source commit accounting changed")
        if self.primary_many_to_one_excess_count != (
            self.primary_source_verified_accepted_pull_count
            - self.primary_distinct_local_source_commit_count
        ):
            raise ValueError("S5 monthly many-to-one accounting changed")
        if self.source_unverified_accepted_pull_count > self.all_accepted_pull_count:
            raise ValueError("S5 monthly unverified source accounting changed")
        if self.canonical_github_time_count + self.canonical_git_fallback_time_count != (
            self.canonical_integration_count
        ):
            raise ValueError("S5 monthly canonical time accounting changed")
        if self.human_contributor_lower_bound != (
            self.known_human_or_unresolved_actor_count
        ):
            raise ValueError("S5 monthly contributor lower bound changed")
        if self.human_contributor_upper_bound != (
            self.known_human_or_unresolved_actor_count + self.unknown_actor_event_count
        ):
            raise ValueError("S5 monthly contributor upper bound changed")
        if self.signed_annotated_stable_release_tag_count > self.stable_release_tag_count:
            raise ValueError("S5 monthly release signature accounting changed")
        return self


class S5StableReleaseTagRecord(BaseModel):
    ref_name: str = Field(pattern=r"^refs/tags/")
    object_type: Literal["tag", "commit"]
    object_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    peeled_commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    event_at: datetime
    event_time_source: Literal["ANNOTATED_TAGGER_AT", "LIGHTWEIGHT_COMMITTER_AT"]
    signature_state: Literal[
        "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED",
        "ANNOTATED_UNSIGNED",
        "LIGHTWEIGHT_UNVERIFIED",
    ]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("event_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_record(self) -> S5StableReleaseTagRecord:
        annotated = self.object_type == "tag"
        if annotated != (self.event_time_source == "ANNOTATED_TAGGER_AT"):
            raise ValueError("S5 stable release time source changed")
        if annotated != (
            self.signature_state
            in {
                "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED",
                "ANNOTATED_UNSIGNED",
            }
        ):
            raise ValueError("S5 stable release signature state changed")
        if not annotated and self.object_sha != self.peeled_commit_sha:
            raise ValueError("S5 lightweight release identity changed")
        return self


class S5MeasurementGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL"]
    evidence: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5AcceptedDevelopmentMeasurementExecutionContractV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-execution-contract-v1"
    ] = "aurex-s5-accepted-development-measurement-execution-contract-v1"
    contract_id: Literal[
        "s5-accepted-development-measurement-execution-contract-v1"
    ] = "s5-accepted-development-measurement-execution-contract-v1"
    frozen_at: datetime
    status: Literal["FROZEN_EXECUTION_CONTRACT_ZERO_MEASUREMENTS"] = (
        "FROZEN_EXECUTION_CONTRACT_ZERO_MEASUREMENTS"
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
    git_environment: tuple[str, ...] = (
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_CONFIG_GLOBAL=OS_DEVNULL",
        "GIT_NO_LAZY_FETCH=1",
        "GIT_OPTIONAL_LOCKS=0",
        "LANG=C",
        "LC_ALL=C",
        "TZ=UTC",
    )
    first_parent_diff_command: tuple[str, ...] = (
        "git",
        "-C",
        "{history_dataset_path}",
        "--no-pager",
        "log",
        "--first-parent",
        "--reverse",
        "--format=%x1e%H%x00",
        "--name-only",
        "-z",
        "--no-renames",
        "--diff-merges=first-parent",
        "{source_cutoff_commit}",
    )
    reachable_commit_command: tuple[str, ...] = (
        "git",
        "-C",
        "{history_dataset_path}",
        "rev-list",
        "--topo-order",
        "{source_cutoff_commit}",
    )
    tag_inventory_command: tuple[str, ...] = (
        "git",
        "-C",
        "{history_dataset_path}",
        "for-each-ref",
        (
            "--format=%(refname)%00%(objecttype)%00%(objectname)%00"
            "%(*objectname)%00%(taggerdate:iso-strict)%00"
            "%(creatordate:iso-strict)%00%(contents:signature)%00%1e"
        ),
        "refs/tags",
    )
    expected_git_process_count: Literal[3] = 3
    maximum_git_process_count: Literal[4] = 4
    maximum_process_seconds: Literal[600] = 600
    maximum_total_seconds: Literal[1_800] = 1_800
    maximum_single_stdout_bytes: Literal[536_870_912] = 536_870_912
    expected_input_row_count: Literal[57_592] = 57_592
    expected_output_row_count: Literal[212] = 212
    result_path: Literal[
        "data/evidence/s5_accepted_development_measurement_result_v1.json"
    ] = "data/evidence/s5_accepted_development_measurement_result_v1.json"
    output_path: Literal[
        "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    ] = "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    partial_file_suffix: Literal[".part"] = ".part"
    authorizes_single_local_measurement_run: Literal[True] = True
    shell_execution_permitted: Literal[False] = False
    network_access_permitted: Literal[False] = False
    repository_fetch_permitted: Literal[False] = False
    repository_mutation_permitted: Literal[False] = False
    market_values_permitted: Literal[False] = False
    returns_permitted: Literal[False] = False
    strategy_parameters_permitted: Literal[False] = False
    candidates_permitted: Literal[False] = False
    signals_permitted: Literal[False] = False
    paper_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
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
    def validate_contract(self) -> S5AcceptedDevelopmentMeasurementExecutionContractV1:
        for bindings in (self.source_bindings, self.implementation_bindings):
            paths = tuple(item.path for item in bindings)
            if paths != tuple(sorted(set(paths))):
                raise ValueError("S5 measurement execution bindings changed")
        if self.source_binding_manifest_evidence_hash != universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        ):
            raise ValueError("S5 measurement execution source manifest changed")
        expected_runner_hash = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.implementation_bindings)
        )
        if (
            self.implementation_binding_manifest_evidence_hash != expected_runner_hash
            or self.runner_contract_hash != expected_runner_hash
        ):
            raise ValueError("S5 measurement execution runner contract changed")
        if self.expected_git_process_count > self.maximum_git_process_count:
            raise ValueError("S5 measurement execution process budget changed")
        if self.protocol_audit_evidence_hash == "0" * 64:
            raise ValueError("S5 measurement execution protocol audit is absent")
        if any(
            (
                self.shell_execution_permitted,
                self.network_access_permitted,
                self.repository_fetch_permitted,
                self.repository_mutation_permitted,
                self.market_values_permitted,
                self.returns_permitted,
                self.strategy_parameters_permitted,
                self.candidates_permitted,
                self.signals_permitted,
                self.paper_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("S5 measurement execution grants forbidden authority")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("S5 measurement execution contract hash changed")
        return self


class S5AcceptedDevelopmentMeasurementExecutionContractAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-execution-contract-audit-v1"
    ] = "aurex-s5-accepted-development-measurement-execution-contract-audit-v1"
    audit_id: Literal[
        "s5-accepted-development-measurement-execution-contract-audit-v1"
    ] = "s5-accepted-development-measurement-execution-contract-audit-v1"
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
    git_processes_executed: Literal[0] = 0
    source_rows_parsed: Literal[0] = 0
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_EXECUTION_CONTRACT_AUDIT"
    ] = "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_EXECUTION_CONTRACT_AUDIT"
    next_authorization: Literal[
        "RUN_S5_ACCEPTED_DEVELOPMENT_MEASUREMENTS_ONCE"
    ] = S5_MEASUREMENT_RUN
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
    ) -> S5AcceptedDevelopmentMeasurementExecutionContractAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 measurement execution auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 measurement execution auditor contract changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 measurement execution audit hash changed")
        return self


class S5AcceptedDevelopmentMeasurementResultV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-result-v1"
    ] = "aurex-s5-accepted-development-measurement-result-v1"
    result_id: Literal[
        "s5-accepted-development-measurement-result-v1"
    ] = "s5-accepted-development-measurement-result-v1"
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float = Field(ge=0, le=86_400)
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    input_file_sha256s: tuple[str, ...] = Field(min_length=5, max_length=5)
    input_row_manifest_evidence_hashes: tuple[str, ...] = Field(min_length=5, max_length=5)
    input_row_count: Literal[57_592] = 57_592
    git_process_count: int = Field(ge=0, le=4)
    first_parent_diff_stdout_sha256: str | None
    reachable_commit_stdout_sha256: str | None
    tag_inventory_stdout_sha256: str | None
    reachable_commit_count: int | None = Field(default=None, ge=0, le=50_395)
    stable_release_tag_inventory_count: int | None = Field(default=None, ge=0)
    primary_events_in_complete_months: int | None = Field(default=None, ge=0, le=16_271)
    primary_events_excluded_after_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=16_271,
    )
    all_accepted_events_in_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=16_279,
    )
    all_accepted_events_excluded_after_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=16_279,
    )
    canonical_events_in_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=16_242,
    )
    canonical_events_excluded_after_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=16_242,
    )
    unresolved_merges_in_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=479,
    )
    unresolved_merges_excluded_after_complete_months: int | None = Field(
        default=None,
        ge=0,
        le=479,
    )
    output_path: str | None
    output_file_sha256: str | None
    output_byte_count: int | None = Field(default=None, ge=0, le=16_777_216)
    output_row_count: int = Field(ge=0, le=212)
    output_row_manifest_evidence_hash: str | None
    gate_results: tuple[S5MeasurementGateResult, ...] = Field(min_length=19, max_length=19)
    passed_gate_count: int = Field(ge=0, le=19)
    failed_gate_count: int = Field(ge=0, le=19)
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_CONSTRUCTION",
        "STOP_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_CONSTRUCTION",
    ]
    next_authorization: Literal[
        "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_RESULT_AUDIT_ONLY",
        "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_FAILURE_ADJUDICATION_ONLY",
    ]
    authorizes_result_audit: bool
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
    limitations: tuple[str, ...] = Field(min_length=10)
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
        "first_parent_diff_stdout_sha256",
        "reachable_commit_stdout_sha256",
        "tag_inventory_stdout_sha256",
        "output_file_sha256",
        "output_row_manifest_evidence_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @field_validator("input_file_sha256s", "input_row_manifest_evidence_hashes")
    @classmethod
    def normalize_hash_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_result(self) -> S5AcceptedDevelopmentMeasurementResultV1:
        if self.completed_at < self.started_at:
            raise ValueError("S5 measurement result completion precedes start")
        if tuple(item.gate_id for item in self.gate_results) != S5_MEASUREMENT_GATES:
            raise ValueError("S5 measurement result gates changed")
        passed = sum(item.status == "PASS" for item in self.gate_results)
        if (self.passed_gate_count, self.failed_gate_count) != (
            passed,
            len(self.gate_results) - passed,
        ):
            raise ValueError("S5 measurement result gate accounting changed")
        successful = self.failed_gate_count == 0
        output_fields = (
            self.output_path,
            self.output_file_sha256,
            self.output_byte_count,
            self.output_row_manifest_evidence_hash,
        )
        process_hashes = (
            self.first_parent_diff_stdout_sha256,
            self.reachable_commit_stdout_sha256,
            self.tag_inventory_stdout_sha256,
        )
        count_fields = (
            self.reachable_commit_count,
            self.stable_release_tag_inventory_count,
            self.primary_events_in_complete_months,
            self.primary_events_excluded_after_complete_months,
            self.all_accepted_events_in_complete_months,
            self.all_accepted_events_excluded_after_complete_months,
            self.canonical_events_in_complete_months,
            self.canonical_events_excluded_after_complete_months,
            self.unresolved_merges_in_complete_months,
            self.unresolved_merges_excluded_after_complete_months,
        )
        exact_pass = (
            self.git_process_count == 3
            and self.elapsed_seconds <= 1_800
            and all(value is not None for value in process_hashes)
            and self.reachable_commit_count == 50_395
            and all(value is not None for value in count_fields)
            and all(value is not None for value in output_fields)
            and self.output_row_count == 212
            and self.failure_type is None
            and self.failure_message is None
        )
        if successful != exact_pass:
            raise ValueError("S5 measurement result pass accounting changed")
        if successful != (
            self.decision == S5_MEASUREMENT_PASS
            and self.next_authorization == S5_MEASUREMENT_RESULT_NEXT
            and self.authorizes_result_audit
        ):
            raise ValueError("S5 measurement result pass decision changed")
        if not successful and (
            self.decision != S5_MEASUREMENT_STOP
            or self.next_authorization != S5_MEASUREMENT_FAILURE_NEXT
            or self.authorizes_result_audit
            or not self.failure_type
            or not self.failure_message
        ):
            raise ValueError("S5 measurement result stop evidence changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("S5 measurement result hash changed")
        return self
