# Jam Successor Feature Specification

## Status

Complete, frozen, and independently reproduced on `2026-08-04`.

This is a causal feature contract, not a strategy. It inspected zero real market
rows and defined no future label, decision threshold, signal conjunction, entry,
exit, stop, target, sizing rule, return, or PnL calculation.

The separately authorized development-distribution stage has since completed. Its
result and next authority boundary are recorded in
`docs/28_JAM_SUCCESSOR_DEVELOPMENT_DISTRIBUTION.md`; this specification remains
immutable historical lineage.

## Mechanism

The selected hypothesis is:

`J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM`

The mechanism asks whether an unusually intense aggressive sell-flow episode causes
temporary price impact, followed by measurable sell-flow decay and price reclaim.
The feature vector measures those components. It does not decide what measurements
are large enough to trade.

## Frozen Protocol

Protocol:

`data/evidence/jam_successor_feature_specification_protocol_v1.json`

Protocol evidence hash:

`86ee3e67c6fc78863378b4a1b30c8cb38f9aafda2335e92054309cd260bfffba`

Protocol-file SHA-256:

`8f863f6db68700431c02e653dbde0dbe770e768bb8d93fa10309e67fe2e0a1e6`

The protocol was frozen before the feature specification. It permitted causal
schema-level transformations, lookbacks, conventional normalization constants, and
synthetic fixtures. It prohibited real archive values, outcomes, trade thresholds,
signals, strategies, candidates, orders, and live authority.

## Source Semantics

Primary source:

`BINANCE_SPOT_MONTHLY_AGGTRADES`

One-minute UTC primitives are constructed from ordered aggregate trades:

- open: first trade price
- high: maximum trade price
- low: minimum trade price
- close: last trade price
- base volume: sum of quantity
- quote volume: sum of `price * quantity`
- raw-trade count: sum of each aggregate's inclusive raw-trade span
- taker-buy quote: quote notional where `is_buyer_maker=false`
- taker-sell quote: quote notional where `is_buyer_maker=true`

`is_buyer_maker=true` means the buyer was maker and the seller was taker. It is
therefore aggressive sell flow. The inverse is aggressive buy flow.

Official one-minute klines remain QA-only. They cannot provide, carry, fill, or
overwrite a feature value.

## Causal Window

Every feature row is evaluated after minute `t` closes.

| Phase | Inclusive lags | Minutes | Purpose |
| --- | ---: | ---: | --- |
| Baseline | `t-132` through `t-13` | 120 | Robust flow normalization |
| Pre-shock reference | `t-12` through `t-8` | 5 | Causal VWAP reference |
| Shock | `t-7` through `t-3` | 5 | Sell-flow intensity and price impact |
| Confirmation | `t-2` through `t` | 3 | Flow decay and price reclaim |

The phases are contiguous and non-overlapping. The maximum lookback and minimum
warm-up are both 133 valid minutes. No value after `t` can affect the row. Even if
later gates eventually qualify a strategy, the earliest possible order is the next
minute.

## Feature Vector

All outputs use Decimal arithmetic, 18 decimal places, and `ROUND_HALF_EVEN`.
Robust z-scores use the conventional `1.4826 * MAD` scale.

### Baseline

1. `baseline_sell_quote_median_120m`
2. `baseline_sell_quote_mad_120m`
3. `baseline_sell_share_median_120m`
4. `baseline_sell_share_mad_120m`

Sell share is taker-sell quote divided by total quote for each minute. Median and
median absolute deviation use the 120 baseline observations only.

### Reference

5. `pre_shock_vwap_5m`

This is total quote divided by total base across the five pre-shock minutes.

### Shock

6. `shock_sell_quote_mean_5m`
7. `shock_sell_flow_robust_z_5m`
8. `shock_sell_share_5m`
9. `shock_price_impact_bps_5m`
10. `shock_low_bps_vs_pre_shock_vwap`

The robust z-score compares mean shock sell quote with the baseline sell-quote
median. Price impact compares the final shock close with pre-shock VWAP. Shock low
compares the minimum shock trade price with the same reference.

