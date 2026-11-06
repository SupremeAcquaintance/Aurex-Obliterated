from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from aurex.backtest_engine.research_post_v4_capability_review import (
    PostV4CapabilityGapReview,
    audit_post_v4_capability_gap_review,
)
from aurex.backtest_engine.research_sandbox_capability_profile import (
    SANDBOX_PROFILE_GATE_IDS,
    BinanceSpotTestnetSandboxInput,
    BinanceSpotTestnetSandboxProfile,
    SandboxCapabilityGateResult,
    audit_binance_spot_testnet_sandbox_profile,
    build_binance_spot_testnet_sandbox_profile,
)
from aurex.backtest_engine.universe import universe_evidence_hash

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REVIEW_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "post_v4_capability_gap_review_v1.json"
)
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "binance_spot_testnet_sandbox_profile_v1.json"
)
SANDBOX_PROFILE_INPUT_FILENAME = "aurex-binance-spot-testnet-input.json"
SANDBOX_PROFILE_FREEZE_COMMAND = (
    "python scripts/freeze_binance_spot_testnet_profile.py "
    '--freeze --input "<path-to-input.json>"'
)
SANDBOX_PROFILE_LIMITATIONS = [
    (
        "This profile records a Binance Spot Testnet capability boundary, not a "
        "production Binance account or identity verification."
    ),
    (
        "GitHub authentication to Spot Testnet does not establish Binance production "
        "account access, venue authorization, or Zimbabwe legal compliance."
    ),
    (
        "Testnet funds, orders, fills, balances, and profit or loss are virtual and "
        "cannot prove a real strategy edge."
    ),
    (
        "Binance may reset Spot Testnet state periodically without advance notice; "
        "Aurex must preserve its own immutable request and reconciliation evidence."
    ),
    (
        "No API key, secret, GitHub identity, production account identifier, or "
        "credential may be stored in the input or frozen profile."
    ),
    (
        "A passing profile authorizes sandbox adapter implementation, official "
        "Testnet requests, virtual orders, and successor charter design only."
    ),
    (
        "A passing profile does not qualify the adapter, create a candidate, accept "
        "a backtest, authorize paper trading, or authorize live trading."
    ),
    (
        "The simulated 100 USD equity and loss limits are test controls, not real "
        "capital deployment or a promise of profit."
    ),
    (
        "Real market performance must use independently audited production market "
        "data and Aurex evidence gates, never Testnet profit or fill quality."
    ),
    (
        "Production qualification, real capital, micro-live trading, and the first "
        "settled 100 USD milestone remain deferred and explicitly unauthorized."
    ),
]


class SandboxProfileStatusResponse(BaseModel):
    workflow_status: Literal[
        "INPUT_REQUIRED",
        "FROZEN_VERIFIED",
        "FROZEN_INVALID",
    ]
    artifact_path: str
    artifact_exists: bool
    artifact_verified: bool
    profile_evidence_hash: str | None = None
    frozen_at: datetime | None = None
    decision: str | None = None
    passed_gate_count: int = 0
    total_gate_count: int = len(SANDBOX_PROFILE_GATE_IDS)
    sandbox_adapter_implementation_authorized: bool = False
    successor_charter_design_authorized: bool = False
    testnet_network_requests_authorized: bool = False
    testnet_virtual_order_entry_authorized: bool = False
    sandbox_qualified: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    real_capital_authorized: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class SandboxProfileTemplateResponse(BaseModel):
    schema_version: Literal["aurex-sandbox-profile-workflow-v1"] = (
        "aurex-sandbox-profile-workflow-v1"
    )
    generated_at: datetime
    input_filename: str = SANDBOX_PROFILE_INPUT_FILENAME
    input_template: dict[str, Any]
    gate_ids: list[str]
    freeze_command: str = SANDBOX_PROFILE_FREEZE_COMMAND
    writes_performed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class SandboxProfilePreflightResponse(BaseModel):
    schema_version: Literal["aurex-sandbox-profile-preflight-v1"] = (
        "aurex-sandbox-profile-preflight-v1"
    )
    status: Literal["PASS", "BLOCKED"]
    decision: str
    attested_at: datetime
    input_evidence_hash: str
    profile_evidence_hash: str
    gate_results: list[SandboxCapabilityGateResult]
    failed_gate_ids: list[str]
    passed_gate_count: int
    total_gate_count: int
    maximum_total_loss_ratio: Decimal
    maximum_daily_loss_ratio: Decimal
    maximum_per_trade_loss_ratio: Decimal
    sandbox_adapter_implementation_authorized: bool
    successor_charter_design_authorized: bool
    testnet_network_requests_authorized: bool
    testnet_virtual_order_entry_authorized: bool
    sandbox_qualified: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    real_capital_authorized: Literal[False] = False
    writes_performed: Literal[False] = False
    frozen_artifact_exists: bool
    next_action: Literal[
        "CORRECT_SANDBOX_INPUT",
        "RUN_INDEPENDENT_CLI_FREEZE",
        "AUDIT_EXISTING_FROZEN_PROFILE",
    ]
    input_filename: str = SANDBOX_PROFILE_INPUT_FILENAME
    freeze_command: str = SANDBOX_PROFILE_FREEZE_COMMAND
    limitations: list[str]

    model_config = ConfigDict(extra="forbid")


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }
        }
    )


