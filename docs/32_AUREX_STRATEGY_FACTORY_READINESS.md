# Aurex Strategy-Factory Readiness

Status: `S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED`

This checkpoint answers one narrow question: can Aurex begin a new strategy research
cycle without repeating the statistical, lifecycle, or operator-control gaps exposed
by its rejected strategies? The answer is yes. It does not answer whether a profitable
strategy exists. None exists today.

## Frozen Authority

- Permitted next action: freeze and independently audit the S3 CFTC source-metadata
  and point-in-time feasibility protocol before reading any position value.
- Strategy candidates created by this checkpoint: `0`.
- Market outcomes opened by this checkpoint: `0`.
- Strategy executions and orders: `0`.
- Qualified or enable-eligible strategies: `0`.
- Paper, Testnet strategy-order, production, and live authority: `false`.
- Real net profit: `$0`.

## Baseline And Closure

The frozen baseline result recorded 11/15 PASS, 4 PARTIAL, and 0 FAIL. Three
research-required blockers were real:

1. Generic acceptance did not mandate cost stress, uncertainty bounds,
   multiple-testing control, or a separate holdout decision.
2. The shared strategy registry did not enforce retired or quarantined lifecycle
   state directly.
3. The operator console was not bound to canonical platform readiness and retained
   stale hard-coded strategy guidance.

All three are now closed. The current independently reconstructed result is 14/15
PASS, 1 PARTIAL, and 0 FAIL, with no research-blocking gate. The only partial gate is
`AUTHENTICATED_SIGNAL_DELIVERY`: code controls exist, but one genuine external
TradingView delivery artifact does not. That proof remains required before an
eligible Pine-delivered strategy can operate; it is not required to write a new
economic hypothesis.

- Frozen baseline result hash:
  `2b8356e9ea74c9e38b25113eb08b7636c9d525b98906d9711d131191d7ec1c9c`.
- Current readiness result:
  `data/evidence/aurex_strategy_factory_readiness_current_result_v24.json`.
- Current readiness result hash:
  `fd8e0d0d38169a18f018d722ff4e60423c1f18b23152a880b0f90aec2977baa0`.
- Current independent audit:
  `data/evidence/aurex_strategy_factory_readiness_current_audit_v24.json`.
- Current independent audit hash:
  `eae481ece180c6d5fcecb9cfe309df9916c25c51ff62ba06c2e0ff8390909afe`.

Earlier current-result generations, including v3, remain preserved. Runtime browser QA found that
the first generation still surfaced the retired deployment-plan strategy in the
Command preview and initial backtest/Pine resource requests. The final generation
removes every hard-coded `trend_pullback_v1` operator default, derives strategy
context only from an `ACTIVE`, evidence-qualified registry definition, and reports
`No qualified strategy`, `Research only`, and `LOCKED / no execution authority`
when no such definition exists. The readiness inspection now tests this condition.

## Universal Contract

Artifact: `data/evidence/aurex_strategy_factory_contract_v1.json`

Contract evidence hash:
`8676ffc5caea7782607ad7e9072e71ab8e09fbd93fe115f47c8860833f33f50e`

Every future candidate under this contract must use all controls together:

- chronological development, validation, and separate holdout windows;
- explicit walk-forward, regime, drawdown, and trade-concentration gates;
- positive trade-level modeled costs and deterministic 1.5x/2.0x cost stress;
- a deterministic moving-block bootstrap expectancy lower bound;
- a hash-bound tested-variant registry and multiplicity-adjusted PF threshold;
- a validation pass before the holdout may be opened, and one holdout decision;
- immutable source, parameter, protocol, trade, and decision evidence.

Partial activation fails closed. Legacy reports remain historical evidence; they do
not acquire factory qualification retroactively.

## Lifecycle Boundary

Current versions are intentionally non-active:

