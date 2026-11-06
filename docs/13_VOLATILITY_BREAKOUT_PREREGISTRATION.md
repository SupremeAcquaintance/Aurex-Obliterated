# Volatility Breakout v1.1 Freeze, Replay, And Binding Incident

## Status

`RETIRED / DIAGNOSTIC REJECT / FORMAL VALIDATION BLOCKED / NOT PAPER-ELIGIBLE`

The source, parameters, windows, and gates were frozen before the strategy outcome was
calculated. The first database registration call was not committed, however. The replay
was persisted before a durable protocol existed, so this version does not have valid
preregistration and cannot receive a formal eligibility verdict.

## Identity

- Strategy: `volatility_breakout_v1`
- Version: `1.1.0`
- Pine path: `pine/strategies/volatility_breakout_v1.pine`
- Prior unaudited v1.0.0 source SHA-256:
  `c06c4f9259e3697e89dc7f0cfdc52f420d77e973134c3b7bc1a3c13637d2d7df`
- Frozen v1.1.0 source SHA-256:
  `4b692f3f95c06ae4bfa787f2c8f4fc2039859d55b9f040cd78284ce720f55d35`
- Walk-forward plan hash:
  `e3a9cf751dabfb5e5390702d4292016dc0cddbc4e000fc44c45194c7110c6d78`
- Outcome fields inspected by the planner before the source freeze: none

The transient protocol ID `42a995dc-1a7a-40d8-ba86-21f08fe3725d` was produced by a
flushed but uncommitted transaction and rolled back. It is not evidence and must never
be cited as a registered protocol.

## Economic Hypothesis

Crypto volatility clusters and range breaks often fail without participation. The
candidate tested whether compression followed by range escape, relative volume, and a
confirmed higher-timeframe directional regime produced enough continuation to survive
fees, adverse fills, and false breakouts.

This mechanism is distinct from `trend_pullback_v1`: it enters expansion away from a
completed range, not a retracement toward an EMA. That distinction did not create edge
in the recorded replay.

## Frozen Contract

- Dataset ID: `9724b9c7-03fa-4cba-9d5f-1e3bd69aa322`
- Dataset SHA-256:
  `2a048a6709d0f066977d317ec2d013d362cc68a5f626d85201e98d9c6925440e`
- Venue/symbol/timeframe: Binance / BTCUSDT / 15m
- Evaluation: `2023-02-01T00:00:00Z` to `2026-07-01T00:00:00Z`
- IS: `2023-02-01T00:00:00Z` to `2025-01-31T23:59:59.999999Z`
- OOS: `2025-02-01T00:00:00Z` to `2026-07-01T00:00:00Z`
- Six expanding fixed-parameter walk-forward folds
- Commission: 0.05% per side
- Slippage: two adverse ticks per market fill
- Intrabar ambiguity: stop first
- Risk: 0.3% equity per trade, capped at 95% position value

Signal thresholds remained the original outcome-blind values: breakout 20,
compression 40, ATR 14, stop 1.8 ATR, reward:risk 2.0, volume average 20, relative
volume 1.15, and confirmed 60-minute EMA 50/200 regime filtering.

## Binding Incident

- Replay ID: `9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7`
- Replay recorded: `2026-07-21T12:11:20.906155Z`
- Replay engine: `volatility-breakout-reference-v1.0.0`
- Replay record hash:
  `67fbd22e0b195cb16c3bc37caadb269e292b91e0e4859bd88d3c89dfcff4c20f`
- Replay audit: `PASS`
- Actual protocol ID: `6d0f10f1-8e23-42a2-874a-b36948bc1738`
- Actual protocol registered: `2026-07-21T12:12:13.076304Z`
- Protocol hash:
  `56430081d944b2adf234f313bd72fe5a92eddb952119a20c45ffc4b0372572a9`
- Registration lag: approximately 52.17 seconds after the replay

Evaluator `reference-replay-validation-v1.2.0` returns `BLOCKED` with
`protocol_registered_before_reference_replay_mismatch`, exposes no metrics, creates no
validation hash, and cannot write a validation record. The committed timestamps are
the authoritative evidence of the failed temporal binding.

## Diagnostic Result

These figures describe the immutable replay. They are negative research evidence, not
a formally preregistered eligibility result.

| Scope | Trades | Net P/L | Profit factor | Expectancy | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Overall | 1,125 | -$533.87 | 0.6734 | -$0.4746 | $556.48 |
| IS | 655 | -$396.66 | 0.6523 | -$0.6056 | $414.76 |
| OOS | 470 | -$137.21 | 0.7222 | -$0.2919 | $149.58 |

All six fixed-parameter walk-forward folds lost and failed. The fixed-path zero-cost
upper bound also lost `$37.10` with profit factor `0.9714`; half costs lost `$285.49`.
This is not merely a fee problem.

## Final Disposition

Retire v1.1.0. Do not rerun, tune, relabel, or register a replacement protocol against
the same observed outcome. Even without the binding failure, the mechanism misses
overall, OOS, drawdown, and walk-forward gates by a wide margin.

Any successor must have a new version, a revised economic hypothesis justified by
failure analysis, a new source hash, and genuinely untouched decision evidence. The
2023-2026 BTCUSDT result is now development-contaminated for volatility-breakout
redesign. A future held-out decision must use a previously uninspected candidate
outcome, such as a preregistered cross-market holdout and/or forward data acquired only
after the durable protocol receipt exists.

## Process Correction

Candidate registration now has a transaction-owning path that commits the protocol,
reopens it in a fresh session, verifies the stored hash, and refuses registration if a
same-strategy/version replay already exists:

```text
python scripts/register_candidate_protocol.py <candidate>
```

The current evaluator independently enforces protocol time no later than replay time.
Both controls are required; a source freeze written in documentation is not a durable
preregistration receipt.
