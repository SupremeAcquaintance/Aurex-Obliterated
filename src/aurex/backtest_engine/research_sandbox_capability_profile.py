from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.research_operator_access_profile import (
    MAX_PLANNING_DAILY_LOSS,
    MAX_PLANNING_RISK_PER_TRADE,
    MAX_PLANNING_TOTAL_LOSS,
)
from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

SANDBOX_PROFILE_SCHEMA_VERSION = "aurex-binance-spot-testnet-profile-v1"
SANDBOX_PROFILE_GATE_IDS = [
    "TESTNET_AUTHENTICATED_ACCESS_ATTESTED",
    "TESTNET_API_CREDENTIAL_PATH_DOCUMENTED",
    "SANDBOX_ENVIRONMENT_AND_ENDPOINTS_BOUND",
    "SPOT_SYMBOL_AND_LEVERAGE_SCOPE_SAFE",
    "SIMULATED_RISK_LIMITS_PROTECTIVE",
    "TESTNET_LIMITATIONS_ACKNOWLEDGED",
    "DATA_BUDGET_EXPLICIT",
    "NO_CREDENTIALS_OR_ACCOUNT_IDENTIFIERS",
    "NO_PRODUCTION_OR_REAL_CAPITAL_AUTHORITY",
]
SANDBOX_PROFILE_PASS_DECISION = (
    "AUTHORIZE_SANDBOX_ADAPTER_IMPLEMENTATION_AND_SUCCESSOR_CHARTER_DESIGN_ONLY"
)
SANDBOX_PROFILE_FAIL_DECISION = "BLOCK_SANDBOX_ADAPTER_AND_SUCCESSOR_CHARTER"
BINANCE_SPOT_TESTNET_REST_URL = "https://testnet.binance.vision/api"
BINANCE_SPOT_TESTNET_WS_API_URL = (
    "wss://ws-api.testnet.binance.vision/ws-api/v3"
)
BINANCE_SPOT_TESTNET_STREAM_URL = "wss://stream.testnet.binance.vision/ws"


