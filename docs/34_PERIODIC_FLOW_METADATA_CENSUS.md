# Aurex Q1 Periodic-Flow Metadata Census

Status: `COMPLETE_METADATA_ONLY_NO_PAYLOAD_NO_OUTCOMES`

Decision: `PERMIT_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL`

Next authorization: `AUTHORIZE_Q1_ONE_MONTH_PAIRED_PAYLOAD_PILOT_PROTOCOL`

This checkpoint establishes official archive publication coverage only. It does
not establish payload integrity, timestamp correctness, usable aggressor-side
semantics, signal behavior, predictive edge, execution quality, or profitability.

## Frozen Scope

- Symbol: `BTCUSDT`.
- Products: Binance Spot and Binance USD-M perpetual futures.
- Archive family: monthly aggregate trades.
- Period: 2020-01 through 2025-12.
- Months: `72`.
- Product-month checksum targets: `144`.
- Development pairs: `48` months, 2020-01 through 2023-12.
- Validation metadata pairs: `24` months, 2024-01 through 2025-12.
- Permitted network operation: GET the exact frozen `.zip.CHECKSUM` URLs.
- Maximum checksum response: `512` bytes.
- Archive HEAD and ZIP payload requests: forbidden.
- Required pass condition: all `144` targets and all `72` paired months present.

The schema register follows the official Binance Public Data documentation:

- Spot aggregate trades: eight columns from `/api/v3/aggTrades`.
- USD-M aggregate trades: seven columns from `/fapi/v1/aggTrades`.
- Spot timestamps: milliseconds through 2024, microseconds from 2025-01.
- USD-M expected timestamp unit: milliseconds, pending payload verification.

Official reference: https://github.com/binance/binance-public-data

The register is documentary. The payload pilot must independently prove actual
column counts, types, timestamp units, and buyer-maker semantics.

## Observed Result

The 144 requests completed on their first attempt:

| Evidence | Result |
| --- | ---: |
| HTTP 200 checksum responses | 144 |
| HTTP 404 responses | 0 |
| Spot months present | 72/72 |
| USD-M months present | 72/72 |
| Paired months present | 72/72 |
| Development pairs | 48/48 |
| Validation metadata pairs | 24/24 |
| HTTP attempts | 144 |
| Archive HEAD requests | 0 |
| Archive payload requests | 0 |
| Archive payload bytes | 0 |
| Market numeric fields inspected | 0 |
| Parameters or returns calculated | 0 |
| Candidates, executions, or orders | 0 |

Every stored record binds the exact URL, checked timestamp, HTTP status, response
byte count, checksum text, checksum-text SHA-256, and published archive SHA-256.
The independent audit reconstructed the complete result from those records.

## Frozen Evidence

- Contract:
  `data/evidence/q1_periodic_flow_metadata_census_contract_v1.json`
- Contract file SHA-256:
  `6305dc04a026a4fd947688f827981bb6b366fdc2730e1e7fbb623e4edaf7ac1e`
- Contract evidence hash:
  `841caf8e7dc20d21722247759f9804f5f896ac5936c40d8000467a96a03acb90`
- Result:
  `data/evidence/q1_periodic_flow_metadata_census_result_v1.json`
- Result file SHA-256:
  `64e28b44520ff3291a19b0b8a813ac84828ef3c8f35fa468e5306b2bc478d247`
- Result evidence hash:
  `54dbfba6642b9057172f32405d7ed983bb66488acd0ab31d6e26358926d41a17`
- Independent audit:
  `data/evidence/q1_periodic_flow_metadata_census_audit_v1.json`
- Audit file SHA-256:
  `0aeda203f78c51acad6dc17edd026c9a6ef1f8bccf48502dc4c8eb1eeb8df350`
- Audit evidence hash:
  `b9d62a43c6ac1af25f70d67f4ff8929e78c5b31b1c2e5017d9481ecacc12b18f`

## Current Source Decision

The authorized paired pilot and subsequent source adjudication are complete under
`docs/35_PERIODIC_FLOW_PAIRED_PAYLOAD_AND_SOURCE_ADJUDICATION.md`. Spot
`aggTrades` passed. USD-M `aggTrades` reproduced one duplicate raw-trade reference
and is rejected for the Q1 perpetual-flow input.

Freeze and independently check a checksum-only monthly USD-M raw `trades`
metadata-census protocol for `BTCUSDT`, `2020-01` through `2025-12`. Do not
request a checksum or ZIP payload before that protocol passes. This decision
authorizes neither full acquisition nor parameter selection, backtesting,
validation outcomes, Pine, paper operation, Testnet strategy orders, production,
or live trading.

## Verification

- Pre-network synthetic and adversarial tests: `7 passed`.
- Canonical contract/result/audit tests: `10 passed`.
- Combined charter/census/readiness/dashboard tests: `23 passed`.
- Contract direct reconstruction: PASS.
- Result direct reconstruction: PASS.
- Independent audit reconstruction: PASS.
- Focused Ruff: PASS.
- Repository-wide Ruff: PASS.
- Pytest collected `1103` tests. The monolithic run reached approximately 1022
  tests without failure before the 20-minute command limit; explicit post-timeout
  slices passed `33` and `68` tests and covered the remaining collection.
- Readiness v5 result hash:
  `4f01d4cb0cf6290591861ba9cae68c46cac7924ce8fef79f86ed9ce70299291c`.
- Readiness v5 independent audit hash:
  `2782565d9c9d684b015986c6948c659dd6f8d42f3bd2652c752d89c46a4911f0`.
