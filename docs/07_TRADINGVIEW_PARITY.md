# Aurex TradingView Trade-Level Parity

## Purpose

The parity harness measures whether Aurex's deterministic `trend_pullback_v1` replay
produces the same completed trades as one imported TradingView strategy report when
both are bound to the same symbol, timeframe, strategy version, parameters, costs,
slippage, Binance Vision reference dataset, and TradingView chart-export dataset.

Parity is not profitability evidence. Every parity response remains
`comparison_only=true` and `acceptance_eligible=false`. It does not create or modify a
backtest run and cannot unlock paper or live execution.

## Evidence Sources

One comparison binds:

- one immutable `backtest_datasets` record and its evidence hash;
- one separately imported immutable `tradingview-chart-export` dataset from
  `tradingview://chart/BINANCE:BTCUSDT/15m`;
- one persisted TradingView `backtest_runs` record and completed-trade evidence hash;
- the exact single-use frozen protocol consumed by that report;
- one reviewed paired-export manifest that binds the frozen run, chart dataset,
  original report bytes, and an exact operator attestation;
- reference replay engine `trend-pullback-reference-v1.1.0`;
- parity engine `tradingview-trade-parity-v1.2.0`;
- tick size, point value, minimum contract, and bounded declared tolerances;
- the TradingView run's parameter, commission, and fixed-tick slippage snapshots.

The harness blocks before comparison when the report did not consume an intact frozen
protocol, the reviewed paired-export hash is absent or stale, either dataset hash
fails audit, the reference dataset is not checksum-verified Binance Vision, the chart
dataset is not a venue-qualified TradingView export, report provenance is incomplete,
metadata differs, the replay is unsupported, costs are malformed, or required trade
fields are missing. Required trade fields are direction, entry and exit time, entry
and exit price, quantity, and fees. Net P/L is always required by the TradingView
report importer.

## Paired-Export Lineage

Exact candles cannot prove that the Strategy Tester report was exported with the same
Pine inputs and Strategy Properties. Aurex therefore requires a no-write paired-export
manifest after both files have been imported. It binds:

- the stable frozen protocol, manifest, run-package, Pine, and settings hashes;
- the verified Binance Vision reference dataset;
- the TradingView chart dataset evidence and canonical candle CSV hashes;
- the report trade evidence hash and SHA-256 of the original submitted CSV bytes;
- ticker, timeframe, source references, and complete coverage;
- an exact timestamped operator statement that both exports came from one unchanged
  frozen run.

The statement is an attestation, not a TradingView signature. Aurex can prove that the
reviewed hashes are unchanged after import; it cannot independently observe or prove
the operator's TradingView tab state.

## Market-Data Rules

Before any trade is compared, v1.2 aligns the two complete candle datasets by
timestamp and requires:

- identical first and last timestamps;
- identical row counts and timestamp sets;
- exact normalized decimal equality for open, high, low, close, and volume;
- source `binance-vision` with verified source artifacts for the reference dataset;
- source `tradingview-chart-export` and exact reference
  `tradingview://chart/BINANCE:BTCUSDT/15m` for the chart dataset;
- exact report reference
  `tradingview://strategy-tester/BINANCE:BTCUSDT/15m`;
- a valid SHA-256 for the original TradingView completed-trades CSV.

A structurally valid candle mismatch is immutable `FAILED` evidence. Every mismatch
is preserved with timestamp, both candle snapshots, and field-level reasons; trade
comparison is not run because any apparent trade agreement or disagreement would be
confounded by different inputs. Missing, unauditable, or wrong-source chart evidence
is `BLOCKED` and cannot be recorded.

## Comparison Rules

Trades are ordered chronologically. Entry time aligns the two sequences within the
declared tolerance. This prevents one missing trade from shifting every later pair.
Each aligned pair compares:

- direction;
- entry time and close time;
- entry and exit price in tick-size units;
- relative quantity difference;
- absolute fee difference;
- absolute net P/L difference;
- exit cause inferred from the TradingView fill versus the replay bracket.

Unaligned records are explicitly reported as `REFERENCE_ONLY` or `REPLAY_ONLY`.
`PASSED` requires every trade to align and every compared field to pass. A structurally
valid disagreement is `FAILED`, not blocked, and may be recorded as useful negative
evidence. Incomplete or unauditable inputs are `BLOCKED` and cannot be recorded.

## API

No-write comparison:

```text
POST /backtests/parity/export-manifest/preflight
POST /backtests/parity/preflight
```

Immutable evidence recording:

```text
POST /backtests/parity/runs
GET  /backtests/parity/runs
GET  /backtests/parity/runs/{id}
GET  /backtests/parity/runs/{id}/audit
```

Example request:

```json
{
  "dataset_id": "immutable-dataset-uuid",
  "tradingview_chart_dataset_id": "tradingview-chart-dataset-uuid",
  "tradingview_run_id": "imported-report-uuid",
  "export_attestation": {
    "statement": "I attest that the selected TradingView chart CSV and Strategy Tester CSV were exported from the same run without changing the Pine source, inputs, Strategy Properties, symbol, timeframe, date range, costs, or order settings.",
    "attested_at": "2026-07-29T16:30:00Z"
  },
  "reviewed_export_manifest_hash": "64-character-hash-returned-by-export-manifest-preflight",
  "tick_size": "0.01",
  "point_value": "1",
  "minimum_contract": "0.001",
  "tolerances": {
    "entry_time_seconds": 0,
    "exit_time_seconds": 0,
    "price_ticks": 1,
    "quantity_relative": "0.000001",
    "money_absolute": "0.01"
  }
}
```

Recording is idempotent by the parity evidence hash. No update endpoint exists. The
audit independently re-hashes the stored record and reruns the comparison against the
current source ledgers, detecting record, source, or engine-result drift.

## Honest Boundary

A synthetic or hand-constructed TradingView run or chart dataset can test software
behavior but cannot prove Pine parity. Operational evidence requires an original
Strategy Tester completed-trades export and matching chart OHLCV export from the same
unchanged chart state, an exact frozen protocol binding, and a reviewed paired-export
manifest. A pass only supports the exact two datasets, run, engine versions, lineage
manifest, and tolerances. It does not establish future edge, execution quality, or
live profitability.
