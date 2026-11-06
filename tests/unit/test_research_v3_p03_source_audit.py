from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v3_p03_source_audit import (
    V3_P03_FAIL_DECISION,
    V3_P03_REQUIRED_L2_COLUMNS,
    V3_P03_REQUIREMENT_IDS,
    V3P03BookDepthSchemaEvidence,
    V3P03SourceArtifact,
    V3P03SourceAuditContract,
    V3P03SourceAuditResult,
    V3P03SourceTarget,
    audit_v3_p03_source_audit_contract,
    audit_v3_p03_source_audit_result,
    authoritative_source_targets,
)
from aurex.backtest_engine.research_v3_p03_stop_result import (
    V3P03SourceAuditStopResult,
    audit_v3_p03_source_audit_stop_result,
)
from aurex.backtest_engine.research_v3_p03_transport_amendment import (
    V3P03TransportAmendment,
    audit_v3_p03_transport_amendment,
)
from scripts.finalize_v3_p03_source_audit_stop import (
    DEFAULT_EXHAUSTED_ATTEMPT,
    DEFAULT_INITIAL_ATTEMPT,
    load_attempt,
)
from scripts.finalize_v3_p03_source_audit_stop import (
    authoritative_result as authoritative_stop_result,
)
from scripts.freeze_v3_p03_source_audit_contract import (
    DEFAULT_CHARTER,
    DEFAULT_REGISTER,
    DEFAULT_V3P02_RESULT,
    authoritative_contract,
    load_inputs,
)
from scripts.freeze_v3_p03_transport_amendment import (
    authoritative_amendment,
)
from scripts.run_v3_p03_source_audit import (
    SOURCE_FILENAMES,
    HttpPayload,
    authoritative_result,
    inspect_bookdepth_schema,
    requirement_findings,
)

OBSERVED_AT = datetime(2026, 7, 28, 14, 0, tzinfo=UTC)


def frozen_contract() -> V3P03SourceAuditContract:
    charter, register, v3p02_result = load_inputs(
        charter_path=DEFAULT_CHARTER,
        register_path=DEFAULT_REGISTER,
        v3p02_result_path=DEFAULT_V3P02_RESULT,
    )
    return authoritative_contract(
        frozen_at=OBSERVED_AT,
        charter=charter,
        register=register,
        v3p02_result=v3p02_result,
    )


def schema_evidence() -> V3P03BookDepthSchemaEvidence:
    return V3P03BookDepthSchemaEvidence(
        archive_sha256="a" * 64,
        published_checksum_sha256="a" * 64,
        archive_member_names=["BTCUSDT-bookDepth-2023-01-01.csv"],
        selected_member_name="BTCUSDT-bookDepth-2023-01-01.csv",
        header_columns=["depth", "notional", "percentage", "timestamp"],
        data_row_count=2880,
        required_l2_columns_present=[],
        required_l2_columns_missing=V3_P03_REQUIRED_L2_COLUMNS,
        numeric_market_fields_inspected=[],
    )


def transport_amendment() -> V3P03TransportAmendment:
    return authoritative_amendment(
        frozen_at=OBSERVED_AT,
        contract=frozen_contract(),
    )


def persisted_stop_inputs() -> tuple[
    V3P03SourceAuditContract,
    V3P03TransportAmendment,
]:
    contract = V3P03SourceAuditContract.model_validate_json(
        Path(
            "data/evidence/v3_p03_source_audit_contract_v1.json"
        ).read_text(encoding="utf-8")
    )
    amendment = V3P03TransportAmendment.model_validate_json(
        Path(
            "data/evidence/v3_p03_transport_amendment_v1.json"
        ).read_text(encoding="utf-8")
    )
    return contract, amendment


def source_artifacts(
    contract: V3P03SourceAuditContract,
) -> list[V3P03SourceArtifact]:
    return [
        V3P03SourceArtifact(
            source_id=target.source_id,
            url=target.url,
            local_path=f"data/evidence/source_snapshots/test/{index}.bin",
            observed_at=OBSERVED_AT,
            response_bytes=1,
            content_sha256=f"{index + 1:064x}",
            content_type="application/octet-stream",
            matched_markers=[],
        )
        for index, target in enumerate(contract.source_targets)
    ]


def test_v3p03_contract_freezes_all_or_nothing_no_outcome_audit() -> None:
    contract = frozen_contract()

    assert contract.requirement_ids == V3_P03_REQUIREMENT_IDS
    assert contract.required_l2_columns == V3_P03_REQUIRED_L2_COLUMNS
    assert len(contract.source_targets) == 5
    assert contract.maximum_http_requests == 5
    assert contract.maximum_archive_payload_requests == 1
    assert contract.qualification_rule.startswith("ALL_EIGHT")
    assert contract.market_numeric_value_inspection_permitted is False
    assert contract.strategy_outcome_inspection_permitted is False
    assert contract.credentialed_requests_permitted is False
    assert contract.selection_permitted is False
    assert audit_v3_p03_source_audit_contract(contract)


def test_v3p03_source_targets_are_exact_and_authoritative() -> None:
    targets = authoritative_source_targets()

    assert len({target.source_id for target in targets}) == 5
    assert sum(target.source_kind == "ARCHIVE" for target in targets) == 1
    assert sum(target.source_kind == "CHECKSUM" for target in targets) == 1
    assert all(target.url.startswith("https://") for target in targets)


def test_v3p03_source_target_refuses_non_authoritative_domain() -> None:
    with pytest.raises(ValidationError, match="authoritative HTTPS"):
        V3P03SourceTarget(
            source_id="UNTRUSTED_SOURCE",
            source_kind="DOCUMENT",
            url=(
                "https://example.com/a/long/enough/non-authoritative/"
                "source-document"
            ),
            maximum_response_bytes=4096,
        )


def test_v3p03_contract_refuses_request_budget_tampering() -> None:
    payload = frozen_contract().model_dump()
    payload["maximum_http_requests"] = 6
    payload["maximum_archive_payload_requests"] = 2

    with pytest.raises(ValidationError):
        V3P03SourceAuditContract.model_validate(payload)


def test_v3p03_bookdepth_schema_proves_missing_sequence_and_queue_fields(
    tmp_path: Path,
) -> None:
    archive_id = (
        "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_ARCHIVE"
    )
    checksum_id = (
        "BINANCE_VISION_BTCUSDT_BOOKDEPTH_2023_01_01_CHECKSUM"
    )
    archive_name = SOURCE_FILENAMES[archive_id]
    archive_path = tmp_path / archive_name
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "BTCUSDT-bookDepth-2023-01-01.csv",
            (
                "timestamp,percentage,depth,notional\n"
                "not-parsed,not-parsed,not-parsed,not-parsed\n"
                "still-not-parsed,still-not-parsed,still-not-parsed,"
                "still-not-parsed\n"
            ),
        )
    archive_bytes = archive_path.read_bytes()
    checksum = hashlib.sha256(archive_bytes).hexdigest()
    payloads = {
        archive_id: HttpPayload(
            source_id=archive_id,
            observed_at=OBSERVED_AT,
            status=200,
            content_type="application/zip",
            payload=archive_bytes,
            request_attempt_count=1,
        ),
        checksum_id: HttpPayload(
            source_id=checksum_id,
            observed_at=OBSERVED_AT,
            status=200,
            content_type="text/plain",
            payload=f"{checksum}  {archive_name}\n".encode(),
            request_attempt_count=1,
        ),
    }

    evidence = inspect_bookdepth_schema(payloads, tmp_path)

    assert evidence.header_columns == [
        "depth",
        "notional",
        "percentage",
        "timestamp",
    ]
    assert evidence.data_row_count == 2
    assert evidence.required_l2_columns_present == []
    assert evidence.required_l2_columns_missing == V3_P03_REQUIRED_L2_COLUMNS
    assert evidence.numeric_market_fields_inspected == []


def test_v3p03_transport_amendment_changes_only_bounded_polling() -> None:
    amendment = transport_amendment()

    assert amendment.trigger_observation.startswith("HTTP_202")
    assert amendment.source_targets_changed is False
    assert amendment.source_substitution_permitted is False
    assert amendment.qualification_rule_changed is False
    assert amendment.decision_rule_changed is False
    assert amendment.market_value_permissions_changed is False
    assert amendment.maximum_pending_polls == 3
    assert amendment.amended_maximum_http_requests == 8
    assert audit_v3_p03_transport_amendment(amendment)


def test_v3p03_transport_amendment_refuses_rule_tampering() -> None:
    payload = transport_amendment().model_dump()
    payload["qualification_rule_changed"] = True

    with pytest.raises(ValidationError):
        V3P03TransportAmendment.model_validate(payload)


