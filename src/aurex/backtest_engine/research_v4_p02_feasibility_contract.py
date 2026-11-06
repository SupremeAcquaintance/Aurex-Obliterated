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

V4P02_FEASIBILITY_CONTRACT_SCHEMA_VERSION = (
    "aurex-v4-p02-deribit-source-census-contract-v1"
)
V4P02_CONTRACT_DECISION = (
    "AUTHORIZE_ONE_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEAD_REQUESTS"
)
V4P02_SAMPLE_DATES = [
    "2023-01-01",
    "2023-12-01",
    "2024-12-01",
]
V4P02_DATASET_PRODUCTS = [
    ("book_snapshot_25", "BTC-PERPETUAL", "HEDGE_BOOK_SNAPSHOT"),
    ("book_snapshot_25", "OPTIONS", "OPTION_BOOK_SNAPSHOT"),
    ("derivative_ticker", "BTC-PERPETUAL", "HEDGE_DERIVATIVE_TICKER"),
    ("liquidations", "OPTIONS", "OPTION_LIQUIDATIONS"),
    ("options_chain", "OPTIONS", "OPTION_CHAIN"),
    ("quotes", "BTC-PERPETUAL", "HEDGE_QUOTES"),
    ("quotes", "OPTIONS", "OPTION_QUOTES"),
    ("trades", "BTC-PERPETUAL", "HEDGE_TRADES"),
    ("trades", "OPTIONS", "OPTION_TRADES"),
]
V4P02_REQUIRED_GATE_IDS = [
    "ACCOUNT_JURISDICTION_AND_DERIVATIVES_ACCESS",
    "ARCHIVE_CALENDAR_INCIDENT_AND_EXPORT_COVERAGE",
    "COLLATERAL_CASH_FLOW_AND_BALANCE_RECONCILIATION",
    "CROSS_SOURCE_CLOCK_AND_INSTRUMENT_BINDING",
    "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE",
    "DELTA_GREEK_AND_DISCRETE_HEDGE_STATE_MACHINE",
    "DETERMINISTIC_MULTI_LEG_ORDER_LIFECYCLE",
    "DISCONNECT_SEQUENCE_AND_SOURCE_REVISION_INTEGRITY",
    "HEDGE_BBO_TRADE_AND_DERIVATIVE_TICKER_FOUNDATION",
    "OPTION_BBO_QUANTITY_AND_BOOK_SNAPSHOT_FOUNDATION",
    "OPTION_CHAIN_INSTRUMENT_LIFECYCLE_FOUNDATION",
    "OPTION_TRADE_AND_LIQUIDATION_FOUNDATION",
    "POINT_IN_TIME_CONTRACT_EXPIRY_AND_SETTLEMENT_RULES",
    "POINT_IN_TIME_FEES_CAPS_AND_DELIVERY_FEES",
    "POINT_IN_TIME_MARGIN_LIQUIDATION_AND_ACCOUNT_MODE",
    "TAIL_LOSS_CAPACITY_CONCENTRATION_AND_KILL_SWITCHES",
    "TRANSPORT_STORAGE_COMMERCIAL_AND_RESOURCE_FEASIBILITY",
]
V4P02_PERMITTED_OBSERVATION_FIELDS = [
    "attempt_count",
    "available_channel_identity",
    "available_since_and_to",
    "content_encoding",
    "content_length",
    "content_type",
    "dataset_exported_until",
    "dataset_identity",
    "dataset_projected_storage_bytes",
    "dataset_symbol_identity",
    "elapsed_milliseconds",
    "etag_or_last_modified_identity",
    "exchange_id",
    "http_status",
    "incident_identity_and_time_boundary",
    "request_identity",
    "response_header_subset",
    "source_revision_identity",
    "symbol_available_since_and_to",
]
V4P02_PROHIBITED_PARSED_FIELDS = [
    "ask_amount_value",
    "ask_iv_value",
    "ask_price_value",
    "bid_amount_value",
    "bid_iv_value",
    "bid_price_value",
    "collateral_amount_value",
    "delta_value",
    "fee_amount_value",
    "gamma_value",
    "implied_volatility_value",
    "margin_amount_value",
    "mark_price_value",
    "option_price_value",
    "profit_or_loss",
    "return_metric",
    "signal",
    "strike_price_value",
    "trade_amount_value",
    "trade_price_value",
    "underlying_price_value",
    "vega_value",
]
V4P02_JOURNAL_POLICY = [
    "APPEND_REQUEST_INTENT_AND_FSYNC_BEFORE_EVERY_ATTEMPT",
    "APPEND_RESPONSE_OR_FAILURE_AND_FSYNC_AFTER_EVERY_ATTEMPT",
    "COUNT_ALL_ATTEMPTS_FROM_DURABLE_JOURNAL_ACROSS_RESTARTS",
    "METADATA_GET_MUST_PASS_BEFORE_ANY_DATASET_HEAD",
    "PERSIST_EACH_HEADER_OBSERVATION_BEFORE_THE_NEXT_REQUEST",
    "PERSIST_AND_VALIDATE_EVERY_DATASET_REDIRECT_HOP",
    "REFUSE_DATASET_BODY_BYTES_AND_UNSAFE_REDIRECT_TARGETS",
    "REFUSE_DUPLICATE_REQUEST_ID_OR_UNDECLARED_URL",
    "STOP_ON_STALE_PART_FILE_OR_UNRECONCILED_REQUEST_INTENT",
    "WRITE_EXACTLY_ONE_COMPLETE_REJECT_OR_TRANSPORT_STOP_ARTIFACT",
]
V4P02_STOP_CONDITIONS = [
    "ANY_BOUND_CHARTER_REGISTER_PROPOSAL_OR_BUILDER_HASH_FAILS",
    "ANY_REQUEST_REQUIRES_CREDENTIALS_RETRY_OR_RESUME",
    "ANY_REDIRECT_EXCEEDS_THREE_HOPS_OR_TARGETS_NONPUBLIC_OR_NONHTTPS_HOST",
    "ANY_RESPONSE_EXCEEDS_BODY_BYTE_OR_WALL_CLOCK_BUDGET",
    "ANY_REQUIRED_DATASET_OR_GROUPED_SYMBOL_IS_ABSENT",
    "ANY_REQUIRED_FIRST_OF_MONTH_HEADER_IS_UNAVAILABLE_OR_AMBIGUOUS",
    "COMPLETE_2023_2024_CALENDAR_OR_INCIDENT_SCOPE_CANNOT_BE_BOUNDED",
    "DATASET_CONTENT_LENGTH_OR_STORAGE_PROJECTION_CANNOT_BE_RECONSTRUCTED",
    "HISTORICAL_FEES_MARGIN_SETTLEMENT_OR_CONTRACT_STATE_CANNOT_BE_BOUNDED",
    "OPTION_AND_HEDGE_SOURCE_IDENTITIES_CANNOT_BE_CROSS_BOUND",
    "SOURCE_REVISION_OR_INTEGRITY_IDENTITY_CANNOT_BE_PRESERVED",
    "VENUE_ACCESS_MULTI_LEG_RECONCILIATION_OR_TAIL_RISK_IS_NOT_FEASIBLE",
]


