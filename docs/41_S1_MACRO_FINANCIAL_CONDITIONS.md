# S1 Macro Financial Conditions

Status: `STRATEGY PREREGISTERED / BTC SOURCE PROTOCOL FROZEN / RUNNER NOT IMPLEMENTED`

This record governs the first successor research family after the terminal Q1
source-sufficiency failure. It does not claim a market edge and grants no trading
authority.

## Mechanism

- Mechanism ID: `S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE`.
- Instrument: Binance Spot Testnet `BTCUSDT`, long or cash, maximum effective
  leverage `1x`, simulated equity `$100`.
- Ex-ante premise: easing U.S. financial conditions may improve global
  risk-bearing capacity; tightening conditions imply cash, never a short.
- The mechanism is independent of the retired trend, breakout, Jam reversal,
  momentum/path-quality, volatility-managed beta, funding-carry, cointegration,
  clock-phase, passive-liquidity, cross-venue arbitrage, options-VRP, and periodic
  derivatives-flow paths.
- No threshold, lookback, rebalance rule, return, strategy candidate, signal, or
  order has been created.

## Evidence Partitions

- Development: `2017-08-17` through `2023-01-01`.
- Historical validation: `2023-01-01` through `2025-01-01`.
- Contamination washout: `2025-01-01` through `2026-11-07`.
- Future holdout: `2026-11-07` through `2027-05-07`.
- Forward: `2027-05-07` onward.

All outcome access remains false. The future dates are intentional: Aurex cannot
manufacture untouched evidence that does not yet exist.

## Frozen Lineage And Charter

- Lineage ledger evidence hash:
  `0e908e278455018f195f0b3a6269e65e67b415889a2fd0bd3d3c7b0df502bdab`.
- Independent lineage audit hash:
  `590d5f5a848c52dc3c4455ebb7ce2d70db8250b6048fd76dbc0e63e825dbb41d`.
- Charter evidence hash:
  `f5f0aa9980df16c4964abe1a41512abeccce2f009a2743492e2f0e1ce86d0c7d`.
- Independent charter audit hash:
  `79cc6e3fda4f1104c2c1df967e34c537695564f2bb29b7c7634863df57ab7239`.

The charter requires point-in-time NFCI vintages. Revised current NFCI values may
not be substituted because doing so would leak later revisions into historical
decisions.

## Source Adjudication

The first metadata protocol used four `HEAD` requests and read zero body bytes.
Three download-style endpoints timed out while the keyless structured API returned
the expected HTTP `400`. Decision:
`STOP_S1_POINT_IN_TIME_VINTAGE_TRANSPORT_UNAVAILABLE`; audit hash:
`9720c07355cdafedd0a1d3e8486311770cdc70e5260cfd1981532c4d3cea9a9e`.

A narrow v2 amendment changed only the transport to open a `GET`, inspect headers,
and close without calling `read()`. Both vintage URLs returned HTTP `200`; the
structured API remained key-gated. Application body bytes remained zero. Result
hash: `14b097c72afef189cdbccc9493618c5773e736a35b867615e60685dfa86b9532`;
audit hash: `18bebaca422d07f42b2cbda77ab5a6433c53740982c388743d081eb600318877`.

The first raw pilot then proved that `fredgraph.csv` does not honor the supplied
`vintage_date` for this use. Both 2020 and 2021 requests returned the identical
51,425-byte current snapshot, hash
`4b489d3be3574ad5c35ffba7a74869f4db1b8ad8d792230f7ed5f57cca038896`,
ending `2026-08-21`. Aurex detected 347 and 294 post-vintage rows and stopped with
`STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED`. Result hash:
`e3249edba089c7a8ebe76ced03958ade36625d4bc759783b305e19b0f731e209`;
audit hash: `39994116cfcd85e4e049509fce104a56d9b5e7dc9c164070548d32ba1effdb11`.

The separately frozen recovery changed only the source transport to the official
ALFRED graph host/path. It passed all ten frozen gates:

- `2020-01-01` vintage: 2,555 rows, last observation `2019-12-20`, 12-day lag,
  42,751 bytes, hash
  `8b7c25125a0bc1d82d15b82df2e9ab7ad08dd2a407e51788ae3f453c2b9d4b01`.
- `2021-01-01` vintage: 2,608 rows, last observation `2020-12-25`, 7-day lag,
  51,399 bytes, hash
  `50da643cbf83dec10f53913806479aab1220959f5c9bb720c67412ee730fa02a`.
- Both files have exact vintage-suffixed headers, increasing unique dates, valid
  decimals, and zero post-vintage observations.
- All 2,555 overlapping observations differ, confirming material point-in-time
  revisions; the later vintage adds 53 observations.

Recovery protocol/result/audit evidence hashes are:

- `d60d13bbc46a93d02edd7951172e612dd04e655cde026a4be00e800e5f1bd312`
- `274e9981103b3e31aea001e543f62d29d0d6941a1529b00cb5b037a854c75472`
- `f658ef8639cd5ad17216389687301addf737bcfa480b6064298f5b5036905f56`

## Full Development Acquisition

The immutable full-acquisition protocol defines 281 Thursday vintages from
`2017-08-17` through `2022-12-29`. Its protocol evidence hash is
`ccbff64f29ce5d85eb52dded23df1c393bb1a5ab4d5ce2c2874d8f284b87195e`;
the independent pre-network audit hash is
`3de2d5970b537a30eb3c5be1c39571b146bdac8116d2b6dc4be0ea20fff4d819`.

The v1 execution addendum was superseded before any network request because a
synthetic interruption test exposed a restart defect after atomic raw-file rename
but before response-marker persistence. The preserved v1 addendum/audit hashes are
`c6279a10bb2daf4e8b7bba9fe4dd9aa1f37047aeefed1f3dd48f3aa713e51f76`
and `e0dd54aef0058539f105877fd3071d9bfacecc6d8c728fb4027f99586b5909bf`.
The narrow v2 amendment repaired that restart path and made CSV parse failures
terminal target evidence. Its amendment/audit hashes are
`74420379ca8d30786c9d81a269052574d1d9aae90f3e85d0e952d14ad1fdbeda`
and `ae7a963a0c68deafd0ff9970ccae6b097c4ada036fb3b19409f8a58f9cb334c5`;
the frozen runner contract hash is
`951318f4e7d27efa73420e69bff31fef219e647c36ed63ad12924ab94b2f9b8d`.
Pre-correction requests and payload bytes were both zero.

The completed acquisition produced:

- 281/281 classified and complete vintages with zero failed targets.
- 281 GET attempts, so every target completed on its first attempt.
- 13,056,155 network bytes exactly matching 13,056,155 persisted raw bytes.
- 281 distinct payload hashes and all 10/10 frozen source gates passing.
- Checkpoint hash
  `92d1a8931c14b476c8217337f91cd7aa0f472ab6b7f525613f45abda982a0ae4`.
- Result hash
  `4e94883da8e48c1dc6282370140084101f123dad2fd427dacee7708ee14c0c5f`.
- Independent audit hash
  `f6669c6d80cd73f330a4d2c09a410e4eabb4b7628152bbd15636e12f13400ab1`.

The independent audit rehashed all 281 raw CSVs and all 562 request/response
markers, reproduced the 13,056,155-byte aggregate, and reconstructed the result.
Decision: `PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION`.

## Causal Development Normalization

The normalization protocol was frozen and audited before any raw NFCI value row
was read for transformation. It permits exactly one row per source vintage with
these fields only: sequence, target ID, source vintage date, selected observation
date, release lag, exact source decimal text, source path, and source SHA-256. It
forbids deltas, rolling statistics, signals, positions, BTC values, returns, and
PnL. Protocol/audit hashes are:

- `998b775e60aad081f421b80be678fd209348df149e8a7cc8f1f05b368e0f6041`
- `2ef0d3405e903c01cdbed8648c26a244c5878bd26bcb2532c5a7f80536d0d087`

