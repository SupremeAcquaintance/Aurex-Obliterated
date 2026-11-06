from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

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


def payload_decimal_or_none(payload: dict | None, key: str) -> Decimal | None:
    if not isinstance(payload, dict) or key not in payload or payload.get(key) is None:
        return None
    return Decimal(str(payload[key]))


def payload_decimal(payload: dict | None, key: str) -> Decimal:
    value = payload_decimal_or_none(payload, key)
    return Decimal("0") if value is None else value


def position_realized_sell_to_close_fees(raw_payload: dict | None) -> Decimal:
    realized_fees = payload_decimal_or_none(
        raw_payload,
        "realized_sell_to_close_fees",
    )
    if realized_fees is not None:
        return realized_fees
    if isinstance(raw_payload, dict):
        last_sell = raw_payload.get("last_sell_to_close")
        if isinstance(last_sell, dict):
            return payload_decimal(last_sell, "allocated_entry_fees") + payload_decimal(
                last_sell,
                "exit_fee",
            )
    return Decimal("0")


class PredictionContractSnapshotRequest(BaseModel):
    venue: PredictionMarketVenue = PredictionMarketVenue.KALSHI
    event_ticker: str = Field(min_length=1, max_length=128)
    market_title: str = Field(min_length=1, max_length=240)
    contract_ticker: str = Field(min_length=1, max_length=160)
    contract_title: str = Field(min_length=1, max_length=240)
    category: str | None = Field(default=None, max_length=120)
    status: PredictionMarketStatus = PredictionMarketStatus.OPEN
    yes_bid_price: Decimal | None = Field(default=None, ge=0, le=1)
    yes_ask_price: Decimal | None = Field(default=None, ge=0, le=1)
    no_bid_price: Decimal | None = Field(default=None, ge=0, le=1)
    no_ask_price: Decimal | None = Field(default=None, ge=0, le=1)
    settlement_value: Decimal | None = Field(default=None, ge=0, le=1)
    closes_at: datetime | None = None
    expiration_at: datetime | None = None
    raw_payload: dict = Field(default_factory=dict)


class PredictionContractResponse(BaseModel):
    id: str
    market_id: str
    venue: PredictionMarketVenue
    contract_ticker: str
    title: str
    status: PredictionMarketStatus
    yes_bid_price: Decimal | None
    yes_ask_price: Decimal | None
    no_bid_price: Decimal | None
    no_ask_price: Decimal | None
    expiration_at: datetime | None
    settlement_value: Decimal | None
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionRiskLimitsRequest(BaseModel):
    max_order_cost: Decimal = Field(default=Decimal("50"), gt=0)
    max_contract_exposure: Decimal = Field(default=Decimal("50"), gt=0)
    max_open_positions: int = Field(default=25, ge=1)
    max_quote_age_seconds: int | None = Field(default=None, ge=1, le=86400)
    max_spread: Decimal | None = Field(default=None, ge=0, le=1)
    max_latency_ms: int | None = Field(default=None, ge=0, le=600000)
    max_slippage: Decimal | None = Field(default=None, ge=0, le=1)


