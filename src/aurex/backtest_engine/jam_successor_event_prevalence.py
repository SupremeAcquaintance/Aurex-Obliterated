from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_MONTHS,
)
from aurex.backtest_engine.jam_successor_event_outcome_protocol import (
    JAM_EVENT_CONDITION_SPECS,
    JAM_EVENT_PREVALENCE_GATE_SPECS,
    JamEventCondition,
    JamProtocolGate,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_PREVALENCE_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-successor-development-event-prevalence-protocol-v1"
)
JAM_PREVALENCE_RESULT_SCHEMA_VERSION = (
    "aurex-jam-successor-development-event-prevalence-result-v1"
)
JAM_PREVALENCE_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-successor-development-event-prevalence-audit-v1"
)
JAM_PREVALENCE_AUTHORIZATION_RECORD = (
    "USER_CONFIRMED_PROCEED_WITH_FROZEN_DEVELOPMENT_EVENT_PREVALENCE_STAGE"
)
JAM_PREVALENCE_AUTHORIZATION_SCOPE = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"
)
JAM_PREVALENCE_PASS_DECISION = (
    "PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION"
)
JAM_PREVALENCE_FAIL_DECISION = "STOP_JAM_SUCCESSOR_EVENT_PREVALENCE_FAILED"
JAM_PREVALENCE_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION"
)
JAM_PREVALENCE_NO_NEXT_AUTHORIZATION = "NONE_EVENT_PREVALENCE_FAILED"
JAM_PREVALENCE_EVENT_ID = "J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1"
JAM_PREVALENCE_EVENT_FEATURE_IDS = tuple(
    feature_id for _, feature_id, _, _ in JAM_EVENT_CONDITION_SPECS
)
JAM_PREVALENCE_QUARTERS = tuple(
    f"{year}-Q{quarter}" for year in (2019, 2020) for quarter in range(1, 5)
)
JAM_PREVALENCE_LEDGER_PATH = (
    "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
)


def normalize_decimal_string(value: str | Decimal) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Jam prevalence decimal is invalid") from exc
    if not parsed.is_finite():
        raise ValueError("Jam prevalence decimal must be finite")
    return format(parsed, "f")


def _evaluate_comparison(
    *,
    observed: Decimal,
    comparison: str,
    threshold: Decimal,
) -> bool:
    if comparison == "GREATER_THAN_OR_EQUAL":
        return observed >= threshold
    if comparison == "LESS_THAN_OR_EQUAL":
        return observed <= threshold
    if comparison == "GREATER_THAN":
        return observed > threshold
    if comparison == "EQUAL":
        return observed == threshold
    raise ValueError("Jam prevalence comparison changed")


