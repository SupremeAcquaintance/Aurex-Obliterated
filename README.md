# Aurex

Aurex is a risk-first trading research and execution platform.

Current implementation stage:

```text
2026-09-26: platform delivery hardening; no qualified strategy
Binance Spot Testnet: historical cancel, fill/fee, stream and recovery proofs exist
Genuine TradingView delivery and candidate-specific Pine parity remain unproven
```

Live trading remains disabled until accepted strategy evidence, broker, account,
jurisdiction, paper evidence, explicit user approval, and execution readiness gates
pass. Current scheduling and evidence are in `docs/10_PROJECT_CONTROL.md` and
`docs/46_AUREX_DELIVERY_REBASELINE.md`. Historical Testnet proofs are not permission
to repeat consumed order campaigns or claims about current account state.

The My-Krypt-Trader integration track is documented in [docs/03_MKT_INTEGRATION_BLUEPRINT.md](docs/03_MKT_INTEGRATION_BLUEPRINT.md). Aurex remains the source of truth; My-Krypt-Trader is treated as a donor system for prediction-market workflows, paper/demo execution mechanics, reconciliation, credential-handling ideas, logging, and operator UX.

## Local Development

Use Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\uvicorn apps.api.main:app --reload --no-proxy-headers --no-access-log
```

Open `http://127.0.0.1:8000/dashboard`. Stop the server with `Ctrl+C`.

For a clean operator launch on port 8917:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8917 --no-proxy-headers --no-access-log
```

Then open `http://127.0.0.1:8917/dashboard`.

Keep the full application on loopback. Do not expose its unauthenticated management
routes through a public tunnel. The separate webhook-only, safe-rejection listener
is documented in `docs/47_TRADINGVIEW_INGRESS_DEPLOYMENT.md`; its deployment check
does not open a listener or grant execution authority.

Verify the frozen Testnet boundary and public connectivity:

```powershell
.\.venv\Scripts\python.exe scripts\freeze_binance_spot_testnet_profile.py --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_binance_spot_testnet_check.ps1 -Mode public -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

Authenticated Testnet checks use hidden interactive prompts and do not persist keys:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_binance_spot_testnet_check.ps1 -Mode authenticated -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_binance_spot_testnet_check.ps1 -Mode test-order -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

`test-order` calls Binance's validation endpoint and does not enter the matching
engine. Testnet results use virtual funds and do not prove strategy edge.

After both checks pass, run the explicitly acknowledged virtual cancel lifecycle:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_binance_spot_testnet_check.ps1 -Mode virtual-cancel -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

This enters and cancels one maximum-USD-10 Testnet limit order using virtual funds.
The order price is derived from Binance's current percentage-price reference and
best bid so it remains inside current filters while resting below the market.
It still does not qualify the sandbox, enable production, or authorize live trading.

Local persistence defaults to SQLite:

```powershell
AUREX_DATABASE_URL=sqlite:///./data/aurex.db
```

Health check:

```text
GET /health
```

## Project Contract

The implementation path is documented in [docs/00_AUREX_MASTER_PLAN.md](docs/00_AUREX_MASTER_PLAN.md).

## Current Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Current notes:

```text
Stage 1 backend skeleton is implemented.
Stage 2 database models and Alembic migration are implemented and tested locally.
Stage 3 TradingView webhook intake is implemented and tested locally.
Stage 4 risk engine is implemented with a pre-paper accepted-backtest eligibility gate, latest DO_NOT_TRADE strategy-review enforcement, auditable risk-decision gate snapshots, and tested locally.
Stage 5 paper execution is implemented with a versioned deterministic costed-market model, configurable commission/spread/impact/latency assumptions, conservative entry/exit cost floors, and hash-bound lifecycle evidence. It remains blocked unless the signal's strategy/symbol has accepted backtest evidence recorded in the risk decision snapshot and no latest scoped DO_NOT_TRADE evidence review. This model is paper simulation evidence, not proof of broker fills.
Stage 6 performance analytics and equity-curve API are implemented and tested locally.
Stage 7 Pine strategy is implemented with static contract tests and an on-chart
trend_pullback_v1 diagnostic table that exposes setup pass counts and latest blockers
without loosening entries. Its alert payload now carries strategy version and settings
fingerprint provenance, and Aurex blocks paper execution when incoming known-Pine
signals do not match the accepted backtest's version/settings evidence.
Stage 8 historical backtest lab is implemented with TradingView completed-trades CSV auto-detection, persisted normalized trade evidence, deterministic evidence hashes, strict report preflight/import, in-sample/out-of-sample metric snapshots, walk-forward validation snapshots, trade distribution and regime breakdown snapshots, cost/slippage/risk acceptance requirements, and tested locally. The exact workflow is in [docs/02_TRADINGVIEW_BACKTEST_IMPORT.md](docs/02_TRADINGVIEW_BACKTEST_IMPORT.md).
Known Pine promotion is stricter than metrics acceptance: only a TradingView CSV import with an exact source-artifact SHA-256 fingerprint, complete trade provenance, matching registry cost/slippage assumptions, and all existing evidence gates can unlock paper progression. Raw JSON reports remain research-only even when their metrics pass. The policy and trust boundary are documented in [docs/08_TRUSTED_BACKTEST_PROMOTION.md](docs/08_TRUSTED_BACKTEST_PROMOTION.md).
TradingView backtest preflight now returns structured diagnostics for header-only or entry-without-exit exports, so the no-trade-data Pine path is visibly rejected with a next action while import remains blocked.
Known Pine strategy backtests now also require complete strategy-parameter snapshots before they can become accepted evidence; incomplete `trend_pullback_v1` settings stay importable as rejected records but cannot unlock paper or live readiness. The dashboard Backtests panel surfaces this parameter evidence directly, and Deployment points to missing parameters when that blocks accepted-backtest readiness.
Stage 9 paper trading dashboard is implemented as a single-view operations console with URL-backed sidebar navigation, resilient partial refreshes, dedicated action notifications, data-driven market posture, dashboard-operable backtest CSV preflight/import controls, responsive navigation, and local contract/HTTP verification.
Stage 10 market state engine is implemented, tested locally, and HTTP smoke-verified.
Stage 11 strategy portfolio controls are implemented, tested locally, HTTP smoke-verified, and browser-verified.
Stage 12 advisory analyst layer is implemented, tested locally, HTTP smoke-verified, and browser-verified.
Stage 13 broker readiness is implemented with sandbox fill, fee/cost reconciliation, position-sync reconciliation, local tests, HTTP smoke verification, and browser verification.
Stage 14 live micro-deployment guard is evidence-hardened with an independent accepted-backtest live-readiness audit for the selected deployment scope, backtest trade-distribution and regime-coverage checks, dashboard-operable strategy evidence reviews with required evidence and deployment-plan freshness gates, context-bound explicit approval records, dashboard-operable due-diligence approval packets, a required live execution adapter readiness gate with a disabled adapter boundary, dashboard-operable first-profit milestone checks, dashboard-visible activation audit blockers, trade journal coverage, broker-statement reconciliation with CSV preflight/reconcile support and current-ledger freshness checks, first-profit milestone reports, daily failure-protocol review, scoped 100-trade/30-calendar-day paper-evidence reports with current-ledger freshness checks, sustained active-day coverage, drawdown, fee/cost, position-sync, risk-lineage, and execution-quality checks, tests, HTTP smoke verification, and browser verification. Non-evidence-grade instant or drifted fills cannot satisfy paper promotion or the profit milestone. Activation remains blocked by default.
Stage 15 real paper evidence intake is implemented with a strict CSV import preflight, preflight/import analysis summaries and fix queues, CSV import batch ledger, duplicate external-trade detection, stop-distance risk reconciliation, reconstructed signal/risk/order/trade lineage, equity-curve updates, trade journals, import history/detail/template/collection-status endpoints, dedicated dashboard intake controls, and Stage 14 paper-evidence audit compatibility.
MKT integration Stage K0/K1/K2/K3, a stronger core K4 resolved-observation evidence gate, first K5 UI progress, and K6 paper-demo readiness/data plumbing are implemented: the adoption/rejection blueprint exists, Aurex-native prediction-market tables and migration exist, binary contract calculations are tested, and a paper-only prediction-market simulator/API can reject over-risk intents, record latency/spread/depth snapshots, partially fill, manually cancel open or partially filled orders, expire stale orders, settle fee-net positions, expose evidence, and reconcile the paper ledger. Prediction contract snapshots can now be preflighted and imported from Aurex-format CSV, My-Krypt-Trader `markets` CSV exports, or bounded direct My-Krypt-Trader SQLite `markets` imports before they enter the evidence ledger, including resolved `result` or `settlement_value` outcomes for settled markets. Dedicated MKT donor-runbook, donor-readiness, DB discovery, DB-inventory, data-readiness, campaign-readiness, and campaign-manifest checks report missing MKT checkout/code/data paths, setup and demo/dry-run safety steps, missing/unusable local donor data, table counts, resolved research rows, replay candidates, missing research gates, blocked projections, side-rationale gaps, replay-plan hashes, and live-disabled state before replay. MKT-derived signal ideas can be recorded as disabled strategy research candidates and observations with evidence hashes, including bounded SQLite import from MKT whale_trades, alerts, and crypto15m_signals. Resolved observations can be evaluated with fee-net IS/OOS, concentration, active-day, walk-forward, OOS drawdown, regime/category coverage, multiple-tested-variant checks, and Bonferroni-adjusted OOS win-rate significance before a candidate becomes paper-eligible. Every research-gate run is now persisted in strategy_research_backtest_runs and exposed through candidate evidence plus readiness-queue endpoints. Prediction-market paper intents for mkt_* strategies are rejected unless the matching MKT research candidate has an accepted Aurex research gate, and the intent snapshot records that gate decision. A guided paper-demo run endpoint now creates a gated paper intent, submits against a recorded/imported contract quote, can settle from an imported contract outcome when no manual settlement is supplied, reconciles, and records progress toward the 100-closed-record/30-calendar-day evidence target. A guarded batch preflight endpoint previews eligible/skipped imported resolved snapshots without mutating the ledger, and a guarded batch replay endpoint can collect multiple paper/demo records while skipping duplicate settled contract/strategy records. A guarded MKT DB campaign preflight/run flow can temporarily import bounded DB rows for preview or import and replay them in one paper-only operation with source-reference scoped batch selection; the preflight now projects completed records, fee-net P/L, countable ledger rows, first failed campaign gate, opposite-side P/L, and side-sensitivity warnings without mutating the ledger, while the campaign manifest builds a stable non-mutating replay-plan hash before replay, and campaign replay requires explicit side-sensitivity acknowledgement and a side-selection rationale before writing side-sensitive evidence, then records a PAPER_DEMO_CAMPAIGN evidence event with the import hash, replay summary, progress summary, side warning, and rationale. A campaign-audit endpoint and dashboard table summarize those campaign evidence events for review. Paper-demo progress now also checks active-day coverage, single-day concentration, unique-contract coverage, single-contract concentration, imported snapshot provenance, clean/countable ledger coverage, expectancy, profit factor, drawdown, fee-net P/L, and matched reconciliation after the latest settlement before live review can be considered, while a demo-ledger endpoint exposes each closed record's strategy attribution, source/import provenance, evidence hash, reconciliation status, fees, P/L, and blockers. The live-deployment guard now surfaces a prediction-demo campaign-quality gate that is required for `mkt_*` strategies and not applicable for ordinary non-MKT strategies. A paper-demo readiness endpoint reports whether the subsystem is blocked, ready to start paper/demo operation, or verified after a complete paper fill, settlement, and reconciliation lifecycle. StrategyConfig remains disabled and live-blocked even when a research candidate passes this gate. The dashboard now includes a Prediction Markets tab with visible paper-demo readiness, paper-demo evidence progress and quality checks, unique-contract/provenance/ledger-clean summaries, an inspectable demo ledger, campaign audit table, guided demo run, batch preflight, batch replay, and MKT donor-runbook/donor-readiness/DB discovery/candidate-inspection/DB-inventory/data-readiness/campaign-readiness/campaign-manifest/preflight/import/campaign replay/projection/side-sensitivity/campaign-evidence controls, plus deployment-panel prediction-demo campaign status, snapshot CSV controls, paper-intent research-gate status, contracts, orders, positions, evidence, and Strategy research-candidate intake/import/backtest controls with visible readiness queue, latest gate evidence, gate-run history, selected-candidate observation evidence, OOS edge, drawdown, regime coverage, variant pressure, statistical edge, blockers, and next actions.
Local development uses SQLite at sqlite:///./data/aurex.db by default.
PostgreSQL remains a later scaling option, not the active local dependency.

