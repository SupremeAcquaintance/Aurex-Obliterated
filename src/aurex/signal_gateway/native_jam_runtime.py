"""Audited Jam decision-to-ledger transactions; no live or qualifying fill authority.

The processor owns locking, source admission and commit. This module never commits
and never accepts caller decisions, equity, acknowledgments or a saved state cache.
"""

from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.config.settings import Settings
from aurex.db.models import (
    Account,
    NativeHistorySeed,
    PaperOrder,
    PaperTrade,
    Position,
    RiskDecision,
)
from aurex.domain.enums import PositionStatus, TradeStatus
from aurex.execution_engine.costs import modeled_execution_costs, quantized_money
from aurex.execution_engine.paper import (
    PaperExecutionEngine,
    close_execution_assumptions_snapshot,
    execution_cost_assumptions,
    paper_execution_evidence_hash,
)
from aurex.risk_engine.native_spot import INITIAL_CAPITAL, MONEY_QUANTUM, as_utc
from aurex.risk_engine.service import DEFAULT_ACCOUNT_NAME
from aurex.signal_gateway.native_bars import NativeBarError, NativeBarFrame, content_hash
from aurex.signal_gateway.native_jam_decisions import (
    JamDecisionTerms,
    JamExitCandidate,
    JamManagedPosition,
    JamSetupDecision,
    JamSetupState,
    evaluate_jam_setup,
    initialize_jam_setup,
    plan_jam_exit,
    resolve_jam_entry,
)
from aurex.signal_gateway.native_jam_features import (
    STEP,
    FeatureModel,
    JamFeatureState,
    advance_jam_features,
    initialize_jam_features,
)
from aurex.signal_gateway.native_jam_history import bind_jam_feature_parameters
from aurex.signal_gateway.native_processing import NativeSeedEvidence, NativeStreamSpec
from aurex.signal_gateway.native_recovery import (
    ONLINE_EXIT_FILL_MODEL,
    NativeRecoveryEvidence,
    RecoveryPosition,
    position_snapshot,
    recovery_exit,
)
from aurex.signal_gateway.schemas import NativeSignalPayload
from aurex.signal_gateway.service import SignalIntakeService


class JamRuntimeConfig(FeatureModel):
    parameters: dict
    terms: JamDecisionTerms

    @model_validator(mode="after")
    def native_costs(self) -> "JamRuntimeConfig":
        if self.terms.slippage_ticks != 0:
            raise ValueError("jam_native_slippage_is_recorded_as_cost_not_price")
        if self.terms.tick_size < MONEY_QUANTUM:
            raise ValueError("jam_native_tick_below_ledger_precision")
        return self

    def bind(self, scope: NativeStreamSpec):
        return bind_jam_feature_parameters(scope, self.parameters)


class JamRiskRecord(FeatureModel):
    id: str
    profile_id: str | None
    approved: bool = Field(strict=True)
    reason: str
    reward_risk: Decimal | None
    risk_amount: Decimal | None
    position_size: Decimal | None
    account_equity: Decimal | None
    rules_snapshot: dict


class JamEntryRecord(FeatureModel):
    trade_id: str
    order_id: str
    position_id: str
    account_id: str
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    risk_amount: Decimal = Field(gt=0)
    opened_at: datetime
    execution_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    _time = field_validator("opened_at")(as_utc)


class JamManagementEvidence(NativeRecoveryEvidence):
    schema_version: Literal["native_jam_managed_exit_v1"] = "native_jam_managed_exit_v1"
    plan: JamManagedPosition


class JamDecisionReceipt(FeatureModel):
    schema_version: Literal["native_jam_decision_receipt_v1"] = "native_jam_decision_receipt_v1"
    config: JamRuntimeConfig
    account_id: str
    equity_before: Decimal = Field(ge=0)
    equity_for_decision: Decimal = Field(ge=0)
    equity_after: Decimal
    decision: JamSetupDecision | None
    resolved_state: JamSetupState
    risk: JamRiskRecord | None = None
    entry: JamEntryRecord | None = None
    management: JamManagementEvidence | None = None
    managed_state: JamManagedPosition | None = None
    precision_rejected: bool = Field(default=False, strict=True)
    source_origin_verified: Literal[False] = False
    forward_qualifying: Literal[False] = False
    live_authority: Literal[False] = False


