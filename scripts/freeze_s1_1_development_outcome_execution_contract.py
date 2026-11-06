from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_development_outcome import (  # noqa: E402
    S11DevelopmentOutcomeProtocol,
    S11DevelopmentOutcomeProtocolAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S11DevelopmentOutcomeExecutionContract,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_1_development_outcome import (  # noqa: E402
    file_sha256,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_1_development_outcome_protocol_audit_v1.json"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/s1_1_development_outcome_execution_contract_v1.json"
)
BUILDER_PATH = Path("scripts/freeze_s1_1_development_outcome_execution_contract.py")
SYNTHETIC_TEST_IDS = (
    "outcome-protocol-zero-value-freeze",
    "primary-equality-is-cash",
    "primary-both-changes-negative",
    "cash-interval-zero-return",
    "initial-long-entry-cost",
    "long-to-cash-transition-cost",
    "terminal-long-liquidation-cost",
    "terminal-entry-two-fill-cost",
    "running-peak-maximum-drawdown",
    "interval-dollar-pnl-profit-factor",
    "stationary-bootstrap-constant-series",
    "stationary-bootstrap-seed-reproducibility",
    "finite-and-infinite-gate-comparison",
    "feature-evidence-hash-determinism",
    "nonpositive-interval-input-rejection",
)


def build_contract(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    frozen_at: datetime,
) -> S11DevelopmentOutcomeExecutionContract:
    protocol = S11DevelopmentOutcomeProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    audit = S11DevelopmentOutcomeProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    feature_path = PROJECT_ROOT / protocol.feature_dataset_path
    price_path = PROJECT_ROOT / protocol.price_dataset_path
    ledger_path = PROJECT_ROOT / protocol.outcome_ledger_path
    result_path = PROJECT_ROOT / "data/evidence/s1_1_development_outcome_result_v1.json"
    if (
        file_sha256(protocol_path) != audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != audit.protocol_evidence_hash
        or file_sha256(feature_path) != protocol.feature_dataset_file_sha256
        or file_sha256(price_path) != protocol.price_dataset_file_sha256
        or ledger_path.exists()
        or result_path.exists()
    ):
        raise ValueError("S1.1 outcome execution freeze boundary changed")
    payload = {
        "frozen_at": frozen_at,
        "builder_contract_hash": file_sha256(PROJECT_ROOT / BUILDER_PATH),
        "protocol_file_sha256": file_sha256(protocol_path),
        "protocol_evidence_hash": protocol.protocol_evidence_hash,
        "protocol_audit_file_sha256": file_sha256(protocol_audit_path),
        "protocol_audit_evidence_hash": audit.audit_evidence_hash,
        "runner_contract_hash": runner_contract_hash(),
        "synthetic_test_ids": SYNTHETIC_TEST_IDS,
        "feature_dataset_file_sha256": file_sha256(feature_path),
        "price_dataset_file_sha256": file_sha256(price_path),
    }
    provisional = S11DevelopmentOutcomeExecutionContract.model_construct(
        **payload,
        contract_evidence_hash="0" * 64,
    )
    complete = provisional.model_dump(mode="json")
    complete["contract_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={"contract_evidence_hash"})
    )
    return S11DevelopmentOutcomeExecutionContract.model_validate(complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze S1.1 outcome execution authority.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"S1.1 outcome execution contract exists: {args.output}")
    contract = build_contract(
        protocol_path=args.protocol,
        protocol_audit_path=args.protocol_audit,
        frozen_at=datetime.now(UTC),
    )
    temporary = args.output.with_name(f"{args.output.name}.part")
    temporary.write_text(contract.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(
        f"WROTE {args.output} {contract.contract_evidence_hash} "
        f"runner={contract.runner_contract_hash} tests={len(contract.synthetic_test_ids)} "
        "values=0 returns=0 outcomes=0 orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
