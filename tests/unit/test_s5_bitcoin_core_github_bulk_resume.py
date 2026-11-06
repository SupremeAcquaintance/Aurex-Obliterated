from __future__ import annotations

from datetime import UTC, datetime

from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5GitHubBulkSuspensionFailureAuditV2,
    evidence_hash_valid,
)
from scripts import freeze_s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3 as resume
from scripts.audit_s5_bitcoin_core_github_bulk_suspension_failure_v2 import (
    DEFAULT_OUTPUT,
)


def test_suspension_audit_preserves_contiguous_prefix() -> None:
    audit = S5GitHubBulkSuspensionFailureAuditV2.model_validate_json(
        DEFAULT_OUTPUT.read_text(encoding="utf-8")
    )

    assert evidence_hash_valid(audit, "audit_evidence_hash")
    assert audit.successful_page_count == 117
    assert audit.raw_record_count == 11_700
    assert audit.next_required_page == 118
    assert audit.page_118_request_attempted is False
    assert audit.remaining_request_attempt_capacity == 182


def test_resume_amendment_retains_original_cohort_and_budget() -> None:
    amendment = resume.build_amendment(frozen_at=datetime(2026, 9, 3, 14, 1, tzinfo=UTC))

    assert amendment.preserved_page_last == 117
    assert amendment.resume_page == 118
    assert amendment.terminal_page == 244
    assert amendment.maximum_resume_request_attempts == 182
    assert amendment.minimum_requests_required_to_terminal_page == 127
    assert amendment.cohort_cutoff_unchanged is True
    assert amendment.orders_permitted is False
