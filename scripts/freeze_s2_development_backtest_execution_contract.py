from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2DevelopmentBacktestExecutionContract,
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestProtocolAudit,
)
from scripts.freeze_s2_development_backtest_protocol import file_sha256  # noqa: E402
from scripts.run_s2_development_backtest import (  # noqa: E402
    build_hashed,
    rooted,
    runner_contract_hash,
)

DEFAULT_PROTOCOL = Path("data/evidence/s2_development_backtest_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_development_backtest_protocol_audit_v1.json")
DEFAULT_OUTPUT = Path("data/evidence/s2_development_backtest_execution_contract_v1.json")
SYNTHETIC_TEST_IDS = (
    "agreement-only-position-rule",
    "entry-cost-before-market-return",
    "terminal-liquidation-cost",
    "cash-interval-no-cost-no-return",
    "peak-to-trough-maximum-drawdown",
    "interval-dollar-pnl-profit-factor",
    "sample-standard-deviation-weekly-sharpe",
    "zero-variance-sharpe-policy",
    "cagr-over-272-week-span",
    "calmar-zero-drawdown-policy",
    "stationary-bootstrap-constant-series",
    "stationary-bootstrap-seed-reproducibility",
    "all-cash-272-interval-simulation",
    "all-long-entry-and-terminal-fill-count",
    "measurement-price-alignment-rejection",
    "exact-fifteen-gate-mapping",
    "finite-and-infinite-metric-comparison",
)


def build_contract(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    frozen_at: datetime,
) -> S2DevelopmentBacktestExecutionContract:
    resolved_protocol = rooted(protocol_path)
    resolved_audit = rooted(protocol_audit_path)
    protocol = S2DevelopmentBacktestProtocol.model_validate_json(
        resolved_protocol.read_text(encoding="utf-8")
    )
    audit = S2DevelopmentBacktestProtocolAudit.model_validate_json(
        resolved_audit.read_text(encoding="utf-8")
    )
    measurement_path = rooted(protocol.measurement_dataset_path)
    price_path = rooted(protocol.price_dataset_path)
    output_paths = (
        rooted(protocol.outcome_ledger_path),
        rooted("data/evidence/s2_development_backtest_result_v1.json"),
        rooted("data/evidence/s2_development_backtest_result_audit_v1.json"),
    )
    if (
        file_sha256(resolved_protocol) != audit.protocol_file_sha256
        or protocol.protocol_evidence_hash != audit.protocol_evidence_hash
        or protocol.next_authorization
        != "AUTHORIZE_S2_DEVELOPMENT_BACKTEST_RUNNER_IMPLEMENTATION_ONLY"
        or protocol.authorizes_backtest_execution_now
        or not protocol.authorizes_runner_implementation
        or file_sha256(measurement_path) != protocol.measurement_dataset_file_sha256
        or file_sha256(price_path) != protocol.price_dataset_file_sha256
        or any(path.exists() for path in output_paths)
    ):
        raise ValueError("S2 development backtest execution boundary changed")
    return build_hashed(
        S2DevelopmentBacktestExecutionContract,
        "contract_evidence_hash",
        frozen_at=frozen_at,
        builder_contract_hash=file_sha256(Path(__file__)),
        protocol_file_sha256=file_sha256(resolved_protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        protocol_audit_file_sha256=file_sha256(resolved_audit),
        protocol_audit_evidence_hash=audit.audit_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        synthetic_test_ids=SYNTHETIC_TEST_IDS,
        measurement_dataset_file_sha256=file_sha256(measurement_path),
        price_dataset_file_sha256=file_sha256(price_path),
    )


def write_contract(path: Path, contract: S2DevelopmentBacktestExecutionContract) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest execution contract exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = contract.model_dump_json(indent=2) + "\n"
    if S2DevelopmentBacktestExecutionContract.model_validate_json(serialized) != contract:
        raise ValueError("S2 backtest execution contract did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest execution contract transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the one-shot S2 development backtest execution authority."
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
            protocol_path=args.protocol,
            protocol_audit_path=args.protocol_audit,
            frozen_at=datetime.now(UTC),
        )
        write_contract(args.output, contract)
        print(
            f"FROZEN {args.output} {contract.contract_evidence_hash} "
            f"runner={contract.runner_contract_hash} tests={len(contract.synthetic_test_ids)} "
            "measurements_parsed=0 prices_parsed=0 returns=0 outcomes=0 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
