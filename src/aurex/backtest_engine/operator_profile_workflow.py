from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from aurex.backtest_engine.research_operator_access_profile import (
    FIRST_PROFIT_MILESTONE,
    MAX_PLANNING_DAILY_LOSS,
    MAX_PLANNING_RISK_PER_TRADE,
    MAX_PLANNING_TOTAL_LOSS,
    OPERATOR_PROFILE_GATE_IDS,
    OperatorAccessCapitalDataInput,
    OperatorProfileGateResult,
    PostV4OperatorAccessProfile,
    audit_post_v4_operator_access_profile,
    build_post_v4_operator_access_profile,
)
from aurex.backtest_engine.research_post_v4_capability_review import (
    PostV4CapabilityGapReview,
    audit_post_v4_capability_gap_review,
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
    / "post_v4_operator_access_profile_v1.json"
)
OPERATOR_PROFILE_INPUT_FILENAME = "aurex-operator-profile-input.json"
OPERATOR_PROFILE_FREEZE_COMMAND = (
    "python scripts/freeze_post_v4_operator_profile.py "
    '--freeze --input "<path-to-input.json>"'
)
OPERATOR_PROFILE_LIMITATIONS = [
    (
        "This profile is an operator attestation and planning boundary, not "
        "independent legal, tax, venue, account, or suitability verification."
    ),
    (
        "A passing profile authorizes only design of a separately frozen successor "
        "discovery charter; it does not authorize discovery execution."
    ),
    (
        "No API key, private key, password, bearer token, account number, or other "
        "credential may be stored in the input or frozen profile."
    ),
    (
        "The first 100 USD milestone is a measurement target and must never be used "
        "to increase risk, leverage, trade frequency, or loss limits."
    ),
    (
        "Free or paid data availability constrains which mechanisms may be proposed "
        "but does not imply that any mechanism has positive edge."
    ),
    (
        "A documented sandbox path does not constitute sandbox qualification or "
        "live readiness."
    ),
    (
        "A verified account and API access do not authorize order entry, credentials "
        "storage, live trading, or capital deployment."
    ),
    (
        "No network request, market-data import, parameter, return, candidate, "
        "development, validation, paper eligibility, sandbox eligibility, live "
        "eligibility, or capital permission is created."
    ),
]


class OperatorProfileStatusResponse(BaseModel):
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
    total_gate_count: int = len(OPERATOR_PROFILE_GATE_IDS)
    successor_charter_design_authorized: bool = False
    successor_alpha_discovery_authorized: Literal[False] = False
    paper_trading_authorized: Literal[False] = False
    live_trading_authorized: Literal[False] = False
    freeze_via_independent_cli_only: Literal[True] = True

    model_config = ConfigDict(extra="forbid")


class OperatorProfileTemplateResponse(BaseModel):
    schema_version: Literal["aurex-operator-profile-workflow-v1"] = (
        "aurex-operator-profile-workflow-v1"
    )
    generated_at: datetime
    input_filename: str = OPERATOR_PROFILE_INPUT_FILENAME
    input_template: dict[str, Any]
    gate_ids: list[str]
    maximum_per_trade_loss_ratio: Decimal
    maximum_daily_loss_ratio: Decimal
    maximum_total_loss_ratio: Decimal
    first_profit_milestone: Decimal
    freeze_command: str = OPERATOR_PROFILE_FREEZE_COMMAND
    writes_performed: Literal[False] = False

    model_config = ConfigDict(extra="forbid")


class OperatorProfilePreflightResponse(BaseModel):
    schema_version: Literal["aurex-operator-profile-preflight-v1"] = (
        "aurex-operator-profile-preflight-v1"
    )
    status: Literal["PASS", "BLOCKED"]
    decision: str
    attested_at: datetime
    input_evidence_hash: str
    profile_evidence_hash: str
    gate_results: list[OperatorProfileGateResult]
    failed_gate_ids: list[str]
    passed_gate_count: int
    total_gate_count: int
    maximum_total_loss_ratio: Decimal
    maximum_daily_loss_ratio: Decimal
    maximum_per_trade_loss_ratio: Decimal
    first_profit_milestone: Decimal
    first_profit_milestone_to_capital_ratio: Decimal
    successor_charter_design_authorized: bool
    successor_alpha_discovery_authorized: Literal[False] = False
    network_requests_authorized: Literal[False] = False
    return_testing_authorized: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    writes_performed: Literal[False] = False
    frozen_artifact_exists: bool
    next_action: Literal[
        "CORRECT_OPERATOR_INPUT",
        "RUN_INDEPENDENT_CLI_FREEZE",
        "AUDIT_EXISTING_FROZEN_PROFILE",
    ]
    input_filename: str = OPERATOR_PROFILE_INPUT_FILENAME
    freeze_command: str = OPERATOR_PROFILE_FREEZE_COMMAND
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


def operator_profile_builder_contract_hash() -> str:
    return source_contract_hash(
        [
            PROJECT_ROOT / "scripts" / "freeze_post_v4_operator_profile.py",
            Path(__file__).resolve(),
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "research_operator_access_profile.py",
        ]
    )


