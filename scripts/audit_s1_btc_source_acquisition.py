from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_acquisition import (  # noqa: E402
    S1BtcSourceAcquisitionProtocol,
)
from aurex.backtest_engine.s1_btc_source_execution import (  # noqa: E402
    S1BtcAcquisitionCheckpoint,
    S1BtcSourceAcquisitionResult,
    S1BtcSourceExecutionContract,
)
from aurex.backtest_engine.s1_btc_source_result_audit import (  # noqa: E402
    S1BtcSourceAcquisitionAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import (  # noqa: E402
    build_result,
    file_sha256,
    parse_checksum_text,
    project_path,
    target_evidence_from_files,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_btc_source_acquisition_protocol_v1.json")
DEFAULT_CONTRACT = Path("data/evidence/s1_btc_source_execution_contract_v1.json")
DEFAULT_CHECKPOINT = Path("data/evidence/s1_btc_source_acquisition_checkpoint_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_btc_source_acquisition_result_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s1_btc_source_acquisition_audit_v1.json")
AUDITOR_PATH = Path("scripts/audit_s1_btc_source_acquisition.py")


def diagnose_failed_target(
    protocol: S1BtcSourceAcquisitionProtocol,
    result: S1BtcSourceAcquisitionResult,
) -> dict:
    failed = [item for item in result.target_evidence if item.outcome == "FAILED"]
    if len(failed) != 1:
        raise ValueError("S1 BTC result does not contain one failed target")
    evidence = failed[0]
    target = protocol.targets[evidence.sequence - 1]
    archive_path = PROJECT_ROOT / target.archive_path
    checksum_path = PROJECT_ROOT / target.checksum_path
    published = parse_checksum_text(checksum_path.read_text(), archive_path.name)
    if file_sha256(archive_path) != published:
        raise ValueError("Failed S1 BTC target no longer matches its checksum")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != target.expected_member_name:
            raise ValueError("Failed S1 BTC target ZIP member policy changed")
        with archive.open(members[0]) as source:
            rows = list(csv.reader(io.TextIOWrapper(source, encoding="utf-8")))
    if not rows or any(len(row) != 12 for row in rows):
        raise ValueError("Failed S1 BTC target row width changed")
    open_times = [int(row[0]) for row in rows]
    if (
        len(open_times) != len(set(open_times))
        or open_times != sorted(open_times)
        or any(
            not target.activation_open_time_ms
            <= value
            < target.activation_open_time_ms + 86_400_000
            for value in open_times
        )
    ):
        raise ValueError("Failed S1 BTC target chronology changed")
    return {
        "failed_target_id": target.target_id,
        "failed_target_expected_open_time_ms": target.activation_open_time_ms,
        "failed_target_first_observed_open_time_ms": open_times[0],
        "failed_target_last_observed_open_time_ms": open_times[-1],
        "failed_target_observed_row_count": len(open_times),
        "failed_target_exact_open_occurrence_count": open_times.count(
            target.activation_open_time_ms
        ),
    }


def verify_checkpoint_sources_independently(
    checkpoint: S1BtcAcquisitionCheckpoint,
    *,
    protocol: S1BtcSourceAcquisitionProtocol,
    contract: S1BtcSourceExecutionContract,
) -> None:
    targets = protocol.targets[: checkpoint.classified_target_count]
    for target, evidence in zip(targets, checkpoint.target_evidence, strict=True):
        if target.sequence != evidence.sequence or target.target_id != evidence.target_id:
            raise ValueError("S1 BTC checkpoint target identity changed")
        for attempt in evidence.attempts:
            if (
                file_sha256(project_path(attempt.request_marker_path))
                != attempt.request_marker_sha256
                or file_sha256(project_path(attempt.response_marker_path))
                != attempt.response_marker_sha256
            ):
                raise ValueError("S1 BTC checkpoint marker hash changed")
        reconstructed = target_evidence_from_files(
            target,
            protocol=protocol,
            contract=contract,
            attempts=evidence.attempts,
            source_mode=evidence.source_mode,
        )
        if reconstructed != evidence:
            raise ValueError("S1 BTC checkpoint source evidence changed")


def build_audit(
    *,
    protocol_path: Path,
    protocol: S1BtcSourceAcquisitionProtocol,
    contract_path: Path,
    contract: S1BtcSourceExecutionContract,
    checkpoint_path: Path,
    checkpoint: S1BtcAcquisitionCheckpoint,
    result_path: Path,
    result: S1BtcSourceAcquisitionResult,
    audited_at: datetime,
) -> S1BtcSourceAcquisitionAudit:
    payload = {
        "audited_at": audited_at,
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "execution_contract_file_sha256": file_sha256(contract_path),
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "checkpoint_file_sha256": file_sha256(checkpoint_path),
        "checkpoint_evidence_hash": checkpoint.checkpoint_evidence_hash,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        **diagnose_failed_target(protocol, result),
    }
    provisional = S1BtcSourceAcquisitionAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S1BtcSourceAcquisitionAudit.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently reconstruct and diagnose the S1 BTC source result."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol = S1BtcSourceAcquisitionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    contract = S1BtcSourceExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    checkpoint = S1BtcAcquisitionCheckpoint.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = S1BtcSourceAcquisitionResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    verify_checkpoint_sources_independently(
        checkpoint,
        protocol=protocol,
        contract=contract,
    )
    reconstructed = build_result(
        checkpoint_path=args.checkpoint,
        checkpoint=checkpoint,
        protocol=protocol,
        completed_at=result.completed_at,
    )
    if reconstructed != result:
        raise SystemExit("S1 BTC acquisition result did not reconstruct exactly")
    audit = build_audit(
        protocol_path=args.protocol,
        protocol=protocol,
        contract_path=args.contract,
        contract=contract,
        checkpoint_path=args.checkpoint,
        checkpoint=checkpoint,
        result_path=args.result,
        result=result,
        audited_at=datetime.now(UTC),
    )
    if args.output.exists():
        raise SystemExit(f"S1 BTC acquisition audit exists: {args.output}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    temporary = args.output.with_name(f"{args.output.name}.part")
    if temporary.exists():
        raise SystemExit(f"Stale S1 BTC audit transaction exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} decision={audit.decision} "
        f"failed_target={audit.failed_target_id} first_open="
        f"{audit.failed_target_first_observed_open_time_ms} prices=0 returns=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
