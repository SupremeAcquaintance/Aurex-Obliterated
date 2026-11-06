from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.broker_engine.binance_spot_testnet import (  # noqa: E402
    BinanceAccountSnapshot,
    BinanceOrderSnapshot,
    BinanceSpotTestnetClient,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
    BinanceTradeSnapshot,
    deterministic_client_order_id,
)
from aurex.broker_engine.binance_testnet_fill_campaign import (  # noqa: E402
    ACKNOWLEDGEMENT_PHRASE,
    DEFAULT_CONTRACT_PATH,
    MAXIMUM_ORDER_NOTIONAL,
    BinanceFillFeeContract,
    account_evidence,
    audit_fill_fee_contract,
    order_evidence,
    run_bounded_fill_campaign,
    trades_evidence,
)


def persist_evidence(evidence: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    part_path = output.with_suffix(f"{output.suffix}.part")
    part_path.write_text(f"{rendered}\n", encoding="utf-8")
    part_path.replace(output)


def checkpoint_evidence(stage: str, value: object) -> object:
    if isinstance(value, BinanceAccountSnapshot):
        return account_evidence(value, assets=("BTC", "USDT"))
    if isinstance(value, BinanceOrderSnapshot):
        return order_evidence(value)
    if isinstance(value, tuple) and all(
        isinstance(item, BinanceTradeSnapshot) for item in value
    ):
        return trades_evidence(value)
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported campaign checkpoint type: {type(value).__name__}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one bounded, non-production Binance Spot Testnet fill, fee, and "
            "balance reconciliation campaign."
        )
    )
    parser.add_argument(
        "--acknowledgement",
        required=True,
        help="Must exactly match the acknowledgement frozen in the campaign contract.",
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.acknowledgement != ACKNOWLEDGEMENT_PHRASE:
        raise BinanceSpotTestnetError(
            "Fill campaign requires the exact frozen Testnet acknowledgement phrase"
        )
    if args.output.exists():
        raise BinanceSpotTestnetError(
            "Campaign evidence already exists; refusing to overwrite or resubmit"
        )
    contract = BinanceFillFeeContract.model_validate_json(args.contract.read_bytes())
    if not audit_fill_fee_contract(contract):
        raise BinanceSpotTestnetError("Frozen fill-and-fee contract is not reproducible")
    if args.acknowledgement != contract.acknowledgement_phrase:
        raise BinanceSpotTestnetError("Acknowledgement does not match the frozen contract")

    checked_at = datetime.now(UTC)
    run_key = (
        f"{contract.contract_sha256}|{checked_at.isoformat()}|{args.output.as_posix()}"
    )
    buy_client_order_id = deterministic_client_order_id("fill-buy", run_key)
    sell_client_order_id = deterministic_client_order_id("fill-sell", run_key)
    cleanup_client_order_id = deterministic_client_order_id("cleanup", run_key)
    evidence: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": contract.contract_id,
        "contract_sha256": contract.contract_sha256,
        "checked_at": checked_at.isoformat(),
        "environment": contract.environment,
        "base_url": contract.base_url,
        "symbol": contract.symbol,
        "product": contract.product,
        "buy_quote_order_quantity": contract.buy_quote_order_quantity,
        "maximum_order_notional": contract.maximum_order_notional,
        "maximum_round_trip_loss": contract.maximum_round_trip_loss,
        "client_order_ids": {
            "buy": buy_client_order_id,
            "sell": sell_client_order_id,
            "cleanup": cleanup_client_order_id,
        },
        "credentials_stored": False,
        "production_authority": False,
        "live_authority": False,
        "real_capital": False,
        "sandbox_qualified": False,
        "check_status": "IN_PROGRESS",
        "checkpoints": {},
    }
    persist_evidence(evidence, args.output)

    try:
        credentials = BinanceTestnetCredentials.from_environment()
        client = BinanceSpotTestnetClient(
            credentials=credentials,
            maximum_virtual_notional=MAXIMUM_ORDER_NOTIONAL,
            virtual_fill_entry_enabled=True,
        )
        client.ping()
        evidence["public_connectivity"] = "PASS"
        evidence["server_time_offset_ms"] = client.synchronize_time()
        persist_evidence(evidence, args.output)

        checkpoints = evidence["checkpoints"]
        if not isinstance(checkpoints, dict):
            raise TypeError("Campaign checkpoint ledger is invalid")

        def record_checkpoint(stage: str, value: object) -> None:
            checkpoints[stage] = checkpoint_evidence(stage, value)
            persist_evidence(evidence, args.output)

        result = run_bounded_fill_campaign(
            client,
            buy_client_order_id=buy_client_order_id,
            sell_client_order_id=sell_client_order_id,
            cleanup_client_order_id=cleanup_client_order_id,
            contract=contract,
            on_checkpoint=record_checkpoint,
        )
        commission_assets = sorted(
            {
                trade.commission_asset
                for trade in result.buy.trades
            }
            | {
                trade.commission_asset
                for sell in result.sells
                for trade in sell.trades
            }
        )
        evidence["initial_account"] = account_evidence(
            result.initial_account,
            assets=("BTC", "USDT", *commission_assets),
        )
        evidence["final_account"] = account_evidence(
            result.final_account,
            assets=("BTC", "USDT", *commission_assets),
        )
        evidence["buy_order"] = {
            **order_evidence(result.buy.order),
            "trades": trades_evidence(result.buy.trades),
            "reconciliation_passed": result.buy.reconciliation.passed,
            "commission_by_asset": {
                asset: str(amount)
                for asset, amount in result.buy.reconciliation.commission_by_asset.items()
            },
        }
        evidence["sell_orders"] = [
            {
                "purpose": sell.purpose,
                **order_evidence(sell.order),
                "trades": trades_evidence(sell.trades),
                "reconciliation_passed": sell.reconciliation.passed,
                "commission_by_asset": {
                    asset: str(amount)
                    for asset, amount in sell.reconciliation.commission_by_asset.items()
                },
            }
            for sell in result.sells
        ]
        evidence["balance_reconciliation"] = {
            "passed": result.balance_reconciliation.passed,
            "expected_deltas": {
                asset: str(amount)
                for asset, amount in result.balance_reconciliation.expected_deltas.items()
                if amount != 0
            },
            "observed_deltas": {
                asset: str(amount)
                for asset, amount in result.balance_reconciliation.observed_deltas.items()
                if amount != 0
            },
            "mismatches": {
                asset: {
                    "expected": str(values["expected"]),
                    "observed": str(values["observed"]),
                }
                for asset, values in result.balance_reconciliation.mismatches.items()
            },
        }
        evidence["sold_base_quantity"] = str(result.sold_base_quantity)
        evidence["expected_base_residual"] = str(result.expected_base_residual)
        evidence["round_trip_quote_delta"] = str(result.round_trip_quote_delta)
        evidence["cleanup_order_used"] = result.cleanup_order_used
        evidence["cleanup_blocker"] = result.cleanup_blocker
        evidence["failed_gates"] = list(result.failed_gates)
        evidence["phase_2b_qualified"] = result.passed
        evidence["check_status"] = "PASS" if result.passed else "FAIL"
        if not result.passed:
            evidence["qualification_blocker"] = (
                "Fill, fee, or balance reconciliation failed one or more frozen gates."
            )
        persist_evidence(evidence, args.output)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0 if result.passed else 1
    except Exception as exc:
        evidence["check_status"] = "FAIL"
        evidence["phase_2b_qualified"] = False
        evidence["failed_stage"] = "fill_fee_campaign"
        evidence["qualification_blocker"] = str(exc)[:500]
        evidence["error_type"] = type(exc).__name__
        persist_evidence(evidence, args.output)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
