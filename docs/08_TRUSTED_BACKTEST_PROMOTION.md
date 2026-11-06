# Core Pine Backtest Promotion Policy

Date: 2026-07-18
Policy: `core_pine_tradingview_export_v2`

## Purpose

Aurex separates two decisions that must not be conflated:

1. **Metrics acceptance** asks whether the supplied trades pass the declared
   statistical, cost, drawdown, OOS, walk-forward, regime, and concentration tests.
2. **Promotion eligibility** asks whether an accepted result has enough provenance and
   integrity to unlock known Pine signals and paper trading.

Raw JSON remains useful for research calculations, fixtures, and negative evidence. It
cannot claim `source_format=tradingview` through `POST /backtests/reports` and cannot
promote a registered Pine strategy.

## Required Promotion Evidence

For a strategy in the Aurex registry, the selected report must satisfy every existing
accepted-backtest gate plus all of the following:

- imported through `POST /backtests/reports/import-csv` as TradingView format;
- `source_format=tradingview`;
- `data_source=tradingview-export`;
- source reference beginning `tradingview://strategy-tester/`;
- a persisted SHA-256 `source_artifact_hash` of the exact uploaded CSV text;
- every persisted trade marked with TradingView source format;
- complete trade ID, direction, entry/exit time, entry/exit price, quantity, and fee;
- the strategy registry's exact commission and slippage model;
- the registry's current strategy version;
- the exact Pine source SHA-256 recorded inside the immutable protocol;
- a current Pine source whose embedded version matches the registry and protocol;
- an immutable pre-registered protocol and intact normalized-trade evidence hash.

The shared policy is evaluated by `aurex.backtest_engine.eligibility`. Signal/risk paper
eligibility and live accepted-backtest readiness consume the same source policy so one
surface cannot quietly advance evidence that another rejects.

## Operator Surfaces

```text
GET /backtests/paper-eligibility?strategy=trend_pullback_v1&symbol=BTCUSDT
GET /backtests/protocols/{protocol_id}/run-manifest
GET /signals/contract?strategy=trend_pullback_v1&symbol=BTCUSDT
GET /live/deployment
```

The Backtest Lab displays metrics state separately from promotion state:

- `METRICS BLOCKED`
- `METRICS ACCEPTED`
- `PROMOTION BLOCKED`
- `PAPER ELIGIBLE`

`source_evidence` includes the policy, exact artifact hash, recorded/current Pine
hashes, expected/current versions, field counts, execution assumptions, reasons, and
the source-contract result.

## Honest Trust Boundary

`trusted=true` means the Aurex promotion source contract passed. It does **not** mean
TradingView attested the export. TradingView CSV files are operator-supplied and can be
edited before upload. Aurex preserves a hash of exactly what it received and the
original parsed rows, but the original external file must be retained for independent
hash verification.

Reports created before migration `20260718_0025` have no artifact fingerprint and are
blocked. The correct recovery is a new frozen protocol plus re-import of the retained
original export, never a manually populated hash.

Protocols registered before source binding or against an older Pine version are also
blocked from promotion. Register a new protocol from the current setup and run the
current Pine source; never rewrite historical protocol snapshots.

Parity evidence remains comparison-only. A parity pass can strengthen confidence in
the reference replay but cannot replace the authoritative TradingView completed-trade
import or independently unlock paper/live progression.
