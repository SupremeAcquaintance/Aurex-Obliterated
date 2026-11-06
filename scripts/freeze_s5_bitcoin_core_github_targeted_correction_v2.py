from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCompletenessCorrectionProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_execution import (  # noqa: E402
    S5_TARGETED_CORRECTION_STOP,
    S5TargetedCompletenessCorrectionResult,
    S5TargetedCorrectionExecutionContract,
    S5TargetedCorrectionExecutionContractAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_failure import (  # noqa: E402
    S5TargetedCorrectionV1FailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (  # noqa: E402
    S5TargetedCorrectionV2Protocol,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v2.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_targeted_correction_v2.py"
)
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_targeted_correction_v2.py")
V1_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
)
V1_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_protocol_audit_v1.json"
)
V1_EXECUTION_CONTRACT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v1.json"
)
V1_EXECUTION_CONTRACT_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v1.json"
)
V1_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v1.json"
)
V1_FAILURE_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v1_failure_audit_v1.json"
)
V1_ATTEMPT_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v1/pull_000010.attempt.json"
)
V1_FAILURE_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v1/failure_pull_000010.json"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(
            {
                "path": path.as_posix(),
                "file_sha256": file_sha256(PROJECT_ROOT / path),
            }
            for path in sorted((MODULE_PATH, SCRIPT_PATH), key=lambda item: item.as_posix())
        )
    )


def source_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                V1_PROTOCOL_PATH,
                V1_PROTOCOL_AUDIT_PATH,
                V1_EXECUTION_CONTRACT_PATH,
                V1_EXECUTION_CONTRACT_AUDIT_PATH,
                V1_RESULT_PATH,
                V1_FAILURE_AUDIT_PATH,
                V1_ATTEMPT_PATH,
                V1_FAILURE_PATH,
            ),
            key=lambda item: item.as_posix(),
        )
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in source_paths()
    )


def load_lineage() -> dict[str, object]:
    protocol = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        V1_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol_audit = S5TargetedCompletenessCorrectionProtocolAudit.model_validate_json(
        V1_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    contract = S5TargetedCorrectionExecutionContract.model_validate_json(
        V1_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract_audit = S5TargetedCorrectionExecutionContractAudit.model_validate_json(
        V1_EXECUTION_CONTRACT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5TargetedCompletenessCorrectionResult.model_validate_json(
        V1_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure_audit = S5TargetedCorrectionV1FailureAudit.model_validate_json(
        V1_FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    attempt = json.loads(V1_ATTEMPT_PATH.read_text(encoding="utf-8"))
    failure = json.loads(V1_FAILURE_PATH.read_text(encoding="utf-8"))
    changed = (
        protocol_audit.protocol_file_sha256 != file_sha256(V1_PROTOCOL_PATH)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract.protocol_evidence_hash != protocol.protocol_evidence_hash
        or contract_audit.contract_file_sha256
        != file_sha256(V1_EXECUTION_CONTRACT_PATH)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.decision != S5_TARGETED_CORRECTION_STOP
        or result.logical_request_attempt_count != 1
        or result.request_attempt_marker_count != 1
        or len(result.response_bindings) != 0
        or result.failure_type != "ResponseFailure"
        or failure_audit.result_file_sha256 != file_sha256(V1_RESULT_PATH)
        or failure_audit.result_evidence_hash != result.result_evidence_hash
        or failure_audit.attempt_marker_file_sha256 != file_sha256(V1_ATTEMPT_PATH)
        or failure_audit.failure_artifact_file_sha256 != file_sha256(V1_FAILURE_PATH)
        or failure_audit.attempted_pull_number != 10
        or not failure_audit.context_manager_defect_verified
        or not failure_audit.uncertain_get_may_have_reached_github
        or attempt.get("pull_number") != 10
        or failure.get("pull_number") != 10
        or failure.get("error", {}).get("type") != "TypeError"
        or failure.get("response", {}).get("http_status") is not None
        or failure.get("response", {}).get("body_byte_count") != 0
    )
    if changed:
        raise ValueError("S5 targeted v2 remediation lineage changed")
    return {
        "protocol": protocol,
        "protocol_audit": protocol_audit,
        "contract": contract,
        "contract_audit": contract_audit,
        "result": result,
        "failure_audit": failure_audit,
    }


def build_protocol(*, frozen_at: datetime) -> S5TargetedCorrectionV2Protocol:
    lineage = load_lineage()
    bindings = source_bindings()
    protocol = lineage["protocol"]
    protocol_audit = lineage["protocol_audit"]
    contract = lineage["contract"]
    contract_audit = lineage["contract_audit"]
    result = lineage["result"]
    failure_audit = lineage["failure_audit"]
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in bindings)
        ),
        "v1_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "v1_protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        "v1_execution_contract_evidence_hash": contract.contract_evidence_hash,
        "v1_execution_contract_audit_evidence_hash": contract_audit.audit_evidence_hash,
        "v1_result_evidence_hash": result.result_evidence_hash,
        "v1_failure_audit_evidence_hash": failure_audit.audit_evidence_hash,
        "target_manifest_evidence_hash": protocol.target_manifest_evidence_hash,
        "limitations": tuple(
            sorted(
                (
                    "The v1 pull-10 GET may have reached GitHub and is counted as uncertain.",
                    "V2 permits exactly one disclosed remedial GET for pull 10.",
                    "The other 193 targets have no prior targeted direct GET attempt.",
                    "At most 195 targeted GET attempts can exist cumulatively across v1 and v2.",
                    "The v1 result and raw failure artifacts remain immutable and binding.",
                    "The v2 response lifecycle must close the httpx response in a finally block.",
                    "A v2 uncertain attempt cannot be retried under this protocol.",
                    "HTTP 200 and 404 remain the only acceptable response statuses.",
                    "Current GitHub metadata may differ from metadata at the "
                    "historical event time.",
                    "No mapping rule or completeness threshold can change during v2 acquisition.",
                    "No accepted event or causal timestamp can be created during v2 acquisition.",
                    "Corrected normalization requires a later frozen and audited protocol.",
                    "No market value, return, parameter, candidate, signal, or order "
                    "is authorized.",
                    "Source completeness, predictive edge, reliability, and profit "
                    "remain unproven.",
                )
            )
        ),
    }
    provisional = S5TargetedCorrectionV2Protocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5TargetedCorrectionV2Protocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5TargetedCorrectionV2Protocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v2 protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v2 protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV2Protocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 targeted v2 protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 targeted v2 remediation.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV2Protocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v2 protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    if Path(protocol.result_path).exists():
        raise ValueError("S5 targeted v2 result already exists")
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
