from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from aurex.db.base import Base
from aurex.db.models import (
    Account,
    PredictionContract,
    PredictionEvidenceEvent,
    PredictionFill,
    PredictionMarket,
    PredictionOrder,
    PredictionOrderIntent,
    PredictionPosition,
    PredictionReconciliationReport,
    PredictionSettlement,
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
)
from aurex.prediction_market.calculations import (
    calculate_binary_gross_payout,
    calculate_binary_settlement_pl,
    estimate_binary_contract_fee,
)


def test_prediction_market_ledger_persists_full_paper_lifecycle() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    quantity = Decimal("10")
    entry_price = Decimal("0.60")
    fees = estimate_binary_contract_fee(quantity, entry_price)
    gross_payout = calculate_binary_gross_payout(
        PredictionMarketSide.YES,
        quantity,
        Decimal("1"),
    )
    realized_pl = calculate_binary_settlement_pl(
        PredictionMarketSide.YES,
        quantity,
        entry_price,
        Decimal("1"),
        fees,
    )

    with Session(engine) as session:
        account = Account(
            name="prediction-paper",
            mode="paper",
            currency="USD",
            starting_equity=Decimal("1000"),
            current_equity=Decimal("1000"),
        )
        market = PredictionMarket(
            venue=PredictionMarketVenue.KALSHI,
            event_ticker="KXBTCD-26JUN25",
            title="Bitcoin above test level on Jun 25",
            category="crypto",
            status=PredictionMarketStatus.OPEN,
            closes_at=now + timedelta(hours=1),
            raw_payload={"source": "fixture"},
            first_seen_at=now,
            last_seen_at=now,
        )
        contract = PredictionContract(
            market=market,
            venue=PredictionMarketVenue.KALSHI,
            contract_ticker="KXBTCD-26JUN25-B62500",
            title="Bitcoin above 62500",
            status=PredictionMarketStatus.OPEN,
            yes_bid_price=Decimal("0.59"),
            yes_ask_price=Decimal("0.60"),
            no_bid_price=Decimal("0.40"),
            no_ask_price=Decimal("0.41"),
            expiration_at=now + timedelta(hours=1),
            raw_payload={"source": "fixture"},
            first_seen_at=now,
            last_seen_at=now,
        )
        intent = PredictionOrderIntent(
            contract=contract,
            strategy="mkt_whale_research_candidate",
            side=PredictionMarketSide.YES,
            action=PredictionMarketOrderAction.BUY,
            order_type=PredictionMarketOrderType.LIMIT,
            quantity=quantity,
            limit_price=entry_price,
            max_cost=Decimal("6.16800000"),
            expected_edge=Decimal("0.050000"),
            confidence=Decimal("0.650000"),
            status=PredictionMarketOrderStatus.CREATED,
            idempotency_key="fixture-prediction-intent",
            intent_snapshot={"paper_only": True, "source": "mkt_research_candidate"},
            created_intent_at=now,
            expires_at=now + timedelta(minutes=2),
        )
        order = PredictionOrder(
            order_intent=intent,
            external_order_id="paper-prediction-order-1",
            status=PredictionMarketOrderStatus.FILLED,
            side=PredictionMarketSide.YES,
            action=PredictionMarketOrderAction.BUY,
            quantity=quantity,
            filled_quantity=quantity,
            limit_price=entry_price,
            average_fill_price=entry_price,
            fees=fees,
            submitted_at=now,
            external_updated_at=now,
            raw_payload={"paper_fill": True},
        )
        fill = PredictionFill(
            order=order,
            external_fill_id="paper-prediction-fill-1",
            side=PredictionMarketSide.YES,
            action=PredictionMarketOrderAction.BUY,
            quantity=quantity,
            price=entry_price,
            fees=fees,
            filled_at=now,
            raw_payload={"paper_fill": True},
        )
        position = PredictionPosition(
            account=account,
            contract=contract,
            side=PredictionMarketSide.YES,
            quantity=quantity,
            average_entry_price=entry_price,
            realized_pl=realized_pl,
            fees=fees,
            status=PredictionMarketPositionStatus.SETTLED,
            opened_at=now,
            closed_at=now + timedelta(minutes=45),
            raw_payload={"paper_only": True},
        )
        settlement = PredictionSettlement(
            contract=contract,
            position=position,
            settlement_value=Decimal("1"),
            gross_payout=gross_payout,
            realized_pl=realized_pl,
            fees=fees,
            settled_at=now + timedelta(minutes=45),
            raw_payload={"source": "fixture"},
        )
        reconciliation = PredictionReconciliationReport(
            status=ReconciliationStatus.MATCHED,
            summary="Prediction paper ledger reconciles with fixture fill and settlement.",
            discrepancies=[],
            venue_snapshot={"orders": 1, "fills": 1, "settlements": 1},
            aurex_snapshot={"positions": 1, "realized_pl": str(realized_pl)},
            reconciled_at=now + timedelta(minutes=46),
        )
        evidence = PredictionEvidenceEvent(
            kind=PredictionMarketEvidenceKind.SETTLEMENT_RECORDED,
            entity_type="prediction_settlement",
            entity_id="fixture-settlement",
            strategy="mkt_whale_research_candidate",
            contract_ticker=contract.contract_ticker,
            evidence_hash="a" * 64,
            payload={
                "settlement_value": "1",
                "gross_payout": str(gross_payout),
                "realized_pl": str(realized_pl),
                "fees": str(fees),
            },
            occurred_at=now + timedelta(minutes=46),
        )

        session.add_all(
            [
                account,
                market,
                contract,
                intent,
                order,
                fill,
                position,
                settlement,
                reconciliation,
                evidence,
            ]
        )
        session.commit()

        saved_contract = session.execute(select(PredictionContract)).scalar_one()
        saved_order = session.execute(select(PredictionOrder)).scalar_one()
        saved_settlement = session.execute(select(PredictionSettlement)).scalar_one()
        saved_reconciliation = session.execute(select(PredictionReconciliationReport)).scalar_one()
        saved_evidence = session.execute(select(PredictionEvidenceEvent)).scalar_one()

        assert saved_contract.market.event_ticker == "KXBTCD-26JUN25"
        assert saved_order.status == PredictionMarketOrderStatus.FILLED
        assert saved_order.fills[0].fees == Decimal("0.16800000")
        assert saved_settlement.realized_pl == Decimal("3.83200000")
        assert saved_settlement.position.status == PredictionMarketPositionStatus.SETTLED
        assert saved_reconciliation.status == ReconciliationStatus.MATCHED
        assert saved_evidence.kind == PredictionMarketEvidenceKind.SETTLEMENT_RECORDED
