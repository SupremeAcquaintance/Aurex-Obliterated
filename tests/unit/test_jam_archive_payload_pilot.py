from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_archive_payload_pilot import (
    JAM_PAYLOAD_PILOT_AGGTRADES_HEADER,
    JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
    JAM_PAYLOAD_PILOT_KLINES_HEADER,
    JAM_PAYLOAD_PILOT_NEXT_AUTHORIZATION,
    JAM_PAYLOAD_PILOT_PASS_DECISION,
    JamPayloadArchiveEvidence,
    JamPayloadHeadObservation,
    JamPayloadPilotProtocol,
    JamPayloadPilotResult,
    JamPayloadReconciliationEvidence,
    audit_jam_payload_pilot_protocol,
    audit_jam_payload_pilot_result,
    authoritative_payload_targets,
)
from scripts.freeze_jam_archive_payload_pilot_protocol import (
    DEFAULT_CENSUS_AUDIT,
    DEFAULT_CENSUS_CONTRACT,
    DEFAULT_CENSUS_RESULT,
    authoritative_protocol,
    load_inputs,
)
from scripts.run_jam_archive_payload_pilot import (
    KlineMinute,
    MinuteAggregate,
    RedirectRejectedError,
    RejectRedirectHandler,
    _validate_archive_url,
    authoritative_result,
    inspect_aggregate_trades,
    inspect_klines,
    reconcile_archives,
)

OBSERVED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def frozen_protocol() -> JamPayloadPilotProtocol:
    contract, result, audit = load_inputs(
        census_contract_path=DEFAULT_CENSUS_CONTRACT,
        census_result_path=DEFAULT_CENSUS_RESULT,
        census_audit_path=DEFAULT_CENSUS_AUDIT,
    )
    return authoritative_protocol(
        frozen_at=OBSERVED_AT,
        census_contract=contract,
        census_result=result,
        census_audit=audit,
        census_result_path=DEFAULT_CENSUS_RESULT,
    )


def archive_evidence(family: str) -> JamPayloadArchiveEvidence:
    target = next(
        target
        for target in authoritative_payload_targets()
        if target.family == family
    )
    is_kline = family == "klines_1m"
    return JamPayloadArchiveEvidence(
        family=family,
        archive_url=target.archive_url,
        local_path=f"jam_archive_payload_pilot_v1/{family}.zip",
        archive_bytes=1000,
        archive_sha256=target.published_archive_sha256,
        published_archive_sha256=target.published_archive_sha256,
        checksum_verified=True,
        csv_member_name=target.expected_csv_member,
        zip_compressed_bytes=900,
        zip_uncompressed_bytes=2000,
        zip_crc_verified=True,
        column_count=target.expected_column_count,
        header_present=False,
        row_count=JAM_PAYLOAD_PILOT_EXPECTED_MINUTES if is_kline else 100,
        first_timestamp_ms=1_546_300_800_000,
        last_timestamp_ms=1_548_979_140_000,
        unique_primary_key_count=(
            JAM_PAYLOAD_PILOT_EXPECTED_MINUTES if is_kline else 100
        ),
        duplicate_primary_key_count=0,
        out_of_order_count=0,
        gap_count=0,
        unique_minute_count=(
            JAM_PAYLOAD_PILOT_EXPECTED_MINUTES if is_kline else 100
        ),
        expected_minute_count=JAM_PAYLOAD_PILOT_EXPECTED_MINUTES,
        inspected_field_names=list(
            JAM_PAYLOAD_PILOT_KLINES_HEADER
            if is_kline
            else JAM_PAYLOAD_PILOT_AGGTRADES_HEADER
        ),
        payload_get_request_count=1,
        archive_pass=True,
        reason_codes=[],
    )


def passing_reconciliation() -> JamPayloadReconciliationEvidence:
    return JamPayloadReconciliationEvidence(
        aggregate_trade_covered_minute_count=100,
        empty_trade_minute_count=JAM_PAYLOAD_PILOT_EXPECTED_MINUTES - 100,
        aggregate_trade_outside_kline_count=0,
        raw_trade_count_mismatch_count=0,
        ohlc_mismatch_count=0,
        base_volume_mismatch_count=0,
        quote_volume_mismatch_count=0,
        taker_buy_base_volume_mismatch_count=0,
        taker_buy_quote_volume_mismatch_count=0,
        reconciliation_pass=True,
        reason_codes=[],
    )