The source-bound runner passed seven synthetic causal/parser tests before its
one-run authority was frozen. Execution addendum/audit hashes are
`4190161d1e4f8928b5d6848f29b01d1e3bd31759fa280d1c12e3c81f319a3c34`
and `110ca7006f8014c50df7083e83d39f5218ef712b981e1209f53e291fce288db1`;
runner contract hash is
`a9cff8a1a1ed6f08ea1b55cde5dcf6f8949cab5044bc7b82fb03655cb8045908`.

The completed normalization produced 281 rows in a 107,885-byte deterministic
JSONL dataset with SHA-256
`789829ee9a9b84de528507c660c7abdcd5bd34a3c4a5d9cae1a46b7cd2ac927b`.
Observed release lags range from 6 to 20 days. Result hash:
`d9816fce4035ec50368eb1d0541f287ea261b9f64c5dee779fc671a998d07f4c`.
The independent audit re-read and rehashed all 281 raw files, reconstructed every
row and the exact dataset bytes, and passed under hash
`5070de85bafb6b657055d4e89e49927b2494c1a3116c700edac5d28bfc67e58d`.
Decision: `PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION`.

## Macro-Only Feature Construction

Before parsing normalized values, Aurex froze exactly three features:
`nfci_level`, `nfci_change_1v`, and `nfci_change_4v`. The protocol requires exact
`Decimal` arithmetic, a four-vintage warm-up, 277 output rows, and no rolling
means, standard deviations, z-scores, percentile ranks, streaks, strategy rules,
or market fields. It also caps future strategy candidates at four. Protocol/audit
hashes are:

- `d2ecbea9b31bc07e0cfec0901f3f262a1dd7e358148ec5e317ea972b51c16ce0`
- `2a1486c2ab3c9c5be5b3cc07a905ad3bcba6f4a961988cf3023f2797526acd8f`

The feature runner passed synthetic exact-arithmetic, warm-up, hash-tamper, and
serialization tests before one-run authority was frozen. Execution addendum/audit
hashes are
`2743b1a1f8234d7e82687fc8985dee044855bb13cc33bfc56f54018fb54f5d81`
and `de8fdc92fa19313120776831e1405623057aee5a598e9f75b782ed7c80f2db7f`;
runner contract hash is
`3b85b9bc81fa47f6e0aa5745128f2d4ef3d2a1bde35c30283da00eb3e345515a`.

The completed run produced 277 feature rows in a 90,632-byte deterministic JSONL
dataset with SHA-256
`db93ee6954fee447cba66b3d873282da4d289f5ef6a63446d6ad036f787b24d6`.
Result hash:
`a59707114ec19c2576e72071fcba5ad7fa36e5232629a40fe1e9704f122f7664`.
Independent reconstruction matched all input row hashes, all feature rows, and the
exact dataset bytes under audit hash
`da54d8a9ee1097994b1b3fc6edc81f844abcb7f9f046426c1f0a51732a0cc1f3`.
Decision: `PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION`.

## Outcome-Blind Strategy Preregistration

S1 has one promotable primary rule: long BTC only when both one-vintage and
four-vintage NFCI changes are below zero; otherwise hold cash. Three simpler rules
are diagnostics only and may not rescue or replace a failed primary. All rules use
1x or cash, and equality means cash.

Signals become executable at 00:00 UTC on the Friday after each Thursday source
vintage. The frozen development path has 276 weekly intervals and 277 required
execution opens. Costs apply only when the binary position changes: 10 bps
commission plus 5 bps slippage/spread per fill at base, and 22.5 bps total per fill
under 1.5x stress. Twelve primary-only gates cover interval count, transitions,
20%-80% exposure, base/stress profitability and profit factor, base/stress drawdown,
positive full years, and an 8-week stationary-block-bootstrap lower bound. Any
primary gate failure stops S1; diagnostics cannot be promoted.

Preregistration/audit hashes are:

- `6ca639fa0ff744dc13c1c8db229d46a8a7710b77bb49eded2ac8cae4a022816f`
- `6d10abaf857bba7dd28c10e19957bdffc7fef7bc67da96d7dfd5060d3ba17c00`

