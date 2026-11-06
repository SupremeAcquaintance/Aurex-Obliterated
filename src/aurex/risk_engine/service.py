from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.backtest_engine.eligibility import (
    PaperBacktestEligibility,
    paper_backtest_eligibility,
)
from aurex.config.settings import Settings, get_settings
from aurex.db.base import utc_now
from aurex.db.models import (
    Account,
    PaperTrade,
    Position,
    RiskDecision,
    RiskProfile,
    Signal,
    SignalEvent,
    StrategyConfig,
    StrategyEvidenceReview,
)
from aurex.domain.enums import (
    PositionStatus,
    SignalStatus,
    StrategyEvidenceDecision,
    TradeStatus,
)
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.calculations import calculate_position_size, calculate_reward_risk
from aurex.risk_engine.native_spot import MAX_TRADE_RISK, evaluate_native_spot
from aurex.strategy_engine.registry import (
    strategy_lifecycle_allows_enable,
    strategy_lifecycle_reason,
    strategy_lifecycle_status,
    strategy_regime_compatible,
)
from aurex.strategy_engine.service import (
    StrategyPortfolioService,
    strategy_config_snapshot,
)

DEFAULT_ACCOUNT_NAME = "paper-main"
DEFAULT_RISK_PROFILE_NAME = "default"


@dataclass(frozen=True)
class RiskEvaluation:
    signal: Signal
    decision: RiskDecision


@dataclass(frozen=True)
class RuleEvaluation:
    approved: bool
    reason: str
    reward_risk: Decimal | None = None
    risk_amount: Decimal | None = None
    position_size: Decimal | None = None
    rules_snapshot: dict[str, object] | None = None


class RiskEngine:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings

    def validate_native_paper_decision(
        self, signal: Signal, decision: RiskDecision, *, now: datetime
    ) -> None:
        account, profile = self.get_or_create_default_profile()
        strategy = StrategyPortfolioService(self.session).get_or_create_config(signal.strategy)
        result = self._evaluate_rules(
            signal=signal,
            account=account,
            risk_profile=profile,
            strategy_config=strategy,
            effective_risk_per_trade=(
                strategy.risk_per_trade
                if strategy.risk_per_trade is not None else profile.risk_per_trade
            ),
            effective_minimum_reward_risk=(
                strategy.minimum_reward_risk or profile.minimum_reward_risk
            ),
            now=now,
        )
        if not result.approved:
            raise ValueError(f"Native paper approval no longer valid: {result.reason}")
        recorded = decision.rules_snapshot.get("native_spot_budget")
        current = (result.rules_snapshot or {}).get("native_spot_budget")
        if (
            recorded is None or recorded != current
            or decision.position_size != result.position_size
            or decision.risk_amount != result.risk_amount
        ):
            raise ValueError("Native paper approval is stale or its sizing evidence changed")

    def evaluate_signal(self, signal: Signal, now: datetime | None = None) -> RiskEvaluation:
        evaluated_at = ensure_utc(now or utc_now())
        account, risk_profile = self.get_or_create_default_profile()
        strategy_config = StrategyPortfolioService(self.session).get_or_create_config(
            signal.strategy
        )
        effective_risk_per_trade = (
            strategy_config.risk_per_trade
            if strategy_config.risk_per_trade is not None
            else risk_profile.risk_per_trade
        )
        effective_minimum_reward_risk = (
            strategy_config.minimum_reward_risk
            if strategy_config.minimum_reward_risk is not None
            else risk_profile.minimum_reward_risk
        )
        if signal.source == "aurex_native":
            effective_risk_per_trade = min(
                effective_risk_per_trade, risk_profile.risk_per_trade, MAX_TRADE_RISK
            )
            effective_minimum_reward_risk = max(
                effective_minimum_reward_risk, risk_profile.minimum_reward_risk
            )
        rule_evaluation = self._evaluate_rules(
            signal=signal,
            account=account,
            risk_profile=risk_profile,
            strategy_config=strategy_config,
            effective_risk_per_trade=effective_risk_per_trade,
            effective_minimum_reward_risk=effective_minimum_reward_risk,
            now=evaluated_at,
        )
        approved = rule_evaluation.approved
        reason = rule_evaluation.reason
        reward_risk = rule_evaluation.reward_risk
        risk_amount = rule_evaluation.risk_amount
        position_size = rule_evaluation.position_size

        decision = RiskDecision(
            signal=signal,
            risk_profile_id=risk_profile.id,
            approved=approved,
            reason=reason,
            reward_risk=reward_risk,
            risk_amount=risk_amount,
            position_size=position_size,
            account_equity=account.current_equity,
            rules_snapshot={
                **risk_profile_snapshot(risk_profile),
                "strategy_config": strategy_config_snapshot(strategy_config),
                "effective_risk_per_trade": str(effective_risk_per_trade),
                "effective_minimum_reward_risk": str(effective_minimum_reward_risk),
                **(rule_evaluation.rules_snapshot or {}),
            },
        )
        self.session.add(decision)
        self.session.flush()

        if approved:
            signal.status = SignalStatus.RISK_APPROVED
            signal.rejection_reason = None
            self._add_signal_event(signal, SignalStatus.RISK_APPROVED, reason)
            SystemEventRecorder(self.session).info(
                "risk_engine",
                "Risk approved signal",
                {
                    "signal_id": signal.id,
                    "risk_decision_id": decision.id,
                    "symbol": signal.symbol,
                    "strategy": signal.strategy,
                    "position_size": str(position_size),
                    "risk_amount": str(risk_amount),
                },
                occurred_at=evaluated_at,
            )
        else:
            signal.status = SignalStatus.RISK_REJECTED
            signal.rejection_reason = reason
            self._add_signal_event(signal, SignalStatus.RISK_REJECTED, reason)
            SystemEventRecorder(self.session).warning(
                "risk_engine",
                "Risk rejected signal",
                {
                    "signal_id": signal.id,
                    "risk_decision_id": decision.id,
                    "symbol": signal.symbol,
                    "strategy": signal.strategy,
                    "reason": reason,
                },
                occurred_at=evaluated_at,
            )

        signal.processed_at = evaluated_at
        self.session.flush()
        return RiskEvaluation(signal=signal, decision=decision)

    def risk_status(self) -> dict[str, object]:
        account, risk_profile = self.get_or_create_default_profile()
        open_positions = self._open_position_count(account)
        daily_realized_pl = self._realized_pl_since(account, day_start(utc_now()))
        weekly_realized_pl = self._realized_pl_since(account, week_start(utc_now()))

        return {
            "account_id": account.id,
            "account_name": account.name,
            "account_mode": account.mode,
            "currency": account.currency,
            "current_equity": account.current_equity,
            "risk_profile_id": risk_profile.id,
            "risk_profile_name": risk_profile.name,
            "risk_per_trade": risk_profile.risk_per_trade,
            "max_daily_loss": risk_profile.max_daily_loss,
            "max_weekly_loss": risk_profile.max_weekly_loss,
            "max_open_positions": risk_profile.max_open_positions,
            "minimum_reward_risk": risk_profile.minimum_reward_risk,
            "max_signal_age_seconds": risk_profile.max_signal_age_seconds,
            "kill_switch_enabled": risk_profile.kill_switch_enabled,
            "open_positions": open_positions,
            "daily_realized_pl": daily_realized_pl,
            "weekly_realized_pl": weekly_realized_pl,
        }

    def set_kill_switch(self, enabled: bool) -> RiskProfile:
        _, risk_profile = self.get_or_create_default_profile()
        risk_profile.kill_switch_enabled = enabled
        self.session.flush()
        return risk_profile

    def get_or_create_default_profile(self) -> tuple[Account, RiskProfile]:
        account = self.session.execute(
            select(Account).where(Account.name == DEFAULT_ACCOUNT_NAME)
        ).scalar_one_or_none()

        if account is None:
            account = Account(
                name=DEFAULT_ACCOUNT_NAME,
                mode="paper",
                currency="USD",
                starting_equity=Decimal("1000"),
                current_equity=Decimal("1000"),
            )
            self.session.add(account)
            self.session.flush()

        risk_profile = self.session.execute(
            select(RiskProfile).where(
                RiskProfile.account_id == account.id,
                RiskProfile.name == DEFAULT_RISK_PROFILE_NAME,
            )
        ).scalar_one_or_none()

        if risk_profile is None:
            risk_profile = RiskProfile(
                account=account,
                name=DEFAULT_RISK_PROFILE_NAME,
            )
            self.session.add(risk_profile)
            self.session.flush()

        return account, risk_profile

    def _evaluate_rules(
        self,
        signal: Signal,
        account: Account,
        risk_profile: RiskProfile,
        strategy_config: StrategyConfig,
        effective_risk_per_trade: Decimal,
        effective_minimum_reward_risk: Decimal,
        now: datetime,
    ) -> RuleEvaluation:
        if risk_profile.kill_switch_enabled:
            return reject("Kill switch is enabled")

        if signal.status in {SignalStatus.DUPLICATE_REJECTED, SignalStatus.REJECTED_INVALID}:
            return reject(f"Signal status {signal.status} cannot be risk-approved")

        if not strategy_lifecycle_allows_enable(signal.strategy):
            return reject(
                f"Strategy {signal.strategy} lifecycle "
                f"{strategy_lifecycle_status(signal.strategy).value} blocks execution: "
                f"{strategy_lifecycle_reason(signal.strategy)}"
            )

        if not strategy_config.is_enabled:
            return reject(f"Strategy {signal.strategy} is disabled")

        if signal.stop_loss is None:
            return reject("Missing stop loss")

        if signal.take_profit is None:
            return reject("Missing take profit")

        source_timestamp = ensure_utc(signal.source_timestamp)
        signal_age = now - source_timestamp
        if signal_age < timedelta(0):
            return reject("Signal timestamp is in the future")
        if signal_age > timedelta(seconds=risk_profile.max_signal_age_seconds):
            return reject("Signal is stale")

        if not strategy_regime_compatible(
            signal.strategy,
            signal.direction,
            signal.market_regime,
            list(strategy_config.allowed_regimes or []),
        ):
            return reject(
                f"Market regime {signal.market_regime} is incompatible with {signal.strategy}"
            )

        try:
            reward_risk = calculate_reward_risk(
                signal.direction,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit,
            )
        except ValueError as exc:
            return reject(str(exc))

        if reward_risk < effective_minimum_reward_risk:
            return reject("Reward:risk is below minimum", reward_risk=reward_risk)

        daily_loss_limit = -(account.current_equity * risk_profile.max_daily_loss)
        daily_realized_pl = self._realized_pl_since(account, day_start(now))
        if daily_realized_pl <= daily_loss_limit:
            return reject("Daily loss limit reached", reward_risk=reward_risk)

        weekly_loss_limit = -(account.current_equity * risk_profile.max_weekly_loss)
        weekly_realized_pl = self._realized_pl_since(account, week_start(now))
        if weekly_realized_pl <= weekly_loss_limit:
            return reject("Weekly loss limit reached", reward_risk=reward_risk)

        if (
            strategy_config.max_open_positions is not None
            and self._open_trade_count_by_strategy(account, signal.strategy)
            >= strategy_config.max_open_positions
        ):
            return reject(
                f"Strategy {signal.strategy} max open positions reached",
                reward_risk=reward_risk,
            )

        if self._open_position_count(account) >= risk_profile.max_open_positions:
            return reject("Max open positions reached", reward_risk=reward_risk)

        backtest_gate = paper_backtest_eligibility(
            self.session,
            strategy=signal.strategy,
            symbol=signal.symbol,
        )
        backtest_gate_snapshot = paper_backtest_gate_snapshot(backtest_gate)
        if not backtest_gate.approved:
            return reject(
                f"Paper trading requires accepted backtest evidence: {backtest_gate.reason}",
                reward_risk=reward_risk,
                rules_snapshot=backtest_gate_snapshot,
            )
        signal_provenance_gate = signal_backtest_provenance_gate(signal, backtest_gate)
        signal_provenance_gate_snapshot = signal_backtest_provenance_gate_snapshot(
            signal_provenance_gate
        )
        if signal_provenance_gate["blocked"]:
            return reject(
                "Paper trading requires signal provenance matching accepted backtest: "
                f"{signal_provenance_gate['reason']}",
                reward_risk=reward_risk,
                rules_snapshot={
                    **backtest_gate_snapshot,
                    **signal_provenance_gate_snapshot,
                },
            )

        strategy_review_gate = latest_strategy_evidence_review_gate(
            self.session,
            strategy=signal.strategy,
            symbol=signal.symbol,
        )
        strategy_review_gate_snapshot = strategy_evidence_review_gate_snapshot(
            strategy_review_gate
        )
        if strategy_review_gate["blocked"]:
            return reject(
                "Paper trading blocked by latest strategy evidence review: "
                f"{strategy_review_gate['reason']}",
                reward_risk=reward_risk,
                rules_snapshot={
                    **backtest_gate_snapshot,
                    **signal_provenance_gate_snapshot,
                    **strategy_review_gate_snapshot,
                },
            )

        native_snapshot = {}
        try:
            if signal.source == "aurex_native":
                sizing = evaluate_native_spot(
                    self.session, self.settings or get_settings(), signal, account,
                    risk_profile, strategy_config, now,
                )
                risk_amount, position_size = sizing.modeled_stop_loss, sizing.quantity
                reward_risk = sizing.net_reward_risk
                native_snapshot = {"native_spot_budget": sizing.snapshot}
            else:
                risk_amount, position_size = calculate_position_size(
                    account.current_equity,
                    effective_risk_per_trade,
                    signal.entry_price,
                    signal.stop_loss,
                )
        except ValueError as exc:
            return reject(
                str(exc),
                reward_risk=reward_risk,
                rules_snapshot={
                    **backtest_gate_snapshot,
                    **signal_provenance_gate_snapshot,
                    **strategy_review_gate_snapshot,
                },
            )

        return RuleEvaluation(
            approved=True,
            reason="Risk approved",
            reward_risk=reward_risk,
            risk_amount=risk_amount,
            position_size=position_size,
            rules_snapshot={
                **backtest_gate_snapshot,
                **signal_provenance_gate_snapshot,
                **strategy_review_gate_snapshot,
                **native_snapshot,
            },
        )

    def _realized_pl_since(self, account: Account, since: datetime) -> Decimal:
        value = self.session.execute(
            select(func.coalesce(func.sum(PaperTrade.realized_pl), Decimal("0"))).where(
                PaperTrade.account_id == account.id,
                PaperTrade.status == TradeStatus.CLOSED,
                PaperTrade.closed_at >= since,
            )
        ).scalar_one()
        return Decimal(value)

    def _open_position_count(self, account: Account) -> int:
        return int(
            self.session.execute(
                select(func.count(Position.id)).where(
                    Position.account_id == account.id,
                    Position.status == PositionStatus.OPEN,
                )
            ).scalar_one()
        )

    def _open_trade_count_by_strategy(self, account: Account, strategy: str) -> int:
        return int(
            self.session.execute(
                select(func.count(PaperTrade.id)).where(
                    PaperTrade.account_id == account.id,
                    PaperTrade.strategy == strategy,
                    PaperTrade.status == TradeStatus.OPEN,
                )
            ).scalar_one()
        )

    def _add_signal_event(self, signal: Signal, status: SignalStatus, message: str) -> None:
        self.session.add(
            SignalEvent(
                signal=signal,
                status=status,
                message=message,
                metadata_json={},
            )
        )


def reject(
    reason: str,
    reward_risk: Decimal | None = None,
    rules_snapshot: dict[str, object] | None = None,
) -> RuleEvaluation:
    return RuleEvaluation(
        approved=False,
        reason=reason,
        reward_risk=reward_risk,
        rules_snapshot=rules_snapshot,
    )


def paper_backtest_gate_snapshot(gate: PaperBacktestEligibility) -> dict[str, object]:
    return {
        "paper_backtest_gate": {
            "approved": gate.approved,
            "reason": gate.reason,
            "backtest_run_id": gate.backtest_run_id,
            "evidence_snapshot": gate.evidence_snapshot,
        }
    }


def signal_backtest_provenance_gate(
    signal: Signal,
    backtest_gate: PaperBacktestEligibility,
) -> dict[str, object]:
    evidence = backtest_gate.evidence_snapshot or {}
    parameter_evidence = evidence.get("strategy_parameter_evidence") or {}
    known_strategy = bool(
        isinstance(parameter_evidence, dict)
        and parameter_evidence.get("known_strategy")
    )
    expected_version = evidence.get("strategy_version")
    expected_fingerprint = evidence.get("strategy_parameter_fingerprint")
    payload = signal.normalized_payload or {}
    signal_version = payload.get("strategy_version")
    signal_fingerprint = payload.get("settings_fingerprint")
    reasons: list[str] = []

    if known_strategy:
        if not signal_version:
            reasons.append("signal_strategy_version_missing")
        elif expected_version and signal_version != expected_version:
            reasons.append("signal_strategy_version_mismatch")

        if not signal_fingerprint:
            reasons.append("signal_settings_fingerprint_missing")
        elif expected_fingerprint and signal_fingerprint != expected_fingerprint:
            reasons.append("signal_settings_fingerprint_mismatch")

    return {
        "blocked": bool(reasons),
        "reason": reasons[0] if reasons else "signal_matches_accepted_backtest",
        "reasons": reasons,
        "known_strategy": known_strategy,
        "strategy": signal.strategy,
        "signal_strategy_version": signal_version,
        "accepted_backtest_strategy_version": expected_version,
        "signal_settings_fingerprint": signal_fingerprint,
        "accepted_backtest_settings_fingerprint": expected_fingerprint,
        "backtest_run_id": backtest_gate.backtest_run_id,
    }


