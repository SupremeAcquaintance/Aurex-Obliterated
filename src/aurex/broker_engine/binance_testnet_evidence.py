from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_SYMBOL,
    BinanceOrderSnapshot,
    BinanceVirtualCancelReconciliation,
    reconcile_virtual_cancel_snapshots,
)
from aurex.broker_engine.binance_testnet_fill_campaign import (
    DEFAULT_CONTRACT_PATH,
    BinanceFillFeeContract,
    audit_fill_fee_contract,
)
from aurex.broker_engine.binance_testnet_restart_soak import (
    DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
    BinanceRestartSoakContract,
    audit_restart_soak_contract,
    restart_soak_evidence_verified,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    DEFAULT_USER_STREAM_CONTRACT_PATH,
    DEFAULT_USER_STREAM_EVIDENCE_PATH,
    BinanceUserStreamContract,
    audit_user_stream_contract,
    user_stream_evidence_verified,
)

DEFAULT_CONNECTIVITY_EVIDENCE_PATH = Path(
    "data/evidence/binance_spot_testnet_public_connectivity_latest.json"
)
DEFAULT_FILL_EVIDENCE_PATH = Path(
    "data/evidence/binance_spot_testnet_fill_fee_latest.json"
)
WorkflowStatus = Literal[
    "NOT_RUN",
    "INVALID",
    "PUBLIC_VERIFIED",
    "AUTHENTICATED_VERIFIED",
    "SIGNED_TEST_ORDER_VERIFIED",
    "VIRTUAL_CANCEL_RECONCILED",
    "FILL_FEE_CONTRACT_FROZEN",
    "FILL_FEE_RECONCILED",
    "USER_STREAM_CONTRACT_FROZEN",
    "USER_STREAM_RECONCILED",
    "RESTART_SOAK_CONTRACT_FROZEN",
    "SANDBOX_QUALIFIED",
]


class BinanceTestnetQualificationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_status: WorkflowStatus
    evidence_path: str
    evidence_sha256: str | None
    checked_at: str | None
    public_connectivity_verified: bool
    authenticated_account_read_verified: bool
    signed_test_order_verified: bool
    virtual_order_submitted: bool
    virtual_cancel_lifecycle_verified: bool
    order_reconciliation_verified: bool
    fill_fee_contract_frozen: bool
    fill_fee_contract_sha256: str | None
    fill_fee_campaign_recorded: bool
    fill_fee_reconciliation_verified: bool
    user_stream_contract_frozen: bool
    user_stream_contract_sha256: str | None
    user_stream_campaign_recorded: bool
    user_stream_reconciliation_verified: bool
    restart_soak_contract_frozen: bool
    restart_soak_contract_sha256: str | None
    restart_soak_campaign_recorded: bool
    restart_soak_reconciliation_verified: bool
    sandbox_qualified: bool
    production_authority: bool
    live_authority: bool
    next_action: str
    summary: str


class BinanceFillFeeEvidenceAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    audit_id: str
    audited_at: datetime
    source_path: str
    source_sha256: str
    preserved_source_path: str
    preserved_source_sha256: str
    contract_path: str
    contract_sha256: str
    buy_order_id: int
    sell_order_id: int
    buy_base_quantity: str
    buy_quote_quantity: str
    sell_base_quantity: str
    sell_quote_quantity: str
    commission_by_asset: dict[str, str]
    expected_btc_delta: str
    observed_btc_delta: str
    expected_usdt_delta: str
    observed_usdt_delta: str
    orders_filled: bool
    order_trade_reconciliation_passed: bool
    balance_reconciliation_passed: bool
    cleanup_order_used: bool
    independent_verifier_passed: bool
    phase_2b_qualified: bool
    whole_sandbox_qualified: bool
    production_authority: bool
    live_authority: bool
    decision: Literal["PHASE_2B_FILL_FEE_RECONCILED"]
    audit_sha256: str