class PredictionOrderIntentCreateRequest(BaseModel):
    contract_id: str = Field(min_length=1)
    strategy: str = Field(min_length=1, max_length=100)
    side: PredictionMarketSide
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal = Field(ge=0, le=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    action: PredictionMarketOrderAction = PredictionMarketOrderAction.BUY
    order_type: PredictionMarketOrderType = PredictionMarketOrderType.LIMIT
    expected_edge: Decimal | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    account_id: str | None = None
    signal_id: str | None = None
    risk_decision_id: str | None = None
    broker_connection_id: str | None = None
    expires_at: datetime | None = None
    risk_limits: PredictionRiskLimitsRequest = Field(default_factory=PredictionRiskLimitsRequest)


class PredictionOrderIntentResponse(BaseModel):
    id: str
    contract_id: str
    signal_id: str | None
    risk_decision_id: str | None
    broker_connection_id: str | None
    strategy: str
    side: PredictionMarketSide
    action: PredictionMarketOrderAction
    order_type: PredictionMarketOrderType
    quantity: Decimal
    limit_price: Decimal
    max_cost: Decimal
    expected_edge: Decimal | None
    confidence: Decimal | None
    status: PredictionMarketOrderStatus
    idempotency_key: str
    intent_snapshot: dict
    created_intent_at: datetime
    expires_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PredictionFillModelRequest(BaseModel):
    available_quantity: Decimal = Field(ge=0)
    latency_ms: int = Field(ge=0)
    execution_price: Decimal | None = Field(default=None, ge=0, le=1)
    raw_payload: dict = Field(default_factory=dict)


class PredictionOrderCancelRequest(BaseModel):
    reason: str = Field(default="manual_order_cancelled", min_length=1, max_length=120)


class PredictionFillResponse(BaseModel):
    id: str
    order_id: str
    external_fill_id: str
    side: PredictionMarketSide
    action: PredictionMarketOrderAction
    quantity: Decimal
    price: Decimal
    fees: Decimal
    filled_at: datetime
    raw_payload: dict

    model_config = ConfigDict(from_attributes=True)


class PredictionOrderResponse(BaseModel):
    id: str
    order_intent_id: str
    broker_connection_id: str | None
    external_order_id: str | None
    status: PredictionMarketOrderStatus
    side: PredictionMarketSide
    action: PredictionMarketOrderAction
    quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal
    average_fill_price: Decimal | None
    fees: Decimal
    submitted_at: datetime | None
    cancelled_at: datetime | None
    external_updated_at: datetime | None
    raw_payload: dict

    model_config = ConfigDict(from_attributes=True)


class PredictionPositionResponse(BaseModel):
    id: str
    account_id: str | None
    contract_id: str
    side: PredictionMarketSide
    quantity: Decimal
    average_entry_price: Decimal
    realized_pl: Decimal
    fees: Decimal
    status: PredictionMarketPositionStatus
    opened_at: datetime
    closed_at: datetime | None
    raw_payload: dict

    @computed_field
    @property
    def realized_sell_to_close_fees(self) -> Decimal:
        return position_realized_sell_to_close_fees(self.raw_payload)

    @computed_field
    @property
    def lifecycle_fees(self) -> Decimal:
        raw_lifecycle_fees = payload_decimal_or_none(
            self.raw_payload,
            "total_lifecycle_fees",
        )
        if raw_lifecycle_fees is not None:
            return raw_lifecycle_fees
        return self.fees + self.realized_sell_to_close_fees

    model_config = ConfigDict(from_attributes=True)


class PredictionOrderSubmissionResponse(BaseModel):
    order: PredictionOrderResponse
    fill: PredictionFillResponse | None
    position: PredictionPositionResponse | None


class PredictionSettlementRequest(BaseModel):
    settlement_value: Decimal = Field(ge=0, le=1)


class PredictionSettlementResponse(BaseModel):
    id: str
    contract_id: str
    position_id: str | None
    settlement_value: Decimal
    gross_payout: Decimal
    realized_pl: Decimal
    fees: Decimal
    settled_at: datetime
    raw_payload: dict

    model_config = ConfigDict(from_attributes=True)


class PredictionReconciliationReportResponse(BaseModel):
    id: str
    broker_connection_id: str | None
    status: ReconciliationStatus
    summary: str
    discrepancies: list
    venue_snapshot: dict
    aurex_snapshot: dict
    reconciled_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionEvidenceEventResponse(BaseModel):
    id: str
    kind: PredictionMarketEvidenceKind
    entity_type: str
    entity_id: str | None
    strategy: str | None
    contract_ticker: str | None
    evidence_hash: str
    payload: dict
    occurred_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionMarketSummaryResponse(BaseModel):
    contracts: int
    order_intents: int
    orders: int
    fills: int
    open_positions: int
    settled_positions: int
    rejected_intents: int
    latest_reconciliation: PredictionReconciliationReportResponse | None
    live_execution_enabled: bool = False


class PredictionPaperDemoReadinessResponse(BaseModel):
    generated_at: datetime
    status: str
    ready_to_start: bool
    demo_lifecycle_verified: bool
    current_check: dict | None = None
    completed_check_count: int
    total_check_count: int
    progress_pct: float
    next_action: str
    checks: list[dict]
    evidence: dict


class PredictionPaperDemoProgressResponse(BaseModel):
    generated_at: datetime
    status: str
    ready_for_live_review: bool
    current_check: dict | None = None
    completed_check_count: int
    total_check_count: int
    progress_pct: float
    target_closed_records: int
    target_calendar_days: int
    target_active_days: int
    target_unique_contracts: int
    raw_closed_records: int
    closed_records: int
    calendar_days: int
    active_days: int
    unique_contracts: int
    remaining_records: int
    remaining_calendar_days: int
    remaining_active_days: int
    remaining_unique_contracts: int
    fee_net_realized_pl: Decimal
    total_fees: Decimal
    expectancy: Decimal
    profit_factor: Decimal | None
    max_drawdown: Decimal
    winning_records: int
    losing_records: int
    breakeven_records: int
    max_single_day_records: int
    max_single_day_record_share: Decimal
    max_single_contract_records: int
    max_single_contract_record_share: Decimal
    provenance_complete_records: int
    provenance_missing_records: int
    countable_ledger_records: int
    ledger_blocked_records: int
    first_closed_at: datetime | None
    latest_closed_at: datetime | None
    latest_reconciliation_status: ReconciliationStatus | None
    checks: list[dict]
    distribution: dict
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoRunbookStepResponse(BaseModel):
    rank: int
    key: str
    label: str
    status: str
    evidence: str
    writes_ledger: bool = False
    next_action: str


class PredictionPaperDemoRunbookResponse(BaseModel):
    generated_at: datetime
    status: str
    readiness_status: str
    progress_status: str
    upstream_research_runbook: dict | None = None
    current_step: PredictionPaperDemoRunbookStepResponse | None = None
    completed_step_count: int
    total_step_count: int
    progress_pct: float
    steps: list[PredictionPaperDemoRunbookStepResponse]
    blockers: list[str]
    next_action: str
    readiness: PredictionPaperDemoReadinessResponse
    progress: PredictionPaperDemoProgressResponse
    live_execution_enabled: bool = False


class PredictionPaperDemoEvidenceRecordResponse(BaseModel):
    settlement_id: str
    position_id: str | None
    contract_id: str
    contract_ticker: str
    venue: PredictionMarketVenue
    side: PredictionMarketSide | None
    strategies: list[str]
    primary_strategy: str | None
    quantity: Decimal | None
    average_entry_price: Decimal | None
    settlement_value: Decimal
    gross_payout: Decimal
    fees: Decimal
    realized_pl: Decimal
    settled_at: datetime
    evidence_event_id: str | None
    evidence_hash: str | None
    source: str
    source_reference: str | None
    csv_format: str | None
    imported_from_mkt: bool
    reconciliation_report_id: str | None
    reconciliation_status: ReconciliationStatus | None
    recorded_evidence_kinds: list[PredictionMarketEvidenceKind]
    missing_evidence_kinds: list[PredictionMarketEvidenceKind]
    counts_toward_target: bool
    blockers: list[str]
    live_execution_enabled: bool = False


class PredictionPaperDemoEvidenceLedgerResponse(BaseModel):
    generated_at: datetime
    records: list[PredictionPaperDemoEvidenceRecordResponse]
    record_count: int
    countable_records: int
    blocked_records: int
    latest_reconciliation_status: ReconciliationStatus | None
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoCampaignAuditRecordResponse(BaseModel):
    evidence_event_id: str
    evidence_hash: str
    occurred_at: datetime
    strategy: str | None
    status: str | None
    source: str | None
    source_reference: str | None
    import_hash: str | None
    donor_quality_status: str | None = None
    donor_evidence_tier: str | None = None
    donor_use_scope: str | None = None
    donor_backtest_depth_ready: bool = False
    side: PredictionMarketSide | None
    side_sensitivity_warning: str | None
    side_sensitivity_acknowledged: bool
    side_selection_rationale: str | None
    attempted_records: int
    completed_records: int
    skipped_records: int
    rejected_records: int
    countable_records: int
    blocked_records: int
    target_closed_records: int
    raw_closed_records: int
    remaining_records: int
    remaining_calendar_days: int
    remaining_active_days: int
    remaining_unique_contracts: int
    progress_pct: float
    current_check_key: str | None = None
    fee_net_realized_pl: Decimal
    ready_for_live_review: bool
    current_result_records: int = 0
    current_result_countable_records: int = 0
    current_result_blocked_records: int = 0
    current_result_fee_net_realized_pl: Decimal = Decimal("0")
    current_result_ledger_status: str = "UNKNOWN"
    current_result_ledger_blockers: list[str] = Field(default_factory=list)
    payload: dict
    live_execution_enabled: bool = False


class PredictionPaperDemoCampaignAuditResponse(BaseModel):
    generated_at: datetime
    records: list[PredictionPaperDemoCampaignAuditRecordResponse]
    record_count: int
    acknowledged_records: int
    side_sensitive_records: int
    current_result_clean_records: int = 0
    current_result_drifted_records: int = 0
    latest_evidence_hash: str | None
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoBatchAuditRecordResponse(BaseModel):
    evidence_event_id: str
    evidence_hash: str
    occurred_at: datetime
    strategy: str | None
    status: str | None
    source: str | None
    source_reference: str | None
    side: PredictionMarketSide | None
    preflight_hash: str | None
    reviewed_preflight_hash: str | None
    attempted_records: int
    completed_records: int
    skipped_records: int
    rejected_records: int
    countable_records: int
    blocked_records: int
    target_closed_records: int
    raw_closed_records: int
    remaining_records: int
    remaining_unique_contracts: int
    progress_pct: float
    current_check_key: str | None = None
    fee_net_realized_pl: Decimal
    ready_for_live_review: bool
    current_result_records: int = 0
    current_result_countable_records: int = 0
    current_result_blocked_records: int = 0
    current_result_fee_net_realized_pl: Decimal = Decimal("0")
    current_result_ledger_status: str = "UNKNOWN"
    current_result_ledger_blockers: list[str] = Field(default_factory=list)
    payload: dict
    live_execution_enabled: bool = False


class PredictionPaperDemoBatchAuditResponse(BaseModel):
    generated_at: datetime
    records: list[PredictionPaperDemoBatchAuditRecordResponse]
    record_count: int
    current_result_clean_records: int = 0
    current_result_drifted_records: int = 0
    latest_evidence_hash: str | None
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoRunRequest(BaseModel):
    contract_id: str | None = None
    strategy: str = Field(default="mkt_whale_research_candidate", min_length=1, max_length=100)
    side: PredictionMarketSide = PredictionMarketSide.YES
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    limit_price: Decimal | None = Field(default=None, ge=0, le=1)
    available_quantity: Decimal | None = Field(default=None, ge=0)
    execution_price: Decimal | None = Field(default=None, ge=0, le=1)
    latency_ms: int = Field(default=500, ge=0)
    settlement_value: Decimal | None = Field(default=None, ge=0, le=1)
    idempotency_key: str | None = Field(default=None, max_length=128)
    risk_limits: PredictionRiskLimitsRequest = Field(default_factory=PredictionRiskLimitsRequest)


class PredictionPaperDemoRunResponse(BaseModel):
    status: str
    completed_lifecycle: bool
    next_action: str
    intent: PredictionOrderIntentResponse
    order: PredictionOrderResponse | None
    fill: PredictionFillResponse | None
    position: PredictionPositionResponse | None
    settlement: PredictionSettlementResponse | None
    reconciliation: PredictionReconciliationReportResponse | None
    run_snapshot: dict


class PredictionPaperDemoBatchRunRequest(BaseModel):
    strategy: str = Field(default="mkt_whale_research_candidate", min_length=1, max_length=100)
    side: PredictionMarketSide = PredictionMarketSide.YES
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    limit_price: Decimal | None = Field(default=None, ge=0, le=1)
    available_quantity: Decimal | None = Field(default=None, ge=0)
    latency_ms: int = Field(default=500, ge=0)
    max_records: int = Field(default=5, ge=1, le=25)
    source: str | None = Field(default=None, max_length=80)
    source_reference: str | None = Field(default=None, max_length=240)
    require_imported_snapshot: bool = True
    require_settlement_value: bool = True
    skip_existing: bool = True
    idempotency_prefix: str = Field(default="paper-demo-batch", min_length=1, max_length=64)
    reviewed_preflight_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )
    risk_limits: PredictionRiskLimitsRequest = Field(default_factory=PredictionRiskLimitsRequest)


