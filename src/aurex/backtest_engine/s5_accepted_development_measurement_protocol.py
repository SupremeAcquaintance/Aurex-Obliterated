from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s5_bitcoin_core_history_payload import S5HistoryBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S5_MEASUREMENT_DECISION = "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
S5_MEASUREMENT_AUDIT_DECISION = (
    "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_AUDIT"
)
S5_MEASUREMENT_NEXT = (
    "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
)

S5_MEASUREMENT_GATES = (
    "ALL_TWENTY_FIVE_SOURCE_BINDINGS_MATCH",
    "CORRECTED_NORMALIZATION_RESULT_AND_INDEPENDENT_AUDIT_PASS",
    "ALL_FIVE_INPUT_FILE_AND_ROW_MANIFEST_HASHES_MATCH",
    "PRIMARY_SOURCE_VERIFIED_ACCEPTED_UNIVERSE_IS_EXACTLY_16271",
    "ALL_ACCEPTED_SENSITIVITY_UNIVERSE_IS_EXACTLY_16279_WITH_EIGHT_UNVERIFIED",
    "CANONICAL_FIRST_PARENT_UNIVERSE_IS_EXACTLY_16242",
    "EVENT_UNIVERSES_REMAIN_SEPARATE_AND_MANY_TO_ONE_LINKS_REMAIN_VISIBLE",
    "ONLY_COMPLETE_UTC_MONTHS_THROUGH_2026_08_ARE_EMITTED",
    "SEVEN_DAY_POST_MONTH_AVAILABILITY_LAG_IS_APPLIED",
    "AUTHOR_AND_UPDATED_TIMESTAMPS_ARE_FORBIDDEN_AS_EVENT_TIME",
    "ACTOR_IDENTITY_USES_ACCOUNT_ID_WITH_EXPLICIT_UNKNOWN_BOUNDS",
    "OUTPUT_CONTAINS_COUNTS_AND_HASHED_MANIFESTS_NOT_ACTOR_IDENTIFIERS",
    "COMPONENT_KEYS_USE_FIRST_PARENT_DIFFS_AND_FROZEN_PATH_RULES",
    "STABLE_RELEASE_TAG_SHAPE_REACHABILITY_TYPE_AND_SIGNATURE_STATE_ARE_PRESERVED",
    "UNVERIFIED_RELEASE_AND_REVIEW_CONTINUITY_CANNOT_BECOME_CANDIDATE_FEATURES",
    "INTEGER_COUNTS_AND_SECONDS_ONLY_WITH_NO_FLOAT_ARITHMETIC",
    "JSONL_ROWS_ARE_ORDERED_UNIQUE_AND_BYTE_REPRODUCIBLE",
    "ANY_INPUT_SCHEMA_HASH_COUNT_TIME_OR_GIT_MISMATCH_STOPS_THE_RUN",
    "ZERO_NETWORK_MARKET_VALUES_RETURNS_CANDIDATES_SIGNALS_OR_ORDERS",
)

S5_MEASUREMENT_OUTPUT_FIELDS = (
    "sequence",
    "month_start",
    "month_end_exclusive",
    "measurement_available_at",
    "primary_source_verified_accepted_pull_count",
    "primary_distinct_local_source_commit_count",
    "primary_many_to_one_excess_count",
    "all_accepted_pull_count",
    "source_unverified_accepted_pull_count",
    "canonical_integration_count",
    "canonical_github_time_count",
    "canonical_git_fallback_time_count",
    "known_human_or_unresolved_actor_count",
    "unknown_actor_event_count",
    "human_contributor_lower_bound",
    "human_contributor_upper_bound",
    "known_bot_actor_count",
    "canonical_component_key_count",
    "unresolved_git_merge_count",
    "stable_release_tag_count",
    "signed_annotated_stable_release_tag_count",
    "primary_event_manifest_evidence_hash",
    "canonical_event_manifest_evidence_hash",
    "component_key_manifest_evidence_hash",
    "release_tag_manifest_evidence_hash",
    "source_normalization_result_evidence_hash",
)

S5_MEASUREMENT_FORBIDDEN_OUTPUT_FIELDS = (
    "btc_open",
    "btc_high",
    "btc_low",
    "btc_close",
    "btc_volume",
    "btc_return",
    "forward_return",
    "benchmark_return",
    "threshold",
    "signal",
    "position",
    "pnl",
    "candidate_id",
    "actor_id",
    "actor_login",
)

