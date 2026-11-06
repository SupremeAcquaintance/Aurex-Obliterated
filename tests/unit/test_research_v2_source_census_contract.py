import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_source_census_contract import (
    V2SourceCensusContract,
    audit_v2_source_census_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_source_census_contract import (
    authoritative_contract,
    load_inputs,
)


class Args:
    evidence_root = Path("data/evidence")
    capability_audit = evidence_root / "v2_capability_audit_v1.json"
    u1_result = evidence_root / "u1_primary_mechanism_result_v1.json"
    universe = evidence_root / "market_universe_manifest_v1.json"
    contamination = evidence_root / "strategy_contamination_ledger_v1.json"


def contract() -> V2SourceCensusContract:
    inputs = load_inputs(Args())
    return authoritative_contract(
        frozen_at=datetime(2026, 7, 27, 16, tzinfo=UTC),
        capability=inputs[0],
        u1_result=inputs[1],
        universe=inputs[2],
        contamination=inputs[3],
    )


def rehash(payload: dict) -> dict:
    payload["contract_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "contract_evidence_hash"
        }
    )
    return payload


def test_v2_source_contract_fixes_metadata_only_5040_check_census() -> None:
    frozen = contract()

    assert len(frozen.symbols) == 35
    assert len(frozen.months) == 24
    assert len(frozen.families) == 6
    assert frozen.expected_checksum_checks == 5040
    assert frozen.decision_rule.minimum_complete_symbols == 20
    assert frozen.authorizes_archive_listing_and_checksum_census is True
    assert frozen.authorizes_archive_payload_download is False
    assert frozen.authorizes_market_data_import is False
    assert frozen.authorizes_strategy_return_calculation is False
    assert frozen.authorizes_mechanism_selection is False
    assert audit_v2_source_census_contract(frozen) is True
    assert V2SourceCensusContract.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_v2_source_contract_refuses_window_or_symbol_substitution() -> None:
    payload = contract().model_dump()
    payload["months"] = payload["months"][1:] + ["2025-01"]

    with pytest.raises(ValidationError, match="exact 24 months"):
        V2SourceCensusContract.model_validate(rehash(payload))

    payload = contract().model_dump()
    payload["symbols"][-1] = "FAKEUSDT"
    with pytest.raises(ValidationError, match="frozen 35-symbol universe"):
        V2SourceCensusContract.model_validate(rehash(payload))


def test_v2_source_contract_refuses_payload_permission() -> None:
    payload = contract().model_dump()
    payload["families"][0]["payload_download_authorized"] = True

    with pytest.raises(ValidationError):
        V2SourceCensusContract.model_validate(rehash(payload))


def test_v2_source_contract_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_source_census_contract.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
