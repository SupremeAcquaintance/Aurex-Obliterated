from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_SYMBOL,
    BinanceAccountSnapshot,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetError,
    BinanceTradeSnapshot,
)
from aurex.broker_engine.binance_testnet_fill_campaign import (
    account_evidence,
    trades_evidence,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    TESTNET_WEBSOCKET_API_URL,
)

DEFAULT_RESTART_SOAK_CONTRACT_PATH = Path(
    "data/evidence/binance_spot_testnet_restart_soak_contract_v1.json"
)
DEFAULT_RESTART_SOAK_STATE_PATH = Path(
    "data/evidence/binance_spot_testnet_restart_soak_state.json"
)
DEFAULT_RESTART_SOAK_EVIDENCE_PATH = Path(
    "data/evidence/binance_spot_testnet_restart_soak_latest.json"
)
RESTART_SOAK_ACKNOWLEDGEMENT = (
    "I ACKNOWLEDGE ONE BOUNDED BINANCE SPOT TESTNET RESTART AND SOAK CAMPAIGN"
)
MAXIMUM_RESTART_ORDER_NOTIONAL = Decimal("10.00")
OPEN_ORDER_STATUSES = {"NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"}
TERMINAL_ORDER_STATUSES = {"CANCELED", "FILLED", "REJECTED", "EXPIRED"}


class BinanceRestartSoakContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    contract_id: str
    frozen_at: datetime
    environment: str
    rest_url: str
    websocket_url: str
    symbol: str
    product: str
    simulated_equity_usd: str
    maximum_order_notional: str
    maximum_orders: int
    required_processes: int
    soak_duration_seconds: int
    heartbeat_interval_seconds: int
    reconciliation_interval_seconds: int
    forced_reconnect_seconds: tuple[int, ...]
    minimum_rest_heartbeats: int
    minimum_reconciliation_checks: int
    acknowledgement_phrase: str
    startup_policy: str
    restart_policy: str
    idempotency_policy: str
    kill_stop_policy: str
    reset_policy: str
    soak_policy: str
    cleanup_policy: str
    pass_gates: tuple[str, ...]
    limitations: tuple[str, ...]
    official_references: tuple[str, ...]
    production_authority: bool
    live_authority: bool
    real_capital_authority: bool
    strategy_eligible: bool
    contract_sha256: str


class BinanceRestartSoakState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: str
    contract_sha256: str
    created_at: datetime
    updated_at: datetime
    stage: Literal[
        "INITIALIZED",
        "SUBMISSION_INTENT_RECORDED",
        "PREPARED",
        "RECOVERED",
        "SOAKING",
        "PASSED",
        "FAILED",
    ]
    process_ids: list[int] = Field(default_factory=list)
    client_order_id: str
    cancel_client_order_id: str
    blocked_client_order_id: str
    placement_request_count: int = 0
    idempotent_resolution_count: int = 0
    blocked_entry_count: int = 0
    kill_stop_enabled: bool = False
    kill_stop_reason: str | None = None
    kill_stop_enabled_at: datetime | None = None
    initial_open_orders: list[dict[str, object]] = Field(default_factory=list)
    restart_open_orders: list[dict[str, object]] = Field(default_factory=list)
    final_open_orders: list[dict[str, object]] = Field(default_factory=list)
    initial_account: dict[str, object] | None = None
    final_account: dict[str, object] | None = None
    account_fingerprint: str | None = None
    placed_order: dict[str, object] | None = None
    restart_resolved_order: dict[str, object] | None = None
    cancelled_order: dict[str, object] | None = None
    final_order: dict[str, object] | None = None
    trades: list[dict[str, object]] = Field(default_factory=list)
    websocket_subscription_ids: list[int] = Field(default_factory=list)
    websocket_reconnect_count: int = 0
    rest_heartbeat_count: int = 0
    reconciliation_check_count: int = 0
    soak_started_at: datetime | None = None
    soak_completed_at: datetime | None = None
    soak_elapsed_seconds: float = 0
    exchange_reset_detected: bool = False
    state_invalidated: bool = False
    failed_gates: list[str] = Field(default_factory=list)
    credentials_stored: bool = False
    production_authority: bool = False
    live_authority: bool = False
    real_capital: bool = False
    state_sha256: str = ""


class BinanceRestartSoakEvidenceAudit(BaseModel):
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
    run_id: str
    process_count: int
    external_order_id: int
    placement_request_count: int
    idempotent_resolution_count: int
    blocked_entry_count: int
    kill_stop_durable: bool
    no_fill_reconciliation_passed: bool
    websocket_reconnect_count: int
    rest_heartbeat_count: int
    reconciliation_check_count: int
    soak_elapsed_seconds: float
    exchange_reset_detected: bool
    independent_verifier_passed: bool
    phase_2d_qualified: bool
    adapter_sandbox_qualified: bool
    production_authority: bool
    live_authority: bool
    decision: Literal["BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED"]
    audit_sha256: str


class RestartSoakRestClient(Protocol):
    def ping(self) -> None: ...

    def account_snapshot(self) -> BinanceAccountSnapshot: ...

    def symbol_rules(self) -> BinanceSpotSymbolRules: ...

    def ticker_price(self) -> Decimal: ...

    def average_price(self, *, expected_minutes: int | None = None) -> Decimal: ...

    def best_bid_price(self) -> Decimal: ...

    def open_orders(self) -> tuple[BinanceOrderSnapshot, ...]: ...

    def place_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot: ...

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot: ...

    def cancel_order(
        self,
        *,
        client_order_id: str,
        new_client_order_id: str | None = None,
    ) -> BinanceOrderSnapshot: ...

    def account_trades(self, *, order_id: int) -> tuple[BinanceTradeSnapshot, ...]: ...


