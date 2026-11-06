from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, getcontext
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.s1_btc_source_execution_v2 import (  # noqa: E402
    S1BtcPriceRowV2,
)
from aurex.backtest_engine.s1_development_outcome import (  # noqa: E402
    S11DevelopmentOutcomeProtocol,
    S11DevelopmentOutcomeProtocolAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (  # noqa: E402
    S1_1_OUTCOME_PASS,
    S1_1_OUTCOME_STOP,
    S11CandidateOutcome,
    S11DevelopmentGateResult,
    S11DevelopmentOutcomeExecutionAudit,
    S11DevelopmentOutcomeExecutionContract,
    S11DevelopmentOutcomeResult,
    S11IntervalOutcome,
)
from aurex.backtest_engine.s1_nfci_feature_execution import (  # noqa: E402
    S1NfciFeatureRow,
)
from aurex.backtest_engine.s1_strategy_preregistration import (  # noqa: E402
    S1StrategyCandidate,
    S1StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.run_s1_btc_source_acquisition import file_sha256  # noqa: E402

getcontext().prec = 60

DEFAULT_PROTOCOL = Path("data/evidence/s1_1_development_outcome_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path(
    "data/evidence/s1_1_development_outcome_protocol_audit_v1.json"
)
DEFAULT_CONTRACT = Path(
    "data/evidence/s1_1_development_outcome_execution_contract_v1.json"
)
DEFAULT_CONTRACT_AUDIT = Path(
    "data/evidence/s1_1_development_outcome_execution_audit_v1.json"
)
DEFAULT_PREREGISTRATION = Path("data/evidence/s1_strategy_preregistration_v1.json")
DEFAULT_RESULT = Path("data/evidence/s1_1_development_outcome_result_v1.json")
EXECUTION_MODULE_PATH = Path(
    "src/aurex/backtest_engine/s1_development_outcome_execution.py"
)
RUNNER_PATH = Path("scripts/run_s1_1_development_outcome.py")


def runner_contract_hash() -> str:
    return universe_evidence_hash(
        {
            EXECUTION_MODULE_PATH.as_posix(): file_sha256(
                PROJECT_ROOT / EXECUTION_MODULE_PATH
            ),
            RUNNER_PATH.as_posix(): file_sha256(PROJECT_ROOT / RUNNER_PATH),
        }
    )


def build_hashed(model_type, hash_field: str, **payload):
    provisional = model_type.model_construct(**payload, **{hash_field: "0" * 64})
    complete = provisional.model_dump(mode="json")
    complete[hash_field] = universe_evidence_hash(
        provisional.model_dump(mode="json", exclude={hash_field})
    )
    return model_type.model_validate(complete)


def load_jsonl(path: Path, model_type) -> tuple:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                rows.append(model_type.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"Invalid {path} row {line_number}") from exc
    return tuple(rows)


def feature_evidence_hash(row: S1NfciFeatureRow) -> str:
    return universe_evidence_hash(row.model_dump(mode="json"))


def desired_position(feature: S1NfciFeatureRow, candidate: S1StrategyCandidate) -> int:
    level = Decimal(feature.nfci_level)
    change_1v = Decimal(feature.nfci_change_1v)
    change_4v = Decimal(feature.nfci_change_4v)
    rules = {
        "NFCI_CHANGE_1V_LT_0_AND_NFCI_CHANGE_4V_LT_0": (
            change_1v < 0 and change_4v < 0
        ),
        "NFCI_CHANGE_1V_LT_0": change_1v < 0,
        "NFCI_CHANGE_4V_LT_0": change_4v < 0,
        "NFCI_LEVEL_LT_0_AND_NFCI_CHANGE_4V_LT_0": (
            level < 0 and change_4v < 0
        ),
    }
    if candidate.long_rule not in rules:
        raise ValueError(f"Unknown frozen S1.1 candidate rule: {candidate.long_rule}")
    return int(rules[candidate.long_rule])


def apply_interval(
    *,
    equity: Decimal,
    current_position: int,
    desired: int,
    current_price: Decimal,
    next_price: Decimal,
    cost_bps: Decimal,
    terminal: bool,
) -> tuple[Decimal, Decimal, bool, bool]:
    if equity <= 0 or current_price <= 0 or next_price <= 0:
        raise ValueError("S1.1 interval requires positive equity and prices")
    before = equity
    entry_fill = desired != current_position
    if entry_fill:
        equity *= Decimal(1) - cost_bps / Decimal(10_000)
    if desired == 1:
        equity *= next_price / current_price
    terminal_fill = terminal and desired == 1
    if terminal_fill:
        equity *= Decimal(1) - cost_bps / Decimal(10_000)
    return equity, equity / before - Decimal(1), entry_fill, terminal_fill


def maximum_drawdown(equities: tuple[Decimal, ...]) -> Decimal:
    if not equities or equities[0] <= 0:
        raise ValueError("S1.1 drawdown requires a positive equity curve")
    peak = equities[0]
    maximum = Decimal(0)
    for equity in equities:
        if equity > peak:
            peak = equity
        decline = (peak - equity) / peak
        if decline > maximum:
            maximum = decline
    return maximum


def profit_factor(pnls: tuple[Decimal, ...]) -> str:
    gains = sum((value for value in pnls if value > 0), Decimal(0))
    losses = -sum((value for value in pnls if value < 0), Decimal(0))
    if losses == 0:
        return "Infinity" if gains > 0 else "0"
    return str(gains / losses)


def stationary_bootstrap_lower_mean(
    returns: tuple[Decimal, ...],
    *,
    resamples: int,
    restart_probability: Decimal,
    seed: int,
    order_index: int,
) -> Decimal:
    if not returns or not 0 <= order_index < resamples:
        raise ValueError("S1.1 bootstrap configuration is invalid")
    rng = random.Random(seed)
    probability = float(restart_probability)
    length = len(returns)
    means: list[Decimal] = []
    for _ in range(resamples):
        index = rng.randrange(length)
        total = Decimal(0)
        for offset in range(length):
            total += returns[index]
            if offset == length - 1:
                continue
            if rng.random() < probability:
                index = rng.randrange(length)
            else:
                index = (index + 1) % length
        means.append(total / Decimal(length))
    means.sort()
    return means[order_index]


def simulate_candidate(
    *,
    features: tuple[S1NfciFeatureRow, ...],
    prices: tuple[S1BtcPriceRowV2, ...],
    candidate: S1StrategyCandidate,
    protocol: S11DevelopmentOutcomeProtocol,
) -> tuple[S11CandidateOutcome, tuple[S11IntervalOutcome, ...]]:
    if len(features) != 277 or len(prices) != 277:
        raise ValueError("S1.1 simulation requires 277 aligned rows")
    base_equity = Decimal(protocol.initial_equity_usd)
    stress_equity = Decimal(protocol.initial_equity_usd)
    base_curve = [base_equity]
    stress_curve = [stress_equity]
    base_pnls: list[Decimal] = []
    stress_pnls: list[Decimal] = []
    base_returns: list[Decimal] = []
    stress_returns: list[Decimal] = []
    annual_factors: dict[int, Decimal] = defaultdict(lambda: Decimal(1))
    current_position = 0
    transition_count = 0
    long_count = 0
    ledgers: list[S11IntervalOutcome] = []

    for index in range(276):
        feature = features[index]
        current_price_row = prices[index]
        next_price_row = prices[index + 1]
        if (
            feature.sequence != current_price_row.feature_sequence
            or next_price_row.feature_sequence != feature.sequence + 1
            or current_price_row.sequence != index + 1
        ):
            raise ValueError("S1.1 feature and price rows are not aligned")
        desired = desired_position(feature, candidate)
        long_count += desired
        terminal = index == 275
        base_before = base_equity
        stress_before = stress_equity
        current_price = Decimal(current_price_row.open_price)
        next_price = Decimal(next_price_row.open_price)
        base_equity, base_return, entry_fill, terminal_fill = apply_interval(
            equity=base_equity,
            current_position=current_position,
            desired=desired,
            current_price=current_price,
            next_price=next_price,
            cost_bps=Decimal(protocol.base_cost_bps_per_fill),
            terminal=terminal,
        )
        stress_equity, stress_return, stress_entry, stress_terminal = apply_interval(
            equity=stress_equity,
            current_position=current_position,
            desired=desired,
            current_price=current_price,
            next_price=next_price,
            cost_bps=Decimal(protocol.stress_cost_bps_per_fill),
            terminal=terminal,
        )
        if (stress_entry, stress_terminal) != (entry_fill, terminal_fill):
            raise ValueError("S1.1 base and stress fills diverged")
        fill_count = int(entry_fill) + int(terminal_fill)
        transition_count += fill_count
        base_pnl = base_equity - base_before
        stress_pnl = stress_equity - stress_before
        base_pnls.append(base_pnl)
        stress_pnls.append(stress_pnl)
        base_returns.append(base_return)
        stress_returns.append(stress_return)
        base_curve.append(base_equity)
        stress_curve.append(stress_equity)
        annual_factors[current_price_row.target_date.year] *= Decimal(1) + base_return
        gross_return = (
            next_price / current_price - Decimal(1) if desired else Decimal(0)
        )
        ledgers.append(
            build_hashed(
                S11IntervalOutcome,
                "interval_evidence_hash",
                candidate_id=candidate.candidate_id,
                interval_sequence=index + 1,
                feature_sequence=feature.sequence,
                target_date=current_price_row.target_date,
                next_target_date=next_price_row.target_date,
                selected_open_time_ms=current_price_row.selected_open_time_ms,
                next_selected_open_time_ms=next_price_row.selected_open_time_ms,
                open_price=current_price_row.open_price,
                next_open_price=next_price_row.open_price,
                desired_position=desired,
                prior_position=current_position,
                entry_fill=entry_fill,
                terminal_liquidation_fill=terminal_fill,
                fill_count=fill_count,
                gross_interval_return=str(gross_return),
                base_equity_before=str(base_before),
                base_equity_after=str(base_equity),
                base_interval_return=str(base_return),
                base_interval_pnl_usd=str(base_pnl),
                stress_equity_before=str(stress_before),
                stress_equity_after=str(stress_equity),
                stress_interval_return=str(stress_return),
                stress_interval_pnl_usd=str(stress_pnl),
                feature_row_evidence_hash=feature_evidence_hash(feature),
                current_price_row_evidence_hash=current_price_row.price_evidence_hash,
                next_price_row_evidence_hash=next_price_row.price_evidence_hash,
            )
        )
        current_position = 0 if terminal else desired

    annual_returns = {
        year: str(annual_factors[year] - Decimal(1)) for year in protocol.full_years
    }
    bootstrap = None
    if candidate.role == "PRIMARY_ELIGIBILITY":
        bootstrap = stationary_bootstrap_lower_mean(
            tuple(stress_returns),
            resamples=protocol.bootstrap_resamples,
            restart_probability=Decimal(protocol.bootstrap_restart_probability),
            seed=protocol.bootstrap_seed,
            order_index=protocol.bootstrap_lower_order_index_zero_based,
        )
    outcome = build_hashed(
        S11CandidateOutcome,
        "outcome_evidence_hash",
        candidate_id=candidate.candidate_id,
        role=candidate.role,
        may_be_promoted=candidate.may_be_promoted,
        position_transition_count=transition_count,
        long_interval_count=long_count,
        long_exposure_fraction=str(Decimal(long_count) / Decimal(276)),
        base_final_equity_usd=str(base_equity),
        base_net_total_return=str(
            base_equity / Decimal(protocol.initial_equity_usd) - Decimal(1)
        ),
        base_profit_factor=profit_factor(tuple(base_pnls)),
        base_maximum_drawdown=str(maximum_drawdown(tuple(base_curve))),
        stress_final_equity_usd=str(stress_equity),
        stress_net_total_return=str(
            stress_equity / Decimal(protocol.initial_equity_usd) - Decimal(1)
        ),
        stress_profit_factor=profit_factor(tuple(stress_pnls)),
        stress_maximum_drawdown=str(maximum_drawdown(tuple(stress_curve))),
        annual_base_returns=annual_returns,
        positive_full_calendar_year_count=sum(
            Decimal(value) > 0 for value in annual_returns.values()
        ),
        stress_bootstrap_lower_mean_weekly_return=(
            None if bootstrap is None else str(bootstrap)
        ),
        interval_manifest_evidence_hash=universe_evidence_hash(
            [item.interval_evidence_hash for item in ledgers]
        ),
    )
    return outcome, tuple(ledgers)


def compare_metric(observed: str, operator: str, threshold: str) -> bool:
    if observed == "Infinity":
        return operator in {"GE", "GT"}
    left = Decimal(observed)
    right = Decimal(threshold)
    return {
        "EQ": left == right,
        "GE": left >= right,
        "LE": left <= right,
        "GT": left > right,
    }[operator]


def evaluate_primary_gates(
    primary: S11CandidateOutcome,
    preregistration: S1StrategyPreregistration,
) -> tuple[S11DevelopmentGateResult, ...]:
    observed = {
        "EXACT_WEEKLY_INTERVAL_COUNT": str(primary.interval_count),
        "MINIMUM_POSITION_TRANSITIONS": str(primary.position_transition_count),
        "MINIMUM_LONG_EXPOSURE_FRACTION": primary.long_exposure_fraction,
        "MAXIMUM_LONG_EXPOSURE_FRACTION": primary.long_exposure_fraction,
        "BASE_NET_TOTAL_RETURN_POSITIVE": primary.base_net_total_return,
        "STRESS_NET_TOTAL_RETURN_POSITIVE": primary.stress_net_total_return,
        "BASE_PROFIT_FACTOR": primary.base_profit_factor,
        "STRESS_PROFIT_FACTOR": primary.stress_profit_factor,
        "BASE_MAXIMUM_DRAWDOWN": primary.base_maximum_drawdown,
        "STRESS_MAXIMUM_DRAWDOWN": primary.stress_maximum_drawdown,
        "POSITIVE_FULL_CALENDAR_YEARS": str(
            primary.positive_full_calendar_year_count
        ),
        "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN": (
            primary.stress_bootstrap_lower_mean_weekly_return or "-Infinity"
        ),
    }
    results = []
    for gate in preregistration.development_gates:
        value = observed[gate.gate_id]
        passed = compare_metric(value, gate.operator, gate.threshold)
        results.append(
            S11DevelopmentGateResult(
                gate_id=gate.gate_id,
                operator=gate.operator,
                threshold=gate.threshold,
                observed=value,
                status="PASS" if passed else "FAIL",
                reason=(
                    "Primary observed metric satisfies the frozen gate."
                    if passed
                    else "Primary observed metric fails the frozen gate."
                ),
            )
        )
    return tuple(results)


def ledger_bytes(rows: tuple[S11IntervalOutcome, ...]) -> bytes:
    return b"".join(
        (json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def write_bytes_once(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"S1.1 outcome artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S1.1 outcome transaction exists: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def load_authority(args):
    protocol = S11DevelopmentOutcomeProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    protocol_audit = S11DevelopmentOutcomeProtocolAudit.model_validate_json(
        args.protocol_audit.read_text(encoding="utf-8")
    )
    contract = S11DevelopmentOutcomeExecutionContract.model_validate_json(
        args.contract.read_text(encoding="utf-8")
    )
    contract_audit = S11DevelopmentOutcomeExecutionAudit.model_validate_json(
        args.contract_audit.read_text(encoding="utf-8")
    )
    preregistration = S1StrategyPreregistration.model_validate_json(
        args.preregistration.read_text(encoding="utf-8")
    )
    if (
        file_sha256(args.protocol) != contract.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != contract.protocol_evidence_hash
        or file_sha256(args.protocol_audit) != contract.protocol_audit_file_sha256
        or protocol_audit.audit_evidence_hash != contract.protocol_audit_evidence_hash
        or runner_contract_hash() != contract.runner_contract_hash
        or file_sha256(args.contract) != contract_audit.contract_file_sha256
        or contract.contract_evidence_hash != contract_audit.contract_evidence_hash
        or preregistration.protocol_evidence_hash
        != protocol.strategy_preregistration_evidence_hash
    ):
        raise ValueError("S1.1 outcome execution authority lineage changed")
    return protocol, contract, preregistration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the one-shot S1.1 development outcome.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite S1.1 outcome: {args.output}")
    protocol, contract, preregistration = load_authority(args)
    feature_path = PROJECT_ROOT / protocol.feature_dataset_path
    price_path = PROJECT_ROOT / protocol.price_dataset_path
    ledger_path = PROJECT_ROOT / protocol.outcome_ledger_path
    if (
        file_sha256(feature_path) != contract.feature_dataset_file_sha256
        or file_sha256(price_path) != contract.price_dataset_file_sha256
        or ledger_path.exists()
    ):
        raise SystemExit("S1.1 outcome input or output boundary changed")
    features = load_jsonl(feature_path, S1NfciFeatureRow)
    prices = load_jsonl(price_path, S1BtcPriceRowV2)
    outcomes = []
    ledger = []
    for candidate in preregistration.candidates:
        outcome, intervals = simulate_candidate(
            features=features,
            prices=prices,
            candidate=candidate,
            protocol=protocol,
        )
        outcomes.append(outcome)
        ledger.extend(intervals)
    ledger_payload = ledger_bytes(tuple(ledger))
    write_bytes_once(ledger_path, ledger_payload)
    primary = next(item for item in outcomes if item.role == "PRIMARY_ELIGIBILITY")
    gates = evaluate_primary_gates(primary, preregistration)
    failed_count = sum(gate.status == "FAIL" for gate in gates)
    decision = S1_1_OUTCOME_STOP if failed_count else S1_1_OUTCOME_PASS
    result = build_hashed(
        S11DevelopmentOutcomeResult,
        "result_evidence_hash",
        completed_at=datetime.now(UTC),
        protocol_file_sha256=file_sha256(args.protocol),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(args.contract),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        feature_dataset_file_sha256=file_sha256(feature_path),
        price_dataset_file_sha256=file_sha256(price_path),
        outcome_ledger_path=protocol.outcome_ledger_path,
        outcome_ledger_file_sha256=file_sha256(ledger_path),
        outcome_ledger_bytes=ledger_path.stat().st_size,
        outcome_ledger_row_count=len(ledger),
        candidate_outcomes=tuple(outcomes),
        primary_gate_results=gates,
        passed_primary_gate_count=12 - failed_count,
        failed_primary_gate_count=failed_count,
        decision=decision,
        next_authorization=(
            "NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED"
            if failed_count
            else "AUTHORIZE_S1_1_VALIDATION_PROTOCOL_ONLY"
        ),
    )
    write_bytes_once(args.output, (result.model_dump_json(indent=2) + "\n").encode())
    print(
        f"WROTE {args.output} {result.result_evidence_hash} decision={result.decision} "
        f"gates={result.passed_primary_gate_count}/12 "
        f"base_return={primary.base_net_total_return} "
        f"stress_return={primary.stress_net_total_return} "
        f"base_pf={primary.base_profit_factor} "
        f"base_dd={primary.base_maximum_drawdown} orders=0",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
