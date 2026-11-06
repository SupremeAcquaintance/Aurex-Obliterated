# Aurex + My-Krypt-Trader Integration Blueprint

Date: 2026-06-25
Status: Stage K0, K1, K2, K3, stronger K4 gate ledger, first K5 evidence drilldown, and K6 paper-demo readiness checkpoint verified locally

## Mission

Aurex remains the source of truth. My-Krypt-Trader is a donor system for useful execution,
Kalshi/prediction-market operations, credential handling, reconciliation behavior, logs, profiles,
and desktop/operator UX.

The target is not to copy a trading bot. The target is to make Aurex a money-seeking operating
system that protects capital, proves edge before risk, and blocks live execution until evidence,
risk, reconciliation, and explicit approval all pass.

## Reality Check

Neither Aurex nor My-Krypt-Trader currently proves profitable signals. Aurex is stronger in
evidence gates, risk governance, backtest discipline, and live blocking. My-Krypt-Trader is stronger
in packaged desktop operations, Kalshi-oriented order lifecycle handling, credential ergonomics,
position rescue, stale order cancellation, and operator-facing logs.

Therefore:

```text
Adopt MKT execution and UX lessons.
Rewrite them into Aurex-native evidence and risk boundaries.
Reject unproven strategy claims and live toggles.
Defer real live venue adapters until paper/demo evidence passes.
```

## Adopt

These pieces are worth absorbing, after rewriting into Aurex style:

1. Kalshi/prediction-market operational concepts: binary contracts, yes/no sides, event tickers,
   order books, fills, settlements, fees, and reconciliation.
2. Order lifecycle behavior: submitted, partially filled, filled, cancelled, rejected, expired, and
   reconciled states.
3. Partial-fill and restart-safe thinking: orders and positions must be reconstructed from durable
   records, not trusted from in-memory state.
4. Stale order cancellation: paper/demo and later live adapters must expire unsupported or stale
   order intents.
5. Credential workflow principles: separate demo/live environments, never place keys in TradingView
   webhooks, and avoid UI designs that make live activation casual.
6. Operator UX ideas: profiles, API-key workflow, logs, positions, signals, history, settings,
   notifications, status badges, and a more terminal-like visual system.
7. Local desktop packaging direction: useful later, but Aurex backend remains the authoritative
   control plane.

## Rewrite

These ideas are useful but must be rewritten before entering Aurex:

1. MKT signal scanners become research candidates only. They cannot be treated as profitable.
2. MKT backtests must be replaced with chronological IS/OOS, walk-forward, cost-adjusted,
   concentration-aware, regime-aware Aurex evidence.
3. MKT confidence/edge scoring must be rebuilt so edge is not circularly derived from market price.
4. MKT live P/L must be fee-net, statement-reconciled, and tied to immutable evidence events.
5. MKT crypto 15-minute market handling must use durable opening prices and venue snapshots, not
   first-observed process memory.
6. MKT desktop UI should inspire Aurex visuals, but navigation and data must remain clear,
   URL-addressable, and gate-oriented.

## Reject

These pieces do not belong in Aurex:

1. Any gambling/roulette/secret-strategy mode.
2. Any direct live toggle that bypasses accepted evidence, risk, reconciliation, and explicit
   approval.
3. Presets that imply reliability from small or in-sample tests.
4. Circular edge calculations where confidence is mostly market-implied price plus arbitrary points.
5. Duplicate ledgers that let a UI state drift away from Aurex evidence.
6. Marketing claims, profit promises, or urgency around the first $100 target.

## Defer

These items are important but not first:

1. Real Kalshi live adapter with current API compatibility.
2. OS-native desktop packaging for Aurex.
3. Advanced credentials vault UX.
4. Automated live order cancellation against a real venue.
5. Multi-venue prediction-market support.
6. Real-time websocket market-data subscriptions.

## Architecture Direction

The Aurex prediction-market vertical is layered like this:

```text
Prediction Market Research
  -> Market/contract snapshots
  -> Research signal observations
  -> Backtest and paper simulation
  -> Risk decision
  -> Prediction order intent
  -> Paper/demo order
  -> Fill records
  -> Position records
  -> Settlement records
  -> Reconciliation report
  -> Immutable evidence event
  -> Live gate audit
```

The live boundary remains:

```text
No accepted backtest evidence -> no paper order eligibility
No 100-trade/30-day paper evidence -> no live readiness
No broker/account/jurisdiction/fee documentation -> no live readiness
No reconciliation -> no live readiness
No explicit approval -> no live readiness
No implemented live adapter -> no live execution
```

## Stage Plan

### Stage K0: Integration Contract

Deliverables:

```text
docs/03_MKT_INTEGRATION_BLUEPRINT.md
Adopt/rewrite/reject/defer decisions
Prediction-market stage map
Explicit no-live-transfer rule
```

Done when:

```text
The blueprint exists and names what Aurex will absorb from MKT without replacing Aurex.
```

### Stage K1: Prediction-Market Primitives

Deliverables:

```text
Prediction-market enums
Market, contract, order intent, order, fill, position, settlement, reconciliation, and evidence tables
Binary contract fee, cost, average fill, payout, and fee-net settlement calculations
Unit and integration tests
```

Done when:

```text
Aurex can persist a complete paper prediction-market lifecycle without adding live execution.
```

### Stage K2: Research Candidate Intake

Deliverables:

```text
MKT whale, momentum, and crypto-event ideas represented as research observations
No trusted execution path
Evidence hashes for imported observations
Candidate status in strategy review
```

Done when:

```text
MKT-derived signals can be studied in Aurex without being trade-eligible by default.
```

Current implementation:

```text
Strategy research candidates are persisted in strategy_research_candidates.
Individual MKT-derived observations are persisted in strategy_research_observations.
The intake API lives under /strategies/research-candidates.
MY_KRYPT_TRADER candidates are forced to trade_eligible=false.
If an MKT candidate requests PAPER_ELIGIBLE, Aurex downgrades it to BACKTEST_REQUIRED.
Registering a candidate creates or updates a disabled StrategyConfig with research_candidate=true.
Observation intake dedupes repeated source_event_id values and records deterministic evidence hashes.
The dashboard Strategy tab shows research candidates and can record candidate/observation intake.
The dashboard and API can import MKT SQLite rows from whale_trades, alerts, and crypto15m_signals
into Aurex research candidates through /strategies/research-candidates/import-mkt.
Operators can run /strategies/research-candidates/mkt-intake-readiness and
/strategies/research-candidates/preflight-mkt first to inspect the same quality verdict without
writing candidates or observations.
Research intake readiness also reports donor DB freshness, bounded scoped log-file metadata, a
scoped start-command hint, and collection-health state so operational collection status is visible
before any research import.
The /strategies/research-candidates/mkt-intake-runbook endpoint turns those checks into an ordered
non-mutating operator checklist before any MKT research rows are written to Aurex.
It also exposes the current actionable step and checklist progress so the dashboard can show the
next blocker or ready ledger-writing action without weakening evidence gates.
When the current step has a manual command, the runbook exposes it as a display-only current command.
The import response reports processed, resolved, and unresolved observation counts plus per-source
quality targets so sparse MKT samples are visibly not backtest-depth evidence.
Sparse or unresolved imports require an explicit research-only acknowledgement before the mutating
import writes observations.
Imported candidates persist the import-quality and source-quality context so sparse MKT provenance
remains visible during later research review.
Imported MKT confidence/edge inputs are preserved as metadata, not trusted profitability.
No candidate is paper-eligible or live-eligible from this path.
```

### Stage K3: Realistic Paper Simulator

Deliverables:

```text
Spread-aware entry model
Latency model
Partial-fill model
Rejected-order model
Stale-order cancellation
Manual open-order cancellation
Fee model marked as paper unless venue-confirmed
Settlement simulation
Reconciliation report
```

Done when:

```text
Paper prediction-market orders can fail, partially fill, expire, settle, and reconcile realistically.
```

Current implementation:

```text
src/aurex/prediction_market/paper.py implements a paper-only binary contract simulator.
src/aurex/api/routes/prediction_market.py exposes the simulator through paper-only API endpoints.
The simulator upserts market/contract snapshots and records immutable market evidence events.
Order intents estimate paper fees and max cost before acceptance.
Order intents are rejected when max order cost, max contract exposure, or max open-position limits fail.
Order intents for mkt_* strategies are rejected unless the matching MY_KRYPT_TRADER research
candidate has PAPER_ELIGIBLE status, trade_eligible=true, and an accepted latest research-gate run.
The intent snapshot records the research-gate decision, candidate id, backtest run id, evidence hash,
and live_execution=blocked.
Submitted paper orders record latency, available quantity, executable price, limit price, and bid/ask spread snapshot.
Buy orders fill only when the limit price can cross the current executable ask price.
Orders can remain submitted with no fill, partially fill, or fully fill.
Partial and full fills create fee-tracked positions and immutable fill evidence.
Operators can manually cancel created, submitted, or partially-filled paper intents with a reasoned
ORDER_CANCELLED evidence event while preserving already-filled paper position quantity.
Stale created/submitted/partially-filled intents expire and stamp matching orders with cancelled_at.
Settlements calculate gross payout and fee-net realized P/L.
Reconciliation checks fill quantity, fill fees, and position quantity against the paper ledger.
The API exposes summary, contracts, order intents, orders, positions, manual order cancellation,
stale-order cancellation, settlement, reconciliation, and evidence inspection.
POST /prediction-market/paper/demo-run creates a research-gated paper intent, submits it against
a recorded/imported quote, optionally settles it from either a request value or imported contract
outcome, and reconciles the paper ledger.
POST /prediction-market/paper/demo-batch-preflight previews eligible, skipped, duplicate, and
risk-blocked imported/resolved contract snapshots without mutating the paper ledger.
POST /prediction-market/paper/demo-batch-run replays multiple imported, resolved contract snapshots
through the same paper/demo lifecycle with a capped batch size and duplicate settled
contract/strategy skip.
GET /prediction-market/paper/demo-progress reports closed records, calendar-day coverage, fee-net
P/L, expectancy, profit factor, drawdown, active-day coverage, single-day concentration,
unique-contract coverage, single-contract concentration, imported snapshot provenance,
clean/countable ledger coverage, reconciliation status, and remaining distance to the
100-record/30-day evidence target.
GET /prediction-market/paper/demo-ledger reports each closed paper/demo record with strategy
attribution, source/import provenance, evidence hash, reconciliation status, fees, P/L, countable
state, and blockers.
GET /prediction-market/contracts/template.csv returns an Aurex contract-snapshot CSV template.
POST /prediction-market/contracts/preflight-csv validates Aurex-format or MKT markets-table CSV
without mutating the ledger.
POST /prediction-market/contracts/import-csv imports READY prediction contract snapshots and records
MARKET_SNAPSHOT evidence. MKT yes quotes are preserved, no quotes are derived as explicit raw-payload
metadata, and the original row remains in raw_payload.
POST /prediction-market/contracts/preflight-mkt-db validates bounded rows directly from the local
My-Krypt-Trader SQLite markets table without mutating the ledger.
POST /prediction-market/contracts/mkt-donor-readiness reports whether the local My-Krypt-Trader
checkout, Python collector files, expected DB paths, and discovered SQLite donor data are present
before any import, manifest, or replay step.
POST /prediction-market/contracts/mkt-runtime-safety inspects MKT Python/Electron default safety
settings, an optional runtime settings.json, and demo/production credential-file presence without
reading secrets or mutating runtime state. It blocks known unsafe runtime settings and reports
SAFETY_DEFAULTS_ONLY when code defaults are safe but runtime settings still need manual confirmation.
When no settings path is supplied, Aurex can discover safe local candidates such as
KRYPT_TRADER_USERDATA/settings.json and Electron userData paths derived from MKT's productName,
then reports the selected settings/userData candidates for operator review.
POST /prediction-market/contracts/mkt-donor-bootstrap creates a local demo-safe MKT userData
folder, writes safe settings only when appropriate, reruns runtime safety, and returns the scoped
KRYPT_TRADER_USERDATA launch command plus expected donor DB path. It does not start MKT or install
dependencies.
POST /prediction-market/contracts/mkt-donor-collection-status rediscovers the Aurex demo userData
folder, reruns runtime safety, inventories the expected donor DB, and reports waiting/empty/
research-ready/replay-ready collection states plus log-file metadata without reading logs.
It also reports collection_quality so sparse replay/research samples cannot be mistaken for
backtest-quality evidence.
POST /prediction-market/contracts/mkt-donor-launch-preflight validates package scripts,
node_modules, the MKT Python venv integrity, runtime safety, collection status, and the scoped
KRYPT_TRADER_USERDATA launch command before the operator runs MKT. A stale pyvenv.cfg base Python
path is setup-needed, not launch-ready. Aurex setup hints now use MKT's strict forced repair mode
with KRYPT_TRADER_PYTHON so the donor backend venv can be recreated from a known working Aurex
interpreter before demo collection starts. Windows command hints use npm.cmd to avoid PowerShell's
npm.ps1 execution-policy block.
POST /prediction-market/contracts/mkt-donor-runbook builds a non-mutating operator checklist with
MKT setup, demo/dry-run safety, collection status, inventory, and Aurex gate steps before donor
data is used. After bootstrap, the runbook follows the same .aurex-demo-userdata donor DB path and
scoped KRYPT_TRADER_USERDATA command as the collection monitor.
POST /prediction-market/contracts/discover-mkt-dbs performs bounded discovery of local
My-Krypt-Trader SQLite candidates and evaluates each through the non-mutating readiness check.
POST /prediction-market/contracts/mkt-db-readiness reports whether the local My-Krypt-Trader
database exists, has a markets table, and contains usable resolved rows before campaign preflight.
POST /prediction-market/contracts/mkt-db-inventory inspects an MKT SQLite database without mutation
and reports table counts, resolved research rows, replay candidates, execution-history presence,
missing tables, blockers, and next actions.
POST /prediction-market/contracts/import-mkt-db imports those READY direct-DB rows with raw_payload
provenance for db_path, sqlite_table, and direct_db_import.
POST /prediction-market/paper/demo-mkt-db-campaign-preflight temporarily imports bounded MKT DB
rows, previews source-reference scoped batch replay, then rolls back so the ledger is unchanged.
The campaign preflight also performs a rollback-protected projected replay summary with projected
completed records, fee-net P/L, countable records, first failed progress gate, opposite-side P/L,
and side-sensitivity warning.
POST /prediction-market/paper/demo-mkt-db-campaign-readiness combines MKT DB data readiness,
strategy research-gate status, rollback-protected campaign projection, side-rationale readiness,
and live-disabled state into a non-mutating operator checklist.
POST /prediction-market/paper/demo-mkt-db-campaign-manifest builds a stable, non-mutating replay
plan hash with the selected DB import, strategy, side, risk controls, projected replay,
opposite-side projection, blockers, and live-disabled controls before any campaign replay.
POST /prediction-market/paper/demo-mkt-db-campaign-run imports bounded MKT DB rows and runs the
guarded paper/demo batch replay in one paper-only operation. If the preflight is side-sensitive,
the run must acknowledge the warning and include a side-selection rationale. Accepted runs write a
PAPER_DEMO_CAMPAIGN evidence event so later reviews can audit the import hash, replay summary,
side warning, and rationale.
GET /prediction-market/paper/demo-campaigns exposes recent PAPER_DEMO_CAMPAIGN evidence events
as a campaign audit trail.
Resolved MKT market rows can carry result or settlement_value into PredictionContract.settlement_value.
Live execution remains absent.
```