def runtime_account(session: Session, account_id: str | None = None) -> Account:
    account = session.scalar(select(Account).where(Account.name == DEFAULT_ACCOUNT_NAME))
    if (
        account is None
        or (account_id is not None and account.id != account_id)
        or account.mode != "paper"
        or account.currency not in {"USD", "USDT"}
        or account.starting_equity != INITIAL_CAPITAL
    ):
        raise NativeBarError("jam_runtime_requires_existing_100_unit_paper_account")
    total = Decimal("0")
    for trade in session.scalars(
        select(PaperTrade).where(
            PaperTrade.account_id == account.id, PaperTrade.status == TradeStatus.CLOSED
        )
    ).yield_per(128):
        if trade.realized_pl is None or trade.closed_at is None:
            raise NativeBarError("jam_runtime_closed_ledger_invalid")
        total += trade.realized_pl
    if account.current_equity != account.starting_equity + total:
        raise NativeBarError("jam_runtime_equity_unreconciled")
    return account


def require_runtime_ledger(session: Session, entry: JamEntryRecord | None) -> None:
    orphan = session.scalar(
        select(PaperOrder.id)
        .outerjoin(PaperTrade, PaperTrade.paper_order_id == PaperOrder.id)
        .where(PaperTrade.id.is_(None))
        .limit(1)
    )
    opened = list(
        session.scalars(select(PaperTrade.id).where(PaperTrade.status == TradeStatus.OPEN).limit(2))
    )
    positions = list(
        session.scalars(select(Position.id).where(Position.status == PositionStatus.OPEN).limit(2))
    )
    if (
        orphan is not None
        or opened != ([entry.trade_id] if entry else [])
        or positions != ([entry.position_id] if entry else [])
    ):
        raise NativeBarError("jam_runtime_open_ledger_unreconciled")


def request_for(decision: JamSetupDecision, scope: NativeStreamSpec, frame: NativeBarFrame):
    candidate = decision.state.awaiting_entry
    if candidate is None:
        return None
    stop = candidate.stop_loss.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
    target = candidate.take_profit.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
    if not Decimal("0") < stop < frame.bar.close < target < Decimal("1000000000000"):
        return None
    return NativeSignalPayload(
        source="aurex_native",
        strategy=scope.strategy,
        strategy_version=scope.strategy_version,
        settings_fingerprint=scope.settings_fingerprint,
        symbol="BTCUSDT",
        timeframe="15m",
        direction="LONG",
        entry_price=frame.bar.close,
        stop_loss=stop,
        take_profit=target,
        market_regime="BREAKOUT_EXPANSION",
        timestamp=frame.closed_at,
    )


def risk_record(session: Session, signal_id: str | None) -> JamRiskRecord | None:
    if signal_id is None:
        return None
    rows = list(
        session.scalars(select(RiskDecision).where(RiskDecision.signal_id == signal_id).limit(2))
    )
    if len(rows) > 1:
        raise NativeBarError("jam_runtime_risk_ambiguous")
    if not rows:
        return None
    row = rows[0]
    session.refresh(row)
    return JamRiskRecord(
        id=row.id,
        profile_id=row.risk_profile_id,
        approved=row.approved,
        reason=row.reason,
        reward_risk=row.reward_risk,
        risk_amount=row.risk_amount,
        position_size=row.position_size,
        account_equity=row.account_equity,
        rules_snapshot=row.rules_snapshot,
    )


def entry_record(session: Session, signal_id: str, account_id: str) -> JamEntryRecord:
    orders = list(
        session.scalars(select(PaperOrder).where(PaperOrder.signal_id == signal_id).limit(2))
    )
    if len(orders) != 1:
        raise NativeBarError("jam_runtime_entry_order_ambiguous")
    order = orders[0]
    trades = list(
        session.scalars(select(PaperTrade).where(PaperTrade.paper_order_id == order.id).limit(2))
    )
    positions = list(
        session.scalars(
            select(Position)
            .where(Position.account_id == account_id, Position.status == PositionStatus.OPEN)
            .limit(2)
        )
    )
    if len(trades) != 1 or len(positions) != 1:
        raise NativeBarError("jam_runtime_entry_position_ambiguous")
    trade, position = trades[0], positions[0]
    for row in (order, trade, position):
        session.refresh(row)
    if trade.account_id != account_id or trade.status != TradeStatus.OPEN:
        raise NativeBarError("jam_runtime_entry_ledger_changed")
    return JamEntryRecord(
        trade_id=trade.id,
        order_id=order.id,
        position_id=position.id,
        account_id=trade.account_id,
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        quantity=trade.quantity,
        risk_amount=trade.risk_amount,
        opened_at=as_utc(trade.opened_at),
        execution_hash=order.execution_assumptions_hash,
    )


def opening_hash(snapshot: RecoveryPosition) -> str:
    return paper_execution_evidence_hash(
        {**snapshot.opening_assumptions, "fill_model": ONLINE_EXIT_FILL_MODEL}
    )


def bound_entry(session: Session, entry: JamEntryRecord, scope: NativeStreamSpec):
    trade = session.get(PaperTrade, entry.trade_id)
    position = session.get(Position, entry.position_id)
    if trade is None or position is None:
        raise NativeBarError("jam_runtime_entry_ledger_missing")
    snapshot = position_snapshot(
        session, trade, position, scope.model_dump(mode="json"), Settings.model_construct()
    )
    expected = JamEntryRecord(
        **{
            name: getattr(snapshot, name)
            for name in JamEntryRecord.model_fields
            if name != "execution_hash"
        },
        execution_hash=opening_hash(snapshot),
    )
    if expected != entry or trade.paper_order.fill_model != ONLINE_EXIT_FILL_MODEL:
        raise NativeBarError("jam_runtime_entry_evidence_mismatch")
    return snapshot


def initial_management(entry: JamEntryRecord, state: JamSetupState) -> JamManagedPosition:
    candidate = state.awaiting_entry
    if (
        candidate is None
        or not state.last_open + STEP <= entry.opened_at < state.last_open + 2 * STEP
    ):
        raise NativeBarError("jam_runtime_entry_time_or_candidate_invalid")
    # entry_open is the signal-bar cursor, NOT a fabricated exchange/fill timestamp.
    # The actual fill time stays in the ledger and controls partial-candle bounds.
    return JamManagedPosition(
        first_open=state.first_open,
        bar_count=state.bar_count,
        context_hash=state.context_hash,
        feature_hash=state.feature_hash,
        entry_open=state.last_open,
        entry_price=entry.entry_price,
        quantity=entry.quantity,
        initial_stop=entry.stop_loss,
        stop_loss=entry.stop_loss,
        take_profit=entry.take_profit,
        failure_level=candidate.failure_level,
        best_price=entry.entry_price,
    )


def management_plan(
    state: JamManagedPosition,
    snapshot: RecoveryPosition,
    features: JamFeatureState,
    scope: NativeStreamSpec,
    config: JamRuntimeConfig,
) -> JamManagedPosition:
    bar = features.recent[-1]
    if snapshot.opened_at > bar.timestamp:
        if (
            features.first_open != state.first_open
            or features.bar_count != state.bar_count + 1
            or state.exit_candidate is not None
        ):
            raise NativeBarError("jam_runtime_partial_management_state_invalid")
        fill = recovery_exit(bar, snapshot)
        candidate = (
            None
            if fill is None
            else JamExitCandidate(
                phase="CLOSE" if fill.reason == "PARTIAL_ENTRY_TARGET_AT_CLOSE" else "BRACKET",
                price=fill.price,
                reason=fill.reason,
                slippage=fill.slippage,
                intrabar_ambiguous=fill.intrabar_ambiguous,
            )
        )
        # A partial candle's high may precede the fill. Hold dynamic stops and best
        # price unchanged until a fully observed candle; only conservative exits apply.
        plan = JamManagedPosition.model_validate(
            {
                **state.model_dump(),
                "bar_count": features.bar_count,
                "feature_hash": content_hash(features.model_dump(mode="json")),
                "exit_candidate": candidate,
            }
        )
    else:
        plan = plan_jam_exit(
            state,
            features=features,
            scope=scope,
            parameters=config.parameters,
            terms=config.terms,
        )
    data = plan.model_dump()
    data["stop_loss"] = plan.stop_loss.quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)
    if plan.exit_candidate is not None:
        data["exit_candidate"]["price"] = plan.exit_candidate.price.quantize(
            MONEY_QUANTUM, rounding=ROUND_DOWN
        )
    return JamManagedPosition.model_validate(data)


