from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from aurex.broker_engine.binance_spot_testnet import (
    DEFAULT_RECV_WINDOW_MS,
    TESTNET_SYMBOL,
    BinanceAccountSnapshot,
    BinanceOrderSnapshot,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
)

TESTNET_WEBSOCKET_API_URL = "wss://ws-api.testnet.binance.vision/ws-api/v3"
DEFAULT_USER_STREAM_CONTRACT_PATH = Path(
    "data/evidence/binance_spot_testnet_user_stream_contract_v1.json"
)
DEFAULT_USER_STREAM_EVIDENCE_PATH = Path(
    "data/evidence/binance_spot_testnet_user_stream_latest.json"
)
USER_STREAM_ACKNOWLEDGEMENT = (
    "I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET USER STREAM CAMPAIGN"
)
MAXIMUM_STREAM_ORDER_NOTIONAL = Decimal("10.00")


class BinanceUserStreamContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    contract_id: str
    frozen_at: datetime
    environment: str
    websocket_url: str
    rest_url: str
    symbol: str
    product: str
    simulated_equity_usd: str
    maximum_order_notional: str
    maximum_orders: int
    event_timeout_seconds: int
    acknowledgement_phrase: str
    subscription_method: str
    reconnect_policy: str
    gap_recovery_policy: str
    duplicate_policy: str
    ambiguous_outcome_policy: str
    cleanup_policy: str
    pass_gates: tuple[str, ...]
    limitations: tuple[str, ...]
    official_references: tuple[str, ...]
    production_authority: bool
    live_authority: bool
    real_capital_authority: bool
    sandbox_qualified: bool
    contract_sha256: str


class BinanceUserStreamEvidenceAudit(BaseModel):
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
    first_order_id: int
    second_order_id: int
    first_subscription_id: int
    second_subscription_id: int
    event_count: int
    execution_report_count: int
    account_position_event_count: int
    duplicate_events_suppressed: int
    forced_disconnect_verified: bool
    rest_gap_recovery_verified: bool
    account_position_match_found: bool
    graceful_unsubscribe_verified: bool
    balance_reconciliation_verified: bool
    independent_verifier_passed: bool
    phase_2c_qualified: bool
    whole_sandbox_qualified: bool
    production_authority: bool
    live_authority: bool
    decision: Literal["PHASE_2C_USER_STREAM_RECONCILED"]
    audit_sha256: str


def build_user_stream_contract(*, frozen_at: datetime) -> BinanceUserStreamContract:
    draft = BinanceUserStreamContract(
        schema_version=1,
        contract_id="binance-spot-testnet-user-stream-v1",
        frozen_at=frozen_at.astimezone(UTC),
        environment="BINANCE_SPOT_TESTNET",
        websocket_url=TESTNET_WEBSOCKET_API_URL,
        rest_url="https://testnet.binance.vision",
        symbol=TESTNET_SYMBOL,
        product="SPOT",
        simulated_equity_usd="100.00",
        maximum_order_notional=format(MAXIMUM_STREAM_ORDER_NOTIONAL, "f"),
        maximum_orders=2,
        event_timeout_seconds=10,
        acknowledgement_phrase=USER_STREAM_ACKNOWLEDGEMENT,
        subscription_method="userDataStream.subscribe.signature",
        reconnect_policy=(
            "Treat every disconnect as a possible event gap. Establish a new WebSocket "
            "API connection and a new signature subscription; never assume replay."
        ),
        gap_recovery_policy=(
            "After reconnect, query every tracked order and the authenticated account "
            "through REST before accepting new execution events."
        ),
        duplicate_policy=(
            "Hash the complete subscription wrapper, suppress exact duplicates across "
            "connections, and retain the duplicate count in evidence."
        ),
        ambiguous_outcome_policy=(
            "Resolve uncertain REST order entry by deterministic client order ID. Never "
            "blindly resubmit an order whose exchange outcome is unknown."
        ),
        cleanup_policy=(
            "Cancel only a proven open campaign order by deterministic identity. Any fill, "
            "unresolved order, nonzero trade ledger, or balance drift fails Phase 2C."
        ),
        pass_gates=(
            "fixed Binance Spot Testnet WebSocket and REST origins",
            "HMAC signature subscription succeeds without persisting credentials",
            "first resting order emits a matching NEW execution report",
            "connection is deliberately closed before first-order cancellation",
            "new connection and signature subscription succeed",
            "REST recovers the missed first-order CANCELED state after reconnect",
            "second resting order emits matching NEW and CANCELED execution reports",
            "at least one USDT account-position event matches the final REST balance",
            "both order trade ledgers are empty and both final orders are CANCELED",
            "initial and final BTC and USDT balances match exactly",
            "duplicate suppression remains active across both connections",
            "graceful unsubscribe succeeds and no cleanup uncertainty remains",
        ),
        limitations=(
            "Testnet events and assets are virtual",
            "this proves event transport and recovery mechanics, not strategy edge",
            "a short campaign does not prove long-duration connection reliability",
            "Phase 2D restart, reset, idempotency, kill-stop, and soak gates remain",
            "whole-sandbox qualification remains false after Phase 2C",
            "production, live, and real-capital authority remain false",
        ),
        official_references=(
            "https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-api.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/user-data-stream.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/CHANGELOG.md",
        ),
        production_authority=False,
        live_authority=False,
        real_capital_authority=False,
        sandbox_qualified=False,
        contract_sha256="",
    )
    return draft.model_copy(update={"contract_sha256": user_stream_contract_sha256(draft)})