class RestartSoakStream(Protocol):
    @property
    def subscription_id(self) -> int | None: ...

    def connect(self) -> None: ...

    def subscribe(self) -> int: ...

    def unsubscribe(self) -> None: ...

    def disconnect(self) -> None: ...


def build_restart_soak_contract(*, frozen_at: datetime) -> BinanceRestartSoakContract:
    draft = BinanceRestartSoakContract(
        schema_version=1,
        contract_id="binance-spot-testnet-restart-soak-v1",
        frozen_at=frozen_at.astimezone(UTC),
        environment="BINANCE_SPOT_TESTNET",
        rest_url=TESTNET_REST_BASE_URL,
        websocket_url=TESTNET_WEBSOCKET_API_URL,
        symbol=TESTNET_SYMBOL,
        product="SPOT",
        simulated_equity_usd="100.00",
        maximum_order_notional=format(MAXIMUM_RESTART_ORDER_NOTIONAL, "f"),
        maximum_orders=1,
        required_processes=3,
        soak_duration_seconds=600,
        heartbeat_interval_seconds=5,
        reconciliation_interval_seconds=30,
        forced_reconnect_seconds=(200, 400),
        minimum_rest_heartbeats=120,
        minimum_reconciliation_checks=20,
        acknowledgement_phrase=RESTART_SOAK_ACKNOWLEDGEMENT,
        startup_policy=(
            "Require a zero-order BTCUSDT startup census. Persist an order intent "
            "atomically before the sole exchange placement request."
        ),
        restart_policy=(
            "Exit the prepare process with the bounded order resting, then recover it "
            "from a separate process using durable state plus the exchange open-order census."
        ),
        idempotency_policy=(
            "A persisted placement request is never submitted again. Restart recovery "
            "must resolve the deterministic client order ID through exchange reads."
        ),
        kill_stop_policy=(
            "Persist the kill-stop before cancellation. It blocks every new order-entry "
            "path while still allowing reconciliation and cancellation."
        ),
        reset_policy=(
            "A missing tracked order, account drift, or erased order history invalidates "
            "the run as a possible Testnet reset. Never recreate the missing order."
        ),
        soak_policy=(
            "Keep the kill-stop enabled for 600 seconds while performing REST heartbeats, "
            "authenticated account/order reconciliation, and two forced WebSocket "
            "signature-subscription reconnects."
        ),
        cleanup_policy=(
            "Cancel only the deterministic campaign order. Any fill, partial fill, "
            "unknown order, balance drift, or unresolved open order fails qualification."
        ),
        pass_gates=(
            "three distinct operating-system processes complete prepare, recover, and soak",
            "startup BTCUSDT open-order census is empty",
            "exactly one bounded resting order is submitted",
            "restart finds exactly one matching open order and performs no duplicate POST",
            "durable kill-stop is enabled before campaign cancellation",
            "a new order attempt is blocked locally while the kill-stop is enabled",
            "tracked order is CANCELED with zero execution and an empty trade ledger",
            "initial and final BTC and USDT account balances match exactly",
            "known canceled order remains queryable throughout the soak",
            "REST heartbeat and reconciliation minimums are met",
            "two forced WebSocket reconnects and three subscriptions succeed",
            "no exchange reset, account drift, open campaign order, or failed gate remains",
        ),
        limitations=(
            "Binance Spot Testnet assets and orders are virtual",
            "a ten-minute soak does not prove 24-hour or production reliability",
            "an actual periodic Testnet reset is not induced",
            "reset handling is proven synthetically and monitored fail-closed during the run",
            "adapter qualification does not prove strategy edge or profitable execution",
            "production, live, real-capital, and strategy authority remain false",
        ),
        official_references=(
            "https://github.com/binance/binance-spot-api-docs/blob/master/testnet/general-info.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/testnet/CHANGELOG.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md",
            "https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-api.md",
        ),
        production_authority=False,
        live_authority=False,
        real_capital_authority=False,
        strategy_eligible=False,
        contract_sha256="",
    )
    return draft.model_copy(
        update={"contract_sha256": restart_soak_contract_sha256(draft)}
    )


def restart_soak_contract_sha256(contract: BinanceRestartSoakContract) -> str:
    payload = contract.model_dump(mode="json")
    payload["contract_sha256"] = ""
    return _payload_sha256(payload)


def audit_restart_soak_contract(contract: BinanceRestartSoakContract) -> bool:
    expected = build_restart_soak_contract(frozen_at=contract.frozen_at)
    return (
        contract == expected
        and contract.contract_sha256 == restart_soak_contract_sha256(contract)
    )


def restart_soak_state_sha256(state: BinanceRestartSoakState) -> str:
    payload = state.model_dump(mode="json")
    payload["state_sha256"] = ""
    return _payload_sha256(payload)


