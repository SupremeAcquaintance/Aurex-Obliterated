from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_STOP,
    S5TargetedCompletenessCorrectionResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_failure import (  # noqa: E402
    S5TargetedCorrectionV1FailureAudit,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_targeted_correction as runner,
)

DEFAULT_RESULT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v1_failure_audit_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_failure.py"
)
AUDITOR_PATH = Path(
    "scripts/audit_s5_bitcoin_core_github_targeted_correction_failure.py"
)
ATTEMPT_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v1/pull_000010.attempt.json"
)
FAILURE_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v1/failure_pull_000010.json"
)


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": runner.file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted((MODULE_PATH, AUDITOR_PATH), key=lambda item: item.as_posix())
        )
    )


def validate_failure_artifacts(
    *,
    result: S5TargetedCompletenessCorrectionResult,
    protocol,
) -> None:
    target = protocol.target_manifest[0]
    runner.validate_attempt_marker(
        path=ATTEMPT_PATH,
        protocol=protocol,
        target=target,
    )
    failure = json.loads(FAILURE_PATH.read_text(encoding="utf-8"))
    response = failure["response"]
    error = failure["error"]
    directory_files = {path.name for path in FAILURE_PATH.parent.iterdir() if path.is_file()}
    expected_files = {ATTEMPT_PATH.name, FAILURE_PATH.name}
    if (
        directory_files != expected_files
        or failure.get("schema_version") != runner.FAILURE_SCHEMA
        or failure.get("protocol_evidence_hash") != protocol.protocol_evidence_hash
        or failure.get("target_manifest_evidence_hash")
        != protocol.target_manifest_evidence_hash
        or failure.get("sequence") != 1
        or failure.get("pull_number") != 10
        or failure.get("request_attempt_count") != 1
        or response.get("http_status") is not None
        or response.get("final_url") is not None
        or response.get("headers") != {}
        or response.get("body_byte_count") != 0
        or response.get("body_sha256") != hashlib.sha256(b"").hexdigest()
        or error.get("type") != "TypeError"
        or error.get("message")
        != "'Response' object does not support the context manager protocol"
        or result.failure_artifact_path != FAILURE_PATH.as_posix()
        or result.failure_artifact_sha256 != runner.file_sha256(FAILURE_PATH)
    ):
        raise ValueError("S5 targeted v1 failure artifacts changed")


def build_audit(
    *, result_path: Path, audited_at: datetime
) -> S5TargetedCorrectionV1FailureAudit:
    protocol, protocol_audit, contract, contract_audit = runner.load_authorization()
    result = S5TargetedCompletenessCorrectionResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    validate_failure_artifacts(result=result, protocol=protocol)
    normalization, census = runner.load_local_lineage(protocol)
    inspection = runner.inspect_git(
        protocol=protocol,
        normalization=normalization,
        census=census,
    )
    changed = (
        result.decision != S5_TARGETED_CORRECTION_STOP
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.protocol_audit_evidence_hash != protocol_audit.audit_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.execution_contract_audit_evidence_hash
        != contract_audit.audit_evidence_hash
        or result.runner_contract_hash != runner.runner_contract_hash()
        or result.request_attempt_marker_count != 1
        or result.logical_request_attempt_count != 1
        or result.new_request_attempt_count != 1
        or result.resumed_response_count != 0
        or len(result.response_bindings) != 0
        or result.failure_type != "ResponseFailure"
        or "context manager protocol" not in str(result.failure_message)
        or inspection.full_graph_stream_sha256 != result.full_graph_stream_sha256
        or inspection.full_graph_commit_count != result.full_graph_commit_count
        or inspection.first_parent_commit_count != result.first_parent_commit_count
        or inspection.first_parent_merge_count != result.first_parent_merge_count
        or inspection.recognized_target_reachable_count
        != result.recognized_target_reachable_count
        or inspection.diagnostics != result.commit_diagnostics
        or result.btc_market_values_read != 0
        or result.returns_calculated != 0
        or result.orders_submitted != 0
    )
    if changed:
        raise ValueError("S5 targeted v1 failure result changed")
    payload = {
        "audited_at": audited_at,
        "result_file_sha256": runner.file_sha256(result_path),
        "result_evidence_hash": result.result_evidence_hash,
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "execution_contract_evidence_hash": contract.contract_evidence_hash,
        "execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "runner_contract_hash": result.runner_contract_hash,
        "auditor_contract_hash": auditor_contract_hash(),
        "attempt_marker_file_sha256": runner.file_sha256(ATTEMPT_PATH),
        "failure_artifact_file_sha256": runner.file_sha256(FAILURE_PATH),
    }
    provisional = S5TargetedCorrectionV1FailureAudit.model_construct(
        **payload, audit_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    return S5TargetedCorrectionV1FailureAudit.model_validate(complete)


def write_atomic(path: Path, audit: S5TargetedCorrectionV1FailureAudit) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v1 failure audit: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v1 failure audit: {temporary}")
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV1FailureAudit.model_validate_json(serialized) != audit:
        raise ValueError("S5 targeted v1 failure audit did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S5 targeted v1 failure.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV1FailureAudit.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_audit(result_path=args.result, audited_at=stored.audited_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v1 failure audit differs")
        print(f"PASS {stored.audit_evidence_hash}")
        return 0
    audit = build_audit(result_path=args.result, audited_at=datetime.now(UTC))
    write_atomic(args.output, audit)
    print(f"AUDITED {args.output} {audit.audit_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