class PredictionPaperDemoBatchPreflightRequest(PredictionPaperDemoBatchRunRequest):
    pass


class PredictionPaperDemoBatchRunItemResponse(BaseModel):
    contract_id: str
    contract_ticker: str
    status: str
    source: str | None = None
    source_reference: str | None = None
    csv_format: str | None = None
    settlement_value: Decimal | None = None
    executable_price: Decimal | None = None
    limit_price: Decimal | None = None
    completed_lifecycle: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    intent_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    position_id: str | None = None
    settlement_id: str | None = None
    reconciliation_status: ReconciliationStatus | None = None
    realized_pl: Decimal | None = None
    evidence_hash: str | None = None
    next_action: str


class PredictionPaperDemoBatchPreflightResponse(BaseModel):
    status: str
    eligible_records: int
    skipped_records: int
    available_contracts: int
    max_records: int
    preflight_hash: str
    results: list[PredictionPaperDemoBatchRunItemResponse]
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoBatchRunResponse(BaseModel):
    status: str
    attempted_records: int
    completed_records: int
    skipped_records: int
    rejected_records: int
    available_contracts: int
    preflight_hash: str | None = None
    reviewed_preflight_hash: str | None = None
    results: list[PredictionPaperDemoBatchRunItemResponse]
    progress: PredictionPaperDemoProgressResponse
    ledger: PredictionPaperDemoEvidenceLedgerResponse
    batch_evidence: PredictionEvidenceEventResponse | None = None
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoMktDbCampaignProjectionResponse(BaseModel):
    side: PredictionMarketSide
    status: str
    attempted_records: int
    completed_records: int
    rejected_records: int
    target_closed_records: int
    target_calendar_days: int
    target_active_days: int
    target_unique_contracts: int
    projected_raw_closed_records: int
    projected_closed_records: int
    projected_calendar_days: int
    projected_active_days: int
    projected_unique_contracts: int
    projected_countable_records: int
    projected_blocked_records: int
    remaining_closed_records: int
    remaining_calendar_days: int
    remaining_active_days: int
    remaining_unique_contracts: int
    projected_progress_pct: float
    projected_fee_net_realized_pl: Decimal
    projected_expectancy: Decimal | None = None
    projected_profit_factor: Decimal | None = None
    projected_max_drawdown: Decimal
    ready_for_live_review: bool
    first_failed_check: str | None = None
    next_action: str
    live_execution_enabled: bool = False


