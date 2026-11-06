from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from aurex.backtest_engine.s1_btc_source_execution_v2 import (
    S1BtcSourceExecutionContractV2,
)
from aurex.backtest_engine.s1_btc_source_v2 import (
    S1BtcSourceAcquisitionProtocolAuditV2,
    S1BtcSourceAcquisitionProtocolV2,
)
from scripts import run_s1_btc_source_acquisition_v2 as runner
from scripts.run_s1_btc_source_acquisition import file_sha256

PROTOCOL_PATH = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v2.json"
)


def load_protocol() -> S1BtcSourceAcquisitionProtocolV2:
    return S1BtcSourceAcquisitionProtocolV2.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )


def contract() -> S1BtcSourceExecutionContractV2:
    protocol = load_protocol()
    audit = S1BtcSourceAcquisitionProtocolAuditV2.model_validate_json(
        PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    return runner.build_hashed(
        S1BtcSourceExecutionContractV2,
        "contract_evidence_hash",
        frozen_at=datetime.now(UTC),
        builder_contract_hash="1" * 64,
        protocol_file_sha256=file_sha256(PROTOCOL_PATH),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(PROTOCOL_AUDIT_PATH),
        protocol_audit_evidence_hash=audit.audit_evidence_hash,
        runner_contract_hash=runner.runner_contract_hash(),
        v1_transport_dependency_file_sha256=file_sha256(
            Path("scripts/run_s1_btc_source_acquisition.py")
        ),
        free_disk_bytes_observed=250_000_000,
        synthetic_test_ids=tuple(f"synthetic-{index}" for index in range(10)),
    )


def rows(target, *, start_hour: int = 0, price: str = "123.45") -> list[list[str]]:
    output = []
    for hour in range(start_hour, 24):
        open_time = target.activation_open_time_ms + hour * 3_600_000
        output.append(
            [
                str(open_time),
                price if hour == start_hour else "124",
                "125",
                "122",
                "124.5",
                "10",
                str(open_time + 3_599_999),
                "1000",
                "10",
                "5",
                "500",
                "0",
            ]
        )
    return output


def archive_bytes(target, data_rows, *, member: str | None = None) -> bytes:
    payload = "\n".join(",".join(row) for row in data_rows) + "\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member or target.expected_member_name, payload)
    return output.getvalue()


def inspect(tmp_path: Path, target, payload: bytes):
    path = tmp_path / "source.zip"
    path.write_bytes(payload)
    return runner.inspect_archive_v2(
        path,
        target=target,
        published_archive_sha256=sha256(payload).hexdigest(),
        maximum_uncompressed_csv_bytes=1_000_000,
    )


def test_s1_1_protocol_declares_prior_exposure_and_zero_returns() -> None:
    protocol = load_protocol()
    assert protocol.prior_materialized_execution_price_count_declared == 21
    assert protocol.returns_calculated == 0
    assert protocol.reuse_target_count == 22
    assert protocol.network_target_count == 255


def test_first_available_midnight_bar_is_selected(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    summary, price = inspect(tmp_path, target, archive_bytes(target, rows(target)))
    assert summary.selected_open_time_ms == target.activation_open_time_ms
    assert summary.activation_delay_minutes == 0
    assert price == "123.45"


def test_first_available_delayed_bar_is_selected_without_backfill(tmp_path: Path) -> None:
    target = load_protocol().targets[21]
    summary, price = inspect(
        tmp_path,
        target,
        archive_bytes(target, rows(target, start_hour=10, price="8123.45")),
    )
    assert summary.selected_open_time_ms == target.activation_open_time_ms + 36_000_000
    assert summary.activation_delay_minutes == 600
    assert price == "8123.45"


def test_real_v1_gap_archive_reuses_exact_hash_and_selects_10utc() -> None:
    protocol = load_protocol()
    item = runner.acquire_target_v2(
        protocol.targets[21],
        protocol=protocol,
        contract=contract(),
        network_body_bytes_before=0,
    )
    assert item.outcome == "COMPLETE"
    assert item.source_mode == "V1_EXACT_HASH_REUSE"
    assert item.attempts == ()
    assert item.archive_summary is not None
    assert item.archive_summary.activation_delay_minutes == 600


def test_reuse_manifest_covers_exactly_the_classified_v1_prefix() -> None:
    protocol = load_protocol()
    assert tuple(item.sequence for item in protocol.reuse_artifacts) == tuple(range(1, 23))
    for target, reuse in zip(
        protocol.targets[:22],
        protocol.reuse_artifacts,
        strict=True,
    ):
        runner.verify_reuse_artifact(target, reuse)


def test_partial_checkpoint_verifies_only_its_classified_prefix(tmp_path: Path) -> None:
    protocol = load_protocol()
    execution_contract = contract()
    first = runner.acquire_target_v2(
        protocol.targets[0],
        protocol=protocol,
        contract=execution_contract,
        network_body_bytes_before=0,
    )
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(execution_contract.model_dump_json(), encoding="utf-8")
    checkpoint = runner.build_checkpoint(
        started_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        protocol_path=PROTOCOL_PATH,
        protocol=protocol,
        contract_path=contract_path,
        contract=execution_contract,
        target_evidence=(first,),
    )
    runner.verify_partial_checkpoint(
        checkpoint,
        protocol=protocol,
        contract=execution_contract,
    )
    assert checkpoint.classified_target_count == 1
    assert checkpoint.next_sequence == 2
    assert checkpoint.terminal is False


def test_archive_rejects_checksum_mismatch(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    payload = archive_bytes(target, rows(target))
    path = tmp_path / "source.zip"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="published SHA-256"):
        runner.inspect_archive_v2(
            path,
            target=target,
            published_archive_sha256="0" * 64,
            maximum_uncompressed_csv_bytes=1_000_000,
        )


def test_archive_rejects_unsafe_member(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    payload = archive_bytes(
        target,
        rows(target),
        member=f"../{target.expected_member_name}",
    )
    with pytest.raises(ValueError, match="safe expected CSV"):
        inspect(tmp_path, target, payload)


def test_archive_rejects_wrong_row_width(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    data_rows = rows(target)
    data_rows[2] = data_rows[2][:-1]
    with pytest.raises(ValueError, match="exactly 12 fields"):
        inspect(tmp_path, target, archive_bytes(target, data_rows))


def test_archive_rejects_duplicate_or_non_increasing_time(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    data_rows = rows(target)
    data_rows[2][0] = data_rows[1][0]
    with pytest.raises(ValueError, match="duplicate"):
        inspect(tmp_path, target, archive_bytes(target, data_rows))


def test_archive_rejects_rows_outside_target_date(tmp_path: Path) -> None:
    target = load_protocol().targets[0]
    data_rows = rows(target)
    data_rows[-1][0] = str(target.activation_open_time_ms + 86_400_000)
    with pytest.raises(ValueError, match="outside"):
        inspect(tmp_path, target, archive_bytes(target, data_rows))


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "bad"])
def test_archive_rejects_invalid_selected_price(tmp_path: Path, price: str) -> None:
    target = load_protocol().targets[0]
    with pytest.raises(ValueError, match="selected open"):
        inspect(
            tmp_path,
            target,
            archive_bytes(target, rows(target, price=price)),
        )


def test_execution_contract_grants_no_outcome_or_order_authority() -> None:
    execution_contract = contract()
    assert execution_contract.authorizes_network_acquisition is True
    assert execution_contract.authorizes_execution_price_values_only is True
    assert execution_contract.authorizes_return_testing is False
    assert execution_contract.authorizes_candidate_outcome is False
    assert execution_contract.authorizes_testnet_strategy_orders is False
    assert execution_contract.authorizes_live is False