def user_stream_contract_sha256(contract: BinanceUserStreamContract) -> str:
    payload = contract.model_dump(mode="json")
    payload["contract_sha256"] = ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit_user_stream_contract(contract: BinanceUserStreamContract) -> bool:
    expected = build_user_stream_contract(frozen_at=contract.frozen_at)
    return (
        contract == expected
        and contract.contract_sha256 == user_stream_contract_sha256(contract)
    )


def user_stream_evidence_verified(
    path: Path,
    contract: BinanceUserStreamContract,
) -> bool:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if not all(
        (
            payload.get("schema_version") == 1,
            payload.get("campaign_id") == contract.contract_id,
            payload.get("contract_sha256") == contract.contract_sha256,
            payload.get("environment") == contract.environment,
            payload.get("websocket_url") == contract.websocket_url,
            payload.get("rest_url") == contract.rest_url,
            payload.get("symbol") == contract.symbol,
            payload.get("product") == contract.product,
            payload.get("maximum_order_notional") == contract.maximum_order_notional,
            payload.get("maximum_orders") == contract.maximum_orders,
            payload.get("subscription_method") == contract.subscription_method,
            payload.get("credentials_stored") is False,
            payload.get("production_authority") is False,
            payload.get("live_authority") is False,
            payload.get("real_capital") is False,
            payload.get("sandbox_qualified") is False,
            payload.get("phase_2c_qualified") is True,
            payload.get("check_status") == "PASS",
        )
    ):
        return False
    client_order_ids = payload.get("client_order_ids")
    subscription_ids = payload.get("subscription_ids")
    first = payload.get("first_order")
    second = payload.get("second_order")
    events = payload.get("events")
    initial = payload.get("initial_account")
    final = payload.get("final_account")
    duplicate = payload.get("duplicate_suppression")
    if not all(
        isinstance(item, dict)
        for item in (
            client_order_ids,
            subscription_ids,
            first,
            second,
            initial,
            final,
            duplicate,
        )
    ) or not isinstance(events, list):
        return False
    if payload.get("event_count") != len(events):
        return False
    first_subscription = subscription_ids.get("first")
    second_subscription = subscription_ids.get("second")
    if (
        not isinstance(first_subscription, int)
        or first_subscription < 0
        or not isinstance(second_subscription, int)
        or second_subscription < 0
    ):
        return False
    if not _stream_order_evidence_safe(
        first,
        expected_client_order_id=client_order_ids.get("first"),
        maximum_notional=Decimal(contract.maximum_order_notional),
    ) or not _stream_order_evidence_safe(
        second,
        expected_client_order_id=client_order_ids.get("second"),
        maximum_notional=Decimal(contract.maximum_order_notional),
    ):
        return False
    first_final = first.get("final")
    second_final = second.get("final")
    if not isinstance(first_final, dict) or not isinstance(second_final, dict):
        return False
    if not all(
        (
            _event_report_exists(
                events,
                subscription_id=first_subscription,
                order=first.get("placed"),
                status="NEW",
            ),
            _event_report_exists(
                events,
                subscription_id=second_subscription,
                order=second.get("placed"),
                status="NEW",
            ),
            _event_report_exists(
                events,
                subscription_id=second_subscription,
                order=second_final,
                status="CANCELED",
            ),
            _account_event_matches_final(
                events,
                subscription_id=second_subscription,
                final_account=final,
            ),
            _account_evidence_assets_match(initial, final, assets=("BTC", "USDT")),
            payload.get("forced_disconnect_verified") is True,
            payload.get("rest_gap_recovery_verified") is True,
            payload.get("account_position_match_found") is True,
            payload.get("graceful_unsubscribe_verified") is True,
            payload.get("balance_reconciliation_verified") is True,
            duplicate.get("enabled") is True,
            isinstance(duplicate.get("duplicate_events_suppressed"), int),
            not payload.get("failed_gates"),
        )
    ):
        return False
    return True


