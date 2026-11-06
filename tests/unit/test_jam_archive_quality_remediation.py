from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_archive_quality_remediation import (
    JAM_QUALITY_NEXT_AUTHORIZATION,
    JAM_QUALITY_PASS_DECISION,
    JamCrossFamilyMismatch,
    JamDuplicateMemberEvidence,
    JamKlineGapInterval,
    JamKlineRowDefect,
    JamMinuteValues,
    JamQualityEvidencePartition,
    audit_jam_archive_quality_protocol,
    audit_jam_archive_quality_result,
    build_jam_archive_quality_protocol,
    build_jam_archive_quality_result,
)

HASH = "a" * 64


def limitations() -> list[str]:
    return [f"Limitation {index}" for index in range(12)]


def partitions() -> list[JamQualityEvidencePartition]:
    return [
        JamQualityEvidencePartition(
            partition_id="JAM_DEVELOPMENT_2019_2020",
            start_month="2019-01",
            end_month="2020-12",
            role="DEVELOPMENT",
        ),
        JamQualityEvidencePartition(
            partition_id="JAM_SEALED_VALIDATION_2021",
            start_month="2021-01",
            end_month="2021-12",
            role="SEALED_VALIDATION",
        ),
        JamQualityEvidencePartition(
            partition_id="JAM_SEALED_HOLDOUT_2022",
            start_month="2022-01",
            end_month="2022-12",
            role="SEALED_HOLDOUT",
        ),
    ]


def minute_values(value: str = "1.00000000") -> JamMinuteValues:
    return JamMinuteValues(
        open_price=value,
        high_price=value,
        low_price=value,
        close_price=value,
        base_volume=value,
        quote_volume=value,
        raw_trade_count=1,
        taker_buy_base_volume=value,
        taker_buy_quote_volume=value,
    )


def quality_result():
    gap_time = 1_546_300_800_000
    duplicate = JamDuplicateMemberEvidence(
        archive_path="archive.zip",
        archive_sha256=HASH,
        duplicate_member_name="nested/BTCUSDT-aggTrades-2021-12.csv",
        canonical_member_bytes=10,
        duplicate_member_bytes=10,
        canonical_member_sha256=HASH,
        duplicate_member_sha256=HASH,
        byte_identical=True,
        policy_pass=True,
    )
    return build_jam_archive_quality_result(
        generated_at=datetime(2026, 8, 4, tzinfo=UTC),
        protocol_evidence_hash=HASH,
        runner_contract_hash=HASH,
        parent_result_evidence_hash=HASH,
        parent_audit_evidence_hash=HASH,
        duplicate_member=duplicate,
        kline_gap_intervals=[
            JamKlineGapInterval(
                month="2019-01",
                start_open_time_ms=gap_time,
                end_open_time_ms=gap_time,
                missing_minute_count=1,
                following_open_time_ms=gap_time + 60_000,
            )
        ],
        kline_row_defects=[
            JamKlineRowDefect(
                month="2019-01",
                open_time_ms=gap_time,
                reason_codes=["CLOSE_TIME_MISMATCH"],
                observed_close_time_ms=gap_time + 59_000,
                expected_close_time_ms=gap_time + 59_999,
            )
        ],
        cross_family_mismatches=[
            JamCrossFamilyMismatch(
                month="2019-01",
                open_time_ms=gap_time + 60_000,
                mismatch_dimensions=["RAW_TRADE_COUNT"],
                aggregate_values=minute_values(),
                kline_values=minute_values("2.00000000"),
            )
        ],
        aggregate_primary_source_qualified=True,
        evidence_partitions=partitions(),
        contaminated_or_excluded_periods=["2023-2025", "2026 onward"],
        limitations=limitations(),
    )


def test_protocol_freezes_no_return_boundary_and_partitions() -> None:
    protocol = build_jam_archive_quality_protocol(
        frozen_at=datetime(2026, 8, 4, tzinfo=UTC),
        parent_protocol_file_sha256=HASH,
        parent_protocol_evidence_hash=HASH,
        parent_result_file_sha256=HASH,
        parent_result_evidence_hash=HASH,
        parent_audit_file_sha256=HASH,
        parent_audit_evidence_hash=HASH,
        raw_manifest_hash=HASH,
        builder_contract_hash=HASH,
        limitations=limitations(),
    )

    assert audit_jam_archive_quality_protocol(protocol)
    assert not protocol.return_calculation_permitted
    assert not protocol.strategy_execution_permitted
    assert [item.role for item in protocol.evidence_partitions] == [
        "DEVELOPMENT",
        "SEALED_VALIDATION",
        "SEALED_HOLDOUT",
    ]


def test_result_reconciles_quarantine_union_and_next_gate() -> None:
    result = quality_result()

    assert audit_jam_archive_quality_result(result)
    assert result.quarantined_minute_count == 2
    assert result.decision == JAM_QUALITY_PASS_DECISION
    assert result.next_required_authorization == JAM_QUALITY_NEXT_AUTHORIZATION
    assert result.return_metrics_calculated == []


def test_result_rejects_quarantine_tampering() -> None:
    payload = quality_result().model_dump()
    payload["quarantined_minute_count"] = 3

    with pytest.raises(ValidationError, match="quarantine manifest changed"):
        type(quality_result()).model_validate(payload)


def test_result_rejects_forbidden_outcome_fields() -> None:
    payload = quality_result().model_dump()
    payload["return_metrics_calculated"] = ["profit_factor"]

    with pytest.raises(ValidationError, match="may contain no outcomes"):
        type(quality_result()).model_validate(payload)
