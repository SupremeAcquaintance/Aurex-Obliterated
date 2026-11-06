import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_metadata_source_contract import (
    V2P01MetadataSourceContract,
    audit_v2_p01_metadata_source_contract,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_p01_metadata_source_contract import (
    authoritative_contract,
    load_theory_screen,
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


def contract() -> V2P01MetadataSourceContract:
    return authoritative_contract(
        frozen_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        screen=load_theory_screen(Args()),
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


def test_v2_metadata_contract_is_bounded_and_no_return() -> None:
    frozen = contract()

    assert len(frozen.source_targets) == 4
    assert len(frozen.requirement_ids) == 8
    assert frozen.maximum_http_requests == 4
    assert frozen.credentials_permitted is False
    assert frozen.private_endpoint_calls_permitted is False
    assert frozen.market_data_numeric_values_permitted is False
    assert frozen.return_calculation_permitted is False
    assert frozen.authorizes_full_archive_acquisition is False
    assert frozen.creates_candidate is False
    assert frozen.opens_development is False
    assert frozen.opens_validation is False
    assert frozen.opens_holdout is False
    assert frozen.opens_forward is False
    assert frozen.creates_live_eligibility is False
    assert audit_v2_p01_metadata_source_contract(frozen)


def test_v2_metadata_contract_refuses_credentials_or_outcomes() -> None:
    payload = contract().model_dump()
    payload["credentials_permitted"] = True
    with pytest.raises(ValidationError):
        V2P01MetadataSourceContract.model_validate(rehash(payload))

    payload = contract().model_dump()
    payload["return_metrics_calculated"] = ["net_pl"]
    with pytest.raises(ValidationError, match="must predate observations"):
        V2P01MetadataSourceContract.model_validate(rehash(payload))


def test_v2_metadata_contract_refuses_source_or_requirement_drift() -> None:
    payload = contract().model_dump()
    payload["source_targets"].reverse()
    with pytest.raises(ValidationError, match="set or order changed"):
        V2P01MetadataSourceContract.model_validate(rehash(payload))

    payload = contract().model_dump()
    payload["requirement_ids"].pop()
    with pytest.raises(ValidationError, match="requirement set changed"):
        V2P01MetadataSourceContract.model_validate(rehash(payload))


def test_v2_metadata_contract_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_p01_metadata_source_contract.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
