# Aurex trend_pullback_v1 Reference Replay

The reference replay is a deterministic comparison tool for one immutable Aurex OHLCV
dataset. It is not an accepted backtest, does not create a backtest report, cannot make
a strategy eligible, and cannot unlock paper or live trading.

## Workflow

1. Import a quality-checked dataset through **Backtests > Historical data**.
2. Set `trend_pullback_v1` v1.3.0 parameters to the intended Pine values.
3. Ensure the dataset begins before `backtest_start`. With 15-minute data, a 60-minute
   higher timeframe, and HTF EMA 200, at least 800 base candles are needed before the
   test boundary for declared warm-up.
4. Select the immutable dataset under **Reference replay**.
5. Record the exchange tick size, point value, minimum contract, commission per side,
   and slippage ticks.
6. Select **Replay preflight** and inspect trades, net P/L, warm-up, diagnostics,
   blockers, assumptions, and replay hash.
7. When status is `READY`, select **Record evidence** to preserve the request, complete
   result, dataset hash, engine hash, and independent record hash. `READY` means the
   engine completed; it does not mean the strategy passed.
8. Run the record audit and compare the result with a TradingView run using the same
   dataset window and settings.

The UI always labels the result `COMPARISON ONLY`.

## Engine Semantics

Engine version: `trend-pullback-reference-v1.1.0`.

The engine currently implements:

- causal EMA, Wilder RSI, and Wilder ATR series;
- previous confirmed higher-timeframe values matching Pine's offset
  `[1]` plus `lookahead_on` contract;
- UTC epoch alignment for higher-timeframe grouping;
- EMA pullback-zone, RSI-reset, confirmation-candle, and trend filters;
- ATR, swing, and wider stop modes;
- point-value-aware equity-risk sizing, maximum position-value capping, and minimum
  contract rounding;
- close-of-signal-bar market entry with directional tick slippage;
- static stop-loss and take-profit brackets;
- commission on entry and exit notional;
- adverse slippage on market and stop fills;
- conservative stop-first resolution when one candle touches stop and target;
- market closure on the candle whose close reaches the frozen backtest boundary;
- deterministic diagnostics, metrics, normalized trades, and engine evidence hash.

No future candle is consulted to form a signal. Higher-timeframe values become visible
from the first base bar after the corresponding higher-timeframe candle is complete.

Two additional strategy-specific engines use the same immutable record and audit
surface:

- `volatility-breakout-reference-v1.0.0` for the retired
  `volatility_breakout_v1` v1.1.0 candidate;
- `slow-breakout-spot-reference-v1.0.0` for `slow_breakout_spot_v1` v1.0.0.

The slow spot engine requires native 4h data, uses only prior 55/20-bar channel values,
Wilder ATR(20), long-only spot sizing, a fixed initial catastrophe stop, confirmed-close
channel exits with adverse market slippage, no same-bar re-entry, and no take-profit.
`ReferenceReplayTrade.take_profit` is therefore nullable. Existing bracket strategies
retain numeric targets and unchanged stop-first semantics.

## API

```text
POST /backtests/reference-replay/preflight
POST /backtests/reference-replay/runs
GET  /backtests/reference-replay/runs
GET  /backtests/reference-replay/runs/{reference_replay_run_id}
GET  /backtests/reference-replay/runs/{reference_replay_run_id}/audit

POST /backtests/reference-replay/validations/preflight
POST /backtests/reference-replay/validations
GET  /backtests/reference-replay/validations
GET  /backtests/reference-replay/validations/{reference_replay_validation_id}
GET  /backtests/reference-replay/validations/{reference_replay_validation_id}/audit
```

The external TradingView handoff is exposed separately:

```text
GET /backtests/protocols/{protocol_id}/run-manifest
GET /backtests/protocols/{protocol_id}/tradingview-run-package
```

The run package is available only for a ready, venue-qualified manifest and includes
the exact Pine source bytes represented as UTF-8 text, their SHA-256, the frozen setup,
and the qualified TradingView chart URL. It mutates no evidence ledger.

Example body:

```json
{
  "dataset_id": "<immutable-dataset-id>",
  "strategy": "trend_pullback_v1",
  "strategy_version": "1.3.0",
  "parameters": {
    "initial_capital": "1000",
    "backtest_start": "2026-02-01T00:00:00Z",
    "backtest_end": "2026-03-31T23:59:59Z",
    "higher_timeframe": "60",
    "pullback_ema_fast": 20,
    "pullback_ema_slow": 50,
    "trend_ema": 200,
    "htf_ema_fast": 50,
    "htf_ema_slow": 200,
    "rsi_length": 14,
    "atr_length": 14,
    "atr_multiplier": "1.5",
    "reward_risk": "2.0",
    "swing_lookback": 5,
    "pullback_atr_tolerance": "0.25",
    "stop_mode": "Wider",
    "risk_per_trade_percent": "0.5",
    "max_position_value_percent": "95",
    "enable_long": true,
    "enable_short": true
  },
  "tick_size": "0.01",
  "point_value": "1",
  "minimum_contract": "0.001",
  "commission_percent": "0.05",
  "slippage_ticks": 2,
  "intrabar_policy": "stop_first"
}
```

