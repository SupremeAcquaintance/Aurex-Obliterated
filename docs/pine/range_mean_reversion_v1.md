# Aurex range_mean_reversion_v1

Status: exploratory/unvalidated; disabled by default; no eligibility evidence

This Pine Script strategy looks for rejection candles at range extremes and targets the range midpoint.

Best regime:

```text
RANGING
```

Core logic:

```text
ADX on the current and higher timeframe must stay below the configured threshold.
Long setups require a rejection below the range low and close back inside the range.
Short setups require a rejection above the range high and close back inside the range.
Stop loss sits outside the rejected range extreme with ATR padding.
Take profit targets the range midpoint, capped by the configured reward:risk.
```

Webhook contract:

```text
strategy: range_mean_reversion_v1
market_regime: RANGING
```

Required external verification:

```text
Paste into TradingView Pine Editor.
Compile successfully.
Run Strategy Tester on the selected symbols/timeframes.
Export or record backtest settings.
Send a webhook to Aurex and confirm POST /webhooks/tradingview accepts it.
```

This strategy must not be enabled for live trading until the Aurex backtest and paper-trading gates pass.
