import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_source_census import (
    V2_CENSUS_FAIL_DECISION,
    V2_CENSUS_PASS_DECISION,
    V2SourceCensusRecord,
    V2SourceCensusResult,
    audit_v2_source_census_result,
    build_v2_source_census_result,
    parse_v2_checksum_text,
    render_v2_source_census_targets,
)
from aurex.backtest_engine.research_v2_source_census_contract import (
    V2SourceCensusContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts import run_v2_source_census as census_script
from scripts.run_v2_source_census import (
    ChecksumHttpObservation,
    fetch_census_record,
)

CONTRACT_PATH = Path(
    "data/evidence/v2_derivatives_source_census_contract_v1.json"
)
CHECKED_AT = datetime(2026, 7, 27, 17, tzinfo=UTC)
RUNNER_HASH = "a" * 64
CHECKSUM = "b" * 64


@pytest.fixture(scope="module")
def contract() -> V2SourceCensusContract:
    return V2SourceCensusContract.model_validate_json(
        CONTRACT_PATH.read_text(encoding="utf-8")
    )


def records_with_complete_symbol_count(
    contract: V2SourceCensusContract,
    complete_symbol_count: int,
) -> list[V2SourceCensusRecord]:
    complete_symbols = set(contract.symbols[:complete_symbol_count])
    records = []
    for target in render_v2_source_census_targets(contract):
        if target.symbol in complete_symbols:
            records.append(
                V2SourceCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    family_id=target.family_id,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=CHECKED_AT,
                    checksum_http_status=200,
                    checksum_text=f"{CHECKSUM}  {target.archive_name}",
                    checksum_sha256=CHECKSUM,
                )
            )
        else:
            records.append(
                V2SourceCensusRecord(
                    symbol=target.symbol,
                    month=target.month,
                    family_id=target.family_id,
                    archive_url=target.archive_url,
                    checksum_url=target.checksum_url,
                    checked_at=CHECKED_AT,
                    checksum_http_status=404,
                )
            )
    return records


def build_result(
    contract: V2SourceCensusContract,
    complete_symbol_count: int,
):
    return build_v2_source_census_result(
        generated_at=CHECKED_AT,
        contract=contract,
        runner_contract_hash=RUNNER_HASH,
        records=records_with_complete_symbol_count(
            contract,
            complete_symbol_count,
        ),
        limitations=[
            "Metadata-only test evidence.",
            "No payloads.",
            "No returns.",
            "No eligibility.",
        ],
    )


def test_v2_census_target_matrix_is_exact_and_canonical(
    contract: V2SourceCensusContract,
) -> None:
    targets = render_v2_source_census_targets(contract)

    assert len(targets) == 5040
    assert len({target.key for target in targets}) == 5040
    assert targets[0].key == ("AAVEUSDT", "2023-01", "spot_klines_1m")
    assert targets[0].checksum_url == (
        "https://data.binance.vision/data/spot/monthly/klines/"
        "AAVEUSDT/1m/AAVEUSDT-1m-2023-01.zip.CHECKSUM"
    )
    assert targets[-1].key == (
        "XRPUSDT",
        "2024-12",
        "um_premium_index_klines_1m",
    )
    assert targets[-1].checksum_url == (
        "https://data.binance.vision/data/futures/um/monthly/"
        "premiumIndexKlines/XRPUSDT/1m/XRPUSDT-1m-2024-12.zip.CHECKSUM"
    )


def test_v2_checksum_parser_is_exact() -> None:
    archive_name = "BTCUSDT-1m-2024-12.zip"

    assert (
        parse_v2_checksum_text(f"{CHECKSUM}  {archive_name}\n", archive_name)
        == CHECKSUM
    )
    assert (
        parse_v2_checksum_text(f"{CHECKSUM} *{archive_name}", archive_name)
        == CHECKSUM
    )
    with pytest.raises(ValueError, match="Malformed"):
        parse_v2_checksum_text(f"{CHECKSUM}  ETHUSDT-1m-2024-12.zip", archive_name)
    with pytest.raises(ValueError, match="Malformed"):
        parse_v2_checksum_text(f"{'z' * 64}  {archive_name}", archive_name)
    with pytest.raises(ValueError, match="exceeds"):
        parse_v2_checksum_text("x" * 4097, archive_name)


