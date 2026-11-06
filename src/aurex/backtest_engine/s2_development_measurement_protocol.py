from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.s2_bigquery_feasibility import S2FeasibilityBinding
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

S2_MEASUREMENT_NEXT = "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
S2_MEASUREMENT_DECISION = "FREEZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL"
S2_MEASUREMENT_AUDIT_DECISION = "PASS_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_AUDIT"

S2_MEASUREMENT_GATES = (
    "ALL_FIFTEEN_PREDECESSOR_ARTIFACT_HASHES_MATCH",
    "INPUT_PAYLOAD_FILE_HASH_AND_280_ROW_MANIFEST_MATCH",
    "INPUT_WEEKS_ARE_STRICTLY_ORDERED_CONTIGUOUS_AND_CAUSAL",
    "ONLY_CURRENT_FOUR_AND_IMMEDIATELY_PRIOR_FOUR_WEEKS_ARE_ACCESSED",
    "ALL_SUMS_USE_INTEGER_ARITHMETIC_AND_ALL_RATIOS_USE_DECIMAL_NEVER_FLOAT",
    "SEVEN_ROW_WARMUP_PRODUCES_EXACTLY_273_MEASUREMENT_ROWS",
    "NONPOSITIVE_DENOMINATOR_MISSING_DUPLICATE_OR_AMBIGUOUS_DATA_STOPS_THE_RUN",
    "NO_IMPUTATION_WINSORIZATION_CLIPPING_RANKING_ZSCORE_OR_OUTCOME_FIT",
    "BOTH_COMPONENTS_MUST_STRICTLY_BROADEN_FOR_BROADENING_AGREEMENT",
    "SOURCE_WEEK_CUTOFF_EXECUTION_DATE_AND_PAYLOAD_HASH_LINEAGE_ARE_RETAINED",
    "JSONL_SERIALIZATION_REPRODUCES_BYTE_FOR_BYTE",
    "NO_STRATEGY_RULE_SIGNAL_POSITION_CANDIDATE_OR_ORDER_IS_CREATED",
    "ZERO_MARKET_VALUES_RETURNS_VALIDATION_HOLDOUT_AND_PROFIT",
)


class S2MeasurementDefinition(BaseModel):
    measurement_id: Literal[
        "confirmed_tx_current_4w",
        "confirmed_tx_prior_4w",
        "confirmed_fee_sats_current_4w",
        "confirmed_fee_sats_prior_4w",
        "confirmed_tx_growth_ppm",
        "confirmed_fee_growth_ppm",
        "settlement_demand_agreement",
    ]
    formula: Literal[
        "SUM_CONFIRMED_NON_COINBASE_TX_LAGS_0_TO_3",
        "SUM_CONFIRMED_NON_COINBASE_TX_LAGS_4_TO_7",
        "SUM_CONFIRMED_FEE_SATOSHIS_LAGS_0_TO_3",
        "SUM_CONFIRMED_FEE_SATOSHIS_LAGS_4_TO_7",
        "ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_TX",
        "ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_FEE",
        "BOTH_BROADENING_IF_BOTH_GROWTH_PPM_GT_ZERO_BOTH_CONTRACTING_IF_BOTH_LT_ZERO_ELSE_FLAT_OR_MIXED",
    ]
    output_type: Literal["INTEGER", "ENUM"]
    unit: Literal["TRANSACTIONS", "SATOSHIS", "PARTS_PER_MILLION", "CATEGORY"]
    maximum_lag_weeks: Literal[3, 7]

    model_config = ConfigDict(extra="forbid", frozen=True)


