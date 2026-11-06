from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_archive_full_acquisition import (
    JAM_FULL_ACQUISITION_NEXT_AUTHORIZATION,
    JAM_FULL_ACQUISITION_PASS_DECISION,
    JAM_FULL_AGGTRADES_HEADER,
    JAM_FULL_KLINES_HEADER,
    JAM_FULL_MONTHS,
    JamFullAcquisitionProtocol,
    JamFullAcquisitionResult,
    JamFullArchiveEvidence,
    JamFullMonthEvidence,
    JamFullMonthReconciliation,
    audit_jam_full_acquisition_protocol,
    audit_jam_full_acquisition_result,
    month_bounds_ms,
)
from scripts.freeze_jam_archive_full_acquisition_protocol import (
    DEFAULT_CENSUS_RESULT,
    DEFAULT_PILOT_AUDIT,
    DEFAULT_PILOT_PROTOCOL,
    DEFAULT_PILOT_RESULT,
    acquisition_targets,
    authoritative_protocol,
    load_inputs,
)
from scripts.run_jam_archive_full_acquisition import (
    KlineMinute,
    MinuteAggregate,
    RedirectRejectedError,
    RejectRedirectHandler,
    _validate_url,
    _validate_zip_member,
    authoritative_result,
    inspect_klines,
    load_checkpoint,
    reconcile_month,
    write_checkpoint,
)

OBSERVED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def frozen_protocol() -> JamFullAcquisitionProtocol:
    census, pilot_protocol, pilot_result, pilot_audit = load_inputs(
        census_result_path=DEFAULT_CENSUS_RESULT,
        pilot_protocol_path=DEFAULT_PILOT_PROTOCOL,
        pilot_result_path=DEFAULT_PILOT_RESULT,
        pilot_audit_path=DEFAULT_PILOT_AUDIT,
    )
    return authoritative_protocol(
        frozen_at=OBSERVED_AT,
        census=census,
        pilot_protocol=pilot_protocol,
        pilot_result=pilot_result,
        pilot_audit=pilot_audit,
        census_result_path=DEFAULT_CENSUS_RESULT,
    )


def synthetic_archive(
    *,
    protocol: JamFullAcquisitionProtocol,
    month: str,
    family: str,
) -> JamFullArchiveEvidence:
    target = next(
        target
        for target in protocol.targets
        if target.month == month and target.family == family
    )
    expected_minutes = month_bounds_ms(month)[2]
    reused = target.reuse_verified_pilot_file
    return JamFullArchiveEvidence(
        family=family,
        month=month,
        archive_url=target.archive_url,
        local_path=f"raw/{month}/{family}.zip",
        reused_pilot_file=reused,
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
        row_count=expected_minutes if family == "klines_1m" else 100,
        first_timestamp_ms=month_bounds_ms(month)[0],
        last_timestamp_ms=month_bounds_ms(month)[1] - 60_000,
        unique_primary_key_count=(
            expected_minutes if family == "klines_1m" else 100
        ),
        duplicate_primary_key_count=0,
        out_of_order_count=0,
        gap_count=0,
        unique_minute_count=(
            expected_minutes if family == "klines_1m" else 100
        ),
        expected_minute_count=expected_minutes,
        inspected_field_names=list(
            JAM_FULL_KLINES_HEADER
            if family == "klines_1m"
            else JAM_FULL_AGGTRADES_HEADER
        ),
        head_request_count=0 if reused else 1,
        payload_get_request_count=0 if reused else 1,
        archive_pass=True,
        reason_codes=[],
    )


def synthetic_month(
    protocol: JamFullAcquisitionProtocol,
    month: str,
) -> JamFullMonthEvidence:
    expected_minutes = month_bounds_ms(month)[2]
    return JamFullMonthEvidence(
        month=month,
        aggregate_trades=synthetic_archive(
            protocol=protocol,
            month=month,
            family="aggTrades",
        ),
        klines_1m=synthetic_archive(
            protocol=protocol,
            month=month,
            family="klines_1m",
        ),
        reconciliation=JamFullMonthReconciliation(
            month=month,
            expected_minute_count=expected_minutes,
            compared_minute_count=expected_minutes,
            aggregate_trade_covered_minute_count=100,
            empty_trade_minute_count=expected_minutes - 100,
            aggregate_trade_outside_kline_count=0,
            raw_trade_count_mismatch_count=0,
            ohlc_mismatch_count=0,
            base_volume_mismatch_count=0,
            quote_volume_mismatch_count=0,
            taker_buy_base_volume_mismatch_count=0,
            taker_buy_quote_volume_mismatch_count=0,
            reconciliation_pass=True,
            reason_codes=[],
        ),
        month_pass=True,
        reason_codes=[],
    )