class BinanceSpotTestnetSandboxInput(BaseModel):
    schema_version: Literal[
        "aurex-binance-spot-testnet-input-v1"
    ] = "aurex-binance-spot-testnet-input-v1"
    attested_at: datetime
    operator_identifier: str = Field(min_length=2, max_length=120)
    attestation_statement: Literal[
        "I_ATTEST_BINANCE_SPOT_TESTNET_ACCESS_IS_AUTHENTICATED_AND_"
        "NO_CREDENTIALS_ARE_INCLUDED"
    ]
    jurisdiction: str = Field(min_length=2, max_length=120)
    sandbox_venue: Literal["Binance Spot Test Network"]
    sandbox_environment: Literal["TESTNET"]
    account_identifier_alias: str = Field(min_length=2, max_length=120)
    authentication_method: Literal["GITHUB_OAUTH"]
    testnet_access_status: Literal["AUTHENTICATED"]
    api_credential_path_status: Literal[
        "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "GENERATED_NOT_STORED_IN_PROFILE",
    ]
    testnet_rest_base_url: Literal["https://testnet.binance.vision/api"]
    testnet_ws_api_url: Literal[
        "wss://ws-api.testnet.binance.vision/ws-api/v3"
    ]
    testnet_stream_url: Literal[
        "wss://stream.testnet.binance.vision/ws"
    ]
    permitted_product_scope: Literal["SPOT_ONLY"]
    permitted_symbols: list[str] = Field(min_length=1, max_length=10)
    maximum_effective_leverage: Decimal = Field(ge=0, le=1)
    simulated_starting_equity: Decimal = Field(gt=0)
    equity_currency: Literal["USD"]
    maximum_total_loss: Decimal = Field(gt=0)
    maximum_daily_loss: Decimal = Field(gt=0)
    maximum_per_trade_loss: Decimal = Field(gt=0)
    one_time_data_budget: Decimal = Field(ge=0)
    monthly_data_budget: Decimal = Field(ge=0)
    data_budget_currency: Literal["USD"]
    paid_data_permitted: bool
    testnet_funds_are_virtual_acknowledged: bool
    testnet_monthly_reset_behavior_acknowledged: bool
    testnet_performance_is_not_edge_evidence_acknowledged: bool
    production_account_verified: Literal[False] = False
    production_api_authorized: Literal[False] = False
    real_capital_authorized: Literal[False] = False
    live_trading_authorized: Literal[False] = False
    testnet_documentation_reference: str = Field(min_length=5, max_length=1000)
    api_documentation_reference: str = Field(min_length=5, max_length=1000)
    fee_schedule_reference: str = Field(min_length=5, max_length=1000)
    access_attestation_reference: str = Field(min_length=5, max_length=1000)
    risk_attestation_reference: str = Field(min_length=5, max_length=1000)
    data_budget_attestation_reference: str = Field(
        min_length=5,
        max_length=1000,
    )
    credentials_stored_or_embedded: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("attested_at")
    @classmethod
    def normalize_attested_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "maximum_effective_leverage",
        "simulated_starting_equity",
        "maximum_total_loss",
        "maximum_daily_loss",
        "maximum_per_trade_loss",
        "one_time_data_budget",
        "monthly_data_budget",
    )
    @classmethod
    def normalize_decimals(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_validator("permitted_symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().upper() for item in value if item.strip()})
        if not normalized:
            raise ValueError("At least one sandbox symbol is required")
        if any(not item.isalnum() for item in normalized):
            raise ValueError("Sandbox symbols must be alphanumeric")
        return normalized

    @field_validator(
        "operator_identifier",
        "jurisdiction",
        "account_identifier_alias",
        "testnet_documentation_reference",
        "api_documentation_reference",
        "fee_schedule_reference",
        "access_attestation_reference",
        "risk_attestation_reference",
        "data_budget_attestation_reference",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_input(self) -> BinanceSpotTestnetSandboxInput:
        if self.permitted_symbols != ["BTCUSDT"]:
            raise ValueError("Initial sandbox scope must be exactly BTCUSDT")
        if (
            not self.paid_data_permitted
            and (
                self.one_time_data_budget != 0
                or self.monthly_data_budget != 0
            )
        ):
            raise ValueError(
                "A nonzero data budget requires paid_data_permitted=true"
            )
        inspected_text = [
            self.operator_identifier,
            self.jurisdiction,
            self.account_identifier_alias,
            self.testnet_documentation_reference,
            self.api_documentation_reference,
            self.fee_schedule_reference,
            self.access_attestation_reference,
            self.risk_attestation_reference,
            self.data_budget_attestation_reference,
        ]
        secret_tokens = (
            "-----begin ",
            "api_key=",
            "apikey=",
            "api-secret",
            "access_token=",
            "authorization: bearer",
            "client_secret=",
            "private_key=",
            "secret=",
            "secret_key=",
            "password=",
            "token=",
        )
        if any(
            token in text.casefold()
            for text in inspected_text
            for token in secret_tokens
        ):
            raise ValueError(
                "Sandbox capability input appears to contain credential material"
            )
        return self


class SandboxCapabilityGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "FAIL"]
    reason: str = Field(min_length=30, max_length=1400)

    model_config = ConfigDict(extra="forbid")


class BinanceSpotTestnetSandboxProfile(BaseModel):
    schema_version: Literal[
        "aurex-binance-spot-testnet-profile-v1"
    ] = SANDBOX_PROFILE_SCHEMA_VERSION
    profile_id: Literal["binance-spot-testnet-sandbox-profile-v1"] = (
        "binance-spot-testnet-sandbox-profile-v1"
    )
    profile_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_SANDBOX_CAPABILITY_NO_CREDENTIALS"] = (
        "FROZEN_SANDBOX_CAPABILITY_NO_CREDENTIALS"
    )
    post_v4_capability_review_evidence_hash: str
    post_v4_capability_review_builder_hash: str
    builder_contract_hash: str
    operator_input: BinanceSpotTestnetSandboxInput
    operator_input_evidence_hash: str
    maximum_total_loss_ratio: Decimal = Field(gt=0)
    maximum_daily_loss_ratio: Decimal = Field(gt=0)
    maximum_per_trade_loss_ratio: Decimal = Field(gt=0)
    gate_results: list[SandboxCapabilityGateResult] = Field(
        min_length=9,
        max_length=9,
    )
    failed_gate_ids: list[str]
    decision: Literal[
        "AUTHORIZE_SANDBOX_ADAPTER_IMPLEMENTATION_AND_SUCCESSOR_CHARTER_"
        "DESIGN_ONLY",
        "BLOCK_SANDBOX_ADAPTER_AND_SUCCESSOR_CHARTER",
    ]
    sandbox_adapter_implementation_authorized: bool
    successor_charter_design_authorized: bool
    testnet_network_requests_authorized: bool
    testnet_virtual_order_entry_authorized: bool
    sandbox_qualified: Literal[False] = False
    creates_sandbox_qualification: Literal[False] = False
    successor_alpha_discovery_authorized: Literal[False] = False
    real_market_data_import_authorized: Literal[False] = False
    parameter_definition_authorized: Literal[False] = False
    return_testing_authorized: Literal[False] = False
    creates_candidate: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    production_account_authorized: Literal[False] = False
    production_api_authorized: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    real_capital_authorized: Literal[False] = False
    stores_credentials: Literal[False] = False
    limitations: list[str] = Field(min_length=8)
    profile_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "post_v4_capability_review_evidence_hash",
        "post_v4_capability_review_builder_hash",
        "builder_contract_hash",
        "operator_input_evidence_hash",
        "profile_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @field_validator(
        "maximum_total_loss_ratio",
        "maximum_daily_loss_ratio",
        "maximum_per_trade_loss_ratio",
    )
    @classmethod
    def normalize_ratios(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_validator("failed_gate_ids", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_profile(self) -> BinanceSpotTestnetSandboxProfile:
        if [item.gate_id for item in self.gate_results] != (
            SANDBOX_PROFILE_GATE_IDS
        ):
            raise ValueError("Sandbox-profile gate set or order changed")
        expected_input_hash = universe_evidence_hash(self.operator_input)
        if self.operator_input_evidence_hash != expected_input_hash:
            raise ValueError("Sandbox-profile input hash does not match")
        equity = self.operator_input.simulated_starting_equity
        expected_ratios = (
            self.operator_input.maximum_total_loss / equity,
            self.operator_input.maximum_daily_loss / equity,
            self.operator_input.maximum_per_trade_loss / equity,
        )
        observed_ratios = (
            self.maximum_total_loss_ratio,
            self.maximum_daily_loss_ratio,
            self.maximum_per_trade_loss_ratio,
        )
        if observed_ratios != expected_ratios:
            raise ValueError("Sandbox-profile derived ratios changed")
        expected_failed = sorted(
            item.gate_id for item in self.gate_results if item.status == "FAIL"
        )
        if self.failed_gate_ids != expected_failed:
            raise ValueError("Sandbox-profile failed gate list changed")
        passing = not expected_failed
        expected_decision = (
            SANDBOX_PROFILE_PASS_DECISION
            if passing
            else SANDBOX_PROFILE_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.sandbox_adapter_implementation_authorized != passing
            or self.successor_charter_design_authorized != passing
            or self.testnet_network_requests_authorized != passing
            or self.testnet_virtual_order_entry_authorized != passing
        ):
            raise ValueError("Sandbox-profile decision is inconsistent")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"profile_evidence_hash"})
        )
        if self.profile_evidence_hash != expected_hash:
            raise ValueError("Sandbox-profile evidence hash does not match")
        return self


