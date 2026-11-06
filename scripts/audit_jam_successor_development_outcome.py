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

from aurex.backtest_engine.jam_successor_development_outcome import (  # noqa: E402
    JamDevelopmentHorizonOutcome,
    JamMatchedControlRecord,
    JamSuccessorDevelopmentOutcomeAudit,
    JamSuccessorDevelopmentOutcomeExecutionProtocol,
    JamSuccessorDevelopmentOutcomeResult,
    audit_jam_successor_outcome_audit,
    audit_jam_successor_outcome_result,
    build_jam_successor_outcome_audit,
)
from scripts.freeze_jam_successor_development_outcome_protocol import (  # noqa: E402
    DEFAULT_DISTRIBUTION_PROTOCOL,
    DEFAULT_DISTRIBUTION_RESULT,
    DEFAULT_EVENT_LEDGER,
    DEFAULT_FEATURE_ROWS,
    DEFAULT_PARENT_EVENT_PROTOCOL,
    DEFAULT_PREVALENCE_AUDIT,
    DEFAULT_PREVALENCE_PROTOCOL,
    DEFAULT_PREVALENCE_RESULT,
    DEFAULT_QUALITY_RESULT,
    file_sha256,
)
from scripts.freeze_jam_successor_development_outcome_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_OUTCOME_PROTOCOL,
)
from scripts.run_jam_successor_development_outcome import (  # noqa: E402
    DEFAULT_CONTROL_LEDGER,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_OUTCOME_LEDGER,
    DEFAULT_OUTPUT,
    run_outcomes,
)

DEFAULT_AUDIT_OUTPUT = Path(
    "data/evidence/jam_successor_development_outcome_audit_v1.json"
)
DEFAULT_TEMP_ROOT = Path(
    ".tmp/jam_successor_development_outcome_independent_audit"
)


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam outcome audit temp root must remain under .tmp")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def _load_jsonl(path: Path, model_type) -> list:
    return [
        model_type.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_audit(
    path: Path,
    audit: JamSuccessorDevelopmentOutcomeAudit,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentOutcomeAudit.model_validate_json(serialized)
        != audit
    ):
        raise ValueError("Jam development outcome audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_audit(args) -> JamSuccessorDevelopmentOutcomeAudit:
    if args.output.exists():
        raise ValueError(f"Jam development outcome audit exists: {args.output}")
    protocol = JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = JamSuccessorDevelopmentOutcomeResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    controls = _load_jsonl(args.control_ledger, JamMatchedControlRecord)
    outcomes = _load_jsonl(args.outcome_ledger, JamDevelopmentHorizonOutcome)
    if (
        not audit_jam_successor_outcome_result(result)
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or file_sha256(args.control_ledger)
        != result.control_ledger_file_sha256
        or file_sha256(args.outcome_ledger)
        != result.outcome_ledger_file_sha256
        or len(controls) != result.control_ledger_record_count
        or len(outcomes) != result.outcome_ledger_record_count
    ):
        raise ValueError("Jam canonical development outcome evidence changed")
    audit_root = _validated_temp_root(args.temp_root)
    reconstructed_controls = audit_root / "controls.jsonl"
    reconstructed_outcomes = audit_root / "outcomes.jsonl"
    reconstructed_result = audit_root / "result.json"
    runner_temp = audit_root / "runner"
    generated_at = (
        result.generated_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    )
    runner_args = SimpleNamespace(
        protocol=args.protocol,
        parent_event_protocol=args.parent_event_protocol,
        prevalence_protocol=args.prevalence_protocol,
        prevalence_result=args.prevalence_result,
        prevalence_audit=args.prevalence_audit,
        event_ledger=args.event_ledger,
        feature_rows=args.feature_rows,
        distribution_protocol=args.distribution_protocol,
        distribution_result=args.distribution_result,
        quality_result=args.quality_result,
        evidence_root=args.evidence_root,
        control_ledger=reconstructed_controls,
        outcome_ledger=reconstructed_outcomes,
        output=reconstructed_result,
        temp_root=runner_temp,
        generated_at=generated_at,
    )
    try:
        reconstructed = run_outcomes(runner_args)
        if (
            reconstructed != result
            or reconstructed.result_evidence_hash != result.result_evidence_hash
            or file_sha256(reconstructed_result) != file_sha256(args.result)
            or reconstructed_controls.read_bytes()
            != args.control_ledger.read_bytes()
            or reconstructed_outcomes.read_bytes()
            != args.outcome_ledger.read_bytes()
        ):
            raise ValueError(
                "Jam independent development outcome reconstruction changed"
            )
        audit = build_jam_successor_outcome_audit(
            audited_at=datetime.now(UTC),
            protocol_path=args.protocol.as_posix(),
            protocol_file_sha256=file_sha256(args.protocol),
            protocol_evidence_hash=protocol.protocol_evidence_hash,
            result_path=args.result.as_posix(),
            result_file_sha256=file_sha256(args.result),
            result_evidence_hash=result.result_evidence_hash,
            control_ledger_path=args.control_ledger.as_posix(),
            control_ledger_file_sha256=result.control_ledger_file_sha256,
            outcome_ledger_path=args.outcome_ledger.as_posix(),
            outcome_ledger_file_sha256=result.outcome_ledger_file_sha256,
            matched_control_count_reconstructed=result.matched_control_count,
            outcome_ledger_record_count_reconstructed=(
                result.outcome_ledger_record_count
            ),
            primary_event_outcome_count_reconstructed=(
                result.primary_outcome_qualified_event_count
            ),
            matched_primary_pair_count_reconstructed=(
                result.matched_primary_pair_count
            ),
            passed_gate_count_reconstructed=result.passed_gate_count,
            failed_gate_count_reconstructed=result.failed_gate_count,
            decision=result.decision,
        )
        if not audit_jam_successor_outcome_audit(audit):
            raise ValueError("Jam development outcome audit failed internal audit")
        _write_audit(args.output, audit)
    finally:
        if audit_root.exists():
            shutil.rmtree(audit_root)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} "
        f"controls={audit.matched_control_count_reconstructed} "
        f"outcomes={audit.primary_event_outcome_count_reconstructed} "
        f"pairs={audit.matched_primary_pair_count_reconstructed} "
        f"gates={audit.passed_gate_count_reconstructed}/11 "
        "validation=False holdout=False strategy_executions=0",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Independently reconstruct and audit the frozen Jam successor "
            "2019-2020 development outcome decision."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_OUTCOME_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--control-ledger",
        type=Path,
        default=DEFAULT_CONTROL_LEDGER,
    )
    parser.add_argument(
        "--outcome-ledger",
        type=Path,
        default=DEFAULT_OUTCOME_LEDGER,
    )
    parser.add_argument(
        "--parent-event-protocol",
        type=Path,
        default=DEFAULT_PARENT_EVENT_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-protocol",
        type=Path,
        default=DEFAULT_PREVALENCE_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-result",
        type=Path,
        default=DEFAULT_PREVALENCE_RESULT,
    )
    parser.add_argument(
        "--prevalence-audit",
        type=Path,
        default=DEFAULT_PREVALENCE_AUDIT,
    )
    parser.add_argument(
        "--event-ledger",
        type=Path,
        default=DEFAULT_EVENT_LEDGER,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--distribution-protocol",
        type=Path,
        default=DEFAULT_DISTRIBUTION_PROTOCOL,
    )
    parser.add_argument(
        "--distribution-result",
        type=Path,
        default=DEFAULT_DISTRIBUTION_RESULT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
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