def binance_testnet_qualification_status(
    path: Path = DEFAULT_CONNECTIVITY_EVIDENCE_PATH,
    *,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    fill_evidence_path: Path = DEFAULT_FILL_EVIDENCE_PATH,
    user_stream_contract_path: Path = DEFAULT_USER_STREAM_CONTRACT_PATH,
    user_stream_evidence_path: Path = DEFAULT_USER_STREAM_EVIDENCE_PATH,
    restart_soak_contract_path: Path = DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    restart_soak_evidence_path: Path = DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
) -> BinanceTestnetQualificationStatus:
    if not path.exists():
        return _status(
            path,
            workflow_status="NOT_RUN",
            next_action="Run the public Binance Spot Testnet connectivity check.",
            summary="No Binance Spot Testnet connectivity evidence has been recorded.",
        )
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _status(
            path,
            workflow_status="INVALID",
            next_action="Rerun the public connectivity check to replace invalid evidence.",
            summary="The latest Binance Spot Testnet evidence cannot be parsed.",
        )
    if not isinstance(payload, dict) or not _has_safe_boundary(payload):
        return _status(
            path,
            workflow_status="INVALID",
            evidence_sha256=hashlib.sha256(raw).hexdigest(),
            next_action="Remove the unsafe evidence and rerun the Testnet-only check.",
            summary="The latest evidence violates the frozen Testnet boundary.",
        )

    public_verified = payload.get("public_connectivity") == "PASS"
    authenticated_verified = payload.get("authenticated_account_read") == "PASS"
    test_order_verified = payload.get("signed_test_order") == "PASS"
    virtual_cancel_verified = payload.get("virtual_cancel_lifecycle") == "PASS"
    reconciliation = virtual_cancel_reconciliation_from_evidence(payload)
    reconciliation_verified = reconciliation is not None and reconciliation.passed
    contract = _verified_fill_fee_contract(contract_path)
    contract_frozen = contract is not None
    fill_recorded = fill_evidence_path.exists()
    fill_verified = (
        contract is not None
        and fill_fee_evidence_verified(fill_evidence_path, contract)
    )
    user_stream_contract = _verified_user_stream_contract(user_stream_contract_path)
    user_stream_contract_frozen = user_stream_contract is not None
    user_stream_recorded = user_stream_evidence_path.exists()
    user_stream_verified = (
        user_stream_contract is not None
        and user_stream_evidence_verified(
            user_stream_evidence_path,
            user_stream_contract,
        )
    )
    restart_soak_contract = _verified_restart_soak_contract(
        restart_soak_contract_path
    )
    restart_soak_contract_frozen = restart_soak_contract is not None
    restart_soak_recorded = restart_soak_evidence_path.exists()
    restart_soak_verified = (
        restart_soak_contract is not None
        and restart_soak_evidence_verified(
            restart_soak_evidence_path,
            restart_soak_contract,
        )
    )
    sandbox_qualified = (
        reconciliation_verified
        and fill_verified
        and user_stream_verified
        and restart_soak_verified
    )
    if sandbox_qualified:
        workflow_status: WorkflowStatus = "SANDBOX_QUALIFIED"
        next_action = (
            "Lock the qualified adapter evidence, then continue strategy and "
            "historical-market-data validation. Production and live remain disabled."
        )
    elif (
        fill_verified
        and user_stream_verified
        and restart_soak_contract_frozen
    ):
        workflow_status = "RESTART_SOAK_CONTRACT_FROZEN"
        next_action = (
            "Review and run the one acknowledged three-process restart, kill-stop, "
            "reset-detection, and ten-minute soak campaign."
        )
    elif fill_verified and user_stream_verified:
        workflow_status: WorkflowStatus = "USER_STREAM_RECONCILED"
        next_action = (
            "Freeze the Phase 2D restart, reset, idempotency, kill-stop, and "
            "duration-soak contract."
        )
    elif fill_verified and user_stream_contract_frozen:
        workflow_status = "USER_STREAM_CONTRACT_FROZEN"
        next_action = (
            "Review the frozen user-stream contract, then run its one explicitly "
            "acknowledged reconnect and REST gap-recovery campaign."
        )
    elif fill_verified:
        workflow_status: WorkflowStatus = "FILL_FEE_RECONCILED"
        next_action = (
            "Freeze the Phase 2C user-data stream and reconnect-recovery contract."
        )
    elif virtual_cancel_verified and reconciliation_verified and contract_frozen:
        workflow_status = "FILL_FEE_CONTRACT_FROZEN"
        next_action = (
            "Review the frozen fill-and-fee contract, then run its one explicitly "
            "acknowledged Testnet campaign."
        )
    elif virtual_cancel_verified and reconciliation_verified:
        workflow_status: WorkflowStatus = "VIRTUAL_CANCEL_RECONCILED"
        next_action = "Freeze the separately guarded fill-and-fee campaign contract."
    elif test_order_verified:
        workflow_status: WorkflowStatus = "SIGNED_TEST_ORDER_VERIFIED"
        next_action = "Run the guarded virtual order and reconciliation campaign."
    elif authenticated_verified:
        workflow_status = "AUTHENTICATED_VERIFIED"
        next_action = "Run signed order/test validation."
    elif public_verified:
        workflow_status = "PUBLIC_VERIFIED"
        next_action = "Run the hidden-prompt authenticated Testnet check."
    else:
        workflow_status = "INVALID"
        next_action = "Rerun the public Binance Spot Testnet connectivity check."

    return _status(
        path,
        workflow_status=workflow_status,
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
        checked_at=str(payload.get("checked_at") or "") or None,
        public_connectivity_verified=public_verified,
        authenticated_account_read_verified=authenticated_verified,
        signed_test_order_verified=test_order_verified,
        virtual_order_submitted=bool(payload.get("virtual_order_submitted")),
        virtual_cancel_lifecycle_verified=virtual_cancel_verified,
        order_reconciliation_verified=reconciliation_verified,
        fill_fee_contract_frozen=contract_frozen,
        fill_fee_contract_sha256=(
            contract.contract_sha256 if contract is not None else None
        ),
        fill_fee_campaign_recorded=fill_recorded,
        fill_fee_reconciliation_verified=fill_verified,
        user_stream_contract_frozen=user_stream_contract_frozen,
        user_stream_contract_sha256=(
            user_stream_contract.contract_sha256
            if user_stream_contract is not None
            else None
        ),
        user_stream_campaign_recorded=user_stream_recorded,
        user_stream_reconciliation_verified=user_stream_verified,
        restart_soak_contract_frozen=restart_soak_contract_frozen,
        restart_soak_contract_sha256=(
            restart_soak_contract.contract_sha256
            if restart_soak_contract is not None
            else None
        ),
        restart_soak_campaign_recorded=restart_soak_recorded,
        restart_soak_reconciliation_verified=restart_soak_verified,
        sandbox_qualified=sandbox_qualified,
        next_action=next_action,
        summary=(
            (
                "The Binance Spot Testnet adapter passed all frozen Phase 2 "
                "qualification gates. Strategy, production, and live authority remain "
                "disabled."
            )
            if sandbox_qualified
            else
            (
                "Recorded Binance Spot Testnet checkpoints reconcile under the "
                "current identity contract; broader sandbox qualification, "
                "production, and live authority remain disabled."
            )
            if reconciliation_verified
            else (
                "Binance Spot Testnet qualification evidence is valid; "
                "production and live authority remain disabled."
            )
        ),
    )