class JamSuccessorDevelopmentEventPrevalenceProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-event-prevalence-protocol-v1"
    ] = JAM_PREVALENCE_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal[
        "jam-successor-development-event-prevalence-protocol-v1"
    ] = "jam-successor-development-event-prevalence-protocol-v1"
    frozen_at: datetime
    status: Literal["FROZEN_DEVELOPMENT_PREVALENCE_ONLY_NO_OUTCOMES"] = (
        "FROZEN_DEVELOPMENT_PREVALENCE_ONLY_NO_OUTCOMES"
    )
    authorization_record: Literal[
        "USER_CONFIRMED_PROCEED_WITH_FROZEN_DEVELOPMENT_EVENT_PREVALENCE_STAGE"
    ] = JAM_PREVALENCE_AUTHORIZATION_RECORD
    authorization_scope: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"
    ] = JAM_PREVALENCE_AUTHORIZATION_SCOPE
    parent_event_protocol_path: str
    parent_event_protocol_file_sha256: str
    parent_event_protocol_evidence_hash: str
    parent_event_audit_path: str
    parent_event_audit_file_sha256: str
    parent_event_audit_evidence_hash: str
    feature_rows_path: str
    feature_rows_file_sha256: str
    feature_rows_schema_hash: str
    feature_rows_bytes: int = Field(gt=0)
    calendar_row_count: Literal[1052640] = 1_052_640
    ready_row_count: Literal[1046202] = 1_046_202
    event_id: Literal[
        "J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1"
    ] = JAM_PREVALENCE_EVENT_ID
    event_conditions: list[JamEventCondition] = Field(min_length=5, max_length=5)
    minimum_event_separation_minutes: Literal[60] = 60
    suppression_resets_between_months: Literal[False] = False
    suppression_resets_between_years: Literal[False] = False
    suppression_resets_at_evidence_partition: Literal[True] = True
    prevalence_gates: list[JamProtocolGate] = Field(min_length=7, max_length=7)
    event_ledger_path: Literal[
        "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
    ] = JAM_PREVALENCE_LEDGER_PATH
    event_ledger_scope: Literal[
        "ALL_RAW_EVENTS_WITH_ACCEPTED_OR_SUPPRESSED_STATUS"
    ] = "ALL_RAW_EVENTS_WITH_ACCEPTED_OR_SUPPRESSED_STATUS"
    builder_contract_hash: str
    network_access_permitted: Literal[False] = False
    development_feature_access_permitted: Literal[True] = True
    validation_2021_access_permitted: Literal[False] = False
    holdout_2022_access_permitted: Literal[False] = False
    future_price_access_permitted: Literal[False] = False
    future_label_calculation_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    matched_control_construction_permitted: Literal[False] = False
    backtest_permitted: Literal[False] = False
    strategy_creation_permitted: Literal[False] = False
    signal_creation_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_eligibility_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: list[str] = Field(min_length=12)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_event_protocol_file_sha256",
        "parent_event_protocol_evidence_hash",
        "parent_event_audit_file_sha256",
        "parent_event_audit_evidence_hash",
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "builder_contract_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("limitations")
    @classmethod
    def normalize_limitations(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_protocol(
        self,
    ) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
        conditions = [
            (
                item.condition_id,
                item.feature_id,
                item.comparison,
                item.source_quantile,
            )
            for item in self.event_conditions
        ]
        gates = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.prevalence_gates
        ]
        if (
            conditions != list(JAM_EVENT_CONDITION_SPECS)
            or gates != list(JAM_EVENT_PREVALENCE_GATE_SPECS)
        ):
            raise ValueError("Jam prevalence event or gate matrix changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam prevalence protocol hash changed")
        return self


class JamPrevalenceInputRow(BaseModel):
    open_time_ms: int = Field(ge=0)
    month: str
    quality_state: Literal["READY"] = "READY"
    shock_sell_flow_robust_z_5m: Decimal
    shock_sell_share_5m: Decimal
    shock_price_impact_bps_5m: Decimal
    sell_flow_decay_ratio_3m_vs_5m: Decimal
    reclaim_bps_vs_pre_shock_vwap: Decimal

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_row(self) -> JamPrevalenceInputRow:
        if (
            self.open_time_ms % 60_000
            or self.month not in JAM_DISTRIBUTION_MONTHS
            or any(
                not getattr(self, feature_id).is_finite()
                for feature_id in JAM_PREVALENCE_EVENT_FEATURE_IDS
            )
        ):
            raise ValueError("Jam prevalence input row changed")
        timestamp = datetime.fromtimestamp(self.open_time_ms / 1_000, tz=UTC)
        if timestamp.strftime("%Y-%m") != self.month:
            raise ValueError("Jam prevalence row month does not match timestamp")
        return self


