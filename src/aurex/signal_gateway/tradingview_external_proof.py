import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.service import (
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
    strategy_parameter_fingerprint,
)
from aurex.domain.enums import SignalStatus
from aurex.signal_gateway.schemas import TradingViewVerificationResponse
from aurex.signal_gateway.tradingview_delivery import (
    TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS,
    TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL,
    tradingview_source_network_snapshot,
    tradingview_source_networks_sha256,
)

EXTERNAL_PROOF_ATTESTATION = (
    "I_ATTEST_THIS_IS_ONE_GENUINE_TRADINGVIEW_ALERT_LOG_RECORD_AND_CONTAINS_"
    "NO_CREDENTIALS"
)
EXPECTED_STRATEGY = "trend_pullback_v1"
EXPECTED_STRATEGY_VERSION = "1.3.0"
EXPECTED_SYMBOL = "BTCUSDT"
EXPECTED_TIMEFRAME = "15m"
EXPECTED_SETTINGS_FINGERPRINT = strategy_parameter_fingerprint(
    EXPECTED_STRATEGY,
    TREND_PULLBACK_V1_PARAMETER_TEMPLATE,
)
MAX_ALERT_LOG_ARTIFACT_BYTES = 25 * 1024 * 1024
MAX_ALERT_TO_RECEIPT_DELTA = timedelta(minutes=15)
MAX_SOURCE_AUTHORITY_AGE = timedelta(hours=24)
ALLOWED_ALERT_LOG_SUFFIXES = {
    ".csv",
    ".jpeg",
    ".jpg",
    ".json",
    ".pdf",
    ".png",
    ".txt",
}
PROOF_GATE_IDS = (
    "ALERT_LOG_ARTIFACT_BOUND",
    "ALERT_TO_RECEIPT_TIME_RECONCILED",
    "DELIVERY_RECEIPT_VERIFIED",
    "LIVE_AND_BROKER_SIDE_EFFECTS_ABSENT",
    "NO_CREDENTIALS_AND_OPERATOR_ATTESTED",
    "REJECTED_V1_3_SCOPE_BOUND",
    "RISK_REJECTION_TIMELINE_COMPLETE",
    "SOURCE_AUTHORITY_FRESH",
    "SOURCE_NETWORKS_AUTHORITY_MATCHED",
    "ZERO_PAPER_SIDE_EFFECTS",
)
_CREDENTIAL_PATTERNS = (
    "-----begin",
    "api_key=",
    "apikey=",
    "api-secret",
    "authorization: bearer",
    "private_key=",
    "secret_key=",
    "password=",
)