### Stage K4: Evidence Gates

Deliverables:

```text
Prediction-market backtest import
Chronological IS/OOS reports
Walk-forward validation
Cost and fee-net metrics
Regime and concentration checks
Multiple-testing controls
Candidate eligibility badge
```

Done when:

```text
A prediction-market strategy can only become paper-eligible after Aurex evidence gates pass.
```

Current implementation:

```text
Resolved strategy_research_observations can now be evaluated as fee-net $1 binary-contract
paper trades.
The gate builds chronological in-sample and out-of-sample samples from observation time.
It checks minimum total trades, minimum OOS trades, positive OOS expectancy, OOS profit factor,
maximum OOS drawdown, active trading days, maximum single-day concentration, walk-forward pass
rate, known regime/category coverage, regime/category pass rate, multiple-tested-variant
limits, and a Bonferroni-adjusted one-sided OOS binomial significance test.
Accepted candidates move only to PAPER_ELIGIBLE research status.
The matching StrategyConfig remains disabled, live_eligible=false, and trade_eligible=false.
Every research-gate evaluation is persisted in strategy_research_backtest_runs with metrics,
requirements, reasons, reviewed time, and evidence hash.
GET /strategies/research-candidates/{candidate_id}/evidence exposes candidate metadata, latest
gate run, recent gate runs, recent observations, and evidence summary counts.
GET /strategies/research-candidates/readiness-queue exposes candidate evidence state, latest
gate summary, blockers, resolved-observation coverage, and next action for operator triage.
The dashboard Strategy tab exposes a Backtest action for the latest selected research candidate.
MKT SQLite research import is implemented for the donor tables currently understood by Aurex.
Scheduled import and deeper regime-specific prediction-market reports are still not implemented.
```

### Stage K5: Operator UI Upgrade

Deliverables:

```text
Prediction-market dashboard section
Research candidates
Paper simulator monitor
Order/fill/settlement ledger
Reconciliation panel
Eligibility and blocked-reason badges
MKT-inspired visual density, status treatment, and logs
```

