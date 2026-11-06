from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (
    S5GitHubPreflightInterpreterAmendmentV2,
)
from scripts.audit_s5_bitcoin_core_github_preflight_failure import build_failure_audit
from scripts.run_s5_bitcoin_core_github_preflight_local_revalidation_v2 import (
    AMENDMENT_PATH,
    TRANSCRIPT_PATH,
    build_result,
    parse_corrected_link,
)


def amendment() -> S5GitHubPreflightInterpreterAmendmentV2:
    return S5GitHubPreflightInterpreterAmendmentV2.model_validate_json(
        AMENDMENT_PATH.read_text(encoding="utf-8")
    )


def test_failure_audit_classifies_transport_success_without_replay() -> None:
    audit = build_failure_audit(audited_at=datetime(2026, 9, 2, tzinfo=UTC))

    assert audit.transport_succeeded is True
    assert audit.interpreter_rejected_source_compatible_response is True
    assert audit.canonical_repository_id == 1_181_927
    assert audit.observed_link_path == "/repositories/1181927/pulls"
    assert audit.merge_commit_sha_key_present is False
    assert audit.head_sha_key_present is True
    assert audit.additional_request_count == 0


def test_corrected_link_accepts_only_bound_canonical_repository_path() -> None:
    transcript = json.loads(Path(TRANSCRIPT_PATH).read_text(encoding="utf-8"))
    link = transcript["response"]["headers"]["link"]
    path, count = parse_corrected_link(link=link, amendment=amendment())

    assert path == "/repositories/1181927/pulls"
    assert count == 24_012

    changed = link.replace("repositories/1181927", "repositories/1181928")
    with pytest.raises(ValueError, match="scope changed"):
        parse_corrected_link(link=changed, amendment=amendment())


def test_corrected_result_uses_preserved_response_and_zero_new_requests() -> None:
    result = build_result(corrected_at=datetime(2026, 9, 2, tzinfo=UTC))

    assert result.passed_gate_count == 14
    assert result.failed_gate_count == 0
    assert result.first_pull_number == 9
    assert result.first_pull_merged_at is None
    assert len(result.first_pull_head_sha) == 40
    assert result.merge_commit_sha_key_present is False
    assert result.terminal_record_count == 24_012
    assert result.bulk_request_page_count_at_100 == 241
    assert result.bulk_unauthenticated_hours_lower_bound == 5
    assert result.original_request_attempt_count == 1
    assert result.additional_network_request_count == 0
    assert result.authorizes_bulk_acquisition_protocol_design is True
    assert result.authorizes_bulk_metadata_acquisition_now is False
