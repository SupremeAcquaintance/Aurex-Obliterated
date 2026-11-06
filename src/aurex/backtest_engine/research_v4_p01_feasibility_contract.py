from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V4P01_FEASIBILITY_CONTRACT_SCHEMA_VERSION = (
    "aurex-v4-p01-cross-venue-feasibility-contract-v1"
)
V4P01_CONTRACT_DECISION = (
    "AUTHORIZE_BOUNDED_PUBLIC_METADATA_AND_SCHEMA_PILOT_NO_MARKET_VALUES"
)
V4P01_REQUIRED_GATE_IDS = [
    "ACCOUNT_AND_JURISDICTION_ACCESS",
    "ARCHIVE_CALENDAR_AND_INCIDENT_COVERAGE",
    "CAPACITY_AND_STALENESS_FOUNDATION",
    "COMMON_ETH_BTC_PRODUCT_IDENTITY",
    "DETERMINISTIC_TWO_LEG_STATE_MACHINE",
    "DISCONNECT_SNAPSHOT_AND_SEQUENCE_RECOVERY",
    "EXCHANGE_AND_LOCAL_TIMESTAMP_IDENTITY",
    "IOC_OR_FOK_ORDER_SEMANTICS",
    "POINT_IN_TIME_FEES_AND_FEE_CURRENCY",
    "POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE",
    "PRE_FUNDED_INVENTORY_AND_BALANCE_ACCOUNTING",
    "RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES",
    "SOURCE_REVISION_AND_BYTE_INTEGRITY",
    "TRANSPORT_RESOURCE_AND_STORAGE_FEASIBILITY",
]
V4P01_PERMITTED_OBSERVATION_FIELDS = [
    "attempt_count",
    "boundary_completeness",
    "capture_line_count",
    "channel_identity",
    "content_encoding",
    "content_length",
    "content_type",
    "disconnect_marker_count",
    "duplicate_local_timestamp_count",
    "elapsed_milliseconds",
    "exchange_id",
    "exchange_timestamp_presence_count",
    "first_and_last_exchange_timestamp",
    "first_and_last_local_timestamp",
    "http_status",
    "incident_identity_and_time_boundary",
    "local_timestamp_presence_count",
    "missing_required_schema_key_count",
    "payload_sha256",
    "product_identity",
    "reconnect_snapshot_count",
    "request_identity",
    "response_header_subset",
    "row_count",
    "schema_key_presence",
    "sequence_or_update_id_presence_count",
    "source_available_since_and_to",
    "source_revision_identity",
    "symbol_available_since_and_to",
]
V4P01_PROHIBITED_PARSED_FIELDS = [
    "ask_price_value",
    "ask_quantity_value",
    "bid_price_value",
    "bid_quantity_value",
    "fee_amount_value",
    "market_price_value",
    "order_book_depth_value",
    "profit_or_loss",
    "return_metric",
    "signal",
    "spread_value",
    "trade_price_value",
    "trade_quantity_value",
]
V4P01_JOURNAL_POLICY = [
    "APPEND_REQUEST_INTENT_AND_FSYNC_BEFORE_EVERY_ATTEMPT",
    "APPEND_RESPONSE_OR_FAILURE_RECORD_AND_FSYNC_AFTER_EVERY_ATTEMPT",
    "COUNT_ALL_ATTEMPTS_FROM_DURABLE_JOURNAL_ACROSS_RESTARTS",
    "HASH_AND_RECORD_PARTIAL_BYTES_BEFORE_TRANSACTIONAL_CLEANUP",
    "PERSIST_EACH_METADATA_OBSERVATION_BEFORE_ANY_PAYLOAD_REQUEST",
    "PERSIST_EACH_PAYLOAD_OBSERVATION_BEFORE_THE_NEXT_REQUEST",
    "REFUSE_DUPLICATE_REQUEST_ID_OR_UNDECLARED_URL",
    "REFUSE_PAYLOAD_PHASE_UNLESS_METADATA_RESULT_PASSES",
    "STOP_ON_STALE_PART_FILE_OR_UNRECONCILED_REQUEST_INTENT",
    "WRITE_EXACTLY_ONE_COMPLETE_REJECT_OR_TRANSPORT_STOP_ARTIFACT",
]
V4P01_STOP_CONDITIONS = [
    "ANY_BOUND_CHARTER_REGISTER_OR_PROPOSAL_HASH_FAILS",
    "ANY_DECLARED_REQUEST_EXCEEDS_ATTEMPT_BYTE_OR_WALL_CLOCK_BUDGET",
    "ANY_REQUEST_INTENT_OR_RESPONSE_RECORD_IS_NOT_DURABLE",
    "ANY_RESPONSE_REQUIRES_A_RETRY_OR_RESUME_NOT_DECLARED_HERE",
    "BINANCE_OR_COINBASE_ETH_BTC_PRODUCT_IS_ABSENT_OR_INCOMPLETE",
    "CUMULATIVE_RESOURCE_USE_CANNOT_BE_RECONSTRUCTED",
    "METADATA_GATE_FAILS_BEFORE_PAYLOAD_PHASE",
    "POINT_IN_TIME_FEES_FILTERS_OR_VENUE_STATE_CANNOT_BE_BOUNDED",
    "PUBLIC_SOURCE_REQUIRES_CREDENTIALS_FOR_THE_FROZEN_SAMPLE",
    "RAW_SCHEMA_CANNOT_PROVE_BBO_QUANTITY_AND_RECOVERY_FIELDS",
    "SOURCE_REVISION_OR_PARTIAL_BYTE_EVIDENCE_CANNOT_BE_PRESERVED",
    "TWO_LEG_ACCESS_INVENTORY_ROLLBACK_OR_RECONCILIATION_IS_NOT_FEASIBLE",
]


