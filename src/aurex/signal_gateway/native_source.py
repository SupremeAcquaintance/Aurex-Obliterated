"""Retained public-data lineage, deliberately not live-origin or entry authority."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    ClosedBar,
    NativeBarCursor,
    NativeBarError,
    aware_utc,
    content_hash,
)
from aurex.signal_gateway.native_market_data import (
    MAX_BATCH_SECONDS,
    PublicCandleEvidence,
    verify_public_evidence,
)

SourcePurpose = Literal["SEED", "CLOSED_BAR", "RECOVERY"]


class NativeObservationAdmission(BaseModel):
    """Operational call lineage, not a transferable TLS signature or trading grant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["native_public_observation_v1"] = "native_public_observation_v1"
    admission: Literal["acquisition_owned_public_https"] = "acquisition_owned_public_https"
    started_at: datetime
    finished_at: datetime
    expected_previous_evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    forward_qualifying: Literal[False] = False
    execution_authority: Literal[False] = False

    @field_validator("started_at", "finished_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return aware_utc(value)

    def check_receipt(
        self,
        source: "NativePublicSourceBinding",
        previous_hash: str | None,
        processed_at: datetime,
    ) -> None:
        acquisition = source.acquisition
        if acquisition.transport != "public_https" or source.purpose == "RECOVERY":
            raise NativeBarError("observation_requires_public_acquisition_without_recovery")
        if self.expected_previous_evidence_hash != previous_hash:
            raise NativeBarError("observation_expected_head_changed")
        if not (
            self.started_at
            <= acquisition.clock.requested_at
            <= acquisition.pages[-1].received_at
            <= self.finished_at
            <= processed_at
        ) or self.finished_at - self.started_at > timedelta(seconds=MAX_BATCH_SECONDS):
            raise NativeBarError("observation_acquisition_timing_invalid")


class NativePublicSourceBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["native_public_source_binding_v1"] = "native_public_source_binding_v1"
    purpose: SourcePurpose
    acquisition: PublicCandleEvidence
    acquisition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    admission: Literal["retained_evidence_reconstruction"] = "retained_evidence_reconstruction"
    forward_qualifying: Literal[False] = False
    execution_authority: Literal[False] = False

    def reconstruct(self) -> tuple[ClosedBar, ...]:
        if content_hash(self.acquisition.model_dump(mode="json")) != self.acquisition_sha256:
            raise NativeBarError("source_acquisition_hash_mismatch")
        bars = verify_public_evidence(self.acquisition)
        if self.purpose != "SEED" and len(bars) != 1:
            raise NativeBarError("source_resume_requires_one_candle")
        return bars

    def check_receipt(
        self,
        *,
        bar: ClosedBar,
        checkpoint: NativeBarCursor,
        sequence: int,
        processed_at: datetime,
    ) -> None:
        bars = self.reconstruct()
        expected_feed = (
            "fixture" if self.acquisition.transport == "injected" else "binance_spot_public"
        )
        if checkpoint.feed_id != expected_feed:
            raise NativeBarError("source_transport_scope_mismatch")
        if bars[-1] != bar:
            raise NativeBarError("source_processed_candle_mismatch")
        if self.acquisition.pages[-1].received_at > processed_at:
            raise NativeBarError("source_received_after_processing")
        if self.purpose == "SEED":
            if (
                sequence != 1
                or len(bars) != checkpoint.bar_count
                or self.acquisition.first_open != checkpoint.first_open
                or self.acquisition.candles_sha256 != checkpoint.history_sha256
            ):
                raise NativeBarError("source_seed_checkpoint_mismatch")
        elif sequence == 1:
            raise NativeBarError("source_resume_without_seed")
        if self.purpose != "RECOVERY" and processed_at - bar.timestamp > timedelta(
            seconds=BASE_SECONDS + 180
        ):
            raise NativeBarError("source_observation_is_stale")


def bind_public_source(
    evidence: PublicCandleEvidence, purpose: SourcePurpose
) -> NativePublicSourceBinding:
    # Revalidate a detached snapshot; model_copy/model_construct can bypass validation.
    evidence = PublicCandleEvidence.model_validate(evidence.model_dump(mode="json"))
    binding = NativePublicSourceBinding(
        purpose=purpose,
        acquisition=evidence,
        acquisition_sha256=content_hash(evidence.model_dump(mode="json")),
    )
    binding.reconstruct()
    return binding