def test_protocol_freezes_96_targets_and_reuses_only_pilot_month() -> None:
    protocol = frozen_protocol()

    assert len(protocol.targets) == 96
    assert protocol.targets == sorted(
        protocol.targets,
        key=lambda target: target.key,
    )
    assert sum(target.reuse_verified_pilot_file for target in protocol.targets) == 2
    assert protocol.network_target_count == 94
    assert protocol.maximum_total_archive_bytes == 60_000_000_000
    assert protocol.minimum_post_acquisition_free_disk_bytes == 20_000_000_000
    assert protocol.feature_calculation_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.live_permitted is False
    assert audit_jam_full_acquisition_protocol(protocol)


def test_protocol_targets_match_metadata_census_exactly() -> None:
    census, *_ = load_inputs(
        census_result_path=DEFAULT_CENSUS_RESULT,
        pilot_protocol_path=DEFAULT_PILOT_PROTOCOL,
        pilot_result_path=DEFAULT_PILOT_RESULT,
        pilot_audit_path=DEFAULT_PILOT_AUDIT,
    )
    targets = acquisition_targets(census)

    assert len(targets) == 96
    assert {
        (target.family, target.month, target.published_archive_sha256)
        for target in targets
    } == {
        (record.family, record.month, record.published_archive_sha256)
        for record in census.records
    }


def test_protocol_refuses_budget_or_authority_tampering() -> None:
    payload = frozen_protocol().model_dump()
    payload["maximum_total_archive_bytes"] = 70_000_000_000
    payload["return_calculation_permitted"] = True

    with pytest.raises(ValidationError):
        JamFullAcquisitionProtocol.model_validate(payload)


def test_month_bounds_cover_leap_and_non_leap_february() -> None:
    assert month_bounds_ms("2019-02")[2] == 40_320
    assert month_bounds_ms("2020-02")[2] == 41_760
    assert month_bounds_ms("2022-12")[2] == 44_640


def test_reconciliation_records_missing_official_kline_without_aborting() -> None:
    protocol = frozen_protocol()
    aggregate = MinuteAggregate(
        open_price=1,
        high_price=1,
        low_price=1,
        close_price=1,
        base_volume=1,
        quote_volume=1,
        raw_trade_count=1,
        taker_buy_base_volume=1,
        taker_buy_quote_volume=1,
    )
    kline = KlineMinute(
        open_price=1,
        high_price=1,
        low_price=1,
        close_price=1,
        base_volume=0,
        quote_volume=0,
        raw_trade_count=0,
        taker_buy_base_volume=0,
        taker_buy_quote_volume=0,
    )

    result = reconcile_month(
        month="2019-03",
        aggregates={0: aggregate},
        klines={1: kline},
        protocol=protocol,
    )

    assert result.aggregate_trade_outside_kline_count == 1
    assert result.reconciliation_pass is False
    assert result.reason_codes == ["AGGREGATE_TRADE_OUTSIDE_KLINE"]


def test_kline_row_invariant_is_recorded_without_aborting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = frozen_protocol()
    target = next(
        target
        for target in protocol.targets
        if target.month == "2019-06" and target.family == "klines_1m"
    )
    archive_path = tmp_path / "june.zip"
    row = (
        "1559347200000,7930.85,7930.85,7930.85,7930.85,0,"
        "1559347213524,0,0,0,0,0\n"
    )
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(target.expected_csv_member, row)
    monkeypatch.setattr(
        "scripts.run_jam_archive_full_acquisition.file_sha256",
        lambda path: target.published_archive_sha256,
    )

    evidence, rows = inspect_klines(
        target=target,
        archive_path=archive_path,
        evidence_root=tmp_path,
        protocol=protocol,
        head_count=1,
        get_count=1,
    )

    assert len(rows) == 1
    assert evidence.archive_pass is False
    assert evidence.gap_count == 1
    assert "KLINE_ROW_INVARIANT_FAILED" in evidence.reason_codes


