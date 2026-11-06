from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s5_bitcoin_core_history_payload import (  # noqa: E402
    S5HistoryBinding,
)
from aurex.backtest_engine.s5_release_tag_source_remediation import (  # noqa: E402
    S5_RELEASE_REMEDIATION_AUDIT_DECISION,
    S5_RELEASE_REMEDIATION_NEXT,
    S5ReleaseTagSourceRemediationProtocolAuditV1,
    S5ReleaseTagSourceRemediationProtocolV1,
)
from aurex.backtest_engine.s5_release_tag_source_remediation_execution import (  # noqa: E402
    S5ReleaseTagSourceRemediationExecutionContractV1,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s5_release_tag_source_remediation import (  # noqa: E402
    EXECUTION_MODULE_PATH,
    implementation_bindings,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s5_release_tag_source_remediation_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s5_release_tag_source_remediation_execution_contract_v1.json"
)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def builder_contract_bindings() -> tuple[S5HistoryBinding, ...]:
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


def builder_contract_hash() -> str:
    return universe_evidence_hash(
        tuple(item.model_dump(mode="json") for item in builder_contract_bindings())
    )


def source_bindings(
    protocol_path: Path,
    protocol_audit_path: Path,
) -> tuple[S5HistoryBinding, ...]:
    paths = tuple(
        sorted((protocol_path, protocol_audit_path), key=lambda path: path.as_posix())
    )
    return tuple(
        S5HistoryBinding(path=path.as_posix(), file_sha256=file_sha256(path))
        for path in paths
    )


def build_contract(
    *,
    frozen_at: datetime,
    protocol_path: Path = DEFAULT_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_PROTOCOL_AUDIT,
) -> S5ReleaseTagSourceRemediationExecutionContractV1:
    protocol = S5ReleaseTagSourceRemediationProtocolV1.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S5ReleaseTagSourceRemediationProtocolAuditV1.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        protocol.next_authorization != S5_RELEASE_REMEDIATION_NEXT
        or not protocol.authorizes_runner_implementation
        or protocol.authorizes_tag_discovery_now
        or protocol.authorizes_repository_copy_now
        or protocol.authorizes_tag_fetch_now
        or protocol_audit.decision != S5_RELEASE_REMEDIATION_AUDIT_DECISION
        or protocol_audit.protocol_file_sha256 != file_sha256(protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
        or protocol_audit.builder_contract_hash != protocol.builder_contract_hash
    ):
        raise ValueError("S5 release remediation execution predecessor lineage changed")
    sources = source_bindings(protocol_path, protocol_audit_path)
    implementations = implementation_bindings()
    return build_hashed(
        S5ReleaseTagSourceRemediationExecutionContractV1,
        "contract_evidence_hash",
        {
            "frozen_at": frozen_at,
            "builder_contract_hash": builder_contract_hash(),
            "source_bindings": sources,
            "source_binding_manifest_evidence_hash": universe_evidence_hash(
                tuple(item.model_dump(mode="json") for item in sources)
            ),
            "implementation_bindings": implementations,
            "implementation_binding_manifest_evidence_hash": runner_contract_hash(),
            "runner_contract_hash": runner_contract_hash(),
            "protocol_evidence_hash": protocol.protocol_evidence_hash,
            "protocol_audit_evidence_hash": protocol_audit.audit_evidence_hash,
        },
    )


def write_contract(
    path: Path,
    contract: S5ReleaseTagSourceRemediationExecutionContractV1,
) -> None:
    if path.exists():
        raise ValueError(f"S5 release remediation execution contract already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S5ReleaseTagSourceRemediationExecutionContractV1.model_validate_json(
        serialized
    ) != contract:
        raise ValueError("S5 release remediation execution contract did not round-trip")
    path.write_text(serialized, encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the S5 release-tag remediation execution contract."
    )
    parser.add_argument("--freeze", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        contract = build_contract(
            frozen_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
        )
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            "discovery=0 copies=0 fetches=0 network=0 market_values=0 returns=0 "
            "candidates=0 signals=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
