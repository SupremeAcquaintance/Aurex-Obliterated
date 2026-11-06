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

Q1_CENSUS_CONTRACT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-metadata-census-contract-v1"
)
Q1_CENSUS_RESULT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-metadata-census-result-v1"
)
Q1_CENSUS_AUDIT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-metadata-census-audit-v1"
)
Q1_CENSUS_PASS_DECISION = (
    "PERMIT_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL"
)
Q1_CENSUS_FAIL_DECISION = "STOP_Q1_METADATA_CENSUS_INCOMPLETE"
Q1_CENSUS_PASS_AUTHORIZATION = (
    "AUTHORIZE_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL"
)
Q1_CENSUS_FAIL_AUTHORIZATION = "NONE_METADATA_CENSUS_FAILED"
Q1_CENSUS_PRODUCTS = ("SPOT", "USD_M_PERPETUAL")
Q1_CENSUS_MONTHS = tuple(
    f"{year}-{month:02d}"
    for year in range(2020, 2026)
    for month in range(1, 13)
)
Q1_CENSUS_TARGET_COUNT = 144
Q1_CENSUS_OFFICIAL_REFERENCE = (
    "https://github.com/binance/binance-public-data"
)
Q1_CENSUS_DOCUMENTATION_CLAIMS = (
    "Binance publishes daily and monthly public Spot and Futures archives.",
    "Every published ZIP archive is accompanied by a CHECKSUM file.",
    "Spot aggregate trades have eight documented columns.",
    "USD-M Futures aggregate trades have seven documented columns.",
    "Spot timestamps from 2025-01-01 onward are documented in microseconds.",
    "Archived files may be revised after publication.",
)
SPOT_AGGTRADE_COLUMNS = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_was_maker",
    "best_price_match",
)
USD_M_AGGTRADE_COLUMNS = (
    "aggregate_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "timestamp",
    "buyer_was_maker",
)


def expected_timestamp_unit(
    product: Literal["SPOT", "USD_M_PERPETUAL"],
    month: str,
) -> Literal["MILLISECONDS", "MICROSECONDS"]:
    if product == "SPOT" and month >= "2025-01":
        return "MICROSECONDS"
    return "MILLISECONDS"


def archive_url(
    product: Literal["SPOT", "USD_M_PERPETUAL"],
    month: str,
) -> str:
    prefix = (
        "data/spot/monthly/aggTrades"
        if product == "SPOT"
        else "data/futures/um/monthly/aggTrades"
    )
    return (
        f"https://data.binance.vision/{prefix}/BTCUSDT/"
        f"BTCUSDT-aggTrades-{month}.zip"
    )


