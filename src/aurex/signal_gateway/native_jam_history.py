"""Read-only Jam arithmetic reconstructed from a consistent, audited native ledger.

No caller-supplied candles/state cache, strategy enablement, or execution authority.
The snapshot is a local content binding, not a signature or forward qualification.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from aurex.backtest_engine.jam_reversal_reference import parse_jam_reversal_spot_parameters
from aurex.backtest_engine.service import (
    KNOWN_STRATEGY_REQUIRED_PARAMETERS,
    strategy_parameter_fingerprint,
)
from aurex.config.settings import Settings
from aurex.signal_gateway.native_bars import NativeBarCursor, NativeBarError, content_hash
from aurex.signal_gateway.native_continuation import require_replay_arithmetic
from aurex.signal_gateway.native_jam_features import (
    JamFeatureParameters,
    JamFeatureState,
    advance_jam_features,
    initialize_jam_features,
)
from aurex.signal_gateway.native_processing import (
    NativeStreamSpec,
    iter_validated_chain,
    verified_native_history,
)


def bind_jam_feature_parameters(scope: NativeStreamSpec, parameters: dict) -> JamFeatureParameters:
    """Bind the full existing Spot v1.0.1 settings contract, not just EMA lengths."""
    require_replay_arithmetic()
    scope = NativeStreamSpec.model_validate(scope.model_dump())
    if scope.strategy != "jam_reversal_spot_v1" or scope.strategy_version != "1.0.1":
        raise NativeBarError("jam_history_strategy_contract_unsupported")
    if set(parameters) != set(KNOWN_STRATEGY_REQUIRED_PARAMETERS[scope.strategy]):
        raise NativeBarError("jam_history_settings_keys_invalid")
    try:
        parameters = json.loads(json.dumps(parameters, allow_nan=False))
        parsed = parse_jam_reversal_spot_parameters(parameters)
        # The historical parser uses int(); native binding must not truncate a fraction
        # or interpret a boolean as a period/count while retaining a different fingerprint.
        for name, value in parsed.items():
            if type(value) is int and (
                type(parameters[name]) is bool or Decimal(str(parameters[name])) != value
            ):
                raise ValueError("non_integral_count")
    except (KeyError, ValueError, TypeError, InvalidOperation) as exc:
        raise NativeBarError("jam_history_settings_invalid") from exc
    if strategy_parameter_fingerprint(scope.strategy, parameters) != scope.settings_fingerprint:
        raise NativeBarError("jam_history_settings_fingerprint_mismatch")
    return JamFeatureParameters.model_validate(
        {
            name: parsed[name]
            for name in JamFeatureParameters.model_fields
            if name not in {"symbol", "timeframe"}
        }
    )


@dataclass(frozen=True)
class NativeJamHistorySnapshot:
    scope: NativeStreamSpec
    head_receipt_id: str
    head_evidence_hash: str
    checkpoint: NativeBarCursor
    settings_sha256: str
    feature_state: JamFeatureState
    source_bound_from_seed: bool
    observed_online_from_seed: bool
    source_origin_verified: Literal[False] = False
    execution_authority: Literal[False] = False
    forward_qualifying: Literal[False] = False


class NativeJamHistoryReader:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        if engine.dialect.name != "sqlite":
            raise ValueError("Native Jam history currently requires SQLite")
        self.engine = engine
        self.settings = settings

    def snapshot(
        self,
        *,
        scope: NativeStreamSpec,
        strategy_parameters: dict,
        expected_head_hash: str | None = None,
    ) -> NativeJamHistorySnapshot:
        self._require_disabled()
        scope = NativeStreamSpec.model_validate(scope.model_dump())
        parameters = bind_jam_feature_parameters(scope, strategy_parameters)
        with self._read_session() as session:
            verified = verified_native_history(session, datetime(1970, 1, 1, tzinfo=UTC))
            if verified.head is None:
                raise NativeBarError("jam_history_requires_initialized_stream")
            row, head = verified.head
            if head.scope != scope:
                raise NativeBarError("jam_history_stream_scope_mismatch")
            if expected_head_hash is not None and row.evidence_hash != expected_head_hash:
                raise NativeBarError("jam_history_expected_head_changed")
            state = initialize_jam_features(verified.legacy_prefix, parameters)
            source_bound = scope.feed_id == "binance_spot_public"
            observed_online = source_bound
            # Reuse the paged receipt auditor, within the same snapshot, for the
            # tail beyond the bounded legacy prefix. Audit time still grows with history.
            for _, receipt in iter_validated_chain(session):
                source_bound &= receipt.public_source is not None
                observed_online &= receipt.public_observation is not None
                if receipt.checkpoint.bar_count > len(verified.legacy_prefix):
                    state = advance_jam_features(state, receipt.bar)
            if (
                state.bar_count != head.checkpoint.bar_count
                or state.first_open != head.checkpoint.first_open
                or state.recent[-1] != head.bar
            ):
                raise NativeBarError("jam_history_reconstruction_head_mismatch")
            self._require_disabled()
            return NativeJamHistorySnapshot(
                scope=scope,
                head_receipt_id=row.id,
                head_evidence_hash=row.evidence_hash,
                checkpoint=head.checkpoint,
                settings_sha256=content_hash(scope.settings_fingerprint),
                feature_state=state,
                source_bound_from_seed=source_bound,
                observed_online_from_seed=observed_online,
            )

    def _require_disabled(self) -> None:
        if self.settings.live_trading_enabled or self.settings.live_execution_adapter != "disabled":
            raise NativeBarError("jam_history_requires_live_disabled")

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        database = self.engine.url.database
        if not database or database == ":memory:" or self.engine.url.query.get("uri"):
            raise NativeBarError("jam_history_requires_file_backed_sqlite")
        uri = Path(database).resolve().as_uri() + "?mode=ro"
        reader = create_engine(
            "sqlite://",
            creator=lambda: sqlite3.connect(uri, uri=True, timeout=5),
            poolclass=NullPool,
        )
        try:
            with Session(reader, autoflush=False) as session:
                session.execute(text("PRAGMA query_only=ON"))
                # An ORM transaction alone does not pin SQLite SELECTs. Both audit
                # passes must see one snapshot, not a head updated between reads.
                session.execute(text("BEGIN"))
                yield session
        finally:
            reader.dispose()
