from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

from aurex.broker_engine.binance_spot_testnet import (
    BinanceOrderSnapshot,
    BinanceSpotTestnetClient,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
    deterministic_client_order_id,
    reconcile_virtual_cancel_snapshots,
)


class VirtualCancelLifecycle(NamedTuple):
    placed: BinanceOrderSnapshot
    queried: BinanceOrderSnapshot
    cancelled: BinanceOrderSnapshot
    final: BinanceOrderSnapshot


def run_virtual_cancel_lifecycle(
    client: BinanceSpotTestnetClient,
    *,
    quantity: Decimal,
    price: Decimal,
    client_order_id: str,
    cancel_client_order_id: str,
    on_checkpoint: Callable[[str, BinanceOrderSnapshot], None] | None = None,
) -> VirtualCancelLifecycle:
    def checkpoint(stage: str, snapshot: BinanceOrderSnapshot) -> None:
        if on_checkpoint is not None:
            on_checkpoint(stage, snapshot)

    try:
        placed = client.place_limit_order(
            side="BUY",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
    except BinanceSpotTestnetError as placement_error:
        if placement_error.status_code is not None:
            raise
        try:
            placed = client.query_order(client_order_id=client_order_id)
        except BinanceSpotTestnetError:
            raise placement_error from None
    checkpoint("placed", placed)

    cancelled: BinanceOrderSnapshot | None = None
    try:
        queried = client.query_order(client_order_id=client_order_id)
        checkpoint("queried", queried)
        cancelled = client.cancel_order(
            client_order_id=client_order_id,
            new_client_order_id=cancel_client_order_id,
        )
        checkpoint("cancelled", cancelled)
        final = client.query_order(order_id=cancelled.order_id)
        checkpoint("final", final)
    except BinanceSpotTestnetError:
        if cancelled is None:
            try:
                cleanup = client.cancel_order(
                    client_order_id=client_order_id,
                    new_client_order_id=cancel_client_order_id,
                )
                checkpoint("cleanup_cancelled", cleanup)
            except BinanceSpotTestnetError:
                pass
        raise
    return VirtualCancelLifecycle(placed, queried, cancelled, final)


def snapshot_evidence(snapshot: BinanceOrderSnapshot) -> dict[str, object]:
    return {
        "external_order_id": snapshot.order_id,
        "client_order_id": snapshot.client_order_id,
        "original_client_order_id": snapshot.original_client_order_id,
        "status": snapshot.status,
        "quantity": str(snapshot.original_quantity),
        "executed_quantity": str(snapshot.executed_quantity),
        "cumulative_quote_quantity": str(snapshot.cumulative_quote_quantity),
    }


def persist_evidence(evidence: dict[str, object], output: Path | None) -> str:
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        part_path = output.with_suffix(f"{output.suffix}.part")
        part_path.write_text(f"{rendered}\n", encoding="utf-8")
        part_path.replace(output)
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a non-production Binance Spot Testnet qualification check."
    )
    parser.add_argument(
        "--mode",
        choices=("public", "authenticated", "test-order", "virtual-cancel"),
        default="public",
    )
    parser.add_argument(
        "--acknowledge-testnet-virtual-order",
        action="store_true",
        help="Required for virtual-cancel mode; never enables production or real capital.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "virtual-cancel" and not args.acknowledge_testnet_virtual_order:
        raise BinanceSpotTestnetError(
            "virtual-cancel requires explicit Testnet virtual-order acknowledgement"
        )
    checked_at = datetime.now(UTC)
    credentials = None if args.mode == "public" else BinanceTestnetCredentials.from_environment()
    client = BinanceSpotTestnetClient(
        credentials=credentials,
        virtual_order_entry_enabled=args.mode == "virtual-cancel",
    )
    client.ping()
    offset_ms = client.synchronize_time()
    rules = client.symbol_rules()
    market_price = client.ticker_price()
    average_price = client.average_price(expected_minutes=rules.percent_average_price_minutes)
    best_bid_price = client.best_bid_price()
    preview_quantity, preview_price = rules.bounded_test_order(
        market_price,
        average_price,
        best_bid_price,
    )

    evidence: dict[str, object] = {
        "schema_version": 1,
        "checked_at": checked_at.isoformat(),
        "environment": client.environment,
        "base_url": client.base_url,
        "mode": args.mode,
        "public_connectivity": "PASS",
        "server_time_offset_ms": offset_ms,
        "symbol": rules.symbol,
        "symbol_status": rules.status,
        "spot_scope": True,
        "market_price": str(market_price),
        "average_price": str(average_price),
        "best_bid_price": str(best_bid_price),
        "resting_order_preview": {
            "side": "BUY",
            "quantity": str(preview_quantity),
            "price": str(preview_price),
            "notional": str(preview_quantity * preview_price),
            "percent_reference_price": str(average_price),
            "percent_average_price_minutes": rules.percent_average_price_minutes,
            "below_best_bid": preview_price < best_bid_price,
            "submitted": False,
        },
        "credentials_stored": False,
        "production_authority": False,
        "live_authority": False,
        "virtual_order_submitted": False,
        "sandbox_qualified": False,
        "check_status": "IN_PROGRESS",
    }

    if args.mode in {"authenticated", "test-order", "virtual-cancel"}:
        account = client.account_snapshot()
        evidence["authenticated_account_read"] = "PASS"
        evidence["account"] = {
            "account_type": account.account_type,
            "can_trade": account.can_trade,
            "permissions": list(account.permissions),
            "nonzero_asset_count": len(account.nonzero_assets),
            "relevant_nonzero_assets": [
                asset for asset in account.nonzero_assets if asset in {"BTC", "USDT"}
            ],
            "maker_commission": (
                str(account.maker_commission) if account.maker_commission is not None else None
            ),
            "taker_commission": (
                str(account.taker_commission) if account.taker_commission is not None else None
            ),
        }

    if args.mode in {"test-order", "virtual-cancel"}:
        quantity, price = preview_quantity, preview_price
        client_order_id = deterministic_client_order_id(
            "validation",
            f"{checked_at.date().isoformat()}|{rules.symbol}|{quantity}|{price}",
        )
        client.test_limit_order(
            side="BUY",
            quantity=quantity,
            price=price,
            client_order_id=client_order_id,
        )
        evidence["signed_test_order"] = "PASS"
        evidence["test_order"] = {
            "side": "BUY",
            "quantity": str(quantity),
            "price": str(price),
            "notional": str(quantity * price),
            "client_order_id": client_order_id,
            "entered_matching_engine": False,
        }

    if args.mode == "virtual-cancel":
        lifecycle_client_order_id = deterministic_client_order_id(
            "cancel",
            f"{checked_at.isoformat()}|{rules.symbol}|{quantity}|{price}",
        )
        cancellation_client_order_id = deterministic_client_order_id(
            "cancel-op",
            f"{lifecycle_client_order_id}|{checked_at.isoformat()}",
        )
        lifecycle_progress: dict[str, object] = {}

        def record_checkpoint(stage: str, snapshot: BinanceOrderSnapshot) -> None:
            lifecycle_progress[stage] = snapshot_evidence(snapshot)
            evidence["virtual_order_submitted"] = True
            evidence["virtual_order_progress"] = lifecycle_progress
            persist_evidence(evidence, args.output)

        try:
            placed, queried, cancelled, final = run_virtual_cancel_lifecycle(
                client,
                quantity=quantity,
                price=price,
                client_order_id=lifecycle_client_order_id,
                cancel_client_order_id=cancellation_client_order_id,
                on_checkpoint=record_checkpoint,
            )
        except BinanceSpotTestnetError as exc:
            evidence["check_status"] = "FAIL"
            evidence["failed_stage"] = "virtual_cancel_lifecycle"
            evidence["qualification_blocker"] = str(exc)
            print(persist_evidence(evidence, args.output))
            return 1
        reconciliation = reconcile_virtual_cancel_snapshots(
            placed=placed,
            queried=queried,
            cancelled=cancelled,
            final=final,
            placement_client_order_id=lifecycle_client_order_id,
            cancellation_client_order_id=cancellation_client_order_id,
            expected_quantity=quantity,
        )
        order_identity_matches = (
            reconciliation.external_order_identity_matches
            and reconciliation.placement_identity_matches
            and reconciliation.cancellation_identity_matches
        )
        reconciliation_passed = reconciliation.passed
        evidence["virtual_order_submitted"] = True
        evidence["virtual_cancel_lifecycle"] = (
            "PASS"
            if reconciliation.lifecycle_status_matches and reconciliation.no_fill_occurred
            else "FAIL"
        )
        evidence["order_reconciliation"] = "PASS" if reconciliation_passed else "FAIL"
        evidence["virtual_order"] = {
            "symbol": final.symbol,
            "side": final.side,
            "type": final.order_type,
            "quantity": str(quantity),
            "price": str(price),
            "notional": str(quantity * price),
            "client_order_id": lifecycle_client_order_id,
            "cancel_client_order_id": cancellation_client_order_id,
            "external_order_id": final.order_id,
            "placed_status": placed.status,
            "queried_status": queried.status,
            "cancel_status": cancelled.status,
            "final_status": final.status,
            "executed_quantity": str(final.executed_quantity),
            "order_identity_matches": order_identity_matches,
            "external_order_identity_matches": (reconciliation.external_order_identity_matches),
            "placement_identity_matches": reconciliation.placement_identity_matches,
            "cancellation_identity_matches": (reconciliation.cancellation_identity_matches),
            "quantity_matches": reconciliation.quantity_matches,
            "no_fill_occurred": reconciliation.no_fill_occurred,
            "lifecycle_status_matches": reconciliation.lifecycle_status_matches,
            "production_authority": False,
            "real_capital": False,
        }
        if not reconciliation_passed:
            evidence["qualification_blocker"] = (
                "Virtual cancel lifecycle did not reconcile exactly; "
                "sandbox qualification remains blocked."
            )

    evidence["check_status"] = "PASS"
    print(persist_evidence(evidence, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
