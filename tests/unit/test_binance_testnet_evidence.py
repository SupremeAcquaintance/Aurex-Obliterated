import json
from datetime import UTC, datetime
from pathlib import Path

from aurex.broker_engine.binance_testnet_evidence import (
    BinanceFillFeeEvidenceAudit,
    audit_fill_fee_evidence_audit,
    binance_testnet_qualification_status,
)
from aurex.broker_engine.binance_testnet_fill_campaign import build_fill_fee_contract
from aurex.broker_engine.binance_testnet_restart_soak import (
    BinanceRestartSoakEvidenceAudit,
    audit_restart_soak_evidence_audit,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    BinanceUserStreamEvidenceAudit,
    audit_user_stream_evidence_audit,
)


def evidence_payload() -> dict:
    return {
        "schema_version": 1,
        "checked_at": "2026-07-30T12:00:00+00:00",
        "environment": "BINANCE_SPOT_TESTNET",
        "base_url": "https://testnet.binance.vision",
        "mode": "public",
        "public_connectivity": "PASS",
        "symbol": "BTCUSDT",
        "credentials_stored": False,
        "production_authority": False,
        "live_authority": False,
        "virtual_order_submitted": False,
        "sandbox_qualified": False,
    }


def write_payload(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def qualification_status(path: Path):
    return binance_testnet_qualification_status(
        path,
        contract_path=path.with_name("missing-contract.json"),
        fill_evidence_path=path.with_name("missing-fill.json"),
        user_stream_contract_path=path.with_name("missing-stream-contract.json"),
        user_stream_evidence_path=path.with_name("missing-stream-evidence.json"),
    )


def add_virtual_cancel_progress(payload: dict) -> None:
    placement_id = "aurex-cancel-bbaee2eb49a33a88"
    cancellation_id = "aurex-cancel-op-eb86fdd03f0ffb9d"
    order_id = 22292295
    quantity = "0.00009000"
    payload["virtual_order_submitted"] = True
    payload["virtual_cancel_lifecycle"] = "PASS"
    payload["order_reconciliation"] = "FAIL"
    payload["virtual_order"] = {
        "client_order_id": placement_id,
        "cancel_client_order_id": cancellation_id,
        "quantity": quantity,
    }
    payload["virtual_order_progress"] = {
        "placed": {
            "external_order_id": order_id,
            "client_order_id": placement_id,
            "original_client_order_id": None,
            "status": "NEW",
            "quantity": quantity,
            "executed_quantity": "0",
            "cumulative_quote_quantity": "0",
        },
        "queried": {
            "external_order_id": order_id,
            "client_order_id": placement_id,
            "original_client_order_id": None,
            "status": "NEW",
            "quantity": quantity,
            "executed_quantity": "0",
            "cumulative_quote_quantity": "0",
        },
        "cancelled": {
            "external_order_id": order_id,
            "client_order_id": cancellation_id,
            "original_client_order_id": placement_id,
            "status": "CANCELED",
            "quantity": quantity,
            "executed_quantity": "0",
            "cumulative_quote_quantity": "0",
        },
        "final": {
            "external_order_id": order_id,
            "client_order_id": placement_id,
            "original_client_order_id": None,
            "status": "CANCELED",
            "quantity": quantity,
            "executed_quantity": "0",
            "cumulative_quote_quantity": "0",
        },
    }


def test_missing_evidence_is_not_run(tmp_path: Path) -> None:
    status = qualification_status(tmp_path / "missing.json")

    assert status.workflow_status == "NOT_RUN"
    assert status.public_connectivity_verified is False
    assert status.live_authority is False


def test_public_evidence_is_verified_without_qualification(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    write_payload(path, evidence_payload())

    status = qualification_status(path)

    assert status.workflow_status == "PUBLIC_VERIFIED"
    assert status.public_connectivity_verified is True
    assert status.authenticated_account_read_verified is False
    assert status.sandbox_qualified is False
    assert status.production_authority is False


def test_authenticated_and_test_order_evidence_advances_status(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    payload = evidence_payload()
    payload["authenticated_account_read"] = "PASS"
    payload["signed_test_order"] = "PASS"
    write_payload(path, payload)

    status = qualification_status(path)

    assert status.workflow_status == "SIGNED_TEST_ORDER_VERIFIED"
    assert status.authenticated_account_read_verified is True
    assert status.signed_test_order_verified is True
    assert status.virtual_cancel_lifecycle_verified is False
    assert status.order_reconciliation_verified is False
    assert status.live_authority is False


def test_virtual_cancel_and_reconciliation_advance_status(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    payload = evidence_payload()
    payload["authenticated_account_read"] = "PASS"
    payload["signed_test_order"] = "PASS"
    add_virtual_cancel_progress(payload)
    write_payload(path, payload)

    status = qualification_status(path)

    assert status.workflow_status == "VIRTUAL_CANCEL_RECONCILED"
    assert status.virtual_order_submitted is True
    assert status.virtual_cancel_lifecycle_verified is True
    assert status.order_reconciliation_verified is True
    assert status.sandbox_qualified is False
    assert status.live_authority is False


def test_declared_failure_is_reconciled_from_exact_exchange_snapshots(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    payload = evidence_payload()
    payload["authenticated_account_read"] = "PASS"
    payload["signed_test_order"] = "PASS"
    add_virtual_cancel_progress(payload)
    write_payload(path, payload)

    status = qualification_status(path)

    assert payload["order_reconciliation"] == "FAIL"
    assert status.workflow_status == "VIRTUAL_CANCEL_RECONCILED"
    assert status.order_reconciliation_verified is True


def test_frozen_fill_contract_advances_without_claiming_fill_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    contract_path = tmp_path / "contract.json"
    payload = evidence_payload()
    payload["authenticated_account_read"] = "PASS"
    payload["signed_test_order"] = "PASS"
    add_virtual_cancel_progress(payload)
    write_payload(path, payload)
    contract = build_fill_fee_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    contract_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")

    status = binance_testnet_qualification_status(
        path,
        contract_path=contract_path,
        fill_evidence_path=tmp_path / "missing-fill.json",
        user_stream_contract_path=tmp_path / "missing-stream-contract.json",
        user_stream_evidence_path=tmp_path / "missing-stream-evidence.json",
    )

    assert status.workflow_status == "FILL_FEE_CONTRACT_FROZEN"
    assert status.fill_fee_contract_frozen is True
    assert status.fill_fee_contract_sha256 == contract.contract_sha256
    assert status.fill_fee_campaign_recorded is False
    assert status.fill_fee_reconciliation_verified is False
    assert status.sandbox_qualified is False


def test_cancellation_identity_drift_cannot_reconcile(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    payload = evidence_payload()
    payload["authenticated_account_read"] = "PASS"
    payload["signed_test_order"] = "PASS"
    add_virtual_cancel_progress(payload)
    payload["virtual_order_progress"]["cancelled"]["client_order_id"] = "unexpected-id"
    payload["order_reconciliation"] = "PASS"
    write_payload(path, payload)

    status = qualification_status(path)

    assert status.workflow_status == "SIGNED_TEST_ORDER_VERIFIED"
    assert status.order_reconciliation_verified is False


def test_unsafe_authority_claim_invalidates_evidence(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    payload = evidence_payload()
    payload["production_authority"] = True
    write_payload(path, payload)

    status = qualification_status(path)

    assert status.workflow_status == "INVALID"
    assert status.public_connectivity_verified is False
    assert status.production_authority is False


def test_recorded_fill_fee_audit_is_reproducible_and_tamper_detecting() -> None:
    path = Path(
        "data/evidence/binance_spot_testnet_fill_fee_audit_20260731T091050Z.json"
    )
    audit = BinanceFillFeeEvidenceAudit.model_validate_json(path.read_bytes())

    assert audit_fill_fee_evidence_audit(audit) is True
    assert audit.decision == "PHASE_2B_FILL_FEE_RECONCILED"
    assert audit.source_sha256 == (
        "9a8876188432292bb27842956287881bf5fc170fa3164e07a97ebc8604ce3e51"
    )
    assert audit.phase_2b_qualified is True
    assert audit.whole_sandbox_qualified is False
    assert audit.live_authority is False

    tampered = audit.model_copy(update={"sell_quote_quantity": "6.50"})
    assert audit_fill_fee_evidence_audit(tampered) is False


def test_recorded_user_stream_audit_is_reproducible_and_tamper_detecting() -> None:
    path = Path(
        "data/evidence/"
        "binance_spot_testnet_user_stream_audit_20260731T100023Z.json"
    )
    audit = BinanceUserStreamEvidenceAudit.model_validate_json(path.read_bytes())

    assert audit_user_stream_evidence_audit(audit) is True
    assert audit.decision == "PHASE_2C_USER_STREAM_RECONCILED"
    assert audit.source_sha256 == (
        "e5bc1e5402f49a07c5fc3389259025e30e9fee1ee6a525389e8e01aee7ba333e"
    )
    assert audit.audit_sha256 == (
        "70cd169d2716a2beac17c2f4a3cca53146b1c96f490b065830d7f774e9059038"
    )
    assert audit.phase_2c_qualified is True
    assert audit.whole_sandbox_qualified is False
    assert audit.live_authority is False

    tampered = audit.model_copy(update={"event_count": 4})
    assert audit_user_stream_evidence_audit(tampered) is False


def test_recorded_restart_soak_audit_is_reproducible_and_tamper_detecting() -> None:
    path = Path(
        "data/evidence/"
        "binance_spot_testnet_restart_soak_audit_20260731T125305Z.json"
    )
    audit = BinanceRestartSoakEvidenceAudit.model_validate_json(path.read_bytes())

    assert audit_restart_soak_evidence_audit(audit) is True
    assert audit.decision == "BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED"
    assert audit.source_sha256 == (
        "8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50"
    )
    assert audit.audit_sha256 == (
        "0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29"
    )
    assert audit.phase_2d_qualified is True
    assert audit.adapter_sandbox_qualified is True
    assert audit.production_authority is False
    assert audit.live_authority is False

    tampered = audit.model_copy(update={"rest_heartbeat_count": 119})
    assert audit_restart_soak_evidence_audit(tampered) is False
