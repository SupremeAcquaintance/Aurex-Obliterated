from enum import StrEnum


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class MarketRegime(StrEnum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT_EXPANSION = "BREAKOUT_EXPANSION"
    CHOPPY_DANGER_ZONE = "CHOPPY_DANGER_ZONE"
    UNKNOWN = "UNKNOWN"


class SignalStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    REJECTED_INVALID = "REJECTED_INVALID"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    SCORED = "SCORED"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    PAPER_ORDER_CREATED = "PAPER_ORDER_CREATED"
    PAPER_EXECUTED = "PAPER_EXECUTED"
    CLOSED = "CLOSED"
    ANALYZED = "ANALYZED"


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TradeStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class StrategyRunStatus(StrEnum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BacktestStatus(StrEnum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalystNoteType(StrEnum):
    TRADE_REVIEW = "TRADE_REVIEW"
    PATTERN_SIMILARITY = "PATTERN_SIMILARITY"
    RISK_ANOMALY = "RISK_ANOMALY"
    STRATEGY_DEGRADATION = "STRATEGY_DEGRADATION"
    PORTFOLIO_SUMMARY = "PORTFOLIO_SUMMARY"


class BrokerEnvironment(StrEnum):
    SANDBOX = "SANDBOX"
    LIVE = "LIVE"


class BrokerConnectionStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class OrderIntentStatus(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    RECONCILED = "RECONCILED"


class BrokerOrderStatus(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class ReconciliationStatus(StrEnum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    NOT_READY = "NOT_READY"


class ReadinessStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class StrategyEvidenceDecision(StrEnum):
    CANDIDATE = "CANDIDATE"
    BLOCKED = "BLOCKED"
    DO_NOT_TRADE = "DO_NOT_TRADE"


class LiveDeploymentStatus(StrEnum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    ACTIVE = "ACTIVE"
    HALTED = "HALTED"


class LiveDailyReviewStatus(StrEnum):
    CLEAN = "CLEAN"
    BLOCKED = "BLOCKED"
    VIOLATION = "VIOLATION"


class LiveApprovalType(StrEnum):
    BROKER = "BROKER"
    ACCOUNT = "ACCOUNT"
    JURISDICTION = "JURISDICTION"
    LIVE_EXECUTION = "LIVE_EXECUTION"


class LiveApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"


class LiveApprovalPacketStatus(StrEnum):
    DRAFT = "DRAFT"
    COMPLETE = "COMPLETE"
    REVOKED = "REVOKED"


class SystemEventSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PredictionMarketVenue(StrEnum):
    KALSHI = "KALSHI"
    INTERNAL_SANDBOX = "INTERNAL_SANDBOX"


class PredictionMarketStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    SETTLED = "SETTLED"
    UNKNOWN = "UNKNOWN"


class PredictionMarketSide(StrEnum):
    YES = "YES"
    NO = "NO"


class PredictionMarketOrderAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class PredictionMarketOrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class PredictionMarketOrderStatus(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECONCILED = "RECONCILED"


class PredictionMarketPositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    SETTLED = "SETTLED"


class PredictionMarketEvidenceKind(StrEnum):
    MARKET_SNAPSHOT = "MARKET_SNAPSHOT"
    SIGNAL_OBSERVATION = "SIGNAL_OBSERVATION"
    ORDER_INTENT = "ORDER_INTENT"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILL_RECEIVED = "FILL_RECEIVED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    POSITION_RECONCILED = "POSITION_RECONCILED"
    SETTLEMENT_RECORDED = "SETTLEMENT_RECORDED"
    PAPER_DEMO_BATCH = "PAPER_DEMO_BATCH"
    PAPER_DEMO_CAMPAIGN = "PAPER_DEMO_CAMPAIGN"
    RISK_BLOCK = "RISK_BLOCK"
    LIVE_GATE = "LIVE_GATE"


class StrategyResearchSource(StrEnum):
    MY_KRYPT_TRADER = "MY_KRYPT_TRADER"
    AUREX = "AUREX"
    MANUAL = "MANUAL"


class StrategyResearchStatus(StrEnum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    BACKTEST_REQUIRED = "BACKTEST_REQUIRED"
    BLOCKED = "BLOCKED"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"


class StrategyResearchObservationType(StrEnum):
    WHALE_TRADE = "WHALE_TRADE"
    MOMENTUM_CLUSTER = "MOMENTUM_CLUSTER"
    CRYPTO_15M = "CRYPTO_15M"
    MANUAL = "MANUAL"
