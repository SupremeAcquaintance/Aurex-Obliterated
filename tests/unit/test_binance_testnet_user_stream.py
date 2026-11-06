from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aurex.broker_engine.binance_spot_testnet import (
    BinanceAccountSnapshot,
    BinanceAssetBalance,
    BinanceOrderSnapshot,
    BinanceSpotTestnetError,
    BinanceTestnetCredentials,
)
from aurex.broker_engine.binance_testnet_user_stream import (
    TESTNET_WEBSOCKET_API_URL,
    BinanceEventDeduplicator,
    BinanceUserDataStreamClient,
    BinanceUserStreamEvidenceAudit,
    account_position_matches_snapshot,
    audit_user_stream_contract,
    audit_user_stream_evidence_audit,
    build_user_stream_contract,
    build_user_stream_evidence_audit,
    parse_user_data_event,
    reconcile_execution_report,
    user_stream_evidence_verified,
)


class FakeConnection:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self.messages = [json.dumps(message) for message in messages]
        self.sent: list[str] = []
        self.closed = False

    def send(self, message: str) -> None:
        self.sent.append(message)

    def recv(self, timeout: float | None = None) -> str:
        del timeout
        if not self.messages:
            raise TimeoutError
        return self.messages.pop(0)

    def close(self, code: int = 1000, reason: str = "") -> None:
        del code, reason
        self.closed = True


def credentials() -> BinanceTestnetCredentials:
    return BinanceTestnetCredentials(
        api_key="testnet-api-key-value",
        secret_key="testnet-secret-key-value",
    )


def execution_event(
    *,
    subscription_id: int = 7,
    status: str = "NEW",
    execution_type: str = "NEW",
) -> dict[str, object]:
    return {
        "subscriptionId": subscription_id,
        "event": {
            "e": "executionReport",
            "E": 1_000,
            "T": 999,
            "s": "BTCUSDT",
            "c": "aurex-stream-two-1234567890ab",
            "C": "",
            "S": "BUY",
            "o": "LIMIT",
            "x": execution_type,
            "X": status,
            "p": "50000.00",
            "q": "0.00010",
            "z": "0",
            "Z": "0",
            "l": "0",
            "L": "0",
            "n": "0",
            "N": None,
            "i": 42,
            "t": -1,
            "I": 88,
        },
    }


def account_event(*, subscription_id: int = 7) -> dict[str, object]:
    return {
        "subscriptionId": subscription_id,
        "event": {
            "e": "outboundAccountPosition",
            "E": 1_001,
            "u": 1_000,
            "B": [
                {"a": "USDT", "f": "94.99900000", "l": "5.00100000"},
            ],
        },
    }


def order() -> BinanceOrderSnapshot:
    return BinanceOrderSnapshot(
        symbol="BTCUSDT",
        order_id=42,
        client_order_id="aurex-stream-two-1234567890ab",
        status="NEW",
        side="BUY",
        order_type="LIMIT",
        price=Decimal("50000.00"),
        original_quantity=Decimal("0.00010"),
        executed_quantity=Decimal("0"),
        cumulative_quote_quantity=Decimal("0"),
        original_quote_order_quantity=Decimal("0"),
        transact_time_ms=999,
        original_client_order_id=None,
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
                free=Decimal("94.99900000"),
                locked=Decimal("5.00100000"),
            ),
        ),
    )


def test_user_stream_contract_is_reproducible() -> None:
    contract = build_user_stream_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )

    assert audit_user_stream_contract(contract) is True
    assert contract.websocket_url == TESTNET_WEBSOCKET_API_URL
    assert contract.maximum_orders == 2
    assert contract.production_authority is False
    assert contract.sandbox_qualified is False
    assert audit_user_stream_contract(
        contract.model_copy(update={"maximum_orders": 3})
    ) is False