| Strategy | Lifecycle |
| --- | --- |
| `trend_pullback_v1` 1.3.0 | `RETIRED` |
| `volatility_breakout_v1` 1.1.0 | `RETIRED` |
| `slow_breakout_spot_v1` 1.0.0 | `RETIRED` |
| `range_mean_reversion_v1` 1.0.0 | `RESEARCH_ONLY` |
| `jam_reversal_v1` 1.14.0 | `QUARANTINED` |
| `jam_reversal_spot_v1` 1.0.1 | `RETIRED` |

API enable attempts return `409`; database reconciliation forces ineligible versions
disabled; the risk engine rechecks lifecycle before any approval. A future `ACTIVE`
definition must also bind the exact factory contract version and a qualification
evidence hash.

## Operator Truth

`GET /system/readiness` validates the frozen contract, current readiness result, and
all bound source hashes. If any source changes, the endpoint reports the strategy
factory blocked until evidence is regenerated and audited. Command displays this
state directly. It no longer presents a retired strategy as the default road ahead.

## S2 Checkpoint

Q1 and S1 are terminal. S1's one-shot primary failed five development gates. Its
separately frozen postmortem reconstructed the existing ledger without parameter
variation and confirmed that high cost sensitivity, unacceptable drawdown,
calendar-year instability, and a negative bootstrap lower bound leave no rescue
path. Decision: `RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE`. Validation and
holdout remain sealed; diagnostics cannot be promoted.

The S2 Bitcoin settlement-demand charter now binds all retired families and freezes
one distinct on-chain mechanism, six research sources, five chronological
partitions, exact source/causal requirements, and explicit independence exclusions.
It was independently reconstructed before any blockchain value, market value,
parameter, return, candidate, execution, or order was opened.

The separately frozen feasibility protocol then spent exactly three public metadata
attempts. The dataset, blocks, and transactions endpoints each returned HTTP `401`.
Neither `gcloud` nor `bq` is installed, no active Cloud project is configured, and
the no-billing sandbox boundary is unverified. Decision:
`BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE`. The only artifact-authorized next
state is `NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES`.

The operator must establish a BigQuery sandbox project without billing, install and
authenticate Google Cloud CLI locally, and select an active project. Aurex must then
freeze a v2 feasibility amendment before another request. This does not authorize
numeric queries, payload acquisition, backtesting, signals, Pine, paper, Testnet
strategy orders, production, or live execution.

Local client remediation is now complete: checksum-verified Google Cloud SDK
`579.0.0` and BigQuery CLI `2.1.36` both respond from a self-contained Aurex tools
directory. Authentication and active-project checks remain false without exposing
identifiers. The remaining operator action is sign-in plus selection or creation of
the no-billing BigQuery sandbox project.

The required v2 amendment is now frozen and independently reconstructed without a
Google request. Protocol/audit hashes are
`0074b2d2594bb5aa5d430e6818218146be244ea57e2386938ebaaf01fc5147a9` /
`1140f679697b1a86757071a4afeb3ceeda120b099fa8e6c374e13e35d009fc19`.
It requires prerequisites in order, forbids account/project/token persistence, and
allows one fresh bounded authenticated run. Eighteen focused v1/v2 tests pass. This
preparation does not change the runtime research decision: source feasibility is
still blocked until OAuth, a selected no-billing sandbox project, three authenticated
metadata checks, and two dry-runs actually pass.

## Final Verification

- Repository-wide Ruff: PASS.
- Focused S1 post-failure analysis tests: `8 passed` in `1.24s`.
- Focused S2 charter tests: `7 passed` in `2.83s`.
- Focused S2 BigQuery feasibility tests: `8 passed` in `0.82s`.
- Focused S2 BigQuery v1/v2 feasibility tests: `18 passed` in `2.33s`.
- Combined S1/S2/readiness verification: `42 passed` in `21.13s`.
- Pytest collection: `1171` tests.
- Focused execution-contract/protocol runner chain: `17 passed`.
- Readiness integration: `1 passed`.
- Most recent complete-suite baseline: `1238 passed`, with one stale readiness
  artifact failure subsequently repaired and targeted below.
- Current complete-suite verification: `1323 passed` in `1532.54s`, with only the
  existing pytest `cache_dir` and Starlette/httpx warnings.
