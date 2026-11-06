from datetime import date
from decimal import Decimal
from pathlib import Path

from aurex.backtest_engine.s1_nfci_raw_pilot import (
    S1NfciRawPilotAudit,
    S1NfciRawPilotProtocol,
    S1NfciRawPilotResult,
)
from scripts.audit_s1_nfci_raw_pilot import build_audit
from scripts.freeze_s1_nfci_raw_pilot_protocol import build_protocol
from scripts.run_s1_nfci_raw_pilot import build_comparison, build_result, parse_snapshot

PROTOCOL_PATH = Path("data/evidence/s1_nfci_raw_pilot_protocol_v1.json")
RESULT_PATH = Path("data/evidence/s1_nfci_raw_pilot_result_v1.json")
AUDIT_PATH = Path("data/evidence/s1_nfci_raw_pilot_audit_v1.json")


def test_parse_snapshot_preserves_point_in_time_structure(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_text(
        "observation_date,NFCI\n"
        "2019-12-13,-0.10\n"
        "2019-12-20,.\n"
        "2019-12-27,-0.20\n",
        encoding="utf-8",
    )

    summary, rows = parse_snapshot(snapshot, vintage_date=date(2020, 1, 1))

    assert summary.row_count == 3
    assert summary.valid_numeric_row_count == 2
    assert summary.missing_value_row_count == 1
    assert summary.post_vintage_observation_count == 0
    assert summary.release_lag_days == 5
    assert rows[date(2019, 12, 13)] == Decimal("-0.10")


def test_stored_s1_nfci_pilot_reconstructs() -> None:
    protocol = S1NfciRawPilotProtocol.model_validate_json(
        PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    result = S1NfciRawPilotResult.model_validate_json(
        RESULT_PATH.read_text(encoding="utf-8")
    )
    audit = S1NfciRawPilotAudit.model_validate_json(
        AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert protocol == build_protocol(frozen_at=protocol.frozen_at)
    assert result == build_result(
        protocol_path=PROTOCOL_PATH,
        protocol=protocol,
        downloads=result.downloads,
        comparison=build_comparison(result.downloads),
        completed_at=result.completed_at,
    )
    assert audit == build_audit(
        protocol_path=PROTOCOL_PATH,
        result_path=RESULT_PATH,
        audited_at=audit.audited_at,
    )
    assert result.btc_market_fields_inspected == ()
    assert result.return_metrics_calculated == ()
    assert result.authorizes_testnet_strategy_orders is False
