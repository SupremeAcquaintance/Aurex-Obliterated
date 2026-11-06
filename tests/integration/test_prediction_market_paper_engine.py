from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aurex.db.base import Base
from aurex.db.models import (
    PredictionEvidenceEvent,
    PredictionFill,
    PredictionOrder,
    PredictionOrderIntent,
    PredictionPosition,
)
from aurex.domain.enums import (
    PredictionMarketEvidenceKind,
    PredictionMarketOrderAction,
    PredictionMarketOrderStatus,
    PredictionMarketPositionStatus,
    PredictionMarketSide,
    PredictionMarketStatus,
    PredictionMarketVenue,
    ReconciliationStatus,
)
from aurex.prediction_market.paper import (
    PredictionContractSnapshot,
    PredictionFillModel,
    PredictionMarketPaperEngine,
    PredictionOrderRequest,
    PredictionRiskLimits,
)


def test_paper_engine_rejects_over_risk_order_and_records_evidence() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)

        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="mkt_whale_research_candidate",
                side=PredictionMarketSide.YES,
                quantity=Decimal("100"),
                limit_price=Decimal("0.70"),
                idempotency_key="over-risk",
                risk_limits=PredictionRiskLimits(max_order_cost=Decimal("10")),
            ),
            now=now,
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert "prediction_research_candidate_missing_for_mkt_strategy" in (
            intent.intent_snapshot["rejection_reasons"]
        )
        assert "prediction_order_cost_exceeds_limit" in (
            intent.intent_snapshot["rejection_reasons"]
        )
        assert "prediction_contract_exposure_exceeds_limit" in (
            intent.intent_snapshot["rejection_reasons"]
        )
        assert intent.intent_snapshot["research_gate"]["approved"] is False
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert [event.kind for event in events][-1] == PredictionMarketEvidenceKind.RISK_BLOCK
        assert session.execute(select(PredictionOrder)).scalar_one_or_none() is None


def test_paper_engine_partially_fills_order_and_opens_fee_tracked_position() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.61"),
                idempotency_key="partial-fill",
                expires_at=now + timedelta(minutes=2),
            ),
            now=now,
        )

        result = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("4"),
                latency_ms=750,
                execution_price=Decimal("0.60"),
                raw_payload={"book_depth": "thin"},
            ),
            now=now + timedelta(seconds=1),
        )
        session.commit()

        assert result.order.status == PredictionMarketOrderStatus.PARTIALLY_FILLED
        assert result.fill is not None
        assert result.fill.quantity == Decimal("4.000000000000")
        assert result.fill.fees == Decimal("0.06720000")
        assert result.position is not None
        assert result.position.quantity == Decimal("4.000000000000")
        assert result.position.fees == Decimal("0.06720000")
        assert result.order.raw_payload["latency_ms"] == 750
        assert result.order.raw_payload["spread_snapshot"] | {
            "max_spread": None,
            "rejection_reason": None,
            "side": "YES",
        } == {
            "side": "YES",
            "bid": "0.59",
            "ask": "0.60",
            "spread": "0.01",
            "max_spread": None,
            "rejection_reason": None,
        }
        assert result.order.raw_payload["raw_fill_model"]["book_depth"] == "thin"
        event_kinds = [
            event.kind for event in session.execute(select(PredictionEvidenceEvent)).scalars()
        ]
        assert PredictionMarketEvidenceKind.ORDER_SUBMITTED in event_kinds
        assert PredictionMarketEvidenceKind.FILL_RECEIVED in event_kinds


def test_paper_engine_accumulates_additional_partial_fills_on_existing_order() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.61"),
                idempotency_key="multi-partial-fill",
                expires_at=now + timedelta(minutes=2),
            ),
            now=now,
        )

        first = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("4"),
                latency_ms=250,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        second = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=300,
                execution_price=Decimal("0.61"),
            ),
            now=now + timedelta(seconds=2),
        )
        report = paper.reconcile_paper_ledger(now=now + timedelta(seconds=3))
        session.commit()

        fills = list(session.execute(select(PredictionFill)).scalars())
        saved_order = session.execute(select(PredictionOrder)).scalar_one()
        saved_position = session.execute(select(PredictionPosition)).scalar_one()
        assert first.order.id == second.order.id
        assert first.order.status == PredictionMarketOrderStatus.FILLED
        assert second.order.status == PredictionMarketOrderStatus.FILLED
        assert second.fill is not None
        assert second.fill.external_fill_id.endswith("-2")
        assert [fill.quantity for fill in fills] == [
            Decimal("4.000000000000"),
            Decimal("6.000000000000"),
        ]
        assert saved_order.filled_quantity == Decimal("10.000000000000")
        assert saved_order.average_fill_price == Decimal("0.60600000")
        assert saved_order.fees == Decimal("0.16711800")
        assert Decimal(saved_order.raw_payload["last_fill_attempt"]["remaining_quantity"]) == (
            Decimal("6")
        )
        assert saved_position.quantity == Decimal("10.000000000000")
        assert saved_position.average_entry_price == Decimal("0.60600000")
        assert saved_position.fees == Decimal("0.16711800")
        assert report.status == ReconciliationStatus.MATCHED
        event_kinds = [
            event.kind for event in session.execute(select(PredictionEvidenceEvent)).scalars()
        ]
        assert event_kinds.count(PredictionMarketEvidenceKind.FILL_RECEIVED) == 2


