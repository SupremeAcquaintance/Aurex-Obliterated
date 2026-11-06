from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aurex.backtest_engine.research_v4_p01_feasibility_runner import (
    V4P01JournalRecord,
    V4P01SourceObservation,
)
from scripts.run_v4_p01_continuation import (
    audit_continuation_terminal,
    corrected_metadata_gate,
    load_continuation_contract,
    reconstruct_continuation_journal,
    run_continuation,
)
from scripts.run_v4_p01_feasibility import (
    EvidenceIntegrityError,
    load_ndjson,
)
from tests.unit.test_research_v4_p01_feasibility_runner import FakeTransport

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = PROJECT_ROOT / "data" / "evidence"
FIXED_NOW = datetime(2026, 7, 29, 10, 0, tzinfo=UTC)


def frozen_inputs():
    return load_continuation_contract(
        charter_path=EVIDENCE / "v4_mechanism_discovery_charter_v1.json",
        register_path=EVIDENCE / "v4_mechanism_proposal_register_v1.json",
        original_contract_path=(
            EVIDENCE / "v4_p01_feasibility_contract_v1.json"
        ),
        continuation_contract_path=(
            EVIDENCE / "v4_p01_feasibility_continuation_contract_v1.json"
        ),
    )


def test_continuation_corrected_gate_passes_only_bound_inherited_metadata() -> None:
    contract, _, _, metadata_observations, _ = frozen_inputs()

    gate = corrected_metadata_gate(
        contract=contract,
        metadata_observations=metadata_observations,
    )

    assert gate.status == "PASS"
    assert gate.payload_phase_authorized is True
    assert gate.contract_evidence_hash == contract.contract_evidence_hash
    assert gate.observation_hashes == (
        contract.inherited_metadata_observation_hashes
    )
    assert "optional symbol end is absent" in gate.reasons[0]


def test_continuation_runs_only_six_payloads_then_rejects_execution_gates(
    tmp_path: Path,
) -> None:
    contract, _, original_terminal, metadata_observations, _ = frozen_inputs()
    original_terminal_hash = original_terminal.result_evidence_hash
    transport = FakeTransport()

    result = run_continuation(
        contract=contract,
        metadata_observations=metadata_observations,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "REJECT"
    assert result.decision == "REJECT_V4P01_BEFORE_PRIMARY_SELECTION"
    assert transport.calls == [item.request_id for item in contract.requests]
    assert result.resource_totals.attempts_used == 6
    assert result.resource_totals.responses_completed == 6
    assert result.selects_primary is False
    assert result.authorizes_returns is False
    assert (
        result.builder_and_contract_hashes[
            "original_terminal_reject_evidence_hash"
        ]
        == original_terminal_hash
    )
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
    assert len(journal) == 12
    assert [
        item.request_sequence
        for item in journal
        if item.record_type == "REQUEST_INTENT"
    ] == list(range(3, 9))


def test_continuation_transport_failure_consumes_one_payload_attempt(
    tmp_path: Path,
) -> None:
    contract, _, _, metadata_observations, _ = frozen_inputs()
    failed_id = contract.requests[0].request_id
    transport = FakeTransport(fail_request_id=failed_id)

    result = run_continuation(
        contract=contract,
        metadata_observations=metadata_observations,
        project_root=tmp_path,
        transport=transport,
        clock=lambda: FIXED_NOW,
    )

    assert result.terminal_kind == "TRANSPORT_STOP"
    assert transport.calls == [failed_id]
    assert result.resource_totals.attempts_used == 1
    assert result.resource_totals.failures_recorded == 1
    assert result.partial_byte_count_and_sha256["byte_count"] == 17
    assert result.unconsumed_request_and_byte_budgets["requests"] == 5


def test_continuation_observations_remain_value_opaque(
    tmp_path: Path,
) -> None:
    contract, _, _, metadata_observations, _ = frozen_inputs()
    run_continuation(
        contract=contract,
        metadata_observations=metadata_observations,
        project_root=tmp_path,
        transport=FakeTransport(),
        clock=lambda: FIXED_NOW,
    )

    payload_text = (tmp_path / contract.payload_observation_path).read_text(
        encoding="utf-8"
    )
    assert "0.050" not in payload_text
    assert "0.051" not in payload_text
    observations = load_ndjson(
        tmp_path / contract.payload_observation_path,
        V4P01SourceObservation,
    )
    assert len(observations) == 6
    assert [item.observation_sequence for item in observations] == list(
        range(3, 9)
    )


def test_continuation_terminal_audit_detects_journal_tamper(
    tmp_path: Path,
) -> None:
    contract, _, _, metadata_observations, _ = frozen_inputs()
    run_continuation(
        contract=contract,
        metadata_observations=metadata_observations,
        project_root=tmp_path,
        transport=FakeTransport(),
        clock=lambda: FIXED_NOW,
    )
    assert audit_continuation_terminal(
        contract=contract,
        metadata_observations=metadata_observations,
        project_root=tmp_path,
    )
    journal_path = tmp_path / contract.journal_path
    text = journal_path.read_text(encoding="utf-8")
    journal_path.write_text(
        text.replace(contract.requests[0].request_id, "V4P01_PILOT_TAMPERED", 1),
        encoding="utf-8",
    )

    with pytest.raises(EvidenceIntegrityError, match="Invalid V4P01 NDJSON"):
        audit_continuation_terminal(
            contract=contract,
            metadata_observations=metadata_observations,
            project_root=tmp_path,
        )


def test_continuation_journal_rejects_out_of_order_intent(
    tmp_path: Path,
) -> None:
    contract, _, _, _, _ = frozen_inputs()
    journal_path = tmp_path / contract.journal_path
    journal_path.parent.mkdir(parents=True)
    journal_path.write_text(
        '{"not":"a valid journal record"}\n',
        encoding="utf-8",
    )

    with pytest.raises(EvidenceIntegrityError, match="Invalid V4P01 NDJSON"):
        reconstruct_continuation_journal(contract, journal_path)


def test_continuation_cli_dry_run_is_explicit_and_non_network() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v4_p01_continuation.py",
            "--dry-run",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "requests=6 metadata_repeats=0 retries=0" in completed.stdout
    assert "V4P01_META_BINANCE" not in completed.stdout
