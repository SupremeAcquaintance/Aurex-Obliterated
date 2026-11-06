# Binance Spot Testnet Phase 2 Tracker

This is the compact resume ledger for Aurex's Binance Spot Testnet execution work.
`docs/10_PROJECT_CONTROL.md` remains the canonical program ledger. Update both files
at every Phase 2 checkpoint.

## Safety Boundary

- Environment: Binance Spot Testnet only
- Origin: `https://testnet.binance.vision`
- Product and symbol: Spot `BTCUSDT`
- Simulated account equity: `$100`
- Maximum notional per Testnet order: `$10`
- Production authority: false
- Live authority: false
- Real-capital authority: false
- Strategy eligibility: none
- Credentials: process environment only; never written to evidence

## Gate Ledger

| Gate | State | Evidence |
| --- | --- | --- |
| 2A. Public connectivity | COMPLETE | `data/evidence/binance_spot_testnet_virtual_cancel_20260731T065201Z.json` |
| 2A. Authenticated account read | COMPLETE | Same preserved source artifact |
| 2A. Signed test order | COMPLETE | Same preserved source artifact |
| 2A. Resting limit placement/query/cancel/final query | COMPLETE | Same preserved source artifact |
| 2A. Exact virtual-cancel reconciliation | COMPLETE | `data/evidence/binance_spot_testnet_virtual_cancel_reconciliation_20260731T065201Z.json` |
| 2B. Fill/fee/balance campaign contract | COMPLETE | `data/evidence/binance_spot_testnet_fill_fee_contract_v1.json` |
| 2B. REST implementation and synthetic failure tests | COMPLETE | 42 scoped Testnet, API, profile, and dashboard tests pass; repository Ruff and frontend syntax pass |
| 2B. Explicit operator acknowledgement | COMPLETE | Exact acknowledgement supplied through the guarded wrapper |
| 2B. Genuine Testnet fill campaign | COMPLETE | `data/evidence/binance_spot_testnet_fill_fee_20260731T091050Z.json` |
| 2B. Independent fill/fee audit | COMPLETE | `data/evidence/binance_spot_testnet_fill_fee_audit_20260731T091050Z.json` |
| 2C. User-data stream and reconnect contract | COMPLETE | `data/evidence/binance_spot_testnet_user_stream_contract_v1.json` |
| 2C. Stream client, recovery runner, and synthetic failure tests | COMPLETE | Signature subscription, typed events, REST parity, reconnect, gap recovery, deduplication, teardown, and independent evidence reconstruction pass |
| 2C. Explicit operator acknowledgement | COMPLETE | Exact acknowledgement supplied through the guarded wrapper |
| 2C. Genuine Testnet reconnect campaign | COMPLETE | `data/evidence/binance_spot_testnet_user_stream_20260731T100023Z.json` |
| 2C. Independent source preservation and audit | COMPLETE | `data/evidence/binance_spot_testnet_user_stream_audit_20260731T100023Z.json` |
| 2D. Restart/reset/idempotency and kill-stop contract | COMPLETE | `data/evidence/binance_spot_testnet_restart_soak_contract_v1.json` |
| 2D. Durable state, guarded executor, staged runner, and synthetic failure tests | COMPLETE | Three-process staging, one-POST idempotency, kill-stop persistence, stale-order recovery, reset fail-closed handling, reconnect soak, evidence reconstruction, API, and dashboard tests pass |
| 2D. Explicit operator acknowledgement | COMPLETE | Exact acknowledgement supplied through the guarded wrapper |
| 2D. Genuine restart/recovery/soak campaign | COMPLETE | `data/evidence/binance_spot_testnet_restart_soak_20260731T125305Z.json` |
| 2D. Independent source preservation and audit | COMPLETE | `data/evidence/binance_spot_testnet_restart_soak_audit_20260731T125305Z.json` |

## Preserved Evidence

- Virtual-cancel source SHA-256:
  `d4a4f6a6be8ab72b2ad4424ee7fcd283dc0f69c66ad381a213077643d57123a6`
- Reconciliation addendum SHA-256:
  `8ba2a284ddea8f8c32b7cc420fbe0d80da861e5263d52a28e0114ee799a41e06`
- External Testnet order: `22292295`
- Proven lifecycle: `NEW -> CANCELED`, zero fill
- Rerun rule: do not rerun the completed virtual-cancel campaign
- Fill/fee contract SHA-256:
  `8eddafafb5db47fa218c993476f5e6ae4cf13a4f4894d671c89321953e8719cd`
- Fill/fee source SHA-256:
  `9a8876188432292bb27842956287881bf5fc170fa3164e07a97ebc8604ce3e51`
- Fill/fee audit SHA-256:
  `720e5a00ac9c97fba284420054e0f5b88751cd82cac52440402edf4d2dfc8251`
- Phase 2B decision: `PHASE_2B_FILL_FEE_RECONCILED`
- User-stream contract SHA-256:
  `ddf06d9d596812c9dcb45c4c6654e8e50a0b5a3ae2928b15fdbf487fad2f8c2d`
- User-stream source SHA-256:
  `e5bc1e5402f49a07c5fc3389259025e30e9fee1ee6a525389e8e01aee7ba333e`
- User-stream audit SHA-256:
  `70cd169d2716a2beac17c2f4a3cca53146b1c96f490b065830d7f774e9059038`
- Phase 2C decision: `PHASE_2C_USER_STREAM_RECONCILED`
- Restart/soak contract SHA-256:
  `5e5f1f22a014fa087c44a13341f862fe6d64ea441db280fabae677bf2af820d8`
- Restart/soak source SHA-256:
  `8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50`
- Restart/soak audit SHA-256:
  `0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29`
- Phase 2D decision: `BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED`

## Phase 2B Frozen Contract

Phase 2B is a separately frozen, bounded campaign:

1. Record sanitized BTC and USDT balances.
2. Validate current exchange filters and a market order through
   `POST /api/v3/order/test`.
3. Submit one deterministic Testnet `MARKET BUY` using a fixed
   `quoteOrderQty` below the `$10` per-order cap.
4. Query the order and `GET /api/v3/myTrades`; reconcile every fill and commission.
5. Sell only campaign-acquired BTC, after base-asset commission and market-step
   rounding, using one deterministic Testnet `MARKET SELL`.
6. Query and reconcile the sell order and trades.
7. Re-read balances and prove exact BTC/USDT deltas from trade quantities, quote
   quantities, and commissions.
8. Preserve each checkpoint immediately. Never blind-retry an order after an
   ambiguous transport or server outcome.
9. Fail qualification if cleanup is incomplete, an unexplained balance delta exists,
   any order exceeds the frozen cap, or any identity, fill, fee, or status predicate
   fails.

This campaign proves execution accounting only. It does not prove strategy edge,
profitability, paper readiness, complete sandbox qualification, or live readiness.

## Phase 2C Frozen Contract

Phase 2C uses Binance's current WebSocket API endpoint
`wss://ws-api.testnet.binance.vision/ws-api/v3` and
`userDataStream.subscribe.signature`; it does not use the retired REST listen-key
workflow.

1. Establish a signature subscription using the process-only HMAC Testnet key.
2. Place one bounded resting BUY and require a matching `NEW` execution report.
3. Deliberately close the connection, cancel that order while disconnected, then
   establish a fresh connection and subscription.
4. Recover the deliberately missed `CANCELED` state and account state through REST.
5. Place and cancel a second bounded resting BUY while connected and require exact
   `NEW` and `CANCELED` execution-report parity with REST.
6. Require a final USDT account-position event to match REST, empty trade ledgers,
   zero executed quantity, and exact initial/final BTC and USDT balances.
7. Hash and suppress exact duplicate events across both connections.
8. Unsubscribe cleanly, persist every checkpoint, refuse overwrite, and block on any
   ambiguous order, fill, balance drift, credential leakage, or cleanup uncertainty.

