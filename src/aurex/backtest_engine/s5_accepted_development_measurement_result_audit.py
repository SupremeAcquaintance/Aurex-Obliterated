from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_MEASUREMENT_AUDIT_REJECT = (
    "REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT"
)
S5_MEASUREMENT_AUDIT_NEXT = (
    "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY"
)


class S5AcceptedDevelopmentMeasurementResultAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-result-audit-v1"
    ] = "aurex-s5-accepted-development-measurement-result-audit-v1"
    audit_id: Literal[
        "s5-accepted-development-measurement-result-audit-v1"
    ] = "s5-accepted-development-measurement-result-audit-v1"
    audited_at: datetime
    result_path: Literal[
        "data/evidence/s5_accepted_development_measurement_result_v1.json"
    ] = "data/evidence/s5_accepted_development_measurement_result_v1.json"
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    protocol_audit_evidence_hash: str
    execution_contract_evidence_hash: str
    execution_contract_audit_evidence_hash: str
    runner_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    auditor_contract_hash: str
    output_path: Literal[
        "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    ] = "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    output_file_sha256: str
    output_byte_count: Literal[271_959] = 271_959
    output_row_count: Literal[212] = 212
    output_row_manifest_evidence_hash: str
    output_manifest_verified: Literal[True] = True
    output_month_grid_verified: Literal[True] = True
    aggregate_accounting_verified: Literal[True] = True
    primary_events_in_complete_months: Literal[16_267] = 16_267
    primary_events_excluded_after_complete_months: Literal[4] = 4
    all_accepted_events_in_complete_months: Literal[16_273] = 16_273
    all_accepted_events_excluded_after_complete_months: Literal[6] = 6
    canonical_events_in_complete_months: Literal[16_238] = 16_238
    canonical_events_excluded_after_complete_months: Literal[4] = 4
    unresolved_merges_in_complete_months: Literal[479] = 479
    unresolved_merges_excluded_after_complete_months: Literal[0] = 0
    stable_release_tag_inventory_count: Literal[0] = 0
    emitted_stable_release_tag_count: Literal[0] = 0
    emitted_signed_annotated_stable_release_tag_count: Literal[0] = 0
    repository_config_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git/config"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git/config"
    repository_config_file_sha256: str
    repository_packed_refs_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git/packed-refs"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git/packed-refs"
    repository_packed_refs_file_sha256: str
    repository_tag_opt_no_tags_observed: Literal[True] = True
    packed_tag_ref_count: Literal[0] = 0
    packed_branch_ref_count: Literal[1] = 1
    packed_master_only_observed: Literal[True] = True
    result_integrity_verified: Literal[True] = True
    nominal_result_pass_upheld: Literal[False] = False
    release_measurement_fields_valid: Literal[False] = False
    nonrelease_measurement_families_independently_reconstructed: Literal[False] = False
    defect_classification: Literal[
        "SOURCE_SCOPE_OMISSION_RENDERED_ABSENT_RELEASE_TAGS_AS_ZERO_COUNTS"
    ] = "SOURCE_SCOPE_OMISSION_RENDERED_ABSENT_RELEASE_TAGS_AS_ZERO_COUNTS"
    measurement_output_rows_parsed: Literal[212] = 212
    source_input_rows_parsed: Literal[0] = 0
    git_processes_executed: Literal[0] = 0
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    parameters_defined: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT"
    ] = S5_MEASUREMENT_AUDIT_REJECT
    next_authorization: Literal[
        "FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY"
    ] = S5_MEASUREMENT_AUDIT_NEXT
    limitations: tuple[str, ...] = Field(min_length=8)
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "protocol_evidence_hash",
        "protocol_audit_evidence_hash",
        "execution_contract_evidence_hash",
        "execution_contract_audit_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "output_file_sha256",
        "output_row_manifest_evidence_hash",
        "repository_config_file_sha256",
        "repository_packed_refs_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5AcceptedDevelopmentMeasurementResultAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 measurement result auditor bindings changed")
        if self.auditor_contract_hash != universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        ):
            raise ValueError("S5 measurement result auditor contract changed")
        if (
            self.primary_events_in_complete_months
            + self.primary_events_excluded_after_complete_months
            != 16_271
            or self.all_accepted_events_in_complete_months
            + self.all_accepted_events_excluded_after_complete_months
            != 16_279
            or self.canonical_events_in_complete_months
            + self.canonical_events_excluded_after_complete_months
            != 16_242
            or self.unresolved_merges_in_complete_months
            + self.unresolved_merges_excluded_after_complete_months
            != 479
        ):
            raise ValueError("S5 measurement result audited accounting changed")
        if (
            self.stable_release_tag_inventory_count != 0
            or self.emitted_stable_release_tag_count != 0
            or self.emitted_signed_annotated_stable_release_tag_count != 0
            or self.packed_tag_ref_count != 0
            or not self.repository_tag_opt_no_tags_observed
            or self.nominal_result_pass_upheld
            or self.release_measurement_fields_valid
        ):
            raise ValueError("S5 measurement release-source rejection changed")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 measurement result audit limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("S5 measurement result audit hash changed")
        return self
