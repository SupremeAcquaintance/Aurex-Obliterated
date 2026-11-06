"""SQLite-only atomic native paper processing; no feed, evaluator or scheduler."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from aurex.backtest_engine.schemas import OhlcvCandle
from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import NativeBarOutcome, NativeHistorySeed, PaperTrade, Position, Signal
from aurex.domain.enums import PositionStatus, TradeStatus
from aurex.signal_gateway.native_bars import (
    BASE_SECONDS,
    MAX_STREAM_BARS,
    MAX_WINDOW_BARS,
    SCHEMA_VERSION,
    ClosedBar,
    NativeBarCursor,
    NativeBarError,
    NativeBarFrame,
    NativeIndicatorParameters,
    aware_utc,
    bind_native_signal_to_bar,
    content_hash,
    prepare_native_closed_bar,
)
from aurex.signal_gateway.native_continuation import (
    NativeIndicatorState,
    continuation_frame,
    initialize_continuation,
    require_replay_arithmetic,
)
from aurex.signal_gateway.native_exits import (
    NativeOnlineExitEvidence,
    manage_online_exit,
    verify_online_exit,
)
from aurex.signal_gateway.native_market_data import PublicCandleEvidence
from aurex.signal_gateway.native_recovery import (
    ONLINE_EXIT_FILL_MODEL,
    RECOVERY_FILL_MODEL,
    NativeRecoveryEvidence,
    manage_recovery,
    verify_recovery,
)
from aurex.signal_gateway.native_source import (
    NativeObservationAdmission,
    NativePublicSourceBinding,
    SourcePurpose,
    bind_public_source,
)
from aurex.signal_gateway.schemas import NativeSignalPayload
from aurex.signal_gateway.service import SignalIntakeService

STREAM_KEY = "native-spot-main"
CHAIN_PAGE_SIZE = 128


class NativeStreamSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feed_id: Literal["fixture", "binance_spot_public"]
    strategy: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    strategy_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    settings_fingerprint: str = Field(min_length=1, max_length=2000)
    parameters: NativeIndicatorParameters = Field(default_factory=NativeIndicatorParameters)

    @field_validator("settings_fingerprint")
    @classmethod
    def validate_fingerprint(cls, value: str) -> str:
        # Canonical Jam settings include internal spaces (for example, Long only).
        # Reject ambiguous outer whitespace/control characters without rewriting evidence.
        if value != value.strip() or not value.isprintable():
            raise ValueError("fingerprint_must_be_printable_without_outer_whitespace")
        return value

    def check_signal(self, signal: NativeSignalPayload | None) -> None:
        if signal is not None and any(
            getattr(signal, name) != getattr(self, name)
            for name in ("strategy", "strategy_version", "settings_fingerprint")
        ):
            raise NativeBarError("signal_stream_provenance_mismatch")


class NativeSeedEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["native_history_seed_v1"] = "native_history_seed_v1"
    scope: NativeStreamSpec
    candles: list[ClosedBar] = Field(min_length=1, max_length=MAX_WINDOW_BARS)


class NativeBarReceipt(BaseModel):
    """Hash-bound processing evidence, not proof of market origin or strategy quality."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[
        "native_bar_processing_v1",
        "native_bar_processing_v2",
        "native_bar_processing_v3",
        "native_bar_processing_v4",
        "native_bar_processing_v5",
        "native_bar_processing_v6",
        "native_bar_processing_v7",
    ] = "native_bar_processing_v1"
    stream_key: Literal["native-spot-main"] = STREAM_KEY
    sequence: int = Field(strict=True, ge=1, le=MAX_STREAM_BARS)
    scope: NativeStreamSpec
    checkpoint: NativeBarCursor
    candle_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    bar: ClosedBar
    closed_at: datetime
    processed_at: datetime
    previous_evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    signal_request: NativeSignalPayload | None
    signal_id: str | None = Field(default=None, min_length=1, max_length=36)
    outcome: Literal[
        "NO_SIGNAL",
        "RISK_REJECTED",
        "PAPER_EXECUTED",
        "DUPLICATE_REJECTED",
        "RECOVERY_NO_ENTRY",
        "SOURCE_OBSERVED_NO_ENTRY",
        "ONLINE_EXIT_NO_ENTRY",
        "JAM_NO_SIGNAL",
    ]
    source_origin_verified: Literal[False] = False
    continuation: NativeIndicatorState | None = None
    recovery: NativeRecoveryEvidence | None = None
    public_source: NativePublicSourceBinding | None = None
    public_observation: NativeObservationAdmission | None = None
    online_exit: NativeOnlineExitEvidence | None = None
    jam_decision: dict | None = None

    @field_validator("closed_at", "processed_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return aware_utc(value)

    @model_validator(mode="after")
    def validate_binding(self) -> "NativeBarReceipt":
        self.scope.check_signal(self.signal_request)
        if self.schema_version == "native_bar_processing_v7":
            from aurex.signal_gateway.native_jam_runtime import JamDecisionReceipt

            if (
                self.jam_decision is None
                or self.public_source is None
                or self.public_observation is None
                or self.recovery is not None
                or self.online_exit is not None
            ):
                raise ValueError("jam_receipt_binding_missing")
            jam = JamDecisionReceipt.model_validate(self.jam_decision)
            jam.config.bind(self.scope)
            if (
                self.public_source.purpose not in {"SEED", "CLOSED_BAR"}
                or (self.sequence == 1) != (jam.decision is None)
                or jam.resolved_state.bar_count != self.checkpoint.bar_count
                or jam.resolved_state.first_open != self.checkpoint.first_open
                or jam.resolved_state.last_open != self.bar.timestamp
                or jam.resolved_state.awaiting_entry is not None
                or self.outcome
                not in {"JAM_NO_SIGNAL", "RISK_REJECTED", "DUPLICATE_REJECTED", "PAPER_EXECUTED"}
            ):
                raise ValueError("jam_receipt_state_binding_invalid")
        elif self.jam_decision is not None or self.outcome == "JAM_NO_SIGNAL":
            raise ValueError("legacy_receipt_has_jam_decision")
        if self.schema_version == "native_bar_processing_v6":
            if (
                self.online_exit is None
                or self.public_source is None
                or self.recovery is not None
                or self.public_source.purpose != "CLOSED_BAR"
                or self.online_exit.source_acquisition_sha256
                != self.public_source.acquisition_sha256
            ):
                raise ValueError("online_exit_receipt_binding_invalid")
        elif self.online_exit is not None or self.outcome == "ONLINE_EXIT_NO_ENTRY":
            raise ValueError("legacy_receipt_has_online_exit")
        if self.schema_version in {
            "native_bar_processing_v5",
            "native_bar_processing_v6",
            "native_bar_processing_v7",
        }:
            if self.public_observation is None or self.public_source is None:
                raise ValueError("observation_receipt_evidence_missing")
            self.public_observation.check_receipt(
                self.public_source, self.previous_evidence_hash, self.processed_at
            )
        elif self.public_observation is not None:
            raise ValueError("legacy_receipt_has_public_observation")
        if self.schema_version in {
            "native_bar_processing_v4",
            "native_bar_processing_v5",
            "native_bar_processing_v6",
            "native_bar_processing_v7",
        }:
            if self.public_source is None:
                raise ValueError("source_receipt_evidence_missing")
            is_recovery = self.public_source.purpose == "RECOVERY"
            if is_recovery != (self.recovery is not None) or (
                self.jam_decision is None
                and self.outcome
                != (
                    "RECOVERY_NO_ENTRY"
                    if is_recovery
                    else "ONLINE_EXIT_NO_ENTRY"
                    if self.online_exit is not None
                    else "SOURCE_OBSERVED_NO_ENTRY"
                )
            ):
                raise ValueError("source_receipt_mode_or_outcome_invalid")
            self.public_source.check_receipt(
                bar=self.bar,
                checkpoint=self.checkpoint,
                sequence=self.sequence,
                processed_at=self.processed_at,
            )
        elif self.public_source is not None or self.outcome == "SOURCE_OBSERVED_NO_ENTRY":
            raise ValueError("legacy_receipt_has_public_source")
        if self.schema_version == "native_bar_processing_v3":
            if self.recovery is None or self.outcome != "RECOVERY_NO_ENTRY":
                raise ValueError("recovery_receipt_evidence_missing")
        elif self.schema_version not in {
            "native_bar_processing_v4",
            "native_bar_processing_v5",
            "native_bar_processing_v6",
            "native_bar_processing_v7",
        } and (self.recovery is not None or self.outcome == "RECOVERY_NO_ENTRY"):
            raise ValueError("legacy_receipt_has_recovery")
        if self.schema_version == "native_bar_processing_v1":
            if self.continuation is not None or self.checkpoint.schema_version != SCHEMA_VERSION:
                raise ValueError("legacy_receipt_has_continuation")
        elif self.continuation is None:
            if (
                self.schema_version
                not in {
                    "native_bar_processing_v3",
                    "native_bar_processing_v4",
                    "native_bar_processing_v5",
                    "native_bar_processing_v6",
                    "native_bar_processing_v7",
                }
                or self.checkpoint.schema_version != SCHEMA_VERSION
            ):
                raise ValueError("continuation_receipt_binding_invalid")
        elif (
            self.checkpoint.schema_version != "native_closed_bar_continuation_v1"
            or self.continuation.parameters != self.scope.parameters
            or self.continuation.last_bar != self.bar
            or self.continuation.first_open != self.checkpoint.first_open
            or self.continuation.bar_count != self.checkpoint.bar_count
        ):
            raise ValueError("continuation_receipt_binding_invalid")
        if (
            self.checkpoint.feed_id != self.scope.feed_id
            or self.checkpoint.parameters_sha256
            != content_hash(self.scope.parameters.model_dump(mode="json"))
            or self.checkpoint.last_open != self.bar.timestamp
            or self.closed_at != self.bar.timestamp + timedelta(seconds=BASE_SECONDS)
            or self.processed_at < self.closed_at
            or self.candle_id
            != content_hash(
                {
                    "feed_id": self.scope.feed_id,
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "open": self.bar.timestamp.isoformat(),
                }
            )
        ):
            raise ValueError("receipt_bar_binding_invalid")
        if self.outcome in {
            "NO_SIGNAL",
            "RECOVERY_NO_ENTRY",
            "SOURCE_OBSERVED_NO_ENTRY",
            "ONLINE_EXIT_NO_ENTRY",
            "JAM_NO_SIGNAL",
        }:
            if self.signal_request is not None or self.signal_id is not None:
                raise ValueError("no_signal_receipt_has_signal")
        else:
            if self.signal_request is None or self.signal_id is None:
                raise ValueError("signal_receipt_missing_signal")
            bind_native_signal_to_bar(
                self.signal_request,
                NativeBarFrame(
                    "READY", self.bar, self.closed_at, self.candle_id, self.checkpoint, {}
                ),
            )
        return self


def receipt_evidence(receipt: NativeBarReceipt) -> dict:
    # v1 evidence predates the continuation field; preserve its canonical bytes.
    return receipt.model_dump(
        mode="json",
        exclude={
            name
            for name in (
                "continuation",
                "recovery",
                "public_source",
                "public_observation",
                "online_exit",
                "jam_decision",
            )
            if getattr(receipt, name) is None
        },
    )


@dataclass(frozen=True)
class NativeBarProcessingResult:
    receipt_id: str
    evidence_hash: str
    outcome: str
    signal_id: str | None
    is_duplicate: bool
    checkpoint: NativeBarCursor
    recovery_disposition: str | None = None
    source_evidence_hash: str | None = None
    source_purpose: str | None = None
    online_exit_disposition: str | None = None


def result_for(
    row: NativeBarOutcome, receipt: NativeBarReceipt, *, duplicate: bool
) -> NativeBarProcessingResult:
    return NativeBarProcessingResult(
        row.id,
        row.evidence_hash,
        row.outcome,
        row.signal_id,
        duplicate,
        receipt.checkpoint,
        receipt.recovery.disposition if receipt.recovery else None,
        receipt.public_source.acquisition_sha256 if receipt.public_source else None,
        receipt.public_source.purpose if receipt.public_source else None,
        receipt.online_exit.disposition if receipt.online_exit else None,
    )


def iter_validated_chain(
    session: Session, *, jam_audit=None
) -> Iterator[tuple[NativeBarOutcome, NativeBarReceipt]]:
    """Keyset pages bound runtime memory, not total audit time or database size."""
    index = 0
    previous_hash = None
    previous = None
    active_entry = None
    unmanaged = False
    held_position = None
    held_execution_hash = None
    active_fill_model = None
    observed_online = False
    if jam_audit is None:
        from aurex.signal_gateway.native_jam_runtime import JamChainAudit

        jam_audit = JamChainAudit(session)
    while True:
        query = select(NativeBarOutcome).where(NativeBarOutcome.stream_key == STREAM_KEY)
        # The first page must include malformed nonpositive keys so validation rejects them.
        if index:
            query = query.where(NativeBarOutcome.sequence > index)
        rows = list(
            session.scalars(query.order_by(NativeBarOutcome.sequence).limit(CHAIN_PAGE_SIZE))
        )
        if not rows:
            jam_audit.finish()
            if held_position is not None:
                trade = session.get(PaperTrade, held_position.trade_id)
                position = session.get(Position, held_position.position_id)
                if (
                    trade is None
                    or position is None
                    or trade.status != TradeStatus.OPEN
                    or position.status != PositionStatus.OPEN
                    or trade.paper_order is None
                    or trade.paper_order.execution_assumptions_hash != held_execution_hash
                ):
                    raise NativeBarError("recovery_held_position_changed_without_receipt")
            return
        signal_ids = [row.signal_id for row in rows if row.signal_id is not None]
        signals = (
            {
                signal.id: signal
                for signal in session.scalars(select(Signal).where(Signal.id.in_(signal_ids)))
            }
            if signal_ids
            else {}
        )
        for row in rows:
            index += 1
            receipt = NativeBarReceipt.model_validate(row.evidence)
            if (
                row.evidence_hash != content_hash(row.evidence)
                or row.evidence_hash != content_hash(receipt_evidence(receipt))
                or row.sequence != index
                or receipt.sequence != index
                or row.candle_id != receipt.candle_id
                or row.outcome != receipt.outcome
                or row.signal_id != receipt.signal_id
                or receipt.previous_evidence_hash != previous_hash
            ):
                raise NativeBarError("processing_receipt_integrity_failed")
            if previous is not None and (
                receipt.scope != previous.scope
                or receipt.checkpoint.first_open != previous.checkpoint.first_open
                or receipt.checkpoint.bar_count != previous.checkpoint.bar_count + 1
                or receipt.bar.timestamp != previous.bar.timestamp + timedelta(seconds=BASE_SECONDS)
                or receipt.processed_at < previous.processed_at
            ):
                raise NativeBarError("processing_chain_continuity_failed")
            if (
                previous is not None
                and previous.public_source is not None
                and receipt.public_source is None
            ):
                raise NativeBarError("processing_source_binding_dropped")
            if observed_online and receipt.public_observation is None and receipt.recovery is None:
                raise NativeBarError("processing_observation_admission_dropped")
            observed_online = observed_online or receipt.public_observation is not None
            if row.signal_id is not None:
                signal = signals.get(row.signal_id)
                if (
                    signal is None
                    or signal.source != "aurex_native"
                    or signal.status.value != receipt.outcome
                    or signal.raw_payload != receipt.signal_request.model_dump(mode="json")
                ):
                    raise NativeBarError("processing_signal_link_invalid")
            management = receipt.online_exit or receipt.recovery
            if management is not None:
                recovery_position = management.position
                if (
                    unmanaged
                    or (active_entry is None) != (recovery_position is None)
                    or (
                        recovery_position is not None
                        and (
                            recovery_position.entry_receipt_id != active_entry[0]
                            or recovery_position.entry_receipt_hash != active_entry[1]
                        )
                    )
                ):
                    raise NativeBarError("recovery_entry_chain_mismatch")
                # Frozen cost fields must match their canonical snapshot; defaults cannot repair it.
                if receipt.online_exit is not None and receipt.online_exit.fill_model != (
                    RECOVERY_FILL_MODEL
                    if active_fill_model == RECOVERY_FILL_MODEL and recovery_position is not None
                    else ONLINE_EXIT_FILL_MODEL
                ):
                    raise NativeBarError("online_exit_fill_model_transition_invalid")
                verifier = (
                    verify_online_exit if receipt.online_exit is not None else verify_recovery
                )
                verifier(
                    session,
                    Settings.model_construct(),
                    receipt.scope.model_dump(mode="json"),
                    receipt.bar,
                    management,
                    receipt.processed_at,
                )
                if management.disposition == "CLOSED":
                    active_entry = None
                    held_position = None
                    held_execution_hash = None
                    active_fill_model = None
                elif management.disposition == "HELD":
                    held_position = recovery_position
                    held_execution_hash = management.execution_hash_after
                    active_fill_model = (
                        receipt.online_exit.fill_model
                        if receipt.online_exit is not None
                        else RECOVERY_FILL_MODEL
                    )
            elif receipt.outcome == "PAPER_EXECUTED" and receipt.jam_decision is None:
                active_entry = (row.id, row.evidence_hash)
                active_fill_model = None
                unmanaged = False
            elif active_entry is not None:
                unmanaged = True
            jam_audit.consume(row, receipt)
            yield row, receipt
            previous, previous_hash = receipt, row.evidence_hash


def validate_chain(session: Session) -> list[tuple[NativeBarOutcome, NativeBarReceipt]]:
    """Materialized inspection helper; runtime processing uses bounded pages instead."""
    return list(iter_validated_chain(session))


def retained_history(
    session: Session, chain: list[tuple[NativeBarOutcome, NativeBarReceipt]]
) -> list[ClosedBar]:
    row = session.scalar(
        select(NativeHistorySeed).where(NativeHistorySeed.stream_key == STREAM_KEY)
    )
    if not chain:
        if row is not None:
            raise NativeBarError("history_seed_without_processing_receipt")
        return []
    if row is None:
        raise NativeBarError("retained_history_seed_missing")
    seed = NativeSeedEvidence.model_validate(row.evidence)
    if (
        row.evidence_hash != content_hash(row.evidence)
        or row.evidence_hash != content_hash(seed.model_dump(mode="json"))
        or seed.scope != chain[0][1].scope
        or len(seed.candles) != chain[0][1].checkpoint.bar_count
        or seed.candles[-1] != chain[0][1].bar
    ):
        raise NativeBarError("retained_history_seed_integrity_failed")
    history = seed.candles + [receipt.bar for _, receipt in chain[1:]]
    if len(history) > MAX_WINDOW_BARS:
        raise NativeBarError("retained_history_window_exhausted")
    checkpoints = {receipt.checkpoint.bar_count: receipt.checkpoint for _, receipt in chain}
    # Reproduce each canonical JSON-array prefix in one pass, without quadratic rehashing.
    digest = sha256(b"[")
    for index, bar in enumerate(history, start=1):
        if index > 1:
            if bar.timestamp - history[index - 2].timestamp != timedelta(seconds=BASE_SECONDS):
                raise NativeBarError("retained_history_discontinuous")
            digest.update(b",")
        digest.update(
            json.dumps(bar.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        )
        checkpoint = checkpoints.get(index)
        if checkpoint is not None:
            prefix = digest.copy()
            prefix.update(b"]")
            if (
                checkpoint.first_open != history[0].timestamp
                or checkpoint.last_open != bar.timestamp
                or checkpoint.history_sha256 != prefix.hexdigest()
            ):
                raise NativeBarError("retained_history_checkpoint_mismatch")
    return history


@dataclass
class VerifiedNativeHistory:
    head: tuple[NativeBarOutcome, NativeBarReceipt] | None = None
    retry: tuple[NativeBarOutcome, NativeBarReceipt] | None = None
    legacy_prefix: list[ClosedBar] = field(default_factory=list)
    continuation: NativeIndicatorState | None = None
    has_public_observations: bool = False
    jam_runtime: object | None = None


def verified_native_history(session: Session, requested_open: datetime) -> VerifiedNativeHistory:
    """Reconstruct every continuation from retained inputs, not a trusted head cache."""
    verified = VerifiedNativeHistory()
    from aurex.signal_gateway.native_jam_runtime import JamChainAudit

    jam_audit = JamChainAudit(session)
    digest = sha256(b"[")
    for item in iter_validated_chain(session, jam_audit=jam_audit):
        _, receipt = item
        if verified.head is None:
            if receipt.continuation is not None:
                raise NativeBarError("continuation_without_legacy_seed")
            verified.legacy_prefix = retained_history(session, [item])
            for index, bar in enumerate(verified.legacy_prefix):
                if index:
                    digest.update(b",")
                digest.update(
                    json.dumps(
                        bar.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                    ).encode()
                )
        elif receipt.continuation is None:
            verified.legacy_prefix.append(receipt.bar)
            digest.update(b",")
            digest.update(
                json.dumps(
                    receipt.bar.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()
            )
            prefix = digest.copy()
            prefix.update(b"]")
            if (
                len(verified.legacy_prefix) > MAX_WINDOW_BARS
                or receipt.checkpoint.history_sha256 != prefix.hexdigest()
            ):
                raise NativeBarError("retained_history_checkpoint_mismatch")
        else:
            state = verified.continuation or initialize_continuation(
                verified.legacy_prefix, receipt.scope.parameters
            )
            frame, state = continuation_frame(state, verified.head[1].checkpoint, receipt.bar)
            if frame.checkpoint != receipt.checkpoint or state != receipt.continuation:
                raise NativeBarError("continuation_reconstruction_mismatch")
            verified.continuation = state
        verified.head = item
        verified.has_public_observations |= receipt.public_observation is not None
        if receipt.bar.timestamp == requested_open:
            verified.retry = item
    if verified.head is None:
        retained_history(session, [])
    if jam_audit.config is not None:
        verified.jam_runtime = jam_audit
    return verified


class NativeBarProcessor:
    """Own a fresh transaction; never commit a caller's unrelated pending work.

    One fixed stream per database. BEGIN IMMEDIATE serializes local writers before
    reading the head, including across processes. Lock errors propagate; no blind
    retry or claim of PostgreSQL/native-to-legacy account-wide isolation is made.
    """

    def __init__(self, engine: Engine, settings: Settings) -> None:
        if engine.dialect.name != "sqlite":
            raise ValueError("Native bar processing currently requires SQLite")
        self.engine = engine
        self.settings = settings

    def process(
        self,
        candles: list[OhlcvCandle | dict],
        *,
        scope: NativeStreamSpec,
        signal: NativeSignalPayload | None,
    ) -> NativeBarProcessingResult:
        """Initialize with a full seed, or verify a supplied prefix against persisted history."""
        if not candles or len(candles) > MAX_WINDOW_BARS:
            raise NativeBarError("window_size_out_of_bounds")
        snapshot = [
            ClosedBar.model_validate(bar.model_dump() if isinstance(bar, BaseModel) else bar)
            for bar in candles
        ]
        return self._process(snapshot, next_bar=None, scope=scope, signal=signal)

    def process_next(
        self,
        candle: OhlcvCandle | dict,
        *,
        scope: NativeStreamSpec,
        signal: NativeSignalPayload | None,
    ) -> NativeBarProcessingResult:
        """Resume from retained seed and receipts; never create or silently repair a seed."""
        bar = ClosedBar.model_validate(
            candle.model_dump() if isinstance(candle, BaseModel) else candle
        )
        return self._process(None, next_bar=bar, scope=scope, signal=signal)

    def recover_next(
        self,
        candle: OhlcvCandle | dict,
        *,
        scope: NativeStreamSpec,
    ) -> NativeBarProcessingResult:
        """Consume one contiguous closed candle for exit-only recovery, never a stale entry.

        Positions touched by this explicit mode cannot qualify as genuine forward paper data.
        Acquisition and recovery scheduling are the caller's responsibility.
        """
        bar = ClosedBar.model_validate(
            candle.model_dump() if isinstance(candle, BaseModel) else candle
        )
        return self._process(None, next_bar=bar, scope=scope, signal=None, recovery=True)

    def process_sourced(
        self, evidence: PublicCandleEvidence, *, scope: NativeStreamSpec, purpose: SourcePurpose
    ) -> NativeBarProcessingResult:
        """Retain and reconstruct source bytes atomically, without any entry argument.

        SEED establishes warmup, CLOSED_BAR observes one fresh candle, and RECOVERY
        supplies one candle to the existing nonqualifying exit-only simulator.
        A file or transport label cannot grant live-origin/forward authority here.
        """
        binding = bind_public_source(evidence, purpose)
        bars = binding.reconstruct()
        return self._process(
            list(bars) if purpose == "SEED" else None,
            next_bar=None if purpose == "SEED" else bars[0],
            scope=scope,
            signal=None,
            recovery=purpose == "RECOVERY",
            public_source=binding,
        )

    def _process(
        self,
        candles: list[OhlcvCandle | dict] | None,
        *,
        next_bar: ClosedBar | None,
        scope: NativeStreamSpec,
        signal: NativeSignalPayload | None,
        recovery: bool = False,
        public_source: NativePublicSourceBinding | None = None,
        public_observation: NativeObservationAdmission | None = None,
        online_exit: bool = False,
        jam_config: dict | None = None,
        expected_jam_head: str | None = None,
    ) -> NativeBarProcessingResult:
        if self.settings.live_trading_enabled or self.settings.live_execution_adapter != "disabled":
            raise ValueError("Native bar processing requires live execution to remain disabled")
        scope = NativeStreamSpec.model_validate(scope.model_dump())
        if signal is not None:
            signal = NativeSignalPayload.model_validate(signal.model_dump())
        scope.check_signal(signal)
        config = None
        if jam_config is not None:
            from aurex.signal_gateway.native_jam_runtime import JamRuntimeConfig

            config = JamRuntimeConfig.model_validate_json(json.dumps(jam_config, allow_nan=False))
            config.bind(scope)
            if (
                signal is not None
                or public_source is None
                or public_observation is None
                or recovery
                or online_exit
            ):
                raise NativeBarError("jam_runtime_requires_sourced_owned_decisions")
        if online_exit and (
            signal is not None
            or recovery
            or next_bar is None
            or public_source is None
            or public_observation is None
            or public_source.purpose != "CLOSED_BAR"
        ):
            raise NativeBarError("online_exit_requires_owned_observation_without_entry")
        if public_observation is not None:
            public_observation = NativeObservationAdmission.model_validate(
                public_observation.model_dump(mode="json")
            )
            if public_source is None or signal is not None or recovery:
                raise NativeBarError("observation_prohibits_entry_recovery_or_missing_source")
        if public_source is not None:
            public_source = NativePublicSourceBinding.model_validate(public_source.model_dump())
            if signal is not None or recovery != (public_source.purpose == "RECOVERY"):
                raise NativeBarError("source_binding_prohibits_entry_or_changed_mode")
        if recovery and (signal is not None or next_bar is None):
            raise NativeBarError("recovery_prohibits_entries_and_seed_initialization")
        require_replay_arithmetic()
        last_input = next_bar if next_bar is not None else candles[-1]
        last_bar = ClosedBar.model_validate(
            last_input.model_dump() if isinstance(last_input, BaseModel) else last_input
        )
        with Session(self.engine, autoflush=False, expire_on_commit=False) as session:
            with session.begin():
                session.execute(text("BEGIN IMMEDIATE"))
                now = aware_utc(utc_now())
                verified = verified_native_history(session, last_bar.timestamp)
                history, retry = verified.legacy_prefix, verified.retry
                previous = verified.head[1] if verified.head else None
                if previous is not None:
                    if previous.scope != scope:
                        raise NativeBarError("processing_stream_scope_changed")
                    if now < previous.processed_at:
                        raise NativeBarError("processing_clock_regressed")
                if retry is not None:
                    if (config is None) != (retry[1].jam_decision is None) or (
                        config is not None
                        and config.model_dump(mode="json") != retry[1].jam_decision["config"]
                    ):
                        raise NativeBarError("processed_bar_jam_config_changed")
                    if recovery != (retry[1].recovery is not None) or online_exit != (
                        retry[1].online_exit is not None
                    ):
                        raise NativeBarError("processed_bar_mode_changed")
                    if last_bar != retry[1].bar:
                        raise NativeBarError("retained_retry_bar_changed")
                    if config is None and signal != retry[1].signal_request:
                        raise NativeBarError("processed_bar_request_changed")
                    if public_source != retry[1].public_source:
                        raise NativeBarError("processed_bar_source_changed")
                    if public_observation != retry[1].public_observation:
                        raise NativeBarError("processed_bar_observation_changed")
                    if candles is not None:
                        frame = prepare_native_closed_bar(
                            candles,
                            now=now,
                            feed_id=scope.feed_id,
                            parameters=scope.parameters,
                            previous=retry[1].checkpoint,
                        )
                        if frame.status != "DUPLICATE":
                            raise NativeBarError("processed_bar_request_changed")
                    return result_for(*retry, duplicate=True)
                if config is not None:
                    if expected_jam_head != (
                        verified.head[0].evidence_hash if verified.head else None
                    ):
                        raise NativeBarError("jam_runtime_expected_head_changed")
                    if previous is not None and verified.jam_runtime is None:
                        raise NativeBarError("jam_runtime_requires_new_stream")
                elif verified.jam_runtime is not None:
                    raise NativeBarError("jam_runtime_decision_binding_dropped")
                if public_observation is not None and (
                    public_observation.expected_previous_evidence_hash
                    != (verified.head[0].evidence_hash if verified.head else None)
                ):
                    raise NativeBarError("observation_expected_head_changed")
                if verified.has_public_observations and public_observation is None and not recovery:
                    raise NativeBarError("processing_observation_admission_dropped")
                if (
                    previous is not None
                    and previous.public_source is not None
                    and public_source is None
                ):
                    raise NativeBarError("processing_source_binding_dropped")
                if public_source is not None and (previous is None) != (
                    public_source.purpose == "SEED"
                ):
                    raise NativeBarError("source_seed_or_resume_mode_invalid")
                if (
                    not recovery
                    and not online_exit
                    and config is None
                    and (
                        session.scalar(
                            select(PaperTrade.id)
                            .where(PaperTrade.status == TradeStatus.OPEN)
                            .limit(1)
                        )
                        is not None
                        or session.scalar(
                            select(Position.id)
                            .where(Position.status == PositionStatus.OPEN)
                            .limit(1)
                        )
                        is not None
                    )
                ):
                    raise NativeBarError("open_position_requires_exit_only_recovery")
                continuation = None
                if recovery and last_bar.timestamp + timedelta(seconds=BASE_SECONDS) > now:
                    raise NativeBarError("candle_not_closed")
                if next_bar is not None:
                    if previous is None:
                        raise NativeBarError("retained_history_not_initialized")
                    if next_bar.timestamp <= previous.bar.timestamp:
                        raise NativeBarError("retry_bar_not_previously_processed")
                    if previous.checkpoint.bar_count >= MAX_WINDOW_BARS:
                        state = verified.continuation or initialize_continuation(
                            history, scope.parameters
                        )
                        frame, continuation = continuation_frame(
                            state, previous.checkpoint, next_bar
                        )
                    else:
                        candles = history + [next_bar]
                if continuation is None:
                    frame = prepare_native_closed_bar(
                        candles,
                        now=last_bar.timestamp + timedelta(seconds=BASE_SECONDS)
                        if recovery
                        else now,
                        feed_id=scope.feed_id,
                        parameters=scope.parameters,
                        previous=previous.checkpoint if previous else None,
                    )
                # Audit and arithmetic can take time. Recheck freshness before any entry effects.
                fresh_now = aware_utc(utc_now())
                if fresh_now < now:
                    raise NativeBarError("processing_clock_regressed")
                if frame.closed_at > fresh_now:
                    raise NativeBarError("candle_not_closed")
                if not recovery and fresh_now - frame.closed_at > timedelta(seconds=180):
                    raise NativeBarError("latest_closed_bar_is_stale")
                if public_source is not None:
                    public_source.check_receipt(
                        bar=frame.bar,
                        checkpoint=frame.checkpoint,
                        sequence=previous.sequence + 1 if previous else 1,
                        processed_at=fresh_now,
                    )
                if public_observation is not None:
                    public_observation.check_receipt(
                        public_source,
                        verified.head[0].evidence_hash if verified.head else None,
                        fresh_now,
                    )
                if previous is None:
                    seed = NativeSeedEvidence(
                        scope=scope,
                        candles=[
                            ClosedBar.model_validate(
                                bar.model_dump() if isinstance(bar, BaseModel) else bar
                            )
                            for bar in candles
                        ],
                    ).model_dump(mode="json")
                    session.add(
                        NativeHistorySeed(
                            stream_key=STREAM_KEY, evidence=seed, evidence_hash=content_hash(seed)
                        )
                    )
                recovery_evidence = None
                exit_evidence = None
                jam_evidence = None
                if config is not None:
                    from aurex.signal_gateway.native_jam_runtime import process_jam_decision

                    jam_evidence, signal, signal_id, outcome = process_jam_decision(
                        session,
                        self.settings,
                        scope,
                        config,
                        frame,
                        candles if previous is None else history,
                        verified.jam_runtime,
                        fresh_now,
                    )
                    jam_evidence = jam_evidence.model_dump(mode="json")
                elif recovery:
                    recovery_evidence = manage_recovery(
                        session, self.settings, scope.model_dump(mode="json"), frame.bar, fresh_now
                    )
                    signal_id, outcome = None, "RECOVERY_NO_ENTRY"
                elif online_exit:
                    exit_evidence = manage_online_exit(
                        session,
                        self.settings,
                        scope.model_dump(mode="json"),
                        frame.bar,
                        fresh_now,
                        public_source,
                        public_observation,
                        verified.head[0].evidence_hash,
                    )
                    signal_id, outcome = None, "ONLINE_EXIT_NO_ENTRY"
                elif signal is not None:
                    signal = bind_native_signal_to_bar(signal, frame)
                    ingest = SignalIntakeService(session, self.settings).ingest_native(
                        signal, commit=False
                    )
                    signal_id = ingest.signal.id
                    outcome = ingest.signal.status.value
                else:
                    signal_id, outcome = (
                        None,
                        ("SOURCE_OBSERVED_NO_ENTRY" if public_source is not None else "NO_SIGNAL"),
                    )
                receipt = NativeBarReceipt(
                    schema_version=(
                        "native_bar_processing_v7"
                        if config is not None
                        else "native_bar_processing_v6"
                        if online_exit
                        else "native_bar_processing_v5"
                        if public_observation is not None
                        else "native_bar_processing_v4"
                        if public_source is not None
                        else "native_bar_processing_v3"
                        if recovery
                        else "native_bar_processing_v2"
                        if continuation
                        else "native_bar_processing_v1"
                    ),
                    continuation=continuation,
                    recovery=recovery_evidence,
                    public_source=public_source,
                    public_observation=public_observation,
                    online_exit=exit_evidence,
                    jam_decision=jam_evidence,
                    sequence=previous.sequence + 1 if previous else 1,
                    scope=scope,
                    checkpoint=frame.checkpoint,
                    candle_id=frame.candle_id,
                    bar=frame.bar,
                    closed_at=frame.closed_at,
                    processed_at=aware_utc(utc_now()),
                    signal_request=signal,
                    signal_id=signal_id,
                    outcome=outcome,
                    previous_evidence_hash=verified.head[0].evidence_hash
                    if verified.head
                    else None,
                )
                if receipt.processed_at < fresh_now:
                    raise NativeBarError("processing_clock_regressed")
                evidence = receipt_evidence(receipt)
                row = NativeBarOutcome(
                    stream_key=STREAM_KEY,
                    sequence=receipt.sequence,
                    candle_id=receipt.candle_id,
                    signal_id=signal_id,
                    outcome=outcome,
                    evidence=evidence,
                    evidence_hash=content_hash(evidence),
                )
                session.add(row)
                session.flush()
                if recovery or online_exit or config is not None:
                    # Validate the new transition as well, before its ledger effects can commit.
                    for _ in iter_validated_chain(session):
                        pass
                result = result_for(row, receipt, duplicate=False)
            return result
