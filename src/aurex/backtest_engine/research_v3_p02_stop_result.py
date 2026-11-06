from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3P02SamplePayloadEvidence,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V3_P02_STOP_SCHEMA_VERSION = (
    "aurex-v3-p02-payload-pilot-transport-stop-result-v1"
)
V3_P02_STOP_DECISION = (
    "STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION"
)
V3_P02_VERIFIED_SAMPLE_KEYS = {
    ("AAVEUSDT", "2023-01"),
    ("BNBUSDT", "2023-12"),
}
V3_P02_FAILED_SAMPLE_KEY = ("DOGEUSDT", "2024-12")


class V3P02FailedSampleRequestEvidence(BaseModel):
    symbol: Literal["DOGEUSDT"] = "DOGEUSDT"
    month: Literal["2024-12"] = "2024-12"
    archive_url: str
    request_marker_local_path: Literal[
        "v3_p02_payload_pilot_v1/DOGEUSDT/"
        "DOGEUSDT-aggTrades-2024-12.zip.request.json"
    ]
    request_marker_sha256: str
    requested_at: datetime
    request_attempt_count: Literal[1] = 1
    failure_code: Literal[
        "TRUNCATED_RESPONSE_BEFORE_DECLARED_CONTENT_LENGTH"
    ] = "TRUNCATED_RESPONSE_BEFORE_DECLARED_CONTENT_LENGTH"
    failure_message: Literal[
        "V3P02 sample size differs from HEAD observation"
    ] = "V3P02 sample size differs from HEAD observation"
    partial_archive_retained: Literal[False] = False
    partial_archive_byte_count_available: Literal[False] = False
    expected_content_length_preserved: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("request_marker_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_failed_request(
        self,
    ) -> V3P02FailedSampleRequestEvidence:
        expected_url = (
            "https://data.binance.vision/data/futures/um/monthly/aggTrades/"
            "DOGEUSDT/DOGEUSDT-aggTrades-2024-12.zip"
        )
        if self.archive_url != expected_url:
            raise ValueError("V3P02 failed sample URL changed")
        return self


class V3P02PayloadPilotStopResult(BaseModel):
    schema_version: Literal[
        "aurex-v3-p02-payload-pilot-transport-stop-result-v1"
    ] = V3_P02_STOP_SCHEMA_VERSION
    result_id: Literal[
        "v3-p02-payload-pilot-transport-stop-v1"
    ] = "v3-p02-payload-pilot-transport-stop-v1"
    result_version: Literal["1.0.0"] = "1.0.0"
    generated_at: datetime
    status: Literal[
        "STOPPED_WITHOUT_AUTHORITATIVE_PAYLOAD_PILOT_RESULT"
    ] = "STOPPED_WITHOUT_AUTHORITATIVE_PAYLOAD_PILOT_RESULT"
    payload_pilot_protocol_evidence_hash: str
    failed_runner_contract_hash: str
    finalizer_contract_hash: str
    head_matrix_completed_before_failure: Literal[True] = True
    head_observation_count: Literal[744] = 744
    exact_head_attempt_count_preserved: Literal[False] = False
    head_attempt_count_lower_bound: Literal[744] = 744
    head_attempt_count_upper_bound: Literal[2232] = 2232
    head_observation_records_preserved: Literal[False] = False
    reported_cohort_size_gate_pass: Literal[True] = True
    reported_sample_size_gate_pass: Literal[True] = True
    reported_free_space_gate_pass: Literal[True] = True
    verified_samples: list[V3P02SamplePayloadEvidence] = Field(
        min_length=2,
        max_length=2,
    )
    failed_sample: V3P02FailedSampleRequestEvidence
    sample_request_marker_count: Literal[3] = 3
    verified_sample_count: Literal[2] = 2
    failed_sample_count: Literal[1] = 1
    authoritative_payload_pilot_result_created: Literal[False] = False
    decision: Literal[
        "STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION"
    ] = V3_P02_STOP_DECISION
    authorizes_retry: Literal[False] = False
    authorizes_full_payload_protocol: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=7)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "payload_pilot_protocol_evidence_hash",
        "failed_runner_contract_hash",
        "finalizer_contract_hash",
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
    def validate_result(self) -> V3P02PayloadPilotStopResult:
        if self.verified_samples != sorted(
            self.verified_samples,
            key=lambda item: (item.symbol, item.month),
        ):
            raise ValueError("V3P02 verified stop samples are not canonical")
        if {
            (item.symbol, item.month) for item in self.verified_samples
        } != V3_P02_VERIFIED_SAMPLE_KEYS:
            raise ValueError("V3P02 verified stop sample set changed")
        if not all(item.sample_pass for item in self.verified_samples):
            raise ValueError("V3P02 preserved verified sample did not pass")
        if (
            self.failed_sample.symbol,
            self.failed_sample.month,
        ) != V3_P02_FAILED_SAMPLE_KEY:
            raise ValueError("V3P02 failed stop sample changed")
        if self.market_numeric_values_inspected or self.return_metrics_calculated:
            raise ValueError("V3P02 stop result may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("V3P02 stop result hash does not match")
        return self


def build_v3_p02_payload_pilot_stop_result(
    **values,
) -> V3P02PayloadPilotStopResult:
    samples = sorted(
        values.pop("verified_samples"),
        key=lambda item: (item.symbol, item.month),
    )
    payload = {
        "schema_version": V3_P02_STOP_SCHEMA_VERSION,
        "result_id": "v3-p02-payload-pilot-transport-stop-v1",
        "result_version": "1.0.0",
        "status": "STOPPED_WITHOUT_AUTHORITATIVE_PAYLOAD_PILOT_RESULT",
        "head_matrix_completed_before_failure": True,
        "head_observation_count": 744,
        "exact_head_attempt_count_preserved": False,
        "head_attempt_count_lower_bound": 744,
        "head_attempt_count_upper_bound": 2232,
        "head_observation_records_preserved": False,
        "reported_cohort_size_gate_pass": True,
        "reported_sample_size_gate_pass": True,
        "reported_free_space_gate_pass": True,
        "verified_samples": samples,
        "sample_request_marker_count": 3,
        "verified_sample_count": 2,
        "failed_sample_count": 1,
        "authoritative_payload_pilot_result_created": False,
        "decision": V3_P02_STOP_DECISION,
        "authorizes_retry": False,
        "authorizes_full_payload_protocol": False,
        "selects_primary": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_live_eligibility": False,
        "market_numeric_values_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return V3P02PayloadPilotStopResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v3_p02_payload_pilot_stop_result(
    result: V3P02PayloadPilotStopResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )
