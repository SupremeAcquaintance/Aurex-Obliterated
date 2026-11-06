from __future__ import annotations

import json
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.research_v4_p01_feasibility_runner import (
    EMPTY_SHA256,
    V4P01JournalRecord,
    V4P01SourceObservation,
)
from scripts.run_v4_p01_feasibility import (
    EvidenceIntegrityError,
    ResponseStream,
    audit_terminal,
    execute_request,
    load_contract,
    load_ndjson,
    reconstruct_journal,
    run_feasibility,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = PROJECT_ROOT / "data" / "evidence"
FIXED_NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


def frozen_contract():
    return load_contract(
        charter_path=EVIDENCE / "v4_mechanism_discovery_charter_v1.json",
        register_path=EVIDENCE / "v4_mechanism_proposal_register_v1.json",
        contract_path=EVIDENCE / "v4_p01_feasibility_contract_v1.json",
    )


def metadata_payload(exchange_id: str) -> bytes:
    product_id = "ethbtc" if exchange_id == "binance" else "ETH-BTC"
    return json.dumps(
        {
            "id": exchange_id,
            "availableSince": "2020-01-01T00:00:00Z",
            "availableTo": "2026-01-01T00:00:00Z",
            "version": "synthetic-v1",
            "datasets": {
                "symbols": [
                    {
                        "id": product_id,
                        "availableSince": "2020-01-01T00:00:00Z",
                        "availableTo": "2026-01-01T00:00:00Z",
                        "dataTypes": [
                            "bookTicker",
                            "depth",
                            "depthSnapshot",
                            "l2update",
                            "snapshot",
                        ],
                    }
                ]
            },
            "incidentReports": [],
        },
        separators=(",", ":"),
    ).encode()


def payload_capture(exchange_id: str, sample_at: datetime) -> bytes:
    local = sample_at.isoformat().replace("+00:00", "Z")
    milliseconds = int(sample_at.timestamp() * 1000)
    if exchange_id == "binance":
        messages = [
            {
                "stream": "ethbtc@bookTicker",
                "data": {
                    "e": "bookTicker",
                    "E": milliseconds,
                    "s": "ethbtc",
                    "u": 1,
                    "b": "0.050",
                    "B": "8.0",
                    "a": "0.051",
                    "A": "7.0",
                },
            },
            {
                "stream": "ethbtc@depth",
                "data": {
                    "e": "depthUpdate",
                    "E": milliseconds + 1,
                    "s": "ethbtc",
                    "U": 1,
                    "u": 2,
                    "b": [["0.050", "8.0"]],
                    "a": [["0.051", "7.0"]],
                },
            },
            {
                "type": "depthSnapshot",
                "symbol": "ethbtc",
                "timestamp": milliseconds + 2,
                "lastUpdateId": 2,
                "bids": [["0.050", "8.0"]],
                "asks": [["0.051", "7.0"]],
            },
        ]
    else:
        messages = [
            {
                "type": "l2update",
                "product_id": "ETH-BTC",
                "time": sample_at.isoformat(),
                "changes": [["buy", "0.050", "8.0"]],
                "sequence": 1,
            },
            {
                "type": "snapshot",
                "product_id": "ETH-BTC",
                "timestamp": sample_at.isoformat(),
                "bids": [["0.050", "8.0"]],
                "asks": [["0.051", "7.0"]],
            },
        ]
    return (
        "\n".join(
            f"{local} {json.dumps(message, separators=(',', ':'))}"
            for message in messages
        )
        + "\n"
    ).encode()


class FakeTransport:
    def __init__(
        self,
        *,
        missing_product_exchange: str | None = None,
        fail_request_id: str | None = None,
        oversized_request_id: str | None = None,
    ):
        self.missing_product_exchange = missing_product_exchange
        self.fail_request_id = fail_request_id
        self.oversized_request_id = oversized_request_id
        self.calls: list[str] = []

    @contextmanager
    def open(self, request):
        self.calls.append(request.request_id)
        if request.phase == "METADATA_CENSUS":
            body = metadata_payload(request.exchange_id)
            if request.exchange_id == self.missing_product_exchange:
                body = body.replace(
                    request.exchange_id.encode(),
                    b"unrelated",
                ).replace(
                    ("ethbtc" if request.exchange_id == "binance" else "ETH-BTC").encode(),
                    b"NOT-ETH-BTC",
                )
        else:
            body = payload_capture(request.exchange_id, request.sample_at)
        if request.request_id == self.oversized_request_id:
            body = b"x" * (request.maximum_response_bytes + 1)

        def chunks():
            if request.request_id == self.fail_request_id:
                yield body[:17]
                raise TimeoutError("synthetic read inactivity timeout")
            yield body

        yield ResponseStream(
            status_code=200,
            headers={
                "content-type": "application/json",
                "content-length": str(len(body)),
                "etag": f'"{request.request_id}-synthetic"',
            },
            chunks=chunks(),
        )


class CrashTransport:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def open(self, request):
        self.calls += 1
        raise KeyboardInterrupt("synthetic process death")
        yield  # pragma: no cover


def test_v4p01_runner_completes_all_source_requests_but_rejects_hard_gates(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    transport = FakeTransport()

    result = run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "REJECT"
    assert result.decision == "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    assert transport.calls == [item.request_id for item in contract.requests]
    assert result.resource_totals.attempts_used == 8
    assert result.resource_totals.responses_completed == 8
    assert result.resource_totals.failures_recorded == 0
    assert result.selects_primary is False
    assert result.authorizes_returns is False
    statuses = {
        item.gate_id: item.status for item in result.execution_gate_results
    }
    assert statuses["COMMON_ETH_BTC_PRODUCT_IDENTITY"] == "PASS"
    assert statuses["RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES"] == "PASS"
    assert statuses["POINT_IN_TIME_FEES_AND_FEE_CURRENCY"] == "FAIL"
    assert statuses["POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE"] == "FAIL"

    journal = load_ndjson(
        tmp_path / contract.journal_path,
        V4P01JournalRecord,
    )
    assert len(journal) == 16
    assert [item.record_type for item in journal] == [
        value
        for _ in range(8)
        for value in ("REQUEST_INTENT", "RESPONSE")
    ]
    for previous, current in zip(journal, journal[1:], strict=False):
        assert current.previous_record_hash == previous.record_evidence_hash


def test_v4p01_runner_never_persists_market_values_in_observations(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=FakeTransport(),
        clock=lambda: FIXED_NOW,
    )

    observation_text = (
        tmp_path / contract.payload_observation_path
    ).read_text(encoding="utf-8")
    assert "0.050" not in observation_text
    assert "0.051" not in observation_text
    assert '"profit' not in observation_text
    assert '"return' not in observation_text
    observations = load_ndjson(
        tmp_path / contract.payload_observation_path,
        V4P01SourceObservation,
    )
    assert len(observations) == 6
    assert all(not item.missing_required_schema_keys for item in observations)


def test_v4p01_metadata_failure_blocks_all_payload_requests(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    transport = FakeTransport(missing_product_exchange="coinbase")

    result = run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "REJECT"
    assert transport.calls == [
        contract.requests[0].request_id,
        contract.requests[1].request_id,
    ]
    assert result.resource_totals.attempts_used == 2
    assert result.metadata_and_payload_observation_hashes["payload"] == []
    common_gate = next(
        item
        for item in result.execution_gate_results
        if item.gate_id == "COMMON_ETH_BTC_PRODUCT_IDENTITY"
    )
    assert common_gate.status == "FAIL"


def test_v4p01_transport_failure_preserves_partial_hash_and_never_retries(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    failed_id = contract.requests[0].request_id
    transport = FakeTransport(fail_request_id=failed_id)

    result = run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert transport.calls == [failed_id]
    assert result.resource_totals.attempts_used == 1
    assert result.resource_totals.failures_recorded == 1
    assert result.partial_byte_count_and_sha256["byte_count"] == 17
    assert (
        result.partial_byte_count_and_sha256["payload_sha256"]
        != EMPTY_SHA256
    )
    assert not list(
        (tmp_path / contract.raw_payload_directory).glob("*.part")
    )
    journal = load_ndjson(
        tmp_path / contract.journal_path,
        V4P01JournalRecord,
    )
    assert [item.record_type for item in journal] == [
        "REQUEST_INTENT",
        "FAILURE",
    ]


def test_v4p01_byte_budget_is_hard_and_consumes_the_only_attempt(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    request = contract.requests[0]
    records = []
    journal_path = tmp_path / contract.journal_path

    result = execute_request(
        contract=contract,
        request=request,
        project_root=tmp_path,
        journal_path=journal_path,
        records=records,
        transport=FakeTransport(oversized_request_id=request.request_id),
        clock=lambda: FIXED_NOW,
        monotonic=time.monotonic,
    )

    assert result.record_type == "FAILURE"
    assert result.failure_class == "ValueError"
    assert result.failure_message == "response byte budget exceeded"
    assert result.byte_count == 0
    assert result.payload_sha256 == EMPTY_SHA256
    assert len(records) == 2
    with pytest.raises(EvidenceIntegrityError, match="already consumed"):
        execute_request(
            contract=contract,
            request=request,
            project_root=tmp_path,
            journal_path=journal_path,
            records=records,
            transport=FakeTransport(),
            clock=lambda: FIXED_NOW,
            monotonic=time.monotonic,
        )


def test_v4p01_process_death_closes_intent_without_retry_on_restart(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    request = contract.requests[0]
    records = []
    journal_path = tmp_path / contract.journal_path
    transport = CrashTransport()

    with pytest.raises(KeyboardInterrupt, match="process death"):
        execute_request(
            contract=contract,
            request=request,
            project_root=tmp_path,
            journal_path=journal_path,
            records=records,
            transport=transport,
            clock=lambda: FIXED_NOW,
            monotonic=time.monotonic,
        )

    stored = reconstruct_journal(contract, journal_path)
    assert len(stored) == 1
    assert stored[0].record_type == "REQUEST_INTENT"
    part_files = list(
        (tmp_path / contract.raw_payload_directory).glob("*.part")
    )
    assert len(part_files) == 1
    result = run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )
    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.failure_class_and_message["failure_class"] == (
        "UnreconciledRequestIntent"
    )
    assert result.partial_byte_count_and_sha256["byte_count"] == 0
    assert not part_files[0].exists()
    stored = reconstruct_journal(contract, journal_path)
    assert [item.record_type for item in stored] == [
        "REQUEST_INTENT",
        "FAILURE",
    ]
    assert transport.calls == 1


def test_v4p01_restart_between_requests_rebuilds_missing_observation(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    transport = FakeTransport()
    records = []

    first_response = execute_request(
        contract=contract,
        request=contract.requests[0],
        project_root=tmp_path,
        journal_path=tmp_path / contract.journal_path,
        records=records,
        transport=transport,
        clock=lambda: FIXED_NOW,
        monotonic=time.monotonic,
    )
    assert first_response.record_type == "RESPONSE"
    assert not (tmp_path / contract.metadata_observation_path).exists()

    result = run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "REJECT"
    assert len(transport.calls) == 8
    observations = load_ndjson(
        tmp_path / contract.metadata_observation_path,
        V4P01SourceObservation,
    )
    assert observations[0].request_id == contract.requests[0].request_id


def test_v4p01_terminal_audit_detects_journal_tampering(
    tmp_path: Path,
) -> None:
    contract = frozen_contract()
    run_feasibility(
        contract=contract,
        project_root=tmp_path,
        transport=FakeTransport(),
        clock=lambda: FIXED_NOW,
    )
    assert audit_terminal(contract=contract, project_root=tmp_path)
    journal_path = tmp_path / contract.journal_path
    text = journal_path.read_text(encoding="utf-8")
    journal_path.write_text(
        text.replace(
            contract.requests[0].request_id,
            "V4P01_META_TAMPERED_EXCHANGE_DETAILS",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvidenceIntegrityError, match="Invalid V4P01 NDJSON"):
        audit_terminal(contract=contract, project_root=tmp_path)


def test_v4p01_runner_cli_requires_explicit_non_network_mode() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_p01_feasibility.py",
            "--dry-run",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "requests=8 retries=0 values=PROHIBITED" in completed.stdout
    assert "V4P01_PILOT_COINBASE_20241201_2359" in completed.stdout
