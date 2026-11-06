from __future__ import annotations

import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.periodic_flow_metadata_census import (
    SPOT_AGGTRADE_COLUMNS,
    USD_M_AGGTRADE_COLUMNS,
    archive_url,
)
from aurex.backtest_engine.periodic_flow_payload_pilot import (
    Q1_PAYLOAD_PASS_AUTHORIZATION,
    Q1_PAYLOAD_PASS_DECISION,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    PeriodicFlowPayloadTarget,
    audit_periodic_flow_payload_protocol,
    audit_periodic_flow_payload_result,
    build_periodic_flow_payload_protocol,
    build_periodic_flow_payload_result,
)
from aurex.backtest_engine.periodic_flow_payload_transport_amendment import (
    PeriodicFlowPayloadTransportAmendment,
    audit_periodic_flow_transport_amendment,
    build_periodic_flow_transport_amendment,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.run_periodic_flow_payload_pilot import (
    MONTH_START_MS,
    file_sha256,
    inspect_pair,
    target_archive_path,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_archive(
    root: Path,
    *,
    product: str,
    outside_month: bool = False,
) -> Path:
    placeholder = PeriodicFlowPayloadTarget(
        product=product,
        archive_url=archive_url(product, "2020-01"),
        published_archive_sha256="0" * 64,
        expected_columns=(
            SPOT_AGGTRADE_COLUMNS
            if product == "SPOT"
            else USD_M_AGGTRADE_COLUMNS
        ),
        expected_column_count=8 if product == "SPOT" else 7,
    )
    path = target_archive_path(root, placeholder)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1,
    ) as archive:
        with archive.open("BTCUSDT-aggTrades-2020-01.csv", "w") as raw:
            for index in range(100_000):
                minute = index * 44_640 // 100_000
                timestamp = MONTH_START_MS + minute * 60_000
                if outside_month and index == 99_999:
                    timestamp = MONTH_START_MS - 1
                row = [
                    str(index + 1),
                    "NOT_A_PARSED_PRICE",
                    "NOT_A_PARSED_QUANTITY",
                    str(index + 1),
                    str(index + 1),
                    str(timestamp),
                    "true" if index % 2 else "false",
                ]
                if product == "SPOT":
                    row.append("true")
                raw.write((",".join(row) + "\n").encode("ascii"))
    return path


def _protocol(root: Path) -> PeriodicFlowPayloadPilotProtocol:
    targets = []
    for product in ("SPOT", "USD_M_PERPETUAL"):
        path = _write_archive(root, product=product)
        targets.append(
            PeriodicFlowPayloadTarget(
                product=product,
                archive_url=archive_url(product, "2020-01"),
                published_archive_sha256=file_sha256(path),
                expected_columns=(
                    SPOT_AGGTRADE_COLUMNS
                    if product == "SPOT"
                    else USD_M_AGGTRADE_COLUMNS
                ),
                expected_column_count=8 if product == "SPOT" else 7,
            )
        )
    targets_tuple = tuple(targets)
    return build_periodic_flow_payload_protocol(
        frozen_at=datetime(2026, 8, 7, tzinfo=UTC),
        census_contract_file_sha256="1" * 64,
        census_contract_evidence_hash="2" * 64,
        census_result_file_sha256="3" * 64,
        census_result_evidence_hash="4" * 64,
        census_audit_file_sha256="5" * 64,
        census_audit_evidence_hash="6" * 64,
        builder_contract_hash="7" * 64,
        targets=targets_tuple,
        target_manifest_hash=universe_evidence_hash(
            {"targets": [item.model_dump() for item in targets_tuple]}
        ),
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )


@pytest.fixture(scope="module")
def passing_pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("q1-payload")
    protocol = _protocol(root)
    evidence, clock = inspect_pair(
        protocol=protocol,
        evidence_root=root,
        request_counts={"SPOT": 1, "USD_M_PERPETUAL": 1},
    )
    return root, protocol, evidence, clock


def test_q1_payload_protocol_freezes_no_outcome_scope(passing_pair) -> None:
    _, protocol, _, _ = passing_pair
    assert audit_periodic_flow_payload_protocol(protocol)
    assert [item.product for item in protocol.targets] == [
        "SPOT",
        "USD_M_PERPETUAL",
    ]
    assert protocol.permitted_methods == ("GET",)
    assert protocol.maximum_unique_archive_urls == 2
    assert protocol.maximum_payload_get_attempts == 6
    assert protocol.price_or_quantity_parsing_permitted is False
    assert protocol.return_calculation_permitted is False
    assert protocol.validation_outcomes_permitted is False
    assert protocol.paper_operation_permitted is False
    assert protocol.testnet_strategy_orders_permitted is False
    assert protocol.live_permitted is False


def test_q1_payload_protocol_refuses_budget_tampering(passing_pair) -> None:
    _, protocol, _, _ = passing_pair
    payload = protocol.model_dump()
    payload["maximum_payload_get_attempts"] = 7
    with pytest.raises(ValidationError):
        PeriodicFlowPayloadPilotProtocol.model_validate(payload)


def test_q1_payload_parser_excludes_price_and_quantity(passing_pair) -> None:
    _, _, evidence, clock = passing_pair
    assert all(item.archive_pass for item in evidence)
    assert all(item.row_count == 100_000 for item in evidence)
    assert all(item.unique_minute_count == 44_640 for item in evidence)
    assert all(item.excluded_numeric_fields == ("price", "quantity") for item in evidence)
    assert all(item.parsed_numeric_fields == (
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "timestamp",
    ) for item in evidence)
    assert clock.paired_minute_count == 44_640
    assert clock.paired_clock_pass is True


def test_q1_payload_result_grants_only_next_protocol(passing_pair) -> None:
    _, protocol, evidence, clock = passing_pair
    result = build_periodic_flow_payload_result(
        generated_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        protocol_file_sha256="8" * 64,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="9" * 64,
        archive_evidence=evidence,
        paired_clock_evidence=clock,
        payload_get_attempt_count=2,
        total_archive_bytes=sum(item.archive_bytes for item in evidence),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes for item in evidence
        ),
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )
    assert audit_periodic_flow_payload_result(result)
    assert result.decision == Q1_PAYLOAD_PASS_DECISION
    assert result.next_authorization == Q1_PAYLOAD_PASS_AUTHORIZATION
    assert result.authorizes_separate_full_development_acquisition_protocol
    assert result.price_or_quantity_values_parsed == ()
    assert result.return_metrics_calculated == ()
    assert result.strategy_candidates_created == 0
    assert result.orders_submitted == 0
    assert result.authorizes_pine_deployment is False
    assert result.authorizes_paper_operation is False
    assert result.authorizes_testnet_strategy_orders is False
    assert result.authorizes_live is False
    assert result.real_net_profit_usd == "0"


def test_q1_payload_result_refuses_authority_tampering(passing_pair) -> None:
    _, protocol, evidence, clock = passing_pair
    result = build_periodic_flow_payload_result(
        generated_at=datetime(2026, 8, 7, 1, tzinfo=UTC),
        protocol_file_sha256="8" * 64,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash="9" * 64,
        archive_evidence=evidence,
        paired_clock_evidence=clock,
        payload_get_attempt_count=2,
        total_archive_bytes=sum(item.archive_bytes for item in evidence),
        total_member_uncompressed_bytes=sum(
            item.zip_uncompressed_bytes for item in evidence
        ),
        limitations=tuple(f"limitation-{index}" for index in range(8)),
    )
    payload = result.model_dump()
    payload["authorizes_live"] = True
    with pytest.raises(ValidationError):
        PeriodicFlowPayloadPilotResult.model_validate(payload)


def test_q1_transport_amendment_restores_only_actual_http_budget() -> None:
    markers = {
        (
            "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
            f"SPOT/marker-{index}.json"
        ): str(index) * 64
        for index in range(1, 7)
    }
    amendment = build_periodic_flow_transport_amendment(
        frozen_at=datetime(2026, 8, 7, 2, tzinfo=UTC),
        parent_protocol_file_sha256="a" * 64,
        parent_protocol_evidence_hash="b" * 64,
        marker_file_sha256=markers,
        limitations=tuple(f"limitation-{index}" for index in range(6)),
    )
    assert audit_periodic_flow_transport_amendment(amendment)
    assert amendment.http_response_count == 0
    assert amendment.payload_bytes_received == 0
    assert amendment.replacement_spot_http_attempts_authorized == 3
    assert amendment.maximum_total_actual_payload_get_attempts == 6
    assert amendment.outcome_and_trading_authority_unchanged is True


def test_q1_transport_amendment_refuses_url_scope_tampering() -> None:
    markers = {
        (
            "data/evidence/source_snapshots/q1_periodic_flow_payload_pilot_v1/"
            f"SPOT/marker-{index}.json"
        ): str(index) * 64
        for index in range(1, 7)
    }
    amendment = build_periodic_flow_transport_amendment(
        frozen_at=datetime(2026, 8, 7, 2, tzinfo=UTC),
        parent_protocol_file_sha256="a" * 64,
        parent_protocol_evidence_hash="b" * 64,
        marker_file_sha256=markers,
        limitations=tuple(f"limitation-{index}" for index in range(6)),
    )
    payload = amendment.model_dump()
    payload["original_urls_unchanged"] = False
    with pytest.raises(ValidationError):
        PeriodicFlowPayloadTransportAmendment.model_validate(payload)


def test_q1_payload_parser_rejects_out_of_month_timestamp(tmp_path) -> None:
    protocol = _protocol(tmp_path)
    spot_target = protocol.targets[0]
    bad_path = _write_archive(tmp_path, product="SPOT", outside_month=True)
    updated_target = spot_target.model_copy(
        update={"published_archive_sha256": file_sha256(bad_path)}
    )
    from scripts.run_periodic_flow_payload_pilot import inspect_archive

    with pytest.raises(ValueError, match="outside frozen month"):
        inspect_archive(
            target=updated_target,
            protocol=protocol,
            archive_path=bad_path,
            evidence_root=tmp_path,
            payload_get_attempt_count=1,
        )


@pytest.mark.parametrize(
    "script",
    [
        "scripts/freeze_periodic_flow_payload_pilot_protocol.py",
        "scripts/freeze_periodic_flow_payload_transport_amendment.py",
        "scripts/run_periodic_flow_payload_pilot.py",
        "scripts/audit_periodic_flow_payload_pilot.py",
    ],
)
def test_q1_payload_scripts_support_direct_invocation(script: str) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
