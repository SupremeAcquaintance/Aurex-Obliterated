# S5 Bitcoin Core Accepted Development Breadth

## Status

S5 has passed source acquisition and corrected normalization. It is not a qualified
strategy and has not read a BTC market value.

- Mechanism: `S5-BITCOIN-CORE-ACCEPTED-DEVELOPMENT-BREADTH`
- Decision: `PASS_S5_GITHUB_CORRECTED_NORMALIZATION`
- Next authority: `FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`
- Qualified strategies: `0`
- Orders submitted: `0`
- Real net profit: `$0`

## Research Claim

Latest checkpoint (2026-09-26): source repair and amended measurement are complete.
See "Complete Release Repair And Audited Measurement V2" below and
`docs/46_AUREX_DELIVERY_REBASELINE.md`. Older
"sole next authorization" entries below are preserved historical checkpoints.

The frozen hypothesis is that sustained breadth in accepted Bitcoin Core
development, peer-reviewed integration, and official release continuity may reduce
protocol-software maintenance risk and may support allocator confidence after the
evidence becomes public. This is a causal hypothesis to test, not an established
relationship. Missing or ambiguous evidence must select cash in any future
candidate and can never authorize a short position.

All repository and GitHub history collected so far is outcome-aware. Historical
measurement can reject S5 or justify prospective observation, but it cannot qualify
S5 for paper, Testnet strategy, production, or live execution.

## Frozen Source Boundary

The local Git history is pinned to Bitcoin Core commit
`dc0395c5858a1d55239b82a834e5075cf2069219`. The GitHub pull cohort is bounded by
creation time `2026-09-02T21:43:33.504800Z`.

- Full Git graph: `50,395` commits.
- First-parent history: `17,543` commits.
- First-parent merge commits: `16,721`.
- Merge messages with a recognized pull number: `7,961`.
- Merge messages unrecognized by the frozen patterns: `8,760`.
- GitHub pull records in the frozen cohort: `24,398`.
- GitHub records classified as accepted: `16,279`.

The GitHub bulk acquisition preserved 245 canonical pages containing 24,407 unique
records, excluded nine post-cutoff records, and consumed 246 historical request
attempts. Bulk result/audit hashes:
`3c2bd020ee115e0d28e75fc80c977ffef2a4bad8ac6ad4cd5f4219380a25e082` /
`cc1a4604a6d8c2819dd629900374f60cbac7ff50499eb14af34f63c2bc1acc29`.

## Preserved Failure Lineage

The first normalization attempt stopped rather than concealing a false assumption.
It produced 16,167 exact mappings, left 554 first-parent merges unresolved, and
found 112 accepted GitHub records unmatched to one canonical merge. Its result hash
is `02f461aeb23e00479a9044e7017daa4eaa569f296cd69d8fdbc7dd7e6e6c3a89`.

An independent adjudication established that one accepted pull per first-parent
merge was not a valid universal invariant. Adjudication protocol/audit/result/result
audit hashes:

- `f067e7e143096e2f754e26e466edc2936a24251024713f6767cb4677699bb451`
- `f8f362463b34cf10d17d1516ed89c2515b940b3de48e93dabc32da038f62eb7e`
- `3c4cc196661cf7356ec6e54e752c850fd79f98f113180f7e6e23b388bab4acd5`
- `f5d2a5016f4e43285d67c93935768b0b7e251be0437bc0c92afd9a1150f54d0f`

Two targeted acquisition implementations also stopped on local defects or an
invalid response-shape expectation. Their immutable STOP result hashes are
`60fd81a117139a228fbe6155983527b96c4ccafebbae43ed22c2672634581287` and
`e320a2af40931dbc4da637d6c28084399ac0e16b0822ae56df37fa4874c7078c`.
Neither was rewritten as a pass.

The corrected v3 targeted acquisition covered the exact 194-record correction
union. It preserved 186 HTTP 200 responses and eight HTTP 404 responses. All 83
recognized targets with an available response were adjudicated, and 75 recovered
by exact second-parent-to-head identity. Targeted result/audit hashes:
`e7c059f0a01998e2af13b72c1ee4d5a6c01f05184f79c3b915dac619f08e2d50` /
`5e6c1f1b7dfd5a28395ec28a0f9cfed08ad053203edacaeb38628687c7edacac`.

