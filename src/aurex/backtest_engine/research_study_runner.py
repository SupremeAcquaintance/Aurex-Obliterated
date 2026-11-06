from __future__ import annotations

import csv
import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import (
    DevelopmentDatasetBundle,
    safe_evidence_path,
)
from aurex.backtest_engine.research_engine import (
    R3Candle,
    R3PreparedMarketData,
    R3ResearchReplayConfig,
    R3ResearchReplayResult,
    prepare_r3_market_data,
    run_r3_research_replay,
)
from aurex.backtest_engine.research_execution_spec import R3ExecutionSpecification
from aurex.backtest_engine.research_result import (
    R3GateResult,
    R3StudyReplayReceipt,
    R3StudyResultLedger,
    build_r3_study_result_ledger,
)
from aurex.backtest_engine.research_run_package import R3PlannedReplay, R3RunPackage
from aurex.backtest_engine.research_study import (
    R3MechanismStudyProtocol,
    R3StudyVariant,
)


def build_planned_replays(
    protocol: R3MechanismStudyProtocol,
) -> list[R3PlannedReplay]:
    plans: list[R3PlannedReplay] = []
    primary = primary_variant(protocol)
    for variant in protocol.variants:
        for multiplier in protocol.costs.stress_multipliers:
            plans.append(
                R3PlannedReplay(
                    run_id=(
                        f"overall--{variant.variant_id}--cost-{decimal_label(multiplier)}"
                    ),
                    category="OVERALL",
                    variant_id=variant.variant_id,
                    variant_role=variant.role,
                    cost_multiplier=multiplier,
                    evaluation_start=protocol.evaluation_start,
                    evaluation_end=protocol.evaluation_end,
                )
            )
        for fold in protocol.folds:
            plans.append(
                R3PlannedReplay(
                    run_id=f"fold--{variant.variant_id}--{fold.fold_id}",
                    category="QUARTERLY_FOLD",
                    variant_id=variant.variant_id,
                    variant_role=variant.role,
                    cost_multiplier=Decimal("1"),
                    evaluation_start=fold.evaluation_start,
                    evaluation_end=fold.evaluation_end,
                    fold_id=fold.fold_id,
                )
            )
    for symbol in protocol.decision_symbols:
        plans.append(
            R3PlannedReplay(
                run_id=f"lomo--{primary.variant_id}--without-{symbol}",
                category="LEAVE_ONE_MARKET_OUT",
                variant_id=primary.variant_id,
                variant_role="PRIMARY",
                cost_multiplier=Decimal("1"),
                evaluation_start=protocol.evaluation_start,
                evaluation_end=protocol.evaluation_end,
                omitted_symbols=[symbol],
            )
        )
    ordered = sorted(plans, key=lambda plan: plan.run_id)
    expected_count = (
        len(protocol.variants) * len(protocol.costs.stress_multipliers)
        + len(protocol.variants) * len(protocol.folds)
        + len(protocol.decision_symbols)
    )
    if len(ordered) != expected_count:
        raise ValueError("R3 replay plan count is inconsistent")
    return ordered


def load_decision_market_data(
    *,
    bundle: DevelopmentDatasetBundle,
    evidence_root: Path,
    decision_symbols: list[str],
) -> R3PreparedMarketData:
    entries = {entry.symbol: entry for entry in bundle.entries}
    expected = sorted(decision_symbols)
    if any(symbol not in entries for symbol in expected):
        raise ValueError("R3 bundle is missing a decision market")
    candles_by_symbol: dict[str, list[R3Candle]] = {}
    for symbol in expected:
        entry = entries[symbol]
        if entry.universe_role != "DECISION_CANDIDATE" or entry.status != "READY":
            raise ValueError(f"R3 decision dataset is not ready: {symbol}")
        path = safe_evidence_path(evidence_root, entry.csv_relative_path)
        if file_sha256(path) != entry.canonical_csv_sha256:
            raise ValueError(f"R3 decision CSV hash mismatch: {symbol}")
        candles_by_symbol[symbol] = load_canonical_ohlcv_csv(path)
        if len(candles_by_symbol[symbol]) != entry.row_count:
            raise ValueError(f"R3 decision CSV row-count mismatch: {symbol}")
    prepared = prepare_r3_market_data(candles_by_symbol)
    if list(prepared.symbols) != expected:
        raise ValueError("R3 prepared market data changed the decision universe")
    return prepared