class PredictionContractSnapshotCsvRequest(BaseModel):
    source: str = Field(default="prediction_market_csv", min_length=1, max_length=80)
    source_reference: str = Field(default="manual-upload", min_length=1, max_length=240)
    csv_text: str = Field(min_length=1)
    csv_format: Literal["auto", "aurex", "mkt_markets"] = "auto"


class PredictionContractSnapshotCsvPreflightResponse(BaseModel):
    source: str
    source_reference: str
    csv_format: str
    import_hash: str
    status: str
    rows_received: int
    importable_count: int
    rejected_count: int
    required_headers: list[str]
    row_results: list[dict]
    analysis_summary: dict
    checked_at: datetime


class PredictionContractSnapshotCsvImportResponse(BaseModel):
    source: str
    source_reference: str
    csv_format: str
    import_hash: str
    status: str
    rows_received: int
    imported_count: int
    rejected_count: int
    contract_ids: list[str]
    row_results: list[dict]
    analysis_summary: dict
    imported_at: datetime


class PredictionContractSnapshotMktDbRequest(BaseModel):
    db_path: str = Field(
        default="My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db",
        min_length=1,
        max_length=600,
    )
    source: str = Field(default="my-krypt-trader", min_length=1, max_length=80)
    source_reference: str = Field(
        default="My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db::markets",
        min_length=1,
        max_length=240,
    )
    status_filter: Literal["all", "open", "resolved"] = "resolved"
    limit: int = Field(default=100, ge=1, le=500)
    min_volume: Decimal | None = Field(default=None, ge=0)
    require_settlement_value: bool = True


