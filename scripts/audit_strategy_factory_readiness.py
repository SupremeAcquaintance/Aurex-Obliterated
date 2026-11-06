from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.strategy_factory_readiness import (  # noqa: E402
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessProtocol,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_protocol,
    audit_readiness_result,
    build_readiness_audit,
    file_sha256,
)
from scripts.run_strategy_factory_readiness import (  # noqa: E402
    build_result,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path(
    "data/evidence/aurex_strategy_factory_readiness_protocol_v1.json"
)
DEFAULT_RESULT = Path(
    "data/evidence/aurex_strategy_factory_readiness_baseline_result_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/aurex_strategy_factory_readiness_baseline_audit_v1.json"
)


def write_audit(path: Path, audit: StrategyFactoryReadinessAudit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if StrategyFactoryReadinessAudit.model_validate_json(serialized) != audit:
        raise ValueError("Strategy-factory readiness audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional readiness audit exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def run(args) -> StrategyFactoryReadinessAudit:
    if args.output.exists():
        raise ValueError(f"Strategy-factory readiness audit exists: {args.output}")
    protocol = StrategyFactoryReadinessProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    result = StrategyFactoryReadinessResult.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    if not audit_readiness_protocol(protocol) or not audit_readiness_result(result):
        raise ValueError("Canonical strategy-factory readiness evidence changed")
    if (
        result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.runner_contract_hash != runner_contract_hash()
    ):
        raise ValueError("Strategy-factory readiness lineage changed")

    reconstructed = build_result(
        protocol=protocol,
        evaluated_at=result.evaluated_at,
    )
    if reconstructed != result:
        raise ValueError("Independent strategy-factory readiness result changed")

    audit = build_readiness_audit(
        audited_at=datetime.now(UTC),
        protocol_path=args.protocol.as_posix(),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        result_path=args.result.as_posix(),
        result_file_sha256=file_sha256(args.result),
        result_evidence_hash=result.result_evidence_hash,
        runner_contract_hash=result.runner_contract_hash,
        strategy_research_ready=result.strategy_research_ready,
        decision=result.decision,
    )
    if not audit_readiness_audit(audit):
        raise ValueError("Strategy-factory readiness audit failed internal audit")
    write_audit(args.output, audit)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"result={audit.result_evidence_hash} "
        f"gates={audit.reconstructed_gate_count} "
        f"research_ready={audit.strategy_research_ready} "
        f"decision={audit.decision} strategies=0 orders=0",
        flush=True,
    )
    return audit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Independently reconstruct the Aurex strategy-factory readiness result."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        run(parse_args())
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