def operator_profile_template_payload(
    *,
    attested_at: str = "YYYY-MM-DDTHH:MM:SS+00:00",
) -> dict[str, Any]:
    return {
        "schema_version": "aurex-post-v4-operator-access-input-v1",
        "attested_at": attested_at,
        "operator_identifier": "NON_SECRET_OPERATOR_ALIAS",
        "attestation_statement": (
            "I_ATTEST_THIS_PROFILE_IS_ACCURATE_AND_CONTAINS_NO_CREDENTIALS"
        ),
        "jurisdiction": "COUNTRY_OR_JURISDICTION",
        "intended_execution_venue": "EXACT_EXCHANGE_NAME",
        "account_identifier_alias": "NON_SECRET_ACCOUNT_ALIAS_NOT_ACCOUNT_NUMBER",
        "account_status": "VERIFIED",
        "api_access_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "sandbox_access_status": "DOCUMENTED_AVAILABLE_NOT_TESTED",
        "permitted_product_scope": "SPOT_ONLY",
        "other_product_scope": None,
        "derivatives_access_confirmed": False,
        "derivatives_suitability_acknowledged": False,
        "maximum_effective_leverage": "1",
        "legal_and_tax_obligations_acknowledged": False,
        "starting_trading_capital": "0.00",
        "capital_currency": "USD",
        "capital_is_borrowed": False,
        "capital_excludes_emergency_funds": False,
        "maximum_total_loss": "0.00",
        "maximum_daily_loss": "0.00",
        "maximum_per_trade_loss": "0.00",
        "one_time_data_budget": "0.00",
        "monthly_data_budget": "0.00",
        "data_budget_currency": "USD",
        "paid_data_permitted": False,
        "venue_terms_reference": (
            "OFFICIAL_TERMS_URL_OR_LOCAL_EVIDENCE_REFERENCE"
        ),
        "fee_schedule_reference": (
            "OFFICIAL_FEE_SCHEDULE_URL_OR_LOCAL_EVIDENCE_REFERENCE"
        ),
        "api_documentation_reference": (
            "OFFICIAL_API_DOCUMENTATION_URL_OR_LOCAL_EVIDENCE_REFERENCE"
        ),
        "product_access_evidence_reference": (
            "OPERATOR_ATTESTATION_OR_NON_SECRET_LOCAL_EVIDENCE_REFERENCE"
        ),
        "sandbox_evidence_reference": (
            "OFFICIAL_SANDBOX_DOCUMENTATION_OR_LOCAL_EVIDENCE_REFERENCE"
        ),
        "capital_source_attestation_reference": (
            "NON_SECRET_OPERATOR_ATTESTATION_REFERENCE"
        ),
        "data_budget_attestation_reference": (
            "NON_SECRET_OPERATOR_ATTESTATION_REFERENCE"
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


def build_operator_profile_preflight(
    operator_input: OperatorAccessCapitalDataInput,
    *,
    review_path: Path = DEFAULT_REVIEW_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> OperatorProfilePreflightResponse:
    review = load_post_v4_capability_review(review_path)
    profile = build_post_v4_operator_access_profile(
        frozen_at=operator_input.attested_at,
        post_v4_capability_review_evidence_hash=review.review_evidence_hash,
        post_v4_capability_review_builder_hash=review.builder_contract_hash,
        builder_contract_hash=operator_profile_builder_contract_hash(),
        operator_input=operator_input,
        limitations=OPERATOR_PROFILE_LIMITATIONS,
    )
    output_exists = output_path.is_file()
    if output_exists:
        next_action = "AUDIT_EXISTING_FROZEN_PROFILE"
    elif profile.successor_charter_design_authorized:
        next_action = "RUN_INDEPENDENT_CLI_FREEZE"
    else:
        next_action = "CORRECT_OPERATOR_INPUT"
    return OperatorProfilePreflightResponse(
        status=(
            "PASS" if profile.successor_charter_design_authorized else "BLOCKED"
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
        first_profit_milestone=profile.first_profit_milestone,
        first_profit_milestone_to_capital_ratio=(
            profile.first_profit_milestone_to_capital_ratio
        ),
        successor_charter_design_authorized=(
            profile.successor_charter_design_authorized
        ),
        frozen_artifact_exists=output_exists,
        next_action=next_action,
        limitations=profile.limitations,
    )


def operator_profile_status(
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> OperatorProfileStatusResponse:
    try:
        relative_path = output_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        relative_path = str(output_path)
    if not output_path.is_file():
        return OperatorProfileStatusResponse(
            workflow_status="INPUT_REQUIRED",
            artifact_path=relative_path,
            artifact_exists=False,
            artifact_verified=False,
        )
    try:
        profile = PostV4OperatorAccessProfile.model_validate_json(
            output_path.read_text(encoding="utf-8")
        )
        verified = (
            audit_post_v4_operator_access_profile(profile)
            and profile.builder_contract_hash
            == operator_profile_builder_contract_hash()
        )
    except (OSError, ValueError):
        profile = None
        verified = False
    if not verified or profile is None:
        return OperatorProfileStatusResponse(
            workflow_status="FROZEN_INVALID",
            artifact_path=relative_path,
            artifact_exists=True,
            artifact_verified=False,
        )
    return OperatorProfileStatusResponse(
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
        successor_charter_design_authorized=(
            profile.successor_charter_design_authorized
        ),
    )


def operator_profile_template_response() -> OperatorProfileTemplateResponse:
    generated_at = datetime.now(UTC)
    return OperatorProfileTemplateResponse(
        generated_at=generated_at,
        input_template=operator_profile_template_payload(
            attested_at=generated_at.isoformat()
        ),
        gate_ids=OPERATOR_PROFILE_GATE_IDS,
        maximum_per_trade_loss_ratio=MAX_PLANNING_RISK_PER_TRADE,
        maximum_daily_loss_ratio=MAX_PLANNING_DAILY_LOSS,
        maximum_total_loss_ratio=MAX_PLANNING_TOTAL_LOSS,
        first_profit_milestone=FIRST_PROFIT_MILESTONE,
    )
