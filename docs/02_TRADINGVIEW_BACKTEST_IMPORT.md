# TradingView Backtest Evidence Workflow

This workflow uses TradingView Strategy Tester as the strategy runner and Aurex as the
evidence ledger and independent acceptance gate. It does not prove that the strategy is
profitable, and it does not enable live trading.

The source reference must bind the TradingView venue, symbol, and timeframe. Use the
canonical form `tradingview://strategy-tester/<VENUE>:<SYMBOL>/<timeframe>`. An
unqualified symbol is rejected because it does not identify the candle feed.

## 1. Prepare Aurex

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload
```

Open `http://127.0.0.1:8000` and use **Backtest Evidence Intake**.

Preserve the matching TradingView chart export through **Historical data** with source
`tradingview-chart-export` and canonical reference
`tradingview://chart/<VENUE>:<SYMBOL>/<timeframe>`. This creates immutable input
evidence and a quality audit; see `docs/05_HISTORICAL_DATASETS.md`. It does not
replace the completed-trades export or count as a backtest. Authentic parity v1.1
blocks until this chart dataset exactly matches the Binance Vision reference by
timestamp and normalized OHLCV value.

## 1.1 Pre-Register The Test Protocol

Do this before opening Strategy Tester results or exporting any trades:

1. Select **Setup** to load the Aurex-owned strategy version and parameter contract.
2. Enter the intended data range, in-sample range, untouched OOS range, costs,
   slippage, risk assumptions, and acceptance criteria.
3. Select **Plan folds**. Aurex deterministically creates anchored folds from only the
   declared in-sample dates, fixed parameters, fold count, and training fraction. It
   reads no CSV, trades, P/L, win rate, drawdown, or other result field and writes
   nothing to the evidence ledger.
4. Review the date boundaries only. Never regenerate folds after seeing results to
   improve a score; a changed plan requires a new protocol and a genuinely new run.
5. Set a stable source reference for the planned TradingView run.
6. Select **Register protocol**.
7. Select **Verify manifest** and require `READY` before running TradingView.
8. Select **Prepare run** and require `READY`; copy Pine and setup from that package.
9. Record the protocol ID, protocol hash, manifest hash, package hash, and Pine source hash. The
   protocol is immutable and single-use.

Registration writes the frozen test design to `backtest_protocols` with a deterministic
SHA-256 hash and timestamp. Aurex returns an existing unconsumed record when the exact
same protocol is submitted twice, so an accidental double-click does not create a new
design. There is no update endpoint. Change the design by registering a new protocol,
then run a new test.

A report without a protocol, with changed settings, with a damaged protocol hash, or
with a protocol already consumed by another report may still be stored for audit, but
its acceptance is blocked and it cannot unlock paper or live readiness.

## 2. Run The Pine Strategy

1. Open TradingView and select the real symbol, exchange, and chart timeframe to test.
2. Paste `pine/strategies/trend_pullback_v1.pine` into Pine Editor.
3. Save it, add it to the chart, and confirm that it compiles as Pine v6.
4. Set the Pine **Backtest start** and **Backtest end** inputs before the run. The
   script applies 0.05% commission and two ticks of slippage in `strategy()`.
5. Keep the capital and all other settings fixed. Do not change parameters during one
   run.
6. Review the **Aurex diagnostics** table on the chart before exporting. If Strategy
   Tester has no completed trades, use the latest blocker and pass counts to determine
   whether the date window, trend, pullback, RSI, confirmation, risk, or quantity gate
   is preventing entries.
7. Record the symbol, exchange, timeframe, date range, Pine settings, commission,
   slippage assumption, and strategy version.
8. Export the Strategy Tester list of completed trades as CSV.

The Pine entry IDs include `TRENDING_UP` or `TRENDING_DOWN`. Aurex uses that explicit
text as regime evidence. An export from an older Pine version can still parse, but it
will fail the regime-coverage gate rather than inventing a regime.

