# Frozen TradingView Run Contract

Date: 2026-07-18
Current strategy: `trend_pullback_v1` v1.3.0

## Current Registered Run

The original protocol omitted the TradingView venue from its source reference. That is
a genuine setup defect because `BTCUSDT` alone does not identify the candle feed. It
remains immutable and unconsumed, but current manifest policy blocks it. The corrected
protocol below replaces it for the external run without deleting historical evidence.

```text
Protocol ID:       288ea36e-abbf-4c1a-b15e-85ef5b097a93
Protocol hash:     3a5345306896b4f57005e61f6891ebb788b071901c71f16767a290aecb7bc160
Manifest hash:     ed328491d093995d772d2bef95fc61177579676f8e785b7e57485f6ffbdfc227
Run package hash:  b1bdf4e6181e6a5ea8f4a2547f41775d2d210aea7393fee80c5db3929ced25e6
Pine SHA-256:      9e68cf52c1072d0efbb4b588d96474439d8283c4ee08c62fd8c700e4870596f7
TradingView ID:    BINANCE:BTCUSDT
Source reference:  tradingview://strategy-tester/BINANCE:BTCUSDT/15m
Manifest:          READY (13/13 checks passed)
Run package:       READY (19,277 bytes / 297 lines)
```

The manifest and package hashes above use the stable v2 hash scope introduced on
2026-07-29. The earlier values were prospectively superseded because they included
protocol consumption state and transient readiness reasons. No protocol field, Pine
byte, setting, cost, date, symbol, timeframe, or source reference changed. The
protocol and Pine hashes therefore remain unchanged.

This protocol is registered and unconsumed. Do not register a replacement merely
because results are weak. Replace it only when a genuine setup error is found and
document why the original protocol was not consumed.

## Aurex Real-Data Reference Evidence

The frozen settings have been replayed against verified official Binance spot kline
archives. December 2025 is included only for indicator warm-up; the trade window
remains `2026-01-01T00:00:00Z` through `2026-03-31T00:00:00Z`.

```text
Dataset ID:           d81be313-ac03-4012-b9c2-0668e70e4b1e
Dataset rows:         11,521 continuous 15-minute candles
Dataset coverage:     2025-12-01T00:00:00Z to 2026-03-31T00:00:00Z
Dataset evidence:     a6f3ba5025043f801302d67ad3686d002a9cd71fd62ae23821e772ba35ed520f
Canonical CSV SHA:    78256b4abc20f6ed5bff4f3cb25f85bc2f6898554f83d968d499e2045cb46f46
Artifact bundle hash: 8e17fd850b4e13c5fb817db7dcdf6ded0b9880e322d93fe36646fb7f0fc9314b
Source verification:  4/4 monthly ZIP archives match official CHECKSUM files

Replay run ID:        a0780214-6e6a-4e89-92e0-6e0c8e64e0a3
Replay engine:        trend-pullback-reference-v1.1.0
Engine evidence:      aef3ef39afc5a170e0e7dffb6b67b40bbc3ed19bb035fa7e8f911d371774c42a
Record evidence:      d5cf749742e8407e589f47206630534157a3a5c55e234344467cbe29aff6de90
Integrity audit:      PASS
```

The result is negative:

```text
Completed trades: 165
Wins / losses:    60 / 105
Net P/L:          -56.26266144456834359502881484
Profit factor:    0.8873119185405395227734327481
Expectancy:       -0.340985826936777839969871606 per trade
Max drawdown:     105.2860460418374101497583642
```

This is comparison-only evidence and is not eligible for acceptance, paper trading,
or live trading. It currently rejects the profitability hypothesis for this engine,
dataset, period, and cost model. TradingView remains authoritative until its authentic
completed-trades export is imported and trade-level parity is measured. The declared
`0.001` minimum contract must also be checked against TradingView's
`syminfo.mincontract`; Aurex has not treated it as verified exchange metadata.

## Frozen Validation Evidence

The recorded replay was evaluated against the frozen protocol without consuming it or
creating a trusted TradingView backtest:

```text
Validation ID:        4e580237-2abe-4c56-99fb-94e780c1f992
Validation status:    REJECTED
Evaluator:            reference-replay-validation-v1.0.0
Validation evidence:  74ecb1b8562bfb12cf0e5456951b73f4c0d344224709951c09af0a9ac92b0378
Trade evidence:       2c39486af924ded394c24cb7d99a1df69ddcba6196d7420d007b8a30a8650ce7
Binding checks:       13/13 PASS
Integrity audit:      PASS
Protocol state:       REGISTERED and unconsumed
```

The chronological split assigns all 165 trades: 85 in sample and 80 out of sample.
The 24-hour purge gap contains no trades. Out-of-sample evidence is materially worse:

```text
OOS wins / losses:    25 / 55
OOS net P/L:          -77.40020859563734909558749818
OOS profit factor:    0.7166499314333067526012171848
OOS expectancy:       -0.967502607445466863694843726 per trade
OOS max drawdown:     102.2251531481178226286323497
```

