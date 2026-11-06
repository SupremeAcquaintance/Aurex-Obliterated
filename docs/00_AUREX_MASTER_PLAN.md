# Aurex Master Plan

Version: 0.2
Date: 2026-07-22
Status: Canonical Stage 1-10 roadmap; Stage 4 research active, no eligible strategy, live activation blocked

Current evidence, decisions, and the exact resume point are maintained in
`docs/10_PROJECT_CONTROL.md`. The numbered implementation stages later in this
document describe delivered capabilities; they do not override the evidence-gated
Stage 1-10 program or imply permission to paper- or live-trade.

## 1. Mission

Aurex is a systematic trading research and execution platform.

It is not a promise machine. It is not a signal-selling shortcut. It is a risk-first operating system for building, testing, rejecting, paper-trading, and eventually live-trading strategies only when the evidence is strong enough.

The core question is never:

```text
Will this trade win?
```

The core question is:

```text
Is this setup statistically worth risking capital on under the current rules?
```

Every trade decision must produce:

```text
Signal
Market regime
Strategy score
Risk decision
Expected reward:risk
Invalidation level
Position size
Execution decision
Journal entry
Outcome
```

No stop loss means no trade.
No risk decision means no trade.
No journal entry means no trade.
No backtest and paper evidence means no live trade.

## 2. Non-Negotiable Principles

1. Capital preservation comes before profit.
2. The system must reject trades more proudly than it accepts trades.
3. Paper trading comes before live execution.
4. Live execution is disabled until explicit readiness gates pass.
5. AI may analyze and score, but it does not get final execution authority.
6. Every decision is stored with enough context to audit later.
7. Strategy rules, parameters, market data source, fees, slippage, and risk settings are versioned.
8. No martingale.
9. No averaging down.
10. No hidden discretionary overrides.
11. No cherry-picking results.
12. No target profit deadline. The first $100 profit milestone is only valid if achieved while obeying every risk rule.

## 3. What Was Strong In The Original Research

The original plan already has the right foundation:

1. It separates signals, market state, scoring, risk, paper execution, journaling, and analytics.
2. It correctly puts risk before live trading.
3. It starts with a small strategy set instead of twenty unfocused ideas.
4. It avoids AI until data exists.
5. It includes measurable performance metrics such as expectancy, profit factor, drawdown, and win rate.
6. It treats rejected signals as valuable data, not as noise.

That is the correct philosophy. Aurex keeps that philosophy and sharpens the missing implementation details.

## 4. Holes We Must Fix

### 4.1 Asset Class Is Undefined

The source plan uses `BTCUSDT`, but also talks like a general trading platform. Crypto, equities, options, futures, forex, and CFDs have different data, fees, execution, settlement, leverage, tax, and regulatory constraints.

V1 decision:

```text
Aurex V1 is asset-class aware, but broker neutral.
The first working system supports paper trading for generic symbols and crypto-style 24/7 symbols.
Live broker integration is not implemented until a later gate.
```

Why:

```text
This lets us build the core system without pretending one broker, exchange, or jurisdiction fits all markets.
```

### 4.2 The First $100 Target Is Not Sized

`$100 profit` means very different things on a `$200`, `$500`, `$1,000`, or `$5,000` account.

If the account is `$500` and risk per trade is `0.5%`, each trade risks `$2.50`. If the system expectancy is `0.30R`, average expected profit is about `$0.75` per trade before fees. That would require roughly `134` net-positive trades to reach `$100`, and that assumes the expectancy holds live.

V1 decision:

```text
The first live target is "$100 net realized profit after fees with zero rule violations."
It is not "make $100 fast."
```

### 4.3 Backtesting Rules Are Too Loose

The original plan mentions backtesting but does not define enough controls.

Required fixes:

```text
No look-ahead bias
No future candle access
No changing parameters after seeing results unless recorded as a new run
Separate in-sample and out-of-sample windows
Walk-forward testing before paper deployment
Fees, spread, slippage, and funding costs included where relevant
Data source recorded
Timezone recorded
Strategy version recorded
Risk settings recorded
```

### 4.4 TradingView Webhooks Are Not A Complete Execution System

TradingView webhooks are useful, but they have hard operational limits. TradingView sends alert messages to an external app by HTTP POST, uses `application/json` only when the alert body is valid JSON, warns not to place secrets in the webhook body, only supports webhook ports `80` and `443`, cancels requests taking more than three seconds, and notes that webhook delivery may occasionally fail.

V1 decision:

```text
The webhook endpoint validates fast, stores the raw payload fast, returns fast, and pushes deeper work to a queue or internal service layer.
```

### 4.5 Security Is Missing

The original plan does not define authentication, payload signing, replay protection, or secret handling.

Required fixes:

```text
HTTPS only in production
TradingView-compatible webhook URL secret, plus header auth for controlled API clients
Optional TradingView IP allowlist
Idempotency key per signal
Timestamp freshness window
No broker keys in alert payloads
Secrets loaded only from environment or secret manager
Raw payload stored but sensitive fields redacted
```

### 4.6 Paper Execution Needs Fill Assumptions

Paper execution is meaningless if it assumes perfect fills.

Required fixes:

```text
Order type recorded
Fill model recorded
Spread model recorded
Slippage model recorded
Fees recorded
Partial fill support planned
Latency recorded
Manual close reason recorded
```

### 4.7 Risk Rules Need Account And Session Awareness

The original rules are good but incomplete.

Required fixes:

```text
Per-account risk settings
Per-symbol risk settings
Per-strategy risk settings
Daily and weekly realized P/L limits
Open exposure limit
Correlation group limit
Cooldown after losses
Cooldown after duplicate signals
Emergency kill switch
Maximum stale signal age
Maximum allowed spread/slippage
Market closed/session filter where relevant
```

### 4.8 Analytics Need Confidence, Not Just Totals

A total win rate can hide strategy decay.

Required fixes:

```text
Performance by strategy
Performance by market regime
Performance by symbol
Performance by timeframe
Performance by session/time of day
Rolling expectancy
Rolling drawdown
Distribution of R multiples
Rejected signal analysis
Execution quality analysis
```

### 4.9 Compliance And Broker Rules Are Missing

Frequent intraday trading and margin trading can cause large losses, account restrictions, tax issues, and broker-specific limitations. For U.S. securities accounts, FINRA currently describes risks around frequent intraday trading, cash account settlement, free-riding/good faith violations, margin deficits, and broker margin requirements. Forex and leveraged products have separate CFTC/NFA risk and registration concerns.

V1 decision:

```text
Aurex is a personal research and execution tool first.
It does not manage third-party funds.
It does not sell financial advice.
It does not make live trades until the user-selected broker, account type, asset class, and jurisdiction are documented.
```

## 5. Market And Product Positioning

Aurex should not compete as "another trading bot." That market is crowded and noisy.

Aurex should compete as:

```text
A professional-grade trade research, risk-control, and execution journal for serious systematic traders.
```

The product edge is not magic signals. The edge is process quality:

```text
Clean signal intake
Strict risk enforcement
Replayable decisions
Transparent rejection reasons
Realistic backtests
Forward paper validation
Strategy degradation detection
Operational discipline
```

The first user is one disciplined builder-trader. The future user may be an advanced trader, small team, or prop-style researcher, but V1 must not create compliance risk by presenting itself as a managed-money product.

## 6. Product Experience

Aurex should feel like a premium trading terminal: modern, glassy, data-dense, and disciplined enough for real risk operations. It can be visually striking, but the interface must never sell fantasy or hide the blocking evidence.

The first dashboard should show:

```text
First-screen market preview
Data-driven equity curve visualization
Risk status
Kill switch state
Account equity
Open paper positions
Latest signals
Accepted vs rejected signals
Top rejection reasons
Performance summary
Strategy health
System health
```

Core views:

```text
Command Center
Signals
Risk
Paper Trades
Performance
Strategies
Backtests
System Events
Settings
```

Design rules:

```text
Dense but readable
Fast to scan
Futuristic glassmorphism without sacrificing legibility
TradingView-grade information hierarchy
Dark command-center theme with clear contrast
No hype language
No profit promises
Clear red/yellow/green operational states
Rejected decisions visible, not hidden
Every number traceable to source data
```

## 7. System Architecture

### 7.1 Technology Stack

```text
Backend: Python 3.12, FastAPI
Database: SQLite for local V1; PostgreSQL-compatible path retained for later scale
ORM: SQLAlchemy
Migrations: Alembic
Validation: Pydantic
Testing: Pytest
Queue/cache: Redis plus RQ or Celery when async work is needed
Frontend: React or Next.js
Charts: Lightweight Charts first; TradingView embeds only where useful
Strategies: Pine Script v6 first, Python research strategies later
Containerization: Docker Compose when service orchestration is needed
Logging: structured JSON logs
```

### 7.2 Repository Shape

```text
apps/
  api/
  worker/
  frontend/

src/
  aurex/
    config/
    db/
    domain/
    signal_gateway/
    market_data/
    market_state/
    strategy_engine/
    risk_engine/
    execution_engine/
    journal_engine/
    analytics_engine/
    backtest_engine/
    observability/

pine/
  strategies/

research/
  notebooks/
  datasets/
  reports/

infra/
  docker/
  alembic/

tests/
  unit/
  integration/
  e2e/

docs/
```

Why this shape:

```text
The API and worker are apps.
The trading logic lives in a reusable Python package.
Pine scripts are versioned separately.
Research artifacts stay separate from production code.
```

### 7.3 Core Flow

```text
TradingView Pine Script
  -> Webhook Gateway
  -> Signal Validation
  -> Idempotency Check
  -> Signal Journal
  -> Market State Resolver
  -> Strategy Scoring
  -> Risk Engine
  -> Paper Execution Engine
  -> Trade Journal
  -> Analytics Engine
  -> Dashboard
```

### 7.4 Later Live Flow

```text
Approved Signal
  -> Risk Engine
  -> Broker Adapter
  -> Order Intent
  -> Broker Order
  -> Fill Reconciliation
  -> Position Sync
  -> Trade Journal
  -> Risk Recalculation
```

Live execution is deliberately absent from V1.

## 8. Domain Model

Required tables for V1:

```text
symbols
accounts
risk_profiles
signals
signal_events
market_candles
market_states
strategy_scores
strategy_configs
analyst_notes
risk_decisions
paper_orders
paper_trades
positions
equity_curve_points
strategy_runs
backtest_runs
backtest_results
broker_connections
order_intents
broker_orders
broker_fills
broker_position_snapshots
broker_reconciliation_reports
live_readiness_checks
live_deployment_plans
live_deployment_gates
live_daily_review_reports
live_approval_records
live_paper_evidence_reports
live_broker_statement_reports
live_profit_milestone_reports
live_approval_packets
system_events
```

Important fields:

```text
signals.raw_payload
signals.normalized_payload
signals.idempotency_key
signals.status
signals.rejection_reason
signals.source_timestamp
signals.received_at
signals.processed_at

risk_decisions.signal_id
risk_decisions.approved
risk_decisions.reason
risk_decisions.reward_risk
risk_decisions.risk_amount
risk_decisions.position_size
risk_decisions.rules_snapshot

paper_trades.entry_price
paper_trades.stop_loss
paper_trades.take_profit
paper_trades.exit_price
paper_trades.realized_pl
paper_trades.r_multiple
paper_trades.fees
paper_trades.slippage
paper_trades.close_reason

backtest_runs.strategy_version
backtest_runs.data_source
backtest_runs.data_start
backtest_runs.data_end
backtest_runs.in_sample_start
backtest_runs.in_sample_end
backtest_runs.out_of_sample_start
backtest_runs.out_of_sample_end
backtest_runs.config_hash
backtest_runs.source_format
backtest_runs.source_reference
backtest_runs.evidence_hash

backtest_trades.backtest_run_id
backtest_trades.sequence
backtest_trades.external_trade_id
backtest_trades.entry_at
backtest_trades.closed_at
backtest_trades.realized_pl
backtest_trades.fees
backtest_trades.slippage
backtest_trades.market_regime
backtest_trades.raw_row
```

## 9. Signal Lifecycle

```text
RECEIVED
VALIDATED
REJECTED_INVALID
DUPLICATE_REJECTED
SCORED
RISK_APPROVED
RISK_REJECTED
PAPER_ORDER_CREATED
PAPER_EXECUTED
CLOSED
ANALYZED
```

Every state change creates a `signal_events` row.

## 10. API Contract

V1 endpoints:

```text
GET  /health
POST /webhooks/tradingview
GET  /signals
GET  /signals/{id}
GET  /trades
GET  /trades/{id}
POST /paper/close-trade
POST /paper/reset
GET  /performance/summary
GET  /performance/equity-curve
GET  /strategies
GET  /strategies/comparison
PATCH /strategies/{strategy}
GET  /risk/status
POST /risk/kill-switch
POST /risk/kill-switch/reset
GET  /system/events
POST /backtests/reports
GET  /backtests/reports
GET  /backtests/reports/{id}
GET  /backtests/reports/{id}/csv
GET  /backtests/reports/{id}/trades
POST /backtests/reports/preflight-csv
POST /backtests/reports/import-csv
GET  /backtests/report-template.csv
POST /backtests/ohlcv/preflight-csv
POST /backtests/ohlcv/import-csv
GET  /backtests/ohlcv/datasets
GET  /backtests/ohlcv/datasets/{id}/audit
POST /backtests/reference-replay/preflight
POST /backtests/trades/import-csv
POST /market/candles/import
POST /market/state/compute
GET  /analyst/summary
GET  /analyst/notes
POST /analyst/trades/{trade_id}/review
POST /analyst/trades/{trade_id}/similarity
POST /analyst/risk-anomalies/scan
POST /analyst/strategy-degradation/scan
GET  /broker/readiness
POST /broker/readiness/run
GET  /broker/connections
POST /broker/sandbox/order-intents
GET  /broker/order-intents
POST /broker/sandbox/order-intents/{order_intent_id}/submit
GET  /broker/orders
POST /broker/sandbox/orders/{broker_order_id}/simulate-fill
POST /broker/reconciliation/run
GET  /broker/reconciliation
POST /broker/emergency-stop
GET  /live/deployment
PATCH /live/deployment/plan
POST /live/deployment/checks/run
POST /live/deployment/daily-review
GET  /live/deployment/daily-reviews
POST /live/deployment/approvals
GET  /live/deployment/approvals
POST /live/deployment/paper-evidence/run
GET  /live/deployment/paper-evidence
POST /live/deployment/broker-statements/reconcile
POST /live/deployment/broker-statements/preflight-csv
POST /live/deployment/broker-statements/reconcile-csv
GET  /live/deployment/broker-statements
POST /live/deployment/profit-milestone/run
GET  /live/deployment/profit-milestones
POST /live/deployment/approval-packet
GET  /live/deployment/approval-packets
POST /live/deployment/activation-attempt
POST /paper/evidence/preflight-csv
POST /paper/evidence/import-csv
GET  /paper/evidence/collection-status
GET  /paper/evidence/imports
GET  /paper/evidence/imports/{batch_id}
GET  /paper/evidence/template.csv
```

TradingView webhook payload:

```json
{
  "source": "tradingview",
  "strategy": "trend_pullback_v1",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "direction": "LONG",
  "entry_price": 68250.50,
  "stop_loss": 67800.00,
  "take_profit": 69200.00,
  "market_regime": "TRENDING_UP",
  "timestamp": "2026-06-05T10:15:00Z"
}
```

## 11. Risk Engine

Default settings:

```text
paper_account_equity: 1000.00
risk_per_trade: 0.005
max_daily_loss: 0.01
max_weekly_loss: 0.03
max_open_positions: 3
minimum_reward_risk: 1.5
duplicate_cooldown_minutes: 30
max_signal_age_seconds: 180
loss_cooldown_count: 3
```

Position sizing:

```text
risk_amount = account_equity * risk_per_trade
position_size = risk_amount / abs(entry_price - stop_loss)
```

Long reward:risk:

```text
risk = entry_price - stop_loss
reward = take_profit - entry_price
reward_risk = reward / risk
```

Short reward:risk:

```text
risk = stop_loss - entry_price
reward = entry_price - take_profit
reward_risk = reward / risk
```

Reject if:

```text
Missing stop loss
Missing take profit
Invalid direction
Invalid price relationship
Reward:risk below minimum
Daily loss limit reached
Weekly loss limit reached
Max open positions reached
Duplicate signal within cooldown
Signal is stale
Kill switch enabled
Market regime is incompatible with strategy
```

## 12. Strategy Roadmap

We start with one strategy, not three.

Reason:

```text
One strategy lets us prove the full system loop with less noise.
After the loop is trustworthy, we add strategy diversity.
```

### Strategy 1: trend_pullback_v1

Best regime:

```text
TRENDING_UP
TRENDING_DOWN
```

Long logic:

```text
Higher timeframe EMA 50 > EMA 200
Current timeframe close > EMA 200
Pullback near EMA 20 or EMA 50
RSI 14 above 40 and below 65
Bullish confirmation candle closes above previous high
Stop loss from recent swing low or ATR
Take profit at configured reward:risk
```

Short logic:

```text
Higher timeframe EMA 50 < EMA 200
Current timeframe close < EMA 200
Pullback near EMA 20 or EMA 50
RSI 14 below 60 and above 35
Bearish confirmation candle closes below previous low
Stop loss from recent swing high or ATR
Take profit at configured reward:risk
```

Later strategies:

```text
volatility_breakout_v1
range_mean_reversion_v1
```

## 13. Backtesting Standard

Backtesting must happen before paper deployment of a strategy.
Accepted backtesting must also be proven before a live micro-deployment plan can advance.

Minimum backtest report:

```text
Strategy name and version
Symbol set
Timeframes
Data source
Data date range
In-sample period
Out-of-sample period
Fees
Spread
Slippage
Starting equity
Risk settings
Total trades
Win rate
Average win
Average loss
Expectancy
Profit factor
Max drawdown
Largest loss
Longest losing streak
R multiple distribution
Performance by regime
Parameter snapshot
```

Minimum acceptance gate:

```text
At least 100 historical trades
Out-of-sample profit factor >= 1.15
Out-of-sample expectancy > 0
Max drawdown compatible with risk profile
No unexplained trades
No rule violations
```

Stronger gate:

```text
300+ historical trades
Walk-forward validation
Monte Carlo trade-order stress test
Performance survives higher slippage assumptions
No single trade or single day dominates results
```

## 14. Paper Trading Standard

Minimum before live readiness review:

```text
100 paper trades
30 calendar days minimum
At least 15 active trading days
No single day may contain more than 25% of counted trades
Positive expectancy
Profit factor >= 1.20
Max drawdown within configured limit
No broken execution logic
No unexplained trades
No manual cherry-picking
No risk rule violations
```

Stronger standard:

```text
300+ paper trades
90 calendar days
Positive expectancy by rolling 30-trade window
Strategy still works after realistic costs
Rejected signals show risk engine is functioning
```

## 15. First Live $100 Profit Protocol

This stage is not allowed until all previous gates pass.

Prerequisites:

```text
Asset class selected
Broker/exchange selected
Broker terms reviewed
Jurisdiction/account constraints documented
Live adapter tested in sandbox where available
Emergency kill switch tested
Position sync tested
Fee/slippage model updated from broker data
Paper-to-live checklist completed
```

Live risk settings:

```text
risk_per_trade: 0.25% to 0.50%
max_daily_loss: 1%
max_weekly_loss: 3%
max_open_positions: 1 to 3
no leverage unless explicitly approved later
stop after 3 consecutive losses
stop after any platform or broker mismatch
```

The first $100 milestone is achieved only when:

```text
Net realized P/L after fees >= $100
Every trade followed the rules
Every trade has a journal entry
No emergency overrides were needed
No max daily or weekly loss rules were breached
Performance analytics reconcile with broker statements
```

Failure conditions:

```text
Daily loss limit hit
Weekly loss limit hit
3 consecutive losses
Unexpected broker fill behavior
Unexplained position mismatch
Strategy expectancy turns negative over rolling live window
Any emotional/manual override outside the system
```

If a failure condition triggers, Aurex stops live trading and returns to analysis.

## 16. Stage By Stage Implementation Path

### Stage 0: Blueprint And Project Contract

Implement:

```text
Create the Aurex master plan
Define stage gates
Define architecture
Define V1 boundaries
Define no-live-trading rule
```

Done when:

```text
This document exists
The user agrees this is the path
Stage 1 can begin
```

### Stage 1: Backend Skeleton

Implement:

```text
Python project structure
FastAPI app
Settings module
Health endpoint
Pytest setup
Local SQLite persistence
Basic structured logging
```

Done when:

```text
GET /health returns OK
Tests run locally
Alembic migrates the local SQLite database
No trading logic exists yet
```

### Stage 2: Database And Migrations

Implement:

```text
SQLAlchemy models
Alembic migrations
Enums for lifecycle states
Database session management
Test database fixtures
```

Done when:

```text
Migrations apply cleanly
Core models persist and query correctly
Unit tests cover model creation
```

### Stage 3: TradingView Signal Gateway

Implement:

```text
POST /webhooks/tradingview
Pydantic payload validation
Raw payload storage
Normalized signal storage
Idempotency key
Duplicate rejection
Authentication
Fast response behavior
Signal event history
```

Done when:

```text
Valid webhook is accepted
Malformed webhook is rejected
Duplicate webhook is rejected
Raw and normalized payloads are stored
Rejection reasons are stored
Tests cover all cases
```

### Stage 4: Risk Engine

Implement:

```text
Risk profile settings
Reward:risk calculation
Position sizing
Daily loss rule
Weekly loss rule
Open position rule
Missing stop/take-profit rule
Stale signal rule
Kill switch rule
RiskDecision storage
```

