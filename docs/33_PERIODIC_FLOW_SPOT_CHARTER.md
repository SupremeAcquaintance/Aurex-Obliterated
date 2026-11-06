# Aurex Q1 Periodic-Flow Spot Charter

Status: `FROZEN_CHARTER_ONLY_NO_OUTCOMES`

This checkpoint freezes one falsifiable research direction. It is not a strategy,
backtest result, signal, paper-trading authorization, or claim of profitability.

## Decision

Mechanism ID:
`Q1-PERIODIC-PERPETUAL-ORDER-FLOW-SPOT-CONTINUATION`

Decision: `FREEZE_Q1_FOR_METADATA_AND_SCHEMA_FEASIBILITY_ONLY`

Next authorization: `AUTHORIZE_Q1_METADATA_ONLY_BTCUSDT_ARCHIVE_CENSUS`

The proposed actor is scheduled or algorithmic participation that concentrates
aggressive Binance USD-M BTCUSDT perpetual orders around UTC quarter-hour
boundaries. The ex ante hypothesis is deliberately one-sided: a positive,
causally completed perpetual order-flow imbalance may later qualify a BTCUSDT Spot
long; a negative reading means cash. It never means a futures order or short.

The rationale is externally motivated, not internally proven. Published research
documents recurring within-hour cryptocurrency activity, and a 2026 preprint
reports quarter-hour order-imbalance predictability in perpetual futures. Separate
peer-reviewed work warns that intraday momentum and reversal can change with
liquidity, jumps, macro events, and regimes. Aurex therefore freezes one sign and
requires independent after-cost falsification instead of selecting the sign after
seeing outcomes.

Sources:

- Binance Public Data: https://github.com/binance/binance-public-data
- Hansen, Kim, and Kimbrough (2024): https://doi.org/10.1093/jjfinec/nbac034
- Kim and Hansen (2026 preprint): https://arxiv.org/abs/2607.09426
- Wen, Bouri, Xu, and Zhao (2022):
  https://doi.org/10.1016/j.najef.2022.101733

Each source is recorded with `does_not_prove_edge=true`.

## Operator Boundary

- Execution venue and product: Binance Spot Testnet, Spot only.
- Execution symbol: `BTCUSDT`.
- Signal market for later research: Binance USD-M perpetual `BTCUSDT` archives.
- Direction: long or cash, no short.
- Maximum effective leverage: `1x`.
- Simulated equity: `$100`.
- Protective limits: `$0.50` per trade, `$1.00` per day, `$10.00` total.
- Paid-data budget: `$0`.
- Production account, real capital, production, and live authority: `false`.

Perpetual data may be studied as an explanatory input. Aurex is not authorized to
place a perpetual order, use margin, borrow, short, or assume liquidation risk.

## Sealed Partitions

| Role | Period | State |
| --- | --- | --- |
| Development | 2020-01-01 to 2024-01-01 | Closed pending separate protocols |
| Validation | 2024-01-01 to 2026-01-01 | Sealed |
| Washout | 2026-01-01 to 2026-08-07 | Excluded from selection and scoring |
| Holdout | 2026-08-07 to 2026-11-07 | Sealed future |
| Forward | 2026-11-07 onward | Locked |

All partitions have `outcome_access_permitted=false`. A later protocol must freeze
one observation duration, imbalance normalization, positive threshold, and holding
horizon before development outcomes are opened. The charter itself defines none.

## Preserved History

The charter binds 11 predecessor artifacts, including the universal strategy
factory contract, readiness v3, sandbox profile, Jam failure, contamination ledger,
and V3 research lineage. It preserves
`STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION` rather than erasing or
retrying it. The related V3 proposal counts as one predecessor variant for future
multiplicity accounting.

## Frozen Evidence

- Charter: `data/evidence/periodic_flow_spot_charter_v1.json`
- Charter file SHA-256:
  `dd6baa815e3a0dab897d5b76ed26e748f1f8480125a32bcfe762851636833881`
- Charter evidence hash:
  `17e9a73193a0c159aa6d3a15fea2412285e3cd12a5a4e0e52e3e27bcf4fa195b`
- Independent audit:
  `data/evidence/periodic_flow_spot_charter_audit_v1.json`
- Independent audit hash:
  `ad6a76574af1f3ff5dbf91f0ed42f6c1c066ff8746b7202bf0fc1c2e0373096a`

The audit reconstructs the charter exactly from source and predecessor evidence.
It records zero market values, returns, candidates, executions, and orders.

## Current Source Decision

The later paired payload and cross-source adjudication is recorded in
`docs/35_PERIODIC_FLOW_PAIRED_PAYLOAD_AND_SOURCE_ADJUDICATION.md`. Spot
`aggTrades` passed the 2020-01 structural pilot. USD-M `aggTrades` reproduced one
invalid duplicate raw-trade reference and is rejected for this research path.

The exact next gate is to freeze and independently check a checksum-only monthly
USD-M raw `trades` metadata-census protocol for `BTCUSDT`, `2020-01` through
`2025-12`. Do not request a checksum or ZIP payload before that protocol passes.
This source migration does not authorize parameter definition, backtesting, Pine,
paper operation, Testnet strategy orders, production, or live trading.

## Verification

- Charter direct reconstruction: PASS.
- Independent audit reconstruction: PASS.
- Focused unit tests: `7 passed`.
- Focused Ruff: PASS.
- Readiness/API/dashboard chain: `13 passed`.
- Complete Aurex suite: `1093 passed` in `776.30s`.
- Repository-wide Ruff: PASS.
- Current readiness v5 result hash:
  `4f01d4cb0cf6290591861ba9cae68c46cac7924ce8fef79f86ed9ce70299291c`.
- Current readiness v5 independent audit hash:
  `2782565d9c9d684b015986c6948c659dd6f8d42f3bd2652c752d89c46a4911f0`.