class PredictionContractSnapshotMktDbReadinessResponse(BaseModel):
    db_path: str
    source: str
    source_reference: str
    status: str
    data_ready: bool
    db_exists: bool
    markets_table_available: bool | None
    rows_received: int
    importable_count: int
    rejected_count: int
    import_hash: str | None = None
    analysis_summary: dict
    query_summary: dict
    error: str | None = None
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDbInventoryTableResponse(BaseModel):
    key: str
    table: str
    exists: bool
    row_count: int
    resolved_count: int | None = None
    latest_at: str | None = None
    usable_for: str
    next_action: str


class PredictionContractSnapshotMktDbInventoryResponse(BaseModel):
    db_path: str
    status: str
    db_exists: bool
    tables_available: int
    total_rows: int
    replay_table_ready: bool
    research_tables_ready: bool
    execution_history_ready: bool
    replay_candidate_count: int
    research_candidate_count: int
    markets_readiness: PredictionContractSnapshotMktDbReadinessResponse | None = None
    tables: list[PredictionContractSnapshotMktDbInventoryTableResponse]
    missing_tables: list[str]
    blockers: list[str]
    error: str | None = None
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorCollectionQualityCheckResponse(BaseModel):
    key: str
    status: str
    passed: bool
    observed: str
    expected: str
    next_action: str