class S2DevelopmentMeasurementProtocol(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-protocol-v1"] = (
        "aurex-s2-development-measurement-protocol-v1"
    )
    protocol_id: Literal["s2-development-measurement-protocol-v1"] = (
        "s2-development-measurement-protocol-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_BEFORE_S2_PAYLOAD_VALUE_READ"] = "FROZEN_BEFORE_S2_PAYLOAD_VALUE_READ"
    builder_contract_hash: str
    charter_evidence_hash: str
    payload_protocol_evidence_hash: str
    payload_protocol_audit_evidence_hash: str
    payload_result_evidence_hash: str
    payload_result_audit_evidence_hash: str
    payload_file_sha256: str
    payload_evidence_hash: str
    source_bindings: tuple[S2FeasibilityBinding, ...] = Field(min_length=15, max_length=15)
    payload_bytes_hashed_during_freeze: Literal[94662] = 94_662
    payload_value_rows_parsed_during_freeze: Literal[0] = 0
    input_row_count: Literal[280] = 280
    first_input_week_start: date = date(2017, 8, 19)
    last_input_week_start: date = date(2022, 12, 24)
    input_frequency: Literal["WEEKLY_SATURDAY_TO_FRIDAY_UTC"] = "WEEKLY_SATURDAY_TO_FRIDAY_UTC"
    decision_cutoff_policy: Literal["FOLLOWING_SATURDAY_00_00_UTC"] = "FOLLOWING_SATURDAY_00_00_UTC"
    earliest_execution_policy: Literal["FOLLOWING_MONDAY_00_00_UTC"] = "FOLLOWING_MONDAY_00_00_UTC"
    confirmation_policy: Literal["BLOCK_SIXTH_CONFIRMATION_STRICTLY_BEFORE_CUTOFF"] = (
        "BLOCK_SIXTH_CONFIRMATION_STRICTLY_BEFORE_CUTOFF"
    )
    current_window_weeks: Literal[4] = 4
    prior_window_weeks: Literal[4] = 4
    maximum_lag_weeks: Literal[7] = 7
    warmup_input_rows: Literal[7] = 7
    expected_measurement_row_count: Literal[273] = 273
    measurement_definitions: tuple[S2MeasurementDefinition, ...] = Field(
        min_length=7,
        max_length=7,
    )
    measurement_count: Literal[7] = 7
    arithmetic_policy: Literal["INTEGER_SUMS_DECIMAL_28_ROUND_HALF_EVEN_PPM_NO_FLOAT"] = (
        "INTEGER_SUMS_DECIMAL_28_ROUND_HALF_EVEN_PPM_NO_FLOAT"
    )
    normalization_policy: Literal["DIMENSIONLESS_PPM_ONLY_NO_RANK_ZSCORE_OR_OUTCOME_FIT"] = (
        "DIMENSIONLESS_PPM_ONLY_NO_RANK_ZSCORE_OR_OUTCOME_FIT"
    )
    missing_value_policy: Literal["REJECT_ENTIRE_RUN_NO_IMPUTATION"] = (
        "REJECT_ENTIRE_RUN_NO_IMPUTATION"
    )
    nonpositive_denominator_policy: Literal["REJECT_ENTIRE_RUN"] = "REJECT_ENTIRE_RUN"
    outlier_policy: Literal["PRESERVE_EXACT_VALUES_NO_WINSORIZATION_OR_CLIPPING"] = (
        "PRESERVE_EXACT_VALUES_NO_WINSORIZATION_OR_CLIPPING"
    )
    agreement_categories: tuple[
        Literal["BOTH_BROADENING"],
        Literal["BOTH_CONTRACTING"],
        Literal["FLAT_OR_MIXED"],
    ] = (
        "BOTH_BROADENING",
        "BOTH_CONTRACTING",
        "FLAT_OR_MIXED",
    )
    output_path: Literal["data/evidence/s2_development_measurements_v1.jsonl"] = (
        "data/evidence/s2_development_measurements_v1.jsonl"
    )
    output_fields: tuple[str, ...] = (
        "sequence",
        "week_start",
        "decision_cutoff_at",
        "earliest_execution_at",
        "source_payload_evidence_hash",
        "confirmed_tx_current_4w",
        "confirmed_tx_prior_4w",
        "confirmed_fee_sats_current_4w",
        "confirmed_fee_sats_prior_4w",
        "confirmed_tx_growth_ppm",
        "confirmed_fee_growth_ppm",
        "settlement_demand_agreement",
    )
    forbidden_output_fields: tuple[str, ...] = (
        "btc_open",
        "btc_high",
        "btc_low",
        "btc_close",
        "btc_volume",
        "btc_return",
        "forward_return",
        "signal",
        "position",
        "pnl",
        "candidate_id",
    )
    quality_gates: tuple[str, ...] = Field(min_length=13, max_length=13)
    future_strategy_family_budget: Literal[1] = 1
    future_candidate_budget: Literal[1] = 1
    future_parameter_combination_budget: Literal[1] = 1
    future_parameter_search_policy: Literal["NO_OUTCOME_DRIVEN_PARAMETER_SEARCH"] = (
        "NO_OUTCOME_DRIVEN_PARAMETER_SEARCH"
    )
    strategy_parameters_defined: tuple[str, ...] = ()
    strategy_rules_defined: tuple[str, ...] = ()
    authorizes_measurement_runner_implementation: Literal[True] = True
    authorizes_payload_value_read_now: Literal[False] = False
    authorizes_measurement_calculation_now: Literal[False] = False
    authorizes_strategy_parameter_definition: Literal[False] = False
    authorizes_market_value_access: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_access: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_strategy_candidate: Literal[False] = False
    authorizes_pine: Literal[False] = False
    authorizes_paper: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    decision: Literal["FREEZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL"] = S2_MEASUREMENT_DECISION
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_MEASUREMENT_NEXT
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "builder_contract_hash",
        "charter_evidence_hash",
        "payload_protocol_evidence_hash",
        "payload_protocol_audit_evidence_hash",
        "payload_result_evidence_hash",
        "payload_result_audit_evidence_hash",
        "payload_file_sha256",
        "payload_evidence_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> S2DevelopmentMeasurementProtocol:
        expected_definitions = (
            (
                "confirmed_tx_current_4w",
                "SUM_CONFIRMED_NON_COINBASE_TX_LAGS_0_TO_3",
                "INTEGER",
                "TRANSACTIONS",
                3,
            ),
            (
                "confirmed_tx_prior_4w",
                "SUM_CONFIRMED_NON_COINBASE_TX_LAGS_4_TO_7",
                "INTEGER",
                "TRANSACTIONS",
                7,
            ),
            (
                "confirmed_fee_sats_current_4w",
                "SUM_CONFIRMED_FEE_SATOSHIS_LAGS_0_TO_3",
                "INTEGER",
                "SATOSHIS",
                3,
            ),
            (
                "confirmed_fee_sats_prior_4w",
                "SUM_CONFIRMED_FEE_SATOSHIS_LAGS_4_TO_7",
                "INTEGER",
                "SATOSHIS",
                7,
            ),
            (
                "confirmed_tx_growth_ppm",
                "ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_TX",
                "INTEGER",
                "PARTS_PER_MILLION",
                7,
            ),
            (
                "confirmed_fee_growth_ppm",
                "ROUND_HALF_EVEN_1E6_TIMES_CURRENT_MINUS_PRIOR_DIVIDED_BY_PRIOR_FEE",
                "INTEGER",
                "PARTS_PER_MILLION",
                7,
            ),
            (
                "settlement_demand_agreement",
                "BOTH_BROADENING_IF_BOTH_GROWTH_PPM_GT_ZERO_BOTH_CONTRACTING_IF_BOTH_LT_ZERO_ELSE_FLAT_OR_MIXED",
                "ENUM",
                "CATEGORY",
                7,
            ),
        )
        actual_definitions = tuple(
            (
                item.measurement_id,
                item.formula,
                item.output_type,
                item.unit,
                item.maximum_lag_weeks,
            )
            for item in self.measurement_definitions
        )
        paths = tuple(item.path for item in self.source_bindings)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("S2 measurement source bindings must be unique and sorted")
        if actual_definitions != expected_definitions:
            raise ValueError("S2 measurement family changed")
        if self.quality_gates != S2_MEASUREMENT_GATES:
            raise ValueError("S2 measurement gates changed")
        if self.expected_measurement_row_count != self.input_row_count - self.warmup_input_rows:
            raise ValueError("S2 measurement warmup changed")
        if set(self.output_fields) & set(self.forbidden_output_fields):
            raise ValueError("S2 measurement output contains a forbidden outcome field")
        if self.strategy_parameters_defined or self.strategy_rules_defined:
            raise ValueError("S2 measurement protocol cannot define a strategy")
        if self.limitations != tuple(sorted(set(self.limitations))):
            raise ValueError("S2 measurement limitations must be unique and sorted")
        expected_hash = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("S2 measurement protocol hash changed")
        return self


