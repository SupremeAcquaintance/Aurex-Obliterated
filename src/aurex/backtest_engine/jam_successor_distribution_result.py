from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.jam_successor_distribution_protocol import (
    JAM_DISTRIBUTION_GATES,
    JAM_DISTRIBUTION_MONTHS,
    JAM_DISTRIBUTION_QUANTILES,
)
from aurex.backtest_engine.jam_successor_feature_specification import (
    JAM_FEATURE_IDS,
    JAM_FEATURE_QUALITY_STATES,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_DISTRIBUTION_RESULT_SCHEMA_VERSION = "aurex-jam-successor-development-distribution-result-v1"
JAM_DISTRIBUTION_AUDIT_SCHEMA_VERSION = "aurex-jam-successor-development-distribution-audit-v1"
JAM_DISTRIBUTION_PASS_DECISION = (
    "PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION"
)
JAM_DISTRIBUTION_FAIL_DECISION = "STOP_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_FAILED"
JAM_DISTRIBUTION_NEXT_AUTHORIZATION = (
    "AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS"
)
JAM_DISTRIBUTION_NO_NEXT_AUTHORIZATION = "NONE_DISTRIBUTION_FAILED"
JAM_DISTRIBUTION_CORRELATION_COUNT = len(tuple(combinations(JAM_FEATURE_IDS, 2)))


def normalize_decimal_string(value: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Jam distribution decimal is invalid") from exc
    if not parsed.is_finite():
        raise ValueError("Jam distribution decimal must be finite")
    return format(parsed, "f")


class JamDevelopmentArchiveEvidence(BaseModel):
    month: str
    archive_path: str = Field(min_length=1)
    archive_sha256: str
    source_row_count: int = Field(gt=0)
    primitive_minute_count: int = Field(gt=0, le=44_640)
    extracted_member_bytes: int = Field(gt=0, le=10_000_000_000)
    parquet_bytes: int = Field(gt=0, le=500_000_000)
    archive_pass: Literal[True] = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)


class JamDevelopmentMonthProfile(BaseModel):
    month: str
    calendar_row_count: int = Field(ge=40_320, le=44_640)
    primitive_minute_count: int = Field(ge=0, le=44_640)
    quarantine_minute_count: int = Field(ge=0, le=44_640)
    ready_row_count: int = Field(ge=0, le=44_640)
    ready_row_rate: str
    quality_state_counts: dict[str, int]

    model_config = ConfigDict(extra="forbid")

    @field_validator("ready_row_rate")
    @classmethod
    def normalize_rate(cls, value: str) -> str:
        normalized = normalize_decimal_string(value)
        if not Decimal(0) <= Decimal(normalized) <= Decimal(1):
            raise ValueError("Jam monthly ready-row rate is outside zero and one")
        return normalized

    @model_validator(mode="after")
    def validate_profile(self) -> JamDevelopmentMonthProfile:
        if (
            tuple(self.quality_state_counts) != JAM_FEATURE_QUALITY_STATES
            or any(value < 0 for value in self.quality_state_counts.values())
            or sum(self.quality_state_counts.values()) != self.calendar_row_count
            or self.quality_state_counts.get("READY", 0) != self.ready_row_count
        ):
            raise ValueError("Jam monthly quality-state counts do not reconcile")
        return self


class JamFeatureDistributionMetric(BaseModel):
    feature_id: str
    calendar_row_count: int = Field(gt=0)
    ready_value_count: int = Field(ge=0)
    null_value_count: int = Field(ge=0)
    unique_value_count: int = Field(ge=0)
    minimum: str
    maximum: str
    mean: str
    population_standard_deviation: str
    quantiles: dict[str, str]
    interquartile_range: str
    negative_value_count: int = Field(ge=0)
    zero_value_count: int = Field(ge=0)
    positive_value_count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "minimum",
        "maximum",
        "mean",
        "population_standard_deviation",
        "interquartile_range",
    )
    @classmethod
    def normalize_values(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator("quantiles")
    @classmethod
    def normalize_quantiles(cls, value: dict[str, str]) -> dict[str, str]:
        if tuple(value) != JAM_DISTRIBUTION_QUANTILES:
            raise ValueError("Jam distribution quantile matrix changed")
        return {key: normalize_decimal_string(item) for key, item in value.items()}

    @model_validator(mode="after")
    def validate_metric(self) -> JamFeatureDistributionMetric:
        if (
            self.calendar_row_count != self.ready_value_count + self.null_value_count
            or self.ready_value_count
            != (self.negative_value_count + self.zero_value_count + self.positive_value_count)
            or Decimal(self.minimum) > Decimal(self.maximum)
            or Decimal(self.population_standard_deviation) < 0
            or Decimal(self.interquartile_range) < 0
        ):
            raise ValueError("Jam feature distribution metric does not reconcile")
        quantile_values = [Decimal(self.quantiles[key]) for key in JAM_DISTRIBUTION_QUANTILES]
        if quantile_values != sorted(quantile_values):
            raise ValueError("Jam feature quantiles are not monotonic")
        expected_iqr = quantile_values[5] - quantile_values[3]
        if Decimal(self.interquartile_range) != expected_iqr:
            raise ValueError("Jam feature interquartile range changed")
        return self


class JamFeatureTailConcentration(BaseModel):
    feature_id: str
    lower_quantile: Literal["0.01"] = "0.01"
    upper_quantile: Literal["0.99"] = "0.99"
    lower_threshold: str
    upper_threshold: str
    lower_tail_count: int = Field(ge=0)
    upper_tail_count: int = Field(ge=0)
    largest_lower_tail_month: str
    largest_lower_tail_month_share: str
    largest_upper_tail_month: str
    largest_upper_tail_month_share: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "lower_threshold",
        "upper_threshold",
        "largest_lower_tail_month_share",
        "largest_upper_tail_month_share",
    )
    @classmethod
    def normalize_values(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @model_validator(mode="after")
    def validate_tail(self) -> JamFeatureTailConcentration:
        shares = (
            Decimal(self.largest_lower_tail_month_share),
            Decimal(self.largest_upper_tail_month_share),
        )
        if Decimal(self.lower_threshold) > Decimal(self.upper_threshold) or any(
            not Decimal(0) <= share <= Decimal(1) for share in shares
        ):
            raise ValueError("Jam feature tail concentration changed")
        return self


class JamFeaturePairwiseCorrelation(BaseModel):
    left_feature_id: str
    right_feature_id: str
    pearson_correlation: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("pearson_correlation")
    @classmethod
    def normalize_correlation(cls, value: str) -> str:
        normalized = normalize_decimal_string(value)
        if not Decimal(-1) <= Decimal(normalized) <= Decimal(1):
            raise ValueError("Jam feature correlation is outside minus one and one")
        return normalized

    @property
    def key(self) -> tuple[str, str]:
        return self.left_feature_id, self.right_feature_id


class JamDistributionGateResult(BaseModel):
    gate_id: str
    passed: bool
    observed: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class JamSuccessorDevelopmentDistributionResult(BaseModel):
    schema_version: Literal["aurex-jam-successor-development-distribution-result-v1"] = (
        JAM_DISTRIBUTION_RESULT_SCHEMA_VERSION
    )
    result_id: Literal["jam-successor-development-distribution-result-v1"] = (
        "jam-successor-development-distribution-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_DEVELOPMENT_DISTRIBUTIONS_NO_RETURNS"] = (
        "COMPLETE_DEVELOPMENT_DISTRIBUTIONS_NO_RETURNS"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    feature_specification_evidence_hash: str
    archive_target_manifest_hash: str
    development_quarantine_manifest_hash: str
    archive_evidence: list[JamDevelopmentArchiveEvidence] = Field(
        min_length=24,
        max_length=24,
    )
    feature_rows_path: Literal[
        "data/evidence/jam_successor_development_feature_rows_v1.parquet"
    ] = "data/evidence/jam_successor_development_feature_rows_v1.parquet"
    feature_rows_file_sha256: str
    feature_rows_bytes: int = Field(gt=0, le=2_000_000_000)
    feature_rows_schema_hash: str
    calendar_row_count: Literal[1052640] = 1_052_640
    primitive_minute_count: int = Field(gt=0, le=1_052_640)
    development_quarantine_minute_count: int = Field(ge=0, le=10_000)
    ready_row_count: int = Field(ge=0, le=1_052_640)
    ready_row_rate: str
    quality_state_counts: dict[str, int]
    monthly_profiles: list[JamDevelopmentMonthProfile] = Field(
        min_length=24,
        max_length=24,
    )
    feature_distributions: list[JamFeatureDistributionMetric] = Field(
        min_length=17,
        max_length=17,
    )
    tail_concentrations: list[JamFeatureTailConcentration] = Field(
        min_length=17,
        max_length=17,
    )
    pairwise_correlations: list[JamFeaturePairwiseCorrelation] = Field(
        min_length=JAM_DISTRIBUTION_CORRELATION_COUNT,
        max_length=JAM_DISTRIBUTION_CORRELATION_COUNT,
    )
    maximum_absolute_pairwise_correlation: str
    maximum_absolute_pair: str = Field(min_length=1)
    gates: list[JamDistributionGateResult] = Field(
        min_length=7,
        max_length=7,
    )
    passed_gate_count: int = Field(ge=0, le=7)
    failed_gate_count: int = Field(ge=0, le=7)
    decision: Literal[
        "PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_FAILED",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS",
        "NONE_DISTRIBUTION_FAILED",
    ]
    real_market_periods_opened: list[str] = Field(min_length=1, max_length=1)
    sealed_market_periods_opened: list[str] = Field(default_factory=list)
    future_labels_defined: list[str] = Field(default_factory=list)
    event_thresholds_defined: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_strategy: Literal[False] = False
    creates_signal: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=16)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "feature_specification_evidence_hash",
        "archive_target_manifest_hash",
        "development_quarantine_manifest_hash",
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "ready_row_rate",
        "maximum_absolute_pairwise_correlation",
    )
    @classmethod
    def normalize_values(cls, value: str) -> str:
        return normalize_decimal_string(value)

    @field_validator(
        "real_market_periods_opened",
        "sealed_market_periods_opened",
        "future_labels_defined",
        "event_thresholds_defined",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> JamSuccessorDevelopmentDistributionResult:
        if (
            [item.month for item in self.archive_evidence] != list(JAM_DISTRIBUTION_MONTHS)
            or [item.month for item in self.monthly_profiles] != list(JAM_DISTRIBUTION_MONTHS)
            or [item.feature_id for item in self.feature_distributions] != list(JAM_FEATURE_IDS)
            or [item.feature_id for item in self.tail_concentrations] != list(JAM_FEATURE_IDS)
            or [item.gate_id for item in self.gates] != list(JAM_DISTRIBUTION_GATES)
        ):
            raise ValueError("Jam distribution result matrix changed")
        expected_pairs = list(combinations(JAM_FEATURE_IDS, 2))
        if [item.key for item in self.pairwise_correlations] != expected_pairs:
            raise ValueError("Jam distribution correlation matrix changed")
        if (
            tuple(self.quality_state_counts) != JAM_FEATURE_QUALITY_STATES
            or any(value < 0 for value in self.quality_state_counts.values())
            or sum(self.quality_state_counts.values()) != self.calendar_row_count
            or self.quality_state_counts.get("READY", 0) != self.ready_row_count
            or sum(item.calendar_row_count for item in self.monthly_profiles)
            != self.calendar_row_count
            or sum(item.primitive_minute_count for item in self.monthly_profiles)
            != self.primitive_minute_count
            or sum(item.primitive_minute_count for item in self.archive_evidence)
            != self.primitive_minute_count
            or sum(item.quarantine_minute_count for item in self.monthly_profiles)
            != self.development_quarantine_minute_count
            or sum(item.ready_row_count for item in self.monthly_profiles) != self.ready_row_count
            or any(
                item.ready_value_count != self.ready_row_count
                or item.calendar_row_count != self.calendar_row_count
                for item in self.feature_distributions
            )
        ):
            raise ValueError("Jam distribution row totals do not reconcile")
        distributions = {item.feature_id: item for item in self.feature_distributions}
        if any(
            item.lower_threshold != distributions[item.feature_id].quantiles["0.01"]
            or item.upper_threshold != distributions[item.feature_id].quantiles["0.99"]
            or item.largest_lower_tail_month not in JAM_DISTRIBUTION_MONTHS
            or item.largest_upper_tail_month not in JAM_DISTRIBUTION_MONTHS
            or item.lower_tail_count <= 0
            or item.upper_tail_count <= 0
            for item in self.tail_concentrations
        ):
            raise ValueError("Jam distribution tail matrix changed")
        expected_rate = Decimal(self.ready_row_count) / Decimal(self.calendar_row_count)
        if Decimal(self.ready_row_rate) != expected_rate:
            raise ValueError("Jam distribution ready-row rate changed")
        passed = sum(item.passed for item in self.gates)
        if self.passed_gate_count != passed or self.failed_gate_count != len(self.gates) - passed:
            raise ValueError("Jam distribution gate totals changed")
        all_passed = passed == len(self.gates)
        if self.decision != (
            JAM_DISTRIBUTION_PASS_DECISION if all_passed else JAM_DISTRIBUTION_FAIL_DECISION
        ) or self.next_required_authorization != (
            JAM_DISTRIBUTION_NEXT_AUTHORIZATION
            if all_passed
            else JAM_DISTRIBUTION_NO_NEXT_AUTHORIZATION
        ):
            raise ValueError("Jam distribution decision changed")
        if (
            self.real_market_periods_opened != ["2019-01_THROUGH_2020-12_DEVELOPMENT"]
            or self.sealed_market_periods_opened
            or self.future_labels_defined
            or self.event_thresholds_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Jam distribution outcome boundary changed")
        maximum = max(abs(Decimal(item.pearson_correlation)) for item in self.pairwise_correlations)
        maximum_item = max(
            self.pairwise_correlations,
            key=lambda item: abs(Decimal(item.pearson_correlation)),
        )
        if Decimal(
            self.maximum_absolute_pairwise_correlation
        ) != maximum or self.maximum_absolute_pair != (
            f"{maximum_item.left_feature_id}|{maximum_item.right_feature_id}"
        ):
            raise ValueError("Jam maximum feature correlation changed")
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"result_evidence_hash"}))
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam distribution result hash does not match")
        return self