def evaluate_sandbox_capability_gates(
    operator_input: BinanceSpotTestnetSandboxInput,
) -> list[SandboxCapabilityGateResult]:
    equity = operator_input.simulated_starting_equity
    total_ratio = operator_input.maximum_total_loss / equity
    daily_ratio = operator_input.maximum_daily_loss / equity
    trade_ratio = operator_input.maximum_per_trade_loss / equity
    loss_pass = (
        operator_input.maximum_per_trade_loss
        <= operator_input.maximum_daily_loss
        <= operator_input.maximum_total_loss
        <= equity
        and trade_ratio <= MAX_PLANNING_RISK_PER_TRADE
        and daily_ratio <= MAX_PLANNING_DAILY_LOSS
        and total_ratio <= MAX_PLANNING_TOTAL_LOSS
    )
    limitation_pass = (
        operator_input.testnet_funds_are_virtual_acknowledged
        and operator_input.testnet_monthly_reset_behavior_acknowledged
        and operator_input.testnet_performance_is_not_edge_evidence_acknowledged
    )
    data_pass = (
        (
            operator_input.paid_data_permitted
            and (
                operator_input.one_time_data_budget > 0
                or operator_input.monthly_data_budget > 0
            )
        )
        or (
            not operator_input.paid_data_permitted
            and operator_input.one_time_data_budget == 0
            and operator_input.monthly_data_budget == 0
        )
    )
    no_production_authority = (
        not operator_input.production_account_verified
        and not operator_input.production_api_authorized
        and not operator_input.real_capital_authorized
        and not operator_input.live_trading_authorized
    )
    values = {
        "TESTNET_AUTHENTICATED_ACCESS_ATTESTED": (
            operator_input.testnet_access_status == "AUTHENTICATED"
            and operator_input.authentication_method == "GITHUB_OAUTH",
            (
                "The operator attests to GitHub-authenticated Binance Spot "
                "Testnet access."
            ),
        ),
        "TESTNET_API_CREDENTIAL_PATH_DOCUMENTED": (
            operator_input.api_credential_path_status
            in {
                "DOCUMENTED_AVAILABLE_NOT_TESTED",
                "GENERATED_NOT_STORED_IN_PROFILE",
            },
            (
                "The official Testnet API credential path is documented without "
                "storing a key."
            ),
        ),
        "SANDBOX_ENVIRONMENT_AND_ENDPOINTS_BOUND": (
            operator_input.testnet_rest_base_url
            == BINANCE_SPOT_TESTNET_REST_URL
            and operator_input.testnet_ws_api_url
            == BINANCE_SPOT_TESTNET_WS_API_URL
            and operator_input.testnet_stream_url
            == BINANCE_SPOT_TESTNET_STREAM_URL,
            (
                "The sandbox environment is bound to the exact official Binance "
                "Spot Testnet endpoints."
            ),
        ),
        "SPOT_SYMBOL_AND_LEVERAGE_SCOPE_SAFE": (
            operator_input.permitted_product_scope == "SPOT_ONLY"
            and operator_input.permitted_symbols == ["BTCUSDT"]
            and operator_input.maximum_effective_leverage <= 1,
            (
                "The initial sandbox scope is BTCUSDT Spot only with effective "
                "leverage capped at 1x."
            ),
        ),
        "SIMULATED_RISK_LIMITS_PROTECTIVE": (
            loss_pass,
            (
                "Simulated loss limits are ordered and remain within 0.5 percent "
                "per trade, 1 percent daily, and 10 percent total."
                if loss_pass
                else "Simulated loss limits must remain ordered and within the "
                "predeclared capital-protection ratios."
            ),
        ),
        "TESTNET_LIMITATIONS_ACKNOWLEDGED": (
            limitation_pass,
            (
                "Virtual funds, periodic resets, and the absence of profit evidence "
                "are explicitly acknowledged."
                if limitation_pass
                else "Virtual funds, reset behavior, and non-edge status must all "
                "be acknowledged."
            ),
        ),
        "DATA_BUDGET_EXPLICIT": (
            data_pass,
            (
                "The paid-data decision and one-time/monthly budget are explicit."
                if data_pass
                else "Paid-data permission and declared budgets are inconsistent."
            ),
        ),
        "NO_CREDENTIALS_OR_ACCOUNT_IDENTIFIERS": (
            not operator_input.credentials_stored_or_embedded,
            (
                "The sandbox input stores no API key, secret, production account "
                "identifier, or credential."
            ),
        ),
        "NO_PRODUCTION_OR_REAL_CAPITAL_AUTHORITY": (
            no_production_authority,
            (
                "Production accounts, production APIs, live trading, and real "
                "capital remain explicitly unauthorized."
                if no_production_authority
                else "A sandbox capability profile cannot create production or "
                "real-capital authority."
            ),
        ),
    }
    return [
        SandboxCapabilityGateResult(
            gate_id=gate_id,
            status="PASS" if values[gate_id][0] else "FAIL",
            reason=values[gate_id][1],
        )
        for gate_id in SANDBOX_PROFILE_GATE_IDS
    ]