class V4P01SourceRequest(BaseModel):
    request_id: str = Field(pattern=r"^V4P01_(META|PILOT)_[A-Z0-9_]{5,80}$")
    phase: Literal["METADATA_CENSUS", "PAYLOAD_SCHEMA_PILOT"]
    sequence: int = Field(ge=1, le=8)
    method: Literal["GET"] = "GET"
    url: str = Field(min_length=20, max_length=1800)
    expected_host: Literal["api.tardis.dev"] = "api.tardis.dev"
    exchange_id: Literal["binance", "coinbase"]
    product_id: Literal["ethbtc", "ETH-BTC"] | None
    sample_at: datetime | None
    offset_minutes: int | None = Field(default=None, ge=0, le=1439)
    required_channels: list[str] = Field(min_length=1)
    request_headers: dict[str, str]
    authentication: Literal["NONE_FREE_FIRST_DAY_SAMPLE"] = (
        "NONE_FREE_FIRST_DAY_SAMPLE"
    )
    maximum_attempts: Literal[1] = 1
    maximum_retries: Literal[0] = 0
    connect_timeout_seconds: Literal[10] = 10
    read_inactivity_timeout_seconds: Literal[30] = 30
    total_wall_clock_timeout_seconds: int = Field(ge=60, le=180)
    maximum_response_bytes: int = Field(ge=1, le=16_777_216)
    range_or_resume_permitted: Literal[False] = False
    market_value_parsing_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("sample_at")
    @classmethod
    def normalize_sample_at(cls, value: datetime | None) -> datetime | None:
        return normalize_timestamp(value) if value is not None else None

    @field_validator("required_channels")
    @classmethod
    def normalize_channels(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_request(self) -> V4P01SourceRequest:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or parsed.hostname != self.expected_host:
            raise ValueError("V4P01 request host or scheme changed")
        if self.request_headers != {
            "Accept": "application/json, application/x-ndjson",
            "Accept-Encoding": "gzip",
            "User-Agent": "Aurex-V4P01-Feasibility/1.0",
        }:
            raise ValueError("V4P01 request headers changed")
        if self.phase == "METADATA_CENSUS":
            if (
                self.product_id is not None
                or self.sample_at is not None
                or self.offset_minutes is not None
                or self.required_channels != ["exchange_metadata"]
                or self.total_wall_clock_timeout_seconds != 60
                or self.maximum_response_bytes != 8_388_608
            ):
                raise ValueError("V4P01 metadata request contract changed")
        else:
            expected_product = (
                "ethbtc" if self.exchange_id == "binance" else "ETH-BTC"
            )
            expected_channels = (
                ["bookTicker", "depth", "depthSnapshot"]
                if self.exchange_id == "binance"
                else ["l2update", "snapshot"]
            )
            if (
                self.product_id != expected_product
                or self.sample_at is None
                or self.sample_at.day != 1
                or self.offset_minutes is None
                or self.required_channels != expected_channels
                or self.total_wall_clock_timeout_seconds != 180
                or self.maximum_response_bytes != 16_777_216
            ):
                raise ValueError("V4P01 payload request contract changed")
        return self


class V4P01TransportBudget(BaseModel):
    metadata_unique_url_budget: Literal[2] = 2
    payload_unique_url_budget: Literal[6] = 6
    total_unique_url_budget: Literal[8] = 8
    total_attempt_budget: Literal[8] = 8
    total_retry_budget: Literal[0] = 0
    maximum_concurrency: Literal[1] = 1
    metadata_response_byte_budget: Literal[16_777_216] = 16_777_216
    payload_response_byte_budget: Literal[100_663_296] = 100_663_296
    total_response_byte_budget: Literal[117_440_512] = 117_440_512
    storage_budget_bytes: Literal[268_435_456] = 268_435_456
    protocol_wall_clock_budget_seconds: Literal[1200] = 1200
    automatic_retry_permitted: Literal[False] = False
    range_or_resume_permitted: Literal[False] = False
    budget_expansion_after_observation_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V4P01ExecutionGate(BaseModel):
    gate_id: str = Field(pattern=r"^[A-Z0-9_]{5,100}$")
    evidence_required: list[str] = Field(min_length=2)
    pass_condition: str = Field(min_length=80, max_length=1200)
    failure_action: Literal["REJECT_V4P01_BEFORE_PRIMARY_SELECTION"] = (
        "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    )
    conservative_override_permitted: Literal[False] = False
    observed_status: Literal["NOT_OBSERVED_PRE_EXECUTION"] = (
        "NOT_OBSERVED_PRE_EXECUTION"
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("evidence_required")
    @classmethod
    def normalize_evidence(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V4P01TerminalArtifactContract(BaseModel):
    complete_artifact: str
    reject_artifact: str
    transport_stop_artifact: str
    mutually_exclusive: Literal[True] = True
    required_common_fields: list[str] = Field(min_length=8)
    required_transport_stop_fields: list[str] = Field(min_length=6)
    result_authorizes_returns: Literal[False] = False
    result_creates_candidate: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "required_common_fields",
        "required_transport_stop_fields",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class V4P01FeasibilityContract(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-cross-venue-feasibility-contract-v1"
    ] = V4P01_FEASIBILITY_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v4-p01-cross-venue-feasibility-v1"] = (
        "v4-p01-cross-venue-feasibility-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_AND_PRE_OUTCOME"] = (
        "FROZEN_PRE_NETWORK_AND_PRE_OUTCOME"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    proposal_evidence_hash: str
    builder_contract_hash: str
    proposal_id: Literal[
        "V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE"
    ]
    exact_common_product: Literal["ETH_BTC"] = "ETH_BTC"
    venue_product_bindings: dict[str, str]
    development_start: datetime
    development_end: datetime
    requests: list[V4P01SourceRequest] = Field(min_length=8, max_length=8)
    transport_budget: V4P01TransportBudget
    execution_gates: list[V4P01ExecutionGate] = Field(
        min_length=14,
        max_length=14,
    )
    permitted_observation_fields: list[str]
    prohibited_parsed_fields: list[str]
    journal_policy: list[str]
    stop_conditions: list[str]
    journal_path: str
    metadata_observation_path: str
    payload_observation_path: str
    raw_payload_directory: str
    terminal_artifacts: V4P01TerminalArtifactContract
    decision: Literal[
        "AUTHORIZE_BOUNDED_PUBLIC_METADATA_AND_SCHEMA_PILOT_NO_MARKET_VALUES"
    ] = V4P01_CONTRACT_DECISION
    authorizes_network_requests: Literal[True] = True
    authorized_network_scope: Literal[
        "EXACT_EIGHT_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    ] = "EXACT_EIGHT_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    credentials_permitted: Literal[False] = False
    private_endpoints_permitted: Literal[False] = False
    market_numeric_value_inspection_permitted: Literal[False] = False
    signal_trade_pnl_or_return_calculation_permitted: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development_outcomes: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    permits_pine_parity: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    strategy_outcome_fields_inspected: list[str] = Field(default_factory=list)
    return_metrics_calculated: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=10)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at", "development_start", "development_end")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "discovery_charter_evidence_hash",
        "proposal_register_evidence_hash",
        "proposal_evidence_hash",
        "builder_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "permitted_observation_fields",
        "prohibited_parsed_fields",
        "journal_policy",
        "stop_conditions",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V4P01FeasibilityContract:
        if self.venue_product_bindings != {
            "binance": "ethbtc",
            "coinbase": "ETH-BTC",
        }:
            raise ValueError("V4P01 venue product binding changed")
        if (
            self.development_start.isoformat()
            != "2023-01-01T00:00:00+00:00"
            or self.development_end.isoformat()
            != "2025-01-01T00:00:00+00:00"
        ):
            raise ValueError("V4P01 development boundary changed")
        if [request.sequence for request in self.requests] != list(range(1, 9)):
            raise ValueError("V4P01 request sequence changed")
        if len({request.request_id for request in self.requests}) != 8:
            raise ValueError("V4P01 request IDs are not unique")
        if len({request.url for request in self.requests}) != 8:
            raise ValueError("V4P01 request URLs are not unique")
        if [gate.gate_id for gate in self.execution_gates] != (
            V4P01_REQUIRED_GATE_IDS
        ):
            raise ValueError("V4P01 execution gate order or identity changed")
        expected_lists = {
            "permitted_observation_fields": V4P01_PERMITTED_OBSERVATION_FIELDS,
            "prohibited_parsed_fields": V4P01_PROHIBITED_PARSED_FIELDS,
            "journal_policy": V4P01_JOURNAL_POLICY,
            "stop_conditions": V4P01_STOP_CONDITIONS,
        }
        for field_name, expected in expected_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"V4P01 {field_name} changed")
        if (
            self.strategy_outcome_fields_inspected
            or self.return_metrics_calculated
        ):
            raise ValueError("V4P01 contract must predate outcomes")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V4P01 contract hash does not match")
        return self


def build_v4_p01_feasibility_contract(
    **values,
) -> V4P01FeasibilityContract:
    payload = {
        "schema_version": V4P01_FEASIBILITY_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v4-p01-cross-venue-feasibility-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_NETWORK_AND_PRE_OUTCOME",
        "exact_common_product": "ETH_BTC",
        "venue_product_bindings": {
            "binance": "ethbtc",
            "coinbase": "ETH-BTC",
        },
        "decision": V4P01_CONTRACT_DECISION,
        "authorizes_network_requests": True,
        "authorized_network_scope": (
            "EXACT_EIGHT_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
        ),
        "credentials_permitted": False,
        "private_endpoints_permitted": False,
        "market_numeric_value_inspection_permitted": False,
        "signal_trade_pnl_or_return_calculation_permitted": False,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_development_outcomes": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "permits_pine_parity": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    payload["frozen_at"] = normalize_timestamp(payload["frozen_at"])
    payload["development_start"] = normalize_timestamp(
        payload["development_start"]
    )
    payload["development_end"] = normalize_timestamp(payload["development_end"])
    for field_name in (
        "permitted_observation_fields",
        "prohibited_parsed_fields",
        "journal_policy",
        "stop_conditions",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    return V4P01FeasibilityContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_p01_feasibility_contract(
    contract: V4P01FeasibilityContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )
