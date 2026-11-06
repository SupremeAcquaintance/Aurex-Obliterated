from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.universe import (
    normalize_sha256,
    normalize_timestamp,
    universe_evidence_hash,
)

Q1_TRANSPORT_AMENDMENT_SCHEMA_VERSION = (
    "aurex-q1-periodic-flow-payload-transport-amendment-v1"
)


class PeriodicFlowPayloadTransportAmendment(BaseModel):
    schema_version: Literal[
        "aurex-q1-periodic-flow-payload-transport-amendment-v1"
    ] = Q1_TRANSPORT_AMENDMENT_SCHEMA_VERSION
    amendment_id: Literal["q1-periodic-flow-payload-transport-amendment-v1"] = (
        "q1-periodic-flow-payload-transport-amendment-v1"
    )
    frozen_at: datetime
    status: Literal["FROZEN_AFTER_LOCAL_TRANSPORT_DENIAL_BEFORE_HTTP"] = (
        "FROZEN_AFTER_LOCAL_TRANSPORT_DENIAL_BEFORE_HTTP"
    )
    parent_protocol_file_sha256: str
    parent_protocol_evidence_hash: str
    failed_product: Literal["SPOT"] = "SPOT"
    local_transport_request_marker_count: Literal[3] = 3
    local_transport_response_marker_count: Literal[3] = 3
    http_response_count: Literal[0] = 0
    payload_bytes_received: Literal[0] = 0
    archive_files_created: Literal[0] = 0
    marker_file_sha256: dict[str, str] = Field(min_length=6, max_length=6)
    reclassifies_markers_as_pre_http_transport_denials: Literal[True] = True
    replacement_spot_http_attempts_authorized: Literal[3] = 3
    maximum_total_actual_payload_get_attempts: Literal[6] = 6
    original_urls_unchanged: Literal[True] = True
    original_checksums_unchanged: Literal[True] = True
    original_byte_limits_unchanged: Literal[True] = True
    original_parser_and_gates_unchanged: Literal[True] = True
    outcome_and_trading_authority_unchanged: Literal[True] = True
    limitations: tuple[str, ...] = Field(min_length=6)
    amendment_evidence_hash: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("frozen_at")
    @classmethod
    def normalize_frozen_at(cls, value: datetime) -> datetime:
        return normalize_timestamp(value)

    @field_validator(
        "parent_protocol_file_sha256",
        "parent_protocol_evidence_hash",
        "amendment_evidence_hash",
    )
    @classmethod
    def normalize_hashes(cls, value: str) -> str:
        return normalize_sha256(value)

    @model_validator(mode="after")
    def validate_amendment(self) -> PeriodicFlowPayloadTransportAmendment:
        if (
            len(self.marker_file_sha256) != 6
            or self.limitations != tuple(sorted(set(self.limitations)))
        ):
            raise ValueError("Q1 transport amendment evidence changed")
        for path, digest in self.marker_file_sha256.items():
            if (
                not path.startswith(
                    "data/evidence/source_snapshots/"
                    "q1_periodic_flow_payload_pilot_v1/SPOT/"
                )
                or not path.endswith(".json")
            ):
                raise ValueError("Q1 transport marker path changed")
            normalize_sha256(digest)
        expected = universe_evidence_hash(
            self.model_dump(exclude={"amendment_evidence_hash"})
        )
        if self.amendment_evidence_hash != expected:
            raise ValueError("Q1 transport amendment hash changed")
        return self


def build_periodic_flow_transport_amendment(
    **values,
) -> PeriodicFlowPayloadTransportAmendment:
    payload = {
        "schema_version": Q1_TRANSPORT_AMENDMENT_SCHEMA_VERSION,
        "amendment_id": "q1-periodic-flow-payload-transport-amendment-v1",
        "status": "FROZEN_AFTER_LOCAL_TRANSPORT_DENIAL_BEFORE_HTTP",
        **values,
    }
    payload["limitations"] = tuple(sorted(set(payload["limitations"])))
    provisional = PeriodicFlowPayloadTransportAmendment.model_construct(
        **payload,
        amendment_evidence_hash="0" * 64,
    )
    payload = provisional.model_dump()
    payload["amendment_evidence_hash"] = universe_evidence_hash(
        provisional.model_dump(exclude={"amendment_evidence_hash"})
    )
    return PeriodicFlowPayloadTransportAmendment.model_validate(payload)


def audit_periodic_flow_transport_amendment(
    amendment: PeriodicFlowPayloadTransportAmendment,
) -> bool:
    return amendment.amendment_evidence_hash == universe_evidence_hash(
        amendment.model_dump(exclude={"amendment_evidence_hash"})
    )