class V4P02SourceRequest(BaseModel):
    request_id: str = Field(pattern=r"^V4P02_(META|HEAD)_[A-Z0-9_]{6,120}$")
    phase: Literal["EXCHANGE_METADATA", "DATASET_HEADER_CENSUS"]
    sequence: int = Field(ge=1, le=28)
    method: Literal["GET", "HEAD"]
    url: str = Field(min_length=20, max_length=800)
    expected_host: Literal["api.tardis.dev", "datasets.tardis.dev"]
    exchange_id: Literal["deribit"] = "deribit"
    dataset_data_type: str | None
    dataset_symbol: Literal["OPTIONS", "BTC-PERPETUAL"] | None
    dataset_role: str | None
    sample_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    request_headers: dict[str, str]
    authentication: Literal["NONE_PUBLIC_FIRST_DAY_SAMPLE"] = (
        "NONE_PUBLIC_FIRST_DAY_SAMPLE"
    )
    maximum_attempts: Literal[1] = 1
    maximum_retries: Literal[0] = 0
    connect_timeout_seconds: Literal[10] = 10
    read_inactivity_timeout_seconds: Literal[20] = 20
    total_wall_clock_timeout_seconds: Literal[45] = 45
    maximum_response_body_bytes: int = Field(ge=0, le=8_388_608)
    redirects_permitted: bool
    maximum_redirects: int = Field(ge=0, le=3)
    redirect_target_policy: Literal[
        "PUBLIC_HTTPS_ONLY_NO_CREDENTIALS_NO_PRIVATE_LOOPBACK_OR_LINK_LOCAL"
    ] = "PUBLIC_HTTPS_ONLY_NO_CREDENTIALS_NO_PRIVATE_LOOPBACK_OR_LINK_LOCAL"
    range_or_resume_permitted: Literal[False] = False
    market_value_parsing_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_request(self) -> V4P02SourceRequest:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or parsed.hostname != self.expected_host:
            raise ValueError("V4P02 request host or scheme changed")
        expected_headers = {
            "Accept": (
                "application/json"
                if self.phase == "EXCHANGE_METADATA"
                else "application/gzip"
            ),
            "Accept-Encoding": "identity",
            "User-Agent": "Aurex-V4P02-Source-Census/1.0",
        }
        if self.request_headers != expected_headers:
            raise ValueError("V4P02 request headers changed")
        if self.phase == "EXCHANGE_METADATA":
            if (
                self.sequence != 1
                or self.method != "GET"
                or self.expected_host != "api.tardis.dev"
                or self.url != "https://api.tardis.dev/v1/exchanges/deribit"
                or self.dataset_data_type is not None
                or self.dataset_symbol is not None
                or self.dataset_role is not None
                or self.sample_date is not None
                or self.maximum_response_body_bytes != 8_388_608
                or self.redirects_permitted
                or self.maximum_redirects != 0
            ):
                raise ValueError("V4P02 metadata request contract changed")
        elif (
            self.sequence == 1
            or self.method != "HEAD"
            or self.expected_host != "datasets.tardis.dev"
            or self.dataset_data_type is None
            or self.dataset_symbol is None
            or self.dataset_role is None
            or self.sample_date not in V4P02_SAMPLE_DATES
            or self.maximum_response_body_bytes != 0
            or not self.redirects_permitted
            or self.maximum_redirects != 3
        ):
            raise ValueError("V4P02 dataset HEAD request contract changed")
        return self


