import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from time import perf_counter

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aurex.backtest_engine.eligibility import paper_backtest_eligibility
from aurex.backtest_engine.service import strategy_parameter_evidence_snapshot
from aurex.config.settings import Settings
from aurex.db.base import utc_now
from aurex.db.models import (
    Account,
    BrokerFill,
    BrokerOrder,
    OrderIntent,
    PaperOrder,
    PaperTrade,
    RiskProfile,
    Signal,
    SignalEvent,
    StrategyConfig,
    Symbol,
)
from aurex.domain.enums import SignalStatus
from aurex.execution_engine.paper import PaperExecutionEngine
from aurex.market_state.service import MarketStateEngine
from aurex.observability.system_events import SystemEventRecorder
from aurex.risk_engine.service import (
    DEFAULT_ACCOUNT_NAME,
    DEFAULT_RISK_PROFILE_NAME,
    RiskEngine,
    risk_profile_snapshot,
)
from aurex.signal_gateway.schemas import (
    NativeSignalPayload,
    SignalContractResponse,
    SignalPayload,
    TradingViewAlertSetupResponse,
    TradingViewRunbookResponse,
    TradingViewRunbookStep,
    TradingViewSignalPayload,
    TradingViewSignalPreflightResponse,
    TradingViewVerificationCheck,
    TradingViewVerificationResponse,
)
from aurex.signal_gateway.tradingview_delivery import (
    TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL,
    tradingview_source_networks_sha256,
)
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES, default_allowed_regime_values
from aurex.strategy_engine.service import strategy_config_snapshot

BASE_REQUIRED_PAYLOAD_FIELDS = [
    "source",
    "strategy",
    "symbol",
    "timeframe",
    "direction",
    "entry_price",
    "stop_loss",
    "take_profit",
    "market_regime",
    "timestamp",
]
PROVENANCE_PAYLOAD_FIELDS = ["strategy_version", "settings_fingerprint"]
PREFLIGHT_ACCOUNT_ID = "preflight-account"
PREFLIGHT_RISK_PROFILE_ID = "preflight-risk-profile"
PREFLIGHT_SIGNAL_ID = "preflight-signal"


@dataclass(frozen=True)
class SignalIngestResult:
    signal: Signal
    is_duplicate: bool
    processing_duration_ms: Decimal
    within_processing_budget: bool


@dataclass(frozen=True)
class WebhookDeliveryContext:
    authentication_status: str
    authentication_transport: str
    request_method: str
    request_path: str
    content_type: str | None
    body_sha256: str
    body_size_bytes: int
    remote_ip: str | None
    user_agent: str | None
    origin_status: str
    source_network_configuration_status: str
    source_networks: tuple[str, ...]
    source_networks_sha256: str
    source_networks_authority_url: str

    def evidence_snapshot(self) -> dict:
        evidence = {
            "authentication_status": self.authentication_status,
            "authentication_transport": self.authentication_transport,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "content_type": self.content_type,
            "body_sha256": self.body_sha256,
            "body_size_bytes": self.body_size_bytes,
            "remote_ip": self.remote_ip,
            "user_agent": self.user_agent,
            "origin_status": self.origin_status,
            "source_network_configuration_status": (
                self.source_network_configuration_status
            ),
            "source_networks": list(self.source_networks),
            "source_networks_sha256": self.source_networks_sha256,
            "source_networks_authority_url": self.source_networks_authority_url,
        }
        evidence["evidence_hash"] = sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return evidence


