# Jam Successor Development Event Prevalence

## Status

Complete and independently reconstructed on `2026-08-05`.

Decision:

`PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION`

This is sample-availability evidence only. It is not evidence that the event
predicts price, survives costs, produces positive expectancy, or can trade.

The separately authorized development outcome stage is now also complete. It
passed only 3/11 gates, and the event definition is retired under decision
`STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.

## Authority

The user authorized the previously identified next stage by instructing Aurex to
continue. The exact bounded scope was:

`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES`

The stage could evaluate the frozen five-condition predicate on the accepted
2019-2020 causal feature rows, preserve raw and non-overlapping events, measure
calendar concentration, and apply seven frozen prevalence gates.

It could not read a future price, calculate a label or return, build a matched
control outcome, run a backtest, open 2021 validation or 2022 holdout, create a
strategy or signal, or submit an order.

## Frozen Lineage

Parent event/outcome protocol evidence hash:

`33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db`

Development feature-row SHA-256:

`fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`

The feature artifact contains 1,052,640 calendar rows and 1,046,202 `READY`
rows from January 2019 through December 2020. Its schema contains only the
previously frozen causal features and their quality state.

Before event evaluation, Aurex froze prevalence protocol:

`data/evidence/jam_successor_development_event_prevalence_protocol_v1.json`

Protocol evidence hash:

`e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd`

Protocol-file SHA-256:

`336c6e516f4def171cc4fd29a5f82ecfde5971f7883593fd3064a4eee7871119`

Builder-contract hash:

`44937ddbc794abff611c2389b69c4f77065c3b7a0475fb3a36812360607fca50`

## Event Evaluation

The raw event remained the exact five-condition long-only conjunction from the
parent protocol. No threshold, comparator, direction, score, variant, or ranking
was changed.

Raw events were processed in ascending evaluation-minute order. The first raw
event was accepted. A later raw event was accepted only when it was at least 60
minutes after the latest accepted event. Suppression did not reset at month or
year boundaries.

Every raw event is preserved in:

`data/evidence/jam_successor_development_event_ledger_v1.jsonl`

The ledger records the five causal feature values, timestamp buckets,
accepted/suppressed status, prior accepted anchor, and elapsed minutes. It contains
no future price or outcome.

Ledger record count: `1,430`

Ledger SHA-256:

`b6fe0c49bbbb8b61ac268b4716d2a50ab5fa08479ccbf254ef532b15a3b7d909`

## Results

| Measure | Observed |
| --- | ---: |
| Raw events | 1,430 |
| Accepted non-overlapping events | 991 |
| Suppressed events | 439 |
| Months with at least five accepted events | 24 of 24 |
| Minimum accepted events in any quarter | 70 |
| Largest month | 2019-08 |
| Largest month count | 82 |
| Largest month share | 8.2744702321% |
| Largest day | 2020-11-22 |
| Largest day count | 6 |
| Largest day share | 0.6054490414% |
| Accepted non-`READY` events | 0 |

## Gate Decision

| Frozen gate | Requirement | Observed | Result |
| --- | ---: | ---: | --- |
| Raw event count | at least 1,000 | 1,430 | PASS |
| Accepted event count | at least 240 | 991 | PASS |
| Months with five events | at least 20 | 24 | PASS |
| Every quarter event count | at least 15 | minimum 70 | PASS |
| Largest month share | at most 10% | 8.2745% | PASS |
| Largest day share | at most 2% | 0.6054% | PASS |
| Accepted non-ready events | exactly 0 | 0 | PASS |

All `7/7` prevalence gates passed.

This means the event occurs often enough and broadly enough for the separately
authorized development outcome calculation. It says nothing about whether returns
are positive.

## Evidence

Result:

`data/evidence/jam_successor_development_event_prevalence_result_v1.json`

Result evidence hash:

`444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea`

Result-file SHA-256:

`1bd0d659f7f582899ed7a61928e77bd92383dc8d22e3d5b79f9e178dde1a41d4`

Runner-contract hash:

`d03c402e8247b9f385151f36ffc3fd19390016a52116a4014edd1fcafc3d4387`

Independent audit:

`data/evidence/jam_successor_development_event_prevalence_audit_v1.json`

Audit evidence hash:

`414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d`

Audit-file SHA-256:

`c93ea38a6418b12e06c26650133457b8926cb0bfb49000168199cb70927c1d77`

The audit reran the frozen predicate and suppression logic from the hash-bound
feature artifact. It reproduced all 1,430 ledger lines and the complete result
byte-for-byte.

## Boundary

Future price rows accessed: `0`

Future labels calculated: `0`

Return metrics calculated: `0`

Matched controls constructed: `0`

Backtests executed: `0`

Strategy executions and orders: `0`

Validation and holdout periods opened: `0`

Real net profit remains `$0`. Paper, production, live, and real-capital authority
remain disabled.

## Historical Next Gate

The historical next authorization was:

`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION`

That stage is complete and recorded in
`docs/31_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME.md`. It calculated the frozen
development-only outcomes and failed 8 of 11 gates.

The current artifact authorization state is
`NONE_DEVELOPMENT_OUTCOME_FAILED`. The lineage may not open 2021 validation or
2022 holdout, create paper eligibility, or enable trading.

## Verification

The frozen protocol check, canonical evidence validation, and independent
byte-for-byte reconstruction pass. The focused Jam lineage suite passes `88`
tests, repository-wide Ruff passes, and the complete Aurex suite passes `1061`
tests in `1426.56` seconds. The only warning is the existing Starlette/httpx
deprecation.
