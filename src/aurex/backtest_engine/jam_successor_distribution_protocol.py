from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_DISTRIBUTION_PROTOCOL_SCHEMA_VERSION = (
    "aurex-jam-successor-development-distribution-protocol-v1"
)
JAM_DISTRIBUTION_PROTOCOL_ID = (
    "jam-successor-development-distribution-protocol-v1"
)
JAM_DISTRIBUTION_AUTHORIZATION = (
    "USER_AUTHORIZED_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS"
)
JAM_DISTRIBUTION_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in (2019, 2020)
    for month in range(1, 13)
)
JAM_DISTRIBUTION_EXPECTED_CALENDAR_ROWS = 1_052_640
JAM_DISTRIBUTION_QUANTILES = (
    "0.001",
    "0.01",
    "0.05",
    "0.25",
    "0.5",
    "0.75",
    "0.95",
    "0.99",
    "0.999",
)
JAM_DISTRIBUTION_GATES = (
    "ALL_24_ARCHIVES_MATCH_FROZEN_SHA256_AND_SOURCE_INVARIANTS",
    "CALENDAR_CONTAINS_EXACTLY_1052640_UTC_MINUTES",
    "READY_ROW_RATE_AT_LEAST_0_90",
    "EVERY_READY_ROW_HAS_ALL_17_FINITE_FEATURES",
    "EVERY_FEATURE_HAS_AT_LEAST_100_UNIQUE_READY_VALUES",
    "EVERY_FEATURE_HAS_POSITIVE_INTERQUARTILE_RANGE",
    "EVERY_MONTH_READY_ROW_RATE_AT_LEAST_0_85",
)


def development_bounds_ms() -> tuple[int, int]:
    start = datetime(2019, 1, 1, tzinfo=UTC)
    end = datetime(2021, 1, 1, tzinfo=UTC)
    return int(start.timestamp() * 1_000), int(end.timestamp() * 1_000)


