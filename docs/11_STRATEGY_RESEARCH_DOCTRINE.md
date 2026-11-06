# Aurex Strategy Research Doctrine

Status: Canonical operating policy

## Purpose

Aurex exists to test whether a trading hypothesis has durable net edge and to reject
it safely when it does not. Profit is an outcome to pursue only after evidence and
capital-protection controls pass; it is not an assumption, software feature, or
guaranteed milestone.

This policy prevents attractive in-sample charts, repeated parameter probes, sparse
trade samples, or implementation completion from being mistaken for tradeable edge.

## Candidate Lifecycle

Every strategy version has exactly one state:

1. `EXPLORATORY`: source and parameters may change. All observed outcomes are
   development-contaminated and cannot support eligibility.
2. `FROZEN`: hypothesis, source hash, parameters, symbols, timeframes, data partitions,
   costs, tolerances, walk-forward plan, and acceptance gates are durably committed and
   reload-verified before held-out outcomes are inspected. A local object, flush,
   source hash, or document without a committed database receipt is insufficient.
3. `VALIDATED`: the immutable candidate has a complete audited replay and chronological
   validation. This state can contain a pass or rejection.
4. `PARITY_CHECKED`: Pine and local-engine behavior have authentic trade-level parity
   evidence where a local replay engine is used. Parity is implementation evidence,
   not profitability evidence.
5. `ELIGIBLE`: every required backtest gate passes. No manual waiver can create edge.
6. `PAPER`: forward evidence is accumulating under deterministic costed execution and
   reconciliation.
7. `SANDBOX_QUALIFIED`: exchange API, lifecycle, reconciliation, monitoring, and
   failure drills pass without real capital.
8. `MICRO_LIVE`: tiny explicitly approved capital is active under hard loss limits.
9. `RETIRED`: the version is rejected, superseded, or stopped. Its evidence remains.

No state may be skipped. Code completion does not advance a candidate.

## Data Discipline

A symbol/timeframe/date window becomes development-contaminated as soon as its outcome
is inspected while choosing or changing logic, filters, parameters, exits, direction,
symbol, or timeframe. Failed probes count as inspected data and must be retained.

Rules:

- Label development, validation, OOS, walk-forward, and forward-paper data explicitly.
- Treat uncertain prior exposure as contaminated.
- Freeze a candidate before opening its held-out result.
- Verify that the durable protocol timestamp is no later than every outcome-producing
  replay timestamp. A post-outcome protocol cannot be backdated or repaired.
- Use a held-out partition once for a promotion decision. A change after inspection
  creates a new version and requires a new untouched decision set.
- Do not select symbols or timeframes because adjacent probes lost and the survivor won.
- Do not weaken gates after seeing a result.
- Preserve zero-trade runs, compiler failures, rejected configurations, and losses.
- Require realistic fees and slippage at base case plus adverse cost stress.
- Prefer fewer independent hypotheses with strong economic reasoning over large search
  spaces that manufacture a local best.

## Required Freeze Record

Before evaluation, record:

- strategy name, version, hypothesis, and expected economic mechanism;
- source bytes and SHA-256;
- complete parameter fingerprint;
- allowed symbol, venue, timeframe, and direction;
- development, IS, OOS, walk-forward, and untouched holdout boundaries;
- dataset source, transformation lineage, and evidence hash;
- commission, spread/slippage, funding/borrow assumptions, and stress scenarios;
- order timing, intrabar, stop, target, sizing, and gap semantics;
- minimum trades and active days, PF, expectancy, drawdown, concentration, regime,
  walk-forward, and OOS gates;
- one decision rule: `ACCEPT`, `REDESIGN`, or `REJECT`.

`REDESIGN` means the current version still fails and is retired. It never authorizes
editing a failed version in place.

## Current Candidate Register

### trend_pullback_v1 v1.3

- State: `RETIRED / REJECTED`.
- A complete immutable replay and historical v1.1 validation exist. The v1.1 record
  remains auditable under its original semantics, but its protocol was committed after
  replay; current evaluator v1.2 blocks that temporal pairing.
- It loses after base and half costs, has negative OOS expectancy, exceeds drawdown,
  and passes zero of six walk-forward folds.
- TradingView parity remains useful only to calibrate Aurex's local replay semantics.

### jam_reversal_v1 v1.14.0

- State: `EXPLORATORY / QUARANTINED`.
- Current TradingView source is exactly 702 lines and matches local SHA-256
  `f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3`.
- The current BTCUSDT 15-minute chart shows `+$24.87`, `5/5` profitable trades, and
  `$2.17` max drawdown for May 1 through July 20, 2026.
- Those metrics are not validation evidence. Versions 1.0.1 through 1.14.0 repeatedly
  changed entries, exits, filters, targets, stops, timeframe behavior, and defaults
  after inspecting the same small windows and adjacent symbol/timeframe probes.
- BTCUSDT 5m/15m/30m/1h and the documented ETHUSDT/SOLUSDT probes are contaminated for
  the tested periods. Sparse survivors and no-loss samples do not establish edge.
- Do not import this run as accepted evidence or enable paper execution.
- A future Jam candidate must receive a new version, an explicit contamination map,
  an untouched decision set, and a frozen protocol before that result is opened.

### jam_reversal_spot_v1 v1.0.1

