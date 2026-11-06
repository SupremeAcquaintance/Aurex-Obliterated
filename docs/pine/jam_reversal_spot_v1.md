# Jam Reversal Spot V1

Status: `v1.0.1 REJECTED / DISABLED`

`jam_reversal_spot_v1` is the long-only, BTCUSDT 15-minute spot descendant of
`jam_reversal_v1` v1.14.0. It was created before opening the 2023-2025 decision
period so Aurex could test the Jam mechanism under the actual Binance Spot Testnet
execution boundary.

## Frozen Differences

- long-only; no short execution path;
- `BTCUSDT` `15m` only;
- `$100` initial capital and `1x` maximum leverage;
- `0.10%` commission per side;
- previous confirmed one-hour EMA values via `[1]` and `lookahead_on`;
- parent v1.14.0 pattern, confirmation, risk, and exit settings otherwise retained.

Pine SHA-256:
`7aa2aaa04e17ccbad70adba9279b4e5eb3057393b5e74f0a7db4cc5dd39d7270`.

## Historical Result

The immutable 2023-02-01 through 2026-01-01 reference replay produced 14 trades,
`-$0.5371` net P/L, PF `0.8301`, negative expectancy, four OOS trades, OOS PF
`0.6771`, and zero of six passing walk-forward folds. Replay and validation audits
both pass.

The zero-cost path was positive, but realistic base fees exceeded gross profit.
This is not an eligible or paper-authorized strategy.

Full contract and decision:
`docs/21_JAM_REVERSAL_SPOT_PREREGISTRATION.md`.

The no-new-returns failure analysis is preserved at
`data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json`, evidence hash
`7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`.
It classifies this version as sample-insufficient, fee-fragile, and non-durable.
No retuning or execution authority was granted.
