from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v2_source_census import parse_v2_checksum_text
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

RAW_TRADES_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in range(2020, 2026)
    for month in range(1, 13)
)
RAW_TRADES_TARGET_COUNT = 72
RAW_TRADES_PASS_DECISION = (
    "PERMIT_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL"
)
RAW_TRADES_FAIL_DECISION = "STOP_Q1_USDM_RAW_TRADES_METADATA_CENSUS_INCOMPLETE"
RAW_TRADES_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL"
)
RAW_TRADES_FAIL_AUTHORIZATION = "NONE_RAW_TRADES_METADATA_CENSUS_FAILED"
OFFICIAL_ARCHIVE_REFERENCE = "https://github.com/binance/binance-public-data"
OFFICIAL_API_REFERENCE = (
    "https://developers.binance.com/en/docs/derivatives/"
    "usds-margined-futures/market-data/rest-api/Recent-Trades-List"
)


def raw_trades_archive_url(month: str) -> str:
    return (
        "https://data.binance.vision/data/futures/um/monthly/trades/"
        f"BTCUSDT/BTCUSDT-trades-{month}.zip"
    )


class RawTradesMetadataTarget(BaseModel):
    product: Literal["USD_M_PERPETUAL"] = "USD_M_PERPETUAL"
    family: Literal["trades"] = "trades"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    partition_role: Literal["DEVELOPMENT", "VALIDATION_METADATA"]
    expected_timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    archive_url: str
    checksum_url: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_target(self) -> RawTradesMetadataTarget:
        expected_role = (
            "DEVELOPMENT" if self.month < "2024-01" else "VALIDATION_METADATA"
        )
        expected_archive = raw_trades_archive_url(self.month)
        if (
            self.month not in RAW_TRADES_MONTHS
            or self.partition_role != expected_role
            or self.archive_url != expected_archive
            or self.checksum_url != f"{expected_archive}.CHECKSUM"
        ):
            raise ValueError("Q1 raw-trades metadata target changed")
        parsed = urlparse(self.checksum_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "data.binance.vision"
            or not parsed.path.endswith(".zip.CHECKSUM")
            or "/futures/um/monthly/trades/BTCUSDT/" not in parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Q1 raw-trades target must be an official checksum URL")
        return self


def authoritative_raw_trades_targets() -> tuple[RawTradesMetadataTarget, ...]:
    return tuple(
        RawTradesMetadataTarget(
            month=month,
            partition_role=(
                "DEVELOPMENT" if month < "2024-01" else "VALIDATION_METADATA"
            ),
            archive_url=raw_trades_archive_url(month),
            checksum_url=f"{raw_trades_archive_url(month)}.CHECKSUM",
        )
        for month in RAW_TRADES_MONTHS
    )


class RawTradesMetadataCensusProtocol(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-metadata-census-protocol-v1"
    ] = "aurex-q1-usdm-raw-trades-metadata-census-protocol-v1"
    protocol_id: Literal["q1-usdm-raw-trades-metadata-census-v1"] = (
        "q1-usdm-raw-trades-metadata-census-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_CHECKSUM_ONLY"] = (
        "FROZEN_PRE_NETWORK_CHECKSUM_ONLY"
    )
    parent_result_file_sha256: str
    parent_result_evidence_hash: str
    parent_audit_file_sha256: str
    parent_audit_evidence_hash: str
    readiness_result_evidence_hash: str
    readiness_audit_evidence_hash: str
    builder_contract_hash: str
    official_archive_reference: Literal[
        "https://github.com/binance/binance-public-data"
    ] = OFFICIAL_ARCHIVE_REFERENCE
    official_api_reference: str = OFFICIAL_API_REFERENCE
    source_semantics: tuple[str, ...]
    targets: tuple[RawTradesMetadataTarget, ...] = Field(
        min_length=RAW_TRADES_TARGET_COUNT,
        max_length=RAW_TRADES_TARGET_COUNT,
    )
    target_manifest_hash: str
    maximum_unique_checksum_urls: Literal[72] = 72
    maximum_http_attempts: Literal[216] = 216
    maximum_checksum_response_bytes: Literal[512] = 512
    request_timeout_seconds: Literal[30] = 30
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    maximum_concurrency: Literal[4] = 4
    required_present_target_count: Literal[72] = 72
    required_development_target_count: Literal[48] = 48
    required_validation_metadata_target_count: Literal[24] = 24
    permitted_http_statuses: tuple[Literal[200], Literal[404]] = (200, 404)
    checksum_get_requests_permitted: Literal[True] = True
    archive_head_requests_permitted: Literal[False] = False
    archive_payload_requests_permitted: Literal[False] = False
    market_numeric_values_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    strategy_outcomes_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    candidate_creation_permitted: Literal[False] = False
    paper_operation_permitted: Literal[False] = False
    testnet_strategy_orders_permitted: Literal[False] = False
    production_permitted: Literal[False] = False
    live_permitted: Literal[False] = False
    pass_decision: Literal[
        "PERMIT_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL"
    ] = RAW_TRADES_PASS_DECISION
    fail_decision: Literal[
        "STOP_Q1_USDM_RAW_TRADES_METADATA_CENSUS_INCOMPLETE"
    ] = RAW_TRADES_FAIL_DECISION
    limitations: tuple[str, ...] = Field(min_length=8)
    protocol_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_result_file_sha256",
        "parent_result_evidence_hash",
        "parent_audit_file_sha256",
        "parent_audit_evidence_hash",
        "readiness_result_evidence_hash",
        "readiness_audit_evidence_hash",
        "builder_contract_hash",
        "target_manifest_hash",
        "protocol_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_protocol(self) -> RawTradesMetadataCensusProtocol:
        targets = authoritative_raw_trades_targets()
        if (
            self.targets != targets
            or self.target_manifest_hash
            != universe_evidence_hash(
                {"targets": [item.model_dump() for item in targets]}
            )
            or self.source_semantics
            != (
                "ARCHIVE_FAMILY_USDM_MONTHLY_RAW_TRADES",
                "MARKET_TRADES_ONLY_EXCLUDING_INSURANCE_FUND_AND_ADL",
                "PRICE_QUANTITY_AND_QUOTE_QUANTITY_FORBIDDEN_IN_THIS_STAGE",
            )
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 raw-trades census protocol scope changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"protocol_evidence_hash"})
        )
        if self.protocol_evidence_hash != expected:
            raise ValueError("Q1 raw-trades census protocol hash changed")
        return self


class RawTradesMetadataProtocolAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-metadata-protocol-audit-v1"
    ] = "aurex-q1-usdm-raw-trades-metadata-protocol-audit-v1"
    audit_id: Literal["q1-usdm-raw-trades-metadata-protocol-audit-v1"] = (
        "q1-usdm-raw-trades-metadata-protocol-audit-v1"
    )
    audited_at: datetime
    protocol_file_sha256: str
    protocol_evidence_hash: str
    builder_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    target_count: Literal[72] = 72
    unique_checksum_url_count: Literal[72] = 72
    development_target_count: Literal[48] = 48
    validation_metadata_target_count: Literal[24] = 24
    network_requests_made: Literal[0] = 0
    archive_payload_requests_made: Literal[0] = 0
    market_numeric_field_count: Literal[0] = 0
    authorizes_checksum_census: Literal[True] = True
    authorizes_payload: Literal[False] = False
    authorizes_outcomes: Literal[False] = False
    authorizes_trading: Literal[False] = False
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "builder_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> RawTradesMetadataProtocolAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 raw-trades protocol audit hash changed")
        return self


class RawTradesMetadataRecord(BaseModel):
    product: Literal["USD_M_PERPETUAL"] = "USD_M_PERPETUAL"
    family: Literal["trades"] = "trades"
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str
    partition_role: Literal["DEVELOPMENT", "VALIDATION_METADATA"]
    expected_timestamp_unit: Literal["MILLISECONDS"] = "MILLISECONDS"
    archive_url: str
    checksum_url: str
    checked_at: datetime
    http_status: Literal[200, 404]
    checksum_response_bytes: int = Field(ge=0, le=512)
    checksum_text: str | None = Field(default=None, max_length=512)
    checksum_text_sha256: str | None = None
    archive_sha256: str | None = None
    availability: Literal["PRESENT", "MISSING"]
    request_attempt_count: int = Field(ge=1, le=3)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("checked_at")
    @classmethod
    def normalize_checked_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator("checksum_text_sha256", "archive_sha256")
    @classmethod
    def normalize_optional_hash(cls, value: str | None) -> str | None:
        return None if value is None else normalize_sha256(value)

    @model_validator(mode="after")
    def validate_record(self) -> RawTradesMetadataRecord:
        target = RawTradesMetadataTarget(
            month=self.month,
            partition_role=self.partition_role,
            archive_url=self.archive_url,
            checksum_url=self.checksum_url,
        )
        present = self.http_status == 200
        fields_present = (
            self.checksum_text is not None
            and self.checksum_text_sha256 is not None
            and self.archive_sha256 is not None
            and self.checksum_response_bytes > 0
        )
        if (
            self.availability != ("PRESENT" if present else "MISSING")
            or fields_present != present
        ):
            raise ValueError("Q1 raw-trades checksum availability does not reconcile")
        if present:
            assert self.checksum_text is not None
            assert self.checksum_text_sha256 is not None
            assert self.archive_sha256 is not None
            archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
            if (
                self.checksum_text_sha256
                != sha256(self.checksum_text.encode("utf-8")).hexdigest()
                or self.archive_sha256
                != parse_v2_checksum_text(self.checksum_text, archive_name)
            ):
                raise ValueError("Q1 raw-trades checksum reconstruction changed")
        elif any(
            (
                self.checksum_response_bytes,
                self.checksum_text,
                self.checksum_text_sha256,
                self.archive_sha256,
            )
        ):
            raise ValueError("Q1 missing raw-trades target contains checksum evidence")
        return self


