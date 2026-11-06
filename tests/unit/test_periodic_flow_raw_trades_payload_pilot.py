from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_payload_pilot import (
    PeriodicFlowPairedClockEvidence,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_evidence_v2 import (
    RawTradesPayloadPilotAuditV2,
    RawTradesPayloadPilotResultV2,
    audit_raw_payload_audit_v2,
    audit_raw_payload_result_v2,
    build_raw_payload_result_v2,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (
    RAW_PAYLOAD_FAIL_DECISION,
    RAW_PAYLOAD_PASS_DECISION,
    RawTradesArchiveEvidence,
    RawTradesPayloadPilotProtocol,
    RawTradesPayloadProtocolAudit,
    audit_raw_payload_protocol,
    audit_raw_payload_protocol_audit,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_periodic_flow_raw_trades_payload_pilot import (
    DEFAULT_RAW_CENSUS_AUDIT,
    DEFAULT_RAW_CENSUS_RESULT,
    DEFAULT_SOURCE_AUDIT,
    DEFAULT_SOURCE_RESULT,
    DEFAULT_SPOT_AUDIT,
    DEFAULT_SPOT_RESULT,
    authoritative_protocol,
)
from scripts.run_periodic_flow_raw_trades_payload_pilot import raw_evidence_reasons

PROTOCOL_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_v1.json"
)
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_audit_v1.json"
)
RESULT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_result_v2.json"
)
AUDIT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_payload_pilot_audit_v2.json"
)


def protocol() -> RawTradesPayloadPilotProtocol:
    return authoritative_protocol(
        frozen_at=datetime(2026, 8, 7, 14, tzinfo=UTC),
        raw_census_result_path=DEFAULT_RAW_CENSUS_RESULT,
        raw_census_audit_path=DEFAULT_RAW_CENSUS_AUDIT,
        source_result_path=DEFAULT_SOURCE_RESULT,
        source_audit_path=DEFAULT_SOURCE_AUDIT,
        spot_result_path=DEFAULT_SPOT_RESULT,
        spot_audit_path=DEFAULT_SPOT_AUDIT,
    )


def passing_raw_evidence() -> RawTradesArchiveEvidence:
    return RawTradesArchiveEvidence(
        archive_bytes=1_000,
        zip_compressed_bytes=900,
        zip_uncompressed_bytes=9_000,
        header_present=False,
        row_count=100_000,
        first_timestamp_ms=1_577_836_800_001,
        last_timestamp_ms=1_580_515_199_999,
        unique_minute_count=44_640,
        minute_coverage_fraction=Decimal("1"),
        maximum_event_gap_minutes=1,
        first_trade_id=1,
        last_trade_id=100_000,
        trade_id_non_increasing_count=0,
        trade_id_duplicate_count=0,
        forward_gap_count=0,
        skipped_trade_id_count=0,
        skipped_trade_id_fraction=Decimal("0"),
        maximum_single_skipped_trade_id_count=0,
        timestamp_regression_count=0,
        buyer_maker_values_observed=(False, True),
        payload_get_attempt_count=1,
        archive_pass=True,
        reason_codes=(),
    )


def passing_clock() -> PeriodicFlowPairedClockEvidence:
    return PeriodicFlowPairedClockEvidence(
        spot_unique_minute_count=44_640,
        usd_m_unique_minute_count=44_640,
        paired_minute_count=44_640,
        union_minute_count=44_640,
        paired_month_coverage_fraction=Decimal("1"),
        paired_union_overlap_fraction=Decimal("1"),
        spot_only_minute_count=0,
        usd_m_only_minute_count=0,
        paired_clock_pass=True,
        reason_codes=(),
    )


def build_result(
    raw: RawTradesArchiveEvidence,
    clock: PeriodicFlowPairedClockEvidence | None = None,
) -> RawTradesPayloadPilotResultV2:
    frozen = protocol()
    return build_raw_payload_result_v2(
        generated_at=datetime(2026, 8, 7, 15, tzinfo=UTC),
        protocol_file_sha256="1" * 64,
        protocol_evidence_hash=frozen.protocol_evidence_hash,
        protocol_audit_file_sha256="2" * 64,
        protocol_audit_evidence_hash="3" * 64,
        runner_contract_hash="4" * 64,
        raw_archive_evidence=raw,
        paired_clock_evidence=clock or passing_clock(),
        request_marker_manifest_hash="5" * 64,
        request_marker_count=raw.payload_get_attempt_count,
        payload_get_attempt_count=raw.payload_get_attempt_count,
        total_new_archive_bytes=raw.archive_bytes,
        limitations=tuple(f"limitation-{index}" for index in range(9)),
    )


def rehash(payload: dict) -> dict:
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )
    return payload


def test_raw_payload_protocol_is_exact_pre_network_and_no_authority() -> None:
    frozen = protocol()

    assert audit_raw_payload_protocol(frozen)
    assert frozen.target.month == "2020-01"
    assert frozen.target.family == "trades"
    assert frozen.maximum_unique_archive_urls == 1
    assert frozen.maximum_payload_get_attempts == 3
    assert frozen.maximum_skipped_trade_id_fraction == Decimal("0.001")
    assert frozen.maximum_single_skipped_trade_id_count == 100
    assert frozen.price_or_quantity_parsing_permitted is False
    assert frozen.return_calculation_permitted is False
    assert frozen.paper_operation_permitted is False
    assert frozen.testnet_strategy_orders_permitted is False
    assert frozen.live_permitted is False