This short campaign proves user-data event transport and reconnect gap recovery only.
It does not prove long-duration stability, strategy edge, whole-sandbox
qualification, production readiness, live eligibility, or profit.

## Phase 2D Frozen Contract

Phase 2D is frozen as one three-process campaign:

1. The prepare process requires an empty authenticated `BTCUSDT` open-order census,
   records durable intent, submits exactly one resting BUY capped at `$10`, persists
   the exchange identity, and exits while the order is still `NEW`.
2. A distinct recovery process loads hash-verified state, requires exactly one
   matching exchange open order, resolves the deterministic client order ID without
   another placement request, and fails closed if the order disappeared.
3. Recovery persists the kill-stop before cancellation. The kill-stop blocks new
   order entry but permits exchange reads and cancellation.
4. Recovery cancels only the deterministic campaign order, then requires exact
   `CANCELED` identity, zero execution, zero cumulative quote, an empty trade ledger,
   no open orders, and exact initial/final BTC and USDT balances.
5. Recovery attempts a separate deterministic entry through the guarded path and
   requires a local kill-stop rejection with no exchange placement call.
6. A third process keeps the kill-stop enabled for 600 seconds. It performs REST
   heartbeats every five seconds, authenticated account/order reconciliation every
   30 seconds, and forced fresh WebSocket signature subscriptions near seconds 200
   and 400.
7. The known canceled order must remain queryable. Binance `-2013`, account drift,
   any open order, or changed execution state is treated as possible Testnet reset
   or external mutation; the state is invalidated and no order is recreated.
8. The final verifier requires three distinct process IDs, one placement request,
   at least one idempotent restart resolution, one blocked entry, 120 REST
   heartbeats, 20 authenticated reconciliation checks, two reconnects, three valid
   subscriptions, no reset, no failed gate, and a durable kill-stop.

Binance documents that Testnet is reset approximately monthly without advance
notice and that pending and executed orders are deleted. Aurex therefore proves the
reset response synthetically and monitors for a reset during the real campaign; it
does not claim to induce an exchange reset.

Passing Phase 2D qualifies only the Binance Spot Testnet execution adapter. It does
not make any strategy eligible, prove profitability, permit production access, or
authorize real capital.

## Implemented Controls

- Market fills are disabled by default behind a separate constructor gate.
- The BUY uses frozen `quoteOrderQty=6.50`; every order remains capped at `$10`.
- Current `MARKET_LOT_SIZE`, notional, market-order, and quote-order-quantity support
  are validated before submission.
- BUY, SELL, order query, and `GET /api/v3/myTrades` have typed, sanitized snapshots.
- Deterministic client order IDs are persisted before order entry.
- Transport, timeout, HTTP 5xx, and Binance `-1007` outcomes are queried by client
  order ID and never blindly resubmitted.
- Partial execution permits at most one filter-valid cleanup SELL and always fails
  qualification; a below-minimum residual is recorded rather than forced.
- The independent status verifier rebuilds trade totals and asset balance equations
  from stored evidence instead of trusting self-reported pass fields.
- Evidence checkpoints are atomically persisted and an existing campaign output is
  never overwritten.
- The Operator view reports contract and fill-reconciliation state.

## Exact Resume Point

Current work: Phase 2B is complete. BUY order `22331495` filled `0.00010000 BTC`
for `6.38180000 USDT`; SELL order `22331518` sold the same quantity for
`6.38179900 USDT`. Both account-trade ledgers reconcile, commission is zero, BTC
returns exactly to its initial balance, and expected/observed USDT delta both equal
`-0.00000100`. No cleanup was needed.

Phase 2C is complete. Order `22344038` emitted `NEW`, was cancelled during the
deliberate disconnect, and was recovered as `CANCELED` through REST. After a fresh
signature subscription, order `22344082` emitted exact `NEW` and `CANCELED`
execution reports. Five unique events were recorded, both trade ledgers were empty,
both orders executed zero quantity, and initial/final BTC and USDT balances matched
exactly. No cleanup was needed.