- Current v17 runtime/API/browser QA: PASS at `127.0.0.1:8923`; source integrity and
  the v2 checkpoint verify, desktop/mobile show no page overflow or console issues,
  and the long OAuth next action wraps without clipping.
- Warning: the existing Starlette/httpx deprecation warning.
- Current desktop browser QA: `1280x720`, no horizontal page overflow, S2 blocker and
  exact next authority visible, execution locked, and no browser-console errors.
- Mobile browser QA: `390x844`, no page overflow, active navigation reachable,
  strategy table contained within its own horizontal scroll region, and all seven
  strategy actions locked.
- Runtime readiness status: `S2_SOURCE_FEASIBILITY_BLOCKED`.
- Active research checkpoint: `S2_BIGQUERY_V2_READY_AUTH_REQUIRED`.
- Runtime next action:
  `COMPLETE_GOOGLE_OAUTH_AND_SELECT_NO_BILLING_PROJECT_THEN_RUN_S2_BIGQUERY_FEASIBILITY_V2_ONCE`.
- Runtime source integrity: verified against current-result v17.
- Current readiness result/audit hashes:
  `5f9fe4d7548027ea536db557985b68fbdb1132726da221762bd2fc64f3dcc9a9` /
  `c9187ff5f43355bb68fb650b714c22c9f56f665511fe09b1425e6aa487a4a0a2`.

## S2 Payload Checkpoint (Current)

Authenticated BigQuery feasibility is complete. V2 preserved an opaque CLI dry-run
failure; a separately frozen v3 REST-only amendment then passed both bounded dry
runs without executing a query or persisting identifiers, tokens, responses, rows,
or values. V3 result/audit hashes:
`54daa95943ab19e10fb540a4cc71a70217cb409a21ff7fb804b60386a98e0690` /
`054c85503c88f62c27bf8e6f1b1c691a9a07215e59f4c7588576eac3ac7aef66`.

The separately frozen development payload v1 query was rejected on an exact schema
mismatch before any row or payload was accepted. The v2 amendment changed only the
fee aggregate cast to `INT64`, then acquired exactly 280 causally cut weekly rows in
one submission under the 60 GB ceiling. V2 result/payload/audit hashes:
`a50c3c69ebfdcabcce5ea9998c5eea60db8ae74756d05fe6b9460564b247094a` /
`fc436388a09ad097829a2edcea4d2789403493a14425b35355a9a50a05eaf070` /
`edc724a48b7cd0f7726ae1cec925bd379738bf78ba152f7077f2a3b3b5ffb719`.

Readiness v19 independently verifies this full failure-and-success lineage. It is
14/15 PASS, one downstream PARTIAL, zero FAIL, research-ready, and still has zero
qualified strategies and zero orders. Result/audit hashes:
`ff3a049b8cc054d2e2253d3ea64e7444b6c2acd3637caa60a692560fa59a2a10` /
`eeb404262d0eb710c8e29fc00061e11691f6443afa4a29bbda55f23fdab86300`.

Runtime status is `S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_REQUIRED`; active checkpoint
is `S2_DEVELOPMENT_PAYLOAD_V2_PASSED`. Exact next action is
`FREEZE_AND_AUDIT_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_BEFORE_PARAMETERS_OR_RETURNS`.
No price join, parameter, return, strategy candidate, Pine action, paper order,
Testnet strategy order, production action, live action, real capital, or profit is
authorized. Payload acquisition success is not evidence of predictive edge.

Current verification: repository-wide Ruff passed; the combined S2/readiness chain
passed `50` tests; the complete repository suite passed `1354` tests in `665.82s`.
Only the existing pytest `cache_dir` and Starlette/httpx warnings remain.

Runtime/API/browser QA passed at `127.0.0.1:8924`. The readiness endpoint reports
the v19 status and checkpoint with source and checkpoint integrity true, zero
qualified strategies, paper/sandbox-strategy/production/live false, and profit
`$0`. Desktop `1280x720` and mobile `390x844` checks found no horizontal page
overflow or browser-console errors; the long next action remains readable.

## S2 Measurement Result (Current)