class PeriodicFlowArchiveSchema(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    api_source: Literal["/api/v3/aggTrades", "/fapi/v1/aggTrades"]
    columns: tuple[str, ...]
    timestamp_rule: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_schema(self) -> PeriodicFlowArchiveSchema:
        if self.product == "SPOT":
            expected_api = "/api/v3/aggTrades"
            expected_columns = SPOT_AGGTRADE_COLUMNS
            expected_rule = (
                "MILLISECONDS_THROUGH_2024_MICROSECONDS_FROM_2025_01"
            )
        else:
            expected_api = "/fapi/v1/aggTrades"
            expected_columns = USD_M_AGGTRADE_COLUMNS
            expected_rule = "MILLISECONDS"
        if (
            self.api_source != expected_api
            or self.columns != expected_columns
            or self.timestamp_rule != expected_rule
        ):
            raise ValueError("Q1 aggregate-trade schema register changed")
        return self


def authoritative_schemas() -> tuple[PeriodicFlowArchiveSchema, ...]:
    return (
        PeriodicFlowArchiveSchema(
            product="SPOT",
            api_source="/api/v3/aggTrades",
            columns=SPOT_AGGTRADE_COLUMNS,
            timestamp_rule=(
                "MILLISECONDS_THROUGH_2024_MICROSECONDS_FROM_2025_01"
            ),
        ),
        PeriodicFlowArchiveSchema(
            product="USD_M_PERPETUAL",
            api_source="/fapi/v1/aggTrades",
            columns=USD_M_AGGTRADE_COLUMNS,
            timestamp_rule="MILLISECONDS",
        ),
    )


class PeriodicFlowMetadataTarget(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    partition_role: Literal["DEVELOPMENT", "VALIDATION"]
    expected_timestamp_unit: Literal["MILLISECONDS", "MICROSECONDS"]
    archive_url: str
    checksum_url: str

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_target(self) -> PeriodicFlowMetadataTarget:
        if self.month not in Q1_CENSUS_MONTHS:
            raise ValueError("Q1 census month is outside the frozen matrix")
        expected_role = "DEVELOPMENT" if self.month < "2024-01" else "VALIDATION"
        expected_archive = archive_url(self.product, self.month)
        if (
            self.partition_role != expected_role
            or self.expected_timestamp_unit
            != expected_timestamp_unit(self.product, self.month)
            or self.archive_url != expected_archive
            or self.checksum_url != f"{expected_archive}.CHECKSUM"
        ):
            raise ValueError("Q1 metadata target changed")
        parsed = urlparse(self.checksum_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "data.binance.vision"
            or not parsed.path.endswith(".zip.CHECKSUM")
        ):
            raise ValueError("Q1 target must use official Binance checksum HTTPS")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.month, self.product


def authoritative_targets() -> tuple[PeriodicFlowMetadataTarget, ...]:
    return tuple(
        PeriodicFlowMetadataTarget(
            product=product,
            month=month,
            partition_role=(
                "DEVELOPMENT" if month < "2024-01" else "VALIDATION"
            ),
            expected_timestamp_unit=expected_timestamp_unit(product, month),
            archive_url=archive_url(product, month),
            checksum_url=f"{archive_url(product, month)}.CHECKSUM",
        )
        for month in Q1_CENSUS_MONTHS
        for product in Q1_CENSUS_PRODUCTS
    )


class PeriodicFlowMetadataCensusContract(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-metadata-census-contract-v1"
    ] = Q1_CENSUS_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["q1-periodic-flow-metadata-census-v1"] = (
        "q1-periodic-flow-metadata-census-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_METADATA_ONLY"] = (
        "FROZEN_PRE_NETWORK_METADATA_ONLY"
    )
    charter_file_sha256: str
    charter_evidence_hash: str
    charter_audit_file_sha256: str
    charter_audit_evidence_hash: str
    readiness_result_evidence_hash: str
    readiness_audit_evidence_hash: str
    builder_contract_hash: str
    official_document_reference: Literal[
        "https://github.com/binance/binance-public-data"
    ] = Q1_CENSUS_OFFICIAL_REFERENCE
    documentation_claims: tuple[str, ...] = Q1_CENSUS_DOCUMENTATION_CLAIMS
    schema_register: tuple[PeriodicFlowArchiveSchema, ...]
    schema_register_hash: str
    targets: tuple[PeriodicFlowMetadataTarget, ...] = Field(
        min_length=Q1_CENSUS_TARGET_COUNT,
        max_length=Q1_CENSUS_TARGET_COUNT,
    )
    target_manifest_hash: str
    maximum_unique_checksum_urls: Literal[144] = 144
    maximum_http_attempts: Literal[432] = 432
    maximum_checksum_response_bytes: Literal[512] = 512
    request_timeout_seconds: Literal[30] = 30
    maximum_retries: Literal[2] = 2
    retry_backoff_seconds: tuple[Literal[1], Literal[3]] = (1, 3)
    maximum_concurrency: Literal[4] = 4
    required_present_target_count: Literal[144] = 144
    required_paired_month_count: Literal[72] = 72
    permitted_http_statuses: tuple[Literal[200], Literal[404]] = (200, 404)
    checksum_get_requests_permitted: Literal[True] = True
    archive_head_requests_permitted: Literal[False] = False
    archive_payload_requests_permitted: Literal[False] = False
    market_numeric_values_permitted: Literal[False] = False
    parameter_definition_permitted: Literal[False] = False
    strategy_outcomes_permitted: Literal[False] = False
    validation_outcomes_permitted: Literal[False] = False
    holdout_access_permitted: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_testnet_strategy_order_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    limitations: tuple[str, ...] = Field(min_length=6)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "charter_file_sha256",
        "charter_evidence_hash",
        "charter_audit_file_sha256",
        "charter_audit_evidence_hash",
        "readiness_result_evidence_hash",
        "readiness_audit_evidence_hash",
        "builder_contract_hash",
        "schema_register_hash",
        "target_manifest_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_contract(self) -> PeriodicFlowMetadataCensusContract:
        schemas = authoritative_schemas()
        targets = authoritative_targets()
        if self.schema_register != schemas:
            raise ValueError("Q1 schema register changed")
        if self.targets != targets:
            raise ValueError("Q1 census target matrix changed")
        if self.documentation_claims != Q1_CENSUS_DOCUMENTATION_CLAIMS:
            raise ValueError("Q1 official documentation claims changed")
        if self.schema_register_hash != universe_evidence_hash(
            {"schemas": [item.model_dump() for item in schemas]}
        ):
            raise ValueError("Q1 schema register hash changed")
        if self.target_manifest_hash != universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets]}
        ):
            raise ValueError("Q1 target manifest hash changed")
        expected = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected:
            raise ValueError("Q1 census contract evidence hash changed")
        return self


