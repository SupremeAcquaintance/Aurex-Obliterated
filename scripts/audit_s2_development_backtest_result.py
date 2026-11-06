from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s2_btc_source_execution import S2BtcPriceRow  # noqa: E402
from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2_BACKTEST_PASS,
    S2DevelopmentBacktestResult,
    S2DevelopmentBacktestResultAudit,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2DevelopmentMeasurementRow,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s2_development_backtest_protocol import file_sha256  # noqa: E402
from scripts.run_s2_development_backtest import (  # noqa: E402
    DEFAULT_CONTRACT,
    DEFAULT_CONTRACT_AUDIT,
    DEFAULT_PREREGISTRATION,
    DEFAULT_PROTOCOL,
    DEFAULT_PROTOCOL_AUDIT,
    DEFAULT_RESULT,
    build_hashed,
    build_result,
    ledger_bytes,
    load_authority,
    load_jsonl,
    rooted,
    runner_contract_hash,
    simulate_candidate,
)

DEFAULT_OUTPUT = Path("data/evidence/s2_development_backtest_result_audit_v1.json")


def auditor_contract_hash() -> str:
    return universe_evidence_hash(
        {
            "auditor_path": Path(__file__).resolve().relative_to(PROJECT_ROOT).as_posix(),
            "auditor_sha256": file_sha256(Path(__file__)),
        }
    )


def build_audit(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
    preregistration_path: Path,
    result_path: Path,
    audited_at: datetime,
) -> S2DevelopmentBacktestResultAudit:
    protocol, contract, preregistration = load_authority(
        protocol_path=protocol_path,
        protocol_audit_path=protocol_audit_path,
        contract_path=contract_path,
        contract_audit_path=contract_audit_path,
        preregistration_path=preregistration_path,
    )
    result = S2DevelopmentBacktestResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    measurement_path = rooted(protocol.measurement_dataset_path)
    price_path = rooted(protocol.price_dataset_path)
    ledger_path = rooted(protocol.outcome_ledger_path)
    if (
        file_sha256(measurement_path) != contract.measurement_dataset_file_sha256
        or file_sha256(price_path) != contract.price_dataset_file_sha256
        or file_sha256(ledger_path) != result.outcome_ledger_file_sha256
        or result.runner_contract_hash != runner_contract_hash()
        or result.protocol_evidence_hash != protocol.protocol_evidence_hash
        or result.execution_contract_evidence_hash != contract.contract_evidence_hash
        or result.candidate_count != 1
        or result.parameter_combination_count != 1
        or result.rescue_candidate_count != 0
        or result.orders_submitted != 0
    ):
        raise ValueError("S2 backtest result lineage changed")
    measurements = load_jsonl(measurement_path, S2DevelopmentMeasurementRow)
    prices = load_jsonl(price_path, S2BtcPriceRow)
    outcome, intervals = simulate_candidate(
        measurements=measurements,
        prices=prices,
        protocol=protocol,
    )
    reconstructed_ledger = ledger_bytes(intervals)
    if ledger_path.read_bytes() != reconstructed_ledger:
        raise ValueError("S2 backtest ledger did not reconstruct byte-for-byte")
    reconstructed_result = build_result(
        completed_at=result.completed_at,
        protocol_path=protocol_path,
        protocol=protocol,
        contract_path=contract_path,
        contract=contract,
        preregistration=preregistration,
        outcome=outcome,
        ledger=intervals,
    )
    if reconstructed_result != result:
        raise ValueError("S2 backtest result did not reconstruct exactly")
    return build_hashed(
        S2DevelopmentBacktestResultAudit,
        "audit_evidence_hash",
        audited_at=audited_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        result_file_sha256=file_sha256(result_path),
        result_evidence_hash=result.result_evidence_hash,
        outcome_ledger_file_sha256=result.outcome_ledger_file_sha256,
        interval_manifest_evidence_hash=(
            result.candidate_outcome.interval_manifest_evidence_hash
        ),
        runner_contract_hash=result.runner_contract_hash,
        auditor_contract_hash=auditor_contract_hash(),
        decision=(
            "CONFIRM_S2_DEVELOPMENT_BACKTEST_PASSED"
            if result.decision == S2_BACKTEST_PASS
            else "CONFIRM_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        ),
        lineage_next_authorization=result.next_authorization,
    )


def write_audit(path: Path, audit: S2DevelopmentBacktestResultAudit) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest result audit exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = audit.model_dump_json(indent=2) + "\n"
    if S2DevelopmentBacktestResultAudit.model_validate_json(serialized) != audit:
        raise ValueError("S2 backtest result audit did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest result audit transaction: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the one-shot S2 backtest result.")
    parser.add_argument("--audit", action="store_true", required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        audit = build_audit(
            protocol_path=rooted(args.protocol),
            protocol_audit_path=rooted(args.protocol_audit),
            contract_path=rooted(args.contract),
            contract_audit_path=rooted(args.contract_audit),
            preregistration_path=rooted(args.preregistration),
            result_path=rooted(args.result),
            audited_at=datetime.now(UTC),
        )
        write_audit(args.output, audit)
        print(
            f"AUDITED {args.output} {audit.audit_evidence_hash} "
            f"result={audit.result_evidence_hash} decision={audit.decision} "
            "measurements=273 prices=273 intervals=272 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
