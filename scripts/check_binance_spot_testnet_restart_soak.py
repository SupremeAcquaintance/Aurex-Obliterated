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
    BinanceSpotTestnetClient,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
    deterministic_client_order_id,
)
from aurex.broker_engine.binance_testnet_restart_soak import (  # noqa: E402
    DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
    DEFAULT_RESTART_SOAK_STATE_PATH,
    MAXIMUM_RESTART_ORDER_NOTIONAL,
    RESTART_SOAK_ACKNOWLEDGEMENT,
    BinanceRestartSoakContract,
    BinanceRestartSoakGuard,
    RestartSoakStateStore,
    audit_restart_soak_contract,
    build_restart_soak_evidence,
    restart_order_evidence,
    run_restart_soak,
)
from aurex.broker_engine.binance_testnet_user_stream import (  # noqa: E402
    BinanceUserDataStreamClient,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one stage of the Binance Spot Testnet Phase 2D cross-process "
            "restart and bounded soak campaign."
        )
    )
    parser.add_argument("--stage", choices=("prepare", "recover", "soak"), required=True)
    parser.add_argument("--acknowledgement", required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_RESTART_SOAK_CONTRACT_PATH,
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_RESTART_SOAK_STATE_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESTART_SOAK_EVIDENCE_PATH,
    )
    return parser.parse_args()


def persist_json(payload: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    part_path = path.with_suffix(f"{path.suffix}.part")
    part_path.write_text(f"{rendered}\n", encoding="utf-8")
    part_path.replace(path)


def main() -> int:
    args = parse_args()
    if args.acknowledgement != RESTART_SOAK_ACKNOWLEDGEMENT:
        raise BinanceSpotTestnetError(
            "Restart-soak campaign requires the exact frozen acknowledgement phrase"
        )
    contract = BinanceRestartSoakContract.model_validate_json(
        args.contract.read_bytes()
    )
    if not audit_restart_soak_contract(contract):
        raise BinanceSpotTestnetError(
            "Frozen restart-soak contract is not reproducible"
        )
    if args.acknowledgement != contract.acknowledgement_phrase:
        raise BinanceSpotTestnetError(
            "Acknowledgement does not match the frozen restart-soak contract"
        )
    if args.output.exists():
        raise BinanceSpotTestnetError(
            "Restart-soak evidence already exists; refusing to overwrite it"
        )

    credentials = BinanceTestnetCredentials.from_environment()
    rest = BinanceSpotTestnetClient(
        credentials=credentials,
        maximum_virtual_notional=MAXIMUM_RESTART_ORDER_NOTIONAL,
        virtual_order_entry_enabled=True,
    )
    rest.ping()
    server_offset_ms = rest.synchronize_time()
    store = RestartSoakStateStore(args.state)
    guard = BinanceRestartSoakGuard(
        rest=rest,
        store=store,
        contract=contract,
    )

    try:
        if args.stage == "prepare":
            if args.state.exists():
                raise BinanceSpotTestnetError(
                    "Restart-soak state already exists; inspect it before any new campaign"
                )
            checked_at = datetime.now(UTC)
            run_key = (
                f"{contract.contract_sha256}|{checked_at.isoformat()}|"
                f"{args.state.as_posix()}"
            )
            run_id = deterministic_client_order_id("run", run_key)
            state = store.create(
                run_id=run_id,
                contract_sha256=contract.contract_sha256,
                client_order_id=deterministic_client_order_id(
                    "restart",
                    run_key,
                ),
                cancel_client_order_id=deterministic_client_order_id(
                    "restart-x",
                    run_key,
                ),
                blocked_client_order_id=deterministic_client_order_id(
                    "kill-proof",
                    run_key,
                ),
            )
            state = store.record_process(state)
            state = guard.prepare(state)
            _print_stage(state, server_offset_ms=server_offset_ms)
            return 0

        state = store.load()
        if state.contract_sha256 != contract.contract_sha256:
            raise BinanceSpotTestnetError(
                "Existing restart-soak state belongs to a different contract"
            )
        state = store.record_process(state)
        if args.stage == "recover":
            state = guard.recover(state)
            _print_stage(state, server_offset_ms=server_offset_ms)
            return 0

        state = run_restart_soak(
            rest=rest,
            stream_factory=lambda: BinanceUserDataStreamClient(
                credentials=credentials,
                server_offset_ms=server_offset_ms,
                timeout_seconds=10,
            ),
            store=store,
            contract=contract,
            state=state,
        )
        if state.stage != "PASSED":
            _print_stage(state, server_offset_ms=server_offset_ms)
            return 1
        evidence = build_restart_soak_evidence(state, contract)
        persist_json(evidence, args.output)
        print(json.dumps(evidence, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        _cleanup_tracked_order(rest, store)
        _fail_existing_state(store, str(exc))
        raise


def _cleanup_tracked_order(
    rest: BinanceSpotTestnetClient,
    store: RestartSoakStateStore,
) -> None:
    if not store.path.exists():
        return
    try:
        state = store.load()
        order = rest.query_order(client_order_id=state.client_order_id)
    except BinanceSpotTestnetError:
        return
    if order.status not in {"NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"}:
        return
    try:
        cancelled = rest.cancel_order(
            client_order_id=state.client_order_id,
            new_client_order_id=state.cancel_client_order_id,
        )
        final = rest.query_order(order_id=order.order_id)
    except BinanceSpotTestnetError:
        return
    store.save(
        state.model_copy(
            update={
                "kill_stop_enabled": True,
                "kill_stop_reason": state.kill_stop_reason or "failure cleanup",
                "kill_stop_enabled_at": state.kill_stop_enabled_at or datetime.now(UTC),
                "cancelled_order": restart_order_evidence(cancelled),
                "final_order": restart_order_evidence(final),
            }
        )
    )


def _fail_existing_state(store: RestartSoakStateStore, message: str) -> None:
    if not store.path.exists():
        return
    try:
        state = store.load()
    except BinanceSpotTestnetError:
        return
    if state.stage != "FAILED":
        store.fail(
            state,
            message,
            reset_detected="reset" in message.lower(),
        )


def _print_stage(state, *, server_offset_ms: int) -> None:
    print(
        json.dumps(
            {
                "run_id": state.run_id,
                "stage": state.stage,
                "process_ids": state.process_ids,
                "placement_request_count": state.placement_request_count,
                "idempotent_resolution_count": state.idempotent_resolution_count,
                "blocked_entry_count": state.blocked_entry_count,
                "kill_stop_enabled": state.kill_stop_enabled,
                "server_time_offset_ms": server_offset_ms,
                "production_authority": False,
                "live_authority": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
