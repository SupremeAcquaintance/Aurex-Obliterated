# Jam Successor Development Outcome

## Status

Complete and independently reconstructed on `2026-08-05`.

Decision:

`STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`

Next required authorization:

`NONE_DEVELOPMENT_OUTCOME_FAILED`

The frozen Jam successor event definition is retired. This is a valid negative
research result, not a strategy, candidate, signal, paper-trading approval, or
claim of profitability.

## Authority

The user authorized the exact bounded stage:

`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION`

The stage could open only the already designated 2019-2020 development
aggregate-trade prices. It could calculate the frozen 15-, 30-, and 60-minute
outcomes, realistic cost cases, deterministic matched controls, month-cluster
inference, and the eleven development gates.

It could not alter the event, threshold, suppression, horizon, cost, control,
bootstrap, or gate rules. It could not open 2021 validation or 2022 holdout,
promote diagnostics, create a strategy or signal, grant paper eligibility, submit
a Testnet strategy order, or enable production, live, or real-capital authority.

## Frozen Execution

Before opening any post-event price, Aurex froze:

`data/evidence/jam_successor_development_outcome_execution_protocol_v1.json`

Protocol evidence hash:

`e7ed92d708c80a87b36c7d24d903cd7be1c1f594def74daab22618ed9bc6e07d`

Protocol-file SHA-256:

`7528082404d66fc19a999ec2afda3a438138826a24b9e480d88ecd8cc5a347b3`

Builder-contract hash:

`6e45696c99efb89bde12f27971058695a7de4456dbf42c2c685c74e0cf2a833a`

The execution remained bound to the parent event protocol, the independently
audited prevalence result, the immutable 1,430-record event ledger, and the
2019-2020 causal feature artifact.

## Source Extraction

The runner read all 24 monthly development aggregate-trade archives using their
previously accepted SHA-256 identities. It requested exactly 86,820 event/control
path minutes, recovered all 86,820, and found zero missing requested minutes.
No kline fallback, synthetic minute, sealed-period row, or network source was used.

Entry was the first normalized aggregate trade in minute `t+1`. Exit was the last
normalized aggregate trade in the fixed horizon minute. Every minute in each path
had to exist and remain outside quarantine.

## Controls And Outcomes

| Measure | Observed |
| --- | ---: |
| Accepted development events | 991 |
| Primary 30-minute event outcomes | 991 |
| Matched controls | 456 |
| Unmatched events | 535 |
| Primary matched pairs | 456 |
| Control-ledger records | 991 |
| Outcome-ledger records | 4,341 |
| Available event outcomes at 15/30/60 minutes | 991 / 991 / 991 |
| Available control outcomes at 15/30/60 minutes | 456 / 456 / 456 |

Controls matched exact calendar month, UTC hour, and frozen activity quartile.
They were at least 1,440 minutes from every raw event, selected without
replacement, separated by at least 60 minutes, and chosen without outcome access.

## Economic Result

The sole selectable primary horizon was 30 minutes. Base costs were 0.10%
commission per side plus two adverse one-cent ticks per fill. Stress costs were
0.15% per side plus ten adverse ticks per fill.

| Frozen measure | Observed | Required | Result |
| --- | ---: | ---: | --- |
| Outcome-qualified events | 991 | at least 200 | PASS |
| Matched control pairs | 456 | at least 180 | PASS |
| Base net mean, 30m | -16.0080982814 bps | at least 5 bps | FAIL |
| Base net profit factor | 0.4643745160 | at least 1.20 | FAIL |
| Stress net mean, 30m | -26.1897882697 bps | above 0 | FAIL |
| Matched excess mean, 30m | 2.9849778847 bps | at least 5 bps | FAIL |
| Bootstrap lower 95%, base mean | -19.7686776431 bps | above 0 | FAIL |
| Bootstrap lower 95%, matched excess | -3.0412893665 bps | above 0 | FAIL |
| Positive calendar years | 0 of 2 | 2 of 2 | FAIL |
| Positive quarters | 0 of 8 | at least 6 of 8 | FAIL |
| Largest monthly absolute-return contribution | 9.0391072505% | at most 20% | PASS |

Only `3/11` gates passed. Both development years and all eight quarters had
negative base net means. The largest monthly contribution was July 2019, but
concentration was not the problem. The failure was broad economic weakness after
costs, weak profit factor, and negative uncertainty bounds.

The positive `2.9849778847` bps matched excess does not establish an edge. It is
below the frozen 5 bps threshold and its one-sided 95% lower bound is negative.
The 15- and 60-minute diagnostics cannot rescue the failed primary result.

## Evidence

Matched-control ledger:

`data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl`

SHA-256:

`c23ea774b26fa50bd4bc37dfc3273efe28d56d4a4ccd545243bbca08d0ab6e34`

Outcome ledger:

`data/evidence/jam_successor_development_outcome_ledger_v1.jsonl`

SHA-256:

`0d322ac7c88f990bc7f714c47f4d4192cb4f81ca8f930e154aa7669336de53d8`

Result:

`data/evidence/jam_successor_development_outcome_result_v1.json`

Result evidence hash:

`560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430`

Result-file SHA-256:

`82639d4af205f089c71192856228873c13e94f8f03587560291e90583b359962`

Runner-contract hash:

`c7f50b5e8920dee6c8da22caf2d72b9f36af5d07054a004c54f9ed89116d7791`

Independent audit:

`data/evidence/jam_successor_development_outcome_audit_v1.json`

Audit evidence hash:

`8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`

Audit-file SHA-256:

`5f658a59ac7f46be964f5c46307faef3b1503b3a37b1487346fa07ef49f3ea4f`

The audit regenerated all 24 source extractions, the complete control and outcome
ledgers, every metric, all bootstrap results, and the terminal decision. The
reconstructed artifacts matched the canonical evidence byte-for-byte.

## Boundary

| Authority or evidence | State |
| --- | --- |
| 2019-2020 development outcomes | Opened and consumed |
| 2021 validation | Sealed |
| 2022 holdout | Sealed |
| Event thresholds or rules changed | No |
| Diagnostics used for selection | No |
| Candidate or strategy created | No |
| Pine parity authorized | No |
| Paper or Testnet strategy execution authorized | No |
| Production, live, or real capital authorized | No |
| Real net profit | `$0` |

This event definition may not be tuned, relabeled, rerun with easier costs, or
advanced to validation. Any future research mechanism must be genuinely unrelated,
separately versioned, and preregistered before its own development evidence is
opened. That is a new research decision, not a continuation authorization for this
failed lineage.

## Verification

The frozen execution-protocol check, independent byte-for-byte reconstruction,
seven focused canonical/synthetic outcome tests, 95 focused Jam lineage tests,
and repository-wide Ruff pass. The complete Aurex suite passes `1068` tests in
`676.74` seconds. The only warning is the existing Starlette/httpx deprecation.
