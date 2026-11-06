from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from scripts import freeze_s5_bitcoin_core_github_bulk_response_amendment_v2 as amendment_script
from scripts.audit_s5_bitcoin_core_github_bulk_failure import (
    DEFAULT_FAILURE,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
)
from scripts.audit_s5_bitcoin_core_github_bulk_failure import (
    build_audit as build_failure_audit,
)
from scripts.run_s5_bitcoin_core_github_bulk_acquisition_v2 import capture_streamed_response


def test_bulk_failure_audit_proves_zero_response_capture() -> None:
    audit = build_failure_audit(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        result_path=DEFAULT_RESULT,
        failure_path=DEFAULT_FAILURE,
        audited_at=datetime(2026, 9, 2, 22, 0, tzinfo=UTC),
    )

    assert audit.request_attempt_count == 1
    assert audit.response_body_bytes_captured == 0
    assert audit.metadata_records_parsed == 0
    assert audit.original_stop_preserved is True
    assert audit.page_one_replay_required is True


def test_bulk_amendment_changes_only_response_handling(tmp_path: Path, monkeypatch) -> None:
    failure_audit = build_failure_audit(
        protocol_path=DEFAULT_PROTOCOL,
        protocol_audit_path=DEFAULT_PROTOCOL_AUDIT,
        result_path=DEFAULT_RESULT,
        failure_path=DEFAULT_FAILURE,
        audited_at=datetime(2026, 9, 2, 22, 0, tzinfo=UTC),
    )
    path = tmp_path / "failure_audit.json"
    path.write_text(failure_audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(amendment_script, "FAILURE_AUDIT_PATH", path)
    amendment = amendment_script.build_amendment(frozen_at=datetime(2026, 9, 2, 22, 1, tzinfo=UTC))

    assert amendment.query_scope_unchanged is True
    assert amendment.headers_unchanged is True
    assert amendment.page_one_maximum_total_attempts_after_replay == 2
    assert amendment.maximum_total_request_attempts_including_prior_failure == 300
    assert amendment.maximum_corrected_run_attempts == 299
    assert amendment.orders_permitted is False


def test_corrected_stream_reader_captures_bounded_response(protocol=None) -> None:
    from scripts.freeze_s5_bitcoin_core_github_bulk_acquisition import build_protocol

    frozen = build_protocol(frozen_at=datetime(2026, 9, 2, 22, 2, tzinfo=UTC))
    request = httpx.Request("GET", "https://api.github.com/example")
    response = httpx.Response(
        200,
        request=request,
        headers={
            "content-type": "application/json",
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1788307200",
            "x-ratelimit-resource": "core",
        },
        content=b"[]",
    )
    headers, body = capture_streamed_response(response, protocol=frozen)

    assert headers["content-type"] == "application/json"
    assert headers["x-ratelimit-limit"] == "60"
    assert body == b"[]"