def load_canonical_ohlcv_csv(path: Path) -> list[R3Candle]:
    candles: list[R3Candle] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]:
            raise ValueError(f"R3 canonical CSV header mismatch: {path}")
        for row in reader:
            candles.append(
                R3Candle(
                    timestamp=datetime.fromisoformat(
                        row["timestamp"].replace("Z", "+00:00")
                    ),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            )
    return candles


def build_replay_config(
    *,
    plan: R3PlannedReplay,
    protocol: R3MechanismStudyProtocol,
    execution_specification: R3ExecutionSpecification,
    market_data: R3PreparedMarketData,
) -> R3ResearchReplayConfig:
    variants = {variant.variant_id: variant for variant in protocol.variants}
    variant = variants.get(plan.variant_id)
    if variant is None or variant.role != plan.variant_role:
        raise ValueError("R3 planned replay names an unknown or mismatched variant")
    return R3ResearchReplayConfig(
        variant_id=variant.variant_id,
        variant_role=variant.role,
        lookback_bars=variant.lookback_bars,
        rebalance_bars=variant.rebalance_bars,
        volatility_lookback_bars=variant.volatility_lookback_bars,
        atr_lookback_bars=variant.atr_lookback_bars,
        catastrophe_stop_atr_multiple=variant.catastrophe_stop_atr_multiple,
        selected_fraction=variant.selected_fraction,
        fixed_selected_count=execution_specification.signals.fixed_selected_count,
        evaluation_start=plan.evaluation_start,
        evaluation_end=plan.evaluation_end,
        baseline_decision_symbols=protocol.decision_symbols,
        omitted_symbols=plan.omitted_symbols,
        initial_capital=protocol.portfolio.initial_capital,
        risk_per_position_percent=protocol.portfolio.risk_per_position_percent,
        max_symbol_exposure_percent=protocol.portfolio.max_symbol_exposure_percent,
        max_gross_exposure_percent=protocol.portfolio.max_gross_exposure_percent,
        max_open_positions=protocol.portfolio.max_open_positions,
        minimum_ranked_positions=protocol.portfolio.minimum_ranked_positions,
        quantity_increment=protocol.portfolio.quantity_increment_assumption,
        price_increment=protocol.portfolio.price_increment_assumption,
        commission_percent_per_side=protocol.costs.commission_percent_per_side,
        adverse_slippage_percent_per_side=(
            protocol.costs.adverse_slippage_percent_per_side
        ),
        cost_multiplier=plan.cost_multiplier,
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        market_data_evidence_hash=market_data.market_data_evidence_hash,
    )


def verify_run_package_sources(package: R3RunPackage, project_root: Path) -> None:
    for relative_path, expected_hash in package.source_file_sha256.items():
        path = (project_root / relative_path).resolve()
        if not path.is_relative_to(project_root.resolve()) or not path.is_file():
            raise ValueError(f"R3 run-package source is missing: {relative_path}")
        if file_sha256(path) != expected_hash:
            raise ValueError(f"R3 run-package source hash changed: {relative_path}")


def execute_r3_study(
    *,
    protocol: R3MechanismStudyProtocol,
    execution_specification: R3ExecutionSpecification,
    run_package: R3RunPackage,
    market_data: R3PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    generated_at: datetime | None = None,
) -> R3StudyResultLedger:
    verify_study_bindings(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    artifact_directory = safe_evidence_path(
        evidence_root, run_package.replay_artifact_directory_relative_path
    )
    if ledger_path.exists() or artifact_directory.exists():
        raise ValueError("R3 result evidence already exists; the study is one-shot")
    temporary_directory = artifact_directory.with_name(
        f"{artifact_directory.name}.part"
    )
    temporary_ledger = ledger_path.with_name(f"{ledger_path.name}.part")
    remove_temporary_directory(temporary_directory, evidence_root)
    if temporary_ledger.exists():
        temporary_ledger.unlink()
    temporary_directory.mkdir(parents=True, exist_ok=False)

    results: dict[str, R3ResearchReplayResult] = {}
    receipts: list[R3StudyReplayReceipt] = []
    try:
        for plan in run_package.planned_replays:
            config = build_replay_config(
                plan=plan,
                protocol=protocol,
                execution_specification=execution_specification,
                market_data=market_data,
            )
            result = run_r3_research_replay(config, market_data)
            filename = f"{plan.run_id}.json"
            temporary_path = temporary_directory / filename
            temporary_path.write_text(
                result.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            artifact_relative = (
                Path(run_package.replay_artifact_directory_relative_path) / filename
            ).as_posix()
            results[plan.run_id] = result
            receipts.append(
                R3StudyReplayReceipt(
                    run_id=plan.run_id,
                    category=plan.category,
                    variant_id=plan.variant_id,
                    variant_role=plan.variant_role,
                    cost_multiplier=plan.cost_multiplier,
                    fold_id=plan.fold_id,
                    omitted_symbols=plan.omitted_symbols,
                    artifact_relative_path=artifact_relative,
                    request_evidence_hash=result.request_evidence_hash,
                    result_evidence_hash=result.result_evidence_hash,
                    artifact_sha256=file_sha256(temporary_path),
                    metrics=result.metrics,
                )
            )
        ledger = build_result_ledger(
            protocol=protocol,
            execution_specification=execution_specification,
            run_package=run_package,
            market_data=market_data,
            receipts=receipts,
            results=results,
            generated_at=generated_at or datetime.now(UTC),
        )
        temporary_ledger.parent.mkdir(parents=True, exist_ok=True)
        temporary_ledger.write_text(
            ledger.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_directory.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory.replace(artifact_directory)
        temporary_ledger.replace(ledger_path)
        return ledger
    except Exception:
        remove_temporary_directory(temporary_directory, evidence_root)
        if temporary_ledger.exists():
            temporary_ledger.unlink()
        raise


def audit_r3_study_artifacts(
    *,
    protocol: R3MechanismStudyProtocol,
    execution_specification: R3ExecutionSpecification,
    run_package: R3RunPackage,
    market_data: R3PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    deterministic_replay: bool,
) -> R3StudyResultLedger:
    verify_study_bindings(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
    )
    verify_run_package_sources(run_package, project_root)
    ledger_path = safe_evidence_path(
        evidence_root, run_package.result_ledger_relative_path
    )
    ledger = R3StudyResultLedger.model_validate_json(
        ledger_path.read_text(encoding="utf-8")
    )
    receipts = {receipt.run_id: receipt for receipt in ledger.replay_receipts}
    planned_ids = [plan.run_id for plan in run_package.planned_replays]
    if sorted(receipts) != planned_ids:
        raise ValueError("R3 result receipts do not match the frozen replay plan")

    results: dict[str, R3ResearchReplayResult] = {}
    for plan in run_package.planned_replays:
        receipt = receipts[plan.run_id]
        if (
            receipt.category != plan.category
            or receipt.variant_id != plan.variant_id
            or receipt.variant_role != plan.variant_role
            or receipt.cost_multiplier != plan.cost_multiplier
            or receipt.fold_id != plan.fold_id
            or receipt.omitted_symbols != plan.omitted_symbols
        ):
            raise ValueError(f"R3 replay receipt changed its plan: {plan.run_id}")
        artifact_path = safe_evidence_path(
            evidence_root, receipt.artifact_relative_path
        )
        if file_sha256(artifact_path) != receipt.artifact_sha256:
            raise ValueError(f"R3 replay artifact hash mismatch: {plan.run_id}")
        result = R3ResearchReplayResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        expected_config = build_replay_config(
            plan=plan,
            protocol=protocol,
            execution_specification=execution_specification,
            market_data=market_data,
        )
        if result.config != expected_config:
            raise ValueError(f"R3 replay config changed: {plan.run_id}")
        if (
            result.request_evidence_hash != receipt.request_evidence_hash
            or result.result_evidence_hash != receipt.result_evidence_hash
            or result.metrics != receipt.metrics
        ):
            raise ValueError(f"R3 replay receipt evidence mismatch: {plan.run_id}")
        if deterministic_replay:
            replayed = run_r3_research_replay(expected_config, market_data)
            if replayed != result:
                raise ValueError(f"R3 deterministic replay mismatch: {plan.run_id}")
        results[plan.run_id] = result

    rebuilt = build_result_ledger(
        protocol=protocol,
        execution_specification=execution_specification,
        run_package=run_package,
        market_data=market_data,
        receipts=ledger.replay_receipts,
        results=results,
        generated_at=ledger.generated_at,
    )
    if rebuilt != ledger:
        raise ValueError("R3 result ledger differs from its deterministic rebuild")
    return ledger


def build_result_ledger(
    *,
    protocol: R3MechanismStudyProtocol,
    execution_specification: R3ExecutionSpecification,
    run_package: R3RunPackage,
    market_data: R3PreparedMarketData,
    receipts: list[R3StudyReplayReceipt],
    results: dict[str, R3ResearchReplayResult],
    generated_at: datetime,
) -> R3StudyResultLedger:
    primary = primary_variant(protocol)
    primary_base = find_result(
        run_package,
        results,
        category="OVERALL",
        variant_id=primary.variant_id,
        cost_multiplier=Decimal("1"),
    )
    primary_double_cost = find_result(
        run_package,
        results,
        category="OVERALL",
        variant_id=primary.variant_id,
        cost_multiplier=Decimal("2"),
    )
    positive_fold_counts = {
        variant.variant_id: sum(
            result.metrics.net_pl > 0
            for plan, result in planned_results(run_package, results)
            if plan.category == "QUARTERLY_FOLD"
            and plan.variant_id == variant.variant_id
        )
        for variant in protocol.variants
    }
    lomo_results = [
        result
        for plan, result in planned_results(run_package, results)
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    ]
    lomo_positive_fraction = Decimal(
        sum(result.metrics.net_pl > 0 for result in lomo_results)
    ) / Decimal(len(lomo_results))
    supportive = [
        variant.variant_id
        for variant in protocol.variants
        if variant.role == "FALSIFICATION"
        and find_result(
            run_package,
            results,
            category="OVERALL",
            variant_id=variant.variant_id,
            cost_multiplier=Decimal("1"),
        ).metrics.net_pl
        > 0
        and positive_fold_counts[variant.variant_id]
        >= protocol.gates.supportive_variant_minimum_positive_folds
    ]
    gates = evaluate_gates(
        protocol=protocol,
        primary=primary_base,
        primary_double_cost=primary_double_cost,
        primary_positive_folds=positive_fold_counts[primary.variant_id],
        lomo_positive_fraction=lomo_positive_fraction,
        supportive_variants=supportive,
    )
    return build_r3_study_result_ledger(
        study_id=protocol.study_id,
        study_version=protocol.study_version,
        generated_at=generated_at,
        status="COMPLETE",
        universe_manifest_evidence_hash=protocol.universe_manifest_evidence_hash,
        development_dataset_bundle_evidence_hash=(
            protocol.development_dataset_bundle_evidence_hash
        ),
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        execution_specification_evidence_hash=(
            execution_specification.specification_evidence_hash
        ),
        run_package_evidence_hash=run_package.package_evidence_hash,
        market_data_evidence_hash=market_data.market_data_evidence_hash,
        planned_replay_count=run_package.expected_replay_count,
        replay_receipts=receipts,
        primary_variant_id=primary.variant_id,
        monthly_net_returns=monthly_net_returns(primary_base),
        positive_fold_counts=positive_fold_counts,
        leave_one_market_out_positive_fraction=lomo_positive_fraction,
        supportive_falsification_variants=supportive,
        gates=gates,
    )


def evaluate_gates(
    *,
    protocol: R3MechanismStudyProtocol,
    primary: R3ResearchReplayResult,
    primary_double_cost: R3ResearchReplayResult,
    primary_positive_folds: int,
    lomo_positive_fraction: Decimal,
    supportive_variants: list[str],
) -> list[R3GateResult]:
    metrics = primary.metrics
    gates = protocol.gates
    return [
        gate(
            "double_cost_net_pl",
            primary_double_cost.metrics.net_pl > 0,
            primary_double_cost.metrics.net_pl,
            "strictly greater than 0 at 2x commission and slippage",
        ),
        gate(
            "leave_one_market_out_positive_fraction",
            lomo_positive_fraction
            >= gates.minimum_leave_one_market_out_positive_fraction,
            lomo_positive_fraction,
            f">= {gates.minimum_leave_one_market_out_positive_fraction}",
        ),
        gate(
            "primary_completed_trades",
            metrics.completed_trades >= gates.minimum_primary_completed_trades,
            metrics.completed_trades,
            f">= {gates.minimum_primary_completed_trades}",
        ),
        gate(
            "primary_maximum_drawdown_percent",
            metrics.maximum_drawdown_percent
            <= gates.maximum_primary_drawdown_percent,
            metrics.maximum_drawdown_percent,
            f"<= {gates.maximum_primary_drawdown_percent}",
        ),
        gate(
            "primary_net_pl",
            metrics.net_pl > 0,
            metrics.net_pl,
            "strictly greater than 0",
        ),
        gate(
            "primary_positive_quarterly_folds",
            primary_positive_folds >= gates.minimum_positive_quarterly_folds,
            primary_positive_folds,
            f">= {gates.minimum_positive_quarterly_folds} of {gates.total_quarterly_folds}",
        ),
        gate(
            "primary_profit_factor",
            metrics.profit_factor is not None
            and metrics.profit_factor >= gates.minimum_primary_profit_factor,
            metrics.profit_factor,
            f">= {gates.minimum_primary_profit_factor}; null fails",
        ),
        gate(
            "single_symbol_gross_profit_fraction",
            metrics.maximum_single_symbol_gross_profit_fraction is not None
            and metrics.maximum_single_symbol_gross_profit_fraction
            <= gates.maximum_single_symbol_gross_profit_fraction,
            metrics.maximum_single_symbol_gross_profit_fraction,
            f"<= {gates.maximum_single_symbol_gross_profit_fraction}; null fails",
        ),
        gate(
            "supportive_falsification_variants",
            len(supportive_variants)
            >= gates.minimum_supportive_falsification_variants,
            len(supportive_variants),
            f">= {gates.minimum_supportive_falsification_variants}",
        ),
        gate(
            "top_five_gross_profit_fraction",
            metrics.top_five_gross_profit_fraction is not None
            and metrics.top_five_gross_profit_fraction
            <= gates.maximum_top_five_gross_profit_fraction,
            metrics.top_five_gross_profit_fraction,
            f"<= {gates.maximum_top_five_gross_profit_fraction}; null fails",
        ),
    ]


def monthly_net_returns(result: R3ResearchReplayResult) -> dict[str, Decimal]:
    month_end_equity: dict[str, Decimal] = {}
    for snapshot in result.equity_curve:
        month_end_equity[snapshot.timestamp.strftime("%Y-%m")] = snapshot.equity
    final_month = (result.config.evaluation_end - timedelta(microseconds=1)).strftime(
        "%Y-%m"
    )
    month_end_equity[final_month] = result.metrics.final_equity
    returns: dict[str, Decimal] = {}
    prior_equity = result.metrics.initial_capital
    for month, ending_equity in sorted(month_end_equity.items()):
        returns[month] = ending_equity / prior_equity - Decimal("1")
        prior_equity = ending_equity
    return returns


def verify_study_bindings(
    *,
    protocol: R3MechanismStudyProtocol,
    execution_specification: R3ExecutionSpecification,
    run_package: R3RunPackage,
    market_data: R3PreparedMarketData,
) -> None:
    if run_package.protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("R3 run package does not match the protocol")
    if (
        run_package.execution_specification_evidence_hash
        != execution_specification.specification_evidence_hash
    ):
        raise ValueError("R3 run package does not match the execution specification")
    if (
        run_package.universe_manifest_evidence_hash
        != protocol.universe_manifest_evidence_hash
    ):
        raise ValueError("R3 run package does not match the universe")
    if (
        run_package.development_dataset_bundle_evidence_hash
        != protocol.development_dataset_bundle_evidence_hash
    ):
        raise ValueError("R3 run package does not match the dataset bundle")
    if run_package.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R3 run package does not match the transformed market data")
    if run_package.planned_replays != build_planned_replays(protocol):
        raise ValueError("R3 run package replay plan has changed")


def planned_results(
    package: R3RunPackage,
    results: dict[str, R3ResearchReplayResult],
):
    for plan in package.planned_replays:
        yield plan, results[plan.run_id]


def find_result(
    package: R3RunPackage,
    results: dict[str, R3ResearchReplayResult],
    *,
    category: str,
    variant_id: str,
    cost_multiplier: Decimal,
) -> R3ResearchReplayResult:
    matches = [
        results[plan.run_id]
        for plan in package.planned_replays
        if plan.category == category
        and plan.variant_id == variant_id
        and plan.cost_multiplier == cost_multiplier
    ]
    if len(matches) != 1:
        raise ValueError("R3 planned result lookup is not unique")
    return matches[0]


def primary_variant(protocol: R3MechanismStudyProtocol) -> R3StudyVariant:
    primary = [variant for variant in protocol.variants if variant.role == "PRIMARY"]
    if len(primary) != 1:
        raise ValueError("R3 protocol must contain exactly one primary variant")
    return primary[0]


def gate(
    gate_id: str,
    passed: bool,
    observed: object,
    requirement: str,
) -> R3GateResult:
    observed_text = "null" if observed is None else str(observed)
    return R3GateResult(
        gate_id=gate_id,
        passed=passed,
        observed=observed_text,
        requirement=requirement,
    )


def decimal_label(value: Decimal) -> str:
    return format(value, "f").replace(".", "p")


def remove_temporary_directory(path: Path, evidence_root: Path) -> None:
    if not path.exists():
        return
    resolved = path.resolve()
    root = evidence_root.resolve()
    if not resolved.is_relative_to(root) or not path.name.endswith(".part"):
        raise ValueError("Refusing to remove an unsafe R3 temporary directory")
    shutil.rmtree(resolved)