def test_v3p03_stop_result_preserves_both_failures_and_rejects() -> None:
    contract, amendment = persisted_stop_inputs()
    attempts = [
        load_attempt(
            DEFAULT_INITIAL_ATTEMPT,
            "INITIAL_HTTP_202",
            contract,
            amendment,
        ),
        load_attempt(
            DEFAULT_EXHAUSTED_ATTEMPT,
            "AMENDED_HTTP_202_EXHAUSTED",
            contract,
            amendment,
        ),
    ]
    result = authoritative_stop_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        amendment=amendment,
        attempts=attempts,
    )

    assert result.decision == V3_P03_FAIL_DECISION
    assert result.attempted_run_count == 2
    assert result.total_http_request_attempt_count == 7
    assert result.evaluated_requirement_ids == []
    assert result.qualified_requirement_ids == []
    assert result.selects_primary is False
    assert result.creates_candidate is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert result.return_metrics_calculated == []
    assert audit_v3_p03_source_audit_stop_result(result)


def test_v3p03_stop_result_refuses_false_evaluation_claim() -> None:
    contract, amendment = persisted_stop_inputs()
    result = authoritative_stop_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        amendment=amendment,
        attempts=[
            load_attempt(
                DEFAULT_INITIAL_ATTEMPT,
                "INITIAL_HTTP_202",
                contract,
                amendment,
            ),
            load_attempt(
                DEFAULT_EXHAUSTED_ATTEMPT,
                "AMENDED_HTTP_202_EXHAUSTED",
                contract,
                amendment,
            ),
        ],
    )
    payload = result.model_dump()
    payload["evaluated_requirement_ids"] = [
        "SEQUENCE_COMPLETE_SUBSECOND_L2_2023_2024"
    ]

    with pytest.raises(ValidationError, match="cannot claim evaluated"):
        V3P03SourceAuditStopResult.model_validate(payload)


def test_v3p03_requirement_matrix_rejects_every_unqualified_dependency() -> None:
    findings = requirement_findings(schema_evidence())

    assert [item.requirement_id for item in findings] == V3_P03_REQUIREMENT_IDS
    assert all(item.qualified is False for item in findings)
    assert {item.status for item in findings} == {
        "CURRENT_ONLY_NOT_DATED",
        "INSUFFICIENT_AGGREGATED_SNAPSHOT",
        "LIVE_ONLY_NOT_HISTORICAL",
        "MISSING_MEASURED_EVIDENCE",
        "OWN_ACCOUNT_ONLY_NOT_COUNTERFACTUAL",
        "SOURCE_AVAILABLE_PENDING_PAYLOAD_QUALIFICATION",
    }


def test_v3p03_result_rejects_without_selecting_or_opening_data() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        source_artifacts=source_artifacts(contract),
        bookdepth_schema_evidence=schema_evidence(),
    )

    assert result.decision == V3_P03_FAIL_DECISION
    assert result.summary.qualified_requirement_count == 0
    assert result.summary.failed_requirement_count == 8
    assert result.selects_primary is False
    assert result.creates_candidate is False
    assert result.opens_validation is False
    assert result.opens_holdout is False
    assert result.opens_forward is False
    assert result.creates_paper_eligibility is False
    assert result.creates_live_eligibility is False
    assert result.market_numeric_values_inspected == []
    assert result.return_metrics_calculated == []
    assert audit_v3_p03_source_audit_result(result)


def test_v3p03_result_refuses_decision_tampering() -> None:
    contract = frozen_contract()
    result = authoritative_result(
        generated_at=OBSERVED_AT,
        contract=contract,
        source_artifacts=source_artifacts(contract),
        bookdepth_schema_evidence=schema_evidence(),
    )
    payload = result.model_dump()
    payload["decision"] = "PERMIT_V3P03_PRIMARY_FEASIBILITY_CONSIDERATION"

    with pytest.raises(ValidationError, match="decision does not reconcile"):
        V3P03SourceAuditResult.model_validate(payload)


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_v3_p03_source_audit_contract.py",
        "scripts/freeze_v3_p03_transport_amendment.py",
        "scripts/finalize_v3_p03_source_audit_stop.py",
        "scripts/run_v3_p03_source_audit.py",
    ],
)
def test_v3p03_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
