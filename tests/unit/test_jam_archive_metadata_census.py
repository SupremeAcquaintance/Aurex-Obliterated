from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_archive_metadata_census import (
    JAM_ARCHIVE_CENSUS_FAIL_DECISION,
    JAM_ARCHIVE_CENSUS_MONTHS,
    JAM_ARCHIVE_CENSUS_NEXT_AUTHORIZATION,
    JAM_ARCHIVE_CENSUS_PASS_DECISION,
    JamArchiveMetadataCensusContract,
    JamArchiveMetadataCensusResult,
    JamArchiveMetadataRecord,
    JamArchiveMetadataTarget,
    audit_jam_archive_census_contract,
    audit_jam_archive_census_result,
    authoritative_targets,
)
from scripts.freeze_jam_archive_metadata_census_contract import (
    DEFAULT_CHARTER,
    authoritative_contract,
    load_charter,
)
from scripts.run_jam_archive_metadata_census import (
    ChecksumHttpObservation,
    RedirectRejectedError,
    RejectRedirectHandler,
    authoritative_result,
    fetch_census_record,
    load_checkpoint,
    write_checkpoint,
)

OBSERVED_AT = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


def frozen_contract() -> JamArchiveMetadataCensusContract:
    return authoritative_contract(
        frozen_at=OBSERVED_AT,
        charter=load_charter(DEFAULT_CHARTER),
    )


def checksum_payload(target: JamArchiveMetadataTarget) -> bytes:
    return f"{'a' * 64}  {target.archive_name}\n".encode()


def observation(
    target: JamArchiveMetadataTarget,
    status: int,
    payload: bytes = b"",
    *,
    final_url: str | None = None,
) -> ChecksumHttpObservation:
    return ChecksumHttpObservation(
        status=status,
        payload=payload,
        checked_at=OBSERVED_AT,
        final_url=final_url or target.checksum_url,
    )


def synthetic_record(
    target: JamArchiveMetadataTarget,
    *,
    present: bool = True,
    attempts: int = 1,
) -> JamArchiveMetadataRecord:
    payload = checksum_payload(target) if present else b""
    return JamArchiveMetadataRecord(
        family=target.family,
        month=target.month,
        archive_url=target.archive_url,
        checksum_url=target.checksum_url,
        final_url=target.checksum_url,
        checked_at=OBSERVED_AT,
        http_status=200 if present else 404,
        checksum_response_bytes=len(payload),
        checksum_text=payload.decode() if present else None,
        checksum_response_sha256=(
            hashlib.sha256(payload).hexdigest() if present else None
        ),
        published_archive_sha256="a" * 64 if present else None,
        availability="PRESENT" if present else "MISSING",
        request_attempt_count=attempts,
        redirect_count=0,
    )


def synthetic_records(
    contract: JamArchiveMetadataCensusContract,
    *,
    missing_key: tuple[str, str] | None = None,
) -> list[JamArchiveMetadataRecord]:
    return [
        synthetic_record(target, present=target.key != missing_key)
        for target in contract.targets
    ]


def test_contract_freezes_exact_metadata_only_request_matrix() -> None:
    contract = frozen_contract()

    assert len(contract.targets) == 96
    assert len({target.key for target in contract.targets}) == 96
    assert {target.symbol for target in contract.targets} == {"BTCUSDT"}
    assert {target.family for target in contract.targets} == {
        "aggTrades",
        "klines_1m",
    }
    assert {target.month for target in contract.targets} == set(
        JAM_ARCHIVE_CENSUS_MONTHS
    )
    assert contract.maximum_unique_checksum_urls == 96
    assert contract.maximum_http_attempts == 288
    assert contract.maximum_checksum_response_bytes == 4096
    assert contract.maximum_concurrency == 4
    assert contract.redirects_permitted is False
    assert contract.archive_head_requests_permitted is False
    assert contract.archive_payload_requests_permitted is False
    assert contract.market_numeric_values_permitted is False
    assert contract.return_calculation_permitted is False
    assert contract.strategy_execution_permitted is False
    assert audit_jam_archive_census_contract(contract)


def test_targets_are_stable_and_canonical() -> None:
    targets = authoritative_targets()

    assert targets == sorted(targets, key=lambda target: target.key)
    assert targets[0].key == ("aggTrades", "2019-01")
    assert targets[-1].key == ("klines_1m", "2022-12")
    assert all(target.checksum_url.endswith(".zip.CHECKSUM") for target in targets)


def test_target_refuses_non_authoritative_domain_or_path() -> None:
    target = authoritative_targets()[0]
    with pytest.raises(ValidationError, match="target changed"):
        JamArchiveMetadataTarget(
            family=target.family,
            month=target.month,
            archive_url=target.archive_url,
            checksum_url=target.checksum_url.replace(
                "data.binance.vision",
                "example.com",
            ),
        )


