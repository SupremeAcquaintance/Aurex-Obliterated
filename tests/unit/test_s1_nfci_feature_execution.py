from datetime import date, timedelta
from pathlib import Path

import pytest

from aurex.backtest_engine.s1_nfci_feature_execution import (
    S1NfciFeatureExecutionAddendum,
    S1NfciFeatureExecutionAudit,
    S1NfciFeatureResult,
    S1NfciFeatureResultAudit,
)
from aurex.backtest_engine.s1_nfci_normalization_execution import (
    S1NfciNormalizedRow,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.audit_s1_nfci_feature_result import build_audit
from scripts.freeze_s1_successor_lineage import file_sha256
from scripts.run_s1_nfci_features import (
    DEFAULT_OUTPUT,
    DEFAULT_RESULT,
    build_feature_rows,
    decimal_to_fixed,
    parse_normalized_rows,
    runner_contract_hash,
    serialize_feature_rows,
)
from scripts.run_s1_nfci_normalization import serialize_rows

EXECUTION_ADDENDUM_PATH = Path(
    "data/evidence/s1_nfci_feature_execution_addendum_v1.json"
)
EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_feature_execution_audit_v1.json"
)
RESULT_AUDIT_PATH = Path("data/evidence/s1_nfci_feature_result_audit_v1.json")


def synthetic_normalized_rows() -> tuple[S1NfciNormalizedRow, ...]:
    first_vintage = date(2017, 8, 17)
    return tuple(
        S1NfciNormalizedRow(
            sequence=index + 1,
            target_id=(
                f"{index + 1:03d}-nfci-vintage-"
                f"{(first_vintage + timedelta(days=7 * index)).isoformat()}"
            ),
            source_vintage_date=first_vintage + timedelta(days=7 * index),
            selected_observation_date=(
                first_vintage + timedelta(days=7 * index - 6)
            ),
            release_lag_days=6,
            nfci_value_source_text=f"{index / 1000:.3f}",
            source_raw_path=f"data/evidence/source_snapshots/test-{index + 1}.csv",
            source_raw_sha256=f"{index + 1:064x}",
        )
        for index in range(281)
    )


def test_feature_rows_use_only_current_lag_1_and_lag_4() -> None:
    rows = synthetic_normalized_rows()
    hashes = tuple(
        universe_evidence_hash(row.model_dump(mode="json")) for row in rows
    )

    features = build_feature_rows(rows, source_row_hashes=hashes)

    assert len(features) == 277
    assert features[0].sequence == 5
    assert features[-1].sequence == 281
    assert features[0].nfci_level == "0.004"
    assert features[0].nfci_change_1v == "0.001"
    assert features[0].nfci_change_4v == "0.004"
    assert features[0].source_normalized_row_sha256 == hashes[4]


def test_decimal_to_fixed_canonicalizes_zero() -> None:
    from decimal import Decimal

    assert decimal_to_fixed(Decimal("-0.000")) == "0"
    assert decimal_to_fixed(Decimal("0.120")) == "0.120"


def test_normalized_parser_rejects_row_hash_tamper() -> None:
    rows = synthetic_normalized_rows()
    hashes = tuple(
        universe_evidence_hash(row.model_dump(mode="json")) for row in rows
    )
    tampered = ("0" * 64, *hashes[1:])

    with pytest.raises(ValueError):
        parse_normalized_rows(
            serialize_rows(rows),
            expected_row_hashes=tampered,
        )


def test_feature_jsonl_serialization_is_byte_stable() -> None:
    rows = synthetic_normalized_rows()
    hashes = tuple(
        universe_evidence_hash(row.model_dump(mode="json")) for row in rows
    )
    features = build_feature_rows(rows, source_row_hashes=hashes)

    first = serialize_feature_rows(features)
    second = serialize_feature_rows(features)

    assert first == second
    assert first.endswith(b"\n")
    assert b'"nfci_change_1v":"0.001"' in first
    assert b'"btc_' not in first
    assert b'"signal"' not in first


def test_feature_execution_lineage_and_result_reconstruct() -> None:
    addendum = S1NfciFeatureExecutionAddendum.model_validate_json(
        EXECUTION_ADDENDUM_PATH.read_text(encoding="utf-8")
    )
    execution_audit = S1NfciFeatureExecutionAudit.model_validate_json(
        EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S1NfciFeatureResult.model_validate_json(
        DEFAULT_RESULT.read_text(encoding="utf-8")
    )
    result_audit = S1NfciFeatureResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert execution_audit.addendum_file_sha256 == file_sha256(
        EXECUTION_ADDENDUM_PATH
    )
    assert execution_audit.addendum_evidence_hash == addendum.addendum_evidence_hash
    assert addendum.runner_contract_hash == runner_contract_hash()
    assert result.runner_contract_hash == addendum.runner_contract_hash
    assert result.feature_dataset_file_sha256 == file_sha256(DEFAULT_OUTPUT)
    assert result_audit == build_audit(
        result_path=DEFAULT_RESULT,
        feature_dataset_path=DEFAULT_OUTPUT,
        audited_at=result_audit.audited_at,
    )
    assert result.strategy_candidates_created == 0
    assert result.btc_market_fields_inspected == ()
    assert result.return_metrics_calculated == ()
    assert result.orders_submitted == 0
