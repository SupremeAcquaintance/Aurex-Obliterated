# S2 Bitcoin Settlement-Demand Charter

Status: `FROZEN_CHARTER_ONLY_NO_OUTCOMES`

S2 is a distinct successor to the retired Q1, S1, and S1.1 lineages. It is not a
rescue, rename, parameter adjustment, or combination of a failed strategy. The
charter selects one source-feasibility hypothesis and grants no outcome or trading
authority.

## Mechanism

- Mechanism ID: `S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT`.
- Family: `BITCOIN_ONCHAIN_SETTLEMENT_DEMAND_BREADTH`.
- Economic actor: Bitcoin users paying for confirmed on-chain settlement.
- Future product boundary: `BTCUSDT` Spot, long or cash, maximum `1x`.
- Future decision cadence: weekly.
- Raw measurement families: confirmed non-coinbase transaction count, confirmed
  transaction fees in satoshis, and agreement between those two measurements.

The ex-ante hypothesis is that persistent joint broadening in confirmed settlement
activity and user-paid fees may identify network demand that is economically
different from exchange price, candle, funding, volatility, and order-flow signals.
Weak demand or disagreement means cash; S2 never authorizes short exposure.

## Causal Boundary

Any later implementation must use only blocks with at least six confirmations at
the decision cutoff. A weekly decision may use only complete UTC days through the
prior Friday, and the earliest corresponding execution is the following Binance
Monday 00:00 UTC open. Missing, reorganized, incomplete, or ambiguous chain data
forces cash. Raw block and transaction fields must be hash-bound before any
transformation.

## Source Boundary

The proposed raw source is Google's `bigquery-public-data.crypto_bitcoin` dataset,
limited initially to metadata for the `blocks` and `transactions` tables. Blockchain
ETL schema and licensing records are bound as supporting source evidence. Coin
Metrics community values are explicitly excluded as trading inputs because the free
community service is documented for non-commercial use.

The next stage may inspect current dataset/table metadata and submit bounded BigQuery
dry runs solely to learn projected bytes processed. It must bind query text, job
metadata, response identity, output hashes, `maximum_bytes_billed`, and zero-dollar
budget controls before a numeric query can ever be proposed.

## Independence Exclusions

S2 cannot use price momentum, trend, pullback, breakout, mean reversion, volatility
scaling, cross-sectional ranking, aggressor flow, order-book state, clock phase, jam
exhaustion, funding, basis, carry, perpetual flow, NFCI, monetary or financial
conditions, hashrate as a primary predictor, or active-address count as a user proxy.
It cannot reuse retired thresholds, diagnostics, or outcomes.

## Evidence Partitions

| Role | Window | State |
| --- | --- | --- |
| Development | 2017-08-17 to 2023-01-01 | Outcome-aware, nonqualifying |
| Historical screen | 2023-01-01 to 2026-11-07 | Outcome-aware, nonqualifying |
| Prospective validation | 2026-11-07 to 2027-05-07 | Locked future |
| Future holdout | 2027-05-07 to 2027-11-07 | Locked future |
| Forward | After 2027-11-07 | Locked future |

All existing historical BTC target periods are declared outcome-aware. They can
support development and falsification but cannot become untouched qualification
evidence. The prospective validation and holdout windows mean S2 cannot honestly
become live-eligible before future evidence exists.

## Frozen Evidence

- Charter: `data/evidence/s2_onchain_settlement_charter_v1.json`.
- Charter evidence hash:
  `77e61e9f01519d6b7b56aa2ce45d4689356120bb1a338ead9edce35ef18fe9b0`.
- Charter file SHA-256:
  `c3ddfc3e985cf4737422f9ae452a4ad10499dc73f44c2be44e27176b9f086832`.
- Independent audit:
  `data/evidence/s2_onchain_settlement_charter_audit_v1.json`.
- Audit evidence hash:
  `88e82b6c0169e6e9f3f645cfadeeb8e3aac797f002e5c5f88cae9fe863746745`.
- Bound predecessor artifacts: `8`.
- Bound research sources: `6`.
- Frozen chronological partitions: `5`.

## Exact Authority

Decision: `FREEZE_S2_FOR_SOURCE_AND_QUERY_FEASIBILITY_ONLY`.

Next authorization:
`AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY`.

Permitted now: public source metadata requests and bounded BigQuery dry runs. Not
permitted: numeric blockchain queries, market-value access, payload acquisition,
parameter definition, returns, validation or holdout access, Pine deployment, paper
operation, Testnet strategy orders, production, live trading, or real capital.
Strategy candidates, executions, orders, and real net profit remain zero.

## Feasibility Result

