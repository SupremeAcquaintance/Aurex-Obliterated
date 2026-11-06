from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.research_v3_discovery_charter import (
    V3MechanismDiscoveryCharter,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3P02AggTradesCensusContract,
    V3P02AggTradesCensusResult,
)
from aurex.backtest_engine.research_v3_p02_payload_pilot import (
    V3_P02_FULL_COHORT_SYMBOLS,
    V3_P02_PILOT_FAIL_DECISION,
    V3_P02_PILOT_PASS_DECISION,
    V3_P02_SAMPLE_KEYS,
    V3P02ArchiveSizeObservation,
    V3P02PayloadPilotProtocol,
    V3P02PayloadPilotResult,
    V3P02PayloadTarget,
    V3P02SamplePayloadEvidence,
    audit_v3_p02_payload_pilot_protocol,
    audit_v3_p02_payload_pilot_result,
    build_v3_p02_payload_pilot_result,
)
from aurex.backtest_engine.research_v3_proposal_register import (
    V3MechanismProposalRegister,
)
from scripts.freeze_v3_p02_payload_pilot_protocol import (
    authoritative_protocol,
)
from scripts.run_v3_p02_payload_pilot import (
    HeadHttpObservation,
    fetch_head_observation,
    inspect_sample_archive,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def frozen_protocol() -> V3P02PayloadPilotProtocol:
    charter = V3MechanismDiscoveryCharter.model_validate_json(
        (
            PROJECT_ROOT
            / "data"
            / "evidence"
            / "v3_mechanism_discovery_charter_v1.json"
        ).read_text(encoding="utf-8")
    )
    register = V3MechanismProposalRegister.model_validate_json(
        (
            PROJECT_ROOT
            / "data"
            / "evidence"
            / "v3_mechanism_proposal_register_v1.json"
        ).read_text(encoding="utf-8")
    )
    census_contract = V3P02AggTradesCensusContract.model_validate_json(
        (
            PROJECT_ROOT
            / "data"
            / "evidence"
            / "v3_p02_aggtrades_census_contract_v1.json"
        ).read_text(encoding="utf-8")
    )
    census_result = V3P02AggTradesCensusResult.model_validate_json(
        (
            PROJECT_ROOT
            / "data"
            / "evidence"
            / "v3_p02_aggtrades_census_result_v1.json"
        ).read_text(encoding="utf-8")
    )
    return authoritative_protocol(
        frozen_at=OBSERVED_AT,
        charter=charter,
        register=register,
        census_contract=census_contract,
        census_result=census_result,
    )


def size_observations(
    protocol: V3P02PayloadPilotProtocol,
    *,
    content_length: int = 1_000_000,
) -> list[V3P02ArchiveSizeObservation]:
    return [
        V3P02ArchiveSizeObservation(
            symbol=target.symbol,
            month=target.month,
            archive_url=target.archive_url,
            observed_at=OBSERVED_AT,
            http_status=200,
            content_length_bytes=content_length,
            etag=None,
            last_modified=None,
            request_attempt_count=1,
        )
        for target in protocol.targets
    ]


def passing_sample(
    target: V3P02PayloadTarget,
) -> V3P02SamplePayloadEvidence:
    year, month_number = (int(part) for part in target.month.split("-"))
    start = datetime(year, month_number, 1, tzinfo=UTC)
    if month_number == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month_number + 1, 1, tzinfo=UTC)
    expected_minutes = int((end - start).total_seconds() // 60)
    first_ms = int(start.timestamp() * 1000)
    return V3P02SamplePayloadEvidence(
        symbol=target.symbol,
        month=target.month,
        archive_url=target.archive_url,
        local_path=(
            f"v3_p02_payload_pilot_v1/{target.symbol}/"
            f"{target.symbol}-aggTrades-{target.month}.zip"
        ),
        archive_bytes=1_000_000,
        archive_sha256=target.checksum_sha256,
        published_checksum_sha256=target.checksum_sha256,
        checksum_verified=True,
        csv_member_name=f"{target.symbol}-aggTrades-{target.month}.csv",
        zip_compressed_bytes=900_000,
        zip_uncompressed_bytes=90_000_000,
        column_count=7,
        header_present=True,
        row_count=expected_minutes,
        first_timestamp_ms=first_ms,
        last_timestamp_ms=first_ms + (expected_minutes - 1) * 60_000,
        unique_minute_count=expected_minutes,
        expected_minute_count=expected_minutes,
        minute_coverage_fraction=Decimal(1),
        maximum_event_gap_minutes=1,
        aggregate_trade_id_gap_count=0,
        duplicate_timestamp_count=0,
        payload_request_count=1,
        sample_pass=True,
        reason_codes=[],
        market_numeric_fields_inspected=[],
    )


def test_v3p02_payload_protocol_freezes_exact_no_return_scope() -> None:
    protocol = frozen_protocol()

    assert len(protocol.targets) == 744
    assert len({target.key for target in protocol.targets}) == 744
    assert protocol.full_cohort_symbols == sorted(V3_P02_FULL_COHORT_SYMBOLS)
    assert protocol.sample_keys == sorted(
        f"{symbol}/{month}" for symbol, month in V3_P02_SAMPLE_KEYS
    )
    assert sum(target.sample_payload for target in protocol.targets) == 3
    assert sum(target.full_cohort for target in protocol.targets) == 240
    assert protocol.expected_column_count == 7
    assert protocol.aggregate_trade_id_column_index == 0
    assert protocol.timestamp_column_index == 5
    assert protocol.maximum_head_http_attempts == 2232
    assert protocol.maximum_sample_payload_requests == 3
    assert protocol.market_price_quantity_or_side_inspection_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.selection_permitted is False
    assert audit_v3_p02_payload_pilot_protocol(protocol)


def test_v3p02_payload_protocol_refuses_resource_tampering() -> None:
    protocol = frozen_protocol()
    payload = protocol.model_dump()
    payload["maximum_zip_expansion_ratio"] = 101

    with pytest.raises(ValidationError):
        V3P02PayloadPilotProtocol.model_validate(payload)


def test_v3p02_head_retries_only_within_frozen_budget() -> None:
    protocol = frozen_protocol()
    target = protocol.targets[0]
    attempts = iter(
        [
            HeadHttpObservation(
                status=503,
                content_length=None,
                etag=None,
                last_modified=None,
                observed_at=OBSERVED_AT,
            ),
            HeadHttpObservation(
                status=200,
                content_length="123456",
                etag='"etag"',
                last_modified="Tue, 28 Jul 2026 12:00:00 GMT",
                observed_at=OBSERVED_AT,
            ),
        ]
    )
    sleeps: list[float] = []

    record = fetch_head_observation(
        target=target,
        protocol=protocol,
        head_once=lambda _url, _timeout: next(attempts),
        sleep=sleeps.append,
    )

    assert record.content_length_bytes == 123456
    assert record.request_attempt_count == 2
    assert sleeps == [1]


def test_v3p02_head_refuses_missing_content_length() -> None:
    protocol = frozen_protocol()

    with pytest.raises(ValueError, match="no Content-Length"):
        fetch_head_observation(
            target=protocol.targets[0],
            protocol=protocol,
            head_once=lambda _url, _timeout: HeadHttpObservation(
                status=200,
                content_length=None,
                etag=None,
                last_modified=None,
                observed_at=OBSERVED_AT,
            ),
            sleep=lambda _delay: None,
        )


def test_v3p02_sample_parser_reads_only_id_and_timestamp(
    tmp_path: Path,
) -> None:
    protocol = frozen_protocol()
    original = next(
        target
        for target in protocol.targets
        if target.key == V3_P02_SAMPLE_KEYS[0]
    )
    archive_path = (
        tmp_path
        / "v3_p02_payload_pilot_v1"
        / original.symbol
        / f"{original.symbol}-aggTrades-{original.month}.zip"
    )
    archive_path.parent.mkdir(parents=True)
    csv_name = f"{original.symbol}-aggTrades-{original.month}.csv"
    start_ms = int(
        datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000
    )
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        with archive.open(csv_name, "w") as raw:
            text = raw
            rows = [
                [
                    "agg_trade_id",
                    "price",
                    "quantity",
                    "first_trade_id",
                    "last_trade_id",
                    "transact_time",
                    "is_buyer_maker",
                ],
                [
                    "100",
                    "not-a-price",
                    "not-a-quantity",
                    "not-a-first-id",
                    "not-a-last-id",
                    str(start_ms),
                    "not-a-side",
                ],
                [
                    "101",
                    "still-not-a-price",
                    "still-not-a-quantity",
                    "still-not-a-first-id",
                    "still-not-a-last-id",
                    str(start_ms + 60_000),
                    "still-not-a-side",
                ],
            ]
            text.write(
                ("\n".join(",".join(row) for row in rows) + "\n").encode()
            )
    target = V3P02PayloadTarget(
        **original.model_dump(exclude={"checksum_sha256"}),
        checksum_sha256=file_sha256(archive_path),
    )

    evidence = inspect_sample_archive(
        target=target,
        archive_path=archive_path,
        evidence_root=tmp_path,
        protocol=protocol,
        payload_request_count=1,
    )

    assert evidence.row_count == 2
    assert evidence.header_present is True
    assert evidence.aggregate_trade_id_gap_count == 0
    assert evidence.market_numeric_fields_inspected == []
    assert evidence.sample_pass is False
    assert evidence.reason_codes == ["MINUTE_COVERAGE_BELOW_0_99"]


def test_v3p02_result_passes_only_all_three_gates() -> None:
    protocol = frozen_protocol()
    samples = [
        passing_sample(target)
        for target in protocol.targets
        if target.key in V3_P02_SAMPLE_KEYS
    ]
    result = build_v3_p02_payload_pilot_result(
        generated_at=OBSERVED_AT,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="a" * 64,
        size_observations=size_observations(protocol),
        sample_evidence=samples,
        free_disk_bytes_before_samples=100_000_000_000,
        limitations=[f"limitation {index}" for index in range(6)],
    )

    assert result.decision == V3_P02_PILOT_PASS_DECISION
    assert result.authorizes_separate_full_payload_protocol is True
    assert result.summary.sample_count == 3
    assert result.summary.sample_gate_pass is True
    assert result.return_metrics_calculated == []
    assert audit_v3_p02_payload_pilot_result(result)


def test_v3p02_result_can_reject_resource_gate_without_downloads() -> None:
    protocol = frozen_protocol()
    result = build_v3_p02_payload_pilot_result(
        generated_at=OBSERVED_AT,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="b" * 64,
        size_observations=size_observations(
            protocol,
            content_length=200_000_000,
        ),
        sample_evidence=[],
        free_disk_bytes_before_samples=30_000_000_000,
        limitations=[f"limitation {index}" for index in range(6)],
    )

    assert result.decision == V3_P02_PILOT_FAIL_DECISION
    assert result.authorizes_separate_full_payload_protocol is False
    assert result.summary.sample_count == 0
    assert result.summary.sample_payload_request_count == 0


def test_v3p02_result_refuses_decision_tampering() -> None:
    protocol = frozen_protocol()
    samples = [
        passing_sample(target)
        for target in protocol.targets
        if target.key in V3_P02_SAMPLE_KEYS
    ]
    result = build_v3_p02_payload_pilot_result(
        generated_at=OBSERVED_AT,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="c" * 64,
        size_observations=size_observations(protocol),
        sample_evidence=samples,
        free_disk_bytes_before_samples=100_000_000_000,
        limitations=[f"limitation {index}" for index in range(6)],
    )
    payload = result.model_dump()
    payload["decision"] = V3_P02_PILOT_FAIL_DECISION

    with pytest.raises(ValidationError):
        V3P02PayloadPilotResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_v3_p02_payload_pilot_protocol.py",
        "scripts/run_v3_p02_payload_pilot.py",
    ],
)
def test_v3p02_payload_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "V3P02" in completed.stdout
