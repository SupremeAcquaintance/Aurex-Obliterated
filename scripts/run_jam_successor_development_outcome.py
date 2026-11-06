from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import zipfile
from bisect import bisect_left
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_development_outcome import (  # noqa: E402
    JAM_OUTCOME_HORIZONS,
    JamAggregateMinutePrice,
    JamControlFeatureRow,
    JamDevelopmentHorizonOutcome,
    JamMatchedControlRecord,
    JamOutcomeArchiveEvidence,
    JamOutcomeBucketMetric,
    JamOutcomeMonthContribution,
    JamSuccessorDevelopmentOutcomeExecutionProtocol,
    JamSuccessorDevelopmentOutcomeResult,
    activity_quartile,
    audit_jam_successor_outcome_protocol,
    audit_jam_successor_outcome_result,
    build_jam_successor_outcome_result,
    build_outcome_gate_results,
    calculate_horizon_outcome,
    cluster_bootstrap_lower_bound,
    decimal_mean,
    normalize_decimal_string,
    profit_factor,
    quantize_outcome,
    select_matched_controls,
)
from aurex.backtest_engine.jam_successor_distribution_protocol import (  # noqa: E402
    JAM_DISTRIBUTION_MONTHS,
    JamDevelopmentArchiveTarget,
)
from aurex.backtest_engine.jam_successor_event_prevalence import (  # noqa: E402
    JAM_PREVALENCE_QUARTERS,
    JamDevelopmentEventLedgerRecord,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_successor_development_outcome_protocol import (  # noqa: E402
    DEFAULT_DISTRIBUTION_PROTOCOL,
    DEFAULT_DISTRIBUTION_RESULT,
    DEFAULT_EVENT_LEDGER,
    DEFAULT_FEATURE_ROWS,
    DEFAULT_PARENT_EVENT_PROTOCOL,
    DEFAULT_PREVALENCE_AUDIT,
    DEFAULT_PREVALENCE_PROTOCOL,
    DEFAULT_PREVALENCE_RESULT,
    DEFAULT_QUALITY_RESULT,
    authoritative_protocol,
    file_sha256,
    load_inputs,
)
from scripts.freeze_jam_successor_development_outcome_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_OUTCOME_PROTOCOL,
)

DEFAULT_EVIDENCE_ROOT = Path("data/evidence")
DEFAULT_CONTROL_LEDGER = Path(
    "data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl"
)
DEFAULT_OUTCOME_LEDGER = Path(
    "data/evidence/jam_successor_development_outcome_ledger_v1.jsonl"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_development_outcome_result_v1.json"
)
DEFAULT_TEMP_ROOT = Path(".tmp/jam_successor_development_outcome")


def source_contract_hash(paths: list[Path]) -> str:
    return universe_evidence_hash(
        {
            "contract_files": {
                path.relative_to(PROJECT_ROOT).as_posix(): file_sha256(path)
                for path in paths
            }
        }
    )


def runner_contract_hash() -> str:
    source_hash = source_contract_hash(
        [
            PROJECT_ROOT / "pyproject.toml",
            PROJECT_ROOT
            / "scripts"
            / "run_jam_successor_development_outcome.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_development_outcome.py",
        ]
    )
    return universe_evidence_hash(
        {
            "source_contract_hash": source_hash,
            "processing_engine": "duckdb",
            "processing_engine_version": duckdb.__version__,
            "python_hash_engine": "sha256",
        }
    )


def _validated_temp_root(path: Path) -> Path:
    resolved = path.resolve()
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError("Jam outcome temp root must remain under .tmp")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)
    return resolved


def _far_from_all(
    open_time_ms: int,
    sorted_times: list[int],
    minimum_minutes: int,
) -> bool:
    index = bisect_left(sorted_times, open_time_ms)
    minimum_ms = minimum_minutes * 60_000
    return all(
        not (
            0 <= neighbor < len(sorted_times)
            and abs(sorted_times[neighbor] - open_time_ms) < minimum_ms
        )
        for neighbor in (index - 1, index)
    )