Done when:

```text
Approved signals include position size
Rejected signals include exact reason
Risk tests pass
No paper trade can be created without risk approval
```

### Stage 5: Paper Execution Engine

Implement:

```text
Paper order creation
Paper trade creation
Open position tracking
Manual close endpoint
Realized P/L
R multiple
Fees and slippage fields
Equity curve updates
```

Done when:

```text
Risk-approved signals create paper trades
Manual close calculates P/L correctly
Equity curve updates
Paper reset works safely
Tests cover long and short trades
```

### Stage 6: Analytics Engine

Implement:

```text
GET /performance/summary
GET /performance/equity-curve
Expectancy
Profit factor
Win rate
Average win
Average loss
Max drawdown
Net P/L
Equity curve points
Best and worst strategy
Breakdown by regime
```

Done when:

```text
Metrics match known fixture data
Equity curve returns chronological latest points
Zero-trade state is handled cleanly
Tests cover edge cases
```

### Stage 7: Pine Strategy V1

Implement:

```text
pine/strategies/trend_pullback_v1.pine
Pine Script v6 strategy
Non-repainting logic
strategy.entry calls
strategy.exit calls
Webhook-ready JSON alert messages
Inputs for EMA, RSI, ATR, reward:risk, higher timeframe, long/short toggles
```

Done when:

```text
Script is ready to paste into TradingView
Alert body matches Aurex API contract
No future-looking data is used
Backtest settings are documented
```

### Stage 8: Historical Backtest Lab

Implement:

```text
Historical OHLCV data adapter
Immutable OHLCV dataset and candle ledger
Dataset provenance, quality snapshot, and integrity audit
Comparison-only deterministic reference replay
TradingView trade-level parity preflight and immutable mismatch ledger
Backtest run model
Backtest report model
Persisted normalized TradingView completed-trade ledger
Deterministic trade-evidence hash and integrity audit
Cost model
Slippage model
Strategy parameter snapshot
Outcome-blind deterministic anchored-fold planner
Immutable single-use pre-registered test protocol
CSV import/export for reports
```

Done when:

```text
A backtest report can be stored
Historical input data is preflighted, versioned, and independently re-hashed
Reference replay is causal, dataset-bound, deterministic, and acceptance-ineligible
Parity binds audited TradingView and OHLCV evidence, reports every disagreement, and remains acceptance-ineligible
Imported completed trades can be retrieved and independently re-hashed
Metrics are calculated consistently
Strategy version and config hash are recorded
Fold dates are planned without inspecting result data or mutating the ledger
The test protocol is frozen before external results are inspected
Acceptance gate can approve or reject a strategy
```

### Stage 9: Paper Trading Dashboard

Implement:

```text
Frontend shell
Command Center
Signals table
Risk panel
Paper trades table
Performance summary
System events feed
Kill switch control
```

Done when:

```text
The dashboard shows real backend data
Risk state is visible
Rejected signals are easy to inspect
No live trading controls exist
```

### Stage 10: Market State Engine

Implement:

```text
EMA slope regime
ADX regime
ATR percentile
Volume relative average
VWAP distance
Higher timeframe trend
Regime confidence score
```

Done when:

```text
Signals can be enriched with computed market regime
Regime logic is testable
Strategy compatibility rules use regime data
```

### Stage 11: Strategy Portfolio

Implement:

```text
volatility_breakout_v1
range_mean_reversion_v1
Strategy comparison
Strategy enable/disable controls
Per-strategy risk settings
```

Done when:

```text
Each strategy has independent metrics
Bad strategies can be disabled without touching others
Portfolio exposure is controlled
```

### Stage 12: AI Analyst Layer

Implement only after enough trade data exists:

```text
Trade quality summaries
Pattern similarity search
Risk anomaly detection
Strategy degradation detection
Post-trade review notes
```

Done when:

```text
AI outputs are advisory only
Risk engine remains final authority
AI recommendations are stored and auditable
```

### Stage 13: Live Broker Readiness

Implement:

```text
Broker adapter interface
Sandbox broker adapter where available
Order intent model
Fill reconciliation
Position sync
Fee/cost reconciliation
Broker statement reconciliation
Emergency stop path
Live-readiness checklist
```

Done when:

```text
Sandbox tests pass
Paper and broker fills can be reconciled
Broker-reported fees reconcile with Aurex recorded order costs
Live mode is still disabled by default
User explicitly approves broker and account settings
```

### Stage 14: Live Micro-Deployment

Implement:

```text
Live mode flag
Tiny risk settings
One broker
One account
One to three symbols
One proven strategy
Daily review report
Automatic stop rules
Live deployment plan
Live deployment gates
Activation attempt audit
```

Done when:

```text
The system can trade live under strict limits
Every live trade is reconciled
The first $100 protocol can be attempted
```

Current Stage 14 guard implementation:

```text
The control plane exists.
Activation remains blocked.
No live broker execution adapter exists yet.
The live_execution_adapter_ready gate exposes that missing adapter as a required blocker.
The live flag remains disabled.
Broker, account, jurisdiction, paper evidence, daily review, kill-switch, and explicit approval gates are auditable.
Approval records store who approved or revoked each live-readiness domain.
Accepted-backtest evidence requires a stored passing backtest report for the selected deployment strategy and symbols.
The live-readiness backtest gate does not trust a report solely because its submitted criteria say "accepted"; it requires a matched immutable single-use protocol registered before report evaluation, at least 100 historical trades, at least 30 out-of-sample trades, positive out-of-sample expectancy, out-of-sample profit factor >= 1.15 when losses exist, a declared max-drawdown limit, non-overlapping sample windows, at least 15 active backtest trading days, no single day above 25% of counted backtest trades, at least 3 explicit anchored fixed-parameter walk-forward folds with valid chronology, matching parameter fingerprints, intact protocol/trade/walk-forward evidence hashes, and at least a 66% pass rate, full market-regime coverage, and recorded cost, slippage, and risk assumptions. Automatically partitioned trade slices remain diagnostic and cannot satisfy this gate.
Paper-evidence reports snapshot only the selected deployment strategy and symbols against the 100-trade, 30-calendar-day, sustained active-day coverage, single-day concentration, expectancy, profit-factor, drawdown-limit, unexplained-trade, risk-lineage, and journal-coverage requirements.
The paper_evidence_complete gate compares each PASS report against the current trade, journal, risk-lineage, and plan-scope ledger; any later ledger change blocks readiness until the report is rerun.
Approval packets link the reviewed broker, account type, asset class, jurisdiction, fee schedule, margin policy, terms, account-constraint, execution-policy, fee/slippage-model, and paper-to-live checklist references without storing live credentials or allowing leverage.
The dashboard can submit review-only approval packets with broker, account, jurisdiction, and due-diligence references; leverage and credential flags keep the packet in draft.
The dashboard can record or revoke explicit broker, account, jurisdiction, and live-execution approvals, updating the approval snapshot without enabling live trading.
The dashboard can run the first-profit milestone audit, which records whether the $100 protocol is clean and includes the live execution adapter audit while live execution remains disabled until a future adapter exists.
The dashboard can surface the latest activation-attempt audit message and blocking gate keys without attempting live execution.
Broker reconciliation snapshots broker fill-fee totals, Aurex paper-order costs, implied slippage, paper-trade costs, and broker/Aurex position state; any broker fee mismatch blocks readiness.
Broker-statement reports compare reviewed statement trade count, net P/L, fees, and slippage against Aurex closed-trade analytics; any mismatch blocks the statement-reconciliation gate.
Broker-statement CSV preflight and reconciliation derive those statement totals from external closed-trade exports so the operator does not hand-calculate the gate inputs.
The broker_statement_reconciliation gate compares PASS reports against the current statement-window ledger; later trade, P/L, fee, slippage, scope, or window drift blocks readiness until reconciliation is rerun.
First-profit milestone reports audit net realized P/L after fees against the $100 target, journal coverage, risk lineage, daily/weekly loss breaches, kill-switch state, and broker statement reconciliation, but remain blocked until live broker execution is implemented.
```

### Stage 15: Real Paper Evidence Intake

Implement:

```text
Paper evidence CSV import endpoint
Paper evidence CSV preflight endpoint
Import batch ledger
Import history and detail views
Collection status endpoint
CSV template endpoint
Dashboard paper-evidence intake panel
Required external trade IDs
Required source reference
Duplicate external-trade detection
Stop-distance risk reconciliation
Closed paper-trade reconstruction
Signal, risk-decision, paper-order, paper-trade, position, equity-curve, and journal lineage
Row-level import outcomes
Preflight and import analysis summaries
Stage 14 paper-evidence compatibility
Broker statement CSV preflight and reconciliation
```

Done when:

```text
Real paper-platform exports can be imported without hand-entering every trade
Duplicate imports do not double-count trades
Preflight validates rows without mutating the paper ledger
Malformed rows are rejected with row-level reasons
Rejected rows are summarized into a fix queue for operator repair
Imported risk amount reconciles to abs(entry - stop loss) * quantity
Imported evidence has no unexplained trades when required lineage is complete
Imported evidence has full journal coverage when journal fields are supplied
Collection status exposes remaining trades, calendar days, active days, and blocking reasons
Broker statement CSV exports derive reconciliation totals without mutating readiness during preflight
Broker/account/jurisdiction approval packets can be documented from the dashboard without storing credentials
Explicit approval records can be documented from the dashboard while live mode remains disabled
The first-profit milestone audit can be run from the dashboard without enabling live execution
Activation-attempt blockers can be reviewed from the dashboard after an audit
Live mode remains disabled
```

Current Stage 15 implementation:

```text
POST /paper/evidence/preflight-csv validates strict CSV text and returns row-level READY, SKIPPED, and REJECTED outcomes without creating an import batch or paper trades.
POST /paper/evidence/import-csv accepts strict CSV text with source and source_reference.
GET /paper/evidence/collection-status returns accepted-backtest status, paper-evidence status, import totals, remaining trade/day gaps, blocking reasons, and next actions.
GET /paper/evidence/imports lists recent import batches for operator review.
GET /paper/evidence/imports/{batch_id} returns one import batch with row-level outcomes.
GET /paper/evidence/template.csv returns the strict CSV template.
paper_evidence_import_batches stores the source, source reference, import hash, counts, row outcomes, and evidence snapshot.
Preflight and import responses include an analysis summary with status counts, rejected reasons, fix queue, active trading days, calendar span, net P/L, fees, slippage, and strategy/symbol/direction coverage.
Each imported row reconstructs a closed PaperTrade with a Signal, approved RiskDecision, filled PaperOrder, closed Position, EquityCurvePoint, and TradeJournalEntry.
The importer requires external_trade_id, timestamps, prices, stop loss, take profit, quantity, risk amount, fees, slippage, close reason, journal author, journal thesis, rule_followed, and emotional_override.
Duplicate source/external_trade_id rows are skipped instead of double-counted.
Duplicate external_trade_id values inside the same CSV are rejected before import.
Rows with invalid direction, invalid price geometry, bad timestamps, negative costs, mismatched stop-distance risk, or mismatched provided realized P/L are rejected.
Stage 14 paper-evidence reports can audit imported trades through the existing integrity and journal checks without special exemptions.
Stage 14 paper-evidence reports independently flag any closed paper trade whose stored risk_amount does not match abs(entry - stop loss) * quantity.
Stage 14 paper-evidence reports block shallow calendar coverage when active trading days are too low or one day dominates the trade count.
Stage 14 paper-evidence reports exclude trades outside the selected deployment strategy and symbol list, while surfacing out-of-scope counts for review.
The dashboard exposes a glassmorphism command-center experience with a market preview, source/reference entry, CSV template loading, CSV preflight, CSV import, latest batch review, export-window analysis, fix-queue visibility, approval-packet submission, explicit approval records, first-profit milestone checks, activation-audit blockers, collection status, Paper scope, and Paper coverage visibility.
Live trading remains blocked.
```