def test_paper_engine_rejects_stale_quote_snapshot_when_limit_is_set() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)

        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("1"),
                limit_price=Decimal("0.60"),
                idempotency_key="stale-quote-risk-block",
                risk_limits=PredictionRiskLimits(max_quote_age_seconds=900),
            ),
            now=now + timedelta(seconds=901),
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert intent.intent_snapshot["rejection_reasons"] == [
            "prediction_quote_snapshot_stale"
        ]
        assert intent.intent_snapshot["quote_freshness"]["age_seconds"] == 901
        assert intent.intent_snapshot["quote_freshness"]["max_quote_age_seconds"] == 900
        assert intent.intent_snapshot["quote_freshness"]["stale"] is True
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert events[-1].kind == PredictionMarketEvidenceKind.RISK_BLOCK
        assert events[-1].payload["quote_freshness"]["rejection_reason"] == (
            "prediction_quote_snapshot_stale"
        )
        assert session.execute(select(PredictionOrder)).scalar_one_or_none() is None


def test_paper_engine_rejects_wide_quote_spread_when_limit_is_set() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)

        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("1"),
                limit_price=Decimal("0.60"),
                idempotency_key="wide-spread-risk-block",
                risk_limits=PredictionRiskLimits(max_spread=Decimal("0.005")),
            ),
            now=now,
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert intent.intent_snapshot["rejection_reasons"] == [
            "prediction_quote_spread_exceeds_limit"
        ]
        assert intent.intent_snapshot["risk_limits"]["max_spread"] == "0.005"
        assert intent.intent_snapshot["quote_spread"] == {
            "side": "YES",
            "bid": "0.59",
            "ask": "0.60",
            "spread": "0.01",
            "max_spread": "0.005",
            "rejection_reason": "prediction_quote_spread_exceeds_limit",
        }
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert events[-1].kind == PredictionMarketEvidenceKind.RISK_BLOCK
        assert events[-1].payload["quote_spread"]["rejection_reason"] == (
            "prediction_quote_spread_exceeds_limit"
        )
        assert session.execute(select(PredictionOrder)).scalar_one_or_none() is None


def test_paper_engine_rejects_order_submission_when_latency_exceeds_limit() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.60"),
                idempotency_key="latency-risk-block",
                risk_limits=PredictionRiskLimits(max_latency_ms=250),
            ),
            now=now,
        )

        submission = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=300,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert submission.order.status == PredictionMarketOrderStatus.REJECTED
        assert submission.order.filled_quantity == Decimal("0E-12")
        assert submission.order.raw_payload["execution_latency"] == {
            "latency_ms": 300,
            "max_latency_ms": 250,
            "exceeded": True,
            "rejection_reason": "prediction_execution_latency_exceeds_limit",
        }
        assert submission.fill is None
        assert submission.position is None
        assert session.execute(select(PredictionFill)).scalar_one_or_none() is None
        assert session.execute(select(PredictionPosition)).scalar_one_or_none() is None
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert events[-1].kind == PredictionMarketEvidenceKind.RISK_BLOCK
        assert events[-1].payload["execution_latency"]["rejection_reason"] == (
            "prediction_execution_latency_exceeds_limit"
        )


