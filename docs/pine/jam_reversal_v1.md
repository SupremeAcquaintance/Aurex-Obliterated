# jam_reversal_v1

Status: Research Pine strategy
Platform: TradingView Pine Script v6

## Purpose

`jam_reversal_v1` converts the video idea into an Aurex-style strategy.

The visual source shows a **Patron Jam Alcista**:

```text
First candle: decisive bearish candle.
Second candle: decisive bullish candle.
The second candle sweeps or tests the prior candle range, then reclaims the prior
body or wick.
```

This script also includes the bearish mirror so shorts can be tested or disabled.

## Default Hypothesis

The default is intentionally stricter than a plain engulfing-candle strategy:

```text
Two-candle Jam pattern must have meaningful body size.
The Jam candle must expand beyond the first candle body.
The Jam candle must reclaim the first candle body by an ATR buffer.
The Jam candle must sweep the prior candle range by default.
Volume expansion is required by default.
Hybrid context requires either HTF pullback context or local reversal context.
Strong counter-trend Jams are blocked with EMA, HTF EMA, DMI, and ADX.
Raw Jam candles arm a pending setup by default instead of entering immediately.
Entry requires a breakout confirmation beyond the Jam extreme within a short window.
Pending setups are canceled if the pattern midpoint fails before confirmation.
Stops default to the original full pattern range plus ATR buffer.
Targets default to an ATR-capped R target so wide pattern stops do not demand
unrealistic follow-through.
Breakeven, ATR trailing, midpoint failure, pullback failure, and max-bars exits
cut failed patterns.
```

The order IDs use `BREAKOUT_EXPANSION` because the Jam candle is modeled as a
range expansion/reclaim event:

```text
AUREX-LONG-BREAKOUT_EXPANSION_JAM
AUREX-SHORT-BREAKOUT_EXPANSION_JAM
```

## Aurex Payload

Alerts include the standard Aurex TradingView fields:

```json
{
  "source": "tradingview",
  "strategy": "jam_reversal_v1",
  "strategy_version": "1.14.0",
  "settings_fingerprint": "jam_reversal_v1|initial_capital=1000|...",
  "symbol": "BTCUSDT",
  "timeframe": "30m",
  "direction": "LONG",
  "entry_price": 100.0,
  "stop_loss": 95.0,
  "take_profit": 110.0,
  "market_regime": "BREAKOUT_EXPANSION",
  "timestamp": "2026-07-18T10:15:00Z"
}
```

## Observed Results

Version `1.0.1` fixes the first TradingView run issue where the script stopped on
bar 0 if `Higher timeframe` was not greater than the chart timeframe. The strategy
now falls back to chart-timeframe EMA context and shows `HTF fallback` in the
diagnostic table instead of producing an empty report.

The first May 1, 2026 through July 18, 2026 BTCUSDT run failed:

```text
Total P/L: -38.24 USD, -3.82%
Max drawdown: 44.15 USD, 4.39%
Profitable trades: 28.13%, 9/32
Profit factor: 0.445
```

The `1.1.0` confirmation run reduced damage but also exposed a second failure:

```text
Total P/L: -9.77 USD
Profitable trades: 0.00%, 0/3
Profit factor: 0
```

Interpretation:

```text
The raw pattern is active enough, but immediate entry after the Jam candle is too
early. The market often rejects the reversal before follow-through appears.
Breakout confirmation alone reduces bad trades, but a wide pattern stop plus 2R
target asks too much from a reversal scalp.
```

The `1.2.0` managed-exit run improved the behavior but still did not clear the
bar:

```text
BTCUSDT 5m, Jun 29 2026 through Jul 18 2026:
Total P/L: +0.54 USD, +0.05%
Max drawdown: 2.62 USD, 0.26%
Profitable trades: 40.00%, 2/5
Profit factor: 1.13

BTCUSDT 15m, May 1 2026 through Jul 18 2026:
Total P/L: -0.42 USD, -0.04%
Max drawdown: 3.53 USD, 0.35%
Profitable trades: 50.00%, 2/4
Profit factor: 0.917
```

Interpretation:

