# Jam Successor Development Feature Distribution

## Status

Complete and independently reconstructed on `2026-08-04`.

This stage calculated the frozen 17-feature measurement system on BTCUSDT
aggregate-trade data from January 2019 through December 2020 only. It did not open
2021 validation or 2022 holdout data. It defined no event, future label, return,
strategy, signal, candidate, order, or PnL field.

## Frozen Protocol

Protocol:

`data/evidence/jam_successor_development_distribution_protocol_v1.json`

Protocol evidence hash:

`8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551`

Protocol-file SHA-256:

`f56eff43ca8868786b55b047041ce3d453ec5cb60ac3754ba1c76dfea03cc6d1`

Archive-target manifest:

`2b997184d44db7992c6955e4c520b0a2c949197a3496177b1fc0cb06658441b2`

The protocol was frozen before development market values were read. It bound all
24 monthly archive identities, 1,052,640 UTC calendar minutes, the 3,063-minute
development quarantine, fixed quantiles, structural gates, and DuckDB `1.3.2`.
Network access, feature modification, validation/holdout access, outcomes, returns,
and trading authority were prohibited.

## Feature Rows

Artifact:

`data/evidence/jam_successor_development_feature_rows_v1.parquet`

File SHA-256:

`fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`

Schema hash:

`15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b`

Size:

`129,887,758` bytes

The artifact contains exactly one row per development calendar minute:

- `open_time_ms`
- `month`
- `quality_state`
- the frozen 17 nullable feature columns

It contains no raw forward price, future outcome, return, trade, order, strategy,
signal, candidate, or PnL column. Non-`READY` rows expose no feature values.

## Source Reconciliation

All 24 frozen aggregate-trade archive SHA-256 identities and canonical member
invariants passed. Aurex aggregated `400,020,102` source rows into `1,049,526`
observed one-minute primitives.

The full calendar and quality-state accounting is:

| Quality state | Rows |
| --- | ---: |
| `READY` | 1,046,202 |
| `PARTITION_RESET_WARMUP` | 132 |
| `SOURCE_QUARANTINE` | 3,063 |
| `POST_DEFECT_WARMUP` | 3,147 |
| `NO_AGGTRADE_MINUTE` | 96 |
| `DEGENERATE_ROBUST_SCALE` | 0 |
| `DEGENERATE_DENOMINATOR` | 0 |
| **Total** | **1,052,640** |

Overall readiness is
`0.9938839489284085727314181487` (`99.388394892840857%`). The lowest
monthly readiness is May 2019 at
`0.9806227598566308243727598566` (`98.062275985663082%`).

## Structural Profile

Every `READY` row has all 17 finite values. Every feature has at least 192,787
unique ready values and a positive interquartile range. The smallest IQR is
`0.029974886021597024` for `baseline_sell_share_mad_120m`.

The largest absolute pairwise Pearson correlation is
`0.965079931305990900` between:

- `baseline_sell_quote_median_120m`
- `baseline_sell_quote_mad_120m`

This is descriptive redundancy evidence only. It does not authorize feature
selection, deletion, weighting, or an event threshold.

The fixed 0.1%, 1%, 5%, 25%, 50%, 75%, 95%, 99%, and 99.9% marginal quantiles,
monthly one-percent tail concentrations, signs, extrema, means, population standard
deviations, and all 136 pairwise correlations are preserved in the result artifact.

## Frozen Gates

All seven gates passed:

1. all 24 archives match frozen SHA-256 and source invariants
2. the calendar contains exactly 1,052,640 UTC minutes
3. overall `READY` rate is at least 0.90
4. every `READY` row has all 17 finite features
5. every feature has at least 100 unique ready values
6. every feature has positive interquartile range
7. every month has `READY` rate of at least 0.85

These gates prove source integrity and measurement viability only. They do not test
predictive value, fee-net expectancy, drawdown, robustness, or profitability.

## Result

Result:

`data/evidence/jam_successor_development_distribution_result_v1.json`

Result evidence hash:

`d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef`

Result-file SHA-256:

`be5e863b6a12b8d37646a6899cab3ee1b4808d429dac6ceaf53a693926ff8cc8`

Runner contract hash:

`aac5beb2a93881103b67a2f12705c1e5d46d2d5a3ba61ba28c53b6d435e59df8`

Decision:

`PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION`

## Independent Reconstruction

Audit:

`data/evidence/jam_successor_development_distribution_audit_v1.json`

Audit evidence hash:

`7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`

Audit-file SHA-256:

`477782c388c8e43adf5da397c640577e3f37b647e4513909c6d68478e7d28840`

The audit rehashed and reprocessed all 24 source archives. It reproduced the
1,052,640-row Parquet byte-for-byte, including its file and schema hashes, then
reproduced the complete serialized result and result evidence hash exactly.

## Numerical Boundary

DuckDB evaluates division through binary floating-point before the frozen
`DECIMAL(38,18)` output cast. Synthetic conformance compares the SQL engine with
the Decimal reference and requires absolute error below one-billionth or relative
error below one-trillionth. Archive aggregation, ordering, state transitions,
stored output, profiling, and reconstruction remain deterministic.

## Next Gate

The exact next authorization at distribution closeout was:

`AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS`

That authorization was subsequently granted. The resulting frozen protocol is
recorded in `docs/29_JAM_SUCCESSOR_EVENT_OUTCOME_PROTOCOL.md`.

It froze, before outcome access:

- the event-definition method
- candidate event prevalence constraints
- future outcome horizons and labels
- overlap and embargo policy
- chronology and development-only discovery rules
- multiplicity, selection, and stopping controls
- the exact boundary for later return calculation

It calculated no future label, return, PnL, strategy result, signal, candidate
eligibility, paper result, or order. Current progression is controlled by that
protocol's development event-prevalence authorization, not by repeating this stage.

Real net profit remains `$0`. Paper strategy execution, Testnet strategy orders,
production, live trading, and real-capital authority remain disabled.

## Verification

Closeout verification passed:

- frozen distribution protocol reconstruction
- 24-archive independent feature/result reconstruction
- byte-identical Parquet and result evidence
- 79 focused Jam lineage tests
- repository-wide Ruff
- all 1,052 Aurex tests in 1,451.94 seconds

The only warning was the existing Starlette/httpx deprecation.
