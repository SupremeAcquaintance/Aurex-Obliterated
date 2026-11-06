from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

OPERATOR_PROFILE_SCHEMA_VERSION = "aurex-post-v4-operator-access-profile-v1"
OPERATOR_PROFILE_GATE_IDS = [
    "ACCOUNT_AND_API_ACCESS_PROVEN",
    "CAPITAL_SOURCE_AND_RESERVE_SAFE",
    "DATA_BUDGET_EXPLICIT",
    "LOSS_LIMITS_CAPITAL_PROTECTIVE",
    "NO_CREDENTIALS_OR_SECRETS",
    "OPERATOR_ATTESTATION_COMPLETE",
    "PRODUCT_SCOPE_AND_LEVERAGE_SAFE",
    "SANDBOX_PATH_AVAILABLE",
    "VENUE_AND_JURISDICTION_BOUND",
]
OPERATOR_PROFILE_PASS_DECISION = "AUTHORIZE_SUCCESSOR_CHARTER_DESIGN_ONLY"
OPERATOR_PROFILE_FAIL_DECISION = "BLOCK_SUCCESSOR_DISCOVERY"
MAX_PLANNING_RISK_PER_TRADE = Decimal("0.005")
MAX_PLANNING_DAILY_LOSS = Decimal("0.01")
MAX_PLANNING_TOTAL_LOSS = Decimal("0.10")
FIRST_PROFIT_MILESTONE = Decimal("100")