def head_observations() -> list[JamPayloadHeadObservation]:
    return [
        JamPayloadHeadObservation(
            family=target.family,
            archive_url=target.archive_url,
            final_url=target.archive_url,
            observed_at=OBSERVED_AT,
            http_status=200,
            content_length_bytes=1000,
            accept_ranges="bytes",
            request_attempt_count=1,
            redirect_count=0,
        )
        for target in authoritative_payload_targets()
    ]


def test_protocol_freezes_earliest_month_and_two_exact_archives() -> None:
    protocol = frozen_protocol()

    assert protocol.pilot_month == "2019-01"
    assert protocol.month_selection_rule == (
        "EARLIEST_MONTH_IN_PROVISIONAL_POOL_NO_OUTCOME_SELECTION"
    )
    assert [target.family for target in protocol.targets] == [
        "aggTrades",
        "klines_1m",
    ]
    assert protocol.maximum_total_archive_bytes == 800_000_000
    assert protocol.maximum_requests_total == 12
    assert protocol.redirects_permitted is False
    assert protocol.market_values_permitted_for_capability_validation is True
    assert protocol.feature_calculation_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.live_permitted is False
    assert audit_jam_payload_pilot_protocol(protocol)


def test_protocol_refuses_url_budget_or_authority_tampering() -> None:
    payload = frozen_protocol().model_dump()
    payload["maximum_total_archive_bytes"] = 900_000_000
    payload["return_calculation_permitted"] = True
    payload["targets"][0]["archive_url"] = "https://example.com/archive.zip"

    with pytest.raises(ValidationError):
        JamPayloadPilotProtocol.model_validate(payload)


def test_transport_rejects_redirects_and_non_protocol_urls() -> None:
    handler = RejectRedirectHandler()

    with pytest.raises(RedirectRejectedError, match="rejected HTTP redirect"):
        handler.redirect_request(
            None,
            None,
            302,
            "Found",
            {},
            "https://data.binance.vision/redirected.zip",
        )
    with pytest.raises(ValueError, match="non-protocol archive URL"):
        _validate_archive_url("https://data.binance.vision/unfrozen.zip")


def test_head_observation_rejects_changed_final_url() -> None:
    target = authoritative_payload_targets()[0]

    with pytest.raises(ValidationError, match="HEAD URL changed"):
        JamPayloadHeadObservation(
            family=target.family,
            archive_url=target.archive_url,
            final_url="https://example.com/redirected.zip",
            observed_at=OBSERVED_AT,
            http_status=200,
            content_length_bytes=1000,
            accept_ranges="bytes",
            request_attempt_count=1,
            redirect_count=0,
        )


