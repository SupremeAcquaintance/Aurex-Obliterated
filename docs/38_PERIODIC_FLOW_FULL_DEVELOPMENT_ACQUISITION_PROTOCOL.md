# Aurex Q1 Paired Full-Development Acquisition Protocol

Status: `FROZEN_AND_INDEPENDENTLY_AUDITED_PRE_NETWORK`

Next authorization:
`AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ARCHIVE_ACQUISITION`

This protocol expands the passing 2020-01 structural pilot into an exact acquisition
plan for development data only. It authorizes implementation and execution of a
bounded archive-quality run. It does not say the other 47 months will pass, and it
does not authorize features, outcomes, strategy research, or trading.

## Exact Matrix

- Symbol: `BTCUSDT`.
- Development period: `2020-01` through `2023-12`.
- Months: 48.
- Spot family: 48 monthly `aggTrades` archives.
- USD-M family: 48 monthly raw `trades` archives.
- Total checksum-pinned targets: 96.
- Local reuse candidates: 37.
- Possible network targets: 59.
- Maximum attempts per network target: 3.
- Maximum payload GET attempts: 177.
- Archive HEAD, redirects, and byte-range requests: forbidden.

Thirty-six Spot archives from 2020-2022 and the passing 2020-01 raw-trades pilot are
local candidates. Candidate means only that exact bytes may already exist. Each must
be freshly rehashed and structurally parsed under this protocol before checkpoint
acceptance. A filename or prior presence is insufficient.

The Spot 2021-12 archive has one narrow exception inherited from immutable prior
evidence: its top-level member may be selected only when the extra member is
byte-identical. Any changed archive hash, member name, member bytes, or member count
fails closed.

## Transport And Storage

- Maximum concurrency: 1.
- Request timeout: 300 seconds.
- Retry delays: 2 and 5 seconds.
- Request marker: required before each attempt.
- Checkpoint: required after each fully qualified archive.
- Partial archive reuse: forbidden.
- Archive-level resume: permitted only from completed qualified checkpoints.
- Maximum compressed bytes per archive: 5 GB.
- Maximum new compressed bytes: 100 GB.
- Maximum expanded bytes per member: 30 GB.
- Maximum total expanded bytes: 1 TB.
- Maximum ZIP expansion ratio: 100x.
- Required free disk after acquisition: 20 GB.

These are hard stop limits, not expected usage claims. Insufficient disk, unexpected
size, transfer ambiguity, or a stale partial file blocks acquisition.

## Structural Gates

Every archive must match its published SHA-256, exact product/family URL, member
policy, six- or eight-column schema, millisecond timestamp semantics, row floor,
minimum 99% minute coverage, maximum 15-minute event gap, zero duplicate IDs, zero
non-increasing IDs, zero timestamp regressions, and both buyer-maker states.

Spot `aggTrades` additionally require zero aggregate-ID and raw-range gaps. USD-M
raw `trades` retain the predeclared pilot bounds: skipped-ID fraction at most
`0.001` and maximum single skipped run of 100. Each month must achieve at least 99%
paired Spot/raw minute coverage.

Only IDs, timestamps, and buyer-maker booleans may be parsed. Price, quantity, and
quote quantity remain excluded.

## Canonical Evidence

- Protocol:
  `data/evidence/q1_periodic_flow_full_development_acquisition_protocol_v1.json`
- Protocol file SHA-256:
  `9b36d16f2c2aafb01f737e3b94b801bb3e439dd5f83cc7e4bb61229f681988ab`
- Protocol evidence hash:
  `44264aa5cd54d6b82156e068cf93de59b0ebfbe1d151363beffe598f3803e67c`
- Independent protocol audit:
  `data/evidence/q1_periodic_flow_full_development_acquisition_protocol_audit_v1.json`
- Audit file SHA-256:
  `1a74712fda24a22ef23c62006ce0a02bba15f90a9cd3eeee23d013088d22209f`
- Audit evidence hash:
  `f4193b58181ab70156edeb1ffd47a41804bb45eb038f5d2fe127948e19d40e52`

The independent audit reconstructed all 96 targets, counts, source bindings,
transport limits, quality gates, and authority flags with zero network request,
payload byte, market numeric value, outcome, candidate, execution, or order.

## Exact Next Gate

The runner and its execution addendum are implemented, source-bound, synthetically
proved, frozen, and independently audited. All 37 local reuse candidates also pass
fresh checksum and ZIP-policy preflight. The acquisition itself has not started:
the point-in-time free-space observation was `48,036,913,152` bytes against the
frozen `120,000,000,000`-byte requirement.

Make at least `120,000,000,000` bytes free on the acquisition volume and rerun the
canonical preflight. No network target may start until that gate passes. Then run
only the checkpointed acquisition in chronological Spot-then-raw order.

A passing acquisition would authorize a separate no-outcome feature/measurement
protocol. It would not prove predictive edge, reliability, a qualified strategy, or
profit. Validation, holdout, Pine deployment, paper operation, Testnet strategy
orders, production, live trading, and real capital remain blocked.

## Execution And Preflight Evidence

- Execution contract:
  `data/evidence/q1_periodic_flow_full_development_execution_contract_v1.json`
- Execution-contract file SHA-256:
  `e9b960f4122a344b1fc7ac0bb4518ac0b057f1c105a804a4f7c165f48276201e`
- Execution-contract evidence hash:
  `542c84962812de3950a543c221f31375cacb8c5de702a805ae74379b2ce1adf9`
- Independent execution-contract audit hash:
  `018ef8a010f9b971c3ed638b5f2173e1520f65104ed3c1574dfb540efd6f16e3`
- Preflight result:
  `data/evidence/q1_periodic_flow_full_development_preflight_result_v1.json`
- Preflight result file SHA-256:
  `c93d6b3cf8b8e55cfc5055a47e1c427b5a2f35f04523a69bcd6fef5cfa92d9b0`
- Preflight result evidence hash:
  `623c22fec5a5895eda9ffac2940f1cd932582d1b7977300f55e0918d78980c5c`
- Independent preflight audit hash:
  `eadf6ea3e7a7cf223f53de83ca0f44d453614579f7589b1e970af5ce15dca4ba`
- Preflight decision: `BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK`.
- Network requests, payload bytes, outcomes, and orders: `0`.
