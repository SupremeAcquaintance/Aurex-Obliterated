import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

import scripts.freeze_tradingview_external_delivery_proof as proof_cli
from aurex.domain.enums import SignalStatus
from aurex.signal_gateway.schemas import (
    TradingViewVerificationCheck,
    TradingViewVerificationResponse,
)
from aurex.signal_gateway.tradingview_delivery import (
    TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS,
    TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL,
    tradingview_source_networks_sha256,
)
from aurex.signal_gateway.tradingview_external_proof import (
    EXPECTED_SETTINGS_FINGERPRINT,
    EXTERNAL_PROOF_ATTESTATION,
    AlertLogArtifactEvidence,
    TradingViewAlertLogClaim,
    TradingViewExternalDeliveryProof,
    TradingViewExternalProofOperatorInput,
    audit_tradingview_external_delivery_proof,
    build_alert_log_artifact_evidence,
    build_tradingview_external_delivery_proof,
)

RECEIVED_AT = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)


def verification_check(check_key: str, status: str) -> TradingViewVerificationCheck:
    return TradingViewVerificationCheck(
        check_key=check_key,
        status=status,
        evidence=f"{check_key} {status}",
        next_action="Preserve evidence.",
    )


def valid_verification() -> TradingViewVerificationResponse:
    networks = list(TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS)
    return TradingViewVerificationResponse(
        strategy="trend_pullback_v1",
        symbol="BTCUSDT",
        status="DELIVERY_VERIFIED_PIPELINE_BLOCKED",
        verified=False,
        delivery_verified=True,
        pipeline_verified=False,
        latest_signal_id="signal-external-proof-001",
        latest_signal_status=SignalStatus.RISK_REJECTED,
        latest_risk_decision_id="risk-external-proof-001",
        risk_approved=False,
        paper_order_id=None,
        paper_trade_id=None,
        provenance_status="BLOCKED",
        delivery_auth_status="SHARED_SECRET_VALIDATED",
        delivery_auth_transport="query",
        delivery_origin_status="TRADINGVIEW_SOURCE_IP_MATCHED",
        delivery_remote_ip="52.89.214.238",
        delivery_evidence_hash="a" * 64,
        delivery_source_network_configuration_status=(
            "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
        ),
        delivery_source_networks=networks,
        delivery_source_networks_sha256=tradingview_source_networks_sha256(
            networks
        ),
        delivery_source_networks_authority_url=(
            TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
        ),
        signal_event_statuses=[
            SignalStatus.RECEIVED,
            SignalStatus.VALIDATED,
            SignalStatus.RISK_REJECTED,
        ],
        missing_event_statuses=[],
        checks=[
            verification_check("webhook_shared_secret_authenticated", "PASS"),
            verification_check("webhook_payload_integrity_recorded", "PASS"),
            verification_check(
                "tradingview_source_network_configuration_safe",
                "PASS",
            ),
            verification_check("tradingview_source_ip_matched", "PASS"),
            verification_check("latest_signal_received", "PASS"),
            verification_check("live_trading_disabled", "PASS"),
            verification_check("signal_event_timeline_complete", "PASS"),
            verification_check("risk_decision_approved", "BLOCKED"),
            verification_check("signal_provenance_matched", "BLOCKED"),
            verification_check("paper_order_created", "BLOCKED"),
            verification_check("paper_trade_opened", "BLOCKED"),
            verification_check("live_order_intent_absent", "PASS"),
            verification_check("broker_execution_absent", "PASS"),
        ],
        next_action="Freeze external delivery evidence.",
        mutates_ledger=False,
        live_trading_enabled=False,
        live_execution_adapter="disabled",
        latest_signal_source_timestamp=RECEIVED_AT - timedelta(minutes=1),
        latest_signal_received_at=RECEIVED_AT,
        latest_signal_idempotency_key="idempotency-external-proof-001",
        latest_signal_strategy_version="1.3.0",
        latest_signal_settings_fingerprint=EXPECTED_SETTINGS_FINGERPRINT,
        latest_signal_timeframe="15m",
        delivery_body_sha256="b" * 64,
        delivery_body_size_bytes=512,
        delivery_request_method="POST",
        delivery_request_path="/webhooks/tradingview",
        delivery_content_type="application/json",
        delivery_user_agent="TradingView",
        live_order_intent_ids=[],
        broker_order_ids=[],
        broker_fill_ids=[],
    )


def valid_operator_input() -> TradingViewExternalProofOperatorInput:
    return TradingViewExternalProofOperatorInput(
        operator_identifier="operator-aurex",
        attested_at=RECEIVED_AT + timedelta(minutes=1),
        attestation_statement=EXTERNAL_PROOF_ATTESTATION,
        source_network_authority_checked_at=RECEIVED_AT
        - timedelta(minutes=30),
        source_network_authority_url=TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL,
        source_networks_observed=list(
            TRADINGVIEW_DOCUMENTED_IPV4_HOST_NETWORKS
        ),
        expected_signal_id="signal-external-proof-001",
        alert_log_claim=TradingViewAlertLogClaim(
            alert_name="Aurex external proof",
            alert_fired_at=RECEIVED_AT - timedelta(seconds=5),
            delivery_status="DELIVERED",
            webhook_status_text="Webhook delivered",
        ),
        credentials_stored_or_embedded=False,
    )


def valid_artifact() -> AlertLogArtifactEvidence:
    return AlertLogArtifactEvidence(
        filename="tradingview-alert-log.png",
        suffix=".png",
        size_bytes=4096,
        sha256="c" * 64,
    )


