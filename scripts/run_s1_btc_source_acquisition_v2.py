from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.binance_vision import BINANCE_KLINE_COLUMNS  # noqa: E402
from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1_1_ACQUISITION_NEXT,
    S1_1_ACQUISITION_PASS,
    S1_1_ACQUISITION_STOP,
    S1BtcAcquisitionCheckpointV2,
    S1BtcArchiveSummaryV2,
    S1BtcPriceRowV2,
    S1BtcSourceAcquisitionResultV2,
    S1BtcSourceExecutionAuditV2,
    S1BtcSourceExecutionContractV2,
    S1BtcTargetEvidenceV2,
    validate_positive_decimal,
)
from aurex.backtest_engine.s1_btc_source_v2 import (  # noqa: E402
    S1BtcReuseArtifactV2,
    S1BtcSourceAcquisitionProtocolAuditV2,
    S1BtcSourceAcquisitionProtocolV2,
)
from aurex.backtest_engine.s1_source_feasibility import S1SourceGate  # noqa: E402
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import (  # noqa: E402
    RUNNER_PATH as V1_RUNNER_PATH,
)
from scripts.run_s1_btc_source_acquisition import (  # noqa: E402
    acquire_resource,
    file_sha256,
    parse_checksum_text,
    project_path,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v2.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_btc_source_acquisition_protocol_audit_v2.json"
)
DEFAULT_CONTRACT = Path("data/evidence/s1_btc_source_execution_contract_v2.json")
DEFAULT_CONTRACT_AUDIT = Path("data/evidence/s1_btc_source_execution_audit_v2.json")
DEFAULT_CHECKPOINT = Path("data/evidence/s1_btc_source_acquisition_checkpoint_v2.json")
DEFAULT_RESULT = Path("data/evidence/s1_btc_source_acquisition_result_v2.json")
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s1_btc_source_execution_v2.py"
)
SOURCE_PROTOCOL_MODULE_PATH = Path("src/aurex/backtest_engine/s1_btc_source_v2.py")
RUNNER_PATH = Path("scripts/run_s1_btc_source_acquisition_v2.py")


def runner_contract_hash() -> str:
    paths = (
        EXECUTION_MODULE_PATH,
        SOURCE_PROTOCOL_MODULE_PATH,
        V1_RUNNER_PATH,
        RUNNER_PATH,
    )
    return universe_evidence_hash(
        {path.as_posix(): file_sha256(PROJECT_ROOT / path) for path in paths}
    )


def build_hashed(model_type, hash_field: str, **payload):
    provisional = model_type.model_construct(**payload, **{hash_field: "0" * 64})
    complete = provisional.model_dump(mode="json")
    complete[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model_type.model_validate(complete)


def inspect_archive_v2(
    archive_path: Path,
    *,
    target,
    published_archive_sha256: str,
    maximum_uncompressed_csv_bytes: int,
) -> tuple[S1BtcArchiveSummaryV2, str]:
    if file_sha256(archive_path) != published_archive_sha256:
        raise ValueError("S1.1 archive does not match its published SHA-256")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) != 1:
            raise ValueError("S1.1 archive must contain exactly one member")
        member = members[0]
        member_path = PurePosixPath(member.filename)
        if (
            member.is_dir()
            or member.filename != target.expected_member_name
            or member_path.is_absolute()
            or ".." in member_path.parts
            or "\\" in member.filename
            or member.flag_bits & 0x1
        ):
            raise ValueError("S1.1 archive member is not the safe expected CSV")
        if member.file_size > maximum_uncompressed_csv_bytes:
            raise ValueError("S1.1 archive member exceeds its uncompressed cap")
        with archive.open(member) as source:
            payload = source.read(maximum_uncompressed_csv_bytes + 1)
        if len(payload) > maximum_uncompressed_csv_bytes:
            raise ValueError("S1.1 archive expanded beyond its byte cap")
    try:
        rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline="")))
    except UnicodeError as exc:
        raise ValueError("S1.1 CSV is not valid UTF-8") from exc
    if not rows or any(len(row) != 12 for row in rows):
        raise ValueError("S1.1 CSV rows must contain exactly 12 fields")
    header_present = tuple(value.strip().lower() for value in rows[0]) == tuple(
        BINANCE_KLINE_COLUMNS
    )
    data_rows = rows[1:] if header_present else rows
    if not data_rows:
        raise ValueError("S1.1 CSV has no kline rows")
    open_times: list[int] = []
    for row in data_rows:
        value = row[0].strip()
        if len(value) != 13 or not value.isdigit():
            raise ValueError("S1.1 open time is not a millisecond timestamp")
        open_times.append(int(value))
    if len(open_times) != len(set(open_times)):
        raise ValueError("S1.1 archive contains duplicate open times")
    if any(
        right <= left for left, right in zip(open_times, open_times[1:], strict=False)
    ):
        raise ValueError("S1.1 archive open times are not strictly increasing")
    day_start = target.activation_open_time_ms
    day_end = day_start + 86_400_000
    if any(not day_start <= value < day_end for value in open_times):
        raise ValueError("S1.1 archive contains a row outside its target date")
    selected_time = open_times[0]
    selected_price = validate_positive_decimal(data_rows[0][1].strip())
    delay_ms = selected_time - day_start
    if delay_ms < 0 or delay_ms % 60_000:
        raise ValueError("S1.1 selected open delay is invalid")
    delay_minutes = delay_ms // 60_000
    if delay_minutes > 1439:
        raise ValueError("S1.1 selected open exceeds the target date")
    summary = build_hashed(
        S1BtcArchiveSummaryV2,
        "summary_evidence_hash",
        member_name=member.filename,
        csv_row_count=len(rows),
        data_row_count=len(data_rows),
        header_present=header_present,
        first_open_time_ms=open_times[0],
        last_open_time_ms=open_times[-1],
        selected_open_time_ms=selected_time,
        activation_delay_minutes=delay_minutes,
        uncompressed_csv_bytes=len(payload),
    )
    return summary, selected_price


def target_evidence_from_files_v2(
    target,
    *,
    contract: S1BtcSourceExecutionContractV2,
    attempts,
    source_mode: str,
) -> S1BtcTargetEvidenceV2:
    archive_path = project_path(target.archive_path)
    checksum_path = project_path(target.checksum_path)
    try:
        published = parse_checksum_text(
            checksum_path.read_text(encoding="utf-8"),
            archive_path.name,
        )
        archive_sha = file_sha256(archive_path)
        checksum_sha = file_sha256(checksum_path)
        summary, selected_price = inspect_archive_v2(
            archive_path,
            target=target,
            published_archive_sha256=published,
            maximum_uncompressed_csv_bytes=contract.maximum_uncompressed_csv_bytes,
        )
        price_row = build_hashed(
            S1BtcPriceRowV2,
            "price_evidence_hash",
            sequence=target.sequence,
            feature_sequence=target.feature_sequence,
            target_date=target.activation_date,
            target_open_time_ms=target.activation_open_time_ms,
            selected_open_time_ms=summary.selected_open_time_ms,
            activation_delay_minutes=summary.activation_delay_minutes,
            open_price=selected_price,
            archive_file_sha256=archive_sha,
            published_archive_sha256=published,
            checksum_file_sha256=checksum_sha,
            source_target_id=target.target_id,
        )
        return build_hashed(
            S1BtcTargetEvidenceV2,
            "target_evidence_hash",
            sequence=target.sequence,
            target_id=target.target_id,
            target_date=target.activation_date,
            outcome="COMPLETE",
            source_mode=source_mode,
            attempts=attempts,
            archive_path=target.archive_path,
            archive_file_sha256=archive_sha,
            archive_bytes=archive_path.stat().st_size,
            checksum_path=target.checksum_path,
            checksum_file_sha256=checksum_sha,
            checksum_bytes=checksum_path.stat().st_size,
            published_archive_sha256=published,
            archive_summary=summary,
            price_row=price_row,
            failure_gate=None,
        )
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        return build_hashed(
            S1BtcTargetEvidenceV2,
            "target_evidence_hash",
            sequence=target.sequence,
            target_id=target.target_id,
            target_date=target.activation_date,
            outcome="FAILED",
            source_mode=source_mode,
            attempts=attempts,
            archive_path=target.archive_path if archive_path.is_file() else None,
            archive_file_sha256=(
                file_sha256(archive_path) if archive_path.is_file() else None
            ),
            archive_bytes=archive_path.stat().st_size if archive_path.is_file() else 0,
            checksum_path=target.checksum_path if checksum_path.is_file() else None,
            checksum_file_sha256=(
                file_sha256(checksum_path) if checksum_path.is_file() else None
            ),
            checksum_bytes=(
                checksum_path.stat().st_size if checksum_path.is_file() else 0
            ),
            published_archive_sha256=None,
            archive_summary=None,
            price_row=None,
            failure_gate=f"SOURCE_STRUCTURE_OR_CHECKSUM_FAILED:{type(exc).__name__}",
        )


def verify_reuse_artifact(
    target,
    reuse: S1BtcReuseArtifactV2,
) -> None:
    archive_path = project_path(reuse.archive_path)
    checksum_path = project_path(reuse.checksum_path)
    if (
        target.sequence != reuse.sequence
        or target.target_id != reuse.target_id
        or file_sha256(archive_path) != reuse.archive_file_sha256
        or file_sha256(checksum_path) != reuse.checksum_file_sha256
        or archive_path.stat().st_size != reuse.archive_bytes
        or checksum_path.stat().st_size != reuse.checksum_bytes
        or parse_checksum_text(checksum_path.read_text(), archive_path.name)
        != reuse.published_archive_sha256
    ):
        raise ValueError("S1.1 exact-hash reuse evidence changed")


def build_failed_transport_target(target, attempts) -> S1BtcTargetEvidenceV2:
    archive_path = project_path(target.archive_path)
    checksum_path = project_path(target.checksum_path)
    return build_hashed(
        S1BtcTargetEvidenceV2,
        "target_evidence_hash",
        sequence=target.sequence,
        target_id=target.target_id,
        target_date=target.activation_date,
        outcome="FAILED",
        source_mode="NETWORK",
        attempts=attempts,
        archive_path=target.archive_path if archive_path.is_file() else None,
        archive_file_sha256=(
            file_sha256(archive_path) if archive_path.is_file() else None
        ),
        archive_bytes=archive_path.stat().st_size if archive_path.is_file() else 0,
        checksum_path=target.checksum_path if checksum_path.is_file() else None,
        checksum_file_sha256=(
            file_sha256(checksum_path) if checksum_path.is_file() else None
        ),
        checksum_bytes=checksum_path.stat().st_size if checksum_path.is_file() else 0,
        published_archive_sha256=None,
        archive_summary=None,
        price_row=None,
        failure_gate="PAYLOAD_TRANSPORT_OR_ATTEMPT_BUDGET_FAILED",
    )


def acquire_target_v2(
    target,
    *,
    protocol: S1BtcSourceAcquisitionProtocolV2,
    contract: S1BtcSourceExecutionContractV2,
    network_body_bytes_before: int,
) -> S1BtcTargetEvidenceV2:
    if target.sequence <= protocol.reuse_target_count:
        reuse = protocol.reuse_artifacts[target.sequence - 1]
        verify_reuse_artifact(target, reuse)
        return target_evidence_from_files_v2(
            target,
            contract=contract,
            attempts=(),
            source_mode="V1_EXACT_HASH_REUSE",
        )
    checksum_attempts = acquire_resource(
        target,
        "CHECKSUM",
        protocol=protocol,
        network_body_bytes_before=network_body_bytes_before,
    )
    if not checksum_attempts or checksum_attempts[-1].outcome != "COMPLETE":
        return build_failed_transport_target(target, checksum_attempts)
    archive_attempts = acquire_resource(
        target,
        "ARCHIVE",
        protocol=protocol,
        network_body_bytes_before=(
            network_body_bytes_before
            + sum(attempt.bytes_received for attempt in checksum_attempts)
        ),
    )
    attempts = checksum_attempts + archive_attempts
    if not archive_attempts or archive_attempts[-1].outcome != "COMPLETE":
        return build_failed_transport_target(target, attempts)
    return target_evidence_from_files_v2(
        target,
        contract=contract,
        attempts=attempts,
        source_mode="NETWORK",
    )


def build_checkpoint(
    *,
    started_at: datetime,
    updated_at: datetime,
    protocol_path: Path,
    protocol: S1BtcSourceAcquisitionProtocolV2,
    contract_path: Path,
    contract: S1BtcSourceExecutionContractV2,
    target_evidence: tuple[S1BtcTargetEvidenceV2, ...],
) -> S1BtcAcquisitionCheckpointV2:
    terminal = bool(
        target_evidence
        and (
            target_evidence[-1].outcome == "FAILED"
            or len(target_evidence) == protocol.target_count
        )
    )
    return build_hashed(
        S1BtcAcquisitionCheckpointV2,
        "checkpoint_evidence_hash",
        started_at=started_at,
        updated_at=updated_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        target_evidence=target_evidence,
        classified_target_count=len(target_evidence),
        complete_target_count=sum(item.outcome == "COMPLETE" for item in target_evidence),
        failed_target_count=sum(item.outcome == "FAILED" for item in target_evidence),
        reused_target_count=sum(
            item.source_mode == "V1_EXACT_HASH_REUSE" for item in target_evidence
        ),
        network_target_count=sum(
            item.source_mode == "NETWORK" for item in target_evidence
        ),
        network_request_count=sum(len(item.attempts) for item in target_evidence),
        network_body_bytes=sum(
            attempt.bytes_received
            for item in target_evidence
            for attempt in item.attempts
        ),
        persisted_source_bytes=sum(
            item.archive_bytes + item.checksum_bytes for item in target_evidence
        ),
        next_sequence=None if terminal else len(target_evidence) + 1,
        terminal=terminal,
    )


def write_model_atomic(path: Path, model, model_type) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        temporary.unlink()
    serialized = model.model_dump_json(indent=2) + "\n"
    if model_type.model_validate_json(serialized) != model:
        raise ValueError("S1.1 evidence did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def verify_partial_checkpoint(
    checkpoint: S1BtcAcquisitionCheckpointV2,
    *,
    protocol: S1BtcSourceAcquisitionProtocolV2,
    contract: S1BtcSourceExecutionContractV2,
) -> None:
    if checkpoint.runner_contract_hash != runner_contract_hash():
        raise ValueError("S1.1 checkpoint runner contract changed")
    targets = protocol.targets[: checkpoint.classified_target_count]
    for target, evidence in zip(targets, checkpoint.target_evidence, strict=True):
        if target.sequence != evidence.sequence or target.target_id != evidence.target_id:
            raise ValueError("S1.1 checkpoint target identity changed")
        if evidence.source_mode == "V1_EXACT_HASH_REUSE":
            verify_reuse_artifact(
                target,
                protocol.reuse_artifacts[target.sequence - 1],
            )
        for attempt in evidence.attempts:
            request = project_path(attempt.request_marker_path)
            response = project_path(attempt.response_marker_path)
            if (
                file_sha256(request) != attempt.request_marker_sha256
                or file_sha256(response) != attempt.response_marker_sha256
            ):
                raise ValueError("S1.1 checkpoint marker hash changed")
        reconstructed = target_evidence_from_files_v2(
            target,
            contract=contract,
            attempts=evidence.attempts,
            source_mode=evidence.source_mode,
        )
        if reconstructed != evidence:
            raise ValueError("S1.1 checkpoint source evidence changed")


def evaluate_gates(
    protocol: S1BtcSourceAcquisitionProtocolV2,
    checkpoint: S1BtcAcquisitionCheckpointV2,
) -> tuple[S1SourceGate, ...]:
    evidence = checkpoint.target_evidence
    complete = len(evidence) == protocol.target_count and all(
        item.outcome == "COMPLETE" for item in evidence
    )
    checks = {
        "ALL_277_FRIDAY_TARGETS_CLASSIFIED": len(evidence) == protocol.target_count,
        "EVERY_ZIP_MATCHES_ITS_PUBLISHED_SHA256": complete
        and all(
            item.archive_file_sha256 == item.published_archive_sha256
            for item in evidence
        ),
        "EVERY_ZIP_HAS_EXACTLY_ONE_SAFE_EXPECTED_CSV_MEMBER": complete
        and all(
            item.archive_summary is not None
            and item.archive_summary.member_name == target.expected_member_name
            for target, item in zip(protocol.targets, evidence, strict=True)
        ),
        "EVERY_CSV_ROW_HAS_EXACTLY_12_KLINE_FIELDS": complete,
        "OPEN_TIMES_ARE_UNIQUE_STRICTLY_INCREASING_AND_WITHIN_TARGET_DATE": complete,
        "FIRST_AVAILABLE_OPEN_EXISTS_ONCE_PER_TARGET_DATE": complete,
        "SELECTED_OPEN_IS_EARLIEST_OBSERVED_OPEN_ON_OR_AFTER_00_00_UTC": complete
        and all(
            item.archive_summary is not None
            and item.archive_summary.selected_open_time_ms
            == item.archive_summary.first_open_time_ms
            for item in evidence
        ),
        "SELECTED_OPEN_IS_POSITIVE_FINITE_DECIMAL_SOURCE_TEXT": complete
        and all(item.price_row is not None for item in evidence),
        "REUSE_AND_NETWORK_EVIDENCE_RECONCILE_EXACTLY": complete
        and checkpoint.reused_target_count == 22
        and checkpoint.network_target_count == 255,
        "OUTPUT_HAS_277_CHRONOLOGICAL_HASH_LINKED_PRICE_ROWS": complete
        and tuple(item.price_row.sequence for item in evidence if item.price_row)
        == tuple(range(1, 278)),
        "ZERO_RETURNS_CANDIDATE_OUTCOMES_VALIDATION_HOLDOUT_AND_ORDERS": True,
    }
    return tuple(
        S1SourceGate(
            gate_id=gate_id,
            status="PASS" if passed else "FAIL",
            reason=(
                "Observed evidence satisfies the frozen S1.1 source condition."
                if passed
                else "Observed evidence does not satisfy the frozen S1.1 source condition."
            ),
        )
        for gate_id, passed in sorted(checks.items())
    )


def dataset_bytes(rows: tuple[S1BtcPriceRowV2, ...]) -> bytes:
    return b"".join(
        (json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def materialize_dataset(path: Path, rows: tuple[S1BtcPriceRowV2, ...]) -> None:
    payload = dataset_bytes(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("Existing S1.1 dataset bytes changed")
        return
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError("Stale S1.1 dataset transaction exists")
    temporary.write_bytes(payload)
    temporary.replace(path)


def build_result(
    *,
    checkpoint_path: Path,
    checkpoint: S1BtcAcquisitionCheckpointV2,
    protocol: S1BtcSourceAcquisitionProtocolV2,
    completed_at: datetime,
) -> S1BtcSourceAcquisitionResultV2:
    gates = evaluate_gates(protocol, checkpoint)
    failed = any(gate.status == "FAIL" for gate in gates)
    rows = tuple(
        item.price_row for item in checkpoint.target_evidence if item.price_row is not None
    )
    dataset_path = project_path(protocol.output_path)
    if not failed:
        materialize_dataset(dataset_path, rows)
    delays = tuple(row.activation_delay_minutes for row in rows)
    return build_hashed(
        S1BtcSourceAcquisitionResultV2,
        "result_evidence_hash",
        completed_at=completed_at,
        checkpoint_file_sha256=file_sha256(checkpoint_path),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_evidence_hash=checkpoint.protocol_evidence_hash,
        execution_contract_evidence_hash=(
            checkpoint.execution_contract_evidence_hash
        ),
        runner_contract_hash=checkpoint.runner_contract_hash,
        target_evidence=checkpoint.target_evidence,
        price_rows=rows if not failed else (),
        gates=gates,
        classified_target_count=checkpoint.classified_target_count,
        complete_target_count=checkpoint.complete_target_count,
        failed_target_count=checkpoint.failed_target_count,
        reused_target_count=checkpoint.reused_target_count,
        network_target_count=checkpoint.network_target_count,
        network_request_count=checkpoint.network_request_count,
        network_body_bytes=checkpoint.network_body_bytes,
        persisted_source_bytes=checkpoint.persisted_source_bytes,
        maximum_activation_delay_minutes_observed=max(delays, default=0),
        delayed_activation_target_count=sum(delay > 0 for delay in delays),
        dataset_path=protocol.output_path if not failed else None,
        dataset_file_sha256=file_sha256(dataset_path) if not failed else None,
        dataset_bytes=dataset_path.stat().st_size if not failed else 0,
        decision=S1_1_ACQUISITION_STOP if failed else S1_1_ACQUISITION_PASS,
        next_authorization=(
            "NONE_S1_1_BTC_SOURCE_ACQUISITION_FAILED"
            if failed
            else S1_1_ACQUISITION_NEXT
        ),
    )


def load_authority(
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
) -> tuple[S1BtcSourceAcquisitionProtocolV2, S1BtcSourceExecutionContractV2]:
    protocol = S1BtcSourceAcquisitionProtocolV2.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S1BtcSourceAcquisitionProtocolAuditV2.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S1BtcSourceExecutionContractV2.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S1BtcSourceExecutionAuditV2.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != contract.protocol_file_sha256
        or protocol.protocol_evidence_hash != contract.protocol_evidence_hash
        or protocol_audit.audit_evidence_hash != contract.protocol_audit_evidence_hash
        or file_sha256(protocol_audit_path) != contract.protocol_audit_file_sha256
        or runner_contract_hash() != contract.runner_contract_hash
        or file_sha256(PROJECT_ROOT / V1_RUNNER_PATH)
        != contract.v1_transport_dependency_file_sha256
        or file_sha256(contract_path) != contract_audit.contract_file_sha256
        or contract.contract_evidence_hash != contract_audit.contract_evidence_hash
        or contract.runner_contract_hash != contract_audit.runner_contract_hash
        or not contract.authorizes_network_acquisition
    ):
        raise ValueError("S1.1 source acquisition authority lineage changed")
    return protocol, contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the bounded, resumable S1.1 BTC source acquisition."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1.1 result: {args.output}")
    protocol, contract = load_authority(
        args.protocol,
        args.protocol_audit,
        args.contract,
        args.contract_audit,
    )
    if shutil.disk_usage(PROJECT_ROOT).free < protocol.minimum_free_disk_bytes:
        raise SystemExit("Insufficient free disk for S1.1 BTC source acquisition")
    if args.checkpoint.exists():
        checkpoint = S1BtcAcquisitionCheckpointV2.model_validate_json(
            args.checkpoint.read_text(encoding="utf-8")
        )
        verify_partial_checkpoint(
            checkpoint,
            protocol=protocol,
            contract=contract,
        )
        if checkpoint.terminal:
            result = build_result(
                checkpoint_path=args.checkpoint,
                checkpoint=checkpoint,
                protocol=protocol,
                completed_at=datetime.now(UTC),
            )
            write_model_atomic(args.output, result, S1BtcSourceAcquisitionResultV2)
            return 0
        started_at = checkpoint.started_at
        evidence = list(checkpoint.target_evidence)
    else:
        started_at = datetime.now(UTC)
        evidence = []
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=started_at,
            protocol_path=args.protocol,
            protocol=protocol,
            contract_path=args.contract,
            contract=contract,
            target_evidence=(),
        )
        write_model_atomic(args.checkpoint, checkpoint, S1BtcAcquisitionCheckpointV2)
    for target in protocol.targets[len(evidence) :]:
        item = acquire_target_v2(
            target,
            protocol=protocol,
            contract=contract,
            network_body_bytes_before=checkpoint.network_body_bytes,
        )
        evidence.append(item)
        checkpoint = build_checkpoint(
            started_at=started_at,
            updated_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol=protocol,
            contract_path=args.contract,
            contract=contract,
            target_evidence=tuple(evidence),
        )
        write_model_atomic(args.checkpoint, checkpoint, S1BtcAcquisitionCheckpointV2)
        print(
            f"CHECKPOINT {len(evidence)}/{protocol.target_count} "
            f"reuse={checkpoint.reused_target_count} "
            f"requests={checkpoint.network_request_count} "
            f"bytes={checkpoint.network_body_bytes} outcome={item.outcome}",
            flush=True,
        )
        if item.outcome == "FAILED":
            break
        time.sleep(protocol.polite_delay_milliseconds / 1000)
    result = build_result(
        checkpoint_path=args.checkpoint,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=datetime.now(UTC),
    )
    write_model_atomic(args.output, result, S1BtcSourceAcquisitionResultV2)
    print(
        f"COMPLETE {args.output} {result.result_evidence_hash} "
        f"decision={result.decision} targets={result.classified_target_count} "
        f"reuse={result.reused_target_count} requests={result.network_request_count} "
        f"prices={len(result.price_rows)} returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