Done when:

```text
The UI makes prediction-market readiness obvious without making live activation feel easy.
```

Current implementation:

```text
The dashboard has a dedicated Prediction Markets tab.
The tab is part of the existing single-view navigation system.
It shows paper-only live state, contracts, intents, orders, fills, open positions, settled positions,
rejected intents, and latest reconciliation state.
It shows the selected paper-order strategy's research-gate status before an intent attempt and
shows the latest intent-gate result after a backend rejection or acceptance.
It shows paper-demo evidence progress toward the 100-record/30-day target and exposes a guided
Demo run control that still uses the backend research/risk gates.
It also surfaces active days, fee-net expectancy, and single-day concentration so the operator can
see evidence quality, not only record count.
It exposes Snapshot CSV controls for template loading, preflight, import, rejected rows, and
actionable YES/NO quote counts.
It can submit market snapshots, paper order intents, paper submissions, settlements, stale-order
expiration, and reconciliation through Aurex API endpoints.
It renders contracts, paper orders, paper positions, and immutable prediction-market evidence.
The Strategy tab surfaces the latest research gate decision, first blocker, OOS edge,
OOS drawdown, regime/category coverage, and multiple-tested-variant pressure.
The Strategy tab also has an evidence drilldown for the selected candidate, showing resolved
observation coverage, accepted/blocked gate history, latest evidence hash, recent gate runs, and
recent observation hashes.
The Strategy tab has a readiness queue that separates paper-research eligible candidates, blocked
gate results, candidates ready for a gate run, and candidates needing resolved observations.
It still does not expose live execution.
```

### Stage K6: Demo/Paper Run

Deliverables:

```text
End-to-end paper/demo operation
At least 100 closed paper/demo records over at least 30 calendar days before live review
Statement-style reconciliation
Daily review
Evidence review
```

Done when:

```text
The system has enough paper evidence to decide whether micro-live is rational.
```

Current implementation:

```text
GET /prediction-market/paper/demo-readiness checks whether the paper/demo subsystem is blocked,
ready to start, or verified after a complete paper lifecycle.
It also reports the current blocking check and readiness progress so the dashboard can show the
next paper/demo gate without inference.
Prediction contract snapshots can be imported from Aurex-format CSV or My-Krypt-Trader markets
exports, giving paper/demo runs a repeatable market-data intake path instead of only manual
single-snapshot entry.
Resolved imported markets can provide the settlement value used by guided paper/demo runs.
Guided paper/demo runs can now execute an end-to-end paper lifecycle from a recorded/imported
contract snapshot when the matching MKT research candidate has accepted Aurex evidence.
Guarded batch replay can run the same lifecycle across imported resolved snapshots, caps each
operator run, requires imported/resolved data by default, and skips already-settled
contract/strategy records instead of inflating evidence counts.
Batch preflight previews that same candidate set before replay and confirms that previewing does
not create intents, orders, fills, or settlements.
GET /prediction-market/paper/demo-progress tracks the remaining closed-record and calendar-day
gap toward the K6 evidence target and blocks live-review readiness when active-day coverage,
single-day concentration, unique-contract coverage, single-contract concentration, snapshot
provenance, clean/countable ledger coverage, expectancy, profit factor, or reconciliation quality
is insufficient.
It also reports the current failing evidence check and progress through the evidence-quality gates.
GET /prediction-market/paper/demo-runbook combines readiness and progress into a read-only ordered
operator checklist from research evidence through paper execution, settlement, reconciliation,
evidence target, and independent live-readiness review.
When MKT research eligibility is missing, it also summarizes the upstream MKT research runbook so
operators can see whether collection, import, or research-gate evidence is the active blocker.
GET /prediction-market/paper/demo-ledger exposes the record-by-record audit surface for closed
paper/demo settlements so operators can see whether a record is countable, imported from MKT,
properly attributed to a strategy, backed by a settlement evidence hash, and reconciled after
settlement.
The check requires live execution to remain disabled, at least one accepted MKT research-gate
candidate, prediction contract snapshot evidence, approved paper-intent gate evidence, recorded
paper fills, recorded settlement, and matched reconciliation before it reports PAPER_DEMO_VERIFIED.
The dashboard Prediction Markets tab displays paper-demo readiness, start readiness, lifecycle
verification, demo evidence progress, demo ledger rows, and the next demo action.
The Command Center surfaces the same blocker chain at the top level so the current paper/demo or
upstream MKT research blocker is visible immediately. It also renders the upstream donor DB and
copyable scoped MKT command when collection is the active blocker; this adopts MKT's operator
ergonomics without letting Aurex launch MKT, write imports, or enable live execution from the
dashboard.
The same top-level panel also renders upstream collection telemetry from the MKT research intake
runbook: DB freshness, collection-health state, parsed/resolved/unresolved observation counts, and
resolved-depth progress. This is the Aurex rewrite of MKT's live operational feedback loop: visible
collector state, explicit parseable/resolved/backtest-depth thresholds, but no hidden execution or
trust upgrade.
Live deployment also rewrites MKT's credential-awareness idea into an Aurex gate:
`mkt_donor_credential_boundary` is not required for non-MKT strategies, but `mkt_*` strategies fail
live-readiness review if production MKT credential material is present in inspected donor profiles.
The gate reports file presence only and never reads or stores secret contents. Strategy evidence
reviews also snapshot the reviewed gate statuses, so a later credential-boundary, kill-switch,
evidence, or scope-status change makes the old CANDIDATE review stale until the operator generates
a fresh review.
The live-deployment guard also exposes the same campaign-quality result as a
prediction_demo_campaign_quality gate: it is required for mkt_* deployment strategies and marked
not applicable for non-MKT strategies.
The 100 closed paper/demo records over at least 30 calendar days are not collected yet.
```

