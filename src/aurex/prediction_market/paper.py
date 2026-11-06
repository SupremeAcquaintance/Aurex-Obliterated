import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.db.base import utc_now
from aurex.db.models import (
    PredictionContract,
    PredictionEvidenceEvent,
    PredictionFill,
    PredictionMarket,
    PredictionOrder,
    PredictionOrderIntent,
    PredictionPosition,
    PredictionReconciliationReport,
    PredictionSettlement,
    StrategyResearchBacktestRun,
    StrategyResearchCandidate,
)
from aurex.domain.enums import (
    PredictionMarketEvidenceKind,
    PredictionMarketOrderAction,
    PredictionMarketOrderStatus,
    PredictionMarketOrderType,
    PredictionMarketPositionStatus,
    PredictionMarketSide,
    PredictionMarketStatus,
    PredictionMarketVenue,
    ReconciliationStatus,
    StrategyResearchSource,
    StrategyResearchStatus,
)
from aurex.prediction_market.calculations import (
    MONEY_QUANTUM,
    calculate_average_fill_price,
    calculate_binary_entry_cost,
    calculate_binary_gross_payout,
    calculate_binary_notional,
    calculate_binary_settlement_pl,
    estimate_binary_contract_fee,
    validate_positive_quantity,
    validate_probability_price,
)


@dataclass(frozen=True)
class PredictionContractSnapshot:
    venue: PredictionMarketVenue
    event_ticker: str
    market_title: str
    contract_ticker: str
    contract_title: str
    category: str | None
    status: PredictionMarketStatus
    yes_bid_price: Decimal | None
    yes_ask_price: Decimal | None
    no_bid_price: Decimal | None
    no_ask_price: Decimal | None
    closes_at: datetime | None
    expiration_at: datetime | None
    raw_payload: dict
    settlement_value: Decimal | None = None


@dataclass(frozen=True)
class PredictionRiskLimits:
    max_order_cost: Decimal = Decimal("50")
    max_contract_exposure: Decimal = Decimal("50")
    max_open_positions: int = 25
    max_quote_age_seconds: int | None = None
    max_spread: Decimal | None = None
    max_latency_ms: int | None = None
    max_slippage: Decimal | None = None


@dataclass(frozen=True)
class PredictionOrderRequest:
    contract_id: str
    strategy: str
    side: PredictionMarketSide
    quantity: Decimal
    limit_price: Decimal
    idempotency_key: str
    action: PredictionMarketOrderAction = PredictionMarketOrderAction.BUY
    order_type: PredictionMarketOrderType = PredictionMarketOrderType.LIMIT
    expected_edge: Decimal | None = None
    confidence: Decimal | None = None
    account_id: str | None = None
    signal_id: str | None = None
    risk_decision_id: str | None = None
    broker_connection_id: str | None = None
    expires_at: datetime | None = None
    risk_limits: PredictionRiskLimits = PredictionRiskLimits()


@dataclass(frozen=True)
class PredictionFillModel:
    available_quantity: Decimal
    latency_ms: int
    execution_price: Decimal | None = None
    raw_payload: dict | None = None


@dataclass(frozen=True)
class PredictionOrderSubmission:
    order: PredictionOrder
    fill: PredictionFill | None
    position: PredictionPosition | None


