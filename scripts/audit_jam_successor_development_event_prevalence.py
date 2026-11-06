from __future__ import annotations

import argparse
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_event_prevalence import (  # noqa: E402
    JamDevelopmentEventLedgerRecord,
    JamSuccessorDevelopmentEventPrevalenceAudit,
    JamSuccessorDevelopmentEventPrevalenceProtocol,
    JamSuccessorDevelopmentEventPrevalenceResult,
    audit_jam_successor_prevalence_audit,
    audit_jam_successor_prevalence_result,
    build_jam_successor_prevalence_audit,
    validate_event_ledger,
)
from scripts.freeze_jam_successor_event_prevalence_protocol import (  # noqa: E402
    DEFAULT_FEATURE_ROWS,
    DEFAULT_PARENT_AUDIT,
    DEFAULT_PARENT_PROTOCOL,
    file_sha256,
)
from scripts.freeze_jam_successor_event_prevalence_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PREVALENCE_PROTOCOL,
)
from scripts.run_jam_successor_development_event_prevalence import (  # noqa: E402
    DEFAULT_EVENT_LEDGER,
    DEFAULT_OUTPUT,
    run_prevalence,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/jam_successor_development_event_prevalence_audit_v1.json"
)
DEFAULT_TEMP_ROOT = Path(
    ".tmp/jam_successor_development_event_prevalence_independent_audit"
)


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam prevalence audit temp root must remain under .tmp")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def _load_ledger(
    path: Path,
) -> list[JamDevelopmentEventLedgerRecord]:
    return [
        JamDevelopmentEventLedgerRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_audit(
    path: Path,
    audit: JamSuccessorDevelopmentEventPrevalenceAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentEventPrevalenceAudit.model_validate_json(
            serialized
        )
        != audit
    ):
        raise ValueError("Jam prevalence audit JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_audit(args) -> JamSuccessorDevelopmentEventPrevalenceAudit:
    if args.output.exists():
        raise ValueError(f"Jam prevalence audit already exists: {args.output}")
    protocol = JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = JamSuccessorDevelopmentEventPrevalenceResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    ledger = _load_ledger(args.event_ledger)
    validate_event_ledger(ledger, conditions=protocol.event_conditions)
    if (
        not audit_jam_successor_prevalence_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or file_sha256(args.event_ledger)
        != result.event_ledger_file_sha256
        or len(ledger) != result.event_ledger_record_count
    ):
        raise ValueError("Jam canonical prevalence evidence changed")
    audit_root = _validated_temp_root(args.temp_root)
    reconstructed_ledger_path = audit_root / "event_ledger.jsonl"
    reconstructed_result_path = audit_root / "result.json"
    generated_at = (
        result.generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    )
    runner_args = SimpleNamespace(
        protocol=args.protocol,
        parent_protocol=args.parent_protocol,
        parent_audit=args.parent_audit,
        feature_rows=args.feature_rows,
        event_ledger=reconstructed_ledger_path,
        output=reconstructed_result_path,
        generated_at=generated_at,
    )
    try:
        reconstructed = run_prevalence(runner_args)
        reconstructed_result_hash = file_sha256(reconstructed_result_path)
        canonical_result_hash = file_sha256(args.result)
        if (
            reconstructed != result
            or reconstructed.result_evidence_hash
            != result.result_evidence_hash
            or reconstructed_result_hash != canonical_result_hash
            or file_sha256(reconstructed_ledger_path)
            != result.event_ledger_file_sha256
            or reconstructed_ledger_path.read_bytes()
            != args.event_ledger.read_bytes()
        ):
            raise ValueError("Jam independent prevalence reconstruction changed")
        audit = build_jam_successor_prevalence_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol.as_posix(),
            protocol_file_sha256=file_sha256(args.protocol),
            protocol_evidence_hash=protocol.protocol_evidence_hash,
            result_path=args.result.as_posix(),
            result_file_sha256=canonical_result_hash,
            result_evidence_hash=result.result_evidence_hash,
            event_ledger_path=args.event_ledger.as_posix(),
            event_ledger_file_sha256=result.event_ledger_file_sha256,
            event_ledger_record_count_reconstructed=(
                result.event_ledger_record_count
            ),
            raw_event_count_reconstructed=result.raw_event_count,
            accepted_event_count_reconstructed=result.accepted_event_count,
            suppressed_event_count_reconstructed=result.suppressed_event_count,
            passed_gate_count_reconstructed=result.passed_gate_count,
            failed_gate_count_reconstructed=result.failed_gate_count,
            decision=result.decision,
        )
        if not audit_jam_successor_prevalence_audit(audit):
            raise ValueError("Jam prevalence audit failed internal audit")
        _write_audit(args.output, audit)
    finally:
        if audit_root.exists():
            shutil.rmtree(audit_root)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} "
        f"raw={audit.raw_event_count_reconstructed} "
        f"accepted={audit.accepted_event_count_reconstructed} "
        f"suppressed={audit.suppressed_event_count_reconstructed} "
        "validation=False holdout=False labels=0 returns=0",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently reconstruct and audit the Jam successor 2019-2020 "
            "event-prevalence result without outcomes or returns."
        )
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=DEFAULT_PREVALENCE_PROTOCOL,
    )
    parser.add_argument("--result", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--event-ledger",
        type=Path,
        default=DEFAULT_EVENT_LEDGER,
    )
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    return parser.parse_args()


def main() -> int:
    try:
        run_audit(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