def test_v2_fetch_preserves_404_without_retry(
    contract: V2SourceCensusContract,
) -> None:
    calls = []
    target = render_v2_source_census_targets(contract)[0]

    def fetch_once(url: str, timeout: int) -> ChecksumHttpObservation:
        calls.append((url, timeout))
        return ChecksumHttpObservation(404, b"", CHECKED_AT)

    record = fetch_census_record(
        target=target,
        contract=contract,
        fetch_once=fetch_once,
        sleep=lambda _delay: pytest.fail("404 must not retry"),
    )

    assert len(calls) == 1
    assert record.checksum_http_status == 404
    assert record.checksum_sha256 is None


def test_v2_fetch_retries_transient_response_then_accepts_checksum(
    contract: V2SourceCensusContract,
) -> None:
    target = render_v2_source_census_targets(contract)[0]
    responses = [
        ChecksumHttpObservation(429, b"", CHECKED_AT),
        ChecksumHttpObservation(
            200,
            f"{CHECKSUM}  {target.archive_name}\n".encode(),
            CHECKED_AT,
        ),
    ]
    sleeps = []

    record = fetch_census_record(
        target=target,
        contract=contract,
        fetch_once=lambda _url, _timeout: responses.pop(0),
        sleep=sleeps.append,
    )

    assert record.checksum_http_status == 200
    assert record.checksum_sha256 == CHECKSUM
    assert sleeps == [1]


def test_v2_fetch_refuses_to_turn_exhausted_server_error_into_missing(
    contract: V2SourceCensusContract,
) -> None:
    target = render_v2_source_census_targets(contract)[0]
    sleeps = []

    with pytest.raises(RuntimeError, match="unresolved after 3 attempts"):
        fetch_census_record(
            target=target,
            contract=contract,
            fetch_once=lambda _url, _timeout: ChecksumHttpObservation(
                503,
                b"",
                CHECKED_AT,
            ),
            sleep=sleeps.append,
        )

    assert sleeps == [1, 3]


@pytest.mark.parametrize(
    ("complete_symbol_count", "expected_decision"),
    [
        (19, V2_CENSUS_FAIL_DECISION),
        (20, V2_CENSUS_PASS_DECISION),
    ],
)
def test_v2_census_decision_uses_exact_twenty_symbol_boundary(
    contract: V2SourceCensusContract,
    complete_symbol_count: int,
    expected_decision: str,
) -> None:
    result = build_result(contract, complete_symbol_count)

    assert result.summary.complete_symbol_count == complete_symbol_count
    assert result.decision == expected_decision
    assert result.summary.present_observations == complete_symbol_count * 24 * 6
    assert result.archive_payload_request_count == 0
    assert result.authorizes_market_data_import is False
    assert (
        audit_v2_source_census_result(
            result=result,
            contract=contract,
            current_runner_contract_hash=RUNNER_HASH,
        )["status"]
        == "PASS"
    )


def test_v2_census_refuses_rehashed_decision_tampering(
    contract: V2SourceCensusContract,
) -> None:
    result = build_result(contract, 20)
    payload = result.model_dump()
    payload["decision"] = V2_CENSUS_FAIL_DECISION
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )

    with pytest.raises(ValidationError, match="does not follow its threshold"):
        V2SourceCensusResult.model_validate(payload)


def test_v2_census_failure_leaves_no_result_file(
    contract: V2SourceCensusContract,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "census.json"

    class Args:
        contract = CONTRACT_PATH
        workers = 1

    args = Args()
    args.output = output
    monkeypatch.setattr(census_script, "load_contract", lambda _path: contract)

    def fail_collection(**_kwargs):
        raise RuntimeError("unresolved observation")

    monkeypatch.setattr(
        census_script,
        "collect_census_records",
        fail_collection,
    )

    with pytest.raises(RuntimeError, match="unresolved observation"):
        census_script.run_census(args)

    assert not output.exists()
    assert not output.with_name(f"{output.name}.part").exists()


def test_v2_census_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v2_source_census.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