class RestartSoakStateStore:
    def __init__(
        self,
        path: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self._now = now or (lambda: datetime.now(UTC))

    def create(
        self,
        *,
        run_id: str,
        contract_sha256: str,
        client_order_id: str,
        cancel_client_order_id: str,
        blocked_client_order_id: str,
    ) -> BinanceRestartSoakState:
        if self.path.exists():
            raise BinanceSpotTestnetError(
                "Restart-soak state already exists; refusing to overwrite durable state"
            )
        now = self._now().astimezone(UTC)
        state = BinanceRestartSoakState(
            run_id=run_id,
            contract_sha256=contract_sha256,
            created_at=now,
            updated_at=now,
            stage="INITIALIZED",
            client_order_id=client_order_id,
            cancel_client_order_id=cancel_client_order_id,
            blocked_client_order_id=blocked_client_order_id,
        )
        return self.save(state)

    def load(self) -> BinanceRestartSoakState:
        try:
            state = BinanceRestartSoakState.model_validate_json(self.path.read_bytes())
        except (OSError, ValueError) as exc:
            raise BinanceSpotTestnetError(
                "Restart-soak durable state is absent or invalid"
            ) from exc
        if state.state_sha256 != restart_soak_state_sha256(state):
            raise BinanceSpotTestnetError(
                "Restart-soak durable state hash does not reconcile"
            )
        if any((state.credentials_stored, state.production_authority, state.live_authority)):
            raise BinanceSpotTestnetError(
                "Restart-soak durable state violates the Testnet-only boundary"
            )
        return state

    def save(self, state: BinanceRestartSoakState) -> BinanceRestartSoakState:
        updated = state.model_copy(
            update={
                "updated_at": self._now().astimezone(UTC),
                "state_sha256": "",
            }
        )
        updated = updated.model_copy(
            update={"state_sha256": restart_soak_state_sha256(updated)}
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        part_path = self.path.with_suffix(f"{self.path.suffix}.part")
        part_path.write_text(
            f"{updated.model_dump_json(indent=2)}\n",
            encoding="utf-8",
        )
        part_path.replace(self.path)
        return updated

    def record_process(self, state: BinanceRestartSoakState) -> BinanceRestartSoakState:
        process_id = os.getpid()
        if process_id in state.process_ids:
            raise BinanceSpotTestnetError(
                "Restart-soak stage must execute in a fresh operating-system process"
            )
        return self.save(
            state.model_copy(update={"process_ids": [*state.process_ids, process_id]})
        )

    def fail(
        self,
        state: BinanceRestartSoakState,
        message: str,
        *,
        reset_detected: bool = False,
    ) -> BinanceRestartSoakState:
        return self.save(
            state.model_copy(
                update={
                    "stage": "FAILED",
                    "kill_stop_enabled": True,
                    "kill_stop_reason": state.kill_stop_reason or "campaign failure",
                    "kill_stop_enabled_at": (
                        state.kill_stop_enabled_at or self._now().astimezone(UTC)
                    ),
                    "exchange_reset_detected": (
                        state.exchange_reset_detected or reset_detected
                    ),
                    "state_invalidated": state.state_invalidated or reset_detected,
                    "failed_gates": [*state.failed_gates, message[:500]],
                }
            )
        )


class BinanceRestartSoakGuard:
    def __init__(
        self,
        *,
        rest: RestartSoakRestClient,
        store: RestartSoakStateStore,
        contract: BinanceRestartSoakContract,
    ) -> None:
        self.rest = rest
        self.store = store
        self.contract = contract

    def prepare(self, state: BinanceRestartSoakState) -> BinanceRestartSoakState:
        self._require_contract(state)
        if state.stage != "INITIALIZED":
            raise BinanceSpotTestnetError("Restart-soak prepare stage is out of order")
        if state.kill_stop_enabled:
            raise BinanceSpotTestnetError("Kill-stop blocks restart-soak order entry")
        open_orders = self.rest.open_orders()
        if open_orders:
            raise BinanceSpotTestnetError(
                "BTCUSDT startup open-order census is not empty; no order was submitted"
            )
        initial_account = self.rest.account_snapshot()
        rules = self.rest.symbol_rules()
        average_price = self.rest.average_price(
            expected_minutes=rules.percent_average_price_minutes
        )
        quantity, price = rules.bounded_test_order(
            self.rest.ticker_price(),
            average_price,
            self.rest.best_bid_price(),
            maximum_notional=Decimal(self.contract.maximum_order_notional),
        )
        state = self.store.save(
            state.model_copy(
                update={
                    "stage": "SUBMISSION_INTENT_RECORDED",
                    "placement_request_count": 1,
                    "initial_open_orders": [],
                    "initial_account": account_evidence(
                        initial_account,
                        assets=("BTC", "USDT"),
                    ),
                    "account_fingerprint": account_fingerprint(initial_account),
                }
            )
        )
        try:
            placed = self.rest.place_limit_order(
                side="BUY",
                quantity=quantity,
                price=price,
                client_order_id=state.client_order_id,
            )
        except BinanceSpotTestnetError as exc:
            if not _ambiguous_order_error(exc):
                raise
            try:
                placed = self.rest.query_order(client_order_id=state.client_order_id)
            except BinanceSpotTestnetError as query_exc:
                raise BinanceSpotTestnetError(
                    "Restart-soak placement outcome is ambiguous; no resubmission allowed"
                ) from query_exc
        _require_resting_identity(
            placed,
            client_order_id=state.client_order_id,
            maximum_notional=Decimal(self.contract.maximum_order_notional),
        )
        return self.store.save(
            state.model_copy(
                update={
                    "stage": "PREPARED",
                    "placed_order": restart_order_evidence(placed),
                }
            )
        )

    def recover(self, state: BinanceRestartSoakState) -> BinanceRestartSoakState:
        self._require_contract(state)
        if state.stage != "PREPARED":
            raise BinanceSpotTestnetError("Restart-soak recover stage is out of order")
        open_orders = self.rest.open_orders()
        matches = [
            order for order in open_orders if order.client_order_id == state.client_order_id
        ]
        if len(matches) != 1 or len(open_orders) != 1:
            missing = not matches
            message = (
                "Tracked restart order disappeared; possible Testnet reset, no recreation"
                if missing
                else "Restart open-order census is ambiguous; no automated cancellation"
            )
            self.store.fail(state, message, reset_detected=missing)
            raise BinanceSpotTestnetError(message)

        resolved = self._resolve_existing(state)
        state = self.store.save(
            state.model_copy(
                update={
                    "idempotent_resolution_count": (
                        state.idempotent_resolution_count + 1
                    ),
                    "restart_open_orders": [
                        restart_order_evidence(order) for order in open_orders
                    ],
                    "restart_resolved_order": restart_order_evidence(resolved),
                }
            )
        )
        state = self.engage_kill_stop(state, reason="restart recovery")
        cancelled = self.rest.cancel_order(
            client_order_id=state.client_order_id,
            new_client_order_id=state.cancel_client_order_id,
        )
        final = self.rest.query_order(order_id=resolved.order_id)
        trades = self.rest.account_trades(order_id=resolved.order_id)
        final_account = self.rest.account_snapshot()
        final_open_orders = self.rest.open_orders()
        _require_cancelled_no_fill(
            resolved=resolved,
            cancelled=cancelled,
            final=final,
            trades=trades,
            client_order_id=state.client_order_id,
            cancel_client_order_id=state.cancel_client_order_id,
        )
        if final_open_orders:
            raise BinanceSpotTestnetError(
                "BTCUSDT open orders remain after restart recovery cancellation"
            )
        if account_fingerprint(final_account) != state.account_fingerprint:
            raise BinanceSpotTestnetError(
                "BTC or USDT account state drifted during no-fill restart recovery"
            )
        self.assert_entry_blocked(state)
        return self.store.save(
            state.model_copy(
                update={
                    "stage": "RECOVERED",
                    "blocked_entry_count": state.blocked_entry_count + 1,
                    "cancelled_order": restart_order_evidence(cancelled),
                    "final_order": restart_order_evidence(final),
                    "trades": trades_evidence(trades),
                    "final_account": account_evidence(
                        final_account,
                        assets=("BTC", "USDT"),
                    ),
                    "final_open_orders": [],
                }
            )
        )

    def engage_kill_stop(
        self,
        state: BinanceRestartSoakState,
        *,
        reason: str,
    ) -> BinanceRestartSoakState:
        if state.kill_stop_enabled:
            return state
        return self.store.save(
            state.model_copy(
                update={
                    "kill_stop_enabled": True,
                    "kill_stop_reason": reason,
                    "kill_stop_enabled_at": datetime.now(UTC),
                }
            )
        )

    def assert_entry_blocked(self, state: BinanceRestartSoakState) -> None:
        if not state.kill_stop_enabled:
            raise BinanceSpotTestnetError(
                "Kill-stop is not enabled; blocked-entry proof cannot proceed"
            )
        try:
            raise_if_entry_blocked(state)
        except BinanceSpotTestnetError as exc:
            if "kill-stop blocks" in str(exc):
                return
            raise
        raise BinanceSpotTestnetError(
            "Durable kill-stop failed to block new order entry"
        )

    def _resolve_existing(
        self,
        state: BinanceRestartSoakState,
    ) -> BinanceOrderSnapshot:
        try:
            order = self.rest.query_order(client_order_id=state.client_order_id)
        except BinanceSpotTestnetError as exc:
            if exc.error_code == -2013:
                message = (
                    "Tracked restart order history disappeared; possible Testnet reset, "
                    "no recreation"
                )
                self.store.fail(state, message, reset_detected=True)
                raise BinanceSpotTestnetError(message) from exc
            raise
        _require_resting_identity(
            order,
            client_order_id=state.client_order_id,
            maximum_notional=Decimal(self.contract.maximum_order_notional),
        )
        return order

    def _require_contract(self, state: BinanceRestartSoakState) -> None:
        if state.contract_sha256 != self.contract.contract_sha256:
            raise BinanceSpotTestnetError(
                "Restart-soak state does not belong to the frozen contract"
            )


def raise_if_entry_blocked(state: BinanceRestartSoakState) -> None:
    if state.kill_stop_enabled:
        raise BinanceSpotTestnetError(
            "Durable Binance Testnet kill-stop blocks new order entry"
        )


def run_restart_soak(
    *,
    rest: RestartSoakRestClient,
    stream_factory: Callable[[], RestartSoakStream],
    store: RestartSoakStateStore,
    contract: BinanceRestartSoakContract,
    state: BinanceRestartSoakState,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> BinanceRestartSoakState:
    if state.stage != "RECOVERED" or not state.kill_stop_enabled:
        raise BinanceSpotTestnetError(
            "Restart soak requires completed recovery with the kill-stop enabled"
        )
    if state.contract_sha256 != contract.contract_sha256:
        raise BinanceSpotTestnetError(
            "Restart-soak state does not belong to the frozen contract"
        )
    state = store.save(
        state.model_copy(
            update={
                "stage": "SOAKING",
                "soak_started_at": datetime.now(UTC),
            }
        )
    )
    started = monotonic()
    next_heartbeat = 0.0
    next_reconciliation = 0.0
    reconnect_schedule = list(contract.forced_reconnect_seconds)
    stream: RestartSoakStream | None = None
    try:
        stream = stream_factory()
        stream.connect()
        subscription_ids = [stream.subscribe()]
        heartbeat_count = 0
        reconciliation_count = 0
        reconnect_count = 0
        while True:
            elapsed = monotonic() - started
            if elapsed >= contract.soak_duration_seconds:
                break
            if elapsed < next_heartbeat:
                sleeper(
                    min(
                        next_heartbeat - elapsed,
                        contract.soak_duration_seconds - elapsed,
                    )
                )
                continue
            rest.ping()
            heartbeat_count += 1
            next_heartbeat += contract.heartbeat_interval_seconds
            if elapsed >= next_reconciliation:
                _reconcile_soak_state(rest, state)
                reconciliation_count += 1
                next_reconciliation += contract.reconciliation_interval_seconds
            if reconnect_schedule and elapsed >= reconnect_schedule[0]:
                reconnect_schedule.pop(0)
                stream.disconnect()
                stream = stream_factory()
                stream.connect()
                subscription_ids.append(stream.subscribe())
                reconnect_count += 1
            state = store.save(
                state.model_copy(
                    update={
                        "websocket_subscription_ids": subscription_ids,
                        "websocket_reconnect_count": reconnect_count,
                        "rest_heartbeat_count": heartbeat_count,
                        "reconciliation_check_count": reconciliation_count,
                        "soak_elapsed_seconds": elapsed,
                    }
                )
            )

        _reconcile_soak_state(rest, state)
        reconciliation_count += 1
        elapsed = monotonic() - started
        if stream.subscription_id is not None:
            stream.unsubscribe()
        stream.disconnect()
        stream = None
        failed_gates = _soak_failed_gates(
            contract=contract,
            elapsed=elapsed,
            heartbeat_count=heartbeat_count,
            reconciliation_count=reconciliation_count,
            reconnect_count=reconnect_count,
            subscription_ids=subscription_ids,
        )
        if failed_gates:
            return store.fail(state, "; ".join(failed_gates))
        return store.save(
            state.model_copy(
                update={
                    "stage": "PASSED",
                    "websocket_subscription_ids": subscription_ids,
                    "websocket_reconnect_count": reconnect_count,
                    "rest_heartbeat_count": heartbeat_count,
                    "reconciliation_check_count": reconciliation_count,
                    "soak_elapsed_seconds": elapsed,
                    "soak_completed_at": datetime.now(UTC),
                    "failed_gates": [],
                }
            )
        )
    except Exception as exc:
        reset_detected = (
            isinstance(exc, BinanceSpotTestnetError)
            and "reset" in str(exc).lower()
        )
        store.fail(state, str(exc), reset_detected=reset_detected)
        raise
    finally:
        if stream is not None:
            try:
                stream.disconnect()
            except Exception:
                pass


def build_restart_soak_evidence(
    state: BinanceRestartSoakState,
    contract: BinanceRestartSoakContract,
) -> dict[str, object]:
    if not restart_soak_state_verified(state, contract):
        raise ValueError("Restart-soak state failed final evidence verification")
    return {
        "schema_version": 1,
        "campaign_id": contract.contract_id,
        "contract_sha256": contract.contract_sha256,
        "run_id": state.run_id,
        "completed_at": state.soak_completed_at.isoformat()
        if state.soak_completed_at
        else None,
        "environment": contract.environment,
        "rest_url": contract.rest_url,
        "websocket_url": contract.websocket_url,
        "symbol": contract.symbol,
        "product": contract.product,
        "process_ids": state.process_ids,
        "client_order_id": state.client_order_id,
        "cancel_client_order_id": state.cancel_client_order_id,
        "blocked_client_order_id": state.blocked_client_order_id,
        "placement_request_count": state.placement_request_count,
        "idempotent_resolution_count": state.idempotent_resolution_count,
        "blocked_entry_count": state.blocked_entry_count,
        "kill_stop_enabled": state.kill_stop_enabled,
        "kill_stop_reason": state.kill_stop_reason,
        "kill_stop_enabled_at": state.kill_stop_enabled_at.isoformat()
        if state.kill_stop_enabled_at
        else None,
        "initial_open_orders": state.initial_open_orders,
        "restart_open_orders": state.restart_open_orders,
        "final_open_orders": state.final_open_orders,
        "initial_account": state.initial_account,
        "final_account": state.final_account,
        "account_fingerprint": state.account_fingerprint,
        "placed_order": state.placed_order,
        "restart_resolved_order": state.restart_resolved_order,
        "cancelled_order": state.cancelled_order,
        "final_order": state.final_order,
        "trades": state.trades,
        "websocket_subscription_ids": state.websocket_subscription_ids,
        "websocket_reconnect_count": state.websocket_reconnect_count,
        "rest_heartbeat_count": state.rest_heartbeat_count,
        "reconciliation_check_count": state.reconciliation_check_count,
        "soak_started_at": state.soak_started_at.isoformat()
        if state.soak_started_at
        else None,
        "soak_completed_at": state.soak_completed_at.isoformat()
        if state.soak_completed_at
        else None,
        "soak_elapsed_seconds": state.soak_elapsed_seconds,
        "exchange_reset_detected": state.exchange_reset_detected,
        "state_invalidated": state.state_invalidated,
        "failed_gates": state.failed_gates,
        "credentials_stored": False,
        "phase_2d_qualified": True,
        "adapter_sandbox_qualified": True,
        "sandbox_qualified": True,
        "strategy_eligible": False,
        "production_authority": False,
        "live_authority": False,
        "real_capital": False,
        "check_status": "PASS",
    }


def restart_soak_state_verified(
    state: BinanceRestartSoakState,
    contract: BinanceRestartSoakContract,
) -> bool:
    orders = (
        state.placed_order,
        state.restart_resolved_order,
        state.cancelled_order,
        state.final_order,
    )
    if (
        not audit_restart_soak_contract(contract)
        or state.state_sha256 != restart_soak_state_sha256(state)
        or state.contract_sha256 != contract.contract_sha256
        or state.stage != "PASSED"
        or len(state.process_ids) != contract.required_processes
        or len(set(state.process_ids)) != contract.required_processes
        or state.placement_request_count != 1
        or state.idempotent_resolution_count < 1
        or state.blocked_entry_count != 1
        or not state.kill_stop_enabled
        or state.initial_open_orders
        or len(state.restart_open_orders) != 1
        or state.final_open_orders
        or any(order is None for order in orders)
        or state.trades
        or state.websocket_reconnect_count != len(contract.forced_reconnect_seconds)
        or len(state.websocket_subscription_ids)
        != len(contract.forced_reconnect_seconds) + 1
        or state.rest_heartbeat_count < contract.minimum_rest_heartbeats
        or state.reconciliation_check_count < contract.minimum_reconciliation_checks
        or state.soak_elapsed_seconds < contract.soak_duration_seconds
        or state.exchange_reset_detected
        or state.state_invalidated
        or state.failed_gates
        or state.initial_account != state.final_account
        or state.credentials_stored
        or state.production_authority
        or state.live_authority
        or state.real_capital
    ):
        return False
    placed, resolved, cancelled, final = orders
    assert placed is not None
    assert resolved is not None
    assert cancelled is not None
    assert final is not None
    try:
        external_ids = {
            int(order["external_order_id"])
            for order in (placed, resolved, cancelled, final)
        }
        quantity = Decimal(str(placed["original_quantity"]))
        price = Decimal(str(placed["price"]))
        restart_order_id = int(state.restart_open_orders[0]["external_order_id"])
    except (KeyError, TypeError, ValueError):
        return False
    return all(
        (
            len(external_ids) == 1,
            restart_order_id in external_ids,
            placed.get("client_order_id") == state.client_order_id,
            resolved.get("client_order_id") == state.client_order_id,
            final.get("client_order_id") == state.client_order_id,
            cancelled.get("client_order_id") == state.cancel_client_order_id,
            cancelled.get("original_client_order_id") == state.client_order_id,
            placed.get("status") == "NEW",
            resolved.get("status") == "NEW",
            cancelled.get("status") == "CANCELED",
            final.get("status") == "CANCELED",
            quantity > 0,
            price > 0,
            quantity * price <= Decimal(contract.maximum_order_notional),
            all(
                Decimal(str(order["executed_quantity"])) == 0
                and Decimal(str(order["cumulative_quote_quantity"])) == 0
                for order in (placed, resolved, cancelled, final)
            ),
        )
    )


def restart_soak_evidence_verified(
    path: Path,
    contract: BinanceRestartSoakContract,
) -> bool:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    try:
        process_ids = payload["process_ids"]
        placed = payload["placed_order"]
        resolved = payload["restart_resolved_order"]
        cancelled = payload["cancelled_order"]
        final = payload["final_order"]
        restart_open = payload["restart_open_orders"]
    except KeyError:
        return False
    if (
        payload.get("schema_version") != 1
        or payload.get("campaign_id") != contract.contract_id
        or payload.get("contract_sha256") != contract.contract_sha256
        or payload.get("environment") != contract.environment
        or payload.get("rest_url") != contract.rest_url
        or payload.get("websocket_url") != contract.websocket_url
        or payload.get("symbol") != contract.symbol
        or payload.get("check_status") != "PASS"
        or payload.get("phase_2d_qualified") is not True
        or payload.get("adapter_sandbox_qualified") is not True
        or payload.get("sandbox_qualified") is not True
        or payload.get("strategy_eligible") is not False
        or payload.get("production_authority") is not False
        or payload.get("live_authority") is not False
        or payload.get("real_capital") is not False
        or payload.get("credentials_stored") is not False
        or not isinstance(process_ids, list)
        or len(process_ids) != contract.required_processes
        or len(set(process_ids)) != contract.required_processes
        or payload.get("placement_request_count") != 1
        or int(payload.get("idempotent_resolution_count", 0)) < 1
        or payload.get("blocked_entry_count") != 1
        or payload.get("kill_stop_enabled") is not True
        or payload.get("initial_open_orders") != []
        or not isinstance(restart_open, list)
        or len(restart_open) != 1
        or payload.get("final_open_orders") != []
        or payload.get("trades") != []
        or payload.get("initial_account") != payload.get("final_account")
        or payload.get("websocket_reconnect_count")
        != len(contract.forced_reconnect_seconds)
        or len(payload.get("websocket_subscription_ids", []))
        != len(contract.forced_reconnect_seconds) + 1
        or int(payload.get("rest_heartbeat_count", 0))
        < contract.minimum_rest_heartbeats
        or int(payload.get("reconciliation_check_count", 0))
        < contract.minimum_reconciliation_checks
        or float(payload.get("soak_elapsed_seconds", 0))
        < contract.soak_duration_seconds
        or payload.get("exchange_reset_detected") is not False
        or payload.get("state_invalidated") is not False
        or payload.get("failed_gates") != []
        or not all(
            isinstance(order, dict)
            for order in (placed, resolved, cancelled, final)
        )
    ):
        return False
    try:
        external_ids = {
            int(order["external_order_id"])
            for order in (placed, resolved, cancelled, final)
        }
        quantity = Decimal(str(placed["original_quantity"]))
        price = Decimal(str(placed["price"]))
    except (KeyError, TypeError, ValueError):
        return False
    return all(
        (
            len(external_ids) == 1,
            int(restart_open[0]["external_order_id"]) in external_ids,
            placed.get("client_order_id") == payload["client_order_id"],
            resolved.get("client_order_id") == payload["client_order_id"],
            final.get("client_order_id") == payload["client_order_id"],
            cancelled.get("client_order_id") == payload["cancel_client_order_id"],
            cancelled.get("original_client_order_id") == payload["client_order_id"],
            placed.get("status") == "NEW",
            resolved.get("status") == "NEW",
            cancelled.get("status") == "CANCELED",
            final.get("status") == "CANCELED",
            quantity > 0,
            price > 0,
            quantity * price <= Decimal(contract.maximum_order_notional),
            all(
                Decimal(str(order["executed_quantity"])) == 0
                and Decimal(str(order["cumulative_quote_quantity"])) == 0
                for order in (placed, resolved, cancelled, final)
            ),
        )
    )


def build_restart_soak_evidence_audit(
    *,
    source_path: Path,
    preserved_source_path: Path,
    contract_path: Path,
    audited_at: datetime,
) -> BinanceRestartSoakEvidenceAudit:
    source_raw = source_path.read_bytes()
    preserved_raw = preserved_source_path.read_bytes()
    if source_raw != preserved_raw:
        raise ValueError("Preserved restart-soak source is not byte-identical")
    contract = BinanceRestartSoakContract.model_validate_json(contract_path.read_bytes())
    if not audit_restart_soak_contract(contract):
        raise ValueError("Restart-soak contract is not reproducible")
    if not restart_soak_evidence_verified(source_path, contract):
        raise ValueError("Restart-soak evidence failed independent reconstruction")
    payload = json.loads(source_raw)
    final_order = payload["final_order"]
    draft = BinanceRestartSoakEvidenceAudit(
        schema_version=1,
        audit_id="binance-spot-testnet-restart-soak-audit-v1",
        audited_at=audited_at.astimezone(UTC),
        source_path=source_path.as_posix(),
        source_sha256=hashlib.sha256(source_raw).hexdigest(),
        preserved_source_path=preserved_source_path.as_posix(),
        preserved_source_sha256=hashlib.sha256(preserved_raw).hexdigest(),
        contract_path=contract_path.as_posix(),
        contract_sha256=contract.contract_sha256,
        run_id=str(payload["run_id"]),
        process_count=len(payload["process_ids"]),
        external_order_id=int(final_order["external_order_id"]),
        placement_request_count=int(payload["placement_request_count"]),
        idempotent_resolution_count=int(payload["idempotent_resolution_count"]),
        blocked_entry_count=int(payload["blocked_entry_count"]),
        kill_stop_durable=payload["kill_stop_enabled"] is True,
        no_fill_reconciliation_passed=True,
        websocket_reconnect_count=int(payload["websocket_reconnect_count"]),
        rest_heartbeat_count=int(payload["rest_heartbeat_count"]),
        reconciliation_check_count=int(payload["reconciliation_check_count"]),
        soak_elapsed_seconds=float(payload["soak_elapsed_seconds"]),
        exchange_reset_detected=False,
        independent_verifier_passed=True,
        phase_2d_qualified=True,
        adapter_sandbox_qualified=True,
        production_authority=False,
        live_authority=False,
        decision="BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED",
        audit_sha256="",
    )
    return draft.model_copy(
        update={"audit_sha256": restart_soak_audit_sha256(draft)}
    )


def restart_soak_audit_sha256(audit: BinanceRestartSoakEvidenceAudit) -> str:
    payload = audit.model_dump(mode="json")
    payload["audit_sha256"] = ""
    return _payload_sha256(payload)


def audit_restart_soak_evidence_audit(
    audit: BinanceRestartSoakEvidenceAudit,
) -> bool:
    try:
        expected = build_restart_soak_evidence_audit(
            source_path=Path(audit.source_path),
            preserved_source_path=Path(audit.preserved_source_path),
            contract_path=Path(audit.contract_path),
            audited_at=audit.audited_at,
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False
    return (
        audit == expected
        and audit.audit_sha256 == restart_soak_audit_sha256(audit)
    )


def account_fingerprint(account: BinanceAccountSnapshot) -> str:
    payload = {
        "can_trade": account.can_trade,
        "account_type": account.account_type,
        "permissions": account.permissions,
        "BTC": {
            "free": str(account.balance("BTC").free),
            "locked": str(account.balance("BTC").locked),
        },
        "USDT": {
            "free": str(account.balance("USDT").free),
            "locked": str(account.balance("USDT").locked),
        },
    }
    return _payload_sha256(payload)


def restart_order_evidence(order: BinanceOrderSnapshot) -> dict[str, object]:
    return {
        "symbol": order.symbol,
        "external_order_id": order.order_id,
        "client_order_id": order.client_order_id,
        "original_client_order_id": order.original_client_order_id,
        "status": order.status,
        "side": order.side,
        "type": order.order_type,
        "price": str(order.price),
        "original_quantity": str(order.original_quantity),
        "original_quote_order_quantity": str(order.original_quote_order_quantity),
        "executed_quantity": str(order.executed_quantity),
        "cumulative_quote_quantity": str(order.cumulative_quote_quantity),
        "transact_time_ms": order.transact_time_ms,
    }


def _reconcile_soak_state(
    rest: RestartSoakRestClient,
    state: BinanceRestartSoakState,
) -> None:
    if not state.kill_stop_enabled:
        raise BinanceSpotTestnetError("Durable kill-stop was disabled during the soak")
    if state.final_order is None:
        raise BinanceSpotTestnetError("Final tracked order is absent during soak")
    order_id = int(state.final_order["external_order_id"])
    try:
        order = rest.query_order(order_id=order_id)
    except BinanceSpotTestnetError as exc:
        if exc.error_code == -2013:
            raise BinanceSpotTestnetError(
                "Tracked order history disappeared during soak; possible Testnet reset"
            ) from exc
        raise
    if (
        order.status != "CANCELED"
        or order.client_order_id != state.client_order_id
        or order.executed_quantity != 0
        or order.cumulative_quote_quantity != 0
    ):
        raise BinanceSpotTestnetError(
            "Tracked order changed after restart cancellation"
        )
    if rest.open_orders():
        raise BinanceSpotTestnetError("BTCUSDT open order appeared during kill-stop soak")
    if account_fingerprint(rest.account_snapshot()) != state.account_fingerprint:
        raise BinanceSpotTestnetError(
            "Account drift or possible Testnet reset detected during soak"
        )


def _soak_failed_gates(
    *,
    contract: BinanceRestartSoakContract,
    elapsed: float,
    heartbeat_count: int,
    reconciliation_count: int,
    reconnect_count: int,
    subscription_ids: list[int],
) -> list[str]:
    failures: list[str] = []
    if elapsed < contract.soak_duration_seconds:
        failures.append("soak duration was shorter than the frozen contract")
    if heartbeat_count < contract.minimum_rest_heartbeats:
        failures.append("REST heartbeat minimum was not met")
    if reconciliation_count < contract.minimum_reconciliation_checks:
        failures.append("authenticated reconciliation minimum was not met")
    if reconnect_count != len(contract.forced_reconnect_seconds):
        failures.append("forced WebSocket reconnect count did not match")
    if len(subscription_ids) != len(contract.forced_reconnect_seconds) + 1:
        failures.append("WebSocket signature-subscription count did not match")
    if any(value < 0 for value in subscription_ids):
        failures.append("WebSocket subscription ID is invalid")
    return failures


def _require_resting_identity(
    order: BinanceOrderSnapshot,
    *,
    client_order_id: str,
    maximum_notional: Decimal,
) -> None:
    if not all(
        (
            order.symbol == TESTNET_SYMBOL,
            order.order_id > 0,
            order.client_order_id == client_order_id,
            order.status == "NEW",
            order.side == "BUY",
            order.order_type == "LIMIT",
            order.original_quantity > 0,
            order.price > 0,
            order.original_quantity * order.price <= maximum_notional,
            order.executed_quantity == 0,
            order.cumulative_quote_quantity == 0,
        )
    ):
        raise BinanceSpotTestnetError(
            "Restart-soak resting order identity or no-fill boundary failed"
        )


def _require_cancelled_no_fill(
    *,
    resolved: BinanceOrderSnapshot,
    cancelled: BinanceOrderSnapshot,
    final: BinanceOrderSnapshot,
    trades: tuple[BinanceTradeSnapshot, ...],
    client_order_id: str,
    cancel_client_order_id: str,
) -> None:
    if not all(
        (
            resolved.order_id == cancelled.order_id == final.order_id,
            resolved.client_order_id == client_order_id,
            cancelled.client_order_id == cancel_client_order_id,
            cancelled.original_client_order_id == client_order_id,
            final.client_order_id == client_order_id,
            resolved.status == "NEW",
            cancelled.status == final.status == "CANCELED",
            resolved.original_quantity
            == cancelled.original_quantity
            == final.original_quantity,
            resolved.executed_quantity
            == cancelled.executed_quantity
            == final.executed_quantity
            == 0,
            resolved.cumulative_quote_quantity
            == cancelled.cumulative_quote_quantity
            == final.cumulative_quote_quantity
            == 0,
            not trades,
        )
    ):
        raise BinanceSpotTestnetError(
            "Restart-soak cancellation did not reconcile exactly with zero fills"
        )


def _ambiguous_order_error(exc: BinanceSpotTestnetError) -> bool:
    return exc.status_code is None or exc.status_code >= 500 or exc.error_code == -1007


def _payload_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