def test_external_delivery_safe_rejection_proof_passes_all_gates() -> None:
    verification = valid_verification()
    artifact = valid_artifact()
    proof = build_tradingview_external_delivery_proof(
        valid_operator_input(),
        verification,
        artifact,
        evaluated_at=RECEIVED_AT + timedelta(minutes=2),
    )

    assert proof.status == "PASS"
    assert proof.decision == "ACCEPT_EXTERNAL_DELIVERY_PROOF_SAFE_REJECTION"
    assert proof.stage_3_external_delivery_proven is True
    assert {gate.status for gate in proof.gates} == {"PASS"}
    assert proof.pipeline_verified is False
    assert proof.strategy_promoted is False
    assert proof.creates_paper_eligibility is False
    assert proof.creates_live_eligibility is False
    assert proof.authorizes_capital is False
    audit_tradingview_external_delivery_proof(
        proof,
        verification,
        artifact,
    )


@pytest.mark.parametrize(
    ("mutation", "failed_gate"),
    [
        ("paper_order", "ZERO_PAPER_SIDE_EFFECTS"),
        ("live_intent", "LIVE_AND_BROKER_SIDE_EFFECTS_ABSENT"),
        ("stale_alert", "ALERT_TO_RECEIPT_TIME_RECONCILED"),
        ("stale_authority", "SOURCE_AUTHORITY_FRESH"),
        ("broad_network", "SOURCE_NETWORKS_AUTHORITY_MATCHED"),
    ],
)
def test_external_delivery_proof_rejects_unsafe_or_unreconciled_evidence(
    mutation: str,
    failed_gate: str,
) -> None:
    verification = valid_verification()
    operator_input = valid_operator_input()
    if mutation == "paper_order":
        verification.paper_order_id = "paper-order-unexpected"
    elif mutation == "live_intent":
        verification.live_order_intent_ids = ["intent-unexpected"]
    elif mutation == "stale_alert":
        operator_input.alert_log_claim.alert_fired_at = RECEIVED_AT - timedelta(
            hours=1
        )
    elif mutation == "stale_authority":
        operator_input.source_network_authority_checked_at = RECEIVED_AT - timedelta(
            days=2
        )
    elif mutation == "broad_network":
        operator_input.source_networks_observed = ["52.89.214.0/24"]

    proof = build_tradingview_external_delivery_proof(
        operator_input,
        verification,
        valid_artifact(),
    )

    gates = {gate.gate_id: gate.status for gate in proof.gates}
    assert proof.status == "FAIL"
    assert proof.stage_3_external_delivery_proven is False
    assert gates[failed_gate] == "FAIL"


def test_external_delivery_proof_detects_record_and_database_drift() -> None:
    verification = valid_verification()
    artifact = valid_artifact()
    proof = build_tradingview_external_delivery_proof(
        valid_operator_input(),
        verification,
        artifact,
    )
    tampered = proof.model_dump(mode="json")
    tampered["decision"] = "REJECT_EXTERNAL_DELIVERY_PROOF"

    with pytest.raises(ValidationError, match="decision does not match"):
        TradingViewExternalDeliveryProof.model_validate(tampered)

    changed_verification = valid_verification()
    changed_verification.delivery_body_size_bytes = 513
    with pytest.raises(ValueError, match="current database verification"):
        audit_tradingview_external_delivery_proof(
            proof,
            changed_verification,
            artifact,
        )


def test_alert_log_artifact_is_hashed_and_size_bounded(tmp_path: Path) -> None:
    artifact_path = tmp_path / "alert-log.png"
    artifact_path.write_bytes(b"sanitized-alert-log-evidence")

    evidence = build_alert_log_artifact_evidence(artifact_path)

    assert evidence.filename == "alert-log.png"
    assert evidence.size_bytes == len(b"sanitized-alert-log-evidence")
    assert len(evidence.sha256) == 64

    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="size"):
        build_alert_log_artifact_evidence(empty)

    unsupported = tmp_path / "alert-log.exe"
    unsupported.write_bytes(b"not accepted")
    with pytest.raises(ValueError, match="must be"):
        build_alert_log_artifact_evidence(unsupported)


def test_external_delivery_proof_cli_preflights_freezes_and_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operator_input_path = tmp_path / "operator-input.json"
    operator_input_path.write_text(
        valid_operator_input().model_dump_json(indent=2),
        encoding="utf-8",
    )
    alert_log_path = tmp_path / "alert-log.png"
    alert_log_path.write_bytes(b"sanitized-genuine-alert-log-placeholder")
    output_path = tmp_path / "external-proof.json"
    verification = valid_verification()
    monkeypatch.setattr(
        proof_cli,
        "current_database_verification",
        lambda: verification,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freeze_tradingview_external_delivery_proof.py",
            "--preflight",
            "--input",
            str(operator_input_path),
            "--alert-log",
            str(alert_log_path),
            "--output",
            str(output_path),
        ],
    )
    assert proof_cli.run() == 0
    assert not output_path.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freeze_tradingview_external_delivery_proof.py",
            "--freeze",
            "--input",
            str(operator_input_path),
            "--alert-log",
            str(alert_log_path),
            "--output",
            str(output_path),
        ],
    )
    assert proof_cli.run() == 0
    assert output_path.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freeze_tradingview_external_delivery_proof.py",
            "--check",
            "--output",
            str(output_path),
            "--alert-log",
            str(alert_log_path),
        ],
    )
    assert proof_cli.run() == 0
