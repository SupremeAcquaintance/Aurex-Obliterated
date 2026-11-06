from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.binance_vision import file_sha256
from aurex.backtest_engine.development_bundle import safe_evidence_path
from aurex.backtest_engine.research_engine import R3PreparedMarketData
from aurex.backtest_engine.research_r31_engine import (
    R31ResearchReplayConfig,
    R31ResearchReplayResult,
    run_r31_research_replay,
)
from aurex.backtest_engine.research_r31_execution_spec import (
    R31ExecutionSpecification,
)
from aurex.backtest_engine.research_r31_result import (
    R31GateResult,
    R31StudyReplayReceipt,
    R31StudyResultLedger,
    build_r31_study_result_ledger,
)
from aurex.backtest_engine.research_r31_run_package import (
    R31PlannedReplay,
    R31RunPackage,
)
from aurex.backtest_engine.research_r31_study import R31MechanismStudyProtocol


def build_planned_replays(
    protocol: R31MechanismStudyProtocol,
) -> list[R31PlannedReplay]:
    variant_id = protocol.signal.signal_id
    plans: list[R31PlannedReplay] = []
    for multiplier in protocol.costs.stress_multipliers:
        plans.append(
            R31PlannedReplay(
                run_id=f"overall--{variant_id}--cost-{decimal_label(multiplier)}",
                category="OVERALL",
                cost_multiplier=multiplier,
                evaluation_start=protocol.evaluation_start,
                evaluation_end=protocol.evaluation_end,
            )
        )
    for fold in protocol.folds:
        plans.append(
            R31PlannedReplay(
                run_id=f"fold--{variant_id}--{fold.fold_id}",
                category="QUARTERLY_FOLD",
                cost_multiplier=Decimal("1"),
                evaluation_start=fold.evaluation_start,
                evaluation_end=fold.evaluation_end,
                fold_id=fold.fold_id,
            )
        )
    for symbol in protocol.decision_symbols:
        plans.append(
            R31PlannedReplay(
                run_id=f"lomo--{variant_id}--without-{symbol}",
                category="LEAVE_ONE_MARKET_OUT",
                cost_multiplier=Decimal("1"),
                evaluation_start=protocol.evaluation_start,
                evaluation_end=protocol.evaluation_end,
                omitted_symbols=[symbol],
            )
        )
    ordered = sorted(plans, key=lambda plan: plan.run_id)
    if len(ordered) != 44:
        raise ValueError("R3.1 replay plan must contain exactly 44 runs")
    return ordered