def test_signature_subscription_never_persists_credentials() -> None:
    connection = FakeConnection(
        [
            {
                "id": "aurex-subscribe-000001",
                "status": 200,
                "result": {"subscriptionId": 7},
            },
            execution_event(),
            {
                "id": "aurex-unsubscribe-000002",
                "status": 200,
                "result": {},
            },
        ]
    )
    client = BinanceUserDataStreamClient(
        credentials=credentials(),
        connector=lambda url, timeout: connection,
        clock_ms=lambda: 1_700_000_000_000,
    )

    client.connect()
    assert client.subscribe() == 7
    event = client.next_event()
    client.unsubscribe()
    client.disconnect()

    sent = [json.loads(message) for message in connection.sent]
    subscribe = sent[0]
    assert subscribe["method"] == "userDataStream.subscribe.signature"
    assert subscribe["params"]["timestamp"] == 1_700_000_000_000
    canonical = (
        "apiKey=testnet-api-key-value&recvWindow=5000&timestamp=1700000000000"
    )
    expected_signature = hmac.new(
        b"testnet-secret-key-value",
        canonical.encode(),
        hashlib.sha256,
    ).hexdigest()
    assert subscribe["params"]["signature"] == expected_signature
    assert "testnet-secret-key-value" not in json.dumps(sent)
    assert event.execution_report is not None
    assert connection.closed is True


def test_event_parser_deduplicates_and_reconciles_with_rest() -> None:
    first = parse_user_data_event(execution_event())
    duplicate = parse_user_data_event(execution_event())
    deduplicator = BinanceEventDeduplicator()

    assert deduplicator.accept(first) is True
    assert deduplicator.accept(duplicate) is False
    assert deduplicator.unique_count == 1
    assert deduplicator.duplicate_count == 1
    assert first.execution_report is not None
    reconciliation = reconcile_execution_report(
        first.execution_report,
        order(),
        subscription_id=7,
    )
    assert reconciliation.passed is True


def test_account_event_matches_exact_rest_balances() -> None:
    event = parse_user_data_event(account_event())

    assert event.account_position is not None
    assert account_position_matches_snapshot(event.account_position, account()) is True
    changed = account()
    changed = BinanceAccountSnapshot(
        **{
            **vars(changed),
            "balances": (
                changed.balance("BTC"),
                BinanceAssetBalance(
                    asset="USDT",
                    free=Decimal("100"),
                    locked=Decimal("0"),
                ),
            ),
        }
    )
    assert account_position_matches_snapshot(event.account_position, changed) is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"subscriptionId": 0, "event": {}},
        {"subscriptionId": -1, "event": {"e": "balanceUpdate", "E": 1}},
        {
            "subscriptionId": 0,
            "event": {
                **execution_event()["event"],
                "s": "ETHUSDT",
            },
        },
    ],
)
def test_malformed_or_out_of_scope_events_are_rejected(
    payload: Mapping[str, object],
) -> None:
    with pytest.raises(BinanceSpotTestnetError):
        parse_user_data_event(payload)


def test_stream_rejects_wrong_response_identity() -> None:
    connection = FakeConnection(
        [{"id": "not-ours", "status": 200, "result": {"subscriptionId": 7}}]
    )
    client = BinanceUserDataStreamClient(
        credentials=credentials(),
        connector=lambda url, timeout: connection,
    )
    client.connect()

    with pytest.raises(BinanceSpotTestnetError, match="unexpected response ID"):
        client.subscribe()