def execute_management(
    session: Session,
    settings: Settings,
    snapshot: RecoveryPosition,
    plan: JamManagedPosition,
    bar,
    now: datetime,
) -> JamManagementEvidence:
    fill = plan.exit_candidate
    trade = session.get(PaperTrade, snapshot.trade_id)
    if fill is not None:
        PaperExecutionEngine(session, settings).close_trade(
            trade.id, fill.price, fill.reason, now=now
        )
        order = trade.paper_order
        order.execution_assumptions = {**order.execution_assumptions, "cost_floor_enforced": True}
        order.execution_assumptions_hash = paper_execution_evidence_hash(
            order.execution_assumptions
        )
        session.flush()
        session.refresh(trade)
    return JamManagementEvidence(
        plan=plan,
        disposition="CLOSED" if fill else "HELD",
        position=snapshot,
        partial_entry_bar=snapshot.opened_at > bar.timestamp,
        exit_price=fill.price if fill else None,
        exit_reason=fill.reason if fill else None,
        recognized_at=now if fill else None,
        total_fees=trade.fees if fill else None,
        total_slippage=trade.slippage if fill else None,
        realized_pl=trade.realized_pl if fill else None,
        execution_hash_after=trade.paper_order.execution_assumptions_hash
        if fill
        else opening_hash(snapshot),
    )


def verify_management(
    session: Session,
    evidence: JamManagementEvidence,
    snapshot: RecoveryPosition,
    plan: JamManagedPosition,
    bar,
    processed_at: datetime,
) -> Decimal:
    fill = plan.exit_candidate
    if (
        evidence.position != snapshot
        or evidence.plan != plan
        or evidence.partial_entry_bar != (snapshot.opened_at > bar.timestamp)
        or evidence.disposition != ("CLOSED" if fill else "HELD")
    ):
        raise NativeBarError("jam_runtime_management_reconstruction_mismatch")
    if fill is None:
        if evidence.execution_hash_after != opening_hash(snapshot):
            raise NativeBarError("jam_runtime_held_execution_mismatch")
        return Decimal("0")
    settings = Settings.model_construct()
    costs = execution_cost_assumptions(snapshot.opening_assumptions, settings)
    exit_fees, exit_slippage = modeled_execution_costs(
        price=fill.price,
        quantity=snapshot.quantity,
        **{key: costs[key] for key in ("commission_bps", "half_spread_bps", "market_impact_bps")},
    )
    opening = snapshot.opening_assumptions["entry"]
    fees = quantized_money(Decimal(opening["fees"]) + exit_fees)
    slippage = quantized_money(Decimal(opening["slippage"]) + exit_slippage)
    pl = quantized_money((fill.price - snapshot.entry_price) * snapshot.quantity - fees - slippage)
    trade = session.get(PaperTrade, snapshot.trade_id)
    position = session.get(Position, snapshot.position_id)
    expected_execution = close_execution_assumptions_snapshot(
        order=PaperOrder(
            execution_assumptions={
                **snapshot.opening_assumptions,
                "fill_model": ONLINE_EXIT_FILL_MODEL,
            },
            fill_model=ONLINE_EXIT_FILL_MODEL,
        ),
        exit_price=fill.price,
        closed_at=evidence.recognized_at,
        modeled_fees=exit_fees,
        modeled_slippage=exit_slippage,
        provided_fees=None,
        provided_slippage=None,
        effective_fees=exit_fees,
        effective_slippage=exit_slippage,
        total_fees=fees,
        total_slippage=slippage,
        fallback_settings=settings,
    )
    expected_execution["cost_floor_enforced"] = True
    if (
        trade.status != TradeStatus.CLOSED
        or position.status != PositionStatus.CLOSED
        or trade.closed_at is None
        or position.closed_at is None
        or as_utc(trade.closed_at) != evidence.recognized_at
        or as_utc(position.closed_at) != evidence.recognized_at
        or not bar.timestamp + STEP <= evidence.recognized_at <= processed_at
        or trade.exit_price != fill.price
        or evidence.exit_price != fill.price
        or trade.close_reason != fill.reason
        or evidence.exit_reason != fill.reason
        or trade.fees != fees
        or evidence.total_fees != fees
        or trade.slippage != slippage
        or evidence.total_slippage != slippage
        or trade.realized_pl != pl
        or evidence.realized_pl != pl
        or trade.paper_order.execution_assumptions != expected_execution
        or evidence.execution_hash_after != paper_execution_evidence_hash(expected_execution)
        or trade.paper_order.execution_assumptions_hash != evidence.execution_hash_after
    ):
        raise NativeBarError("jam_runtime_close_ledger_mismatch")
    return pl