The separately frozen v1 feasibility protocol spent exactly three public metadata
attempts after eight focused tests passed. Google returned HTTP `401` for the public
dataset, blocks table, and transactions table without authentication. This machine
also has no `gcloud` or `bq` command, no active Cloud project, and no verified
no-billing sandbox boundary.

- Protocol/audit hashes:
  `9e91ba7e6d8b388e4873ccd255336577ae1f2c900e3c88f35df6abc6a09720f0` /
  `e952ebf625acad59909c506d1fe4e1683c4580d61ae4203858770ca86dcb25d0`.
- Result/audit hashes:
  `8986a9ed6b41af03e6ba7fe72054138362a04ee3f1eae6b1278656b1b56df9f1` /
  `1c4bcf38b0484495a069b050a404c3e5135bd1fb748097dced37c3d78aa68b38`.
- Decision: `BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE`.
- Exact next authorization:
  `NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES`.

No dry run, query execution, row result, blockchain value, market value, payload,
parameter, return, candidate, signal, or order occurred. Retry requires a new frozen
protocol version after the operator establishes authenticated BigQuery sandbox access
without a billing account.

Post-result local remediation installed the checksum-verified Google Cloud SDK
`579.0.0` and BigQuery CLI `2.1.36` under
`%LOCALAPPDATA%/AurexTools579/google-cloud-sdk`. Both executables respond. Boolean
checks confirm that active Google authentication and an active Cloud project remain
unconfigured; no account or project identifier was displayed. The remaining blocker
therefore requires operator sign-in and selection or creation of a BigQuery sandbox
project without billing. The consumed v1 preflight remains immutable and must be
followed by a frozen v2 amendment.

## Authenticated Feasibility Amendment

The separate v2 amendment is now frozen and independently reconstructed. It binds
the charter plus the complete v1 protocol/result lineage and permits one fresh,
ordered preflight only after local clients, active user OAuth, an active project, and
the no-billing boundary all pass. It then permits at most one access-token request,
three authenticated public-metadata requests, and two `bq --dry_run` requests.

- Protocol: `data/evidence/s2_bigquery_feasibility_protocol_v2.json`.
- Protocol evidence hash:
  `0074b2d2594bb5aa5d430e6818218146be244ea57e2386938ebaaf01fc5147a9`.
- Independent protocol audit:
  `data/evidence/s2_bigquery_feasibility_protocol_audit_v2.json`.
- Audit evidence hash:
  `1140f679697b1a86757071a4afeb3ceeda120b099fa8e6c374e13e35d009fc19`.
- Focused v1/v2 feasibility verification: `18 passed`.
- Requests made by v2 so far: `0`.

Account identifiers, project identifiers, credentials, and tokens are forbidden
from evidence artifacts. Query result rows, blockchain values, market values,
payloads, parameters, returns, candidates, orders, and trading authority remain
zero. The exact blocker is user-owned Google OAuth plus selection or creation of a
BigQuery sandbox project without billing. After that, Aurex may run v2 once; even a
pass authorizes only a separately frozen source-payload protocol, not a numeric query
or any strategy execution.

## Authenticated Feasibility And Payload Result (Current)

The operator completed OAuth and selected a BigQuery sandbox project without
billing. Authenticated metadata checks passed. The consumed v2 feasibility run
stopped on its first opaque `bq` CLI dry-run error; the failure remains immutable.
A separately frozen v3 transport amendment used BigQuery REST dry runs only, and
both ordered dry runs returned HTTP `200`. No numeric query executed at feasibility.

The frozen v1 payload protocol then authorized one development-only numeric query.
That query completed but Aurex rejected the response because the aggregate fee field
was `NUMERIC` instead of the required `INTEGER`; zero rows and zero payload bytes
were accepted. A separate v2 schema amendment cast only that aggregate to `INT64`.
The v2 query completed in one submission, processed `46,852,212,436` bytes under its
frozen 60 GB ceiling, and persisted exactly 280 weekly causal rows spanning
`2017-08-19` through `2022-12-24`.

- Payload protocol v1/audit hashes:
  `63d0e0f7c7f456c8ac1015066105cfd2077cdd739ff80afc01f37ebf656868b7` /
  `e1c6e4797d8d1f8027f9f7e8f06a87382c285ade70e407eddcd6587a4749f02e`.
- Failed v1 result/failure-audit hashes:
  `38c151ef24be8987eaa970d1bb0dbb2657ec414b4898e8a1002360185ceda899` /
  `2685797df5497fbd709179385d7a1d9e8565698fe04faa42bdcc2b24b9d564e8`.
- Payload protocol v2/audit hashes:
  `93d4280e7d852ce5e83b3c3215a67b48c906149e5041ccda08febaedd42131fb` /
  `c3fda102a02c5b2fcffe50a7ac14ff25940813e2f64dd8cfaf554ce10bb5d3a4`.