class JamSuccessorDevelopmentDistributionAudit(BaseModel):
    schema_version: Literal["aurex-jam-successor-development-distribution-audit-v1"] = (
        JAM_DISTRIBUTION_AUDIT_SCHEMA_VERSION
    )
    audited_at: datetime
    protocol_path: str
    protocol_file_sha256: str
    protocol_evidence_hash: str
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    feature_rows_path: str
    feature_rows_file_sha256: str
    feature_rows_schema_hash: str
    archive_count_reconstructed: Literal[24] = 24
    calendar_row_count_reconstructed: Literal[1052640] = 1_052_640
    feature_count_reconstructed: Literal[17] = 17
    sealed_market_periods_opened: Literal[0] = 0
    return_metrics_calculated: Literal[False] = False
    decision: Literal[
        "PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION",
        "STOP_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_FAILED",
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
        "feature_rows_file_sha256",
        "feature_rows_schema_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(
        self,
    ) -> JamSuccessorDevelopmentDistributionAudit:
        expected_hash = universe_evidence_hash(self.model_dump(exclude={"audit_evidence_hash"}))
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam distribution audit hash changed")
        return self


def build_jam_successor_distribution_result(
    **values,
) -> JamSuccessorDevelopmentDistributionResult:
    correlations = values["pairwise_correlations"]
    maximum_item = max(
        correlations,
        key=lambda item: abs(Decimal(item.pearson_correlation)),
    )
    passed = sum(item.passed for item in values["gates"])
    payload = {
        "schema_version": JAM_DISTRIBUTION_RESULT_SCHEMA_VERSION,
        "result_id": "jam-successor-development-distribution-result-v1",
        "status": "COMPLETE_DEVELOPMENT_DISTRIBUTIONS_NO_RETURNS",
        "feature_rows_path": ("data/evidence/jam_successor_development_feature_rows_v1.parquet"),
        "calendar_row_count": 1_052_640,
        "maximum_absolute_pairwise_correlation": normalize_decimal_string(
            str(abs(Decimal(maximum_item.pearson_correlation)))
        ),
        "maximum_absolute_pair": (
            f"{maximum_item.left_feature_id}|{maximum_item.right_feature_id}"
        ),
        "passed_gate_count": passed,
        "failed_gate_count": len(values["gates"]) - passed,
        "decision": (
            JAM_DISTRIBUTION_PASS_DECISION
            if passed == len(values["gates"])
            else JAM_DISTRIBUTION_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_DISTRIBUTION_NEXT_AUTHORIZATION
            if passed == len(values["gates"])
            else JAM_DISTRIBUTION_NO_NEXT_AUTHORIZATION
        ),
        "real_market_periods_opened": ["2019-01_THROUGH_2020-12_DEVELOPMENT"],
        "sealed_market_periods_opened": [],
        "future_labels_defined": [],
        "event_thresholds_defined": [],
        "return_metrics_calculated": [],
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
    return JamSuccessorDevelopmentDistributionResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_successor_distribution_audit(
    **values,
) -> JamSuccessorDevelopmentDistributionAudit:
    payload = {
        "schema_version": JAM_DISTRIBUTION_AUDIT_SCHEMA_VERSION,
        "archive_count_reconstructed": 24,
        "calendar_row_count_reconstructed": 1_052_640,
        "feature_count_reconstructed": 17,
        "sealed_market_periods_opened": 0,
        "return_metrics_calculated": False,
        **values,
    }
    return JamSuccessorDevelopmentDistributionAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_distribution_result(
    result: JamSuccessorDevelopmentDistributionResult,
) -> bool:
    try:
        JamSuccessorDevelopmentDistributionResult.model_validate(result.model_dump())
    except ValueError:
        return False
    return True


def audit_jam_successor_distribution_audit(
    audit: JamSuccessorDevelopmentDistributionAudit,
) -> bool:
    try:
        JamSuccessorDevelopmentDistributionAudit.model_validate(audit.model_dump())
    except ValueError:
        return False
    return True
