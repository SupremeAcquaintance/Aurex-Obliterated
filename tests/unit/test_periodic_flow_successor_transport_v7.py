from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (
    PeriodicFlowSuccessorTransportAmendmentV5,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (
    audit_hash,
    build_transport_amendment_v7,
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def test_v7_preserves_total_payload_cap_and_refuses_partial_adoption() -> None:
    v5 = PeriodicFlowSuccessorTransportAmendmentV5.model_validate_json(
        open(
            "data/evidence/q1_periodic_flow_successor_transport_amendment_v5.json",
            encoding="utf-8",
        ).read()
    )
    inherited = v5.model_dump(
        exclude={
            "schema_version",
            "amendment_id",
            "frozen_at",
            "status",
            "request_marker_schema",
            "response_marker_schema",
            "next_authorization",
            "limitations",
            "amendment_evidence_hash",
        }
    )
    hashes = {
        name: _hash(name)
        for name in (
            "parent_v6_validator_amendment_file_sha256",
            "parent_v6_validator_amendment_evidence_hash",
            "parent_v6_contract_file_sha256",
            "parent_v6_contract_evidence_hash",
            "parent_v6_contract_audit_file_sha256",
            "parent_v6_contract_audit_evidence_hash",
            "terminal_v6_result_file_sha256",
            "terminal_v6_result_evidence_hash",
            "terminal_v6_checkpoint_file_sha256",
            "terminal_v6_checkpoint_evidence_hash",
            "terminal_v6_audit_file_sha256",
            "terminal_v6_audit_evidence_hash",
        )
    }
    amendment = build_transport_amendment_v7(
        **inherited,
        **hashes,
        frozen_at=datetime(2026, 8, 14, tzinfo=UTC),
        limitations=tuple(f"limitation-{number}" for number in range(12)),
    )

    assert audit_hash(amendment, "amendment_evidence_hash")
    assert (
        amendment.seed_total_new_archive_bytes
        + amendment.maximum_remaining_payload_bytes
        == amendment.inherited_maximum_new_archive_bytes_total
    )
    assert amendment.failed_partial_adoption_permitted is False
    assert amendment.strategy_or_order_authority is False