def build_user_stream_evidence_audit(
    *,
    source_path: Path,
    preserved_source_path: Path,
    contract_path: Path,
    audited_at: datetime,
) -> BinanceUserStreamEvidenceAudit:
    source_raw = source_path.read_bytes()
    preserved_raw = preserved_source_path.read_bytes()
    if source_raw != preserved_raw:
        raise ValueError("Preserved user-stream source is not byte-identical")
    contract = BinanceUserStreamContract.model_validate_json(contract_path.read_bytes())
    if not audit_user_stream_contract(contract):
        raise ValueError("User-stream contract is not reproducible")
    if not user_stream_evidence_verified(source_path, contract):
        raise ValueError("User-stream evidence failed independent reconstruction")
    payload = json.loads(source_raw)
    first_order = payload["first_order"]["final"]
    second_order = payload["second_order"]["final"]
    subscriptions = payload["subscription_ids"]
    events = payload["events"]
    duplicate = payload["duplicate_suppression"]
    draft = BinanceUserStreamEvidenceAudit(
        schema_version=1,
        audit_id="binance-spot-testnet-user-stream-audit-v1",
        audited_at=audited_at.astimezone(UTC),
        source_path=source_path.as_posix(),
        source_sha256=hashlib.sha256(source_raw).hexdigest(),
        preserved_source_path=preserved_source_path.as_posix(),
        preserved_source_sha256=hashlib.sha256(preserved_raw).hexdigest(),
        contract_path=contract_path.as_posix(),
        contract_sha256=contract.contract_sha256,
        first_order_id=int(first_order["external_order_id"]),
        second_order_id=int(second_order["external_order_id"]),
        first_subscription_id=int(subscriptions["first"]),
        second_subscription_id=int(subscriptions["second"]),
        event_count=len(events),
        execution_report_count=sum(
            1
            for event in events
            if isinstance(event, Mapping)
            and event.get("event_type") == "executionReport"
        ),
        account_position_event_count=sum(
            1
            for event in events
            if isinstance(event, Mapping)
            and event.get("event_type") == "outboundAccountPosition"
        ),
        duplicate_events_suppressed=int(
            duplicate["duplicate_events_suppressed"]
        ),
        forced_disconnect_verified=True,
        rest_gap_recovery_verified=True,
        account_position_match_found=True,
        graceful_unsubscribe_verified=True,
        balance_reconciliation_verified=True,
        independent_verifier_passed=True,
        phase_2c_qualified=True,
        whole_sandbox_qualified=False,
        production_authority=False,
        live_authority=False,
        decision="PHASE_2C_USER_STREAM_RECONCILED",
        audit_sha256="",
    )
    return draft.model_copy(
        update={"audit_sha256": user_stream_audit_sha256(draft)}
    )