Prediction paper-demo readiness now reports the current blocking check and readiness progress so the
Prediction Markets dashboard can show the next paper/demo gate without inferring it from the full
check list. This is read-only readiness guidance and does not enable live execution.
Prediction paper-demo progress now reports the current failing evidence check and completion
percentage across the paper evidence target checks, again read-only and live-disabled.
The `/prediction-market/paper/demo-runbook` endpoint combines readiness and evidence progress into
one ordered, non-mutating paper/demo operator checklist from MKT research gate through paper fill,
settlement, reconciliation, evidence targets, and independent live-readiness review.
When the paper/demo path is blocked by missing MKT research eligibility, the runbook includes the
upstream MKT research runbook summary so the operator can see whether collection, import, or the
research gate is the real blocker.
The Command Center now surfaces that same evidence-path blocker chain at the top level: current
blocker, upstream blocker, path progress, live boundary, donor DB, unblock command, and next
action. The unblock command can be copied from Command Center, but Aurex still does not execute MKT
or enable live trading.
It also shows upstream MKT collection telemetry from the paper/demo runbook: DB freshness, MKT
collection/health status, parsed/resolved/unresolved research rows, and resolved-depth progress.
This gives immediate post-launch feedback without importing rows or writing paper/demo evidence.
The upstream runbook also exposes an evidence-threshold ladder for parseable rows, resolved rows,
and 100 resolved rows before an Aurex research backtest gate can be considered; Command Center
renders the next unfinished threshold.

