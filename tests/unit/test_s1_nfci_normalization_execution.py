from datetime import date
from pathlib import Path

import pytest

from aurex.backtest_engine.s1_nfci_normalization_execution import (
    S1NfciNormalizationExecutionAddendum,
    S1NfciNormalizationExecutionAudit,
    S1NfciNormalizationResult,
    S1NfciNormalizationResultAudit,
    S1NfciNormalizedRow,
)
from scripts.audit_s1_nfci_normalization_result import build_audit
from scripts.freeze_s1_successor_lineage import file_sha256
from scripts.run_s1_nfci_normalization import (
    DEFAULT_OUTPUT,
    DEFAULT_RESULT,
    runner_contract_hash,
    select_latest_nfci,
    serialize_rows,
)

EXECUTION_ADDENDUM_PATH = Path(
    "data/evidence/s1_nfci_normalization_execution_addendum_v1.json"
)
EXECUTION_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_execution_audit_v1.json"
)
RESULT_AUDIT_PATH = Path(
    "data/evidence/s1_nfci_normalization_result_audit_v1.json"
)


def test_select_latest_nfci_preserves_source_decimal_text() -> None:
    selected_date, selected_value, row_count = select_latest_nfci(
        (
            "observation_date,NFCI_20200109\n"
            "2019-12-27,-0.12000\n"
            "2020-01-03,-0.12300\n"
        ),
        expected_value_column="NFCI_20200109",
        vintage_date=date(2020, 1, 9),
    )

    assert selected_date == date(2020, 1, 3)
    assert selected_value == "-0.12300"
    assert row_count == 2


@pytest.mark.parametrize(
    "csv_text",
    (
        (
            "observation_date,NFCI_20200109\n"
            "2020-01-03,-0.1\n"
            "2020-01-03,-0.2\n"
        ),
        "observation_date,NFCI_20200109\n2020-01-10,-0.1\n",
        "observation_date,NFCI_20200109\n2020-01-03,NaN\n",
        "observation_date,NFCI_20200109\n2020-01-03,.\n",
        "observation_date,NFCI_20200109\n2020-01-03, -0.1\n",
    ),
)
def test_select_latest_nfci_rejects_noncausal_or_invalid_rows(csv_text: str) -> None:
    with pytest.raises(ValueError):
        select_latest_nfci(
            csv_text,
            expected_value_column="NFCI_20200109",
            vintage_date=date(2020, 1, 9),
        )


def test_normalized_jsonl_serialization_is_byte_stable() -> None:
    row = S1NfciNormalizedRow(
        sequence=1,
        target_id="001-nfci-vintage-2020-01-09",
        source_vintage_date=date(2020, 1, 9),
        selected_observation_date=date(2020, 1, 3),
        release_lag_days=6,
        nfci_value_source_text="-0.12300",
        source_raw_path="data/evidence/source_snapshots/test.csv",
        source_raw_sha256="0" * 64,
    )

    first = serialize_rows((row,))
    second = serialize_rows((row,))

    assert first == second
    assert first.endswith(b"\n")
    assert b'"nfci_value_source_text":"-0.12300"' in first
    assert b'"btc_' not in first
    assert b'"signal"' not in first


def test_normalization_execution_lineage_and_result_reconstruct() -> None:
    addendum = S1NfciNormalizationExecutionAddendum.model_validate_json(
        EXECUTION_ADDENDUM_PATH.read_text(encoding="utf-8")
    )
    execution_audit = S1NfciNormalizationExecutionAudit.model_validate_json(
        EXECUTION_AUDIT_PATH.read_text(encoding="utf-8")
    )
    result = S1NfciNormalizationResult.model_validate_json(
        DEFAULT_RESULT.read_text(encoding="utf-8")
    )
    result_audit = S1NfciNormalizationResultAudit.model_validate_json(
        RESULT_AUDIT_PATH.read_text(encoding="utf-8")
    )

    assert execution_audit.addendum_file_sha256 == file_sha256(
        EXECUTION_ADDENDUM_PATH
    )
    assert execution_audit.addendum_evidence_hash == addendum.addendum_evidence_hash
    assert addendum.runner_contract_hash == runner_contract_hash()
    assert result.runner_contract_hash == addendum.runner_contract_hash
    assert result.dataset_file_sha256 == file_sha256(DEFAULT_OUTPUT)
    assert result_audit == build_audit(
        result_path=DEFAULT_RESULT,
        dataset_path=DEFAULT_OUTPUT,
        audited_at=result_audit.audited_at,
    )
    assert result.derived_feature_count == 0
    assert result.btc_market_fields_inspected == ()
    assert result.return_metrics_calculated == ()
    assert result.orders_submitted == 0
