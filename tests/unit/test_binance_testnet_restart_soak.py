from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aurex.broker_engine.binance_spot_testnet import (
    BinanceAccountSnapshot,
    BinanceAssetBalance,
    BinanceOrderSnapshot,
    BinanceSpotSymbolRules,
    BinanceSpotTestnetError,
    deterministic_client_order_id,
)
from aurex.broker_engine.binance_testnet_restart_soak import (
    BinanceRestartSoakGuard,
    RestartSoakStateStore,
    audit_restart_soak_contract,
    audit_restart_soak_evidence_audit,
    build_restart_soak_contract,
    build_restart_soak_evidence,
    build_restart_soak_evidence_audit,
    restart_soak_evidence_verified,
    restart_soak_state_verified,
    run_restart_soak,
)


def rules() -> BinanceSpotSymbolRules:
    return BinanceSpotSymbolRules(
        symbol="BTCUSDT",
        status="TRADING",
        base_asset="BTC",
        quote_asset="USDT",
        tick_size=Decimal("0.01"),
        min_price=Decimal("0.01"),
        max_price=Decimal("1000000"),
        step_size=Decimal("0.00001"),
        min_quantity=Decimal("0.00001"),
        max_quantity=Decimal("100"),
        market_step_size=Decimal("0.00001"),
        market_min_quantity=Decimal("0.00001"),
        market_max_quantity=Decimal("100"),
        min_notional=Decimal("5"),
        max_notional=Decimal("1000000"),
        notional_applies_to_market=True,
        maximum_notional_applies_to_market=False,
        market_order_allowed=True,
        quote_order_quantity_market_allowed=True,
        bid_multiplier_up=Decimal("2"),
        bid_multiplier_down=Decimal("0.5"),
        ask_multiplier_up=Decimal("2"),
        ask_multiplier_down=Decimal("0.5"),
        percent_average_price_minutes=5,
    )


def account() -> BinanceAccountSnapshot:
    return BinanceAccountSnapshot(
        can_trade=True,
        account_type="SPOT",
        permissions=("SPOT",),
        nonzero_assets=("BTC", "USDT"),
        maker_commission=Decimal("0"),
        taker_commission=Decimal("0"),
        balances=(
            BinanceAssetBalance(
                asset="BTC",
                free=Decimal("1"),
                locked=Decimal("0"),
            ),
            BinanceAssetBalance(
                asset="USDT",
                free=Decimal("10000"),
                locked=Decimal("0"),
            ),
        ),
    )


def order(
    *,
    client_order_id: str,
    status: str,
    original_client_order_id: str | None = None,
) -> BinanceOrderSnapshot:
    return BinanceOrderSnapshot(
        symbol="BTCUSDT",
        order_id=9001,
        client_order_id=client_order_id,
        status=status,
        side="BUY",
        order_type="LIMIT",
        price=Decimal("89999.99"),
        original_quantity=Decimal("0.00006"),
        executed_quantity=Decimal("0"),
        cumulative_quote_quantity=Decimal("0"),
        original_quote_order_quantity=Decimal("0"),
        transact_time_ms=1_000,
        original_client_order_id=original_client_order_id,
    )


