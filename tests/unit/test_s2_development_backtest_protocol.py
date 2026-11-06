from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.s2_development_backtest import (
    S2_BACKTEST_PROTOCOL_NEXT,
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestProtocolAudit,
)
from scripts.audit_s2_development_backtest_protocol import build_audit
from scripts.freeze_s2_development_backtest_protocol import (
    MEASUREMENT_DATASET_PATH,
    PRICE_DATASET_PATH,
    PROJECT_ROOT,
    SOURCE_RESULT_PATH,
    build_protocol,
)

FROZEN_AT = datetime(2026, 8, 30, 21, 0, tzinfo=UTC)


def test_s2_backtest_protocol_freezes_exact_preregistered_calculation() -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert S2DevelopmentBacktestProtocol.model_validate_json(
        protocol.model_dump_json()
    ) == protocol
    assert protocol.candidate_count == 1
    assert protocol.parameter_combination_count == 1
    assert protocol.measurement_row_count == 273
    assert protocol.price_row_count == 273
    assert protocol.interval_count == 272
    assert protocol.first_signal_sequence == 8
    assert protocol.last_signal_sequence == 279
    assert protocol.terminal_price_sequence == 280
    assert protocol.base_cost_bps_per_fill == "15"
    assert protocol.stress_cost_bps_per_fill == "22.5"
    assert protocol.bootstrap_resamples == 10_000
    assert protocol.bootstrap_seed == 2718
    assert protocol.bootstrap_lower_order_index_zero_based == 499
    assert protocol.development_gate_count == 15
    assert protocol.next_authorization == S2_BACKTEST_PROTOCOL_NEXT


def test_protocol_freeze_hashes_but_does_not_parse_value_bearing_files(monkeypatch) -> None:
    guarded = {
        (PROJECT_ROOT / SOURCE_RESULT_PATH).resolve(),
        (PROJECT_ROOT / MEASUREMENT_DATASET_PATH).resolve(),
        (PROJECT_ROOT / PRICE_DATASET_PATH).resolve(),
    }
    original = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path.resolve() in guarded:
            raise AssertionError(f"Protocol freeze parsed value-bearing file: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    protocol = build_protocol(frozen_at=FROZEN_AT)

    assert protocol.measurement_values_parsed_during_protocol_freeze == 0
    assert protocol.price_values_parsed_during_protocol_freeze == 0
    assert protocol.returns_calculated_during_protocol_freeze == 0


@pytest.mark.parametrize(
    "field",
    (
        "authorizes_backtest_execution_now",
        "authorizes_historical_screen_access",
        "authorizes_validation_access",
        "authorizes_holdout_access",
        "authorizes_rescue_candidate",
        "authorizes_pine",
        "authorizes_paper",
        "authorizes_testnet_strategy_orders",
        "authorizes_production",
        "authorizes_live",
    ),
)
def test_protocol_rejects_authority_escalation(field: str) -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload[field] = True

    with pytest.raises(ValidationError):
        S2DevelopmentBacktestProtocol.model_validate(payload)


def test_protocol_rejects_formula_change() -> None:
    payload = build_protocol(frozen_at=FROZEN_AT).model_dump(mode="json")
    payload["bootstrap_lower_order_index_zero_based"] = 500

    with pytest.raises(ValidationError):
        S2DevelopmentBacktestProtocol.model_validate(payload)


def test_protocol_audit_reconstructs_frozen_bytes(tmp_path) -> None:
    protocol = build_protocol(frozen_at=FROZEN_AT)
    path = tmp_path / "protocol.json"
    path.write_text(protocol.model_dump_json(indent=2) + "\n", encoding="utf-8")

    audit = build_audit(protocol_path=path, audited_at=FROZEN_AT)

    assert S2DevelopmentBacktestProtocolAudit.model_validate_json(
        audit.model_dump_json()
    ) == audit
    assert audit.measurement_values_parsed == 0
    assert audit.price_values_parsed == 0
    assert audit.returns_calculated == 0
    assert audit.next_authorization == S2_BACKTEST_PROTOCOL_NEXT
