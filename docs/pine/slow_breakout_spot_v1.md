# slow_breakout_spot_v1

Status: retired/rejected, disabled, held-out decision final.

Version: `1.0.0`

Pine SHA-256:
`2312c6ce75b79b691bfa3542e4d44221a917f2efdeb0853408d93b5e1a099f16`

## Hypothesis

A slower long-only channel breakout may capture persistent crypto spot trends with
substantially less turnover than Aurex's rejected 15-minute candidates. The candidate
uses no shorting, leverage, funding, borrow, volume expansion, or higher-timeframe
filter. This was a testable hypothesis, not a claim of edge.

The preregistered ETH/SOL campaign rejected version `1.0.0`. ETH failed the
walk-forward gate; SOL failed OOS expectancy, OOS profit factor, and walk-forward.
See `docs/15_SLOW_BREAKOUT_SPOT_PREREGISTRATION.md` for immutable result identifiers.

## Frozen Contract

- Native chart timeframe: `4h` only.
- Market assumption: Binance spot.
- Direction: long only.
- Entry: confirmed close above the highest high of the previous 55 bars.
- Exit: confirmed close below the lowest low of the previous 20 bars.
- Catastrophe stop: fixed at entry-signal close minus `3.0 * ATR(20)`.
- Profit target: none.
- Entry and market-exit slippage: two adverse ticks.
- Commission: `0.05%` per side.
- Initial capital: `$1,000` per symbol replay.
- Risk per trade: `0.25%` of current equity.
- Maximum position value: `50%` of current equity.
- Quantity: point-value-aware and rounded down to the symbol quantity step.
- Intrabar collision policy: stop first.
- Same-bar re-entry after any exit: prohibited.
- Backtest window: `2023-02-01T00:00:00Z` through
  `2026-07-01T00:00:00Z`.

The strategy emits entry alerts with `take_profit: null`. Aurex can preserve that
payload, but its current paper risk engine rejects missing take-profit values. This is
intentional: no synthetic target may be added merely to satisfy an execution schema.
Execution support for channel exits requires a separately designed and tested risk and
order-management contract after eligibility and parity.

## Evidence Boundary

The source contract and deterministic local fixtures pass. TradingView compilation and
trade-level Pine/local parity remain unproven because the TradingView workspace was not
mutated. A local held-out pass can advance only to explicit Pine compile/parity work.
It cannot unlock paper or live trading.

The complete preregistration, data lineage, gates, and authoritative protocol receipts
are in `docs/15_SLOW_BREAKOUT_SPOT_PREREGISTRATION.md`.
