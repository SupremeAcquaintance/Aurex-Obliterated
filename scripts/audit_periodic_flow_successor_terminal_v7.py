from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_successor_terminal_audit_v7 import (  # noqa: E402
    EXPECTED_EXCLUSION_REASON_COUNTS,
    PeriodicFlowSuccessorTerminalAuditV7,
    audit_successor_terminal_audit_v7,
    build_successor_terminal_audit_v7,
)
from aurex.backtest_engine.periodic_flow_successor_transport_v7 import (  # noqa: E402
    PeriodicFlowSuccessorAcquisitionResultV7,
    PeriodicFlowSuccessorCheckpointV7,
    audit_hash,
)
from scripts.run_periodic_flow_full_development_acquisition import (  # noqa: E402
    file_sha256,
    source_contract_hash,
)
from scripts.run_periodic_flow_successor_acquisition_v3 import (  # noqa: E402
    marker_state_v3,
    verify_checkpoint_archives_v3,
)
from scripts.run_periodic_flow_successor_acquisition_v7 import (  # noqa: E402
    DEFAULT_ACQUISITION_ROOT,
    DEFAULT_AMENDMENT,
    DEFAULT_AMENDMENT_AUDIT,
    DEFAULT_CHECKPOINT,
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_EXECUTION_CONTRACT,
    DEFAULT_EXECUTION_CONTRACT_AUDIT,
    DEFAULT_INHERITED_TRANSPORT_AMENDMENT,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    DEFAULT_V6_CHECKPOINT,
    DEFAULT_V6_RESULT,
    DEFAULT_V6_TERMINAL_AUDIT,
    DEFAULT_VALIDATOR_AMENDMENT,
    current_runner_source_hash_v7,
    load_context,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_successor_acquisition_terminal_audit_v7.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_successor_terminal_audit_v7.py"
)
SCRIPT_PATH = Path("scripts/audit_periodic_flow_successor_terminal_v7.py")


def auditor_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def _response_outcomes(root: Path) -> Counter[str]:
    outcomes: Counter[str] = Counter()
    for path in root.rglob("*.response.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        outcomes[payload["outcome"]] += 1
    return outcomes


def authoritative_audit(*, args, audited_at):
    context = load_context(args)
    checkpoint = PeriodicFlowSuccessorCheckpointV7.model_validate_json(
        args.checkpoint.read_text(encoding="utf-8")
    )
    result = PeriodicFlowSuccessorAcquisitionResultV7.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if (
        not audit_hash(checkpoint, "checkpoint_evidence_hash")
        or not audit_hash(result, "result_evidence_hash")
        or result.checkpoint_file_sha256 != file_sha256(args.checkpoint)
        or result.checkpoint_evidence_hash != checkpoint.checkpoint_evidence_hash
        or result.runner_source_hash != current_runner_source_hash_v7()
        or result.decision != "STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED"
        or result.next_authorization != "NONE_SOURCE_SUFFICIENCY_FAILED"
        or result.hard_failure_target_key is not None
        or result.hard_failure_reason is not None
    ):
        raise ValueError("Q1 successor v7 terminal lineage changed")
    verify_checkpoint_archives_v3(
        checkpoint=checkpoint, evidence_root=args.evidence_root
    )
    state = marker_state_v3(args.acquisition_root)
    outcomes = _response_outcomes(args.acquisition_root)
    reason_counts = Counter(
        reason
        for exclusion in checkpoint.excluded_month_evidence
        for reason in exclusion.reason_codes
    )
    stages = Counter(
        exclusion.failed_stage for exclusion in checkpoint.excluded_month_evidence
    )
    qualified_2023 = tuple(
        pair.month
        for pair in checkpoint.paired_month_evidence
        if pair.month.startswith("2023-")
    )
    classified = {
        pair.month for pair in checkpoint.paired_month_evidence
    } | {item.month for item in checkpoint.excluded_month_evidence}
    if (
        len(classified) != 37
        or len(checkpoint.archive_evidence) != 73
        or len(checkpoint.paired_month_evidence) != 19
        or len(checkpoint.excluded_month_evidence) != 18
        or qualified_2023 != ("2023-07", "2023-08")
        or dict(reason_counts) != EXPECTED_EXCLUSION_REASON_COUNTS
        or stages != Counter({"USDM_ARCHIVE": 17, "SPOT_ARCHIVE": 1})
        or state.request_count != 23
        or state.response_count != 23
        or state.payload_bytes_received != 10_171_727_846
        or state.manifest_hash != checkpoint.request_marker_manifest_hash
        or outcomes != Counter({"PASS": 17, "TRANSIENT": 6})
        or tuple(args.acquisition_root.rglob("*.part"))
    ):
        raise ValueError("Q1 successor v7 terminal corpus evidence changed")
    return build_successor_terminal_audit_v7(
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
        execution_contract_audit_file_sha256=file_sha256(
            args.execution_contract_audit
        ),
        execution_contract_audit_evidence_hash=(
            context.contract_audit.audit_evidence_hash
        ),
        runner_source_hash=current_runner_source_hash_v7(),
        auditor_contract_hash=auditor_contract_hash(),
        qualified_months_by_year=result.qualified_months_by_year,
        exclusion_reason_counts=dict(reason_counts),
        request_marker_manifest_hash=state.manifest_hash,
        findings=(
            "All 37 development months have exactly one terminal classification.",
            "All 73 inspected archives remain exact-size and SHA-256 verifiable.",
            "All 23 v7 request markers have exactly one matching response marker.",
            "The v7 evidence root contains no partial archive.",
            "Seventeen transport responses passed and six were bounded transients.",
            "Nineteen paired months qualified against a minimum requirement of thirty.",
            "The 2020 and 2023 per-year minimum of six qualified months failed.",
            "Twelve qualified quarters failed the requirement for all sixteen quarters.",
            "Only July and August qualified in 2023.",
            "Seventeen exclusions were USD-M archive failures and one was Spot.",
            "The original 100000000000-byte corpus limit was respected.",
            "No price, quantity, feature, parameter, return, or outcome was parsed.",
            "No strategy, signal, execution, paper authority, or order was created.",
            "Source insufficiency grants no measurement-protocol authorization.",
            "Real capital authority and real net profit remain zero.",
        ),
    )


def _write(path: Path, audit: PeriodicFlowSuccessorTerminalAuditV7) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite Q1 successor v7 audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    temporary.write_text(
        audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Q1 successor v7 stop.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument(
        "--validator-amendment", type=Path, default=DEFAULT_VALIDATOR_AMENDMENT
    )
    parser.add_argument(
        "--inherited-transport-amendment",
        type=Path,
        default=DEFAULT_INHERITED_TRANSPORT_AMENDMENT,
    )
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
    parser.add_argument("--v6-checkpoint", type=Path, default=DEFAULT_V6_CHECKPOINT)
    parser.add_argument("--v6-result", type=Path, default=DEFAULT_V6_RESULT)
    parser.add_argument(
        "--v6-terminal-audit", type=Path, default=DEFAULT_V6_TERMINAL_AUDIT
    )
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowSuccessorTerminalAuditV7.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_audit(args=args, audited_at=stored.audited_at)
            if stored != expected or not audit_successor_terminal_audit_v7(stored):
                raise ValueError("Stored Q1 successor v7 audit changed")
            print(f"PASS {args.output} {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = authoritative_audit(args=args, audited_at=datetime.now(UTC))
        _write(args.output, audit)
        print(f"AUDITED {args.output} {audit.audit_evidence_hash}", flush=True)
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
