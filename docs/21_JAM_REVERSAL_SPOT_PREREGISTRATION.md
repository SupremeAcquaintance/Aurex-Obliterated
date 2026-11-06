# Aurex Jam Reversal Spot V1 Preregistration

Status: `REJECTED / HOLDOUT OPENED / VERSION RETIRED`

This contract defines the only Jam Reversal candidate currently permitted to enter
Aurex historical validation. It does not qualify the strategy, authorize paper
orders, authorize live trading, or claim profitability.

- Protocol ID: `f788795a-ac75-4763-93c2-75a031ee2c70`
- Protocol hash:
  `219d6d069e678f23d3dc49588bc21a5eda9c21970ef83f5fdcb7610d1083bbda`
- Walk-forward plan hash:
  `8ed49714b300c9ec077b0203f154cfb629ce986b3e0acba5ad5ceef30c6be054`
- Durable registration: `2026-07-31T18:24:22.241923Z`
- Outcome fields inspected before registration: none

The earlier v1.0.0 protocol
`1aa77691-6b62-4738-b1b9-89c2f1f8cc06` was superseded without a replay after the
higher-timeframe realtime/reload stability risk was found. It remains immutable
historical evidence of an unrun design and is not an eligible candidate.
The first v1.0.1 protocol `920b1cbf-0990-4cd6-b835-445e1c7ab2d8` was also
superseded without a replay because its data start incorrectly included the
warmup-only month and could not bind to evaluator v1.2.

## Candidate Identity

- Strategy: `jam_reversal_spot_v1`
- Version: `1.0.1`
- Venue/product: Binance spot
- Symbol/timeframe: `BTCUSDT` / `15m`
- Direction: long-only
- Maximum leverage: `1x`
- Initial capital: `$100`
- Risk per trade: `0.5%`
- Maximum position value: `95%`
- Default enabled: `false`

The candidate descends from `jam_reversal_v1` v1.14.0. The parent Pine source is
preserved unchanged at
`f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3`.
The descendant source is
`7aa2aaa04e17ccbad70adba9279b4e5eb3057393b5e74f0a7db4cc5dd39d7270`.

## Adaptation Boundary

The descendant was created before opening any earlier-period Jam result. Its changes
are execution-driven:

- disable shorts because Binance Spot Testnet does not provide a deployable short
  path;
- restrict operation to `BTCUSDT` `15m`;
- set initial capital to the operator's declared `$100`;
- model `0.10%` commission per side instead of relying on Testnet's zero commission;
- bind the historical run to the untouched period ending before 2026.
- use the previous confirmed one-hour EMA values so reloaded history and realtime
  execution do not depend on a developing higher-timeframe bar.

Pattern recognition, higher-timeframe context, confirmation, stop, target,
breakeven, trailing, midpoint failure, pullback failure, cooldown, and sizing logic
otherwise retain the parent v1.14.0 settings.

## Contamination Map

The following parent results remain excluded from candidate acceptance:

- `BTCUSDT` `5m`, `15m`, `30m`, and `1h` from May 1 through July 21, 2026;
- documented `ETHUSDT` and `SOLUSDT` neighbor probes;
- every observed metric from Jam versions 1.0.1 through 1.14.0.

The descendant decision period is:

- warmup source: January 1-31, 2023;
- in-sample: February 1, 2023 through December 31, 2024;
- out-of-sample: January 1 through December 31, 2025;
- hard result end: January 1, 2026, exclusive.

No Jam return from this decision period was inspected before the authoritative
immutable protocol was committed.

## Data Contract

- Aurex dataset:
  `9724b9c7-03fa-4cba-9d5f-1e3bd69aa322`
- Source: Binance Vision monthly spot klines
- Dataset evidence hash:
  `2a048a6709d0f066977d317ec2d013d362cc68a5f626d85201e98d9c6925440e`
- Full stored coverage: January 1, 2023 through June 30, 2026
- Rows: `122,587`
- Documented outage: five missing 15-minute intervals on March 24, 2023
- Undocumented gaps: zero

The documented exchange outage is preserved. Aurex must not synthesize candles
inside it.

## Execution Contract