class PeriodicFlowMetadataRecord(BaseModel):
    product: Literal["SPOT", "USD_M_PERPETUAL"]
    symbol: Literal["BTCUSDT"] = "BTCUSDT"
    month: str
    partition_role: Literal["DEVELOPMENT", "VALIDATION"]
    expected_timestamp_unit: Literal["MILLISECONDS", "MICROSECONDS"]
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
    def validate_record(self) -> PeriodicFlowMetadataRecord:
        target = PeriodicFlowMetadataTarget(
            product=self.product,
            month=self.month,
            partition_role=self.partition_role,
            expected_timestamp_unit=self.expected_timestamp_unit,
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
            raise ValueError("Q1 checksum availability does not reconcile")
        if present:
            assert self.checksum_text is not None
            assert self.checksum_text_sha256 is not None
            assert self.archive_sha256 is not None
            text_hash = sha256(self.checksum_text.encode("utf-8")).hexdigest()
            archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
            parsed_hash = parse_v2_checksum_text(
                self.checksum_text,
                archive_name,
            )
            if (
                self.checksum_text_sha256 != text_hash
                or self.archive_sha256 != parsed_hash
            ):
                raise ValueError("Q1 checksum text reconstruction changed")
        elif any(
            (
                self.checksum_response_bytes,
                self.checksum_text,
                self.checksum_text_sha256,
                self.archive_sha256,
            )
        ):
            raise ValueError("Q1 missing target cannot contain checksum evidence")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return self.month, self.product


class PeriodicFlowMetadataSummary(BaseModel):
    target_count: Literal[144] = 144
    observed_count: Literal[144] = 144
    present_count: int = Field(ge=0, le=144)
    missing_count: int = Field(ge=0, le=144)
    spot_present_count: int = Field(ge=0, le=72)
    usd_m_present_count: int = Field(ge=0, le=72)
    paired_present_month_count: int = Field(ge=0, le=72)
    development_paired_month_count: int = Field(ge=0, le=48)
    validation_paired_month_count: int = Field(ge=0, le=24)
    http_attempt_count: int = Field(ge=144, le=432)
    missing_target_keys: tuple[str, ...]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_summary(self) -> PeriodicFlowMetadataSummary:
        if self.present_count + self.missing_count != 144:
            raise ValueError("Q1 metadata observation counts do not reconcile")
        if self.present_count != self.spot_present_count + self.usd_m_present_count:
            raise ValueError("Q1 product observation counts do not reconcile")
        if self.paired_present_month_count != (
            self.development_paired_month_count
            + self.validation_paired_month_count
        ):
            raise ValueError("Q1 partition pair counts do not reconcile")
        if self.missing_count != len(self.missing_target_keys):
            raise ValueError("Q1 missing target keys do not reconcile")
        return self


def summarize_records(
    records: tuple[PeriodicFlowMetadataRecord, ...],
) -> PeriodicFlowMetadataSummary:
    present = sum(item.availability == "PRESENT" for item in records)
    spot = sum(
        item.product == "SPOT" and item.availability == "PRESENT"
        for item in records
    )
    usd_m = sum(
        item.product == "USD_M_PERPETUAL" and item.availability == "PRESENT"
        for item in records
    )
    present_keys = {
        item.key for item in records if item.availability == "PRESENT"
    }
    paired_months = tuple(
        month
        for month in Q1_CENSUS_MONTHS
        if all((month, product) in present_keys for product in Q1_CENSUS_PRODUCTS)
    )
    return PeriodicFlowMetadataSummary(
        present_count=present,
        missing_count=144 - present,
        spot_present_count=spot,
        usd_m_present_count=usd_m,
        paired_present_month_count=len(paired_months),
        development_paired_month_count=sum(month < "2024-01" for month in paired_months),
        validation_paired_month_count=sum(month >= "2024-01" for month in paired_months),
        http_attempt_count=sum(item.request_attempt_count for item in records),
        missing_target_keys=tuple(
            f"{item.month}:{item.product}"
            for item in records
            if item.availability == "MISSING"
        ),
    )


class PeriodicFlowMetadataCensusResult(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-metadata-census-result-v1"
    ] = Q1_CENSUS_RESULT_SCHEMA_VERSION
    result_id: Literal["q1-periodic-flow-metadata-census-result-v1"] = (
        "q1-periodic-flow-metadata-census-result-v1"
    )
    generated_at: datetime
    status: Literal["COMPLETE_METADATA_ONLY_NO_PAYLOAD_NO_OUTCOMES"] = (
        "COMPLETE_METADATA_ONLY_NO_PAYLOAD_NO_OUTCOMES"
    )
    contract_file_sha256: str
    contract_evidence_hash: str
    target_manifest_hash: str
    schema_register_hash: str
    runner_contract_hash: str
    records: tuple[PeriodicFlowMetadataRecord, ...] = Field(
        min_length=144,
        max_length=144,
    )
    summary: PeriodicFlowMetadataSummary
    decision: Literal[
        "PERMIT_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL",
        "STOP_Q1_METADATA_CENSUS_INCOMPLETE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL",
        "NONE_METADATA_CENSUS_FAILED",
    ]
    authorizes_separate_payload_pilot_protocol: bool
    unique_checksum_urls_requested: Literal[144] = 144
    checksum_get_requests_made: int = Field(ge=144, le=432)
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
    limitations: tuple[str, ...] = Field(min_length=6)
    result_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "target_manifest_hash",
        "schema_register_hash",
        "runner_contract_hash",
        "result_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_result(self) -> PeriodicFlowMetadataCensusResult:
        expected_records = tuple(sorted(self.records, key=lambda item: item.key))
        if self.records != expected_records:
            raise ValueError("Q1 census records are not canonical")
        if tuple(item.key for item in self.records) != tuple(
            item.key for item in authoritative_targets()
        ):
            raise ValueError("Q1 census result target matrix changed")
        expected_summary = summarize_records(self.records)
        if self.summary != expected_summary:
            raise ValueError("Q1 census summary does not match records")
        passed = (
            self.summary.present_count == 144
            and self.summary.paired_present_month_count == 72
        )
        if (
            self.decision
            != (Q1_CENSUS_PASS_DECISION if passed else Q1_CENSUS_FAIL_DECISION)
            or self.next_authorization
            != (
                Q1_CENSUS_PASS_AUTHORIZATION
                if passed
                else Q1_CENSUS_FAIL_AUTHORIZATION
            )
            or self.authorizes_separate_payload_pilot_protocol != passed
            or self.checksum_get_requests_made != self.summary.http_attempt_count
        ):
            raise ValueError("Q1 census decision does not match evidence")
        if any(
            (
                self.market_numeric_fields_inspected,
                self.parameters_defined,
                self.return_metrics_calculated,
            )
        ):
            raise ValueError("Q1 census cannot contain outcomes or parameters")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"result_evidence_hash"})
        )
        if self.result_evidence_hash != expected_hash:
            raise ValueError("Q1 census result evidence hash changed")
        return self