def test_independent_evidence_reader_rebuilds_phase_2c_gates(tmp_path: Path) -> None:
    contract = build_user_stream_contract(
        frozen_at=datetime(2026, 7, 31, tzinfo=UTC)
    )
    first_id = "aurex-stream-one-1234567890ab"
    second_id = "aurex-stream-two-1234567890ab"

    def order_item(order_id: int, client_order_id: str, status: str) -> dict:
        return {
            "symbol": "BTCUSDT",
            "external_order_id": order_id,
            "client_order_id": client_order_id,
            "status": status,
            "side": "BUY",
            "type": "LIMIT",
            "price": "89999.99",
            "original_quantity": "0.00006",
            "executed_quantity": "0",
            "cumulative_quote_quantity": "0",
        }

    def report(
        subscription_id: int,
        order_id: int,
        client_order_id: str,
        status: str,
    ) -> dict:
        return {
            "subscription_id": subscription_id,
            "event_type": "executionReport",
            "execution_report": {
                "symbol": "BTCUSDT",
                "external_order_id": order_id,
                "client_order_id": client_order_id,
                "original_client_order_id": None,
                "side": "BUY",
                "type": "LIMIT",
                "status": status,
                "original_quantity": "0.00006",
                "executed_quantity": "0",
                "cumulative_quote_quantity": "0",
            },
        }

    balance = {
        "BTC": {"free": "1", "locked": "0", "total": "1"},
        "USDT": {"free": "100", "locked": "0", "total": "100"},
    }
    payload = {
        "schema_version": 1,
        "campaign_id": contract.contract_id,
        "contract_sha256": contract.contract_sha256,
        "environment": contract.environment,
        "websocket_url": contract.websocket_url,
        "rest_url": contract.rest_url,
        "symbol": contract.symbol,
        "product": contract.product,
        "maximum_order_notional": contract.maximum_order_notional,
        "maximum_orders": contract.maximum_orders,
        "subscription_method": contract.subscription_method,
        "client_order_ids": {"first": first_id, "second": second_id},
        "subscription_ids": {"first": 3, "second": 4},
        "credentials_stored": False,
        "production_authority": False,
        "live_authority": False,
        "real_capital": False,
        "sandbox_qualified": False,
        "phase_2c_qualified": True,
        "check_status": "PASS",
        "first_order": {
            "placed": order_item(1, first_id, "NEW"),
            "final": order_item(1, first_id, "CANCELED"),
            "trades": [],
        },
        "second_order": {
            "placed": order_item(2, second_id, "NEW"),
            "final": order_item(2, second_id, "CANCELED"),
            "trades": [],
        },
        "events": [
            report(3, 1, first_id, "NEW"),
            report(4, 2, second_id, "NEW"),
            report(4, 2, second_id, "CANCELED"),
            {
                "subscription_id": 4,
                "event_type": "outboundAccountPosition",
                "account_position": {
                    "balances": {"USDT": {"free": "100", "locked": "0"}}
                },
            },
        ],
        "event_count": 4,
        "initial_account": {"balances": balance},
        "final_account": {"balances": balance},
        "forced_disconnect_verified": True,
        "rest_gap_recovery_verified": True,
        "account_position_match_found": True,
        "graceful_unsubscribe_verified": True,
        "balance_reconciliation_verified": True,
        "duplicate_suppression": {
            "enabled": True,
            "duplicate_events_suppressed": 0,
        },
        "failed_gates": [],
    }
    path = tmp_path / "stream.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert user_stream_evidence_verified(path, contract) is True
    preserved_path = tmp_path / "preserved.json"
    preserved_path.write_bytes(path.read_bytes())
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")
    audit = build_user_stream_evidence_audit(
        source_path=path,
        preserved_source_path=preserved_path,
        contract_path=contract_path,
        audited_at=datetime(2026, 7, 31, 12, tzinfo=UTC),
    )
    assert audit_user_stream_evidence_audit(audit) is True
    reparsed = BinanceUserStreamEvidenceAudit.model_validate_json(
        audit.model_dump_json()
    )
    assert audit_user_stream_evidence_audit(reparsed) is True
    assert audit.decision == "PHASE_2C_USER_STREAM_RECONCILED"
    assert audit.phase_2c_qualified is True
    assert audit.whole_sandbox_qualified is False
    assert audit.live_authority is False

    payload["final_account"]["balances"]["USDT"]["free"] = "99.99"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert user_stream_evidence_verified(path, contract) is False
    assert audit_user_stream_evidence_audit(audit) is False
