from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_NEXT,
    S5_TARGETED_CORRECTION_PASS,
    S5TargetedCorrectionExecutionContract,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV3,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3_result_audit import (  # noqa: E402
    S5TargetedCorrectionV3ResultAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction as base,
)
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction_v3 as runner,
)

DEFAULT_RESULT = runner.DEFAULT_RESULT
DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_result_audit_v3.json"
)
V1_EXECUTION_CONTRACT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v1.json"
)
MODEL_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_v3_result_audit.py"
)
SCRIPT_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_targeted_correction_result_v3.py"
)
AUDITOR_IMPLEMENTATION_PATHS = (
    MODEL_PATH,
    SCRIPT_PATH,
    runner.RUNNER_PATH,
    runner.V2_RUNNER_PATH,
    base.RUNNER_PATH,
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(
            path=path.as_posix(),
            file_sha256=file_sha256(PROJECT_ROOT / path),
        )
        for path in sorted(AUDITOR_IMPLEMENTATION_PATHS, key=lambda item: item.as_posix())
    )


def manifest_hash(rows: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def verify_transitive_v1_runner() -> S5TargetedCorrectionExecutionContract:
    contract = S5TargetedCorrectionExecutionContract.model_validate_json(
        V1_EXECUTION_CONTRACT.read_text(encoding="utf-8")
    )
    if (
        not base.bindings_match(contract.source_bindings)
        or not base.bindings_match(contract.implementation_bindings)
        or base.runner_contract_hash() != contract.runner_contract_hash
    ):
        raise ValueError("S5 targeted transitive v1 runner lineage changed")
    return contract


def verify_raw_artifact_set(
    *, target_protocol, protocol
) -> tuple[S5HistoryBinding, ...]:
    response_directory = Path(protocol.raw_response_directory)
    expected_responses = {
        runner.response_path(protocol, target)
        for target in target_protocol.target_manifest[1:]
    }
    expected_markers = {
        runner.attempt_path(protocol, target)
        for target in target_protocol.target_manifest[1:]
    }
    observed = set(response_directory.glob("*.json"))
    if observed != expected_responses | expected_markers:
        raise ValueError("S5 targeted v3 raw artifact set changed")
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in sorted(expected_markers, key=lambda item: item.as_posix())
    )


def reconstruct(
    result_path: Path,
) -> tuple[
    S5TargetedCompletenessCorrectionResultV3,
    S5TargetedCorrectionExecutionContract,
    tuple[S5HistoryBinding, ...],
]:
    target, protocol, protocol_audit, contract, contract_audit = (
        runner.load_authorization()
    )
    v1_contract = verify_transitive_v1_runner()
    result = S5TargetedCompletenessCorrectionResultV3.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if (
        result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash
        != contract_audit.audit_evidence_hash
        or result.runner_contract_hash != runner.runner_contract_hash()
        or result.decision != S5_TARGETED_CORRECTION_PASS
        or result.next_authorization != S5_TARGETED_CORRECTION_NEXT
        or result.failed_gate_count != 0
        or result.failure_type is not None
        or result.failure_message is not None
        or result.failure_artifact_path is not None
        or result.failure_artifact_sha256 is not None
    ):
        raise ValueError("S5 targeted v3 result is not an auditable PASS")
    marker_bindings = verify_raw_artifact_set(
        target_protocol=target,
        protocol=protocol,
    )
    adopted = runner.load_adopted_response(
        target_protocol=target,
        protocol=protocol,
    )
    v3_responses = runner.load_existing_responses(
        target_protocol=target,
        protocol=protocol,
    )
    if len(v3_responses) != 193:
        raise ValueError("S5 targeted v3 response count changed")
    normalization, census = base.load_local_lineage(target)
    git_inspection = base.inspect_git(
        protocol=target,
        normalization=normalization,
        census=census,
    )
    reconstructed = runner.build_result(
        target_protocol=target,
        protocol=protocol,
        protocol_audit=protocol_audit,
        contract=contract,
        contract_audit=contract_audit,
        git_inspection=git_inspection,
        responses=[adopted, *v3_responses],
        started_at=result.started_at,
        completed_at=result.completed_at,
        resumed_v3_response_count=(
            result.resumed_response_count - result.adopted_response_count
        ),
        new_request_attempt_count=result.new_request_attempt_count,
        rate_limit_wait_count=result.rate_limit_wait_count,
        rate_limit_wait_seconds=result.rate_limit_wait_seconds,
        failure_type=None,
        failure_message=None,
        failure_artifact_path=None,
    )
    if reconstructed != result:
        raise ValueError("S5 targeted v3 result differs from reconstruction")
    return result, v1_contract, marker_bindings


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5TargetedCorrectionV3ResultAudit:
    result, v1_contract, marker_bindings = reconstruct(result_path)
    implementation = implementation_bindings()
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": result.protocol_evidence_hash,
        "protocol_audit_evidence_hash": result.protocol_audit_evidence_hash,
        "execution_contract_evidence_hash": (
            result.execution_contract_evidence_hash
        ),
        "execution_contract_audit_evidence_hash": (
            result.execution_contract_audit_evidence_hash
        ),
        "runner_contract_hash": result.runner_contract_hash,
        "transitive_v1_execution_contract_evidence_hash": (
            v1_contract.contract_evidence_hash
        ),
        "transitive_v1_runner_contract_hash": v1_contract.runner_contract_hash,
        "auditor_implementation_bindings": implementation,
        "auditor_contract_hash": manifest_hash(implementation),
        "response_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(row.model_dump(mode="json") for row in result.response_bindings)
        ),
        "v3_request_marker_manifest_evidence_hash": manifest_hash(marker_bindings),
        "full_graph_stream_sha256": result.full_graph_stream_sha256,
        "http_200_count": result.http_200_count,
        "http_404_count": result.http_404_count,
        "empty_merge_commit_sha_response_count": (
            result.empty_merge_commit_sha_response_count
        ),
        "total_response_bytes": result.total_response_bytes,
    }
    provisional = S5TargetedCorrectionV3ResultAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5TargetedCorrectionV3ResultAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5TargetedCorrectionV3ResultAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v3 result audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v3 result-audit transaction: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV3ResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 targeted v3 result audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit the S5 targeted v3 result."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = S5TargetedCorrectionV3ResultAudit.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = build_audit(
                result_path=args.result,
                audited_at=stored.audited_at,
            )
            if stored != expected:
                raise ValueError("Stored S5 targeted v3 result audit changed")
            print(f"PASS {stored.audit_evidence_hash}")
            return 0
        audit = build_audit(
            result_path=args.result,
            audited_at=datetime.now(UTC),
        )
        write_atomic(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"responses={audit.response_count} http_200={audit.http_200_count} "
            f"http_404={audit.http_404_count} "
            f"empty_merge_sha={audit.empty_merge_commit_sha_response_count} "
            "github_requests=0 market_values=0 returns=0 orders=0"
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