class JamDevelopmentEventLedgerRecord(BaseModel):
    raw_event_sequence: int = Field(gt=0)
    accepted_event_sequence: int | None = Field(default=None, gt=0)
    event_id: Literal[
        "J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1"
    ] = JAM_PREVALENCE_EVENT_ID
    open_time_ms: int = Field(ge=0)
    calendar_month: str
    calendar_day: str
    calendar_quarter: str
    quality_state: Literal["READY"] = "READY"
    status: Literal[
        "ACCEPTED_FIRST_EVENT",
        "ACCEPTED_MINIMUM_SEPARATION_MET",
        "SUPPRESSED_WITHIN_60_MINUTES",
    ]
    accepted: bool
    prior_accepted_open_time_ms: int | None = Field(default=None, ge=0)
    minutes_since_prior_accepted: int | None = Field(default=None, ge=0)
    shock_sell_flow_robust_z_5m: str
    shock_sell_share_5m: str
    shock_price_impact_bps_5m: str
    sell_flow_decay_ratio_3m_vs_5m: str
    reclaim_bps_vs_pre_shock_vwap: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(*JAM_PREVALENCE_EVENT_FEATURE_IDS)
    @classmethod
    def normalize_features(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_record(self) -> JamDevelopmentEventLedgerRecord:
        timestamp = datetime.fromtimestamp(self.open_time_ms / 1_000, tz=UTC)
        expected_quarter = f"{timestamp.year}-Q{((timestamp.month - 1) // 3) + 1}"
        if (
            self.open_time_ms % 60_000
            or self.calendar_month != timestamp.strftime("%Y-%m")
            or self.calendar_day != timestamp.date().isoformat()
            or self.calendar_quarter != expected_quarter
            or self.calendar_month not in JAM_DISTRIBUTION_MONTHS
            or self.calendar_quarter not in JAM_PREVALENCE_QUARTERS
        ):
            raise ValueError("Jam event ledger timestamp fields changed")
        if self.accepted != self.status.startswith("ACCEPTED"):
            raise ValueError("Jam event ledger acceptance status changed")
        if self.accepted != (self.accepted_event_sequence is not None):
            raise ValueError("Jam event ledger accepted sequence changed")
        if self.status == "ACCEPTED_FIRST_EVENT":
            if (
                self.prior_accepted_open_time_ms is not None
                or self.minutes_since_prior_accepted is not None
            ):
                raise ValueError("Jam first event suppression state changed")
        elif (
            self.prior_accepted_open_time_ms is None
            or self.minutes_since_prior_accepted is None
        ):
            raise ValueError("Jam event suppression anchor is missing")
        return self


class JamPrevalenceBucketCount(BaseModel):
    bucket: str = Field(min_length=1)
    accepted_event_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class JamPrevalenceGateResult(BaseModel):
    gate_id: str = Field(min_length=1)
    comparison: Literal[
        "GREATER_THAN_OR_EQUAL",
        "LESS_THAN_OR_EQUAL",
        "GREATER_THAN",
        "EQUAL",
    ]
    threshold: str
    units: str = Field(min_length=1)
    observed: str
    passed: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("threshold", "observed")
    @classmethod
    def normalize_values(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_gate(self) -> JamPrevalenceGateResult:
        expected = _evaluate_comparison(
            observed=Decimal(self.observed),
            comparison=self.comparison,
            threshold=Decimal(self.threshold),
        )
        if self.passed != expected:
            raise ValueError("Jam prevalence gate decision changed")
        return self


class JamSuccessorDevelopmentEventPrevalenceResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-event-prevalence-result-v1"
    ] = JAM_PREVALENCE_RESULT_SCHEMA_VERSION
    result_id: Literal[
        "jam-successor-development-event-prevalence-result-v1"
    ] = "jam-successor-development-event-prevalence-result-v1"
    generated_at: datetime
    status: Literal["COMPLETE_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"] = (
        "COMPLETE_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    parent_event_protocol_evidence_hash: str
    feature_rows_file_sha256: str
    feature_rows_schema_hash: str
    event_ledger_path: Literal[
        "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
    ] = JAM_PREVALENCE_LEDGER_PATH
    event_ledger_file_sha256: str
    event_ledger_bytes: int = Field(ge=0)
    event_ledger_record_count: int = Field(ge=0)
    calendar_row_count: Literal[1052640] = 1_052_640
    ready_row_count: Literal[1046202] = 1_046_202
    raw_event_count: int = Field(ge=0)
    accepted_event_count: int = Field(ge=0)
    suppressed_event_count: int = Field(ge=0)
    accepted_non_ready_event_count: Literal[0] = 0
    raw_event_rate_per_ready_row: str
    accepted_event_rate_per_ready_row: str
    suppression_rate_per_raw_event: str
    monthly_counts: list[JamPrevalenceBucketCount] = Field(
        min_length=24,
        max_length=24,
    )
    quarterly_counts: list[JamPrevalenceBucketCount] = Field(
        min_length=8,
        max_length=8,
    )
    daily_counts: list[JamPrevalenceBucketCount]
    months_with_at_least_five_events: int = Field(ge=0, le=24)
    minimum_quarter_event_count: int = Field(ge=0)
    largest_month: str = Field(min_length=1)
    largest_month_event_count: int = Field(ge=0)
    largest_month_event_share: str
    largest_day: str = Field(min_length=1)
    largest_day_event_count: int = Field(ge=0)
    largest_day_event_share: str
    gates: list[JamPrevalenceGateResult] = Field(min_length=7, max_length=7)
    passed_gate_count: int = Field(ge=0, le=7)
    failed_gate_count: int = Field(ge=0, le=7)
    decision: Literal[
        "PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_EVENT_PREVALENCE_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION",
        "NONE_EVENT_PREVALENCE_FAILED",
    ]
    real_market_periods_opened: list[str] = Field(min_length=1, max_length=1)
    sealed_market_periods_opened: list[str] = Field(default_factory=list)
    future_price_rows_accessed: Literal[0] = 0
    future_labels_calculated: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    matched_controls_constructed: Literal[0] = 0
    backtests_executed: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    creates_strategy: Literal[False] = False
    creates_signal: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=12)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "parent_event_protocol_evidence_hash",
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "event_ledger_file_sha256",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "raw_event_rate_per_ready_row",
        "accepted_event_rate_per_ready_row",
        "suppression_rate_per_raw_event",
        "largest_month_event_share",
        "largest_day_event_share",
    )
    @classmethod
    def normalize_rates(cls, value: str) -> str:
        normalized = normalize_decimal_string(value)
        if not Decimal(0) <= Decimal(normalized) <= Decimal(1):
            raise ValueError("Jam prevalence rate is outside zero and one")
        return normalized

    @field_validator(
        "real_market_periods_opened",
        "sealed_market_periods_opened",
        "future_labels_calculated",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> JamSuccessorDevelopmentEventPrevalenceResult:
        if (
            [item.bucket for item in self.monthly_counts]
            != list(JAM_DISTRIBUTION_MONTHS)
            or [item.bucket for item in self.quarterly_counts]
            != list(JAM_PREVALENCE_QUARTERS)
        ):
            raise ValueError("Jam prevalence time bucket matrix changed")
        if [item.bucket for item in self.daily_counts] != sorted(
            item.bucket for item in self.daily_counts
        ):
            raise ValueError("Jam prevalence daily counts are not chronological")
        if len({item.bucket for item in self.daily_counts}) != len(self.daily_counts):
            raise ValueError("Jam prevalence daily count is duplicated")
        if (
            self.event_ledger_record_count != self.raw_event_count
            or self.raw_event_count
            != self.accepted_event_count + self.suppressed_event_count
            or sum(item.accepted_event_count for item in self.monthly_counts)
            != self.accepted_event_count
            or sum(item.accepted_event_count for item in self.quarterly_counts)
            != self.accepted_event_count
            or sum(item.accepted_event_count for item in self.daily_counts)
            != self.accepted_event_count
        ):
            raise ValueError("Jam prevalence event counts do not reconcile")
        divisor = Decimal(self.ready_row_count)
        expected_raw_rate = Decimal(self.raw_event_count) / divisor
        expected_accepted_rate = Decimal(self.accepted_event_count) / divisor
        expected_suppression_rate = (
            Decimal(self.suppressed_event_count) / Decimal(self.raw_event_count)
            if self.raw_event_count
            else Decimal(0)
        )
        if (
            Decimal(self.raw_event_rate_per_ready_row) != expected_raw_rate
            or Decimal(self.accepted_event_rate_per_ready_row)
            != expected_accepted_rate
            or Decimal(self.suppression_rate_per_raw_event)
            != expected_suppression_rate
        ):
            raise ValueError("Jam prevalence rates do not reconcile")
        expected_months = sum(
            item.accepted_event_count >= 5 for item in self.monthly_counts
        )
        expected_minimum_quarter = min(
            item.accepted_event_count for item in self.quarterly_counts
        )
        maximum_month = max(
            self.monthly_counts,
            key=lambda item: (item.accepted_event_count, item.bucket),
        )
        expected_month_share = (
            Decimal(maximum_month.accepted_event_count)
            / Decimal(self.accepted_event_count)
            if self.accepted_event_count
            else Decimal(0)
        )
        if self.daily_counts:
            maximum_day = max(
                self.daily_counts,
                key=lambda item: (item.accepted_event_count, item.bucket),
            )
            expected_day = maximum_day.bucket
            expected_day_count = maximum_day.accepted_event_count
        else:
            expected_day = "NONE"
            expected_day_count = 0
        expected_day_share = (
            Decimal(expected_day_count) / Decimal(self.accepted_event_count)
            if self.accepted_event_count
            else Decimal(0)
        )
        if (
            self.months_with_at_least_five_events != expected_months
            or self.minimum_quarter_event_count != expected_minimum_quarter
            or self.largest_month != maximum_month.bucket
            or self.largest_month_event_count != maximum_month.accepted_event_count
            or Decimal(self.largest_month_event_share) != expected_month_share
            or self.largest_day != expected_day
            or self.largest_day_event_count != expected_day_count
            or Decimal(self.largest_day_event_share) != expected_day_share
        ):
            raise ValueError("Jam prevalence concentration summary changed")
        gate_matrix = [
            (item.gate_id, item.comparison, item.threshold, item.units)
            for item in self.gates
        ]
        if gate_matrix != list(JAM_EVENT_PREVALENCE_GATE_SPECS):
            raise ValueError("Jam prevalence result gate matrix changed")
        observed = [
            str(self.raw_event_count),
            str(self.accepted_event_count),
            str(self.months_with_at_least_five_events),
            str(self.minimum_quarter_event_count),
            self.largest_month_event_share,
            self.largest_day_event_share,
            str(self.accepted_non_ready_event_count),
        ]
        if [item.observed for item in self.gates] != [
            normalize_decimal_string(item) for item in observed
        ]:
            raise ValueError("Jam prevalence gate observations changed")
        passed = sum(item.passed for item in self.gates)
        all_passed = passed == len(self.gates)
        if (
            self.passed_gate_count != passed
            or self.failed_gate_count != len(self.gates) - passed
            or self.decision
            != (
                JAM_PREVALENCE_PASS_DECISION
                if all_passed
                else JAM_PREVALENCE_FAIL_DECISION
            )
            or self.next_required_authorization
            != (
                JAM_PREVALENCE_NEXT_AUTHORIZATION
                if all_passed
                else JAM_PREVALENCE_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam prevalence decision changed")
        if (
            self.real_market_periods_opened
            != ["2019-01_THROUGH_2020-12_DEVELOPMENT_FEATURES_ONLY"]
            or self.sealed_market_periods_opened
            or self.future_price_rows_accessed
            or self.future_labels_calculated
            or self.return_metrics_calculated
            or self.matched_controls_constructed
            or self.backtests_executed
            or self.strategy_executions
        ):
            raise ValueError("Jam prevalence outcome boundary changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam prevalence result hash changed")
        return self


class JamSuccessorDevelopmentEventPrevalenceAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-event-prevalence-audit-v1"
    ] = JAM_PREVALENCE_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    event_ledger_path: str
    event_ledger_file_sha256: str
    event_ledger_record_count_reconstructed: int = Field(ge=0)
    raw_event_count_reconstructed: int = Field(ge=0)
    accepted_event_count_reconstructed: int = Field(ge=0)
    suppressed_event_count_reconstructed: int = Field(ge=0)
    passed_gate_count_reconstructed: int = Field(ge=0, le=7)
    failed_gate_count_reconstructed: int = Field(ge=0, le=7)
    sealed_market_periods_opened: Literal[0] = 0
    future_price_rows_accessed: Literal[0] = 0
    future_labels_calculated: Literal[0] = 0
    return_metrics_calculated: Literal[0] = 0
    matched_controls_constructed: Literal[0] = 0
    backtests_executed: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    decision: Literal[
        "PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_EVENT_PREVALENCE_FAILED",
    ]
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
        "event_ledger_file_sha256",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(
        self,
    ) -> JamSuccessorDevelopmentEventPrevalenceAudit:
        if (
            self.event_ledger_record_count_reconstructed
            != self.raw_event_count_reconstructed
            or self.raw_event_count_reconstructed
            != self.accepted_event_count_reconstructed
            + self.suppressed_event_count_reconstructed
        ):
            raise ValueError("Jam prevalence audit counts do not reconcile")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam prevalence audit hash changed")
        return self


def event_row_matches(
    row: JamPrevalenceInputRow,
    conditions: list[JamEventCondition],
) -> bool:
    for condition in conditions:
        observed = getattr(row, condition.feature_id)
        if not _evaluate_comparison(
            observed=observed,
            comparison=condition.comparison,
            threshold=Decimal(condition.frozen_threshold),
        ):
            return False
    return True


def build_event_ledger(
    rows: list[JamPrevalenceInputRow],
    *,
    conditions: list[JamEventCondition],
    minimum_separation_minutes: int = 60,
) -> list[JamDevelopmentEventLedgerRecord]:
    if minimum_separation_minutes != 60:
        raise ValueError("Jam event suppression interval changed")
    observed_times = [row.open_time_ms for row in rows]
    if observed_times != sorted(observed_times) or len(set(observed_times)) != len(
        observed_times
    ):
        raise ValueError("Jam raw events are not strictly chronological")
    records: list[JamDevelopmentEventLedgerRecord] = []
    last_accepted: int | None = None
    accepted_sequence = 0
    for raw_sequence, row in enumerate(rows, start=1):
        if not event_row_matches(row, conditions):
            raise ValueError("Jam raw event does not satisfy the frozen predicate")
        if last_accepted is None:
            accepted = True
            status = "ACCEPTED_FIRST_EVENT"
            minutes_since_prior = None
        else:
            elapsed_ms = row.open_time_ms - last_accepted
            if elapsed_ms < 0 or elapsed_ms % 60_000:
                raise ValueError("Jam raw event elapsed time changed")
            minutes_since_prior = elapsed_ms // 60_000
            accepted = minutes_since_prior >= minimum_separation_minutes
            status = (
                "ACCEPTED_MINIMUM_SEPARATION_MET"
                if accepted
                else "SUPPRESSED_WITHIN_60_MINUTES"
            )
        if accepted:
            accepted_sequence += 1
        timestamp = datetime.fromtimestamp(row.open_time_ms / 1_000, tz=UTC)
        record = JamDevelopmentEventLedgerRecord(
            raw_event_sequence=raw_sequence,
            accepted_event_sequence=accepted_sequence if accepted else None,
            open_time_ms=row.open_time_ms,
            calendar_month=timestamp.strftime("%Y-%m"),
            calendar_day=timestamp.date().isoformat(),
            calendar_quarter=f"{timestamp.year}-Q{((timestamp.month - 1) // 3) + 1}",
            status=status,
            accepted=accepted,
            prior_accepted_open_time_ms=last_accepted,
            minutes_since_prior_accepted=minutes_since_prior,
            **{
                feature_id: normalize_decimal_string(getattr(row, feature_id))
                for feature_id in JAM_PREVALENCE_EVENT_FEATURE_IDS
            },
        )
        records.append(record)
        if accepted:
            last_accepted = row.open_time_ms
    validate_event_ledger(records, conditions=conditions)
    return records


def validate_event_ledger(
    records: list[JamDevelopmentEventLedgerRecord],
    *,
    conditions: list[JamEventCondition],
) -> None:
    accepted_sequence = 0
    last_accepted: int | None = None
    for raw_sequence, record in enumerate(records, start=1):
        if record.raw_event_sequence != raw_sequence:
            raise ValueError("Jam raw event sequence changed")
        row = JamPrevalenceInputRow(
            open_time_ms=record.open_time_ms,
            month=record.calendar_month,
            **{
                feature_id: Decimal(getattr(record, feature_id))
                for feature_id in JAM_PREVALENCE_EVENT_FEATURE_IDS
            },
        )
        if not event_row_matches(row, conditions):
            raise ValueError("Jam event ledger predicate changed")
        if last_accepted is None:
            expected_accepted = True
            expected_status = "ACCEPTED_FIRST_EVENT"
            expected_minutes = None
        else:
            expected_minutes = (record.open_time_ms - last_accepted) // 60_000
            expected_accepted = expected_minutes >= 60
            expected_status = (
                "ACCEPTED_MINIMUM_SEPARATION_MET"
                if expected_accepted
                else "SUPPRESSED_WITHIN_60_MINUTES"
            )
        if expected_accepted:
            accepted_sequence += 1
        if (
            record.accepted != expected_accepted
            or record.status != expected_status
            or record.prior_accepted_open_time_ms != last_accepted
            or record.minutes_since_prior_accepted != expected_minutes
            or record.accepted_event_sequence
            != (accepted_sequence if expected_accepted else None)
        ):
            raise ValueError("Jam event ledger suppression changed")
        if expected_accepted:
            last_accepted = record.open_time_ms


def build_prevalence_gate_results(
    observations: list[str],
) -> list[JamPrevalenceGateResult]:
    if len(observations) != len(JAM_EVENT_PREVALENCE_GATE_SPECS):
        raise ValueError("Jam prevalence gate observations changed")
    results = []
    for spec, observed in zip(
        JAM_EVENT_PREVALENCE_GATE_SPECS,
        observations,
        strict=True,
    ):
        gate_id, comparison, threshold, units = spec
        normalized_observed = normalize_decimal_string(observed)
        results.append(
            JamPrevalenceGateResult(
                gate_id=gate_id,
                comparison=comparison,
                threshold=threshold,
                units=units,
                observed=normalized_observed,
                passed=_evaluate_comparison(
                    observed=Decimal(normalized_observed),
                    comparison=comparison,
                    threshold=Decimal(threshold),
                ),
            )
        )
    return results


def build_jam_successor_prevalence_protocol(
    **values,
) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    payload = {
        "schema_version": JAM_PREVALENCE_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "jam-successor-development-event-prevalence-protocol-v1",
        "status": "FROZEN_DEVELOPMENT_PREVALENCE_ONLY_NO_OUTCOMES",
        "authorization_record": JAM_PREVALENCE_AUTHORIZATION_RECORD,
        "authorization_scope": JAM_PREVALENCE_AUTHORIZATION_SCOPE,
        "calendar_row_count": 1_052_640,
        "ready_row_count": 1_046_202,
        "event_id": JAM_PREVALENCE_EVENT_ID,
        "minimum_event_separation_minutes": 60,
        "suppression_resets_between_months": False,
        "suppression_resets_between_years": False,
        "suppression_resets_at_evidence_partition": True,
        "prevalence_gates": [
            JamProtocolGate(
                gate_id=gate_id,
                comparison=comparison,
                threshold=threshold,
                units=units,
            )
            for gate_id, comparison, threshold, units in JAM_EVENT_PREVALENCE_GATE_SPECS
        ],
        "event_ledger_path": JAM_PREVALENCE_LEDGER_PATH,
        "event_ledger_scope": "ALL_RAW_EVENTS_WITH_ACCEPTED_OR_SUPPRESSED_STATUS",
        "network_access_permitted": False,
        "development_feature_access_permitted": True,
        "validation_2021_access_permitted": False,
        "holdout_2022_access_permitted": False,
        "future_price_access_permitted": False,
        "future_label_calculation_permitted": False,
        "return_calculation_permitted": False,
        "matched_control_construction_permitted": False,
        "backtest_permitted": False,
        "strategy_creation_permitted": False,
        "signal_creation_permitted": False,
        "candidate_creation_permitted": False,
        "paper_eligibility_permitted": False,
        "testnet_strategy_orders_permitted": False,
        "production_permitted": False,
        "live_permitted": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorDevelopmentEventPrevalenceProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_prevalence_result(
    *,
    records: list[JamDevelopmentEventLedgerRecord],
    **values,
) -> JamSuccessorDevelopmentEventPrevalenceResult:
    accepted = [record for record in records if record.accepted]
    monthly_map = {month: 0 for month in JAM_DISTRIBUTION_MONTHS}
    quarterly_map = {quarter: 0 for quarter in JAM_PREVALENCE_QUARTERS}
    daily_map: dict[str, int] = {}
    for record in accepted:
        monthly_map[record.calendar_month] += 1
        quarterly_map[record.calendar_quarter] += 1
        daily_map[record.calendar_day] = daily_map.get(record.calendar_day, 0) + 1
    monthly_counts = [
        JamPrevalenceBucketCount(bucket=key, accepted_event_count=count)
        for key, count in monthly_map.items()
    ]
    quarterly_counts = [
        JamPrevalenceBucketCount(bucket=key, accepted_event_count=count)
        for key, count in quarterly_map.items()
    ]
    daily_counts = [
        JamPrevalenceBucketCount(bucket=key, accepted_event_count=count)
        for key, count in sorted(daily_map.items())
    ]
    raw_count = len(records)
    accepted_count = len(accepted)
    suppressed_count = raw_count - accepted_count
    largest_month = max(
        monthly_counts,
        key=lambda item: (item.accepted_event_count, item.bucket),
    )
    largest_day = (
        max(
            daily_counts,
            key=lambda item: (item.accepted_event_count, item.bucket),
        )
        if daily_counts
        else JamPrevalenceBucketCount(bucket="NONE", accepted_event_count=0)
    )
    largest_month_share = (
        Decimal(largest_month.accepted_event_count) / Decimal(accepted_count)
        if accepted_count
        else Decimal(0)
    )
    largest_day_share = (
        Decimal(largest_day.accepted_event_count) / Decimal(accepted_count)
        if accepted_count
        else Decimal(0)
    )
    months_with_five = sum(
        item.accepted_event_count >= 5 for item in monthly_counts
    )
    minimum_quarter = min(item.accepted_event_count for item in quarterly_counts)
    observations = [
        str(raw_count),
        str(accepted_count),
        str(months_with_five),
        str(minimum_quarter),
        normalize_decimal_string(largest_month_share),
        normalize_decimal_string(largest_day_share),
        "0",
    ]
    gates = build_prevalence_gate_results(observations)
    passed = sum(item.passed for item in gates)
    payload = {
        "schema_version": JAM_PREVALENCE_RESULT_SCHEMA_VERSION,
        "result_id": "jam-successor-development-event-prevalence-result-v1",
        "status": "COMPLETE_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES",
        "event_ledger_path": JAM_PREVALENCE_LEDGER_PATH,
        "event_ledger_record_count": raw_count,
        "calendar_row_count": 1_052_640,
        "ready_row_count": 1_046_202,
        "raw_event_count": raw_count,
        "accepted_event_count": accepted_count,
        "suppressed_event_count": suppressed_count,
        "accepted_non_ready_event_count": 0,
        "raw_event_rate_per_ready_row": normalize_decimal_string(
            Decimal(raw_count) / Decimal(1_046_202)
        ),
        "accepted_event_rate_per_ready_row": normalize_decimal_string(
            Decimal(accepted_count) / Decimal(1_046_202)
        ),
        "suppression_rate_per_raw_event": normalize_decimal_string(
            Decimal(suppressed_count) / Decimal(raw_count) if raw_count else Decimal(0)
        ),
        "monthly_counts": monthly_counts,
        "quarterly_counts": quarterly_counts,
        "daily_counts": daily_counts,
        "months_with_at_least_five_events": months_with_five,
        "minimum_quarter_event_count": minimum_quarter,
        "largest_month": largest_month.bucket,
        "largest_month_event_count": largest_month.accepted_event_count,
        "largest_month_event_share": normalize_decimal_string(largest_month_share),
        "largest_day": largest_day.bucket,
        "largest_day_event_count": largest_day.accepted_event_count,
        "largest_day_event_share": normalize_decimal_string(largest_day_share),
        "gates": gates,
        "passed_gate_count": passed,
        "failed_gate_count": len(gates) - passed,
        "decision": (
            JAM_PREVALENCE_PASS_DECISION
            if passed == len(gates)
            else JAM_PREVALENCE_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_PREVALENCE_NEXT_AUTHORIZATION
            if passed == len(gates)
            else JAM_PREVALENCE_NO_NEXT_AUTHORIZATION
        ),
        "real_market_periods_opened": [
            "2019-01_THROUGH_2020-12_DEVELOPMENT_FEATURES_ONLY"
        ],
        "sealed_market_periods_opened": [],
        "future_price_rows_accessed": 0,
        "future_labels_calculated": [],
        "return_metrics_calculated": [],
        "matched_controls_constructed": 0,
        "backtests_executed": 0,
        "strategy_executions": 0,
        "creates_strategy": False,
        "creates_signal": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamSuccessorDevelopmentEventPrevalenceResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_prevalence_audit(
    **values,
) -> JamSuccessorDevelopmentEventPrevalenceAudit:
    payload = {
        "schema_version": JAM_PREVALENCE_AUDIT_SCHEMA_VERSION,
        "sealed_market_periods_opened": 0,
        "future_price_rows_accessed": 0,
        "future_labels_calculated": 0,
        "return_metrics_calculated": 0,
        "matched_controls_constructed": 0,
        "backtests_executed": 0,
        "strategy_executions": 0,
        **values,
    }
    return JamSuccessorDevelopmentEventPrevalenceAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_prevalence_protocol(
    protocol: JamSuccessorDevelopmentEventPrevalenceProtocol,
) -> bool:
    try:
        JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate(
            protocol.model_dump()
        )
    except ValueError:
        return False
    return True


def audit_jam_successor_prevalence_result(
    result: JamSuccessorDevelopmentEventPrevalenceResult,
) -> bool:
    try:
        JamSuccessorDevelopmentEventPrevalenceResult.model_validate(
            result.model_dump()
        )
    except ValueError:
        return False
    return True


def audit_jam_successor_prevalence_audit(
    audit: JamSuccessorDevelopmentEventPrevalenceAudit,
) -> bool:
    try:
        JamSuccessorDevelopmentEventPrevalenceAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
