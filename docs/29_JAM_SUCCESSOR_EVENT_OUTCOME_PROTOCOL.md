# Jam Successor Event And Outcome Protocol

## Status

Frozen and independently reconstructed on `2026-08-05`.

This protocol was frozen pre-event and pre-outcome. Its development prevalence and
outcome stages are now complete. The frozen event failed the development outcome
gates and is retired under decision
`STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.

## Parent Evidence

The protocol is bound to:

- distribution protocol evidence:
  `8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551`
- distribution result evidence:
  `d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef`
- distribution audit evidence:
  `7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`
- feature-row SHA-256:
  `fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`
- feature-row schema hash:
  `15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b`
- causal feature-specification evidence:
  `8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`

No row-level development feature value was inspected while designing the protocol.
Only the already accepted marginal distribution statistics were used.

## Primary Event

Event identity:

`J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1`

The event is long-only and evaluated after minute `t` closes. A row is a raw event
only when it is `READY` and all five conditions are true:

| Condition | Frozen predicate |
| --- | --- |
| Extreme aggressive sell flow | `shock_sell_flow_robust_z_5m >= 4.625575808694040576` |
| Sell-side dominance | `shock_sell_share_5m >= 0.495418809496035904` |
| Negative shock price impact | `shock_price_impact_bps_5m <= -8.269710038582845440` |
| Confirmation flow decay | `sell_flow_decay_ratio_3m_vs_5m <= 0.938264464494273536` |
| Causal price reclaim | `reclaim_bps_vs_pre_shock_vwap >= 0.389389126850270272` |

The thresholds are the frozen development `q95`, `q50`, `q25`, `q50`, and `q50`
values respectively. There is no alternative threshold, weighted score, ranking,
classifier, model fit, or parameter grid.

Missing features mean not an event. That rule cannot be relaxed.

## Event Suppression

Raw events are ordered by `evaluation_open_time_ms`.

The first raw event is accepted. Each later raw event is accepted only if its
evaluation time is at least 60 minutes after the prior accepted event. Suppressed
events remain in audit evidence but create no future outcome.

Suppression resets at every evidence-partition boundary. This guarantees that the
longest frozen outcome windows do not overlap.

## Prevalence Gates

Before any future price or outcome may be joined, the development-only event screen
must pass all seven gates:

1. at least 1,000 raw events
2. at least 240 non-overlapping accepted events
3. at least 20 of 24 months contain at least five accepted events
4. every one of the eight development quarters contains at least 15 accepted events
5. the largest month contains no more than 10% of accepted events
6. the largest UTC day contains no more than 2% of accepted events
7. zero accepted events have a non-`READY` feature row

Failure stops this event definition. Aurex may not lower a threshold, shorten the
separation, add a variant, or inspect outcomes to rescue prevalence.

## Outcome Timing

The future entry benchmark is the first aggregate-trade price in minute `t+1`.
The exit benchmark is the last aggregate-trade price at the relevant horizon.

| Horizon | Role |
| ---: | --- |
| 15 minutes | Non-selectable diagnostic |
| 30 minutes | Primary |
| 60 minutes | Non-selectable diagnostic |

Only the 30-minute horizon may determine progression. The 15- and 60-minute
outcomes, maximum favorable excursion, and maximum adverse excursion cannot replace
or rescue it.

Every aggregate-trade minute from `t+1` through the horizon must exist, remain
unquarantined, and stay inside the same evidence partition. Otherwise the outcome
is unavailable. No minute or price may be synthesized.

## Costs

Base case:

- commission: `0.10%` per side
- adverse slippage: two `$0.01` ticks per fill

Stress case:

- commission: `0.15%` per side
- adverse slippage: ten `$0.01` ticks per fill

For a long event:

- entry fill = entry reference plus adverse ticks times tick size
- exit fill = exit reference minus adverse ticks times tick size
- net return bps =
  `10000 * ((exit_fill * (1 - exit_fee)) / (entry_fill * (1 + entry_fee)) - 1)`

Binance Spot Testnet's zero commission is explicitly not economic evidence.

## Matched Controls

Every accepted event is eligible for one deterministic non-event control. Controls
must be `READY` and match:

1. calendar month
2. UTC hour of day
3. the development quartile of
   `baseline_sell_quote_median_120m`

Controls must be at least 1,440 minutes from any accepted event, are selected
one-to-one without replacement, and are separated by at least 60 minutes.
Events are processed chronologically. The nearest eligible timestamp is selected;
an exact distance tie selects the earlier timestamp.

Future outcomes cannot affect matching. An unmatched event remains in the event
study but is excluded from the matched contrast.

## Development Decision

The 30-minute development outcome may advance only if all eleven gates pass:

1. at least 200 outcome-qualified events
2. at least 180 matched pairs
3. base-cost mean net return of at least 5 bps
4. base-cost profit factor of at least 1.20
5. positive stress-cost mean net return
6. matched excess mean return of at least 5 bps
7. positive one-sided 95% bootstrap lower bound for base net mean
8. positive one-sided 95% bootstrap lower bound for matched excess mean
9. positive base net mean in both 2019 and 2020
10. positive base net mean in at least six of eight quarters
11. no month contributes more than 20% of absolute return

Inference uses a calendar-month cluster bootstrap with replacement, 10,000
repetitions, fixed seed `20260805`, and one-sided 95% percentile lower bounds.

There is one primary event, one direction, and one selectable horizon, so no
multiplicity correction is needed. Diagnostics cannot be promoted after seeing
results.

## Sealed Evidence

| Partition | Current state |
| --- | --- |
| 2019-2020 development | Features opened; events and outcomes not calculated |
| 2021 validation | Sealed |
| 2022 holdout | Sealed |
| 2023-2025 Jam decision evidence | Consumed and excluded |
| 2026 Jam exploratory/forward periods | Consumed or reserved and excluded |

Development must pass unchanged before a new authorization can open 2021.
Validation must pass every fixed validation gate before a new authorization can
open 2022. Thresholds, matching, costs, horizons, and gates cannot be re-estimated
after development or validation.

A failure at any stage retires this event definition. It cannot be edited in place.

## Evidence

Protocol:

`data/evidence/jam_successor_event_outcome_protocol_v1.json`

Protocol evidence hash:

`33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db`

Protocol-file SHA-256:

`6eaf28df7810a9ebb93a048ded432c27d9d7791fdca6210d84d752e89a1f5081`

Builder contract hash:

`9a4835b95eb6a8c1c91a71e3543ed45f1b9f4da6d96d3e7ae696e968f97bacd8`

Independent audit:

`data/evidence/jam_successor_event_outcome_protocol_audit_v1.json`

Audit evidence hash:

`b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4`

Audit-file SHA-256:

`24f292d0441dcaf2128530b51d84cfd535f960430bb8df01c7641c64c75e0281`

Decision:

`PASS_EVENT_AND_OUTCOME_PROTOCOL_AWAIT_DEVELOPMENT_EVENT_PREVALENCE_AUTHORIZATION`

## Historical Gates

The historical next authorization was:

`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES`

That stage passed. The later bounded authorization
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION` was also executed.
Only 3/11 development outcome gates passed, so the lineage stopped before
validation. The complete result is recorded in
`docs/31_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME.md`.

The current artifact authorization state is:

`NONE_DEVELOPMENT_OUTCOME_FAILED`

Real net profit remains `$0`; paper, production, live, and real-capital authority
remain disabled.

## Verification

The frozen protocol check and independent audit reconstruction pass. The focused
Jam lineage suite passes `83` tests, repository-wide Ruff passes, and the complete
Aurex suite passes `1056` tests in `843.20` seconds. The only warning is the
existing Starlette/httpx deprecation.