## BTC Execution-Price Source Protocol

The source protocol binds 277 official Binance Spot daily `BTCUSDT` `1h` archive
and checksum pairs from `2017-09-15` through `2022-12-30`. Each target must match
its published SHA-256, contain exactly one safe expected CSV member, expose one
unique positive finite 00:00 UTC open, and preserve request/response evidence. The
manifest is bounded to 1,662 possible requests and 55,541,824 payload bytes.

Protocol/audit hashes are:

- `bed364619aa4a141d339e405948e6a0a4113afb5c0ee1dedf5c288346255ffe2`
- `19cf011a7f817b221f03748d9db48a614d235c7a79de8cc6e737ad20f3bce1bd`

No request, payload byte, BTC value, return, candidate outcome, or order was opened
during either freeze.

## BTC Source Execution And V1 Failure

The v1 runner was implemented, covered by 18 adversarial tests, and frozen under
execution-contract hash
`6f521177bc363094d434067e83394317a85ba3736a95b64724537ddc240f7b28`.
Its independent contract audit hash is
`3a08711647a12b8f173ce49fcfc8286e3831a20cf4c4d26ba3722f9c9d642113`.

The bounded source run stopped at target 22. Binance's published, checksum-valid
`2018-02-09` daily archive contains only 14 bars from 10:00 through 23:00 UTC, so
the exact 00:00 activation bar did not exist. Result hash
`f444378a3b89b49812615b8b9313147e32e2ecb646348675054893bea99a57fd`
is terminal. Independent audit hash
`b98dff769d6537ee55d00705ea7fe585868390f7c7d0651ed99f91177771949e`
confirmed the source gap with zero return calculation and zero orders.

Post-run audit also found that v1's partial-checkpoint verifier compared a partial
classified prefix to all 277 targets with strict ZIP length semantics. It did not
cause the source-gap stop, but v1 must not be represented as fully crash-safe.

## S1.1 Timing Amendment And Complete Source

S1.1 is separately versioned. Before any remaining date was inspected, it froze the
rule "select the earliest valid Binance 1h open within the target Friday." The
amendment declares the 21 development execution prices already materialized by v1,
zero returns, zero strategy outcomes, and development attempt index 2. It changes
no macro hypothesis, candidate rule, role, cost, gate, or date partition.

- Timing amendment/audit hashes:
  `972e49bc1e732bfe567417db63a0b81b26f093517ec7f2532af67b06d7737ada` /
  `cd53258a7cd8987b4dac63a8aadd6648cd59d37b6cd94525959b3c56fd24e3fe`.
- Source protocol/audit hashes:
  `f6cbee32ed45a14388e116d3e9038a9b32afe9fc5b3ddc0132746e431413f419` /
  `ceb7fffa67ece3a06fec4e9ec0cdb46e03d9b8254a82691508732758a7fbff05`.
- Execution contract/audit hashes:
  `fdb47fabbf335b253c97fbd3cc5b146399dc40331d018ef3e7569186e264df6f` /
  `41055aa1222a1837d520108996f7e56a0a04a7174c123f1480a8e3c5b9523558`.

The complete run passed all 11 source gates: 277/277 targets, 22 exact-hash v1
reuses, 255 network targets, 510 first-attempt requests, and 429,427 new payload
bytes. Exactly one activation was delayed, by 600 minutes; the other 276 selected
00:00 UTC. Dataset SHA-256 is
`48302226780765f625c1f2241a73d09f07c75227515d8647cdb8ab9759e4fd57`.
Result/audit hashes are
`87e413172462f7006332a53be3ba74b6b7bdd1c61e03d0f7f71e218322e3caa0` /
`5685b46d8ef2c787ce606025ee76d75bbf00a830237f692b5ec7b6145ac053f3`.

## Development Outcome And Terminal Decision