class PredictionContractSnapshotMktDonorCollectionTargetResponse(BaseModel):
    key: str
    label: str
    current_count: int
    target_count: int
    remaining_count: int
    progress_pct: float
    status: str
    next_action: str


class PredictionContractSnapshotMktDonorCollectionQualityResponse(BaseModel):
    status: str
    evidence_tier: str
    aurex_use_scope: str
    replay_candidate_count: int
    research_candidate_count: int
    context_row_count: int
    total_rows: int
    latest_row_at: str | None = None
    minimum_backtest_replay_rows: int
    minimum_backtest_research_rows: int
    backtest_depth_progress_pct: float
    targets: list[PredictionContractSnapshotMktDonorCollectionTargetResponse]
    checks: list[PredictionContractSnapshotMktDonorCollectionQualityCheckResponse]
    blockers: list[str]
    next_action: str
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorLaunchHealthCheckResponse(BaseModel):
    key: str
    status: str
    passed: bool
    observed: str
    expected: str
    next_action: str


class PredictionContractSnapshotMktDonorLaunchHealthResponse(BaseModel):
    status: str
    checks: list[PredictionContractSnapshotMktDonorLaunchHealthCheckResponse]
    blockers: list[str]
    next_action: str
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDbDiscoveryRequest(BaseModel):
    search_roots: list[str] = Field(
        default_factory=lambda: ["My-Krypt-Trader", "My-Krypt-Trader/python"],
        min_length=1,
        max_length=8,
    )
    limit: int = Field(default=25, ge=1, le=100)
    status_filter: Literal["all", "open", "resolved"] = "resolved"
    min_volume: Decimal | None = Field(default=None, ge=0)
    require_settlement_value: bool = True


class PredictionContractSnapshotMktDbDiscoveryCandidateResponse(BaseModel):
    db_path: str
    file_size_bytes: int | None = None
    modified_at: datetime | None = None
    readiness: PredictionContractSnapshotMktDbReadinessResponse


class PredictionContractSnapshotMktDbDiscoveryResponse(BaseModel):
    search_roots: list[str]
    candidate_count: int
    ready_count: int
    candidates: list[PredictionContractSnapshotMktDbDiscoveryCandidateResponse]
    skipped_paths: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorReadinessRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    search_roots: list[str] = Field(
        default_factory=lambda: [
            "My-Krypt-Trader",
            "My-Krypt-Trader/python",
            "My-Krypt-Trader/python/data",
        ],
        min_length=1,
        max_length=8,
    )
    limit: int = Field(default=25, ge=1, le=100)
    status_filter: Literal["all", "open", "resolved"] = "resolved"
    min_volume: Decimal | None = Field(default=None, ge=0)
    require_settlement_value: bool = True


class PredictionContractSnapshotMktDonorReadinessResponse(BaseModel):
    status: str
    mkt_root: str
    root_exists: bool
    python_dir_exists: bool
    data_dir_exists: bool
    db_module_exists: bool
    expected_db_paths: list[str]
    collector_files: list[dict]
    command_hints: list[dict]
    discovery: PredictionContractSnapshotMktDbDiscoveryResponse
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktRuntimeSafetyRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    settings_path: str | None = Field(default=None, min_length=1, max_length=600)
    userdata_path: str | None = Field(default=None, min_length=1, max_length=600)


class PredictionContractSnapshotMktRuntimeSafetyCheckResponse(BaseModel):
    key: str
    status: str
    passed: bool
    observed: str
    expected: str
    source: str
    next_action: str


class PredictionContractSnapshotMktRuntimeSafetyCredentialResponse(BaseModel):
    env: str
    credentials_dir: str
    api_key_file_exists: bool
    rsa_key_file_exists: bool
    credential_pair_present: bool
    contents_read: bool = False


class PredictionContractSnapshotMktRuntimePathCandidateResponse(BaseModel):
    key: str
    path: str
    exists: bool
    selected: bool
    source: str
    purpose: str


