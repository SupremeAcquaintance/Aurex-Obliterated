# Aurex Core Non-Kalshi Pipeline Audit

Date: 2026-07-18
Scope: Core TradingView/Pine, backtest, paper evidence, and live-readiness path only.
Kalshi and My-Krypt-Trader remain optional research modules.

## Current Reality

Aurex has enough backend structure to test the core path, but it has not proven a
profitable strategy. The system can ingest TradingView-style signals, enforce a strict
accepted-backtest gate before paper execution, import TradingView completed-trade CSVs,
persist immutable backtest evidence, preflight and preserve immutable OHLCV datasets,
import paper evidence, and keep live deployment blocked behind safety gates.

Known Pine promotion now requires an exact SHA-256 fingerprint of the imported CSV,
TradingView parser provenance, complete trade fields, and the registry-owned execution
assumptions. Statistical acceptance alone cannot unlock signals, paper, or live gates.

The immediate product risk is not missing ambition. It is operator friction and
provenance drift: Pine, dashboard defaults, accepted backtest metadata, and webhook
payloads must match exactly or Aurex will correctly block paper execution.

One verified official Binance dataset and one immutable Aurex reference replay now
exist. The replay integrity audit passes, but its 165-trade result is unprofitable:
net P/L `-56.2627`, profit factor `0.8873`, and expectancy `-0.3410` per trade. This is
negative comparison evidence, not an accepted backtest. Its frozen statistical
validation is also immutable and audit-clean: all 13 protocol bindings pass, but the
result is `REJECTED`. Out-of-sample profit factor falls to `0.7166`, expectancy falls
to `-0.9675`, and max drawdown is `102.2252`. The current strategy hypothesis has
failed locally and must not advance unless authentic TradingView evidence disproves a
replay mismatch or a new predeclared strategy version earns independent evidence.

## Stage 1 Audit

| Layer | Evidence in code | Status | Blocker |
| --- | --- | --- | --- |
| Pine strategies | `pine/strategies/*.pine` | Present | `trend_pullback_v1` still needs real TradingView confirmation that it creates closed trades on target symbols/timeframes. |
| Pine diagnostics | `trend_pullback_v1.pine` | Improved | Diagnostics now distinguish setup discovery from open/closed strategy trade creation. |
| Strategy registry | `src/aurex/strategy_engine/registry.py` | Fixed | `trend_pullback_v1` registry version now matches Pine `strategyVersion`. |
| Webhook intake | `POST /webhooks/tradingview` | Present and hardened | Canonicalizes timeframe/UTC timestamp, binds idempotency to strategy provenance, enforces one canonical database record per key, preserves duplicate audit rows, rejects conflicting auth transports, and exposes processing-budget headers. Public HTTPS exposure is still required for TradingView. |
| Signal preflight | `POST /signals/preflight/tradingview` | Present | Must be run with the exact accepted-backtest version and settings fingerprint before sending real alerts. |
| Backtest import | `POST /backtests/reports/preflight-csv` and `POST /backtests/reports/import-csv` | Present | Needs real TradingView completed-trade exports, not fixtures. |
| Historical datasets | `/backtests/ohlcv/*` | Verified real dataset present | 11,521 continuous BTCUSDT 15-minute candles are bound to four checksum-verified Binance archives; TradingView candle identity is not yet established. |
| Reference replay | `/backtests/reference-replay/*` | Immutable negative evidence recorded | Record `a0780214-6e6a-4e89-92e0-6e0c8e64e0a3` passes integrity audit, but the strategy loses after declared costs and cannot satisfy acceptance. |
| Frozen replay validation | `/backtests/reference-replay/validations/*` | Immutable rejection recorded | Corrected validation `4e580237-2abe-4c56-99fb-94e780c1f992` binds 13/13 inputs to the venue-qualified protocol and passes audit, but fails five overall and OOS gates. It remains comparison-only. |
| TradingView parity | `/backtests/parity/*` | Infrastructure complete | Deterministic trade alignment, mismatch diagnostics, immutable recording, and audit exist; a real matching TradingView report and OHLCV export have not been compared yet. |
| Fold planner | `POST /backtests/window-plan` | Present | Deterministically plans date-only anchored folds without outcome inspection or ledger mutation; plans must not be regenerated after results. |
| Backtest protocol | `POST /backtests/protocols` | Enforced | Must be registered before results, match the report exactly, remain hash-intact, and be consumed by only one report. |
| Backtest acceptance and promotion | `aurex.backtest_engine.eligibility` | Hardened | Metrics acceptance remains available for research. Known Pine promotion additionally requires the TradingView CSV path, exact artifact fingerprint, complete trade provenance, and matching execution assumptions. |
| Paper execution | `aurex.execution_engine.paper` | Costed and evidence-hardened | Native fills use `deterministic_costed_market_v1` with configurable commission, half-spread, market-impact, and latency assumptions. Entry and exit costs are applied under a conservative floor and the complete lifecycle snapshot is hash-bound. This is a declared simulation model, not proof of broker fills. |
| Paper evidence | `/paper/evidence/*` | Evidence-grade filter enforced | Only hash-valid deterministic costed fills or hash-verified imported paper evidence can count. Legacy `instant`, fixture, incomplete, cost-inconsistent, or drifted fills block both paper promotion and the first-profit milestone. Real forward evidence across the selected deployment scope is still required. |
| Live readiness | `/live/deployment` | Present | Correctly blocked until accepted backtest, paper evidence, broker/account/jurisdiction packet, reconciliation, daily review, kill switch, approval, and adapter readiness pass. |

## Concrete Blockers

1. `trend_pullback_v1` must be verified in TradingView with closed trades visible in
   Strategy Tester. Local tests can check the Pine contract, but they cannot prove
   TradingView runtime behavior.
2. The first accepted backtest must come from real exported completed trades for the
   exact symbol, timeframe, version, and settings snapshot that Pine will later send
   in alerts. A hand-authored JSON report can be metrics-accepted but cannot promote.
3. Protocol `288ea36e-abbf-4c1a-b15e-85ef5b097a93` is frozen, hash-intact, venue-bound,
   manifest `READY`, package `READY`, and unconsumed. Superseded protocol
   `170470b2-9238-435e-9b91-5aae806b5f52` remains immutable but is blocked because it
   omitted the TradingView venue.
4. Walk-forward evidence must declare chronological, non-overlapping train/test folds
   inside the in-sample period. Automatic equal slices of one trade history are useful
   diagnostics but cannot satisfy the acceptance gate.
5. The trade-level parity harness now exists, but Aurex still needs a real TradingView
   completed-trades export and matching OHLCV comparison. Until that evidence passes,
   TradingView remains the authoritative strategy runner.
6. The local frozen validation rejects `trend_pullback_v1` v1.3. Passing three
   in-sample walk-forward folds does not offset the independent OOS loss. Do not tune
   thresholds or parameters against the held-out interval.
7. Webhook testing needs an externally reachable HTTPS endpoint or a tunnel configured
   outside Aurex.
8. Paper execution is gated behind accepted backtest evidence, so a successful webhook
   before accepted evidence should be expected to store then risk-reject the signal.
9. The native deterministic paper model uses explicit conservative defaults, but they
   are not venue-calibrated broker observations. Paper success can advance research;
   it cannot substitute for broker sandbox statements, fill reconciliation, or live
   adapter evidence.
10. Live trading remains unavailable by design because no real broker/exchange adapter
   has passed sandbox, reconciliation, kill-switch, and manual-approval checks.

## Next Implementation Order

1. Run the registered venue-qualified v1.3 package unchanged on `BINANCE:BTCUSDT` in
   TradingView and verify that Strategy Tester produces completed trades.
2. Export and preserve both TradingView completed trades and matching chart OHLCV so
   candle identity can be measured against the verified Binance dataset.
3. Load and import the first real TradingView completed-trade CSV through backtest
   preflight, retain the original file, and record its returned source-artifact hash.
4. If preflight is structurally READY but acceptance BLOCKED, inspect the exact gate
   reasons instead of changing thresholds.
5. Run **Compare trades** with the imported TradingView report and matching immutable
   dataset, inspect every mismatch, then record the pass or failure as immutable
   comparison evidence.
6. If TradingView confirms the negative replay, reject or revise this strategy without
   lowering acceptance thresholds or fitting the existing OOS interval. If it differs,
   resolve candle and engine parity first.
7. Once a real accepted backtest exists, run signal contract and no-write preflight.
8. Send one TradingView alert to Aurex and verify signal, risk decision, costed paper
   order, assumptions hash, and paper trade lineage.
9. Close the paper trade and verify total fees, slippage, P/L, lifecycle assumptions,
   and execution hash before starting the evidence window.
10. Only then collect forward paper evidence. Legacy instant fills do not count.
