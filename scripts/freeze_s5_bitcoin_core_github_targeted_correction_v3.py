from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5TargetedCompletenessCorrectionProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (  # noqa: E402
    S5TargetedCorrectionV2Protocol,
    S5TargetedCorrectionV2ProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (  # noqa: E402
    S5TargetedCompletenessCorrectionResultV2,
    S5TargetedCorrectionV2ExecutionContract,
    S5TargetedCorrectionV2ExecutionContractAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_failure import (  # noqa: E402
    S5TargetedCorrectionV2FailureAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v3 import (  # noqa: E402
    S5TargetedCorrectionV3Protocol,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v3.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_bitcoin_core_github_targeted_correction_v3.py"
)
SCRIPT_PATH = Path("scripts/freeze_s5_bitcoin_core_github_targeted_correction_v3.py")
TARGET_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
)
V2_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v2.json"
)
V2_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_audit_v2.json"
)
V2_EXECUTION_CONTRACT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v2.json"
)
V2_EXECUTION_CONTRACT_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_audit_v2.json"
)
V2_RESULT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_result_v2.json"
)
V2_FAILURE_AUDIT_PATH = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_v2_failure_audit_v1.json"
)
ADOPTED_RESPONSE_PATH = Path(
    "data/evidence/s5_github_targeted_pull_responses_v2/failure_pull_000010.json"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                TARGET_PROTOCOL_PATH,
                V2_PROTOCOL_PATH,
                V2_PROTOCOL_AUDIT_PATH,
                V2_EXECUTION_CONTRACT_PATH,
                V2_EXECUTION_CONTRACT_AUDIT_PATH,
                V2_RESULT_PATH,
                V2_FAILURE_AUDIT_PATH,
                ADOPTED_RESPONSE_PATH,
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
    target = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        TARGET_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    v2 = S5TargetedCorrectionV2Protocol.model_validate_json(
        V2_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    v2_audit = S5TargetedCorrectionV2ProtocolAudit.model_validate_json(
        V2_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    contract = S5TargetedCorrectionV2ExecutionContract.model_validate_json(
        V2_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract_audit = S5TargetedCorrectionV2ExecutionContractAudit.model_validate_json(
        V2_EXECUTION_CONTRACT_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S5TargetedCompletenessCorrectionResultV2.model_validate_json(
        V2_RESULT_PATH.read_text(encoding="utf-8")
    )
    failure_audit = S5TargetedCorrectionV2FailureAudit.model_validate_json(
        V2_FAILURE_AUDIT_PATH.read_text(encoding="utf-8")
    )
    envelope = json.loads(ADOPTED_RESPONSE_PATH.read_text(encoding="utf-8"))
    body = base64.b64decode(envelope["response"]["body_base64"], validate=True)
    pull = json.loads(body)
    changed = (
        v2.v1_protocol_evidence_hash != target.protocol_evidence_hash
        or v2.target_manifest_evidence_hash != target.target_manifest_evidence_hash
        or v2_audit.protocol_file_sha256 != file_sha256(V2_PROTOCOL_PATH)
        or v2_audit.protocol_evidence_hash != v2.protocol_evidence_hash
        or contract.v2_protocol_evidence_hash != v2.protocol_evidence_hash
        or contract_audit.contract_file_sha256
        != file_sha256(V2_EXECUTION_CONTRACT_PATH)
        or contract_audit.contract_evidence_hash != contract.contract_evidence_hash
        or result.protocol_evidence_hash != v2.protocol_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or failure_audit.result_file_sha256 != file_sha256(V2_RESULT_PATH)
        or failure_audit.result_evidence_hash != result.result_evidence_hash
        or failure_audit.failure_artifact_file_sha256
        != file_sha256(ADOPTED_RESPONSE_PATH)
        or failure_audit.pull_number != 10
        or failure_audit.http_status != 200
        or failure_audit.merge_commit_sha_source_value != ""
        or envelope.get("pull_number") != 10
        or envelope.get("response", {}).get("http_status") != 200
        or envelope.get("response", {}).get("body_sha256")
        != hashlib.sha256(body).hexdigest()
        or pull.get("number") != 10
        or pull.get("merged") is not True
        or pull.get("merge_commit_sha") != ""
    )
    if changed:
        raise ValueError("S5 targeted v3 schema remediation lineage changed")
    return {
        "target": target,
        "v2": v2,
        "v2_audit": v2_audit,
        "contract": contract,
        "contract_audit": contract_audit,
        "result": result,
        "failure_audit": failure_audit,
        "body_hash": hashlib.sha256(body).hexdigest(),
    }


def build_protocol(*, frozen_at: datetime) -> S5TargetedCorrectionV3Protocol:
    lineage = load_lineage()
    bindings = source_bindings()
    target = lineage["target"]
    v2 = lineage["v2"]
    contract = lineage["contract"]
    result = lineage["result"]
    failure_audit = lineage["failure_audit"]
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": bindings,
        "source_binding_manifest_evidence_hash": universe_evidence_hash(
            tuple(binding.model_dump(mode="json") for binding in bindings)
        ),
        "target_protocol_evidence_hash": target.protocol_evidence_hash,
        "v2_protocol_evidence_hash": v2.protocol_evidence_hash,
        "v2_execution_contract_evidence_hash": contract.contract_evidence_hash,
        "v2_result_evidence_hash": result.result_evidence_hash,
        "v2_failure_audit_evidence_hash": failure_audit.audit_evidence_hash,
        "target_manifest_evidence_hash": target.target_manifest_evidence_hash,
        "adopted_response_file_sha256": file_sha256(ADOPTED_RESPONSE_PATH),
        "adopted_response_body_sha256": lineage["body_hash"],
        "limitations": tuple(
            sorted(
                (
                    "Pull 10 is adopted from the complete v2 HTTP 200 response artifact.",
                    "Pull 10 cannot be requested again under v3.",
                    "V3 permits requests only for the remaining 193 untouched targets.",
                    "Cumulative possible targeted GET attempts remain capped at 195.",
                    "Null, empty, and SHA-40 merge_commit_sha values remain distinct.",
                    "Allowing an empty source value does not infer a merge identity.",
                    "The corrected response lifecycle from v2 remains mandatory.",
                    "A v3 uncertain request cannot be retried under this protocol.",
                    "Current GitHub metadata may reflect post-event mutations.",
                    "No mapping or completeness rule can change during acquisition.",
                    "No response automatically creates an accepted event or timestamp.",
                    "Corrected normalization requires a later frozen protocol and audit.",
                    "No market value, return, parameter, candidate, signal, or order "
                    "is authorized.",
                    "Reliability, predictive edge, and profitability remain unproven.",
                )
            )
        ),
    }
    provisional = S5TargetedCorrectionV3Protocol.model_construct(
        **payload, protocol_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["protocol_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"protocol_evidence_hash"})
    )
    return S5TargetedCorrectionV3Protocol.model_validate(complete)


def write_atomic(path: Path, protocol: S5TargetedCorrectionV3Protocol) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v3 protocol: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v3 protocol transaction: {temporary}")
    serialized = protocol.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV3Protocol.model_validate_json(serialized) != protocol:
        raise ValueError("S5 targeted v3 protocol did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 targeted v3 remediation.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV3Protocol.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_protocol(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v3 protocol differs")
        print(f"PASS {stored.protocol_evidence_hash}")
        return 0
    protocol = build_protocol(frozen_at=datetime.now(UTC))
    if Path(protocol.result_path).exists():
        raise ValueError("S5 targeted v3 result already exists")
    write_atomic(args.output, protocol)
    print(f"FROZEN {args.output} {protocol.protocol_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