def build_replay_config(
    *,
    plan: R31PlannedReplay,
    protocol: R31MechanismStudyProtocol,
    execution_specification: R31ExecutionSpecification,
    market_data: R3PreparedMarketData,
) -> R31ResearchReplayConfig:
    if plan.variant_id != protocol.signal.signal_id:
        raise ValueError("R3.1 plan names an unknown signal")
    return R31ResearchReplayConfig(
        evaluation_start=plan.evaluation_start,
        evaluation_end=plan.evaluation_end,
        baseline_decision_symbols=protocol.decision_symbols,
        omitted_symbols=plan.omitted_symbols,
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


def verify_run_package_sources(package: R31RunPackage, project_root: Path) -> None:
    for relative_path, expected_hash in package.source_file_sha256.items():
        path = (project_root / relative_path).resolve()
        if not path.is_relative_to(project_root.resolve()) or not path.is_file():
            raise ValueError(f"R3.1 source is missing: {relative_path}")
        if file_sha256(path) != expected_hash:
            raise ValueError(f"R3.1 source hash changed: {relative_path}")


def execute_r31_study(
    *,
    protocol: R31MechanismStudyProtocol,
    execution_specification: R31ExecutionSpecification,
    run_package: R31RunPackage,
    market_data: R3PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    generated_at: datetime | None = None,
) -> R31StudyResultLedger:
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
        raise ValueError("R3.1 evidence exists; the study is one-shot")
    temporary_directory = artifact_directory.with_name(
        f"{artifact_directory.name}.part"
    )
    temporary_ledger = ledger_path.with_name(f"{ledger_path.name}.part")
    remove_temporary_directory(temporary_directory, evidence_root)
    if temporary_ledger.exists():
        temporary_ledger.unlink()
    temporary_directory.mkdir(parents=True, exist_ok=False)

    results: dict[str, R31ResearchReplayResult] = {}
    receipts: list[R31StudyReplayReceipt] = []
    artifact_directory_committed = False
    try:
        for plan in run_package.planned_replays:
            config = build_replay_config(
                plan=plan,
                protocol=protocol,
                execution_specification=execution_specification,
                market_data=market_data,
            )
            result = run_r31_research_replay(config, market_data)
            filename = f"{plan.run_id}.json"
            temporary_path = temporary_directory / filename
            serialized = result.model_dump_json(indent=2) + "\n"
            if R31ResearchReplayResult.model_validate_json(serialized) != result:
                raise ValueError(f"R3.1 result JSON did not round-trip: {plan.run_id}")
            temporary_path.write_text(serialized, encoding="utf-8")
            artifact_relative = (
                Path(run_package.replay_artifact_directory_relative_path) / filename
            ).as_posix()
            results[plan.run_id] = result
            receipts.append(
                R31StudyReplayReceipt(
                    run_id=plan.run_id,
                    category=plan.category,
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
        serialized_ledger = ledger.model_dump_json(indent=2) + "\n"
        if R31StudyResultLedger.model_validate_json(serialized_ledger) != ledger:
            raise ValueError("R3.1 ledger JSON did not round-trip")
        temporary_ledger.parent.mkdir(parents=True, exist_ok=True)
        temporary_ledger.write_text(serialized_ledger, encoding="utf-8")
        artifact_directory.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory.replace(artifact_directory)
        artifact_directory_committed = True
        temporary_ledger.replace(ledger_path)
        return ledger
    except Exception:
        remove_temporary_directory(temporary_directory, evidence_root)
        if artifact_directory_committed and not ledger_path.exists():
            remove_committed_artifact_directory(artifact_directory, evidence_root)
        if temporary_ledger.exists():
            temporary_ledger.unlink()
        raise


def audit_r31_study_artifacts(
    *,
    protocol: R31MechanismStudyProtocol,
    execution_specification: R31ExecutionSpecification,
    run_package: R31RunPackage,
    market_data: R3PreparedMarketData,
    evidence_root: Path,
    project_root: Path,
    deterministic_replay: bool,
) -> R31StudyResultLedger:
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
    ledger = R31StudyResultLedger.model_validate_json(
        ledger_path.read_text(encoding="utf-8")
    )
    receipts = {receipt.run_id: receipt for receipt in ledger.replay_receipts}
    planned_ids = [plan.run_id for plan in run_package.planned_replays]
    if sorted(receipts) != planned_ids:
        raise ValueError("R3.1 receipts do not match the frozen plan")

    results: dict[str, R31ResearchReplayResult] = {}
    for plan in run_package.planned_replays:
        receipt = receipts[plan.run_id]
        if (
            receipt.category != plan.category
            or receipt.cost_multiplier != plan.cost_multiplier
            or receipt.fold_id != plan.fold_id
            or receipt.omitted_symbols != plan.omitted_symbols
        ):
            raise ValueError(f"R3.1 receipt changed its plan: {plan.run_id}")
        artifact_path = safe_evidence_path(
            evidence_root, receipt.artifact_relative_path
        )
        if file_sha256(artifact_path) != receipt.artifact_sha256:
            raise ValueError(f"R3.1 artifact hash mismatch: {plan.run_id}")
        result = R31ResearchReplayResult.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        expected_config = build_replay_config(
            plan=plan,
            protocol=protocol,
            execution_specification=execution_specification,
            market_data=market_data,
        )
        if result.config != expected_config:
            raise ValueError(f"R3.1 config changed: {plan.run_id}")
        if (
            result.request_evidence_hash != receipt.request_evidence_hash
            or result.result_evidence_hash != receipt.result_evidence_hash
            or result.metrics != receipt.metrics
        ):
            raise ValueError(f"R3.1 receipt evidence mismatch: {plan.run_id}")
        if deterministic_replay:
            replayed = run_r31_research_replay(expected_config, market_data)
            if replayed != result:
                raise ValueError(f"R3.1 deterministic mismatch: {plan.run_id}")
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
        raise ValueError("R3.1 ledger differs from its deterministic rebuild")
    return ledger


def build_result_ledger(
    *,
    protocol: R31MechanismStudyProtocol,
    execution_specification: R31ExecutionSpecification,
    run_package: R31RunPackage,
    market_data: R3PreparedMarketData,
    receipts: list[R31StudyReplayReceipt],
    results: dict[str, R31ResearchReplayResult],
    generated_at: datetime,
) -> R31StudyResultLedger:
    primary = find_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("1"),
    )
    double_cost = find_result(
        run_package,
        results,
        category="OVERALL",
        cost_multiplier=Decimal("2"),
    )
    positive_folds = sum(
        result.metrics.net_pl > 0
        for plan, result in planned_results(run_package, results)
        if plan.category == "QUARTERLY_FOLD"
    )
    lomo = [
        result
        for plan, result in planned_results(run_package, results)
        if plan.category == "LEAVE_ONE_MARKET_OUT"
    ]
    lomo_fraction = Decimal(
        sum(result.metrics.net_pl > 0 for result in lomo)
    ) / Decimal(len(lomo))
    gates = evaluate_gates(
        protocol=protocol,
        primary=primary,
        double_cost=double_cost,
        positive_folds=positive_folds,
        lomo_positive_fraction=lomo_fraction,
    )
    return build_r31_study_result_ledger(
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
        primary_variant_id=protocol.signal.signal_id,
        monthly_net_returns=corrected_monthly_net_returns(primary),
        positive_quarterly_folds=positive_folds,
        leave_one_market_out_positive_fraction=lomo_fraction,
        gates=gates,
    )


def evaluate_gates(
    *,
    protocol: R31MechanismStudyProtocol,
    primary: R31ResearchReplayResult,
    double_cost: R31ResearchReplayResult,
    positive_folds: int,
    lomo_positive_fraction: Decimal,
) -> list[R31GateResult]:
    metrics = primary.metrics
    gates = protocol.gates
    return [
        gate(
            "double_cost_net_pl",
            double_cost.metrics.net_pl > 0,
            double_cost.metrics.net_pl,
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
            positive_folds >= gates.minimum_positive_quarterly_folds,
            positive_folds,
            f">= {gates.minimum_positive_quarterly_folds} of 6",
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
            "top_five_gross_profit_fraction",
            metrics.top_five_gross_profit_fraction is not None
            and metrics.top_five_gross_profit_fraction
            <= gates.maximum_top_five_gross_profit_fraction,
            metrics.top_five_gross_profit_fraction,
            f"<= {gates.maximum_top_five_gross_profit_fraction}; null fails",
        ),
    ]


def corrected_monthly_net_returns(
    result: R31ResearchReplayResult,
) -> dict[str, Decimal]:
    month_end_equity: dict[str, Decimal] = {}
    for snapshot in result.equity_curve:
        month = (snapshot.timestamp - timedelta(microseconds=1)).strftime("%Y-%m")
        month_end_equity[month] = snapshot.equity
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
    protocol: R31MechanismStudyProtocol,
    execution_specification: R31ExecutionSpecification,
    run_package: R31RunPackage,
    market_data: R3PreparedMarketData,
) -> None:
    if run_package.protocol_evidence_hash != protocol.protocol_evidence_hash:
        raise ValueError("R3.1 package does not match the protocol")
    if (
        run_package.execution_specification_evidence_hash
        != execution_specification.specification_evidence_hash
    ):
        raise ValueError("R3.1 package does not match the execution specification")
    if (
        run_package.universe_manifest_evidence_hash
        != protocol.universe_manifest_evidence_hash
    ):
        raise ValueError("R3.1 package does not match the universe")
    if (
        run_package.development_dataset_bundle_evidence_hash
        != protocol.development_dataset_bundle_evidence_hash
    ):
        raise ValueError("R3.1 package does not match the dataset bundle")
    if run_package.market_data_evidence_hash != market_data.market_data_evidence_hash:
        raise ValueError("R3.1 package does not match transformed market data")
    if run_package.planned_replays != build_planned_replays(protocol):
        raise ValueError("R3.1 replay plan changed")


def planned_results(
    package: R31RunPackage,
    results: dict[str, R31ResearchReplayResult],
):
    for plan in package.planned_replays:
        yield plan, results[plan.run_id]


def find_result(
    package: R31RunPackage,
    results: dict[str, R31ResearchReplayResult],
    *,
    category: str,
    cost_multiplier: Decimal,
) -> R31ResearchReplayResult:
    matches = [
        results[plan.run_id]
        for plan in package.planned_replays
        if plan.category == category and plan.cost_multiplier == cost_multiplier
    ]
    if len(matches) != 1:
        raise ValueError("R3.1 planned result lookup is not unique")
    return matches[0]


def gate(
    gate_id: str,
    passed: bool,
    observed: object,
    requirement: str,
) -> R31GateResult:
    return R31GateResult(
        gate_id=gate_id,
        passed=passed,
        observed="null" if observed is None else str(observed),
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
        raise ValueError("Refusing to remove unsafe R3.1 temporary directory")
    shutil.rmtree(resolved)


def remove_committed_artifact_directory(path: Path, evidence_root: Path) -> None:
    resolved = path.resolve()
    root = evidence_root.resolve()
    if (
        not resolved.is_relative_to(root)
        or path.name != "r31_path_quality_results_v1"
    ):
        raise ValueError("Refusing to roll back unsafe R3.1 artifact directory")
    if resolved.exists():
        shutil.rmtree(resolved)