class RawTradesMetadataSummary(BaseModel):
    target_count: Literal[72] = 72
    observed_count: Literal[72] = 72
    present_count: int = Field(ge=0, le=72)
    missing_count: int = Field(ge=0, le=72)
    development_present_count: int = Field(ge=0, le=48)
    validation_metadata_present_count: int = Field(ge=0, le=24)
    http_attempt_count: int = Field(ge=72, le=216)
    missing_months: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_summary(self) -> RawTradesMetadataSummary:
        if (
            self.present_count + self.missing_count != 72
            or self.present_count
            != self.development_present_count
            + self.validation_metadata_present_count
            or self.missing_count != len(self.missing_months)
        ):
            raise ValueError("Q1 raw-trades metadata summary does not reconcile")
        return self


def summarize_raw_trades_records(
    records: tuple[RawTradesMetadataRecord, ...],
) -> RawTradesMetadataSummary:
    present = tuple(item for item in records if item.availability == "PRESENT")
    return RawTradesMetadataSummary(
        present_count=len(present),
        missing_count=72 - len(present),
        development_present_count=sum(
            item.partition_role == "DEVELOPMENT" for item in present
        ),
        validation_metadata_present_count=sum(
            item.partition_role == "VALIDATION_METADATA" for item in present
        ),
        http_attempt_count=sum(item.request_attempt_count for item in records),
        missing_months=tuple(
            item.month for item in records if item.availability == "MISSING"
        ),
    )


class RawTradesMetadataCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-metadata-census-result-v1"
    ] = "aurex-q1-usdm-raw-trades-metadata-census-result-v1"
    result_id: Literal["q1-usdm-raw-trades-metadata-census-result-v1"] = (
        "q1-usdm-raw-trades-metadata-census-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_CHECKSUM_ONLY_NO_PAYLOAD_NO_OUTCOMES"] = (
        "COMPLETE_CHECKSUM_ONLY_NO_PAYLOAD_NO_OUTCOMES"
    )
    protocol_file_sha256: str
    protocol_evidence_hash: str
    protocol_audit_file_sha256: str
    protocol_audit_evidence_hash: str
    target_manifest_hash: str
    runner_contract_hash: str
    records: tuple[RawTradesMetadataRecord, ...] = Field(
        min_length=72,
        max_length=72,
    )
    summary: RawTradesMetadataSummary
    decision: Literal[
        "PERMIT_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL",
        "STOP_Q1_USDM_RAW_TRADES_METADATA_CENSUS_INCOMPLETE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL",
        "NONE_RAW_TRADES_METADATA_CENSUS_FAILED",
    ]
    authorizes_one_month_payload_protocol: bool
    unique_checksum_urls_requested: Literal[72] = 72
    checksum_get_requests_made: int = Field(ge=72, le=216)
    archive_head_requests_made: Literal[0] = 0
    archive_payload_requests_made: Literal[0] = 0
    archive_payload_bytes: Literal[0] = 0
    market_numeric_fields_inspected: tuple[str, ...] = ()
    parameters_defined: tuple[str, ...] = ()
    return_metrics_calculated: tuple[str, ...] = ()
    strategy_candidates_created: Literal[0] = 0
    strategy_executions: Literal[0] = 0
    orders_submitted: Literal[0] = 0
    authorizes_parameter_definition: Literal[False] = False
    authorizes_return_testing: Literal[False] = False
    authorizes_validation_outcomes: Literal[False] = False
    authorizes_holdout_access: Literal[False] = False
    authorizes_pine_deployment: Literal[False] = False
    authorizes_paper_operation: Literal[False] = False
    authorizes_testnet_strategy_orders: Literal[False] = False
    authorizes_production: Literal[False] = False
    authorizes_live: Literal[False] = False
    real_net_profit_usd: Literal["0"] = "0"
    limitations: tuple[str, ...] = Field(min_length=8)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "protocol_file_sha256",
        "protocol_evidence_hash",
        "protocol_audit_file_sha256",
        "protocol_audit_evidence_hash",
        "target_manifest_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> RawTradesMetadataCensusResult:
        expected_records = tuple(sorted(self.records, key=lambda item: item.month))
        if (
            self.records != expected_records
            or tuple(item.month for item in self.records) != RAW_TRADES_MONTHS
            or self.summary != summarize_raw_trades_records(self.records)
        ):
            raise ValueError("Q1 raw-trades census records changed")
        passed = self.summary.present_count == 72
        if (
            self.decision
            != (RAW_TRADES_PASS_DECISION if passed else RAW_TRADES_FAIL_DECISION)
            or self.next_authorization
            != (
                RAW_TRADES_PASS_AUTHORIZATION
                if passed
                else RAW_TRADES_FAIL_AUTHORIZATION
            )
            or self.authorizes_one_month_payload_protocol != passed
            or self.checksum_get_requests_made != self.summary.http_attempt_count
            or self.limitations != tuple(sorted(set(self.limitations)))
            or self.market_numeric_fields_inspected
            or self.parameters_defined
            or self.return_metrics_calculated
        ):
            raise ValueError("Q1 raw-trades census decision or authority changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected:
            raise ValueError("Q1 raw-trades census result hash changed")
        return self


class RawTradesMetadataCensusAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-usdm-raw-trades-metadata-census-audit-v1"
    ] = "aurex-q1-usdm-raw-trades-metadata-census-audit-v1"
    audit_id: Literal["q1-usdm-raw-trades-metadata-census-audit-v1"] = (
        "q1-usdm-raw-trades-metadata-census-audit-v1"
    )
    audited_at: datetime
    result_file_sha256: str
    result_evidence_hash: str
    protocol_evidence_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    target_count: Literal[72] = 72
    present_count: int = Field(ge=0, le=72)
    development_present_count: int = Field(ge=0, le=48)
    validation_metadata_present_count: int = Field(ge=0, le=24)
    checksum_get_requests_made: int = Field(ge=72, le=216)
    archive_payload_requests_made: Literal[0] = 0
    market_numeric_field_count: Literal[0] = 0
    parameter_count: Literal[0] = 0
    return_metric_count: Literal[0] = 0
    strategy_candidate_count: Literal[0] = 0
    order_count: Literal[0] = 0
    decision: Literal[
        "PERMIT_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL",
        "STOP_Q1_USDM_RAW_TRADES_METADATA_CENSUS_INCOMPLETE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL",
        "NONE_RAW_TRADES_METADATA_CENSUS_FAILED",
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
        "protocol_evidence_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> RawTradesMetadataCensusAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 raw-trades census audit hash changed")
        return self