def _normalized_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _canonical_sha256(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def current_external_proof_builder_sha256() -> str:
    return sha256(Path(__file__).read_bytes()).hexdigest()


class TradingViewAlertLogClaim(BaseModel):
    alert_name: str = Field(min_length=2, max_length=160)
    alert_fired_at: datetime
    delivery_status: Literal["DELIVERED"]
    webhook_status_text: str = Field(min_length=2, max_length=240)

    model_config = ConfigDict(extra="forbid")

    @field_validator("alert_fired_at")
    @classmethod
    def normalize_alert_fired_at(cls, value: datetime) -> datetime:
        return _normalized_timestamp(value)

    @field_validator("alert_name", "webhook_status_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized


class TradingViewExternalProofOperatorInput(BaseModel):
    schema_version: Literal[
        "aurex-tradingview-external-proof-operator-input-v1"
    ] = "aurex-tradingview-external-proof-operator-input-v1"
    operator_identifier: str = Field(min_length=2, max_length=120)
    attested_at: datetime
    attestation_statement: Literal[EXTERNAL_PROOF_ATTESTATION]
    source_network_authority_checked_at: datetime
    source_network_authority_url: Literal[
        TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
    ]
    source_networks_observed: list[str] = Field(min_length=1, max_length=32)
    expected_signal_id: str = Field(min_length=8, max_length=120)
    alert_log_claim: TradingViewAlertLogClaim
    credentials_stored_or_embedded: Literal[False] = False

    model_config = ConfigDict(extra="forbid")

    @field_validator("attested_at", "source_network_authority_checked_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalized_timestamp(value)

    @field_validator("operator_identifier", "expected_signal_id")
    @classmethod
    def normalize_operator_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("operator identifier cannot be blank")
        return normalized


class AlertLogArtifactEvidence(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    suffix: str
    size_bytes: int = Field(gt=0, le=MAX_ALERT_LOG_ARTIFACT_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")


class ExternalProofGateResult(BaseModel):
    gate_id: str
    status: Literal["PASS", "FAIL"]
    evidence: str

    model_config = ConfigDict(extra="forbid")


class TradingViewExternalDeliveryProof(BaseModel):
    schema_version: Literal[
        "aurex-tradingview-external-delivery-proof-v1"
    ] = "aurex-tradingview-external-delivery-proof-v1"
    proof_id: str
    evaluated_at: datetime
    status: Literal["PASS", "FAIL"]
    decision: Literal[
        "ACCEPT_EXTERNAL_DELIVERY_PROOF_SAFE_REJECTION",
        "REJECT_EXTERNAL_DELIVERY_PROOF",
    ]
    operator_input: TradingViewExternalProofOperatorInput
    verification_snapshot: TradingViewVerificationResponse
    alert_log_artifact: AlertLogArtifactEvidence
    operator_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verification_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    builder_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    gates: list[ExternalProofGateResult]
    stage_3_external_delivery_proven: bool
    pipeline_verified: Literal[False] = False
    strategy_promoted: Literal[False] = False
    creates_paper_eligibility: Literal[False] = False
    creates_sandbox_eligibility: Literal[False] = False
    creates_live_eligibility: Literal[False] = False
    authorizes_live_trading: Literal[False] = False
    authorizes_capital: Literal[False] = False
    evidence_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    model_config = ConfigDict(extra="forbid")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalized_timestamp(value)

    @model_validator(mode="after")
    def verify_internal_hashes(self) -> "TradingViewExternalDeliveryProof":
        if tuple(sorted(gate.gate_id for gate in self.gates)) != PROOF_GATE_IDS:
            raise ValueError("external proof gate set is incomplete or unexpected")
        if self.operator_input_sha256 != _canonical_sha256(self.operator_input):
            raise ValueError("operator input hash does not match")
        if self.verification_snapshot_sha256 != _canonical_sha256(
            self.verification_snapshot
        ):
            raise ValueError("verification snapshot hash does not match")
        expected_status = (
            "PASS" if all(gate.status == "PASS" for gate in self.gates) else "FAIL"
        )
        if self.status != expected_status:
            raise ValueError("external proof status does not match gate results")
        expected_decision = (
            "ACCEPT_EXTERNAL_DELIVERY_PROOF_SAFE_REJECTION"
            if expected_status == "PASS"
            else "REJECT_EXTERNAL_DELIVERY_PROOF"
        )
        if self.decision != expected_decision:
            raise ValueError("external proof decision does not match status")
        if self.stage_3_external_delivery_proven != (expected_status == "PASS"):
            raise ValueError("Stage 3 proof flag does not match status")
        hash_payload = self.model_dump(mode="json", exclude={"evidence_hash"})
        if self.evidence_hash != _canonical_sha256(hash_payload):
            raise ValueError("external proof evidence hash does not match")
        return self


def build_alert_log_artifact_evidence(path: Path) -> AlertLogArtifactEvidence:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError("alert-log artifact does not exist or is not a file")
    suffix = resolved.suffix.lower()
    if suffix not in ALLOWED_ALERT_LOG_SUFFIXES:
        raise ValueError(
            "alert-log artifact must be CSV, image, JSON, PDF, or text evidence"
        )
    size_bytes = resolved.stat().st_size
    if size_bytes <= 0 or size_bytes > MAX_ALERT_LOG_ARTIFACT_BYTES:
        raise ValueError("alert-log artifact size is outside the accepted boundary")
    return AlertLogArtifactEvidence(
        filename=resolved.name,
        suffix=suffix,
        size_bytes=size_bytes,
        sha256=sha256(resolved.read_bytes()).hexdigest(),
    )


def _proof_checks(
    operator_input: TradingViewExternalProofOperatorInput,
    verification: TradingViewVerificationResponse,
    alert_log_artifact: AlertLogArtifactEvidence,
) -> dict[str, tuple[bool, str]]:
    checks = {check.check_key: check.status for check in verification.checks}
    delivery_checks_pass = all(
        checks.get(check_key) == "PASS"
        for check_key in (
            "webhook_shared_secret_authenticated",
            "webhook_payload_integrity_recorded",
            "tradingview_source_network_configuration_safe",
            "tradingview_source_ip_matched",
        )
    )
    safe_side_effect_checks_pass = all(
        checks.get(check_key) == "PASS"
        for check_key in (
            "live_trading_disabled",
            "live_order_intent_absent",
            "broker_execution_absent",
        )
    )
    scope_bound = (
        verification.latest_signal_id == operator_input.expected_signal_id
        and verification.strategy == EXPECTED_STRATEGY
        and verification.symbol == EXPECTED_SYMBOL
        and verification.latest_signal_strategy_version == EXPECTED_STRATEGY_VERSION
        and verification.latest_signal_timeframe == EXPECTED_TIMEFRAME
        and verification.latest_signal_settings_fingerprint
        == EXPECTED_SETTINGS_FINGERPRINT
    )
    delivery_verified = (
        verification.status == "DELIVERY_VERIFIED_PIPELINE_BLOCKED"
        and verification.delivery_verified
        and not verification.pipeline_verified
        and not verification.verified
        and delivery_checks_pass
        and verification.delivery_body_sha256 is not None
        and len(verification.delivery_body_sha256) == 64
        and (verification.delivery_body_size_bytes or 0) > 0
        and verification.delivery_request_method == "POST"
        and verification.delivery_request_path == "/webhooks/tradingview"
        and str(verification.delivery_content_type or "").lower().startswith(
            "application/json"
        )
    )
    risk_rejection_complete = (
        verification.latest_signal_status == SignalStatus.RISK_REJECTED
        and verification.risk_approved is False
        and verification.latest_risk_decision_id is not None
        and verification.signal_event_statuses
        == [
            SignalStatus.RECEIVED,
            SignalStatus.VALIDATED,
            SignalStatus.RISK_REJECTED,
        ]
        and not verification.missing_event_statuses
        and checks.get("risk_decision_approved") == "BLOCKED"
    )
    zero_paper = (
        verification.paper_order_id is None
        and verification.paper_trade_id is None
        and checks.get("paper_order_created") == "BLOCKED"
        and checks.get("paper_trade_opened") == "BLOCKED"
    )
    zero_live_and_broker = (
        not verification.live_trading_enabled
        and verification.live_execution_adapter == "disabled"
        and not verification.live_order_intent_ids
        and not verification.broker_order_ids
        and not verification.broker_fill_ids
        and safe_side_effect_checks_pass
    )
    alert_artifact_bound = (
        operator_input.alert_log_claim.delivery_status == "DELIVERED"
        and alert_log_artifact.suffix in ALLOWED_ALERT_LOG_SUFFIXES
        and 0 < alert_log_artifact.size_bytes <= MAX_ALERT_LOG_ARTIFACT_BYTES
        and len(alert_log_artifact.sha256) == 64
    )
    receipt_time = verification.latest_signal_received_at
    alert_time_reconciled = bool(
        receipt_time is not None
        and abs(receipt_time - operator_input.alert_log_claim.alert_fired_at)
        <= MAX_ALERT_TO_RECEIPT_DELTA
    )
    authority_time = operator_input.source_network_authority_checked_at
    authority_fresh = bool(
        receipt_time is not None
        and authority_time <= receipt_time
        and receipt_time - authority_time <= MAX_SOURCE_AUTHORITY_AGE
        and operator_input.source_network_authority_url
        == TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
    )
    authority_snapshot = tradingview_source_network_snapshot(
        ",".join(operator_input.source_networks_observed)
    )
    source_networks_matched = (
        authority_snapshot.configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
        and authority_snapshot.networks
        == TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS
        and list(authority_snapshot.networks)
        == verification.delivery_source_networks
        and authority_snapshot.networks_sha256
        == verification.delivery_source_networks_sha256
        and verification.delivery_source_networks_authority_url
        == TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
        and tradingview_source_networks_sha256(
            verification.delivery_source_networks
        )
        == verification.delivery_source_networks_sha256
    )
    serialized_input = json.dumps(
        operator_input.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).lower()
    no_credentials = (
        not operator_input.credentials_stored_or_embedded
        and operator_input.attestation_statement == EXTERNAL_PROOF_ATTESTATION
        and not any(pattern in serialized_input for pattern in _CREDENTIAL_PATTERNS)
    )
    return {
        "ALERT_LOG_ARTIFACT_BOUND": (
            alert_artifact_bound,
            (
                f"Alert-log artifact {alert_log_artifact.filename} is "
                f"{alert_log_artifact.size_bytes} bytes with SHA-256 "
                f"{alert_log_artifact.sha256}."
            ),
        ),
        "ALERT_TO_RECEIPT_TIME_RECONCILED": (
            alert_time_reconciled,
            (
                f"Alert fired at {operator_input.alert_log_claim.alert_fired_at}; "
                f"Aurex received at {receipt_time}."
            ),
        ),
        "DELIVERY_RECEIPT_VERIFIED": (
            delivery_verified,
            (
                f"Verification status {verification.status}; delivery "
                f"{verification.delivery_verified}; pipeline "
                f"{verification.pipeline_verified}; receipt "
                f"{verification.delivery_evidence_hash}."
            ),
        ),
        "LIVE_AND_BROKER_SIDE_EFFECTS_ABSENT": (
            zero_live_and_broker,
            (
                f"Live enabled {verification.live_trading_enabled}; adapter "
                f"{verification.live_execution_adapter}; intents "
                f"{verification.live_order_intent_ids}; broker orders "
                f"{verification.broker_order_ids}; fills "
                f"{verification.broker_fill_ids}."
            ),
        ),
        "NO_CREDENTIALS_AND_OPERATOR_ATTESTED": (
            no_credentials,
            "The operator input contains the exact no-credentials attestation.",
        ),
        "REJECTED_V1_3_SCOPE_BOUND": (
            scope_bound,
            (
                f"{verification.strategy} "
                f"{verification.latest_signal_strategy_version} "
                f"{verification.symbol} {verification.latest_signal_timeframe}; "
                f"settings {verification.latest_signal_settings_fingerprint}."
            ),
        ),
        "RISK_REJECTION_TIMELINE_COMPLETE": (
            risk_rejection_complete,
            (
                f"Signal {verification.latest_signal_id} status "
                f"{verification.latest_signal_status}; events "
                f"{[status.value for status in verification.signal_event_statuses]}."
            ),
        ),
        "SOURCE_AUTHORITY_FRESH": (
            authority_fresh,
            (
                f"Source authority checked at {authority_time}; receipt at "
                f"{receipt_time}; authority "
                f"{operator_input.source_network_authority_url}."
            ),
        ),
        "SOURCE_NETWORKS_AUTHORITY_MATCHED": (
            source_networks_matched,
            (
                f"Observed networks {list(authority_snapshot.networks)}; receipt "
                f"networks {verification.delivery_source_networks}; hash "
                f"{verification.delivery_source_networks_sha256}."
            ),
        ),
        "ZERO_PAPER_SIDE_EFFECTS": (
            zero_paper,
            (
                f"Paper order {verification.paper_order_id}; paper trade "
                f"{verification.paper_trade_id}."
            ),
        ),
    }


def build_tradingview_external_delivery_proof(
    operator_input: TradingViewExternalProofOperatorInput,
    verification_snapshot: TradingViewVerificationResponse,
    alert_log_artifact: AlertLogArtifactEvidence,
    *,
    evaluated_at: datetime | None = None,
) -> TradingViewExternalDeliveryProof:
    evaluated_at = _normalized_timestamp(evaluated_at or datetime.now(UTC))
    checks = _proof_checks(
        operator_input,
        verification_snapshot,
        alert_log_artifact,
    )
    gates = [
        ExternalProofGateResult(
            gate_id=gate_id,
            status="PASS" if checks[gate_id][0] else "FAIL",
            evidence=checks[gate_id][1],
        )
        for gate_id in PROOF_GATE_IDS
    ]
    passed = all(gate.status == "PASS" for gate in gates)
    payload = {
        "schema_version": "aurex-tradingview-external-delivery-proof-v1",
        "proof_id": (
            f"tradingview-external-proof-"
            f"{verification_snapshot.latest_signal_id or 'missing'}"
        ),
        "evaluated_at": evaluated_at,
        "status": "PASS" if passed else "FAIL",
        "decision": (
            "ACCEPT_EXTERNAL_DELIVERY_PROOF_SAFE_REJECTION"
            if passed
            else "REJECT_EXTERNAL_DELIVERY_PROOF"
        ),
        "operator_input": operator_input,
        "verification_snapshot": verification_snapshot,
        "alert_log_artifact": alert_log_artifact,
        "operator_input_sha256": _canonical_sha256(operator_input),
        "verification_snapshot_sha256": _canonical_sha256(
            verification_snapshot
        ),
        "builder_source_sha256": current_external_proof_builder_sha256(),
        "gates": gates,
        "stage_3_external_delivery_proven": passed,
        "pipeline_verified": False,
        "strategy_promoted": False,
        "creates_paper_eligibility": False,
        "creates_sandbox_eligibility": False,
        "creates_live_eligibility": False,
        "authorizes_live_trading": False,
        "authorizes_capital": False,
    }
    payload["evidence_hash"] = _canonical_sha256(
        TradingViewExternalDeliveryProof.model_construct(**payload).model_dump(
            mode="json",
            exclude={"evidence_hash"},
        )
    )
    return TradingViewExternalDeliveryProof.model_validate(payload)


def audit_tradingview_external_delivery_proof(
    proof: TradingViewExternalDeliveryProof,
    current_verification_snapshot: TradingViewVerificationResponse,
    alert_log_artifact: AlertLogArtifactEvidence,
) -> None:
    if proof.builder_source_sha256 != current_external_proof_builder_sha256():
        raise ValueError("external proof builder source hash does not match")
    if proof.alert_log_artifact != alert_log_artifact:
        raise ValueError("alert-log artifact evidence does not match frozen proof")
    if proof.verification_snapshot != current_verification_snapshot:
        raise ValueError("current database verification does not match frozen proof")
    rebuilt = build_tradingview_external_delivery_proof(
        proof.operator_input,
        current_verification_snapshot,
        alert_log_artifact,
        evaluated_at=proof.evaluated_at,
    )
    if rebuilt.model_dump(mode="json") != proof.model_dump(mode="json"):
        raise ValueError("external delivery proof reconstruction does not match")