def _verified_fill_fee_contract(path: Path) -> BinanceFillFeeContract | None:
    try:
        contract = BinanceFillFeeContract.model_validate_json(path.read_bytes())
    except (OSError, ValueError):
        return None
    return contract if audit_fill_fee_contract(contract) else None


def _verified_user_stream_contract(path: Path) -> BinanceUserStreamContract | None:
    try:
        contract = BinanceUserStreamContract.model_validate_json(path.read_bytes())
    except (OSError, ValueError):
        return None
    return contract if audit_user_stream_contract(contract) else None


def _verified_restart_soak_contract(
    path: Path,
) -> BinanceRestartSoakContract | None:
    try:
        contract = BinanceRestartSoakContract.model_validate_json(path.read_bytes())
    except (OSError, ValueError):
        return None
    return contract if audit_restart_soak_contract(contract) else None


def fill_fee_evidence_verified(
    path: Path,
    contract: BinanceFillFeeContract,
) -> bool:
    try:
        payload = json.loads(path.read_bytes())
        buy = payload["buy_order"]
        sells = payload["sell_orders"]
        balance = payload["balance_reconciliation"]
        initial_balances = payload["initial_account"]["balances"]
        final_balances = payload["final_account"]["balances"]
        expected = {
            asset: Decimal(str(amount))
            for asset, amount in balance["expected_deltas"].items()
        }
        observed = {
            asset: Decimal(str(amount))
            for asset, amount in balance["observed_deltas"].items()
        }
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        json.JSONDecodeError,
    ):
        return False
    if (
        not isinstance(payload, dict)
        or payload.get("environment") != "BINANCE_SPOT_TESTNET"
        or payload.get("base_url") != TESTNET_REST_BASE_URL
        or payload.get("symbol") != TESTNET_SYMBOL
        or payload.get("contract_sha256") != contract.contract_sha256
        or payload.get("credentials_stored") is not False
        or payload.get("production_authority") is not False
        or payload.get("live_authority") is not False
        or payload.get("real_capital") is not False
        or payload.get("sandbox_qualified") is not False
        or payload.get("check_status") != "PASS"
        or payload.get("phase_2b_qualified") is not True
        or payload.get("failed_gates") != []
        or payload.get("cleanup_order_used") is not False
        or not isinstance(buy, dict)
        or not isinstance(sells, list)
        or len(sells) != 1
        or not isinstance(sells[0], dict)
        or buy.get("status") != "FILLED"
        or buy.get("reconciliation_passed") is not True
        or sells[0].get("status") != "FILLED"
        or sells[0].get("reconciliation_passed") is not True
        or not isinstance(balance, dict)
        or balance.get("passed") is not True
        or balance.get("mismatches") != {}
        or not isinstance(initial_balances, dict)
        or not isinstance(final_balances, dict)
        or not _order_trade_evidence_matches(buy, expected_side="BUY")
        or not _order_trade_evidence_matches(sells[0], expected_side="SELL")
    ):
        return False
    computed_expected = _expected_deltas_from_trade_evidence(
        buy_trades=buy["trades"],
        sell_trades=sells[0]["trades"],
    )
    if computed_expected is None or expected != computed_expected:
        return False
    assets = set(initial_balances) | set(final_balances) | set(expected)
    for asset in assets:
        try:
            initial_total = Decimal(
                str(initial_balances.get(asset, {}).get("total", "0"))
            )
            final_total = Decimal(str(final_balances.get(asset, {}).get("total", "0")))
        except (AttributeError, InvalidOperation):
            return False
        actual_delta = final_total - initial_total
        if actual_delta != expected.get(asset, Decimal("0")):
            return False
        if observed.get(asset, Decimal("0")) != actual_delta:
            return False
    try:
        return (
            Decimal(str(payload.get("expected_base_residual", "-1")))
            == expected.get("BTC", Decimal("0"))
            and Decimal(str(payload.get("round_trip_quote_delta", "1")))
            == expected.get("USDT", Decimal("0"))
            and expected.get("BTC", Decimal("0")) >= 0
            and expected.get("USDT", Decimal("0"))
            >= Decimal(f"-{contract.maximum_round_trip_loss}")
            and Decimal(str(buy["cumulative_quote_quantity"]))
            <= Decimal(contract.maximum_order_notional)
            and Decimal(str(sells[0]["cumulative_quote_quantity"]))
            <= Decimal(contract.maximum_order_notional)
        )
    except (KeyError, InvalidOperation):
        return False