def load_run_inputs(args) -> tuple[
    JamSuccessorDevelopmentOutcomeExecutionProtocol,
    tuple,
]:
    parent_inputs = load_inputs(args)
    protocol = JamSuccessorDevelopmentOutcomeExecutionProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=parent_inputs,
        args=args,
    )
    if (
        protocol != expected
        or not audit_jam_successor_outcome_protocol(protocol)
        or protocol.network_access_permitted
        or protocol.validation_2021_access_permitted
        or protocol.holdout_2022_access_permitted
        or protocol.threshold_change_permitted
        or protocol.diagnostic_rescue_permitted
        or protocol.strategy_creation_permitted
        or protocol.signal_creation_permitted
        or protocol.candidate_creation_permitted
        or protocol.paper_eligibility_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.production_permitted
        or protocol.live_permitted
        or protocol.real_market_values_opened
        or protocol.future_labels_calculated
        or protocol.return_metrics_calculated
    ):
        raise ValueError("Jam outcome execution protocol or authority changed")
    return protocol, parent_inputs


def build_matched_controls(
    *,
    protocol: JamSuccessorDevelopmentOutcomeExecutionProtocol,
    event_ledger: list[JamDevelopmentEventLedgerRecord],
    feature_rows_path: Path,
) -> list[JamMatchedControlRecord]:
    accepted = [record for record in event_ledger if record.accepted]
    accepted_times = [record.open_time_ms for record in accepted]
    raw_times = {record.open_time_ms for record in event_ledger}
    accepted_set = set(accepted_times)
    q25 = Decimal(protocol.activity_q25)
    q50 = Decimal(protocol.activity_q50)
    q75 = Decimal(protocol.activity_q75)
    event_rows: dict[int, JamControlFeatureRow] = {}
    candidate_groups: dict[tuple[str, int, str], list[JamControlFeatureRow]] = {}
    connection = duckdb.connect(database=":memory:")
    try:
        cursor = connection.execute(
            """
            SELECT
                open_time_ms,
                month,
                hour(epoch_ms(open_time_ms))::INTEGER AS utc_hour,
                baseline_sell_quote_median_120m
            FROM read_parquet(?)
            WHERE quality_state = 'READY'
            ORDER BY open_time_ms
            """,
            [str(feature_rows_path.resolve())],
        )
        while True:
            batch = cursor.fetchmany(100_000)
            if not batch:
                break
            for open_time_value, month, hour, activity in batch:
                open_time_ms = int(open_time_value)
                value = Decimal(activity)
                quartile = activity_quartile(
                    value,
                    q25=q25,
                    q50=q50,
                    q75=q75,
                )
                row = JamControlFeatureRow(
                    open_time_ms=open_time_ms,
                    month=str(month),
                    utc_hour=int(hour),
                    activity_value=normalize_decimal_string(value),
                    activity_quartile=quartile,
                )
                if open_time_ms in accepted_set:
                    event_rows[open_time_ms] = row
                if (
                    open_time_ms not in raw_times
                    and _far_from_all(
                        open_time_ms,
                        accepted_times,
                        protocol.event_exclusion_radius_minutes,
                    )
                ):
                    candidate_groups.setdefault(
                        (row.month, row.utc_hour, row.activity_quartile),
                        [],
                    ).append(row)
    finally:
        connection.close()
    controls = select_matched_controls(
        accepted_event_times=accepted_times,
        event_activity_rows=event_rows,
        candidate_groups=candidate_groups,
    )
    selected_times = sorted(
        record.control_open_time_ms
        for record in controls
        if record.control_open_time_ms is not None
    )
    if (
        len(controls) != protocol.accepted_event_count
        or len(selected_times) != len(set(selected_times))
        or any(time in raw_times for time in selected_times)
        or any(
            not _far_from_all(
                time,
                accepted_times,
                protocol.event_exclusion_radius_minutes,
            )
            for time in selected_times
        )
        or any(
            later - earlier < protocol.control_minimum_separation_minutes * 60_000
            for earlier, later in zip(
                selected_times,
                selected_times[1:],
                strict=False,
            )
        )
    ):
        raise ValueError("Jam matched control invariants changed")
    return controls


