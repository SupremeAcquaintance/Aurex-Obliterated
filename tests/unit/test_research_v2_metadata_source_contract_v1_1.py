import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2P01MetadataSourceContract,
)
from aurex.backtest_engine.research_v2_metadata_source_contract_v1_1 import (
    V2P01MetadataSourceContractV1_1,
    audit_v2_p01_metadata_source_contract_v1_1,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_p01_metadata_source_contract_v1_1 import (
    authoritative_contract,
    load_inputs,
)


class Args:
    foundation_protocol = Path(
        "data/evidence/v2_derivatives_foundation_protocol_v1.json"
    )
    foundation_result = Path(
        "data/evidence/v2_derivatives_foundation_result_v1.json"
    )
    charter = Path("data/evidence/v2_mechanism_discovery_charter_v1.json")
    theory_screen = Path("data/evidence/v2_mechanism_theory_screen_v1.json")
    superseded_contract = Path(
        "data/evidence/v2_p01_metadata_source_contract_v1.json"
    )


def contracts() -> tuple[
    V2P01MetadataSourceContract,
    V2P01MetadataSourceContractV1_1,
]:
    superseded, screen = load_inputs(Args())
    revised = authoritative_contract(
        frozen_at=datetime(2026, 7, 28, 15, tzinfo=UTC),
        superseded=superseded,
        screen=screen,
    )
    return superseded, revised


def rehash(payload: dict) -> dict:
    payload["contract_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "contract_evidence_hash"
        }
    )
    return payload


def test_v1_1_changes_only_declared_source_access_fields() -> None:
    superseded, revised = contracts()
    audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=revised,
        superseded_contract=superseded,
    )

    assert audit["status"] == "PASS"
    assert revised.supersedes_contract_evidence_hash == (
        superseded.contract_evidence_hash
    )
    assert len(revised.replaced_source_ids) == 2
    assert revised.return_calculation_permitted is False
    assert revised.authorizes_full_archive_acquisition is False
    assert revised.creates_candidate is False
    assert revised.creates_live_eligibility is False


def test_v1_1_refuses_permission_or_marker_drift() -> None:
    superseded, revised = contracts()
    payload = revised.model_dump()
    payload["source_targets"][1]["required_markers"].pop()
    drifted = V2P01MetadataSourceContractV1_1.model_validate(rehash(payload))

    audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=drifted,
        superseded_contract=superseded,
    )
    assert audit["status"] == "FAIL"
    assert any(
        reason.startswith("SOURCE_SEMANTIC_DRIFT:")
        for reason in audit["reasons"]
    )

    payload = revised.model_dump()
    payload["authorizes_full_archive_acquisition"] = True
    with pytest.raises(ValidationError):
        V2P01MetadataSourceContractV1_1.model_validate(rehash(payload))


def test_v1_1_refuses_undeclared_source_replacement() -> None:
    superseded, revised = contracts()
    payload = revised.model_dump()
    payload["source_targets"][0]["requested_url"] = (
        "https://raw.githubusercontent.com/binance/"
        "binance-public-data/master/README.txt"
    )
    drifted = V2P01MetadataSourceContractV1_1.model_validate(rehash(payload))

    audit = audit_v2_p01_metadata_source_contract_v1_1(
        contract=drifted,
        superseded_contract=superseded,
    )
    assert audit["status"] == "FAIL"
    assert (
        "UNDECLARED_SOURCE_CHANGE:BINANCE_PUBLIC_DATA_README"
        in audit["reasons"]
    )


def test_v1_1_contract_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_p01_metadata_source_contract_v1_1.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