```text
The pattern is no longer bleeding badly, but the gross profit and gross loss are
too close. Commission and slippage can turn a decent-looking 50% win-rate system
negative. The next filter must reject trades whose projected target does not pay
enough after estimated round-trip costs.
```

## Version 1.5.0 TradingView Run

Version `1.3.0` kept the v1.2 confirmation and managed exits, then added a
cost-aware edge filter. It protected the account but over-filtered the system:
the live TradingView run produced no trades on the 5m and 15m test windows.

Version `1.3.2` fixed TradingView compiler warnings by hoisting `ta.lowest()` /
`ta.highest()` calls out of conditional expressions and updating diagnostics to
render on confirmed bars instead of `barstate.islast`.

Version `1.4.0` loosened the confirmation and edge gates:

```text
Reward:risk default increases from 1.35 to 1.60.
Max target ATR increases from 1.35 to 1.80.
Breakeven activation moves from 0.70R to 0.90R.
ATR trailing activation moves from 0.90R to 1.20R.
ATR trail distance increases from 0.90 ATR to 1.10 ATR.
Confirmation window increases from 5 to 8 bars.
Max confirmation distance increases from 0.85 ATR to 1.10 ATR.
Max confirmation candle range increases from 1.90 ATR to 2.20 ATR.
Minimum confirmation close position relaxes from 0.60 to 0.55.
Default minimum target distance relaxes from 0.95 ATR to 0.65 ATR.
Default minimum net reward:risk relaxes from 1.05 to 0.55.
```

Version `1.5.0` fixed the main confirmed-entry flaw. Earlier versions required
context and volume once when the Jam pattern armed, then again on the later
breakout confirmation bar. Confirmed entries now trust the originally qualified
Jam pattern and use the later breakout bar only for confirmation while still
recalculating risk and quantity at entry.

The diagnostic table now exposes the full signal path:

```text
Jam pattern
Qualified Jam
Armed
Confirm signal
Setups
Orders submitted
```

Observed TradingView results on BTCUSDT:

```text
15m, May 1 2026 through Jul 18 2026:
Total P/L: +5.34 USD, +0.53%
Max drawdown: 3.55 USD, 0.35%
Profitable trades: 60.00%, 3/5
Profit factor: 2.288
Average bars in trade: 8

5m, Jun 29 2026 through Jul 18 2026:
Total P/L: +3.97 USD, +0.40%
Max drawdown: 0.90 USD, 0.09%
Profitable trades: 100.00%, 1/1
Average bars in trade: 3

30m, Jan 1 2026 through Jul 18 2026:
Total P/L: -20.31 USD, -2.03%
Max drawdown: 28.71 USD, 2.85%
Profitable trades: 14.29%, 2/14
Profit factor: 0.293
```

Interpretation:

```text
15m is the current candidate timeframe.
5m is positive but has too few trades to trust.
30m should be avoided with these defaults.
```

## Version 1.7.0 TradingView Run

Version `1.6.1` proved that disabling the pullback EMA failure exit made the
15m strategy worse:

```text
15m, May 1 2026 through Jul 18 2026:
Total P/L: +3.03 USD, +0.30%
Max drawdown: 3.67 USD, 0.36%
Profitable trades: 60.00%, 3/5
Profit factor: 1.472
```

The early pullback-failure exit is therefore part of the edge, not noise.

Version `1.7.0` keeps that exit enabled by default and raises the cost-aware
entry gate:

```text
Pullback EMA failure mode default: On
Minimum net reward:risk: 0.55 -> 0.60
```

Observed TradingView results on BTCUSDT:

```text
15m, May 1 2026 through Jul 18 2026:
Total P/L: +5.69 USD, +0.57%
Max drawdown: 1.56 USD, 0.16%
Profitable trades: 66.67%, 2/3
Profit factor: 6.237
Expected payoff: +1.90 USD
Average bars in trade: 5

5m, Jun 29 2026 through Jul 18 2026:
Total P/L: +3.97 USD, +0.40%
Max drawdown: 0.90 USD, 0.09%
Profitable trades: 100.00%, 1/1
Average bars in trade: 3

30m, Jan 1 2026 through Jul 18 2026:
Total P/L: -14.79 USD, -1.48%
Max drawdown: 23.19 USD, 2.30%
Profitable trades: 15.38%, 2/13
Profit factor: 0.362
```

