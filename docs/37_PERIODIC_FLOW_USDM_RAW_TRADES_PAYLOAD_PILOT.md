# Aurex Q1 USD-M Raw-Trades Payload Pilot

Status: `COMPLETE_STRUCTURAL_RAW_TRADES_PILOT_NO_OUTCOMES`

Decision: `PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL`

Next authorization: `AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL`

This checkpoint answers one question: can the checksum-pinned Binance USD-M raw
`trades` family supply structurally valid, causally pairable order-flow events for
one mechanically selected development month? The answer is yes for `2020-01`.
That is source evidence, not evidence of predictive edge or profitability.

## Frozen Boundary

- Product and archive: USD-M perpetual `BTCUSDT` monthly raw `trades`.
- Month and role: `2020-01`, development only.
- Exact new archive URL count: 1.
- Maximum attempts: 3; observed attempts: 1.
- Published archive SHA-256:
  `5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939`.
- Qualified local Spot reference SHA-256:
  `ea2f0aa850fb08b5c8124d2f8080c03689c30cdadf797363fc74b506b92a8d8b`.
- Parsed fields: raw trade ID, millisecond timestamp, and buyer-maker boolean.
- Price, quantity, quote quantity, features, parameters, returns, validation,
  holdout, candidate creation, and all strategy operation were forbidden.

The protocol froze compressed and expanded byte limits, ZIP expansion, disk reserve,
exact six-column schema, row count, clock coverage, event gaps, strict ID ordering,
duplicate rejection, bounded forward omissions, timestamp ordering, buyer-maker
domain, and paired Spot/raw minute coverage before the archive was requested.

## Observed Result

| Evidence | Result |
| --- | ---: |
| Archive bytes | 128,838,558 |
| Rows | 10,281,248 |
| Raw minute coverage | 44,640 / 44,640 |
| Paired Spot/raw minutes | 44,640 / 44,640 |
| Maximum event gap | 1 minute |
| Duplicate trade IDs | 0 |
| Non-increasing trade IDs | 0 |
| Forward gaps | 726 |
| Skipped trade IDs | 1,809 |
| Skipped-ID fraction | 0.0001759204485592173611407580450 |
| Maximum single skipped-ID count | 35 |
| Timestamp regressions | 0 |
| Buyer-maker values | false and true |
| Additional archive requests | 1 |
| Strategy candidates / executions / orders | 0 / 0 / 0 |

All frozen structural gates passed. Forward omissions were not treated as absent:
they were measured against the predeclared maximum fraction of `0.001` and maximum
single omission of 100. The pilot did not parse the excluded numeric fields.

## Canonical Evidence

- Frozen protocol:
  `data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_v1.json`
- Protocol file SHA-256:
  `004f16d7f90d53ae3bdab382c817405665870e62e3fe462a1e844808df4a791d`
- Protocol evidence hash:
  `79e7ec935f31dba86a0173398133ec4abd0acc3f2a559bc5dda0dd3f3fa77451`
- Pre-network protocol audit:
  `data/evidence/q1_usdm_raw_trades_payload_pilot_protocol_audit_v1.json`
- Protocol-audit file SHA-256:
  `e59a2d67f075274a4bedb1d9b6437a0d25b1588cf54babe948e84e789dddcf55`
- Protocol-audit evidence hash:
  `26ec1c8fd400228443beeda4130b17a019428fa8ef22b67c937e122c2b97bbe3`
- Canonical marker-bound result:
  `data/evidence/q1_usdm_raw_trades_payload_pilot_result_v2.json`
- Result file SHA-256:
  `294fd609bd9f8c0bd1449d8759b218b4cb8828cec590e8781840120634a756af`
- Result evidence hash:
  `4d0c4ef5b1f56bc498d2625fe1acd5a33faffe679425c82c5e2c83b6fc572477`
- Independent audit:
  `data/evidence/q1_usdm_raw_trades_payload_pilot_audit_v2.json`
- Audit file SHA-256:
  `bfc23dbbd0e8f4d173e082d80d4c513d956eb1360bdb5509881cfe471e24a9d2`
- Audit evidence hash:
  `3e627038aa89748165874e32cd62bd8da202670b37613c3221944cda6e350fd0`
- Request-marker manifest hash:
  `a215fed5b7e4be0f368641bb0f4d5fa3049c0b073ddf550db0a19c476d62a2ac`

The initial v1 result/audit files are preserved as provisional evidence. Canonical
v2 supersedes them because v2 hash-binds the persisted request marker and attempt
count. The frozen protocol itself was not rewritten; its original file and evidence
hashes still reconstruct exactly.

## Completed Next Gate

Freeze and independently check a paired full-development acquisition protocol for
Spot `aggTrades` and USD-M raw `trades` covering `2020-01` through `2023-12` only.
Bind all published archive checksums, the qualified pilot, byte/storage budgets,
resumable request markers, parser semantics, month-level quality gates, cross-source
clock rules, quarantine behavior, and terminal decisions before another ZIP is
requested.

Validation and holdout remain sealed. A future acquisition pass would establish a
development source bundle only. It would still not prove a signal, strategy,
reliable trade, or profit, and it would not authorize Pine, paper, Testnet strategy
orders, production, live trading, or real capital.

The paired full-development acquisition protocol is now frozen and independently
audited in `docs/38_PERIODIC_FLOW_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL.md`. No
additional archive was requested while freezing it.