S5_MEASUREMENT_INPUT_FILE_SHA256S = (
    "1075bcd84b27a8408c26d9beab481b7b6df762a922267e57bae05a1725ee5888",
    "e13d5aba80bcb688abf004fc8813dfd81a3083c1bc295859267b9baac001e564",
    "6e11c4183adfde890d3188a6ae20bdce1700faf3651e76f2b0975051a0968bd2",
    "5975b299d2b6e291ac1961038e067150372846d4d54e11a84ca5405781b3627c",
    "992c21f70d99e1243296d851b836119ff7825cd54574ac98ef32f65bf0a66de8",
)

S5_MEASUREMENT_INPUT_ROW_MANIFEST_HASHES = (
    "8322a392190b090d656e5bca6a07b07712aff650cf0630336893eebda2dc27bb",
    "f2258f31f962eca23a0954f5b6fd3f91605d884af2697a8818ad52ac6ef737f7",
    "c7ec6e975596d509d633a8b1f1a6ac4baac731a3d2b73d2fbdcf5f7b125b5b93",
    "cc4733623e3d000495af0e9c2c767e76fca353eba9d367399a023b64beb98d8b",
    "0aefeb2063b45c2fbd852ca76c4460e0ac88562fb454b2de3ada7f196fd082ab",
)

S5_MEASUREMENT_SOURCE_PATHS = tuple(
    sorted(
        (
            "data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl",
            "data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl",
            "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl",
            "data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl",
            "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl",
            "data/evidence/s5_bitcoin_core_development_charter_audit_v1.json",
            "data/evidence/s5_bitcoin_core_development_charter_v1.json",
            (
                "data/evidence/"
                "s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
            ),
            "data/evidence/s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json",
            "data/evidence/s5_bitcoin_core_github_bulk_final_result_audit_v4.json",
            "data/evidence/s5_bitcoin_core_github_bulk_result_v4.json",
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_"
                "execution_contract_audit_v2.json"
            ),
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_"
                "execution_contract_v2.json"
            ),
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_protocol_audit_v2.json"
            ),
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_protocol_v2.json"
            ),
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_result_audit_v2.json"
            ),
            (
                "data/evidence/"
                "s5_bitcoin_core_github_corrected_normalization_result_v2.json"
            ),
            "data/evidence/s5_bitcoin_core_history_census_protocol_audit_v1.json",
            "data/evidence/s5_bitcoin_core_history_census_protocol_v1.json",
            "data/evidence/s5_bitcoin_core_history_census_result_audit_v1.json",
            "data/evidence/s5_bitcoin_core_history_census_result_v1.json",
            "data/evidence/s5_bitcoin_core_history_payload_protocol_audit_v1.json",
            "data/evidence/s5_bitcoin_core_history_payload_protocol_v1.json",
            "data/evidence/s5_bitcoin_core_history_payload_result_audit_v2.json",
            "data/evidence/s5_bitcoin_core_history_payload_result_v2.json",
        )
    )
)