- State: `RETIRED / REJECTED`.
- This separately identified descendant preserved the Jam v1.14.0 mechanics while
  adapting them before outcome inspection to Binance spot: long-only, BTCUSDT 15m,
  `$100`, `1x`, `0.10%` commission per side, and confirmed previous-hour EMA inputs.
- Protocol `f788795a-ac75-4763-93c2-75a031ee2c70` was durably committed before the
  result. Its replay, validation, and both integrity audits are immutable and pass.
- The 2023-2025 decision set produced 14 trades, `-$0.5371`, PF `0.8301`, negative
  expectancy, four OOS trades, OOS PF `0.6771`, and zero of six passing folds.
- Zero costs produced `+$1.2642`, but base fees were `$1.8008`; the path is too sparse
  and too fee-fragile for forward paper.
- Do not tune, rerun, relabel, or paper-trade v1.0.1. Its BTCUSDT 15m period from
  February 1, 2023 through January 1, 2026 is now holdout-opened and retired.
- Full decision:
  `data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json`.
- The stored-evidence-only failure analysis classifies the version as
  `INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE`; artifact
  `data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json`, hash
  `7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`.
- Historical research remains bound to contamination ledger v1. Jam v1.0.1 is added
  through append-only contamination ledger v2 without mutating old lineage.
- Any successor discussion must state a falsifiable economic mechanism change before
  parameters. This analysis grants no new-candidate or execution authority.
- The frozen design-only successor charter selects aggressive sell-flow exhaustion
  and reclaim for future capability review only. It rejects candle retuning and
  historically unidentifiable maker fills, and defers cross-asset reversal outside
  the BTCUSDT operator scope.
- The selected hypothesis requires Binance aggregate-trade aggressor identity and is
  not exactly Pine-compatible. A future qualified backend signal may be visualized in
  Pine, but a candle proxy must not be called equivalent.
- Charter artifact:
  `data/evidence/jam_successor_hypothesis_charter_v1.json`, hash
  `426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`.

### volatility_breakout_v1 v1.1.0

- State: `RETIRED / DIAGNOSTIC REJECT / FORMAL VALIDATION BLOCKED`.
- Source and parameters were frozen before outcome inspection, but the first protocol
  transaction rolled back. The durable protocol was recorded approximately 52 seconds
  after the replay and fails evaluator v1.2 temporal binding.
- The replay itself audits `PASS`: 1,125 trades, `-$533.87`, PF `0.6734`, negative IS
  and OOS expectancy, `$556.48` max drawdown, and zero of six walk-forward folds.
- Its zero-cost fixed-path upper bound also loses `-$37.10`, so the failure is not only
  commission or slippage.
- Do not tune, rerun, or relabel this version. The observed 2023-2026 BTCUSDT outcome is
  development-contaminated for any successor.

### slow_breakout_spot_v1 v1.0.0

- State: `RETIRED / REJECTED`.
- Mechanism: native 4-hour, long-only spot, prior 55-bar high entry, prior 20-bar low
  exit, fixed 3 ATR catastrophe stop, no take-profit, 0.25% risk, 50% notional cap.
- BTCUSDT is development-contaminated. ETHUSDT and SOLUSDT are the untouched decision
  markets, each with an audited 7,662-row native 4h Binance Vision dataset.
- Authoritative protocols are ETH `ff612386-ffa3-41e8-a332-1565d8d46495` and SOL
  `080084a0-d1b2-435b-ad9b-bd294a9bf603`. They bind source, parameters, costs, dates,
  folds, acceptance gates, tick size, point value, and quantity step.
- Both replay and validation audits pass, but both individual validations failed.
  ETH passed its aggregate and OOS gates but only one of five walk-forward folds.
  SOL's 26-trade OOS segment lost `-$18.39`, recorded PF `0.5185`, and passed no
  walk-forward fold.
- The combined `+$104.43` and PF `1.6968` do not rescue the candidate because the
  frozen rule required both markets to pass independently.
- Current paper risk rules also reject its intentional null take-profit, but that
  execution limitation is no longer the blocker: the candidate itself is ineligible.
- Full contract: `docs/15_SLOW_BREAKOUT_SPOT_PREREGISTRATION.md`.

## Active Sequence

1. Preserve the slow-spot rejection and complete development-only failure attribution.
   Do not optimize against the opened ETH/SOL outcomes.
2. Correct future study design before choosing another candidate: expected trade rate,
   fold duration, minimum fold sample, portfolio capital overlap, correlation,
   survivorship, and untouched market/time boundaries must agree mechanically.
3. Select a genuinely distinct economic hypothesis or retire this research family.
   Any successor requires a new version, source, protocol, and untouched decision set.
4. With explicit authority, run the bounded frozen trend parity calibration. This
   validates engine semantics only and cannot promote a rejected strategy.
5. Complete one genuine authenticated external TradingView webhook proof in
   paper-only mode with the expected eligibility-safe risk rejection.
6. Start forward paper evidence only after a future candidate passes all eligibility,
   parity, and operational gates.

## Money Boundary

No backtest, parity result, or five-trade chart makes money reliable. Aurex may pursue
micro-live profit only after accepted held-out evidence, forward paper success,
exchange sandbox qualification, reconciled execution, hard risk limits, monitoring,
and explicit approval. The first `$100` milestone is measured net of all costs and
remains `$0` until real settled evidence says otherwise.