class S2DevelopmentMeasurementProtocolAudit(BaseModel):
    schema_version: Literal["aurex-s2-development-measurement-protocol-audit-v1"] = (
        "aurex-s2-development-measurement-protocol-audit-v1"
    )
    audit_id: Literal["s2-development-measurement-protocol-audit-v1"] = (
        "s2-development-measurement-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_path: Literal["data/evidence/s2_development_measurement_protocol_v1.json"] = (
        "data/evidence/s2_development_measurement_protocol_v1.json"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    payload_file_sha256: str
    payload_evidence_hash: str
    source_binding_count: Literal[15] = 15
    payload_bytes_hashed: Literal[94662] = 94_662
    payload_value_rows_parsed: Literal[0] = 0
    measurement_definition_count: Literal[7] = 7
    expected_measurement_row_count: Literal[273] = 273
    reconstructed_exactly: Literal[True] = True
    network_requests_observed: Literal[0] = 0
    market_values_read: Literal[0] = 0
    returns_calculated: Literal[0] = 0
    strategy_candidates_created: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    decision: Literal["PASS_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_AUDIT"] = (
        S2_MEASUREMENT_AUDIT_DECISION
    )
    next_authorization: Literal[
        "AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY"
    ] = S2_MEASUREMENT_NEXT
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "payload_file_sha256",
        "payload_evidence_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> S2DevelopmentMeasurementProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(mode="json", exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("S2 measurement protocol audit hash changed")
        return self
