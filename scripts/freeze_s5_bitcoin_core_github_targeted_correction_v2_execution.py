from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction import (  # noqa: E402
    S5TargetedCompletenessCorrectionProtocol,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2 import (  # noqa: E402
    S5_TARGETED_V2_RUN,
    S5TargetedCorrectionV2Protocol,
    S5TargetedCorrectionV2ProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_targeted_correction_v2_execution import (  # noqa: E402
    S5TargetedCorrectionV2ExecutionContract,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_targeted_correction_execution_contract_v2.json"
)
TARGET_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v1.json"
)
V2_PROTOCOL_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_v2.json"
)
V2_PROTOCOL_AUDIT_PATH = Path(
    "data/evidence/s5_bitcoin_core_github_targeted_correction_protocol_audit_v2.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/"
    "s5_bitcoin_core_github_targeted_correction_v2_execution.py"
)
RUNNER_PATH = Path("scripts/run_s5_bitcoin_core_github_targeted_correction_v2.py")
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_targeted_correction_v2_execution.py"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def bindings(paths: tuple[Path, ...]) -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(PROJECT_ROOT / path))
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def manifest_hash(rows: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return bindings((TARGET_PROTOCOL_PATH, V2_PROTOCOL_PATH, V2_PROTOCOL_AUDIT_PATH))


def implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    return bindings((EXECUTION_MODULE_PATH, RUNNER_PATH, SCRIPT_PATH))


def builder_contract_hash() -> str:
    return manifest_hash(implementation_bindings())


def runner_contract_hash() -> str:
    return manifest_hash(bindings((EXECUTION_MODULE_PATH, RUNNER_PATH)))


def load_protocols() -> tuple[
    S5TargetedCompletenessCorrectionProtocol,
    S5TargetedCorrectionV2Protocol,
    S5TargetedCorrectionV2ProtocolAudit,
]:
    target = S5TargetedCompletenessCorrectionProtocol.model_validate_json(
        TARGET_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    protocol = S5TargetedCorrectionV2Protocol.model_validate_json(
        V2_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    audit = S5TargetedCorrectionV2ProtocolAudit.model_validate_json(
        V2_PROTOCOL_AUDIT_PATH.read_text(encoding="utf-8")
    )
    changed = (
        protocol.v1_protocol_evidence_hash != target.protocol_evidence_hash
        or protocol.target_manifest_evidence_hash
        != target.target_manifest_evidence_hash
        or protocol.next_authorization != S5_TARGETED_V2_RUN
        or audit.protocol_file_sha256 != file_sha256(V2_PROTOCOL_PATH)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.target_manifest_evidence_hash
        != target.target_manifest_evidence_hash
        or any(
            file_sha256(PROJECT_ROOT / row.path) != row.file_sha256
            for row in protocol.source_bindings
        )
    )
    if changed:
        raise ValueError("S5 targeted v2 execution predecessor lineage changed")
    return target, protocol, audit


def build_contract(
    *, frozen_at: datetime
) -> S5TargetedCorrectionV2ExecutionContract:
    target, protocol, audit = load_protocols()
    sources = source_bindings()
    implementation = implementation_bindings()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": sources,
        "source_binding_manifest_evidence_hash": manifest_hash(sources),
        "implementation_bindings": implementation,
        "implementation_binding_manifest_evidence_hash": manifest_hash(implementation),
        "v1_target_protocol_evidence_hash": target.protocol_evidence_hash,
        "v2_protocol_file_sha256": file_sha256(V2_PROTOCOL_PATH),
        "v2_protocol_evidence_hash": protocol.protocol_evidence_hash,
        "v2_protocol_audit_file_sha256": file_sha256(V2_PROTOCOL_AUDIT_PATH),
        "v2_protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "target_manifest_evidence_hash": target.target_manifest_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
    }
    provisional = S5TargetedCorrectionV2ExecutionContract.model_construct(
        **payload, contract_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S5TargetedCorrectionV2ExecutionContract.model_validate(complete)


def write_atomic(
    path: Path, contract: S5TargetedCorrectionV2ExecutionContract
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 targeted v2 contract: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 targeted v2 contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S5TargetedCorrectionV2ExecutionContract.model_validate_json(
        serialized
    ) != contract:
        raise ValueError("S5 targeted v2 execution contract did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 targeted v2 execution.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5TargetedCorrectionV2ExecutionContract.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_contract(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 targeted v2 execution contract differs")
        print(f"PASS {stored.contract_evidence_hash}")
        return 0
    contract = build_contract(frozen_at=datetime.now(UTC))
    if Path(contract.result_path).exists():
        raise ValueError("S5 targeted v2 result already exists")
    write_atomic(args.output, contract)
    print(f"FROZEN {args.output} {contract.contract_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
