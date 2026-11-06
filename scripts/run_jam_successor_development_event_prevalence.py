from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aurex.backtest_engine.jam_successor_event_prevalence import (  # noqa: E402
    JAM_PREVALENCE_EVENT_FEATURE_IDS,
    JamDevelopmentEventLedgerRecord,
    JamPrevalenceInputRow,
    JamSuccessorDevelopmentEventPrevalenceProtocol,
    JamSuccessorDevelopmentEventPrevalenceResult,
    audit_jam_successor_prevalence_protocol,
    audit_jam_successor_prevalence_result,
    build_event_ledger,
    build_jam_successor_prevalence_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash  # noqa: E402
from scripts.freeze_jam_successor_event_prevalence_protocol import (  # noqa: E402
    DEFAULT_FEATURE_ROWS,
    DEFAULT_PARENT_AUDIT,
    DEFAULT_PARENT_PROTOCOL,
    authoritative_protocol,
    file_sha256,
    load_inputs,
)
from scripts.freeze_jam_successor_event_prevalence_protocol import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_PREVALENCE_PROTOCOL,
)

DEFAULT_EVENT_LEDGER = Path(
    "data/evidence/jam_successor_development_event_ledger_v1.jsonl"
)
DEFAULT_OUTPUT = Path(
    "data/evidence/jam_successor_development_event_prevalence_result_v1.json"
)


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
            / "run_jam_successor_development_event_prevalence.py",
            PROJECT_ROOT
            / "src"
            / "aurex"
            / "backtest_engine"
            / "jam_successor_event_prevalence.py",
        ]
    )
    return universe_evidence_hash(
        {
            "source_contract_hash": source_hash,
            "processing_engine": "duckdb",
            "processing_engine_version": duckdb.__version__,
        }
    )


def _write_ledger(
    path: Path,
    records: list[JamDevelopmentEventLedgerRecord],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "".join(record.model_dump_json() + "\n" for record in records)
    reconstructed = [
        JamDevelopmentEventLedgerRecord.model_validate_json(line)
        for line in serialized.splitlines()
    ]
    if reconstructed != records:
        raise ValueError("Jam event ledger JSONL did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional ledger exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _write_result(
    path: Path,
    result: JamSuccessorDevelopmentEventPrevalenceResult,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = result.model_dump_json(indent=2) + "\n"
    if (
        JamSuccessorDevelopmentEventPrevalenceResult.model_validate_json(
            serialized
        )
        != result
    ):
        raise ValueError("Jam prevalence result JSON did not round-trip")
    temporary = path.with_name(f"{path.name}.part")
    if temporary.exists():
        raise ValueError(f"Stale transactional result exists: {temporary}")
    temporary.write_text(serialized, encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_run_inputs(
    *,
    protocol_path: Path,
    parent_protocol_path: Path,
    parent_audit_path: Path,
    feature_rows_path: Path,
) -> JamSuccessorDevelopmentEventPrevalenceProtocol:
    parent_inputs = load_inputs(
        parent_protocol_path=parent_protocol_path,
        parent_audit_path=parent_audit_path,
        feature_rows_path=feature_rows_path,
    )
    protocol = JamSuccessorDevelopmentEventPrevalenceProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    expected = authoritative_protocol(
        frozen_at=protocol.frozen_at,
        inputs=parent_inputs,
        parent_protocol_path=parent_protocol_path,
        parent_audit_path=parent_audit_path,
        feature_rows_path=feature_rows_path,
    )
    if (
        protocol != expected
        or not audit_jam_successor_prevalence_protocol(protocol)
        or protocol.network_access_permitted
        or protocol.validation_2021_access_permitted
        or protocol.holdout_2022_access_permitted
        or protocol.future_price_access_permitted
        or protocol.future_label_calculation_permitted
        or protocol.return_calculation_permitted
        or protocol.matched_control_construction_permitted
        or protocol.backtest_permitted
        or protocol.strategy_creation_permitted
        or protocol.signal_creation_permitted
        or protocol.candidate_creation_permitted
        or protocol.paper_eligibility_permitted
        or protocol.testnet_strategy_orders_permitted
        or protocol.production_permitted
        or protocol.live_permitted
    ):
        raise ValueError("Jam prevalence protocol or authority boundary changed")
    return protocol


def _event_query(protocol: JamSuccessorDevelopmentEventPrevalenceProtocol) -> str:
    expressions = []
    for condition in protocol.event_conditions:
        operator = (
            ">=" if condition.comparison == "GREATER_THAN_OR_EQUAL" else "<="
        )
        expressions.append(
            f'"{condition.feature_id}" {operator} '
            f"CAST('{condition.frozen_threshold}' AS DECIMAL(38,18))"
        )
    if tuple(condition.feature_id for condition in protocol.event_conditions) != (
        JAM_PREVALENCE_EVENT_FEATURE_IDS
    ):
        raise ValueError("Jam prevalence event feature order changed")
    selected_features = ",\n".join(
        f'            "{feature_id}"'
        for feature_id in JAM_PREVALENCE_EVENT_FEATURE_IDS
    )
    predicate = "\n            AND ".join(expressions)
    return f"""
        SELECT
            open_time_ms,
            month,
            quality_state,
{selected_features}
        FROM read_parquet(?)
        WHERE quality_state = 'READY'
            AND {predicate}
        ORDER BY open_time_ms
    """


def read_raw_events(
    *,
    protocol: JamSuccessorDevelopmentEventPrevalenceProtocol,
    feature_rows_path: Path,
) -> list[JamPrevalenceInputRow]:
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET threads = 1")
        connection.execute("SET preserve_insertion_order = true")
        (
            calendar_rows,
            ready_rows,
            first_time,
            last_time,
            distinct_months,
            non_development_rows,
        ) = connection.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE quality_state = 'READY'),
                min(open_time_ms),
                max(open_time_ms),
                count(DISTINCT month),
                count(*) FILTER (
                    WHERE month < '2019-01' OR month > '2020-12'
                )
            FROM read_parquet(?)
            """,
            [str(feature_rows_path.resolve())],
        ).fetchone()
        expected_first = int(datetime(2019, 1, 1, tzinfo=UTC).timestamp() * 1_000)
        expected_last = int(
            datetime(2020, 12, 31, 23, 59, tzinfo=UTC).timestamp() * 1_000
        )
        if (
            int(calendar_rows) != protocol.calendar_row_count
            or int(ready_rows) != protocol.ready_row_count
            or int(first_time) != expected_first
            or int(last_time) != expected_last
            or int(distinct_months) != 24
            or int(non_development_rows)
        ):
            raise ValueError("Jam prevalence source rows changed")
        rows = connection.execute(
            _event_query(protocol),
            [str(feature_rows_path.resolve())],
        ).fetchall()
    finally:
        connection.close()
    return [
        JamPrevalenceInputRow(
            open_time_ms=int(row[0]),
            month=str(row[1]),
            quality_state=str(row[2]),
            **{
                feature_id: Decimal(row[index])
                for index, feature_id in enumerate(
                    JAM_PREVALENCE_EVENT_FEATURE_IDS,
                    start=3,
                )
            },
        )
        for row in rows
    ]


def run_prevalence(args) -> JamSuccessorDevelopmentEventPrevalenceResult:
    if args.output.exists() or args.event_ledger.exists():
        raise ValueError("Jam prevalence result or event ledger already exists")
    protocol = load_run_inputs(
        protocol_path=args.protocol,
        parent_protocol_path=args.parent_protocol,
        parent_audit_path=args.parent_audit,
        feature_rows_path=args.feature_rows,
    )
    raw_rows = read_raw_events(
        protocol=protocol,
        feature_rows_path=args.feature_rows,
    )
    records = build_event_ledger(
        raw_rows,
        conditions=protocol.event_conditions,
        minimum_separation_minutes=protocol.minimum_event_separation_minutes,
    )
    _write_ledger(args.event_ledger, records)
    generated_at = (
        datetime.fromisoformat(args.generated_at.replace("Z", "+00:00"))
        if args.generated_at
        else datetime.now(UTC)
    )
    result = build_jam_successor_prevalence_result(
        records=records,
        generated_at=generated_at,
        protocol_evidence_hash=protocol.protocol_evidence_hash,
        runner_contract_hash=runner_contract_hash(),
        parent_event_protocol_evidence_hash=(
            protocol.parent_event_protocol_evidence_hash
        ),
        feature_rows_file_sha256=protocol.feature_rows_file_sha256,
        feature_rows_schema_hash=protocol.feature_rows_schema_hash,
        event_ledger_file_sha256=file_sha256(args.event_ledger),
        event_ledger_bytes=args.event_ledger.stat().st_size,
        limitations=[
            (
                "The result measures only event frequency, chronological "
                "suppression, calendar distribution, and concentration."
            ),
            (
                "The immutable ledger contains all raw matches and their "
                "accepted or suppressed status."
            ),
            (
                "Only frozen causal feature rows from 2019-2020 development were "
                "read."
            ),
            (
                "No aggregate-trade row or price after an event was opened."
            ),
            (
                "No future label, return, path statistic, fee, slippage, control "
                "outcome, or backtest was calculated."
            ),
            (
                "The 2021 validation and 2022 holdout partitions remained sealed."
            ),
            (
                "Every prevalence gate is conjunctive and no failed gate may be "
                "waived."
            ),
            (
                "A prevalence failure retires this event definition without "
                "threshold relaxation."
            ),
            (
                "A prevalence pass establishes sample availability only and does "
                "not establish predictive or economic edge."
            ),
            (
                "Outcome calculation requires separate explicit authorization."
            ),
            (
                "This result creates no strategy, signal, candidate, paper "
                "eligibility, or order authority."
            ),
            (
                "Exact Pine parity remains unavailable because the event uses "
                "aggregate-trade aggressor identity."
            ),
            (
                "Production, live, real capital, and real profit remain disabled "
                "and zero."
            ),
        ],
    )
    if not audit_jam_successor_prevalence_result(result):
        raise ValueError("Jam prevalence result failed internal audit")
    _write_result(args.output, result)
    print(
        f"WROTE {args.output} {result.result_evidence_hash} "
        f"raw={result.raw_event_count} accepted={result.accepted_event_count} "
        f"suppressed={result.suppressed_event_count} "
        f"gates={result.passed_gate_count}/7 decision={result.decision} "
        "labels=0 returns=0 validation=False holdout=False",
        flush=True,
    )
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the frozen Jam event predicate and prevalence gates on "
            "2019-2020 development features without outcomes or returns."
        )
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=DEFAULT_PREVALENCE_PROTOCOL,
    )
    parser.add_argument(
        "--parent-protocol",
        type=Path,
        default=DEFAULT_PARENT_PROTOCOL,
    )
    parser.add_argument(
        "--parent-audit",
        type=Path,
        default=DEFAULT_PARENT_AUDIT,
    )
    parser.add_argument(
        "--feature-rows",
        type=Path,
        default=DEFAULT_FEATURE_ROWS,
    )
    parser.add_argument(
        "--event-ledger",
        type=Path,
        default=DEFAULT_EVENT_LEDGER,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default="")
    return parser.parse_args()


def main() -> int:
    try:
        run_prevalence(parse_args())
    except (OSError, ValueError, duckdb.Error) as exc:
        print(f"FAIL {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
