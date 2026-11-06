from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5ReleaseTagSourceRemediationExecutionContractAuditV1,
    S5ReleaseTagSourceRemediationExecutionContractV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s5_release_tag_source_remediation_execution import (  # noqa: E402
    build_contract,
    builder_contract_hash,
    file_sha256,
)

DEFAULT_CONTRACT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_audit_v1.json"
)
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s5_release_tag_source_remediation_execution.py"
)


def build_hashed[ModelT: BaseModel](
    model: type[ModelT],
    hash_field: str,
    values: dict,
) -> ModelT:
    payload = dict(values)
    payload[hash_field] = "0" * 64
    preliminary = model.model_construct(**payload)
    payload[hash_field] = universe_evidence_hash(
        preliminary.model_dump(mode="json", exclude={hash_field})
    )
    return model.model_validate(payload)


def auditor_contract_bindings() -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted(
            (EXECUTION_MODULE_PATH, Path(__file__).resolve().relative_to(PROJECT_ROOT)),
            key=lambda path: path.as_posix(),
        )
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in auditor_contract_bindings())
    )


def build_audit(
    *,
    contract_path: Path,
    audited_at: datetime,
) -> S5ReleaseTagSourceRemediationExecutionContractAuditV1:
    contract = S5ReleaseTagSourceRemediationExecutionContractV1.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    if contract.builder_contract_hash != builder_contract_hash():
        raise ValueError("S5 release remediation execution builder changed")
    if build_contract(frozen_at=contract.frozen_at) != contract:
        raise ValueError(
            "S5 release remediation execution contract did not reconstruct exactly"
        )
    if any(
        not (PROJECT_ROOT / binding.path).is_file()
        or file_sha256(PROJECT_ROOT / binding.path) != binding.file_sha256
        for binding in (*contract.source_bindings, *contract.implementation_bindings)
    ):
        raise ValueError("S5 release remediation execution binding changed")
    auditor_bindings = auditor_contract_bindings()
    return build_hashed(
        S5ReleaseTagSourceRemediationExecutionContractAuditV1,
        "audit_evidence_hash",
        {
            "audited_at": audited_at,
            "contract_file_sha256": file_sha256(contract_path),
            "contract_evidence_hash": contract.contract_evidence_hash,
            "builder_contract_hash": contract.builder_contract_hash,
            "runner_contract_hash": contract.runner_contract_hash,
            "source_binding_manifest_evidence_hash": (
                contract.source_binding_manifest_evidence_hash
            ),
            "implementation_binding_manifest_evidence_hash": (
                contract.implementation_binding_manifest_evidence_hash
            ),
            "auditor_implementation_bindings": auditor_bindings,
            "auditor_contract_hash": auditor_contract_hash(),
        },
    )


def write_audit(
    path: Path,
    audit: S5ReleaseTagSourceRemediationExecutionContractAuditV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 release remediation execution audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S5ReleaseTagSourceRemediationExecutionContractAuditV1.model_validate_json(
        serialized
    ) != audit:
        raise ValueError("S5 release remediation execution audit did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the frozen S5 release-tag remediation execution contract."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--audit", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = (
                S5ReleaseTagSourceRemediationExecutionContractAuditV1.model_validate_json(
                    args.output.read_text(encoding="utf-8")
                )
            )
            expected = build_audit(
                contract_path=args.contract,
                audited_at=stored.audited_at,
            )
            if stored != expected:
                raise ValueError("Stored S5 release remediation execution audit changed")
            print(f"PASS {stored.audit_evidence_hash}", flush=True)
            return 0
        audit = build_audit(
            contract_path=args.contract,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            "discovery=0 copies=0 fetches=0 network=0 market_values=0 returns=0 "
            "orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
