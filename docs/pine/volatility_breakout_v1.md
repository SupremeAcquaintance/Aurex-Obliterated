# Aurex volatility_breakout_v1

Status: `RETIRED / DIAGNOSTIC REJECT / TEMPORAL VALIDATION BLOCKED / DISABLED`

Current version: `1.1.0`

Evidence record: `docs/13_VOLATILITY_BREAKOUT_PREREGISTRATION.md`

## Economic Hypothesis

Volatility clusters. A close beyond a recent range after below-average ATR may carry
short-lived continuation when relative volume confirms participation and the direction
agrees with the last confirmed higher-timeframe EMA regime. The candidate is a
compression-expansion strategy, not a repaired or re-parameterized trend pullback.

## Frozen Signal Logic

- BTCUSDT, 15-minute chart, confirmed bars only.
- ATR(14) below its 40-bar ATR average marks compression.
- Close breaks the previous 20-bar high or low and agrees with candle direction.
- Volume is at least 1.15 times its 20-bar average.
- Last confirmed 1-hour EMA 50/200 permits direction.
- Stop is 1.8 ATR from signal close.
- Target is 2.0 initial risk from expected slipped entry.
- Risk is 0.3% of current equity, capped at 95% position value.
- Commission is 0.05% per side and slippage is two ticks per market fill.

## Contract Hardening From v1.0.0

No v1.0.0 performance was inspected. Before evaluation, v1.1.0 added:

- explicit version and settings fingerprint in alerts;
- confirmed higher-timeframe values to prevent realtime/history drift;
- fixed date window, slippage, risk sizing, and position-value cap;
- end-of-window liquidation and diagnostics;
- exact Pine/source/protocol bindings.

The original breakout, compression, volume, EMA, stop, and target thresholds did not
change. These are reproducibility and capital controls, not outcome-driven tuning.

## Promotion Boundary

The immutable replay loses `-$533.87` over 1,125 trades, has PF `0.6734`, negative IS
and OOS expectancy, and passes zero of six walk-forward folds. Its zero-cost fixed-path
upper bound also loses. The replay audits cleanly, but the durable protocol was
registered after it, so evaluator v1.2 blocks formal validation.

This version is retired and must not be rerun, tuned, or relabeled against the observed
window. A successor requires a new hypothesis, version, source hash, durable protocol,
and genuinely untouched decision evidence. Paper and live trading remain blocked.