class JamChainAudit:
    """Recompute decisions from the retained seed and every prior receipt, not caches."""

    def __init__(self, session: Session):
        self.session = session
        self.config: JamRuntimeConfig | None = None
        self.features: JamFeatureState | None = None
        self.state: JamSetupState | None = None
        self.account_id: str | None = None
        self.entry: JamEntryRecord | None = None
        self.managed: JamManagedPosition | None = None
        self.equity: Decimal | None = None
        self.started_at: datetime | None = None
        self.closed_count = 0

    def finish(self) -> None:
        if self.config is None:
            return
        account = runtime_account(self.session, self.account_id)
        require_runtime_ledger(self.session, self.entry)
        closed_count = self.session.scalar(
            select(func.count())
            .select_from(PaperTrade)
            .where(
                PaperTrade.account_id == self.account_id,
                PaperTrade.status == TradeStatus.CLOSED,
                PaperTrade.closed_at > self.started_at,
            )
        )
        if account.current_equity != self.equity or closed_count != self.closed_count:
            raise NativeBarError("jam_runtime_account_changed_without_receipt")

    def consume(self, row, receipt) -> None:
        if receipt.jam_decision is None:
            if self.config is not None:
                raise NativeBarError("jam_runtime_decision_binding_dropped")
            return
        saved = JamDecisionReceipt.model_validate(receipt.jam_decision)
        config = saved.config
        management = None
        decision_equity = saved.equity_before
        if self.config is None:
            account = runtime_account(self.session, saved.account_id)
            if receipt.sequence != 1 or self.entry is not None:
                raise NativeBarError("jam_runtime_requires_new_stream")
            self.started_at = receipt.processed_at
            self.equity = account.starting_equity + sum(
                (
                    trade.realized_pl
                    for trade in self.session.scalars(
                        select(PaperTrade).where(
                            PaperTrade.account_id == account.id,
                            PaperTrade.status == TradeStatus.CLOSED,
                            PaperTrade.closed_at <= self.started_at,
                        )
                    ).yield_per(128)
                ),
                Decimal("0"),
            )
            seed_row = self.session.scalar(
                select(NativeHistorySeed).where(NativeHistorySeed.stream_key == receipt.stream_key)
            )
            if seed_row is None:
                raise NativeBarError("jam_runtime_seed_missing")
            seed = NativeSeedEvidence.model_validate(seed_row.evidence)
            if (
                seed.scope != receipt.scope
                or seed.candles[-1] != receipt.bar
                or len(seed.candles) != receipt.checkpoint.bar_count
                or seed_row.evidence_hash != content_hash(seed.model_dump(mode="json"))
                or content_hash([bar.model_dump(mode="json") for bar in seed.candles])
                != receipt.checkpoint.history_sha256
            ):
                raise NativeBarError("jam_runtime_seed_binding_mismatch")
            self.features = initialize_jam_features(seed.candles, config.bind(receipt.scope))
            self.config, self.account_id = config, account.id
            state = initialize_jam_setup(
                features=self.features,
                scope=receipt.scope,
                parameters=config.parameters,
                terms=config.terms,
            )
            expected_decision = None
            request = None
        else:
            if config != self.config or saved.account_id != self.account_id:
                raise NativeBarError("jam_runtime_config_or_account_changed")
            self.features = advance_jam_features(self.features, receipt.bar)
            if self.entry is not None:
                snapshot = bound_entry(self.session, self.entry, receipt.scope)
                plan = management_plan(self.managed, snapshot, self.features, receipt.scope, config)
                if saved.management is None:
                    raise NativeBarError("jam_runtime_management_missing")
                management = saved.management
                pl = verify_management(
                    self.session, management, snapshot, plan, receipt.bar, receipt.processed_at
                )
                if plan.exit_candidate is not None:
                    self.closed_count += 1
                    if plan.exit_candidate.phase == "BRACKET":
                        decision_equity += pl
                        self.entry, self.managed = None, None
                else:
                    self.managed = plan
            expected_decision = evaluate_jam_setup(
                self.state,
                features=self.features,
                scope=receipt.scope,
                parameters=config.parameters,
                terms=config.terms,
                equity=decision_equity,
                entry_window=True,
                position_open=self.entry is not None,
            )
            state = expected_decision.state
            request = request_for(
                expected_decision,
                receipt.scope,
                NativeBarFrame(
                    "READY",
                    receipt.bar,
                    receipt.closed_at,
                    receipt.candle_id,
                    receipt.checkpoint,
                    {},
                ),
            )
        if (
            saved.equity_before != self.equity
            or saved.equity_for_decision != decision_equity
            or saved.management != management
        ):
            raise NativeBarError("jam_runtime_equity_or_management_mismatch")
        if management is not None and management.disposition == "CLOSED":
            self.equity += management.realized_pl
            self.entry, self.managed = None, None
        if saved.equity_after != self.equity:
            raise NativeBarError("jam_runtime_equity_after_mismatch")
        if saved.decision != expected_decision or receipt.signal_request != request:
            raise NativeBarError("jam_runtime_decision_reconstruction_mismatch")
        precision_rejected = state.awaiting_entry is not None and request is None
        if saved.precision_rejected != precision_rejected:
            raise NativeBarError("jam_runtime_precision_disposition_mismatch")
        risk = risk_record(self.session, receipt.signal_id)
        if saved.risk != risk:
            raise NativeBarError("jam_runtime_risk_evidence_mismatch")
        if receipt.outcome == "PAPER_EXECUTED":
            if (
                risk is None
                or not risk.approved
                or request is None
                or risk.account_equity != saved.equity_for_decision
            ):
                raise NativeBarError("jam_runtime_entry_without_risk_approval")
            actual = saved.entry
            if (
                actual is None
                or actual.account_id != self.account_id
                or self.entry is not None
                or not receipt.closed_at <= actual.opened_at <= receipt.processed_at
            ):
                raise NativeBarError("jam_runtime_entry_evidence_mismatch")
            bound = bound_entry(self.session, actual, receipt.scope)
            if bound.entry_receipt_id != row.id or bound.entry_receipt_hash != row.evidence_hash:
                raise NativeBarError("jam_runtime_entry_receipt_mismatch")
            self.entry = actual
            self.managed = initial_management(actual, state)
        else:
            if saved.entry is not None or (risk is not None and risk.approved):
                raise NativeBarError("jam_runtime_rejection_has_approved_entry")
            if receipt.outcome == "RISK_REJECTED" and risk is None:
                raise NativeBarError("jam_runtime_rejection_missing_risk")
            if (
                receipt.signal_id is not None
                and self.session.scalar(
                    select(PaperOrder.id).where(PaperOrder.signal_id == receipt.signal_id)
                )
                is not None
            ):
                raise NativeBarError("jam_runtime_rejection_has_order")
        if state.awaiting_entry is not None:
            state = resolve_jam_entry(
                state, proposal_hash=state.proposal_hash, filled=saved.entry is not None
            )
        if state != saved.resolved_state or self.managed != saved.managed_state:
            raise NativeBarError("jam_runtime_resolution_reconstruction_mismatch")
        self.state = state