def test_aggregate_parser_validates_rows_without_creating_features(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = frozen_protocol()
    target = protocol.targets[0]
    archive_path = tmp_path / "aggregate.zip"
    rows = [
        "1,10.0,1.0,100,100,1546300800000,True,True",
        "2,11.0,2.0,101,101,1546300860000,False,True",
    ]
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(target.expected_csv_member, "\n".join(rows) + "\n")
    monkeypatch.setattr(
        "scripts.run_jam_archive_payload_pilot.file_sha256",
        lambda _: target.published_archive_sha256,
    )

    evidence, minutes = inspect_aggregate_trades(
        target=target,
        archive_path=archive_path,
        evidence_root=tmp_path,
        protocol=protocol,
        request_count=1,
    )

    assert evidence.archive_pass is True
    assert evidence.row_count == 2
    assert evidence.gap_count == 0
    assert evidence.inspected_field_names == sorted(
        JAM_PAYLOAD_PILOT_AGGTRADES_HEADER
    )
    assert len(minutes) == 2


def test_kline_parser_records_incomplete_month_as_failed_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = frozen_protocol()
    target = protocol.targets[1]
    archive_path = tmp_path / "klines.zip"
    row = (
        "1546300800000,10,10,10,10,1,1546300859999,10,1,1,10,0\n"
    )
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(target.expected_csv_member, row)
    monkeypatch.setattr(
        "scripts.run_jam_archive_payload_pilot.file_sha256",
        lambda _: target.published_archive_sha256,
    )

    evidence, minutes = inspect_klines(
        target=target,
        archive_path=archive_path,
        evidence_root=tmp_path,
        protocol=protocol,
        request_count=1,
    )

    assert evidence.archive_pass is False
    assert evidence.reason_codes == ["KLINE_MONTH_CONTINUITY_FAILED"]
    assert len(minutes) == 1


def test_cross_family_reconciliation_detects_no_mismatch() -> None:
    protocol = frozen_protocol()
    zero = Decimal(0)
    ten = Decimal(10)
    aggregate = {
        0: MinuteAggregate(
            open_price=ten,
            high_price=ten,
            low_price=ten,
            close_price=ten,
            base_volume=Decimal(1),
            quote_volume=ten,
            raw_trade_count=1,
            taker_buy_base_volume=zero,
            taker_buy_quote_volume=zero,
        )
    }
    kline = {
        minute: KlineMinute(
            open_price=ten,
            high_price=ten,
            low_price=ten,
            close_price=ten,
            base_volume=Decimal(1) if minute == 0 else zero,
            quote_volume=ten if minute == 0 else zero,
            raw_trade_count=1 if minute == 0 else 0,
            taker_buy_base_volume=zero,
            taker_buy_quote_volume=zero,
        )
        for minute in range(JAM_PAYLOAD_PILOT_EXPECTED_MINUTES)
    }

    result = reconcile_archives(
        aggregate_minutes=aggregate,
        kline_minutes=kline,
        protocol=protocol,
    )

    assert result.reconciliation_pass is True
    assert result.reason_codes == []
    assert result.empty_trade_minute_count == (
        JAM_PAYLOAD_PILOT_EXPECTED_MINUTES - 1
    )


def test_cross_family_reconciliation_records_mismatch_as_failure() -> None:
    protocol = frozen_protocol()
    ten = Decimal(10)
    aggregate = {
        0: MinuteAggregate(
            open_price=ten,
            high_price=ten,
            low_price=ten,
            close_price=ten,
            base_volume=Decimal(1),
            quote_volume=ten,
            raw_trade_count=1,
            taker_buy_base_volume=Decimal(0),
            taker_buy_quote_volume=Decimal(0),
        )
    }
    kline = {
        minute: KlineMinute(
            open_price=ten,
            high_price=ten,
            low_price=ten,
            close_price=ten,
            base_volume=Decimal(2) if minute == 0 else Decimal(0),
            quote_volume=ten if minute == 0 else Decimal(0),
            raw_trade_count=1 if minute == 0 else 0,
            taker_buy_base_volume=Decimal(0),
            taker_buy_quote_volume=Decimal(0),
        )
        for minute in range(JAM_PAYLOAD_PILOT_EXPECTED_MINUTES)
    }

    result = reconcile_archives(
        aggregate_minutes=aggregate,
        kline_minutes=kline,
        protocol=protocol,
    )

    assert result.reconciliation_pass is False
    assert result.base_volume_mismatch_count == 1
    assert result.reason_codes == ["BASE_VOLUME_MISMATCH"]


def test_result_passes_only_to_separate_full_acquisition_authorization() -> None:
    protocol = frozen_protocol()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        protocol=protocol,
        head_observations=head_observations(),
        archive_evidence=[
            archive_evidence("aggTrades"),
            archive_evidence("klines_1m"),
        ],
        reconciliation=passing_reconciliation(),
    )

    assert result.decision == JAM_PAYLOAD_PILOT_PASS_DECISION
    assert result.next_required_authorization == (
        JAM_PAYLOAD_PILOT_NEXT_AUTHORIZATION
    )
    assert result.total_head_request_count == 2
    assert result.total_payload_get_request_count == 2
    assert result.feature_fields_created == []
    assert result.parameters_defined == []
    assert result.return_metrics_calculated == []
    assert result.strategy_executions == 0
    assert result.creates_candidate is False
    assert result.creates_testnet_order_authority is False
    assert result.creates_live_eligibility is False
    assert audit_jam_payload_pilot_result(result)


def test_result_refuses_return_or_decision_tampering() -> None:
    protocol = frozen_protocol()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        protocol=protocol,
        head_observations=head_observations(),
        archive_evidence=[
            archive_evidence("aggTrades"),
            archive_evidence("klines_1m"),
        ],
        reconciliation=passing_reconciliation(),
    )
    payload = result.model_dump()
    payload["return_metrics_calculated"] = ["net_return"]
    payload["creates_live_eligibility"] = True

    with pytest.raises(ValidationError):
        JamPayloadPilotResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_jam_archive_payload_pilot_protocol.py",
        "scripts/run_jam_archive_payload_pilot.py",
        "scripts/audit_jam_archive_payload_pilot.py",
    ],
)
def test_payload_pilot_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