## Corrected Normalization Contract

The corrected protocol keeps three event universes separate:

1. Canonical first-parent Git integrations, with one canonical pull owner per merge.
2. Source-verified accepted GitHub pull events, including accepted pulls that do not
   own a canonical first-parent merge.
3. All GitHub-accepted pull events, retaining eight explicitly unverified local
   source links for sensitivity analysis only.

Targeted metadata never overwrites the frozen bulk snapshot. A recognized recovery
requires the census pull number, direct response pull number, and exact Git merge
second-parent `head.sha` to agree. Ambiguous many-to-one source links are retained
but never guessed into canonical ownership. The two disclosed many-to-one pull
groups are `(25882, 25891)` and `(26081, 26084)`.

Event time is GitHub `merged_at` when available and otherwise the local Git
committer timestamp, with the timestamp source retained on every canonical row.
Author dates are never treated as publication time.

Corrected protocol/audit hashes:
`d8a6c5bf331c75a127e47f63c3e2f14c6d3a1292f9015666009da3a1b106bc95` /
`b664ae816c730550f7876aaba41c7090797b848bfdfeaf9c2c0fa420d36fff8c`.
Execution contract/audit hashes:
`9a374dc928e74d3708e587ed5e9eec436225dc560f35d62b036c277a69779477` /
`bec0bd3756616fe3161b74f18318111dc0d9a4bd55365c9af65114f552f8ced6`.

## Corrected Outputs

The one authorized run passed all 19 gates in 40.666 seconds. It executed two local
Git processes and zero network requests, BTC reads, return calculations, candidate
creations, or orders. Result evidence hash:
`a205e0759b235fae0810ae9203afa4dd81087f52ce782cd4e8c00c670fdd45a5`.

- Normalized pull rows: `24,398`; file hash
  `1075bcd84b27a8408c26d9beab481b7b6df762a922267e57bae05a1725ee5888`.
- Canonical merge mappings: `16,242`; file hash
  `e13d5aba80bcb688abf004fc8813dfd81a3083c1bc295859267b9baac001e564`.
- Target resolutions: `194`; file hash
  `6e11c4183adfde890d3188a6ae20bdce1700faf3651e76f2b0975051a0968bd2`.
- Accepted-source coverage rows: `16,279`; file hash
  `5975b299d2b6e291ac1961038e067150372846d4d54e11a84ca5405781b3627c`.
- Corrected unresolved Git merges: `479`; file hash
  `992c21f70d99e1243296d851b836119ff7825cd54574ac98ef32f65bf0a66de8`.

Exactly `16,271` accepted GitHub events have a verified local source link; eight are
explicitly unverified. The canonical Git integration universe contains `16,242`
events. These counts are not interchangeable.

## Independent Result Audit

The independent audit strictly parsed and rehashed all 57,592 output rows, reran
the two permitted Git processes, reconstructed all five datasets, and rebuilt the
result exactly. It made zero network requests and read zero market values. Audit
evidence hash:
`d0d66d194c6136164999341f5e044bf60d8f2e7b585531a863ba599d54254648`.

The complete S5 source, acquisition, correction, and normalization unit suite passes
`129` tests.

## Truth Boundary And Next Step

This checkpoint proves deterministic source linkage and explicit uncertainty. It
does not prove source-history immutability after the frozen snapshot, a causal link
to BTC returns, predictive edge, a reliable signal, or profitability.

The sole next authorization is
`FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`. That protocol must bind
the primary and sensitivity event universes, complete-month availability rules,
identity uncertainty, many-to-one handling, release-tag handling, exact formulas,
resource ceilings, deterministic serialization, and a future runner boundary before
any measurement output is computed. It may not read BTC values, calculate returns,
define a strategy candidate, deploy Pine, operate paper or Testnet strategy orders,
or authorize production or live trading.

## Complete Release Repair And Audited Measurement V2