def test_paper_engine_rejects_order_submission_when_slippage_exceeds_limit() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.65"),
                idempotency_key="slippage-risk-block",
                risk_limits=PredictionRiskLimits(max_slippage=Decimal("0.01")),
            ),
            now=now,
        )

        submission = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=100,
                execution_price=Decimal("0.62"),
            ),
            now=now + timedelta(seconds=1),
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert submission.order.status == PredictionMarketOrderStatus.REJECTED
        assert submission.order.raw_payload["execution_slippage"] == {
            "side": "YES",
            "action": "BUY",
            "reference_price": "0.60",
            "execution_price": "0.62",
            "adverse_slippage": "0.02",
            "max_slippage": "0.01",
            "exceeded": True,
            "rejection_reason": "prediction_execution_slippage_exceeds_limit",
        }
        assert submission.fill is None
        assert submission.position is None
        assert session.execute(select(PredictionFill)).scalar_one_or_none() is None
        assert session.execute(select(PredictionPosition)).scalar_one_or_none() is None
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert events[-1].kind == PredictionMarketEvidenceKind.RISK_BLOCK
        assert events[-1].payload["execution_slippage"]["rejection_reason"] == (
            "prediction_execution_slippage_exceeds_limit"
        )


def test_paper_engine_expires_stale_unfilled_order() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.55"),
                idempotency_key="stale-unfilled",
                expires_at=now + timedelta(seconds=30),
            ),
            now=now,
        )
        result = paper.submit_order(
            intent.id,
            PredictionFillModel(available_quantity=Decimal("10"), latency_ms=300),
            now=now + timedelta(seconds=1),
        )

        cancelled = paper.cancel_stale_orders(now=now + timedelta(seconds=31))
        session.commit()

        saved_intent = session.execute(select(PredictionOrderIntent)).scalar_one()
        saved_order = session.execute(select(PredictionOrder)).scalar_one()
        assert result.fill is None
        assert result.order.status == PredictionMarketOrderStatus.EXPIRED
        assert cancelled == 1
        assert saved_intent.status == PredictionMarketOrderStatus.EXPIRED
        assert saved_order.status == PredictionMarketOrderStatus.EXPIRED
        assert saved_order.cancelled_at == (now + timedelta(seconds=31)).replace(tzinfo=None)
        assert session.execute(select(PredictionFill)).scalar_one_or_none() is None


def test_paper_engine_manually_cancels_remaining_partial_order() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.61"),
                idempotency_key="manual-cancel-partial",
                expires_at=now + timedelta(minutes=5),
            ),
            now=now,
        )
        submission = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("4"),
                latency_ms=250,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )

        cancelled = paper.cancel_order_intent(
            intent.id,
            reason="operator_manual_cancel",
            now=now + timedelta(seconds=5),
        )
        report = paper.reconcile_paper_ledger(now=now + timedelta(seconds=6))
        session.commit()

        saved_order = session.execute(select(PredictionOrder)).scalar_one()
        saved_position = session.execute(select(PredictionPosition)).scalar_one()
        cancel_event = list(
            session.execute(
                select(PredictionEvidenceEvent).where(
                    PredictionEvidenceEvent.kind
                    == PredictionMarketEvidenceKind.ORDER_CANCELLED
                )
            ).scalars()
        )[-1]
        assert submission.fill is not None
        assert cancelled.status == PredictionMarketOrderStatus.CANCELLED
        assert saved_order.status == PredictionMarketOrderStatus.CANCELLED
        assert saved_order.cancelled_at == (now + timedelta(seconds=5)).replace(tzinfo=None)
        assert saved_order.raw_payload["cancel_reason"] == "operator_manual_cancel"
        assert saved_position.status == PredictionMarketPositionStatus.OPEN
        assert saved_position.quantity == Decimal("4.000000000000")
        assert cancel_event.payload["reason"] == "operator_manual_cancel"
        assert Decimal(cancel_event.payload["filled_quantity"]) == Decimal("4")
        assert report.status == ReconciliationStatus.MATCHED


