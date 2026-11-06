import json
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256
from math import exp, lgamma, log, log1p

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurex.db.models import (
    PaperTrade,
    StrategyConfig,
    StrategyResearchBacktestRun,
    StrategyResearchCandidate,
    StrategyResearchObservation,
)
from aurex.domain.enums import (
    PredictionMarketSide,
    StrategyResearchObservationType,
    StrategyResearchSource,
    StrategyResearchStatus,
    TradeStatus,
)
from aurex.observability.system_events import SystemEventRecorder
from aurex.prediction_market.calculations import (
    calculate_binary_settlement_pl,
    estimate_binary_contract_fee,
    validate_probability_price,
)
from aurex.strategy_engine.registry import (
    REGISTERED_STRATEGIES,
    default_allowed_regime_values,
    strategy_lifecycle_allows_enable,
    strategy_lifecycle_reason,
    strategy_lifecycle_status,
)
from aurex.strategy_engine.schemas import (
    StrategyComparisonItem,
    StrategyComparisonResponse,
    StrategyConfigUpdate,
    StrategyResearchBacktestRequest,
    StrategyResearchBacktestResponse,
    StrategyResearchCandidateCreate,
    StrategyResearchObservationCreate,
)

ZERO = Decimal("0")
ONE = Decimal("1")
TRADE_QUANTITY = Decimal("1")
METRIC_QUANTUM = Decimal("0.0001")
MONEY_QUANTUM = Decimal("0.00000001")
RESEARCH_ONLY_REASON = (
    "research_candidate_only_backtest_and_forward_evidence_required_before_any_trade_eligibility"
)
REQUIRED_RESEARCH_EVIDENCE = {
    "accepted_backtest": "required_before_paper_eligibility",
    "chronological_oos": "required",
    "walk_forward": "required",
    "fee_net_profitability": "required",
    "paper_evidence": "required_before_live_review",
    "live_execution": "blocked",
}


