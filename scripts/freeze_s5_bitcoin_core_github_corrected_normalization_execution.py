from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    S5GitHubCorrectedNormalizationProtocolAuditV2,
    S5GitHubCorrectedNormalizationProtocolV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_corrected_normalization_execution import (  # noqa: E402
    S5GitHubCorrectedNormalizationExecutionContractV2,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts import (  # noqa: E402
    run_s5_bitcoin_core_github_corrected_normalization as runner,
)
from scripts.freeze_s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PROTOCOL,
)
from scripts.freeze_s5_bitcoin_core_github_corrected_normalization import (  # noqa: E402
    file_sha256,
)

DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_protocol_audit_v2.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/"
    "s5_bitcoin_core_github_corrected_normalization_execution_contract_v2.json"
)
SCRIPT_PATH = Path(
    "scripts/freeze_s5_bitcoin_core_github_corrected_normalization_execution.py"
)


def bindings(paths: tuple[Path, ...]) -> tuple[S5HistoryBinding, ...]:
    return tuple(
        S5HistoryBinding(
            path=path.as_posix(),
            file_sha256=file_sha256(PROJECT_ROOT / path),
        )
        for path in sorted(paths, key=lambda item: item.as_posix())
    )


def manifest_hash(rows: tuple[S5HistoryBinding, ...]) -> str:
    return universe_evidence_hash(
        tuple(row.model_dump(mode="json") for row in rows)
    )


def source_bindings() -> tuple[S5HistoryBinding, ...]:
    return bindings((DEFAULT_PROTOCOL, DEFAULT_PROTOCOL_AUDIT))


def runner_implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    return bindings(runner.RUNNER_IMPLEMENTATION_PATHS)


def implementation_bindings() -> tuple[S5HistoryBinding, ...]:
    return bindings((*runner.RUNNER_IMPLEMENTATION_PATHS, SCRIPT_PATH))


def builder_contract_hash() -> str:
    return manifest_hash(implementation_bindings())


def runner_contract_hash() -> str:
    return manifest_hash(runner_implementation_bindings())


def load_protocol() -> tuple[
    S5GitHubCorrectedNormalizationProtocolV2,
    S5GitHubCorrectedNormalizationProtocolAuditV2,
]:
    protocol = S5GitHubCorrectedNormalizationProtocolV2.model_validate_json(
        DEFAULT_PROTOCOL.read_text(encoding="utf-8")
    )
    audit = S5GitHubCorrectedNormalizationProtocolAuditV2.model_validate_json(
        DEFAULT_PROTOCOL_AUDIT.read_text(encoding="utf-8")
    )
    if (
        audit.protocol_file_sha256 != file_sha256(DEFAULT_PROTOCOL)
        or audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or any(
            file_sha256(PROJECT_ROOT / row.path) != row.file_sha256
            for row in protocol.source_bindings
        )
    ):
        raise ValueError("S5 corrected execution protocol lineage changed")
    return protocol, audit


def build_contract(
    *, frozen_at: datetime
) -> S5GitHubCorrectedNormalizationExecutionContractV2:
    protocol, audit = load_protocol()
    sources = source_bindings()
    implementation = implementation_bindings()
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": builder_contract_hash(),
        "source_bindings": sources,
        "source_binding_manifest_evidence_hash": manifest_hash(sources),
        "implementation_bindings": implementation,
        "implementation_binding_manifest_evidence_hash": manifest_hash(implementation),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
    }
    provisional = S5GitHubCorrectedNormalizationExecutionContractV2.model_construct(
        **payload,
        contract_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S5GitHubCorrectedNormalizationExecutionContractV2.model_validate(complete)


def write_atomic(
    path: Path,
    contract: S5GitHubCorrectedNormalizationExecutionContractV2,
) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite S5 corrected execution contract: {path}")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S5 corrected execution contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S5GitHubCorrectedNormalizationExecutionContractV2.model_validate_json(
        serialized
    ) != contract:
        raise ValueError("S5 corrected execution contract did not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S5 corrected execution v2.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        stored = S5GitHubCorrectedNormalizationExecutionContractV2.model_validate_json(
            args.output.read_text(encoding="utf-8")
        )
        expected = build_contract(frozen_at=stored.frozen_at)
        if stored != expected:
            raise SystemExit("Stored S5 corrected execution contract differs")
        print(f"PASS {stored.contract_evidence_hash}")
        return 0
    contract = build_contract(frozen_at=datetime.now(UTC))
    if Path(contract.result_path).exists():
        raise ValueError("S5 corrected normalization result already exists")
    write_atomic(args.output, contract)
    print(f"FROZEN {args.output} {contract.contract_evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