def process_jam_decision(
    session: Session,
    settings: Settings,
    scope: NativeStreamSpec,
    config: JamRuntimeConfig,
    frame: NativeBarFrame,
    history: list,
    audit: JamChainAudit | None,
    now: datetime,
):
    config = JamRuntimeConfig.model_validate_json(config.model_dump_json())
    config.bind(scope)
    connection = session.connection()
    if (
        connection.dialect.name != "sqlite"
        or not connection.connection.driver_connection.in_transaction
    ):
        raise NativeBarError("jam_runtime_requires_locked_transaction")
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        raise NativeBarError("jam_runtime_requires_live_disabled")
    active_entry = audit.entry if audit else None
    managed = audit.managed if audit else None
    require_runtime_ledger(session, active_entry)
    account = runtime_account(session, audit.account_id if audit else None)
    equity_before = account.current_equity
    management = None
    pending_management = None
    if audit is None:
        features = initialize_jam_features(history, config.bind(scope))
        state = initialize_jam_setup(
            features=features, scope=scope, parameters=config.parameters, terms=config.terms
        )
        decision = None
        request = None
    else:
        if config != audit.config:
            raise NativeBarError("jam_runtime_config_changed")
        features = advance_jam_features(audit.features, frame.bar)
        if active_entry is not None:
            snapshot = bound_entry(session, active_entry, scope)
            plan = management_plan(managed, snapshot, features, scope, config)
            if plan.exit_candidate is not None and plan.exit_candidate.phase == "CLOSE":
                pending_management = (snapshot, plan)
            else:
                management = execute_management(session, settings, snapshot, plan, frame.bar, now)
                if plan.exit_candidate is not None:
                    active_entry, managed = None, None
                else:
                    managed = plan
        decision = evaluate_jam_setup(
            audit.state,
            features=features,
            scope=scope,
            parameters=config.parameters,
            terms=config.terms,
            equity=account.current_equity,
            entry_window=True,
            position_open=active_entry is not None,
        )
        state = decision.state
        request = request_for(decision, scope, frame)
    equity_for_decision = account.current_equity
    if pending_management is not None:
        snapshot, plan = pending_management
        management = execute_management(session, settings, snapshot, plan, frame.bar, now)
        active_entry, managed = None, None
    precision_rejected = state.awaiting_entry is not None and request is None
    signal_id, outcome, risk, entry = None, "JAM_NO_SIGNAL", None, None
    if request is not None:
        result = SignalIntakeService(session, settings).ingest_native(request, commit=False)
        signal_id, outcome = result.signal.id, result.signal.status.value
        risk = risk_record(session, signal_id)
        if outcome == "PAPER_EXECUTED":
            order = session.scalar(select(PaperOrder).where(PaperOrder.signal_id == signal_id))
            order.fill_model = ONLINE_EXIT_FILL_MODEL
            order.execution_assumptions = {
                **order.execution_assumptions,
                "fill_model": ONLINE_EXIT_FILL_MODEL,
            }
            order.execution_assumptions_hash = paper_execution_evidence_hash(
                order.execution_assumptions
            )
            session.flush()
            entry = entry_record(session, signal_id, account.id)
            managed = initial_management(entry, state)
    if state.awaiting_entry is not None:
        state = resolve_jam_entry(
            state, proposal_hash=state.proposal_hash, filled=entry is not None
        )
    evidence = JamDecisionReceipt(
        config=config,
        account_id=account.id,
        equity_before=equity_before,
        equity_for_decision=equity_for_decision,
        equity_after=account.current_equity,
        decision=decision,
        resolved_state=state,
        risk=risk,
        entry=entry,
        management=management,
        managed_state=managed,
        precision_rejected=precision_rejected,
    )
    return evidence, request, signal_id, outcome