The Pine alert payload also includes a `strategy_version` and `settings_fingerprint`.
After a backtest is accepted, Aurex compares incoming paper-trading signals against
that accepted backtest's version and recorded parameter fingerprint. Missing or
mismatched signal provenance blocks paper execution even if the price geometry and
risk rules are otherwise valid.

## 3. Preflight The Export

In the dashboard:

1. Enter the recorded strategy scope and sample windows.
2. Select the matching unconsumed protocol in **Backtest protocol**.
3. Set **CSV timezone** to the timezone used by the export timestamps. Use `UTC` when
   the export includes UTC timestamps.
4. Set **Source reference** to the exact value frozen in the protocol, such as
   `tradingview://strategy-tester/BINANCE:BTCUSDT/15m`.
5. Enter the exact parameter, commission, slippage, and risk assumptions frozen in the
   protocol.
6. Confirm **Walk-forward windows JSON** still matches the registered protocol. Each
   fold must have an expanding or rolling training period followed by a non-overlapping
   test period inside the declared in-sample range. The parameter snapshot must match
   the report, and `configuration_reference` must identify the recorded fold setup.
7. Choose the exported file in **TradingView CSV file**. Aurex loads its contents into
   the report field without changing the frozen source reference. Direct paste remains
   available when needed. The dashboard rejects empty files and files above 20 MiB.
8. Select **Preflight**.

Preflight does not write to the database. It auto-detects Aurex or TradingView format,
pairs TradingView entry and exit rows, normalizes the completed trades, computes both
an exact-source `source_artifact_hash` over the uploaded CSV bytes and a deterministic
normalized-trade evidence hash, and returns row-level outcomes plus acceptance reasons.
For known Pine strategies such as `trend_pullback_v1`, the accepted-evidence gate also
requires a complete strategy-parameter snapshot. A structurally valid CSV can therefore
preflight as `READY` for import while its acceptance remains blocked by
`Strategy parameters missing for trend_pullback_v1`. Importing that record preserves an
honest rejected backtest; it does not unlock paper or live readiness. The dashboard
Backtests panel shows **Parameter evidence** as `COMPLETE` or `MISSING`, and the
Deployment backtest row points to missing parameters when they are the active blocker.

Aurex no longer treats equal chronological slices of one report as walk-forward
validation. When no explicit folds are supplied, preflight still calculates those
slices as a stability diagnostic, but `walk_forward.acceptance_eligible` is `false` and
the acceptance gate remains blocked. Explicit folds are validated for chronology,
non-overlapping test periods, in-sample containment, inclusion of prior test periods in
the next training period, and an exact parameter fingerprint match. The final OOS range
remains outside these folds so it stays a separate holdout.

Example fold shape:

```json
[
  {
    "window_id": "wf-1",
    "train_start": "2026-01-01T00:00:00Z",
    "train_end": "2026-01-31T23:59:59Z",
    "test_start": "2026-02-01T00:00:00Z",
    "test_end": "2026-02-14T23:59:59Z",
    "configuration_reference": "tradingview://BINANCE/BTCUSDT/15m/wf-1",
    "parameters": {
      "initial_capital": "1000",
      "reward_risk": "2.0"
    }
  }
]
```

For a known Pine strategy, `parameters` must contain the full setup contract returned
by `GET /backtests/strategy-setup`, not only the abbreviated fields shown above.

If the TradingView export has headers but no completed trade rows, preflight returns a
structured `REJECTED` response instead of importing or mutating the ledger. The
`analysis_summary.diagnostic.status` will be `NO_COMPLETED_TRADE_ROWS`, with a next
action to confirm that the Pine strategy creates closed trades in Strategy Tester,
extend the chart/date range if needed, and export the List of Trades. If the export
contains entries without completed exits, the diagnostic status becomes
`ENTRY_ROWS_WITHOUT_COMPLETED_EXITS`. Both cases keep import blocked until completed
trade evidence exists.