class PeriodicFlowMetadataCensusAudit(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-metadata-census-audit-v1"
    ] = Q1_CENSUS_AUDIT_SCHEMA_VERSION
    audit_id: Literal["q1-periodic-flow-metadata-census-audit-v1"] = (
        "q1-periodic-flow-metadata-census-audit-v1"
    )
    audited_at: datetime
    contract_path: Literal[
        "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
    ] = "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
    contract_file_sha256: str
    contract_evidence_hash: str
    result_path: Literal[
        "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
    ] = "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
    result_file_sha256: str
    result_evidence_hash: str
    builder_contract_hash: str
    runner_contract_hash: str
    auditor_contract_hash: str
    reconstructed_exactly: Literal[True] = True
    target_count: Literal[144] = 144
    present_count: int = Field(ge=0, le=144)
    paired_present_month_count: int = Field(ge=0, le=72)
    checksum_get_requests_made: int = Field(ge=144, le=432)
    archive_payload_requests_made: Literal[0] = 0
    market_numeric_field_count: Literal[0] = 0
    parameter_count: Literal[0] = 0
    return_metric_count: Literal[0] = 0
    strategy_candidate_count: Literal[0] = 0
    order_count: Literal[0] = 0
    decision: Literal[
        "PERMIT_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL",
        "STOP_Q1_METADATA_CENSUS_INCOMPLETE",
    ]
    next_authorization: Literal[
        "AUTHORIZE_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL",
        "NONE_METADATA_CENSUS_FAILED",
    ]
    audit_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("audited_at")
    @classmethod
    def normalize_audited_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "contract_file_sha256",
        "contract_evidence_hash",
        "result_file_sha256",
        "result_evidence_hash",
        "builder_contract_hash",
        "runner_contract_hash",
        "auditor_contract_hash",
        "audit_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_audit(self) -> PeriodicFlowMetadataCensusAudit:
        expected = universe_evidence_hash(
            self.model_dump(exclude={"audit_evidence_hash"})
        )
        if self.audit_evidence_hash != expected:
            raise ValueError("Q1 census audit evidence hash changed")
        return self