## 17. Testing Strategy

Required tests:

```text
Valid webhook accepted
Invalid webhook rejected
Missing stop loss rejected
Missing take profit rejected
Invalid long price geometry rejected
Invalid short price geometry rejected
Bad reward:risk rejected
Position sizing correct
Daily loss limit blocks trade
Weekly loss limit blocks trade
Duplicate signal cooldown works
Kill switch blocks trade
Paper long close calculates P/L
Paper short close calculates P/L
Performance summary calculates metrics correctly
Backtest report stores config hash
Accepted backtest live-readiness gate blocks missing or wrong-scope evidence
Paper evidence import creates auditable closed trades
Paper evidence preflight validates without mutating the ledger
Paper evidence import rejects duplicate external trade IDs inside one CSV
Paper evidence preflight exposes an analysis summary and fix queue
Paper evidence collection status reports missing and partial readiness evidence
Paper evidence duplicate import does not double-count
Paper evidence missing required CSV headers is rejected
Paper evidence risk amount mismatch is rejected and audited
```

Test layers:

```text
Unit tests for pure calculations
Integration tests for API + database
Contract tests for webhook payload
Regression tests for analytics fixtures
End-to-end tests for signal -> risk -> paper trade
```

## 18. Source Constraints Checked

Primary references reviewed while creating this plan:

1. TradingView webhook documentation: https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/
2. TradingView Pine Script alerts documentation: https://www.tradingview.com/pine-script-docs/concepts/alerts/
3. TradingView Pine Script v6 reference: https://www.tradingview.com/pine-script-reference/v6/
4. FINRA frequent intraday trading overview: https://www.finra.org/investors/insights/frequent-intraday-trading
5. SEC Investor.gov day trading risk overview: https://www.investor.gov/additional-resources/spotlight/directors-take/thinking-day-trading-know-risks
6. CFTC forex fraud and risk overview: https://www.cftc.gov/LearnAndProtect/forexfrauds

## 19. Current Build Position

We are at:

```text
Stage 4: Real-market strategy research
Stage 5: No eligible strategy
```

Next action:

```text
Preserve the rejected slow_breakout_spot_v1 holdout, complete its mechanism-level
postmortem, and define a separately versioned hypothesis with a genuinely untouched
decision set. In parallel, complete authentic TradingView parity and webhook proof
only with the required operator authority. Do not start forward paper evidence until
a strategy passes the frozen eligibility gates.
```

Later-stage paper evidence capabilities already exist, including batch fingerprinting,
external-trade idempotency, row-level outcomes, reconstructed lineage, equity-curve
updates, and journal coverage. Capability is not readiness. Live activation remains
blocked until accepted backtest evidence, broker/account/jurisdiction settings,
forward paper evidence, reconciliation, kill-switch state, daily review, explicit user
approval, and a qualified live execution adapter are all proven.

## 20. My-Krypt-Trader Integration Track

My-Krypt-Trader is not replacing Aurex. It is a donor codebase for useful ideas around
prediction-market workflows, paper/demo order lifecycle, reconciliation, credential handling,
logging, desktop/operator UX, and visual polish.

The integration contract is documented in:

```text
docs/03_MKT_INTEGRATION_BLUEPRINT.md
```

Current integration position:

```text
Stage K0: Complete. Aurex/MKT adopt, rewrite, reject, and defer decisions are documented.
Stage K1: Complete. Aurex-native prediction-market primitives are implemented with migration tests.
Stage K2: Complete for manual/API/dashboard intake. MKT signal ideas can be recorded as disabled
          strategy research candidates and observations with evidence hashes, forced
          trade_eligible=false. Bounded MKT SQLite import can ingest whale_trades, alerts,
          and crypto15m_signals as research-only observations.
Stage K3: Backend/API core complete. Paper-only prediction-market simulator supports risk rejection,
          latency/spread/depth snapshots, partial fills, stale expiration, fee-net settlement,
          evidence inspection, reconciliation, and research-gate rejection snapshots for mkt_*
          paper intents that lack accepted Aurex candidate evidence.
Stage K4: Core resolved-observation gate complete. MKT-derived observations can be evaluated as
          fee-net binary-contract paper trades with chronological OOS, active-day, concentration,
          walk-forward, maximum OOS drawdown, regime/category coverage, regime pass-rate, and
          multiple-tested-variant checks plus Bonferroni-adjusted OOS binomial significance before
          paper eligibility. Each gate run is persisted in
          strategy_research_backtest_runs with metrics, requirements, reasons, reviewed time, and
          evidence hash. Deeper regime reports are still not implemented.
Stage K5: First operator view complete. The dashboard exposes a paper-only Prediction Markets tab
          for snapshots, paper intents, submissions, stale expiration, settlement, reconciliation,
          contracts, orders, positions, evidence, snapshot CSV preflight/import, paper-demo
          progress, guided demo run controls, paper-intent research gate status, and
          research-candidate backtest gates. The
          Strategy tab now surfaces latest research gate decision, first blocker, OOS edge,
          OOS drawdown, regime/category coverage, variant pressure, gate-run history, and selected
          candidate observation evidence through the research evidence drilldown. It also exposes
          a research readiness queue that ranks candidates by evidence state and next action without
          presenting that queue as a profitability ranking.
Stage K6: Readiness checkpoint started. The API exposes
          /prediction-market/paper/demo-readiness, /prediction-market/paper/demo-progress,
          /prediction-market/paper/demo-ledger, /prediction-market/paper/demo-run,
          /prediction-market/paper/demo-batch-preflight, and
          /prediction-market/paper/demo-batch-run.
          The dashboard shows paper-demo readiness, start readiness, demo lifecycle verification,
          paper-demo evidence progress, demo ledger rows, guided demo controls, guarded batch
          preflight/replay controls, and the next demo action.
          Demo progress requires closed-record count, calendar-day coverage,
          active-day coverage, single-day concentration, fee-net expectancy, profit factor,
          drawdown visibility, unique-contract coverage, single-contract concentration,
          imported snapshot provenance, clean/countable ledger coverage, and matched
          reconciliation after the latest settlement before live review can be considered.
          The demo ledger exposes each closed record's strategy attribution, source/import
          provenance, evidence hash, reconciliation state, fees, P/L, countable state, and
          blockers.
          Batch preflight previews eligible/skipped imported resolved snapshots without mutating
          the ledger. Batch replay runs those snapshots through the same paper/demo lifecycle and
          skips duplicate settled contract/strategy records.
          MKT donor runbook, demo donor bootstrap, donor launch preflight, donor collection status,
          runtime safety preflight, donor readiness, DB discovery, candidate inspection, DB
          inventory, data readiness, campaign readiness, and campaign manifest checks can report
          missing MKT checkout/code/data paths, setup state, demo/dry-run runtime safety, selected
          runtime settings/userData path candidates, workspace-local donor runtime scaffolds,
          launch prerequisites, missing or empty donor DBs, log-file metadata, table counts,
          resolved research rows, replay candidates, missing research gates, blocked projections,
          side-rationale gaps, stable replay-plan hashes, and live-disabled controls before replay.
          MKT DB campaign preflight/run can preview bounded direct-DB imports without mutation or
          import and replay them through the guarded paper/demo lifecycle in one paper-only
          operation. Campaign preflight now also projects fee-net replay outcomes and the first
          failed progress gate without writing evidence. It also compares the opposite side so
          operators can see when a projection is side-sensitive or likely hindsight-dependent.
          Campaign manifest builds a non-mutating replay plan from the selected DB import, side,
          strategy, risk controls, projections, blockers, and live-disabled state before replay.
          Side-sensitive campaign replay requires explicit acknowledgement and a side-selection
          rationale before evidence is written. Accepted campaign replay records a
          PAPER_DEMO_CAMPAIGN evidence event with import, replay, progress, side-warning, and
          rationale context. A campaign-audit endpoint and dashboard table summarize those
          campaign evidence events for review.
          Live deployment now surfaces this paper/demo campaign quality as a required gate for
          mkt_* deployment strategies and as not applicable for ordinary non-MKT strategies.
          Prediction contract snapshots can be preflighted/imported from Aurex-format CSV, MKT
          markets CSV exports, or bounded direct My-Krypt-Trader SQLite markets imports before
          paper/demo operation, including resolved market outcomes that can settle guided
          paper/demo runs. The 100 closed paper/demo records over at least 30 calendar days are
          not collected yet.
Stage K7: Started at the readiness-guard level only. The adapter is still not implemented, but
          the live-deployment guard can now block MKT/prediction-market candidates on missing
          campaign-quality evidence before any adapter work is considered.
Stage K8: Not started.
Live execution: Still blocked.
```

The prediction-market simulator is not proof of edge. It is infrastructure for honest testing.
Any MKT-derived whale, momentum, or crypto-event idea must pass Aurex backtest, paper evidence,
risk, reconciliation, and explicit approval gates before real capital is considered.

## Core Pine Promotion Hardening

Known Pine strategies distinguish statistical acceptance from permission to advance.
A report submitted as raw JSON can still be measured and preserved as research
evidence, but the public JSON endpoint rejects self-declared TradingView provenance and
the report cannot unlock signals, paper, or live readiness.

Promotion requires the TradingView completed-trades CSV importer, an exact SHA-256
fingerprint of the uploaded artifact, a TradingView strategy-tester source reference,
complete persisted trade fields, registry-matching commission/slippage assumptions, an
intact pre-registered protocol, and all existing OOS, walk-forward, drawdown, regime,
and concentration gates. Paper eligibility and live readiness use the same policy.

The artifact fingerprint proves which operator-supplied bytes Aurex received; it is not
a TradingView signature and cannot prove that the file was never edited before upload.
Older reports without a fingerprint are intentionally promotion-blocked and must be
recreated by registering a new protocol and re-importing the retained original CSV.
See `docs/08_TRUSTED_BACKTEST_PROMOTION.md`.
