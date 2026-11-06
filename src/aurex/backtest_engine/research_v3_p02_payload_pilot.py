from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3_P02_MONTHS,
    archive_url,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P02_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION = (
    "aurex-v3-p02-aggregate-trades-payload-pilot-protocol-v1"
)
V3_P02_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION = (
    "aurex-v3-p02-aggregate-trades-payload-pilot-result-v1"
)
V3_P02_FULL_COHORT_SYMBOLS = V2_COMPLETE_SYMBOLS[:10]
V3_P02_SAMPLE_KEYS = [
    ("AAVEUSDT", "2023-01"),
    ("BNBUSDT", "2023-12"),
    ("DOGEUSDT", "2024-12"),
]
V3_P02_EXPECTED_HEADER = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
]
V3_P02_PILOT_PASS_DECISION = (
    "PERMIT_SEPARATE_V3P02_TEN_SYMBOL_FULL_PAYLOAD_PROTOCOL"
)
V3_P02_PILOT_FAIL_DECISION = (
    "REJECT_V3P02_PAYLOAD_OR_RESOURCE_FEASIBILITY"
)


class V3P02PayloadTarget(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9]{5,20}$")
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    archive_url: str
    checksum_sha256: str
    sample_payload: bool
    full_cohort: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> V3P02PayloadTarget:
        if self.archive_url != archive_url(self.symbol, self.month):
            raise ValueError("V3P02 payload target URL changed")
        if self.sample_payload != ((self.symbol, self.month) in V3_P02_SAMPLE_KEYS):
            raise ValueError("V3P02 sample target changed")
        if self.full_cohort != (self.symbol in V3_P02_FULL_COHORT_SYMBOLS):
            raise ValueError("V3P02 full cohort target changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.month


class V3P02PayloadPilotProtocol(BaseModel):
    schema_version: Literal[
        "aurex-v3-p02-aggregate-trades-payload-pilot-protocol-v1"
    ] = V3_P02_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal["v3-p02-aggregate-trades-payload-pilot-v1"] = (
        "v3-p02-aggregate-trades-payload-pilot-v1"
    )
    protocol_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_PAYLOAD_SIZE_OR_SCHEMA_OBSERVATION"] = (
        "FROZEN_PRE_PAYLOAD_SIZE_OR_SCHEMA_OBSERVATION"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    census_contract_evidence_hash: str
    census_result_evidence_hash: str
    builder_contract_hash: str
    targets: list[V3P02PayloadTarget] = Field(min_length=744, max_length=744)
    target_manifest_hash: str
    full_cohort_symbols: list[str] = Field(min_length=10, max_length=10)
    sample_keys: list[str] = Field(min_length=3, max_length=3)
    maximum_head_http_attempts: Literal[2232] = 2232
    maximum_head_concurrency: Literal[4] = 4
    maximum_head_retries: Literal[2] = 2
    head_retry_backoff_seconds: list[int] = Field(
        default_factory=lambda: [1, 3]
    )
    request_timeout_seconds: Literal[60] = 60
    maximum_sample_payload_requests: Literal[3] = 3
    maximum_sample_payload_bytes: Literal[3_000_000_000] = 3_000_000_000
    maximum_single_sample_uncompressed_bytes: Literal[20_000_000_000] = (
        20_000_000_000
    )
    maximum_zip_expansion_ratio: Literal[100] = 100
    maximum_full_cohort_compressed_bytes: Literal[40_000_000_000] = (
        40_000_000_000
    )
    minimum_post_acquisition_free_bytes: Literal[20_000_000_000] = (
        20_000_000_000
    )
    expected_column_count: Literal[7] = 7
    expected_normalized_header: list[str] = Field(
        default_factory=lambda: V3_P02_EXPECTED_HEADER.copy()
    )
    aggregate_trade_id_column_index: Literal[0] = 0
    timestamp_column_index: Literal[5] = 5
    minimum_sample_month_coverage_fraction: Literal["0.99"] = "0.99"
    maximum_sample_event_gap_minutes: Literal[15] = 15
    maximum_sample_aggregate_trade_id_gap_count: Literal[0] = 0
    archive_payload_retention: Literal[
        "PRESERVE_THREE_CHECKSUM_VERIFIED_SAMPLE_ARCHIVES"
    ] = "PRESERVE_THREE_CHECKSUM_VERIFIED_SAMPLE_ARCHIVES"
    market_price_quantity_or_side_inspection_permitted: Literal[False] = False
    strategy_outcome_inspection_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    selection_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "census_contract_evidence_hash",
        "census_result_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "full_cohort_symbols",
        "sample_keys",
        "head_retry_backoff_seconds",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list) -> list:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_protocol(self) -> V3P02PayloadPilotProtocol:
        expected_keys = {
            (symbol, month)
            for symbol in V2_COMPLETE_SYMBOLS
            for month in V3_P02_MONTHS
        }
        if (
            self.targets != sorted(self.targets, key=lambda item: item.key)
            or {item.key for item in self.targets} != expected_keys
            or len({item.key for item in self.targets}) != 744
        ):
            raise ValueError("V3P02 payload target matrix changed")
        if self.full_cohort_symbols != sorted(V3_P02_FULL_COHORT_SYMBOLS):
            raise ValueError("V3P02 full cohort changed")
        if self.sample_keys != sorted(
            f"{symbol}/{month}" for symbol, month in V3_P02_SAMPLE_KEYS
        ):
            raise ValueError("V3P02 sample keys changed")
        if self.head_retry_backoff_seconds != [1, 3]:
            raise ValueError("V3P02 HEAD retry policy changed")
        if self.expected_normalized_header != V3_P02_EXPECTED_HEADER:
            raise ValueError("V3P02 aggregate-trade header changed")
        expected_manifest = universe_evidence_hash(
            {"targets": [item.model_dump() for item in self.targets]}
        )
        if self.target_manifest_hash != expected_manifest:
            raise ValueError("V3P02 payload manifest changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("V3P02 payload protocol hash does not match")
        return self


class V3P02ArchiveSizeObservation(BaseModel):
    symbol: str
    month: str
    archive_url: str
    observed_at: datetime
    http_status: Literal[200] = 200
    content_length_bytes: int = Field(gt=0, le=10_000_000_000)
    etag: str | None
    last_modified: str | None
    request_attempt_count: int = Field(ge=1, le=3)

    model_config = ConfigDict(extra="forbid")

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_observation(self) -> V3P02ArchiveSizeObservation:
        if self.archive_url != archive_url(self.symbol, self.month):
            raise ValueError("V3P02 HEAD observation target changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.symbol, self.month


class V3P02SamplePayloadEvidence(BaseModel):
    symbol: str
    month: str
    archive_url: str
    local_path: str
    archive_bytes: int = Field(gt=0, le=3_000_000_000)
    archive_sha256: str
    published_checksum_sha256: str
    checksum_verified: Literal[True] = True
    csv_member_name: str
    zip_compressed_bytes: int = Field(gt=0)
    zip_uncompressed_bytes: int = Field(gt=0, le=20_000_000_000)
    column_count: Literal[7] = 7
    header_present: bool
    row_count: int = Field(gt=0)
    first_timestamp_ms: int = Field(gt=0)
    last_timestamp_ms: int = Field(gt=0)
    unique_minute_count: int = Field(gt=0)
    expected_minute_count: int = Field(gt=0)
    minute_coverage_fraction: Decimal = Field(gt=0, le=1)
    maximum_event_gap_minutes: int = Field(ge=0)
    aggregate_trade_id_gap_count: int = Field(ge=0)
    duplicate_timestamp_count: int = Field(ge=0)
    payload_request_count: int = Field(ge=0, le=1)
    sample_pass: bool
    reason_codes: list[str]
    market_numeric_fields_inspected: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256", "published_checksum_sha256")
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("reason_codes", "market_numeric_fields_inspected")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_sample(self) -> V3P02SamplePayloadEvidence:
        if self.archive_url != archive_url(self.symbol, self.month):
            raise ValueError("V3P02 sample target changed")
        if (self.symbol, self.month) not in V3_P02_SAMPLE_KEYS:
            raise ValueError("V3P02 sample key is not frozen")
        expected_local_path = (
            "v3_p02_payload_pilot_v1/"
            f"{self.symbol}/{self.symbol}-aggTrades-{self.month}.zip"
        )
        if self.local_path != expected_local_path:
            raise ValueError("V3P02 sample local path changed")
        if self.csv_member_name != (
            f"{self.symbol}-aggTrades-{self.month}.csv"
        ):
            raise ValueError("V3P02 sample CSV member changed")
        if (
            self.zip_compressed_bytes > self.archive_bytes
            or self.zip_uncompressed_bytes
            > self.zip_compressed_bytes * 100
        ):
            raise ValueError("V3P02 sample ZIP resource evidence changed")
        if self.archive_sha256 != self.published_checksum_sha256:
            raise ValueError("V3P02 sample checksum does not reconcile")
        expected_fraction = Decimal(self.unique_minute_count) / Decimal(
            self.expected_minute_count
        )
        if self.minute_coverage_fraction != expected_fraction:
            raise ValueError("V3P02 sample minute coverage does not reconcile")
        reasons = []
        if self.minute_coverage_fraction < Decimal("0.99"):
            reasons.append("MINUTE_COVERAGE_BELOW_0_99")
        if self.maximum_event_gap_minutes > 15:
            reasons.append("EVENT_GAP_EXCEEDS_15_MINUTES")
        if self.aggregate_trade_id_gap_count > 0:
            reasons.append("AGGREGATE_TRADE_ID_GAP")
        if self.reason_codes != sorted(reasons) or self.sample_pass != (not reasons):
            raise ValueError("V3P02 sample decision does not reconcile")
        if self.market_numeric_fields_inspected:
            raise ValueError("V3P02 sample may inspect no market numeric fields")
        return self


class V3P02PayloadPilotSummary(BaseModel):
    head_observation_count: Literal[744] = 744
    total_head_http_attempt_count: int = Field(ge=744, le=2232)
    all_symbols_compressed_bytes: int = Field(gt=0)
    full_cohort_compressed_bytes: int = Field(gt=0)
    sample_target_compressed_bytes: int = Field(gt=0)
    sample_payload_bytes: int = Field(ge=0, le=3_000_000_000)
    sample_payload_request_count: int = Field(ge=0, le=3)
    free_disk_bytes_before_samples: int = Field(gt=0)
    projected_free_bytes_after_full_cohort: int
    sample_count: int = Field(ge=0, le=3)
    passed_sample_count: int = Field(ge=0, le=3)
    failed_sample_count: int = Field(ge=0, le=3)
    size_gate_pass: bool
    sample_size_gate_pass: bool
    free_space_gate_pass: bool
    sample_gate_pass: bool

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_summary(self) -> V3P02PayloadPilotSummary:
        if self.sample_count not in {0, 3}:
            raise ValueError("V3P02 sample count must be zero or complete")
        if (
            self.passed_sample_count + self.failed_sample_count
            != self.sample_count
        ):
            raise ValueError("V3P02 sample counts do not reconcile")
        if (
            (self.sample_payload_bytes == 0) != (self.sample_count == 0)
            or self.sample_payload_request_count > self.sample_count
        ):
            raise ValueError("V3P02 sample resource totals do not reconcile")
        if self.size_gate_pass != (
            self.full_cohort_compressed_bytes <= 40_000_000_000
        ):
            raise ValueError("V3P02 size gate does not reconcile")
        if self.sample_size_gate_pass != (
            self.sample_target_compressed_bytes <= 3_000_000_000
        ):
            raise ValueError("V3P02 sample size gate does not reconcile")
        if self.projected_free_bytes_after_full_cohort != (
            self.free_disk_bytes_before_samples
            - self.full_cohort_compressed_bytes
        ):
            raise ValueError("V3P02 projected disk space does not reconcile")
        if self.free_space_gate_pass != (
            self.projected_free_bytes_after_full_cohort >= 20_000_000_000
        ):
            raise ValueError("V3P02 free-space gate does not reconcile")
        if self.sample_gate_pass != (
            self.sample_count == 3 and self.passed_sample_count == 3
        ):
            raise ValueError("V3P02 sample gate does not reconcile")
        if (
            self.sample_count == 0
            and self.size_gate_pass
            and self.sample_size_gate_pass
            and self.free_space_gate_pass
        ):
            raise ValueError(
                "V3P02 cannot omit samples after passing resource gates"
            )
        return self


class V3P02PayloadPilotResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p02-aggregate-trades-payload-pilot-result-v1"
    ] = V3_P02_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION
    result_id: Literal["v3-p02-aggregate-trades-payload-pilot-v1"] = (
        "v3-p02-aggregate-trades-payload-pilot-v1"
    )
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal["COMPLETE_NO_RETURN_PAYLOAD_PILOT"] = (
        "COMPLETE_NO_RETURN_PAYLOAD_PILOT"
    )
    protocol_evidence_hash: str
    runner_contract_hash: str
    size_observations: list[V3P02ArchiveSizeObservation] = Field(
        min_length=744,
        max_length=744,
    )
    sample_evidence: list[V3P02SamplePayloadEvidence] = Field(
        min_length=0,
        max_length=3,
    )
    summary: V3P02PayloadPilotSummary
    decision: Literal[
        "PERMIT_SEPARATE_V3P02_TEN_SYMBOL_FULL_PAYLOAD_PROTOCOL",
        "REJECT_V3P02_PAYLOAD_OR_RESOURCE_FEASIBILITY",
    ]
    authorizes_separate_full_payload_protocol: bool
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_evidence_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "market_numeric_values_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> V3P02PayloadPilotResult:
        expected_keys = {
            (symbol, month)
            for symbol in V2_COMPLETE_SYMBOLS
            for month in V3_P02_MONTHS
        }
        if (
            self.size_observations
            != sorted(self.size_observations, key=lambda item: item.key)
            or {item.key for item in self.size_observations} != expected_keys
        ):
            raise ValueError("V3P02 size observation matrix changed")
        sample_keys = {
            (item.symbol, item.month) for item in self.sample_evidence
        }
        if self.sample_evidence != sorted(
            self.sample_evidence,
            key=lambda item: (item.symbol, item.month),
        ) or sample_keys not in (set(), set(V3_P02_SAMPLE_KEYS)):
            raise ValueError("V3P02 sample evidence is not canonical")
        passed = (
            self.summary.size_gate_pass
            and self.summary.sample_size_gate_pass
            and self.summary.free_space_gate_pass
            and self.summary.sample_gate_pass
        )
        expected_decision = (
            V3_P02_PILOT_PASS_DECISION
            if passed
            else V3_P02_PILOT_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.authorizes_separate_full_payload_protocol != passed
        ):
            raise ValueError("V3P02 pilot decision does not reconcile")
        if self.market_numeric_values_inspected or self.return_metrics_calculated:
            raise ValueError("V3P02 pilot may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P02 pilot result hash does not match")
        return self


def build_v3_p02_payload_pilot_protocol(
    **values,
) -> V3P02PayloadPilotProtocol:
    targets = sorted(values.pop("targets"), key=lambda item: item.key)
    payload = {
        "schema_version": V3_P02_PAYLOAD_PILOT_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": "v3-p02-aggregate-trades-payload-pilot-v1",
        "protocol_version": "1.0.0",
        "status": "FROZEN_PRE_PAYLOAD_SIZE_OR_SCHEMA_OBSERVATION",
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
        "full_cohort_symbols": V3_P02_FULL_COHORT_SYMBOLS,
        "sample_keys": [
            f"{symbol}/{month}" for symbol, month in V3_P02_SAMPLE_KEYS
        ],
        "maximum_head_http_attempts": 2232,
        "maximum_head_concurrency": 4,
        "maximum_head_retries": 2,
        "head_retry_backoff_seconds": [1, 3],
        "request_timeout_seconds": 60,
        "maximum_sample_payload_requests": 3,
        "maximum_sample_payload_bytes": 3_000_000_000,
        "maximum_single_sample_uncompressed_bytes": 20_000_000_000,
        "maximum_zip_expansion_ratio": 100,
        "maximum_full_cohort_compressed_bytes": 40_000_000_000,
        "minimum_post_acquisition_free_bytes": 20_000_000_000,
        "expected_column_count": 7,
        "expected_normalized_header": V3_P02_EXPECTED_HEADER,
        "aggregate_trade_id_column_index": 0,
        "timestamp_column_index": 5,
        "minimum_sample_month_coverage_fraction": "0.99",
        "maximum_sample_event_gap_minutes": 15,
        "maximum_sample_aggregate_trade_id_gap_count": 0,
        "archive_payload_retention": (
            "PRESERVE_THREE_CHECKSUM_VERIFIED_SAMPLE_ARCHIVES"
        ),
        "market_price_quantity_or_side_inspection_permitted": False,
        "strategy_outcome_inspection_permitted": False,
        "return_calculation_permitted": False,
        "selection_permitted": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P02PayloadPilotProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def build_v3_p02_payload_pilot_result(
    **values,
) -> V3P02PayloadPilotResult:
    observations = sorted(
        values.pop("size_observations"),
        key=lambda item: item.key,
    )
    samples = sorted(
        values.pop("sample_evidence"),
        key=lambda item: (item.symbol, item.month),
    )
    full_cohort = set(V3_P02_FULL_COHORT_SYMBOLS)
    sample_keys = set(V3_P02_SAMPLE_KEYS)
    full_bytes = sum(
        item.content_length_bytes
        for item in observations
        if item.symbol in full_cohort
    )
    passed_samples = sum(item.sample_pass for item in samples)
    sample_count = len(samples)
    free_disk = values.pop("free_disk_bytes_before_samples")
    summary = V3P02PayloadPilotSummary(
        total_head_http_attempt_count=sum(
            item.request_attempt_count for item in observations
        ),
        all_symbols_compressed_bytes=sum(
            item.content_length_bytes for item in observations
        ),
        full_cohort_compressed_bytes=full_bytes,
        sample_target_compressed_bytes=sum(
            item.content_length_bytes
            for item in observations
            if item.key in sample_keys
        ),
        sample_payload_bytes=sum(item.archive_bytes for item in samples),
        sample_payload_request_count=sum(
            item.payload_request_count for item in samples
        ),
        free_disk_bytes_before_samples=free_disk,
        projected_free_bytes_after_full_cohort=free_disk - full_bytes,
        sample_count=sample_count,
        passed_sample_count=passed_samples,
        failed_sample_count=sample_count - passed_samples,
        size_gate_pass=full_bytes <= 40_000_000_000,
        sample_size_gate_pass=sum(
            item.content_length_bytes
            for item in observations
            if item.key in sample_keys
        )
        <= 3_000_000_000,
        free_space_gate_pass=free_disk - full_bytes >= 20_000_000_000,
        sample_gate_pass=sample_count == 3 and passed_samples == 3,
    )
    passed = (
        summary.size_gate_pass
        and summary.sample_size_gate_pass
        and summary.free_space_gate_pass
        and summary.sample_gate_pass
    )
    payload = {
        "schema_version": V3_P02_PAYLOAD_PILOT_RESULT_SCHEMA_VERSION,
        "result_id": "v3-p02-aggregate-trades-payload-pilot-v1",
        "result_version": "1.0.0",
        "status": "COMPLETE_NO_RETURN_PAYLOAD_PILOT",
        "size_observations": observations,
        "sample_evidence": samples,
        "summary": summary,
        "decision": (
            V3_P02_PILOT_PASS_DECISION
            if passed
            else V3_P02_PILOT_FAIL_DECISION
        ),
        "authorizes_separate_full_payload_protocol": passed,
        "selects_primary": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P02PayloadPilotResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p02_payload_pilot_protocol(
    protocol: V3P02PayloadPilotProtocol,
) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_v3_p02_payload_pilot_result(
    result: V3P02PayloadPilotResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
