from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.periodic_flow_full_development_acquisition import (  # noqa: E402
    PeriodicFlowFullDevelopmentProtocol,
    PeriodicFlowFullDevelopmentProtocolAudit,
    audit_full_development_protocol,
    audit_full_development_protocol_audit,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (  # noqa: E402
    RUNNER_SOURCE_PATHS,
    PeriodicFlowExecutionContract,
    audit_execution_contract,
    build_execution_contract,
    source_contract_hash,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402

DEFAULT_PROTOCOL = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/q1_periodic_flow_full_development_acquisition_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/q1_periodic_flow_full_development_execution_contract_v1.json"
)
MODULE_PATH = Path(
    "src/aurex/backtest_engine/periodic_flow_full_development_runner.py"
)
SCRIPT_PATH = Path(
    "scripts/freeze_periodic_flow_full_development_execution_contract.py"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def builder_contract_hash() -> str:
    return source_contract_hash(PROJECT_ROOT, (MODULE_PATH, SCRIPT_PATH))


def authoritative_contract(
    *,
    frozen_at: datetime,
    protocol_path: Path = DEFAULT_PROTOCOL,
    protocol_audit_path: Path = DEFAULT_PROTOCOL_AUDIT,
) -> PeriodicFlowExecutionContract:
    protocol = PeriodicFlowFullDevelopmentProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = PeriodicFlowFullDevelopmentProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    if (
        not audit_full_development_protocol(protocol)
        or not audit_full_development_protocol_audit(protocol_audit)
        or protocol_audit.protocol_file_sha256 != file_sha256(protocol_path)
        or protocol_audit.protocol_evidence_hash != protocol.protocol_evidence_hash
    ):
        raise ValueError("Q1 parent acquisition authority changed")
    processing_order = [
        {"month": target.month, "product": target.product}
        for target in sorted(protocol.targets, key=lambda item: item.key)
    ]
    return build_execution_contract(
        frozen_at=frozen_at,
        parent_protocol_file_sha256=file_sha256(protocol_path),
        parent_protocol_evidence_hash=protocol.protocol_evidence_hash,
        parent_protocol_audit_file_sha256=file_sha256(protocol_audit_path),
        parent_protocol_audit_evidence_hash=protocol_audit.audit_evidence_hash,
        builder_contract_hash=builder_contract_hash(),
        runner_source_hash=source_contract_hash(PROJECT_ROOT, RUNNER_SOURCE_PATHS),
        processing_manifest_hash=universe_evidence_hash(
            {"processing_order": processing_order}
        ),
        limitations=(
            "The addendum narrows transport behavior and never expands the parent protocol.",
            "Targets execute in chronological month order with Spot before USD-M raw trades.",
            "The first target, pair, integrity, budget, or resource failure stops later work.",
            "A missing or changed reuse candidate cannot fall back to the network.",
            "Every network attempt is a full GET preceded by an immutable request marker.",
            "HEAD, redirect, range, concurrent, and partial-resume behavior remains forbidden.",
            "Interrupted partial bytes are counted, recorded, deleted, and never parsed.",
            "Only an exact-hash completed destination may be recovered after interruption.",
            "All received bytes count against the same conservative 100 GB ceiling.",
            "Preflight requires the 100 GB ceiling plus the 20 GB remaining-disk reserve.",
            "Only IDs, timestamps, maker booleans, and archive structure may be inspected.",
            "Prices, quantities, features, returns, outcomes, and parameters remain sealed.",
            "No Pine, paper, Testnet strategy-order, production, or live authority is created.",
        ),
    )


def write_contract(path: Path, contract: PeriodicFlowExecutionContract) -> None:
    if path.exists():
        raise ValueError(f"Refusing to overwrite execution contract: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale execution-contract transaction: {temporary}")
    serialized = contract.model_dump_json(indent=2) + "\n"
    if PeriodicFlowExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("Q1 execution contract did not round-trip")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze or check the Q1 full-development execution addendum."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.check:
            stored = PeriodicFlowExecutionContract.model_validate_json(
                args.output.read_text(encoding="utf-8")
            )
            expected = authoritative_contract(
                frozen_at=stored.frozen_at,
                protocol_path=args.protocol,
                protocol_audit_path=args.protocol_audit,
            )
            if stored != expected or not audit_execution_contract(stored):
                raise ValueError("Stored Q1 execution contract changed")
            print(
                f"PASS {args.output} {stored.contract_evidence_hash} "
                "requests=0 outcomes=0 orders=0",
                flush=True,
            )
            return 0
        contract = authoritative_contract(
            frozen_at=datetime.now(UTC),
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
        )
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            "requests=0 outcomes=0 orders=0",
            flush=True,
        )
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