Phase 2D is complete. Run `aurex-run-ca2c2b4a5b5cfc71` used three distinct
processes and exactly one exchange placement request. Order `22377060` was recovered
after the prepare process exited, resolved idempotently without a duplicate POST,
and canceled only after the durable kill-stop was enabled. A separate entry was
blocked locally. The order remained zero-fill with an empty trade ledger, no open
orders remained, and initial/final BTC and USDT balances matched exactly.

The kill-stop remained enabled through a `602.766` second soak with 120 REST
heartbeats, 21 authenticated reconciliations, two forced WebSocket reconnects, and
three valid signature subscriptions. No reset or state invalidation was detected.
The source was preserved byte-for-byte and the independent audit decision is
`BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED`.

Do not rerun Phase 2A, 2B, 2C, or 2D. The Binance Spot Testnet execution adapter is
now sandbox-qualified. This still creates no strategy eligibility, production or
live authority, real-capital authority, or evidence of profit.

The next program action was completed with `jam_reversal_spot_v1` v1.0.1. Its
preregistered BTCUSDT 15m historical decision produced 14 trades, `-$0.5371`, PF
`0.8301`, negative OOS evidence, and zero of six passing folds. Both audits pass and
the version is retired.

The bounded no-new-returns failure analysis is complete under evidence hash
`7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`.
It confirms that the drawdown gate passed, but the sample, base-cost expectancy,
profit factor, OOS, active-day, and walk-forward gates failed.

The design-only successor charter is now frozen under hash
`426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`.
It selects aggressive sell-flow exhaustion and reclaim for future capability review
only. It creates no strategy, parameter, return, or execution authority.

The metadata-only official Binance archive census is complete. All 96 frozen
BTCUSDT 2019-2022 aggregate-trade and one-minute-kline checksum targets were present
in 96 first-attempt GETs. Result hash
`e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e`
and independent audit hash
`3f57bd2fb843059606bf32a284db0cc15e58c436115a922073b0c862aaaabfcb`
both pass. No archive payload or market value was requested.

The separately authorized January 2019 payload pilot is complete. Both source
hashes matched, and 5,989,468 aggregate-trade rows reconciled exactly to all 44,640
one-minute klines. Result hash
`f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974`
and independent audit hash
`bc8880252f50215be1fbb46803e1325d5e40c2b34101ad02bad0d4284ad710bf`
pass.

The separately authorized full 2019-2022 acquisition is complete. All 96 official
archive checksums passed, but only 23/48 paired months passed every frozen quality
rule. Full-acquisition result hash
`ffe45a45bc9340e3323aac9ddd4257a19597bcee260961f787b50c8b1dee121b`
records decision `STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED` and artifact next
authorization `NONE_ACQUISITION_FAILED`.
Independent reconstruction of all 96 raw archives and 48 monthly records passed
under audit hash
`d0f1d8bc4a2fe8745bf678aacdeeaeb3ef547fed49b9956dc54d36311c96e961`.

The separately authorized archive-quality remediation is now complete. Both
2021-12 aggregate members are byte-identical. Aurex reconstructed 4,009 missing
kline minutes, eight invalid rows, and 144 mismatch minutes, producing a
4,161-minute quarantine. Aggregate trades qualify as the primary historical source;
one-minute klines are QA-only. Result hash
`02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`
and independent audit hash
`146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`
pass.

Current next action: do not begin returns, backtesting, strategy orders, or forward
paper. The separately authorized no-return feature specification is complete: 17
features, a 133-minute causal window, seven fail-closed quality states, and nine
synthetic conformance cases. Specification hash
`8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`
and audit hash
`760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`
pass.

Obtain explicit authorization
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS` before running
the frozen features on 2019-2020 development data. Do not open 2021 or 2022, join
future returns, rerun Phase 2, tune Jam v1.0.1, or begin forward paper.