def _build(model, hash_field: str, values: dict):
    provisional = model.model_construct(**values, **{hash_field: "0" * 64})
    payload = provisional.model_dump()
    payload[hash_field] = universe_evidence_hash(
        provisional.model_dump(exclude={hash_field})
    )
    return model.model_validate(payload)


def build_raw_trades_protocol(**values) -> RawTradesMetadataCensusProtocol:
    targets = authoritative_raw_trades_targets()
    payload = {
        **values,
        "targets": targets,
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ),
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(RawTradesMetadataCensusProtocol, "protocol_evidence_hash", payload)


def build_raw_trades_protocol_audit(**values) -> RawTradesMetadataProtocolAudit:
    return _build(RawTradesMetadataProtocolAudit, "audit_evidence_hash", values)


def build_raw_trades_result(**values) -> RawTradesMetadataCensusResult:
    records = tuple(sorted(values.pop("records"), key=lambda item: item.month))
    summary = summarize_raw_trades_records(records)
    passed = summary.present_count == 72
    payload = {
        **values,
        "records": records,
        "summary": summary,
        "decision": (
            RAW_TRADES_PASS_DECISION if passed else RAW_TRADES_FAIL_DECISION
        ),
        "next_authorization": (
            RAW_TRADES_PASS_AUTHORIZATION
            if passed
            else RAW_TRADES_FAIL_AUTHORIZATION
        ),
        "authorizes_one_month_payload_protocol": passed,
        "checksum_get_requests_made": summary.http_attempt_count,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    return _build(RawTradesMetadataCensusResult, "result_evidence_hash", payload)


def build_raw_trades_audit(**values) -> RawTradesMetadataCensusAudit:
    return _build(RawTradesMetadataCensusAudit, "audit_evidence_hash", values)


def audit_raw_trades_protocol(protocol: RawTradesMetadataCensusProtocol) -> bool:
    return protocol.protocol_evidence_hash == universe_evidence_hash(
        protocol.model_dump(exclude={"protocol_evidence_hash"})
    )


def audit_raw_trades_protocol_audit(audit: RawTradesMetadataProtocolAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )


def audit_raw_trades_result(result: RawTradesMetadataCensusResult) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_raw_trades_audit(audit: RawTradesMetadataCensusAudit) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