S5_MEASUREMENT_DEFINITION_ROWS = (
    (
        "primary_source_verified_accepted_pull_count",
        "COUNT_PRIMARY_PULL_NUMBER_WITH_GITHUB_MERGED_AT_IN_MONTH",
        "PRIMARY_ACCEPTED",
        True,
    ),
    (
        "primary_distinct_local_source_commit_count",
        "COUNT_DISTINCT_PRIMARY_LOCAL_SOURCE_COMMIT_SHA_IN_MONTH",
        "PRIMARY_ACCEPTED",
        True,
    ),
    (
        "primary_many_to_one_excess_count",
        "PRIMARY_ACCEPTED_COUNT_MINUS_DISTINCT_LOCAL_SOURCE_COMMIT_COUNT",
        "PRIMARY_ACCEPTED",
        False,
    ),
    (
        "all_accepted_pull_count",
        "COUNT_ALL_ACCEPTED_PULL_NUMBER_WITH_GITHUB_MERGED_AT_IN_MONTH",
        "ALL_ACCEPTED_SENSITIVITY",
        False,
    ),
    (
        "source_unverified_accepted_pull_count",
        "COUNT_ALL_ACCEPTED_EVENTS_WITH_LOCAL_SOURCE_LINK_VERIFIED_FALSE_IN_MONTH",
        "ALL_ACCEPTED_SENSITIVITY",
        False,
    ),
    (
        "canonical_integration_count",
        "COUNT_DISTINCT_CANONICAL_MERGE_COMMIT_SHA_WITH_EVENT_AT_IN_MONTH",
        "CANONICAL_INTEGRATION",
        True,
    ),
    (
        "canonical_github_time_count",
        "COUNT_CANONICAL_EVENTS_WITH_EVENT_TIME_SOURCE_GITHUB_MERGED_AT_IN_MONTH",
        "CANONICAL_INTEGRATION",
        False,
    ),
    (
        "canonical_git_fallback_time_count",
        "COUNT_CANONICAL_EVENTS_WITH_EVENT_TIME_SOURCE_GIT_COMMITTER_AT_IN_MONTH",
        "CANONICAL_INTEGRATION",
        False,
    ),
    (
        "known_human_or_unresolved_actor_count",
        "COUNT_DISTINCT_PRIMARY_ACTOR_ID_CLASS_HUMAN_OR_UNRESOLVED_IN_MONTH",
        "PRIMARY_ACCEPTED",
        True,
    ),
    (
        "unknown_actor_event_count",
        "COUNT_PRIMARY_EVENTS_WITH_ACTOR_IDENTITY_STATUS_UNKNOWN_IN_MONTH",
        "PRIMARY_ACCEPTED",
        False,
    ),
    (
        "human_contributor_lower_bound",
        "KNOWN_HUMAN_OR_UNRESOLVED_DISTINCT_ACTOR_COUNT",
        "PRIMARY_ACCEPTED",
        True,
    ),
    (
        "human_contributor_upper_bound",
        "KNOWN_HUMAN_OR_UNRESOLVED_COUNT_PLUS_UNKNOWN_ACTOR_EVENT_COUNT",
        "PRIMARY_ACCEPTED",
        False,
    ),
    (
        "known_bot_actor_count",
        "COUNT_DISTINCT_PRIMARY_ACTOR_ID_CLASS_BOT_IN_MONTH",
        "PRIMARY_ACCEPTED",
        False,
    ),
    (
        "canonical_component_key_count",
        (
            "COUNT_DISTINCT_FROZEN_COMPONENT_KEYS_TOUCHED_BY_"
            "CANONICAL_INTEGRATIONS_IN_MONTH"
        ),
        "CANONICAL_INTEGRATION",
        True,
    ),
    (
        "unresolved_git_merge_count",
        "COUNT_UNRESOLVED_GIT_MERGES_BY_GIT_COMMITTER_AT_MONTH",
        "UNRESOLVED_GIT_MERGE",
        False,
    ),
    (
        "stable_release_tag_count",
        "COUNT_REACHABLE_EXACT_STABLE_NAME_TAG_EVENTS_IN_MONTH",
        "OFFICIAL_STABLE_TAG",
        False,
    ),
    (
        "signed_annotated_stable_release_tag_count",
        (
            "COUNT_REACHABLE_STABLE_ANNOTATED_TAG_EVENTS_WITH_"
            "SIGNATURE_PRESENT_IN_MONTH"
        ),
        "OFFICIAL_STABLE_TAG",
        False,
    ),
)


class S5MeasurementEventUniverse(BaseModel):
    universe_id: Literal[
        "SOURCE_VERIFIED_ACCEPTED_GITHUB_PULLS",
        "ALL_ACCEPTED_GITHUB_PULLS_SENSITIVITY",
        "CANONICAL_FIRST_PARENT_INTEGRATIONS",
    ]
    role: Literal["PRIMARY", "SENSITIVITY", "CORROBORATION"]
    row_count: Literal[16_271, 16_279, 16_242]
    event_key: Literal["PULL_NUMBER", "MERGE_COMMIT_SHA"]
    event_time: Literal["GITHUB_MERGED_AT", "SOURCE_LABELED_CANONICAL_EVENT_AT"]
    source_link_required: bool
    canonical_owner_required: bool
    many_to_one_policy: Literal[
        "COUNT_PULL_EVENTS_AND_REPORT_DISTINCT_SOURCE_COMMITS_SEPARATELY",
        "COUNT_EACH_CANONICAL_FIRST_PARENT_MERGE_ONCE",
    ]
    eligible_for_primary_measurement: bool

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5MeasurementDefinition(BaseModel):
    measurement_id: Literal[
        "primary_source_verified_accepted_pull_count",
        "primary_distinct_local_source_commit_count",
        "primary_many_to_one_excess_count",
        "all_accepted_pull_count",
        "source_unverified_accepted_pull_count",
        "canonical_integration_count",
        "canonical_github_time_count",
        "canonical_git_fallback_time_count",
        "known_human_or_unresolved_actor_count",
        "unknown_actor_event_count",
        "human_contributor_lower_bound",
        "human_contributor_upper_bound",
        "known_bot_actor_count",
        "canonical_component_key_count",
        "unresolved_git_merge_count",
        "stable_release_tag_count",
        "signed_annotated_stable_release_tag_count",
    ]
    formula: str = Field(min_length=12)
    output_type: Literal["NONNEGATIVE_INTEGER"] = "NONNEGATIVE_INTEGER"
    source_universe: Literal[
        "PRIMARY_ACCEPTED",
        "ALL_ACCEPTED_SENSITIVITY",
        "CANONICAL_INTEGRATION",
        "UNRESOLVED_GIT_MERGE",
        "OFFICIAL_STABLE_TAG",
    ]
    candidate_feature_eligible: bool

    model_config = ConfigDict(extra="forbid", frozen=True)


