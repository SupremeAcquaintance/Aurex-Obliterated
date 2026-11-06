from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v5 import (
    PeriodicFlowInterleavedRowProbeV5,
    audit_successor_terminal_audit_v5,
    build_successor_terminal_audit_v5,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def test_v5_terminal_audit_proves_validator_defect_and_grants_no_authority() -> None:
    hashes = {
        name: _hash(name)
        for name in (
            "result_file_sha256",
            "result_evidence_hash",
            "checkpoint_file_sha256",
            "checkpoint_evidence_hash",
            "protocol_file_sha256",
            "protocol_evidence_hash",
            "transport_amendment_file_sha256",
            "transport_amendment_evidence_hash",
            "execution_contract_file_sha256",
            "execution_contract_evidence_hash",
            "execution_contract_audit_file_sha256",
            "execution_contract_audit_evidence_hash",
            "runner_source_hash",
            "auditor_contract_hash",
            "request_file_sha256",
            "response_file_sha256",
            "request_marker_manifest_hash",
        )
    }
    rows = (
        (1, 3_166_744_581, 1_672_531_204_118),
        (2, 3_227_590_792, 1_674_604_940_087),
        (3, 3_166_744_582, 1_672_531_204_178),
        (4, 3_227_590_793, 1_674_604_940_100),
        (5, 3_166_744_583, 1_672_531_204_178),
        (6, 3_227_590_794, 1_674_604_940_118),
    )
    audit = build_successor_terminal_audit_v5(
        **hashes,
        audited_at=datetime(2026, 8, 13, tzinfo=UTC),
        frozen_failure_reason=(
            "primary_id_skipped_fraction less_than_equal "
            "16867608.08325330886319725218"
        ),
        failed_archive_relative_path=(
            "q1_periodic_flow_successor_acquisition_v5/BTCUSDT/2023-01/"
            "trades/BTCUSDT-trades-2023-01.zip"
        ),
        interleaved_row_probe=tuple(
            PeriodicFlowInterleavedRowProbeV5(
                ordinal=ordinal, primary_id=primary_id, timestamp_ms=timestamp
            )
            for ordinal, primary_id, timestamp in rows
        ),
        findings=tuple(f"finding-{number}" for number in range(8)),
    )

    assert audit_successor_terminal_audit_v5(audit)
    assert audit.validator_evidence_model_failure_observed is True
    assert audit.source_archive_integrity_failure_observed is False
    assert audit.authorizes_live is False
    assert audit.orders_submitted == 0
