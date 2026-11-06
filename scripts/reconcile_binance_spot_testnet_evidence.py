from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from aurex.broker_engine.binance_spot_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_SYMBOL,
)
from aurex.broker_engine.binance_testnet_evidence import (
    virtual_cancel_reconciliation_from_evidence,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile a preserved Binance Spot Testnet virtual-cancel artifact "
            "without sending any network request."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.input.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not _has_safe_boundary(payload):
        raise ValueError("Input evidence violates the Binance Spot Testnet boundary")
    reconciliation = virtual_cancel_reconciliation_from_evidence(payload)
    if reconciliation is None:
        raise ValueError("Input evidence lacks a complete virtual-cancel checkpoint set")

    source_virtual_order = payload.get("virtual_order")
    virtual_order = source_virtual_order if isinstance(source_virtual_order, dict) else {}
    artifact = {
        "schema_version": 1,
        "artifact_type": "BINANCE_SPOT_TESTNET_RECONCILIATION_ADDENDUM",
        "created_at": datetime.now(UTC).isoformat(),
        "environment": "BINANCE_SPOT_TESTNET",
        "base_url": TESTNET_REST_BASE_URL,
        "symbol": TESTNET_SYMBOL,
        "source_evidence": {
            "path": args.input.as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "checked_at": payload.get("checked_at"),
            "declared_order_reconciliation": payload.get("order_reconciliation"),
            "external_order_id": virtual_order.get("external_order_id"),
        },
        "reconciliation_contract": {
            "version": 2,
            "final_query_selector": "external_order_id",
            "placement_identity_stages": ["placed", "queried", "final"],
            "cancellation_identity_stage": "cancelled",
            "requires_exact_quantity": True,
            "requires_zero_fill": True,
            "requires_final_cancelled": True,
        },
        "result": {
            **asdict(reconciliation),
            "passed": reconciliation.passed,
        },
        "decision": (
            "VIRTUAL_CANCEL_RECONCILED"
            if reconciliation.passed
            else "VIRTUAL_CANCEL_RECONCILIATION_FAILED"
        ),
        "credentials_stored": False,
        "sandbox_qualified": False,
        "production_authority": False,
        "live_authority": False,
    }
    rendered = json.dumps(artifact, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    part_path = args.output.with_suffix(f"{args.output.suffix}.part")
    part_path.write_text(f"{rendered}\n", encoding="utf-8")
    part_path.replace(args.output)
    print(rendered)
    return 0 if reconciliation.passed else 1


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


if __name__ == "__main__":
    raise SystemExit(main())
