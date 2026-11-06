# Aurex Q1 USD-M Raw-Trades Metadata Census

Status: `COMPLETE_CHECKSUM_ONLY_NO_PAYLOAD_NO_OUTCOMES`

Decision: `PERMIT_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL`

Next authorization: `AUTHORIZE_Q1_USDM_RAW_TRADES_ONE_MONTH_PAYLOAD_PROTOCOL`

This checkpoint establishes official monthly publication coverage for the USD-M
raw `trades` archive family selected by the preceding cross-source adjudication.
It does not establish archive payload quality, row schema, timestamp integrity,
continuity, buyer-side semantics, predictive edge, or profitability.

## Frozen Scope

- Product: Binance USD-M perpetual futures.
- Symbol: `BTCUSDT`.
- Archive family: monthly raw `trades`.
- Period: `2020-01` through `2025-12`.
- Targets: 72 exact `.zip.CHECKSUM` URLs.
- Development metadata: 48 months, 2020-01 through 2023-12.
- Validation metadata: 24 months, 2024-01 through 2025-12.
- Maximum unique checksum URLs: 72.
- Maximum HTTP attempts: 216.
- Maximum checksum response: 512 bytes.
- Maximum concurrency: 4.
- Archive HEAD and ZIP payload requests: forbidden.
- Price, quantity, quote quantity, parameters, and outcomes: forbidden.
- Required pass condition: all 72 checksum sidecars present.

The protocol binds the daily cross-source result that rejected USD-M `aggTrades`,
readiness v6, the exact target manifest, request budgets, fail-closed decisions,
and all no-trading authority fields. A separate pre-network audit reconstructed
the protocol exactly before any checksum request was made.

Official references:

- Binance Public Data: https://github.com/binance/binance-public-data
- Binance USD-M recent trades:
  https://developers.binance.com/en/docs/derivatives/usds-margined-futures/market-data/rest-api/Recent-Trades-List

## Observed Result

All targets completed on their first HTTP attempt:

| Evidence | Result |
| --- | ---: |
| Targets observed | 72/72 |
| Checksum sidecars present | 72/72 |
| Missing sidecars | 0 |
| Development months present | 48/48 |
| Validation-metadata months present | 24/24 |
| HTTP attempts | 72 |
| Archive HEAD requests | 0 |
| Archive payload requests | 0 |
| Archive payload bytes | 0 |
| Market numeric fields inspected | 0 |
| Parameters or returns calculated | 0 |
| Candidates, executions, or orders | 0 |

Every record preserves the exact archive URL, checksum URL, checked timestamp,
HTTP status, response byte count, checksum text, checksum-text SHA-256, published
archive SHA-256, partition role, and attempt count. The result and independent
audit reconstruct exactly from those records.

## Frozen Evidence

- Protocol:
  `data/evidence/q1_usdm_raw_trades_metadata_census_protocol_v1.json`
- Protocol file SHA-256:
  `1d413d8e7442d3c0b0e31d2f09efcc766759ccd9ab34bec86d2d5c44a4d31b51`
- Protocol evidence hash:
  `08ca0b4fce3790b398f3535511d19915b3a8b80e6e8c5c1326c6caf9198e9e6e`
- Pre-network protocol audit:
  `data/evidence/q1_usdm_raw_trades_metadata_census_protocol_audit_v1.json`
- Protocol-audit file SHA-256:
  `e23a5ac763d5a4afc3df32baf12a360e235b4950b07cf81beb6dddfd619f32f8`
- Protocol-audit evidence hash:
  `10d1c474780cfa3e4903022c44170fd0a3b2beaa8072f9c5c362ea07f3a9fb67`
- Result:
  `data/evidence/q1_usdm_raw_trades_metadata_census_result_v1.json`
- Result file SHA-256:
  `868c2043af1eef683ee2e97fb279fdfb5ffe2fcfaa889cca5fe6a6d93014d893`
- Result evidence hash:
  `64da0748128779cbfc040883437a1523e571fe68b3746decc9bc7adccc7c793a`
- Independent result audit:
  `data/evidence/q1_usdm_raw_trades_metadata_census_audit_v1.json`
- Result-audit file SHA-256:
  `e563b039c2658dee6885e71d94fda34395ed73ffe88bd8ee58ba8c087d37cb68`
- Result-audit evidence hash:
  `e29b821c8795482dc64f25230d6f2d50c3f9feccda48a22326ec81de2c68c95a`

## Completed Next Gate

Freeze and independently check a one-month USD-M raw `trades` payload protocol
for the mechanically selected earliest development month, `2020-01`. Bind the
existing qualified 2020-01 Spot `aggTrades` evidence and pin the published raw-
trades archive hash from this census. The protocol must freeze byte, expansion,
row, schema, timestamp, ID-continuity, clock-coverage, buyer-side semantics, and
quarantine gates before the raw-trades ZIP is requested.

That protocol independently passed before one checksum-pinned archive request. The
one-month structural pilot also passed and is documented in
`docs/37_PERIODIC_FLOW_USDM_RAW_TRADES_PAYLOAD_PILOT.md`. It authorizes only a
separately frozen paired full-development acquisition protocol. It does not
authorize parameter selection, return testing, Pine, paper operation, Testnet
strategy orders, production, or live trading.