class JamDevelopmentArchiveTarget(BaseModel):
    month: str = Field(pattern=r"^(2019|2020)-(0[1-9]|1[0-2])$")
    local_path: str = Field(min_length=1)
    archive_sha256: str
    archive_bytes: int = Field(gt=0, le=2_500_000_000)
    csv_member_name: str = Field(min_length=1)
    csv_member_bytes: int = Field(gt=0, le=20_000_000_000)
    source_row_count: int = Field(gt=0)
    source_minute_count: int = Field(gt=0, le=44_640)
    header_present: bool

    model_config = ConfigDict(extra="forbid")

    @field_validator("archive_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_target(self) -> JamDevelopmentArchiveTarget:
        expected_member = f"BTCUSDT-aggTrades-{self.month}.csv"
        expected_archive = f"BTCUSDT-aggTrades-{self.month}.zip"
        if (
            self.csv_member_name != expected_member
            or not self.local_path.endswith(f"/aggTrades/{expected_archive}")
        ):
            raise ValueError("Jam distribution archive target changed")
        return self


class JamSuccessorDevelopmentDistributionProtocol(BaseModel):
    schema_version: Literal[
        "aurex-jam-successor-development-distribution-protocol-v1"
    ] = JAM_DISTRIBUTION_PROTOCOL_SCHEMA_VERSION
    protocol_id: Literal[
        "jam-successor-development-distribution-protocol-v1"
    ] = JAM_DISTRIBUTION_PROTOCOL_ID
    frozen_at: datetime
    status: Literal["FROZEN_PRE_DEVELOPMENT_VALUE_ACCESS"] = (
        "FROZEN_PRE_DEVELOPMENT_VALUE_ACCESS"
    )
    authorization_record: Literal[
        "USER_AUTHORIZED_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS"
    ] = JAM_DISTRIBUTION_AUTHORIZATION
    feature_protocol_path: Literal[
        "data/evidence/jam_successor_feature_specification_protocol_v1.json"
    ] = "data/evidence/jam_successor_feature_specification_protocol_v1.json"
    feature_protocol_file_sha256: str
    feature_protocol_evidence_hash: str
    feature_specification_path: Literal[
        "data/evidence/jam_successor_feature_specification_v1.json"
    ] = "data/evidence/jam_successor_feature_specification_v1.json"
    feature_specification_file_sha256: str
    feature_specification_evidence_hash: str
    feature_audit_path: Literal[
        "data/evidence/jam_successor_feature_specification_audit_v1.json"
    ] = "data/evidence/jam_successor_feature_specification_audit_v1.json"
    feature_audit_file_sha256: str
    feature_audit_evidence_hash: str
    full_acquisition_protocol_evidence_hash: str
    full_acquisition_result_evidence_hash: str
    full_acquisition_audit_evidence_hash: str
    full_acquisition_raw_manifest_hash: str
    quality_result_evidence_hash: str
    global_quarantine_manifest_hash: str
    development_quarantine_minute_count: int = Field(ge=0, le=10_000)
    development_quarantine_manifest_hash: str
    builder_contract_hash: str
    archive_targets: list[JamDevelopmentArchiveTarget] = Field(
        min_length=24,
        max_length=24,
    )
    archive_target_manifest_hash: str
    development_start_ms: int
    development_end_exclusive_ms: int
    expected_calendar_row_count: Literal[1052640] = (
        JAM_DISTRIBUTION_EXPECTED_CALENDAR_ROWS
    )
    distribution_quantiles: tuple[str, ...] = JAM_DISTRIBUTION_QUANTILES
    structural_gates: tuple[str, ...] = JAM_DISTRIBUTION_GATES
    ready_row_rate_minimum: Literal["0.90"] = "0.90"
    monthly_ready_row_rate_minimum: Literal["0.85"] = "0.85"
    minimum_unique_values_per_feature: Literal[100] = 100
    tail_probability: Literal["0.01"] = "0.01"
    pairwise_correlation_reporting_permitted: Literal[True] = True
    tail_concentration_reporting_permitted: Literal[True] = True
    output_feature_rows_path: Literal[
        "data/evidence/jam_successor_development_feature_rows_v1.parquet"
    ] = "data/evidence/jam_successor_development_feature_rows_v1.parquet"
    processing_engine: Literal["duckdb"] = "duckdb"
    processing_engine_version: Literal["1.3.2"] = "1.3.2"
    maximum_extracted_member_bytes: Literal[10000000000] = 10_000_000_000
    maximum_output_parquet_bytes: Literal[2000000000] = 2_000_000_000
    network_access_permitted: Literal[False] = False
    development_raw_value_access_permitted: Literal[True] = True
    frozen_feature_calculation_permitted: Literal[True] = True
    distribution_calculation_permitted: Literal[True] = True
    feature_modification_permitted: Literal[False] = False
    validation_2021_access_permitted: Literal[False] = False
    holdout_2022_access_permitted: Literal[False] = False
    future_label_definition_permitted: Literal[False] = False
    event_threshold_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    outcome_access_permitted: Literal[False] = False
    strategy_creation_permitted: Literal[False] = False
    signal_creation_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_eligibility_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    limitations: list[str] = Field(min_length=16)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "feature_protocol_file_sha256",
        "feature_protocol_evidence_hash",
        "feature_specification_file_sha256",
        "feature_specification_evidence_hash",
        "feature_audit_file_sha256",
        "feature_audit_evidence_hash",
        "full_acquisition_protocol_evidence_hash",
        "full_acquisition_result_evidence_hash",
        "full_acquisition_audit_evidence_hash",
        "full_acquisition_raw_manifest_hash",
        "quality_result_evidence_hash",
        "global_quarantine_manifest_hash",
        "development_quarantine_manifest_hash",
        "builder_contract_hash",
        "archive_target_manifest_hash",
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
    ) -> JamSuccessorDevelopmentDistributionProtocol:
        start_ms, end_ms = development_bounds_ms()
        if (
            [item.month for item in self.archive_targets]
            != list(JAM_DISTRIBUTION_MONTHS)
            or self.development_start_ms != start_ms
            or self.development_end_exclusive_ms != end_ms
            or self.distribution_quantiles != JAM_DISTRIBUTION_QUANTILES
            or self.structural_gates != JAM_DISTRIBUTION_GATES
        ):
            raise ValueError("Jam distribution frozen matrix changed")
        target_payload = [item.model_dump() for item in self.archive_targets]
        if self.archive_target_manifest_hash != universe_evidence_hash(
            {"archive_targets": target_payload}
        ):
            raise ValueError("Jam distribution archive manifest changed")
        if any(
            (
                self.network_access_permitted,
                self.feature_modification_permitted,
                self.validation_2021_access_permitted,
                self.holdout_2022_access_permitted,
                self.future_label_definition_permitted,
                self.event_threshold_definition_permitted,
                self.return_calculation_permitted,
                self.outcome_access_permitted,
                self.strategy_creation_permitted,
                self.signal_creation_permitted,
                self.candidate_creation_permitted,
                self.paper_eligibility_permitted,
                self.testnet_strategy_orders_permitted,
                self.production_permitted,
                self.live_permitted,
            )
        ):
            raise ValueError("Jam distribution protocol grants forbidden authority")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected_hash:
            raise ValueError("Jam distribution protocol hash does not match")
        return self


def build_jam_successor_distribution_protocol(
    **values,
) -> JamSuccessorDevelopmentDistributionProtocol:
    targets = sorted(values.pop("archive_targets"), key=lambda item: item.month)
    start_ms, end_ms = development_bounds_ms()
    payload = {
        "schema_version": JAM_DISTRIBUTION_PROTOCOL_SCHEMA_VERSION,
        "protocol_id": JAM_DISTRIBUTION_PROTOCOL_ID,
        "status": "FROZEN_PRE_DEVELOPMENT_VALUE_ACCESS",
        "authorization_record": JAM_DISTRIBUTION_AUTHORIZATION,
        "feature_protocol_path": (
            "data/evidence/jam_successor_feature_specification_protocol_v1.json"
        ),
        "feature_specification_path": (
            "data/evidence/jam_successor_feature_specification_v1.json"
        ),
        "feature_audit_path": (
            "data/evidence/jam_successor_feature_specification_audit_v1.json"
        ),
        "archive_targets": targets,
        "archive_target_manifest_hash": universe_evidence_hash(
            {"archive_targets": [item.model_dump() for item in targets]}
        ),
        "development_start_ms": start_ms,
        "development_end_exclusive_ms": end_ms,
        "expected_calendar_row_count": (
            JAM_DISTRIBUTION_EXPECTED_CALENDAR_ROWS
        ),
        "distribution_quantiles": JAM_DISTRIBUTION_QUANTILES,
        "structural_gates": JAM_DISTRIBUTION_GATES,
        "ready_row_rate_minimum": "0.90",
        "monthly_ready_row_rate_minimum": "0.85",
        "minimum_unique_values_per_feature": 100,
        "tail_probability": "0.01",
        "pairwise_correlation_reporting_permitted": True,
        "tail_concentration_reporting_permitted": True,
        "output_feature_rows_path": (
            "data/evidence/jam_successor_development_feature_rows_v1.parquet"
        ),
        "processing_engine": "duckdb",
        "processing_engine_version": "1.3.2",
        "maximum_extracted_member_bytes": 10_000_000_000,
        "maximum_output_parquet_bytes": 2_000_000_000,
        "network_access_permitted": False,
        "development_raw_value_access_permitted": True,
        "frozen_feature_calculation_permitted": True,
        "distribution_calculation_permitted": True,
        "feature_modification_permitted": False,
        "validation_2021_access_permitted": False,
        "holdout_2022_access_permitted": False,
        "future_label_definition_permitted": False,
        "event_threshold_definition_permitted": False,
        "return_calculation_permitted": False,
        "outcome_access_permitted": False,
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
    return JamSuccessorDevelopmentDistributionProtocol(
        **payload,
        protocol_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_successor_distribution_protocol(
    protocol: JamSuccessorDevelopmentDistributionProtocol,
) -> bool:
    try:
        JamSuccessorDevelopmentDistributionProtocol.model_validate(
            protocol.model_dump()
        )
    except ValueError:
        return False
    return True
