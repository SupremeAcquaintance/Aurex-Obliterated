import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (
    RAW_TRADES_FAIL_DECISION,
    RAW_TRADES_MONTHS,
    RAW_TRADES_PASS_DECISION,
    RawTradesMetadataCensusAudit,
    RawTradesMetadataCensusProtocol,
    RawTradesMetadataCensusResult,
    RawTradesMetadataProtocolAudit,
    RawTradesMetadataRecord,
    RawTradesMetadataTarget,
    audit_raw_trades_audit,
    audit_raw_trades_protocol,
    audit_raw_trades_protocol_audit,
    audit_raw_trades_result,
    authoritative_raw_trades_targets,
    build_raw_trades_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_periodic_flow_raw_trades_metadata_census import (
    DEFAULT_PARENT_AUDIT,
    DEFAULT_PARENT_RESULT,
    DEFAULT_READINESS_AUDIT,
    DEFAULT_READINESS_RESULT,
    authoritative_protocol,
)
from scripts.run_periodic_flow_raw_trades_metadata_census import (
    ChecksumHttpObservation,
    fetch_raw_trades_metadata_record,
)

PROTOCOL_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_protocol_v1.json"
)
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_protocol_audit_v1.json"
)
RESULT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_result_v1.json"
)
AUDIT_PATH = Path(
    "data/evidence/q1_usdm_raw_trades_metadata_census_audit_v1.json"
)


def protocol() -> RawTradesMetadataCensusProtocol:
    return authoritative_protocol(
        frozen_at=datetime(2026, 8, 7, 12, tzinfo=UTC),
        parent_result_path=DEFAULT_PARENT_RESULT,
        parent_audit_path=DEFAULT_PARENT_AUDIT,
        readiness_result_path=DEFAULT_READINESS_RESULT,
        readiness_audit_path=DEFAULT_READINESS_AUDIT,
    )


def present_record(target: RawTradesMetadataTarget) -> RawTradesMetadataRecord:
    archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
    checksum_text = f"{'a' * 64}  {archive_name}"
    return RawTradesMetadataRecord(
        **target.model_dump(),
        checked_at=datetime(2026, 8, 7, 12, tzinfo=UTC),
        http_status=200,
        checksum_response_bytes=len(checksum_text.encode("utf-8")) + 1,
        checksum_text=checksum_text,
        checksum_text_sha256=sha256(checksum_text.encode("utf-8")).hexdigest(),
        archive_sha256="a" * 64,
        availability="PRESENT",
        request_attempt_count=1,
    )