def build_binance_spot_testnet_sandbox_profile(
    *,
    frozen_at: datetime,
    post_v4_capability_review_evidence_hash: str,
    post_v4_capability_review_builder_hash: str,
    builder_contract_hash: str,
    operator_input: BinanceSpotTestnetSandboxInput,
    limitations: list[str],
) -> BinanceSpotTestnetSandboxProfile:
    gates = evaluate_sandbox_capability_gates(operator_input)
    failed = sorted(item.gate_id for item in gates if item.status == "FAIL")
    passing = not failed
    equity = operator_input.simulated_starting_equity
    payload = {
        "schema_version": SANDBOX_PROFILE_SCHEMA_VERSION,
        "profile_id": "binance-spot-testnet-sandbox-profile-v1",
        "profile_version": "1.0.0",
        "frozen_at": normalize_timestamp(frozen_at),
        "status": "FROZEN_SANDBOX_CAPABILITY_NO_CREDENTIALS",
        "post_v4_capability_review_evidence_hash": (
            post_v4_capability_review_evidence_hash
        ),
        "post_v4_capability_review_builder_hash": (
            post_v4_capability_review_builder_hash
        ),
        "builder_contract_hash": builder_contract_hash,
        "operator_input": operator_input,
        "operator_input_evidence_hash": universe_evidence_hash(operator_input),
        "maximum_total_loss_ratio": (
            operator_input.maximum_total_loss / equity
        ).normalize(),
        "maximum_daily_loss_ratio": (
            operator_input.maximum_daily_loss / equity
        ).normalize(),
        "maximum_per_trade_loss_ratio": (
            operator_input.maximum_per_trade_loss / equity
        ).normalize(),
        "gate_results": gates,
        "failed_gate_ids": failed,
        "decision": (
            SANDBOX_PROFILE_PASS_DECISION
            if passing
            else SANDBOX_PROFILE_FAIL_DECISION
        ),
        "sandbox_adapter_implementation_authorized": passing,
        "successor_charter_design_authorized": passing,
        "testnet_network_requests_authorized": passing,
        "testnet_virtual_order_entry_authorized": passing,
        "sandbox_qualified": False,
        "creates_sandbox_qualification": False,
        "successor_alpha_discovery_authorized": False,
        "real_market_data_import_authorized": False,
        "parameter_definition_authorized": False,
        "return_testing_authorized": False,
        "creates_candidate": False,
        "creates_paper_eligibility": False,
        "production_account_authorized": False,
        "production_api_authorized": False,
        "creates_live_eligibility": False,
        "real_capital_authorized": False,
        "stores_credentials": False,
        "limitations": sorted(set(limitations)),
    }
    return BinanceSpotTestnetSandboxProfile(
        **payload,
        profile_evidence_hash=universe_evidence_hash(payload),
    )


def audit_binance_spot_testnet_sandbox_profile(
    profile: BinanceSpotTestnetSandboxProfile,
) -> bool:
    return profile.profile_evidence_hash == universe_evidence_hash(
        profile.model_dump(exclude={"profile_evidence_hash"})
    )
