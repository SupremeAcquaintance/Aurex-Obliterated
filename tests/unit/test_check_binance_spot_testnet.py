from decimal import Decimal

import pytest

from aurex.broker_engine.binance_spot_testnet import (
    BinanceOrderSnapshot,
    BinanceSpotTestnetError,
)
from scripts.check_binance_spot_testnet import run_virtual_cancel_lifecycle


def order_snapshot(status: str) -> BinanceOrderSnapshot:
    return BinanceOrderSnapshot(
        symbol="BTCUSDT",
        order_id=42,
        client_order_id="aurex-cancel-1234567890abcdef",
        status=status,
        side="BUY",
        order_type="LIMIT",
        price=Decimal("50000"),
        original_quantity=Decimal("0.0001"),
        executed_quantity=Decimal("0"),
        cumulative_quote_quantity=Decimal("0"),
        original_quote_order_quantity=Decimal("0"),
        transact_time_ms=1_000,
        original_client_order_id=None,
    )


class UncertainPlacementClient:
    def __init__(self) -> None:
        self.query_results = [
            order_snapshot("NEW"),
            order_snapshot("NEW"),
            order_snapshot("CANCELED"),
        ]
        self.cancel_calls = 0

    def place_limit_order(self, **_: object) -> BinanceOrderSnapshot:
        raise BinanceSpotTestnetError("network outcome uncertain")

    def query_order(self, **_: object) -> BinanceOrderSnapshot:
        return self.query_results.pop(0)

    def cancel_order(self, **_: object) -> BinanceOrderSnapshot:
        self.cancel_calls += 1
        return order_snapshot("CANCELED")


class QueryFailureClient:
    def __init__(self) -> None:
        self.cancel_calls = 0

    def place_limit_order(self, **_: object) -> BinanceOrderSnapshot:
        return order_snapshot("NEW")

    def query_order(self, **_: object) -> BinanceOrderSnapshot:
        raise BinanceSpotTestnetError("query failed")

    def cancel_order(self, **_: object) -> BinanceOrderSnapshot:
        self.cancel_calls += 1
        return order_snapshot("CANCELED")


class FinalQueryFailureClient:
    def __init__(self) -> None:
        self.query_calls = 0
        self.cancel_calls = 0

    def place_limit_order(self, **_: object) -> BinanceOrderSnapshot:
        return order_snapshot("NEW")

    def query_order(self, **_: object) -> BinanceOrderSnapshot:
        self.query_calls += 1
        if self.query_calls == 1:
            return order_snapshot("NEW")
        raise BinanceSpotTestnetError("final query failed")

    def cancel_order(self, **_: object) -> BinanceOrderSnapshot:
        self.cancel_calls += 1
        return order_snapshot("CANCELED")


def test_uncertain_placement_recovers_by_client_id_without_resubmission() -> None:
    client = UncertainPlacementClient()

    lifecycle = run_virtual_cancel_lifecycle(
        client,  # type: ignore[arg-type]
        quantity=Decimal("0.0001"),
        price=Decimal("50000"),
        client_order_id="aurex-cancel-1234567890abcdef",
        cancel_client_order_id="aurex-cancel-op-1234567890abcdef",
    )

    assert lifecycle.placed.status == "NEW"
    assert lifecycle.final.status == "CANCELED"
    assert client.cancel_calls == 1


def test_post_placement_failure_attempts_cleanup_cancellation() -> None:
    client = QueryFailureClient()

    with pytest.raises(BinanceSpotTestnetError, match="query failed"):
        run_virtual_cancel_lifecycle(
            client,  # type: ignore[arg-type]
            quantity=Decimal("0.0001"),
            price=Decimal("50000"),
            client_order_id="aurex-cancel-1234567890abcdef",
            cancel_client_order_id="aurex-cancel-op-1234567890abcdef",
        )

    assert client.cancel_calls == 1


def test_final_query_failure_preserves_cancel_checkpoint_without_second_cancel() -> None:
    client = FinalQueryFailureClient()
    checkpoints: list[str] = []

    with pytest.raises(BinanceSpotTestnetError, match="final query failed"):
        run_virtual_cancel_lifecycle(
            client,  # type: ignore[arg-type]
            quantity=Decimal("0.0001"),
            price=Decimal("50000"),
            client_order_id="aurex-cancel-1234567890abcdef",
            cancel_client_order_id="aurex-cancel-op-1234567890abcdef",
            on_checkpoint=lambda stage, _: checkpoints.append(stage),
        )

    assert checkpoints == ["placed", "queried", "cancelled"]
    assert client.cancel_calls == 1
