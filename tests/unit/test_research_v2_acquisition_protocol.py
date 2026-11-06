import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_acquisition_protocol import (
    V2_COMPLETE_SYMBOLS,
    V2_EXCLUDED_INCOMPLETE_SYMBOLS,
    V2_PILOT_MONTHS,
    V2_PILOT_SYMBOLS,
    V2DerivativesAcquisitionProtocol,
    audit_v2_derivatives_acquisition_protocol,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.freeze_v2_acquisition_protocol import (
    authoritative_protocol,
    load_inputs,
)


class Args:
    census_contract = Path(
        "data/evidence/v2_derivatives_source_census_contract_v1.json"
    )
    census_result = Path(
        "data/evidence/v2_derivatives_source_census_result_v1.json"
    )


def protocol() -> V2DerivativesAcquisitionProtocol:
    contract, result = load_inputs(Args())
    return authoritative_protocol(
        frozen_at=datetime(2026, 7, 28, 1, tzinfo=UTC),
        contract=contract,
        result=result,
    )


def rehash(payload: dict) -> dict:
    payload["protocol_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "protocol_evidence_hash"
        }
    )
    return payload


def test_v2_acquisition_protocol_authorizes_only_exact_pilot() -> None:
    frozen = protocol()

    assert frozen.complete_source_symbols == V2_COMPLETE_SYMBOLS
    assert frozen.excluded_incomplete_symbols == (
        V2_EXCLUDED_INCOMPLETE_SYMBOLS
    )
    assert frozen.pilot_symbols == V2_PILOT_SYMBOLS
    assert frozen.pilot_months == V2_PILOT_MONTHS
    assert len(frozen.targets) == 54
    assert len({target.key for target in frozen.targets}) == 54
    assert frozen.authorizes_archive_payload_download is True
    assert frozen.authorized_payload_scope == "EXACT_54_PILOT_TARGETS_ONLY"
    assert frozen.authorizes_full_archive_payload_download is False
    assert frozen.authorizes_market_data_import is False
    assert frozen.authorizes_strategy_return_calculation is False
    assert frozen.creates_candidate is False
    assert frozen.creates_live_eligibility is False
    assert audit_v2_derivatives_acquisition_protocol(frozen)
    assert V2DerivativesAcquisitionProtocol.model_validate_json(
        frozen.model_dump_json()
    ) == frozen


def test_v2_acquisition_protocol_pins_census_checksums() -> None:
    frozen = protocol()

    assert all(len(target.census_checksum_sha256) == 64 for target in frozen.targets)
    assert frozen.integrity.checksum_refresh_before_archive_get is True
    assert frozen.integrity.refreshed_checksum_must_equal_census_checksum is True
    assert frozen.integrity.archive_hash_must_equal_refreshed_checksum is True
    assert frozen.integrity.checksum_revision_action == (
        "BLOCK_AND_FREEZE_SOURCE_REVISION_DIVERGENCE"
    )


def test_v2_acquisition_protocol_refuses_scope_expansion() -> None:
    payload = protocol().model_dump()
    payload["pilot_symbols"][-1] = "CFXUSDT"

    with pytest.raises(ValidationError, match="pilot-symbol rule changed"):
        V2DerivativesAcquisitionProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["authorizes_full_archive_payload_download"] = True
    with pytest.raises(ValidationError):
        V2DerivativesAcquisitionProtocol.model_validate(rehash(payload))

    payload = protocol().model_dump()
    payload["authorizes_strategy_return_calculation"] = True
    with pytest.raises(ValidationError):
        V2DerivativesAcquisitionProtocol.model_validate(rehash(payload))


def test_v2_acquisition_protocol_refuses_resource_limit_relaxation() -> None:
    payload = protocol().model_dump()
    payload["resource_limits"]["maximum_pilot_compressed_bytes"] *= 2

    with pytest.raises(ValidationError):
        V2DerivativesAcquisitionProtocol.model_validate(rehash(payload))


def test_v2_acquisition_protocol_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/freeze_v2_acquisition_protocol.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