All three frozen fixed-parameter walk-forward folds pass inside the in-sample period.
That result does not override the later OOS collapse. Distribution checks cover 68
active trading days with a maximum single-day trade share of `3.64%`, so the failure
is not explained by one concentrated trading day. Regime results identify a concrete
weakness: the strategy is approximately flat in `TRENDING_DOWN` with profit factor
`1.0400`, but loses heavily in `TRENDING_UP` with profit factor `0.6811`.

The validation fails five frozen gates: overall profit factor, overall expectancy,
maximum drawdown, OOS expectancy, and OOS profit factor. This is evidence of temporal
decay and regime weakness. It is not permission to lower thresholds or tune against
the held-out period.

## Purpose

The run manifest is the last code-side check before an external TradingView run. It
prevents a report from being promoted when the operator ran different Pine bytes,
version, symbol, timeframe, settings, dates, costs, or slippage than Aurex registered.

The manifest is no-write and does not prove that TradingView executed the strategy.
It proves that Aurex has one internally consistent frozen run specification.

## Operator Sequence

1. Open **Backtests** and select **Setup**.
2. Set one symbol, one chart timeframe, all Pine inputs, dates, costs, slippage, risk,
   acceptance criteria, and explicit walk-forward folds.
3. Select **Register protocol**.
4. Select **Verify manifest**. Do not open Strategy Tester unless the state is `READY`.
5. Record the displayed protocol, manifest, package, and Pine source hashes.
6. Select **Prepare run**, then use **Copy Pine** and **Copy setup**. Do not copy from
   an editor, documentation page, or superseded protocol.
7. Open the package URL and verify the chart header says `BINANCE:BTCUSDT` and `15m`.
8. Paste the packaged Pine source into TradingView and use the manifest values.
9. Confirm the diagnostics table reports setup counts, submitted orders, filled
   entries, and closed trades.
10. Export **Strategy Tester completed trades** without changing the chart or inputs.
11. From that same unchanged chart state, export the complete matching chart OHLCV
    window, including warm-up history. Preserve both original files.
12. Import the chart CSV as source `tradingview-chart-export` with reference
    `tradingview://chart/BINANCE:BTCUSDT/15m`. Its timestamps and every normalized
    OHLCV value must match the immutable Binance Vision reference before trade
    comparison can run.
13. Select the same unconsumed protocol, load the original completed-trades CSV, and
    run **Preflight**.
14. Import only when preflight is structurally ready. Select both immutable datasets
    and the imported report in **TradingView parity**.
15. Confirm the paired-export attestation, then select **Prepare lineage**. Review the
    resulting hash. Any evidence-selection change invalidates it.
16. Select **Compare trades** only when export lineage is `READY`. Aurex still treats
    parity as comparison-only and cannot promote rejected v1.3.

## API

```text
GET /backtests/protocols/{protocol_id}/run-manifest
GET /backtests/protocols/{protocol_id}/tradingview-run-package
POST /backtests/parity/export-manifest/preflight
```

A `READY` response requires:

- intact protocol hash and unconsumed protocol;
- exactly one TradingView symbol;
- TradingView data source and a venue-qualified strategy-tester reference whose
  symbol and timeframe match the protocol;
- Pine version equal to the registry and declared protocol version;
- recorded Pine SHA-256 equal to the current repository source;
- complete parameter fingerprint;
- exact registry commission and slippage models;
- a higher timeframe greater than the chart timeframe.

Any failed check returns `BLOCKED` with stable reason codes. Correct recovery is to fix
the setup and register a new protocol. Historical protocols and reports are immutable.

The run-package endpoint is also no-write. It returns the exact UTF-8 Pine source,
source byte and line counts, qualified TradingView URL, frozen setup, and an independent
package hash. A package is `READY` only when its manifest is ready and a second source
read still matches the registered Pine SHA-256.

## Evidence Boundary

The stable v2 manifest hash covers protocol identity, current source evidence,
settings, and TradingView setup. The package hash additionally covers Pine byte and
line counts. Consumption status, readiness checks, and reasons remain visible but are
outside these configuration hashes, allowing the exact frozen configuration to be
re-derived after the single-use protocol is consumed. The imported report separately
stores the SHA-256 of the exact operator-supplied CSV and the normalized
completed-trade ledger.

Neither hash is a TradingView signature. A human can edit an export before Aurex sees
it. Retain the original file, preserve its filesystem metadata when possible, and use
trade-level parity as additional comparison evidence. Profitability remains unproven
until authentic out-of-sample and forward paper evidence pass their independent gates.

The Binance Vision dataset proves source provenance and deterministic Aurex replay. It
does not prove that TradingView's chart candles are equal. Parity engine v1.2 requires
a separately immutable matching TradingView chart export, exact timestamp/OHLCV
reconciliation, a protocol-bound report, and a reviewed paired-export lineage manifest
before interpreting trade mismatches as strategy-engine errors.

Superseded protocol `170470b2-9238-435e-9b91-5aae806b5f52` remains `REGISTERED` and
unconsumed. Under the venue-qualified policy its current manifest is `BLOCKED` because
`tradingview://strategy-tester/BTCUSDT/15m` does not bind an exchange. Its earlier
validation remains valid historical comparison evidence, but it is not the external
run contract.