class SignalIntakeService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def ingest_tradingview(
        self,
        payload: TradingViewSignalPayload,
        *,
        delivery_context: WebhookDeliveryContext | None = None,
    ) -> SignalIngestResult:
        payload = TradingViewSignalPayload.model_validate(payload.model_dump())
        return self._ingest(payload, delivery_context=delivery_context)

    def ingest_native(
        self, payload: NativeSignalPayload, *, commit: bool = True
    ) -> SignalIngestResult:
        """Use the same paper/risk path without fabricating TradingView provenance."""
        if self.settings.live_trading_enabled or self.settings.live_execution_adapter != "disabled":
            raise ValueError("Native paper intake requires live execution to remain disabled")
        if not commit and not self.session.in_transaction():
            raise ValueError("Caller-managed native intake requires an active transaction")
        if not commit:
            connection = self.session.connection()
            # SQLite's legacy driver can have an ORM transaction but no BEGIN yet.
            # Releasing a first SAVEPOINT in that state would commit the signal.
            if connection.dialect.name == "sqlite" and not (
                connection.connection.driver_connection.in_transaction
            ):
                raise ValueError("Caller-managed native intake requires a database transaction")
        payload = NativeSignalPayload.model_validate(payload.model_dump())
        return self._ingest(payload, delivery_context=None, commit=commit)

    def _ingest(
        self,
        payload: SignalPayload,
        *,
        delivery_context: WebhookDeliveryContext | None,
        commit: bool = True,
    ) -> SignalIngestResult:
        started_at = perf_counter()
        received_at = utc_now()
        normalized_symbol = normalize_symbol(payload.symbol)
        raw_payload = payload.model_dump(mode="json")
        normalized_payload = {
            **raw_payload,
            "symbol": normalized_symbol,
            "source": payload.source.lower(),
        }
        idempotency_key = build_idempotency_key(payload, normalized_symbol)

        symbol = self._get_or_create_symbol(normalized_symbol)
        duplicate_of = self._find_duplicate(payload, normalized_symbol, idempotency_key)

        if duplicate_of is not None:
            return self._record_duplicate(
                payload=payload,
                symbol=symbol,
                normalized_symbol=normalized_symbol,
                idempotency_key=idempotency_key,
                raw_payload=raw_payload,
                normalized_payload=normalized_payload,
                received_at=received_at,
                duplicate_of=duplicate_of,
                started_at=started_at,
                delivery_context=delivery_context,
                commit=commit,
            )

        try:
            with self.session.begin_nested():
                signal = self._create_signal(
                    payload=payload,
                    symbol=symbol,
                    normalized_symbol=normalized_symbol,
                    idempotency_key=idempotency_key,
                    raw_payload=raw_payload,
                    normalized_payload=normalized_payload,
                    received_at=received_at,
                    status=SignalStatus.VALIDATED,
                    rejection_reason=None,
                    duplicate_of_signal_id=None,
                )
        except IntegrityError:
            duplicate_of = self._find_exact_duplicate(idempotency_key)
            if duplicate_of is None:
                raise
            return self._record_duplicate(
                payload=payload,
                symbol=symbol,
                normalized_symbol=normalized_symbol,
                idempotency_key=idempotency_key,
                raw_payload=raw_payload,
                normalized_payload=normalized_payload,
                received_at=received_at,
                duplicate_of=duplicate_of,
                started_at=started_at,
                delivery_context=delivery_context,
                commit=commit,
            )

        self._add_event(
            signal,
            SignalStatus.RECEIVED,
            "Signal received",
            metadata_json=delivery_event_metadata(delivery_context),
        )
        self._add_event(signal, SignalStatus.VALIDATED, "Signal validated")
        MarketStateEngine(self.session).enrich_signal(signal)
        SystemEventRecorder(self.session).info(
            "signal_gateway",
            "Signal validated",
            {
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "strategy": signal.strategy,
                "direction": signal.direction.value,
            },
            occurred_at=received_at,
        )
        risk_evaluation = RiskEngine(self.session, self.settings).evaluate_signal(
            signal, now=received_at
        )
        if risk_evaluation.decision.approved:
            PaperExecutionEngine(self.session, self.settings).execute_approved_signal(
                signal,
                risk_evaluation.decision,
                now=received_at,
            )
        signal.processed_at = utc_now()
        self._finish_intake(signal, commit=commit)
        return self._ingest_result(signal, False, started_at)

    def _record_duplicate(
        self,
        *,
        payload: SignalPayload,
        symbol: Symbol,
        normalized_symbol: str,
        idempotency_key: str,
        raw_payload: dict,
        normalized_payload: dict,
        received_at,
        duplicate_of: Signal,
        started_at: float,
        delivery_context: WebhookDeliveryContext | None,
        commit: bool,
    ) -> SignalIngestResult:
        signal = self._create_signal(
            payload=payload,
            symbol=symbol,
            normalized_symbol=normalized_symbol,
            idempotency_key=idempotency_key,
            raw_payload=raw_payload,
            normalized_payload=normalized_payload,
            received_at=received_at,
            status=SignalStatus.DUPLICATE_REJECTED,
            rejection_reason="Duplicate signal within configured cooldown window",
            duplicate_of_signal_id=duplicate_of.id,
        )
        self._add_event(
            signal,
            SignalStatus.RECEIVED,
            "Signal received",
            metadata_json=delivery_event_metadata(delivery_context),
        )
        self._add_event(signal, SignalStatus.DUPLICATE_REJECTED, "Duplicate signal rejected")
        SystemEventRecorder(self.session).warning(
            "signal_gateway",
            "Duplicate signal rejected",
            {
                "signal_id": signal.id,
                "duplicate_of_signal_id": duplicate_of.id,
                "symbol": signal.symbol,
                "strategy": signal.strategy,
            },
            occurred_at=received_at,
        )
        signal.processed_at = utc_now()
        self._finish_intake(signal, commit=commit)
        return self._ingest_result(signal, True, started_at)

    def _finish_intake(self, signal: Signal, *, commit: bool) -> None:
        if commit:
            self.session.commit()
            self.session.refresh(signal)
        else:
            self.session.flush()

    def _ingest_result(
        self,
        signal: Signal,
        is_duplicate: bool,
        started_at: float,
    ) -> SignalIngestResult:
        duration_ms = Decimal(str((perf_counter() - started_at) * 1000)).quantize(
            Decimal("0.001")
        )
        return SignalIngestResult(
            signal=signal,
            is_duplicate=is_duplicate,
            processing_duration_ms=duration_ms,
            within_processing_budget=(
                duration_ms <= Decimal(self.settings.webhook_processing_budget_ms)
            ),
        )

    def _get_or_create_symbol(self, normalized_symbol: str) -> Symbol:
        existing = self.session.execute(
            select(Symbol).where(Symbol.symbol == normalized_symbol)
        ).scalar_one_or_none()

        if existing is not None:
            return existing

        symbol = Symbol(symbol=normalized_symbol)
        self.session.add(symbol)
        self.session.flush()
        return symbol

    def _find_duplicate(
        self,
        payload: SignalPayload,
        normalized_symbol: str,
        idempotency_key: str,
    ) -> Signal | None:
        exact_duplicate = self._find_exact_duplicate(idempotency_key)

        if exact_duplicate is not None:
            return exact_duplicate

        if self.settings.duplicate_cooldown_minutes == 0:
            return None

        cooldown_start = payload.timestamp - timedelta(
            minutes=self.settings.duplicate_cooldown_minutes
        )
        candidates = self.session.execute(
            select(Signal)
            .where(
                and_(
                    Signal.source == payload.source,
                    Signal.symbol == normalized_symbol,
                    Signal.strategy == payload.strategy,
                    Signal.timeframe == payload.timeframe,
                    Signal.direction == payload.direction,
                    Signal.source_timestamp >= cooldown_start,
                    Signal.source_timestamp <= payload.timestamp,
                    Signal.status != SignalStatus.DUPLICATE_REJECTED,
                )
            )
            .order_by(Signal.source_timestamp.desc())
        ).scalars()
        return next(
            (
                signal
                for signal in candidates
                if signal.strategy_version == payload.strategy_version
                and signal.settings_fingerprint == payload.settings_fingerprint
            ),
            None,
        )

    def _find_exact_duplicate(self, idempotency_key: str) -> Signal | None:
        return self.session.execute(
            select(Signal)
            .where(
                Signal.idempotency_key == idempotency_key,
                Signal.status != SignalStatus.DUPLICATE_REJECTED,
            )
            .order_by(Signal.received_at.asc())
            .limit(1)
        ).scalar_one_or_none()

    def _create_signal(
        self,
        payload: SignalPayload,
        symbol: Symbol,
        normalized_symbol: str,
        idempotency_key: str,
        raw_payload: dict,
        normalized_payload: dict,
        received_at,
        status: SignalStatus,
        rejection_reason: str | None,
        duplicate_of_signal_id: str | None,
    ) -> Signal:
        signal = Signal(
            source=payload.source,
            strategy=payload.strategy,
            symbol_ref=symbol,
            symbol=normalized_symbol,
            timeframe=payload.timeframe,
            direction=payload.direction,
            entry_price=payload.entry_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            market_regime=payload.market_regime,
            status=status,
            idempotency_key=idempotency_key,
            duplicate_of_signal_id=duplicate_of_signal_id,
            raw_payload=raw_payload,
            normalized_payload=normalized_payload,
            rejection_reason=rejection_reason,
            source_timestamp=payload.timestamp,
            received_at=received_at,
            processed_at=None,
        )
        self.session.add(signal)
        self.session.flush()
        return signal

    def _add_event(
        self,
        signal: Signal,
        status: SignalStatus,
        message: str,
        *,
        metadata_json: dict | None = None,
    ) -> None:
        self.session.add(
            SignalEvent(
                signal=signal,
                status=status,
                message=message,
                metadata_json=metadata_json or {},
            )
        )