The development measurement protocol was frozen before parsing payload values and
independently reconstructed. It fixes one current-four-week versus prior-four-week
family, exact integer/Decimal PPM arithmetic, strict agreement categories, no
imputation or outcome-fitted normalization, and one future candidate/parameter
combination budget. Protocol/audit hashes:
`dedb2d9a0fb23d6a943d290c36333107adf3ef873754d2b8572ac3692377a17b` /
`3a72c31dd90db8aa0b307972e70f33b7a3b0909956888c3052666343462edd0e`.

The synthetically verified runner received separately frozen one-shot execution
authority. Addendum/audit hashes:
`2f7522cb652d888d8494a2552a01f2b6b20412e442544e978f429b070218b0d7` /
`9176539c110987c109c709d8d9b59c97b1472f5ec5ba8a274262deccfe6b544b`.
It produced 273 deterministic measurement rows from the 280-row payload. Dataset
SHA-256/result/audit hashes:
`513237db0a939170efb2113444fdd633a5c5dc1b397b8022b154020cfdf4b327` /
`8e4534468b2f471b56e4b7d3391a08f1299b6d0079c8fc4b3ae4880630977f3b` /
`3af9c1b2332932f6064fe9ccc1172b888e14abe53cd529abcd4c0c930e913523`.

Readiness v21 independently verifies the complete chain. Result/audit hashes:
`2829175094ceecdc98f9f93eae7d7126ddfb6f54b64b60d4cd5156262bab4f12` /
`e0980b16b8e25a314baa1905134c9167f504a7a311754ba882aab6fdc359848f`.
Runtime status is `S2_STRATEGY_PREREGISTRATION_PROTOCOL_REQUIRED`; checkpoint is
`S2_DEVELOPMENT_MEASUREMENT_RESULT_PASSED`. The run used zero market values,
parameters, returns, candidates, signals, or orders. It proves deterministic source
measurement only, not edge. The next rule must be preregistered before prices or
returns are opened.

Current verification: repository-wide Ruff passed; the focused measurement/readiness
chain passed `36` tests; the complete repository suite passed `1389` tests in
`575.12s`. Only the existing pytest `cache_dir` and Starlette/httpx warnings remain.

Runtime/API/browser QA passed at `127.0.0.1:8925`. The readiness endpoint reports
v21 source and checkpoint integrity true, zero qualified strategies, and every
execution mode false. Desktop `1280x720` and mobile `390x844` checks found no page
overflow or browser-console errors; the preregistration next action remains readable.

## S2 Strategy Preregistration (Current)

The single S2 candidate was frozen and independently reconstructed before any BTC
market value or return was read. Protocol/audit hashes:
`5d6cd308ad31cfc22588760c8890b97d49bcce95682bcb563397fe19acfa7a6c` /
`d71184f3b0bd674f8a55750c174e01a23c9d76c7882d4d6c111c37ff92aa67c9`.
It is long 1x only on `BOTH_BROADENING`, otherwise cash, with zero parameters, one
combination, no diagnostics, and no rescue tuning. Costs, 272 weekly intervals, and
15 falsification gates are frozen. Readiness v22 result/audit hashes:
`397d4971bb087f919ca106caa4c265e2bd8fc6aef794f2258788661d4e8acdfa` /
`bc00e9866ddbc74f4f0e7198f3ba8f86f6c29d1b55a8f6a6b0461d6d959899ba`.
Current status is `S2_BTC_SOURCE_ACQUISITION_PROTOCOL_REQUIRED`; market values,
returns, candidates outcomes, Pine, paper, Testnet strategy orders, and live remain
locked. Targeted preregistration/readiness verification passed `18` tests.

Runtime/API/browser QA passed at `127.0.0.1:8926`. V22 source and checkpoint
integrity are true; desktop `1280x720` and mobile `390x844` have no page overflow or
browser-console errors, and the exact source-protocol next action is visible.

## S2 Terminal Development Outcome (Current)

