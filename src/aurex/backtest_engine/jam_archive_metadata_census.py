from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

JAM_ARCHIVE_CENSUS_CONTRACT_SCHEMA_VERSION = (
    "aurex-jam-archive-metadata-census-contract-v1"
)
JAM_ARCHIVE_CENSUS_CHECKPOINT_SCHEMA_VERSION = (
    "aurex-jam-archive-metadata-census-checkpoint-v1"
)
JAM_ARCHIVE_CENSUS_RESULT_SCHEMA_VERSION = (
    "aurex-jam-archive-metadata-census-result-v1"
)
JAM_ARCHIVE_CENSUS_AUDIT_SCHEMA_VERSION = (
    "aurex-jam-archive-metadata-census-audit-v1"
)
JAM_ARCHIVE_CENSUS_PASS_DECISION = (
    "PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION"
)
JAM_ARCHIVE_CENSUS_FAIL_DECISION = (
    "STOP_INCOMPLETE_JAM_ARCHIVE_METADATA_COVERAGE"
)
JAM_ARCHIVE_CENSUS_NEXT_AUTHORIZATION = (
    "AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT"
)
JAM_ARCHIVE_CENSUS_NO_NEXT_AUTHORIZATION = "NONE_CENSUS_FAILED"
JAM_ARCHIVE_CENSUS_SYMBOL = "BTCUSDT"
JAM_ARCHIVE_CENSUS_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in range(2019, 2023)
    for month in range(1, 13)
)
JAM_ARCHIVE_CENSUS_FAMILIES = ("aggTrades", "klines_1m")
JAM_ARCHIVE_CENSUS_TARGET_COUNT = 96
JAM_ARCHIVE_CENSUS_MAXIMUM_ATTEMPTS = 288


def archive_url(family: str, month: str) -> str:
    if family == "aggTrades":
        return (
            "https://data.binance.vision/data/spot/monthly/aggTrades/"
            f"{JAM_ARCHIVE_CENSUS_SYMBOL}/"
            f"{JAM_ARCHIVE_CENSUS_SYMBOL}-aggTrades-{month}.zip"
        )
    if family == "klines_1m":
        return (
            "https://data.binance.vision/data/spot/monthly/klines/"
            f"{JAM_ARCHIVE_CENSUS_SYMBOL}/1m/"
            f"{JAM_ARCHIVE_CENSUS_SYMBOL}-1m-{month}.zip"
        )
    raise ValueError(f"Unsupported Jam archive family: {family}")


class JamArchiveMetadataTarget(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    symbol: Literal["BTCUSDT"] = JAM_ARCHIVE_CENSUS_SYMBOL
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    archive_url: str = Field(min_length=60, max_length=1000)
    checksum_url: str = Field(min_length=70, max_length=1100)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_target(self) -> JamArchiveMetadataTarget:
        expected_archive = archive_url(self.family, self.month)
        expected_checksum = f"{expected_archive}.CHECKSUM"
        if (
            self.archive_url != expected_archive
            or self.checksum_url != expected_checksum
        ):
            raise ValueError("Jam archive census target changed")
        for value in (self.archive_url, self.checksum_url):
            parsed = urlparse(value)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "data.binance.vision"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.port is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "Jam archive census target must use exact Binance Vision HTTPS"
                )
        if not self.archive_url.endswith(".zip") or not self.checksum_url.endswith(
            ".zip.CHECKSUM"
        ):
            raise ValueError("Jam archive census URL suffix changed")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.family, self.month

    @property
    def archive_name(self) -> str:
        return PurePosixPath(urlparse(self.archive_url).path).name


def authoritative_targets() -> list[JamArchiveMetadataTarget]:
    return [
        JamArchiveMetadataTarget(
            family=family,
            month=month,
            archive_url=archive_url(family, month),
            checksum_url=f"{archive_url(family, month)}.CHECKSUM",
        )
        for family in JAM_ARCHIVE_CENSUS_FAMILIES
        for month in JAM_ARCHIVE_CENSUS_MONTHS
    ]


