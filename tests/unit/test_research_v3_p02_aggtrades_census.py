from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
)
from aurex.backtest_engine.research_v3_p02_aggtrades_census import (
    V3_P02_CENSUS_PASS_DECISION,
    V3_P02_MONTHS,
    V3P02AggTradesCensusContract,
    V3P02AggTradesCensusRecord,
    V3P02AggTradesCensusResult,
    V3P02AggTradesTarget,
    archive_url,
    audit_v3_p02_census_contract,
    audit_v3_p02_census_result,
    authoritative_targets,
)
from scripts.freeze_v3_p02_aggtrades_census_contract import (
    DEFAULT_CHARTER,
    DEFAULT_REGISTER,
    authoritative_contract,
    load_inputs,
)
from scripts.run_v3_p02_aggtrades_census import (
    ChecksumHttpObservation,
    authoritative_result,
    fetch_census_record,
)

OBSERVED_AT = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def frozen_contract() -> V3P02AggTradesCensusContract:
    charter, register = load_inputs(DEFAULT_CHARTER, DEFAULT_REGISTER)
    return authoritative_contract(
        frozen_at=OBSERVED_AT,
        charter=charter,
        register=register,
    )


def observation(status: int, payload: bytes = b"") -> ChecksumHttpObservation:
    return ChecksumHttpObservation(
        status=status,
        payload=payload,
        checked_at=OBSERVED_AT,
    )


def checksum_payload(target: V3P02AggTradesTarget) -> bytes:
    archive_name = target.archive_url.rsplit("/", 1)[-1]
    return f"{'a' * 64}  {archive_name}\n".encode()


def synthetic_records(
    contract: V3P02AggTradesCensusContract,
    complete_symbol_count: int,
) -> list[V3P02AggTradesCensusRecord]:
    complete = set(V2_COMPLETE_SYMBOLS[:complete_symbol_count])
    records = []
    for target in contract.targets:
        is_present = target.symbol in complete
        records.append(
            V3P02AggTradesCensusRecord(
                symbol=target.symbol,
                month=target.month,
                archive_url=target.archive_url,
                checksum_url=target.checksum_url,
                checked_at=OBSERVED_AT,
                http_status=200 if is_present else 404,
                checksum_response_bytes=100 if is_present else 0,
                checksum_sha256="a" * 64 if is_present else None,
                availability="PRESENT" if is_present else "MISSING",
                request_attempt_count=1,
            )
        )
    return records


def test_v3p02_contract_freezes_exact_no_outcome_request_matrix() -> None:
    contract = frozen_contract()

    assert len(contract.targets) == 744
    assert len({target.key for target in contract.targets}) == 744
    assert {target.symbol for target in contract.targets} == set(
        V2_COMPLETE_SYMBOLS
    )
    assert {target.month for target in contract.targets} == set(V3_P02_MONTHS)
    assert contract.maximum_unique_checksum_urls == 744
    assert contract.maximum_http_attempts == 2232
    assert contract.maximum_concurrency == 4
    assert contract.minimum_complete_symbols == 10
    assert contract.archive_payload_requests_permitted is False
    assert contract.market_numeric_values_permitted is False
    assert contract.strategy_outcomes_permitted is False
    assert contract.selection_permitted is False
    assert audit_v3_p02_census_contract(contract)


def test_v3p02_target_refuses_non_authoritative_url() -> None:
    expected = archive_url("AAVEUSDT", "2023-01")
    with pytest.raises(
        ValidationError,
        match="aggregate-trade target changed",
    ):
        V3P02AggTradesTarget(
            symbol="AAVEUSDT",
            month="2023-01",
            archive_url=expected,
            checksum_url=(
                "https://example.com/data/futures/um/monthly/aggTrades/"
                "AAVEUSDT/AAVEUSDT-aggTrades-2023-01.zip.CHECKSUM"
            ),
        )


def test_v3p02_contract_refuses_threshold_or_request_budget_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["minimum_complete_symbols"] = 9
    payload["maximum_http_attempts"] = 2231

    with pytest.raises(ValidationError):
        V3P02AggTradesCensusContract.model_validate(payload)


def test_v3p02_authoritative_targets_are_stable_and_canonical() -> None:
    targets = authoritative_targets()

    assert targets == sorted(targets, key=lambda item: item.key)
    assert targets[0].key == (V2_COMPLETE_SYMBOLS[0], "2023-01")
    assert targets[-1].key == (V2_COMPLETE_SYMBOLS[-1], "2024-12")


def test_v3p02_fetch_parses_checksum_without_requesting_payload() -> None:
    contract = frozen_contract()
    target = contract.targets[0]
    calls = []

    def fetch(url: str, timeout: int, maximum_bytes: int):
        calls.append((url, timeout, maximum_bytes))
        return observation(200, checksum_payload(target))

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
    assert record.availability == "PRESENT"
    assert record.checksum_sha256 == "a" * 64
    assert record.request_attempt_count == 1


def test_v3p02_fetch_retries_only_within_frozen_budget() -> None:
    contract = frozen_contract()
    target = contract.targets[0]
    statuses = iter([503, 429, 404])
    sleeps = []

    record = fetch_census_record(
        target=target,
        contract=contract,
        fetch_once=lambda *_: observation(next(statuses)),
        sleep=sleeps.append,
    )

    assert record.availability == "MISSING"
    assert record.request_attempt_count == 3
    assert sleeps == [1, 3]


def test_v3p02_fetch_aborts_on_unexpected_http_status() -> None:
    contract = frozen_contract()

    with pytest.raises(RuntimeError, match="Unexpected HTTP 403"):
        fetch_census_record(
            target=contract.targets[0],
            contract=contract,
            fetch_once=lambda *_: observation(403),
        )


def test_v3p02_result_pass_only_permits_separate_pilot_protocol() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        records=synthetic_records(contract, complete_symbol_count=10),
    )

    assert result.decision == V3_P02_CENSUS_PASS_DECISION
    assert result.summary.complete_symbol_count == 10
    assert result.summary.http_attempt_count == 744
    assert result.authorizes_separate_pilot_protocol is True
    assert result.archive_payload_requests_made == 0
    assert result.market_numeric_values_inspected == []
    assert result.return_metrics_calculated == []
    assert result.selects_primary is False
    assert result.creates_candidate is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert audit_v3_p02_census_result(result)


def test_v3p02_result_refuses_decision_tampering() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        records=synthetic_records(contract, complete_symbol_count=10),
    )
    payload = result.model_dump()
    payload["authorizes_separate_pilot_protocol"] = False

    with pytest.raises(ValidationError, match="decision does not reconcile"):
        V3P02AggTradesCensusResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_v3_p02_aggtrades_census_contract.py",
        "scripts/run_v3_p02_aggtrades_census.py",
    ],
)
def test_v3p02_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