def required_outcome_minutes(
    *,
    evaluation_times: list[int],
    quarantined_minutes: set[int],
) -> set[int]:
    required: set[int] = set()
    for evaluation_time in evaluation_times:
        for horizon in JAM_OUTCOME_HORIZONS:
            path = [
                evaluation_time + offset * 60_000
                for offset in range(1, horizon + 1)
            ]
            if (
                all(
                    1_546_300_800_000 <= minute < 1_609_459_200_000
                    for minute in path
                )
                and not any(minute in quarantined_minutes for minute in path)
            ):
                required.update(path)
    return required


def _extract_canonical_member(
    *,
    target: JamDevelopmentArchiveTarget,
    archive_path: Path,
    extracted_path: Path,
) -> None:
    if (
        archive_path.stat().st_size != target.archive_bytes
        or file_sha256(archive_path) != target.archive_sha256
    ):
        raise ValueError(f"Jam outcome archive identity changed: {target.month}")
    with zipfile.ZipFile(archive_path) as archive:
        members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename == target.csv_member_name
        ]
        if len(members) != 1 or members[0].file_size != target.csv_member_bytes:
            raise ValueError(
                f"Jam outcome canonical archive member changed: {target.month}"
            )
        with archive.open(members[0]) as source, extracted_path.open("xb") as output:
            shutil.copyfileobj(source, output, length=8 * 1_048_576)
    if extracted_path.stat().st_size != target.csv_member_bytes:
        raise ValueError(f"Jam outcome archive extraction changed: {target.month}")


def extract_archive_minutes(
    *,
    target: JamDevelopmentArchiveTarget,
    evidence_root: Path,
    temp_root: Path,
    requested_minutes: set[int],
) -> tuple[dict[int, JamAggregateMinutePrice], JamOutcomeArchiveEvidence]:
    archive_path = evidence_root / target.local_path
    if not archive_path.is_file():
        raise ValueError(f"Jam outcome archive is missing: {target.local_path}")
    actual_hash = file_sha256(archive_path)
    if (
        archive_path.stat().st_size != target.archive_bytes
        or actual_hash != target.archive_sha256
    ):
        raise ValueError(f"Jam outcome archive hash changed: {target.month}")
    if not requested_minutes:
        return {}, JamOutcomeArchiveEvidence(
            month=target.month,
            archive_path=target.local_path,
            archive_sha256=actual_hash,
            requested_minute_count=0,
            recovered_minute_count=0,
            missing_minute_count=0,
            archive_identity_passed=True,
        )
    extracted_path = temp_root / f"{target.month}-aggTrades.csv"
    _extract_canonical_member(
        target=target,
        archive_path=archive_path,
        extracted_path=extracted_path,
    )
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET threads = 4")
        connection.execute("SET preserve_insertion_order = true")
        connection.execute("CREATE TABLE needed(open_time_ms BIGINT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO needed VALUES (?)",
            [(minute,) for minute in sorted(requested_minutes)],
        )
        header = "true" if target.header_present else "false"
        rows = connection.execute(
            f"""
            WITH source AS (
                SELECT
                    aggregate_trade_id,
                    price,
                    CASE
                        WHEN transact_time >= 1000000000000000
                        THEN floor(transact_time / 1000)::BIGINT
                        ELSE transact_time
                    END AS transact_time_ms
                FROM read_csv(
                    ?,
                    columns={{
                        'aggregate_trade_id': 'BIGINT',
                        'price': 'DECIMAL(38,8)',
                        'quantity': 'DECIMAL(38,8)',
                        'first_trade_id': 'BIGINT',
                        'last_trade_id': 'BIGINT',
                        'transact_time': 'BIGINT',
                        'is_buyer_maker': 'BOOLEAN',
                        'is_best_match': 'BOOLEAN'
                    }},
                    header={header},
                    auto_detect=false,
                    delim=',',
                    quote='',
                    escape='',
                    strict_mode=true,
                    parallel=true
                )
            ),
            selected AS (
                SELECT
                    floor(transact_time_ms / 60000)::BIGINT * 60000
                        AS open_time_ms,
                    aggregate_trade_id,
                    transact_time_ms,
                    price
                FROM source
                INNER JOIN needed
                    ON floor(transact_time_ms / 60000)::BIGINT * 60000
                        = needed.open_time_ms
            )
            SELECT
                open_time_ms,
                first(price ORDER BY transact_time_ms, aggregate_trade_id),
                max(price),
                min(price),
                last(price ORDER BY transact_time_ms, aggregate_trade_id)
            FROM selected
            GROUP BY open_time_ms
            ORDER BY open_time_ms
            """,
            [str(extracted_path.resolve())],
        ).fetchall()
    finally:
        connection.close()
        if extracted_path.exists():
            extracted_path.unlink()
    recovered = {
        int(row[0]): JamAggregateMinutePrice(
            open_time_ms=int(row[0]),
            first_price=normalize_decimal_string(Decimal(row[1])),
            high_price=normalize_decimal_string(Decimal(row[2])),
            low_price=normalize_decimal_string(Decimal(row[3])),
            last_price=normalize_decimal_string(Decimal(row[4])),
        )
        for row in rows
    }
    if not set(recovered).issubset(requested_minutes):
        raise ValueError(f"Jam outcome recovered minute scope changed: {target.month}")
    evidence = JamOutcomeArchiveEvidence(
        month=target.month,
        archive_path=target.local_path,
        archive_sha256=actual_hash,
        requested_minute_count=len(requested_minutes),
        recovered_minute_count=len(recovered),
        missing_minute_count=len(requested_minutes - set(recovered)),
        archive_identity_passed=True,
    )
    print(
        f"OUTCOME_SOURCE {target.month} "
        f"requested={evidence.requested_minute_count} "
        f"recovered={evidence.recovered_minute_count} "
        f"missing={evidence.missing_minute_count}",
        flush=True,
    )
    return recovered, evidence