The frozen S2 source protocol acquired and independently audited exactly 273
BTCUSDT Monday 00:00 UTC 1h opens. The separately frozen one-shot development
backtest evaluated one zero-parameter candidate over 272 weekly intervals with 15
predeclared gates. It passed 9 and failed 6.

The base result was positive at `+12.0634726023%`, but base profit factor was only
`1.0274819937`, base maximum drawdown was `70.7740%`, stress maximum drawdown was
`70.9273%`, only two full calendar years were positive, the stress-bootstrap 95%
lower mean weekly return was `-0.4543001949%`, and base Calmar was `0.0311030531`.
These are material edge, stability, and capital-risk failures.

Decision: `STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2`. The independent audit
reconstructed all 272 intervals exactly. S2 has no rescue, promotion, validation,
paper, sandbox-strategy, production, or live authorization. Qualified and enable-
eligible strategy counts remain zero; orders and real net profit remain zero.

Readiness v23 must report checkpoint `S2_DEVELOPMENT_BACKTEST_FAILED_RETIRED`, keep
every execution mode false, and expose only this research next action:
`FREEZE_AND_AUDIT_A_DISTINCT_S3_MECHANISM_CHARTER_WITHOUT_TUNING_OR_REUSING_S2`.

## S3 CFTC Positioning Charter (Current)

S3 is now frozen as one regulated-participant-positioning hypothesis: the weekly
change in CFTC TFF futures-only leveraged-money net positioning for CME Bitcoin,
contract-market code `133741`, may later be evaluated as BTCUSDT Spot long-or-cash.
It does not authorize futures trading, shorting, leverage, or use of other COT
categories.

Charter/audit hashes:
`2cf73ead1b04999c3b5f9f818bb60d18ad96d2041fae2d65d77084aa88e4802a` /
`f746adc212d5e41f66507a372d60824bdb84609e50b05e797a6116b60d39c90b`.
The audit reconstructed all 12 predecessor bindings, 8 sources, and 6 contiguous
partitions exactly.

The 2018 through July 2021 published leveraged-money result is known and therefore
contaminated. It cannot qualify S3. Development from 2022 onward is also
outcome-aware and nonqualifying; prospective validation and the separate future
holdout remain sealed through `2027-11-07`.

No CFTC position values, BTC market values, parameters, returns, candidates,
signals, executions, or orders were created. Readiness v24 reports
`S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED`, verifies checkpoint
`S3_CFTC_POSITIONING_CHARTER_PASSED`, and exposes only
`AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY`.
Any inability to prove actual historical release timing, delayed-report handling,
revision identity, contract-code continuity, zero-dollar access, or reuse rights
must stop S3 before numeric position data.

## S3 Source Feasibility Terminal Outcome (Current)

The S3 metadata protocol was frozen and audited before requests. Protocol/audit
hashes:
`1d9e2b672b754c3e6d7296fc3c75fd8d7ab4f49e445b06383ec4e1722271c15a` /
`bbea600436e66ee35e809a323c0f83bdbdfe948e352c4f2f4fa1add03999d7c1`.

The restricted run received zero responses and was correctly adjudicated as a
transport failure rather than causal source evidence. Result/failure-audit hashes:
`75700f67e97577d7680b97b6bedf28539c9815eb1bf424764d30094b73fe53d8` /
`704373d76fc38d794ef43b96b6ad9d13b3839ec65b11a2394e584ceceb34cef5`.

A frozen one-run transport amendment preserved all three URLs, all source gates,
and every data/execution prohibition. Amendment/audit hashes:
`dc3b2acdf29878250a28edb5f951b04b09e78e5f96110798f28f187fe8a2dda9` /
`dcd641b6febf4d93546f79f8113a8d5c3409d0b5984c6faf150f86913e30ffc6`.
The external-network run still failed to obtain all three responses and wrote no
result or response artifact. The durable receipt explicitly records the unknown
partial-response count instead of inferring one. Receipt/audit hashes:
`166e3039f51e95046ab2030eeee383e5d9cdfaa046e9fffe366b636dfc5e7d23` /
`915cc64207adb02e77efb31fb693db1970e0be612b89b51e227be8d7368bfba2`.

