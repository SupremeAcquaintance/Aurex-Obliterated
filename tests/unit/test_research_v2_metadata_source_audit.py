import hashlib
import subprocess
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from aurex.backtest_engine.research_v2_metadata_source_audit import (
    V2MetadataSourceObservation,
    V2P01MetadataSourceAuditResult,
    audit_v2_p01_metadata_source_audit_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from scripts.run_v2_p01_metadata_source_audit import (
    authoritative_result,
    fetch_source,
    load_contract,
    runner_contract_hash,
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
    metadata_contract = Path(
        "data/evidence/v2_p01_metadata_source_contract_v1_1.json"
    )
    superseded_contract = Path(
        "data/evidence/v2_p01_metadata_source_contract_v1.json"
    )


class FakeResponse:
    def __init__(self, *, payload: bytes, final_url: str):
        self._stream = BytesIO(payload)
        self._final_url = final_url
        self.status = 200
        self.headers = {"Content-Type": "text/plain; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._final_url

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def fake_observations() -> list[V2MetadataSourceObservation]:
    contract = load_contract(Args())
    checked_at = datetime(2026, 7, 28, 13, tzinfo=UTC)
    return [
        V2MetadataSourceObservation(
            source_id=target.source_id,
            requested_url=target.requested_url,
            final_url=target.requested_url,
            checked_at=checked_at,
            http_status=200,
            content_type="text/plain",
            response_bytes=128,
            response_sha256=hashlib.sha256(
                target.source_id.encode("ascii")
            ).hexdigest(),
            required_markers=target.required_markers,
            found_markers=target.required_markers,
            missing_markers=[],
        )
        for target in contract.source_targets
    ]


def result() -> V2P01MetadataSourceAuditResult:
    return authoritative_result(
        generated_at=datetime(2026, 7, 28, 13, tzinfo=UTC),
        contract=load_contract(Args()),
        observations=fake_observations(),
    )


def rehash(payload: dict) -> dict:
    payload["result_evidence_hash"] = universe_evidence_hash(
        {
            key: value
            for key, value in payload.items()
            if key != "result_evidence_hash"
        }
    )
    return payload


def test_v2_metadata_audit_preserves_six_unresolved_requirements() -> None:
    frozen = result()
    contract = load_contract(Args())

    assert frozen.ready_historical_requirement_count == 2
    assert frozen.unresolved_historical_requirement_count == 6
    assert frozen.conservative_override_requirement_count == 5
    assert frozen.credentials_used is False
    assert frozen.private_endpoint_calls_made is False
    assert frozen.response_bodies_persisted is False
    assert frozen.authorizes_full_archive_acquisition is False
    assert frozen.authorizes_return_testing is False
    assert frozen.creates_candidate is False
    assert frozen.opens_development is False
    assert frozen.creates_live_eligibility is False
    assert (
        audit_v2_p01_metadata_source_audit_result(
            result=frozen,
            contract=contract,
            current_runner_contract_hash=runner_contract_hash(),
        )["status"]
        == "PASS"
    )


def test_v2_metadata_audit_refuses_relabeling_current_rules_historical() -> None:
    payload = result().model_dump()
    payload["requirement_assessments"][3]["status"] = (
        "READY_HISTORICAL_ARCHIVE"
    )
    payload["requirement_assessments"][3][
        "blocks_direct_historical_replay"
    ] = False
    payload["requirement_assessments"][3][
        "conservative_research_override_permitted"
    ] = False
    payload["requirement_assessments"][3][
        "required_protocol_treatment"
    ] = "USE_IMMUTABLE_ARCHIVE_AND_AUDIT"

    with pytest.raises(ValidationError, match="status changed"):
        V2P01MetadataSourceAuditResult.model_validate(rehash(payload))


def test_v2_metadata_source_fetch_requires_every_marker() -> None:
    target = load_contract(Args()).source_targets[0]
    payload = "\n".join(target.required_markers[:-1]).encode("utf-8")

    def opener(request, timeout):
        del request, timeout
        return FakeResponse(payload=payload, final_url=target.requested_url)

    with pytest.raises(ValueError, match="failed after 1 attempts"):
        fetch_source(
            target=target,
            checked_at=datetime(2026, 7, 28, 13, tzinfo=UTC),
            timeout_seconds=1,
            retry_attempts=1,
            opener=opener,
            sleeper=lambda seconds: None,
        )


def test_v2_metadata_source_fetch_hashes_and_discards_body() -> None:
    target = load_contract(Args()).source_targets[0]
    payload = "\n".join(target.required_markers).encode("utf-8")

    def opener(request, timeout):
        del request, timeout
        return FakeResponse(payload=payload, final_url=target.requested_url)

    observation = fetch_source(
        target=target,
        checked_at=datetime(2026, 7, 28, 13, tzinfo=UTC),
        timeout_seconds=1,
        retry_attempts=1,
        opener=opener,
        sleeper=lambda seconds: None,
    )

    assert observation.response_sha256 == hashlib.sha256(payload).hexdigest()
    assert observation.response_bytes == len(payload)
    assert observation.response_body_persisted is False
    assert observation.missing_markers == []


def test_v2_metadata_audit_script_supports_direct_invocation() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_v2_p01_metadata_source_audit.py",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