def extract_required_prices(
    *,
    protocol: JamSuccessorDevelopmentOutcomeExecutionProtocol,
    evaluation_times: list[int],
    quarantined_minutes: set[int],
    evidence_root: Path,
    temp_root: Path,
) -> tuple[dict[int, JamAggregateMinutePrice], list[JamOutcomeArchiveEvidence]]:
    required = required_outcome_minutes(
        evaluation_times=evaluation_times,
        quarantined_minutes=quarantined_minutes,
    )
    by_month = {month: set() for month in JAM_DISTRIBUTION_MONTHS}
    for minute in required:
        month = datetime.fromtimestamp(minute / 1_000, tz=UTC).strftime("%Y-%m")
        if month not in by_month:
            raise ValueError("Jam outcome requested a sealed month")
        by_month[month].add(minute)
    prices: dict[int, JamAggregateMinutePrice] = {}
    archive_evidence = []
    for target in protocol.archive_targets:
        recovered, evidence = extract_archive_minutes(
            target=target,
            evidence_root=evidence_root,
            temp_root=temp_root,
            requested_minutes=by_month[target.month],
        )
        overlap = set(prices).intersection(recovered)
        if overlap:
            raise ValueError("Jam outcome source minute is duplicated")
        prices.update(recovered)
        archive_evidence.append(evidence)
    return prices, archive_evidence


def build_outcome_ledger(
    *,
    event_ledger: list[JamDevelopmentEventLedgerRecord],
    controls: list[JamMatchedControlRecord],
    minute_prices: dict[int, JamAggregateMinutePrice],
    quarantined_minutes: set[int],
) -> list[JamDevelopmentHorizonOutcome]:
    outcomes = []
    accepted = [record for record in event_ledger if record.accepted]
    for record in accepted:
        if record.accepted_event_sequence is None:
            raise ValueError("Jam accepted event sequence is missing")
        for horizon in JAM_OUTCOME_HORIZONS:
            outcomes.append(
                calculate_horizon_outcome(
                    subject_type="EVENT",
                    subject_sequence=record.accepted_event_sequence,
                    paired_event_sequence=record.accepted_event_sequence,
                    evaluation_open_time_ms=record.open_time_ms,
                    horizon_minutes=horizon,
                    minute_prices=minute_prices,
                    quarantined_minutes=quarantined_minutes,
                )
            )
    for control in controls:
        if control.control_open_time_ms is None:
            continue
        for horizon in JAM_OUTCOME_HORIZONS:
            outcomes.append(
                calculate_horizon_outcome(
                    subject_type="CONTROL",
                    subject_sequence=control.event_sequence,
                    paired_event_sequence=control.event_sequence,
                    evaluation_open_time_ms=control.control_open_time_ms,
                    horizon_minutes=horizon,
                    minute_prices=minute_prices,
                    quarantined_minutes=quarantined_minutes,
                )
            )
    return outcomes


