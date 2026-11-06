from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeExecutionAudit,
    S11DevelopmentOutcomeExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s1_1_development_outcome_execution_contract import (  # noqa: E402
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    build_contract,
)
from scripts.run_s1_1_development_outcome import file_sha256  # noqa: E402

DEFAULT_CONTRACT = Path(
    "data/evidence/s1_1_development_outcome_execution_contract_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_1_development_outcome_execution_audit_v1.json"
)
AUDITOR_PATH = Path("scripts/audit_s1_1_development_outcome_execution_contract.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit S1.1 outcome execution authority.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = S11DevelopmentOutcomeExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    reconstructed = build_contract(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        frozen_at=contract.frozen_at,
    )
    if reconstructed != contract:
        raise SystemExit("S1.1 outcome execution contract did not reconstruct")
    payload = {
        "audited_at": datetime.now(UTC),
        "contract_file_sha256": file_sha256(args.contract),
        "contract_evidence_hash": contract.contract_evidence_hash,
        "protocol_evidence_hash": contract.protocol_evidence_hash,
        "runner_contract_hash": contract.runner_contract_hash,
        "auditor_source_sha256": file_sha256(PROJECT_ROOT / AUDITOR_PATH),
        "synthetic_test_ids": contract.synthetic_test_ids,
    }
    provisional = S11DevelopmentOutcomeExecutionAudit.model_construct(
        **payload,
        audit_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["audit_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"audit_evidence_hash"})
    )
    audit = S11DevelopmentOutcomeExecutionAudit.model_validate(complete)
    if args.output.exists():
        raise SystemExit(f"S1.1 outcome execution audit exists: {args.output}")
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {audit.audit_evidence_hash} "
        f"contract={audit.contract_evidence_hash} tests={len(audit.synthetic_test_ids)} "
        "values=0 returns=0 outcomes=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
