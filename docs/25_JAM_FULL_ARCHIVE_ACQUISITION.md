# Jam Full 2019-2022 Archive Acquisition

## Status

Acquisition and independent raw-file reconstruction complete on `2026-08-01`.
The frozen source-quality gate failed.

This stage acquired and validated the complete frozen BTCUSDT Spot monthly
aggregate-trade and one-minute-kline matrix from January 2019 through December
2022. It did not calculate a feature, parameter, signal, return, trade, PnL, or
strategy ranking.

## Frozen Protocol

Protocol:

`data/evidence/jam_archive_full_acquisition_protocol_v1.json`

Protocol evidence hash:

`b27197c3b9c7e4366b3e72442206562e1ae2967931ec3fa383e59c9133bcaf74`

The protocol bound:

- 48 exact months and two source families per month
- 96 published archive SHA-256 identities
- reuse of the two independently audited January 2019 pilot files
- 94 remaining network targets
- 2.5 GB maximum compressed size per archive
- 60 GB maximum compressed size overall
- 20 GB maximum uncompressed size per member
- 600 GB maximum uncompressed size overall
- 20 GB minimum free disk after acquisition
- at most 282 HEAD attempts and 282 GET attempts
- two retries with deterministic 2- and 5-second backoff
- no redirects
- resumable byte-range GET
- exact ZIP, schema, timestamp, ordering, continuity, and cross-family rules
- no feature, parameter, return, strategy, order, production, or live authority

## Acquisition

All 96 published archive identities are present and checksum-verified.

- reused pilot archives: 2
- newly acquired archives: 94
- HEAD requests: 94
- payload GET requests: 95
- redirects: 0
- compressed archive bytes: 29,691,768,890
- declared member bytes: 161,290,218,393
- free disk after acquisition: 70,690,512,896 bytes

One aggregate-trade download, April 2022, required a resumable second attempt. Its
completed archive matched the frozen published SHA-256. Every other new archive
completed in one GET attempt.

The raw files and immutable request/response markers are beneath:

`data/evidence/jam_archive_full_acquisition_v1/BTCUSDT`

The January 2019 reused files remain beneath:

`data/evidence/jam_archive_payload_pilot_v1/BTCUSDT/2019-01`

## Runner Incidents

The initial runner stopped when it encountered a genuine March 2019 missing-kline
span. A second revision stopped on an official empty June 2019 candle whose close
timestamp was not the frozen `open + 59,999 ms` value. The final recorder preserves
both defects as failed evidence and continues the census without relaxing either
rule.

The 2021-12 aggregate archive contains one correct top-level CSV and a second nested
copy. The final runner parses only the safe canonical top-level member, includes
the entire ZIP member footprint in resource totals, and records
`ZIP_MEMBER_MATRIX_FAILED` and `ZIP_MEMBER_SAFETY_FAILED`.

Before continuing from the 35-month checkpoint, Aurex:

- preserved the original checkpoint
- verified the published SHA-256 of all 70 completed archives
- verified that every completed archive retained exactly one expected member
- bound the known old and new runner hashes
- wrote a reproducible checkpoint-migration record

Migration evidence hash:

`bb971b20617fd54fb97b190d7bea68832f4a092d78b74585f698e850996ac4d0`

Old checkpoint evidence hash:

`eaffe3d3c44737167f3a509f287fdaf13a3115dbffbf45aaf81089d840cfc691`

Migrated checkpoint evidence hash:

`873fa0e9fa69d393ed2131abdd7ae5737f76f6fde5873534b806442b3aa15315`

## Source-Quality Result

Exactly 23 of 48 months passed every frozen rule. Twenty-five failed at least one.

- 2019: 5 passed, 7 failed
- 2020: 5 passed, 7 failed
- 2021: 4 passed, 8 failed
- 2022: 9 passed, 3 failed

Failed months:

`2019-03, 2019-05, 2019-06, 2019-08, 2019-10, 2019-11, 2019-12,
2020-02, 2020-03, 2020-04, 2020-06, 2020-10, 2020-11, 2020-12,
2021-01, 2021-02, 2021-03, 2021-04, 2021-08, 2021-09, 2021-10,
2021-12, 2022-02, 2022-04, 2022-05`

Archive-level failure counts:

- kline continuity failure: 16 months
- kline row-invariant failure: 8 months
- aggregate ZIP member-matrix/safety failure: 1 month
- cross-family reconciliation failure: 18 months

## Row And Reconciliation Evidence