def test_duplicate_nested_zip_member_is_recorded_and_canonical_is_selected(
    tmp_path: Path,
) -> None:
    protocol = frozen_protocol()
    target = next(
        target
        for target in protocol.targets
        if target.month == "2021-12" and target.family == "aggTrades"
    )
    archive_path = tmp_path / "duplicate.zip"
    row = "1,1,1,1,1,1638316800000,false,true\n"
    nested = f"unexpected/path/{target.expected_csv_member}"
    with zipfile.ZipFile(archive_path, "w") as output:
        output.writestr(target.expected_csv_member, row)
        output.writestr(nested, row)

    with zipfile.ZipFile(archive_path) as archive:
        member, reasons, compressed_bytes, uncompressed_bytes = (
            _validate_zip_member(
                archive=archive,
                target=target,
                protocol=protocol,
            )
        )

    assert member.filename == target.expected_csv_member
    assert reasons == [
        "ZIP_MEMBER_MATRIX_FAILED",
        "ZIP_MEMBER_SAFETY_FAILED",
    ]
    assert compressed_bytes > 0
    assert uncompressed_bytes == len(row.encode()) * 2


def test_transport_rejects_redirects_and_reused_pilot_network_target() -> None:
    protocol = frozen_protocol()
    handler = RejectRedirectHandler()

    with pytest.raises(RedirectRejectedError):
        handler.redirect_request(
            None,
            None,
            302,
            "Found",
            {},
            "https://data.binance.vision/redirected.zip",
        )
    pilot_target = next(
        target for target in protocol.targets if target.reuse_verified_pilot_file
    )
    with pytest.raises(ValueError, match="non-network target"):
        _validate_url(pilot_target, protocol)


def test_checkpoint_round_trip_and_lineage_guard(tmp_path: Path) -> None:
    protocol = frozen_protocol()
    path = tmp_path / "checkpoint.json"
    months = [synthetic_month(protocol, "2019-01")]

    write_checkpoint(path=path, protocol=protocol, months=months)

    assert load_checkpoint(path=path, protocol=protocol) == months
    payload = path.read_text(encoding="utf-8").replace(
        protocol.protocol_evidence_hash,
        "0" * 64,
    )
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint audit failed"):
        load_checkpoint(path=path, protocol=protocol)


def test_complete_result_passes_only_to_no_return_feature_specification() -> None:
    protocol = frozen_protocol()
    months = [synthetic_month(protocol, month) for month in JAM_FULL_MONTHS]
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        protocol=protocol,
        months=months,
    )

    assert result.passed_month_count == 48
    assert result.failed_month_count == 0
    assert result.total_archive_count == 96
    assert result.reused_pilot_archive_count == 2
    assert result.newly_acquired_archive_count == 94
    assert result.total_head_request_count == 94
    assert result.total_payload_get_request_count == 94
    assert result.decision == JAM_FULL_ACQUISITION_PASS_DECISION
    assert (
        result.next_required_authorization
        == JAM_FULL_ACQUISITION_NEXT_AUTHORIZATION
    )
    assert result.feature_fields_created == []
    assert result.return_metrics_calculated == []
    assert result.creates_candidate is False
    assert result.creates_testnet_order_authority is False
    assert result.creates_live_eligibility is False
    assert audit_jam_full_acquisition_result(result)


def test_result_refuses_return_or_live_tampering() -> None:
    protocol = frozen_protocol()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        protocol=protocol,
        months=[synthetic_month(protocol, month) for month in JAM_FULL_MONTHS],
    )
    payload = result.model_dump()
    payload["return_metrics_calculated"] = ["net_return"]
    payload["creates_live_eligibility"] = True

    with pytest.raises(ValidationError):
        JamFullAcquisitionResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/audit_jam_archive_full_acquisition.py",
        "scripts/freeze_jam_archive_full_acquisition_protocol.py",
        "scripts/migrate_jam_full_acquisition_checkpoint.py",
        "scripts/run_jam_archive_full_acquisition.py",
    ],
)
def test_full_acquisition_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