def delivery_event_metadata(delivery_context: WebhookDeliveryContext | None) -> dict:
    if delivery_context is None:
        return {}
    return {"webhook_delivery": delivery_context.evidence_snapshot()}


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace(" ", "")


def build_idempotency_key(payload: SignalPayload, normalized_symbol: str) -> str:
    raw_key = "|".join(
        [
            payload.source.lower(),
            payload.strategy,
            payload.strategy_version or "",
            payload.settings_fingerprint or "",
            normalized_symbol,
            payload.timeframe,
            payload.direction.value,
            payload.timestamp.isoformat(),
        ]
    )
    return sha256(raw_key.encode("utf-8")).hexdigest()


def signal_contract_preflight(
    session: Session,
    *,
    strategy: str,
    symbol: str,
) -> SignalContractResponse:
    normalized_strategy = strategy.strip()
    normalized_symbol = normalize_symbol(symbol)
    backtest_gate = paper_backtest_eligibility(
        session,
        strategy=normalized_strategy,
        symbol=normalized_symbol,
    )
    evidence = backtest_gate.evidence_snapshot or {}
    parameter_evidence = evidence.get("strategy_parameter_evidence")
    if not isinstance(parameter_evidence, dict):
        parameter_evidence = strategy_parameter_evidence_snapshot(normalized_strategy, {})

    known_strategy = bool(parameter_evidence.get("known_strategy"))
    reasons = [str(reason) for reason in evidence.get("reasons") or [backtest_gate.reason]]
    settings_fingerprint = evidence.get("strategy_parameter_fingerprint")
    strategy_version = evidence.get("strategy_version")
    status = "READY" if backtest_gate.approved else "BLOCKED"
    if backtest_gate.approved and not known_strategy:
        status = "READY_UNTRACKED"

    required_payload_fields = list(BASE_REQUIRED_PAYLOAD_FIELDS)
    if known_strategy:
        required_payload_fields.extend(PROVENANCE_PAYLOAD_FIELDS)

    return SignalContractResponse(
        strategy=normalized_strategy,
        symbol=normalized_symbol,
        status=status,
        ready_for_paper=backtest_gate.approved,
        reason=backtest_gate.reason,
        reasons=reasons,
        accepted_backtest_run_id=backtest_gate.backtest_run_id,
        strategy_version=strategy_version if isinstance(strategy_version, str) else None,
        settings_fingerprint=(
            settings_fingerprint if isinstance(settings_fingerprint, str) else None
        ),
        settings_fingerprint_preview=short_contract_hash(settings_fingerprint),
        known_strategy=known_strategy,
        requires_provenance=known_strategy,
        required_parameters=[
            str(item) for item in parameter_evidence.get("required_parameters") or []
        ],
        missing_parameters=[
            str(item) for item in parameter_evidence.get("missing_parameters") or []
        ],
        required_payload_fields=required_payload_fields,
        optional_payload_fields=[],
        example_payload=signal_contract_example_payload(
            normalized_strategy,
            normalized_symbol,
            strategy_version if isinstance(strategy_version, str) else None,
            settings_fingerprint if isinstance(settings_fingerprint, str) else None,
            known_strategy,
        ),
        next_actions=signal_contract_next_actions(backtest_gate.approved, known_strategy, reasons),
        evidence_snapshot=evidence,
    )


def tradingview_signal_preflight(
    session: Session,
    settings: Settings,
    payload: TradingViewSignalPayload,
) -> TradingViewSignalPreflightResponse:
    normalized_symbol = normalize_symbol(payload.symbol)
    raw_payload = payload.model_dump(mode="json")
    normalized_payload = {
        **raw_payload,
        "symbol": normalized_symbol,
        "source": payload.source.lower(),
    }
    contract = signal_contract_preflight(
        session,
        strategy=payload.strategy,
        symbol=normalized_symbol,
    )
    idempotency_key = build_idempotency_key(payload, normalized_symbol)
    duplicate_of = SignalIntakeService(session, settings)._find_duplicate(
        payload,
        normalized_symbol,
        idempotency_key,
    )
    if duplicate_of is not None:
        return TradingViewSignalPreflightResponse(
            status="DUPLICATE_BLOCKED",
            would_execute_paper=False,
            reason="Duplicate signal within configured cooldown window",
            reasons=["duplicate_signal_within_cooldown"],
            idempotency_key=idempotency_key,
            duplicate_status="DUPLICATE",
            duplicate_signal_id=duplicate_of.id,
            duplicate_cooldown_minutes=settings.duplicate_cooldown_minutes,
            expected_webhook_status=SignalStatus.DUPLICATE_REJECTED,
            expected_webhook_http_status=409,
            normalized_payload=normalized_payload,
            contract=contract,
            reward_risk=None,
            risk_amount=None,
            position_size=None,
            account_equity=None,
            rules_snapshot={},
            mutates_ledger=False,
            next_actions=[
                "Do not resend this alert unless it is a genuinely new TradingView event.",
                "Change the source timestamp only when the market setup is actually new.",
            ],
        )

    account, risk_profile = preflight_account_and_risk_profile(session)
    strategy_config = preflight_strategy_config(session, payload.strategy)
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
    signal = preflight_signal(
        payload=payload,
        normalized_symbol=normalized_symbol,
        idempotency_key=idempotency_key,
        raw_payload=raw_payload,
        normalized_payload=normalized_payload,
    )
    evaluated_at = utc_now()
    rule_evaluation = RiskEngine(session)._evaluate_rules(
        signal=signal,
        account=account,
        risk_profile=risk_profile,
        strategy_config=strategy_config,
        effective_risk_per_trade=effective_risk_per_trade,
        effective_minimum_reward_risk=effective_minimum_reward_risk,
        now=evaluated_at,
    )
    rules_snapshot = {
        **risk_profile_snapshot(risk_profile),
        "strategy_config": strategy_config_snapshot(strategy_config),
        "effective_risk_per_trade": str(effective_risk_per_trade),
        "effective_minimum_reward_risk": str(effective_minimum_reward_risk),
        **(rule_evaluation.rules_snapshot or {}),
    }
    return TradingViewSignalPreflightResponse(
        status="PASS" if rule_evaluation.approved else "BLOCKED",
        would_execute_paper=rule_evaluation.approved,
        reason=rule_evaluation.reason,
        reasons=[] if rule_evaluation.approved else [rule_evaluation.reason],
        idempotency_key=idempotency_key,
        duplicate_status="CLEAR",
        duplicate_signal_id=None,
        duplicate_cooldown_minutes=settings.duplicate_cooldown_minutes,
        expected_webhook_status=(
            SignalStatus.PAPER_EXECUTED
            if rule_evaluation.approved
            else SignalStatus.RISK_REJECTED
        ),
        expected_webhook_http_status=202,
        normalized_payload=normalized_payload,
        contract=contract,
        reward_risk=rule_evaluation.reward_risk,
        risk_amount=rule_evaluation.risk_amount,
        position_size=rule_evaluation.position_size,
        account_equity=account.current_equity,
        rules_snapshot=rules_snapshot,
        mutates_ledger=False,
        next_actions=tradingview_signal_preflight_next_actions(rule_evaluation.reason),
    )


