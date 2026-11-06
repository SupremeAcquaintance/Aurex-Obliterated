# Jam Archive Metadata Census

## Status

Complete and independently audited on `2026-08-01`.

This stage checked publication metadata only. It did not download or inspect a
market-data archive.

## Frozen Scope

- Source: `https://data.binance.vision`
- Venue dataset: Binance spot monthly archives
- Symbol: `BTCUSDT`
- Families: aggregate trades (`aggTrades`) and one-minute klines (`1m`)
- Months: January 2019 through December 2022
- Exact targets: 96 `.zip.CHECKSUM` URLs
- Method: `GET`
- Maximum concurrency: 4
- Maximum attempts: 288
- Maximum response per checksum: 4,096 bytes
- Redirects: forbidden
- Archive `HEAD` requests: forbidden
- Archive ZIP requests: forbidden

The pre-network contract is:

`data/evidence/jam_archive_metadata_census_contract_v1.json`

Contract evidence hash:

`3670f121f303bf39a17dbc7b057bde913e30252687139046ae4785269f4e8302`

Target-manifest hash:

`8eddad0f88511872596f51634448451ab6406c978118c9c3e341b14ddd13dcc9`

## Observed Result

The frozen runner completed all 96 observations:

- aggregate-trade checksums: 48 present, 0 missing
- one-minute-kline checksums: 48 present, 0 missing
- total present: 96
- total missing: 0
- HTTP attempts: 96
- retries: 0
- checksum-text bytes: 8,785
- redirects followed: 0
- archive `HEAD` requests: 0
- archive payload requests: 0
- archive payload bytes: 0
- market numeric values inspected: none
- features, parameters, or returns calculated: none
- strategy executions or orders: 0

Result:

`data/evidence/jam_archive_metadata_census_result_v1.json`

Result evidence hash:

`e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e`

Result-file SHA-256:

`5a998bc2ff7b778c7c6052a297114d0d490314bff1d47b779d24abf46aeb5102`

Checkpoint:

`data/evidence/jam_archive_metadata_census_checkpoint_v1.json`

## Independent Audit

The separate audit reconstructed the target count, unique checksum URLs, HTTP
attempt count, response-byte total, coverage decision, and all zero-authority
fields from the persisted result.

Audit:

`data/evidence/jam_archive_metadata_census_audit_v1.json`

Audit evidence hash:

`3f57bd2fb843059606bf32a284db0cc15e58c436115a922073b0c862aaaabfcb`

Decision:

`PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION`

Closeout verification passed the 22-test focused charter/census suite,
repository-wide Ruff, all contract/result/audit reconstruction commands, and the
full `1004`-test Aurex suite in `354.13` seconds. The only warnings were the
existing pytest `cache_dir` configuration warning and Starlette/httpx deprecation.

## Meaning

The required historical archive names and published checksums existed when the
census ran. This is sufficient to pass the metadata-coverage gate.

It does not establish that archive bytes are downloadable, intact, parseable,
continuous, correctly timestamped, or suitable for the selected mechanism. It
does not establish a predictive edge, profitability, execution quality, or
strategy eligibility.

## Exact Next Gate

No payload acquisition is currently authorized.

The next required authorization is:

`AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT`

That later gate must freeze one month and both required source families before
network access. The pilot must verify published file hashes, bounded download
sizes, ZIP safety, CSV schema, timestamp units, ordering, duplicates, gaps,
aggregate-trade/one-minute reconciliation, and durable raw-file identity. It may
not calculate Jam features, define thresholds, inspect returns, create a
candidate, submit a Testnet strategy order, or grant production/live authority.

## Post-Census Checkpoint

The separately authorized January 2019 payload pilot completed and independently
rebuilt on `2026-08-01`. Both archive hashes matched, 5,989,468 aggregate-trade
rows reconciled exactly to 44,640 one-minute klines, and all frozen mismatch counts
were zero.

Payload-pilot result hash:

`f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974`

The next gate is now:

`AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION`