def sandbox_profile_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_binance_spot_testnet_profile.py",
            Path(__file__).resolve(),
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_sandbox_capability_profile.py",
        ]
    )


def sandbox_profile_template_payload(
    *,
    attested_at: str = "YYYY-MM-DDTHH:MM:SS+00:00",
) -> dict[str, Any]:
    return {
        "schema_version": "aurex-binance-spot-testnet-input-v1",
        "attested_at": attested_at,
        "operator_identifier": "NON_SECRET_OPERATOR_ALIAS",
        "attestation_statement": (
            "I_ATTEST_BINANCE_SPOT_TESTNET_ACCESS_IS_AUTHENTICATED_AND_"
            "NO_CREDENTIALS_ARE_INCLUDED"
        ),
        "jurisdiction": "Zimbabwe",
        "sandbox_venue": "Binance Spot Test Network",
        "sandbox_environment": "TESTNET",
        "account_identifier_alias": "aurex_binance_spot_testnet",
        "authentication_method": "GITHUB_OAUTH",
        "testnet_access_status": "AUTHENTICATED",
        "api_credential_path_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "testnet_rest_base_url": "https://testnet.binance.vision/api",
        "testnet_ws_api_url": (
            "wss://ws-api.testnet.binance.vision/ws-api/v3"
        ),
        "testnet_stream_url": "wss://stream.testnet.binance.vision/ws",
        "permitted_product_scope": "SPOT_ONLY",
        "permitted_symbols": ["BTCUSDT"],
        "maximum_effective_leverage": "1",
        "simulated_starting_equity": "100.00",
        "equity_currency": "USD",
        "maximum_total_loss": "10.00",
        "maximum_daily_loss": "1.00",
        "maximum_per_trade_loss": "0.50",
        "one_time_data_budget": "0.00",
        "monthly_data_budget": "0.00",
        "data_budget_currency": "USD",
        "paid_data_permitted": False,
        "testnet_funds_are_virtual_acknowledged": True,
        "testnet_monthly_reset_behavior_acknowledged": True,
        "testnet_performance_is_not_edge_evidence_acknowledged": True,
        "production_account_verified": False,
        "production_api_authorized": False,
        "real_capital_authorized": False,
        "live_trading_authorized": False,
        "testnet_documentation_reference": "https://testnet.binance.vision/",
        "api_documentation_reference": (
            "https://developers.binance.com/en/docs/products/spot/rest-api"
        ),
        "fee_schedule_reference": "https://www.binance.com/en/fee/trading",
        "access_attestation_reference": (
            "operator-attestation:testnet-authenticated"
        ),
        "risk_attestation_reference": (
            "operator-attestation:100-usd-simulated-risk-boundary"
        ),
        "data_budget_attestation_reference": (
            "operator-attestation:zero-usd-initial-data-budget"
        ),
        "credentials_stored_or_embedded": False,
    }


def load_post_v4_capability_review(
    path: Path = DEFAULT_REVIEW_PATH,
) -> PostV4CapabilityGapReview:
    if not path.is_file():
        raise ValueError("Post-V4 capability review is missing")
    review = PostV4CapabilityGapReview.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    if (
        not audit_post_v4_capability_gap_review(review)
        or review.successor_discovery_authorized
        or review.creates_candidate
    ):
        raise ValueError("Post-V4 capability review audit failed")
    return review


