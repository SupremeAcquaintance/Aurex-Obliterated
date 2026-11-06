# Aurex Immutable Historical Datasets

Historical OHLCV data is input evidence, not a backtest result. Importing a dataset
does not prove a strategy, satisfy an accepted-backtest gate, allow paper execution, or
enable live trading.

## Operator Workflow

Use **Backtests > Historical data**:

1. Export timestamp, open, high, low, close, and volume rows from the intended source.
2. Set the strategy symbol and timeframe in the Strategy report fields. Historical
   data uses that same symbol and timeframe.
3. Record the dataset source, stable source reference, and CSV timezone.
4. Select **Continuous 24/7** for uninterrupted markets such as crypto. Select
   **24/7 with documented outages** only when every observed gap is an exchange
   incident with an exact missing-window declaration and a stable source reference.
   Select **Session based** only when scheduled exchange closures create larger gaps.
5. Choose the OHLCV CSV file and select **Data preflight**.
6. Inspect rejected rows, missing intervals, coverage, and the dataset hash.
7. Select **Import data** only when preflight is `READY`.

The dashboard rejects empty files and files above 50 MiB. Larger datasets should use
the API after reviewing server request-size and storage limits.

## Evidence Rules

Preflight is no-write. It:

- accepts common case-insensitive timestamp/time and OHLCV header variants;
- applies the declared timezone to naive timestamps and normalizes all times to UTC;
- requires finite, positive OHLC prices and non-negative volume;
- requires high to be at least every OHLC value and low to be no greater than them;
- rejects duplicate timestamps and mixed timestamp order;
- accepts descending exports but canonicalizes them to ascending order;
- rejects timestamps that do not align to the declared interval;
- rejects missing intervals for continuous 24/7 datasets;
- accepts a 24/7 outage only when every observed missing window exactly matches one
  declared outage and every declaration matches an observed gap;
- rejects undocumented, partially matched, duplicate, timezone-naive, and extraneous
  outage declarations;
- records session-based gaps as explicit warnings requiring calendar review;
- warns when fewer than 200 candles are available for indicator warm-up.

An accepted dataset receives a deterministic SHA-256 evidence hash over its normalized
symbol, timeframe, provenance, timezone, continuity policy, documented outage
evidence, timestamps, and exact decimal OHLCV strings. Changing an outage window,
reason, citation, or title therefore changes the dataset evidence identity. Re-importing
the same evidence returns the existing dataset. There is no update endpoint.

The integrity endpoint recomputes the hash and row count from the persisted candle
ledger. Direct database modification therefore changes the audit to `BLOCKED`.

## API

```text
POST /backtests/ohlcv/preflight-csv
POST /backtests/ohlcv/import-csv
GET  /backtests/ohlcv/datasets
GET  /backtests/ohlcv/datasets/{dataset_id}
GET  /backtests/ohlcv/datasets/{dataset_id}/audit
```

Example:

```powershell
$csv = Get-Content -Raw "C:\path\to\BTCUSDT-15m.csv"
$request = @{
  symbol = "BTCUSDT"
  timeframe = "15m"
  source = "tradingview-chart-export"
  source_reference = "tradingview://chart/BINANCE/BTCUSDT/15m/2026-Q1"
  csv_timezone = "UTC"
  continuity = "continuous_24_7"
  csv_text = $csv
}
$body = $request | ConvertTo-Json -Depth 5

$preflight = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/backtests/ohlcv/preflight-csv" `
  -ContentType "application/json" `
  -Body $body

if ($preflight.status -eq "READY") {
  $dataset = Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/backtests/ohlcv/import-csv" `
    -ContentType "application/json" `
    -Body $body
}
```

For a checksum-verified Binance Vision dataset with a documented exchange outage:

```powershell
.\.venv\Scripts\python.exe scripts\submit_ohlcv_dataset.py `
  --api-url http://127.0.0.1:8000 `
  --csv C:\path\to\BTCUSDT-15m.csv `
  --manifest C:\path\to\BTCUSDT-15m.manifest.json `
  --continuity continuous_24_7_with_documented_outages `
  --documented-gaps-json C:\path\to\documented-gaps.json `
  --import-dataset
```

The documented-gaps file is a JSON array. `start` is the first expected candle that
is absent and `end` is the next observed candle timestamp, making the interval
half-open (`start <= missing candle < end`):

```json
[
  {
    "start": "2023-03-24T12:45:00Z",
    "end": "2023-03-24T14:00:00Z",
    "reason": "Exchange-wide spot trading outage.",
    "source_reference": "https://example.com/stable-incident-reference",
    "source_title": "Exchange incident report"
  }
]
```

## Current Boundary

Aurex now preserves historical input evidence and can run a no-write, comparison-only
`trend_pullback_v1` reference replay against one immutable dataset. See
`docs/06_REFERENCE_REPLAY.md`. The replay cannot become acceptance evidence until its
trades are parity-tested against TradingView. Dataset quality and local calculations
cannot prove Pine parity or future profitability.