Aggregate trades:

- rows: 1,972,243,570
- aggregate events outside available kline minutes: 0
- recorded aggregate-ID or raw-trade-span gap reason: 0 months

One-minute klines:

- expected rows: 2,103,840
- observed rows: 2,099,831
- missing rows: 4,009
- recorded continuity/row defects: 4,017

Cross-family mismatch totals at decimal tolerance `0.00000001`:

- raw-trade-count mismatches: 144
- OHLC mismatches: 135
- base-volume mismatches: 144
- quote-volume mismatches: 144
- taker-buy base-volume mismatches: 142
- taker-buy quote-volume mismatches: 142

These counts show that official aggregate trades and official one-minute klines are
not perfectly coextensive under an exact zero-defect rule. They do not show that
either family is suitable for a trading strategy, and they do not establish edge.

## Evidence

Result:

`data/evidence/jam_archive_full_acquisition_result_v1.json`

Result evidence hash:

`ffe45a45bc9340e3323aac9ddd4257a19597bcee260961f787b50c8b1dee121b`

Result-file SHA-256:

`d33559a1696c1e4db45b410ef25e2b72d61854a9d10c2b5403521bac12a136a6`

Decision:

`STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED`

Artifact next authorization:

`NONE_ACQUISITION_FAILED`

Independent audit:

`data/evidence/jam_archive_full_acquisition_audit_v1.json`

Audit evidence hash:

`d0f1d8bc4a2fe8745bf678aacdeeaeb3ef547fed49b9956dc54d36311c96e961`

Audit-file SHA-256:

`8a1cca59bb8c3238639bda0ed104331bdf27ef855b98b35ad4dd1d1acb881198`

Raw-manifest hash:

`362633896615d1ce287f71563b5e63c97b87a47dec4a5a8a5af5524fbbfe017d`

The independent process rehashed all 96 ZIPs and reconstructed all 48 monthly
archive and reconciliation records from raw CSV members. Its rebuilt records,
result-file identity, decision, and authority boundary match the authoritative
result.

Closeout verification passed:

- frozen protocol rebuild/check
- 35-to-48-month checkpoint-migration replay
- final result/checkpoint/raw-hash audit
- independent 96-archive, 48-month raw reconstruction
- 50 focused Jam charter/census/pilot/full-acquisition tests
- repository-wide Ruff
- all 1,032 Aurex tests in 435.31 seconds

The only warnings were the existing pytest `cache_dir` configuration warning and
Starlette/httpx deprecation.

## Meaning

The one-month pilot correctly proved the acquisition machinery on January 2019,
but that clean month did not generalize to the entire 2019-2022 paired-source
matrix. The full gate therefore failed exactly as designed.

The result does not authorize
`AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`. It creates no Jam
successor implementation, candidate, paper eligibility, Testnet strategy-order
authority, production authority, live eligibility, capital permission, or profit.

Real net profit remains `$0`. Production and live trading remain disabled.

## Proposed Remediation Gate

The next program action is not feature specification and not backtesting. A separate
user-authorized, no-return remediation-design stage is required:

`AUTHORIZE_JAM_ARCHIVE_QUALITY_REMEDIATION_DESIGN_NO_RETURNS`

That stage may use the existing acquired files to:

- independently compare the duplicate 2021-12 members
- classify missing-minute and row-invariant intervals
- characterize the 144 reconciliation disagreements without returns
- evaluate aggregate trades as the primary mechanism source
- define deterministic outage, empty-minute, and canonical-member policy
- define whether and how secondary kline evidence may be used
- freeze exclusions, provenance, and future evidence partitions

It may not define Jam features or thresholds, inspect returns, select a strategy,
create a candidate, begin forward paper, submit Testnet strategy orders, or enable
production/live execution.

## Post-Closeout Remediation

The separately authorized remediation stage completed on `2026-08-04`. It did not
change this failed acquisition result. Instead, it established a deterministic
aggregate-primary policy over the preserved files.

Both 2021-12 aggregate members are byte-identical. Aurex enumerated all 4,009
missing kline minutes, eight invalid rows, and 144 cross-family mismatch minutes,
then froze a union quarantine of 4,161 minutes. Aggregate trades qualify as the
primary source for the future aggressor-flow mechanism; klines are QA-only.

See `docs/26_JAM_ARCHIVE_QUALITY_REMEDIATION.md`. The remediation result hash is
`02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`
and independent audit hash is
`146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`.
The exact next gate is
`AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`.