def user_stream_audit_sha256(audit: BinanceUserStreamEvidenceAudit) -> str:
    payload = audit.model_dump(mode="json")
    payload["audit_sha256"] = ""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit_user_stream_evidence_audit(
    audit: BinanceUserStreamEvidenceAudit,
) -> bool:
    try:
        expected = build_user_stream_evidence_audit(
            source_path=Path(audit.source_path),
            preserved_source_path=Path(audit.preserved_source_path),
            contract_path=Path(audit.contract_path),
            audited_at=audit.audited_at,
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False
    return (
        audit == expected
        and audit.audit_sha256 == user_stream_audit_sha256(audit)
    )


@dataclass(frozen=True)
class BinanceExecutionReport:
    subscription_id: int
    event_time_ms: int
    transaction_time_ms: int
    symbol: str
    order_id: int
    client_order_id: str
    original_client_order_id: str | None
    side: str
    order_type: str
    execution_type: str
    order_status: str
    price: Decimal
    original_quantity: Decimal
    executed_quantity: Decimal
    cumulative_quote_quantity: Decimal
    last_executed_quantity: Decimal
    last_executed_price: Decimal
    commission: Decimal
    commission_asset: str | None
    trade_id: int
    execution_id: int


@dataclass(frozen=True)
class BinanceStreamBalance:
    asset: str
    free: Decimal
    locked: Decimal


@dataclass(frozen=True)
class BinanceAccountPosition:
    subscription_id: int
    event_time_ms: int
    last_account_update_ms: int
    balances: tuple[BinanceStreamBalance, ...]


@dataclass(frozen=True)
class BinanceUserDataEvent:
    subscription_id: int
    event_type: str
    event_time_ms: int
    event_key: str
    execution_report: BinanceExecutionReport | None = None
    account_position: BinanceAccountPosition | None = None

    def evidence(self) -> dict[str, object]:
        result: dict[str, object] = {
            "subscription_id": self.subscription_id,
            "event_type": self.event_type,
            "event_time_ms": self.event_time_ms,
            "event_key": self.event_key,
        }
        if self.execution_report is not None:
            report = self.execution_report
            result["execution_report"] = {
                "transaction_time_ms": report.transaction_time_ms,
                "symbol": report.symbol,
                "external_order_id": report.order_id,
                "client_order_id": report.client_order_id,
                "original_client_order_id": report.original_client_order_id,
                "side": report.side,
                "type": report.order_type,
                "execution_type": report.execution_type,
                "status": report.order_status,
                "price": str(report.price),
                "original_quantity": str(report.original_quantity),
                "executed_quantity": str(report.executed_quantity),
                "cumulative_quote_quantity": str(report.cumulative_quote_quantity),
                "last_executed_quantity": str(report.last_executed_quantity),
                "last_executed_price": str(report.last_executed_price),
                "commission": str(report.commission),
                "commission_asset": report.commission_asset,
                "trade_id": report.trade_id,
                "execution_id": report.execution_id,
            }
        if self.account_position is not None:
            result["account_position"] = {
                "last_account_update_ms": self.account_position.last_account_update_ms,
                "balances": {
                    balance.asset: {
                        "free": str(balance.free),
                        "locked": str(balance.locked),
                    }
                    for balance in self.account_position.balances
                    if balance.asset in {"BTC", "USDT"}
                },
            }
        return result


def parse_user_data_event(payload: object) -> BinanceUserDataEvent:
    if not isinstance(payload, Mapping):
        raise BinanceSpotTestnetError("Binance user-data stream message is not an object")
    subscription_id = payload.get("subscriptionId")
    event = payload.get("event")
    if not isinstance(subscription_id, int) or subscription_id < 0:
        raise BinanceSpotTestnetError("Binance user-data event subscription ID is invalid")
    if not isinstance(event, Mapping):
        raise BinanceSpotTestnetError("Binance user-data event payload is missing")
    event_type = event.get("e")
    event_time = event.get("E")
    if not isinstance(event_type, str) or not event_type:
        raise BinanceSpotTestnetError("Binance user-data event type is invalid")
    if not isinstance(event_time, int) or event_time <= 0:
        raise BinanceSpotTestnetError("Binance user-data event time is invalid")
    event_key = _event_key(subscription_id, event)
    execution_report = (
        _parse_execution_report(subscription_id, event)
        if event_type == "executionReport"
        else None
    )
    account_position = (
        _parse_account_position(subscription_id, event)
        if event_type == "outboundAccountPosition"
        else None
    )
    return BinanceUserDataEvent(
        subscription_id=subscription_id,
        event_type=event_type,
        event_time_ms=event_time,
        event_key=event_key,
        execution_report=execution_report,
        account_position=account_position,
    )


class BinanceEventDeduplicator:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.duplicate_count = 0

    def accept(self, event: BinanceUserDataEvent) -> bool:
        if event.event_key in self._seen:
            self.duplicate_count += 1
            return False
        self._seen.add(event.event_key)
        return True

    @property
    def unique_count(self) -> int:
        return len(self._seen)


@dataclass(frozen=True)
class BinanceExecutionReportReconciliation:
    subscription_matches: bool
    symbol_matches: bool
    external_order_identity_matches: bool
    client_order_identity_matches: bool
    side_matches: bool
    type_matches: bool
    status_matches: bool
    quantity_matches: bool
    execution_quantity_matches: bool
    cumulative_quote_matches: bool

    @property
    def passed(self) -> bool:
        return all(vars(self).values())


def reconcile_execution_report(
    report: BinanceExecutionReport,
    order: BinanceOrderSnapshot,
    *,
    subscription_id: int,
) -> BinanceExecutionReportReconciliation:
    report_ids = {
        value
        for value in (report.client_order_id, report.original_client_order_id)
        if value
    }
    order_ids = {
        value
        for value in (order.client_order_id, order.original_client_order_id)
        if value
    }
    return BinanceExecutionReportReconciliation(
        subscription_matches=report.subscription_id == subscription_id,
        symbol_matches=report.symbol == order.symbol == TESTNET_SYMBOL,
        external_order_identity_matches=report.order_id == order.order_id,
        client_order_identity_matches=bool(report_ids & order_ids),
        side_matches=report.side == order.side,
        type_matches=report.order_type == order.order_type,
        status_matches=report.order_status == order.status,
        quantity_matches=report.original_quantity == order.original_quantity,
        execution_quantity_matches=report.executed_quantity == order.executed_quantity,
        cumulative_quote_matches=(
            report.cumulative_quote_quantity == order.cumulative_quote_quantity
        ),
    )


def account_position_matches_snapshot(
    position: BinanceAccountPosition,
    account: BinanceAccountSnapshot,
    *,
    required_asset: str = "USDT",
) -> bool:
    event_assets = {balance.asset for balance in position.balances}
    if required_asset not in event_assets:
        return False
    return all(
        balance.free == account.balance(balance.asset).free
        and balance.locked == account.balance(balance.asset).locked
        for balance in position.balances
    )


class BinanceWebSocketConnection(Protocol):
    def send(self, message: str) -> None: ...

    def recv(self, timeout: float | None = None) -> str | bytes: ...

    def close(self, code: int = 1000, reason: str = "") -> None: ...


BinanceWebSocketConnector = Callable[[str, float], BinanceWebSocketConnection]


class BinanceUserDataStreamClient:
    def __init__(
        self,
        *,
        credentials: BinanceTestnetCredentials,
        connector: BinanceWebSocketConnector | None = None,
        clock_ms: Callable[[], int] | None = None,
        server_offset_ms: int = 0,
        recv_window_ms: int = DEFAULT_RECV_WINDOW_MS,
        timeout_seconds: float = 10,
    ) -> None:
        if recv_window_ms <= 0 or recv_window_ms > 60_000:
            raise ValueError("recv_window_ms must be between 1 and 60000")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._credentials = credentials
        self._connector = connector or _connect_websocket
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._server_offset_ms = server_offset_ms
        self._recv_window_ms = recv_window_ms
        self._timeout_seconds = timeout_seconds
        self._connection: BinanceWebSocketConnection | None = None
        self._subscription_id: int | None = None
        self._request_sequence = 0
        self._event_buffer: list[BinanceUserDataEvent] = []

    @property
    def websocket_url(self) -> str:
        return TESTNET_WEBSOCKET_API_URL

    @property
    def subscription_id(self) -> int | None:
        return self._subscription_id

    def connect(self) -> None:
        if self._connection is not None:
            raise BinanceSpotTestnetError("Binance user-data stream is already connected")
        self._connection = self._connector(
            TESTNET_WEBSOCKET_API_URL,
            self._timeout_seconds,
        )

    def subscribe(self) -> int:
        if self._connection is None:
            raise BinanceSpotTestnetError("Binance user-data stream is not connected")
        if self._subscription_id is not None:
            raise BinanceSpotTestnetError("Binance user-data subscription is already active")
        request_id = self._next_request_id("subscribe")
        params: dict[str, object] = {
            "apiKey": self._credentials.api_key,
            "recvWindow": self._recv_window_ms,
            "timestamp": self._clock_ms() + self._server_offset_ms,
        }
        params["signature"] = _websocket_signature(
            params,
            secret_key=self._credentials.secret_key,
        )
        self._send(
            {
                "id": request_id,
                "method": "userDataStream.subscribe.signature",
                "params": params,
            }
        )
        response = self._wait_for_response(request_id)
        result = response.get("result")
        subscription_id = (
            result.get("subscriptionId") if isinstance(result, Mapping) else None
        )
        if not isinstance(subscription_id, int) or subscription_id < 0:
            raise BinanceSpotTestnetError(
                "Binance user-data subscription response is invalid"
            )
        self._subscription_id = subscription_id
        return subscription_id

    def next_event(self, *, timeout_seconds: float | None = None) -> BinanceUserDataEvent:
        if self._event_buffer:
            return self._event_buffer.pop(0)
        payload = self._receive_payload(timeout_seconds)
        if "event" not in payload:
            raise BinanceSpotTestnetError(
                "Unexpected Binance WebSocket API response while waiting for an event"
            )
        event = parse_user_data_event(payload)
        if self._subscription_id is not None and event.subscription_id != self._subscription_id:
            raise BinanceSpotTestnetError(
                "Binance event belongs to an unexpected subscription"
            )
        return event

    def unsubscribe(self) -> None:
        if self._connection is None or self._subscription_id is None:
            raise BinanceSpotTestnetError("No active Binance user-data subscription")
        request_id = self._next_request_id("unsubscribe")
        self._send(
            {
                "id": request_id,
                "method": "userDataStream.unsubscribe",
                "params": {"subscriptionId": self._subscription_id},
            }
        )
        self._wait_for_response(request_id)
        self._subscription_id = None

    def disconnect(self) -> None:
        connection = self._connection
        self._connection = None
        self._subscription_id = None
        self._event_buffer.clear()
        if connection is not None:
            connection.close()

    def _next_request_id(self, purpose: str) -> str:
        self._request_sequence += 1
        return f"aurex-{purpose}-{self._request_sequence:06d}"

    def _send(self, payload: Mapping[str, object]) -> None:
        if self._connection is None:
            raise BinanceSpotTestnetError("Binance user-data stream is not connected")
        self._connection.send(json.dumps(payload, separators=(",", ":")))

    def _wait_for_response(self, request_id: str) -> Mapping[str, object]:
        while True:
            payload = self._receive_payload(self._timeout_seconds)
            if "event" in payload:
                self._event_buffer.append(parse_user_data_event(payload))
                continue
            if payload.get("id") != request_id:
                raise BinanceSpotTestnetError(
                    "Binance WebSocket API returned an unexpected response ID"
                )
            status = payload.get("status")
            if not isinstance(status, int) or status < 200 or status >= 300:
                error = payload.get("error")
                message = (
                    str(error.get("msg", "request rejected"))
                    if isinstance(error, Mapping)
                    else "request rejected"
                )
                raise BinanceSpotTestnetError(
                    f"Binance user-data stream rejected the request: {message}",
                    status_code=status if isinstance(status, int) else None,
                )
            return payload

    def _receive_payload(self, timeout_seconds: float | None) -> Mapping[str, object]:
        if self._connection is None:
            raise BinanceSpotTestnetError("Binance user-data stream is not connected")
        raw = self._connection.recv(
            self._timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        if isinstance(raw, bytes):
            raise BinanceSpotTestnetError(
                "Binary Binance user-data messages are outside the JSON contract"
            )
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BinanceSpotTestnetError(
                "Binance user-data stream returned invalid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise BinanceSpotTestnetError(
                "Binance user-data stream returned a non-object message"
            )
        return payload


def _connect_websocket(url: str, timeout_seconds: float) -> BinanceWebSocketConnection:
    from websockets.sync.client import connect

    return connect(
        url,
        open_timeout=timeout_seconds,
        close_timeout=timeout_seconds,
        ping_interval=20,
        ping_timeout=20,
        max_size=1_048_576,
    )


def _websocket_signature(
    parameters: Mapping[str, object],
    *,
    secret_key: str,
) -> str:
    signing_parameters = {
        key: value for key, value in parameters.items() if key != "signature"
    }
    canonical = "&".join(
        f"{key}={signing_parameters[key]}" for key in sorted(signing_parameters)
    )
    return hmac.new(
        secret_key.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _event_key(subscription_id: int, event: Mapping[str, object]) -> str:
    raw = json.dumps(
        {"subscriptionId": subscription_id, "event": event},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_execution_report(
    subscription_id: int,
    event: Mapping[str, object],
) -> BinanceExecutionReport:
    report = BinanceExecutionReport(
        subscription_id=subscription_id,
        event_time_ms=_positive_int(event, "E"),
        transaction_time_ms=_positive_int(event, "T"),
        symbol=str(event.get("s", "")),
        order_id=_positive_int(event, "i"),
        client_order_id=str(event.get("c", "")),
        original_client_order_id=(
            str(event["C"]) if event.get("C") not in (None, "") else None
        ),
        side=str(event.get("S", "")),
        order_type=str(event.get("o", "")),
        execution_type=str(event.get("x", "")),
        order_status=str(event.get("X", "")),
        price=_decimal(event, "p"),
        original_quantity=_decimal(event, "q"),
        executed_quantity=_decimal(event, "z"),
        cumulative_quote_quantity=_decimal(event, "Z"),
        last_executed_quantity=_decimal(event, "l"),
        last_executed_price=_decimal(event, "L"),
        commission=_decimal(event, "n"),
        commission_asset=(
            str(event["N"]) if event.get("N") not in (None, "") else None
        ),
        trade_id=int(event.get("t", -1)),
        execution_id=_positive_int(event, "I"),
    )
    if (
        report.symbol != TESTNET_SYMBOL
        or not report.client_order_id
        or report.side not in {"BUY", "SELL"}
        or not report.order_type
        or not report.execution_type
        or not report.order_status
        or min(
            report.price,
            report.original_quantity,
            report.executed_quantity,
            report.cumulative_quote_quantity,
            report.last_executed_quantity,
            report.last_executed_price,
            report.commission,
        )
        < 0
    ):
        raise BinanceSpotTestnetError(
            "Binance execution report violates the BTCUSDT event contract"
        )
    return report


def _parse_account_position(
    subscription_id: int,
    event: Mapping[str, object],
) -> BinanceAccountPosition:
    balances = event.get("B")
    if not isinstance(balances, list) or not balances:
        raise BinanceSpotTestnetError("Binance account-position balances are invalid")
    parsed: list[BinanceStreamBalance] = []
    for item in balances:
        if not isinstance(item, Mapping):
            raise BinanceSpotTestnetError(
                "Binance account-position balance item is invalid"
            )
        asset = str(item.get("a", ""))
        free = _decimal(item, "f")
        locked = _decimal(item, "l")
        if not asset or free < 0 or locked < 0:
            raise BinanceSpotTestnetError(
                "Binance account-position balance violates the event contract"
            )
        parsed.append(BinanceStreamBalance(asset=asset, free=free, locked=locked))
    return BinanceAccountPosition(
        subscription_id=subscription_id,
        event_time_ms=_positive_int(event, "E"),
        last_account_update_ms=_positive_int(event, "u"),
        balances=tuple(parsed),
    )


def _positive_int(payload: Mapping[str, object], field_name: str) -> int:
    try:
        value = int(payload[field_name])
    except (KeyError, TypeError, ValueError) as exc:
        raise BinanceSpotTestnetError(
            f"Binance user-data field {field_name} is invalid"
        ) from exc
    if value <= 0:
        raise BinanceSpotTestnetError(
            f"Binance user-data field {field_name} is invalid"
        )
    return value


def _decimal(payload: Mapping[str, object], field_name: str) -> Decimal:
    try:
        return Decimal(str(payload[field_name]))
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise BinanceSpotTestnetError(
            f"Binance user-data field {field_name} is invalid"
        ) from exc


def _stream_order_evidence_safe(
    order_group: Mapping[str, object],
    *,
    expected_client_order_id: object,
    maximum_notional: Decimal,
) -> bool:
    placed = order_group.get("placed")
    final = order_group.get("final")
    trades = order_group.get("trades")
    if (
        not isinstance(expected_client_order_id, str)
        or not isinstance(placed, Mapping)
        or not isinstance(final, Mapping)
        or not isinstance(trades, list)
        or trades
    ):
        return False
    try:
        placed_order_id = int(placed["external_order_id"])
        final_order_id = int(final["external_order_id"])
        quantity = Decimal(str(placed["original_quantity"]))
        price = Decimal(str(placed["price"]))
        placed_executed = Decimal(str(placed["executed_quantity"]))
        final_executed = Decimal(str(final["executed_quantity"]))
        final_quote = Decimal(str(final["cumulative_quote_quantity"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return False
    return all(
        (
            placed.get("symbol") == TESTNET_SYMBOL,
            final.get("symbol") == TESTNET_SYMBOL,
            placed_order_id > 0,
            final_order_id == placed_order_id,
            placed.get("client_order_id") == expected_client_order_id,
            final.get("client_order_id") == expected_client_order_id,
            placed.get("side") == "BUY",
            final.get("side") == "BUY",
            placed.get("type") == "LIMIT",
            final.get("type") == "LIMIT",
            placed.get("status") == "NEW",
            final.get("status") == "CANCELED",
            quantity > 0,
            price > 0,
            quantity * price <= maximum_notional,
            placed_executed == 0,
            final_executed == 0,
            final_quote == 0,
        )
    )


def _event_report_exists(
    events: list[object],
    *,
    subscription_id: int,
    order: object,
    status: str,
) -> bool:
    if not isinstance(order, Mapping):
        return False
    try:
        order_id = int(order["external_order_id"])
        quantity = Decimal(str(order["original_quantity"]))
        executed = Decimal(str(order["executed_quantity"]))
        quote = Decimal(str(order["cumulative_quote_quantity"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return False
    order_client_id = str(order.get("client_order_id", ""))
    for item in events:
        if not isinstance(item, Mapping):
            continue
        report = item.get("execution_report")
        if (
            item.get("subscription_id") != subscription_id
            or item.get("event_type") != "executionReport"
            or not isinstance(report, Mapping)
        ):
            continue
        report_ids = {
            str(value)
            for value in (
                report.get("client_order_id"),
                report.get("original_client_order_id"),
            )
            if value
        }
        try:
            matches = all(
                (
                    int(report["external_order_id"]) == order_id,
                    report.get("symbol") == TESTNET_SYMBOL,
                    report.get("side") == "BUY",
                    report.get("type") == "LIMIT",
                    report.get("status") == status,
                    order_client_id in report_ids,
                    Decimal(str(report["original_quantity"])) == quantity,
                    Decimal(str(report["executed_quantity"])) == executed,
                    Decimal(str(report["cumulative_quote_quantity"])) == quote,
                )
            )
        except (KeyError, InvalidOperation, TypeError, ValueError):
            continue
        if matches:
            return True
    return False


def _account_event_matches_final(
    events: list[object],
    *,
    subscription_id: int,
    final_account: Mapping[str, object],
) -> bool:
    final_balances = final_account.get("balances")
    if not isinstance(final_balances, Mapping):
        return False
    final_usdt = final_balances.get("USDT")
    if not isinstance(final_usdt, Mapping):
        return False
    try:
        expected_free = Decimal(str(final_usdt["free"]))
        expected_locked = Decimal(str(final_usdt["locked"]))
    except (KeyError, InvalidOperation, TypeError, ValueError):
        return False
    for item in events:
        if not isinstance(item, Mapping):
            continue
        position = item.get("account_position")
        if (
            item.get("subscription_id") != subscription_id
            or item.get("event_type") != "outboundAccountPosition"
            or not isinstance(position, Mapping)
        ):
            continue
        balances = position.get("balances")
        usdt = balances.get("USDT") if isinstance(balances, Mapping) else None
        if not isinstance(usdt, Mapping):
            continue
        try:
            if (
                Decimal(str(usdt["free"])) == expected_free
                and Decimal(str(usdt["locked"])) == expected_locked
            ):
                return True
        except (KeyError, InvalidOperation, TypeError, ValueError):
            continue
    return False


def _account_evidence_assets_match(
    left: Mapping[str, object],
    right: Mapping[str, object],
    *,
    assets: tuple[str, ...],
) -> bool:
    left_balances = left.get("balances")
    right_balances = right.get("balances")
    if not isinstance(left_balances, Mapping) or not isinstance(right_balances, Mapping):
        return False
    for asset in assets:
        left_balance = left_balances.get(asset)
        right_balance = right_balances.get(asset)
        if not isinstance(left_balance, Mapping) or not isinstance(right_balance, Mapping):
            return False
        try:
            for field in ("free", "locked", "total"):
                if Decimal(str(left_balance[field])) != Decimal(
                    str(right_balance[field])
                ):
                    return False
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return False
    return True
