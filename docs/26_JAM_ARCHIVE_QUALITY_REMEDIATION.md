# Jam Archive Quality Remediation

## Status

Complete and independently reproduced on `2026-08-04`.

This stage used the existing checksum-verified BTCUSDT 2019-2022 Binance Spot
monthly aggregate-trade and one-minute-kline archives. It made no network request
and calculated no feature, threshold, directional label, return, PnL, ranking,
signal, order, or strategy outcome.

## Intended Use

The intended future research mechanism is aggressive sell-flow exhaustion and
reclaim. It requires aggressor-side trade flow, which is observable in Binance
aggregate trades through the buyer-maker field and is not available in ordinary
candles.

The source decision therefore asks whether aggregate trades can be the historical
feature authority while official one-minute klines remain an independent quality
reference. It does not ask whether the mechanism is profitable.

## Frozen Boundary

Protocol:

`data/evidence/jam_archive_quality_remediation_protocol_v1.json`

Protocol evidence hash:

`128eb77a416ba9ebd47154639fe383f1f9b9c0058c149c8f7dc62c4e5e24c57a`

Protocol-file SHA-256:

`aa48c6342792f2d34777f4dce5773619455911607d7132e32e5a3a3121ffb95e`

The protocol binds the prior full-acquisition protocol, failed result, independent
audit, and 96-archive raw manifest. It freezes three chronological evidence roles
before outcome access:

| Period | Role | Outcome access in this stage |
| --- | --- | --- |
| 2019-01 through 2020-12 | Development | Prohibited |
| 2021-01 through 2021-12 | Sealed validation | Prohibited |
| 2022-01 through 2022-12 | Sealed holdout | Prohibited |

The consumed 2023-2025 Jam period remains contaminated and excluded. The existing
2026 exploratory and forward-lock boundaries remain outside this historical pool.

## Reconstructed Defects

The runner inspected all 48 kline archives, compared both members of the official
2021-12 aggregate-trade archive byte-for-byte, and reconstructed every mismatch in
the 18 failed cross-family months.

| Quality dimension | Reconstructed result |
| --- | ---: |
| Missing kline minutes | 4,009 |
| Missing-minute intervals | 21 |
| Invalid kline rows | 8 |
| Cross-family mismatch minutes | 144 |
| Raw-trade-count mismatches | 144 |
| OHLC mismatches | 135 |
| Base-volume mismatches | 144 |
| Quote-volume mismatches | 144 |
| Taker-buy base-volume mismatches | 142 |
| Taker-buy quote-volume mismatches | 142 |
| Aggregate minutes outside kline coverage | 0 |
| Unique quarantined minutes | 4,161 |

The 2021-12 canonical and nested aggregate-trade members both contain the same
number of bytes and have SHA-256
`4a2d823de4b60232442c92cc44d109dc31da89ca988d5111c9f07209c462fa54`.
The duplicate is therefore a packaging defect, not conflicting market content.

## Source Policy

The following policy passed:

1. `BINANCE_SPOT_MONTHLY_AGGTRADES` is the primary historical source for the future
   Jam mechanism.
2. `BINANCE_SPOT_MONTHLY_KLINES_1M_QA_ONLY` is a secondary quality source. It may
   reveal defects but may not silently overwrite aggregate-trade values.
3. The top-level 2021-12 aggregate member is canonical only because its bytes are
   identical to the duplicate member.
4. A missing paired-source minute is an observability gap, never a zero-flow minute.
5. Aurex may not synthesize a tradable bar across a gap.
6. Every missing, invalid, or mismatching minute is quarantined.
7. Any future stateful feature must reset at a quarantine boundary.
8. Eligibility may resume only after the feature's full maximum causal lookback has
   elapsed. No numeric warm-up exists yet because no feature lookback is authorized.
9. Pine cannot be treated as exact parity for aggressor-flow logic. A later
   qualified implementation would be backend-authoritative; Pine may visualize.

Quarantine manifest hash:

`618df63c38ca848e7d34188d20e99f3eac330f76cec5226bb6046d33354c9d27`

Issue manifest hash:

`477bdb334689c83f805dcf123e365692ea70c64bf9965005606198227eb7ae54`

## Evidence

Result:

`data/evidence/jam_archive_quality_remediation_result_v1.json`

Result evidence hash:

`02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`

Result-file SHA-256:

`db1d1321598e07ba24d30aacd8b41cc28af0db186ccf4de7789a5bb2f7b18097`

Independent audit:

`data/evidence/jam_archive_quality_remediation_audit_v1.json`

Audit evidence hash:

`146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`

Audit-file SHA-256:

`e3b880637f65d73a35f4dd8c56a824f571223a586756346d97c3d80399890c8f`

The independent pass reread the raw files, repeated the 2021-12 byte comparison,
reconstructed all 48 kline months and all 18 mismatch months, and reproduced the
saved result exactly.

## Decision

`PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION`

Exact next required authorization:

`AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`

That future gate may define causal source-to-feature transformations and their
quality-state behavior. It may not inspect returns, tune thresholds from outcomes,
create a strategy candidate, begin paper trading, submit Testnet strategy orders,
enable production/live execution, or use real capital.

Aggregate-source qualification is not evidence of edge. Aurex still has no
qualified strategy, no reliable trade signal, no live authority, and `$0` real net
profit.

## Verification

Closeout verification passed:

- frozen remediation protocol rebuild
- result and audit model/hash validation
- two complete raw-file reconstructions
- 65 focused Jam lineage tests
- repository-wide Ruff
- all 1,036 Aurex tests in 790.27 seconds

The only test warning was the existing Starlette/httpx deprecation.

## Post-Remediation Feature Contract

The separately authorized feature-specification stage completed on `2026-08-04`.
It preserved the aggregate-primary and 4,161-minute quarantine policy, then froze a
17-feature measurement system across 133 causal minutes without inspecting a real
market row or outcome.

See `docs/27_JAM_SUCCESSOR_FEATURE_SPECIFICATION.md`. Specification evidence hash:
`8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`.
Independent audit hash:
`760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`.
The exact next gate is
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS`.
