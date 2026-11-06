from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_v4_p01_feasibility_contract import (
    V4P01ExecutionGate,
    V4P01SourceRequest,
    V4P01TerminalArtifactContract,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

V4P01_CONTINUATION_SCHEMA_VERSION = (
    "aurex-v4-p01-feasibility-continuation-contract-v1"
)
V4P01_CONTINUATION_REQUEST_IDS = [
    "V4P01_PILOT_BINANCE_20230101_0000",
    "V4P01_PILOT_COINBASE_20230101_0000",
    "V4P01_PILOT_BINANCE_20231201_1200",
    "V4P01_PILOT_COINBASE_20231201_1200",
    "V4P01_PILOT_BINANCE_20241201_2359",
    "V4P01_PILOT_COINBASE_20241201_2359",
]
V4P01_CONSUMED_REQUEST_IDS = [
    "V4P01_META_BINANCE_EXCHANGE_DETAILS",
    "V4P01_META_COINBASE_EXCHANGE_DETAILS",
]
TARDIS_INSTRUMENT_METADATA_URL = (
    "https://docs.tardis.dev/api/instruments-metadata-api"
)
TARDIS_EXCHANGE_DETAILS_URL = "https://docs.tardis.dev/api/http"


class V4P01ContinuationBudget(BaseModel):
    inherited_attempts_consumed: Literal[2] = 2
    inherited_response_bytes_consumed: Literal[74788] = 74_788
    metadata_attempt_budget: Literal[0] = 0
    payload_unique_url_budget: Literal[6] = 6
    continuation_attempt_budget: Literal[6] = 6
    continuation_retry_budget: Literal[0] = 0
    maximum_concurrency: Literal[1] = 1
    payload_response_byte_budget: Literal[100_663_296] = 100_663_296
    continuation_storage_budget_bytes: Literal[268_435_456] = 268_435_456
    continuation_wall_clock_budget_seconds: Literal[1080] = 1080
    inherited_plus_continuation_attempt_ceiling: Literal[8] = 8
    automatic_retry_permitted: Literal[False] = False
    metadata_repeat_permitted: Literal[False] = False
    range_or_resume_permitted: Literal[False] = False
    budget_expansion_permitted: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class V4P01ContinuationContract(BaseModel):
    schema_version: Literal[
        "aurex-v4-p01-feasibility-continuation-contract-v1"
    ] = V4P01_CONTINUATION_SCHEMA_VERSION
    contract_id: Literal["v4-p01-feasibility-continuation-v1"] = (
        "v4-p01-feasibility-continuation-v1"
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_PRE_PAYLOAD_AND_PRE_OUTCOME"] = (
        "FROZEN_PRE_PAYLOAD_AND_PRE_OUTCOME"
    )
    original_contract_evidence_hash: str
    original_terminal_reject_evidence_hash: str
    original_runner_contract_hash: str
    original_metadata_gate_evidence_hash: str
    inherited_metadata_observation_hashes: list[str] = Field(
        min_length=2,
        max_length=2,
    )
    builder_contract_hash: str
    correction_class: Literal[
        "RUNNER_INTERPRETATION_DEFECT_NOT_MARKET_OR_STRATEGY_EVIDENCE"
    ] = "RUNNER_INTERPRETATION_DEFECT_NOT_MARKET_OR_STRATEGY_EVIDENCE"
    incorrect_interpretation: str
    documented_semantic: str
    corrected_metadata_condition: str
    official_source_urls: list[str] = Field(min_length=2, max_length=2)
    source_reviewed_at: datetime
    consumed_request_ids: list[str] = Field(min_length=2, max_length=2)
    requests: list[V4P01SourceRequest] = Field(min_length=6, max_length=6)
    transport_budget: V4P01ContinuationBudget
    venue_product_bindings: dict[str, str]
    development_start: datetime
    development_end: datetime
    execution_gates: list[V4P01ExecutionGate] = Field(
        min_length=14,
        max_length=14,
    )
    journal_path: str
    corrected_metadata_gate_path: str
    payload_observation_path: str
    raw_payload_directory: str
    terminal_artifacts: V4P01TerminalArtifactContract
    decision: Literal[
        "AUTHORIZE_ONLY_SIX_UNCONSUMED_PUBLIC_PAYLOAD_SCHEMA_REQUESTS"
    ] = "AUTHORIZE_ONLY_SIX_UNCONSUMED_PUBLIC_PAYLOAD_SCHEMA_REQUESTS"
    authorizes_network_requests: Literal[True] = True
    authorized_network_scope: Literal[
        "EXACT_SIX_UNCONSUMED_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    ] = "EXACT_SIX_UNCONSUMED_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
    metadata_requests_authorized: Literal[False] = False
    credentials_permitted: Literal[False] = False
    market_numeric_value_inspection_permitted: Literal[False] = False
    signal_trade_pnl_or_return_calculation_permitted: Literal[False] = False
    original_reject_is_deleted_or_rewritten: Literal[False] = False
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
    limitations: list[str] = Field(min_length=8)
    contract_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "frozen_at",
        "source_reviewed_at",
        "development_start",
        "development_end",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "original_contract_evidence_hash",
        "original_terminal_reject_evidence_hash",
        "original_runner_contract_hash",
        "original_metadata_gate_evidence_hash",
        "inherited_metadata_observation_hashes",
        "builder_contract_hash",
        "contract_evidence_hash",
    )
    @classmethod
    def normalize_hashes(
        cls,
        value: str | list[str],
    ) -> str | list[str]:
        if isinstance(value, list):
            return [normalize_sha256(item) for item in value]
        return normalize_sha256(value)

    @field_validator(
        "official_source_urls",
        "consumed_request_ids",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    )
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_contract(self) -> V4P01ContinuationContract:
        if self.official_source_urls != sorted(
            [TARDIS_EXCHANGE_DETAILS_URL, TARDIS_INSTRUMENT_METADATA_URL]
        ):
            raise ValueError("V4P01 continuation official source binding changed")
        if self.consumed_request_ids != sorted(V4P01_CONSUMED_REQUEST_IDS):
            raise ValueError("V4P01 consumed request identity changed")
        if [item.request_id for item in self.requests] != (
            V4P01_CONTINUATION_REQUEST_IDS
        ):
            raise ValueError("V4P01 continuation request identity changed")
        if [item.sequence for item in self.requests] != list(range(3, 9)):
            raise ValueError("V4P01 continuation request sequence changed")
        if any(item.phase != "PAYLOAD_SCHEMA_PILOT" for item in self.requests):
            raise ValueError("V4P01 continuation cannot repeat metadata")
        if self.venue_product_bindings != {
            "binance": "ethbtc",
            "coinbase": "ETH-BTC",
        }:
            raise ValueError("V4P01 continuation venue product binding changed")
        if (
            self.development_start.isoformat()
            != "2023-01-01T00:00:00+00:00"
            or self.development_end.isoformat()
            != "2025-01-01T00:00:00+00:00"
        ):
            raise ValueError("V4P01 continuation boundary changed")
        if self.strategy_outcome_fields_inspected or self.return_metrics_calculated:
            raise ValueError("V4P01 continuation must remain pre-outcome")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"contract_evidence_hash"})
        )
        if self.contract_evidence_hash != expected_hash:
            raise ValueError("V4P01 continuation contract hash does not match")
        return self


def build_v4_p01_continuation_contract(
    **values,
) -> V4P01ContinuationContract:
    payload = {
        "schema_version": V4P01_CONTINUATION_SCHEMA_VERSION,
        "contract_id": "v4-p01-feasibility-continuation-v1",
        "contract_version": "1.0.0",
        "status": "FROZEN_PRE_PAYLOAD_AND_PRE_OUTCOME",
        "correction_class": (
            "RUNNER_INTERPRETATION_DEFECT_NOT_MARKET_OR_STRATEGY_EVIDENCE"
        ),
        "decision": (
            "AUTHORIZE_ONLY_SIX_UNCONSUMED_PUBLIC_PAYLOAD_SCHEMA_REQUESTS"
        ),
        "authorizes_network_requests": True,
        "authorized_network_scope": (
            "EXACT_SIX_UNCONSUMED_PUBLIC_TARDIS_GET_REQUESTS_ONLY"
        ),
        "metadata_requests_authorized": False,
        "credentials_permitted": False,
        "market_numeric_value_inspection_permitted": False,
        "signal_trade_pnl_or_return_calculation_permitted": False,
        "original_reject_is_deleted_or_rewritten": False,
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
        "official_source_urls",
        "consumed_request_ids",
        "strategy_outcome_fields_inspected",
        "return_metrics_calculated",
        "limitations",
    ):
        payload[field_name] = sorted(set(payload[field_name]))
    for field_name in (
        "frozen_at",
        "source_reviewed_at",
        "development_start",
        "development_end",
    ):
        payload[field_name] = normalize_timestamp(payload[field_name])
    return V4P01ContinuationContract(
        **payload,
        contract_evidence_hash=universe_evidence_hash(payload),
    )


def audit_v4_p01_continuation_contract(
    contract: V4P01ContinuationContract,
) -> bool:
    return contract.contract_evidence_hash == universe_evidence_hash(
        contract.model_dump(exclude={"contract_evidence_hash"})
    )