class JamArchiveMetadataCensusContract(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-metadata-census-contract-v1"
    ] = JAM_ARCHIVE_CENSUS_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["jam-archive-metadata-census-v1"] = (
        "jam-archive-metadata-census-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_METADATA_ONLY"] = (
        "FROZEN_PRE_NETWORK_METADATA_ONLY"
    )
    authorization_record: Literal[
        "USER_AUTHORIZED_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
    ] = "USER_AUTHORIZED_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
    successor_charter_path: Literal[
        "data/evidence/jam_successor_hypothesis_charter_v1.json"
    ] = "data/evidence/jam_successor_hypothesis_charter_v1.json"
    successor_charter_evidence_hash: str
    selected_proposal_id: Literal[
        "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    ] = "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
    builder_contract_hash: str
    targets: list[JamArchiveMetadataTarget] = Field(
        min_length=JAM_ARCHIVE_CENSUS_TARGET_COUNT,
        max_length=JAM_ARCHIVE_CENSUS_TARGET_COUNT,
    )
    target_manifest_hash: str
    source_domain: Literal["data.binance.vision"] = "data.binance.vision"
    source_scope: Literal[
        "spot_monthly_btcusdt_aggtrades_and_1m_klines_2019_2022"
    ] = "spot_monthly_btcusdt_aggtrades_and_1m_klines_2019_2022"
    permitted_method: Literal["GET"] = "GET"
    permitted_resource: Literal["CHECKSUM_TEXT_ONLY"] = "CHECKSUM_TEXT_ONLY"
    maximum_unique_checksum_urls: Literal[96] = 96
    maximum_http_attempts: Literal[288] = 288
    maximum_checksum_response_bytes: Literal[4096] = 4096
    maximum_total_checksum_response_bytes: Literal[393216] = 393216
    request_timeout_seconds: Literal[30] = 30
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: list[int] = Field(default_factory=lambda: [1, 3])
    maximum_concurrency: Literal[4] = 4
    permitted_http_statuses: list[int] = Field(
        default_factory=lambda: [200, 404]
    )
    redirects_permitted: Literal[False] = False
    archive_head_requests_permitted: Literal[False] = False
    archive_payload_requests_permitted: Literal[False] = False
    market_numeric_values_permitted: Literal[False] = False
    feature_calculation_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    return_calculation_permitted: Literal[False] = False
    strategy_execution_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "successor_charter_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "retry_backoff_seconds",
        "permitted_http_statuses",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list) -> list:
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_contract(self) -> JamArchiveMetadataCensusContract:
        expected_targets = authoritative_targets()
        if self.targets != expected_targets:
            raise ValueError("Jam archive census target matrix changed")
        expected_manifest_hash = universe_evidence_hash(
            {"targets": [target.model_dump() for target in expected_targets]}
        )
        if self.target_manifest_hash != expected_manifest_hash:
            raise ValueError("Jam archive census target manifest changed")
        if self.retry_backoff_seconds != [1, 3]:
            raise ValueError("Jam archive census retry policy changed")
        if self.permitted_http_statuses != [200, 404]:
            raise ValueError("Jam archive census HTTP policy changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("Jam archive census contract hash does not match")
        return self


class JamArchiveMetadataRecord(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    symbol: Literal["BTCUSDT"] = JAM_ARCHIVE_CENSUS_SYMBOL
    month: str = Field(pattern=r"^(2019|2020|2021|2022)-(0[1-9]|1[0-2])$")
    archive_url: str
    checksum_url: str
    final_url: str
    checked_at: datetime
    http_status: Literal[200, 404]
    checksum_response_bytes: int = Field(ge=0, le=4096)
    checksum_text: str | None = Field(default=None, max_length=1100)
    checksum_response_sha256: str | None
    published_archive_sha256: str | None
    availability: Literal["PRESENT", "MISSING"]
    request_attempt_count: int = Field(ge=1, le=3)
    redirect_count: Literal[0] = 0

    model_config = ConfigDict(extra="forbid")

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "checksum_response_sha256",
        "published_archive_sha256",
    )
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return normalize_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_record(self) -> JamArchiveMetadataRecord:
        target = JamArchiveMetadataTarget(
            family=self.family,
            symbol=self.symbol,
            month=self.month,
            archive_url=self.archive_url,
            checksum_url=self.checksum_url,
        )
        if self.final_url != self.checksum_url:
            raise ValueError("Jam archive census followed or received a redirect")
        present = self.http_status == 200
        optional_values = (
            self.checksum_text,
            self.checksum_response_sha256,
            self.published_archive_sha256,
        )
        if (
            self.availability != ("PRESENT" if present else "MISSING")
            or (self.checksum_response_bytes > 0) != present
            or any(value is None for value in optional_values) == present
        ):
            raise ValueError("Jam archive census availability does not reconcile")
        if present:
            assert self.checksum_text is not None
            assert self.checksum_response_sha256 is not None
            assert self.published_archive_sha256 is not None
            encoded = self.checksum_text.encode("utf-8")
            if len(encoded) != self.checksum_response_bytes:
                raise ValueError("Jam checksum byte count does not reconcile")
            if hashlib.sha256(encoded).hexdigest() != self.checksum_response_sha256:
                raise ValueError("Jam checksum response hash does not reconcile")
            checksum_match = re.fullmatch(
                r"([0-9a-fA-F]{64})(?: {2}|\s+\*)([^\s/\\]+)",
                self.checksum_text.strip(),
            )
            if (
                checksum_match is None
                or checksum_match.group(1).lower()
                != self.published_archive_sha256
                or checksum_match.group(2) != target.archive_name
            ):
                raise ValueError("Jam checksum text identity does not reconcile")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.family, self.month


class JamArchiveMetadataCheckpoint(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-metadata-census-checkpoint-v1"
    ] = JAM_ARCHIVE_CENSUS_CHECKPOINT_SCHEMA_VERSION
    updated_at: datetime
    contract_evidence_hash: str
    target_manifest_hash: str
    runner_contract_hash: str
    records: list[JamArchiveMetadataRecord] = Field(max_length=96)
    archive_payload_requests_made: Literal[0] = 0
    archive_payload_bytes_received: Literal[0] = 0
    checkpoint_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("updated_at")
    @classmethod
    def normalize_updated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "target_manifest_hash",
        "runner_contract_hash",
        "checkpoint_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_checkpoint(self) -> JamArchiveMetadataCheckpoint:
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("Jam archive checkpoint records are not canonical")
        expected_keys = {target.key for target in authoritative_targets()}
        record_keys = {record.key for record in self.records}
        if len(record_keys) != len(self.records) or not record_keys <= expected_keys:
            raise ValueError("Jam archive checkpoint target set changed")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"checkpoint_evidence_hash"})
        )
        if self.checkpoint_evidence_hash != expected_hash:
            raise ValueError("Jam archive checkpoint hash does not match")
        return self