def build_fill_fee_evidence_audit(
    *,
    audited_at: datetime,
    source_path: Path,
    preserved_source_path: Path,
    contract_path: Path,
) -> BinanceFillFeeEvidenceAudit:
    source_raw = source_path.read_bytes()
    preserved_raw = preserved_source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_raw).hexdigest()
    preserved_sha256 = hashlib.sha256(preserved_raw).hexdigest()
    if source_raw != preserved_raw:
        raise ValueError("Preserved fill-and-fee source is not byte-identical")
    contract = _verified_fill_fee_contract(contract_path)
    if contract is None:
        raise ValueError("Fill-and-fee contract is absent or invalid")
    if not fill_fee_evidence_verified(source_path, contract):
        raise ValueError("Fill-and-fee source failed the independent verifier")
    payload = json.loads(source_raw)
    buy = payload["buy_order"]
    sell = payload["sell_orders"][0]
    balance = payload["balance_reconciliation"]
    expected = balance["expected_deltas"]
    observed = balance["observed_deltas"]
    commissions: dict[str, Decimal] = {}
    for order in (buy, sell):
        for asset, amount in order["commission_by_asset"].items():
            commissions[asset] = commissions.get(asset, Decimal("0")) + Decimal(
                str(amount)
            )
    draft = BinanceFillFeeEvidenceAudit(
        schema_version=1,
        audit_id="binance-spot-testnet-fill-fee-audit-v1",
        audited_at=audited_at,
        source_path=source_path.as_posix(),
        source_sha256=source_sha256,
        preserved_source_path=preserved_source_path.as_posix(),
        preserved_source_sha256=preserved_sha256,
        contract_path=contract_path.as_posix(),
        contract_sha256=contract.contract_sha256,
        buy_order_id=int(buy["external_order_id"]),
        sell_order_id=int(sell["external_order_id"]),
        buy_base_quantity=str(buy["executed_quantity"]),
        buy_quote_quantity=str(buy["cumulative_quote_quantity"]),
        sell_base_quantity=str(sell["executed_quantity"]),
        sell_quote_quantity=str(sell["cumulative_quote_quantity"]),
        commission_by_asset={
            asset: str(amount) for asset, amount in sorted(commissions.items())
        },
        expected_btc_delta=str(expected.get("BTC", "0")),
        observed_btc_delta=str(observed.get("BTC", "0")),
        expected_usdt_delta=str(expected.get("USDT", "0")),
        observed_usdt_delta=str(observed.get("USDT", "0")),
        orders_filled=buy["status"] == sell["status"] == "FILLED",
        order_trade_reconciliation_passed=(
            buy["reconciliation_passed"] is True
            and sell["reconciliation_passed"] is True
        ),
        balance_reconciliation_passed=balance["passed"] is True,
        cleanup_order_used=payload["cleanup_order_used"] is True,
        independent_verifier_passed=True,
        phase_2b_qualified=True,
        whole_sandbox_qualified=False,
        production_authority=False,
        live_authority=False,
        decision="PHASE_2B_FILL_FEE_RECONCILED",
        audit_sha256="",
    )
    return draft.model_copy(update={"audit_sha256": fill_fee_audit_sha256(draft)})