class StrategyPortfolioService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_strategies(self) -> None:
        existing = {
            config.strategy: config
            for config in self.session.execute(select(StrategyConfig)).scalars()
        }
        for definition in REGISTERED_STRATEGIES.values():
            config = existing.get(definition.strategy)
            if config is None:
                self.session.add(
                    StrategyConfig(
                        strategy=definition.strategy,
                        version=definition.version,
                        display_name=definition.display_name,
                        description=definition.description,
                        is_enabled=definition.default_enabled,
                        allowed_regimes=default_allowed_regime_values(definition),
                        risk_per_trade=definition.default_risk_per_trade,
                        minimum_reward_risk=definition.default_minimum_reward_risk,
                        max_open_positions=definition.default_max_open_positions,
                        parameters={
                            "pine_path": definition.pine_path,
                            "docs_path": definition.docs_path,
                            "lifecycle_status": definition.lifecycle_status.value,
                            "lifecycle_reason": definition.lifecycle_reason,
                            "enable_eligible": strategy_lifecycle_allows_enable(
                                definition.strategy
                            ),
                            "qualification_contract_version": (
                                definition.qualification_contract_version
                            ),
                            "qualification_evidence_hash": (
                                definition.qualification_evidence_hash
                            ),
                        },
                    )
                )
                continue

            config.version = definition.version
            config.display_name = definition.display_name
            config.description = definition.description
            config.allowed_regimes = default_allowed_regime_values(definition)
            if not strategy_lifecycle_allows_enable(definition.strategy):
                config.is_enabled = False
            config.parameters = {
                **(config.parameters or {}),
                "pine_path": definition.pine_path,
                "docs_path": definition.docs_path,
                "lifecycle_status": definition.lifecycle_status.value,
                "lifecycle_reason": definition.lifecycle_reason,
                "enable_eligible": strategy_lifecycle_allows_enable(definition.strategy),
                "qualification_contract_version": (
                    definition.qualification_contract_version
                ),
                "qualification_evidence_hash": definition.qualification_evidence_hash,
            }

        self.session.flush()

    def list_configs(self) -> list[StrategyConfig]:
        self.ensure_default_strategies()
        return list(
            self.session.execute(
                select(StrategyConfig).order_by(StrategyConfig.strategy.asc())
            ).scalars()
        )

    def get_config(self, strategy: str) -> StrategyConfig | None:
        self.ensure_default_strategies()
        return self.session.execute(
            select(StrategyConfig).where(StrategyConfig.strategy == strategy)
        ).scalar_one_or_none()

    def get_or_create_config(self, strategy: str) -> StrategyConfig:
        config = self.get_config(strategy)
        if config is not None:
            return config

        config = StrategyConfig(
            strategy=strategy,
            version="unregistered",
            display_name=strategy,
            description="Unregistered strategy. Disabled until explicitly reviewed.",
            is_enabled=False,
            allowed_regimes=[],
            parameters={},
        )
        self.session.add(config)
        self.session.flush()
        return config

    def update_config(self, strategy: str, payload: StrategyConfigUpdate) -> StrategyConfig:
        config = self.get_or_create_config(strategy)
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("is_enabled") is True and not strategy_lifecycle_allows_enable(
            strategy
        ):
            lifecycle = strategy_lifecycle_status(strategy).value
            reason = strategy_lifecycle_reason(strategy)
            raise ValueError(
                f"Strategy {strategy} cannot be enabled while lifecycle is "
                f"{lifecycle}: {reason}"
            )
        for field, value in changes.items():
            setattr(config, field, value)
        SystemEventRecorder(self.session).info(
            "strategy_portfolio",
            "Strategy configuration updated",
            {
                "strategy": config.strategy,
                "is_enabled": config.is_enabled,
                "risk_per_trade": str(config.risk_per_trade),
                "minimum_reward_risk": str(config.minimum_reward_risk),
                "max_open_positions": config.max_open_positions,
            },
        )
        self.session.flush()
        return config

    def strategy_comparison(self) -> StrategyComparisonResponse:
        configs = self.list_configs()
        trades = list(self.session.execute(select(PaperTrade)).scalars())
        closed_by_strategy: dict[str, list[PaperTrade]] = defaultdict(list)
        open_by_strategy: dict[str, int] = defaultdict(int)

        for trade in trades:
            if trade.status == TradeStatus.OPEN:
                open_by_strategy[trade.strategy] += 1
            if trade.status == TradeStatus.CLOSED and trade.realized_pl is not None:
                closed_by_strategy[trade.strategy].append(trade)

        return StrategyComparisonResponse(
            strategies=[
                self._comparison_item(
                    config,
                    closed_by_strategy.get(config.strategy, []),
                    open_by_strategy.get(config.strategy, 0),
                )
                for config in configs
            ]
        )

    def register_research_candidate(
        self,
        payload: StrategyResearchCandidateCreate,
        now: datetime | None = None,
    ) -> StrategyResearchCandidate:
        observed_at = ensure_utc(now or datetime.now(UTC))
        existing = self.session.execute(
            select(StrategyResearchCandidate).where(
                StrategyResearchCandidate.source == payload.source,
                StrategyResearchCandidate.candidate_key == payload.candidate_key,
            )
        ).scalar_one_or_none()
        normalized_payload = normalize_candidate_payload(payload)
        evidence_hash = research_hash(
            {
                "source": payload.source.value,
                "candidate_key": payload.candidate_key,
                "strategy": payload.strategy,
                "display_name": payload.display_name,
                "hypothesis": payload.hypothesis,
                "normalized_payload": normalized_payload,
            }
        )
        status = research_status_for_candidate(payload.source, payload.status)
        if existing is None:
            candidate = StrategyResearchCandidate(
                source=payload.source,
                candidate_key=payload.candidate_key,
                strategy=payload.strategy,
                display_name=payload.display_name,
                hypothesis=payload.hypothesis,
                status=status,
                trade_eligible=False,
                eligibility_reason=RESEARCH_ONLY_REASON,
                required_evidence=dict(REQUIRED_RESEARCH_EVIDENCE),
                evidence_hash=evidence_hash,
                source_reference=payload.source_reference,
                raw_payload=payload.raw_payload,
                normalized_payload=normalized_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            self.session.add(candidate)
        else:
            candidate = existing
            candidate.strategy = payload.strategy
            candidate.display_name = payload.display_name
            candidate.hypothesis = payload.hypothesis
            candidate.status = status
            candidate.trade_eligible = False
            candidate.eligibility_reason = RESEARCH_ONLY_REASON
            candidate.required_evidence = dict(REQUIRED_RESEARCH_EVIDENCE)
            candidate.evidence_hash = evidence_hash
            candidate.source_reference = payload.source_reference
            candidate.raw_payload = payload.raw_payload
            candidate.normalized_payload = normalized_payload
            candidate.last_seen_at = observed_at
        self.session.flush()
        self._force_research_strategy_disabled(candidate)
        SystemEventRecorder(self.session).info(
            "strategy_research",
            "Strategy research candidate recorded",
            {
                "candidate_id": candidate.id,
                "candidate_key": candidate.candidate_key,
                "strategy": candidate.strategy,
                "source": candidate.source.value,
                "trade_eligible": candidate.trade_eligible,
                "eligibility_reason": candidate.eligibility_reason,
            },
            occurred_at=observed_at,
        )
        self.session.flush()
        return candidate

    def record_research_observation(
        self,
        payload: StrategyResearchObservationCreate,
        now: datetime | None = None,
    ) -> StrategyResearchObservation:
        observed_at = ensure_utc(payload.observed_at or now or datetime.now(UTC))
        candidate = self._research_candidate_for_observation(payload, observed_at)
        observation_snapshot = normalize_observation_payload(payload)
        evidence_hash = research_hash(
            {
                "candidate_id": candidate.id,
                "observation_type": payload.observation_type.value,
                "source_event_id": payload.source_event_id,
                "symbol": payload.symbol,
                "contract_ticker": payload.contract_ticker,
                "side": payload.side,
                "confidence": str(payload.confidence) if payload.confidence is not None else None,
                "implied_probability": (
                    str(payload.implied_probability)
                    if payload.implied_probability is not None
                    else None
                ),
                "expected_edge": (
                    str(payload.expected_edge) if payload.expected_edge is not None else None
                ),
                "observation_snapshot": observation_snapshot,
            }
        )
        existing = self._existing_observation(candidate.id, payload, evidence_hash)
        if existing is not None:
            if payload.resolved_at and existing.resolved_at is None:
                existing.resolved_at = ensure_utc(payload.resolved_at)
                existing.outcome_snapshot = payload.outcome_snapshot
                self.session.flush()
            return existing
        observation = StrategyResearchObservation(
            candidate=candidate,
            observation_type=payload.observation_type,
            source_event_id=payload.source_event_id,
            symbol=payload.symbol.upper() if payload.symbol else None,
            contract_ticker=payload.contract_ticker,
            side=payload.side.upper() if payload.side else None,
            confidence=payload.confidence,
            implied_probability=payload.implied_probability,
            expected_edge=payload.expected_edge,
            observation_snapshot=observation_snapshot,
            raw_payload=payload.raw_payload,
            evidence_hash=evidence_hash,
            observed_at=observed_at,
            resolved_at=ensure_utc(payload.resolved_at) if payload.resolved_at else None,
            outcome_snapshot=payload.outcome_snapshot,
        )
        candidate.last_seen_at = observed_at
        candidate.status = research_status_for_observation(payload.observation_type)
        candidate.trade_eligible = False
        candidate.eligibility_reason = RESEARCH_ONLY_REASON
        self.session.add(observation)
        self.session.flush()
        SystemEventRecorder(self.session).info(
            "strategy_research",
            "Strategy research observation recorded",
            {
                "candidate_id": candidate.id,
                "observation_id": observation.id,
                "observation_type": observation.observation_type.value,
                "strategy": candidate.strategy,
                "trade_eligible": candidate.trade_eligible,
            },
            occurred_at=observed_at,
        )
        self.session.flush()
        return observation

    def list_research_candidates(self) -> list[dict]:
        candidates = list(
            self.session.execute(
                select(StrategyResearchCandidate).order_by(
                    StrategyResearchCandidate.last_seen_at.desc()
                )
            ).scalars()
        )
        counts = dict(
            self.session.execute(
                select(
                    StrategyResearchObservation.candidate_id,
                    func.count(StrategyResearchObservation.id),
                ).group_by(StrategyResearchObservation.candidate_id)
            ).all()
        )
        return [
            research_candidate_response(candidate, counts.get(candidate.id, 0))
            for candidate in candidates
        ]

    def list_research_observations(
        self,
        candidate_id: str | None = None,
        limit: int = 50,
    ) -> list[StrategyResearchObservation]:
        bounded_limit = min(max(limit, 1), 200)
        query = select(StrategyResearchObservation).order_by(
            StrategyResearchObservation.observed_at.desc()
        )
        if candidate_id:
            query = query.where(StrategyResearchObservation.candidate_id == candidate_id)
        return list(self.session.execute(query.limit(bounded_limit)).scalars())

    def research_readiness_queue(self, limit: int = 25) -> dict[str, object]:
        generated_at = ensure_utc(datetime.now(UTC))
        bounded_limit = min(max(limit, 1), 100)
        candidates = list(
            self.session.execute(
                select(StrategyResearchCandidate).order_by(
                    StrategyResearchCandidate.last_seen_at.desc()
                )
            ).scalars()
        )
        observation_counts = dict(
            self.session.execute(
                select(
                    StrategyResearchObservation.candidate_id,
                    func.count(StrategyResearchObservation.id),
                ).group_by(StrategyResearchObservation.candidate_id)
            ).all()
        )
        resolved_counts = dict(
            self.session.execute(
                select(
                    StrategyResearchObservation.candidate_id,
                    func.count(StrategyResearchObservation.id),
                )
                .where(StrategyResearchObservation.resolved_at.is_not(None))
                .group_by(StrategyResearchObservation.candidate_id)
            ).all()
        )
        latest_runs: dict[str, StrategyResearchBacktestRun] = {}
        runs = list(
            self.session.execute(
                select(StrategyResearchBacktestRun).order_by(
                    StrategyResearchBacktestRun.reviewed_at.desc()
                )
            ).scalars()
        )
        for run in runs:
            latest_runs.setdefault(run.candidate_id, run)

        items = [
            research_readiness_item(
                candidate,
                observation_count=int(observation_counts.get(candidate.id, 0)),
                resolved_observation_count=int(resolved_counts.get(candidate.id, 0)),
                latest_run=latest_runs.get(candidate.id),
            )
            for candidate in candidates
        ]
        items.sort(
            key=lambda item: (
                int(item.pop("_sort_priority")),
                -int(item["resolved_observation_count"]),
                str(item["candidate_key"]),
            )
        )
        for index, item in enumerate(items, start=1):
            item["rank"] = index

        summary = research_readiness_summary(items)
        return {
            "generated_at": generated_at,
            "candidate_count": len(candidates),
            "summary": summary,
            "items": items[:bounded_limit],
        }

    def research_evidence_for_candidate(
        self,
        candidate_id: str,
        observation_limit: int = 50,
        backtest_limit: int = 10,
    ) -> dict[str, object]:
        candidate = self.session.get(StrategyResearchCandidate, candidate_id)
        if candidate is None:
            raise ValueError("Strategy research candidate not found")
        bounded_observation_limit = min(max(observation_limit, 1), 200)
        bounded_backtest_limit = min(max(backtest_limit, 1), 50)
        observations = list(
            self.session.execute(
                select(StrategyResearchObservation)
                .where(StrategyResearchObservation.candidate_id == candidate_id)
                .order_by(StrategyResearchObservation.observed_at.desc())
                .limit(bounded_observation_limit)
            ).scalars()
        )
        backtest_runs = list(
            self.session.execute(
                select(StrategyResearchBacktestRun)
                .where(StrategyResearchBacktestRun.candidate_id == candidate_id)
                .order_by(StrategyResearchBacktestRun.reviewed_at.desc())
                .limit(bounded_backtest_limit)
            ).scalars()
        )
        observation_count = int(
            self.session.scalar(
                select(func.count(StrategyResearchObservation.id)).where(
                    StrategyResearchObservation.candidate_id == candidate_id
                )
            )
            or 0
        )
        resolved_observation_count = int(
            self.session.scalar(
                select(func.count(StrategyResearchObservation.id)).where(
                    StrategyResearchObservation.candidate_id == candidate_id,
                    StrategyResearchObservation.resolved_at.is_not(None),
                )
            )
            or 0
        )
        backtest_run_count = int(
            self.session.scalar(
                select(func.count(StrategyResearchBacktestRun.id)).where(
                    StrategyResearchBacktestRun.candidate_id == candidate_id
                )
            )
            or 0
        )
        accepted_backtest_run_count = int(
            self.session.scalar(
                select(func.count(StrategyResearchBacktestRun.id)).where(
                    StrategyResearchBacktestRun.candidate_id == candidate_id,
                    StrategyResearchBacktestRun.accepted.is_(True),
                )
            )
            or 0
        )
        latest = backtest_runs[0] if backtest_runs else None
        return {
            "candidate": research_candidate_response(candidate, observation_count),
            "latest_backtest": (
                research_backtest_run_response(latest) if latest is not None else None
            ),
            "backtest_runs": [research_backtest_run_response(run) for run in backtest_runs],
            "observations": observations,
            "evidence_summary": {
                "observation_count": observation_count,
                "resolved_observation_count": resolved_observation_count,
                "unresolved_observation_count": (
                    observation_count - resolved_observation_count
                ),
                "backtest_run_count": backtest_run_count,
                "accepted_backtest_run_count": accepted_backtest_run_count,
                "blocked_backtest_run_count": (
                    backtest_run_count - accepted_backtest_run_count
                ),
                "latest_backtest_hash": (
                    latest.evidence_hash
                    if latest is not None
                    else (candidate.normalized_payload or {}).get(
                        "latest_research_backtest_hash"
                    )
                ),
            },
        }

    def run_research_backtest(
        self,
        candidate_id: str,
        payload: StrategyResearchBacktestRequest,
        now: datetime | None = None,
    ) -> StrategyResearchBacktestResponse:
        reviewed_at = ensure_utc(now or datetime.now(UTC))
        candidate = self.session.get(StrategyResearchCandidate, candidate_id)
        if candidate is None:
            raise ValueError("Strategy research candidate not found")
        observations = list(
            self.session.execute(
                select(StrategyResearchObservation)
                .where(StrategyResearchObservation.candidate_id == candidate_id)
                .order_by(StrategyResearchObservation.observed_at.asc())
            ).scalars()
        )
        trades, skipped = resolved_research_trades(observations, payload.fee_rate)
        metrics = research_backtest_metrics(trades, payload, skipped)
        reasons = research_backtest_reasons(metrics, payload)
        accepted = not reasons
        decision = (
            StrategyResearchStatus.PAPER_ELIGIBLE
            if accepted
            else StrategyResearchStatus.BACKTEST_REQUIRED
        )
        candidate.status = decision
        candidate.trade_eligible = accepted
        candidate.eligibility_reason = (
            "prediction_research_backtest_passed_paper_eligible_not_live"
            if accepted
            else reasons[0]
        )
        candidate.required_evidence = {
            **dict(REQUIRED_RESEARCH_EVIDENCE),
            "latest_backtest": "passed" if accepted else "blocked",
            "live_execution": "blocked",
        }
        requirements = research_backtest_requirements(payload)
        report_payload = {
            "candidate_id": candidate.id,
            "strategy": candidate.strategy,
            "accepted": accepted,
            "decision": decision.value,
            "reasons": reasons,
            "metrics": metrics,
            "requirements": requirements,
            "reviewed_at": reviewed_at.isoformat(),
        }
        evidence_hash = research_hash(report_payload)
        backtest_run = StrategyResearchBacktestRun(
            candidate=candidate,
            strategy=candidate.strategy,
            accepted=accepted,
            decision=decision,
            reason=candidate.eligibility_reason,
            reasons=reasons,
            metrics=metrics,
            requirements=requirements,
            evidence_hash=evidence_hash,
            reviewed_at=reviewed_at,
        )
        self.session.add(backtest_run)
        self.session.flush()
        report_payload = {
            **report_payload,
            "backtest_run_id": backtest_run.id,
            "evidence_hash": evidence_hash,
        }
        candidate.normalized_payload = {
            **(candidate.normalized_payload or {}),
            "latest_research_backtest": report_payload,
            "latest_research_backtest_hash": evidence_hash,
            "latest_research_backtest_run_id": backtest_run.id,
        }
        candidate.evidence_hash = evidence_hash
        self._force_research_strategy_disabled(candidate)
        SystemEventRecorder(self.session).info(
            "strategy_research",
            "Strategy research backtest gate evaluated",
            {
                "candidate_id": candidate.id,
                "strategy": candidate.strategy,
                "accepted": accepted,
                "decision": decision.value,
                "reason": candidate.eligibility_reason,
            },
            occurred_at=reviewed_at,
        )
        self.session.flush()
        return StrategyResearchBacktestResponse(
            backtest_run_id=backtest_run.id,
            candidate_id=candidate.id,
            strategy=candidate.strategy,
            accepted=accepted,
            decision=decision,
            reason=candidate.eligibility_reason,
            reasons=reasons,
            metrics=metrics,
            requirements=requirements,
            evidence_hash=evidence_hash,
        )

    def _research_candidate_for_observation(
        self,
        payload: StrategyResearchObservationCreate,
        observed_at: datetime,
    ) -> StrategyResearchCandidate:
        if payload.candidate_id:
            candidate = self.session.get(StrategyResearchCandidate, payload.candidate_id)
            if candidate is None:
                raise ValueError("Strategy research candidate not found")
            return candidate
        if not payload.candidate_key:
            raise ValueError("candidate_id or candidate_key is required")
        candidate = self.session.execute(
            select(StrategyResearchCandidate).where(
                StrategyResearchCandidate.source == payload.source,
                StrategyResearchCandidate.candidate_key == payload.candidate_key,
            )
        ).scalar_one_or_none()
        if candidate is not None:
            return candidate
        if not payload.strategy or not payload.display_name or not payload.hypothesis:
            raise ValueError(
                "strategy, display_name, and hypothesis are required for a new candidate"
            )
        return self.register_research_candidate(
            StrategyResearchCandidateCreate(
                source=payload.source,
                candidate_key=payload.candidate_key,
                strategy=payload.strategy,
                display_name=payload.display_name,
                hypothesis=payload.hypothesis,
                status=research_status_for_observation(payload.observation_type),
                raw_payload=payload.raw_payload,
                normalized_payload=payload.observation_snapshot,
            ),
            now=observed_at,
        )

    def _existing_observation(
        self,
        candidate_id: str,
        payload: StrategyResearchObservationCreate,
        evidence_hash: str,
    ) -> StrategyResearchObservation | None:
        if payload.source_event_id:
            existing = self.session.execute(
                select(StrategyResearchObservation).where(
                    StrategyResearchObservation.candidate_id == candidate_id,
                    StrategyResearchObservation.source_event_id == payload.source_event_id,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
        return self.session.execute(
            select(StrategyResearchObservation).where(
                StrategyResearchObservation.candidate_id == candidate_id,
                StrategyResearchObservation.evidence_hash == evidence_hash,
            )
        ).scalar_one_or_none()

    def _force_research_strategy_disabled(self, candidate: StrategyResearchCandidate) -> None:
        config = self.get_or_create_config(candidate.strategy)
        config.is_enabled = False
        config.description = (
            config.description
            if config.version != "unregistered"
            else "Research candidate. Disabled until accepted evidence gates pass."
        )
        config.parameters = {
            **(config.parameters or {}),
            "research_candidate": True,
            "research_candidate_id": candidate.id,
            "research_source": candidate.source.value,
            "paper_eligible": (
                candidate.status == StrategyResearchStatus.PAPER_ELIGIBLE
                and candidate.trade_eligible
            ),
            "live_eligible": False,
            "trade_eligible": False,
            "eligibility_reason": candidate.eligibility_reason,
        }
        config.notes = candidate.eligibility_reason

    def _comparison_item(
        self,
        config: StrategyConfig,
        closed_trades: list[PaperTrade],
        open_trades: int,
    ) -> StrategyComparisonItem:
        realized_values = [trade.realized_pl or ZERO for trade in closed_trades]
        wins = [value for value in realized_values if value > 0]
        losses = [abs(value) for value in realized_values if value < 0]
        total = len(realized_values)
        win_count = len(wins)
        loss_count = len(losses)
        total_net_pl = sum(realized_values, ZERO)
        average_win = sum(wins, ZERO) / win_count if win_count else ZERO
        average_loss = sum(losses, ZERO) / loss_count if loss_count else ZERO
        win_rate = Decimal(win_count) / Decimal(total) if total else ZERO
        loss_rate = Decimal(loss_count) / Decimal(total) if total else ZERO
        expectancy = (win_rate * average_win) - (loss_rate * average_loss)

        return StrategyComparisonItem(
            strategy=config.strategy,
            display_name=config.display_name,
            is_enabled=config.is_enabled,
            allowed_regimes=list(config.allowed_regimes or []),
            risk_per_trade=config.risk_per_trade,
            minimum_reward_risk=config.minimum_reward_risk,
            max_open_positions=config.max_open_positions,
            open_trades=open_trades,
            closed_trades=total,
            wins=win_count,
            losses=loss_count,
            win_rate=win_rate,
            expectancy=expectancy,
            total_net_pl=total_net_pl,
        )


def strategy_config_snapshot(config: StrategyConfig) -> dict[str, object]:
    return {
        "strategy": config.strategy,
        "version": config.version,
        "is_enabled": config.is_enabled,
        "allowed_regimes": list(config.allowed_regimes or []),
        "risk_per_trade": str(config.risk_per_trade) if config.risk_per_trade else None,
        "minimum_reward_risk": (
            str(config.minimum_reward_risk) if config.minimum_reward_risk else None
        ),
        "max_open_positions": config.max_open_positions,
    }


def strategy_config_response(config: StrategyConfig) -> dict[str, object]:
    lifecycle = strategy_lifecycle_status(config.strategy)
    return {
        "id": config.id,
        "strategy": config.strategy,
        "version": config.version,
        "display_name": config.display_name,
        "description": config.description,
        "is_enabled": config.is_enabled,
        "allowed_regimes": list(config.allowed_regimes or []),
        "risk_per_trade": config.risk_per_trade,
        "minimum_reward_risk": config.minimum_reward_risk,
        "max_open_positions": config.max_open_positions,
        "parameters": dict(config.parameters or {}),
        "notes": config.notes,
        "lifecycle_status": lifecycle.value,
        "lifecycle_reason": strategy_lifecycle_reason(config.strategy),
        "enable_eligible": strategy_lifecycle_allows_enable(config.strategy),
    }


def research_status_for_candidate(
    source: StrategyResearchSource,
    requested_status: StrategyResearchStatus,
) -> StrategyResearchStatus:
    if source == StrategyResearchSource.MY_KRYPT_TRADER:
        if requested_status == StrategyResearchStatus.PAPER_ELIGIBLE:
            return StrategyResearchStatus.BACKTEST_REQUIRED
        return requested_status
    return requested_status


def research_status_for_observation(
    observation_type: StrategyResearchObservationType,
) -> StrategyResearchStatus:
    if observation_type in {
        StrategyResearchObservationType.WHALE_TRADE,
        StrategyResearchObservationType.MOMENTUM_CLUSTER,
        StrategyResearchObservationType.CRYPTO_15M,
    }:
        return StrategyResearchStatus.BACKTEST_REQUIRED
    return StrategyResearchStatus.RESEARCH_ONLY


def normalize_candidate_payload(payload: StrategyResearchCandidateCreate) -> dict[str, object]:
    return {
        "source": payload.source.value,
        "candidate_key": payload.candidate_key,
        "strategy": payload.strategy,
        "display_name": payload.display_name,
        "hypothesis": payload.hypothesis,
        "source_reference": payload.source_reference,
        **(payload.normalized_payload or {}),
    }


def normalize_observation_payload(payload: StrategyResearchObservationCreate) -> dict[str, object]:
    snapshot = {
        "source": payload.source.value,
        "observation_type": payload.observation_type.value,
        "source_event_id": payload.source_event_id,
        "symbol": payload.symbol.upper() if payload.symbol else None,
        "contract_ticker": payload.contract_ticker,
        "side": payload.side.upper() if payload.side else None,
        "confidence": str(payload.confidence) if payload.confidence is not None else None,
        "implied_probability": (
            str(payload.implied_probability) if payload.implied_probability is not None else None
        ),
        "expected_edge": str(payload.expected_edge) if payload.expected_edge is not None else None,
    }
    return {**snapshot, **(payload.observation_snapshot or {})}


def research_hash(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolved_research_trades(
    observations: list[StrategyResearchObservation],
    fee_rate: Decimal,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    trades: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for observation in observations:
        trade, reason = research_trade_from_observation(observation, fee_rate)
        if trade is not None:
            trades.append(trade)
            continue
        skipped.append(
            {
                "observation_id": observation.id,
                "source_event_id": observation.source_event_id,
                "reason": reason,
            }
        )
    return trades, skipped


def research_trade_from_observation(
    observation: StrategyResearchObservation,
    fee_rate: Decimal,
) -> tuple[dict[str, object] | None, str]:
    if observation.resolved_at is None:
        return None, "observation_unresolved"
    if observation.implied_probability is None:
        return None, "missing_entry_probability"
    side_raw = (observation.side or "").upper()
    if side_raw not in {PredictionMarketSide.YES.value, PredictionMarketSide.NO.value}:
        return None, "invalid_or_missing_side"

    side = PredictionMarketSide(side_raw)
    try:
        entry_price = validate_probability_price(
            Decimal(str(observation.implied_probability)),
            field_name="implied probability",
        )
        settlement_value = settlement_value_from_outcome(
            observation.outcome_snapshot or {},
            side,
        )
        fee = estimate_binary_contract_fee(TRADE_QUANTITY, entry_price, fee_rate)
        net_pl = calculate_binary_settlement_pl(
            side,
            TRADE_QUANTITY,
            entry_price,
            settlement_value,
            fee,
        )
    except (ArithmeticError, TypeError, ValueError):
        return None, "invalid_research_trade_payload"

    observed_at = ensure_utc(observation.observed_at)
    resolved_at = ensure_utc(observation.resolved_at)
    return (
        {
            "observation_id": observation.id,
            "source_event_id": observation.source_event_id,
            "symbol": observation.symbol,
            "contract_ticker": observation.contract_ticker,
            "side": side.value,
            "entry_price": entry_price,
            "settlement_value": settlement_value,
            "fee": fee,
            "net_pl": net_pl,
            "win": net_pl > ZERO,
            "observed_at": observed_at,
            "resolved_at": resolved_at,
            "trading_day": observed_at.date().isoformat(),
            "regime": research_regime_label(observation),
            "variant_key": research_variant_key(observation),
            "observation_snapshot": observation.observation_snapshot or {},
        },
        "resolved",
    )


def settlement_value_from_outcome(
    outcome_snapshot: dict[str, object],
    side: PredictionMarketSide,
) -> Decimal:
    for key in ("settlement_value", "final_settlement_value", "outcome_value"):
        if key in outcome_snapshot:
            return validate_probability_price(
                Decimal(str(outcome_snapshot[key])),
                field_name="settlement value",
            )

    outcome = (
        outcome_snapshot.get("winning_side")
        or outcome_snapshot.get("resolved_side")
        or outcome_snapshot.get("outcome")
        or outcome_snapshot.get("result")
    )
    if isinstance(outcome, bool):
        return ONE if outcome else ZERO
    normalized = str(outcome or "").strip().upper()
    if normalized in {"YES", "TRUE", "1"}:
        return ONE
    if normalized in {"NO", "FALSE", "0"}:
        return ZERO
    if normalized in {"WIN", "WON", "PROFIT"}:
        return ONE if side == PredictionMarketSide.YES else ZERO
    if normalized in {"LOSS", "LOST"}:
        return ZERO if side == PredictionMarketSide.YES else ONE
    raise ValueError("Outcome snapshot must include a binary settlement result")


def research_regime_label(observation: StrategyResearchObservation) -> str:
    snapshot = observation.observation_snapshot or {}
    for key in ("market_regime", "regime", "category", "market_category"):
        value = snapshot.get(key)
        if value:
            return str(value).strip().upper()
    return "UNKNOWN"


def research_variant_key(observation: StrategyResearchObservation) -> str:
    snapshot = observation.observation_snapshot or {}
    for key in ("variant_key", "parameter_set", "threshold_key", "signal_type", "mkt_table"):
        value = snapshot.get(key)
        if value:
            return str(value).strip().lower()
    return observation.observation_type.value.lower()


def research_backtest_metrics(
    trades: list[dict[str, object]],
    request: StrategyResearchBacktestRequest,
    skipped: list[dict[str, object]],
) -> dict[str, object]:
    in_sample, out_of_sample = split_research_samples(trades, request.oos_fraction)
    distribution = research_trade_distribution(trades)
    base_metrics = {
        "overall": research_metric_summary(trades),
        "in_sample": research_metric_summary(in_sample),
        "out_of_sample": research_metric_summary(out_of_sample),
    }
    multiple_testing = research_multiple_testing(trades, request, base_metrics)
    regime_breakdown = research_regime_breakdown(trades, request)
    return {
        "total_trades": len(trades),
        "skipped_observations": len(skipped),
        "skipped_sample": skipped[:10],
        **base_metrics,
        "active_trading_days": distribution["active_trading_days"],
        "max_single_day_trade_share": distribution["max_single_day_trade_share"],
        "max_single_day_trade_count": distribution["max_single_day_trade_count"],
        "walk_forward": research_walk_forward(trades, request),
        "regime_breakdown": regime_breakdown,
        "regime_diagnostics": research_regime_diagnostics(regime_breakdown, request),
        "multiple_testing": multiple_testing,
        "variant_diagnostics": research_variant_diagnostics(
            trades,
            multiple_testing,
            request,
        ),
        "statistical_significance": research_statistical_significance(
            base_metrics,
            multiple_testing,
            request,
        ),
    }


def research_backtest_reasons(
    metrics: dict[str, object],
    request: StrategyResearchBacktestRequest,
) -> list[str]:
    reasons: list[str] = []
    total_trades = int(metrics["total_trades"])
    oos = metrics["out_of_sample"]
    assert isinstance(oos, dict)
    walk_forward = metrics["walk_forward"]
    assert isinstance(walk_forward, dict)
    regime = metrics["regime_breakdown"]
    assert isinstance(regime, dict)
    multiple_testing = metrics["multiple_testing"]
    assert isinstance(multiple_testing, dict)
    significance = metrics["statistical_significance"]
    assert isinstance(significance, dict)

    if total_trades == 0:
        reasons.append("prediction_research_resolved_observations_missing")
    if total_trades < request.minimum_trades:
        reasons.append("prediction_research_minimum_trades_not_met")
    if int(oos["total_trades"]) < request.minimum_oos_trades:
        reasons.append("prediction_research_oos_trades_not_met")
    if int(oos["total_trades"]) > 0 and Decimal(str(oos["expectancy"])) <= ZERO:
        reasons.append("prediction_research_oos_expectancy_not_positive")
    if not profit_factor_meets_requirement(oos, request.minimum_oos_profit_factor):
        reasons.append("prediction_research_oos_profit_factor_below_minimum")
    if Decimal(str(oos["max_drawdown"])) > request.maximum_oos_drawdown:
        reasons.append("prediction_research_oos_drawdown_exceeds_limit")
    if int(metrics["active_trading_days"]) < request.minimum_active_days:
        reasons.append("prediction_research_active_days_not_met")
    if Decimal(str(metrics["max_single_day_trade_share"])) > request.maximum_single_day_share:
        reasons.append("prediction_research_trade_concentration_too_high")
    if (
        int(walk_forward["window_count"]) < request.minimum_walk_forward_windows
        or Decimal(str(walk_forward["pass_rate"])) < request.minimum_walk_forward_pass_rate
    ):
        reasons.append("prediction_research_walk_forward_not_passed")
    if request.require_known_regime and int(regime["missing_regime_count"]) > 0:
        reasons.append("prediction_research_regime_missing")
    if int(regime["eligible_group_count"]) < request.minimum_regime_groups:
        reasons.append("prediction_research_regime_coverage_not_met")
    if (
        int(regime["eligible_group_count"]) > 0
        and Decimal(str(regime["eligible_group_pass_rate"])) < request.minimum_regime_pass_rate
    ):
        reasons.append("prediction_research_regime_pass_rate_below_minimum")
    if int(multiple_testing["effective_tested_variant_count"]) > request.maximum_tested_variants:
        reasons.append("prediction_research_too_many_tested_variants")
    if not bool(multiple_testing["adjusted_profit_factor_passed"]):
        reasons.append("prediction_research_multiple_testing_adjusted_profit_factor_not_met")
    if not bool(significance["minimum_sample_passed"]):
        reasons.append("prediction_research_statistical_oos_trades_not_met")
    elif not bool(significance["passed"]):
        reasons.append("prediction_research_statistical_significance_not_met")
    return reasons


def profit_factor_meets_requirement(
    summary: dict[str, object],
    minimum_profit_factor: Decimal,
) -> bool:
    if int(summary["total_trades"]) == 0:
        return False
    if bool(summary["profit_factor_infinite"]):
        return True
    profit_factor = summary["profit_factor"]
    if profit_factor is None:
        return False
    return Decimal(str(profit_factor)) >= minimum_profit_factor


def research_backtest_requirements(
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    return {
        "minimum_trades": request.minimum_trades,
        "minimum_oos_trades": request.minimum_oos_trades,
        "minimum_oos_profit_factor": decimal_metric(request.minimum_oos_profit_factor),
        "maximum_oos_drawdown": decimal_money(request.maximum_oos_drawdown),
        "minimum_active_days": request.minimum_active_days,
        "maximum_single_day_share": decimal_metric(request.maximum_single_day_share),
        "oos_fraction": decimal_metric(request.oos_fraction),
        "minimum_walk_forward_windows": request.minimum_walk_forward_windows,
        "minimum_walk_forward_pass_rate": decimal_metric(
            request.minimum_walk_forward_pass_rate
        ),
        "require_known_regime": request.require_known_regime,
        "minimum_regime_groups": request.minimum_regime_groups,
        "minimum_regime_trades": request.minimum_regime_trades,
        "minimum_regime_pass_rate": decimal_metric(request.minimum_regime_pass_rate),
        "tested_variant_count": request.tested_variant_count,
        "maximum_tested_variants": request.maximum_tested_variants,
        "multiple_testing_profit_factor_step": decimal_metric(
            request.multiple_testing_profit_factor_step
        ),
        "maximum_multiple_testing_profit_factor_penalty": decimal_metric(
            request.maximum_multiple_testing_profit_factor_penalty
        ),
        "minimum_statistical_oos_trades": request.minimum_statistical_oos_trades,
        "statistical_null_win_probability": decimal_metric(
            request.statistical_null_win_probability
        ),
        "maximum_statistical_p_value": decimal_metric(request.maximum_statistical_p_value),
        "fee_rate": decimal_metric(request.fee_rate),
    }


def split_research_samples(
    trades: list[dict[str, object]],
    oos_fraction: Decimal,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if not trades:
        return [], []
    oos_count = int(
        (Decimal(len(trades)) * oos_fraction).to_integral_value(rounding=ROUND_CEILING)
    )
    oos_count = min(len(trades), max(1, oos_count))
    split_at = len(trades) - oos_count
    return trades[:split_at], trades[split_at:]


def research_metric_summary(trades: list[dict[str, object]]) -> dict[str, object]:
    net_values = [Decimal(str(trade["net_pl"])) for trade in trades]
    wins = [value for value in net_values if value > ZERO]
    losses = [abs(value) for value in net_values if value < ZERO]
    total = len(net_values)
    gross_profit = sum(wins, ZERO)
    gross_loss = sum(losses, ZERO)
    net_pl = sum(net_values, ZERO)
    win_rate = Decimal(len(wins)) / Decimal(total) if total else ZERO
    expectancy = net_pl / Decimal(total) if total else ZERO
    profit_factor = research_profit_factor(gross_profit, gross_loss)
    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "net_pl": decimal_money(net_pl),
        "gross_profit": decimal_money(gross_profit),
        "gross_loss": decimal_money(gross_loss),
        "expectancy": decimal_money(expectancy),
        "win_rate": decimal_metric(win_rate),
        "profit_factor": None if profit_factor is None else decimal_metric(profit_factor),
        "profit_factor_infinite": profit_factor is None and gross_profit > ZERO,
        "max_drawdown": decimal_money(research_max_drawdown(net_values)),
    }


def research_profit_factor(gross_profit: Decimal, gross_loss: Decimal) -> Decimal | None:
    if gross_loss == ZERO:
        return None if gross_profit > ZERO else ZERO
    return gross_profit / gross_loss


def research_max_drawdown(values: list[Decimal]) -> Decimal:
    peak = ZERO
    equity = ZERO
    max_drawdown = ZERO
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def research_trade_distribution(trades: list[dict[str, object]]) -> dict[str, object]:
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        counts[str(trade["trading_day"])] += 1
    max_count = max(counts.values(), default=0)
    share = Decimal(max_count) / Decimal(len(trades)) if trades else ZERO
    return {
        "active_trading_days": len(counts),
        "max_single_day_trade_count": max_count,
        "max_single_day_trade_share": decimal_metric(share),
    }


def research_regime_breakdown(
    trades: list[dict[str, object]],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    missing = 0
    for trade in trades:
        regime = str(trade.get("regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        if regime == "UNKNOWN":
            missing += 1
        grouped[regime].append(trade)

    groups: list[dict[str, object]] = []
    eligible_count = 0
    passed_count = 0
    for regime, regime_trades in sorted(grouped.items()):
        summary = research_metric_summary(regime_trades)
        eligible = (
            regime != "UNKNOWN"
            and int(summary["total_trades"]) >= request.minimum_regime_trades
        )
        passed = (
            eligible
            and Decimal(str(summary["expectancy"])) > ZERO
            and profit_factor_meets_requirement(summary, request.minimum_oos_profit_factor)
        )
        if eligible:
            eligible_count += 1
        if passed:
            passed_count += 1
        groups.append(
            {
                "regime": regime,
                "eligible": eligible,
                "passed": passed,
                "summary": summary,
            }
        )

    pass_rate = Decimal(passed_count) / Decimal(eligible_count) if eligible_count else ZERO
    return {
        "regime_count": len(grouped),
        "missing_regime_count": missing,
        "eligible_group_count": eligible_count,
        "passed_group_count": passed_count,
        "eligible_group_pass_rate": decimal_metric(pass_rate),
        "minimum_group_trades": request.minimum_regime_trades,
        "groups": groups,
    }


def research_regime_diagnostics(
    regime_breakdown: dict[str, object],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    groups = regime_breakdown.get("groups")
    if not isinstance(groups, list):
        groups = []

    group_diagnostics = [
        research_regime_group_diagnostic(group, request) for group in groups
    ]
    thin_groups = [
        group for group in group_diagnostics if group["status"] == "THIN_SAMPLE"
    ]
    weak_groups = [
        group
        for group in group_diagnostics
        if str(group["status"]).startswith("FAIL_")
    ]
    unknown_count = int(regime_breakdown.get("missing_regime_count") or 0)
    eligible_count = int(regime_breakdown.get("eligible_group_count") or 0)
    pass_rate = Decimal(str(regime_breakdown.get("eligible_group_pass_rate") or "0"))
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if request.require_known_regime and unknown_count > 0:
        blocking_reasons.append("unknown_regime_rows")
    elif unknown_count > 0:
        warnings.append("unknown_regime_rows")
    if eligible_count < request.minimum_regime_groups:
        blocking_reasons.append("insufficient_regime_coverage")
    if eligible_count > 0 and pass_rate < request.minimum_regime_pass_rate:
        blocking_reasons.append("regime_pass_rate_below_minimum")
    if thin_groups:
        warnings.append("thin_regime_groups")
    if weak_groups:
        warnings.append("weak_regime_groups")

    if blocking_reasons:
        status = "BLOCKED"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "unknown_regime_rows": unknown_count,
        "thin_group_count": len(thin_groups),
        "weak_group_count": len(weak_groups),
        "passed_group_count": int(regime_breakdown.get("passed_group_count") or 0),
        "eligible_group_count": eligible_count,
        "minimum_group_trades": request.minimum_regime_trades,
        "minimum_group_pass_rate": decimal_metric(request.minimum_regime_pass_rate),
        "group_diagnostics": group_diagnostics,
        "next_action": research_regime_diagnostics_next_action(
            blocking_reasons,
            warnings,
        ),
    }


def research_regime_group_diagnostic(
    group: object,
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    if not isinstance(group, dict):
        return {
            "regime": "UNKNOWN",
            "status": "MALFORMED_GROUP",
            "total_trades": 0,
            "expectancy": decimal_money(ZERO),
            "profit_factor": None,
            "profit_factor_infinite": False,
            "max_drawdown": decimal_money(ZERO),
            "reason": "Malformed regime group.",
        }
    regime = str(group.get("regime") or "UNKNOWN")
    summary = group.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    total_trades = int(summary.get("total_trades") or 0)
    expectancy = Decimal(str(summary.get("expectancy") or "0"))
    eligible = bool(group.get("eligible"))
    passed = bool(group.get("passed"))
    profit_factor_ok = profit_factor_meets_requirement(
        {
            "total_trades": total_trades,
            "profit_factor": summary.get("profit_factor"),
            "profit_factor_infinite": bool(summary.get("profit_factor_infinite")),
        },
        request.minimum_oos_profit_factor,
    )

    if regime == "UNKNOWN":
        status = "UNKNOWN_REGIME"
        reason = "Rows are missing market regime/category labels."
    elif not eligible:
        status = "THIN_SAMPLE"
        reason = f"Needs at least {request.minimum_regime_trades} trades in this group."
    elif passed:
        status = "PASS"
        reason = "Group has positive expectancy and passes profit-factor threshold."
    elif expectancy <= ZERO:
        status = "FAIL_EXPECTANCY"
        reason = "Group expectancy is not positive."
    elif not profit_factor_ok:
        status = "FAIL_PROFIT_FACTOR"
        reason = "Group profit factor is below the required threshold."
    else:
        status = "FAIL"
        reason = "Group did not satisfy the regime gate."

    return {
        "regime": regime,
        "status": status,
        "total_trades": total_trades,
        "expectancy": summary.get("expectancy", decimal_money(ZERO)),
        "profit_factor": summary.get("profit_factor"),
        "profit_factor_infinite": bool(summary.get("profit_factor_infinite", False)),
        "max_drawdown": summary.get("max_drawdown", decimal_money(ZERO)),
        "reason": reason,
    }


def research_regime_diagnostics_next_action(
    blocking_reasons: list[str],
    warnings: list[str],
) -> str:
    if "unknown_regime_rows" in blocking_reasons:
        return "Label MKT observations with regime/category before trusting the gate."
    if "insufficient_regime_coverage" in blocking_reasons:
        return "Collect enough resolved observations across more regime/category groups."
    if "regime_pass_rate_below_minimum" in blocking_reasons:
        return "Reject or revise the candidate; too many eligible regimes fail."
    if "weak_regime_groups" in warnings:
        return "Treat weak groups as exclusion candidates before paper-demo replay."
    if "thin_regime_groups" in warnings:
        return "Collect more observations in thin regime/category groups."
    if "unknown_regime_rows" in warnings:
        return "Improve regime/category labeling before expanding paper-demo use."
    return "Regime diagnostics are clean; continue with other evidence gates."


def research_multiple_testing(
    trades: list[dict[str, object]],
    request: StrategyResearchBacktestRequest,
    metrics: dict[str, object],
) -> dict[str, object]:
    variants = sorted(
        {
            str(trade.get("variant_key") or "base").strip().lower()
            for trade in trades
            if str(trade.get("variant_key") or "").strip()
        }
    )
    actual_variant_count = max(1, len(variants)) if trades else 0
    effective_count = max(request.tested_variant_count, actual_variant_count)
    penalty = Decimal(max(0, effective_count - 1)) * request.multiple_testing_profit_factor_step
    penalty = min(penalty, request.maximum_multiple_testing_profit_factor_penalty)
    adjusted_minimum = request.minimum_oos_profit_factor + penalty
    oos = metrics["out_of_sample"]
    assert isinstance(oos, dict)
    passed = profit_factor_meets_requirement(oos, adjusted_minimum)
    return {
        "actual_variant_count": actual_variant_count,
        "reported_tested_variant_count": request.tested_variant_count,
        "effective_tested_variant_count": effective_count,
        "maximum_tested_variants": request.maximum_tested_variants,
        "profit_factor_penalty": decimal_metric(penalty),
        "adjusted_minimum_oos_profit_factor": decimal_metric(adjusted_minimum),
        "adjusted_profit_factor_passed": passed,
        "variants": variants[:25],
    }


def research_variant_diagnostics(
    trades: list[dict[str, object]],
    multiple_testing: dict[str, object],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        variant = str(trade.get("variant_key") or "base").strip().lower() or "base"
        grouped[variant].append(trade)

    group_diagnostics = [
        research_variant_group_diagnostic(variant, variant_trades, request)
        for variant, variant_trades in sorted(grouped.items())
    ]
    thin_groups = [
        group for group in group_diagnostics if group["status"] == "THIN_SAMPLE"
    ]
    weak_groups = [
        group
        for group in group_diagnostics
        if str(group["status"]).startswith("FAIL_")
    ]
    max_variant_trades = max((len(group) for group in grouped.values()), default=0)
    dominant_variant_share = (
        Decimal(max_variant_trades) / Decimal(len(trades)) if trades else ZERO
    )
    effective_count = int(multiple_testing.get("effective_tested_variant_count") or 0)
    maximum_variants = int(multiple_testing.get("maximum_tested_variants") or 0)
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if effective_count > request.maximum_tested_variants:
        blocking_reasons.append("too_many_tested_variants")
    if not bool(multiple_testing.get("adjusted_profit_factor_passed", False)):
        blocking_reasons.append("adjusted_profit_factor_not_met")
    if thin_groups:
        warnings.append("thin_variant_groups")
    if weak_groups:
        warnings.append("weak_variant_groups")
    if dominant_variant_share > Decimal("0.75") and len(grouped) > 1:
        warnings.append("variant_concentration_high")

    if blocking_reasons:
        status = "BLOCKED"
    elif warnings:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "actual_variant_count": int(multiple_testing.get("actual_variant_count") or 0),
        "effective_tested_variant_count": effective_count,
        "maximum_tested_variants": maximum_variants,
        "adjusted_profit_factor_passed": bool(
            multiple_testing.get("adjusted_profit_factor_passed", False)
        ),
        "adjusted_minimum_oos_profit_factor": multiple_testing.get(
            "adjusted_minimum_oos_profit_factor"
        ),
        "thin_group_count": len(thin_groups),
        "weak_group_count": len(weak_groups),
        "dominant_variant_trade_share": decimal_metric(dominant_variant_share),
        "minimum_variant_trades": request.minimum_regime_trades,
        "group_diagnostics": group_diagnostics[:25],
        "next_action": research_variant_diagnostics_next_action(
            blocking_reasons,
            warnings,
        ),
    }


def research_variant_group_diagnostic(
    variant: str,
    trades: list[dict[str, object]],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    summary = research_metric_summary(trades)
    total_trades = int(summary["total_trades"])
    expectancy = Decimal(str(summary["expectancy"]))
    profit_factor_ok = profit_factor_meets_requirement(
        summary,
        request.minimum_oos_profit_factor,
    )

    if total_trades < request.minimum_regime_trades:
        status = "THIN_SAMPLE"
        reason = f"Needs at least {request.minimum_regime_trades} trades in this variant."
    elif expectancy <= ZERO:
        status = "FAIL_EXPECTANCY"
        reason = "Variant expectancy is not positive."
    elif not profit_factor_ok:
        status = "FAIL_PROFIT_FACTOR"
        reason = "Variant profit factor is below the required threshold."
    else:
        status = "PASS"
        reason = "Variant has positive expectancy and passes profit-factor threshold."

    return {
        "variant": variant,
        "status": status,
        "total_trades": total_trades,
        "expectancy": summary["expectancy"],
        "profit_factor": summary["profit_factor"],
        "profit_factor_infinite": bool(summary["profit_factor_infinite"]),
        "max_drawdown": summary["max_drawdown"],
        "reason": reason,
    }


def research_variant_diagnostics_next_action(
    blocking_reasons: list[str],
    warnings: list[str],
) -> str:
    if "too_many_tested_variants" in blocking_reasons:
        return "Reduce tested variants or collect new evidence before paper-demo use."
    if "adjusted_profit_factor_not_met" in blocking_reasons:
        return "Reject or revise the candidate; edge does not survive variant adjustment."
    if "weak_variant_groups" in warnings:
        return "Review weak variants before replay; avoid cherry-picking only winners."
    if "thin_variant_groups" in warnings:
        return "Collect more observations per variant before trusting variant behavior."
    if "variant_concentration_high" in warnings:
        return "Balance evidence across variants or narrow the candidate definition."
    return "Variant diagnostics are clean; continue with other evidence gates."


def research_statistical_significance(
    metrics: dict[str, object],
    multiple_testing: dict[str, object],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    oos = metrics["out_of_sample"]
    assert isinstance(oos, dict)
    oos_trades = int(oos["total_trades"])
    wins = int(oos["wins"])
    raw_p_value = binomial_survival_probability(
        n=oos_trades,
        k=wins,
        probability=request.statistical_null_win_probability,
    )
    bonferroni_tests = max(1, int(multiple_testing["effective_tested_variant_count"]))
    adjusted_p_value = min(ONE, raw_p_value * Decimal(bonferroni_tests))
    minimum_sample_passed = oos_trades >= request.minimum_statistical_oos_trades
    p_value_passed = adjusted_p_value <= request.maximum_statistical_p_value
    return {
        "method": "one_sided_binomial_survival_bonferroni",
        "sample": "out_of_sample",
        "oos_trades": oos_trades,
        "wins": wins,
        "losses": int(oos["losses"]),
        "observed_win_rate": oos["win_rate"],
        "null_win_probability": decimal_metric(request.statistical_null_win_probability),
        "raw_p_value": decimal_probability(raw_p_value),
        "bonferroni_test_count": bonferroni_tests,
        "adjusted_p_value": decimal_probability(adjusted_p_value),
        "maximum_p_value": decimal_metric(request.maximum_statistical_p_value),
        "minimum_oos_trades": request.minimum_statistical_oos_trades,
        "minimum_sample_passed": minimum_sample_passed,
        "p_value_passed": p_value_passed,
        "passed": minimum_sample_passed and p_value_passed,
    }


def binomial_survival_probability(
    *,
    n: int,
    k: int,
    probability: Decimal,
) -> Decimal:
    if n <= 0 or k <= 0:
        return ONE
    if k > n:
        return ZERO
    p = float(probability)
    logs = [
        (
            lgamma(n + 1)
            - lgamma(successes + 1)
            - lgamma(n - successes + 1)
            + successes * log(p)
            + (n - successes) * log1p(-p)
        )
        for successes in range(k, n + 1)
    ]
    maximum_log = max(logs)
    value = exp(maximum_log) * sum(exp(term - maximum_log) for term in logs)
    bounded = min(1.0, max(0.0, value))
    return Decimal(str(bounded))


def research_walk_forward(
    trades: list[dict[str, object]],
    request: StrategyResearchBacktestRequest,
) -> dict[str, object]:
    if not trades:
        return {
            "window_count": 0,
            "passed_windows": 0,
            "pass_rate": decimal_metric(ZERO),
            "windows": [],
        }

    window_count = min(request.minimum_walk_forward_windows, len(trades))
    base_size = len(trades) // window_count
    remainder = len(trades) % window_count
    start = 0
    windows: list[dict[str, object]] = []
    passed_windows = 0
    for index in range(window_count):
        size = base_size + (1 if index < remainder else 0)
        end = start + size
        window_trades = trades[start:end]
        summary = research_metric_summary(window_trades)
        passed = (
            int(summary["total_trades"]) > 0
            and Decimal(str(summary["expectancy"])) > ZERO
            and profit_factor_meets_requirement(summary, request.minimum_oos_profit_factor)
        )
        if passed:
            passed_windows += 1
        windows.append(
            {
                "index": index + 1,
                "start_observed_at": (
                    ensure_utc(window_trades[0]["observed_at"]).isoformat()
                    if window_trades
                    else None
                ),
                "end_observed_at": (
                    ensure_utc(window_trades[-1]["observed_at"]).isoformat()
                    if window_trades
                    else None
                ),
                "passed": passed,
                "summary": summary,
            }
        )
        start = end

    pass_rate = Decimal(passed_windows) / Decimal(window_count) if window_count else ZERO
    return {
        "window_count": window_count,
        "passed_windows": passed_windows,
        "pass_rate": decimal_metric(pass_rate),
        "windows": windows,
    }


def decimal_metric(value: Decimal) -> str:
    return str(value.quantize(METRIC_QUANTUM))


def decimal_money(value: Decimal) -> str:
    return str(value.quantize(MONEY_QUANTUM))


def decimal_probability(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001")))


def research_candidate_response(
    candidate: StrategyResearchCandidate,
    observation_count: int,
) -> dict[str, object]:
    return {
        "id": candidate.id,
        "source": candidate.source,
        "candidate_key": candidate.candidate_key,
        "strategy": candidate.strategy,
        "display_name": candidate.display_name,
        "hypothesis": candidate.hypothesis,
        "status": candidate.status,
        "trade_eligible": candidate.trade_eligible,
        "eligibility_reason": candidate.eligibility_reason,
        "required_evidence": candidate.required_evidence,
        "evidence_hash": candidate.evidence_hash,
        "source_reference": candidate.source_reference,
        "raw_payload": candidate.raw_payload,
        "normalized_payload": candidate.normalized_payload,
        "first_seen_at": candidate.first_seen_at,
        "last_seen_at": candidate.last_seen_at,
        "observation_count": observation_count,
    }


def research_readiness_item(
    candidate: StrategyResearchCandidate,
    *,
    observation_count: int,
    resolved_observation_count: int,
    latest_run: StrategyResearchBacktestRun | None,
) -> dict[str, object]:
    metrics = latest_run.metrics if latest_run is not None else {}
    oos = metrics.get("out_of_sample") if isinstance(metrics, dict) else {}
    if not isinstance(oos, dict):
        oos = {}
    regime = metrics.get("regime_breakdown") if isinstance(metrics, dict) else {}
    if not isinstance(regime, dict):
        regime = {}
    regime_diagnostics = (
        metrics.get("regime_diagnostics") if isinstance(metrics, dict) else {}
    )
    if not isinstance(regime_diagnostics, dict):
        regime_diagnostics = {}
    variants = metrics.get("multiple_testing") if isinstance(metrics, dict) else {}
    if not isinstance(variants, dict):
        variants = {}
    variant_diagnostics = (
        metrics.get("variant_diagnostics") if isinstance(metrics, dict) else {}
    )
    if not isinstance(variant_diagnostics, dict):
        variant_diagnostics = {}
    significance = metrics.get("statistical_significance") if isinstance(metrics, dict) else {}
    if not isinstance(significance, dict):
        significance = {}

    readiness_state = research_readiness_state(
        candidate,
        latest_run,
        resolved_observation_count,
    )
    first_blocker = None
    if latest_run is not None and latest_run.reasons:
        first_blocker = str(latest_run.reasons[0])

    return {
        "_sort_priority": research_readiness_priority(readiness_state),
        "rank": 0,
        "candidate_id": candidate.id,
        "candidate_key": candidate.candidate_key,
        "strategy": candidate.strategy,
        "display_name": candidate.display_name,
        "status": candidate.status,
        "trade_eligible": candidate.trade_eligible,
        "readiness_state": readiness_state,
        "next_action": research_readiness_next_action(
            readiness_state,
            first_blocker,
            resolved_observation_count,
        ),
        "observation_count": observation_count,
        "resolved_observation_count": resolved_observation_count,
        "latest_backtest_run_id": latest_run.id if latest_run is not None else None,
        "latest_backtest_accepted": latest_run.accepted if latest_run is not None else None,
        "latest_backtest_reviewed_at": (
            latest_run.reviewed_at if latest_run is not None else None
        ),
        "first_blocker": first_blocker,
        "total_trades": metrics.get("total_trades") if isinstance(metrics, dict) else None,
        "oos_trades": oos.get("total_trades"),
        "oos_expectancy": oos.get("expectancy"),
        "oos_profit_factor": oos.get("profit_factor"),
        "oos_profit_factor_infinite": bool(oos.get("profit_factor_infinite", False)),
        "oos_max_drawdown": oos.get("max_drawdown"),
        "regime_coverage": research_regime_coverage_label(regime),
        "regime_diagnostics": research_regime_diagnostics_label(regime_diagnostics),
        "variant_pressure": research_variant_pressure_label(variants),
        "variant_diagnostics": research_variant_diagnostics_label(variant_diagnostics),
        "statistical_significance": research_significance_label(significance),
        "evidence_hash": (
            latest_run.evidence_hash if latest_run is not None else candidate.evidence_hash
        ),
    }


def research_readiness_state(
    candidate: StrategyResearchCandidate,
    latest_run: StrategyResearchBacktestRun | None,
    resolved_observation_count: int,
) -> str:
    if latest_run is not None and latest_run.accepted and candidate.trade_eligible:
        return "PAPER_RESEARCH_ELIGIBLE"
    if latest_run is not None and not latest_run.accepted:
        return "GATE_BLOCKED"
    if resolved_observation_count > 0:
        return "READY_FOR_RESEARCH_GATE"
    return "NEEDS_RESOLVED_OBSERVATIONS"


def research_readiness_priority(readiness_state: str) -> int:
    priorities = {
        "PAPER_RESEARCH_ELIGIBLE": 0,
        "GATE_BLOCKED": 1,
        "READY_FOR_RESEARCH_GATE": 2,
        "NEEDS_RESOLVED_OBSERVATIONS": 3,
    }
    return priorities.get(readiness_state, 9)


def research_readiness_next_action(
    readiness_state: str,
    first_blocker: str | None,
    resolved_observation_count: int,
) -> str:
    if readiness_state == "PAPER_RESEARCH_ELIGIBLE":
        return "Paper-demo only; keep live disabled and collect forward evidence."
    if readiness_state == "GATE_BLOCKED":
        blocker = (first_blocker or "research gate blocked").replace("_", " ")
        return f"Fix blocker: {blocker}."
    if readiness_state == "READY_FOR_RESEARCH_GATE":
        return f"Run research gate on {resolved_observation_count} resolved observations."
    return "Import or resolve observations before backtesting."


def research_regime_coverage_label(regime: dict[str, object]) -> str | None:
    if not regime:
        return None
    return (
        f"{regime.get('passed_group_count', 0)}/"
        f"{regime.get('eligible_group_count', 0)} pass, "
        f"{regime.get('missing_regime_count', 0)} unknown"
    )


def research_regime_diagnostics_label(diagnostics: dict[str, object]) -> str | None:
    if not diagnostics:
        return None
    return (
        f"{diagnostics.get('status', 'UNKNOWN')}: "
        f"{diagnostics.get('thin_group_count', 0)} thin, "
        f"{diagnostics.get('weak_group_count', 0)} weak, "
        f"{diagnostics.get('unknown_regime_rows', 0)} unknown"
    )


def research_variant_pressure_label(variants: dict[str, object]) -> str | None:
    if not variants:
        return None
    return (
        f"{variants.get('effective_tested_variant_count', 0)}/"
        f"{variants.get('maximum_tested_variants', 0)} variants"
    )


def research_variant_diagnostics_label(diagnostics: dict[str, object]) -> str | None:
    if not diagnostics:
        return None
    return (
        f"{diagnostics.get('status', 'UNKNOWN')}: "
        f"{diagnostics.get('effective_tested_variant_count', 0)}/"
        f"{diagnostics.get('maximum_tested_variants', 0)} tested, "
        f"{diagnostics.get('thin_group_count', 0)} thin, "
        f"{diagnostics.get('weak_group_count', 0)} weak"
    )


def research_significance_label(significance: dict[str, object]) -> str | None:
    if not significance:
        return None
    state = "pass" if significance.get("passed") else "block"
    return (
        f"{state}, p={significance.get('adjusted_p_value', '--')} "
        f"({significance.get('wins', 0)}/{significance.get('oos_trades', 0)} OOS)"
    )


def research_readiness_summary(items: list[dict[str, object]]) -> dict[str, object]:
    states: dict[str, int] = defaultdict(int)
    for item in items:
        states[str(item["readiness_state"])] += 1
    return {
        "paper_research_eligible": states["PAPER_RESEARCH_ELIGIBLE"],
        "gate_blocked": states["GATE_BLOCKED"],
        "ready_for_research_gate": states["READY_FOR_RESEARCH_GATE"],
        "needs_resolved_observations": states["NEEDS_RESOLVED_OBSERVATIONS"],
        "top_next_action": (
            str(items[0]["next_action"]) if items else "Record research candidates first."
        ),
    }


def research_backtest_run_response(
    run: StrategyResearchBacktestRun,
) -> dict[str, object]:
    return {
        "id": run.id,
        "candidate_id": run.candidate_id,
        "strategy": run.strategy,
        "accepted": run.accepted,
        "decision": run.decision,
        "reason": run.reason,
        "reasons": run.reasons,
        "metrics": run.metrics,
        "requirements": run.requirements,
        "evidence_hash": run.evidence_hash,
        "reviewed_at": run.reviewed_at,
    }
