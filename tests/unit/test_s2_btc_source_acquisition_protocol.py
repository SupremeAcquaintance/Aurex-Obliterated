from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_btc_source_acquisition import (
    S2_BTC_SOURCE_PROTOCOL_NEXT,
    S2BtcSourceAcquisitionProtocol,
    S2BtcSourceAcquisitionProtocolAudit,
)
from scripts.audit_s2_btc_source_acquisition_protocol import build_audit
from scripts.freeze_s2_btc_source_acquisition_protocol import build_protocol

FROZEN_AT = datetime(2026, 8, 30, 19, 0, tzinfo=UTC)


def test_s2_btc_source_protocol_reconstructs_without_market_access() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert S2BtcSourceAcquisitionProtocol.model_validate_json(
        protocol.model_dump_json()
    ) == protocol
    assert len(protocol.targets) == 273
    assert protocol.targets[0].activation_date.isoformat() == "2017-10-16"
    assert protocol.targets[-1].activation_date.isoformat() == "2023-01-02"
    assert tuple(target.measurement_sequence for target in protocol.targets) == tuple(
        range(8, 281)
    )
    assert all(target.activation_date.weekday() == 0 for target in protocol.targets)
    assert protocol.maximum_network_requests == 1_638
    assert protocol.maximum_total_payload_bytes == 54_739_776
    assert protocol.btc_market_values_read_during_protocol_freeze == 0
    assert protocol.return_metrics_calculated == ()
    assert protocol.next_authorization == S2_BTC_SOURCE_PROTOCOL_NEXT


@pytest.mark.parametrize(
    "field",
    (
        "authorizes_network_acquisition_now",
        "authorizes_return_testing",
        "authorizes_historical_screen_access",
        "authorizes_validation_access",
        "authorizes_holdout_access",
        "authorizes_candidate_outcome",
        "authorizes_pine",
        "authorizes_paper",
        "authorizes_testnet_strategy_orders",
        "authorizes_production",
        "authorizes_live",
    ),
)
def test_s2_btc_source_protocol_rejects_authority_escalation(field: str) -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload[field] = True

    with pytest.raises(ValidationError):
        S2BtcSourceAcquisitionProtocol.model_validate(payload)


def test_s2_btc_source_protocol_rejects_target_timestamp_substitution() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["targets"][0]["activation_open_time_ms"] += 3_600_000

    with pytest.raises(ValidationError, match="target timestamp changed"):
        S2BtcSourceAcquisitionProtocol.model_validate(payload)


def test_s2_btc_source_protocol_rejects_source_host_substitution() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["targets"][0]["archive_url"] = payload["targets"][0][
        "archive_url"
    ].replace("data.binance.vision", "example.com")

    with pytest.raises(ValidationError, match="archive URL changed"):
        S2BtcSourceAcquisitionProtocol.model_validate(payload)


def test_s2_btc_source_protocol_rejects_schedule_change() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["targets"] = list(reversed(payload["targets"]))

    with pytest.raises(ValidationError, match="target sequence changed"):
        S2BtcSourceAcquisitionProtocol.model_validate(payload)


def test_s2_btc_source_protocol_audit_reconstructs_frozen_file(tmp_path) -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8")

    audit = build_audit(protocol_path=protocol_path, audited_at=FROZEN_AT)

    assert S2BtcSourceAcquisitionProtocolAudit.model_validate_json(
        audit.model_dump_json()
    ) == audit
    assert audit.target_count == 273
    assert audit.network_requests_observed == 0
    assert audit.btc_market_values_read == 0
    assert audit.returns_calculated == 0
    assert audit.next_authorization == S2_BTC_SOURCE_PROTOCOL_NEXT