def fill_fee_audit_sha256(audit: BinanceFillFeeEvidenceAudit) -> str:
    payload = audit.model_dump(mode="json")
    payload["audit_sha256"] = ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit_fill_fee_evidence_audit(audit: BinanceFillFeeEvidenceAudit) -> bool:
    try:
        expected = build_fill_fee_evidence_audit(
            audited_at=audit.audited_at,
            source_path=Path(audit.source_path),
            preserved_source_path=Path(audit.preserved_source_path),
            contract_path=Path(audit.contract_path),
        )
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
        return False
    return audit == expected and audit.audit_sha256 == fill_fee_audit_sha256(audit)


def _order_trade_evidence_matches(
    order: Mapping[str, object],
    *,
    expected_side: str,
) -> bool:
    trades = order.get("trades")
    if not isinstance(trades, list) or not trades:
        return False
    try:
        executed = Decimal(str(order["executed_quantity"]))
        cumulative_quote = Decimal(str(order["cumulative_quote_quantity"]))
        order_id = int(order["external_order_id"])
        trade_quantity = sum(
            (Decimal(str(trade["quantity"])) for trade in trades),
            Decimal("0"),
        )
        trade_quote = sum(
            (Decimal(str(trade["quote_quantity"])) for trade in trades),
            Decimal("0"),
        )
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False
    try:
        rows_valid = all(
            isinstance(trade, dict)
            and trade.get("symbol") == TESTNET_SYMBOL
            and trade.get("external_order_id") == order_id
            and trade.get("is_buyer") is (expected_side == "BUY")
            and Decimal(str(trade.get("commission", "-1"))) >= 0
            and bool(trade.get("commission_asset"))
            for trade in trades
        )
    except InvalidOperation:
        return False
    trade_ids = [
        trade.get("trade_id") for trade in trades if isinstance(trade, dict)
    ]
    return (
        order.get("side") == expected_side
        and order.get("symbol") == TESTNET_SYMBOL
        and executed == trade_quantity
        and cumulative_quote == trade_quote
        and rows_valid
        and all(isinstance(trade_id, int) and trade_id > 0 for trade_id in trade_ids)
        and len(trade_ids) == len(set(trade_ids))
    )