def signal_backtest_provenance_gate_snapshot(gate: dict[str, object]) -> dict[str, object]:
    return {"signal_backtest_provenance_gate": gate}


def latest_strategy_evidence_review_gate(
    session: Session,
    *,
    strategy: str,
    symbol: str,
) -> dict[str, object]:
    symbol = symbol.upper()
    reviews = session.execute(
        select(StrategyEvidenceReview)
        .where(StrategyEvidenceReview.strategy == strategy)
        .order_by(StrategyEvidenceReview.reviewed_at.desc())
    ).scalars()
    for review in reviews:
        review_symbols = {item.upper() for item in review.symbols or []}
        if review_symbols and symbol not in review_symbols:
            continue
        blocked = review.decision == StrategyEvidenceDecision.DO_NOT_TRADE
        return {
            "blocked": blocked,
            "reason": (
                "strategy_evidence_review_do_not_trade"
                if blocked
                else "latest_strategy_evidence_review_allows_paper_trading"
            ),
            "review_id": review.id,
            "decision": review.decision.value,
            "strategy": review.strategy,
            "symbols": list(review.symbols or []),
            "summary": review.summary,
            "reasons": list(review.reasons or []),
            "next_actions": list(review.next_actions or []),
            "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        }
    return {
        "blocked": False,
        "reason": "strategy_evidence_review_not_recorded",
        "review_id": None,
        "decision": None,
        "strategy": strategy,
        "symbols": [symbol],
        "summary": None,
        "reasons": [],
        "next_actions": [],
        "reviewed_at": None,
    }


def strategy_evidence_review_gate_snapshot(gate: dict[str, object]) -> dict[str, object]:
    return {"strategy_evidence_review_gate": gate}


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def day_start(value: datetime) -> datetime:
    value = ensure_utc(value)
    return datetime.combine(value.date(), time.min, tzinfo=UTC)


def week_start(value: datetime) -> datetime:
    value = day_start(value)
    return value - timedelta(days=value.weekday())


def risk_profile_snapshot(risk_profile: RiskProfile) -> dict[str, str | int | bool]:
    return {
        "risk_per_trade": str(risk_profile.risk_per_trade),
        "max_daily_loss": str(risk_profile.max_daily_loss),
        "max_weekly_loss": str(risk_profile.max_weekly_loss),
        "max_open_positions": risk_profile.max_open_positions,
        "minimum_reward_risk": str(risk_profile.minimum_reward_risk),
        "duplicate_cooldown_minutes": risk_profile.duplicate_cooldown_minutes,
        "max_signal_age_seconds": risk_profile.max_signal_age_seconds,
        "loss_cooldown_count": risk_profile.loss_cooldown_count,
        "kill_switch_enabled": risk_profile.kill_switch_enabled,
    }