Outcome formulas were frozen before parsing either dataset. Protocol/audit hashes
are
`412c8bc189ac723a3fa211b9a2ebf8b35dea8c1e6e94df33f183e07f7517c6da` /
`0da15939a68f5a5ad548d40f390bf02e27f9f623f1607eae42e55c8de6d2bc79`.
The one-shot execution contract/audit hashes are
`adcb48e8c808ab69f0354e171be6e58b44b11ed930ff7b807cc283d5c9900767` /
`d0fc778ecbd2149339e8c7c411b821a814c6b7e5d9fe7872fc16d581a3e0edab`.

The sole primary passed 7/12 gates and failed 5. Base net return was
`7.6958%`, but base profit factor was only `1.01395`, maximum drawdown was
`66.3009%`, only 2/5 full calendar years were positive, and the stress-bootstrap
95% lower mean weekly return was `-0.48377%`. Stress net return was only `0.8049%`.
These failures reject durability and capital suitability. Diagnostics remain
non-promotable; the profitable four-vintage diagnostic also suffered about 74%
drawdown and cannot rescue the primary.

Outcome result/audit hashes are
`8d900beb2dcbfcb0d11fed1f8ee0a99ecfa812e03900dae21a886973f86cc317` /
`ab1f10d0208560933e048f1fb93e5b03f0988048e7c4b5e6057dba14b0c2495d`.
Decision: `STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED`. Validation and holdout remain
sealed. No Pine, paper, Testnet strategy order, production, live, or profit
authority exists.

## Controlled Post-Failure Analysis

The descriptive postmortem was frozen before its metrics were calculated. It bound
the terminal result, independent audit, and 1,104-row development ledger; fixed
seven analysis questions; permitted zero parameter variants; and prohibited
diagnostic rescue, validation, holdout, paper, Testnet strategy orders, production,
and live execution. Protocol/audit hashes are
`f4b7ebd92fd1a149d784cce1840c08180d8c942ff2e54b6047313f91ba359c9b` /
`5b88bb69058ccde7f839bcb8405123fdd8db283920bccb000ddaf8cfbd431a83`.
The separately frozen execution contract/audit hashes are
`84a4d09a653ca932e837adaa515faa47301a4a38cea5915839fd8ded22209064` /
`13a27548fa293a6082b9fa8311bb321162cf4f8318aeeeacc777017caf79945b`.

The reconstructed cost-free primary exposure returned `22.9048%`. Eighty-eight
charged fills reduced final return to `7.6958%` at base cost and `0.8049%` under
stress; only `10.4588%` of the base positive return remained under stress. This
does not mean costs alone caused failure: base PF remained `1.01395`, and the base
maximum drawdown was `66.3009%`. The maximum drawdown ran from `2021-04-16` to
`2022-11-25` and did not recover before development ended. The primary had 44 long
episodes averaging `1.9773` weekly intervals and a nonzero long-interval hit rate
of `51.7241%`. The five largest stress gains supplied `40.1360%` of all positive
stress PnL; the five largest losses supplied `37.9805%` of all stress losses. Two
of the three diagnostic position vectors were identical, reducing them to two
unique diagnostic behaviors.

Result/audit hashes are
`0db0fd10424b5bcc07a7f10c42c88d3a3843c0dddbcdc6a29c6665529c192988` /
`be6340eb9bf978c4cff9f06427169cd1b03a76f2a5030aa028aa4343c2f97ffe`.
Decision: `RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE`.

## Exact Next Action

S1 and S1.1 are retired. Do not tune the primary, promote a diagnostic, reinterpret
the positive gross or base return, or open validation. The only permitted program
action is `AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY`. S2 must be economically
distinct, bind the complete predecessor and multiplicity history, and freeze its
source and feasibility requirements before any new market outcome is opened. Pine,
paper, Testnet strategy orders, production, and live remain unauthorized. Real net
profit remains `$0`.

## Source References

- <https://www.chicagofed.org/research/data/nfci/current-data>
- <https://alfred.stlouisfed.org/series/downloaddata?seid=NFCI>
- <https://alfred.stlouisfed.org/help/downloaddata>
- <https://fred.stlouisfed.org/docs/api/fred/realtime_period.html>
- <https://fred.stlouisfed.org/docs/api/fred/fred_vs_alfred.html>