def test_paper_engine_sells_to_close_open_position_fee_net_and_reconciles() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        buy_intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.60"),
                idempotency_key="buy-before-sell-close",
            ),
            now=now,
        )
        buy_submission = paper.submit_order(
            buy_intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=400,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        assert buy_submission.position is not None

        sell_intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                action=PredictionMarketOrderAction.SELL,
                quantity=Decimal("4"),
                limit_price=Decimal("0.58"),
                idempotency_key="sell-to-close-partial",
            ),
            now=now + timedelta(seconds=2),
        )
        sell_submission = paper.submit_order(
            sell_intent.id,
            PredictionFillModel(
                available_quantity=Decimal("4"),
                latency_ms=300,
                execution_price=Decimal("0.59"),
            ),
            now=now + timedelta(seconds=3),
        )
        report = paper.reconcile_paper_ledger(now=now + timedelta(seconds=4))
        session.commit()

        saved_position = session.execute(select(PredictionPosition)).scalar_one()
        sell_order = sell_submission.order
        assert sell_intent.status == PredictionMarketOrderStatus.FILLED
        assert sell_intent.intent_snapshot["execution_boundary"] == (
            "paper_sell_to_close_only_no_short_selling_no_live_execution"
        )
        assert sell_order.status == PredictionMarketOrderStatus.FILLED
        assert sell_order.action == PredictionMarketOrderAction.SELL
        assert sell_submission.fill is not None
        assert sell_submission.fill.action == PredictionMarketOrderAction.SELL
        assert sell_submission.fill.fees == Decimal("0.06773200")
        assert saved_position.status == PredictionMarketPositionStatus.OPEN
        assert saved_position.quantity == Decimal("6.000000000000")
        assert saved_position.fees == Decimal("0.10080000")
        assert saved_position.realized_pl == Decimal("-0.17493200")
        assert saved_position.raw_payload["last_sell_to_close"]["allocated_entry_fees"] == (
            "0.06720000"
        )
        assert saved_position.raw_payload["realized_sell_to_close_entry_fees"] == (
            "0.06720000"
        )
        assert saved_position.raw_payload["realized_sell_to_close_exit_fees"] == (
            "0.06773200"
        )
        assert saved_position.raw_payload["realized_sell_to_close_fees"] == "0.13493200"
        assert saved_position.raw_payload["realized_sell_to_close_pl"] == "-0.17493200"
        assert report.status == ReconciliationStatus.MATCHED
        assert report.discrepancies == []


def test_paper_engine_settlement_preserves_prior_sell_to_close_realized_pl() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        buy_intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.60"),
                idempotency_key="settle-after-partial-sell-buy",
            ),
            now=now,
        )
        buy_submission = paper.submit_order(
            buy_intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=100,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        assert buy_submission.position is not None
        sell_intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                action=PredictionMarketOrderAction.SELL,
                quantity=Decimal("4"),
                limit_price=Decimal("0.58"),
                idempotency_key="settle-after-partial-sell-close",
            ),
            now=now + timedelta(seconds=2),
        )
        paper.submit_order(
            sell_intent.id,
            PredictionFillModel(
                available_quantity=Decimal("4"),
                latency_ms=100,
                execution_price=Decimal("0.59"),
            ),
            now=now + timedelta(seconds=3),
        )
        settlement = paper.settle_position(
            buy_submission.position.id,
            Decimal("1"),
            now=now + timedelta(minutes=5),
        )
        report = paper.reconcile_paper_ledger(now=now + timedelta(minutes=6))
        session.commit()

        saved_position = session.execute(select(PredictionPosition)).scalar_one()
        assert settlement.gross_payout == Decimal("6.00000000")
        assert settlement.fees == Decimal("0.23573200")
        assert settlement.raw_payload["prior_realized_pl"] == "-0.17493200"
        assert settlement.raw_payload["remaining_settlement_realized_pl"] == "2.29920000"
        assert settlement.raw_payload["prior_realized_fees"] == "0.13493200"
        assert settlement.raw_payload["remaining_settlement_fees"] == "0.10080000"
        assert settlement.raw_payload["total_lifecycle_fees"] == "0.23573200"
        assert settlement.realized_pl == Decimal("2.12426800")
        assert saved_position.realized_pl == Decimal("2.12426800")
        assert saved_position.raw_payload["total_lifecycle_fees"] == "0.23573200"
        assert saved_position.status == PredictionMarketPositionStatus.SETTLED
        assert report.status == ReconciliationStatus.MATCHED
        settlement_event = list(
            session.execute(
                select(PredictionEvidenceEvent).where(
                    PredictionEvidenceEvent.kind
                    == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED
                )
            ).scalars()
        )[-1]
        assert settlement_event.payload["prior_realized_pl"] == "-0.17493200"
        assert settlement_event.payload["remaining_settlement_realized_pl"] == "2.29920000"
        assert settlement_event.payload["realized_pl"] == "2.12426800"
        assert settlement_event.payload["fees"] == "0.23573200"
        assert settlement_event.payload["prior_realized_fees"] == "0.13493200"
        assert settlement_event.payload["remaining_settlement_fees"] == "0.10080000"
        assert settlement_event.payload["total_lifecycle_fees"] == "0.23573200"