def result_with(
    records: tuple[RawTradesMetadataRecord, ...],
) -> RawTradesMetadataCensusResult:
    frozen = protocol()
    return build_raw_trades_result(
        generated_at=datetime(2026, 8, 7, 13, tzinfo=UTC),
        protocol_file_sha256="1" * 64,
        protocol_evidence_hash=frozen.protocol_evidence_hash,
        protocol_audit_file_sha256="2" * 64,
        protocol_audit_evidence_hash="3" * 64,
        target_manifest_hash=frozen.target_manifest_hash,
        runner_contract_hash="4" * 64,
        records=records,
        limitations=tuple(f"limitation-{index}" for index in range(8)),
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


def test_raw_trades_target_matrix_is_exact_and_checksum_only() -> None:
    targets = authoritative_raw_trades_targets()

    assert len(targets) == 72
    assert tuple(item.month for item in targets) == RAW_TRADES_MONTHS
    assert len({item.checksum_url for item in targets}) == 72
    assert sum(item.partition_role == "DEVELOPMENT" for item in targets) == 48
    assert sum(item.partition_role == "VALIDATION_METADATA" for item in targets) == 24
    assert all(
        "/futures/um/monthly/trades/BTCUSDT/" in item.checksum_url
        and item.checksum_url.endswith(".zip.CHECKSUM")
        for item in targets
    )


def test_raw_trades_protocol_is_pre_network_and_grants_no_outcome_authority() -> None:
    frozen = protocol()

    assert audit_raw_trades_protocol(frozen)
    assert frozen.maximum_unique_checksum_urls == 72
    assert frozen.required_present_target_count == 72
    assert frozen.checksum_get_requests_permitted is True
    assert frozen.archive_head_requests_permitted is False
    assert frozen.archive_payload_requests_permitted is False
    assert frozen.market_numeric_values_permitted is False
    assert frozen.strategy_outcomes_permitted is False
    assert frozen.paper_operation_permitted is False
    assert frozen.testnet_strategy_orders_permitted is False
    assert frozen.live_permitted is False


def test_raw_trades_target_refuses_month_family_and_url_drift() -> None:
    target = authoritative_raw_trades_targets()[0]

    for update in (
        {"month": "2019-12"},
        {"family": "aggTrades"},
        {"checksum_url": target.checksum_url.replace("BTCUSDT", "ETHUSDT")},
        {"archive_url": target.archive_url + "?download=1"},
    ):
        payload = target.model_dump()
        payload.update(update)
        with pytest.raises(ValidationError):
            RawTradesMetadataTarget.model_validate(payload)


def test_raw_trades_fetch_parses_checksum_without_requesting_archive() -> None:
    frozen = protocol()
    target = frozen.targets[0]
    archive_name = Path(target.archive_url).name
    payload = f"{'b' * 64}  {archive_name}\n".encode()

    def fake_fetch(url: str, timeout: int, maximum_bytes: int):
        assert url == target.checksum_url
        assert timeout == 30
        assert maximum_bytes == 512
        return ChecksumHttpObservation(
            status=200,
            payload=payload,
            checked_at=datetime(2026, 8, 7, 12, tzinfo=UTC),
        )

    record = fetch_raw_trades_metadata_record(
        target=target,
        protocol=frozen,
        fetch_once=fake_fetch,
    )

    assert record.availability == "PRESENT"
    assert record.archive_sha256 == "b" * 64
    assert record.checksum_response_bytes == len(payload)


def test_raw_trades_fetch_preserves_404_and_refuses_unfrozen_target() -> None:
    frozen = protocol()
    target = frozen.targets[0]
    missing = fetch_raw_trades_metadata_record(
        target=target,
        protocol=frozen,
        fetch_once=lambda *_: ChecksumHttpObservation(
            status=404,
            payload=b"",
            checked_at=datetime(2026, 8, 7, 12, tzinfo=UTC),
        ),
    )
    assert missing.availability == "MISSING"
    assert missing.checksum_text is None

    other = frozen.targets[1].model_dump()
    other["month"] = "2019-12"
    with pytest.raises(ValidationError):
        RawTradesMetadataTarget.model_validate(other)


def test_raw_trades_result_passes_only_when_all_72_targets_are_present() -> None:
    records = tuple(present_record(item) for item in authoritative_raw_trades_targets())
    passed = result_with(records)

    assert audit_raw_trades_result(passed)
    assert passed.decision == RAW_TRADES_PASS_DECISION
    assert passed.summary.present_count == 72
    assert passed.summary.development_present_count == 48
    assert passed.summary.validation_metadata_present_count == 24
    assert passed.authorizes_one_month_payload_protocol is True
    assert passed.archive_payload_requests_made == 0
    assert passed.market_numeric_fields_inspected == ()

    missing_payload = records[0].model_dump()
    missing_payload.update(
        http_status=404,
        checksum_response_bytes=0,
        checksum_text=None,
        checksum_text_sha256=None,
        archive_sha256=None,
        availability="MISSING",
    )
    incomplete = result_with(
        (RawTradesMetadataRecord.model_validate(missing_payload), *records[1:])
    )
    assert incomplete.decision == RAW_TRADES_FAIL_DECISION
    assert incomplete.summary.present_count == 71
    assert incomplete.authorizes_one_month_payload_protocol is False


def test_raw_trades_result_rejects_rehashed_outcomes_and_trading_authority() -> None:
    result = result_with(
        tuple(present_record(item) for item in authoritative_raw_trades_targets())
    )
    payload = result.model_dump()
    payload["return_metrics_calculated"] = ["expectancy"]
    with pytest.raises(ValidationError):
        RawTradesMetadataCensusResult.model_validate(rehash(payload))

    payload = result.model_dump()
    payload["authorizes_testnet_strategy_orders"] = True
    with pytest.raises(ValidationError):
        RawTradesMetadataCensusResult.model_validate(rehash(payload))


def test_canonical_raw_trades_census_lineage_is_complete_and_checksum_only() -> None:
    frozen = RawTradesMetadataCensusProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = RawTradesMetadataProtocolAudit.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = RawTradesMetadataCensusResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = RawTradesMetadataCensusAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit_raw_trades_protocol(frozen)
    assert audit_raw_trades_protocol_audit(protocol_audit)
    assert audit_raw_trades_result(result)
    assert audit_raw_trades_audit(audit)
    assert protocol_audit.protocol_evidence_hash == frozen.protocol_evidence_hash
    assert result.protocol_evidence_hash == frozen.protocol_evidence_hash
    assert audit.result_evidence_hash == result.result_evidence_hash
    assert result.summary.present_count == 72
    assert result.summary.missing_count == 0
    assert result.summary.development_present_count == 48
    assert result.summary.validation_metadata_present_count == 24
    assert result.checksum_get_requests_made == 72
    assert all(record.request_attempt_count == 1 for record in result.records)
    assert result.archive_head_requests_made == 0
    assert result.archive_payload_requests_made == 0
    assert result.archive_payload_bytes == 0
    assert result.market_numeric_fields_inspected == ()
    assert result.return_metrics_calculated == ()
    assert result.strategy_candidates_created == 0
    assert result.orders_submitted == 0
    assert result.authorizes_one_month_payload_protocol is True
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False


@pytest.mark.parametrize(
    ("script", "flag"),
    (
        ("scripts/freeze_periodic_flow_raw_trades_metadata_census.py", "--check"),
        ("scripts/audit_periodic_flow_raw_trades_metadata_protocol.py", "--check"),
        ("scripts/run_periodic_flow_raw_trades_metadata_census.py", "--check"),
        ("scripts/audit_periodic_flow_raw_trades_metadata_census.py", "--check"),
    ),
)
def test_raw_trades_census_direct_checks_pass(script: str, flag: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, flag],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("PASS ")