def test_contract_refuses_network_or_trading_authority_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["archive_payload_requests_permitted"] = True
    payload["creates_testnet_order_authority"] = True

    with pytest.raises(ValidationError):
        JamArchiveMetadataCensusContract.model_validate(payload)


def test_fetch_parses_checksum_without_requesting_archive() -> None:
    contract = frozen_contract()
    target = contract.targets[0]
    calls = []

    def fetch(url: str, timeout: int, maximum_bytes: int):
        calls.append((url, timeout, maximum_bytes))
        return observation(target, 200, checksum_payload(target))

    record = fetch_census_record(
        target=target,
        contract=contract,
        fetch_once=fetch,
    )

    assert calls == [
        (
            target.checksum_url,
            contract.request_timeout_seconds,
            contract.maximum_checksum_response_bytes,
        )
    ]
    assert target.archive_url not in {call[0] for call in calls}
    assert record.availability == "PRESENT"
    assert record.published_archive_sha256 == "a" * 64
    assert record.redirect_count == 0


def test_fetch_rejects_redirected_final_url_and_zip_bytes() -> None:
    contract = frozen_contract()
    target = contract.targets[0]

    with pytest.raises(RedirectRejectedError):
        fetch_census_record(
            target=target,
            contract=contract,
            fetch_once=lambda *_: observation(
                target,
                200,
                checksum_payload(target),
                final_url="https://example.com/file.zip.CHECKSUM",
            ),
        )

    with pytest.raises(ValueError, match="ZIP payload"):
        fetch_census_record(
            target=target,
            contract=contract,
            fetch_once=lambda *_: observation(
                target,
                200,
                b"PK\x03\x04archive bytes",
            ),
        )


def test_redirect_handler_fails_closed() -> None:
    handler = RejectRedirectHandler()

    with pytest.raises(RedirectRejectedError, match="rejected HTTP redirect"):
        handler.redirect_request(
            None,
            None,
            302,
            "Found",
            {},
            "https://data.binance.vision/redirected.zip.CHECKSUM",
        )


def test_fetch_retries_only_within_frozen_budget() -> None:
    contract = frozen_contract()
    target = contract.targets[0]
    statuses = iter([503, 429, 404])
    sleeps = []

    record = fetch_census_record(
        target=target,
        contract=contract,
        fetch_once=lambda *_: observation(target, next(statuses)),
        sleep=sleeps.append,
    )

    assert record.availability == "MISSING"
    assert record.request_attempt_count == 3
    assert sleeps == [1, 3]


def test_checkpoint_round_trip_and_lineage_guard(tmp_path: Path) -> None:
    contract = frozen_contract()
    checkpoint_path = tmp_path / "checkpoint.json"
    records = [synthetic_record(contract.targets[0])]

    checkpoint = write_checkpoint(
        path=checkpoint_path,
        contract=contract,
        records=records,
    )

    assert load_checkpoint(path=checkpoint_path, contract=contract) == records
    payload = checkpoint.model_dump()
    payload["archive_payload_requests_made"] = 1
    with pytest.raises(ValidationError):
        type(checkpoint).model_validate(payload)


def test_complete_result_passes_only_to_separate_authorization() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        records=synthetic_records(contract),
    )

    assert result.decision == JAM_ARCHIVE_CENSUS_PASS_DECISION
    assert (
        result.next_required_authorization
        == JAM_ARCHIVE_CENSUS_NEXT_AUTHORIZATION
    )
    assert result.summary.present_count == 96
    assert result.summary.complete is True
    assert result.archive_head_requests_made == 0
    assert result.archive_payload_requests_made == 0
    assert result.archive_payload_bytes_received == 0
    assert result.redirects_followed == 0
    assert result.market_numeric_values_inspected == []
    assert result.return_metrics_calculated == []
    assert result.creates_candidate is False
    assert result.creates_testnet_order_authority is False
    assert result.creates_live_eligibility is False
    assert audit_jam_archive_census_result(result)


def test_one_missing_target_stops_census() -> None:
    contract = frozen_contract()
    missing_key = contract.targets[0].key
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        records=synthetic_records(contract, missing_key=missing_key),
    )

    assert result.decision == JAM_ARCHIVE_CENSUS_FAIL_DECISION
    assert result.next_required_authorization == "NONE_CENSUS_FAILED"
    assert result.summary.present_count == 95
    assert result.summary.complete is False


def test_result_refuses_decision_or_payload_tampering() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        records=synthetic_records(contract),
    )
    payload = result.model_dump()
    payload["archive_payload_requests_made"] = 1
    payload["decision"] = JAM_ARCHIVE_CENSUS_FAIL_DECISION

    with pytest.raises(ValidationError):
        JamArchiveMetadataCensusResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_jam_archive_metadata_census_contract.py",
        "scripts/run_jam_archive_metadata_census.py",
        "scripts/audit_jam_archive_metadata_census.py",
    ],
)
def test_jam_archive_census_scripts_support_direct_invocation(
    script: str,
) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