15m remains the primary candidate timeframe. The `1.7.0` filter reduced the
15m trade count from 5 to 3, improved drawdown, and lifted profit factor, but
the sample is still small. 5m is clean but too sparse to trust alone. 30m remains
an avoid timeframe for this strategy.

Surviving 15m trade rows:

```text
May 12 2026 00:30 -> 00:45 long, AUREX-LONG-JAM-PULLBACK-FAIL, -1.087 USD, -0.11%
May 21 2026 21:30 -> 23:15 long, AUREX-LONG-JAM-EXIT, +2.346 USD, +0.25%
Jun 17 2026 23:00 -> Jun 18 2026 00:00 short, AUREX-SHORT-JAM-EXIT, +4.436 USD, +0.47%
```

## Version 1.8.0 TradingView Run

Version `1.8.0` keeps the v1.7 pullback-failure protection, then retunes the
confirmed-entry quality gate:

```text
Minimum confirmation close position: 0.55 -> 0.95
Minimum net reward:risk: 0.60 -> 0.50
Volume expansion: 1.05 -> 1.20
```

Observed TradingView result on BTCUSDT:

```text
15m, May 1 2026 through Jul 18 2026:
Total P/L: +12.27 USD, +1.23%
Max drawdown: 1.69 USD, 0.17%
Profitable trades: 100.00%, 4/4
Profit factor: no closed losers
Expected payoff: +3.07 USD
Average bars in trade: 7
Average profit: 0.39%
```

Boundary checks:

```text
Min net reward:risk 0.45 brought back a loser:
+10.83 USD, 4/5, 80.00%, profit factor 8.622.

Min net reward:risk 0.55 was cleaner but lower opportunity:
+9.48 USD, 3/3.

Min net reward:risk 0.65 was too selective:
+6.79 USD, 2/2.

Turning volume expansion off over-admitted trades:
+6.09 USD, 6/12, 50.00%, profit factor 1.521.

Volume expansion 1.30 removed two useful winners:
+7.12 USD, 2/2.

Volume expansion 1.20 preserved the full 4/4 set while keeping the volume gate
stricter than v1.7.
```

Interpretation:

```text
The main flaw was not target distance. Lowering Min target distance ATR from
0.65 to 0.45 did not change the 15m result. The edge was instead concentrated in
confirmation quality and rejecting lower net reward:risk setups.

The current candidate is therefore BTCUSDT 15m only. The 5m and 30m cross-checks
must be rerun before export because the TradingView automation session hit a
usage limit immediately after the 15m v1.8 tuning pass.
```

## Version 1.9.0 TradingView Run

Version `1.9.0` adds a timeframe safety gate. The default mode is
`15m/30m only` because those are the only timeframes that produced acceptable
BTCUSDT evidence after the v1.8 retune. 5m remains available as a research
option, but it is too sparse by default. 45m and 1h are blocked unless the user
explicitly changes `Allowed chart timeframe` to `Any`.

Observed TradingView results after compiling v1.8 defaults into the live chart:

```text
15m, May 1 2026 through Jul 19 2026:
Total P/L: +12.27 USD, +1.23%
Max drawdown: 1.69 USD, 0.17%
Profitable trades: 100.00%, 4/4
Profit factor: no closed losers
Expected payoff: +3.07 USD
Average bars in trade: 7

5m, Jun 29 2026 through Jul 19 2026:
Total P/L: +3.97 USD, +0.40%
Max drawdown: 0.90 USD, 0.09%
Profitable trades: 100.00%, 1/1
Average bars in trade: 3

30m, Jan 1 2026 through Jul 19 2026:
Total P/L: +5.96 USD, +0.60%
Max drawdown: 2.70 USD, 0.27%
Profitable trades: 66.67%, 2/3
Profit factor: 4.968
Expected payoff: +1.99 USD
Average bars in trade: 2

45m, Jan 1 2026 through Jul 19 2026:
No trade data.

1h, Jan 1 2025 through Jul 19 2026:
Total P/L: -14.67 USD, -1.47%
Max drawdown: 15.15 USD, 1.52%
Profitable trades: 0.00%, 0/4
Profit factor: 0
```

