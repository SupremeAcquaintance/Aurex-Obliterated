import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_metadata_census import (
    Q1_CENSUS_FAIL_DECISION,
    Q1_CENSUS_MONTHS,
    Q1_CENSUS_PASS_DECISION,
    PeriodicFlowMetadataCensusAudit,
    PeriodicFlowMetadataCensusContract,
    PeriodicFlowMetadataCensusResult,
    PeriodicFlowMetadataRecord,
    PeriodicFlowMetadataTarget,
    audit_metadata_census_audit,
    audit_metadata_census_contract,
    audit_metadata_census_result,
    authoritative_schemas,
    authoritative_targets,
    build_metadata_census_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_periodic_flow_metadata_census_contract import (
    authoritative_contract,
)
from scripts.run_periodic_flow_metadata_census import (
    ChecksumHttpObservation,
    fetch_metadata_record,
)

CONTRACT_PATH = Path(
    "data/evidence/q1_periodic_flow_metadata_census_contract_v1.json"
)
RESULT_PATH = Path(
    "data/evidence/q1_periodic_flow_metadata_census_result_v1.json"
)
AUDIT_PATH = Path(
    "data/evidence/q1_periodic_flow_metadata_census_audit_v1.json"
)


def canonical_contract() -> PeriodicFlowMetadataCensusContract:
    return PeriodicFlowMetadataCensusContract.model_validate_json(
        CONTRACT_PATH.read_text(encoding="utf-8")
    )


def make_present_record(
    target: PeriodicFlowMetadataTarget,
) -> PeriodicFlowMetadataRecord:
    archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
    checksum_text = f"{'0' * 64}  {archive_name}"
    return PeriodicFlowMetadataRecord(
        **target.model_dump(),
        checked_at=datetime(2026, 8, 7, tzinfo=UTC),
        http_status=200,
        checksum_response_bytes=len(checksum_text.encode("utf-8")) + 1,
        checksum_text=checksum_text,
        checksum_text_sha256=sha256(checksum_text.encode("utf-8")).hexdigest(),
        archive_sha256="0" * 64,
        availability="PRESENT",
        request_attempt_count=1,
    )


def build_result(
    records: tuple[PeriodicFlowMetadataRecord, ...],
) -> PeriodicFlowMetadataCensusResult:
    contract = canonical_contract()
    return build_metadata_census_result(
        generated_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        contract_file_sha256="1" * 64,
        contract_evidence_hash=contract.contract_evidence_hash,
        target_manifest_hash=contract.target_manifest_hash,
        schema_register_hash=contract.schema_register_hash,
        runner_contract_hash="2" * 64,
        records=records,
        limitations=("bounded",) * 6,
    )


def rehash_result(payload: dict) -> dict:
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )
    return payload


def test_canonical_q1_census_contract_reconstructs_exactly() -> None:
    stored = canonical_contract()
    expected = authoritative_contract(
        frozen_at=stored.frozen_at,
        charter_path=Path("data/evidence/periodic_flow_spot_charter_v1.json"),
        charter_audit_path=Path(
            "data/evidence/periodic_flow_spot_charter_audit_v1.json"
        ),
        readiness_result_path=Path(
            "data/evidence/aurex_strategy_factory_readiness_current_result_v4.json"
        ),
        readiness_audit_path=Path(
            "data/evidence/aurex_strategy_factory_readiness_current_audit_v4.json"
        ),
    )

    assert stored == expected
    assert audit_metadata_census_contract(stored)
    assert stored.archive_payload_requests_permitted is False
    assert stored.market_numeric_values_permitted is False


def test_q1_matrix_has_exact_products_months_schemas_and_timestamp_units() -> None:
    targets = authoritative_targets()
    schemas = authoritative_schemas()

    assert len(targets) == 144
    assert len(Q1_CENSUS_MONTHS) == 72
    assert {item.product for item in targets} == {"SPOT", "USD_M_PERPETUAL"}
    assert len({item.checksum_url for item in targets}) == 144
    assert all(item.checksum_url.endswith(".zip.CHECKSUM") for item in targets)
    assert all(
        item.expected_timestamp_unit == "MICROSECONDS"
        for item in targets
        if item.product == "SPOT" and item.month >= "2025-01"
    )
    assert all(
        item.expected_timestamp_unit == "MILLISECONDS"
        for item in targets
        if item.product == "USD_M_PERPETUAL" or item.month < "2025-01"
    )
    assert [(item.product, len(item.columns)) for item in schemas] == [
        ("SPOT", 8),
        ("USD_M_PERPETUAL", 7),
    ]