def _outcome_metrics(
    outcomes: list[JamDevelopmentHorizonOutcome],
) -> dict:
    event_primary = [
        item
        for item in outcomes
        if item.subject_type == "EVENT"
        and item.horizon_minutes == 30
        and item.status == "AVAILABLE"
    ]
    control_primary = {
        item.paired_event_sequence: item
        for item in outcomes
        if item.subject_type == "CONTROL"
        and item.horizon_minutes == 30
        and item.status == "AVAILABLE"
    }
    base_values = [
        Decimal(item.base_net_return_bps)
        for item in event_primary
        if item.base_net_return_bps is not None
    ]
    stress_values = [
        Decimal(item.stress_net_return_bps)
        for item in event_primary
        if item.stress_net_return_bps is not None
    ]
    matched_excess = []
    matched_months: dict[int, str] = {}
    for item in event_primary:
        control = control_primary.get(item.paired_event_sequence)
        if control is None:
            continue
        if item.base_net_return_bps is None or control.base_net_return_bps is None:
            raise ValueError("Jam matched primary return is missing")
        matched_excess.append(
            quantize_outcome(
                Decimal(item.base_net_return_bps)
                - Decimal(control.base_net_return_bps)
            )
        )
        matched_months[item.paired_event_sequence] = item.calendar_month
    base_by_month = {month: [] for month in JAM_DISTRIBUTION_MONTHS}
    excess_by_month = {month: [] for month in JAM_DISTRIBUTION_MONTHS}
    for item in event_primary:
        if item.base_net_return_bps is None:
            raise ValueError("Jam event primary return is missing")
        base_by_month[item.calendar_month].append(
            Decimal(item.base_net_return_bps)
        )
    excess_index = 0
    for item in event_primary:
        if item.paired_event_sequence in matched_months:
            excess_by_month[item.calendar_month].append(
                matched_excess[excess_index]
            )
            excess_index += 1
    yearly = []
    for year in ("2019", "2020"):
        values = [
            value
            for month, month_values in base_by_month.items()
            if month.startswith(year)
            for value in month_values
        ]
        yearly.append(
            JamOutcomeBucketMetric(
                bucket=year,
                outcome_count=len(values),
                base_net_mean_bps=normalize_decimal_string(decimal_mean(values)),
            )
        )
    quarterly = []
    for quarter in JAM_PREVALENCE_QUARTERS:
        year, quarter_number = quarter.split("-Q")
        start_month = (int(quarter_number) - 1) * 3 + 1
        quarter_months = {
            f"{year}-{month:02d}"
            for month in range(start_month, start_month + 3)
        }
        values = [
            value
            for month, month_values in base_by_month.items()
            if month in quarter_months
            for value in month_values
        ]
        quarterly.append(
            JamOutcomeBucketMetric(
                bucket=quarter,
                outcome_count=len(values),
                base_net_mean_bps=normalize_decimal_string(decimal_mean(values)),
            )
        )
    absolute_sums = {
        month: sum((abs(value) for value in values), Decimal(0))
        for month, values in base_by_month.items()
    }
    total_absolute = sum(absolute_sums.values(), Decimal(0))
    contributions = [
        JamOutcomeMonthContribution(
            month=month,
            absolute_return_sum_bps=normalize_decimal_string(
                quantize_outcome(absolute_sums[month])
            ),
            contribution_share=normalize_decimal_string(
                quantize_outcome(absolute_sums[month] / total_absolute)
                if total_absolute
                else Decimal(0)
            ),
        )
        for month in JAM_DISTRIBUTION_MONTHS
    ]
    largest = max(
        contributions,
        key=lambda item: (Decimal(item.contribution_share), item.month),
    )
    return {
        "event_primary": event_primary,
        "control_primary": control_primary,
        "matched_excess": matched_excess,
        "base_values": base_values,
        "stress_values": stress_values,
        "base_by_month": base_by_month,
        "excess_by_month": excess_by_month,
        "yearly": yearly,
        "quarterly": quarterly,
        "contributions": contributions,
        "largest": largest,
    }