def tradingview_signal_runbook(
    session: Session,
    settings: Settings,
    *,
    strategy: str,
    symbol: str,
) -> TradingViewRunbookResponse:
    contract = signal_contract_preflight(session, strategy=strategy, symbol=symbol)
    live_step = TradingViewRunbookStep(
        step_key="live_boundary",
        title="Keep live trading disabled",
        status="PASS" if not settings.live_trading_enabled else "BLOCKED",
        evidence=(
            "live_trading_enabled=false"
            if not settings.live_trading_enabled
            else "live_trading_enabled=true"
        ),
        next_action=(
            "Keep live mode disabled during TradingView paper testing."
            if not settings.live_trading_enabled
            else "Disable live trading before any TradingView paper-test run."
        ),
    )
    contract_step = TradingViewRunbookStep(
        step_key="accepted_backtest_contract",
        title="Confirm accepted backtest contract",
        status="PASS" if contract.ready_for_paper else "BLOCKED",
        evidence=f"{contract.reason}; backtest {contract.accepted_backtest_run_id or 'none'}",
        next_action=(
            "Use the generated payload and run no-write preflight."
            if contract.ready_for_paper
            else (contract.next_actions[0] if contract.next_actions else "Fix contract blockers.")
        ),
    )
    preflight_status = (
        "NOT_RUN"
        if contract.ready_for_paper and not settings.live_trading_enabled
        else "BLOCKED"
    )
    preflight_step = TradingViewRunbookStep(
        step_key="payload_preflight",
        title="Run no-write payload preflight",
        status=preflight_status,
        evidence="No payload preflight result is persisted; run the preflight control each test.",
        next_action=(
            "Paste the generated alert JSON and run Preflight alert."
            if preflight_status == "NOT_RUN"
            else "Unblock the contract and live boundary before payload preflight."
        ),
    )
    webhook_step = TradingViewRunbookStep(
        step_key="webhook_rehearsal",
        title="Send only after preflight PASS",
        status="NOT_RUN" if preflight_status == "NOT_RUN" else "BLOCKED",
        evidence="Expected webhook status is available only after payload preflight.",
        next_action=(
            "Send the TradingView alert only when preflight expects PAPER_EXECUTED."
            if preflight_status == "NOT_RUN"
            else "Run and pass no-write payload preflight first."
        ),
    )
    evidence_step = TradingViewRunbookStep(
        step_key="paper_evidence_collection",
        title="Collect paper evidence",
        status="NOT_RUN",
        evidence="Paper/demo evidence must still be collected after webhook execution.",
        next_action="After a paper trade opens, monitor outcome and collect evidence exports.",
    )
    steps = [live_step, contract_step, preflight_step, webhook_step, evidence_step]
    current_step = next((step for step in steps if step.status != "PASS"), None)
    completed = sum(1 for step in steps if step.status == "PASS")
    total = len(steps)
    ready_to_preflight = (
        not settings.live_trading_enabled
        and contract.ready_for_paper
        and preflight_step.status == "NOT_RUN"
    )
    status = (
        "LIVE_GUARD_BLOCKED"
        if settings.live_trading_enabled
        else "READY_TO_PREFLIGHT"
        if ready_to_preflight
        else "BLOCKED"
    )
    return TradingViewRunbookResponse(
        strategy=contract.strategy,
        symbol=contract.symbol,
        status=status,
        ready_to_preflight=ready_to_preflight,
        ready_to_send_webhook=False,
        live_trading_enabled=settings.live_trading_enabled,
        contract=contract,
        steps=steps,
        current_step=current_step,
        completed_step_count=completed,
        total_step_count=total,
        progress_pct=Decimal(completed * 100) / Decimal(total),
        next_action=(
            current_step.next_action
            if current_step is not None
            else "Review paper evidence before any live-readiness work."
        ),
        webhook_endpoint="/webhooks/tradingview",
        preflight_endpoint="/signals/preflight/tradingview",
        required_header="X-Aurex-Webhook-Secret",
        mutates_ledger=False,
    )


def tradingview_alert_setup(
    session: Session,
    settings: Settings,
    *,
    strategy: str,
    symbol: str,
) -> TradingViewAlertSetupResponse:
    contract = signal_contract_preflight(session, strategy=strategy, symbol=symbol)
    ready = bool(contract.ready_for_paper and not settings.live_trading_enabled)
    status = (
        "READY_TO_PREFLIGHT"
        if ready
        else "LIVE_GUARD_BLOCKED"
        if settings.live_trading_enabled
        else "BLOCKED"
    )
    next_actions = tradingview_alert_setup_next_actions(contract, settings, ready)
    return TradingViewAlertSetupResponse(
        strategy=contract.strategy,
        symbol=contract.symbol,
        status=status,
        ready_for_alert_preflight=ready,
        live_trading_enabled=settings.live_trading_enabled,
        webhook_endpoint="/webhooks/tradingview",
        webhook_method="POST",
        webhook_url_template=(
            "https://<your-aurex-public-host>/webhooks/tradingview"
            "?secret=<AUREX_WEBHOOK_SECRET>"
        ),
        webhook_secret_transport="query_parameter_for_tradingview_or_header_for_api_clients",
        header_auth_supported=True,
        query_secret_supported=True,
        required_header="X-Aurex-Webhook-Secret",
        preflight_endpoint="/signals/preflight/tradingview",
        verification_endpoint="/signals/tradingview-verification",
        alert_condition=f"Aurex {contract.strategy} / any alert() function call",
        alert_message=contract.example_payload,
        accepted_backtest_run_id=contract.accepted_backtest_run_id,
        strategy_version=contract.strategy_version,
        settings_fingerprint=contract.settings_fingerprint,
        settings_fingerprint_preview=contract.settings_fingerprint_preview,
        required_payload_fields=contract.required_payload_fields,
        next_actions=next_actions,
        security_notes=[
            "Do not put broker credentials or exchange API keys in TradingView alerts.",
            "Use HTTPS for any public webhook URL.",
            "Rotate AUREX_WEBHOOK_SECRET if a webhook URL is shared or exposed.",
            "Run no-write preflight before enabling or re-enabling an alert.",
        ],
        delivery_constraints=[
            "TradingView sends the alert message as the POST body.",
            "Valid JSON alert messages are sent with application/json content type.",
            "TradingView webhook URLs must use port 80 or 443.",
            "TradingView cancels webhook requests that take longer than three seconds.",
            "TradingView webhook delivery can fail occasionally; verify in Aurex after sending.",
        ],
        contract=contract,
        mutates_ledger=False,
    )