class OperatorAccessCapitalDataInput(BaseModel):
    schema_version: Literal[
        "aurex-post-v4-operator-access-input-v1"
    ] = "aurex-post-v4-operator-access-input-v1"
    attested_at: datetime
    operator_identifier: str = Field(min_length=2, max_length=120)
    attestation_statement: Literal[
        "I_ATTEST_THIS_PROFILE_IS_ACCURATE_AND_CONTAINS_NO_CREDENTIALS"
    ]
    jurisdiction: str = Field(min_length=2, max_length=120)
    intended_execution_venue: str = Field(min_length=2, max_length=120)
    account_identifier_alias: str = Field(min_length=2, max_length=120)
    account_status: Literal["NONE", "UNVERIFIED", "VERIFIED"]
    api_access_status: Literal[
        "UNKNOWN",
        "UNAVAILABLE",
        "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "VERIFIED_READ_ONLY",
        "VERIFIED_ORDER_ENTRY_DISABLED",
    ]
    sandbox_access_status: Literal[
        "UNKNOWN",
        "UNAVAILABLE",
        "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "VERIFIED",
    ]
    permitted_product_scope: Literal[
        "SPOT_ONLY",
        "SPOT_AND_PERPETUALS",
        "SPOT_PERPETUALS_AND_OPTIONS",
        "OTHER",
    ]
    other_product_scope: str | None = Field(
        default=None,
        min_length=2,
        max_length=240,
    )
    derivatives_access_confirmed: bool
    derivatives_suitability_acknowledged: bool
    maximum_effective_leverage: Decimal = Field(ge=0, le=100)
    legal_and_tax_obligations_acknowledged: bool
    starting_trading_capital: Decimal = Field(gt=0)
    capital_currency: str = Field(min_length=3, max_length=12)
    capital_is_borrowed: Literal[False] = False
    capital_excludes_emergency_funds: bool
    maximum_total_loss: Decimal = Field(gt=0)
    maximum_daily_loss: Decimal = Field(gt=0)
    maximum_per_trade_loss: Decimal = Field(gt=0)
    one_time_data_budget: Decimal = Field(ge=0)
    monthly_data_budget: Decimal = Field(ge=0)
    data_budget_currency: str = Field(min_length=3, max_length=12)
    paid_data_permitted: bool
    venue_terms_reference: str = Field(min_length=5, max_length=1000)
    fee_schedule_reference: str = Field(min_length=5, max_length=1000)
    api_documentation_reference: str = Field(min_length=5, max_length=1000)
    product_access_evidence_reference: str = Field(
        min_length=5,
        max_length=1000,
    )
    sandbox_evidence_reference: str = Field(min_length=5, max_length=1000)
    capital_source_attestation_reference: str = Field(
        min_length=5,
        max_length=1000,
    )
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
        "starting_trading_capital",
        "maximum_total_loss",
        "maximum_daily_loss",
        "maximum_per_trade_loss",
        "one_time_data_budget",
        "monthly_data_budget",
        "maximum_effective_leverage",
    )
    @classmethod
    def normalize_decimals(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_validator("capital_currency", "data_budget_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.isalnum():
            raise ValueError("Operator-profile currency must be alphanumeric")
        return normalized

    @field_validator("account_identifier_alias")
    @classmethod
    def reject_account_number_aliases(cls, value: str) -> str:
        normalized = value.strip()
        compact = "".join(character for character in normalized if character.isalnum())
        digits = sum(character.isdigit() for character in compact)
        if re.search(r"\d{8,}", normalized) or (
            digits >= 6 and digits / max(len(compact), 1) >= 0.6
        ):
            raise ValueError(
                "Account alias must not contain an account number"
            )
        return normalized

    @field_validator(
        "operator_identifier",
        "jurisdiction",
        "intended_execution_venue",
        "account_identifier_alias",
        "other_product_scope",
        "venue_terms_reference",
        "fee_schedule_reference",
        "api_documentation_reference",
        "product_access_evidence_reference",
        "sandbox_evidence_reference",
        "capital_source_attestation_reference",
        "data_budget_attestation_reference",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_input(self) -> OperatorAccessCapitalDataInput:
        if self.permitted_product_scope == "OTHER":
            if not self.other_product_scope:
                raise ValueError("OTHER product scope requires a description")
        elif self.other_product_scope is not None:
            raise ValueError("Non-OTHER product scope cannot add a description")
        derivatives = self.permitted_product_scope in {
            "SPOT_AND_PERPETUALS",
            "SPOT_PERPETUALS_AND_OPTIONS",
        }
        if derivatives and not (
            self.derivatives_access_confirmed
            and self.derivatives_suitability_acknowledged
        ):
            raise ValueError(
                "Derivative scope requires access and suitability acknowledgement"
            )
        if (
            not derivatives
            and self.permitted_product_scope != "OTHER"
            and (
                self.derivatives_access_confirmed
                or self.derivatives_suitability_acknowledged
            )
        ):
            raise ValueError(
                "Spot-only scope cannot attest derivative access or suitability"
            )
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
        secret_tokens = (
            "-----begin ",
            "api_key=",
            "apikey=",
            "api-secret",
            "access_token=",
            "authorization: bearer",
            "client_secret=",
            "mnemonic=",
            "private_key=",
            "recovery phrase",
            "seed phrase",
            "secret=",
            "secret_key=",
            "password=",
            "token=",
        )
        inspected_text = [
            self.operator_identifier,
            self.jurisdiction,
            self.intended_execution_venue,
            self.account_identifier_alias,
            self.other_product_scope or "",
            self.venue_terms_reference,
            self.fee_schedule_reference,
            self.api_documentation_reference,
            self.product_access_evidence_reference,
            self.sandbox_evidence_reference,
            self.capital_source_attestation_reference,
            self.data_budget_attestation_reference,
        ]
        if any(
            token in text.casefold()
            for text in inspected_text
            for token in secret_tokens
        ):
            raise ValueError(
                "Operator profile appears to contain credential material"
            )
        return self


class OperatorProfileGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "FAIL"]
    reason: str = Field(min_length=30, max_length=1400)

    model_config = ConfigDict(extra="forbid")


class PostV4OperatorAccessProfile(BaseModel):
    schema_version: Literal[
        "aurex-post-v4-operator-access-profile-v1"
    ] = OPERATOR_PROFILE_SCHEMA_VERSION
    profile_id: Literal["post-v4-operator-access-profile-v1"] = (
        "post-v4-operator-access-profile-v1"
    )
    profile_version: Literal["1.0.0"] = "1.0.0"
    frozen_at: datetime
    status: Literal["FROZEN_OPERATOR_ATTESTATION_NO_CREDENTIALS"] = (
        "FROZEN_OPERATOR_ATTESTATION_NO_CREDENTIALS"
    )
    post_v4_capability_review_evidence_hash: str
    post_v4_capability_review_builder_hash: str
    builder_contract_hash: str
    operator_input: OperatorAccessCapitalDataInput
    operator_input_evidence_hash: str
    maximum_total_loss_ratio: Decimal = Field(gt=0)
    maximum_daily_loss_ratio: Decimal = Field(gt=0)
    maximum_per_trade_loss_ratio: Decimal = Field(gt=0)
    first_profit_milestone: Decimal = FIRST_PROFIT_MILESTONE
    first_profit_milestone_to_capital_ratio: Decimal = Field(gt=0)
    gate_results: list[OperatorProfileGateResult] = Field(
        min_length=9,
        max_length=9,
    )
    failed_gate_ids: list[str]
    decision: Literal[
        "AUTHORIZE_SUCCESSOR_CHARTER_DESIGN_ONLY",
        "BLOCK_SUCCESSOR_DISCOVERY",
    ]
    successor_charter_design_authorized: bool
    successor_alpha_discovery_authorized: Literal[False] = False
    network_requests_authorized: Literal[False] = False
    market_data_import_authorized: Literal[False] = False
    parameter_definition_authorized: Literal[False] = False
    return_testing_authorized: Literal[False] = False
    creates_candidate: Literal[False] = False
    opens_development: Literal[False] = False
    opens_validation: Literal[False] = False
    opens_holdout: Literal[False] = False
    opens_forward: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
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
        "first_profit_milestone",
        "first_profit_milestone_to_capital_ratio",
    )
    @classmethod
    def normalize_ratios(cls, value: Decimal) -> Decimal:
        return value.normalize()

    @field_validator("failed_gate_ids", "limitations")
    @classmethod
    def normalize_lists(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_profile(self) -> PostV4OperatorAccessProfile:
        if [item.gate_id for item in self.gate_results] != (
            OPERATOR_PROFILE_GATE_IDS
        ):
            raise ValueError("Operator-profile gate set or order changed")
        expected_input_hash = universe_evidence_hash(self.operator_input)
        if self.operator_input_evidence_hash != expected_input_hash:
            raise ValueError("Operator-profile input hash does not match")
        capital = self.operator_input.starting_trading_capital
        expected_ratios = (
            self.operator_input.maximum_total_loss / capital,
            self.operator_input.maximum_daily_loss / capital,
            self.operator_input.maximum_per_trade_loss / capital,
            FIRST_PROFIT_MILESTONE / capital,
        )
        observed_ratios = (
            self.maximum_total_loss_ratio,
            self.maximum_daily_loss_ratio,
            self.maximum_per_trade_loss_ratio,
            self.first_profit_milestone_to_capital_ratio,
        )
        if observed_ratios != expected_ratios:
            raise ValueError("Operator-profile derived ratios changed")
        if self.first_profit_milestone != FIRST_PROFIT_MILESTONE:
            raise ValueError("Operator-profile first profit milestone changed")
        expected_failed = sorted(
            item.gate_id for item in self.gate_results if item.status == "FAIL"
        )
        if self.failed_gate_ids != expected_failed:
            raise ValueError("Operator-profile failed gate list changed")
        passing = not expected_failed
        expected_decision = (
            OPERATOR_PROFILE_PASS_DECISION
            if passing
            else OPERATOR_PROFILE_FAIL_DECISION
        )
        if (
            self.decision != expected_decision
            or self.successor_charter_design_authorized != passing
        ):
            raise ValueError("Operator-profile decision is inconsistent")
        expected_hash = universe_evidence_hash(
            self.model_dump(exclude={"profile_evidence_hash"})
        )
        if self.profile_evidence_hash != expected_hash:
            raise ValueError("Operator-profile evidence hash does not match")
        return self


def evaluate_operator_profile_gates(
    operator_input: OperatorAccessCapitalDataInput,
) -> list[OperatorProfileGateResult]:
    capital = operator_input.starting_trading_capital
    total_ratio = operator_input.maximum_total_loss / capital
    daily_ratio = operator_input.maximum_daily_loss / capital
    trade_ratio = operator_input.maximum_per_trade_loss / capital
    derivatives = operator_input.permitted_product_scope in {
        "SPOT_AND_PERPETUALS",
        "SPOT_PERPETUALS_AND_OPTIONS",
    }
    access_pass = (
        operator_input.account_status == "VERIFIED"
        and operator_input.api_access_status
        in {
            "DOCUMENTED_AVAILABLE_NOT_TESTED",
            "VERIFIED_READ_ONLY",
            "VERIFIED_ORDER_ENTRY_DISABLED",
        }
    )
    loss_pass = (
        operator_input.maximum_per_trade_loss
        <= operator_input.maximum_daily_loss
        <= operator_input.maximum_total_loss
        <= capital
        and trade_ratio <= MAX_PLANNING_RISK_PER_TRADE
        and daily_ratio <= MAX_PLANNING_DAILY_LOSS
        and total_ratio <= MAX_PLANNING_TOTAL_LOSS
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
    values = {
        "ACCOUNT_AND_API_ACCESS_PROVEN": (
            access_pass,
            (
                "The account is verified and API access is documented or verified."
                if access_pass
                else "A verified account and documented or verified API access "
                "are required before successor charter design."
            ),
        ),
        "CAPITAL_SOURCE_AND_RESERVE_SAFE": (
            (
                not operator_input.capital_is_borrowed
                and operator_input.capital_excludes_emergency_funds
            ),
            (
                "Capital is unborrowed and excludes emergency funds."
                if operator_input.capital_excludes_emergency_funds
                else "Trading capital must be unborrowed and separate from "
                "emergency funds."
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
        "LOSS_LIMITS_CAPITAL_PROTECTIVE": (
            loss_pass,
            (
                "Absolute limits are ordered and remain within 0.5 percent per "
                "trade, 1 percent daily, and 10 percent total."
                if loss_pass
                else "Loss limits must be ordered per-trade <= daily <= total <= "
                "capital and remain within 0.5 percent, 1 percent, and 10 percent."
            ),
        ),
        "NO_CREDENTIALS_OR_SECRETS": (
            not operator_input.credentials_stored_or_embedded,
            "The operator input stores no API key, private key, password, or secret.",
        ),
        "OPERATOR_ATTESTATION_COMPLETE": (
            (
                operator_input.attestation_statement
                == (
                    "I_ATTEST_THIS_PROFILE_IS_ACCURATE_AND_CONTAINS_NO_"
                    "CREDENTIALS"
                )
            ),
            "The named operator supplied the exact no-credentials attestation.",
        ),
        "PRODUCT_SCOPE_AND_LEVERAGE_SAFE": (
            (
                operator_input.maximum_effective_leverage <= 1
                and (
                    not derivatives
                    or (
                        operator_input.derivatives_access_confirmed
                        and operator_input.derivatives_suitability_acknowledged
                    )
                )
            ),
            (
                "Product scope is explicit, derivative attestations are consistent, "
                "and effective leverage is capped at 1x."
                if operator_input.maximum_effective_leverage <= 1
                else "Effective leverage above 1x is not permitted by this "
                "capital-protection profile."
            ),
        ),
        "SANDBOX_PATH_AVAILABLE": (
            operator_input.sandbox_access_status
            in {"DOCUMENTED_AVAILABLE_NOT_TESTED", "VERIFIED"},
            (
                "A sandbox or testnet path is documented or verified."
                if operator_input.sandbox_access_status
                in {"DOCUMENTED_AVAILABLE_NOT_TESTED", "VERIFIED"}
                else "A documented sandbox or testnet path is required before "
                "successor charter design."
            ),
        ),
        "VENUE_AND_JURISDICTION_BOUND": (
            (
                operator_input.legal_and_tax_obligations_acknowledged
                and bool(operator_input.intended_execution_venue)
                and bool(operator_input.jurisdiction)
            ),
            (
                "The exact venue and jurisdiction are named and legal/tax "
                "obligations are acknowledged."
                if operator_input.legal_and_tax_obligations_acknowledged
                else "Venue and jurisdiction require an explicit legal and tax "
                "obligations acknowledgement."
            ),
        ),
    }
    return [
        OperatorProfileGateResult(
            gate_id=gate_id,
            status="PASS" if values[gate_id][0] else "FAIL",
            reason=values[gate_id][1],
        )
        for gate_id in OPERATOR_PROFILE_GATE_IDS
    ]


def build_post_v4_operator_access_profile(
    *,
    frozen_at: datetime,
    post_v4_capability_review_evidence_hash: str,
    post_v4_capability_review_builder_hash: str,
    builder_contract_hash: str,
    operator_input: OperatorAccessCapitalDataInput,
    limitations: list[str],
) -> PostV4OperatorAccessProfile:
    gates = evaluate_operator_profile_gates(operator_input)
    failed = sorted(item.gate_id for item in gates if item.status == "FAIL")
    capital = operator_input.starting_trading_capital
    passing = not failed
    payload = {
        "schema_version": OPERATOR_PROFILE_SCHEMA_VERSION,
        "profile_id": "post-v4-operator-access-profile-v1",
        "profile_version": "1.0.0",
        "frozen_at": normalize_timestamp(frozen_at),
        "status": "FROZEN_OPERATOR_ATTESTATION_NO_CREDENTIALS",
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
            operator_input.maximum_total_loss / capital
        ).normalize(),
        "maximum_daily_loss_ratio": (
            operator_input.maximum_daily_loss / capital
        ).normalize(),
        "maximum_per_trade_loss_ratio": (
            operator_input.maximum_per_trade_loss / capital
        ).normalize(),
        "first_profit_milestone": FIRST_PROFIT_MILESTONE,
        "first_profit_milestone_to_capital_ratio": (
            FIRST_PROFIT_MILESTONE / capital
        ).normalize(),
        "gate_results": gates,
        "failed_gate_ids": failed,
        "decision": (
            OPERATOR_PROFILE_PASS_DECISION
            if passing
            else OPERATOR_PROFILE_FAIL_DECISION
        ),
        "successor_charter_design_authorized": passing,
        "successor_alpha_discovery_authorized": False,
        "network_requests_authorized": False,
        "market_data_import_authorized": False,
        "parameter_definition_authorized": False,
        "return_testing_authorized": False,
        "creates_candidate": False,
        "opens_development": False,
        "opens_validation": False,
        "opens_holdout": False,
        "opens_forward": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "stores_credentials": False,
        "limitations": sorted(set(limitations)),
    }
    return PostV4OperatorAccessProfile(
        **payload,
        profile_evidence_hash=universe_evidence_hash(payload),
    )


def audit_post_v4_operator_access_profile(
    profile: PostV4OperatorAccessProfile,
) -> bool:
    return profile.profile_evidence_hash == universe_evidence_hash(
        profile.model_dump(exclude={"profile_evidence_hash"})
    )
