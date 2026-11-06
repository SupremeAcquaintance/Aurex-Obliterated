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

from aurex.backtest_engine.s2_btc_source_execution import S2BtcPriceRow  # noqa: E402
from aurex.backtest_engine.s2_development_backtest import (  # noqa: E402
    S2_BACKTEST_PASS,
    S2_BACKTEST_STOP,
    S2DevelopmentBacktestExecutionAudit,
    S2DevelopmentBacktestExecutionContract,
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestProtocolAudit,
    S2DevelopmentBacktestResult,
    S2DevelopmentCandidateOutcome,
    S2DevelopmentGateResult,
    S2DevelopmentIntervalOutcome,
)
from aurex.backtest_engine.s2_development_measurement_execution import (  # noqa: E402
    S2DevelopmentMeasurementRow,
)
from aurex.backtest_engine.s2_strategy_preregistration import (  # noqa: E402
    S2StrategyPreregistration,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_s2_development_backtest_protocol import file_sha256  # noqa: E402

getcontext().prec = 60

DEFAULT_PROTOCOL = Path("data/evidence/s2_development_backtest_protocol_v1.json")
DEFAULT_PROTOCOL_AUDIT = Path("data/evidence/s2_development_backtest_protocol_audit_v1.json")
DEFAULT_CONTRACT = Path("data/evidence/s2_development_backtest_execution_contract_v1.json")
DEFAULT_CONTRACT_AUDIT = Path("data/evidence/s2_development_backtest_execution_audit_v1.json")
DEFAULT_PREREGISTRATION = Path("data/evidence/s2_strategy_preregistration_v1.json")
DEFAULT_RESULT = Path("data/evidence/s2_development_backtest_result_v1.json")
EXECUTION_MODULE_PATH = Path("src/aurex/backtest_engine/s2_development_backtest.py")
RUNNER_PATH = Path("scripts/run_s2_development_backtest.py")


def rooted(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


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


def measurement_evidence_hash(row: S2DevelopmentMeasurementRow) -> str:
    return universe_evidence_hash(row.model_dump(mode="json"))


def desired_position(measurement: S2DevelopmentMeasurementRow) -> int:
    return int(measurement.settlement_demand_agreement == "BOTH_BROADENING")


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
        raise ValueError("S2 interval requires positive equity and prices")
    if current_position not in (0, 1) or desired not in (0, 1):
        raise ValueError("S2 interval position left the binary domain")
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
        raise ValueError("S2 drawdown requires a positive equity curve")
    peak = equities[0]
    maximum = Decimal(0)
    for equity in equities:
        if equity > peak:
            peak = equity
        decline = (peak - equity) / peak
        maximum = max(maximum, decline)
    return maximum


def profit_factor(pnls: tuple[Decimal, ...]) -> str:
    gains = sum((value for value in pnls if value > 0), Decimal(0))
    losses = -sum((value for value in pnls if value < 0), Decimal(0))
    if losses == 0:
        return "Infinity" if gains > 0 else "0"
    return str(gains / losses)


def weekly_sharpe(returns: tuple[Decimal, ...]) -> str:
    if len(returns) < 2:
        raise ValueError("S2 Sharpe requires at least two weekly returns")
    mean = sum(returns, Decimal(0)) / Decimal(len(returns))
    variance = sum((value - mean) ** 2 for value in returns) / Decimal(
        len(returns) - 1
    )
    if variance == 0:
        return "Infinity" if mean > 0 else "0"
    return str(mean / variance.sqrt() * Decimal(52).sqrt())


def compound_annual_growth_rate(
    final_equity: Decimal, initial_equity: Decimal, interval_count: int
) -> Decimal:
    if final_equity <= 0 or initial_equity <= 0 or interval_count <= 0:
        raise ValueError("S2 CAGR requires positive equity and intervals")
    return (final_equity / initial_equity) ** (
        Decimal(52) / Decimal(interval_count)
    ) - Decimal(1)


def calmar_ratio(cagr: Decimal, drawdown: Decimal) -> str:
    if drawdown == 0:
        return "Infinity" if cagr > 0 else "0"
    return str(cagr / drawdown)


def stationary_bootstrap_lower_mean(
    returns: tuple[Decimal, ...],
    *,
    resamples: int,
    restart_probability: Decimal,
    seed: int,
    order_index: int,
) -> Decimal:
    if not returns or not 0 <= order_index < resamples:
        raise ValueError("S2 bootstrap configuration is invalid")
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
    measurements: tuple[S2DevelopmentMeasurementRow, ...],
    prices: tuple[S2BtcPriceRow, ...],
    protocol: S2DevelopmentBacktestProtocol,
) -> tuple[S2DevelopmentCandidateOutcome, tuple[S2DevelopmentIntervalOutcome, ...]]:
    if len(measurements) != 273 or len(prices) != 273:
        raise ValueError("S2 simulation requires 273 aligned rows")
    base_equity = Decimal(protocol.initial_equity_usd)
    stress_equity = Decimal(protocol.initial_equity_usd)
    buy_hold_equity = Decimal(protocol.initial_equity_usd)
    base_curve = [base_equity]
    stress_curve = [stress_equity]
    buy_hold_curve = [buy_hold_equity]
    base_pnls: list[Decimal] = []
    stress_pnls: list[Decimal] = []
    base_returns: list[Decimal] = []
    stress_returns: list[Decimal] = []
    annual_factors: dict[int, Decimal] = defaultdict(lambda: Decimal(1))
    current_position = 0
    transition_count = 0
    long_count = 0
    ledgers: list[S2DevelopmentIntervalOutcome] = []
    for index in range(272):
        measurement = measurements[index]
        current_price_row = prices[index]
        next_price_row = prices[index + 1]
        if (
            measurement.sequence != current_price_row.measurement_sequence
            or next_price_row.measurement_sequence != measurement.sequence + 1
            or measurement.earliest_execution_at != current_price_row.activation_date
            or current_price_row.sequence != index + 1
        ):
            raise ValueError("S2 measurement and price rows are not aligned")
        desired = desired_position(measurement)
        long_count += desired
        terminal = index == 271
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
        buy_hold_equity, _, _, _ = apply_interval(
            equity=buy_hold_equity,
            current_position=0 if index == 0 else 1,
            desired=1,
            current_price=current_price,
            next_price=next_price,
            cost_bps=Decimal(protocol.base_cost_bps_per_fill),
            terminal=terminal,
        )
        if (stress_entry, stress_terminal) != (entry_fill, terminal_fill):
            raise ValueError("S2 base and stress fills diverged")
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
        buy_hold_curve.append(buy_hold_equity)
        annual_factors[current_price_row.activation_date.year] *= Decimal(1) + base_return
        gross_return = (
            next_price / current_price - Decimal(1) if desired else Decimal(0)
        )
        ledgers.append(
            build_hashed(
                S2DevelopmentIntervalOutcome,
                "interval_evidence_hash",
                candidate_id=protocol.candidate_id,
                interval_sequence=index + 1,
                measurement_sequence=measurement.sequence,
                activation_date=current_price_row.activation_date,
                next_activation_date=next_price_row.activation_date,
                activation_open_time_ms=current_price_row.activation_open_time_ms,
                next_activation_open_time_ms=next_price_row.activation_open_time_ms,
                open_price=current_price_row.open_price,
                next_open_price=next_price_row.open_price,
                settlement_demand_agreement=measurement.settlement_demand_agreement,
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
                measurement_row_evidence_hash=measurement_evidence_hash(measurement),
                current_price_row_evidence_hash=current_price_row.price_evidence_hash,
                next_price_row_evidence_hash=next_price_row.price_evidence_hash,
            )
        )
        current_position = 0 if terminal else desired
    initial = Decimal(protocol.initial_equity_usd)
    base_drawdown = maximum_drawdown(tuple(base_curve))
    buy_hold_drawdown = maximum_drawdown(tuple(buy_hold_curve))
    base_cagr = compound_annual_growth_rate(base_equity, initial, 272)
    annual_returns = {
        year: str(annual_factors[year] - Decimal(1)) for year in protocol.full_years
    }
    bootstrap = stationary_bootstrap_lower_mean(
        tuple(stress_returns),
        resamples=protocol.bootstrap_resamples,
        restart_probability=Decimal(protocol.bootstrap_restart_probability),
        seed=protocol.bootstrap_seed,
        order_index=protocol.bootstrap_lower_order_index_zero_based,
    )
    outcome = build_hashed(
        S2DevelopmentCandidateOutcome,
        "outcome_evidence_hash",
        candidate_id=protocol.candidate_id,
        position_transition_count=transition_count,
        long_interval_count=long_count,
        long_exposure_fraction=str(Decimal(long_count) / Decimal(272)),
        base_final_equity_usd=str(base_equity),
        base_net_total_return=str(base_equity / initial - Decimal(1)),
        base_profit_factor=profit_factor(tuple(base_pnls)),
        base_maximum_drawdown=str(base_drawdown),
        base_weekly_sharpe=weekly_sharpe(tuple(base_returns)),
        base_cagr=str(base_cagr),
        base_calmar_ratio=calmar_ratio(base_cagr, base_drawdown),
        stress_final_equity_usd=str(stress_equity),
        stress_net_total_return=str(stress_equity / initial - Decimal(1)),
        stress_profit_factor=profit_factor(tuple(stress_pnls)),
        stress_maximum_drawdown=str(maximum_drawdown(tuple(stress_curve))),
        stress_weekly_sharpe=weekly_sharpe(tuple(stress_returns)),
        annual_base_returns=annual_returns,
        positive_full_calendar_year_count=sum(
            Decimal(value) > 0 for value in annual_returns.values()
        ),
        stress_bootstrap_lower_mean_weekly_return=str(bootstrap),
        buy_hold_base_final_equity_usd=str(buy_hold_equity),
        buy_hold_base_net_total_return=str(buy_hold_equity / initial - Decimal(1)),
        buy_hold_base_maximum_drawdown=str(buy_hold_drawdown),
        base_drawdown_minus_buy_hold_drawdown=str(base_drawdown - buy_hold_drawdown),
        interval_manifest_evidence_hash=universe_evidence_hash(
            [item.interval_evidence_hash for item in ledgers]
        ),
    )
    return outcome, tuple(ledgers)


def compare_metric(observed: str, operator: str, threshold: str) -> bool:
    if observed == "Infinity":
        return operator in {"GE", "GT"}
    if observed == "-Infinity":
        return operator in {"LE", "LT"}
    left = Decimal(observed)
    right = Decimal(threshold)
    return {
        "EQ": left == right,
        "GE": left >= right,
        "LE": left <= right,
        "GT": left > right,
        "LT": left < right,
    }[operator]


def evaluate_gates(
    outcome: S2DevelopmentCandidateOutcome,
    preregistration: S2StrategyPreregistration,
) -> tuple[S2DevelopmentGateResult, ...]:
    observed = {
        "EXACT_WEEKLY_INTERVAL_COUNT": str(outcome.interval_count),
        "MINIMUM_POSITION_TRANSITIONS": str(outcome.position_transition_count),
        "MINIMUM_LONG_EXPOSURE_FRACTION": outcome.long_exposure_fraction,
        "MAXIMUM_LONG_EXPOSURE_FRACTION": outcome.long_exposure_fraction,
        "BASE_NET_TOTAL_RETURN_POSITIVE": outcome.base_net_total_return,
        "STRESS_NET_TOTAL_RETURN_POSITIVE": outcome.stress_net_total_return,
        "BASE_PROFIT_FACTOR": outcome.base_profit_factor,
        "STRESS_PROFIT_FACTOR": outcome.stress_profit_factor,
        "BASE_MAXIMUM_DRAWDOWN": outcome.base_maximum_drawdown,
        "STRESS_MAXIMUM_DRAWDOWN": outcome.stress_maximum_drawdown,
        "POSITIVE_FULL_CALENDAR_YEARS": str(outcome.positive_full_calendar_year_count),
        "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN": (
            outcome.stress_bootstrap_lower_mean_weekly_return
        ),
        "STRESS_WEEKLY_SHARPE": outcome.stress_weekly_sharpe,
        "BASE_CALMAR_RATIO": outcome.base_calmar_ratio,
        "BASE_MAXIMUM_DRAWDOWN_NOT_WORSE_THAN_BUY_AND_HOLD": (
            outcome.base_drawdown_minus_buy_hold_drawdown
        ),
    }
    if tuple(observed) != tuple(gate.gate_id for gate in preregistration.development_gates):
        raise ValueError("S2 development gate implementation changed")
    return tuple(
        S2DevelopmentGateResult(
            gate_id=gate.gate_id,
            operator=gate.operator,
            threshold=gate.threshold,
            observed=observed[gate.gate_id],
            status=(
                "PASS"
                if compare_metric(observed[gate.gate_id], gate.operator, gate.threshold)
                else "FAIL"
            ),
            reason=(
                "Observed metric satisfies the frozen S2 development gate."
                if compare_metric(observed[gate.gate_id], gate.operator, gate.threshold)
                else "Observed metric fails the frozen S2 development gate."
            ),
        )
        for gate in preregistration.development_gates
    )


def ledger_bytes(rows: tuple[S2DevelopmentIntervalOutcome, ...]) -> bytes:
    return b"".join(
        (json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n").encode("utf-8")
        for row in rows
    )


def write_bytes_once(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"S2 development backtest artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale S2 backtest transaction exists: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def load_authority(
    *,
    protocol_path: Path,
    protocol_audit_path: Path,
    contract_path: Path,
    contract_audit_path: Path,
    preregistration_path: Path,
) -> tuple[
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestExecutionContract,
    S2StrategyPreregistration,
]:
    protocol = S2DevelopmentBacktestProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    protocol_audit = S2DevelopmentBacktestProtocolAudit.model_validate_json(
        protocol_audit_path.read_text(encoding="utf-8")
    )
    contract = S2DevelopmentBacktestExecutionContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    contract_audit = S2DevelopmentBacktestExecutionAudit.model_validate_json(
        contract_audit_path.read_text(encoding="utf-8")
    )
    preregistration = S2StrategyPreregistration.model_validate_json(
        preregistration_path.read_text(encoding="utf-8")
    )
    if (
        file_sha256(protocol_path) != contract.protocol_file_sha256
        or protocol.protocol_evidence_hash != protocol_audit.protocol_evidence_hash
        or protocol.protocol_evidence_hash != contract.protocol_evidence_hash
        or file_sha256(protocol_audit_path) != contract.protocol_audit_file_sha256
        or protocol_audit.audit_evidence_hash != contract.protocol_audit_evidence_hash
        or runner_contract_hash() != contract.runner_contract_hash
        or file_sha256(contract_path) != contract_audit.contract_file_sha256
        or contract.contract_evidence_hash != contract_audit.contract_evidence_hash
        or preregistration.protocol_evidence_hash != protocol.preregistration_evidence_hash
        or not contract.authorizes_one_development_backtest
    ):
        raise ValueError("S2 development backtest execution authority changed")
    return protocol, contract, preregistration


def build_result(
    *,
    completed_at: datetime,
    protocol_path: Path,
    protocol: S2DevelopmentBacktestProtocol,
    contract_path: Path,
    contract: S2DevelopmentBacktestExecutionContract,
    preregistration: S2StrategyPreregistration,
    outcome: S2DevelopmentCandidateOutcome,
    ledger: tuple[S2DevelopmentIntervalOutcome, ...],
) -> S2DevelopmentBacktestResult:
    ledger_path = rooted(protocol.outcome_ledger_path)
    gates = evaluate_gates(outcome, preregistration)
    failed = sum(gate.status == "FAIL" for gate in gates)
    return build_hashed(
        S2DevelopmentBacktestResult,
        "result_evidence_hash",
        completed_at=completed_at,
        protocol_file_sha256=file_sha256(protocol_path),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_contract_file_sha256=file_sha256(contract_path),
        execution_contract_evidence_hash=contract.contract_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        measurement_dataset_file_sha256=protocol.measurement_dataset_file_sha256,
        price_dataset_file_sha256=protocol.price_dataset_file_sha256,
        outcome_ledger_path=protocol.outcome_ledger_path,
        outcome_ledger_file_sha256=file_sha256(ledger_path),
        outcome_ledger_bytes=ledger_path.stat().st_size,
        candidate_outcome=outcome,
        gate_results=gates,
        passed_gate_count=15 - failed,
        failed_gate_count=failed,
        decision=S2_BACKTEST_STOP if failed else S2_BACKTEST_PASS,
        next_authorization=(
            "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
            if failed
            else "AUTHORIZE_S2_HISTORICAL_SCREEN_PROTOCOL_ONLY"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the one-shot S2 development backtest.")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--contract-audit", type=Path, default=DEFAULT_CONTRACT_AUDIT)
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        protocol_path = rooted(args.protocol)
        protocol_audit_path = rooted(args.protocol_audit)
        contract_path = rooted(args.contract)
        contract_audit_path = rooted(args.contract_audit)
        preregistration_path = rooted(args.preregistration)
        output_path = rooted(args.output)
        if output_path.exists():
            raise ValueError(f"Refusing to overwrite S2 backtest result: {output_path}")
        protocol, contract, preregistration = load_authority(
            protocol_path=protocol_path,
            protocol_audit_path=protocol_audit_path,
            contract_path=contract_path,
            contract_audit_path=contract_audit_path,
            preregistration_path=preregistration_path,
        )
        measurement_path = rooted(protocol.measurement_dataset_path)
        price_path = rooted(protocol.price_dataset_path)
        ledger_path = rooted(protocol.outcome_ledger_path)
        if (
            file_sha256(measurement_path) != contract.measurement_dataset_file_sha256
            or file_sha256(price_path) != contract.price_dataset_file_sha256
            or ledger_path.exists()
        ):
            raise ValueError("S2 backtest input or output boundary changed")
        measurements = load_jsonl(measurement_path, S2DevelopmentMeasurementRow)
        prices = load_jsonl(price_path, S2BtcPriceRow)
        outcome, ledger = simulate_candidate(
            measurements=measurements, prices=prices, protocol=protocol
        )
        write_bytes_once(ledger_path, ledger_bytes(ledger))
        result = build_result(
            completed_at=datetime.now(UTC),
            protocol_path=protocol_path,
            protocol=protocol,
            contract_path=contract_path,
            contract=contract,
            preregistration=preregistration,
            outcome=outcome,
            ledger=ledger,
        )
        write_bytes_once(output_path, (result.model_dump_json(indent=2) + "\n").encode())
        print(
            f"COMPLETE {output_path} {result.result_evidence_hash} "
            f"decision={result.decision} gates={result.passed_gate_count}/15 "
            f"base_return={outcome.base_net_total_return} "
            f"stress_return={outcome.stress_net_total_return} "
            f"base_pf={outcome.base_profit_factor} returns=272 orders=0",
            flush=True,
        )
    except (OSError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
