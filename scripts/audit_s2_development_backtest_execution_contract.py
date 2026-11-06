from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2DevelopmentBacktestExecutionAudit,
    S2DevelopmentBacktestExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s2_development_backtest_execution_contract import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    build_contract,
)
from scripts.freeze_s2_development_backtest_protocol import file_sha256  # noqa: E402
from scripts.run_s2_development_backtest import build_hashed, rooted  # noqa: E402

DEFAULT_CONTRACT = Path("data/evidence/s2_development_backtest_execution_contract_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_backtest_execution_audit_v1.json")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "auditor_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "auditor_sha256": file_sha256(Path(__file__)),
        }
    )


def build_audit(
    *,
    contract_path: Path,
    contract: S2DevelopmentBacktestExecutionContract,
    audited_at: datetime,
) -> S2DevelopmentBacktestExecutionAudit:
    return build_hashed(
        S2DevelopmentBacktestExecutionAudit,
        "audit_evidence_hash",
        audited_at=audited_at,
        contract_file_sha256=file_sha256(contract_path),
        contract_evidence_hash=contract.contract_evidence_hash,
        protocol_evidence_hash=contract.protocol_evidence_hash,
        runner_contract_hash=contract.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        synthetic_test_ids=contract.synthetic_test_ids,
    )


def write_audit(path: Path, audit: S2DevelopmentBacktestExecutionAudit) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest execution audit exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S2DevelopmentBacktestExecutionAudit.model_validate_json(serialized) != audit:
        raise ValueError("S2 backtest execution audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest execution audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S2 backtest execution authority.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        contract_path = rooted(args.contract)
        contract = S2DevelopmentBacktestExecutionContract.model_validate_json(
            contract_path.read_text(encoding="utf-8")
        )
        reconstructed = build_contract(
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            frozen_at=contract.frozen_at,
        )
        if reconstructed != contract:
            raise ValueError("S2 backtest execution contract did not reconstruct")
        audit = build_audit(
            contract_path=contract_path,
            contract=contract,
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"contract={audit.contract_evidence_hash} tests={len(audit.synthetic_test_ids)} "
            "measurements_parsed=0 prices_parsed=0 returns=0 outcomes=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