def _expected_deltas_from_trade_evidence(
    *,
    buy_trades: object,
    sell_trades: object,
) -> dict[str, Decimal] | None:
    if not isinstance(buy_trades, list) or not isinstance(sell_trades, list):
        return None
    deltas: dict[str, Decimal] = {}

    def add(asset: str, amount: Decimal) -> None:
        deltas[asset] = deltas.get(asset, Decimal("0")) + amount

    try:
        for side, trades in (("BUY", buy_trades), ("SELL", sell_trades)):
            for trade in trades:
                if not isinstance(trade, dict):
                    return None
                quantity = Decimal(str(trade["quantity"]))
                quote_quantity = Decimal(str(trade["quote_quantity"]))
                commission = Decimal(str(trade["commission"]))
                commission_asset = str(trade["commission_asset"])
                direction = Decimal("1") if side == "BUY" else Decimal("-1")
                add("BTC", direction * quantity)
                add("USDT", -direction * quote_quantity)
                add(commission_asset, -commission)
    except (KeyError, InvalidOperation):
        return None
    return {
        asset: amount for asset, amount in sorted(deltas.items()) if amount != 0
    }


def virtual_cancel_reconciliation_from_evidence(
    payload: Mapping[str, object],
) -> BinanceVirtualCancelReconciliation | None:
    virtual_order = payload.get("virtual_order")
    progress = payload.get("virtual_order_progress")
    if not isinstance(virtual_order, Mapping) or not isinstance(progress, Mapping):
        return None
    stage_names = ("placed", "queried", "cancelled", "final")
    if not all(isinstance(progress.get(stage), Mapping) for stage in stage_names):
        return None
    placement_client_order_id = virtual_order.get("client_order_id")
    cancellation_client_order_id = virtual_order.get("cancel_client_order_id")
    if not isinstance(placement_client_order_id, str) or not placement_client_order_id:
        return None
    if not isinstance(cancellation_client_order_id, str) or not cancellation_client_order_id:
        return None
    try:
        expected_quantity = Decimal(str(virtual_order["quantity"]))
        placed = _snapshot_from_evidence(progress["placed"])
        queried = _snapshot_from_evidence(progress["queried"])
        cancelled = _snapshot_from_evidence(progress["cancelled"])
        final = _snapshot_from_evidence(progress["final"])
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    if (
        expected_quantity <= 0
        or placed is None
        or queried is None
        or cancelled is None
        or final is None
    ):
        return None
    return reconcile_virtual_cancel_snapshots(
        placed=placed,
        queried=queried,
        cancelled=cancelled,
        final=final,
        placement_client_order_id=placement_client_order_id,
        cancellation_client_order_id=cancellation_client_order_id,
        expected_quantity=expected_quantity,
    )


