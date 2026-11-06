from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aurex.backtest_engine.datasets import normalize_timeframe
from aurex.domain.enums import Direction, MarketRegime, SignalStatus


class SignalPayload(BaseModel):
    source: str = Field(min_length=1)
    strategy: str = Field(min_length=1, max_length=100)
    strategy_version: str | None = Field(default=None, min_length=1, max_length=64)
    settings_fingerprint: str | None = Field(default=None, min_length=1, max_length=2000)
    symbol: str = Field(min_length=1, max_length=64)
    timeframe: str = Field(min_length=1, max_length=32)
    direction: Direction
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    timestamp: datetime

    model_config = ConfigDict(extra="forbid")

    @field_validator("strategy", "strategy_version", "settings_fingerprint", "symbol")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be blank")
        return stripped

    @field_validator("timeframe")
    @classmethod
    def canonicalize_timeframe(cls, value: str) -> str:
        try:
            timeframe, _ = normalize_timeframe(value)
        except ValueError as exc:
            raise ValueError(str(exc).replace("OHLCV ", "")) from exc
        return timeframe

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_price_geometry_when_complete(self) -> "SignalPayload":
        if self.stop_loss is None or self.take_profit is None:
            return self

        if self.direction == Direction.LONG:
            valid = self.stop_loss < self.entry_price < self.take_profit
        else:
            valid = self.take_profit < self.entry_price < self.stop_loss

        if not valid:
            raise ValueError("entry, stop_loss, and take_profit do not match direction")

        return self


class TradingViewSignalPayload(SignalPayload):
    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        source = value.strip().lower()
        if source != "tradingview":
            raise ValueError("source must be tradingview")
        return source


class NativeSignalPayload(SignalPayload):
    """Local strategy-engine input, not an authenticated external delivery receipt."""

    strategy_version: str = Field(min_length=1, max_length=64)
    settings_fingerprint: str = Field(min_length=1, max_length=2000)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        source = value.strip().lower()
        if source != "aurex_native":
            raise ValueError("source must be aurex_native")
        return source

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("native signal timestamp must include a timezone")
        return value.astimezone(UTC)


class SignalResponse(BaseModel):
    id: str
    source: str
    strategy: str
    strategy_version: str | None = None
    settings_fingerprint: str | None = None
    symbol: str
    timeframe: str
    direction: Direction
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    market_regime: MarketRegime
    status: SignalStatus
    idempotency_key: str
    duplicate_of_signal_id: str | None
    rejection_reason: str | None
    source_timestamp: datetime
    received_at: datetime
    processed_at: datetime | None
    processing_latency_ms: Decimal | None
    latest_risk_decision: "RiskDecisionResponse | None" = None

    model_config = ConfigDict(from_attributes=True)


class SignalContractResponse(BaseModel):
    strategy: str
    symbol: str
    status: str
    ready_for_paper: bool
    reason: str
    reasons: list[str]
    accepted_backtest_run_id: str | None
    strategy_version: str | None
    settings_fingerprint: str | None
    settings_fingerprint_preview: str | None
    known_strategy: bool
    requires_provenance: bool
    required_parameters: list[str]
    missing_parameters: list[str]
    required_payload_fields: list[str]
    optional_payload_fields: list[str]
    example_payload: dict
    next_actions: list[str]
    evidence_snapshot: dict


class TradingViewSignalPreflightResponse(BaseModel):
    status: str
    would_execute_paper: bool
    reason: str
    reasons: list[str]
    idempotency_key: str
    duplicate_status: str
    duplicate_signal_id: str | None
    duplicate_cooldown_minutes: int
    expected_webhook_status: SignalStatus
    expected_webhook_http_status: int
    normalized_payload: dict
    contract: SignalContractResponse
    reward_risk: Decimal | None
    risk_amount: Decimal | None
    position_size: Decimal | None
    account_equity: Decimal | None
    rules_snapshot: dict
    mutates_ledger: bool
    next_actions: list[str]


class TradingViewRunbookStep(BaseModel):
    step_key: str
    title: str
    status: str
    evidence: str
    next_action: str


class TradingViewRunbookResponse(BaseModel):
    strategy: str
    symbol: str
    status: str
    ready_to_preflight: bool
    ready_to_send_webhook: bool
    live_trading_enabled: bool
    contract: SignalContractResponse
    steps: list[TradingViewRunbookStep]
    current_step: TradingViewRunbookStep | None
    completed_step_count: int
    total_step_count: int
    progress_pct: Decimal
    next_action: str
    webhook_endpoint: str
    preflight_endpoint: str
    required_header: str
    mutates_ledger: bool


class TradingViewAlertSetupResponse(BaseModel):
    strategy: str
    symbol: str
    status: str
    ready_for_alert_preflight: bool
    live_trading_enabled: bool
    webhook_endpoint: str
    webhook_method: str
    webhook_url_template: str
    webhook_secret_transport: str
    header_auth_supported: bool
    query_secret_supported: bool
    required_header: str
    preflight_endpoint: str
    verification_endpoint: str
    alert_condition: str
    alert_message: dict
    accepted_backtest_run_id: str | None
    strategy_version: str | None
    settings_fingerprint: str | None
    settings_fingerprint_preview: str | None
    required_payload_fields: list[str]
    next_actions: list[str]
    security_notes: list[str]
    delivery_constraints: list[str]
    contract: SignalContractResponse
    mutates_ledger: bool = False


class TradingViewVerificationCheck(BaseModel):
    check_key: str
    status: str
    evidence: str
    next_action: str


class TradingViewVerificationResponse(BaseModel):
    strategy: str
    symbol: str
    status: str
    verified: bool
    delivery_verified: bool
    pipeline_verified: bool
    latest_signal_id: str | None
    latest_signal_status: SignalStatus | None
    latest_risk_decision_id: str | None
    risk_approved: bool | None
    paper_order_id: str | None
    paper_trade_id: str | None
    provenance_status: str
    delivery_auth_status: str
    delivery_auth_transport: str | None
    delivery_origin_status: str
    delivery_remote_ip: str | None
    delivery_evidence_hash: str | None
    delivery_source_network_configuration_status: str = "UNKNOWN"
    delivery_source_networks: list[str] = Field(default_factory=list)
    delivery_source_networks_sha256: str | None = None
    delivery_source_networks_authority_url: str | None = None
    signal_event_statuses: list[SignalStatus]
    missing_event_statuses: list[SignalStatus]
    checks: list[TradingViewVerificationCheck]
    next_action: str
    mutates_ledger: bool
    live_trading_enabled: bool = False
    live_execution_adapter: str = "unknown"
    latest_signal_source_timestamp: datetime | None = None
    latest_signal_received_at: datetime | None = None
    latest_signal_idempotency_key: str | None = None
    latest_signal_strategy_version: str | None = None
    latest_signal_settings_fingerprint: str | None = None
    latest_signal_timeframe: str | None = None
    delivery_body_sha256: str | None = None
    delivery_body_size_bytes: int | None = None
    delivery_request_method: str | None = None
    delivery_request_path: str | None = None
    delivery_content_type: str | None = None
    delivery_user_agent: str | None = None
    live_order_intent_ids: list[str] = Field(default_factory=list)
    broker_order_ids: list[str] = Field(default_factory=list)
    broker_fill_ids: list[str] = Field(default_factory=list)


class RiskDecisionResponse(BaseModel):
    id: str
    approved: bool
    reason: str
    reward_risk: Decimal | None
    risk_amount: Decimal | None
    position_size: Decimal | None
    account_equity: Decimal | None
    rules_snapshot: dict

    model_config = ConfigDict(from_attributes=True)
