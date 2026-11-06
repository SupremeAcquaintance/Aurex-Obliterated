from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.jam_successor_feature_specification import (
    JAM_FEATURE_IDS,
    aggregate_fixture_trades,
    compute_feature_row,
)
from scripts.freeze_jam_successor_feature_specification import (
    SYNTHETIC_START_MS,
    run_conformance_cases,
    synthetic_fixture,
)


def test_synthetic_fixture_maps_aggressor_side_exactly() -> None:
    trades = synthetic_fixture()
    first = aggregate_fixture_trades(trades)[0]

    assert first.taker_buy_quote_volume == (
        trades[0].price * trades[0].quantity
    )
    assert first.taker_sell_quote_volume == (
        trades[1].price * trades[1].quantity
    )
    assert first.quote_volume == (
        first.taker_buy_quote_volume + first.taker_sell_quote_volume
    )


def test_feature_row_is_ready_only_after_exact_133_minute_window() -> None:
    trades = synthetic_fixture()
    minutes = aggregate_fixture_trades(trades)
    evaluation = SYNTHETIC_START_MS + 132 * 60_000

    row = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )

    assert row.quality_state == "READY"
    assert tuple(row.feature_values) == JAM_FEATURE_IDS
    assert len(row.feature_values) == 17
    assert all(
        value.as_tuple().exponent == -18 for value in row.feature_values.values()
    )


def test_future_minute_cannot_change_current_feature_row() -> None:
    evaluation = SYNTHETIC_START_MS + 132 * 60_000
    current = compute_feature_row(
        minutes=aggregate_fixture_trades(synthetic_fixture()),
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )
    future = compute_feature_row(
        minutes=aggregate_fixture_trades(
            synthetic_fixture(include_future=True)
        ),
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )

    assert future == current


@pytest.mark.parametrize(
    ("partition_start", "quarantine_offset", "drop_current", "expected"),
    [
        (100, None, False, "PARTITION_RESET_WARMUP"),
        (0, 0, False, "SOURCE_QUARANTINE"),
        (0, 10, False, "POST_DEFECT_WARMUP"),
        (0, None, True, "NO_AGGTRADE_MINUTE"),
    ],
)
def test_quality_state_withholds_entire_vector(
    partition_start: int,
    quarantine_offset: int | None,
    drop_current: bool,
    expected: str,
) -> None:
    evaluation = SYNTHETIC_START_MS + 132 * 60_000
    minutes = aggregate_fixture_trades(synthetic_fixture())
    if drop_current:
        minutes = minutes[:-1]
    quarantine = (
        set()
        if quarantine_offset is None
        else {evaluation - quarantine_offset * 60_000}
    )

    row = compute_feature_row(
        minutes=minutes,
        evaluation_open_time_ms=evaluation,
        partition_start_ms=(
            SYNTHETIC_START_MS
            if partition_start == 0
            else evaluation - partition_start * 60_000
        ),
        quarantined_open_times=quarantine,
    )

    assert row.quality_state == expected
    assert row.feature_values == {}


def test_zero_mad_withholds_robust_features() -> None:
    evaluation = SYNTHETIC_START_MS + 132 * 60_000
    row = compute_feature_row(
        minutes=aggregate_fixture_trades(
            synthetic_fixture(constant_baseline=True)
        ),
        evaluation_open_time_ms=evaluation,
        partition_start_ms=SYNTHETIC_START_MS,
    )

    assert row.quality_state == "DEGENERATE_ROBUST_SCALE"
    assert row.feature_values == {}


def test_all_nine_conformance_cases_are_hash_bound() -> None:
    cases = run_conformance_cases()

    assert len(cases) == 9
    assert all(case.passed for case in cases)
    assert [case.case_id for case in cases] == sorted(
        case.case_id for case in cases
    )


def test_minute_invariant_rejects_quote_side_drift() -> None:
    minute = aggregate_fixture_trades(synthetic_fixture())[0]
    payload = minute.model_dump()
    payload["taker_sell_quote_volume"] += Decimal("0.00000001")

    with pytest.raises(ValidationError, match="minute invariant changed"):
        type(minute).model_validate(payload)