Decision:
`RETIRE_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL`.
S3 has no retry, payload, backtest, paper, sandbox-strategy, production, or live
authority. This is not evidence about edge or source impossibility.

Readiness v25 result/audit hashes:
`a21f0a7afa76f274523ba75e3a077fabb4fa98938162e09ef3839f52a492a362` /
`031a2471668222a94b294b1d1d1dacec80634d48b064f01829bbdaa5ebf1c5b1`.
It remains 14/15 PASS, one downstream PARTIAL, zero FAIL, research-ready for a new
mechanism charter only, with zero qualified strategies and all execution modes
false. The only next action is
`FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY`.

## S4 Spot Bitcoin ETP Charter (Current)

S4 is frozen as one economically distinct primary-market mechanism: aggregate net
creations and redemptions across the complete U.S. spot Bitcoin ETP universe, with
cross-fund breadth, may later be evaluated as BTCUSDT Spot long-or-cash. It does not
reuse price, volatility, flow, funding, basis, macro, on-chain, options, or CFTC
inputs.

Charter/audit hashes:
`8827763c7b1d71255ceff1859c0e69835403c7653ead6ad6f233edae5b9c08b4` /
`1e083ef726bfb46cb1d37f15b5c9c16b00562a3c2923a8b0907749ebd7bffbc7`.
The charter binds 20 predecessor artifacts, eight official sources, six contiguous
partitions, the 2024 cash-only regime, and the `2025-07-29` SEC in-kind regime
change. Per-fund operational effective dates remain mandatory.

All currently available ETP and BTC history is outcome-aware and nonqualifying.
Zero ETP rows or numeric payloads were parsed; zero market values, parameters,
returns, candidates, signals, executions, and orders were created. All trading
authority remains false and real net profit remains `$0`.

Readiness v26 result/audit hashes:
`dc74c231794432335ea3fceb525dd3e336c37e108763ee6cba595b4a69f4ee8d` /
`ab0d3e55cf04ec5f201c0e874b4487912be5ac3f9db6691d64cef76e6b912b15`.
It remains 14/15 PASS, one downstream PARTIAL, and zero FAIL. Runtime status is
`S4_ETP_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED`, checkpoint
`S4_SPOT_BITCOIN_ETP_CHARTER_PASSED`, with only this next authorization:
`AUTHORIZE_S4_ETP_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY`.

## S4 Protocol-Design Terminal Outcome (Current)

The S4 metadata protocol was frozen and audited with exact per-attempt persistence
before any network request. Protocol/audit hashes:
`6c0415149eabf9c22c60854a35b563a26b68b2746899cd53a17e08fac79883bd` /
`68f6ef9529dbd8f2a62fc690dd4c29cb699994149a3b84aafb0ff0e4ab70a258`.

A separate pre-run review proved that six mandatory PASS gates cannot be reached
from the frozen response surface. SEC identity fields cannot establish the required
issuer daily-history endpoints, publication timing, cash/in-kind operating dates,
or corporate-action and non-creation reconciliation while issuer and filing bodies
are forbidden. Review/audit hashes:
`1837ce1e7fb36edeee235d0270043455fa7a3e3e005d183141c6376b4d4f23ff` /
`a656f8a605c1dc1be0d599aa5b74d41ef1dd2f0e7fb073f81b8639b8855b0696`.

Decision: `BLOCK_S4_RUN_PROTOCOL_PASS_CONDITION_UNREACHABLE`. Zero requests were
made and the one-run authority remains unused. No conclusion was inferred about
source availability or predictive edge. ETP values, BTC prices, parameters,
returns, candidates, orders, and real profit remain zero.

Readiness v27 result/audit hashes:
`691b04e6bbf7069094a7c3dbd039439f78a2b2c2accd3947f8aebbb7db741efe` /
`6ee5c34d911a3756d89e9050f3f2813293f659ee314c00f2dee229b776879134`.
Runtime status and checkpoint are `S4_PROTOCOL_DESIGN_INFEASIBLE_RETIRED`; the only
next action is `FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY`.
