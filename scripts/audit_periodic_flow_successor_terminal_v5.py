from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v5 import (  # noqa: E402
    PeriodicFlowInterleavedRowProbeV5,
    PeriodicFlowSuccessorTerminalAuditV5,
    audit_successor_terminal_audit_v5,
    build_successor_terminal_audit_v5,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v5 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV5,
    PeriodicFlowSuccessorCheckpointV5,
    audit_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
    target_archive_path,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    _attempt_path,
    marker_state_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v5 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    current_runner_source_hash_v5,
    load_context,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v5.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_terminal_audit_v5.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_successor_terminal_v5.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def _row_probe(archive_path: Path, member_name: str):
    with zipfile.ZipFile(archive_path) as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        if len(files) != 1 or files[0].filename != member_name:
            raise ValueError("Q1 successor v5 failed archive member changed")
        with archive.open(files[0]) as binary:
            rows = csv.reader(io.TextIOWrapper(binary, encoding="utf-8", newline=""))
            header = next(rows)
            if header != ["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"]:
                raise ValueError("Q1 successor v5 failed archive header changed")
            probe = []
            for ordinal in range(1, 7):
                row = next(rows)
                probe.append(
                    PeriodicFlowInterleavedRowProbeV5(
                        ordinal=ordinal,
                        primary_id=int(row[0]),
                        timestamp_ms=int(row[4]),
                    )
                )
    return tuple(probe)


def authoritative_audit(*, args, audited_at):
    context = load_context(args)
    checkpoint = PeriodicFlowSuccessorCheckpointV5.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV5.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_hash(result, "result_evidence_hash")
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.runner_source_hash != current_runner_source_hash_v5()
        or result.decision != "STOP_Q1_SUCCESSOR_ACQUISITION_INTEGRITY_FAILED"
        or result.hard_failure_target_key != "2023-01|USD_M_PERPETUAL"
        or result.hard_failure_reason is None
        or "primary_id_skipped_fraction" not in result.hard_failure_reason
        or "16867608.08325330886319725218" not in result.hard_failure_reason
        or len(checkpoint.archive_evidence) != 51
        or len(checkpoint.paired_month_evidence) != 17
        or len(checkpoint.excluded_month_evidence) != 8
    ):
        raise ValueError("Q1 successor v5 terminal lineage changed")
    target = next(
        item
        for item in context.protocol.targets
        if item.month == "2023-01" and item.product == "USD_M_PERPETUAL"
    )
    archive_path = target_archive_path(args.acquisition_root, target)
    request_path = _attempt_path(args.acquisition_root, target, 1, "request")
    response_path = _attempt_path(args.acquisition_root, target, 1, "response")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    response = json.loads(response_path.read_text(encoding="utf-8"))
    state = marker_state_v3(args.acquisition_root)
    if (
        request.get("target_key") != "2023-01|USD_M_PERPETUAL"
        or request.get("range_start") != 0
        or response.get("target_key") != "2023-01|USD_M_PERPETUAL"
        or response.get("status") != 200
        or response.get("outcome") != "PASS"
        or response.get("bytes_received") != 797_254_027
        or not archive_path.is_file()
        or archive_path.stat().st_size != 797_254_027
        or file_sha256(archive_path) != target.published_archive_sha256
        or state.request_count != 6
        or state.response_count != 6
        or state.payload_bytes_received != 5_260_608_134
        or state.manifest_hash != checkpoint.request_marker_manifest_hash
    ):
        raise ValueError("Q1 successor v5 terminal source evidence changed")
    probe = _row_probe(archive_path, target.expected_member_name)
    regressions = sum(
        current.primary_id < previous.primary_id
        for previous, current in zip(probe, probe[1:], strict=False)
    )
    timestamp_regressions = sum(
        current.timestamp_ms < previous.timestamp_ms
        for previous, current in zip(probe, probe[1:], strict=False)
    )
    return build_successor_terminal_audit_v5(
        audited_at=audited_at,
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        checkpoint_file_sha256=file_sha256(args.checkpoint),
        checkpoint_evidence_hash=checkpoint.checkpoint_evidence_hash,
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=context.protocol.protocol_evidence_hash,
        transport_amendment_file_sha256=file_sha256(args.amendment),
        transport_amendment_evidence_hash=context.protocol.amendment_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.execution_contract),
        execution_contract_evidence_hash=context.contract.contract_evidence_hash,
        execution_contract_audit_file_sha256=file_sha256(args.execution_contract_audit),
        execution_contract_audit_evidence_hash=context.contract_audit.audit_evidence_hash,
        runner_source_hash=current_runner_source_hash_v5(),
        auditor_contract_hash=auditor_contract_hash(),
        frozen_failure_reason=result.hard_failure_reason,
        failed_archive_relative_path=archive_path.resolve()
        .relative_to(args.evidence_root.resolve())
        .as_posix(),
        request_file_sha256=file_sha256(request_path),
        response_file_sha256=file_sha256(response_path),
        interleaved_row_probe=probe,
        probe_primary_id_regression_count=regressions,
        probe_timestamp_regression_count=timestamp_regressions,
        request_marker_manifest_hash=state.manifest_hash,
        findings=(
            "All six v5 request markers have exactly one matching response marker.",
            "The failed target transport completed with HTTP 200 and the exact published SHA-256.",
            "The first six data rows alternate between two distant ID and timestamp streams.",
            "The probe contains two primary-ID regressions and two timestamp regressions.",
            "Forward-gap accumulation is undefined once source row order is non-monotonic.",
            "The inherited evidence model rejected the resulting skipped fraction above one.",
            "The affected archive must be excluded whole rather than reordered or synthesized.",
            "A fresh validator continuation may reuse the checksum-verified terminal archive.",
            "No outcome, feature, parameter, or return was created; no strategy, "
            "signal, execution, or order exists.",
        ),
    )


def _write(path: Path, audit: PeriodicFlowSuccessorTerminalAuditV5) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v5 audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Q1 successor v5 validator stop.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    parser.add_argument("--amendment-audit", type=Path, default=DEFAULT_AMENDMENT_AUDIT)
    parser.add_argument(
        "--execution-contract", type=Path, default=DEFAULT_EXECUTION_CONTRACT
    )
    parser.add_argument(
        "--execution-contract-audit",
        type=Path,
        default=DEFAULT_EXECUTION_CONTRACT_AUDIT,
    )
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence"))
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTerminalAuditV5.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_successor_terminal_audit_v5(stored):
                raise ValueError("Stored Q1 successor v5 audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        _write(args.output, audit)
        print(f"AUDITED {args.output} {audit.audit_evidence_hash}", flush=True)
        return 0
    except (OSError, StopIteration, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