The first repair fetched 42 stable tags but omitted 90 annotated maintenance-branch
tags through an invalid master-ancestry restriction. Its independent audit rejected
the nominal pass. A separate repair acquired all 132 frozen stable refs, preserving
the original repository and the incomplete 42-tag repository. The complete-source
audit passed with hash
`f224e7b99256ac04b0ffd8762076cd75f528e7cb88dd402371a2e126ab128e6c`.

The amended protocol keeps the original 212 months, seven-day availability lag,
event universes, component formulas, and identity bounds. Annotated releases use
tagger time without requiring master ancestry. The 28 lightweight tags retain the
cutoff-reachability condition and an explicit historical-existence limitation.
All 132 tag rows are preserved; all fall within the fixed measurement window.

The amended runner executed exactly three local Git processes and no network. It
emitted 212 rows and proved that every non-release field matches v1. A separate
monthly arithmetic implementation reconstructed the entire JSONL output exactly,
including event, actor, component, and release manifests. The original v1 output
and its rejection remain unchanged.

- Monthly output SHA-256:
  `ee98f762806770d3c1b17f26a14fc718db9dab75318c734d20e69d6cec23a6f1`.
- Result evidence hash:
  `69d42d1c9e8754d8fa43a0b4ea1aa5cd52904f150c1475e25a572cba34e39c71`.
- Independent audit evidence hash:
  `37f27c2ddfb81aaad18424aaa6ed9224da5fe086bb4f8490514caba0c796cfd1`.

Measurement construction is complete. Predictive edge remains untested. The frozen
S5 prospective validation and holdout end in November 2027; historical results
cannot qualify this lineage. Under the 2026-09-26 delivery rebaseline, further S5
outcome research is deferred while platform readiness and execution evidence are
reconciled. No candidate, signal, trading authority, or profit was created.

## Measurement Protocol And Rejected First Run

On `2026-09-08`, Aurex froze and independently reconstructed the outcome-blind
monthly measurement protocol before parsing any source row. It separates 16,271
source-verified accepted pulls as the primary universe, all 16,279 accepted pulls
as a sensitivity universe, and 16,242 canonical first-parent integrations as a
corroboration universe. It predeclares 212 complete UTC months from January 2009
through August 2026, a seven-day availability lag, identity bounds, deterministic
component keys, stable-release tag rules, and 17 integer measurement fields.
Protocol/audit hashes:
`0d4f9dbc73675a0e625971a9a53181bcd4a2b707ebe02f01a28edfc4c65478d0` /
`0b6ad1358d206822ab530447bc184dfb98ecd12d209e8cd8c2f3675f17c70064`.

The exact runner and its three-process Git contract were then frozen and audited
without executing a measurement. Execution contract/audit hashes:
`da08133f957e4129421e5e708b93c87212d4273b3da8bdc1daed5b62e86a0154` /
`68a683dc72b1292131929af5ce1f23ef960bd672d7525bd09afbbaef69ca7c71`.

The one authorized run emitted 212 internally valid monthly rows in 7.250 seconds.
It accounted for 16,267 primary events plus four incomplete-month exclusions,
16,273 all-accepted events plus six exclusions, 16,238 canonical integrations plus
four exclusions, and all 479 unresolved merges. Output/result hashes:
`56a54bee72f77102e21c03975eb7a32e95b8eb2ff68882dd32fbe8a01f8bddd8` /
`6d0d3efc7da6dc5d909bea7bca0e892e8ea45c8ab9541c521109d644b85d7c3c`.

The independent result audit rejected the nominal PASS. The frozen Git repository
was acquired with `tagOpt = --no-tags`; its packed refs contain only
`refs/heads/master` and zero tag refs. Consequently, 212 zero release counts mean
"release metadata absent," not "no releases." Treating those values as valid would
be a source-scope error. The original result and output remain immutable evidence
of the defect. Rejection audit hash:
`e8b8970a7af07f2298f4b1cf9e53d656c6dc0bcd7396838968ffda915ea5afdd`.

Decision: `REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT`. The sole next
authorization is `FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY`. That
protocol may design a bounded official Git tag acquisition into a new isolated
evidence repository. It may not mutate the frozen no-tags source, access BTC values,
calculate returns, define a candidate, create a signal, or submit an order.