### Confirmation

11. `confirmation_sell_quote_mean_3m`
12. `confirmation_sell_flow_robust_z_3m`
13. `confirmation_sell_share_3m`

These measure whether aggressive sell pressure remains elevated during the three
confirmation minutes.

### Decay And Reclaim

14. `sell_flow_decay_ratio_3m_vs_5m`
15. `sell_share_decay_delta_5m_to_3m`
16. `reclaim_bps_vs_pre_shock_vwap`
17. `bounce_bps_from_shock_low`

The flow ratio compares confirmation mean sell quote with shock mean sell quote.
The share delta subtracts confirmation sell share from shock sell share. Reclaim
compares the final confirmation close with pre-shock VWAP. Bounce compares that
close with the shock low.

These are measurements, not predicates. The specification contains no required
sign, cutoff, conjunction, or ranking.

## Quality States

- `READY`: all 133 required minutes are valid.
- `PARTITION_RESET_WARMUP`: fewer than 133 valid minutes exist in the active
  partition.
- `SOURCE_QUARANTINE`: evaluation minute is in the frozen 4,161-minute quarantine.
- `POST_DEFECT_WARMUP`: a quarantined or absent minute remains in the 133-minute
  window.
- `NO_AGGTRADE_MINUTE`: evaluation minute has no aggregate trade; it is not
  synthesized.
- `DEGENERATE_ROBUST_SCALE`: baseline sell-quote MAD is zero.
- `DEGENERATE_DENOMINATOR`: a required price or volume denominator is zero.

Only `READY` may expose feature values. All other states emit an empty vector.
Development, validation, and holdout boundaries each reset state. Rolling values
cannot cross a partition boundary.

## Evidence Partitions

| Period | Role | Outcome access |
| --- | --- | --- |
| 2019-2020 | Development | Prohibited in this stage |
| 2021 | Sealed validation | Prohibited |
| 2022 | Sealed holdout | Prohibited |

The consumed 2023-2025 Jam period remains excluded. Existing 2026 exploratory and
forward boundaries remain authoritative.

## Conformance

Nine deterministic synthetic cases passed:

1. aggressor-side mapping
2. exact 17-feature readiness after 133 minutes
3. future-minute invariance
4. evidence-partition reset
5. current-minute quarantine
6. post-defect warm-up
7. absent aggregate minute without synthesis
8. zero-MAD fail-closed behavior
9. byte-stable Decimal calculation

Conformance manifest hash:

`cae28c8f9acdc3884747281d78003f128a33907aca89d73fed6217d5974122bc`

The fixtures contain no copied market observation or outcome.

## Evidence

Specification:

`data/evidence/jam_successor_feature_specification_v1.json`

Specification evidence hash:

`8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`

Specification-file SHA-256:

`83a91e2dc1037e240e8b43122cbe8e2109f86ad4afb0f7d45b8caf9d0aef9a36`

Independent audit:

`data/evidence/jam_successor_feature_specification_audit_v1.json`

Audit evidence hash:

`760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`

Audit-file SHA-256:

`e1d296cd9c090b783bb4179dcd9683eb10b19fdeb830215d3ba8df867eec06d9`

## Decision

`PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION`

The exact next authorization at specification closeout was:

`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS`

That authorization was subsequently granted and completed without opening 2021 or
2022 or joining a future return or outcome. Current progression is controlled by
the development-distribution result, not by repeating this authorization.

This specification establishes a testable measurement system. It does not establish
edge, reliability, signal quality, eligibility, or profit. Real net profit remains
`$0`; production and live trading remain disabled.

## Verification

Closeout verification passed:

- frozen protocol rebuild
- frozen specification rebuild
- independent audit rebuild
- all nine synthetic conformance cases
- 78 focused Jam lineage tests
- repository-wide Ruff
- all 1,049 Aurex tests in 1,042.31 seconds

The only test warning was the existing Starlette/httpx deprecation.