- Passed v2 result/payload/audit hashes:
  `a50c3c69ebfdcabcce5ea9998c5eea60db8ae74756d05fe6b9460564b247094a` /
  `fc436388a09ad097829a2edcea4d2789403493a14425b35355a9a50a05eaf070` /
  `edc724a48b7cd0f7726ae1cec925bd379738bf78ba152f7077f2a3b3b5ffb719`.

Decision: `PASS_S2_DEVELOPMENT_PAYLOAD_ACQUIRED`. Exact next authorization:
`AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`. This permits protocol design
only. Market prices, parameters, returns, validation, holdout, signals, Pine, paper,
Testnet strategy orders, production, live trading, real capital, and profit remain
unauthorized. The prospective validation and holdout windows remain sealed.

## Development Measurement Construction (Current)

Before parsing payload values, Aurex froze a seven-measurement family using current
four-week and prior-four-week transaction/fee sums, deterministic PPM changes, and
strict `BOTH_BROADENING`, `BOTH_CONTRACTING`, or `FLAT_OR_MIXED` agreement. It
forbids imputation, clipping, winsorization, z-scores, rankings, outcome fitting, and
multiple candidate or parameter combinations. Protocol/audit hashes:
`dedb2d9a0fb23d6a943d290c36333107adf3ef873754d2b8572ac3692377a17b` /
`3a72c31dd90db8aa0b307972e70f33b7a3b0909956888c3052666343462edd0e`.

After synthetic verification, the separately frozen execution addendum permitted
one payload-only run. The result contains 273 causal measurement rows and was
independently reproduced byte for byte. Dataset/result/audit hashes:
`513237db0a939170efb2113444fdd633a5c5dc1b397b8022b154020cfdf4b327` /
`8e4534468b2f471b56e4b7d3391a08f1299b6d0079c8fc4b3ae4880630977f3b` /
`3af9c1b2332932f6064fe9ccc1172b888e14abe53cd529abcd4c0c930e913523`.

Decision: `PASS_S2_DEVELOPMENT_MEASUREMENT_CONSTRUCTION`. Exact next authorization:
`AUTHORIZE_S2_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY`. Market values,
strategy parameters, returns, candidates, signals, validation, holdout, Pine, paper,
Testnet strategy orders, production, live trading, and real capital remain locked.
Measurement integrity does not establish predictive edge or profitability.

## BTC Source And Development Backtest Result

The BTC source protocol was frozen before market-value access and bound 273 exact
Binance Vision daily archives. All 273 Monday 00:00 UTC BTCUSDT 1h opens were
checksum-verified and independently reconstructed. Source result/audit hashes:
`6ba8c88d62c92f36696032f4fbd7697cf43369e1ace4050cf109086dcd76f3cd` /
`8b2e6ec3aa26ea0e282051fd76a157550750c92c9d88fd1ba058e219c7d1db10`.
Price dataset SHA-256:
`6c9c09c8b6a4c484f64a366a8b66a1e939d198894117f9f91b01ea12024af156`.

The backtest protocol, all formulas, costs, bootstrap settings, and 15 gates were
then frozen and independently audited before returns were calculated. One run was
authorized. The primary candidate passed 9 gates and failed 6: base profit factor,
base drawdown, stress drawdown, positive calendar years, stress bootstrap lower
bound, and base Calmar. Result/audit hashes:
`a9661515cbbb584ceaa8894c250f31916d8e35e9e67ea4670b21226c9a99eb54` /
`c59985486e9ccc46191161f9e42d9b7b9a3ae11482720d51fe42ef45d16d0e86`.

Decision: `STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2`. This is terminal for the
S2 lineage. The positive base and stress total returns cannot override the frozen
risk and reliability failures. No post-outcome tuning, diagnostic promotion,
historical screen, validation, holdout, Pine, paper, Testnet strategy order,
production, live trade, or real-capital action is authorized. S2 generated zero
orders and zero real profit.

Any S3 work must begin from a distinct preregistered economic mechanism and a new
causal charter. It may learn from S2's failure, but it must not alter S2's rule,
thresholds, costs, partitions, or gates to manufacture a pass.

## Successor Transition

S3 was frozen on `2026-08-30` as a distinct CFTC leveraged-money positioning
hypothesis. Its charter and independent audit bind the terminal S2 result and audit
by file hash, so no S2 rescue or relabeling occurred. S3 currently authorizes only
a point-in-time source-metadata feasibility protocol. It has read zero CFTC position
values and zero BTC market values, created no strategy candidate, and granted no
paper, Testnet strategy-order, production, or live authority.