def build_sandbox_profile_preflight(
    operator_input: BinanceSpotTestnetSandboxInput,
    *,
    review_path: Path = DEFAULT_REVIEW_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> SandboxProfilePreflightResponse:
    review = load_post_v4_capability_review(review_path)
    profile = build_binance_spot_testnet_sandbox_profile(
        frozen_at=operator_input.attested_at,
        post_v4_capability_review_evidence_hash=review.review_evidence_hash,
        post_v4_capability_review_builder_hash=review.builder_contract_hash,
        builder_contract_hash=sandbox_profile_builder_contract_hash(),
        operator_input=operator_input,
        limitations=SANDBOX_PROFILE_LIMITATIONS,
    )
    output_exists = output_path.is_file()
    if output_exists:
        next_action = "AUDIT_EXISTING_FROZEN_PROFILE"
    elif profile.sandbox_adapter_implementation_authorized:
        next_action = "RUN_INDEPENDENT_CLI_FREEZE"
    else:
        next_action = "CORRECT_SANDBOX_INPUT"
    return SandboxProfilePreflightResponse(
        status=(
            "PASS"
            if profile.sandbox_adapter_implementation_authorized
            else "BLOCKED"
        ),
        decision=profile.decision,
        attested_at=profile.operator_input.attested_at,
        input_evidence_hash=profile.operator_input_evidence_hash,
        profile_evidence_hash=profile.profile_evidence_hash,
        gate_results=profile.gate_results,
        failed_gate_ids=profile.failed_gate_ids,
        passed_gate_count=sum(
            gate.status == "PASS" for gate in profile.gate_results
        ),
        total_gate_count=len(profile.gate_results),
        maximum_total_loss_ratio=profile.maximum_total_loss_ratio,
        maximum_daily_loss_ratio=profile.maximum_daily_loss_ratio,
        maximum_per_trade_loss_ratio=profile.maximum_per_trade_loss_ratio,
        sandbox_adapter_implementation_authorized=(
            profile.sandbox_adapter_implementation_authorized
        ),
        successor_charter_design_authorized=(
            profile.successor_charter_design_authorized
        ),
        testnet_network_requests_authorized=(
            profile.testnet_network_requests_authorized
        ),
        testnet_virtual_order_entry_authorized=(
            profile.testnet_virtual_order_entry_authorized
        ),
        frozen_artifact_exists=output_exists,
        next_action=next_action,
        limitations=profile.limitations,
    )


def sandbox_profile_status(
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> SandboxProfileStatusResponse:
    try:
        relative_path = output_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        relative_path = str(output_path)
    if not output_path.is_file():
        return SandboxProfileStatusResponse(
            workflow_status="INPUT_REQUIRED",
            artifact_path=relative_path,
            artifact_exists=False,
            artifact_verified=False,
        )
    try:
        profile = BinanceSpotTestnetSandboxProfile.model_validate_json(
            output_path.read_text(encoding="utf-8")
        )
        verified = (
            audit_binance_spot_testnet_sandbox_profile(profile)
            and profile.builder_contract_hash
            == sandbox_profile_builder_contract_hash()
        )
    except (OSError, ValueError):
        profile = None
        verified = False
    if not verified or profile is None:
        return SandboxProfileStatusResponse(
            workflow_status="FROZEN_INVALID",
            artifact_path=relative_path,
            artifact_exists=True,
            artifact_verified=False,
        )
    return SandboxProfileStatusResponse(
        workflow_status="FROZEN_VERIFIED",
        artifact_path=relative_path,
        artifact_exists=True,
        artifact_verified=True,
        profile_evidence_hash=profile.profile_evidence_hash,
        frozen_at=profile.frozen_at,
        decision=profile.decision,
        passed_gate_count=sum(
            gate.status == "PASS" for gate in profile.gate_results
        ),
        sandbox_adapter_implementation_authorized=(
            profile.sandbox_adapter_implementation_authorized
        ),
        successor_charter_design_authorized=(
            profile.successor_charter_design_authorized
        ),
        testnet_network_requests_authorized=(
            profile.testnet_network_requests_authorized
        ),
        testnet_virtual_order_entry_authorized=(
            profile.testnet_virtual_order_entry_authorized
        ),
    )


def sandbox_profile_template_response() -> SandboxProfileTemplateResponse:
    generated_at = datetime.now(UTC)
    return SandboxProfileTemplateResponse(
        generated_at=generated_at,
        input_template=sandbox_profile_template_payload(
            attested_at=generated_at.isoformat()
        ),
        gate_ids=SANDBOX_PROFILE_GATE_IDS,
    )
