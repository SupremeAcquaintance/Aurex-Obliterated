# Jam One-Month Archive Payload Pilot

## Status

Complete and independently rebuilt on `2026-08-01`.

The pilot establishes that Aurex can safely acquire, parse, validate, and reconcile
one month of official Binance spot aggregate trades and one-minute klines. It does
not test a trading hypothesis.

## Frozen Protocol

Pilot month: January 2019.

The month was selected by the rule
`EARLIEST_MONTH_IN_PROVISIONAL_POOL_NO_OUTCOME_SELECTION` before any payload was
opened.

Frozen targets:

- `BTCUSDT-aggTrades-2019-01.zip`
- `BTCUSDT-1m-2019-01.zip`

Resource boundaries:

- maximum compressed bytes per archive: 750,000,000
- maximum compressed bytes total: 800,000,000
- maximum uncompressed member bytes per archive: 4,000,000,000
- maximum uncompressed member bytes total: 4,100,000,000
- maximum HTTP attempts: 12
- redirects: forbidden
- minimum free disk before acquisition: 5,000,000,000 bytes plus observed files

Protocol:

`data/evidence/jam_archive_payload_pilot_protocol_v1.json`

Protocol evidence hash:

`1e9a6ef48ac06353f933d21cb193bf0b1489f03f79e6a4562062a0ddddbba24e`

## Acquisition

Exactly four successful HTTP requests were made:

- aggregate-trade HEAD: 1
- aggregate-trade GET: 1
- one-minute-kline HEAD: 1
- one-minute-kline GET: 1

No redirect or retry occurred.

Aggregate-trade archive:

- compressed bytes: 93,204,261
- uncompressed CSV bytes: 406,620,226
- published and observed SHA-256:
  `588bff60b17e906ad4b654d0f615d838a2b2ec36b7790e5db40c6d2a03556355`

One-minute-kline archive:

- compressed bytes: 2,120,781
- uncompressed CSV bytes: 6,368,720
- published and observed SHA-256:
  `08dd2f7306258d1b9fd0b9fc00ee807c1c96e9803c74c78c00a0072bfc826728`

Total compressed bytes: 95,325,042.

The ZIPs are preserved beneath:

`data/evidence/jam_archive_payload_pilot_v1/BTCUSDT/2019-01`

Request and response markers are stored beside each archive.

## Data Validation

Both ZIPs contained exactly one expected, non-encrypted, non-link CSV member. Their
declared expansion, path, schema, and CRC checks passed.

Aggregate trades:

- rows: 5,989,468
- unique covered minutes: 44,640
- aggregate-trade ID gaps: 0
- raw-trade-span gaps: 0
- duplicate primary keys: 0
- out-of-order rows: 0

One-minute klines:

- rows: 44,640
- expected rows: 44,640
- unique minutes: 44,640
- missing-minute gaps: 0
- duplicate primary keys: 0
- out-of-order rows: 0
- open-time alignment and close-time invariants: passed
- OHLC, volume, trade-count, and taker-volume row invariants: passed

## Cross-Family Reconciliation

All 44,640 minutes were compared. Tolerance for decimal volume comparisons was
`0.00000001`.

- aggregate trades outside kline coverage: 0
- raw-trade-count mismatches: 0
- OHLC mismatches: 0
- base-volume mismatches: 0
- quote-volume mismatches: 0
- taker-buy base-volume mismatches: 0
- taker-buy quote-volume mismatches: 0

## Evidence

Result:

`data/evidence/jam_archive_payload_pilot_result_v1.json`

Result evidence hash:

`f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974`

Result-file SHA-256:

`ce63c4a89e1281bbf7e95b16e3412b9e7142a09d005bb59ad5191ae4f8420f7f`

Independent audit:

`data/evidence/jam_archive_payload_pilot_audit_v1.json`

Audit evidence hash:

`bc8880252f50215be1fbb46803e1325d5e40c2b34101ad02bad0d4284ad710bf`

Decision:

`PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION`

Closeout verification passed the 35-test Jam charter/census/payload lineage suite,
repository-wide Ruff, all protocol/result/audit reconstruction commands, and the
full `1017`-test Aurex suite in `556.17` seconds. The only warnings were the
existing pytest `cache_dir` configuration warning and Starlette/httpx deprecation.

## Meaning

The January 2019 source pair is internally consistent enough for data-engineering
use. Aurex now has evidence that its acquisition, archive safety, schema parsing,
timestamp handling, and cross-family reconciliation design work on one real month.

One month does not establish full 2019-2022 coverage quality. It also does not
establish a Jam feature definition, threshold, signal, backtest result, predictive
edge, profitability, or trading eligibility.

## Exact Next Gate

No additional archive acquisition is currently authorized.

The next required authorization is:

`AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION`

That stage must freeze the remaining exact archive manifest, published hashes,
request and storage budgets, resumability rules, validation requirements, and
evidence partition before network access. It may acquire and validate data but may
not define Jam parameters, inspect returns, create a candidate, begin forward
paper, submit Testnet strategy orders, or enable production/live trading.

## Post-Pilot Checkpoint

The separately authorized full acquisition subsequently completed. Preserve this
pilot as the clean January 2019 capability proof, but use
`docs/25_JAM_FULL_ARCHIVE_ACQUISITION.md` for the current program state.

Only 23 of 48 full-period months passed every frozen paired-source rule. The
authoritative full-acquisition decision is
`STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED`; feature specification is not
authorized.