class PredictionContractSnapshotMktRuntimeSafetyResponse(BaseModel):
    status: str
    mkt_root: str
    root_exists: bool
    settings_path: str | None = None
    settings_exists: bool
    settings_loaded: bool
    settings_error: str | None = None
    settings_auto_discovered: bool
    settings_candidates: list[PredictionContractSnapshotMktRuntimePathCandidateResponse]
    userdata_path: str | None = None
    userdata_auto_discovered: bool
    userdata_candidates: list[PredictionContractSnapshotMktRuntimePathCandidateResponse]
    credentials: list[PredictionContractSnapshotMktRuntimeSafetyCredentialResponse]
    checks: list[PredictionContractSnapshotMktRuntimeSafetyCheckResponse]
    passed_checks: int
    warning_checks: int
    failed_checks: int
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorBootstrapRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    userdata_path: str | None = Field(default=None, min_length=1, max_length=600)
    overwrite_existing_settings: bool = False


class PredictionContractSnapshotMktDonorBootstrapResponse(BaseModel):
    status: str
    mkt_root: str
    userdata_path: str
    settings_path: str
    settings_written: bool
    directories_created: list[str]
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse
    command_hints: list[dict]
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorCollectionStatusRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    settings_path: str | None = Field(default=None, min_length=1, max_length=600)
    userdata_path: str | None = Field(default=None, min_length=1, max_length=600)
    db_path: str | None = Field(default=None, min_length=1, max_length=600)
    status_filter: Literal["all", "open", "resolved"] = "resolved"
    limit: int = Field(default=100, ge=1, le=500)
    min_volume: Decimal | None = Field(default=None, ge=0)
    require_settlement_value: bool = True


class PredictionContractSnapshotMktDonorCollectionStatusResponse(BaseModel):
    status: str
    mkt_root: str
    settings_path: str | None = None
    userdata_path: str | None = None
    db_path: str
    data_dir_exists: bool
    logs_dir_exists: bool
    db_file_size_bytes: int | None = None
    db_modified_at: datetime | None = None
    db_age_seconds: int | None = None
    latest_log_modified_at: datetime | None = None
    latest_log_age_seconds: int | None = None
    freshness_window_seconds: int
    recommended_recheck_after_seconds: int | None = None
    recommended_recheck_at: datetime | None = None
    collection_freshness_status: str
    log_files: list[dict]
    command_hints: list[dict] = Field(default_factory=list)
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse
    collection_quality: PredictionContractSnapshotMktDonorCollectionQualityResponse
    launch_health: PredictionContractSnapshotMktDonorLaunchHealthResponse
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorLaunchPreflightRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    settings_path: str | None = Field(default=None, min_length=1, max_length=600)
    userdata_path: str | None = Field(default=None, min_length=1, max_length=600)
    db_path: str | None = Field(default=None, min_length=1, max_length=600)


class PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse(BaseModel):
    key: str
    status: str
    passed: bool
    observed: str
    expected: str
    source: str
    next_action: str


class PredictionContractSnapshotMktDonorLaunchPreflightResponse(BaseModel):
    status: str
    mkt_root: str
    userdata_path: str | None = None
    settings_path: str | None = None
    db_path: str
    launch_command: str | None = None
    launch_scope: str
    evidence_tier: str
    aurex_use_scope: str
    backtest_depth_ready: bool
    evidence_boundary: str
    setup_commands: list[dict]
    checks: list[PredictionContractSnapshotMktDonorLaunchPreflightCheckResponse]
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse
    collection_status: PredictionContractSnapshotMktDonorCollectionStatusResponse
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDonorRunbookRequest(BaseModel):
    mkt_root: str = Field(default="My-Krypt-Trader", min_length=1, max_length=600)
    db_path: str | None = Field(default=None, min_length=1, max_length=600)
    settings_path: str | None = Field(default=None, min_length=1, max_length=600)
    userdata_path: str | None = Field(default=None, min_length=1, max_length=600)
    search_roots: list[str] = Field(
        default_factory=lambda: [
            "My-Krypt-Trader",
            "My-Krypt-Trader/python",
            "My-Krypt-Trader/python/data",
        ],
        min_length=1,
        max_length=8,
    )
    limit: int = Field(default=25, ge=1, le=100)
    status_filter: Literal["all", "open", "resolved"] = "resolved"
    min_volume: Decimal | None = Field(default=None, ge=0)
    require_settlement_value: bool = True


class PredictionContractSnapshotMktDonorRunbookStepResponse(BaseModel):
    step: int
    title: str
    status: str
    command: str | None = None
    purpose: str
    verification: str
    safety_gate: str
    blockers: list[str]
    next_action: str