class V4P02TransportBudget(BaseModel):
    metadata_get_budget: Literal[1] = 1
    dataset_head_budget: Literal[27] = 27
    total_unique_url_budget: Literal[28] = 28
    total_attempt_budget: Literal[28] = 28
    total_retry_budget: Literal[0] = 0
    metadata_redirect_budget: Literal[0] = 0
    dataset_redirect_budget: Literal[81] = 81
    total_http_hop_budget: Literal[109] = 109
    maximum_concurrency: Literal[1] = 1
    maximum_metadata_body_bytes: Literal[8_388_608] = 8_388_608
    maximum_dataset_head_body_bytes: Literal[0] = 0
    total_response_body_byte_budget: Literal[8_388_608] = 8_388_608
    evidence_storage_budget_bytes: Literal[33_554_432] = 33_554_432
    projected_dataset_storage_ceiling_bytes: Literal[2_199_023_255_552] = (
        2_199_023_255_552
    )
    protocol_wall_clock_budget_seconds: Literal[1260] = 1260
    automatic_retry_permitted: Literal[False] = False
    dataset_redirects_permitted: Literal[True] = True
    redirect_scheme_downgrade_permitted: Literal[False] = False
    redirect_to_private_loopback_or_link_local_permitted: Literal[False] = False
    range_or_resume_permitted: Literal[False] = False
    budget_expansion_after_observation_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V4P02ExecutionGate(BaseModel):
    gate_id: str = Field(pattern=r"^[A-Z0-9_]{8,120}$")
    evidence_required: list[str] = Field(min_length=2)
    pass_condition: str = Field(min_length=100, max_length=1800)
    failure_action: Literal["REJECT_V4P02_BEFORE_PRIMARY_SELECTION"] = (
        "REJECT_V4P02_BEFORE_PRIMARY_SELECTION"
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


class V4P02TerminalArtifactContract(BaseModel):
    complete_artifact: str
    reject_artifact: str
    transport_stop_artifact: str
    mutually_exclusive: Literal[True] = True
    result_authorizes_payload_gets: Literal[False] = False
    result_authorizes_returns: Literal[False] = False
    result_creates_candidate: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V4P02FeasibilityContract(BaseModel):
    schema_version: Literal[
        "aurex-v4-p02-deribit-source-census-contract-v1"
    ] = V4P02_FEASIBILITY_CONTRACT_SCHEMA_VERSION
    contract_id: Literal["v4-p02-deribit-source-census-v1"] = (
        "v4-p02-deribit-source-census-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_NETWORK_PRE_PAYLOAD_PRE_OUTCOME"] = (
        "FROZEN_PRE_NETWORK_PRE_PAYLOAD_PRE_OUTCOME"
    )
    discovery_charter_evidence_hash: str
    proposal_register_evidence_hash: str
    proposal_evidence_hash: str
    builder_contract_hash: str
    proposal_id: Literal[
        "V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM"
    ]
    development_start: datetime
    development_end: datetime
    option_currency: Literal["BTC"] = "BTC"
    hedge_instrument: Literal["BTC-PERPETUAL"] = "BTC-PERPETUAL"
    grouped_option_symbol: Literal["OPTIONS"] = "OPTIONS"
    sample_dates: list[str] = Field(min_length=3, max_length=3)
    dataset_products: list[dict[str, str]] = Field(
        min_length=9,
        max_length=9,
    )
    requests: list[V4P02SourceRequest] = Field(min_length=28, max_length=28)
    transport_budget: V4P02TransportBudget
    execution_gates: list[V4P02ExecutionGate] = Field(
        min_length=17,
        max_length=17,
    )
    permitted_observation_fields: list[str]
    prohibited_parsed_fields: list[str]
    journal_policy: list[str]
    stop_conditions: list[str]
    official_documentation_sources: list[str] = Field(min_length=5)
    journal_path: str
    metadata_observation_path: str
    header_observation_path: str
    terminal_artifacts: V4P02TerminalArtifactContract
    decision: Literal[
        "AUTHORIZE_ONE_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEAD_REQUESTS"
    ] = V4P02_CONTRACT_DECISION
    authorizes_network_requests: Literal[True] = True
    authorized_network_scope: Literal[
        "EXACT_ONE_TARDIS_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEADS"
    ] = "EXACT_ONE_TARDIS_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEADS"
    dataset_payload_gets_permitted: Literal[False] = False
    raw_replay_requests_permitted: Literal[False] = False
    deribit_api_requests_permitted: Literal[False] = False
    credentials_permitted: Literal[False] = False
    market_numeric_value_inspection_permitted: Literal[False] = False
    signal_trade_pnl_or_return_calculation_permitted: Literal[False] = False
    selects_primary: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development_outcomes: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
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
        "official_documentation_sources",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V4P02FeasibilityContract:
        if self.sample_dates != V4P02_SAMPLE_DATES:
            raise ValueError("V4P02 sample dates changed")
        expected_products = [
            {
                "data_type": data_type,
                "symbol": symbol,
                "role": role,
            }
            for data_type, symbol, role in V4P02_DATASET_PRODUCTS
        ]
        if self.dataset_products != expected_products:
            raise ValueError("V4P02 dataset product matrix changed")
        if (
            self.development_start.isoformat()
            != "2023-01-01T00:00:00+00:00"
            or self.development_end.isoformat()
            != "2025-01-01T00:00:00+00:00"
        ):
            raise ValueError("V4P02 development boundary changed")
        if [item.sequence for item in self.requests] != list(range(1, 29)):
            raise ValueError("V4P02 request sequence changed")
        if len({item.request_id for item in self.requests}) != 28:
            raise ValueError("V4P02 request IDs are not unique")
        if len({item.url for item in self.requests}) != 28:
            raise ValueError("V4P02 request URLs are not unique")
        expected_matrix = [
            (data_type, symbol, role, sample_date)
            for sample_date in self.sample_dates
            for data_type, symbol, role in V4P02_DATASET_PRODUCTS
        ]
        observed_matrix = [
            (
                item.dataset_data_type,
                item.dataset_symbol,
                item.dataset_role,
                item.sample_date,
            )
            for item in self.requests[1:]
        ]
        if observed_matrix != expected_matrix:
            raise ValueError("V4P02 dataset request matrix changed")
        if [item.gate_id for item in self.execution_gates] != (
            V4P02_REQUIRED_GATE_IDS
        ):
            raise ValueError("V4P02 execution gate order changed")
        expected_lists = {
            "permitted_observation_fields": V4P02_PERMITTED_OBSERVATION_FIELDS,
            "prohibited_parsed_fields": V4P02_PROHIBITED_PARSED_FIELDS,
            "journal_policy": V4P02_JOURNAL_POLICY,
            "stop_conditions": V4P02_STOP_CONDITIONS,
        }
        for field_name, expected in expected_lists.items():
            if getattr(self, field_name) != sorted(expected):
                raise ValueError(f"V4P02 {field_name} changed")
        if self.strategy_outcome_fields_inspected or self.return_metrics_calculated:
            raise ValueError("V4P02 contract must remain pre-outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V4P02 contract hash does not match")
        return self


def build_v4_p02_feasibility_contract(
    **values,
) -> V4P02FeasibilityContract:
    payload = {
        "schema_version": V4P02_FEASIBILITY_CONTRACT_SCHEMA_VERSION,
        "contract_id": "v4-p02-deribit-source-census-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_NETWORK_PRE_PAYLOAD_PRE_OUTCOME",
        "option_currency": "BTC",
        "hedge_instrument": "BTC-PERPETUAL",
        "grouped_option_symbol": "OPTIONS",
        "decision": V4P02_CONTRACT_DECISION,
        "authorizes_network_requests": True,
        "authorized_network_scope": (
            "EXACT_ONE_TARDIS_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEADS"
        ),
        "dataset_payload_gets_permitted": False,
        "raw_replay_requests_permitted": False,
        "deribit_api_requests_permitted": False,
        "credentials_permitted": False,
        "market_numeric_value_inspection_permitted": False,
        "signal_trade_pnl_or_return_calculation_permitted": False,
        "selects_primary": False,
        "creates_candidate": False,
        "opens_development_outcomes": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "strategy_outcome_fields_inspected": [],
        "return_metrics_calculated": [],
        **values,
    }
    for field_name in (
        "permitted_observation_fields",
        "prohibited_parsed_fields",
        "journal_policy",
        "stop_conditions",
        "official_documentation_sources",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    for field_name in ("frozen_at", "development_start", "development_end"):
        payload[field_name] = normalize_timestamp(payload[field_name])
    return V4P02FeasibilityContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_p02_feasibility_contract(
    contract: V4P02FeasibilityContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )
