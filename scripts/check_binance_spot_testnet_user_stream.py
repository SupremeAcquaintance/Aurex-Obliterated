from __future__ import annotations

import argparse
import json
import sys
import time
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
    account_evidence,
    order_evidence,
    trades_evidence,
)
from aurex.broker_engine.binance_testnet_user_stream import (  # noqa: E402
    DEFAULT_USER_STREAM_CONTRACT_PATH,
    MAXIMUM_STREAM_ORDER_NOTIONAL,
    USER_STREAM_ACKNOWLEDGEMENT,
    BinanceUserDataEvent,
    BinanceUserDataStreamClient,
    BinanceUserStreamContract,
    audit_user_stream_contract,
)
from aurex.broker_engine.binance_testnet_user_stream_campaign import (  # noqa: E402
    run_user_stream_campaign,
)


def persist_evidence(evidence: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    part_path = output.with_suffix(f"{output.suffix}.part")
    part_path.write_text(f"{rendered}\n", encoding="utf-8")
    part_path.replace(output)


def checkpoint_evidence(value: object) -> object:
    if isinstance(value, BinanceAccountSnapshot):
        return account_evidence(value, assets=("BTC", "USDT"))
    if isinstance(value, BinanceOrderSnapshot):
        return order_evidence(value)
    if isinstance(value, tuple) and all(
        isinstance(item, BinanceTradeSnapshot) for item in value
    ):
        return trades_evidence(value)
    if isinstance(value, BinanceUserDataEvent):
        return value.evidence()
    if isinstance(value, dict):
        return value
    raise TypeError(f"Unsupported user-stream checkpoint: {type(value).__name__}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one bounded Binance Spot Testnet user-data reconnect and REST "
            "gap-recovery campaign."
        )
    )
    parser.add_argument("--acknowledgement", required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_USER_STREAM_CONTRACT_PATH,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def campaign_client_order_ids(
    contract: BinanceUserStreamContract,
    *,
    checked_at: datetime,
    output: Path,
) -> dict[str, str]:
    run_key = (
        f"{contract.contract_sha256}|{checked_at.isoformat()}|{output.as_posix()}"
    )
    identities = {
        "first": deterministic_client_order_id("stream-one", run_key),
        "first_cancel": deterministic_client_order_id(
            "gap-cancel",
            f"{run_key}|first-cancel",
        ),
        "second": deterministic_client_order_id("stream-two", run_key),
        "second_cancel": deterministic_client_order_id(
            "event-x",
            f"{run_key}|second-cancel",
        ),
    }
    if len(set(identities.values())) != len(identities):
        raise BinanceSpotTestnetError(
            "User-stream campaign client-order identities are not unique"
        )
    return identities


def main() -> int:
    args = parse_args()
    if args.acknowledgement != USER_STREAM_ACKNOWLEDGEMENT:
        raise BinanceSpotTestnetError(
            "User-stream campaign requires the exact frozen acknowledgement phrase"
        )
    if args.output.exists():
        raise BinanceSpotTestnetError(
            "User-stream evidence already exists; refusing to overwrite or resubmit"
        )
    contract = BinanceUserStreamContract.model_validate_json(args.contract.read_bytes())
    if not audit_user_stream_contract(contract):
        raise BinanceSpotTestnetError("Frozen user-stream contract is not reproducible")
    if args.acknowledgement != contract.acknowledgement_phrase:
        raise BinanceSpotTestnetError("Acknowledgement does not match the frozen contract")

    checked_at = datetime.now(UTC)
    client_order_ids = campaign_client_order_ids(
        contract,
        checked_at=checked_at,
        output=args.output,
    )
    evidence: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": contract.contract_id,
        "contract_sha256": contract.contract_sha256,
        "checked_at": checked_at.isoformat(),
        "environment": contract.environment,
        "websocket_url": contract.websocket_url,
        "rest_url": contract.rest_url,
        "symbol": contract.symbol,
        "product": contract.product,
        "maximum_order_notional": contract.maximum_order_notional,
        "maximum_orders": contract.maximum_orders,
        "subscription_method": contract.subscription_method,
        "client_order_ids": client_order_ids,
        "credentials_stored": False,
        "production_authority": False,
        "live_authority": False,
        "real_capital": False,
        "sandbox_qualified": False,
        "phase_2c_qualified": False,
        "check_status": "IN_PROGRESS",
        "checkpoints": {},
    }
    persist_evidence(evidence, args.output)

    rest: BinanceSpotTestnetClient | None = None
    try:
        credentials = BinanceTestnetCredentials.from_environment()
        rest = BinanceSpotTestnetClient(
            credentials=credentials,
            maximum_virtual_notional=MAXIMUM_STREAM_ORDER_NOTIONAL,
            virtual_order_entry_enabled=True,
        )
        rest.ping()
        evidence["public_connectivity"] = "PASS"
        server_offset_ms = rest.synchronize_time()
        evidence["server_time_offset_ms"] = server_offset_ms
        persist_evidence(evidence, args.output)

        checkpoints = evidence["checkpoints"]
        if not isinstance(checkpoints, dict):
            raise TypeError("User-stream checkpoint ledger is invalid")
        repeated_checkpoint_counts: dict[str, int] = {}

        def record_checkpoint(stage: str, value: object) -> None:
            count = repeated_checkpoint_counts.get(stage, 0) + 1
            repeated_checkpoint_counts[stage] = count
            key = stage if count == 1 else f"{stage}_{count}"
            checkpoints[key] = checkpoint_evidence(value)
            persist_evidence(evidence, args.output)

        def stream_factory() -> BinanceUserDataStreamClient:
            return BinanceUserDataStreamClient(
                credentials=credentials,
                server_offset_ms=server_offset_ms,
                timeout_seconds=contract.event_timeout_seconds,
            )

        result = run_user_stream_campaign(
            rest,
            stream_factory=stream_factory,
            contract=contract,
            first_client_order_id=client_order_ids["first"],
            first_cancel_client_order_id=client_order_ids["first_cancel"],
            second_client_order_id=client_order_ids["second"],
            second_cancel_client_order_id=client_order_ids["second_cancel"],
            on_checkpoint=record_checkpoint,
            monotonic=time.monotonic,
        )
        evidence["subscription_ids"] = {
            "first": result.first_subscription_id,
            "second": result.second_subscription_id,
        }
        evidence["event_count"] = len(result.events)
        evidence["events"] = [event.evidence() for event in result.events]
        evidence["duplicate_suppression"] = {
            "enabled": True,
            "duplicate_events_suppressed": result.duplicate_event_count,
        }
        evidence["first_order"] = {
            "placed": order_evidence(result.first_order.placed),
            "cancelled": order_evidence(result.first_order.cancelled),
            "final": order_evidence(result.first_order.final),
            "trades": trades_evidence(result.first_order.trades),
            "new_event_reconciliation": {
                **vars(result.first_new_reconciliation),
                "passed": result.first_new_reconciliation.passed,
            },
        }
        evidence["second_order"] = {
            "placed": order_evidence(result.second_order.placed),
            "cancelled": order_evidence(result.second_order.cancelled),
            "final": order_evidence(result.second_order.final),
            "trades": trades_evidence(result.second_order.trades),
            "new_event_reconciliation": {
                **vars(result.second_new_reconciliation),
                "passed": result.second_new_reconciliation.passed,
            },
            "cancel_event_reconciliation": {
                **vars(result.second_cancel_reconciliation),
                "passed": result.second_cancel_reconciliation.passed,
            },
        }
        evidence["initial_account"] = account_evidence(
            result.initial_account,
            assets=("BTC", "USDT"),
        )
        evidence["recovery_account"] = account_evidence(
            result.recovery_account,
            assets=("BTC", "USDT"),
        )
        evidence["final_account"] = account_evidence(
            result.final_account,
            assets=("BTC", "USDT"),
        )
        evidence["forced_disconnect_verified"] = result.forced_disconnect_verified
        evidence["rest_gap_recovery_verified"] = result.rest_gap_recovery_verified
        evidence["account_position_match_found"] = result.account_position_match_found
        evidence["graceful_unsubscribe_verified"] = (
            result.graceful_unsubscribe_verified
        )
        evidence["balance_reconciliation_verified"] = (
            result.balance_reconciliation_verified
        )
        evidence["failed_gates"] = list(result.failed_gates)
        evidence["phase_2c_qualified"] = result.passed
        evidence["check_status"] = "PASS" if result.passed else "FAIL"
        if not result.passed:
            evidence["qualification_blocker"] = (
                "User-data stream or REST recovery failed one or more frozen gates."
            )
        persist_evidence(evidence, args.output)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0 if result.passed else 1
    except Exception as exc:
        evidence["check_status"] = "FAIL"
        evidence["phase_2c_qualified"] = False
        evidence["failed_stage"] = "user_stream_campaign"
        evidence["qualification_blocker"] = str(exc)[:500]
        evidence["error_type"] = type(exc).__name__
        evidence["cleanup"] = _cleanup_known_orders(rest, client_order_ids)
        persist_evidence(evidence, args.output)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 1


def _cleanup_known_orders(
    client: BinanceSpotTestnetClient | None,
    client_order_ids: dict[str, str],
) -> dict[str, object]:
    if client is None:
        return {"attempted": False, "uncertain": True, "orders": []}
    outcomes: list[dict[str, object]] = []
    uncertain = False
    for purpose in ("first", "second"):
        client_order_id = client_order_ids[purpose]
        try:
            order = client.query_order(client_order_id=client_order_id)
        except BinanceSpotTestnetError as exc:
            outcomes.append(
                {
                    "purpose": purpose,
                    "client_order_id": client_order_id,
                    "query": "NOT_RESOLVED",
                    "error_code": exc.error_code,
                }
            )
            if exc.error_code != -2013:
                uncertain = True
            continue
        if order.status in {"NEW", "PARTIALLY_FILLED"}:
            cleanup_id = deterministic_client_order_id(
                f"{purpose}-cleanup",
                client_order_id,
            )
            try:
                order = client.cancel_order(
                    client_order_id=client_order_id,
                    new_client_order_id=cleanup_id,
                )
            except BinanceSpotTestnetError:
                uncertain = True
        if order.status not in {"CANCELED", "FILLED", "REJECTED", "EXPIRED"}:
            uncertain = True
        outcomes.append(
            {
                "purpose": purpose,
                "client_order_id": client_order_id,
                "external_order_id": order.order_id,
                "status": order.status,
                "executed_quantity": str(order.executed_quantity),
            }
        )
    return {"attempted": True, "uncertain": uncertain, "orders": outcomes}


if __name__ == "__main__":
    raise SystemExit(main())
