from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

from aurex.backtest_engine.s1_nfci_full_acquisition import (
    S1NfciFullAcquisitionProtocol,
    S1NfciFullAcquisitionTarget,
)
from aurex.backtest_engine.s1_nfci_full_execution import (
    S1NfciAcquisitionExecutionAddendum,
    S1NfciAcquisitionExecutionAudit,
)
from aurex.backtest_engine.s1_nfci_full_execution_v2 import (
    S1NfciAcquisitionExecutionAmendmentV2,
    S1NfciAcquisitionExecutionAuditV2,
)
from aurex.backtest_engine.s1_nfci_raw_pilot import S1NfciSnapshotSummary
from scripts.freeze_s1_successor_lineage import file_sha256
from scripts.run_s1_nfci_full_acquisition import (
    attempt_from_markers,
    classify_error,
    marker_path,
    recover_interrupted_attempt,
    runner_contract_hash,
    structural_failure_gate,
    validate_target,
)
from scripts.run_s1_nfci_raw_pilot import write_json_atomic

PROTOCOL_PATH = Path("data/evidence/s1_nfci_full_acquisition_protocol_v1.json")
ADDENDUM_PATH = Path("data/evidence/s1_nfci_acquisition_execution_addendum_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_acquisition_execution_audit_v1.json")
AMENDMENT_V2_PATH = Path(
    "data/evidence/s1_nfci_acquisition_execution_amendment_v2.json"
)
AUDIT_V2_PATH = Path("data/evidence/s1_nfci_acquisition_execution_audit_v2.json")


def stored_protocol() -> S1NfciFullAcquisitionProtocol:
    return S1NfciFullAcquisitionProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def test_runner_allowlist_and_error_classification() -> None:
    protocol = stored_protocol()
    validate_target(protocol.targets[0])

    transient = HTTPError("https://example.invalid", 429, "rate", None, None)
    permanent = HTTPError("https://example.invalid", 404, "missing", None, None)

    assert classify_error(transient, protocol=protocol) == (
        "TRANSIENT_FAILURE",
        "HTTPError",
    )
    assert classify_error(permanent, protocol=protocol) == (
        "PERMANENT_FAILURE",
        "HTTPError",
    )


def test_structural_gate_rejects_post_vintage_data() -> None:
    protocol = stored_protocol()
    target = protocol.targets[0]
    summary = S1NfciSnapshotSummary(
        csv_header=("observation_date", target.expected_value_column),
        row_count=100,
        valid_numeric_row_count=100,
        missing_value_row_count=0,
        distinct_observation_date_count=100,
        duplicate_observation_date_count=0,
        non_increasing_observation_date_count=0,
        post_vintage_observation_count=1,
        first_observation_date="1971-01-08",
        last_observation_date="2017-08-18",
        release_lag_days=0,
    )

    assert structural_failure_gate(target, summary, protocol=protocol) == (
        "NO_POST_VINTAGE_OBSERVATION_PER_TARGET"
    )


def test_v1_execution_contract_is_preserved_as_superseded() -> None:
    addendum = S1NfciAcquisitionExecutionAddendum.model_validate_json(
        ADDENDUM_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciAcquisitionExecutionAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert audit.addendum_file_sha256
    assert audit.addendum_evidence_hash == addendum.addendum_evidence_hash
    assert addendum.runner_contract_hash != runner_contract_hash()
    assert addendum.authorizes_network_acquisition is True
    assert addendum.authorizes_btc_market_value_access is False
    assert datetime.now(UTC) >= addendum.frozen_at


def test_atomic_raw_rename_interruption_reconciles_complete(tmp_path: Path) -> None:
    protocol = stored_protocol()
    raw_path = tmp_path / "nfci.csv"
    target = S1NfciFullAcquisitionTarget(
        sequence=1,
        target_id="001-nfci-vintage-2017-08-17",
        vintage_date="2017-08-17",
        url=(
            "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
            "?id=NFCI&vintage_date=2017-08-17"
        ),
        expected_value_column="NFCI_20170817",
        raw_path=raw_path.as_posix(),
    )
    request_path = marker_path(target, 1, "request")
    write_json_atomic(
        request_path,
        {
            "target_id": target.target_id,
            "attempt": 1,
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    raw_path.write_text(
        "observation_date,NFCI_20170817\n2017-08-11,-0.1\n",
        encoding="utf-8",
    )

    recover_interrupted_attempt(target, 1, protocol=protocol)
    attempt = attempt_from_markers(target, 1)

    assert attempt.outcome == "COMPLETE"
    assert attempt.status_code == 200
    assert attempt.bytes_received == raw_path.stat().st_size


def test_v2_execution_amendment_and_audit_lineage_is_intact() -> None:
    amendment = S1NfciAcquisitionExecutionAmendmentV2.model_validate_json(
        AMENDMENT_V2_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciAcquisitionExecutionAuditV2.model_validate_json(
        AUDIT_V2_PATH.read_text(encoding="utf-8")
    )

    assert audit.addendum_file_sha256 == file_sha256(AMENDMENT_V2_PATH)
    assert audit.addendum_evidence_hash == amendment.addendum_evidence_hash
    assert audit.protocol_evidence_hash == amendment.protocol_evidence_hash
    assert audit.runner_contract_hash == amendment.runner_contract_hash
    assert amendment.runner_contract_hash == runner_contract_hash()
    assert amendment.pre_correction_network_requests == 0