class PredictionContractSnapshotMktDonorRunbookResponse(BaseModel):
    status: str
    mkt_root: str
    db_path: str
    donor_readiness: PredictionContractSnapshotMktDonorReadinessResponse
    db_inventory: PredictionContractSnapshotMktDbInventoryResponse
    collection_status: PredictionContractSnapshotMktDonorCollectionStatusResponse
    runtime_safety: PredictionContractSnapshotMktRuntimeSafetyResponse
    steps: list[PredictionContractSnapshotMktDonorRunbookStepResponse]
    blockers: list[str]
    next_action: str
    checked_at: datetime
    live_execution_enabled: bool = False


class PredictionContractSnapshotMktDbPreflightResponse(BaseModel):
    db_path: str
    source: str
    source_reference: str
    csv_format: str
    import_hash: str
    status: str
    rows_received: int
    importable_count: int
    rejected_count: int
    required_headers: list[str]
    row_results: list[dict]
    analysis_summary: dict
    query_summary: dict
    checked_at: datetime


class PredictionContractSnapshotMktDbImportResponse(BaseModel):
    db_path: str
    source: str
    source_reference: str
    csv_format: str
    import_hash: str
    status: str
    rows_received: int
    imported_count: int
    rejected_count: int
    contract_ids: list[str]
    row_results: list[dict]
    analysis_summary: dict
    query_summary: dict
    imported_at: datetime


class PredictionPaperDemoMktDbCampaignPreflightRequest(BaseModel):
    db_import: PredictionContractSnapshotMktDbRequest = Field(
        default_factory=PredictionContractSnapshotMktDbRequest
    )
    batch: PredictionPaperDemoBatchPreflightRequest = Field(
        default_factory=PredictionPaperDemoBatchPreflightRequest
    )


class PredictionPaperDemoMktDbCampaignRunRequest(BaseModel):
    db_import: PredictionContractSnapshotMktDbRequest = Field(
        default_factory=PredictionContractSnapshotMktDbRequest
    )
    batch: PredictionPaperDemoBatchRunRequest = Field(
        default_factory=PredictionPaperDemoBatchRunRequest
    )
    acknowledge_side_sensitivity: bool = False
    side_selection_rationale: str | None = Field(default=None, max_length=800)
    reviewed_manifest_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
    )


class PredictionPaperDemoMktDbCampaignPreflightResponse(BaseModel):
    status: str
    import_preflight: PredictionContractSnapshotMktDbPreflightResponse
    batch_preflight: PredictionPaperDemoBatchPreflightResponse
    projected_replay: PredictionPaperDemoMktDbCampaignProjectionResponse | None = None
    opposite_side_projection: PredictionPaperDemoMktDbCampaignProjectionResponse | None = None
    side_sensitivity_warning: str | None = None
    mutated_ledger: bool = False
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoMktDbCampaignReadinessResponse(BaseModel):
    status: str
    ready_for_campaign_preflight: bool
    ready_for_campaign_replay: bool
    data_readiness: PredictionContractSnapshotMktDbReadinessResponse
    data_quality_status: str
    data_evidence_tier: str
    data_use_scope: str
    data_backtest_depth_ready: bool
    strategy_gate: dict
    campaign_preflight: PredictionPaperDemoMktDbCampaignPreflightResponse | None = None
    checks: list[dict]
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoMktDbCampaignManifestResponse(BaseModel):
    status: str
    replay_ready: bool
    manifest_hash: str
    manifest: dict
    readiness: PredictionPaperDemoMktDbCampaignReadinessResponse
    blockers: list[str]
    generated_at: datetime
    mutated_ledger: bool = False
    next_action: str
    live_execution_enabled: bool = False


class PredictionPaperDemoMktDbCampaignRunResponse(BaseModel):
    status: str
    import_result: PredictionContractSnapshotMktDbImportResponse
    batch: PredictionPaperDemoBatchRunResponse
    progress: PredictionPaperDemoProgressResponse
    ledger: PredictionPaperDemoEvidenceLedgerResponse
    campaign_evidence: PredictionEvidenceEventResponse | None = None
    manifest_hash: str | None = None
    reviewed_manifest_hash: str | None = None
    side_sensitivity_warning: str | None = None
    side_sensitivity_acknowledged: bool = False
    side_selection_rationale: str | None = None
    next_action: str
    live_execution_enabled: bool = False