If preflight is `REJECTED`, correct the export or metadata. Do not import a partial or
malformed file. A valid small sample may be structurally `READY` while its analysis is
still rejected by the evidence gates; importing it preserves that honest rejected run.

## 4. Import And Inspect

Select **Import** only after structural preflight is `READY`. Aurex persists:

- the report scope, settings, cost/slippage/risk assumptions, and acceptance criteria;
- the SHA-256 fingerprint of the exact CSV text received by Aurex;
- every normalized completed trade and its original source rows;
- fee and slippage values when present, or explicit missing values when absent;
- the evidence hash, metrics, out-of-sample analysis, distribution, regimes, and gate
  reasons.
- the explicit walk-forward definitions, per-fold metrics, test-trade hashes, and a
  deterministic walk-forward evidence hash.

Use these endpoints to inspect the persisted evidence:

```text
GET /backtests/reports
GET /backtests/reports/{run_id}
GET /backtests/reports/{run_id}/trades?limit=5000
```

The paper and live-readiness gates recompute the normalized-trade hash from the
persisted trade ledger and require the source-artifact fingerprint. A missing or
invalid artifact fingerprint, missing ledger, count mismatch, modified trade, missing
protocol, protocol hash mismatch, or protocol/report mismatch blocks promotion.

For registered Aurex Pine strategies, statistical acceptance and promotion eligibility
are deliberately separate. A report can have `acceptance_passed=true` and still be
blocked from signals, paper, and live progression unless it came through the
TradingView CSV importer with `data_source=tradingview-export`, a
`tradingview://strategy-tester/` reference, complete trade fields, and the exact Pine
commission/slippage contract. Inspect the current result through:

```text
GET /backtests/paper-eligibility?strategy=trend_pullback_v1&symbol=BTCUSDT
```

The artifact hash binds the evidence to an operator-supplied file; it does not prove
that TradingView cryptographically signed or attested the file. Keep the original CSV
so its hash can be independently checked later.

## API Example

Set the dates and JSON assumptions to the values actually used in TradingView:

```powershell
$requestParameters = @{
  initial_capital = "1000"
  backtest_start = "2026-01-01T00:00:00Z"
  backtest_end = "2026-05-31T23:59:59Z"
  higher_timeframe = "60"
  pullback_ema_fast = 20
  pullback_ema_slow = 50
  trend_ema = 200
  htf_ema_fast = 50
  htf_ema_slow = 200
  rsi_length = 14
  atr_length = 14
  atr_multiplier = "1.5"
  reward_risk = "2.0"
  swing_lookback = 5
  pullback_atr_tolerance = "0.25"
  stop_mode = "Wider"
  risk_per_trade_percent = "0.5"
  max_position_value_percent = "95.0"
  enable_long = $true
  enable_short = $true
}
$windowPlanRequest = @{
  strategy = "trend_pullback_v1"
  in_sample_start = "2026-01-01T00:00:00Z"
  in_sample_end = "2026-03-31T23:59:59Z"
  parameters = $requestParameters
  window_count = 3
  initial_training_fraction = "0.333333"
}
$windowPlan = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/backtests/window-plan" `
  -ContentType "application/json" `
  -Body ($windowPlanRequest | ConvertTo-Json -Depth 10)

$protocolRequest = @{
  strategy = "trend_pullback_v1"
  strategy_version = "1.3.0"
  symbols = @("BTCUSDT")
  timeframe = "15m"
  data_source = "tradingview-export"
  csv_timezone = "UTC"
  source_reference = "tradingview://strategy-tester/BINANCE:BTCUSDT/15m"
  data_start = "2026-01-01T00:00:00Z"
  data_end = "2026-05-31T23:59:59Z"
  in_sample_start = "2026-01-01T00:00:00Z"
  in_sample_end = "2026-03-31T23:59:59Z"
  out_of_sample_start = "2026-04-01T00:00:00Z"
  out_of_sample_end = "2026-05-31T23:59:59Z"
  parameters = $requestParameters
  cost_model = @{ commission_percent = "0.05" }
  slippage_model = @{ type = "fixed_ticks"; ticks = "2" }
  risk_snapshot = @{ risk_per_trade = "0.005" }
  walk_forward_windows = $windowPlan.windows
  acceptance_criteria = @{
    min_trades = 100
    min_profit_factor = "1.15"
    max_drawdown = "50"
    min_out_of_sample_trades = 30
    min_out_of_sample_profit_factor = "1.15"
    min_active_trading_days = 15
    max_single_day_trade_share = "0.25"
  }
}
$protocolBody = $protocolRequest | ConvertTo-Json -Depth 10
$protocol = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/backtests/protocols" `
  -ContentType "application/json" `
  -Body $protocolBody

# Run TradingView only after the protocol above is registered. Then export the CSV.
[string]$csv = Get-Content -Raw "C:\path\to\tradingview-completed-trades.csv"
$request = $protocolRequest.Clone()
$request["protocol_id"] = $protocol.id
$request["csv_format"] = "auto"
$request["csv_text"] = $csv
$body = $request | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/backtests/reports/preflight-csv" `
  -ContentType "application/json" `
  -Body $body

$report = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/backtests/reports/import-csv" `
  -ContentType "application/json" `
  -Body $body

Invoke-RestMethod -Method Get `
  -Uri "http://127.0.0.1:8000/backtests/reports/$($report.id)/trades?limit=5000"