def build_result(
    *,
    protocol: JamSuccessorDevelopmentOutcomeExecutionProtocol,
    event_ledger: list[JamDevelopmentEventLedgerRecord],
    controls: list[JamMatchedControlRecord],
    outcomes: list[JamDevelopmentHorizonOutcome],
    archive_evidence: list[JamOutcomeArchiveEvidence],
    generated_at: datetime,
    control_ledger_sha256: str,
    control_ledger_bytes: int,
    outcome_ledger_sha256: str,
    outcome_ledger_bytes: int,
) -> JamSuccessorDevelopmentOutcomeResult:
    metrics = _outcome_metrics(outcomes)
    base_mean = decimal_mean(metrics["base_values"])
    stress_mean = decimal_mean(metrics["stress_values"])
    excess_mean = decimal_mean(metrics["matched_excess"])
    base_bootstrap = cluster_bootstrap_lower_bound(metrics["base_by_month"])
    excess_bootstrap = cluster_bootstrap_lower_bound(metrics["excess_by_month"])
    positive_years = sum(
        Decimal(item.base_net_mean_bps) > 0 for item in metrics["yearly"]
    )
    positive_quarters = sum(
        Decimal(item.base_net_mean_bps) > 0 for item in metrics["quarterly"]
    )
    observations = [
        str(len(metrics["event_primary"])),
        str(len(metrics["matched_excess"])),
        normalize_decimal_string(base_mean),
        profit_factor(metrics["base_values"]),
        normalize_decimal_string(stress_mean),
        normalize_decimal_string(excess_mean),
        normalize_decimal_string(base_bootstrap),
        normalize_decimal_string(excess_bootstrap),
        str(positive_years),
        str(positive_quarters),
        metrics["largest"].contribution_share,
    ]
    gates = build_outcome_gate_results(observations)
    event_horizon_counts = {
        str(horizon): sum(
            item.subject_type == "EVENT"
            and item.horizon_minutes == horizon
            and item.status == "AVAILABLE"
            for item in outcomes
        )
        for horizon in JAM_OUTCOME_HORIZONS
    }
    control_horizon_counts = {
        str(horizon): sum(
            item.subject_type == "CONTROL"
            and item.horizon_minutes == horizon
            and item.status == "AVAILABLE"
            for item in outcomes
        )
        for horizon in JAM_OUTCOME_HORIZONS
    }
    matched_count = sum(record.status == "MATCHED" for record in controls)
    return build_jam_successor_outcome_result(
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        prevalence_result_evidence_hash=protocol.prevalence_result_evidence_hash,
        event_ledger_file_sha256=protocol.event_ledger_file_sha256,
        feature_rows_file_sha256=protocol.feature_rows_file_sha256,
        control_ledger_file_sha256=control_ledger_sha256,
        control_ledger_bytes=control_ledger_bytes,
        matched_control_count=matched_count,
        unmatched_event_count=len(controls) - matched_count,
        outcome_ledger_file_sha256=outcome_ledger_sha256,
        outcome_ledger_bytes=outcome_ledger_bytes,
        outcome_ledger_record_count=len(outcomes),
        archive_evidence=archive_evidence,
        primary_outcome_qualified_event_count=len(metrics["event_primary"]),
        primary_outcome_qualified_control_count=len(metrics["control_primary"]),
        matched_primary_pair_count=len(metrics["matched_excess"]),
        event_horizon_available_counts=event_horizon_counts,
        control_horizon_available_counts=control_horizon_counts,
        base_net_mean_30m_bps=normalize_decimal_string(base_mean),
        base_net_profit_factor_30m=profit_factor(metrics["base_values"]),
        stress_net_mean_30m_bps=normalize_decimal_string(stress_mean),
        matched_excess_mean_30m_bps=normalize_decimal_string(excess_mean),
        bootstrap_lower_95_base_net_mean_30m_bps=normalize_decimal_string(
            base_bootstrap
        ),
        bootstrap_lower_95_matched_excess_mean_30m_bps=(
            normalize_decimal_string(excess_bootstrap)
        ),
        yearly_metrics=metrics["yearly"],
        quarterly_metrics=metrics["quarterly"],
        positive_year_count=positive_years,
        positive_quarter_count=positive_quarters,
        monthly_absolute_return_contributions=metrics["contributions"],
        largest_month_absolute_return_contribution=(
            metrics["largest"].contribution_share
        ),
        largest_contribution_month=metrics["largest"].month,
        gates=gates,
        return_metrics_calculated=[
            "BASE_NET_RETURN_BPS_15M_DIAGNOSTIC",
            "BASE_NET_RETURN_BPS_30M_PRIMARY",
            "BASE_NET_RETURN_BPS_60M_DIAGNOSTIC",
            "STRESS_NET_RETURN_BPS_15M_DIAGNOSTIC",
            "STRESS_NET_RETURN_BPS_30M_PRIMARY",
            "STRESS_NET_RETURN_BPS_60M_DIAGNOSTIC",
            "MAXIMUM_FAVORABLE_EXCURSION_BPS",
            "MAXIMUM_ADVERSE_EXCURSION_BPS",
            "MATCHED_EXCESS_BASE_NET_RETURN_BPS_30M",
            "CALENDAR_MONTH_CLUSTER_BOOTSTRAP_LOWER_BOUNDS",
        ],
        limitations=[
            (
                "This result is development evidence only and cannot establish "
                "untouched validation or live profitability."
            ),
            (
                "Only accepted 2019-2020 events and outcome-blind deterministic "
                "controls received outcomes."
            ),
            (
                "All 2021 validation and 2022 holdout source archives remained "
                "sealed."
            ),
            (
                "Every unavailable path remained unavailable; no aggregate minute "
                "or price was synthesized."
            ),
            (
                "Official klines remained QA-only and supplied no outcome price."
            ),
            (
                "The 30-minute horizon alone controls the advancement decision."
            ),
            (
                "The 15- and 60-minute horizons and path excursions are "
                "non-selectable diagnostics."
            ),
            (
                "Base and stress results include the frozen two-sided commission "
                "and adverse-tick assumptions."
            ),
            (
                "Control matching used no future price or return."
            ),
            (
                "Bootstrap confidence bounds use the frozen deterministic month "
                "resampling matrix."
            ),
            (
                "All eleven gates are conjunctive; one failure stops the event "
                "definition."
            ),
            (
                "No observed result may authorize threshold, horizon, control, "
                "cost, or gate changes."
            ),
            (
                "A development pass would require explicit authority before "
                "opening sealed validation."
            ),
            (
                "A development failure permits no validation, Pine parity, paper, "
                "or Testnet strategy execution."
            ),
            (
                "This result creates no strategy, signal, candidate, paper "
                "eligibility, or order authority."
            ),
            (
                "Historical modeled returns are not settled cash profit."
            ),
            (
                "Exact Pine parity remains unavailable for the aggregate-trade "
                "aggressor mechanism."
            ),
            (
                "Production, live, and real-capital authority remain disabled."
            ),
            (
                "Real net profit remains zero regardless of this historical "
                "development decision."
            ),
        ],
    )


def _serialize_jsonl(records: list) -> bytes:
    return "".join(record.model_dump_json() + "\n" for record in records).encode(
        "utf-8"
    )


def _serialize_result(result: JamSuccessorDevelopmentOutcomeResult) -> bytes:
    serialized = (result.model_dump_json(indent=2) + "\n").encode("utf-8")
    if (
        JamSuccessorDevelopmentOutcomeResult.model_validate_json(serialized)
        != result
    ):
        raise ValueError("Jam development outcome result did not round-trip")
    return serialized


def _write_transaction(
    outputs: list[tuple[Path, bytes]],
) -> None:
    parts = []
    for path, payload in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f"{path.name}.part")
        if path.exists() or part.exists():
            raise ValueError(f"Jam outcome output already exists: {path}")
        part.write_bytes(payload)
        parts.append((part, path))
    for part, path in parts:
        part.replace(path)


def run_outcomes(args) -> JamSuccessorDevelopmentOutcomeResult:
    protocol, parent_inputs = load_run_inputs(args)
    event_ledger = parent_inputs[7]
    quarantined_minutes = {
        int(item["open_time_ms"]) for item in parent_inputs[8]
    }
    controls = build_matched_controls(
        protocol=protocol,
        event_ledger=event_ledger,
        feature_rows_path=args.feature_rows,
    )
    evaluation_times = [
        record.open_time_ms for record in event_ledger if record.accepted
    ] + [
        record.control_open_time_ms
        for record in controls
        if record.control_open_time_ms is not None
    ]
    temp_root = _validated_temp_root(args.temp_root)
    try:
        minute_prices, archive_evidence = extract_required_prices(
            protocol=protocol,
            evaluation_times=evaluation_times,
            quarantined_minutes=quarantined_minutes,
            evidence_root=args.evidence_root,
            temp_root=temp_root,
        )
        outcomes = build_outcome_ledger(
            event_ledger=event_ledger,
            controls=controls,
            minute_prices=minute_prices,
            quarantined_minutes=quarantined_minutes,
        )
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)
    control_bytes = _serialize_jsonl(controls)
    outcome_bytes = _serialize_jsonl(outcomes)
    control_hash = hashlib.sha256(control_bytes).hexdigest()
    outcome_hash = hashlib.sha256(outcome_bytes).hexdigest()
    generated_at = (
        datetime.fromisoformat(args.generated_at.replace("Z", "+00:00"))
        if args.generated_at
        else datetime.now(UTC)
    )
    result = build_result(
        protocol=protocol,
        event_ledger=event_ledger,
        controls=controls,
        outcomes=outcomes,
        archive_evidence=archive_evidence,
        generated_at=generated_at,
        control_ledger_sha256=control_hash,
        control_ledger_bytes=len(control_bytes),
        outcome_ledger_sha256=outcome_hash,
        outcome_ledger_bytes=len(outcome_bytes),
    )
    if not audit_jam_successor_outcome_result(result):
        raise ValueError("Jam development outcome result failed internal audit")
    result_bytes = _serialize_result(result)
    _write_transaction(
        [
            (args.control_ledger, control_bytes),
            (args.outcome_ledger, outcome_bytes),
            (args.output, result_bytes),
        ]
    )
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"controls={result.matched_control_count}/991 "
        f"outcomes={result.primary_outcome_qualified_event_count} "
        f"pairs={result.matched_primary_pair_count} "
        f"gates={result.passed_gate_count}/11 decision={result.decision} "
        "validation=False holdout=False strategy_executions=0",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Execute the frozen Jam successor 2019-2020 development outcomes, "
            "costs, controls, inference, and gates exactly once."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_OUTCOME_PROTOCOL)
    parser.add_argument(
        "--parent-event-protocol",
        type=Path,
        default=DEFAULT_PARENT_EVENT_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-protocol",
        type=Path,
        default=DEFAULT_PREVALENCE_PROTOCOL,
    )
    parser.add_argument(
        "--prevalence-result",
        type=Path,
        default=DEFAULT_PREVALENCE_RESULT,
    )
    parser.add_argument(
        "--prevalence-audit",
        type=Path,
        default=DEFAULT_PREVALENCE_AUDIT,
    )
    parser.add_argument(
        "--event-ledger",
        type=Path,
        default=DEFAULT_EVENT_LEDGER,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--distribution-protocol",
        type=Path,
        default=DEFAULT_DISTRIBUTION_PROTOCOL,
    )
    parser.add_argument(
        "--distribution-result",
        type=Path,
        default=DEFAULT_DISTRIBUTION_RESULT,
    )
    parser.add_argument(
        "--quality-result",
        type=Path,
        default=DEFAULT_QUALITY_RESULT,
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
    )
    parser.add_argument(
        "--control-ledger",
        type=Path,
        default=DEFAULT_CONTROL_LEDGER,
    )
    parser.add_argument(
        "--outcome-ledger",
        type=Path,
        default=DEFAULT_OUTCOME_LEDGER,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--temp-root", type=Path, default=DEFAULT_TEMP_ROOT)
    parser.add_argument("--generated-at", default="")
    return parser.parse_args()


def main() -> int:
    try:
        run_outcomes(parse_args())
    except (OSError, ValueError, duckdb.Error) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
