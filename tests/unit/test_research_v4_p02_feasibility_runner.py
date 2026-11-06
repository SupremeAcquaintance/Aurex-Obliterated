from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.research_v4_p02_feasibility_contract import (
    V4P02FeasibilityContract,
)
from aurex.backtest_engine.research_v4_p02_feasibility_runner import (
    V4P02HeaderObservation,
    V4P02TerminalResult,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.run_v4_p02_feasibility import (
    EvidenceIntegrityError,
    ResponseStream,
    append_durable_line,
    audit_terminal,
    execute_request,
    main,
    reconstruct_journal,
    run_feasibility,
    safe_project_path,
    validate_public_https_url,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    PROJECT_ROOT / "data/evidence/v4_p02_feasibility_contract_v1.json"
)
NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


class StepMonotonic:
    def __init__(self, step: float = 0.001):
        self.value = 0.0
        self.step = step

    def __call__(self) -> float:
        current = self.value
        self.value += self.step
        return current


class SyntheticTransport:
    def __init__(self, responses: dict[str, list[ResponseStream]]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    @contextmanager
    def open(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
    ) -> Iterator[ResponseStream]:
        del headers, connect_timeout_seconds, read_timeout_seconds
        self.calls.append((method, url))
        queue = self.responses.get(url, [])
        if not queue:
            raise AssertionError(f"Unexpected synthetic request: {method} {url}")
        yield queue.pop(0)


class CrashTransport:
    def __init__(self):
        self.calls = 0

    @contextmanager
    def open(self, **_kwargs) -> Iterator[ResponseStream]:
        self.calls += 1
        raise SystemExit("synthetic process death")
        yield  # pragma: no cover


def contract() -> V4P02FeasibilityContract:
    return V4P02FeasibilityContract.model_validate_json(
        CONTRACT_PATH.read_text(encoding="utf-8")
    )


def metadata_bytes(*, include_market_value: bool = False) -> bytes:
    payload = {
        "id": "deribit",
        "availableSince": "2020-01-01T00:00:00Z",
        "availableChannels": ["trades", "book", "ticker"],
        "incidentReports": [],
        "datasets": {
            "exportedUntil": "2026-07-01T00:00:00Z",
            "dataTypes": [
                "book_snapshot_25",
                "derivative_ticker",
                "liquidations",
                "options_chain",
                "quotes",
                "trades",
            ],
            "symbols": [
                {
                    "id": "BTC-PERPETUAL",
                    "availableSince": "2020-01-01T00:00:00Z",
                },
                {
                    "id": "OPTIONS",
                    "availableSince": "2020-01-01T00:00:00Z",
                },
            ],
        },
    }
    if include_market_value:
        payload["mark_price"] = 999_999
    return json.dumps(payload, separators=(",", ":")).encode()


def response(
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    chunks: list[bytes] | None = None,
) -> ResponseStream:
    return ResponseStream(
        status_code=status,
        headers=headers or {},
        chunks=iter(chunks or []),
    )


def successful_responses(
    frozen: V4P02FeasibilityContract,
    *,
    content_length: int = 10_000,
    include_market_value: bool = False,
) -> dict[str, list[ResponseStream]]:
    metadata = metadata_bytes(include_market_value=include_market_value)
    values = {
        frozen.requests[0].url: [
            response(
                headers={
                    "content-type": "application/json",
                    "content-length": str(len(metadata)),
                    "etag": "metadata-v1",
                },
                chunks=[metadata],
            )
        ]
    }
    for request in frozen.requests[1:]:
        values[request.url] = [
            response(
                headers={
                    "content-type": "application/gzip",
                    "content-length": str(content_length + request.sequence),
                    "etag": f"dataset-{request.sequence}",
                }
            )
        ]
    return values


def run_synthetic(
    tmp_path: Path,
    frozen: V4P02FeasibilityContract,
    transport,
    *,
    monotonic=None,
    host_validator=lambda _url: None,
):
    return run_feasibility(
        contract=frozen,
        project_root=tmp_path,
        transport=transport,
        host_validator=host_validator,
        clock=lambda: NOW,
        monotonic=monotonic or StepMonotonic(),
    )


def test_full_synthetic_census_rejects_without_payload_permission(
    tmp_path: Path,
) -> None:
    frozen = contract()
    transport = SyntheticTransport(successful_responses(frozen))

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "REJECT"
    assert result.resource_totals.attempts_used == 28
    assert result.resource_totals.responses_completed == 28
    assert result.resource_totals.failures_recorded == 0
    assert result.storage_projection is not None
    assert result.storage_projection.status == "PASS"
    assert result.authorizes_dataset_payload_gets is False
    assert result.authorizes_returns is False
    assert result.selects_primary is False
    assert len(transport.calls) == 28
    assert all(method == "HEAD" for method, _url in transport.calls[1:])
    audited = audit_terminal(contract=frozen, project_root=tmp_path)
    assert audited == result


def test_metadata_transport_failure_stops_after_one_attempt(
    tmp_path: Path,
) -> None:
    frozen = contract()
    transport = SyntheticTransport(
        {
            frozen.requests[0].url: [
                response(status=503, headers={"content-length": "0"})
            ]
        }
    )

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.resource_totals.attempts_used == 1
    assert result.resource_totals.failures_recorded == 1
    assert len(transport.calls) == 1


def test_three_safe_redirects_are_recorded_and_method_is_preserved(
    tmp_path: Path,
) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    request = frozen.requests[1]
    redirect_urls = [
        "https://cdn.example.com/a",
        "https://cdn.example.com/b",
        "https://cdn.example.com/c",
    ]
    responses[request.url] = [
        response(status=302, headers={"location": redirect_urls[0]})
    ]
    responses[redirect_urls[0]] = [
        response(status=307, headers={"location": redirect_urls[1]})
    ]
    responses[redirect_urls[1]] = [
        response(status=308, headers={"location": redirect_urls[2]})
    ]
    responses[redirect_urls[2]] = [
        response(
            headers={
                "content-length": "1234",
                "content-type": "application/gzip",
                "etag": "redirected",
            }
        )
    ]
    transport = SyntheticTransport(responses)

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "REJECT"
    assert result.resource_totals.http_hops_used == 31
    headers = V4P02HeaderObservation.model_validate_json(
        safe_project_path(
            tmp_path,
            frozen.header_observation_path,
        )
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert len(headers.redirect_chain) == 3
    assert all(
        method == "HEAD"
        for method, url in transport.calls
        if url in {request.url, *redirect_urls}
    )


@pytest.mark.parametrize(
    "target",
    [
        "http://public.example.com/file.csv.gz",
        "https://127.0.0.1/file.csv.gz",
        "https://169.254.1.1/file.csv.gz",
        "https://100.64.0.1/file.csv.gz",
        "https://user:secret@public.example.com/file.csv.gz",
    ],
)
def test_unsafe_redirect_target_stops_without_following(
    tmp_path: Path,
    target: str,
) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    request = frozen.requests[1]
    responses[request.url] = [
        response(status=302, headers={"location": target})
    ]
    transport = SyntheticTransport(responses)

    def validator(url: str) -> None:
        if url == target:
            validate_public_https_url(url)

    result = run_synthetic(
        tmp_path,
        frozen,
        transport,
        host_validator=validator,
    )

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.resource_totals.attempts_used == 2
    assert target not in [url for _method, url in transport.calls]


def test_fourth_redirect_stops_at_frozen_hop_budget(tmp_path: Path) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    request = frozen.requests[1]
    urls = [
        request.url,
        "https://cdn.example.com/1",
        "https://cdn.example.com/2",
        "https://cdn.example.com/3",
        "https://cdn.example.com/4",
    ]
    for current, target in zip(urls[:-1], urls[1:], strict=True):
        responses[current] = [
            response(status=302, headers={"location": target})
        ]
    transport = SyntheticTransport(responses)

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.resource_totals.http_hops_used == 5
    assert urls[-1] not in [url for _method, url in transport.calls]


def test_nonempty_head_body_is_terminal_transport_failure(
    tmp_path: Path,
) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    responses[frozen.requests[1].url] = [
        response(
            headers={"content-length": "1"},
            chunks=[b"x"],
        )
    ]
    transport = SyntheticTransport(responses)

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.failure_class_and_message["failure_class"] == "ValueError"
    assert "HEAD response contained body" in (
        result.failure_class_and_message["failure_message"]
    )


@pytest.mark.parametrize("declared", [None, "0", "not-a-number"])
def test_ambiguous_content_length_rejects_projection(
    tmp_path: Path,
    declared: str | None,
) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    headers = {"content-type": "application/gzip"}
    if declared is not None:
        headers["content-length"] = declared
    responses[frozen.requests[1].url] = [response(headers=headers)]

    result = run_synthetic(
        tmp_path,
        frozen,
        SyntheticTransport(responses),
    )

    assert result.terminal_kind == "REJECT"
    assert result.storage_projection is None
    gate = next(
        item
        for item in result.execution_gate_results
        if item.gate_id == "DATASET_IDENTITY_AND_GROUPED_OPTION_SCOPE"
    )
    assert gate.status == "FAIL"


def test_metadata_body_limit_is_enforced(tmp_path: Path) -> None:
    frozen = contract()
    oversized = b"x" * 8_388_609
    transport = SyntheticTransport(
        {
            frozen.requests[0].url: [
                response(
                    headers={"content-length": str(len(oversized))},
                    chunks=[oversized],
                )
            ]
        }
    )

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.resource_totals.attempts_used == 1
    assert result.resource_totals.response_body_bytes == 0
    assert "metadata body budget exceeded" in (
        result.failure_class_and_message["failure_message"]
    )


def test_metadata_gate_failure_prevents_every_head_request(
    tmp_path: Path,
) -> None:
    frozen = contract()
    payload = json.loads(metadata_bytes())
    payload["datasets"]["exportedUntil"] = "2024-01-01T00:00:00Z"
    raw = json.dumps(payload, separators=(",", ":")).encode()
    transport = SyntheticTransport(
        {
            frozen.requests[0].url: [
                response(
                    headers={
                        "content-type": "application/json",
                        "content-length": str(len(raw)),
                    },
                    chunks=[raw],
                )
            ]
        }
    )

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.terminal_kind == "REJECT"
    assert result.resource_totals.attempts_used == 1
    assert transport.calls == [("GET", frozen.requests[0].url)]
    assert result.metadata_gate_hash is not None


def test_stale_raw_metadata_is_rejected_before_intent(tmp_path: Path) -> None:
    frozen = contract()
    raw_path = (
        safe_project_path(tmp_path, frozen.journal_path).parent
        / "metadata_response_v1.body"
    )
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(b"stale")
    transport = SyntheticTransport({})

    with pytest.raises(
        EvidenceIntegrityError,
        match="raw metadata has no durable response",
    ):
        run_synthetic(tmp_path, frozen, transport)

    assert transport.calls == []
    assert not safe_project_path(tmp_path, frozen.journal_path).exists()


def test_logical_timeout_is_terminal_without_transport_call(
    tmp_path: Path,
) -> None:
    frozen = contract()
    transport = SyntheticTransport({})
    monotonic = iter([0.0, 46.0, 46.0])

    result = run_synthetic(
        tmp_path,
        frozen,
        transport,
        monotonic=lambda: next(monotonic),
    )

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.failure_class_and_message["failure_class"] == "TimeoutError"
    assert transport.calls == []


def test_process_death_is_closed_on_restart_without_retry(
    tmp_path: Path,
) -> None:
    frozen = contract()
    crashing = CrashTransport()

    with pytest.raises(SystemExit, match="process death"):
        run_synthetic(tmp_path, frozen, crashing)

    replacement = SyntheticTransport({})
    result = run_synthetic(tmp_path, frozen, replacement)

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert result.resource_totals.attempts_used == 1
    assert result.failure_class_and_message["failure_class"] == (
        "UnreconciledRequestIntent"
    )
    assert replacement.calls == []


def test_restart_reconstructs_missing_metadata_observation(
    tmp_path: Path,
) -> None:
    frozen = contract()
    responses = successful_responses(frozen)
    metadata_transport = SyntheticTransport(
        {frozen.requests[0].url: responses.pop(frozen.requests[0].url)}
    )
    journal_path = safe_project_path(tmp_path, frozen.journal_path)
    records = []
    outcome = execute_request(
        contract=frozen,
        request=frozen.requests[0],
        project_root=tmp_path,
        journal_path=journal_path,
        records=records,
        transport=metadata_transport,
        host_validator=lambda _url: None,
        clock=lambda: NOW,
        monotonic=StepMonotonic(),
    )
    assert outcome.record_type == "RESPONSE"
    metadata_path = safe_project_path(
        tmp_path,
        frozen.metadata_observation_path,
    )
    assert not metadata_path.exists()

    result = run_synthetic(
        tmp_path,
        frozen,
        SyntheticTransport(responses),
    )

    assert result.resource_totals.attempts_used == 28
    assert metadata_path.exists()


def test_storage_ceiling_failure_is_deterministic(tmp_path: Path) -> None:
    frozen = contract()
    transport = SyntheticTransport(
        successful_responses(frozen, content_length=400_000_000)
    )

    result = run_synthetic(tmp_path, frozen, transport)

    assert result.storage_projection is not None
    assert result.storage_projection.status == "FAIL"
    assert (
        result.storage_projection.total_projected_storage_bytes
        > result.storage_projection.ceiling_bytes
    )


def test_observations_do_not_persist_market_numeric_fields(
    tmp_path: Path,
) -> None:
    frozen = contract()
    result = run_synthetic(
        tmp_path,
        frozen,
        SyntheticTransport(
            successful_responses(frozen, include_market_value=True)
        ),
    )
    assert result.terminal_kind == "REJECT"
    metadata_text = safe_project_path(
        tmp_path,
        frozen.metadata_observation_path,
    ).read_text(encoding="utf-8")
    header_text = safe_project_path(
        tmp_path,
        frozen.header_observation_path,
    ).read_text(encoding="utf-8")
    assert "mark_price" not in metadata_text
    assert "999999" not in metadata_text
    assert "mark_price" not in header_text


def test_tampered_journal_is_rejected(tmp_path: Path) -> None:
    frozen = contract()
    result = run_synthetic(
        tmp_path,
        frozen,
        SyntheticTransport(successful_responses(frozen)),
    )
    assert result.terminal_kind == "REJECT"
    journal_path = safe_project_path(tmp_path, frozen.journal_path)
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["request_sequence"] = 2
    lines[0] = json.dumps(first, separators=(",", ":"))
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceIntegrityError, match="Invalid V4P02 NDJSON"):
        reconstruct_journal(frozen, journal_path)


def test_duplicate_intent_is_rejected(tmp_path: Path) -> None:
    frozen = contract()
    transport = CrashTransport()
    with pytest.raises(SystemExit):
        run_synthetic(tmp_path, frozen, transport)
    journal_path = safe_project_path(tmp_path, frozen.journal_path)
    first = json.loads(journal_path.read_text(encoding="utf-8").splitlines()[0])
    first["record_sequence"] = 2
    first["previous_record_hash"] = first["record_evidence_hash"]
    first.pop("record_evidence_hash")
    first["recorded_at"] = datetime.fromisoformat(
        first["recorded_at"].replace("Z", "+00:00")
    )
    from aurex.backtest_engine.research_v4_p02_feasibility_runner import (
        build_v4_p02_journal_record,
    )

    duplicate = build_v4_p02_journal_record(**first)
    append_durable_line(journal_path, duplicate.model_dump(mode="json"))

    with pytest.raises(
        EvidenceIntegrityError,
        match="Duplicate, overlapping, or out-of-order",
    ):
        reconstruct_journal(frozen, journal_path)


def test_terminal_model_rejects_forged_empty_permission_boundary(
    tmp_path: Path,
) -> None:
    frozen = contract()
    result = run_synthetic(
        tmp_path,
        frozen,
        SyntheticTransport(successful_responses(frozen)),
    )
    payload = result.model_dump(mode="json")
    payload["selection_and_permission_boundary"] = {}
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )

    with pytest.raises(ValueError, match="permission boundary changed"):
        V4P02TerminalResult.model_validate(payload)


def test_cli_dry_run_is_explicitly_non_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_v4_p02_feasibility.py", "--dry-run"],
    )

    assert main() == 0
    output = capsys.readouterr().out
    assert "V4P02 DRY RUN" in output
    assert "requests=28" in output
    assert "payload_gets=PROHIBITED" in output
    assert "values=PROHIBITED" in output
