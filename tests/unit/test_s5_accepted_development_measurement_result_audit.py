from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s5_accepted_development_measurement_result_audit import (
    S5_MEASUREMENT_AUDIT_NEXT,
    S5_MEASUREMENT_AUDIT_REJECT,
    S5AcceptedDevelopmentMeasurementResultAuditV1,
)
from scripts.audit_s5_accepted_development_measurement_result import (
    DEFAULT_OUTPUT_ROWS,
    DEFAULT_RESULT,
    build_audit,
    load_rows,
    repository_ref_state,
)


def audit_time() -> datetime:
    return datetime(2026, 9, 8, 22, 0, tzinfo=UTC)


def test_result_audit_rejects_absent_release_source_without_outcomes() -> None:
    audit = build_audit(
        result_path=DEFAULT_RESULT,
        output_rows_path=DEFAULT_OUTPUT_ROWS,
        audited_at=audit_time(),
    )

    assert audit.result_integrity_verified
    assert audit.output_manifest_verified
    assert audit.aggregate_accounting_verified
    assert not audit.nominal_result_pass_upheld
    assert not audit.release_measurement_fields_valid
    assert not audit.nonrelease_measurement_families_independently_reconstructed
    assert audit.stable_release_tag_inventory_count == 0
    assert audit.packed_tag_ref_count == 0
    assert audit.repository_tag_opt_no_tags_observed
    assert audit.decision == S5_MEASUREMENT_AUDIT_REJECT
    assert audit.next_authorization == S5_MEASUREMENT_AUDIT_NEXT
    assert audit.market_values_read == 0
    assert audit.returns_calculated == 0
    assert audit.orders_submitted == 0


def test_result_rows_reconcile_complete_month_accounting() -> None:
    rows = load_rows(DEFAULT_OUTPUT_ROWS)

    assert len(rows) == 212
    assert sum(row.primary_source_verified_accepted_pull_count for row in rows) == 16_267
    assert sum(row.all_accepted_pull_count for row in rows) == 16_273
    assert sum(row.canonical_integration_count for row in rows) == 16_238
    assert sum(row.unresolved_git_merge_count for row in rows) == 479
    assert sum(row.stable_release_tag_count for row in rows) == 0


def test_repository_ref_state_proves_tags_were_not_acquired() -> None:
    no_tags, tag_count, branch_count, master_only = repository_ref_state()

    assert no_tags
    assert tag_count == 0
    assert branch_count == 1
    assert master_only


def test_result_audit_rejects_nominal_pass_tampering() -> None:
    audit = build_audit(
        result_path=DEFAULT_RESULT,
        output_rows_path=DEFAULT_OUTPUT_ROWS,
        audited_at=audit_time(),
    )
    payload = audit.model_dump(mode="json")
    payload["nominal_result_pass_upheld"] = True

    with pytest.raises(ValidationError):
        S5AcceptedDevelopmentMeasurementResultAuditV1.model_validate(payload)