def test_q1_fetch_parses_checksum_text_without_archive_payload() -> None:
    contract = canonical_contract()
    target = contract.targets[0]
    archive_name = target.archive_url.rsplit("/", maxsplit=1)[-1]
    payload = f"{'a' * 64}  {archive_name}\n".encode()

    def fake_fetch(url: str, timeout: int, maximum_bytes: int):
        assert url == target.checksum_url
        assert timeout == 30
        assert maximum_bytes == 512
        return ChecksumHttpObservation(
            status=200,
            payload=payload,
            checked_at=datetime(2026, 8, 7, tzinfo=UTC),
        )

    record = fetch_metadata_record(
        target=target,
        contract=contract,
        fetch_once=fake_fetch,
    )

    assert record.availability == "PRESENT"
    assert record.archive_sha256 == "a" * 64
    assert record.checksum_response_bytes == len(payload)


def test_q1_fetch_records_404_and_refuses_unfrozen_target() -> None:
    contract = canonical_contract()
    target = contract.targets[0]

    record = fetch_metadata_record(
        target=target,
        contract=contract,
        fetch_once=lambda *_: ChecksumHttpObservation(
            status=404,
            payload=b"",
            checked_at=datetime(2026, 8, 7, tzinfo=UTC),
        ),
    )
    assert record.availability == "MISSING"
    assert record.checksum_text is None

    payload = target.model_dump()
    payload["month"] = "2019-12"
    with pytest.raises(ValidationError):
        PeriodicFlowMetadataTarget.model_validate(payload)


def test_q1_result_passes_only_with_every_paired_month_present() -> None:
    records = tuple(make_present_record(target) for target in authoritative_targets())
    passed = build_result(records)
    assert passed.decision == Q1_CENSUS_PASS_DECISION
    assert passed.summary.present_count == 144
    assert passed.summary.paired_present_month_count == 72
    assert passed.authorizes_separate_payload_pilot_protocol is True
    assert passed.archive_payload_requests_made == 0
    assert audit_metadata_census_result(passed)

    missing_payload = records[0].model_dump()
    missing_payload.update(
        http_status=404,
        checksum_response_bytes=0,
        checksum_text=None,
        checksum_text_sha256=None,
        archive_sha256=None,
        availability="MISSING",
    )
    incomplete = build_result(
        (PeriodicFlowMetadataRecord.model_validate(missing_payload), *records[1:])
    )
    assert incomplete.decision == Q1_CENSUS_FAIL_DECISION
    assert incomplete.summary.paired_present_month_count == 71
    assert incomplete.authorizes_separate_payload_pilot_protocol is False


def test_q1_result_rejects_rehashed_authority_and_outcome_tampering() -> None:
    result = build_result(
        tuple(make_present_record(target) for target in authoritative_targets())
    )
    payload = result.model_dump()
    payload["authorizes_testnet_strategy_orders"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowMetadataCensusResult.model_validate(rehash_result(payload))

    payload = result.model_dump()
    payload["return_metrics_calculated"] = ["net_expectancy"]
    with pytest.raises(ValidationError, match="cannot contain outcomes"):
        PeriodicFlowMetadataCensusResult.model_validate(rehash_result(payload))


def test_canonical_q1_result_and_audit_bind_complete_metadata_only_evidence() -> None:
    result = PeriodicFlowMetadataCensusResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = PeriodicFlowMetadataCensusAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit_metadata_census_result(result)
    assert audit_metadata_census_audit(audit)
    assert audit.result_evidence_hash == result.result_evidence_hash
    assert result.summary.present_count == 144
    assert result.summary.missing_count == 0
    assert result.summary.spot_present_count == 72
    assert result.summary.usd_m_present_count == 72
    assert result.summary.paired_present_month_count == 72
    assert result.summary.development_paired_month_count == 48
    assert result.summary.validation_paired_month_count == 24
    assert result.checksum_get_requests_made == 144
    assert all(record.http_status == 200 for record in result.records)
    assert result.archive_head_requests_made == 0
    assert result.archive_payload_requests_made == 0
    assert result.archive_payload_bytes == 0
    assert result.market_numeric_fields_inspected == ()
    assert result.parameters_defined == ()
    assert result.return_metrics_calculated == ()
    assert result.strategy_candidates_created == 0
    assert result.orders_submitted == 0


@pytest.mark.parametrize(
    ("script", "flag"),
    (
        ("scripts/freeze_periodic_flow_metadata_census_contract.py", "--check"),
        ("scripts/run_periodic_flow_metadata_census.py", "--check"),
        ("scripts/audit_periodic_flow_metadata_census.py", "--check"),
    ),
)
def test_q1_census_direct_check_commands_pass(script: str, flag: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, flag],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.startswith("PASS ")