### Stage K7: Live Adapter Readiness

Deliverables:

```text
Current venue API verification from primary docs
Credential vault implementation
Demo/sandbox adapter if available
Explicit live adapter readiness gate
Emergency cancellation path
Position rescue and reconciliation
MKT-only prediction demo campaign-quality gate in live deployment readiness
```

Done when:

```text
The adapter can prove safe behavior without enabling broad live trading.
```

### Stage K8: First $100 Net Profit Protocol

Deliverables:

```text
Micro-live plan
Strict capital limits
Daily and weekly loss limits
One strategy/scope only
Post-trade review
Broker statement reconciliation
First-profit milestone report
```

Done when:

```text
Aurex records at least $100 net realized profit after fees with zero rule violations and clean
reconciliation, or it blocks and sends the strategy back to research.
```

## Progress Ledger

```text
K0: Complete. Blueprint exists with adopt/rewrite/reject/defer decisions.
K1: Complete. Prediction-market enums, database primitives, calculation helpers, migration,
    and lifecycle tests are implemented.
K2: Complete for manual/API/dashboard intake and bounded MKT SQLite import. Scheduled MKT import
    is not implemented yet.
K3: Core backend and API complete. Longer-running paper/demo operation is not started.
K4: Core resolved-observation gate complete with OOS, drawdown, active-day, concentration,
    walk-forward, regime/category coverage, regime pass-rate, multiple-variant controls,
    Bonferroni-adjusted OOS binomial significance, and a persisted
    strategy_research_backtest_runs evidence ledger. Deeper regime reports are not implemented yet.
K5: First operator view complete with research-gate evidence summaries, selected-candidate
    evidence drilldown, readiness queue next actions, and visible Prediction Markets paper-intent
    research gate status. Full visual redesign and advanced desktop packaging are not done.
K6: Readiness checkpoint started. The paper-demo readiness endpoint and dashboard status are
    implemented, and prediction contract snapshots can be preflighted/imported from Aurex or MKT
    CSV exports or directly from the bounded My-Krypt-Trader SQLite markets table, including
    resolved market outcomes. The MKT DB discovery, data-readiness, and campaign-readiness checks now make
    missing/unusable local donor data, missing research gates, blocked projections, and
    side-rationale gaps explicit operator blockers before replay. Guided paper-demo runs, guarded batch preflight, guarded batch
    replay, guarded MKT DB campaign preflight/replay, and progress tracking are implemented, and the demo ledger now exposes
    closed-record source, evidence hash, strategy attribution, reconciliation state, countability, and blockers. The real
    100-record/30-calendar-day evidence campaign is not completed. Progress tracking now audits
    active-day coverage, single-day concentration, unique-contract coverage, single-contract
    concentration, imported snapshot provenance, clean/countable ledger coverage, fee-net
    expectancy, profit factor, drawdown, and reconciliation quality.
K7: Started at the readiness-guard level only. MKT deployment plans now require the
    prediction_demo_campaign_quality gate before live review can proceed. Real adapter and
    credential work is still not started.
K8: Not started.
Live execution: Still blocked.
```