class FakeRest:
    def __init__(self) -> None:
        self.placement_count = 0
        self.current: BinanceOrderSnapshot | None = None
        self.reset = False
        self.account = account()

    def ping(self) -> None:
        return None

    def account_snapshot(self) -> BinanceAccountSnapshot:
        return self.account

    def symbol_rules(self) -> BinanceSpotSymbolRules:
        return rules()

    def ticker_price(self) -> Decimal:
        return Decimal("100000")

    def average_price(self, *, expected_minutes: int | None = None) -> Decimal:
        assert expected_minutes in (None, 5)
        return Decimal("100000")

    def best_bid_price(self) -> Decimal:
        return Decimal("99999.99")

    def open_orders(self) -> tuple[BinanceOrderSnapshot, ...]:
        if self.reset:
            return ()
        if self.current is not None and self.current.status == "NEW":
            return (self.current,)
        return ()

    def place_limit_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        price: Decimal,
        client_order_id: str,
    ) -> BinanceOrderSnapshot:
        assert side == "BUY"
        assert quantity == Decimal("0.00006")
        assert price == Decimal("89999.99")
        self.placement_count += 1
        self.current = order(client_order_id=client_order_id, status="NEW")
        return self.current

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot:
        if self.reset or self.current is None:
            raise BinanceSpotTestnetError(
                "Order does not exist",
                status_code=400,
                error_code=-2013,
            )
        assert client_order_id is None or client_order_id in {
            self.current.client_order_id,
            self.current.original_client_order_id,
        }
        assert order_id is None or order_id == self.current.order_id
        if self.current.status == "CANCELED":
            return order(
                client_order_id=self.current.original_client_order_id or "",
                status="CANCELED",
            )
        return self.current

    def cancel_order(
        self,
        *,
        client_order_id: str,
        new_client_order_id: str | None = None,
    ) -> BinanceOrderSnapshot:
        assert self.current is not None
        assert self.current.client_order_id == client_order_id
        assert new_client_order_id is not None
        self.current = order(
            client_order_id=new_client_order_id,
            status="CANCELED",
            original_client_order_id=client_order_id,
        )
        return self.current

    def account_trades(self, *, order_id: int) -> tuple:
        assert order_id == 9001
        return ()


class FakeStream:
    def __init__(self) -> None:
        self._subscription_id: int | None = None

    @property
    def subscription_id(self) -> int | None:
        return self._subscription_id

    def connect(self) -> None:
        return None

    def subscribe(self) -> int:
        self._subscription_id = 0
        return 0

    def unsubscribe(self) -> None:
        self._subscription_id = None

    def disconnect(self) -> None:
        self._subscription_id = None


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


class LatencyRest(FakeRest):
    def __init__(self, clock: FakeClock) -> None:
        super().__init__()
        self.clock = clock

    def ping(self) -> None:
        self.clock.value += 0.1

    def account_snapshot(self) -> BinanceAccountSnapshot:
        self.clock.value += 0.1
        return super().account_snapshot()

    def open_orders(self) -> tuple[BinanceOrderSnapshot, ...]:
        self.clock.value += 0.1
        return super().open_orders()

    def query_order(
        self,
        *,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> BinanceOrderSnapshot:
        self.clock.value += 0.1
        return super().query_order(
            client_order_id=client_order_id,
            order_id=order_id,
        )


def create_state(store: RestartSoakStateStore, contract_sha256: str):
    run_id = "restart-soak-unit"
    return store.create(
        run_id=run_id,
        contract_sha256=contract_sha256,
        client_order_id=deterministic_client_order_id("restart", run_id),
        cancel_client_order_id=deterministic_client_order_id(
            "restart-x",
            run_id,
        ),
        blocked_client_order_id=deterministic_client_order_id(
            "kill-proof",
            run_id,
        ),
    )


def test_restart_soak_contract_is_reproducible() -> None:
    contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )

    assert audit_restart_soak_contract(contract) is True
    assert contract.soak_duration_seconds == 600
    assert contract.maximum_orders == 1
    assert contract.production_authority is False


def test_state_store_rejects_tampering(tmp_path: Path) -> None:
    contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    store = RestartSoakStateStore(tmp_path / "state.json")
    create_state(store, contract.contract_sha256)
    payload = json.loads(store.path.read_text(encoding="utf-8"))
    payload["kill_stop_enabled"] = True
    store.path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BinanceSpotTestnetError, match="hash"):
        store.load()


def test_restart_recovery_is_idempotent_and_kill_stop_blocks_entry(
    tmp_path: Path,
) -> None:
    contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    store = RestartSoakStateStore(tmp_path / "state.json")
    rest = FakeRest()
    guard = BinanceRestartSoakGuard(rest=rest, store=store, contract=contract)
    state = guard.prepare(create_state(store, contract.contract_sha256))

    recovered = guard.recover(state)

    assert rest.placement_count == 1
    assert recovered.idempotent_resolution_count == 1
    assert recovered.blocked_entry_count == 1
    assert recovered.kill_stop_enabled is True
    assert recovered.final_order is not None
    assert recovered.final_order["status"] == "CANCELED"
    assert recovered.trades == []


