# slow_breakout_spot_v1 Preregistration

Status: `RETIRED / HELD-OUT DECISION REJECTED`.

Strategy version: `1.0.0`.

Pine SHA-256:
`2312c6ce75b79b691bfa3542e4d44221a917f2efdeb0853408d93b5e1a099f16`.

Local engine: `slow-breakout-spot-reference-v1.0.0`.

## Contamination Map

- BTCUSDT 2023-2026 is development-contaminated by prior strategy results and failure
  analysis. It is not part of this decision.
- ETHUSDT 4h and SOLUSDT 4h were imported and audited without running this candidate.
- Synthetic unit/integration candles prove semantics only and are not market outcomes.
- As of the authoritative protocol commit, no `slow_breakout_spot_v1` replay existed.

## Immutable Datasets

| Symbol | Dataset ID | Evidence hash | CSV SHA-256 | Rows |
| --- | --- | --- | --- | ---: |
| ETHUSDT | `287e1cca-27d9-4308-8ae7-458d563d4867` | `41acac572e4669b12af1cc477aff8ede82d792ecdce12fd670af135fdaefd12b` | `55680fa42c33901e57586acead6165b30b4f2b6f46410b4517a59fc1014f1279` | 7,662 |
| SOLUSDT | `411799dd-1e55-4b97-ba7b-b6952146ecb5` | `6bc0e852d6d97f30d43cd226706c080907a677d45ff2e17cff3869f0744319d1` | `2eb590e55ecb4cbaccb5d5ffe5229908569e3ba996ce765b60c591a2710d9066` | 7,662 |

Both datasets are native 4-hour Binance Vision candles from
`2023-01-01T00:00:00Z` through `2026-06-30T20:00:00Z`, with verified monthly archive
checksums, no gaps, and latest integrity audit `PASS`.

## Frozen Parameters

```text
initial_capital=1000
backtest_start=2023-02-01T00:00:00Z
backtest_end=2026-07-01T00:00:00Z
entry_channel_length=55
exit_channel_length=20
atr_length=20
atr_stop_multiplier=3.0
risk_per_trade_percent=0.25
max_position_value_percent=50.0
enable_long=true
```

Commission is `0.05%` per side. Slippage is two adverse ticks. There is no leverage,
shorting, funding, borrow cost, favorable gap improvement, profit target, parameter
optimization, or post-result threshold change.

## Execution Specification

Binance's official public spot `exchangeInfo` endpoint was checked on 2026-07-22 before
the authoritative protocols were committed:

`https://data-api.binance.vision/api/v3/exchangeInfo`

| Symbol | Tick size | Point value | Minimum contract/step |
| --- | ---: | ---: | ---: |
| ETHUSDT | 0.01 | 1 | 0.0001 |
| SOLUSDT | 0.01 | 1 | 0.001 |

These values are part of each authoritative protocol's risk snapshot and must match
the replay request. Validation blocks a mismatch. Current exchange rules are not proof
of historical liquidity or execution quality; they only freeze deterministic rounding
and tick-valued slippage for this research decision.

## Authoritative Protocols

| Symbol | Protocol ID | Protocol hash | Registered UTC |
| --- | --- | --- | --- |
| ETHUSDT | `ff612386-ffa3-41e8-a332-1565d8d46495` | `66045e3554a0dd3a9db47e71dcedccb83624610b1dd2d7676480b16e47be8c67` | `2026-07-22T11:49:17.484902Z` |
| SOLUSDT | `080084a0-d1b2-435b-ad9b-bd294a9bf603` | `af79109cc893bc08550993e0c1375f905b92873cfaa35a2c2afab1c7f8fdc987` | `2026-07-22T11:49:17.559446Z` |

Both commits were reopened in fresh sessions and hash-verified. Both use walk-forward
plan hash `0ddadf63cf5c94d396b0e3020e1a75080727d1972d123b5c657526c6e556de6e`.
Outcome fields inspected before registration: none.

An earlier committed pair, ETH `fb6fe139-d6f7-40dc-a225-7ddc770d8dec` and SOL
`242b35f7-21ad-480d-8688-33e6a1a5bd8c`, omitted tick size, point value, and minimum
contract binding. No outcome was produced. Those records remain immutable but are
superseded and forbidden for evaluation; they are not authoritative preregistration.

## Individual Gates

Each symbol must independently satisfy:

- at least 25 total trades;
- PF at least `1.15` and positive net expectancy;
- maximum drawdown no greater than `$100` from `$1,000` initial capital;
- OOS period beginning `2025-01-01`, at least 10 OOS trades, PF at least `1.15`, and
  positive OOS expectancy;
- at least 15 active trading days and no single day above 25% of trades;
- complete market-regime evidence;
- five predeclared expanding fixed-parameter folds, at least three valid folds, at
  least five test trades per valid fold, and pass rate at least `0.66`;
- complete costs, trade dates, risk snapshot, dataset/replay/protocol integrity, and
  temporal plus execution-spec binding.

## Cross-Market Gates

The candidate-level evaluator is frozen before outcomes. It requires:

- both individual validations pass without a missing or failed required binding;
- combined PF at least `1.15` and combined positive expectancy;
- neither ETH nor SOL has negative base-cost net P/L;
- combined P/L remains positive with fees and slippage at 150% of base assumptions;
- neither symbol supplies more than 70% of combined gross profits.

Any failure produces `REJECT` for version `1.0.0`. A pass produces only eligibility for
Pine compile/parity review. Paper remains blocked until authentic trade-level parity,
targetless risk/order support, and the normal Aurex promotion controls pass.

## One-Shot Procedure

`scripts/run_slow_breakout_spot_holdouts.py` discovers only the current protocol hashes,
verifies current Pine source identity, records both replay outcomes in one transaction,
records both validations, audits all four records, applies the frozen cross-market rule,
and writes a hash-bound artifact. It emits no first-market result before attempting the
second.

The outcome-blind dry run passed with request hashes:

- ETHUSDT: `bd4a8762f5e8f8eca0ab399eabc83f5d438f7ca5d8c21f37a949bf8f9817ce11`.
- SOLUSDT: `2c5175f7a5ac26b78f07615c5952f3d2091fd5ffb423ba5f6cdf09d386b7a145`.

No real replay may use a different request under version `1.0.0`.

## Held-Out Decision

The atomic campaign completed at `2026-07-22T12:08:32.543335+00:00`. Both replay
audits and both validation audits returned `PASS`. The immutable campaign artifact is
`data/evidence/slow_breakout_spot_v1_1.0.0_cross_market_decision.json`, with artifact
evidence hash
`ce8ce41c25e8dff811db44bf8fe8a77af8d920f67c811be8b6fd403154a95c82`.

| Market | Replay ID | Validation ID | Result | Principal failure |
| --- | --- | --- | --- | --- |
| ETHUSDT | `0bbe94e9-4596-41f0-9889-e21ab26085e7` | `efa5db06-08f9-4344-8869-294cdca54d38` | `REJECTED` | Walk-forward pass rate `0.20 < 0.66` |
| SOLUSDT | `97700413-7a29-4dff-aa7c-aab086e8c1b1` | `9ea9e6dd-61d1-4e4e-a1d6-f15cfb899d72` | `REJECTED` | OOS expectancy `-0.7073`, OOS PF `0.5185`, walk-forward pass rate `0` |

ETH recorded 53 trades, `+$44.6864` net, PF `1.5557`, and OOS `+$7.2549` with PF
`1.2082`. SOL recorded 53 trades, `+$59.7447` net and PF `1.8602`, but its 26-trade
OOS period lost `-$18.3894`. The pooled result was 106 trades, `+$104.4311`, PF
`1.6968`, and `+$101.2308` under the frozen 150% cost stress. Those attractive pooled
numbers cannot override either failed individual validation.

The cross-market evaluator returned `REJECT`, evidence hash
`b1214ceb3e2f6ef416d0ef83b27e93e331afa5ff59c3201680f5e8013c9bd4d3`, because both
individual validations were required to pass. Version `1.0.0` is retired. It is not
eligible for Pine parity, paper trading, promotion, or live execution, and its opened
ETH/SOL windows may not be reused to promote a renamed or lightly tuned successor.