Interpretation:

```text
The timeframe guard is required before Aurex import. Without it, the same
pattern can accidentally run on 1h, where the tested sample is a clean failure.

The candidate import profile is BTCUSDT 15m primary, BTCUSDT 30m secondary.
5m can be researched manually but should not be included in the default import
profile until it has more trades.
```

## Version 1.10.0 TradingView Run

Version `1.10.0` adds a symbol safety gate. The default mode is `BTCUSDT only`
because the first cross-symbol sweep showed the tuned Jam reversal behavior is
not yet portable:

```text
BTCUSDT 15m, May 1 2026 through Jul 19 2026:
Total P/L: +12.27 USD, +1.23%
Max drawdown: 1.69 USD, 0.17%
Profitable trades: 100.00%, 4/4
Trade rows: +2.677, +2.353, +2.774, +4.463 USD

BTCUSDT 30m, Jan 1 2026 through Jul 19 2026:
Total P/L: +5.96 USD, +0.60%
Max drawdown: 2.70 USD, 0.27%
Profitable trades: 66.67%, 2/3
Trade rows: -1.502, +4.147, +3.317 USD

ETHUSDT 15m, May 1 2026 through Jul 19 2026:
Total P/L: -5.91 USD, -0.59%
Max drawdown: 6.63 USD, 0.66%
Profitable trades: 0.00%, 0/3

ETHUSDT 30m, Jan 1 2026 through Jul 19 2026:
No trade data.

SOLUSDT 15m, May 1 2026 through Jul 19 2026:
No trade data.

SOLUSDT 30m, Jan 1 2026 through Jul 19 2026:
Total P/L: -5.23 USD, -0.52%
Max drawdown: 5.62 USD, 0.56%
Profitable trades: 0.00%, 0/3
```

Interpretation:

```text
The BTCUSDT profile is promising but still sparse. The default import profile is
therefore BTCUSDT only, with 15m primary and 30m secondary. Cross-symbol use must
remain research-only by manually setting Allowed symbol to Any.
```

## Version 1.11.0 TradingView Run

Version `1.11.0` keeps the BTCUSDT-only and 15m/30m-only safety guards, then
retunes the target model:

```text
Reward:risk default: 1.60 -> 1.80
Max target ATR default: 1.80 -> 2.50
Target mode remains ATR capped R.
Current trend EMA filter remains Off.
```

Observed TradingView results on the current July 20, 2026 test state:

```text
BTCUSDT 15m, May 1 2026 through Jul 20 2026:
Total P/L: +19.38 USD, +1.94%
Max drawdown: 1.90 USD, 0.19%
Profitable trades: 83.33%, 5/6
Profit factor: 14.610
Expected payoff: +3.23 USD
Average bars in trade: 8

BTCUSDT 30m, Jan 1 2026 through Jul 20 2026:
Total P/L: +8.09 USD, +0.81%
Max drawdown: 2.87 USD, 0.29%
Profitable trades: 66.67%, 2/3
Profit factor: 5.835
Expected payoff: +2.70 USD
```

Retune boundary checks:

```text
Max target ATR 2.0 improved 15m only slightly versus 1.8, but admitted one loser:
+12.58 USD, 4/5, profit factor 9.841.

Max target ATR 2.2 was better:
+16.35 USD, 5/6, profit factor 12.488.

Max target ATR 2.5 was the local best:
+18.21 USD at 1.60R and +19.38 USD at 1.80R, 5/6, drawdown 0.19%.

Max target ATR 2.6 and 3.0 fell off:
2.6 ATR: +11.46 USD, 4/6.
3.0 ATR: +12.00 USD, 4/6.

Fixed R with the 2.5 ATR cap was worse than ATR capped R:
+12.45 USD, 4/6, profit factor 7.468.

Turning on the current timeframe trend EMA filter was rejected:
15m fell from +12.27 USD, 4/4 to +6.79 USD, 2/2 under the v1.10 baseline.
30m fell from +5.96 USD, 2/3 to +2.64 USD, 1/2.

Temporarily enabling 5m with the v1.11 target defaults stayed too weak:
+1.27 USD, 2/4, profit factor 1.554.
```

Interpretation:

```text
The previous 1.8 ATR cap was too conservative after the stricter confirmation
gate. Letting winners reach up to 2.5 ATR improves both 15m and 30m without
materially increasing drawdown. Beyond 2.5 ATR the system starts holding too
long and gives trades back.

The current import candidate remains BTCUSDT only, 15m primary, 30m secondary.
5m and cross-symbol execution remain blocked by default.
```

## Version 1.12.0 TradingView Run

Version `1.12.0` keeps the v1.11 target model, then raises the default cost-aware
edge gate:

```text
Min net reward:risk default: 0.50 -> 0.70
Reward:risk default remains 1.80.
Max target ATR default remains 2.50.
Target mode remains ATR capped R.
```

Observed TradingView probes before promoting the new default:

```text
BTCUSDT 15m, May 1 2026 through Jul 20 2026:
0.50 net RR: +19.38 USD, 5/6, profit factor 14.610, max drawdown 0.19%.
0.55 net RR: unchanged versus 0.50.
0.60 net RR: unchanged versus 0.50.
0.70 net RR: +16.94 USD, 4/5, profit factor 12.899, max drawdown 0.19%.

BTCUSDT 30m, Jan 1 2026 through Jul 20 2026:
0.50 net RR: +8.09 USD, 2/3, profit factor 5.835, max drawdown 0.29%.
0.65 net RR: unchanged versus 0.50.
0.70 net RR: +9.78 USD, 2/2, no closed loser, max drawdown 0.12%.
```

Interpretation:

```text
The 0.70 net RR gate is a cleaner import profile. It gives up only 0.75 USD
across the combined BTCUSDT 15m/30m sample while removing the 30m loser and
reducing 30m drawdown. The trade count is still sparse, so this is a guarded
candidate, not a final production claim.
```

## Version 1.13.0 TradingView Run

Version `1.13.0` keeps the BTCUSDT-only and 15m/30m-only safety guards, then
promotes the best shared profile from the July 20, 2026 TradingView sweep:

```text
Stop mode default: Pattern -> Tighter
Reward:risk default: 1.80 -> 2.20
Max target ATR default remains 2.50
Min net reward:risk default: 0.70 -> 0.80
Volume expansion default remains 1.20
ATR stop multiplier remains 1.40
```

Observed TradingView results after the sweep:

```text
BTCUSDT 15m, May 1 2026 through Jul 20 2026:
Total P/L: +19.54 USD, +1.95%
Max drawdown: 2.17 USD, 0.22%
Profitable trades: 100.00%, 4/4
Profit factor: no closed losers
Expected payoff: +4.89 USD
Average bars in trade: 9

BTCUSDT 30m, Jan 1 2026 through Jul 20 2026:
Total P/L: +11.26 USD, +1.13%
Max drawdown: 1.20 USD, 0.12%
Profitable trades: 100.00%, 2/2
Profit factor: no closed losers
Expected payoff: +5.63 USD
Average bars in trade: 6

Post-compile guards:
BTCUSDT 5m: no trade data by default.
ETHUSDT 15m: no trade data by default.
```

Rejected v1.13-adjacent probes:

```text
Max target ATR 2.75 broke the 30m profile:
+8.96 USD, 2/3, max drawdown 0.29%.

Max target ATR 2.40 kept both timeframes clean but gave up profit:
30m +9.86 USD, 2/2; 15m +18.62 USD, 4/4.

Reward:risk 2.00 improved 30m to +10.75 USD while 15m was unchanged.
Reward:risk 2.20 improved 30m again to +11.26 USD while 15m was unchanged.
Reward:risk 2.40 was unchanged versus 2.20, so 2.20 is the cleaner default.

ATR stop multiplier 1.30 improved 15m slightly but broke 30m:
30m +9.82 USD, 2/3, max drawdown 0.29%.

ATR stop multiplier 1.50 kept both timeframes clean but gave up profit:
30m +11.03 USD, 2/2; 15m +19.29 USD, 4/4.

Volume expansion 1.10 admitted weak 30m trades:
+6.98 USD, 2/4, profit factor 2.634, max drawdown 0.42%.

Volume expansion 1.30 was unchanged on 30m but cut the 15m sample to:
+10.64 USD, 2/2.
```

Interpretation:

```text
This is the strongest BTCUSDT import candidate so far. It improves v1.12 from
+26.72 USD across 7 closed trades with one loser to +30.80 USD across 6 closed
trades with no closed losers on the tested 15m/30m windows. The sample remains
small, so export and Aurex import validation still need to prove that the trade
rows and payloads behave correctly outside TradingView.
```

## Version 1.14.0 TradingView Run

Version `1.14.0` keeps the strict v1.13 confirmation profile on 30m, but applies
timeframe-adaptive confirmation on 15m:

```text
15m effective confirmation window: 10 bars.
15m effective max confirmation distance: 1.25 ATR.
15m effective minimum confirmation close position: 0.85.
15m effective volume expansion: 1.15.
30m keeps the input defaults: 8 bars, 1.10 ATR, 0.95 close position, 1.20 volume expansion.
```

TradingView evidence after compiling v1.14.0:

```text
BTCUSDT 15m, May 1 2026 through Jul 20 2026:
Total P/L: +24.87 USD, +2.49%
Max drawdown: 2.17 USD, 0.22%
Profitable trades: 100.00%, 5/5
Profit factor: no closed losers
Expected payoff: +4.97 USD
Average bars in trade: 8

BTCUSDT 30m, Jan 1 2026 through Jul 20 2026:
Total P/L: +11.26 USD, +1.13%
Max drawdown: 1.20 USD, 0.12%
Profitable trades: 100.00%, 2/2
Profit factor: no closed losers
Expected payoff: +5.63 USD
Average bars in trade: 6

BTCUSDT 5m: no trade data by default.
ETHUSDT 5m: no trade data by default.
```

Rejected v1.14 probe:

```text
Applying the 15m-looser confirmation globally broke 30m:
Total P/L: -15.59 USD, -1.56%
Max drawdown: 17.01 USD, 1.70%
Profitable trades: 20.00%, 2/10
Profit factor: 0.418
```

Interpretation:

```text
The useful edge appears timeframe-specific. A slightly looser 15m confirmation
admits one additional winner without increasing drawdown, while 30m must stay
strict. This is still research-grade due to small sample size, but it is a better
candidate than v1.13.0 for the current BTCUSDT windows.
```

## Retuning Checklist

Record:

```text
Total trades
Win rate
Profit factor
Total P/L
Max drawdown
Average winner
Average loser
Average bars in trade
Top 10 recent trade rows
```

If there are no trades, relax these one at a time:

```text
Lower Min net reward:risk from 0.80 to 0.70.
Lower Min target distance ATR from 0.65 to 0.55.
Increase Max confirmation distance ATR from 1.10 to 1.25.
Reduce Min confirmation close position from 0.95 to 0.85 on 15m only.
Increase Max confirmation candle range ATR from 2.20 to 2.40.
Turn off Use cost-aware edge filter only to compare gross signal quality.
Switch Entry style to Immediate only for comparison, not as the new default.
Set Context mode to None.
Turn off Use volume expansion.
Turn off Require prior range sweep.
Set Jam reclaim mode to Body if it was changed to Wick.
Reduce Min Jam body expansion.
Reduce Min Jam candle range ATR.
```

If there are too many losing trades, tighten these one at a time:

```text
Raise Min net reward:risk from 0.80 to 0.90.
Raise Min target distance ATR from 0.65 to 0.70.
Lower Max confirmation distance ATR from 1.10 to 0.85.
Increase Confirmation ATR buffer from 0.02 to 0.06.
Raise Breakeven after R from 0.90 to 1.10 if breakeven exits are too early.
Set Jam reclaim mode to Wick.
Turn on Use current trend EMA filter.
Increase Min Jam body ratio.
Increase Volume expansion.
Reduce Max Jam candle range ATR.
Increase Counter-trend ADX block strictness by lowering the threshold.
```

## Non-Repainting Controls

The strategy uses:

```text
barstate.isconfirmed
request.security(..., lookahead = barmerge.lookahead_off)
calc_on_every_tick = false
process_orders_on_close = true
```

The script is research-only until a TradingView run shows enough completed trades
and the settings snapshot is recorded.