def build_metadata_census_contract(**values) -> PeriodicFlowMetadataCensusContract:
    values = {
        **values,
        "schema_register": authoritative_schemas(),
        "schema_register_hash": universe_evidence_hash(
            {"schemas": [item.model_dump() for item in authoritative_schemas()]}
        ),
        "targets": authoritative_targets(),
        "target_manifest_hash": universe_evidence_hash(
            {"targets": [item.model_dump() for item in authoritative_targets()]}
        ),
    }
    provisional = PeriodicFlowMetadataCensusContract.model_construct(
        **values,
        contract_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"contract_evidence_hash"})
    )
    return PeriodicFlowMetadataCensusContract.model_validate(payload)


def build_metadata_census_result(**values) -> PeriodicFlowMetadataCensusResult:
    records = tuple(sorted(values.pop("records"), key=lambda item: item.key))
    summary = summarize_records(records)
    passed = summary.present_count == 144 and summary.paired_present_month_count == 72
    values = {
        **values,
        "records": records,
        "summary": summary,
        "decision": Q1_CENSUS_PASS_DECISION if passed else Q1_CENSUS_FAIL_DECISION,
        "next_authorization": (
            Q1_CENSUS_PASS_AUTHORIZATION if passed else Q1_CENSUS_FAIL_AUTHORIZATION
        ),
        "authorizes_separate_payload_pilot_protocol": passed,
        "checksum_get_requests_made": summary.http_attempt_count,
    }
    provisional = PeriodicFlowMetadataCensusResult.model_construct(
        **values,
        result_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["result_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"result_evidence_hash"})
    )
    return PeriodicFlowMetadataCensusResult.model_validate(payload)


def build_metadata_census_audit(**values) -> PeriodicFlowMetadataCensusAudit:
    provisional = PeriodicFlowMetadataCensusAudit.model_construct(
        **values,
        audit_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"audit_evidence_hash"})
    )
    return PeriodicFlowMetadataCensusAudit.model_validate(payload)


def audit_metadata_census_contract(
    contract: PeriodicFlowMetadataCensusContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )


def audit_metadata_census_result(
    result: PeriodicFlowMetadataCensusResult,
) -> bool:
    return result.result_evidence_hash == universe_evidence_hash(
        result.model_dump(exclude={"result_evidence_hash"})
    )


def audit_metadata_census_audit(
    audit: PeriodicFlowMetadataCensusAudit,
) -> bool:
    return audit.audit_evidence_hash == universe_evidence_hash(
        audit.model_dump(exclude={"audit_evidence_hash"})
    )
