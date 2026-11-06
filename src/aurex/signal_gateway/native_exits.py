"""Fresh acquired-candle paper exits; modeled OHLC outcomes, never real fills."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.models import PaperOrder
from aurex.signal_gateway.native_bars import BASE_SECONDS, ClosedBar, NativeBarError
from aurex.signal_gateway.native_recovery import (
    ONLINE_EXIT_FILL_MODEL,
    NativeRecoveryEvidence,
    _manage_position_exit,
    _verify_position_exit,
)
from aurex.signal_gateway.native_source import NativeObservationAdmission, NativePublicSourceBinding


class NativeOnlineExitEvidence(NativeRecoveryEvidence):
    schema_version: Literal["native_online_paper_exit_v1"] = "native_online_paper_exit_v1"
    fill_model: Literal["native_ohlc_online_exit_v1", "native_ohlc_recovery_v1"]
    source_acquisition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def manage_online_exit(
    session: Session,
    settings: Settings,
    scope: dict,
    bar: ClosedBar,
    now: datetime,
    source: NativePublicSourceBinding,
    admission: NativeObservationAdmission,
    previous_hash: str | None,
) -> NativeOnlineExitEvidence:
    """No entry, seed or stale recovery fallback. All effects share the receipt transaction."""
    admission.check_receipt(source, previous_hash, now)
    if source.purpose != "CLOSED_BAR" or source.reconstruct() != (bar,):
        raise NativeBarError("online_exit_requires_one_acquired_closed_bar")
    closed_at = bar.timestamp + timedelta(seconds=BASE_SECONDS)
    if not closed_at <= now <= closed_at + timedelta(seconds=180):
        raise NativeBarError("online_exit_requires_fresh_closed_bar")
    managed = _manage_position_exit(session, settings, scope, bar, now, ONLINE_EXIT_FILL_MODEL)
    model = (
        session.get(PaperOrder, managed.position.order_id).fill_model
        if managed.position is not None
        else ONLINE_EXIT_FILL_MODEL
    )
    return NativeOnlineExitEvidence(
        **managed.model_dump(exclude={"schema_version"}),
        fill_model=model,
        source_acquisition_sha256=source.acquisition_sha256,
    )


def verify_online_exit(
    session: Session,
    settings: Settings,
    scope: dict,
    bar: ClosedBar,
    evidence: NativeOnlineExitEvidence,
    processed_at: datetime,
) -> None:
    _verify_position_exit(
        session, settings, scope, bar, evidence, processed_at, evidence.fill_model
    )
