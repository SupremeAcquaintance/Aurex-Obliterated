# trend_pullback_v1

Status: retired/rejected; disabled by default on fresh databases; parity calibration only
Platform: TradingView Pine Script v6

## Purpose

`trend_pullback_v1` detects trend-continuation pullback setups and sends webhook-ready JSON alerts to Aurex.

The script is intentionally simple:

```text
Higher-timeframe trend filter
Current-timeframe EMA trend filter
Pullback near EMA 20 or EMA 50
RSI reset filter
Confirmation candle
ATR, swing, or wider stop
Fixed reward:risk take profit
```

## Aurex Payload

The script sends alerts shaped like:

```json
{
  "source": "tradingview",
  "strategy": "trend_pullback_v1",
  "strategy_version": "1.3.0",
  "settings_fingerprint": "trend_pullback_v1|initial_capital=1000|...",
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "direction": "LONG",
  "entry_price": 100.0,
  "stop_loss": 95.0,
  "take_profit": 110.0,
  "market_regime": "TRENDING_UP",
  "timestamp": "2026-06-06T10:15:00Z"
}
```

## TradingView Alert Setup

1. Add `pine/strategies/trend_pullback_v1.pine` to TradingView Pine Editor.
2. Save and add it to a chart.
3. Create an alert.
4. Set condition to `Aurex trend_pullback_v1` and choose any `alert()` function call.
5. Set the webhook URL to your public HTTPS Aurex URL:

```text
https://<your-aurex-public-host>/webhooks/tradingview?secret=<AUREX_WEBHOOK_SECRET>
```

6. Keep the alert message as the JSON produced by the Pine `alert()` call.

TradingView sends the alert message as the POST body. When the body is valid JSON,
TradingView uses `application/json`. Aurex also accepts `X-Aurex-Webhook-Secret` for
controlled API clients, but the query secret is the TradingView-compatible path because
the alert UI is URL-and-body oriented. Do not put broker credentials, exchange API keys,
or account secrets in the alert body. Rotate `AUREX_WEBHOOK_SECRET` if the webhook URL
is exposed.

The alert payload includes `strategy_version` and `settings_fingerprint`. Aurex
compares those values with the accepted backtest's recorded strategy version and Pine
input snapshot before allowing paper execution. A signal that omits or mismatches this
provenance can still be stored and audited, but it is risk-rejected and creates no
paper trade.

## Backtest Notes

Before running or inspecting Strategy Tester results, freeze the intended symbol,
timeframe, dates, Pine inputs, costs, risk assumptions, acceptance rules, and
walk-forward folds with **Register protocol** in Aurex Backtest Evidence Intake. Use
**Plan folds** first to derive date-only anchored folds without reading outcomes, then
register before opening the results. Select **Verify manifest** and require `READY`
before opening TradingView. The manifest binds the exact Pine SHA-256, version, symbol,
timeframe, inputs, costs, slippage, dates, and protocol. Never replan folds after
seeing P/L. The resulting protocol is immutable and single-use. A report without a matched protocol is stored
only as rejected evidence and cannot unlock paper trading.

Use fixed settings during a test run. Any parameter change creates a new strategy run and must be recorded separately in Aurex.

The strategy declaration applies 0.05% commission and two ticks of slippage. The
`Backtest start` and `Backtest end` inputs enforce the recorded test window and block
new entries outside it.

Position quantity risks 0.5% of current strategy equity at the selected stop by
default. Risk is measured from the expected slipped entry and multiplied by
`syminfo.pointvalue`. Quantity is capped at 95% of current equity value and rounded
down to `syminfo.mincontract`, preventing precision and minimum-size order rejection.

Version `1.3.0` expands the optional **Aurex diagnostics** table in the chart's
top-right corner. The table does not loosen entries, exits, alerts, or evidence gates.
It counts how often each long/short setup filter passed inside the selected backtest
window and shows the latest blocker for each side:

```text
Flat position
Trend filter
Pullback zone
RSI reset
Confirmation
Risk > tick
Quantity > 0
Setups
Orders submitted
Filled entries
Open trades
Closed trades
Latest blocker
```

Use the diagnostic table before exporting if Strategy Tester reports no trades. If
`Setups` stays at `0`, the latest blocker and low pass-count rows show whether the
date window, trend filter, pullback zone, RSI reset, confirmation candle, stop/risk
geometry, or position quantity is preventing entries. If `Setups` is above `0` but
`Orders submitted` stays at `0`, the issue is setup gating. If orders are submitted but
`Filled entries` stays at `0`, the issue is order acceptance or symbol sizing, not
signal discovery. Do not loosen filters just to create trades; record the blocker
and test a deliberate strategy revision separately.

The entry order IDs are `AUREX-LONG-TRENDING_UP` and
`AUREX-SHORT-TRENDING_DOWN`. Keep those regime labels in the Strategy Tester export;
Aurex uses them as explicit regime evidence and does not infer a favorable regime from
trade direction alone.

Record:

```text
Symbol
Chart timeframe
Higher timeframe
Date range
Commission
Slippage assumption
EMA lengths
RSI length
ATR length
ATR multiplier
Reward:risk ratio
Stop mode
Risk per trade (%)
Max position value (%)
Long/short toggles
```

Export the Strategy Tester list of completed trades and follow
`docs/02_TRADINGVIEW_BACKTEST_IMPORT.md`. Load the file through **TradingView CSV
file** or paste it, then preflight before import. An Aurex
accepted result means only that the submitted historical evidence met the configured
floor; it is not a claim of future profitability.

Backtest acceptance also requires explicit anchored walk-forward train/test folds
inside the in-sample period. Each fold must use the same recorded parameter fingerprint
as the report. Aurex may show automatically partitioned trade slices for diagnosis, but
those slices are not independent walk-forward evidence and cannot unlock paper trading.

## Non-Repainting Controls

The script uses:

```text
barstate.isconfirmed
request.security(..., ta.ema(close, length)[1], lookahead = barmerge.lookahead_on)
calc_on_every_tick = false
process_orders_on_close = true
```

The `[1]` offset is required. `lookahead_on` without that offset is prohibited. The
script also raises a runtime error when the requested higher timeframe is not greater
than the chart timeframe. Entries are evaluated on confirmed chart bars only.