```

An honestly rejected run remains persisted with output shaped like:

```json
{
  "source_format": "tradingview",
  "source_artifact_hash": "<sha256-of-exact-uploaded-csv>",
  "evidence_hash": "<sha256>",
  "result": {
    "total_trades": 1,
    "acceptance_passed": false,
    "acceptance_reasons": [
      "Total trades 1 below minimum 100",
      "Out-of-sample trades 0 below minimum 30",
      "Active trading days 1 below minimum 15"
    ]
  }
}
```

The exact reasons depend on the submitted evidence and criteria.

## Honest Limitations

- TradingView exports are operator-supplied and are not cryptographically signed by
  TradingView. Aurex can bind the exact bytes received, validate their structure, and
  audit the normalized ledger, but it cannot prove that a human did not fabricate or
  edit a CSV before import.
- Backtests imported before migration `20260718_0025` have no source-artifact hash and
  are intentionally promotion-blocked. Re-register the frozen protocol and re-import
  the retained original CSV. Do not populate hashes manually or manufacture a
  replacement file from stored normalized trades.

- Aurex has a no-write, comparison-only candle replay for `trend_pullback_v1`.
  Authentic trade parity requires separately immutable Binance Vision and TradingView
  chart datasets with exact candle parity. TradingView's completed-trade output
  remains authoritative until both candle and trade-level parity pass. The replay
  cannot satisfy acceptance or unlock paper execution.
- TradingView changes export headers across views and locales. The importer accepts
  common English semantic variants; an unknown localized export is rejected clearly
  and needs a tested header adapter.
- Reported net P/L is stored as TradingView reported it. Fees are recorded separately
  and are not subtracted a second time.
- Missing per-trade fees or slippage remain `null`; Aurex does not silently turn them
  into zero. Declared report-level cost and slippage models are still required.
- Out-of-sample status is derived from the submitted OOS date window. The operator must
  choose that split before evaluating the run.
- Aurex's current explicit walk-forward method evaluates predeclared fixed parameters
  across anchored train/test folds. It is not automated parameter optimization. Any
  future optimization workflow must preserve each fold's search space, selected
  parameters, and untouched test export separately.
- Passing the gates means the supplied historical evidence met the configured floor. It
  does not establish future reliability, remove overfitting risk, or authorize money.
- Pine alerts, paper execution, and live deployment are separate milestones. Live mode
  remains disabled.