def test_paper_engine_rejects_sell_to_close_without_open_position() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)

        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                action=PredictionMarketOrderAction.SELL,
                quantity=Decimal("1"),
                limit_price=Decimal("0.58"),
                idempotency_key="sell-to-close-missing-position",
            ),
            now=now,
        )
        session.commit()

        assert intent.status == PredictionMarketOrderStatus.REJECTED
        assert intent.max_cost == Decimal("0.01705200")
        assert intent.intent_snapshot["rejection_reasons"] == [
            "prediction_sell_to_close_position_missing"
        ]
        events = list(session.execute(select(PredictionEvidenceEvent)).scalars())
        assert events[-1].kind == PredictionMarketEvidenceKind.RISK_BLOCK
        assert events[-1].payload["action"] == PredictionMarketOrderAction.SELL
        assert session.execute(select(PredictionOrder)).scalar_one_or_none() is None


def test_paper_engine_settles_fee_net_position_and_reconciles() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.60"),
                idempotency_key="settled-win",
            ),
            now=now,
        )
        submission = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=500,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        assert submission.position is not None

        settlement = paper.settle_position(
            submission.position.id,
            Decimal("1"),
            now=now + timedelta(minutes=20),
        )
        report = paper.reconcile_paper_ledger(now=now + timedelta(minutes=21))
        session.commit()

        saved_position = session.execute(select(PredictionPosition)).scalar_one()
        assert submission.order.status == PredictionMarketOrderStatus.FILLED
        assert settlement.gross_payout == Decimal("10.00000000")
        assert settlement.fees == Decimal("0.16800000")
        assert settlement.realized_pl == Decimal("3.83200000")
        assert saved_position.status == PredictionMarketPositionStatus.SETTLED
        assert report.status == ReconciliationStatus.MATCHED
        assert report.discrepancies == []
        event_kinds = [
            event.kind for event in session.execute(select(PredictionEvidenceEvent)).scalars()
        ]
        assert PredictionMarketEvidenceKind.SETTLEMENT_RECORDED in event_kinds
        assert PredictionMarketEvidenceKind.POSITION_RECONCILED in event_kinds


def test_paper_engine_reconciliation_detects_settlement_money_drift() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)

    with Session(engine) as session:
        paper = PredictionMarketPaperEngine(session)
        contract = paper.upsert_contract_snapshot(contract_snapshot(now), now=now)
        intent = paper.create_order_intent(
            PredictionOrderRequest(
                contract_id=contract.id,
                strategy="fixture_prediction_strategy",
                side=PredictionMarketSide.YES,
                quantity=Decimal("10"),
                limit_price=Decimal("0.60"),
                idempotency_key="settlement-money-drift",
            ),
            now=now,
        )
        submission = paper.submit_order(
            intent.id,
            PredictionFillModel(
                available_quantity=Decimal("10"),
                latency_ms=500,
                execution_price=Decimal("0.60"),
            ),
            now=now + timedelta(seconds=1),
        )
        assert submission.position is not None
        settlement = paper.settle_position(
            submission.position.id,
            Decimal("1"),
            now=now + timedelta(minutes=20),
        )
        settlement.realized_pl = Decimal("0")
        settlement.fees = Decimal("0")

        report = paper.reconcile_paper_ledger(now=now + timedelta(minutes=21))
        session.commit()

        assert report.status == ReconciliationStatus.DISCREPANCY
        reasons = {discrepancy["reason"] for discrepancy in report.discrepancies}
        assert "settlement_realized_pl_mismatch" in reasons
        assert "settlement_fee_mismatch" in reasons
        assert "settlement_raw_realized_pl_mismatch" in reasons
        assert "settlement_raw_fee_mismatch" in reasons


def contract_snapshot(now: datetime) -> PredictionContractSnapshot:
    return PredictionContractSnapshot(
        venue=PredictionMarketVenue.KALSHI,
        event_ticker="KXBTCD-26JUN25",
        market_title="Bitcoin above test level on Jun 25",
        contract_ticker="KXBTCD-26JUN25-B62500",
        contract_title="Bitcoin above 62500",
        category="crypto",
        status=PredictionMarketStatus.OPEN,
        yes_bid_price=Decimal("0.59"),
        yes_ask_price=Decimal("0.60"),
        no_bid_price=Decimal("0.40"),
        no_ask_price=Decimal("0.41"),
        closes_at=now + timedelta(hours=1),
        expiration_at=now + timedelta(hours=1),
        raw_payload={"source": "fixture"},
    )
