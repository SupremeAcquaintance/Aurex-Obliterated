"""One acquired observation, exit-only or risk-gated Jam transaction per call."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import PaperTrade, Position
from aurex.domain.enums import PositionStatus, TradeStatus
from aurex.signal_gateway.native_bars import MAX_WINDOW_BARS, NativeBarError, aware_utc
from aurex.signal_gateway.native_market_data import (
    CLOSE_DELAY_SECONDS,
    EPOCH,
    STEP,
    PublicCandleClient,
    window_end,
)
from aurex.signal_gateway.native_processing import (
    NativeBarProcessingResult,
    NativeBarProcessor,
    NativeStreamSpec,
    verified_native_history,
)
from aurex.signal_gateway.native_source import NativeObservationAdmission, bind_public_source


@dataclass(frozen=True)
class NativeObservationResult:
    status: Literal[
        "WAITING_FOR_CLOSE", "OBSERVED_NO_ENTRY", "EXITS_MANAGED_NO_ENTRY", "JAM_EVALUATED"
    ]
    next_observation_at: datetime
    processing: NativeBarProcessingResult | None = None


class NativePublicObserver:
    """Own acquisition rather than accepting a caller-supplied packet or transport.

    This boundary assumes trusted local Python code. Its persisted metadata is not
    a signature and grants no live-origin authentication or forward qualification.
    """

    def __init__(self, engine: Engine, settings: Settings) -> None:
        self._processor = NativeBarProcessor(engine, settings)

    def observe(
        self, *, scope: NativeStreamSpec, seed_count: int = 1000
    ) -> NativeObservationResult:
        return self._poll(scope=scope, seed_count=seed_count, manage_exits=False)

    def manage_exits(self, *, scope: NativeStreamSpec) -> NativeObservationResult:
        """Explicit one-candle exit management; cannot initialize a stream or open a trade."""
        return self._poll(scope=scope, seed_count=1, manage_exits=True)

    def evaluate_jam(
        self, *, scope: NativeStreamSpec, config: dict, seed_count: int = 1000
    ) -> NativeObservationResult:
        """Acquire and evaluate one closed bar; paper entry remains risk-gated.

        This opt-in mode starts a new stream and manages its own paper positions.
        No caller candle, decision, equity or fill acknowledgment is accepted.
        """
        from aurex.signal_gateway.native_jam_runtime import JamRuntimeConfig

        config = JamRuntimeConfig.model_validate(config)
        config.bind(scope)
        return self._poll(
            scope=scope,
            seed_count=seed_count,
            manage_exits=False,
            jam_config=config.model_dump(mode="json"),
        )

    def _poll(
        self,
        *,
        scope: NativeStreamSpec,
        seed_count: int,
        manage_exits: bool,
        jam_config: dict | None = None,
    ) -> NativeObservationResult:
        settings = self._processor.settings
        if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
            raise NativeBarError("observation_requires_live_disabled")
        scope = NativeStreamSpec.model_validate(scope.model_dump(mode="json"))
        if scope.feed_id != "binance_spot_public":
            raise NativeBarError("observation_requires_public_stream")
        if type(seed_count) is not int or not 1 <= seed_count <= MAX_WINDOW_BARS:
            raise NativeBarError("observation_seed_size_invalid")
        planned_at = aware_utc(utc_now())
        # Close the consistent read snapshot before any network request. The write
        # transaction later compares this head, never silently applying a stale plan.
        with Session(self._processor.engine, autoflush=False) as session:
            session.execute(text("BEGIN"))
            verified = verified_native_history(session, EPOCH)
            head = verified.head[1] if verified.head else None
            previous_hash = verified.head[0].evidence_hash if verified.head else None
            if head is None and manage_exits:
                raise NativeBarError("online_exit_requires_initialized_stream")
            if head is not None:
                if (head.jam_decision is None) != (jam_config is None):
                    raise NativeBarError("jam_runtime_stream_mode_changed")
                if jam_config is not None and head.jam_decision["config"] != jam_config:
                    raise NativeBarError("jam_runtime_config_changed")
                if head.scope != scope:
                    raise NativeBarError("processing_stream_scope_changed")
                if planned_at < head.processed_at:
                    raise NativeBarError("processing_clock_regressed")
                if head.public_source is None and not manage_exits:
                    raise NativeBarError("observation_requires_source_bound_history")
            if (
                not manage_exits
                and jam_config is None
                and (
                    session.scalar(
                        select(PaperTrade.id).where(PaperTrade.status == TradeStatus.OPEN)
                    )
                    is not None
                    or session.scalar(
                        select(Position.id).where(Position.status == PositionStatus.OPEN)
                    )
                    is not None
                )
            ):
                raise NativeBarError("open_position_requires_online_exit_monitor")
        delay = timedelta(seconds=CLOSE_DELAY_SECONDS)
        if head is None:
            boundary = EPOCH + STEP * ((planned_at - delay - EPOCH) // STEP)
            count, purpose = seed_count, "SEED"
            first_open = boundary - STEP * count
            # Bootstrap at a fresh close rather than accepting an old ending window.
            if planned_at - boundary > timedelta(seconds=180):
                return NativeObservationResult("WAITING_FOR_CLOSE", boundary + STEP + delay)
        else:
            first_open = head.bar.timestamp + STEP
            count, purpose = 1, "CLOSED_BAR"
        closed_at = window_end(first_open, count)
        started_at = aware_utc(utc_now())
        if started_at < planned_at:
            raise NativeBarError("processing_clock_regressed")
        if started_at < closed_at + delay:
            return NativeObservationResult("WAITING_FOR_CLOSE", closed_at + delay)
        if started_at - closed_at > timedelta(seconds=180):
            raise NativeBarError("observation_window_missed_requires_reconciliation")
        evidence = PublicCandleClient().acquire(count=count, first_open=first_open)
        admission = NativeObservationAdmission(
            started_at=started_at,
            finished_at=aware_utc(utc_now()),
            expected_previous_evidence_hash=previous_hash,
        )
        if evidence.first_open != first_open or evidence.bar_count != count:
            raise NativeBarError("observation_acquired_window_changed")
        binding = bind_public_source(evidence, purpose)
        admission.check_receipt(binding, previous_hash, admission.finished_at)
        bars = binding.reconstruct()
        processing = self._processor._process(
            list(bars) if head is None else None,
            next_bar=None if head is None else bars[0],
            scope=scope,
            signal=None,
            public_source=binding,
            public_observation=admission,
            online_exit=manage_exits,
            jam_config=jam_config,
            expected_jam_head=previous_hash,
        )
        return NativeObservationResult(
            "JAM_EVALUATED"
            if jam_config is not None
            else "EXITS_MANAGED_NO_ENTRY"
            if manage_exits
            else "OBSERVED_NO_ENTRY",
            closed_at + STEP + delay,
            processing,
        )
