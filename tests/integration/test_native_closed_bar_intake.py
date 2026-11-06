from sqlalchemy import select

from aurex.db.models import PaperOrder
from aurex.domain.enums import SignalStatus
from aurex.signal_gateway.native_bars import bind_native_signal_to_bar, prepare_native_closed_bar
from aurex.signal_gateway.service import SignalIntakeService
from tests.integration.test_native_signal_intake import NOW, native_payload
from tests.integration.test_native_signal_intake import eligible_fixture as eligible_fixture
from tests.integration.test_native_signal_intake import session as session
from tests.integration.test_native_signal_intake import settings as settings
from tests.unit.test_native_closed_bars import SMALL, bars


def prepared():
    frame = prepare_native_closed_bar(bars(), now=NOW, feed_id="fixture", parameters=SMALL)
    return bind_native_signal_to_bar(native_payload(), frame)


def test_closed_bar_preflight_does_not_revive_a_retired_strategy(session, settings):
    result = SignalIntakeService(session, settings).ingest_native(prepared())
    assert result.signal.status == SignalStatus.RISK_REJECTED
    assert "lifecycle" in result.signal.rejection_reason
    assert session.scalars(select(PaperOrder)).all() == []


def test_fixture_bound_bar_still_uses_costed_risk_and_duplicate_controls(
    session, settings, eligible_fixture
):
    # Synthetic approval exists only in this disposable database, never in Aurex's ledger.
    service = SignalIntakeService(session, settings)
    first = service.ingest_native(prepared())
    assert first.signal.status == SignalStatus.PAPER_EXECUTED
    assert service.ingest_native(prepared()).signal.status == SignalStatus.DUPLICATE_REJECTED
    assert len(session.scalars(select(PaperOrder)).all()) == 1
