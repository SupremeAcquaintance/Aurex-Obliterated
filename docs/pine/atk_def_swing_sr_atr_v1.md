# atk_def_swing_sr_atr_v1

Status: Research Pine strategy
Platform: TradingView Pine Script v6

## Purpose

`atk_def_swing_sr_atr_v1` converts the attached ATK/DEF swing high-low support and
resistance indicator into a testable Aurex-style strategy.

Core logic:

```text
Confirmed swing highs become active resistance.
Confirmed swing lows become active support.
Range retest entries trade rejection back away from active S/R.
Breakout entries trade closes through active S/R with an ATR buffer.
ATR defines stop distance.
Fixed reward:risk defines take profit.
Optional higher-timeframe EMA bias and ADX regime filters can be enabled.
```

## Aurex Payload

Alerts include the standard Aurex TradingView fields:

```json
{
  "source": "tradingview",
  "strategy": "atk_def_swing_sr_atr_v1",
  "strategy_version": "1.5.0",
  "settings_fingerprint": "atk_def_swing_sr_atr_v1|initial_capital=1000|...",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "direction": "LONG",
  "entry_price": 100.0,
  "stop_loss": 95.0,
  "take_profit": 110.0,
  "market_regime": "RANGING",
  "timestamp": "2026-07-05T10:15:00Z"
}
```

Range retests emit `market_regime: RANGING`. Breakouts emit
`market_regime: BREAKOUT_EXPANSION`. Entry order IDs also include those regime labels
so TradingView completed-trade exports can be parsed by Aurex without hand-labeling.

## First Test Pass

Version `1.0.0` produced a high-trade, negative-expectancy first pass on BTCUSDT
30m for January 1, 2026 through July 5, 2026:

```text
203 trades
32.51% profitable
0.83 profit factor
-12.15% total P/L
20.48% max drawdown
```

Version `1.1.0` was then changed to stricter defaults:

```text
Breakout-only mode
Higher-timeframe EMA bias enabled
Current-timeframe EMA trend filter enabled
ADX breakout filter enabled
Breakout volume filter enabled
Minimum S/R range required
Maximum breakout extension required
Trade cooldown enabled
```

Version `1.1.0` was cleaner but still rejected on BTCUSDT 30m for June 15, 2026
through July 5, 2026:

```text
8 trades
25.00% profitable
0.347 profit factor
-1.36% total P/L
1.53% max drawdown
```

The trade list showed the immediate breakout entries were still vulnerable to false
breaks. Version `1.2.0` changed the default hypothesis to **Breakout retest**:

```text
First close through a swing level only arms a pending retest.
The script enters only if price retests the broken level within the retest window.
The retest bar must close back in the breakout direction.
The pending retest level is plotted in cyan.
Default reward:risk is increased to 2.5.
```

Version `1.2.0` produced no Strategy Tester trades on the BTCUSDT June 15, 2026
through July 5, 2026 window tested by the operator. The diagnostics showed the
breakout-retest path was too narrow, not that order creation was broken.

Version `1.3.0` pivots the default to **Sweep reclaim**, which is closer to the
attached indicator's support/resistance purpose:

```text
Long: price sweeps below active support, then closes back above it.
Short: price sweeps above active resistance, then closes back below it.
The reclaim candle must show wick rejection.
Sweep entries use RANGING regime labels.
Sweep mode does not use trend or ADX filters by default.
```

Version `1.3.0` produced enough data to diagnose the strategy, but the win rate was
too low on BTCUSDT 30m for January 1, 2026 through July 5, 2026:

```text
84 trades
25.00% profitable
0.723 profit factor
-8.92% total P/L
11.58% max drawdown
Average winner 1.86%
Average loser -1.19%
```

The payoff ratio improved, but the trade list showed many early sweep-fade entries
losing while price kept trending through the active level.

Version `1.4.0` tested confirmed sweep entries:

```text
The sweep/reclaim candle arms a pending setup.
The script enters only if price follows through beyond the reclaim candle within 3 bars.
Long confirmation requires a close above the reclaim candle high plus a small ATR buffer.
Short confirmation requires a close below the reclaim candle low plus a small ATR buffer.
The stop remains anchored to the original sweep candle.
The armed sweep level is plotted in fuchsia.
Set Sweep entry style to Immediate to reproduce the v1.3 behavior.
```

The BTCUSDT 30m January 1, 2026 through July 5, 2026 result was still negative:

```text
45 trades
22.22% profitable
0.634 profit factor
-6.75% total P/L
10.06% max drawdown
Average winner 2.40%
Average loser -1.46%
Average bars in trade 75
```

Confirmed sweeps cut trade count, but they also lowered win rate and increased loss
size. Version `1.5.0` therefore returns the default `Sweep entry style` to
**Immediate** and adds two filters around the v1.3 baseline:

```text
Block trend-leg sweep fades:
  Blocks long sweeps when ADX, DMI, current EMA, and HTF EMA all point down.
  Blocks short sweeps when ADX, DMI, current EMA, and HTF EMA all point up.

Exit sweep on level failure:
  Long sweep closes if it loses reclaimed support by an ATR buffer.
  Short sweep closes if it loses reclaimed resistance by an ATR buffer.
```

Test `1.5.0` defaults first on BTCUSDT 30m for January 1, 2026 through July 5,
2026. Then isolate behavior with `Entry mode`:

```text
Sweep reclaim: test only liquidity sweep and reclaim.
Retest: test only support/resistance rejection.
Breakout: test only immediate swing-level breaks.
Breakout retest: test only break-and-retest entries.
Both: allow range retests plus break-and-retest entries.
```

If the revised default produces too few trades, relax these one at a time:

```text
Increase Trend-leg fade min ADX.
Turn off Block trend-leg sweep fades.
Turn off Exit sweep on level failure.
Reduce Sweep ATR buffer.
Reduce Sweep wick/body multiplier.
Turn off Require level range.
Increase Level active bars.
```

## Non-Repainting Controls

The strategy waits for confirmed pivot bars before a level becomes tradable. It also
uses:

```text
barstate.isconfirmed
request.security(..., lookahead = barmerge.lookahead_off)
calc_on_every_tick = false
process_orders_on_close = true
```

The script is for research. Do not import or paper-route it until a TradingView run has
enough completed trades and the settings snapshot is recorded.