def test_raw_payload_protocol_binds_qualified_spot_and_exact_raw_hash() -> None:
    frozen = protocol()

    assert frozen.qualified_spot_reference.source_archive_pass is True
    assert frozen.qualified_spot_reference.unique_minute_count == 44_640
    assert frozen.qualified_spot_reference.archive_sha256.startswith("ea2f0aa8")
    assert frozen.target.published_archive_sha256.startswith("5d3b5ab9")
    assert frozen.target.expected_columns == (
        "trade_id",
        "price",
        "quantity",
        "quote_quantity",
        "timestamp",
        "buyer_was_maker",
    )


def test_raw_payload_reason_gate_accepts_only_bounded_forward_omissions() -> None:
    assert raw_evidence_reasons(
        row_count=100_000,
        minute_coverage_fraction=Decimal("1"),
        maximum_event_gap_minutes=1,
        trade_id_non_increasing_count=0,
        trade_id_duplicate_count=0,
        skipped_trade_id_fraction=Decimal("0.0009"),
        maximum_single_skipped_trade_id_count=100,
        timestamp_regression_count=0,
        buyer_maker_values_observed=(False, True),
    ) == ()

    reasons = raw_evidence_reasons(
        row_count=99_999,
        minute_coverage_fraction=Decimal("0.98"),
        maximum_event_gap_minutes=16,
        trade_id_non_increasing_count=1,
        trade_id_duplicate_count=1,
        skipped_trade_id_fraction=Decimal("0.0011"),
        maximum_single_skipped_trade_id_count=101,
        timestamp_regression_count=1,
        buyer_maker_values_observed=(True,),
    )
    assert set(reasons) == {
        "BUYER_MAKER_DOMAIN_INCOMPLETE",
        "EVENT_GAP_EXCEEDS_15_MINUTES",
        "MINUTE_COVERAGE_BELOW_0_99",
        "ROW_COUNT_BELOW_100000",
        "SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100",
        "SKIPPED_TRADE_ID_FRACTION_EXCEEDS_0_001",
        "TIMESTAMP_REGRESSION",
        "TRADE_ID_DUPLICATE",
        "TRADE_ID_NOT_STRICTLY_INCREASING",
    }


def test_raw_archive_model_rejects_mismatched_skipped_fraction() -> None:
    payload = passing_raw_evidence().model_dump()
    payload["skipped_trade_id_count"] = 1
    payload["forward_gap_count"] = 1
    with pytest.raises(ValidationError, match="skipped-ID fraction"):
        RawTradesArchiveEvidence.model_validate(payload)


def test_raw_payload_result_passes_only_when_archive_and_pair_pass() -> None:
    passed = build_result(passing_raw_evidence())
    assert audit_raw_payload_result_v2(passed)
    assert passed.decision == RAW_PAYLOAD_PASS_DECISION
    assert passed.authorizes_paired_full_development_acquisition_protocol is True
    assert passed.price_or_quantity_values_parsed == ()
    assert passed.orders_submitted == 0

    payload = passing_raw_evidence().model_dump()
    payload.update(
        trade_id_non_increasing_count=1,
        trade_id_duplicate_count=1,
        archive_pass=False,
        reason_codes=(
            "TRADE_ID_DUPLICATE",
            "TRADE_ID_NOT_STRICTLY_INCREASING",
        ),
    )
    failed = build_result(RawTradesArchiveEvidence.model_validate(payload))
    assert failed.decision == RAW_PAYLOAD_FAIL_DECISION
    assert failed.authorizes_paired_full_development_acquisition_protocol is False


def test_raw_payload_result_rejects_rehashed_outcome_or_trading_claims() -> None:
    result = build_result(passing_raw_evidence())
    payload = result.model_dump()
    payload["return_metrics_calculated"] = ["expectancy"]
    with pytest.raises(ValidationError):
        RawTradesPayloadPilotResultV2.model_validate(rehash(payload))


def test_canonical_raw_payload_lineage_is_complete_marker_bound_and_no_outcomes() -> None:
    frozen = RawTradesPayloadPilotProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = RawTradesPayloadProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = RawTradesPayloadPilotResultV2.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = RawTradesPayloadPilotAuditV2.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit_raw_payload_protocol(frozen)
    assert audit_raw_payload_protocol_audit(protocol_audit)
    assert audit_raw_payload_result_v2(result)
    assert audit_raw_payload_audit_v2(audit)
    assert protocol_audit.protocol_evidence_hash == frozen.protocol_evidence_hash
    assert result.protocol_evidence_hash == frozen.protocol_evidence_hash
    assert audit.result_evidence_hash == result.result_evidence_hash
    assert audit.request_marker_manifest_hash == result.request_marker_manifest_hash
    assert result.request_marker_count == 1
    assert result.payload_get_attempt_count == 1
    assert result.raw_archive_evidence.row_count == 10_281_248
    assert result.raw_archive_evidence.unique_minute_count == 44_640
    assert result.raw_archive_evidence.trade_id_duplicate_count == 0
    assert result.raw_archive_evidence.trade_id_non_increasing_count == 0
    assert result.raw_archive_evidence.forward_gap_count == 726
    assert result.raw_archive_evidence.skipped_trade_id_count == 1_809
    assert result.raw_archive_evidence.maximum_single_skipped_trade_id_count == 35
    assert result.raw_archive_evidence.timestamp_regression_count == 0
    assert result.raw_archive_evidence.archive_pass is True
    assert result.paired_clock_evidence.paired_minute_count == 44_640
    assert result.authorizes_paired_full_development_acquisition_protocol is True
    assert result.price_or_quantity_values_parsed == ()
    assert result.return_metrics_calculated == ()
    assert result.strategy_candidates_created == 0
    assert result.orders_submitted == 0
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False

    payload = result.model_dump()
    payload["authorizes_testnet_strategy_orders"] = True
    with pytest.raises(ValidationError):
        RawTradesPayloadPilotResultV2.model_validate(rehash(payload))