def _snapshot_from_evidence(
    payload: Mapping[str, object],
) -> BinanceOrderSnapshot | None:
    order_id = payload.get("external_order_id")
    client_order_id = payload.get("client_order_id")
    status = payload.get("status")
    if (
        not isinstance(order_id, int)
        or order_id <= 0
        or not isinstance(client_order_id, str)
        or not client_order_id
        or not isinstance(status, str)
    ):
        return None
    original_client_order_id = payload.get("original_client_order_id")
    if original_client_order_id is not None and not isinstance(original_client_order_id, str):
        return None
    return BinanceOrderSnapshot(
        symbol=TESTNET_SYMBOL,
        order_id=order_id,
        client_order_id=client_order_id,
        status=status,
        side="BUY",
        order_type="LIMIT",
        price=Decimal("0"),
        original_quantity=Decimal(str(payload["quantity"])),
        executed_quantity=Decimal(str(payload["executed_quantity"])),
        cumulative_quote_quantity=Decimal(str(payload["cumulative_quote_quantity"])),
        original_quote_order_quantity=Decimal("0"),
        transact_time_ms=None,
        original_client_order_id=original_client_order_id,
    )


def _has_safe_boundary(payload: dict[str, object]) -> bool:
    return (
        payload.get("environment") == "BINANCE_SPOT_TESTNET"
        and payload.get("base_url") == TESTNET_REST_BASE_URL
        and payload.get("symbol") == TESTNET_SYMBOL
        and payload.get("credentials_stored") is False
        and payload.get("production_authority") is False
        and payload.get("live_authority") is False
        and payload.get("sandbox_qualified") is False
    )


def _status(
    path: Path,
    *,
    workflow_status: WorkflowStatus,
    evidence_sha256: str | None = None,
    checked_at: str | None = None,
    public_connectivity_verified: bool = False,
    authenticated_account_read_verified: bool = False,
    signed_test_order_verified: bool = False,
    virtual_order_submitted: bool = False,
    virtual_cancel_lifecycle_verified: bool = False,
    order_reconciliation_verified: bool = False,
    fill_fee_contract_frozen: bool = False,
    fill_fee_contract_sha256: str | None = None,
    fill_fee_campaign_recorded: bool = False,
    fill_fee_reconciliation_verified: bool = False,
    user_stream_contract_frozen: bool = False,
    user_stream_contract_sha256: str | None = None,
    user_stream_campaign_recorded: bool = False,
    user_stream_reconciliation_verified: bool = False,
    restart_soak_contract_frozen: bool = False,
    restart_soak_contract_sha256: str | None = None,
    restart_soak_campaign_recorded: bool = False,
    restart_soak_reconciliation_verified: bool = False,
    sandbox_qualified: bool = False,
    next_action: str,
    summary: str,
) -> BinanceTestnetQualificationStatus:
    return BinanceTestnetQualificationStatus(
        workflow_status=workflow_status,
        evidence_path=path.as_posix(),
        evidence_sha256=evidence_sha256,
        checked_at=checked_at,
        public_connectivity_verified=public_connectivity_verified,
        authenticated_account_read_verified=authenticated_account_read_verified,
        signed_test_order_verified=signed_test_order_verified,
        virtual_order_submitted=virtual_order_submitted,
        virtual_cancel_lifecycle_verified=virtual_cancel_lifecycle_verified,
        order_reconciliation_verified=order_reconciliation_verified,
        fill_fee_contract_frozen=fill_fee_contract_frozen,
        fill_fee_contract_sha256=fill_fee_contract_sha256,
        fill_fee_campaign_recorded=fill_fee_campaign_recorded,
        fill_fee_reconciliation_verified=fill_fee_reconciliation_verified,
        user_stream_contract_frozen=user_stream_contract_frozen,
        user_stream_contract_sha256=user_stream_contract_sha256,
        user_stream_campaign_recorded=user_stream_campaign_recorded,
        user_stream_reconciliation_verified=user_stream_reconciliation_verified,
        restart_soak_contract_frozen=restart_soak_contract_frozen,
        restart_soak_contract_sha256=restart_soak_contract_sha256,
        restart_soak_campaign_recorded=restart_soak_campaign_recorded,
        restart_soak_reconciliation_verified=restart_soak_reconciliation_verified,
        sandbox_qualified=sandbox_qualified,
        production_authority=False,
        live_authority=False,
        next_action=next_action,
        summary=summary,
    )
