# Aurex Q1 Paired Payload And Source Adjudication

Status: `COMPLETE_SOURCE_MIGRATION_NO_OUTCOMES`

Decision: `PERMIT_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL`

Next authorization: `AUTHORIZE_Q1_USDM_RAW_TRADES_METADATA_CENSUS_PROTOCOL`

This checkpoint tested whether the two metadata-census archive families were
structurally fit for the Q1 periodic-flow research mechanism. Binance Spot
`aggTrades` passed the one-month pilot. Binance USD-M `aggTrades` did not: one
raw-trade identifier was referenced by two adjacent aggregate records. A frozen
cross-source adjudication reproduced that condition from the official daily
archive and found the referenced raw trade exactly once in official USD-M raw
`trades`. Aurex therefore rejects USD-M `aggTrades` for this research path and
permits only a separate checksum-only census protocol for USD-M raw `trades`.

This is source qualification, not strategy qualification. It opened no price or
quantity values, calculated no returns, and created no signal, strategy, order,
execution authority, or profit claim.

## Paired Payload Pilot

The protocol froze the mechanically selected earliest development month,
`2020-01`, before either archive was requested. It pinned both published hashes,
byte and row budgets, schemas, timestamp rules, identity checks, clock coverage,
and fail-closed decisions.

| Observation | Spot `aggTrades` | USD-M `aggTrades` |
| --- | ---: | ---: |
| Compressed bytes | 214,923,676 | 102,586,079 |
| Rows | 14,051,798 | 7,436,296 |
| January UTC minutes present | 44,640 | 44,640 |
| Aggregate IDs contiguous | PASS | PASS |
| Timestamps monotonic | PASS | PASS |
| Adjacent raw-range discontinuities | 0 | 505 |

The pair had all 44,640 shared January minutes. The strict pilot correctly
stopped at `STOP_Q1_PAIRED_PAYLOAD_CAPABILITY_FAILED`; no full acquisition was
authorized.

Frozen evidence:

- Protocol evidence hash:
  `f2a6df06336a96050421c449e48a9c8c06aef871b97e73c280a3309c90ca43cc`.
- Transport-amendment evidence hash:
  `e5d4c2ab74975ba9aeed754c767f7bc67c11468646ded77f87e980f623a662bd`.
- Result evidence hash:
  `131d3d3a8925982379cf4186257c2c41852de95c228c6dd97b1c4abe494e3565`.
- Independent audit hash:
  `0e099618d30dec7db047f25a0c530b38c55c6a255d09cac39a831392e303746a`.

The transport amendment preserves six zero-byte Spot request markers from the
first sandbox-blocked attempt and restores only the original actual-HTTP budget.
It changes no URL, checksum, parser, structural gate, or authority.

## Gap Remediation

The remediation protocol was frozen before the discontinuity magnitudes were
opened. It distinguished documented forward gaps from invalid overlap:

- 504 forward gaps covering 1,374 skipped raw IDs over a 10,283,057-ID span;
- skipped-ID fraction
  `0.0001336178531345299359908245184`;
- maximum forward gap: 35;
- buckets: 252 size-one, 232 size 2-10, and 20 size 11-100;
- adjacent raw-range overlaps: exactly 1.

Binance documents the USD-M aggregate-trade endpoint as market trades excluding
insurance-fund and ADL trades. That source rule can explain sparse forward gaps;
it cannot justify two aggregates claiming the same raw trade. The remediation
therefore stopped at `STOP_Q1_USDM_SOURCE_SEMANTICS_UNRESOLVED`.

Frozen evidence:

- Protocol evidence hash:
  `3c69bde0263a3582cba8b3165c515837e0de979819c0537196d1301db1a324ad`.
- Result evidence hash:
  `dea09a8f545b8c1885ac1e1c8f5a6d370ab719559c801b16fb12c4f5d49685a3`.
- Independent audit hash:
  `d4b555735662dfed6ced975c32e1ed3aaf7313c6b93dc95211bbe5f7b4ccfa6f`.

Official references:

- Binance USD-M compressed aggregate trades:
  https://developers.binance.com/en/docs/derivatives/usds-margined-futures/market-data/rest-api/Compressed-Aggregate-Trades-List
- Binance Public Data archive documentation:
  https://github.com/binance/binance-public-data

## Overlap Localization

The checksum-only overlap census localized the single event without requesting a
new payload:

- date: `2020-01-15`;
- preceding aggregate ID: `22154875`;
- current aggregate ID: `22154876`;
- raw trade ID claimed by both: `30414701`;
- timestamp in both records: `1579076873303`;
- overlap depth: 1.

The official daily identities were present for both archive families:

- USD-M daily `aggTrades` SHA-256:
  `db33bbd493ae7b9cb63458def8bb411d54cf93080e5fa1ce0a19e6b3f36ff1de`.
- USD-M daily raw `trades` SHA-256:
  `2de17c79495e43ff4c4435f271c2ead39978bd90678f94330aa5a096583822fd`.

The result permitted only a frozen daily cross-source payload protocol.

Frozen evidence:

- Protocol evidence hash:
  `188a4d2eb16d40d478518b0abd7f86d19e234428ec68cd4047c50920e8cf7b2b`.
- Result evidence hash:
  `488041793701639de79d7528aaae2f05b975668542f8a59b566e1cb025c6b727`.
- Independent audit hash:
  `c9e6170819e16f73b5eb77ae72c780c3bb2acfb188db5a8cf65ac5d59f1cc89a`.

## Daily Cross-Source Adjudication

The exact checksum-pinned daily archives reproduced the same aggregate duplicate.
The raw `trades` archive contained raw trade ID `30414701` exactly once at the
same timestamp. Price, quantity, and quote quantity were neither parsed nor
persisted. The adjudication therefore makes the conservative source decision:

- retain Spot `aggTrades` as the Q1 Spot archive family;
- reject USD-M `aggTrades` as the Q1 perpetual-flow archive family;
- consider USD-M raw `trades` only after a separate monthly checksum census;
- do not reinterpret or waive the duplicate aggregate reference;
- do not authorize full acquisition, parameters, outcomes, Pine, paper operation,
  Testnet strategy orders, production, or live trading.

Frozen evidence:

- Protocol evidence hash:
  `f6d0f34a02dfd03f4027c109ac1a89eda241721dd56d475f355c106d7faf6b15`.
- Result evidence hash:
  `b7332d7eeb2b298f2db897939f6abc7ea29f6c2a658640c84814c5e401a6c7d4`.
- Independent audit hash:
  `998a0f38e432a4cca41709006b821a3af9808c631f6ad95e6f64702929bd3c98`.

## Current Raw-Trades Decision

The authorized checksum-only raw `trades` census is complete under
`docs/36_PERIODIC_FLOW_USDM_RAW_TRADES_METADATA_CENSUS.md`. All 72 monthly
checksum sidecars were present on their first request. No archive payload or
market value was opened.

Freeze and independently check a one-month USD-M raw `trades` payload protocol
for the mechanically selected earliest development month, `2020-01`, binding the
existing qualified Spot `aggTrades` evidence. Do not request the raw-trades ZIP
before that protocol passes. This authorization does not permit parameter
selection, return testing, Pine, paper operation, Testnet strategy orders,
production, or live trading.