class PredictionMarketPaperEngine:
    """Paper-only binary contract simulator.

    This engine borrows the useful MKT order-lifecycle ideas while staying inside Aurex's
    evidence-first boundary. It never submits live orders.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_contract_snapshot(
        self,
        snapshot: PredictionContractSnapshot,
        *,
        now: datetime | None = None,
    ) -> PredictionContract:
        observed_at = ensure_utc(now or utc_now())
        validate_optional_price(snapshot.yes_bid_price, "yes_bid_price")
        validate_optional_price(snapshot.yes_ask_price, "yes_ask_price")
        validate_optional_price(snapshot.no_bid_price, "no_bid_price")
        validate_optional_price(snapshot.no_ask_price, "no_ask_price")
        validate_optional_price(snapshot.settlement_value, "settlement_value")

        market = self.session.execute(
            select(PredictionMarket).where(
                PredictionMarket.venue == snapshot.venue,
                PredictionMarket.event_ticker == snapshot.event_ticker,
            )
        ).scalar_one_or_none()
        if market is None:
            market = PredictionMarket(
                venue=snapshot.venue,
                event_ticker=snapshot.event_ticker,
                title=snapshot.market_title,
                category=snapshot.category,
                status=snapshot.status,
                closes_at=snapshot.closes_at,
                raw_payload=snapshot.raw_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            self.session.add(market)
        else:
            market.title = snapshot.market_title
            market.category = snapshot.category
            market.status = snapshot.status
            market.closes_at = snapshot.closes_at
            market.raw_payload = snapshot.raw_payload
            market.last_seen_at = observed_at
        self.session.flush()

        contract = self.session.execute(
            select(PredictionContract).where(
                PredictionContract.venue == snapshot.venue,
                PredictionContract.contract_ticker == snapshot.contract_ticker,
            )
        ).scalar_one_or_none()
        if contract is None:
            contract = PredictionContract(
                market=market,
                venue=snapshot.venue,
                contract_ticker=snapshot.contract_ticker,
                title=snapshot.contract_title,
                status=snapshot.status,
                yes_bid_price=snapshot.yes_bid_price,
                yes_ask_price=snapshot.yes_ask_price,
                no_bid_price=snapshot.no_bid_price,
                no_ask_price=snapshot.no_ask_price,
                expiration_at=snapshot.expiration_at,
                settlement_value=snapshot.settlement_value,
                raw_payload=snapshot.raw_payload,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
            )
            self.session.add(contract)
        else:
            contract.market = market
            contract.title = snapshot.contract_title
            contract.status = snapshot.status
            contract.yes_bid_price = snapshot.yes_bid_price
            contract.yes_ask_price = snapshot.yes_ask_price
            contract.no_bid_price = snapshot.no_bid_price
            contract.no_ask_price = snapshot.no_ask_price
            contract.expiration_at = snapshot.expiration_at
            if snapshot.settlement_value is not None:
                contract.settlement_value = snapshot.settlement_value
            contract.raw_payload = snapshot.raw_payload
            contract.last_seen_at = observed_at
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.MARKET_SNAPSHOT,
            "prediction_contract",
            contract.id,
            {
                "venue": contract.venue.value,
                "event_ticker": market.event_ticker,
                "contract_ticker": contract.contract_ticker,
                "yes_bid_price": decimal_or_none(contract.yes_bid_price),
                "yes_ask_price": decimal_or_none(contract.yes_ask_price),
                "no_bid_price": decimal_or_none(contract.no_bid_price),
                "no_ask_price": decimal_or_none(contract.no_ask_price),
                "settlement_value": decimal_or_none(contract.settlement_value),
                "raw_payload": snapshot.raw_payload,
            },
            strategy=None,
            contract_ticker=contract.contract_ticker,
            occurred_at=observed_at,
        )
        return contract

    def create_order_intent(
        self,
        request: PredictionOrderRequest,
        *,
        now: datetime | None = None,
    ) -> PredictionOrderIntent:
        created_at = ensure_utc(now or utc_now())
        contract = self.session.get(PredictionContract, request.contract_id)
        if contract is None:
            raise ValueError("Prediction contract not found")
        validate_positive_quantity(request.quantity)
        validate_probability_price(request.limit_price, field_name="limit price")

        existing = self.session.execute(
            select(PredictionOrderIntent).where(
                PredictionOrderIntent.idempotency_key == request.idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        estimated_fee = estimate_binary_contract_fee(request.quantity, request.limit_price)
        max_cost = (
            calculate_binary_entry_cost(request.quantity, request.limit_price, estimated_fee)
            if request.action == PredictionMarketOrderAction.BUY
            else estimated_fee
        )
        research_gate = self._research_gate_snapshot(request.strategy)
        quote_freshness = quote_freshness_snapshot(
            contract,
            created_at,
            request.risk_limits.max_quote_age_seconds,
        )
        quote_spread = quote_spread_snapshot(
            contract,
            request.side,
            request.risk_limits.max_spread,
        )
        rejection_reasons = [
            *research_gate["rejection_reasons"],
            *self._risk_rejection_reasons(
                request,
                max_cost,
                quote_freshness,
                quote_spread,
            ),
        ]
        status = (
            PredictionMarketOrderStatus.REJECTED
            if rejection_reasons
            else PredictionMarketOrderStatus.CREATED
        )
        intent = PredictionOrderIntent(
            contract=contract,
            signal_id=request.signal_id,
            risk_decision_id=request.risk_decision_id,
            broker_connection_id=request.broker_connection_id,
            strategy=request.strategy,
            side=request.side,
            action=request.action,
            order_type=request.order_type,
            quantity=request.quantity,
            limit_price=request.limit_price,
            max_cost=max_cost,
            expected_edge=request.expected_edge,
            confidence=request.confidence,
            status=status,
            idempotency_key=request.idempotency_key,
            intent_snapshot={
                "paper_only": True,
                "account_id": request.account_id,
                "estimated_fee": str(estimated_fee),
                "execution_boundary": execution_boundary_for(request.action),
                "research_gate": research_gate["snapshot"],
                "risk_limits": {
                    "max_order_cost": str(request.risk_limits.max_order_cost),
                    "max_contract_exposure": str(request.risk_limits.max_contract_exposure),
                    "max_open_positions": request.risk_limits.max_open_positions,
                    "max_quote_age_seconds": request.risk_limits.max_quote_age_seconds,
                    "max_spread": (
                        str(request.risk_limits.max_spread)
                        if request.risk_limits.max_spread is not None
                        else None
                    ),
                    "max_latency_ms": request.risk_limits.max_latency_ms,
                    "max_slippage": (
                        str(request.risk_limits.max_slippage)
                        if request.risk_limits.max_slippage is not None
                        else None
                    ),
                },
                "quote_freshness": quote_freshness,
                "quote_spread": quote_spread,
                "rejection_reasons": rejection_reasons,
            },
            created_intent_at=created_at,
            expires_at=request.expires_at,
        )
        self.session.add(intent)
        self.session.flush()

        evidence_kind = (
            PredictionMarketEvidenceKind.RISK_BLOCK
            if rejection_reasons
            else PredictionMarketEvidenceKind.ORDER_INTENT
        )
        self._record_evidence(
            evidence_kind,
            "prediction_order_intent",
            intent.id,
            {
                "status": intent.status.value,
                "strategy": intent.strategy,
                "contract_ticker": contract.contract_ticker,
                "side": intent.side.value,
                "action": intent.action.value,
                "quantity": str(intent.quantity),
                "limit_price": str(intent.limit_price),
                "max_cost": str(intent.max_cost),
                "rejection_reasons": rejection_reasons,
                "research_gate": intent.intent_snapshot.get("research_gate"),
                "quote_freshness": quote_freshness,
                "quote_spread": quote_spread,
            },
            strategy=intent.strategy,
            contract_ticker=contract.contract_ticker,
            occurred_at=created_at,
        )
        return intent

    def submit_order(
        self,
        order_intent_id: str,
        fill_model: PredictionFillModel,
        *,
        now: datetime | None = None,
    ) -> PredictionOrderSubmission:
        submitted_at = ensure_utc(now or utc_now())
        intent = self.session.get(PredictionOrderIntent, order_intent_id)
        if intent is None:
            raise ValueError("Prediction order intent not found")
        if intent.status == PredictionMarketOrderStatus.REJECTED:
            raise ValueError("Rejected prediction order intents cannot be submitted")
        if intent.expires_at is not None and ensure_utc(intent.expires_at) <= submitted_at:
            intent.status = PredictionMarketOrderStatus.EXPIRED
            self.session.flush()
            self._record_evidence(
                PredictionMarketEvidenceKind.ORDER_CANCELLED,
                "prediction_order_intent",
                intent.id,
                {"reason": "intent_expired_before_submission"},
                strategy=intent.strategy,
                contract_ticker=intent.contract.contract_ticker,
                occurred_at=submitted_at,
            )
            raise ValueError("Prediction order intent is expired")

        existing_order = self.session.execute(
            select(PredictionOrder).where(PredictionOrder.order_intent_id == intent.id)
        ).scalar_one_or_none()
        if existing_order is not None and existing_order.status not in {
            PredictionMarketOrderStatus.SUBMITTED,
            PredictionMarketOrderStatus.PARTIALLY_FILLED,
        }:
            return PredictionOrderSubmission(
                order=existing_order,
                fill=existing_order.fills[-1] if existing_order.fills else None,
                position=self._position_for(existing_order),
            )

        available_quantity = max(fill_model.available_quantity, Decimal("0"))
        market_price = fill_model.execution_price or executable_price(intent)
        if market_price is not None:
            validate_probability_price(market_price, field_name="execution price")

        latency = execution_latency_snapshot(intent, fill_model.latency_ms)
        latency_rejection = latency.get("rejection_reason")
        slippage = execution_slippage_snapshot(intent, market_price)
        slippage_rejection = slippage.get("rejection_reason")
        execution_rejections = [
            str(rejection)
            for rejection in (latency_rejection, slippage_rejection)
            if rejection is not None
        ]
        if execution_rejections:
            rejection_payload = {
                "status": PredictionMarketOrderStatus.REJECTED.value,
                "strategy": intent.strategy,
                "contract_ticker": intent.contract.contract_ticker,
                "side": intent.side.value,
                "action": intent.action.value,
                "quantity": str(intent.quantity),
                "limit_price": str(intent.limit_price),
                "market_price": decimal_or_none(market_price),
                "rejection_reasons": execution_rejections,
                "execution_latency": latency,
                "execution_slippage": slippage,
                "spread_snapshot": spread_snapshot(intent),
            }
            if existing_order is not None:
                existing_order.external_updated_at = submitted_at
                existing_order.raw_payload = {
                    **(existing_order.raw_payload or {}),
                    "last_rejection": rejection_payload,
                    "last_rejected_at": submitted_at.isoformat(),
                }
                self.session.flush()
                self._record_evidence(
                    PredictionMarketEvidenceKind.RISK_BLOCK,
                    "prediction_order",
                    existing_order.id,
                    {
                        **rejection_payload,
                        "status": existing_order.status.value,
                        "existing_filled_quantity": str(existing_order.filled_quantity),
                    },
                    strategy=intent.strategy,
                    contract_ticker=intent.contract.contract_ticker,
                    occurred_at=submitted_at,
                )
                return PredictionOrderSubmission(
                    order=existing_order,
                    fill=None,
                    position=self._position_for(existing_order),
                )

            order = PredictionOrder(
                order_intent=intent,
                broker_connection_id=intent.broker_connection_id,
                external_order_id=f"paper-prediction-order-{intent.id}",
                status=PredictionMarketOrderStatus.REJECTED,
                side=intent.side,
                action=intent.action,
                quantity=intent.quantity,
                filled_quantity=Decimal("0"),
                limit_price=intent.limit_price,
                average_fill_price=None,
                fees=Decimal("0"),
                submitted_at=submitted_at,
                external_updated_at=submitted_at,
                raw_payload={
                    "paper_only": True,
                    "latency_ms": fill_model.latency_ms,
                    "available_quantity": str(available_quantity),
                    "market_price": decimal_or_none(market_price),
                    "limit_price": str(intent.limit_price),
                    "spread_snapshot": spread_snapshot(intent),
                    "execution_boundary": execution_boundary_for(intent.action),
                    "execution_latency": latency,
                    "execution_slippage": slippage,
                    "rejection_reasons": execution_rejections,
                    "raw_fill_model": fill_model.raw_payload or {},
                },
            )
            intent.status = PredictionMarketOrderStatus.REJECTED
            self.session.add(order)
            self.session.flush()
            self._record_evidence(
                PredictionMarketEvidenceKind.RISK_BLOCK,
                "prediction_order",
                order.id,
                rejection_payload,
                strategy=intent.strategy,
                contract_ticker=intent.contract.contract_ticker,
                occurred_at=submitted_at,
            )
            return PredictionOrderSubmission(order=order, fill=None, position=None)

        previously_filled = (
            existing_order.filled_quantity if existing_order is not None else Decimal("0")
        )
        remaining_quantity = max(intent.quantity - previously_filled, Decimal("0"))
        fillable_quantity = min(available_quantity, remaining_quantity)
        fill_quantity = executable_quantity(intent, fillable_quantity, market_price)
        if intent.action == PredictionMarketOrderAction.SELL:
            fill_quantity = min(fill_quantity, self._open_position_quantity(intent))
        cumulative_filled = previously_filled + fill_quantity
        order_status = order_status_for_fill(intent.quantity, cumulative_filled)
        if existing_order is None:
            order = PredictionOrder(
                order_intent=intent,
                broker_connection_id=intent.broker_connection_id,
                external_order_id=f"paper-prediction-order-{intent.id}",
                status=order_status,
                side=intent.side,
                action=intent.action,
                quantity=intent.quantity,
                filled_quantity=fill_quantity,
                limit_price=intent.limit_price,
                average_fill_price=market_price if fill_quantity > 0 else None,
                fees=Decimal("0"),
                submitted_at=submitted_at,
                external_updated_at=submitted_at,
                raw_payload={
                    "paper_only": True,
                    "latency_ms": fill_model.latency_ms,
                    "available_quantity": str(available_quantity),
                    "market_price": decimal_or_none(market_price),
                    "limit_price": str(intent.limit_price),
                    "spread_snapshot": spread_snapshot(intent),
                    "execution_boundary": execution_boundary_for(intent.action),
                    "raw_fill_model": fill_model.raw_payload or {},
                },
            )
            self.session.add(order)
        else:
            order = existing_order
            if fill_quantity > 0 and market_price is not None:
                order.average_fill_price = calculate_average_fill_price(
                    previously_filled,
                    order.average_fill_price,
                    fill_quantity,
                    market_price,
                )
            order.status = order_status
            order.filled_quantity = cumulative_filled
            order.external_updated_at = submitted_at
            order.raw_payload = {
                **(order.raw_payload or {}),
                "last_fill_attempt": {
                    "latency_ms": fill_model.latency_ms,
                    "available_quantity": str(available_quantity),
                    "remaining_quantity": str(remaining_quantity),
                    "filled_quantity": str(fill_quantity),
                    "cumulative_filled_quantity": str(cumulative_filled),
                    "market_price": decimal_or_none(market_price),
                    "attempted_at": submitted_at.isoformat(),
                    "raw_fill_model": fill_model.raw_payload or {},
                },
            }
        intent.status = order_status
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.ORDER_SUBMITTED,
            "prediction_order",
            order.id,
            {
                "status": order.status.value,
                "latency_ms": fill_model.latency_ms,
                "available_quantity": str(available_quantity),
                "market_price": decimal_or_none(market_price),
                "limit_price": str(intent.limit_price),
                "filled_quantity": str(fill_quantity),
                "cumulative_filled_quantity": str(cumulative_filled),
                "spread_snapshot": spread_snapshot(intent),
                "side": intent.side.value,
                "action": intent.action.value,
            },
            strategy=intent.strategy,
            contract_ticker=intent.contract.contract_ticker,
            occurred_at=submitted_at,
        )

        if fill_quantity == 0 or market_price is None:
            return PredictionOrderSubmission(order=order, fill=None, position=None)

        fee = estimate_binary_contract_fee(fill_quantity, market_price)
        fill = PredictionFill(
            order=order,
            external_fill_id=f"paper-prediction-fill-{order.id}-{len(order.fills) + 1}",
            side=order.side,
            action=order.action,
            quantity=fill_quantity,
            price=market_price,
            fees=fee,
            filled_at=submitted_at,
            raw_payload={"paper_only": True, "latency_ms": fill_model.latency_ms},
        )
        order.fees += fee
        self.session.add(fill)
        position = (
            self._apply_buy_fill(intent, fill, submitted_at)
            if intent.action == PredictionMarketOrderAction.BUY
            else self._apply_sell_fill(intent, fill, submitted_at)
        )
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.FILL_RECEIVED,
            "prediction_fill",
            fill.id,
            {
                "order_id": order.id,
                "side": fill.side.value,
                "action": fill.action.value,
                "quantity": str(fill.quantity),
                "price": str(fill.price),
                "fees": str(fill.fees),
                "order_status": order.status.value,
                "position_id": position.id,
            },
            strategy=intent.strategy,
            contract_ticker=intent.contract.contract_ticker,
            occurred_at=submitted_at,
        )
        return PredictionOrderSubmission(order=order, fill=fill, position=position)

    def cancel_stale_orders(self, *, now: datetime | None = None) -> int:
        cancelled_at = ensure_utc(now or utc_now())
        stale_intents = list(
            self.session.execute(
                select(PredictionOrderIntent).where(
                    PredictionOrderIntent.expires_at.is_not(None),
                    PredictionOrderIntent.status.in_(
                        [
                            PredictionMarketOrderStatus.CREATED,
                            PredictionMarketOrderStatus.SUBMITTED,
                            PredictionMarketOrderStatus.PARTIALLY_FILLED,
                        ]
                    ),
                )
            ).scalars()
        )
        cancelled_count = 0
        for intent in stale_intents:
            if intent.expires_at is None or ensure_utc(intent.expires_at) > cancelled_at:
                continue
            intent.status = PredictionMarketOrderStatus.EXPIRED
            orders = list(
                self.session.execute(
                    select(PredictionOrder).where(PredictionOrder.order_intent_id == intent.id)
                ).scalars()
            )
            for order in orders:
                if order.status in {
                    PredictionMarketOrderStatus.SUBMITTED,
                    PredictionMarketOrderStatus.PARTIALLY_FILLED,
                    PredictionMarketOrderStatus.CREATED,
                }:
                    order.status = PredictionMarketOrderStatus.EXPIRED
                    order.cancelled_at = cancelled_at
                    order.external_updated_at = cancelled_at
            self._record_evidence(
                PredictionMarketEvidenceKind.ORDER_CANCELLED,
                "prediction_order_intent",
                intent.id,
                {"reason": "stale_order_expired", "expired_at": cancelled_at.isoformat()},
                strategy=intent.strategy,
                contract_ticker=intent.contract.contract_ticker,
                occurred_at=cancelled_at,
            )
            cancelled_count += 1
        self.session.flush()
        return cancelled_count

    def cancel_order_intent(
        self,
        order_intent_id: str,
        *,
        reason: str = "manual_order_cancelled",
        now: datetime | None = None,
    ) -> PredictionOrderIntent:
        cancelled_at = ensure_utc(now or utc_now())
        intent = self.session.get(PredictionOrderIntent, order_intent_id)
        if intent is None:
            raise ValueError("Prediction order intent not found")
        if intent.status == PredictionMarketOrderStatus.REJECTED:
            raise ValueError("Rejected prediction order intents cannot be cancelled")
        if intent.status == PredictionMarketOrderStatus.FILLED:
            raise ValueError("Filled prediction order intents cannot be cancelled")
        if intent.status in {
            PredictionMarketOrderStatus.CANCELLED,
            PredictionMarketOrderStatus.EXPIRED,
        }:
            return intent

        intent.status = PredictionMarketOrderStatus.CANCELLED
        orders = list(
            self.session.execute(
                select(PredictionOrder).where(PredictionOrder.order_intent_id == intent.id)
            ).scalars()
        )
        for order in orders:
            if order.status in {
                PredictionMarketOrderStatus.CREATED,
                PredictionMarketOrderStatus.SUBMITTED,
                PredictionMarketOrderStatus.PARTIALLY_FILLED,
            }:
                order.status = PredictionMarketOrderStatus.CANCELLED
                order.cancelled_at = cancelled_at
                order.external_updated_at = cancelled_at
                order.raw_payload = {
                    **(order.raw_payload or {}),
                    "cancel_reason": reason,
                    "cancelled_at": cancelled_at.isoformat(),
                }
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.ORDER_CANCELLED,
            "prediction_order_intent",
            intent.id,
            {
                "reason": reason,
                "cancelled_at": cancelled_at.isoformat(),
                "order_ids": [order.id for order in orders],
                "filled_quantity": str(
                    sum((order.filled_quantity for order in orders), Decimal("0"))
                ),
            },
            strategy=intent.strategy,
            contract_ticker=intent.contract.contract_ticker,
            occurred_at=cancelled_at,
        )
        self.session.flush()
        return intent

    def settle_position(
        self,
        position_id: str,
        settlement_value: Decimal,
        *,
        now: datetime | None = None,
    ) -> PredictionSettlement:
        settled_at = ensure_utc(now or utc_now())
        validate_probability_price(settlement_value, field_name="settlement value")
        position = self.session.get(PredictionPosition, position_id)
        if position is None:
            raise ValueError("Prediction position not found")
        if position.status == PredictionMarketPositionStatus.SETTLED:
            existing = self.session.execute(
                select(PredictionSettlement).where(PredictionSettlement.position_id == position.id)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            raise ValueError("Prediction position is settled but settlement record is missing")
        if position.status == PredictionMarketPositionStatus.CLOSED or position.quantity <= 0:
            raise ValueError("Closed prediction positions cannot be settled")

        prior_realized_pl = position.realized_pl
        remaining_fees = position.fees
        _, _, prior_realized_fees = sell_to_close_fee_totals(position.raw_payload)
        total_lifecycle_fees = (prior_realized_fees + remaining_fees).quantize(
            MONEY_QUANTUM
        )
        gross_payout = calculate_binary_gross_payout(
            position.side,
            position.quantity,
            settlement_value,
        )
        remaining_settlement_realized_pl = calculate_binary_settlement_pl(
            position.side,
            position.quantity,
            position.average_entry_price,
            settlement_value,
            remaining_fees,
        )
        cumulative_realized_pl = (
            prior_realized_pl + remaining_settlement_realized_pl
        ).quantize(MONEY_QUANTUM)
        position.status = PredictionMarketPositionStatus.SETTLED
        position.realized_pl = cumulative_realized_pl
        position.closed_at = settled_at
        position.contract.status = PredictionMarketStatus.SETTLED
        position.contract.settlement_value = settlement_value
        position.raw_payload = {
            **(position.raw_payload or {}),
            "paper_only": True,
            "prior_realized_pl": str(prior_realized_pl),
            "remaining_settlement_realized_pl": str(remaining_settlement_realized_pl),
            "cumulative_realized_pl": str(cumulative_realized_pl),
            "prior_realized_fees": str(prior_realized_fees),
            "remaining_settlement_fees": str(remaining_fees),
            "total_lifecycle_fees": str(total_lifecycle_fees),
        }
        settlement = PredictionSettlement(
            contract=position.contract,
            position=position,
            settlement_value=settlement_value,
            gross_payout=gross_payout,
            realized_pl=cumulative_realized_pl,
            fees=total_lifecycle_fees,
            settled_at=settled_at,
            raw_payload={
                "paper_only": True,
                "prior_realized_pl": str(prior_realized_pl),
                "remaining_settlement_realized_pl": str(remaining_settlement_realized_pl),
                "cumulative_realized_pl": str(cumulative_realized_pl),
                "prior_realized_fees": str(prior_realized_fees),
                "remaining_settlement_fees": str(remaining_fees),
                "total_lifecycle_fees": str(total_lifecycle_fees),
            },
        )
        self.session.add(settlement)
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
            "prediction_settlement",
            settlement.id,
            {
                "position_id": position.id,
                "settlement_value": str(settlement_value),
                "gross_payout": str(gross_payout),
                "prior_realized_pl": str(prior_realized_pl),
                "remaining_settlement_realized_pl": str(remaining_settlement_realized_pl),
                "realized_pl": str(cumulative_realized_pl),
                "fees": str(total_lifecycle_fees),
                "prior_realized_fees": str(prior_realized_fees),
                "remaining_settlement_fees": str(remaining_fees),
                "total_lifecycle_fees": str(total_lifecycle_fees),
            },
            strategy=None,
            contract_ticker=position.contract.contract_ticker,
            occurred_at=settled_at,
        )
        return settlement

    def paper_reconciliation_discrepancies(self) -> list[dict[str, str]]:
        discrepancies: list[dict[str, str]] = []
        orders = list(self.session.execute(select(PredictionOrder)).scalars())
        positions = list(self.session.execute(select(PredictionPosition)).scalars())
        settlements = list(self.session.execute(select(PredictionSettlement)).scalars())

        for order in orders:
            fill_quantity = sum((fill.quantity for fill in order.fills), Decimal("0"))
            fill_fees = sum((fill.fees for fill in order.fills), Decimal("0"))
            if fill_quantity != order.filled_quantity:
                discrepancies.append(
                    {
                        "entity": "prediction_order",
                        "id": order.id,
                        "reason": "filled_quantity_mismatch",
                    }
                )
            if fill_fees != order.fees:
                discrepancies.append(
                    {
                        "entity": "prediction_order",
                        "id": order.id,
                        "reason": "fee_mismatch",
                    }
                )

        net_filled_by_contract_side: dict[tuple[str, PredictionMarketSide], Decimal] = {}
        for fill in self.session.execute(select(PredictionFill)).scalars():
            key = (fill.order.order_intent.contract_id, fill.side)
            signed_quantity = (
                fill.quantity
                if fill.action == PredictionMarketOrderAction.BUY
                else -fill.quantity
            )
            net_filled_by_contract_side[key] = (
                net_filled_by_contract_side.get(key, Decimal("0")) + signed_quantity
            )

        position_by_contract_side: dict[tuple[str, PredictionMarketSide], Decimal] = {}
        for position in positions:
            key = (position.contract_id, position.side)
            position_by_contract_side[key] = (
                position_by_contract_side.get(key, Decimal("0")) + position.quantity
            )

        for key, filled_quantity in net_filled_by_contract_side.items():
            position_quantity = position_by_contract_side.get(key, Decimal("0"))
            if position_quantity != filled_quantity:
                discrepancies.append(
                    {
                        "entity": "prediction_position",
                        "contract_id": key[0],
                        "side": key[1].value,
                        "reason": "position_quantity_mismatch",
                    }
                )

        settlements_by_position_id: dict[str, list[PredictionSettlement]] = {}
        for settlement in settlements:
            if settlement.position_id is not None:
                settlements_by_position_id.setdefault(settlement.position_id, []).append(
                    settlement
                )

            position = settlement.position
            if position is None:
                discrepancies.append(
                    {
                        "entity": "prediction_settlement",
                        "id": settlement.id,
                        "reason": "settlement_position_missing",
                    }
                )
                continue

            if position.status != PredictionMarketPositionStatus.SETTLED:
                discrepancies.append(
                    {
                        "entity": "prediction_settlement",
                        "id": settlement.id,
                        "position_id": position.id,
                        "reason": "settlement_position_status_mismatch",
                    }
                )
            if settlement.contract_id != position.contract_id:
                discrepancies.append(
                    {
                        "entity": "prediction_settlement",
                        "id": settlement.id,
                        "position_id": position.id,
                        "reason": "settlement_contract_mismatch",
                    }
                )
            if position.closed_at is None or ensure_utc(position.closed_at) != ensure_utc(
                settlement.settled_at
            ):
                discrepancies.append(
                    {
                        "entity": "prediction_settlement",
                        "id": settlement.id,
                        "position_id": position.id,
                        "reason": "settlement_closed_at_mismatch",
                    }
                )
            if settlement.realized_pl != position.realized_pl:
                discrepancies.append(
                    {
                        "entity": "prediction_settlement",
                        "id": settlement.id,
                        "position_id": position.id,
                        "reason": "settlement_realized_pl_mismatch",
                    }
                )

            position_raw = position.raw_payload if isinstance(position.raw_payload, dict) else {}
            position_lifecycle_fees = payload_decimal(
                position_raw,
                "total_lifecycle_fees",
            )
            if "total_lifecycle_fees" in position_raw:
                if settlement.fees != position_lifecycle_fees.quantize(MONEY_QUANTUM):
                    discrepancies.append(
                        {
                            "entity": "prediction_settlement",
                            "id": settlement.id,
                            "position_id": position.id,
                            "reason": "settlement_fee_mismatch",
                        }
                    )

            settlement_raw = (
                settlement.raw_payload if isinstance(settlement.raw_payload, dict) else {}
            )
            raw_realized_pl = payload_decimal(settlement_raw, "cumulative_realized_pl")
            if "cumulative_realized_pl" in settlement_raw:
                if settlement.realized_pl != raw_realized_pl.quantize(MONEY_QUANTUM):
                    discrepancies.append(
                        {
                            "entity": "prediction_settlement",
                            "id": settlement.id,
                            "reason": "settlement_raw_realized_pl_mismatch",
                        }
                    )
            raw_lifecycle_fees = payload_decimal(settlement_raw, "total_lifecycle_fees")
            if "total_lifecycle_fees" in settlement_raw:
                if settlement.fees != raw_lifecycle_fees.quantize(MONEY_QUANTUM):
                    discrepancies.append(
                        {
                            "entity": "prediction_settlement",
                            "id": settlement.id,
                            "reason": "settlement_raw_fee_mismatch",
                        }
                    )

        for position in positions:
            if position.status != PredictionMarketPositionStatus.SETTLED:
                continue
            position_settlements = settlements_by_position_id.get(position.id, [])
            if not position_settlements:
                discrepancies.append(
                    {
                        "entity": "prediction_position",
                        "id": position.id,
                        "reason": "settled_position_missing_settlement",
                    }
                )
            elif len(position_settlements) > 1:
                discrepancies.append(
                    {
                        "entity": "prediction_position",
                        "id": position.id,
                        "reason": "settled_position_duplicate_settlements",
                    }
                )

        return discrepancies

    def reconcile_paper_ledger(
        self,
        *,
        now: datetime | None = None,
    ) -> PredictionReconciliationReport:
        reconciled_at = ensure_utc(now or utc_now())
        orders = list(self.session.execute(select(PredictionOrder)).scalars())
        settlements = list(self.session.execute(select(PredictionSettlement)).scalars())
        positions = list(self.session.execute(select(PredictionPosition)).scalars())
        discrepancies = self.paper_reconciliation_discrepancies()

        status = (
            ReconciliationStatus.NOT_READY
            if not orders
            else ReconciliationStatus.DISCREPANCY
            if discrepancies
            else ReconciliationStatus.MATCHED
        )
        report = PredictionReconciliationReport(
            status=status,
            summary=reconciliation_summary(status, len(discrepancies)),
            discrepancies=discrepancies,
            venue_snapshot={
                "paper_only": True,
                "orders": len(orders),
                "fills": self.session.query(PredictionFill).count(),
                "settlements": len(settlements),
            },
            aurex_snapshot={
                "positions": len(positions),
                "settled_positions": sum(
                    1
                    for position in positions
                    if position.status == PredictionMarketPositionStatus.SETTLED
                ),
            },
            reconciled_at=reconciled_at,
        )
        self.session.add(report)
        self.session.flush()
        self._record_evidence(
            PredictionMarketEvidenceKind.POSITION_RECONCILED,
            "prediction_reconciliation_report",
            report.id,
            {
                "status": report.status.value,
                "discrepancies": discrepancies,
                "summary": report.summary,
            },
            strategy=None,
            contract_ticker=None,
            occurred_at=reconciled_at,
        )
        return report

    def _risk_rejection_reasons(
        self,
        request: PredictionOrderRequest,
        max_cost: Decimal,
        quote_freshness: dict[str, object],
        quote_spread: dict[str, object],
    ) -> list[str]:
        reasons: list[str] = []
        for quote_reason in (
            quote_freshness.get("rejection_reason"),
            quote_spread.get("rejection_reason"),
        ):
            if quote_reason is not None:
                reasons.append(str(quote_reason))
        if request.action == PredictionMarketOrderAction.SELL:
            open_quantity = self._open_position_quantity_for_request(request)
            if open_quantity <= 0:
                reasons.append("prediction_sell_to_close_position_missing")
            elif request.quantity > open_quantity:
                reasons.append("prediction_sell_quantity_exceeds_open_position")
            return reasons

        if max_cost > request.risk_limits.max_order_cost:
            reasons.append("prediction_order_cost_exceeds_limit")
        open_positions = list(
            self.session.execute(
                select(PredictionPosition).where(
                    PredictionPosition.status == PredictionMarketPositionStatus.OPEN
                )
            ).scalars()
        )
        if len(open_positions) >= request.risk_limits.max_open_positions:
            reasons.append("prediction_max_open_positions_reached")
        contract_exposure = sum(
            (
                calculate_binary_entry_cost(
                    position.quantity,
                    position.average_entry_price,
                    position.fees,
                )
                for position in open_positions
                if position.contract_id == request.contract_id and position.side == request.side
            ),
            Decimal("0"),
        )
        if contract_exposure + max_cost > request.risk_limits.max_contract_exposure:
            reasons.append("prediction_contract_exposure_exceeds_limit")
        return reasons

    def _research_gate_snapshot(self, strategy: str) -> dict[str, object]:
        candidate = self.session.execute(
            select(StrategyResearchCandidate)
            .where(
                StrategyResearchCandidate.source == StrategyResearchSource.MY_KRYPT_TRADER,
                StrategyResearchCandidate.strategy == strategy,
            )
            .order_by(StrategyResearchCandidate.last_seen_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        requires_gate = candidate is not None or strategy.lower().startswith("mkt_")
        if not requires_gate:
            return {
                "rejection_reasons": [],
                "snapshot": {
                    "required": False,
                    "approved": True,
                    "reason": "prediction_research_gate_not_required_for_strategy",
                    "strategy": strategy,
                },
            }

        latest_run = None
        if candidate is not None:
            latest_run = self.session.execute(
                select(StrategyResearchBacktestRun)
                .where(StrategyResearchBacktestRun.candidate_id == candidate.id)
                .order_by(StrategyResearchBacktestRun.reviewed_at.desc())
                .limit(1)
            ).scalar_one_or_none()

        approved = (
            candidate is not None
            and candidate.status == StrategyResearchStatus.PAPER_ELIGIBLE
            and candidate.trade_eligible
            and latest_run is not None
            and latest_run.accepted
        )
        if approved:
            return {
                "rejection_reasons": [],
                "snapshot": {
                    "required": True,
                    "approved": True,
                    "strategy": strategy,
                    "candidate_id": candidate.id,
                    "candidate_key": candidate.candidate_key,
                    "backtest_run_id": latest_run.id,
                    "evidence_hash": latest_run.evidence_hash,
                    "reviewed_at": latest_run.reviewed_at.isoformat(),
                    "reason": "prediction_research_gate_passed_for_paper_only",
                    "live_execution": "blocked",
                },
            }

        reason = research_gate_block_reason(candidate, latest_run)
        return {
            "rejection_reasons": [reason],
            "snapshot": {
                "required": True,
                "approved": False,
                "strategy": strategy,
                "candidate_id": candidate.id if candidate is not None else None,
                "candidate_key": candidate.candidate_key if candidate is not None else None,
                "backtest_run_id": latest_run.id if latest_run is not None else None,
                "evidence_hash": (
                    latest_run.evidence_hash
                    if latest_run is not None
                    else (candidate.evidence_hash if candidate is not None else None)
                ),
                "reason": reason,
                "live_execution": "blocked",
            },
        }

    def _apply_buy_fill(
        self,
        intent: PredictionOrderIntent,
        fill: PredictionFill,
        filled_at: datetime,
    ) -> PredictionPosition:
        position = self.session.execute(
            select(PredictionPosition)
            .where(
                PredictionPosition.account_id == intent.intent_snapshot.get("account_id"),
                PredictionPosition.contract_id == intent.contract_id,
                PredictionPosition.side == intent.side,
                PredictionPosition.status == PredictionMarketPositionStatus.OPEN,
            )
            .limit(1)
        ).scalar_one_or_none()
        if position is None:
            position = PredictionPosition(
                account_id=intent.intent_snapshot.get("account_id"),
                contract=intent.contract,
                side=intent.side,
                quantity=fill.quantity,
                average_entry_price=fill.price,
                realized_pl=Decimal("0"),
                fees=fill.fees,
                status=PredictionMarketPositionStatus.OPEN,
                opened_at=filled_at,
                raw_payload={"paper_only": True},
            )
            self.session.add(position)
            return position

        position.average_entry_price = calculate_average_fill_price(
            position.quantity,
            position.average_entry_price,
            fill.quantity,
            fill.price,
        )
        position.quantity += fill.quantity
        position.fees += fill.fees
        return position

    def _apply_sell_fill(
        self,
        intent: PredictionOrderIntent,
        fill: PredictionFill,
        filled_at: datetime,
    ) -> PredictionPosition:
        position = self._open_position_for_intent(intent)
        if position is None or position.quantity <= 0:
            raise ValueError("Sell-to-close requires an open prediction position")
        if fill.quantity > position.quantity:
            raise ValueError("Sell-to-close quantity exceeds open prediction position")

        original_quantity = position.quantity
        allocated_entry_fees = (
            (position.fees * fill.quantity) / original_quantity
        ).quantize(MONEY_QUANTUM)
        proceeds = calculate_binary_notional(fill.quantity, fill.price)
        cost_basis = calculate_binary_notional(fill.quantity, position.average_entry_price)
        realized_pl = (
            proceeds - cost_basis - allocated_entry_fees - fill.fees
        ).quantize(MONEY_QUANTUM)
        raw_payload = position.raw_payload or {}
        (
            prior_realized_entry_fees,
            prior_realized_exit_fees,
            prior_realized_fees,
        ) = sell_to_close_fee_totals(raw_payload)
        realized_sell_to_close_entry_fees = (
            prior_realized_entry_fees + allocated_entry_fees
        ).quantize(MONEY_QUANTUM)
        realized_sell_to_close_exit_fees = (
            prior_realized_exit_fees + fill.fees
        ).quantize(MONEY_QUANTUM)
        realized_sell_to_close_fees = (
            prior_realized_fees + allocated_entry_fees + fill.fees
        ).quantize(MONEY_QUANTUM)
        prior_sell_to_close_pl = sell_to_close_pl_total(raw_payload)
        realized_sell_to_close_pl = (prior_sell_to_close_pl + realized_pl).quantize(
            MONEY_QUANTUM
        )

        position.quantity -= fill.quantity
        position.fees = (position.fees - allocated_entry_fees).quantize(MONEY_QUANTUM)
        position.realized_pl = (position.realized_pl + realized_pl).quantize(MONEY_QUANTUM)
        position.raw_payload = {
            **raw_payload,
            "paper_only": True,
            "realized_sell_to_close_entry_fees": str(
                realized_sell_to_close_entry_fees
            ),
            "realized_sell_to_close_exit_fees": str(realized_sell_to_close_exit_fees),
            "realized_sell_to_close_fees": str(realized_sell_to_close_fees),
            "realized_sell_to_close_pl": str(realized_sell_to_close_pl),
            "last_sell_to_close": {
                "fill_id": fill.id,
                "quantity": str(fill.quantity),
                "price": str(fill.price),
                "exit_fee": str(fill.fees),
                "allocated_entry_fees": str(allocated_entry_fees),
                "realized_pl": str(realized_pl),
                "filled_at": filled_at.isoformat(),
            },
        }
        if position.quantity == 0:
            position.status = PredictionMarketPositionStatus.CLOSED
            position.closed_at = filled_at
        return position

    def _position_for(self, order: PredictionOrder) -> PredictionPosition | None:
        return self.session.execute(
            select(PredictionPosition)
            .where(
                PredictionPosition.contract_id == order.order_intent.contract_id,
                PredictionPosition.side == order.side,
                PredictionPosition.status == PredictionMarketPositionStatus.OPEN,
            )
            .limit(1)
        ).scalar_one_or_none()

    def _open_position_quantity_for_request(self, request: PredictionOrderRequest) -> Decimal:
        position = self.session.execute(
            select(PredictionPosition)
            .where(
                PredictionPosition.account_id == request.account_id,
                PredictionPosition.contract_id == request.contract_id,
                PredictionPosition.side == request.side,
                PredictionPosition.status == PredictionMarketPositionStatus.OPEN,
            )
            .limit(1)
        ).scalar_one_or_none()
        return Decimal("0") if position is None else position.quantity

    def _open_position_quantity(self, intent: PredictionOrderIntent) -> Decimal:
        position = self._open_position_for_intent(intent)
        return Decimal("0") if position is None else position.quantity

    def _open_position_for_intent(
        self,
        intent: PredictionOrderIntent,
    ) -> PredictionPosition | None:
        return self.session.execute(
            select(PredictionPosition)
            .where(
                PredictionPosition.account_id == intent.intent_snapshot.get("account_id"),
                PredictionPosition.contract_id == intent.contract_id,
                PredictionPosition.side == intent.side,
                PredictionPosition.status == PredictionMarketPositionStatus.OPEN,
            )
            .limit(1)
        ).scalar_one_or_none()

    def _record_evidence(
        self,
        kind: PredictionMarketEvidenceKind,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
        *,
        strategy: str | None,
        contract_ticker: str | None,
        occurred_at: datetime,
    ) -> PredictionEvidenceEvent:
        evidence_hash = hash_evidence_payload(kind, entity_type, entity_id, payload)
        event = PredictionEvidenceEvent(
            kind=kind,
            entity_type=entity_type,
            entity_id=entity_id,
            strategy=strategy,
            contract_ticker=contract_ticker,
            evidence_hash=evidence_hash,
            payload=payload,
            occurred_at=occurred_at,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def record_evidence_event(
        self,
        kind: PredictionMarketEvidenceKind,
        entity_type: str,
        entity_id: str | None,
        payload: dict,
        *,
        strategy: str | None,
        contract_ticker: str | None = None,
        occurred_at: datetime | None = None,
    ) -> PredictionEvidenceEvent:
        return self._record_evidence(
            kind,
            entity_type,
            entity_id,
            payload,
            strategy=strategy,
            contract_ticker=contract_ticker,
            occurred_at=ensure_utc(occurred_at or utc_now()),
        )


def executable_price(intent: PredictionOrderIntent) -> Decimal | None:
    contract = intent.contract
    if intent.side == PredictionMarketSide.YES:
        return (
            contract.yes_ask_price
            if intent.action == PredictionMarketOrderAction.BUY
            else contract.yes_bid_price
        )
    return (
        contract.no_ask_price
        if intent.action == PredictionMarketOrderAction.BUY
        else contract.no_bid_price
    )


def spread_snapshot(intent: PredictionOrderIntent) -> dict[str, object]:
    return quote_spread_snapshot(intent.contract, intent.side, None)


def executable_quantity(
    intent: PredictionOrderIntent,
    available_quantity: Decimal,
    market_price: Decimal | None,
) -> Decimal:
    if market_price is None or available_quantity <= 0:
        return Decimal("0")
    if intent.action == PredictionMarketOrderAction.BUY and intent.limit_price < market_price:
        return Decimal("0")
    if intent.action == PredictionMarketOrderAction.SELL and intent.limit_price > market_price:
        return Decimal("0")
    return min(intent.quantity, available_quantity)


def execution_boundary_for(action: PredictionMarketOrderAction) -> str:
    if action == PredictionMarketOrderAction.SELL:
        return "paper_sell_to_close_only_no_short_selling_no_live_execution"
    return "paper_buy_open_or_add_only_no_live_execution"


def execution_latency_snapshot(
    intent: PredictionOrderIntent,
    latency_ms: int,
) -> dict[str, object]:
    risk_limits = intent.intent_snapshot.get("risk_limits") if intent.intent_snapshot else {}
    max_latency_ms = (
        risk_limits.get("max_latency_ms") if isinstance(risk_limits, dict) else None
    )
    exceeded = max_latency_ms is not None and latency_ms > int(max_latency_ms)
    return {
        "latency_ms": latency_ms,
        "max_latency_ms": max_latency_ms,
        "exceeded": exceeded,
        "rejection_reason": (
            "prediction_execution_latency_exceeds_limit" if exceeded else None
        ),
    }


def execution_slippage_snapshot(
    intent: PredictionOrderIntent,
    execution_price: Decimal | None,
) -> dict[str, object]:
    risk_limits = intent.intent_snapshot.get("risk_limits") if intent.intent_snapshot else {}
    raw_max_slippage = (
        risk_limits.get("max_slippage") if isinstance(risk_limits, dict) else None
    )
    max_slippage = Decimal(str(raw_max_slippage)) if raw_max_slippage is not None else None
    if max_slippage is not None:
        validate_probability_price(max_slippage, field_name="max slippage")
    reference_price = executable_price(intent)
    adverse_slippage = None
    if execution_price is not None and reference_price is not None:
        raw_slippage = (
            execution_price - reference_price
            if intent.action == PredictionMarketOrderAction.BUY
            else reference_price - execution_price
        )
        adverse_slippage = max(Decimal("0"), raw_slippage)

    rejection_reason = None
    if max_slippage is not None and execution_price is not None:
        if reference_price is None:
            rejection_reason = "prediction_execution_slippage_reference_missing"
        elif adverse_slippage is not None and adverse_slippage > max_slippage:
            rejection_reason = "prediction_execution_slippage_exceeds_limit"

    return {
        "side": intent.side.value,
        "action": intent.action.value,
        "reference_price": decimal_or_none(reference_price),
        "execution_price": decimal_or_none(execution_price),
        "adverse_slippage": decimal_or_none(adverse_slippage),
        "max_slippage": decimal_or_none(max_slippage),
        "exceeded": rejection_reason is not None,
        "rejection_reason": rejection_reason,
    }


def order_status_for_fill(
    requested_quantity: Decimal,
    filled_quantity: Decimal,
) -> PredictionMarketOrderStatus:
    if filled_quantity <= 0:
        return PredictionMarketOrderStatus.SUBMITTED
    if filled_quantity < requested_quantity:
        return PredictionMarketOrderStatus.PARTIALLY_FILLED
    return PredictionMarketOrderStatus.FILLED


def research_gate_block_reason(
    candidate: StrategyResearchCandidate | None,
    latest_run: StrategyResearchBacktestRun | None,
) -> str:
    if candidate is None:
        return "prediction_research_candidate_missing_for_mkt_strategy"
    if latest_run is None:
        return "prediction_research_backtest_missing_for_paper_intent"
    if not latest_run.accepted:
        return "prediction_research_backtest_not_accepted_for_paper_intent"
    if candidate.status != StrategyResearchStatus.PAPER_ELIGIBLE or not candidate.trade_eligible:
        return "prediction_research_candidate_not_paper_eligible"
    return "prediction_research_gate_not_approved_for_paper_intent"


def reconciliation_summary(status: ReconciliationStatus, discrepancy_count: int) -> str:
    if status == ReconciliationStatus.NOT_READY:
        return "No prediction-market paper orders are available to reconcile."
    if status == ReconciliationStatus.DISCREPANCY:
        return f"Found {discrepancy_count} prediction-market reconciliation discrepancies."
    return "Prediction-market paper orders, fills, positions, and settlements reconcile."


def validate_optional_price(value: Decimal | None, field_name: str) -> None:
    if value is not None:
        validate_probability_price(value, field_name=field_name)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def decimal_or_none(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def payload_decimal(payload: dict | None, key: str) -> Decimal:
    if not isinstance(payload, dict):
        return Decimal("0")
    value = payload.get(key)
    return Decimal("0") if value is None else Decimal(str(value))


def payload_has_key(payload: dict | None, key: str) -> bool:
    return isinstance(payload, dict) and key in payload


def sell_to_close_fee_totals(raw_payload: dict | None) -> tuple[Decimal, Decimal, Decimal]:
    entry_fees = payload_decimal(raw_payload, "realized_sell_to_close_entry_fees")
    exit_fees = payload_decimal(raw_payload, "realized_sell_to_close_exit_fees")
    total_fees = payload_decimal(raw_payload, "realized_sell_to_close_fees")
    has_cumulative_fees = any(
        payload_has_key(raw_payload, key)
        for key in (
            "realized_sell_to_close_entry_fees",
            "realized_sell_to_close_exit_fees",
            "realized_sell_to_close_fees",
        )
    )
    if not has_cumulative_fees and isinstance(raw_payload, dict):
        last_sell = raw_payload.get("last_sell_to_close")
        if isinstance(last_sell, dict):
            entry_fees = payload_decimal(last_sell, "allocated_entry_fees")
            exit_fees = payload_decimal(last_sell, "exit_fee")
            total_fees = (entry_fees + exit_fees).quantize(MONEY_QUANTUM)
    elif total_fees == 0 and (entry_fees != 0 or exit_fees != 0):
        total_fees = (entry_fees + exit_fees).quantize(MONEY_QUANTUM)
    return (
        entry_fees.quantize(MONEY_QUANTUM),
        exit_fees.quantize(MONEY_QUANTUM),
        total_fees.quantize(MONEY_QUANTUM),
    )


def sell_to_close_pl_total(raw_payload: dict | None) -> Decimal:
    if payload_has_key(raw_payload, "realized_sell_to_close_pl"):
        return payload_decimal(raw_payload, "realized_sell_to_close_pl").quantize(
            MONEY_QUANTUM
        )
    if isinstance(raw_payload, dict):
        last_sell = raw_payload.get("last_sell_to_close")
        if isinstance(last_sell, dict):
            return payload_decimal(last_sell, "realized_pl").quantize(MONEY_QUANTUM)
    return Decimal("0")


def quote_snapshot_age_seconds(contract: PredictionContract, now: datetime) -> int:
    observed_at = ensure_utc(contract.last_seen_at)
    current_at = ensure_utc(now)
    return max(0, int((current_at - observed_at).total_seconds()))


def quote_freshness_snapshot(
    contract: PredictionContract,
    now: datetime,
    max_quote_age_seconds: int | None,
) -> dict[str, object]:
    age_seconds = quote_snapshot_age_seconds(contract, now)
    stale = max_quote_age_seconds is not None and age_seconds > max_quote_age_seconds
    return {
        "contract_last_seen_at": ensure_utc(contract.last_seen_at).isoformat(),
        "checked_at": ensure_utc(now).isoformat(),
        "age_seconds": age_seconds,
        "max_quote_age_seconds": max_quote_age_seconds,
        "stale": stale,
        "rejection_reason": "prediction_quote_snapshot_stale" if stale else None,
    }


def quote_spread_snapshot(
    contract: PredictionContract,
    side: PredictionMarketSide,
    max_spread: Decimal | None,
) -> dict[str, object]:
    if side == PredictionMarketSide.YES:
        bid = contract.yes_bid_price
        ask = contract.yes_ask_price
    else:
        bid = contract.no_bid_price
        ask = contract.no_ask_price
    spread = None if bid is None or ask is None else ask - bid
    rejection_reason = None
    if max_spread is not None:
        validate_probability_price(max_spread, field_name="max spread")
        if spread is None:
            rejection_reason = "prediction_quote_spread_missing"
        elif spread < 0:
            rejection_reason = "prediction_quote_spread_invalid"
        elif spread > max_spread:
            rejection_reason = "prediction_quote_spread_exceeds_limit"
    return {
        "side": side.value,
        "bid": decimal_or_none(bid),
        "ask": decimal_or_none(ask),
        "spread": decimal_or_none(spread),
        "max_spread": decimal_or_none(max_spread),
        "rejection_reason": rejection_reason,
    }


def hash_evidence_payload(
    kind: PredictionMarketEvidenceKind,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
) -> str:
    normalized = json.dumps(
        {
            "kind": kind.value,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
        },
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(normalized.encode("utf-8")).hexdigest()