- Entry: confirmed signal-bar close plus two adverse ticks
- Stop: trigger or gap price plus two adverse ticks
- Target: declared limit without favorable gap improvement
- Same-bar stop and target: stop-first, flagged as intrabar ambiguous
- Tick size: `$0.01`
- Point value: `1`
- Quantity step: `0.00001 BTC`
- Base commission: `0.10%` per side
- Commission stress: `0.15%` per side
- Base slippage: `2` ticks per fill
- Slippage stress: `10` ticks per fill
- Bar magnifier: disabled

Local replay remains comparison evidence until trade-level parity is checked against
the frozen Pine source in TradingView.

## Acceptance Gates

All gates are conjunctive:

- at least `60` closed trades;
- aggregate profit factor at least `1.20`;
- positive aggregate expectancy after base costs;
- maximum drawdown no greater than `$10`;
- at least `20` out-of-sample trades;
- out-of-sample profit factor at least `1.15`;
- positive out-of-sample expectancy after base costs;
- at least `30` active trading days;
- no single day may contain more than `10%` of all trades;
- a market-regime breakdown must be present;
- all six frozen walk-forward folds must be evaluated;
- each passing fold must contain at least seven trades, have profit factor at least
  `1.0`, and positive expectancy;
- at least `66%` of folds must pass;
- replay and validation integrity audits must pass;
- no production or real-capital authority may be introduced.

Failure means `REJECT` or a separately versioned redesign. Parameters may not be
edited after seeing this result.

## Forward Boundary

Historical passage alone does not authorize Testnet orders. Before forward paper:

1. establish local-to-Pine trade-level parity;
2. freeze the exact TradingView alert fingerprint;
3. bind alerts to the qualified Binance Spot Testnet adapter;
4. apply the operator risk limits and kill switch;
5. preregister a forward-paper observation count and duration.

Production remains out of scope.

## Recorded Decision

The authoritative run opened the decision set once on July 31, 2026.

- Reference replay:
  `82e5ff23-a4de-423b-b8df-6394d09566a1`
- Replay record hash:
  `e744038580b0d413c15ba25b7a8936faa6fc3f08d67f7ffbd01f29ffe77db257`
- Validation:
  `6ad2fef6-ffd3-4773-9f02-52e80596bdd4`
- Validation hash:
  `02e2f67a72569a177cfea56ac2ec3dd3265a7cc460359188fa7611d25da64762`
- Decision artifact:
  `data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json`
- Artifact evidence hash:
  `d8b108df43a82b3bb5db0cdffd3ec94992e9baf43fede05bbd01dd518a03c5fd`
- Replay audit: `PASS`
- Validation audit: `PASS`
- Verdict: `REJECT_CURRENT_VERSION`

Observed base-cost result:

- trades: `14`;
- wins/losses: `5 / 9`;
- net P/L: `-$0.5371` on `$100`;
- profit factor: `0.8301`;
- expectancy: `-$0.0384` per trade;
- maximum drawdown: `$2.2222`;
- OOS trades: `4`;
- OOS net P/L: `-$0.2929`;
- OOS profit factor: `0.6771`;
- walk-forward folds passed: `0 / 6`.

The zero-cost fixed-path upper bound was `+$1.2642` with PF `1.6461`, but the base
fee model consumed `$1.8008`; half-cost PF was only `1.1421`. The failure is both
statistical and economic: the sample is far too sparse, OOS is negative, and the
gross edge is too small to survive the frozen spot costs.

Version v1.0.1 is retired. It may not be tuned, rerun under changed assumptions, or
used for forward paper. A successor must use a new version, a new preregistration,
and data not opened by this decision.

## Bounded Failure Analysis

The post-result analysis used only the stored decision artifact. It opened no new
return, reran no strategy, and selected no replacement parameter.

- Failure-analysis artifact:
  `data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json`
- Evidence hash:
  `7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`
- Frozen historical contamination ledger:
  `data/evidence/strategy_contamination_ledger_v1.json`
- Append-only Jam contamination ledger:
  `data/evidence/strategy_contamination_ledger_v2.json`
- Ledger v2 hash:
  `f24cc36011e9f9ddc40e277197bd3fa03310cac12b6848b30714aae26cdb37bd`
- Classification:
  `INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE`
- Next decision:
  `STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN`

The analysis grants no parameter-retuning, candidate, paper, Testnet strategy-order,
production, or live authority. A successor may be proposed only after an economic
mechanism change is stated before parameters, the consumed 2023-2025 Jam window is
excluded from rescue tuning, and genuinely unopened decision evidence is reserved.
