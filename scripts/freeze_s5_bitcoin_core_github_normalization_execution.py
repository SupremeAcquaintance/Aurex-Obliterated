from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_normalization import (  # noqa: E402
    S5_GITHUB_NORMALIZATION_NEXT,
    S5GitHubNormalizationProtocol,
    S5GitHubNormalizationProtocolAudit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_normalization_execution import (  # noqa: E402
    S5GitHubNormalizationExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_bitcoin_core_github_normalization import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_s5_bitcoin_core_github_normalization import (  # noqa: E402
    file_sha256,
)
from scripts.run_s5_bitcoin_core_github_normalization import (  # noqa: E402
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    EXECUTION_MODULE_PATH,
    runner_contract_hash,
)

DEFAULT_OUTPUT = Path(
    "data/evidence/s5_bitcoin_core_github_normalization_execution_contract_v1.json"
)
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_normalization_execution.py"
)
SYNTHETIC_TEST_IDS = (
    "NORMALIZE_PULL_REQUIRED_SCHEMA",
    "NULL_ACTOR_EXPLICIT_UNKNOWN",
    "BOT_TYPE_CLASSIFIED",
    "BOT_SUFFIX_CLASSIFIED",
    "GIT_PARENT_STREAM_TOPOLOGY",
    "GIT_PARENT_STREAM_REJECTS_INVALID_SHA",
    "RECOGNIZED_NUMBER_AND_HEAD_SHA_EXACT",
    "UNRECOGNIZED_HEAD_SHA_RECOVERY",
    "UNRESOLVED_MERGE_PRESERVED",
    "REVERSE_COVERAGE_FAILURE_DETECTED",
    "AMBIGUOUS_HEAD_FAILURE_DETECTED",
    "DETERMINISTIC_JSONL_SERIALIZATION",
)


def builder_contract_hash() -> str:
    paths = (EXECUTION_MODULE_PATH, SCRIPT_PATH)
    return universe_evidence_hash(
        tuple(
            {"path": path.as_posix(), "file_sha256": file_sha256(PROJECT_ROOT / path)}
            for path in paths
        )
    )


def load_protocol() -> tuple[
    S5GitHubNormalizationProtocol,
    S5GitHubNormalizationProtocolAudit,
]:
    protocol = S5GitHubNormalizationProtocol.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    audit = S5GitHubNormalizationProtocolAudit.model_validate_json(
        DEFAULT_PROTOCOL_AUDIT.read_text(encoding="utf-8")
    )
    if (
        audit.protocol_file_sha256 != file_sha256(DEFAULT_PROTOCOL)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or audit.next_authorization != S5_GITHUB_NORMALIZATION_NEXT
    ):
        raise ValueError("S5 normalization execution protocol lineage changed")
    return protocol, audit


def build_contract(*, frozen_at: datetime) -> S5GitHubNormalizationExecutionContract:
    protocol, audit = load_protocol()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "protocol_file_sha256": file_sha256(DEFAULT_PROTOCOL),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(DEFAULT_PROTOCOL_AUDIT),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "synthetic_test_ids": SYNTHETIC_TEST_IDS,
    }
    provisional = S5GitHubNormalizationExecutionContract.model_construct(
        **payload, contract_evidence_hash="0" * 64
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S5GitHubNormalizationExecutionContract.model_validate(complete)


def output_paths(protocol: S5GitHubNormalizationProtocol) -> tuple[Path, ...]:
    return (
        Path(protocol.pull_output_path),
        Path(protocol.mapping_output_path),
        Path(protocol.unresolved_output_path),
        DEFAULT_RESULT,
    )


def ensure_outputs_absent(protocol: S5GitHubNormalizationProtocol) -> None:
    existing = tuple(
        path.as_posix()
        for path in output_paths(protocol)
        if path.exists() or path.with_name(f"{path.name}.part").exists()
    )
    if existing:
        raise ValueError(f"S5 normalization outputs already exist: {existing}")


def write_atomic(
    path: Path, contract: S5GitHubNormalizationExecutionContract
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 normalization contract: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 normalization contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S5GitHubNormalizationExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("S5 normalization execution contract did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or check the S5 normalization execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5GitHubNormalizationExecutionContract.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_contract(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 normalization execution contract differs")
        print(f"PASS {stored.contract_evidence_hash}")
        return 0
    protocol, _audit = load_protocol()
    ensure_outputs_absent(protocol)
    contract = build_contract(frozen_at=datetime.now(UTC))
    write_atomic(args.output, contract)
    print(f"FROZEN {args.output} {contract.contract_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