MKT runtime safety is now an explicit Aurex gate: `/prediction-market/contracts/mkt-runtime-safety`
checks MKT Python/Electron defaults, an optional runtime settings file, and credential-file
presence without reading secrets, starting MKT, importing rows, replaying campaigns, or enabling
live execution. If no settings path is supplied, Aurex reports safe local runtime path candidates
such as `KRYPT_TRADER_USERDATA/settings.json` and Electron userData locations for operator review.
Live deployment now also has a separate MKT donor credential-boundary gate: non-MKT strategies mark
it not required, while `mkt_*` strategies fail live-readiness review if production MKT credential
material is present in inspected donor credential directories. This check reports file presence
only; it does not read credential contents or store secrets in Aurex. Strategy evidence reviews now
also record the reviewed readiness-gate statuses and become blocked if any reviewed gate later
changes status or was missing from the review snapshot, so credential-boundary, kill-switch,
evidence, and deployment-scope changes require a fresh review.
The `/prediction-market/contracts/mkt-donor-bootstrap` gate can also create a workspace-local
demo userData scaffold and return the scoped MKT launch command, while still refusing to start MKT
or overwrite unsafe settings by default.
The `/prediction-market/contracts/mkt-donor-collection-status` gate then monitors that scaffold
read-only, reporting whether the donor DB is missing, empty, research-ready, or replay-ready.
The donor runbook consumes that same status so its collection step points to the scoped demo
userData DB and launch command.
The `/prediction-market/contracts/mkt-donor-launch-preflight` gate validates package scripts,
node_modules, MKT Python venv integrity, runtime safety, collection status, and the scoped launch
command before the operator runs MKT. It treats stale pyvenv.cfg base Python paths as setup-needed,
not launch-ready. The donor setup path now supports a strict forced repair using
`KRYPT_TRADER_PYTHON` so Aurex can recreate MKT's backend venv with a known working interpreter.
On Windows, Aurex command hints use `npm.cmd` so PowerShell does not trip over `npm.ps1` execution
policy.
Current local state is launch-ready for scoped demo collection only; the donor DB is still empty
and no backtest/signal/live-trading claim is implied.
The collection monitor now also reports donor collection quality: sparse replay/research samples
are visible, but backtest-candidate quality requires materially deeper resolved donor data before
strategy reliability can be argued. It tracks remaining targets for context rows, resolved replay
candidates, resolved research observations, and capped backtest-depth progress.
The MKT research import path now also has a non-mutating intake-readiness gate, preflight, and
import quality report: processed rows, resolved vs unresolved depth, per-source targets for
whale/momentum/crypto15m observations, sparse-sample warnings, and a backtest-candidate label only
after 100 resolved observations for a source. Sparse or unresolved MKT research imports now require
an explicit research-only acknowledgement before the mutating import endpoint writes observations.
Imported MKT research candidates persist import-quality status, source-quality status,
resolved-depth counts, blockers, and acknowledgement state for later audit.
MKT research intake readiness also reports scoped donor DB file size, modified time, age, and
freshness so an empty/stale DB points the operator back to launching or restarting MKT collection.
It also returns a scoped `KRYPT_TRADER_USERDATA` launch command hint for MKT demo collection without
executing it.
It now includes a research collection-health summary so waiting, inactive, collecting, sparse
sample, and backtest-depth states are visible separately from strategy evidence gates.
That health summary also uses bounded log-file metadata from the scoped MKT userData logs folder so
a recent launch can be distinguished from a truly inactive collector without reading log contents.
The `/strategies/research-candidates/mkt-intake-runbook` endpoint turns that same readiness into an
ordered, non-mutating operator checklist from scoped MKT launch through preflight, research-only
import, research backtest gates, and live-disabled boundary review.
The runbook also reports the current actionable step and progress so the operator can see the next
blocking action without inferring it from the full checklist.
When the current step has a manual command, the runbook exposes it as `current_command` and the
Strategy dashboard shows it beside the current step without executing it.
It also reports collection freshness from DB/log modified timestamps so a launch-ready donor can
still be flagged as not currently writing.
Launch health now summarizes that operational state separately from strategy evidence: blocked,
starting, inactive, stale, collecting, sample-ready, or backtest-candidate. It keeps live execution
disabled and does not treat a launched donor or sparse rows as a reliable signal.
MKT's Electron startup now maps `KRYPT_TRADER_USERDATA` into Electron `userData`, and Aurex launch
preflight blocks the donor launch if that scoped folder support is missing.
```