## Frozen Statistical Validation

Reference replay execution and statistical validation are separate immutable records.
The validation preflight binds one recorded replay to one intact, unconsumed frozen
protocol and verifies strategy, version, symbol, timeframe, parameters, dates, costs,
slippage, and risk settings. A binding mismatch is `BLOCKED` and cannot be recorded.

A bound validation is recorded as `PASSED` or `REJECTED`; negative evidence is
preserved rather than discarded. It evaluates the complete period, chronological
in-sample and out-of-sample partitions, the protocol's fixed-parameter walk-forward
folds, trade concentration, purge-gap assignment, and market-regime performance. Its
evidence hash binds the source replay, protocol, evaluator, metrics, reasons, and trade
ledger. Audit replays the evaluation and distinguishes record tampering from source or
evaluator drift.

Evaluator `reference-replay-validation-v1.1.0` introduced drawdown from cumulative
realized P/L starting at zero inside each whole-period, IS, OOS, and walk-forward
evaluation segment. This is translation-invariant and prevents the first post-trade
account-equity value from silently becoming the high-water baseline. The whole-period
drawdown must exactly match the recorded reference replay or validation is `BLOCKED`.

The same evaluator records fixed-path cost sensitivity at zero, half, base, 150%, and
200% fee/slippage multipliers. The base case must reconcile net P/L, expectancy,
profit factor, and drawdown to replay. These scenarios hold trade timestamps,
directions, and quantities constant, so they isolate modeled monetary cost sensitivity
rather than claiming order-book, market-impact, or position-sizing re-simulation.

Evaluator `reference-replay-validation-v1.2.0` retains those metric and cost rules and
adds temporal preregistration binding. The durable protocol record must have
`registered_at <= replay.recorded_at`; otherwise validation is `BLOCKED`, metrics are
not exposed, no validation hash is produced, and no validation record can be written.

When a protocol declares `tick_size`, `point_value`, and `minimum_contract` in its risk
snapshot, evaluator v1.2 also binds those values to the replay request. The authoritative
slow spot protocols declare all three. A mismatch blocks validation before metrics are
exposed. Older protocols without those fields retain their original warning rather than
being silently rewritten.

Evaluator and evidence schemas are versioned. Legacy v1.0.0 and v1.1.0 validation
records remain immutable and are re-audited with their original evaluator/schema
semantics instead of being rewritten by later controls.

Validation never consumes the TradingView protocol and never promotes a reference
replay. Both passed and rejected records remain comparison-only, with acceptance,
paper eligibility, and live eligibility false. Only an authentic TradingView report
can consume the frozen protocol and enter the trusted backtest path.

## Honest Limitations

- Pine built-ins and TradingView's broker emulator remain authoritative until measured
  parity exists. Matching formulas alone is not proof.
- The engine has no tick data or bar magnifier. Stop-first is intentionally pessimistic
  when both bracket prices occur inside one candle.
- Higher-timeframe grouping uses UTC epoch boundaries. This is appropriate for the
  initial continuous crypto scope but can differ from exchange-session boundaries.
- Session-based datasets are rejected by replay v1.
- Positive limit gaps receive no favorable price improvement.
- Funding, borrow costs, spread, liquidity impact, and partial fills are not modeled.
- Cost-sensitivity scenarios hold the recorded path and quantities fixed. They do not
  model cost-driven sizing changes, queue position, depth, or market impact.
- The replay preflight writes nothing. The explicit record endpoint persists immutable
  comparison evidence in a separate ledger; it never appears as an accepted backtest.
- Only `READY` runs can be recorded. Negative P/L remains recordable because readiness
  describes deterministic execution, not profitability.
- A record audit recomputes its record hash, re-audits the dataset, reruns the engine,
  and compares the dataset hash, engine hash, and complete result snapshot.
- A position can remain open only when the dataset does not contain the candle whose
  close reaches `backtest_end`.

The trade-level parity harness is documented in `docs/07_TRADINGVIEW_PARITY.md`. It can
compare and preserve immutable mismatch evidence, but operational parity remains
unproven until a real TradingView completed-trades export and matching chart dataset
are loaded. The reference replay remains comparison-only regardless of parity status.