def tradingview_alert_setup_next_actions(
    contract: SignalContractResponse,
    settings: Settings,
    ready: bool,
) -> list[str]:
    if settings.live_trading_enabled:
        return [
            "Disable live trading before configuring TradingView paper alerts.",
            "Re-run alert setup after the live boundary is safe.",
        ]
    if not contract.ready_for_paper:
        first_action = (
            contract.next_actions[0]
            if contract.next_actions
            else "Import accepted backtest evidence."
        )
        return [
            first_action,
            "Do not enable the TradingView alert until no-write preflight can pass.",
        ]
    if ready:
        return [
            "Copy the alert message into TradingView and configure the webhook URL template.",
            "Run no-write preflight using the same payload before enabling the alert.",
            (
                "After the first alert fires, verify signal, risk decision, "
                "paper order, and paper trade."
            ),
        ]
    return ["Review the signal contract before configuring TradingView alerts."]


def tradingview_signal_verification(
    session: Session,
    settings: Settings,
    *,
    strategy: str,
    symbol: str,
) -> TradingViewVerificationResponse:
    normalized_symbol = normalize_symbol(symbol)
    latest_signal = session.execute(
        select(Signal)
        .where(
            Signal.source == "tradingview",
            Signal.strategy == strategy,
            Signal.symbol == normalized_symbol,
        )
        .order_by(Signal.received_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_signal is None:
        checks = [
            TradingViewVerificationCheck(
                check_key="latest_signal_received",
                status="NOT_RUN",
                evidence="No TradingView signal found for this strategy and symbol.",
                next_action="Send a preflight-passed TradingView alert to the webhook.",
            )
        ]
        return TradingViewVerificationResponse(
            strategy=strategy,
            symbol=normalized_symbol,
            status="NO_SIGNAL",
            verified=False,
            delivery_verified=False,
            pipeline_verified=False,
            latest_signal_id=None,
            latest_signal_status=None,
            latest_risk_decision_id=None,
            risk_approved=None,
            paper_order_id=None,
            paper_trade_id=None,
            provenance_status="UNKNOWN",
            delivery_auth_status="UNKNOWN",
            delivery_auth_transport=None,
            delivery_origin_status="UNKNOWN",
            delivery_remote_ip=None,
            delivery_evidence_hash=None,
            signal_event_statuses=[],
            missing_event_statuses=[],
            checks=checks,
            next_action=checks[0].next_action,
            mutates_ledger=False,
            live_trading_enabled=settings.live_trading_enabled,
            live_execution_adapter=settings.live_execution_adapter,
        )

    decision = latest_signal.latest_risk_decision
    paper_order = session.execute(
        select(PaperOrder).where(PaperOrder.signal_id == latest_signal.id).limit(1)
    ).scalar_one_or_none()
    paper_trade = None
    if paper_order is not None:
        paper_trade = session.execute(
            select(PaperTrade)
            .where(PaperTrade.paper_order_id == paper_order.id)
            .limit(1)
        ).scalar_one_or_none()
    live_order_intent_ids = list(
        session.execute(
            select(OrderIntent.id).where(OrderIntent.signal_id == latest_signal.id)
        ).scalars()
    )
    broker_order_ids = list(
        session.execute(
            select(BrokerOrder.id)
            .join(OrderIntent, BrokerOrder.order_intent_id == OrderIntent.id)
            .where(OrderIntent.signal_id == latest_signal.id)
        ).scalars()
    )
    broker_fill_ids = list(
        session.execute(
            select(BrokerFill.id)
            .join(BrokerOrder, BrokerFill.broker_order_id == BrokerOrder.id)
            .join(OrderIntent, BrokerOrder.order_intent_id == OrderIntent.id)
            .where(OrderIntent.signal_id == latest_signal.id)
        ).scalars()
    )

    provenance_gate = {}
    if decision is not None:
        provenance_gate = decision.rules_snapshot.get("signal_backtest_provenance_gate") or {}
    provenance_status = verification_provenance_status(provenance_gate)
    signal_events = list(
        session.execute(
            select(SignalEvent)
            .where(SignalEvent.signal_id == latest_signal.id)
            .order_by(SignalEvent.created_at.asc())
        ).scalars()
    )
    recorded_signal_event_statuses = [event.status for event in signal_events]
    delivery = tradingview_delivery_snapshot(signal_events)
    expected_event_statuses = expected_signal_event_statuses(latest_signal.status)
    signal_event_statuses = ordered_recorded_signal_statuses(
        recorded_signal_event_statuses,
        expected_event_statuses,
    )
    missing_event_statuses = [
        status
        for status in expected_event_statuses
        if status not in recorded_signal_event_statuses
    ]
    checks = tradingview_verification_checks(
        latest_signal,
        decision,
        paper_order,
        paper_trade,
        provenance_status,
        signal_event_statuses,
        missing_event_statuses,
        delivery,
        live_order_intent_ids,
        broker_order_ids,
        broker_fill_ids,
        settings.live_trading_enabled,
    )
    delivery_check_keys = {
        "webhook_shared_secret_authenticated",
        "webhook_payload_integrity_recorded",
        "tradingview_source_network_configuration_safe",
        "tradingview_source_ip_matched",
    }
    delivery_verified = all(
        check.status == "PASS" for check in checks if check.check_key in delivery_check_keys
    )
    pipeline_verified = all(
        check.status == "PASS"
        for check in checks
        if check.check_key not in delivery_check_keys
    )
    verified = pipeline_verified and delivery_verified
    status = (
        "VERIFIED"
        if verified
        else "DELIVERY_VERIFIED_PIPELINE_BLOCKED"
        if delivery_verified
        else "PIPELINE_VERIFIED_ORIGIN_UNPROVEN"
        if pipeline_verified
        else "BLOCKED"
    )
    current_check = next((check for check in checks if check.status != "PASS"), None)
    return TradingViewVerificationResponse(
        strategy=strategy,
        symbol=normalized_symbol,
        status=status,
        verified=verified,
        delivery_verified=delivery_verified,
        pipeline_verified=pipeline_verified,
        latest_signal_id=latest_signal.id,
        latest_signal_status=latest_signal.status,
        latest_risk_decision_id=decision.id if decision is not None else None,
        risk_approved=decision.approved if decision is not None else None,
        paper_order_id=paper_order.id if paper_order is not None else None,
        paper_trade_id=paper_trade.id if paper_trade is not None else None,
        provenance_status=provenance_status,
        delivery_auth_status=str(delivery.get("authentication_status") or "MISSING"),
        delivery_auth_transport=delivery.get("authentication_transport"),
        delivery_origin_status=str(delivery.get("origin_status") or "MISSING"),
        delivery_remote_ip=delivery.get("remote_ip"),
        delivery_evidence_hash=delivery.get("evidence_hash"),
        delivery_source_network_configuration_status=str(
            delivery.get("source_network_configuration_status") or "MISSING"
        ),
        delivery_source_networks=list(delivery.get("source_networks") or []),
        delivery_source_networks_sha256=delivery.get("source_networks_sha256"),
        delivery_source_networks_authority_url=delivery.get(
            "source_networks_authority_url"
        ),
        signal_event_statuses=signal_event_statuses,
        missing_event_statuses=missing_event_statuses,
        checks=checks,
        next_action=(
            current_check.next_action
            if current_check is not None
            else "External TradingView paper path verified. Monitor and preserve the evidence."
        ),
        mutates_ledger=False,
        live_trading_enabled=settings.live_trading_enabled,
        live_execution_adapter=settings.live_execution_adapter,
        latest_signal_source_timestamp=latest_signal.source_timestamp,
        latest_signal_received_at=latest_signal.received_at,
        latest_signal_idempotency_key=latest_signal.idempotency_key,
        latest_signal_strategy_version=latest_signal.strategy_version,
        latest_signal_settings_fingerprint=latest_signal.settings_fingerprint,
        latest_signal_timeframe=latest_signal.timeframe,
        delivery_body_sha256=delivery.get("body_sha256"),
        delivery_body_size_bytes=delivery.get("body_size_bytes"),
        delivery_request_method=delivery.get("request_method"),
        delivery_request_path=delivery.get("request_path"),
        delivery_content_type=delivery.get("content_type"),
        delivery_user_agent=delivery.get("user_agent"),
        live_order_intent_ids=live_order_intent_ids,
        broker_order_ids=broker_order_ids,
        broker_fill_ids=broker_fill_ids,
    )


def verification_provenance_status(gate: object) -> str:
    if not isinstance(gate, dict):
        return "MISSING"
    if gate.get("known_strategy") is False:
        return "UNTRACKED"
    if gate.get("blocked"):
        return "BLOCKED"
    return "MATCHED"


def expected_signal_event_statuses(signal_status: SignalStatus) -> list[SignalStatus]:
    if signal_status == SignalStatus.PAPER_EXECUTED:
        return [
            SignalStatus.RECEIVED,
            SignalStatus.VALIDATED,
            SignalStatus.RISK_APPROVED,
            SignalStatus.PAPER_ORDER_CREATED,
            SignalStatus.PAPER_EXECUTED,
        ]
    if signal_status == SignalStatus.RISK_REJECTED:
        return [
            SignalStatus.RECEIVED,
            SignalStatus.VALIDATED,
            SignalStatus.RISK_REJECTED,
        ]
    if signal_status == SignalStatus.DUPLICATE_REJECTED:
        return [SignalStatus.RECEIVED, SignalStatus.DUPLICATE_REJECTED]
    if signal_status == SignalStatus.VALIDATED:
        return [SignalStatus.RECEIVED, SignalStatus.VALIDATED]
    return [SignalStatus.RECEIVED, signal_status]


def ordered_recorded_signal_statuses(
    recorded_statuses: list[SignalStatus],
    expected_statuses: list[SignalStatus],
) -> list[SignalStatus]:
    ordered = [status for status in expected_statuses if status in recorded_statuses]
    ordered.extend(status for status in recorded_statuses if status not in ordered)
    return ordered


def tradingview_delivery_snapshot(signal_events: list[SignalEvent]) -> dict:
    received_event = next(
        (event for event in signal_events if event.status == SignalStatus.RECEIVED),
        None,
    )
    if received_event is None or not isinstance(received_event.metadata_json, dict):
        return {}
    snapshot = received_event.metadata_json.get("webhook_delivery")
    return snapshot if isinstance(snapshot, dict) else {}


def tradingview_delivery_evidence_hash(delivery: dict) -> str:
    hash_payload = {key: value for key, value in delivery.items() if key != "evidence_hash"}
    return sha256(
        json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def tradingview_verification_checks(
    signal: Signal,
    decision,
    paper_order: PaperOrder | None,
    paper_trade: PaperTrade | None,
    provenance_status: str,
    signal_event_statuses: list[SignalStatus],
    missing_event_statuses: list[SignalStatus],
    delivery: dict,
    live_order_intent_ids: list[str],
    broker_order_ids: list[str],
    broker_fill_ids: list[str],
    live_trading_enabled: bool,
) -> list[TradingViewVerificationCheck]:
    authentication_status = delivery.get("authentication_status")
    origin_status = delivery.get("origin_status")
    body_sha256 = delivery.get("body_sha256")
    body_size_bytes = delivery.get("body_size_bytes")
    evidence_hash = delivery.get("evidence_hash")
    content_type = str(delivery.get("content_type") or "").lower()
    request_method = delivery.get("request_method")
    request_path = delivery.get("request_path")
    source_network_configuration_status = delivery.get(
        "source_network_configuration_status"
    )
    source_networks = delivery.get("source_networks")
    source_networks_sha256 = delivery.get("source_networks_sha256")
    source_networks_authority_url = delivery.get("source_networks_authority_url")
    source_network_configuration_safe = bool(
        source_network_configuration_status
        == "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS"
        and isinstance(source_networks, list)
        and source_networks
        and all(isinstance(value, str) for value in source_networks)
        and source_networks_sha256
        == tradingview_source_networks_sha256(source_networks)
        and source_networks_authority_url
        == TRADINGVIEW_WEBHOOK_SOURCE_AUTHORITY_URL
    )
    payload_integrity_recorded = bool(
        isinstance(body_sha256, str)
        and len(body_sha256) == 64
        and isinstance(body_size_bytes, int)
        and body_size_bytes > 0
        and request_method == "POST"
        and request_path == "/webhooks/tradingview"
        and content_type.startswith("application/json")
        and isinstance(evidence_hash, str)
        and evidence_hash == tradingview_delivery_evidence_hash(delivery)
    )
    return [
        TradingViewVerificationCheck(
            check_key="webhook_shared_secret_authenticated",
            status=(
                "PASS" if authentication_status == "SHARED_SECRET_VALIDATED" else "BLOCKED"
            ),
            evidence=f"Webhook authentication status {authentication_status or 'MISSING'}.",
            next_action=(
                "Review webhook payload integrity."
                if authentication_status == "SHARED_SECRET_VALIDATED"
                else "Send the alert through the authenticated TradingView webhook endpoint."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="webhook_payload_integrity_recorded",
            status="PASS" if payload_integrity_recorded else "BLOCKED",
            evidence=(
                f"Body SHA-256 {body_sha256}; {body_size_bytes or 0} bytes; "
                f"{request_method or 'UNKNOWN'} {request_path or 'UNKNOWN'}; "
                f"content type {content_type or 'MISSING'}; receipt hash "
                f"{evidence_hash or 'MISSING'}."
            ),
            next_action=(
                "Review TradingView source IP evidence."
                if payload_integrity_recorded
                else "Send valid JSON by POST so Aurex can preserve exact delivery evidence."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="tradingview_source_network_configuration_safe",
            status="PASS" if source_network_configuration_safe else "BLOCKED",
            evidence=(
                f"Configuration status "
                f"{source_network_configuration_status or 'MISSING'}; "
                f"{len(source_networks) if isinstance(source_networks, list) else 0} "
                f"canonical host networks; hash "
                f"{source_networks_sha256 or 'MISSING'}; authority "
                f"{source_networks_authority_url or 'MISSING'}."
            ),
            next_action=(
                "Review the direct peer match."
                if source_network_configuration_safe
                else (
                    "Configure only the exact IPv4 sender hosts documented by "
                    "TradingView and send a new alert."
                )
            ),
        ),
        TradingViewVerificationCheck(
            check_key="tradingview_source_ip_matched",
            status="PASS" if origin_status == "TRADINGVIEW_SOURCE_IP_MATCHED" else "BLOCKED",
            evidence=(
                f"Direct peer {delivery.get('remote_ip') or 'MISSING'}; "
                f"origin status {origin_status or 'MISSING'}."
            ),
            next_action=(
                "Review the Aurex signal and paper execution timeline."
                if origin_status == "TRADINGVIEW_SOURCE_IP_MATCHED"
                else (
                    "Deliver the alert from TradingView to Aurex directly; a local or "
                    "unattested proxy request cannot prove platform origin."
                )
            ),
        ),
        TradingViewVerificationCheck(
            check_key="latest_signal_received",
            status="PASS",
            evidence=f"Signal {signal.id} status {signal.status}.",
            next_action="Review risk decision for the latest signal.",
        ),
        TradingViewVerificationCheck(
            check_key="live_trading_disabled",
            status="PASS" if not live_trading_enabled else "BLOCKED",
            evidence=f"Live trading enabled is {live_trading_enabled}.",
            next_action=(
                "Review the signal event timeline."
                if not live_trading_enabled
                else "Disable live trading before accepting external alert evidence."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="signal_event_timeline_complete",
            status="PASS" if not missing_event_statuses else "BLOCKED",
            evidence=signal_event_timeline_evidence(
                signal_event_statuses,
                missing_event_statuses,
            ),
            next_action=(
                "Review risk decision for the latest signal."
                if not missing_event_statuses
                else "Investigate missing signal audit events before trusting the run."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="risk_decision_approved",
            status="PASS" if decision is not None and decision.approved else "BLOCKED",
            evidence=(
                f"Risk decision {decision.id}: {decision.reason}"
                if decision is not None
                else "No risk decision recorded."
            ),
            next_action=(
                "Review paper order creation."
                if decision is not None and decision.approved
                else "Fix the risk rejection reason, then rerun payload preflight."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="signal_provenance_matched",
            status="PASS" if provenance_status in {"MATCHED", "UNTRACKED"} else "BLOCKED",
            evidence=f"Provenance status {provenance_status}.",
            next_action=(
                "Review paper order creation."
                if provenance_status in {"MATCHED", "UNTRACKED"}
                else "Send alerts with the accepted backtest version and settings fingerprint."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="paper_order_created",
            status="PASS" if paper_order is not None else "BLOCKED",
            evidence=(
                f"Paper order {paper_order.id} status {paper_order.status}."
                if paper_order is not None
                else "No paper order found for latest signal."
            ),
            next_action=(
                "Review paper trade creation."
                if paper_order is not None
                else "Only risk-approved signals create paper orders."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="paper_trade_opened",
            status="PASS" if paper_trade is not None else "BLOCKED",
            evidence=(
                f"Paper trade {paper_trade.id} status {paper_trade.status}."
                if paper_trade is not None
                else "No paper trade found for latest signal."
            ),
            next_action=(
                "Monitor the trade and collect paper evidence."
                if paper_trade is not None
                else "Investigate paper execution before sending more alerts."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="live_order_intent_absent",
            status="PASS" if not live_order_intent_ids else "BLOCKED",
            evidence=(
                "No live order intent exists for the signal."
                if not live_order_intent_ids
                else f"Live order intents found: {live_order_intent_ids}."
            ),
            next_action=(
                "Review broker-order side effects."
                if not live_order_intent_ids
                else "Stop and investigate the unexpected live order intent."
            ),
        ),
        TradingViewVerificationCheck(
            check_key="broker_execution_absent",
            status=(
                "PASS"
                if not broker_order_ids and not broker_fill_ids
                else "BLOCKED"
            ),
            evidence=(
                "No broker order or fill exists for the signal."
                if not broker_order_ids and not broker_fill_ids
                else (
                    f"Broker orders {broker_order_ids}; broker fills "
                    f"{broker_fill_ids}."
                )
            ),
            next_action=(
                "External signal side-effect review is complete."
                if not broker_order_ids and not broker_fill_ids
                else "Stop and reconcile all unexpected broker side effects."
            ),
        ),
    ]


def signal_event_timeline_evidence(
    signal_event_statuses: list[SignalStatus],
    missing_event_statuses: list[SignalStatus],
) -> str:
    recorded = ", ".join(status.value for status in signal_event_statuses) or "none"
    if not missing_event_statuses:
        return f"Recorded signal events: {recorded}."
    missing = ", ".join(status.value for status in missing_event_statuses)
    return f"Recorded signal events: {recorded}. Missing: {missing}."


def preflight_account_and_risk_profile(session: Session) -> tuple[Account, RiskProfile]:
    account = session.execute(
        select(Account).where(Account.name == DEFAULT_ACCOUNT_NAME)
    ).scalar_one_or_none()
    if account is None:
        account = Account(
            id=PREFLIGHT_ACCOUNT_ID,
            name=DEFAULT_ACCOUNT_NAME,
            mode="paper",
            currency="USD",
            starting_equity=Decimal("1000"),
            current_equity=Decimal("1000"),
        )

    risk_profile = session.execute(
        select(RiskProfile).where(
            RiskProfile.account_id == account.id,
            RiskProfile.name == DEFAULT_RISK_PROFILE_NAME,
        )
    ).scalar_one_or_none()
    if risk_profile is None:
        risk_profile = RiskProfile(
            id=PREFLIGHT_RISK_PROFILE_ID,
            account_id=account.id,
            name=DEFAULT_RISK_PROFILE_NAME,
            risk_per_trade=Decimal("0.005"),
            max_daily_loss=Decimal("0.01"),
            max_weekly_loss=Decimal("0.03"),
            max_open_positions=3,
            minimum_reward_risk=Decimal("1.5"),
            duplicate_cooldown_minutes=30,
            max_signal_age_seconds=180,
            loss_cooldown_count=3,
            kill_switch_enabled=False,
            is_active=True,
        )
    return account, risk_profile


def preflight_strategy_config(session: Session, strategy: str) -> StrategyConfig:
    config = session.execute(
        select(StrategyConfig).where(StrategyConfig.strategy == strategy)
    ).scalar_one_or_none()
    if config is not None:
        return config

    definition = REGISTERED_STRATEGIES.get(strategy)
    if definition is None:
        return StrategyConfig(
            strategy=strategy,
            version="unregistered",
            display_name=strategy,
            description="Unregistered strategy. Disabled until explicitly reviewed.",
            is_enabled=False,
            allowed_regimes=[],
            parameters={},
        )
    return StrategyConfig(
        strategy=definition.strategy,
        version=definition.version,
        display_name=definition.display_name,
        description=definition.description,
        is_enabled=True,
        allowed_regimes=default_allowed_regime_values(definition),
        risk_per_trade=definition.default_risk_per_trade,
        minimum_reward_risk=definition.default_minimum_reward_risk,
        max_open_positions=definition.default_max_open_positions,
        parameters={
            "pine_path": definition.pine_path,
            "docs_path": definition.docs_path,
        },
    )


def preflight_signal(
    *,
    payload: TradingViewSignalPayload,
    normalized_symbol: str,
    idempotency_key: str,
    raw_payload: dict,
    normalized_payload: dict,
) -> Signal:
    return Signal(
        id=PREFLIGHT_SIGNAL_ID,
        source=payload.source,
        strategy=payload.strategy,
        symbol=normalized_symbol,
        timeframe=payload.timeframe,
        direction=payload.direction,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        market_regime=payload.market_regime,
        status=SignalStatus.VALIDATED,
        idempotency_key=idempotency_key,
        raw_payload=raw_payload,
        normalized_payload=normalized_payload,
        source_timestamp=payload.timestamp,
    )


def tradingview_signal_preflight_next_actions(reason: str) -> list[str]:
    if reason == "Risk approved":
        return [
            "This payload can be sent to the TradingView webhook for paper execution.",
            "Confirm the TradingView alert source matches this exact payload before enabling it.",
        ]
    if "signal provenance" in reason:
        return [
            "Update the TradingView alert payload with the contract strategy_version "
            "and settings_fingerprint.",
            "Re-run preflight before sending the alert to the webhook.",
        ]
    if "accepted backtest evidence" in reason:
        return [
            "Import an accepted backtest for this strategy and symbol first.",
            "Confirm the Signals contract reads READY before testing the webhook.",
        ]
    return [
        f"Fix risk blocker: {reason}.",
        "Re-run preflight before sending the alert to the webhook.",
    ]


def short_contract_hash(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:24]


def signal_contract_example_payload(
    strategy: str,
    symbol: str,
    strategy_version: str | None,
    settings_fingerprint: str | None,
    known_strategy: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source": "tradingview",
        "strategy": strategy,
        "symbol": symbol,
        "timeframe": "15m",
        "direction": "LONG",
        "entry_price": "100",
        "stop_loss": "95",
        "take_profit": "110",
        "market_regime": "TRENDING_UP",
        "timestamp": utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if known_strategy:
        payload["strategy_version"] = strategy_version or "<accepted-backtest-version>"
        payload["settings_fingerprint"] = settings_fingerprint or "<accepted-settings-fingerprint>"
    return payload


def signal_contract_next_actions(
    approved: bool,
    known_strategy: bool,
    reasons: list[str],
) -> list[str]:
    if not approved:
        if "accepted_backtest_missing_for_paper_trading" in reasons:
            return [
                "Import an accepted backtest for this strategy and symbol before "
                "sending paper alerts.",
                "Use the exact Pine settings snapshot from the TradingView strategy tester.",
            ]
        if "accepted_backtest_strategy_parameters_missing" in reasons:
            return [
                "Re-import the backtest with the full known Pine Parameters JSON.",
                "Do not send TradingView alerts until the expected settings "
                "fingerprint is available.",
            ]
        return [
            f"Fix accepted-backtest blocker: {reasons[0] if reasons else 'unknown'}.",
            "Run the signal contract preflight again before sending TradingView alerts.",
        ]
    if known_strategy:
        return [
            "Configure TradingView alerts from the same Pine script version and input settings.",
            "Confirm incoming alerts carry this exact strategy_version and settings_fingerprint.",
        ]
    return [
        "This strategy has accepted backtest evidence, but Aurex does not track a "
        "settings fingerprint for it yet.",
        "Add a known-strategy parameter template before relying on Pine provenance enforcement.",
    ]