class JamArchiveFamilySummary(BaseModel):
    family: Literal["aggTrades", "klines_1m"]
    target_count: Literal[48] = 48
    present_count: int = Field(ge=0, le=48)
    missing_count: int = Field(ge=0, le=48)
    complete: bool

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_summary(self) -> JamArchiveFamilySummary:
        if (
            self.present_count + self.missing_count != 48
            or self.complete != (self.present_count == 48)
        ):
            raise ValueError("Jam archive family summary does not reconcile")
        return self


class JamArchiveMetadataSummary(BaseModel):
    target_count: Literal[96] = 96
    observed_count: Literal[96] = 96
    present_count: int = Field(ge=0, le=96)
    missing_count: int = Field(ge=0, le=96)
    checksum_http_attempt_count: int = Field(ge=96, le=288)
    checksum_response_bytes: int = Field(ge=0, le=393216)
    family_summaries: list[JamArchiveFamilySummary] = Field(
        min_length=2,
        max_length=2,
    )
    complete: bool

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_summary(self) -> JamArchiveMetadataSummary:
        if (
            self.present_count + self.missing_count != 96
            or [item.family for item in self.family_summaries]
            != list(JAM_ARCHIVE_CENSUS_FAMILIES)
            or self.complete != (self.present_count == 96)
        ):
            raise ValueError("Jam archive census summary does not reconcile")
        return self


class JamArchiveMetadataCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-metadata-census-result-v1"
    ] = JAM_ARCHIVE_CENSUS_RESULT_SCHEMA_VERSION
    result_id: Literal["jam-archive-metadata-census-result-v1"] = (
        "jam-archive-metadata-census-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_METADATA_ONLY_NO_MARKET_PAYLOAD"] = (
        "COMPLETE_METADATA_ONLY_NO_MARKET_PAYLOAD"
    )
    contract_evidence_hash: str
    target_manifest_hash: str
    runner_contract_hash: str
    records: list[JamArchiveMetadataRecord] = Field(
        min_length=96,
        max_length=96,
    )
    summary: JamArchiveMetadataSummary
    decision: Literal[
        "PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION",
        "STOP_INCOMPLETE_JAM_ARCHIVE_METADATA_COVERAGE",
    ]
    next_required_authorization: Literal[
        "AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT",
        "NONE_CENSUS_FAILED",
    ]
    archive_head_requests_made: Literal[0] = 0
    archive_payload_requests_made: Literal[0] = 0
    archive_payload_bytes_received: Literal[0] = 0
    redirects_followed: Literal[0] = 0
    market_numeric_values_inspected: list[str] = Field(default_factory=list)
    features_calculated: list[str] = Field(default_factory=list)
    parameters_defined: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    strategy_executions: Literal[0] = 0
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_order_authority: Literal[False] = False
    creates_production_authority: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: list[str] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_evidence_hash",
        "target_manifest_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "market_numeric_values_inspected",
        "features_calculated",
        "parameters_defined",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_result(self) -> JamArchiveMetadataCensusResult:
        if self.records != sorted(self.records, key=lambda item: item.key):
            raise ValueError("Jam archive census records are not canonical")
        expected_keys = {target.key for target in authoritative_targets()}
        if (
            len({record.key for record in self.records}) != 96
            or {record.key for record in self.records} != expected_keys
        ):
            raise ValueError("Jam archive census result matrix changed")
        expected_summary = summarize_records(self.records)
        if self.summary != expected_summary:
            raise ValueError("Jam archive census summary does not match records")
        passed = expected_summary.complete
        if (
            self.decision
            != (
                JAM_ARCHIVE_CENSUS_PASS_DECISION
                if passed
                else JAM_ARCHIVE_CENSUS_FAIL_DECISION
            )
            or self.next_required_authorization
            != (
                JAM_ARCHIVE_CENSUS_NEXT_AUTHORIZATION
                if passed
                else JAM_ARCHIVE_CENSUS_NO_NEXT_AUTHORIZATION
            )
        ):
            raise ValueError("Jam archive census decision does not reconcile")
        if any(
            (
                self.market_numeric_values_inspected,
                self.features_calculated,
                self.parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("Jam archive metadata census may contain no outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Jam archive census result hash does not match")
        return self


class JamArchiveMetadataCensusAudit(BaseModel):
    schema_version: Literal[
        "aurex-jam-archive-metadata-census-audit-v1"
    ] = JAM_ARCHIVE_CENSUS_AUDIT_SCHEMA_VERSION
    audited_at: datetime
    result_path: str
    result_file_sha256: str
    result_evidence_hash: str
    contract_evidence_hash: str
    target_manifest_hash: str
    record_count: Literal[96] = 96
    unique_checksum_url_count: Literal[96] = 96
    checksum_get_attempt_count: int = Field(ge=96, le=288)
    checksum_response_bytes: int = Field(ge=0, le=393216)
    archive_head_requests_made: Literal[0] = 0
    archive_payload_requests_made: Literal[0] = 0
    archive_payload_bytes_received: Literal[0] = 0
    redirects_followed: Literal[0] = 0
    market_numeric_values_inspected: Literal[False] = False
    coverage_complete: bool
    decision: Literal[
        "PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION",
        "STOP_INCOMPLETE_JAM_ARCHIVE_METADATA_COVERAGE",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "result_file_sha256",
        "result_evidence_hash",
        "contract_evidence_hash",
        "target_manifest_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> JamArchiveMetadataCensusAudit:
        expected_decision = (
            JAM_ARCHIVE_CENSUS_PASS_DECISION
            if self.coverage_complete
            else JAM_ARCHIVE_CENSUS_FAIL_DECISION
        )
        if self.decision != expected_decision:
            raise ValueError("Jam archive census audit decision does not reconcile")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected_hash:
            raise ValueError("Jam archive census audit hash does not match")
        return self


def summarize_records(
    records: list[JamArchiveMetadataRecord],
) -> JamArchiveMetadataSummary:
    present = sum(record.availability == "PRESENT" for record in records)
    family_summaries = []
    for family in JAM_ARCHIVE_CENSUS_FAMILIES:
        family_records = [record for record in records if record.family == family]
        family_present = sum(
            record.availability == "PRESENT" for record in family_records
        )
        family_summaries.append(
            JamArchiveFamilySummary(
                family=family,
                present_count=family_present,
                missing_count=48 - family_present,
                complete=family_present == 48,
            )
        )
    return JamArchiveMetadataSummary(
        present_count=present,
        missing_count=96 - present,
        checksum_http_attempt_count=sum(
            record.request_attempt_count for record in records
        ),
        checksum_response_bytes=sum(
            record.checksum_response_bytes for record in records
        ),
        family_summaries=family_summaries,
        complete=present == 96,
    )


def build_jam_archive_census_contract(
    **values,
) -> JamArchiveMetadataCensusContract:
    targets = authoritative_targets()
    payload = {
        "schema_version": JAM_ARCHIVE_CENSUS_CONTRACT_SCHEMA_VERSION,
        "contract_id": "jam-archive-metadata-census-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_NETWORK_METADATA_ONLY",
        "authorization_record": (
            "USER_AUTHORIZED_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS"
        ),
        "successor_charter_path": (
            "data/evidence/jam_successor_hypothesis_charter_v1.json"
        ),
        "selected_proposal_id": (
            "J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM"
        ),
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [target.model_dump() for target in targets]}
        ),
        "source_domain": "data.binance.vision",
        "source_scope": (
            "spot_monthly_btcusdt_aggtrades_and_1m_klines_2019_2022"
        ),
        "permitted_method": "GET",
        "permitted_resource": "CHECKSUM_TEXT_ONLY",
        "maximum_unique_checksum_urls": 96,
        "maximum_http_attempts": 288,
        "maximum_checksum_response_bytes": 4096,
        "maximum_total_checksum_response_bytes": 393216,
        "request_timeout_seconds": 30,
        "maximum_retries": 2,
        "retry_backoff_seconds": [1, 3],
        "maximum_concurrency": 4,
        "permitted_http_statuses": [200, 404],
        "redirects_permitted": False,
        "archive_head_requests_permitted": False,
        "archive_payload_requests_permitted": False,
        "market_numeric_values_permitted": False,
        "feature_calculation_permitted": False,
        "parameter_definition_permitted": False,
        "return_calculation_permitted": False,
        "strategy_execution_permitted": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamArchiveMetadataCensusContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_archive_checkpoint(
    **values,
) -> JamArchiveMetadataCheckpoint:
    records = sorted(values.pop("records"), key=lambda item: item.key)
    payload = {
        "schema_version": JAM_ARCHIVE_CENSUS_CHECKPOINT_SCHEMA_VERSION,
        "records": records,
        "archive_payload_requests_made": 0,
        "archive_payload_bytes_received": 0,
        **values,
    }
    return JamArchiveMetadataCheckpoint(
        **payload,
        checkpoint_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_archive_census_result(
    **values,
) -> JamArchiveMetadataCensusResult:
    records = sorted(values.pop("records"), key=lambda item: item.key)
    summary = summarize_records(records)
    passed = summary.complete
    payload = {
        "schema_version": JAM_ARCHIVE_CENSUS_RESULT_SCHEMA_VERSION,
        "result_id": "jam-archive-metadata-census-result-v1",
        "status": "COMPLETE_METADATA_ONLY_NO_MARKET_PAYLOAD",
        "records": records,
        "summary": summary,
        "decision": (
            JAM_ARCHIVE_CENSUS_PASS_DECISION
            if passed
            else JAM_ARCHIVE_CENSUS_FAIL_DECISION
        ),
        "next_required_authorization": (
            JAM_ARCHIVE_CENSUS_NEXT_AUTHORIZATION
            if passed
            else JAM_ARCHIVE_CENSUS_NO_NEXT_AUTHORIZATION
        ),
        "archive_head_requests_made": 0,
        "archive_payload_requests_made": 0,
        "archive_payload_bytes_received": 0,
        "redirects_followed": 0,
        "market_numeric_values_inspected": [],
        "features_calculated": [],
        "parameters_defined": [],
        "return_metrics_calculated": [],
        "strategy_executions": 0,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "creates_testnet_order_authority": False,
        "creates_production_authority": False,
        "creates_live_eligibility": False,
        **values,
    }
    payload["limitations"] = sorted(set(payload["limitations"]))
    return JamArchiveMetadataCensusResult(
        **payload,
        result_evidence_hash=universe_evidence_hash(payload),
    )


def build_jam_archive_census_audit(
    **values,
) -> JamArchiveMetadataCensusAudit:
    payload = {
        "schema_version": JAM_ARCHIVE_CENSUS_AUDIT_SCHEMA_VERSION,
        "record_count": 96,
        "unique_checksum_url_count": 96,
        "archive_head_requests_made": 0,
        "archive_payload_requests_made": 0,
        "archive_payload_bytes_received": 0,
        "redirects_followed": 0,
        "market_numeric_values_inspected": False,
        **values,
    }
    return JamArchiveMetadataCensusAudit(
        **payload,
        audit_evidence_hash=universe_evidence_hash(payload),
    )


def audit_jam_archive_census_contract(
    contract: JamArchiveMetadataCensusContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )


def audit_jam_archive_checkpoint(
    checkpoint: JamArchiveMetadataCheckpoint,
) -> bool:
    return checkpoint.checkpoint_evidence_hash == universe_evidence_hash(
        checkpoint.model_dump(exclude={"checkpoint_evidence_hash"})
    )


def audit_jam_archive_census_result(
    result: JamArchiveMetadataCensusResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_jam_archive_census_audit(
    audit: JamArchiveMetadataCensusAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