def test_restart_missing_order_detects_reset_without_resubmission(
    tmp_path: Path,
) -> None:
    contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    store = RestartSoakStateStore(tmp_path / "state.json")
    rest = FakeRest()
    guard = BinanceRestartSoakGuard(rest=rest, store=store, contract=contract)
    state = guard.prepare(create_state(store, contract.contract_sha256))
    rest.reset = True

    with pytest.raises(BinanceSpotTestnetError, match="reset"):
        guard.recover(state)

    failed = store.load()
    assert rest.placement_count == 1
    assert failed.stage == "FAILED"
    assert failed.exchange_reset_detected is True
    assert failed.state_invalidated is True
    assert failed.kill_stop_enabled is True


def test_full_soak_qualifies_only_the_testnet_adapter(tmp_path: Path) -> None:
    contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    store = RestartSoakStateStore(tmp_path / "state.json")
    rest = FakeRest()
    guard = BinanceRestartSoakGuard(rest=rest, store=store, contract=contract)
    state = guard.prepare(create_state(store, contract.contract_sha256))
    state = guard.recover(state)
    state = store.save(
        state.model_copy(update={"process_ids": [101, 202, 303]})
    )
    clock = FakeClock()

    passed = run_restart_soak(
        rest=rest,
        stream_factory=FakeStream,
        store=store,
        contract=contract,
        state=state,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert passed.stage == "PASSED"
    assert passed.soak_elapsed_seconds == 600
    assert passed.rest_heartbeat_count == 120
    assert passed.reconciliation_check_count == 21
    assert passed.websocket_reconnect_count == 2
    assert restart_soak_state_verified(passed, contract) is True
    evidence = build_restart_soak_evidence(passed, contract)
    assert evidence["adapter_sandbox_qualified"] is True
    assert evidence["strategy_eligible"] is False
    assert evidence["production_authority"] is False
    contract_path = tmp_path / "contract.json"
    source_path = tmp_path / "evidence.json"
    preserved_path = tmp_path / "preserved.json"
    contract_path.write_text(contract.model_dump_json(), encoding="utf-8")
    source_path.write_text(json.dumps(evidence), encoding="utf-8")
    preserved_path.write_bytes(source_path.read_bytes())
    assert restart_soak_evidence_verified(source_path, contract) is True
    audit = build_restart_soak_evidence_audit(
        source_path=source_path,
        preserved_source_path=preserved_path,
        contract_path=contract_path,
        audited_at=datetime(2026, 7, 31, 1, tzinfo=UTC),
    )
    assert audit_restart_soak_evidence_audit(audit) is True
    assert audit.adapter_sandbox_qualified is True
    assert audit.live_authority is False


def test_soak_uses_absolute_deadlines_instead_of_accumulating_request_drift(
    tmp_path: Path,
) -> None:
    base_contract = build_restart_soak_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    contract = base_contract.model_copy(
        update={
            "soak_duration_seconds": 60,
            "reconciliation_interval_seconds": 10,
            "forced_reconnect_seconds": (20, 40),
            "minimum_rest_heartbeats": 12,
            "minimum_reconciliation_checks": 6,
        }
    )
    store = RestartSoakStateStore(tmp_path / "state.json")
    clock = FakeClock()
    rest = LatencyRest(clock)
    guard = BinanceRestartSoakGuard(rest=rest, store=store, contract=contract)
    state = guard.prepare(create_state(store, contract.contract_sha256))
    state = guard.recover(state)

    passed = run_restart_soak(
        rest=rest,
        stream_factory=FakeStream,
        store=store,
        contract=contract,
        state=state,
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert passed.stage == "PASSED"
    assert passed.rest_heartbeat_count == 12
    assert passed.reconciliation_check_count == 7
    assert passed.soak_elapsed_seconds >= 60