class S5AcceptedDevelopmentMeasurementProtocolV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-protocol-v1"
    ] = "aurex-s5-accepted-development-measurement-protocol-v1"
    protocol_id: Literal[
        "s5-accepted-development-measurement-protocol-v1"
    ] = "s5-accepted-development-measurement-protocol-v1"
    frozen_at: datetime
    status: Literal[
        "FROZEN_BEFORE_MEASUREMENT_EXECUTION_OR_BTC_OUTCOME_ACCESS"
    ] = "FROZEN_BEFORE_MEASUREMENT_EXECUTION_OR_BTC_OUTCOME_ACCESS"
    builder_contract_hash: str
    source_bindings: tuple[S5HistoryBinding, ...] = Field(min_length=25, max_length=25)
    source_binding_manifest_evidence_hash: str
    charter_evidence_hash: str
    charter_audit_evidence_hash: str
    corrected_normalization_protocol_evidence_hash: str
    corrected_normalization_protocol_audit_evidence_hash: str
    corrected_normalization_execution_contract_evidence_hash: str
    corrected_normalization_execution_contract_audit_evidence_hash: str
    corrected_normalization_result_evidence_hash: str
    corrected_normalization_result_audit_evidence_hash: str
    history_dataset_path: Literal[
        "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    ] = "data/evidence/s5_bitcoin_core_history_payload_v1.git"
    history_dataset_directory_sha256: str
    source_cutoff_commit: Literal[
        "dc0395c5858a1d55239b82a834e5075cf2069219"
    ] = "dc0395c5858a1d55239b82a834e5075cf2069219"
    github_cohort_created_at_cutoff: datetime
    normalized_pull_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_github_pulls_normalized_v2.jsonl"
    canonical_mapping_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_canonical_merge_mapping_v2.jsonl"
    target_resolution_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_target_resolution_v2.jsonl"
    accepted_coverage_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_accepted_source_coverage_v2.jsonl"
    unresolved_merge_path: Literal[
        "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"
    ] = "data/evidence/datasets/s5_bitcoin_core_unresolved_git_merges_v2.jsonl"
    input_paths: tuple[str, ...] = Field(min_length=5, max_length=5)
    input_file_sha256s: tuple[str, ...] = Field(min_length=5, max_length=5)
    input_row_counts: tuple[Literal[24_398, 16_242, 194, 16_279, 479], ...] = Field(
        min_length=5,
        max_length=5,
    )
    input_row_manifest_evidence_hashes: tuple[str, ...] = Field(
        min_length=5,
        max_length=5,
    )
    event_universes: tuple[S5MeasurementEventUniverse, ...] = Field(
        min_length=3,
        max_length=3,
    )
    many_to_one_pull_groups: tuple[tuple[int, ...], ...] = ((25_882, 25_891), (26_081, 26_084))
    measurement_frequency: Literal["MONTHLY"] = "MONTHLY"
    month_boundary_policy: Literal["UTC_CALENDAR_MONTH_START_INCLUSIVE_END_EXCLUSIVE"] = (
        "UTC_CALENDAR_MONTH_START_INCLUSIVE_END_EXCLUSIVE"
    )
    measurement_period_start_month: date = date(2009, 1, 1)
    measurement_period_end_exclusive: date = date(2026, 9, 1)
    expected_measurement_month_count: Literal[212] = 212
    incomplete_month_policy: Literal["EXCLUDE"] = "EXCLUDE"
    post_month_availability_lag_days: Literal[7] = 7
    measurement_availability_policy: Literal[
        "MONTH_END_EXCLUSIVE_PLUS_SEVEN_CALENDAR_DAYS_AT_00_00_UTC"
    ] = "MONTH_END_EXCLUSIVE_PLUS_SEVEN_CALENDAR_DAYS_AT_00_00_UTC"
    primary_event_time_policy: Literal["GITHUB_MERGED_AT_ONLY"] = "GITHUB_MERGED_AT_ONLY"
    canonical_event_time_policy: Literal[
        "GITHUB_MERGED_AT_ELSE_GIT_COMMITTER_AT_WITH_SOURCE_LABEL"
    ] = "GITHUB_MERGED_AT_ELSE_GIT_COMMITTER_AT_WITH_SOURCE_LABEL"
    forbidden_event_time_fields: tuple[str, ...] = (
        "created_at",
        "closed_at",
        "updated_at",
        "git_author_at",
    )
    actor_identity_key_policy: Literal[
        "GITHUB_NUMERIC_ACTOR_ID_ONLY_NEVER_LOGIN_OR_CURRENT_MAILMAP"
    ] = "GITHUB_NUMERIC_ACTOR_ID_ONLY_NEVER_LOGIN_OR_CURRENT_MAILMAP"
    actor_output_privacy_policy: Literal[
        "PERSIST_COUNTS_AND_SORTED_ID_MANIFEST_HASHES_ONLY"
    ] = "PERSIST_COUNTS_AND_SORTED_ID_MANIFEST_HASHES_ONLY"
    unknown_actor_lower_bound_policy: Literal[
        "KNOWN_HUMAN_OR_UNRESOLVED_DISTINCT_ACTOR_IDS_ONLY"
    ] = "KNOWN_HUMAN_OR_UNRESOLVED_DISTINCT_ACTOR_IDS_ONLY"
    unknown_actor_upper_bound_policy: Literal[
        "KNOWN_HUMAN_OR_UNRESOLVED_DISTINCT_ACTOR_IDS_PLUS_UNKNOWN_EVENT_COUNT"
    ] = "KNOWN_HUMAN_OR_UNRESOLVED_DISTINCT_ACTOR_IDS_PLUS_UNKNOWN_EVENT_COUNT"
    bot_policy: Literal["REPORT_DISTINCT_KNOWN_BOT_ACTOR_IDS_SEPARATELY"] = (
        "REPORT_DISTINCT_KNOWN_BOT_ACTOR_IDS_SEPARATELY"
    )
    component_diff_policy: Literal[
        "DIFF_EACH_CANONICAL_MERGE_FIRST_PARENT_TO_MERGE_WITH_RENAMES_DISABLED"
    ] = "DIFF_EACH_CANONICAL_MERGE_FIRST_PARENT_TO_MERGE_WITH_RENAMES_DISABLED"
    component_path_policy: Literal[
        "ROOT_FOR_NO_SLASH_SRC_SECOND_DIRECTORY_ELSE_SRC_ROOT_OTHERWISE_FIRST_SEGMENT"
    ] = "ROOT_FOR_NO_SLASH_SRC_SECOND_DIRECTORY_ELSE_SRC_ROOT_OTHERWISE_FIRST_SEGMENT"
    component_key_rules: tuple[str, ...] = (
        "NO_SLASH_PATH_TO_ROOT",
        "SRC_WITH_AT_LEAST_THREE_SEGMENTS_TO_SRC_SLASH_SECOND_SEGMENT",
        "OTHER_SRC_PATH_TO_SRC_ROOT",
        "NON_SRC_PATH_WITH_SLASH_TO_FIRST_SEGMENT",
    )
    component_path_separator: Literal["/"] = "/"
    component_invalid_path_policy: Literal["REJECT_ENTIRE_RUN"] = "REJECT_ENTIRE_RUN"
    stable_release_tag_regex: Literal[
        r"^refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    ] = r"^refs/tags/v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?$"
    release_reachability_policy: Literal[
        "PEELED_COMMIT_MUST_BE_ANCESTOR_OF_SOURCE_CUTOFF_COMMIT"
    ] = "PEELED_COMMIT_MUST_BE_ANCESTOR_OF_SOURCE_CUTOFF_COMMIT"
    release_event_time_policy: Literal[
        "ANNOTATED_TAGGER_AT_ELSE_LIGHTWEIGHT_PEELED_COMMIT_COMMITTER_AT_WITH_SOURCE_LABEL"
    ] = (
        "ANNOTATED_TAGGER_AT_ELSE_LIGHTWEIGHT_PEELED_COMMIT_COMMITTER_AT_WITH_SOURCE_LABEL"
    )
    release_signature_states: tuple[
        Literal[
            "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED",
            "ANNOTATED_UNSIGNED",
            "LIGHTWEIGHT_UNVERIFIED",
        ],
        ...,
    ] = (
        "SIGNED_ANNOTATED_SIGNATURE_PRESENT_NOT_VERIFIED",
        "ANNOTATED_UNSIGNED",
        "LIGHTWEIGHT_UNVERIFIED",
    )
    release_continuity_candidate_feature_eligible: Literal[False] = False
    review_continuity_candidate_feature_eligible: Literal[False] = False
    review_event_records_acquired: Literal[0] = 0
    measurement_definitions: tuple[S5MeasurementDefinition, ...] = Field(
        min_length=17,
        max_length=17,
    )
    measurement_definition_count: Literal[17] = 17
    output_path: Literal[
        "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    ] = "data/evidence/s5_accepted_development_monthly_measurements_v1.jsonl"
    output_fields: tuple[str, ...] = S5_MEASUREMENT_OUTPUT_FIELDS
    forbidden_output_fields: tuple[str, ...] = S5_MEASUREMENT_FORBIDDEN_OUTPUT_FIELDS
    serialization_policy: Literal[
        "UTF8_JSONL_SORTED_KEYS_COMPACT_LF_TERMINATED_SHA256"
    ] = "UTF8_JSONL_SORTED_KEYS_COMPACT_LF_TERMINATED_SHA256"
    arithmetic_policy: Literal["NONNEGATIVE_INTEGER_COUNTS_AND_SECONDS_NO_FLOAT"] = (
        "NONNEGATIVE_INTEGER_COUNTS_AND_SECONDS_NO_FLOAT"
    )
    maximum_local_git_processes_for_future_runner: Literal[4] = 4
    maximum_future_runner_seconds: Literal[1_800] = 1_800
    maximum_future_output_bytes: Literal[16_777_216] = 16_777_216
    future_network_request_budget: Literal[0] = 0
    quality_gates: tuple[str, ...] = Field(min_length=19, max_length=19)
    source_jsonl_rows_parsed_during_freeze: Literal[0] = 0
    git_processes_executed_during_freeze: Literal[0] = 0
    network_requests_executed_during_freeze: Literal[0] = 0
    market_values_read_during_freeze: Literal[0] = 0
    exact_parameters_defined: tuple[str, ...] = ()
    strategy_rules_defined: tuple[str, ...] = ()
    future_strategy_family_budget: Literal[1] = 1
    future_candidate_budget: Literal[1] = 1
    future_parameter_combination_budget: Literal[1] = 1
    future_parameter_search_policy: Literal[
        "NO_OUTCOME_DRIVEN_METRIC_THRESHOLD_WINDOW_OR_RULE_SEARCH"
    ] = "NO_OUTCOME_DRIVEN_METRIC_THRESHOLD_WINDOW_OR_RULE_SEARCH"
    authorizes_measurement_runner_implementation: Literal[True] = True
    authorizes_measurement_execution_now: Literal[False] = False
    authorizes_repository_mutation: Literal[False] = False
    authorizes_network_requests: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_strategy_parameter_definition: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_signal_generation: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    decision: Literal[
        "FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL"
    ] = S5_MEASUREMENT_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_MEASUREMENT_NEXT
    limitations: tuple[str, ...] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at", "github_cohort_created_at_cutoff")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "source_binding_manifest_evidence_hash",
        "charter_evidence_hash",
        "charter_audit_evidence_hash",
        "corrected_normalization_protocol_evidence_hash",
        "corrected_normalization_protocol_audit_evidence_hash",
        "corrected_normalization_execution_contract_evidence_hash",
        "corrected_normalization_execution_contract_audit_evidence_hash",
        "corrected_normalization_result_evidence_hash",
        "corrected_normalization_result_audit_evidence_hash",
        "history_dataset_directory_sha256",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("input_file_sha256s", "input_row_manifest_evidence_hashes")
    @classmethod
    def normalize_hash_sets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S5AcceptedDevelopmentMeasurementProtocolV1:
        source_paths = tuple(item.path for item in self.source_bindings)
        if source_paths != tuple(sorted(set(source_paths))):
            raise ValueError("S5 measurement source bindings changed")
        if source_paths != S5_MEASUREMENT_SOURCE_PATHS:
            raise ValueError("S5 measurement source path set changed")
        expected_binding_manifest = universe_evidence_hash(
            tuple(item.model_dump(mode="json") for item in self.source_bindings)
        )
        if self.source_binding_manifest_evidence_hash != expected_binding_manifest:
            raise ValueError("S5 measurement source binding manifest changed")
        expected_inputs = (
            self.normalized_pull_path,
            self.canonical_mapping_path,
            self.target_resolution_path,
            self.accepted_coverage_path,
            self.unresolved_merge_path,
        )
        if self.input_paths != expected_inputs:
            raise ValueError("S5 measurement input order changed")
        if self.input_row_counts != (24_398, 16_242, 194, 16_279, 479):
            raise ValueError("S5 measurement input row counts changed")
        if self.input_file_sha256s != S5_MEASUREMENT_INPUT_FILE_SHA256S:
            raise ValueError("S5 measurement input file identities changed")
        if (
            self.input_row_manifest_evidence_hashes
            != S5_MEASUREMENT_INPUT_ROW_MANIFEST_HASHES
        ):
            raise ValueError("S5 measurement input row manifests changed")
        expected_universes = (
            (
                "SOURCE_VERIFIED_ACCEPTED_GITHUB_PULLS",
                "PRIMARY",
                16_271,
                "PULL_NUMBER",
                "GITHUB_MERGED_AT",
                True,
                False,
                "COUNT_PULL_EVENTS_AND_REPORT_DISTINCT_SOURCE_COMMITS_SEPARATELY",
                True,
            ),
            (
                "ALL_ACCEPTED_GITHUB_PULLS_SENSITIVITY",
                "SENSITIVITY",
                16_279,
                "PULL_NUMBER",
                "GITHUB_MERGED_AT",
                False,
                False,
                "COUNT_PULL_EVENTS_AND_REPORT_DISTINCT_SOURCE_COMMITS_SEPARATELY",
                False,
            ),
            (
                "CANONICAL_FIRST_PARENT_INTEGRATIONS",
                "CORROBORATION",
                16_242,
                "MERGE_COMMIT_SHA",
                "SOURCE_LABELED_CANONICAL_EVENT_AT",
                True,
                True,
                "COUNT_EACH_CANONICAL_FIRST_PARENT_MERGE_ONCE",
                False,
            ),
        )
        actual_universes = tuple(
            (
                item.universe_id,
                item.role,
                item.row_count,
                item.event_key,
                item.event_time,
                item.source_link_required,
                item.canonical_owner_required,
                item.many_to_one_policy,
                item.eligible_for_primary_measurement,
            )
            for item in self.event_universes
        )
        if actual_universes != expected_universes:
            raise ValueError("S5 measurement event universes changed")
        if self.many_to_one_pull_groups != ((25_882, 25_891), (26_081, 26_084)):
            raise ValueError("S5 measurement many-to-one groups changed")
        if self.measurement_period_start_month != date(2009, 1, 1):
            raise ValueError("S5 measurement start month changed")
        if self.measurement_period_end_exclusive != date(2026, 9, 1):
            raise ValueError("S5 measurement terminal complete month changed")
        if self.github_cohort_created_at_cutoff != datetime(
            2026,
            9,
            2,
            21,
            43,
            33,
            504800,
            tzinfo=UTC,
        ):
            raise ValueError("S5 measurement GitHub cohort cutoff changed")
        month_count = (
            (self.measurement_period_end_exclusive.year - self.measurement_period_start_month.year)
            * 12
            + self.measurement_period_end_exclusive.month
            - self.measurement_period_start_month.month
        )
        if month_count != self.expected_measurement_month_count:
            raise ValueError("S5 measurement month accounting changed")
        actual_definitions = tuple(
            (
                item.measurement_id,
                item.formula,
                item.source_universe,
                item.candidate_feature_eligible,
            )
            for item in self.measurement_definitions
        )
        if actual_definitions != S5_MEASUREMENT_DEFINITION_ROWS:
            raise ValueError("S5 measurement definitions changed")
        if self.measurement_definition_count != len(self.measurement_definitions):
            raise ValueError("S5 measurement definition count changed")
        if self.output_fields != S5_MEASUREMENT_OUTPUT_FIELDS:
            raise ValueError("S5 measurement output fields changed")
        if self.forbidden_output_fields != S5_MEASUREMENT_FORBIDDEN_OUTPUT_FIELDS:
            raise ValueError("S5 measurement forbidden fields changed")
        if set(self.output_fields) & set(self.forbidden_output_fields):
            raise ValueError("S5 measurement output includes a forbidden field")
        if self.quality_gates != S5_MEASUREMENT_GATES:
            raise ValueError("S5 measurement gates changed")
        if self.component_key_rules != (
            "NO_SLASH_PATH_TO_ROOT",
            "SRC_WITH_AT_LEAST_THREE_SEGMENTS_TO_SRC_SLASH_SECOND_SEGMENT",
            "OTHER_SRC_PATH_TO_SRC_ROOT",
            "NON_SRC_PATH_WITH_SLASH_TO_FIRST_SEGMENT",
        ):
            raise ValueError("S5 measurement component key rules changed")
        if self.exact_parameters_defined or self.strategy_rules_defined:
            raise ValueError("S5 measurement protocol cannot define a strategy")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S5 measurement limitations changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("S5 measurement protocol hash changed")
        return self


class S5AcceptedDevelopmentMeasurementProtocolAuditV1(BaseModel):
    schema_version: Literal[
        "aurex-s5-accepted-development-measurement-protocol-audit-v1"
    ] = "aurex-s5-accepted-development-measurement-protocol-audit-v1"
    audit_id: Literal[
        "s5-accepted-development-measurement-protocol-audit-v1"
    ] = "s5-accepted-development-measurement-protocol-audit-v1"
    audited_at: datetime
    protocol_path: Literal[
        "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
    ] = "data/evidence/s5_accepted_development_measurement_protocol_v1.json"
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_implementation_bindings: tuple[S5HistoryBinding, ...] = Field(
        min_length=2,
        max_length=2,
    )
    auditor_contract_hash: str
    source_binding_manifest_evidence_hash: str
    corrected_normalization_result_evidence_hash: str
    corrected_normalization_result_audit_evidence_hash: str
    source_binding_count: Literal[25] = 25
    input_file_count: Literal[5] = 5
    input_row_count: Literal[57_592] = 57_592
    primary_event_count: Literal[16_271] = 16_271
    all_accepted_event_count: Literal[16_279] = 16_279
    source_unverified_event_count: Literal[8] = 8
    canonical_integration_count: Literal[16_242] = 16_242
    expected_measurement_month_count: Literal[212] = 212
    measurement_definition_count: Literal[17] = 17
    protocol_reconstructed_exactly: Literal[True] = True
    source_jsonl_rows_parsed: Literal[0] = 0
    git_processes_executed: Literal[0] = 0
    network_requests_executed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    candidates_created: Literal[0] = 0
    signals_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal[
        "PASS_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_AUDIT"
    ] = S5_MEASUREMENT_AUDIT_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
    ] = S5_MEASUREMENT_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "source_binding_manifest_evidence_hash",
        "corrected_normalization_result_evidence_hash",
        "corrected_normalization_result_audit_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S5AcceptedDevelopmentMeasurementProtocolAuditV1:
        paths = tuple(item.path for item in self.auditor_implementation_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S5 measurement protocol auditor bindings changed")
        expected_auditor_hash = universe_evidence_hash(
            tuple(
                item.model_dump(mode="json")
                for item in self.auditor_implementation_bindings
            )
        )
        if self.auditor_contract_hash != expected_auditor_hash:
            raise ValueError("S5 measurement protocol auditor contract changed")
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S5 measurement protocol audit hash changed")
        return self


def audit_s5_measurement_protocol(
    protocol: S5AcceptedDevelopmentMeasurementProtocolV1,
) -> bool:
    try:
        S5AcceptedDevelopmentMeasurementProtocolV1.model_validate(
            protocol.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True


def audit_s5_measurement_protocol_audit(
    audit: S5AcceptedDevelopmentMeasurementProtocolAuditV1,
) -> bool:
    try:
        S5AcceptedDevelopmentMeasurementProtocolAuditV1.model_validate(
            audit.model_dump(mode="json")
        )
    except ValueError:
        return False
    return True
