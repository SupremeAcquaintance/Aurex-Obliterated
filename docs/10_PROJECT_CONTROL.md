# Aurex Project Control

This is the compact control surface for the existing Stage 1-10 Aurex goal. It does
not replace `docs/00_AUREX_MASTER_PLAN.md` or `docs/01_IMPLEMENTATION_LOG.md`.

## Autonomous Goal In Progress - 2026-10-09

CURRENT RESUME (October 11, v64 in verification): v63 combined regression/browser
verification passed, superseding its older pending text below; details in docs/01.
Stage 3 now includes opt-in owned native-supervisor status/start/stop/restart and
dashboard controls. Initial 18 lifecycle cases passed. Expanded v64b run found a
real rejected-child shutdown hang (91 pass, 1 fail); unbuffered parent-pipe reads
correct it, with all three targeted real-process tests passing in v64c. Broader
regression, rendered controls and fresh source audit are pending. Do not promote
these partial results to platform acceptance. Exact current verification: docs/01.
No autostart, live orders, strategy promotion or operator DB upgrade. Genuine-feed
clock and full-history capacity remain unresolved external dependencies. Continue
independent lifecycle/operator acceptance; do not repeat unchanged external probes.

The operator activated the pre-live delivery goal in attachment
`2db94d28-50d2-47a8-887a-e500e18b4885/pasted-text-1.txt`. Routine checkpoints do not
require renewed permission. Continue implementation, verification and the next
eligible dependency; preserve external approval and real-money boundaries.

Latest verified integration is v56: 884 distinct native/risk/paper/readiness tests
passed in 301.88 seconds, zero failures/errors/skips. JUnit counts were independently
checked. Source-capability result/audit: 14 PASS / 1 PARTIAL / 0 FAIL, not operational
acceptance. Exact artifacts, hashes and earlier failed test history are in docs/46.

Stage 1 integration now includes entry AND managed exits: `native_jam_runtime.py`,
v7 receipts and opt-in `evaluate_jam` reconstruct setup/management from retained
history and atomically record existing risk/paper effects. Original trade stops are
immutable; dynamic stops live in audited receipts. Partial candles cannot activate
trails from pre-fill highs. BRACKET closes precede setup evaluation; CLOSE exits
follow it. Fees, slippage, ledger identity and equity are independently reconstructed.

Stage 2 is IN PROGRESS (v57): bounded cooperative supervisor, explicit existing-DB
CLI, OS-held process lock, resource/clock limits, bounded Retry-After handling,
stop controls and durable journals are implemented. Separate read-only auditing
reconstructs history and matches journal receipt references. Initial 17 and expanded
25 supervisor cases passed; final verification/source freeze status is in docs/46.

Actual no-entry demonstration reached the next fresh boundary, then stopped on
`public_server_clock_skew`. Its separate diagnostic DB alone was migrated to 0031.
Run-1 audit confirms zero receipts, signals, orders or trades. Retained evidence:
`data/evidence/native_supervisor_public_20261009_v1/`. Windows reports unsynchronized
Local CMOS Clock; reading time configuration was denied. The unchanged two-second
guard rejected a real measured discrepancy. Operator/IT time synchronization was
requested asynchronously. Do not repeatedly retry or change the OS/guard to mask it.

v57 final regression is verified: 186 distinct tests passed, including 28 supervisor
cases; source-capability reconstruction passes. The current clock blocker is not
permission to stop all work or mark the full goal blocked.

Independent Stage 3 work (v58): added consistent SQLite backups, independent integrity/
logical/table/schema verification, restore-to-new-path only, and guarded copy-only
0029/0030-to-0031 upgrade/rollback rehearsal. Initial 13 tests passed, including real
0029 migrations. Rehearsal on the actual operator snapshot PASSED: old table contents
and schemas preserved, only two empty native tables added, rollback restored 0029,
and original DB before/after SHA-256 is identical. Private artifacts are git-ignored:
`data/backups/native-upgrade-rehearsal-20261009-v1/`. SQLite-only backup does NOT cover
external evidence/configuration/source files or prove runtime service cutover.
Final v58 regression, fresh-process backup verification and source hashes: docs/46.

v58 final verification is complete: 93 distinct combined tests passed with no
failures/errors/skips; fresh-process backup verification and source reconstruction
pass. v59 private runtime work is verified: explicit current-schema preflight,
loopback/host/origin boundary, instance-bound diagnostic requests, settings/file
identity drift checks, graceful stop controls and new-run journals. Expanded 36
fixture tests pass, including real child-process restore/restart and occupied-port
rejection. Genuine snapshot service rehearsal passed: both processes stopped, kill
state persisted and trading-table hashes were unchanged. Final combined 145 distinct
tests passed; exact source/rehearsal evidence and limits are in docs/46.

Current Stage 3 work is v60 application recovery. Added safe source/config/evidence
bundles with explicit FULL_EVIDENCE or OPERATIONAL_WITHOUT_RAW_ARCHIVES coverage,
per-file hashes, source-change checks, no-overwrite restores and readback verification.
Pinned binary dependency escrow and isolated offline environment reconstruction are
implemented. Initial 24 bundle tests and combined 35 bundle/dependency tests passed.
Thirty-nine exact installed-version wheels were downloaded into a private directory;
offline installation and restored-source service rehearsal are being verified.

Actual capacity preflight: full scope 77,767,608,005 source bytes needs 158,297,787,786
free for backup plus restore; observed free was 79,915,769,856. Full-history recovery is
BLOCKED on capacity, not silently omitted. Operator was asked asynchronously for a
separate writable destination with at least 160 GB free; no archives were deleted.
Operational scope fits, explicitly omitting 6,827 raw ZIP/partial archives containing
76,175,685,917 bytes. It is NOT a complete historical-evidence backup. Exact current
package/install/rehearsal results and final regression: docs/46.

v60 operational restoration and offline restored-source startup have PASSED. Two
real service cycles preserved kill state, rejected hostile origins, stopped cleanly
and left trading-table hashes unchanged. Report:
`data/backups/application-restored-rehearsal-20261010-v1/rehearsal.json`.
This proves operational scope only, not the omitted historical archives or cutover.

Current correction (v61): final readback must complete BEFORE publishing a restore
receipt. The launcher now requires a versioned v2 receipt with verified readback;
legacy receipts cannot silently satisfy that guard. The actual v60 rehearsal waited
for successful readback, but its package is historical, not a current release bundle.
Refresh the latest-source recovery package before final cutover, not after every edit.

v61 correction verified: 98 distinct tests passed; source reconstruction passes.
v62 implemented bounded/serialized dashboard reads, fail-closed stale safety state,
private-service status and honest equity empty states. Six executable transport tests
and 43 dashboard/private-runtime/readiness tests passed. Browser rehearsal c passed all
14 tabs on desktop/mobile, kill protection and injected source-failure recovery on a
new disposable 0031 copy. Earlier browser a/b failures were missing test binary and
CSS-uppercase assertion errors, retained in `.tmp/operator-dashboard-v62[a-c]-20261010/`.
Current v63 finalizes explicit unknown-risk labels, stale strategy-enable blocking and
animation-stable screenshots. Final source-bound regression/browser checks are pending.
Immediate next work after verification: native supervisor lifecycle/status integration
and remaining operational acceptance. A web service is not a running trading supervisor.
Complete full-history recovery when capacity is supplied. Keep operator DB at 0029
until guarded cutover is justified; do not replace it from a rehearsal automatically.
Reattempt genuine admission/restart only after meaningful clock-state change.
Jam streams stop on missed windows; automatic gap recovery is NOT implemented.
The operator DB was not migrated; no genuine stream admitted or strategy activated.
All seven goal stages remain in scope; routine checkpoints need no permission.

## Historical Verified Checkpoint - 2026-10-09 (v55)

This dated checkpoint supersedes earlier "latest" resume sections for scheduling;
earlier evidence and decisions remain historical records.

**Goal:** deliver a reproducible Aurex research-to-execution workflow and determine
whether an independently validated, cost-positive BTCUSDT spot strategy exists.
Progress toward the first settled $100 net profit only after qualification, forward
paper evidence, sandbox reconciliation, and explicit approval of micro-live trading.
Profit has no guaranteed amount or completion date. Capital remains $100, unborrowed,
spot only, at most 1x; existing loss limits and the $0 data budget still apply.

**Current state:** no qualified strategy or demonstrated live profit. The S5 original
monthly measurement was rejected for missing release data. The first source repair
fetched only 42 of 132 stable tags and was independently rejected. The complete
repair captured all 132 frozen identities (104 annotated, 28 lightweight) with zero
drift. Its independent result audit now passes. The amended measurement has also
completed: 212 monthly rows, all 132 releases accounted for, and every non-release
field equal to v1. A separate arithmetic reconstruction reproduced all output bytes.
Result/audit hashes are `69d42d1c9e8754d8fa43a0b4ea1aa5cd52904f150c1475e25a572cba34e39c71`
and `37f27c2ddfb81aaad18424aaa6ed9224da5fe086bb4f8490514caba0c796cfd1`.

**Priority decision:** S5 measurements are usable for bounded research, but S5 cannot
serve the requested near-term income objective. Its frozen prospective validation
runs from 2026-11-07 to 2027-05-07 and its holdout ends 2027-11-07. No historical
result can shorten those partitions or qualify this lineage. Defer additional S5
outcome research while closing platform delivery and execution-evidence gaps.
This is a scheduling decision, not a statistical rejection or a new strategy.

**Operator decision (September 27):** continue on the $0 route. TradingView Basic
does not expose webhook alerts on the inspected account. Defer Pine webhook
delivery, cloud receiver deployment, and relay development; do not mark them done.
Do not purchase access or start trials. Focus on local Aurex-native mechanics,
using the existing evidence, risk, and paper services. Native signal provenance
must remain distinct from authenticated external TradingView delivery.

**Distance to production:** core native integration is still in progress, not a
deployment-ready trading product. Do not interpret 14/15 source-capability gates
as a completion percentage. The ordered remaining gates are:

1. Integrate the pure deterministic candidate/managed-exit proposals with atomic
   source/head/settings/decision binding and existing risk/paper services. The pure
   kernel now proposes decisions; it does not persist or execute them.
2. Finish the stoppable supervisor and demonstrate restart, outages, missed windows,
   rate limits, disk exhaustion, monitoring and reconciliation on a genuine feed.
3. Demonstrate private operational deployment, backups/restores and upgrade/rollback.
   Public exposure additionally requires management authentication/authorization;
   the current main API must remain private. Hosting alone does not close these gates.
4. Qualify a candidate independently of software readiness, including frozen costs
   and untouched validation, then eligible forward-paper evidence and current Testnet
   execution/reconciliation. Old Jam rejection and July Testnet proofs are not passes.
5. Verify current account/product eligibility, operator compliance confirmation,
   risk/execution readiness and explicit micro-live approval before any real order.

No honest percentage or profit date follows from these gates. Code can be completed
without finding a profitable strategy; retain a no-go outcome. The October 8 public
diagnostic now passes the unchanged clock guard and offline reconstruction for one
candle. This supersedes the old point-in-time clock failure, not the requirement for
fresh, continuously accepted observations. It did not open the operator database.

**Execution plan:**

1. DONE: independently verify the complete-source audit.
2. DONE: freeze, execute, and independently audit the corrected 212-month measurement.
3. DONE: retain S5 as nonqualifying long-term research; defer more S5 outcome work.
4. DONE for this checkpoint: reconcile software readiness and the three known
   regression failures; historical package suites and readiness integration pass.
   The historical package mismatch is runtime metadata drift (Python 3.12.13 to
   3.12.14); historical reconstruction tests now use recorded metadata. The R3 live
   runtime guard is separately tested. No old replay result has been rerun or changed.
   The readiness API verifies the amended measurement. The current native-intake
   checkpoint uses v55 capability evidence; final verification is recorded in
   `docs/46_AUREX_DELIVERY_REBASELINE.md`. Genuine missing external TradingView
   evidence remains a separate deferred requirement, not a native-path blocker.
5. IN PROGRESS: close native core mechanics. A local-only native intake now uses
   the existing risk and paper services, requires version/settings provenance,
   refuses live-enabled configuration, and cannot fabricate webhook receipts.
   Regression fixtures exercise costed paper entry/exit and rejection paths in
   disposable databases. They are not qualifying backtests or forward paper data.
   Future-dated signals are now rejected by the shared risk engine. No native
   HTTP endpoint, continuous market-data runner, or eligible strategy was added.
6. DONE for native paper scope: cost-aware sizing, quote affordability, and total
   strategy/account loss budgets. The native policy is BTCUSDT LONG only, one open
   position, explicit 100-unit starting equity, no borrowing; it includes rounded
   entry/stop-exit fees and slippage in modeled stop risk. Per-trade/daily/weekly
   fractions cannot exceed 0.5%/1%/3%; cumulative net strategy/account loss budgets
   are 10 units. Profit does not increase the risk base beyond initial capital.
   Cost assumptions and loss budgets are recorded, and execution rechecks approval.
   An orphan order without a trade blocks admission until the ledger is reconciled.
   These are modeled admission limits, not guarantees through gaps or real fills.
   Historical replay, imported evidence and the legacy research sizing semantics
   were not rewritten. The empty local paper account was aligned from the old
   1,000-unit default to the operator-approved 100; no trades, orders, positions or
   equity history existed, and the existing kill-switch state was preserved.
7. IN PROGRESS: connect causal closed-bar generation to native intake. Implemented
   a pure BTCUSDT 15m closed-bar preflight with UTC alignment, finite OHLCV, bounded
   freshness, continuity and warmup checks, existing replay indicator calculations,
   stable candle identities and hash-bound fixed-seed content cursors. Retries are
   no-ops; revised history, skipped bars and changed scope/parameters reject. A
   signal/bar consistency helper requires the same close time, price and spot scope.
   A bounded SQLite native processor now invokes these checks and commits each
   bar outcome/checkpoint with all signal/risk/paper effects in one transaction.
   Caller-managed native intake requires a real database transaction, not merely
   an ORM transaction. Existing intake callers retain their commit behavior.
   Records bind stream scope, bar content, request and signal result, with unique
   sequence/candle identities and a validated hash chain. Known retries return
   their original receipt without advancing the head or creating another order.
   The initial warmup seed is now retained in that same first transaction. The
   one-candle resume path reconstructs history from the seed and committed receipts,
   verifies every prefix hash, and rejects missing, orphaned or changed seed data.
   No external caller seed is required to resume an initialized stream. Old streams
   without retained seed data fail closed; the migration does not invent a seed.
   The processor itself does not acquire data, evaluate a strategy or schedule work. Explicit recovery
   can now close a modeled paper position, but qualifying online exits are unfinished.
   The processor is an opt-in local service, not a new API or a full native runner.
   The 4,096-bar legacy prefix remains bounded and never slides/reseeds. New v2
   receipts continue EMA/RSI/ATR and confirmed-hour EMA recurrences past that
   boundary, with explicit versioned hash-chain semantics and unchanged v1 bytes.
   State is reconstructed from retained inputs, not trusted solely because its
   receipt hash matches. Runtime receipt reads are paged; total audit time and
   database storage still grow. This is not an indefinitely qualified runner.
   Explicit `recover_next` now consumes one contiguous closed candle without any
   entry authority and records v3 FLAT/HELD/CLOSED recovery evidence. Existing
   costed close logic and conservative replay brackets are reused. Every touched
   position, including a held one, gets a non-qualifying recovery fill model.
   Partially observed entry bars use an explicit adverse stop bound, never a claim
   of an exact intrabar fill. Recognition time is current processing time, not a
   fabricated historical close time; costs and losses feed existing risk limits.
   The receipt and all ledger effects commit together. Normal processing refuses
   to advance an open position past its missing exit-management step. Missing
   candles or unreconciled state stop recovery rather than inventing a resolution.
   A separate read-only public acquisition client now retains raw HTTPS responses,
   reconstructs exact BTCUSDT 15m history and bounds clock skew, pagination, body
   sizes and request timing. It grants no execution or forward-paper authority.
   The real check reached Binance but rejected an approximately eight-second
   server/local clock discrepancy before fetching candles. The host uses managed
   domain time; no system settings were changed and the two-second guard remains.
   Source-bound v4 receipts now retain the full acquisition evidence and its canonical
   hash with seed/checkpoint/recovery effects. `process_sourced` separates SEED,
   CLOSED_BAR and RECOVERY purposes and has no signal argument. Observations record
   `SOURCE_OBSERVED_NO_ENTRY`, not a fabricated strategy evaluation. Raw bodies,
   normalization, scope, timing and seed linkage are reconstructed on every audit.
   Exact retries retain the original source; changed or dropped bindings reject.
   Existing v1-v3 receipts are unchanged, and later attachment cannot authenticate
   previously unbound history. Reconstruction still grants no live-origin authority.
   A one-shot `NativePublicObserver` now owns default public acquisition rather than
   accepting a caller packet, client or transport. It reads and closes a consistent
   stream snapshot before network I/O, requests exactly the next candle (or a fresh
   initial seed), and rechecks the expected head inside the atomic transaction.
   v5 receipts retain acquisition admission timing and previous-head linkage while
   preserving old receipt bytes. Repeated polls wait without refetching a committed
   witness. Missed observation windows stop; they never skip or backfill into forward
   evidence. Observation-only calls still block open positions; explicit exit management
   is described below. After online
   admission, new imported-only observations cannot silently drop that admission,
   including after explicit nonqualifying recovery. Local metadata is not a TLS
   signature; origin, entry and forward qualification flags remain false. No real
   observation was accepted and no operator migration was applied in this increment.
   `NativePublicObserver.manage_exits` now acquires the next fresh candle for an
   existing stream and records FLAT/HELD/CLOSED modeled exits in v6 receipts. Source,
   admission, frozen costs, ledger/account/position effects and checkpoint commit
   atomically. Existing conservative replay brackets handle gaps and ambiguous bars;
   partial entry candles retain explicit adverse bounds, not invented exact fills.
   Entry kill switches do not block this explicit exit-only operation. Recovery
   quarantine cannot be upgraded by later online processing, and the new online
   OHLC fill model is also nonqualifying. The path can manage an existing native
   paper position without authenticating its old entry/history. It cannot seed,
   enter, skip candles or silently recover a missed window. Old v1-v5 bytes persist.
   No real acquisition or operator migration occurred during this implementation.
   Pure bounded Jam features now retain trend/pullback EMA, previous ATR/pullback,
   volume SMA, DMI/ADX, local-reversal context and confirmed-hour EMA with exact
   replay arithmetic, including warmup, missing DX and restart behavior. This is
   not a strategy decision or source witness. A read-only `NativeJamHistoryReader`
   now binds the full Spot v1.0.1 settings fingerprint and reconstructs these features
   from the audited seed/receipt chain inside one pinned SQLite snapshot. Read-only
   storage is enforced; there is no caller candle/state-cache input or ledger write.
   Its exact head hash supports later stale-decision rejection but is not execution
   authority. Canonical internal spaces are now accepted in stream fingerprints;
   values are not rewritten, and control/outer whitespace still reject.
   NEXT: deterministic Jam evaluation and its managed-exit state, then atomic
   decision binding and a stoppable runner. The latest one-candle public diagnostic
   passes the clock guard; keep checking it on every acquisition. Recovery simulation is
   not a substitute for source-verified forward exits or supervision on data failure.
   Do not start a forward campaign before those components and failure stops work.
   Keep historical replay, synthetic mechanics and genuine forward observations
   separate. An inactive/rejected candidate must not execute to populate a report.
8. Advance a candidate only through preregistered costs, chronological validation,
   untouched holdout, execution parity where applicable, and forward paper evidence.
9. Require current sandbox/risk qualification and explicit micro-live approval before
   any real order. Measure realized profit net of all costs; retain a no-go outcome.

**Delivery discipline:** finish consecutive authorized local steps in the same work
session. Reuse verified implementations; add a new protocol only when assumptions,
data access, or research decisions change. Record results and the exact next action
at the top of this file. Keep research effort bounded by a concrete go/no-go question,
not by an obligation to find profit. Do not re-open rejected strategies by tuning
them on their already-observed outcomes.

**Delivery checkpoint:** deployment inspection and local hardening are complete.
The standard Uvicorn defaults could trust proxy headers and log query secrets;
the restricted ingress launcher disables both. The ordinary webhook now rejects
forwarding headers too. The public-facing app exposes only the frozen retired
candidate's webhook, requires direct HTTPS and exact reviewed senders, authenticates
before reading the body, bounds body size/time, and keeps all trading locks intact.
The complete v37 regression baseline passed 1,746 tests. Final review then delayed
DB-backed router imports until after configuration validation, so malformed settings
cannot bypass sanitized startup errors; new fresh-process regressions cover this.
Final v38 focused verification and audit details are in the delivery rebaseline.
The September 29 local database check matched then-head `20260718_0029`. A synthetic
preflight on that database opened read-only predicts `RISK_REJECTED` and no paper
execution. No alert, order, public listener, firewall change, purchase or cloud
deployment was made. Tests and diagnostic snapshots are recorded in
`docs/46_AUREX_DELIVERY_REBASELINE.md`.

**Exact resume point:** continue step 7 from the atomic processor in
`src/aurex/signal_gateway/native_processing.py`. Bar outcome and checkpoint are a
single append-only record in the signal/paper transaction, including no-signal and
rejected outcomes. No-signal is supplied by the caller, not yet an independently
verified strategy evaluation. The seed is now retained and verified with all
committed bar prefixes; `process_next` accepts one new or previously processed
candle after restart. Versioned continuation now removes the fixed-prefix stop
without reseeding or changing prior receipts. Exact replay arithmetic and hourly
visibility, restart/retry behavior, corrupted-state rejection, concurrent workers,
outer-commit failures and risk gates are covered in disposable fixtures. These
states cover preflight indicators, not every strategy-specific lookback feature.
Exit-only recovery is now implemented and tested in disposable ledgers. It accepts
only the next contiguous closed candle, never seeds a stream or submits a signal.
Changed mode/content retries fail. Recovery receipt audits reconstruct the bracket
decision and frozen entry costs and reconcile trade/position/account state. An
untracked manual close or skipped management interval requires explicit reconciliation;
it is not silently repaired. Current loss recognition is retained for risk accounting.
All positions touched by recovery are non-qualifying, even if recovery occurred on
time. No stale entry bypass was added: normal entry admission remains 180 seconds.
Read-only acquisition now exists in `src/aurex/signal_gateway/native_market_data.py`;
`scripts/check_native_public_data.py` acquires or reconstructs retained responses
without opening the operator DB. It uses only Binance's public time/klines host,
no credentials or order endpoints, with strict exact-range pagination and fail-closed
transport/data checks. Injected transports/clocks are labelled, never live proof.
The October 6 attempt stopped on `public_server_clock_skew`: its retained diagnostic is
`data/evidence/native_public_clock_blocker_20261006_v1.json`. The diagnostic is a
Windows shell report, not an accepted candle artifact. That attempt accepted no candles.
The October 8 one-candle diagnostic now passes the unchanged guard and reconstructs
offline; details and limitations are below. It is not an admitted online stream.
If disagreement recurs, stop and reconcile it without modifying organisation-wide
time configuration or relaxing the guard. Keep local development moving.
Source-to-receipt binding is now implemented in `native_source.py` and
`NativeBarProcessor.process_sourced`. v4 receipts retain the source response bytes,
canonical acquisition hash and explicit seed/closed-observation/recovery purpose
in the same transaction as every effect. Imported source records are reconstructed,
not treated as authenticated online observations. This path has no entry argument;
old raw paths cannot silently drop source tracking once attached. Retries require
the original witness, not a refetched packet with different timing metadata.
Initial seed/source consistency, continuation, rollback, process death, concurrent
workers, restart and rehashed corruption are covered using disposable fixtures.
No extra migration is needed and old receipt bytes remain unchanged.
Acquisition-owned admission is now implemented in `native_observation.py`: one bounded
poll, no imported packet or injected transport API, no entry or scheduler. v5 admission
records are committed with source and checkpoint; expected-head races, source/timing
changes, clock regression, stale windows and open positions fail closed. It can wait
for the next close without network/ledger writes and resume from retained state after
lost acknowledgement. It assumes trusted local Python code, not signed provenance.
Explicit recovery remains nonqualifying and cannot clear the online admission rule.
Explicit `manage_exits` now adds a source-bound one-candle paper management step.
v6 receipts bind FLAT/HELD/CLOSED results to acquired data and atomically reconcile
frozen-cost exits with account equity and positions. Legacy entry history stays
unattested, partial-candle fills remain conservative modeled bounds, and recovery
quarantine is permanent. The new `native_ohlc_online_exit_v1` fill model is excluded
from qualifying paper evidence. No public packet-based or signal/entry API was added.
Bounded Jam feature arithmetic is now implemented separately in `native_jam_features.py`.
It requires explicit bounded feature parameters, contiguous 15m candles, Decimal28
arithmetic and the existing 60-minute confirmed-hour semantics. Tests compare exact
values, including warmup/nulls, local reversal, serialization and the 4,096 boundary.
The maximum recent-candle buffer is 501; RMA seeds are discarded once initialized.
This is fixture-tested mechanics only. A structurally valid serialized state is
not proof of historical provenance or an eligible strategy. No existing receipt
schema, strategy registry, operator ledger or historical replay was modified.
`NativeJamHistoryReader` now binds full Spot v1.0.1 settings and reconstructs from
the audited retained prefix and paged continuation under one explicit read snapshot.
It opens a separate SQLite `mode=ro` connection with query-only enforcement, never
creates a missing database and does not persist state. Scope/head/settings mismatch,
corruption and live-enabled configuration reject. Source/online-from-seed coverage
is explicit and never upgrades origin or forward authority. Total audit time still
grows with the ledger; this is not an indefinitely qualified runner.
`native_jam_decisions.py` now supplies bounded pure setup and managed-exit state.
Full settings/scope/terms bind each state; only the next contiguous feature bar is
accepted. Pending expiry/cancellation, context/volume filters and confirmation reuse
the frozen geometry helpers. An entry proposal blocks advance until explicit
resolution; rejection consumes the proposal without inventing a fill or cooldown.
Managed exits check the old bracket before updating next-bar breakeven/trailing
stops; midpoint, pullback and time exits follow. Boundary-fill initialization excludes
pre-fill signal-bar highs. Partial entry candles reject, and historical window-end
liquidation is not a native scheduling rule. Outputs remain nonqualifying proposals.
Next bind these decisions to audited retained history and an exact receipt head,
reconstruct decision state, then revalidate the head/settings and current ledger in
the SAME transaction as risk approval, sizing, entry/exit effects and the receipt.
Do not trust caller-supplied fill acknowledgments or serialized state in that writer.
Preserve bracket-before-entry / close-exit-after-entry ordering, conservative partial
entry bounds, replay/retry identity and existing nonqualifying fill-model exclusions.
Define crash, rejected-entry, held-stop, open-position and changed-head tests before
enabling the new receipt path. No decision receipt schema or operator migration was
added in v55. Pure input hashes alone are not source or fill attestation.
Do not reactivate retired Jam or tune it using consumed outcomes. Follow with the
stoppable supervised runner. Connect source-owned entry decisions and define
eligible forward execution evidence before claiming a qualifying campaign; a fresh
OHLC source alone does not establish execution quality. Do not deploy the partial
runner against the operator ledger or begin a campaign before these pieces work.
Current processor provenance remains false; a local file hash or feed name alone
cannot turn an imported observation into trusted forward evidence. Missing data,
corrupt receipts, counter/disk exhaustion and unmanaged external changes still
need operational stop/alert/reconciliation handling. Recovery refuses such inputs;
it cannot guarantee position management while offline or without valid data.
No genuine forward campaign has started, and no strategy was qualified.
The processor currently supports one fixed stream in SQLite only. It does not
claim PostgreSQL support, cross-ingress account-wide serialization, cryptographic
authentication of a database administrator, or detection of wholesale ledger
replacement. Keep fixture mechanics and safe rejection paths separate from a
qualifying paper campaign. Do not reopen consumed research. Exchange tick/lot/
notional filters and current Testnet state are still separate execution prerequisites.
The new sizing uses internal ledger precision, not verified current exchange filters;
USD/USDT parity is explicitly a paper-model assumption, not an FX guarantee.
The September 27 implementation/profile alignment and September 29 post-interruption
risk verification are in docs/46. Read-only reinspection confirms 100 paper units,
zero paper orders/trades and live execution disabled; no second reset was performed.
The later September 29 closed-bar checkpoint only used synthetic fixtures and did
not modify the operator ledger. Its verification and limitations are also in docs/46.
The interrupted September 30 final report was recovered on October 4: 375 tests,
zero failures/errors/skips, 390.724 seconds. It is a historical checkpoint, not the
latest changed-source regression. The September 30 atomic-processing and October 4
seed-retention/migration checks used disposable databases only. Migrations
`20260930_0030` and `20261004_0031` are implemented and tested, not applied to the operator
database; the agent will perform the guarded upgrade when deploying the native
runner. Continuation uses receipt JSON and requires no additional migration.
Recovery also uses receipt JSON and requires no additional migration. No operator
command is requested. Verification and v55 evidence are in docs/46; acquisition
contracts and remaining operational requirements are in docs/49.
Assistant integration audit: local Python/CLI and a FastAPI management API exist,
but no Aurex MCP server or installed connector exists. Keep management private;
it lacks general authentication and some GET paths may write defaults. A local
read-only MCP adapter is a scoped follow-up, not a prerequisite or live authority.
See `docs/48_ASSISTANT_INTEGRATION.md`; no public access or connector was configured.
No routine commands are requested from the operator. The October 8 clock/public-data
diagnostic passed without a clock or tolerance change; archive and reconstruction:
`data/evidence/native_public_probe_20261008_v1.json`, SHA-256
`9078183e309cdd971cf78d5f77c563ccc239658bd1a2ff05776ba2ac6a639804`.
The bar closed at 11:15 UTC and was received at 11:26:43.895326 UTC, outside the
180-second entry window. It is a connectivity/clock diagnostic, not an accepted
online observation, stream seed or qualifying campaign. Continuous fresh acceptance
remains to be demonstrated; repeat clock disagreement must still stop. Do not return to hosting searches
or request TradingView payment: the user selected deferral. Genuine external
delivery and candidate-specific Pine trade parity remain missing, and the disabled
relay is unfinished. July 31 Testnet proofs do not establish current account state.
Do not invent external receipts, enable a retired candidate, alter the operator
ledger with test fixtures, restart S5 acquisition, rerun the consumed v2 measurement,
or create a new alpha family by default. Routine authorized commands are agent-run.

**Goal-tool limitation:** the existing app goal remains unfinished and has stale text
and a blocked status. The available goal API can change only terminal/pause status;
it cannot edit or resume that objective. This document is the updated working goal.
No false completion or duplicate goal is used to bypass that limitation.

## Canonical Sources

- Master goal and roadmap: `docs/00_AUREX_MASTER_PLAN.md`
- Current checkpoint, priorities, decisions, evidence, and resume point: this file
- Assistant-access inventory and proposed read-only connector: `docs/48_ASSISTANT_INTEGRATION.md`
- Detailed implementation history: `docs/01_IMPLEMENTATION_LOG.md`
- Historical data contract: `docs/05_HISTORICAL_DATASETS.md`
- Local reference replay contract: `docs/06_REFERENCE_REPLAY.md`
- TradingView parity contract: `docs/07_TRADINGVIEW_PARITY.md`
- Promotion contract: `docs/08_TRUSTED_BACKTEST_PROMOTION.md`
- Frozen TradingView run contract: `docs/09_FROZEN_TRADINGVIEW_RUN.md`
- Strategy research and contamination policy: `docs/11_STRATEGY_RESEARCH_DOCTRINE.md`
- TradingView webhook evidence contract: `docs/12_TRADINGVIEW_WEBHOOK_EVIDENCE.md`
- Frozen volatility-breakout candidate: `docs/13_VOLATILITY_BREAKOUT_PREREGISTRATION.md`
- Rejected-strategy failure analysis: `docs/14_STRATEGY_FAILURE_ANALYSIS.md`
- Frozen slow spot candidate: `docs/15_SLOW_BREAKOUT_SPOT_PREREGISTRATION.md`
- Post-rejection research reset: `docs/16_STRATEGY_RESEARCH_RESET.md`
- Operator-profile intake and freeze boundary: `docs/17_OPERATOR_PROFILE_INTAKE.md`
- Binance Spot Testnet qualification: `docs/20_BINANCE_TESTNET_PHASE2_TRACKER.md`
- Jam Reversal Spot preregistration and rejection:
  `docs/21_JAM_REVERSAL_SPOT_PREREGISTRATION.md`
- Jam successor mechanism charter:
  `docs/22_JAM_SUCCESSOR_HYPOTHESIS_CHARTER.md`
- Jam archive-quality remediation:
  `docs/26_JAM_ARCHIVE_QUALITY_REMEDIATION.md`
- Jam successor causal feature specification:
  `docs/27_JAM_SUCCESSOR_FEATURE_SPECIFICATION.md`
- Jam successor development feature distribution:
  `docs/28_JAM_SUCCESSOR_DEVELOPMENT_DISTRIBUTION.md`
- Jam successor event and outcome protocol:
  `docs/29_JAM_SUCCESSOR_EVENT_OUTCOME_PROTOCOL.md`
- Jam successor development event prevalence:
  `docs/30_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE.md`
- Jam successor development outcome and terminal rejection:
  `docs/31_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME.md`
- Strategy-factory readiness closure and next authority:
  `docs/32_AUREX_STRATEGY_FACTORY_READINESS.md`
- Q1 USD-M raw-trades structural payload pilot:
  `docs/37_PERIODIC_FLOW_USDM_RAW_TRADES_PAYLOAD_PILOT.md`
- Q1 paired full-development acquisition protocol:
  `docs/38_PERIODIC_FLOW_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL.md`
- Q1 successor acquisition terminal decision and exact boundary:
  `docs/40_PERIODIC_FLOW_SUCCESSOR_ACQUISITION.md`
- S1 macro-financial-conditions lineage, source adjudication, and exact boundary:
  `docs/41_S1_MACRO_FINANCIAL_CONDITIONS.md`
- S2 Bitcoin settlement-demand charter and exact source-feasibility boundary:
  `docs/42_S2_ONCHAIN_SETTLEMENT_DEMAND.md`

## Master Goal

Build Aurex's core non-Kalshi system into an evidence-first strategy research,
validation, risk, and paper-trading platform that can reject weak strategies safely
and operationalize a strategy only when reproducible evidence and capital-protection
controls justify progression. Preserve the original Stage 1-10 roadmap. Binance
Vision is the primary historical replay source, authenticated TradingView webhooks
are the external Pine signal path, TradingView MCP is an additive research/parity
tool, and deterministic exchange APIs are the only acceptable future execution path.
Live trading remains disabled until every required gate passes and a human explicitly
approves it.

The immediate objective is not to tune another strategy until it looks profitable.
V2 P01 stopped before return calculation because zero symbols met its frozen
strict-continuity rule. V3 is closed after its no-return feasibility screen selected
zero primaries. V4 now has a frozen crash-safe discovery charter and a frozen
no-return proposal register containing only two independent theories:
inventory-backed same-asset cross-venue arbitrage and delta-hedged crypto
variance-risk-premium harvesting. One of three proposal slots is deliberately unused;
neither mechanism is selected, parameterized, or return-tested. V4P01 has completed
its bounded source-feasibility round and is rejected before primary selection. Its
two metadata and six payload requests all completed with zero retries, but recovery
snapshot schema, upstream source revision identity, point-in-time fees, and
point-in-time filters/product/venue state failed hard gates. A documented
`availableTo` interpretation defect and a Binance wire-symbol case defect are
preserved in separate correction artifacts; neither changes the rejection or permits
a retry. V4P02 implemented and passed a crash-safe synthetic census runner, then
consumed its one metadata attempt. Tardis declared a `203,310,405`-byte response
against the frozen `8,388,608`-byte maximum; Aurex rejected it from headers, accepted
zero body bytes, made zero retries, and consumed none of the 27 dataset HEADs. V4 is
now closed by a terminal no-return screen selecting zero primaries. A separately
frozen post-V4 capability review prohibits successor alpha discovery until the
operator freezes the intended venue, product scope, account/API access, starting
capital, maximum loss, and data-acquisition budget. The credential-free typed
operator-profile contract, shared no-write workflow, status/template/preflight API,
dedicated dashboard intake, and template/preflight/freeze/check CLI are implemented
and verified. The HTTP layer cannot freeze or write an artifact, rejected values are
not echoed, and any edit invalidates export handoff. No real profile artifact exists
because the operator has not supplied those values. The independent Stage 3 track
now binds each webhook receipt to the exact reviewed TradingView sender-host
configuration, blocks broad CIDR or
undocumented-host false proofs, exposes paper/live/broker side effects, and has a
database-backed template/preflight/freeze/check package for one genuine alert-log
safe-rejection proof. That code is verified, but no external proof exists because
TradingView has not sent the bounded alert and no genuine alert-log artifact has
   been supplied. The independent frozen-v1.3 parity path is now code-ready under a
   protocol-bound paired-export contract: Aurex must reconcile a matching TradingView
   chart OHLCV export exactly against the checksum-verified Binance Vision reference,
   verify that the Strategy Tester report consumed the exact frozen protocol, and
   require a reviewed operator-attested lineage hash before comparing any trade.
   Missing or stale lineage blocks the run; any valid candle mismatch freezes a failed
   comparison before trade matching. No authentic TradingView chart export, Strategy
   Tester export, paired-export attestation, or real parity verdict exists yet, and
   parity cannot change v1.3's rejection. Critical evidence controls are also part of
   the safety boundary: the active workspace must remain visible on mobile, missing
   values must render explicitly, and lineage/compare/record actions must remain
   fail-closed until their evidence exists. Asynchronous action locks must remain
   separate from renderer-owned eligibility and risk policy so request cleanup cannot
   re-enable a control that new evidence has disabled. Local desktop/mobile runtime
   verification now confirms those conditions for the paired-lineage workflow.
   A fresh read-only TradingView identity check on `2026-07-30` observes
   `BINANCE:BTCUSDT` at `30m` with `Aurex jam_reversal_v1` as a study and no strategy
   metrics. That state is not the frozen `trend_pullback_v1` v1.3 `15m` run and cannot
   satisfy parity. The local jam file remains the historical v1.14 `strategy()` hash,
   but the current chart source could not be read without opening Pine Editor, so the
   matching display name does not establish current source identity. Preserve every
   prior outcome and do not
rescue it through after-the-fact retries, thresholds, request resizing, or
reinterpretation. Only a future candidate that survives untouched validation may
   enter Pine parity and forward paper operation. Aurex pursues profit by preserving
statistical honesty and capital, not by presuming that an edge exists.

The current Jam successor lineage has completed and failed its frozen 2019-2020
development outcome screen. Aggregate trades remained the primary source, 4,161
global defective minutes remained quarantined, and the exact five-condition event
produced 991 accepted outcomes. Deterministic matching found 456 controls. After
base costs, mean 30-minute return was `-16.008098281388651150` bps and profit
factor was `0.464374516027724364`; stress mean was
`-26.189788269683100509` bps. Bootstrap lower bounds were negative, neither year
and none of eight quarters were positive, and only 3/11 gates passed. An
independent 24-month reconstruction reproduced both ledgers and the result
byte-for-byte. Decision: `STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.
The event definition is retired. The 2021 validation and 2022 holdout partitions
remain sealed, and no candidate, strategy, signal, trade, or authority was created.

The aligned priority order is fixed: obtain and independently freeze the real
non-secret operator capability facts; complete frozen-v1.3 parity and one authenticated
webhook proof only under their explicit external authority boundaries; design a new
successor charter only after the operator profile permits charter design; then require
untouched backtest eligibility, forward paper evidence, exchange sandbox qualification,
explicit micro-live approval, and finally the first settled `$100` net-profit milestone.
No implementation convenience, UI state, synthetic test, or promising metric may skip
that order.

When every permitted preparation and safety audit is complete but the next evidence
requires operator facts or explicit external authority, Aurex must pause. It must not
manufacture synthetic exports, inferred account facts, speculative strategy work, or
unrequested TradingView mutations merely to appear active. The resumed read-only
identity path is now also exhausted: current chart identity and the local jam source
are known, but binding the loaded source requires opening TradingView UI.

## Program Success Contract

Aurex is successful only when the following claims are supported in order:

1. A separately versioned strategy shows positive net expectancy and controlled
   drawdown on genuinely untouched evidence under realistic costs.
2. Pine and Aurex agree at trade level where TradingView supplies the signal logic.
3. Forward paper operation reproduces the expected behavior with complete delivery,
   fill, fee, reconciliation, and failure evidence.
4. Exchange sandbox operation proves deterministic order lifecycle, balances,
   positions, retries, idempotency, monitoring, and kill switches.
5. Explicitly approved micro-live operation preserves every risk rule. Only then may
   Aurex pursue the first `$100` of settled net profit.

No stage promises profit. A failed strategy is useful progress only when its negative
evidence is preserved and the next hypothesis remains statistically honest.

## Current State

Checkpoint: `2026-08-27T06:26:00Z`

Active resume point: Q1 remains terminal. S1 v1 is terminal after a checksum-valid
Binance archive lacked the preregistered exact 00:00 UTC bar. S1.1 then froze a
separately versioned, source-availability-only first-valid-Friday-bar amendment before
inspecting the remaining 255 dates, declared 21 prior development price exposures,
and corrected the v1 partial-checkpoint resume defect. Its source run passed all 11
gates with 277/277 prices, 22 exact-hash reuses, 510 new requests, and one 600-minute
delayed activation. The sole promotable consistent-easing primary was then executed
once under frozen costs and gates. It passed 7/12 development gates and is rejected.
Base return was `7.6958%`, but PF was `1.01395`, drawdown was `66.3009%`, only 2/5
full years were positive, and the stress-bootstrap lower bound was negative. The
three diagnostics remain non-promotable. Validation and holdout remain sealed.

Terminal outcome result/audit hashes are
`8d900beb2dcbfcb0d11fed1f8ee0a99ecfa812e03900dae21a886973f86cc317` /
`ab1f10d0208560933e048f1fb93e5b03f0988048e7c4b5e6057dba14b0c2495d`.
Decision: `STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED`; lineage next authorization:
`NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED`. The only permitted program continuation is
`AUTHORIZE_POST_S1_FAILURE_ANALYSIS_PROTOCOL_ONLY`. Do not tune the primary, promote
a diagnostic, or open validation. Pine, paper, Testnet strategy orders, production,
live, and real-profit authority remain false. Real net profit remains `$0`.

Program continuation: `TESTNET VIRTUAL CANCEL LIFECYCLE AND RECONCILIATION VERIFIED
FROM PRESERVED COMPLETE CHECKPOINT / PHASE 2B FILL, FEE, AND BALANCE RECONCILIATION
INDEPENDENTLY VERIFIED / PHASE 2C USER-DATA, RECONNECT, AND REST GAP RECOVERY
INDEPENDENTLY VERIFIED / PHASE 2D RESTART, IDEMPOTENCY, KILL-STOP, AND SOAK
INDEPENDENTLY VERIFIED / BINANCE SPOT TESTNET ADAPTER SANDBOX-QUALIFIED`. The
separate production profile remains 7 of 9 and blocked. This is an
execution-sandbox boundary, not a claim that any strategy is ready or profitable.
The separately preregistered `jam_reversal_spot_v1` v1.0.1 historical decision is
also complete and rejected: 14 trades, `-$0.5371`, PF `0.8301`, negative OOS, and
zero of six passing folds. Paper and production authority remain false.
The Jam successor development outcome result is complete under evidence hash
`560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430`
and independent audit hash
`8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`.
Only 3/11 frozen gates passed on 2019-2020. The terminal artifact authorization is
`NONE_DEVELOPMENT_OUTCOME_FAILED`; validation, holdout, candidate, signal,
strategy, paper, Testnet strategy-order, production, and live authority remain
false.

The Aurex strategy-factory readiness audit is now closed for pre-strategy work.
The frozen baseline found 11/15 passing gates, four partial gates, and three
research blockers. Aurex then implemented a universal strict acceptance contract,
machine-readable lifecycle enforcement, and canonical operator readiness
visibility without creating or evaluating a strategy. The current independent
rescore is 14/15 PASS, 1 PARTIAL, and 0 FAIL. All research-required gates pass.
The remaining partial gate is one genuine authenticated external TradingView
delivery proof; it is downstream of mechanism research and cannot be replaced by
an internal test. The factory contract evidence hash is
`8676ffc5caea7782607ad7e9072e71ab8e09fbd93fe115f47c8860833f33f50e`.
Every current registered strategy is `RETIRED`, `QUARANTINED`, or
`RESEARCH_ONLY`; zero are `ACTIVE` or enable-eligible. Authorization is
`READY_FOR_STRATEGY_CHARTER_ONLY`. Paper, Testnet strategy-order, production,
live, and real-capital authority remain false. Real net profit remains `$0`.
Runtime browser verification then exposed and closed one operator-truth defect:
the Command preview and initial research resources still inherited the retired
deployment-plan strategy. Strategy context is now loaded only from an `ACTIVE`,
evidence-qualified registry definition. With none present, Command reports `No
qualified strategy`, `Research only`, and `Capital protected`; backtest and Pine
inputs no longer silently default to a retired strategy. The readiness rescore is
being preserved as a new current-result generation rather than overwriting the
earlier immutable checkpoint. The live boundary now states `LOCKED / no execution
authority`, matching the canonical paper, Testnet strategy-order, and live flags.

The first post-readiness charter is now frozen and independently reconstructed.
Q1 studies whether causally completed positive Binance USD-M BTCUSDT perpetual
order-flow imbalance at UTC quarter-hour boundaries can later predict after-cost
BTCUSDT Spot continuation. It permits long or cash Spot research only; it permits
no futures order, short, margin, leverage above `1x`, or real capital. Charter hash
`17e9a73193a0c159aa6d3a15fea2412285e3cd12a5a4e0e52e3e27bcf4fa195b`
and audit hash
`ad6a76574af1f3ff5dbf91f0ed42f6c1c066ff8746b7202bf0fc1c2e0373096a`
bind zero market values, returns, parameters, candidates, executions, and orders.
The only next authorization is
`AUTHORIZE_Q1_METADATA_ONLY_BTCUSDT_ARCHIVE_CENSUS`.

The Q1 metadata census completed and independently reconstructed all 144 frozen
official checksum targets, covering 72/72 paired BTCUSDT Spot and USD-M perpetual
months from 2020-01 through 2025-12.
Contract hash
`841caf8e7dc20d21722247759f9804f5f896ac5936c40d8000467a96a03acb90`,
result hash
`54dbfba6642b9057172f32405d7ed983bb66488acd0ab31d6e26358926d41a17`,
and audit hash
`b9d62a43c6ac1af25f70d67f4ff8929e78c5b31b1c2e5017d9481ecacc12b18f`
preserve zero archive HEAD requests, payload requests, payload bytes, market-value
fields, parameters, returns, candidates, executions, and orders.

The separately frozen 2020-01 paired payload pilot then inspected exactly two
checksum-pinned archives. Spot `aggTrades` passed. USD-M `aggTrades` had complete
clocks and contiguous aggregate IDs but 505 adjacent raw-range discontinuities.
The remediation separated 504 forward gaps, compatible with Binance's documented
exclusion of insurance-fund and ADL trades, from one invalid adjacent overlap. A
checksum census localized that overlap to `2020-01-15`: aggregate IDs `22154875`
and `22154876` both referenced raw trade ID `30414701` at timestamp
`1579076873303`. The frozen daily cross-source adjudication reproduced the defect
in official daily `aggTrades` and found the raw trade exactly once in official
USD-M raw `trades`. Aurex therefore rejects USD-M `aggTrades` for Q1 and permits
only a separate checksum-only USD-M raw `trades` monthly metadata-census protocol.
No price or quantity value, return, parameter, signal, strategy, or order was
opened by this source decision.

The USD-M raw `trades` metadata census is now complete under a separately frozen
and pre-network-audited protocol. All 72 official monthly checksum sidecars from
2020-01 through 2025-12 were present on their first attempt: 48/48 development
months and 24/24 validation-metadata months. Protocol hash
`08ca0b4fce3790b398f3535511d19915b3a8b80e6e8c5c1326c6caf9198e9e6e`,
result hash
`64da0748128779cbfc040883437a1523e571fe68b3746decc9bc7adccc7c793a`,
and result-audit hash
`e29b821c8795482dc64f25230d6f2d50c3f9feccda48a22326ec81de2c68c95a`
preserve zero archive HEAD requests, payload requests, payload bytes, market
numeric fields, parameters, returns, candidates, executions, and orders. The next
authorization was to freeze a one-month 2020-01 USD-M raw `trades` payload protocol
binding the already qualified Spot `aggTrades` evidence.

That protocol was frozen and independently reconstructed before one exact payload
request. The checksum-pinned USD-M raw `trades` archive contained 10,281,248 rows,
covered all 44,640 January minutes, had zero duplicate or non-increasing trade IDs,
zero timestamp regressions, 726 forward gaps totaling 1,809 skipped IDs, and a
maximum single omission of 35 IDs. Both buyer-maker states were present. It paired
with all 44,640 qualified Spot minutes and passed every predeclared structural gate.
The request-attempt journal is hash-bound in canonical result v2. This proves source
capability for one development month only. It does not prove an economic feature,
signal, strategy, predictive edge, or profit.

The paired full-development acquisition protocol is now separately frozen and
independently reconstructed before another payload request. Its exact 2020-2023
matrix contains 96 targets: 48 Spot `aggTrades` and 48 USD-M raw `trades`. Thirty-
seven local archive candidates may be reused only after fresh checksum and
structural revalidation; at most 59 targets may require network acquisition. The
runner must stream one archive at a time, write a marker before each attempt,
checkpoint every qualified archive, discard partial files, and enforce the frozen
100 GB new-payload and 20 GB post-acquisition disk-reserve ceilings. Price,
quantity, quote quantity, features, parameters, outcomes, validation, holdout,
Pine, paper, Testnet strategy orders, production, and live remain forbidden.

| Stage | Classification | Current evidence |
| --- | --- | --- |
| 1. Pipeline audit | PROVEN | Core pipeline and blockers documented and tested. |
| 2. Pine validation | READ-ONLY CHART IDENTITY KNOWN / CURRENT JAM SOURCE BINDING UNPROVEN / PARITY CODE-READY | The live chart is `BINANCE:BTCUSDT` `30m`, contains a same-named jam study, and has no strategy metrics. The local v1.14 file is a `strategy()` with the unchanged historical hash, but current chart source retrieval requires opening Pine Editor and was not authorized. Display-name equality is not source identity. The chart is neither the frozen v1.3 `15m` state nor parity evidence; no authentic exports, attestation, or parity verdict exist. |
| 3. Webhook | CODE-READY / PROOF PACKAGE READY / UNPROVEN EXTERNALLY | Auth, exact-body receipt hashing, exact documented-host configuration binding, idempotency, normalization, risk routing, side-effect verification, and immutable external-proof packaging exist. Broad CIDRs cannot produce proof. Internal tests cannot masquerade as TradingView evidence; no genuine alert receipt or alert-log artifact exists yet. |
| 4. Real backtesting | S2 CHARTER FROZEN / SOURCE METADATA AND QUERY-COST FEASIBILITY NEXT / ZERO QUALIFIED STRATEGIES | The reusable factory mandates development, validation, and separate holdout partitions, cost stress, bootstrap uncertainty, multiplicity control, walk-forward, regime, drawdown, and concentration evidence. Q1 and S1 are terminal. S2 now binds one distinct Bitcoin on-chain settlement-demand family, its raw-source boundary, five chronological partitions, and exact exclusions before blockchain or market outcomes. Only BigQuery metadata and bounded dry-run cost checks are next; no numeric data, parameter, signal, return, candidate, or order has been authorized. Source feasibility cannot establish edge. |
| 5. Eligibility | NO ELIGIBLE STRATEGY / V4 CLOSED / TESTNET PROFILE FROZEN 9 OF 9 / PRODUCTION PROFILE 7 OF 9 | A separate Binance Spot Testnet capability profile is frozen and independently verified for `BTCUSDT` Spot at `1x`, simulated `$100` equity, and protective `$0.50` per-trade, `$1.00` daily, and `$10.00` total loss limits. It authorizes adapter implementation, successor-charter design, Testnet requests, and virtual Testnet orders only. It does not create strategy, return, paper, sandbox-qualification, production, live, or capital authority. The production operator draft remains blocked on account/API and Zimbabwe venue/legal verification. |
| 6. Paper evidence | IMPLEMENTED BUT NOT STARTED FOR AN ELIGIBLE STRATEGY | Evidence-grade costed execution exists; no eligible forward campaign exists. |
| 7. Operator UI | CANONICAL PLATFORM READINESS VISIBLE / LIFECYCLE ACTIONS FAIL-CLOSED | `/system/readiness` validates the current rescore, factory contract, and every bound source hash before reporting research readiness. Command renders the exact platform gate counts, zero qualified strategies, downstream external-signal proof, paper authority, sandbox capability, and next action. Strategy rows display lifecycle and disable enable actions for every current version. The existing operator, parity, and evidence views remain available. |
| 8. Live readiness | TESTNET ADAPTER SANDBOX-QUALIFIED / PRODUCTION AND LIVE INTENTIONALLY BLOCKED | Phase 2A-D evidence now independently reconciles. Phase 2D run `aurex-run-ca2c2b4a5b5cfc71` used processes `656`, `48024`, and `57776`, submitted order `22377060` exactly once, resolved it idempotently after process restart, enabled the durable kill-stop before cancellation, blocked another entry locally, and finished `CANCELED` with zero execution, no trades, no open orders, and exact BTC/USDT balance restoration. The `602.766` second soak recorded 120 REST heartbeats, 21 authenticated reconciliations, two forced reconnects, three subscriptions, and no reset. Source hash `8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50` and audit hash `0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29` are preserved under decision `BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED`. Strategy eligibility, production, live, real-capital authority, and profit remain false. |
| 9. Micro-live | NOT STARTED | No real capital authorized. |
| 10. First $100 | NOT STARTED | Real net profit remains `$0`. |

## Pre-Resume Git Checkpoint

- Branch: `main`
- Commit: `02474d623e3cfd48267a5b5aebba992758e49daf`
- Status: intentionally dirty with extensive existing Aurex research/UI changes,
  evidence artifacts, and modified nested repositories `My-Krypt-Trader` and
  `tradingview-mcp-jackson`.
- Safety decision: treat all unrelated modifications as user/prior-program work. Do
  not reset, clean, stash, checkout, or revert them; work only with scoped files.
- Current V3 additions are uncommitted and must remain bound by their artifact/source
  hashes rather than an assumed clean Git state.

## Execution Plan

1. [COMPLETE] Complete strict documented-outage replay validation and tests.
2. [COMPLETE] Restore Ruff, focused replay/dataset tests, and the complete test suite.
3. [COMPLETE] Restart Aurex from current code and verify health/live-disabled state.
4. [COMPLETE] Run and persist the complete 2023-2026 `trend_pullback_v1` v1.3 replay.
5. [COMPLETE] Bind the replay to a chronological protocol and evaluate all eligibility gates.
6. [COMPLETE] Record the `REJECT` verdict and preserve negative evidence.
7. [COMPLETE] Establish read-only TradingView chart and source identity.
8. [AWAITING EXPLICIT MUTATION AUTHORITY] Run bounded v1.3 trade-level parity.
9. [CODE READY / EXTERNAL RUN PENDING] Complete a genuine authenticated TradingView delivery and preserve its delivery/risk evidence without bypassing eligibility.
10. [FAILED HONESTLY] Freeze `volatility_breakout_v1` v1.1, but preserve that its first
    protocol transaction rolled back and its durable protocol was registered after the
    replay.
11. [COMPLETE / RETIRED] Record and audit the deterministic volatility replay as
    diagnostic negative evidence: 1,125 trades, `-$533.87`, PF `0.6734`, and 0/6
    walk-forward folds.
12. [COMPLETE] Add evaluator v1.2 temporal binding plus durable, commit-verified
    candidate registration that refuses candidates with existing outcomes.
13. [COMPLETE] Attribute both rejected mechanisms and preserve deterministic analysis
    hashes without converting outcome-conditioned buckets into new rules.
14. [COMPLETE] Import and audit native 4h BTC development plus untouched ETH/SOL data.
15. [COMPLETE] Implement, test, freeze, and durably preregister
    `slow_breakout_spot_v1` v1.0.0 with explicit execution-spec binding.
16. [COMPLETE / REJECTED] Execute one atomic ETH/SOL holdout campaign, record and audit
    both validations, and apply the frozen cross-market decision rule.
17. [BLOCKED BY ELIGIBILITY] Do not permit slow spot parity or forward paper evidence;
    both individual validations failed and v1.0.0 is retired.
18. [COMPLETE] Complete mechanism-level failure attribution and define a
    portfolio-aware, statistically coherent research reset before another candidate.
19. [COMPLETE / FOUNDATION] Implement deterministic shared-capital spot portfolio
    replay, tamper-detecting audit, and a hash-audited contamination ledger.
20. [COMPLETE] Freeze and offline-audit a survivorship-aware market-universe manifest,
    raw source snapshot, contamination binding, and four-part data boundary before
    importing or inspecting another strategy outcome.
21. [COMPLETE / DEVELOPMENT DATA ONLY] Import and offline-audit checksum-verified 4h
    OHLC for the 38 included markets over `2023-01-01` through `2024-12-31`. The frozen
    bundle contains 166,668 exact candles; validation, holdout, and forward remain
    unopened.
22. [COMPLETE / FROZEN PRE-OUTCOME] Predeclare the R3 economic hypothesis, one fixed
    primary, two non-selectable falsification variants, six quarterly folds, shared
    capital, costs, concentration controls, and all-or-nothing advancement gates.
23. [COMPLETE / FROZEN PRE-OUTCOME] Freeze exact timestamp, ranking, ATR, stop, fill,
    allocation, fold-reset, liquidation, metric, cost-stress, and leave-one-market-out
    semantics in a separately hash-bound execution contract.
24. [COMPLETE / FROZEN PRE-OUTCOME] Implement and test the deterministic R3 research
    engine, then freeze its source, runtime, transformed-data, and exact 62-replay run
    package before calculating any development result.
25. [COMPLETE / NO CANDIDATE] Execute R3 once, preserve every primary, falsification,
    fold, cost-stress, concentration, and leave-one-market-out result, and apply the
    frozen rule. The primary passed 9/10 gates but only 3/6 positive folds, so it did
    not advance.
26. [COMPLETE / DIAGNOSTIC ONLY] Preserve the immutable v1 ledger and publish a
    separately hash-bound correction for midnight monthly-boundary labeling. The
    correction affects no trade, metric used by a gate, gate result, or verdict.
27. [COMPLETE / DESCRIPTIVE ONLY] Execute the frozen failure analysis using only stored
    R3 artifacts and opened development data. The deterministic result passed all five
    continuation criteria and returned `PROPOSE_BOUNDED_R3_1`; it created no candidate,
    changed no R3 gate or verdict, and opened no sealed partition.
28. [COMPLETE / FROZEN PRE-R3.1-OUTCOME] Register exactly one R3.1 path-quality
    hypothesis. Keep the 84-day/14-day schedule and all portfolio/risk gates fixed;
    replace only endpoint-return ranking with positive OLS log-price slope times
    regression R-squared. One parameter set is selectable, so no best-variant selection
    or multiplicity correction is permitted.
29. [COMPLETE / FROZEN PRE-OUTCOME] Freeze exact R3.1 arithmetic and execution semantics, then
    implement and verify its engine only on synthetic fixtures. Bind source, runtime,
    transformed development data, and the complete run matrix before calculating any
    R3.1 development return.
30. [COMPLETE / PERMIT R4 PREREGISTRATION] Execute R3.1 once and apply every frozen
    gate. All 44 replays completed, all 9/9 gates passed, and a full deterministic
    replay reproduced the ledger. R3.1 itself creates no eligibility.
31. [COMPLETE / FROZEN PRE-OUTCOME] Freeze the unchanged R4 path-quality candidate,
    checksum-verified 2025 validation bundle, terminal-market execution semantics,
    deterministic engine, runtime, source lineage, transformed data, and exact
    42-replay package before calculating any 2025 strategy outcome.
32. [COMPLETE / RETIRED] Open 2025 exactly once, execute and preserve all 42 R4
    replays, apply the nine frozen gates, and complete both stored-artifact and full
    deterministic audits. R4 passed 4/9 gates and returned `RETIRE_R4_CANDIDATE`; it
    permits no Pine parity, paper, sandbox, or live progression.
33. [COMPLETE / FAMILY STOPPED] Freeze and execute a bounded R4 failure analysis
    using only the stored 42-run evidence. The signal lost `-$52.02` before modeled
    costs, 1/4 quarters and 3/12 months were positive, and 0/35 leave-one-market-out
    runs recovered positive net P/L. The deterministic decision is
    `STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY`.
34. [COMPLETE / FROZEN BEFORE DISCOVERY] Freeze a U1 mechanism-discovery charter
    that permits up to three theory-only proposals but at most one return-tested
    mechanism and one selectable parameter set. Preserve 2025 as internal validation,
    require the sealed 2026 holdout for eligibility, and prohibit every R4-derived
    rescue rule.
35. [COMPLETE / NO RETURN METRICS] Evaluate exactly three independent premises by
    research support, point-in-time data feasibility, and current execution fit. Select
    `P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA` for protocol design; defer signed-jump
    risk for missing high-frequency data and funding carry for missing derivatives
    data and execution controls. No candidate or return was created.
36. [COMPLETE / RETIRED] Freeze the exact U1 primary hypothesis,
    benchmark, volatility estimator, exposure rule, basket construction, parameters,
    shared-capital execution, costs, folds, run matrix, gates, and stop decision before
    calculating any 2023-2024 development return. Execute the frozen 47-run campaign
    once and complete both artifact and full deterministic audits. U1 passed 11/13
    gates but failed maximum drawdown and temporal robustness, so the mechanism is
    stopped without a rescue variant.
37. [COMPLETE / NO-RETURN CAPABILITY AUDIT] Preserve the U1 stop and audit the local
    and official-source capability boundary for a genuinely different,
    lower-directional-risk lineage. The frozen V2 audit found audited spot OHLCV ready
    and 11 derivatives data, execution, collateral, liquidation, reconciliation, and
    adapter capabilities blocked.
38. [COMPLETE / METADATA ONLY] Freeze a 5,040-check archive census contract covering
    all 35 symbols, all 24 development months, and six one-minute spot/perpetual,
    funding, mark, index, and premium data families. It permits checksum metadata only
    and prohibits archive payloads, market-data import, mechanism selection, and
    return calculation.
39. [COMPLETE / FOUNDATION ONLY] Execute and freeze the metadata-only source census.
    The immutable 5,040-record result found 31 complete symbols and 250 observed
    `404` responses across four incomplete symbols. The threshold passed without
    inspecting an archive payload, market-data value, strategy outcome, or return.
40. [COMPLETE / FROZEN PRE-PAYLOAD] Freeze a deterministic resource/schema pilot
    over the first, median, and last complete symbols; first, middle, and last census
    months; and all six families. Pin all 54 census checksums, cap compressed and
    uncompressed bytes, and prohibit automatic full acquisition.
41. [COMPLETE / SCHEMA-RESOURCE PASS] Implement and execute only the 54-target
    acquisition pilot. All targets passed checksum revision, byte, ZIP safety, schema,
    finite-value, ordering, and timestamp gates. The result permits design of a
    separate full-acquisition protocol but does not authorize that download.
42. [COMPLETE / SYNTHETIC FOUNDATION] Freeze, implement, and audit synthetic-only
    paired execution, signed funding settlement, fees, collateral, margin,
    liquidation/ADL, partial-fill rollback, kill switch, and reconciliation
    semantics. All 14 frozen scenarios pass without real market data.
43. [COMPLETE / NO RETURN METRICS] Freeze a separate V2 discovery charter and screen
    exactly three lower-directional-risk premises. Select
    `P01_POSITIVE_FUNDING_SPOT_PERP_CARRY` for full-data and protocol design only;
    keep premium convergence nonselectable and reject reverse carry under this
    charter because historical spot-borrow state and reverse execution are absent.
44. [COMPLETE / METADATA ONLY] Freeze the exact eight-requirement P01 metadata-source
    contract. Preserve its deterministic failure when the Binance documentation
    catalog returned an empty HTTP 202 body; supersede only the two inaccessible source
    URLs under v1.1 without changing any requirement, marker, permission, or outcome
    boundary.
45. [COMPLETE / PROTOCOL DESIGN PERMITTED] Execute the four-source v1.1 audit without
    credentials, private endpoints, stored response bodies, market values, or returns.
    Preserve that only funding and price archives are directly historical, six
    requirements block unqualified historical replay, five permit conservative
    research-only overrides, and lifecycle continuity has no override.
46. [COMPLETE / FROZEN PRE-PAYLOAD AND PRE-RETURN] Freeze one integrated P01
    full-acquisition and development protocol. Bind all 4,464 source targets, the two
    current public filter snapshots, exact normalization, resource ceilings, one
    parameter set, paired execution, costs, margin overrides, eight temporal folds,
    35 runs, all-or-nothing gates, and automatic retirement.
47. [COMPLETE / P01 RETIRED BEFORE RETURNS] Implement and execute the checksum-bound
    full acquisition and qualification runner. All 4,464 archives and 163,010,201
    rows were inspected; 255/3,720 kline archives failed strict continuity and every
    symbol had at least one gap. The immutable audited decision is
    `STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA`. No signal, trade, P/L, or
    return was calculated.
48. [COMPLETE / FROZEN PRE-PROPOSAL] Freeze a V3 discovery charter before another
    proposal screen. Require actual payload-level coverage feasibility and an exact
    missing-row policy before mechanism selection, preserve all contaminated windows
    and retired families, permit no P01/P02 rescue, and authorize at most one
    independently motivated development study.
49. [COMPLETE / FROZEN PRE-FEASIBILITY] Register exactly three independent,
    economically motivated proposals with primary research support and exact
    timestamp/schema/coverage, missing-row, execution-dependency, and pre-return
    falsification contracts. Select none and define no parameter or return.
50. [COMPLETE / V3 CLOSED ZERO-SELECTION] Execute and freeze proposal-specific
    feasibility without price-value or return inspection. V3P01 passed 4/11 and
    failed 7/11 execution/metadata requirements. V3P02 verified two samples but its
    third response truncated after the three-request budget was exhausted, so no
    authoritative pilot result exists. V3P03 stopped without qualified historical
    L2/queue evidence. The terminal screen selects zero primaries.
51. [COMPLETE / FROZEN PRE-V4-PROPOSAL] Freeze a V4 discovery charter before
    proposing or inspecting another mechanism. Treat V3 terminal artifacts as
    immutable input, prohibit direct V3 rescue, and predeclare incremental
    observation persistence, bounded transfer/recovery semantics, source feasibility,
    execution feasibility, contamination boundaries, proposal budget, and
    zero-or-one selection rules.
52. [COMPLETE / TWO THEORY PROPOSALS / NO OUTCOMES] Freeze only
    `V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE` and
    `V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM`. Leave the third proposal slot
    unused rather than pad the round with a related, inaccessible, or retired-family
    theory. Select neither and authorize no network, payload, parameter, return, or
    trading permission.
53. [COMPLETE / FROZEN PRE-NETWORK] Freeze the V4P01 ETH/BTC metadata-census,
    source-transport, execution, jurisdiction/account-access, point-in-time rule,
    resource-budget, persistence, and terminal-stop contract. It permits exactly two
    metadata and six free first-of-month one-minute schema requests to
    `api.tardis.dev`, with one attempt each and no value parsing.
54. [COMPLETE / REJECTED PRE-RETURN] Implement and verify the crash-safe V4P01
    runner; execute the two metadata requests; preserve the first interpretation
    reject; freeze a no-repeat continuation contract from official optional-field
    semantics; execute the six unconsumed payload requests; and freeze a terminal
    explanation addendum. V4P01 fails recovery-snapshot schema, source-revision,
    point-in-time fee, and point-in-time venue/filter-state gates. Select no primary,
    make no retry, and calculate no return.
55. [COMPLETE / TRANSPORT STOPPED NO RETRY] Freeze the V4P02 source and execution
    contract; implement and synthetically verify its crash-safe runner; then consume
    the exact first metadata attempt. Tardis declared `203,310,405` response bytes
    against the frozen `8,388,608` maximum. Aurex accepted zero body bytes, made no
    retry, consumed no dataset HEAD, and wrote an audited transport-stop terminal.
56. [COMPLETE / V4 CLOSED ZERO-SELECTION] Freeze the terminal V4 feasibility
    screen. V4P01 is rejected and V4P02 is transport-stopped; select zero primaries,
    calculate no return, and grant no candidate or downstream permission.
57. [PARALLEL / AUTHORITY-BOUND] Preserve the independent TradingView parity and
    authenticated webhook tracks. Mutate TradingView only with explicit authority;
    delivery proof must terminate at eligibility-safe rejection and create no paper
    order while no strategy is eligible.
58. [ACTIVE / CONTRACT READY / OPERATOR INPUT REQUIRED] Preserve the frozen post-V4
    capability-gap review. The credential-free operator-profile type and
    template/preflight/freeze/check CLI are implemented and tested. Next the operator
    must supply the intended venue, product scope, account/API and sandbox access,
    unborrowed non-emergency starting capital, protective loss limits, and
    data-acquisition budget. Do not create the real profile until preflight passes.
    In parallel, only rejected v1.3 parity and one genuine webhook delivery to
    paper-safe rejection may advance under their existing authority boundaries.
59. [COMPLETE PREPARATION / EXTERNAL EVENT PENDING] Harden the Stage 3 proof path
    before any real alert. Bind the exact canonical TradingView sender-host list and
    its hash into every receipt; block broad, IPv6, invalid, or undocumented network
    configurations from delivery proof; expose receipt timestamps/body fields and
    all paper/live/broker side effects; and implement a credential-free,
    database-backed template/preflight/freeze/check package. Do not create the real
    proof until one genuine TradingView alert is source-matched, safely risk-rejected,
    reconciled to a sanitized alert-log artifact, and passes all ten frozen gates.
60. [COMPLETE PREPARATION / EXPLICIT AUTHORITY AND EXPORTS PENDING] Replace report-only
    v1.3 parity with parity v1.1. Require one checksum-verified Binance Vision
    reference dataset, one separately imported TradingView chart OHLCV dataset from
    the same frozen chart state as the Strategy Tester report, exact venue-qualified
    source references, identical symbol/timeframe/coverage, and exact Decimal
    timestamp/OHLCV equality before trade comparison. Block missing, wrong, or
    tampered lineage without recording; freeze structurally valid candle disagreement
    as immutable `FAILED` evidence before trade matching. Keep all evidence selectors
    deliberately unselected until the operator chooses them. This calibrates the
    engine only and cannot alter v1.3's rejection or unlock paper/live progression.
61. [COMPLETE PREPARATION / REAL OPERATOR FACTS PENDING] Promote the post-V4
    operator-profile gate from CLI-only intake to one shared typed workflow. Add
    read-only status/template and no-write preflight endpoints, sanitize all
    validation errors, cap requests at 64 KiB, reject credential and account-number
    shapes, return no submitted identity/capital values, and prevent the web layer
    from freezing evidence. Add one dedicated Operator tab that defaults to
    unverified/unknown/blank facts, renders all nine gates and derived risk ratios,
    invalidates a prior pass on every edit, and permits input download/CLI handoff
    only after `9/9`. Keep independent CLI freeze/check mandatory. Synthetic UI
    passes are software tests only; no real profile, successor authority, paper,
    live, or capital permission exists.
62. [COMPLETE PREPARATION / EXPLICIT AUTHORITY AND REAL EXPORTS PENDING] Upgrade
    frozen-v1.3 parity to v1.2. Make the frozen manifest/package hashes stable across
    single-use protocol consumption; require the imported report to bind the exact
    intact protocol; build a no-write paired-export manifest over the frozen run,
    reference dataset, chart dataset, original report bytes, coverage, source
    references, and exact timestamped operator attestation; and require its reviewed
    hash in parity preflight and immutable evidence. Add dedicated lineage status,
    hash, attestation, invalidation, and comparison gating to the Backtests UI.
    Preserve the honest boundary that TradingView does not sign this attestation.
    This closes a provenance gap only; it does not create real parity, rehabilitate
    v1.3, or authorize paper/live/capital use.
63. [COMPLETE / RUNTIME-VERIFIED] Run the protocol-bound paired-lineage UI against a
    healthy local Aurex server at desktop and mobile widths. Preserve fail-closed
    evidence actions, automatically reveal the active tab inside the mobile
    navigation strip, render unavailable warm-up fields as `n/a`, and revise the
    versioned controller URL so existing browser caches receive the corrected code.
    Verify zero mobile horizontal overflow, JavaScript syntax, dashboard contracts,
    Ruff, and the complete `895`-test project boundary. This is operator-UX and
    control-plane evidence only; it creates no TradingView, parity, strategy, paper,
    live, or capital evidence.
64. [COMPLETE / FAIL-CLOSED RUNTIME-VERIFIED] Remove the shared async action
    wrapper's unconditional control re-enable. Track in-flight actions independently,
    suppress duplicate pointer and keyboard activation, and leave native `disabled`
    state exclusively under the latest renderer policy. Bump the controller asset
    revision and verify in Chromium that a newly disabled control stays disabled, an
    ordinary action does not stay locked, duplicate invocation runs once, and all
    unqualified parity actions remain disabled. This repairs control behavior only;
    external evidence and every strategy/trading permission remain unchanged.
65. [BLOCKED / THIRD CONSECUTIVE EXTERNAL-INPUT CHECKPOINT] Audit the canonical
    database and required artifact paths after all permitted parity, webhook,
    operator-intake, responsive, and fail-closed preparation is complete. Confirm
    zero v1.3 reports, zero fully protocol-bound reports, zero TradingView chart
    datasets, zero parity runs, zero signals/events, no real operator profile, and no
    external-delivery proof. Do not invent another synthetic task. Resume only when
    the operator supplies the frozen non-secret profile facts or explicitly
    authorizes one of the exact TradingView workflows already defined.
66. [COMPLETE / READ-ONLY EXTERNAL IDENTITY] After goal resume, call TradingView
    chart state exactly once without changing symbol, timeframe, studies, source, or
    workspace state. Preserve that the live chart is `BINANCE:BTCUSDT` at `30m`, its
    only study is `Aurex jam_reversal_v1`, and Strategy Tester returns zero metrics
    with `No strategy found on chart`. Capture one read-only chart image. This
    supersedes the current-state portion of the historical `2026-07-20` `15m`
    observation but does not alter its evidence, establish jam as a strategy, or
    satisfy frozen-v1.3 parity.
67. [COMPLETE / IDENTITY DISCREPANCY PRESERVED] Attempt current Pine source retrieval
    without opening a panel or changing workspace state. Preserve the fail-closed
    result `Could not open Pine Editor or Monaco not found in React fiber tree`.
    Independently verify that Aurex's local jam v1.14 file still has historical
    SHA-256 `f1c7231b...49a7c3` and declares `strategy()`. Because TradingView exposes
    no strategy metrics and current chart source is unavailable, classify the
    same-named chart study's source binding as unproven. Do not infer identity,
    evaluate jam, or open Pine Editor without explicit authority.
68. [BLOCKED AGAIN / THIRD RESUMED CHECKPOINT] Re-audit required files, the canonical
    SQLite database in read-only mode, settings, and the resumed identity boundary.
    Confirm zero v1.3 reports, zero fully protocol-bound reports, zero TradingView
    chart datasets, zero parity runs, zero signals/events, absent operator/external
    proof artifacts, and `live_trading_enabled=false`. The two resumed read-only
    identity steps created useful context but did not remove the need for operator
    facts or explicit TradingView UI/workflow authority. Do not continue with study
    values, speculative jam analysis, synthetic exports, or another internal proxy.
69. [REAL INPUT RECEIVED / PREFLIGHT 7 OF 9 / FREEZE BLOCKED] Map the operator's
    non-secret answers into a temporary typed draft: Zimbabwe; provisional
    `Binance.com`; alias `aurex_primary_spot`; spot-only `BTCUSDT`; `1x`; `$100`
    unborrowed non-emergency capital; `$0` one-time/monthly data budget; and maximum
    losses of `$0.50` per trade, `$1.00` daily, and `$10.00` total. Preserve
    `account_status=UNVERIFIED`, `api_access_status=UNKNOWN`, and
    `legal_and_tax_obligations_acknowledged=false`. Run the real no-write CLI
    preflight and preserve decision `BLOCK_SUCCESSOR_DISCOVERY`, profile hash
    `a2b95051...c540794`, and exactly two failed gates:
    `ACCOUNT_AND_API_ACCESS_PROVEN` and `VENUE_AND_JURISDICTION_BOUND`. Do not freeze
    until Binance identity/API access and the Zimbabwe venue/legal boundary are
    truthfully resolved.
70. [TESTNET PROFILE FROZEN / SIGNED VALIDATION VERIFIED] Preserve production
    profile gate truth, then create a separate Testnet-only capability contract from
    the operator's confirmed GitHub-authenticated Binance Spot Testnet access. Freeze
    and independently check all nine gates. Implement a fixed-origin BTCUSDT Spot
    client with local filter enforcement, hidden-prompt process-only credentials,
    signed account and order/test paths, a default-off virtual-order switch, and
    sanitized evidence. Preserve the real public-connectivity, authenticated-account,
    and signed `order/test` passes without upgrading virtual-order,
    sandbox-qualification, production, live, or capital status.
71. [VIRTUAL CANCEL PASSED / RECONCILIATION FAILED CLOSED / CONTRACT FIXED] Preserve
    the first real Testnet lifecycle: order `22276358`, `NEW` before cancellation,
    `CANCELED` after cancellation, zero executed quantity, matching quantity, and
    `virtual_cancel_lifecycle=PASS`. Preserve `order_reconciliation=FAIL` and do not
    qualify the sandbox. Correct the response model to retain both
    `origClientOrderId` and cancellation `clientOrderId`; assign the cancellation a
    deterministic Aurex ID; compare external order, placement, and cancellation
    lineage independently; then require one fresh real rerun.
72. [COMPLETE / FROZEN PRE-OUTCOME] Create `jam_reversal_spot_v1` from the Jam
    v1.14.0 lineage before opening earlier returns. Bind long-only BTCUSDT 15m,
    `$100`, `1x`, realistic costs, confirmed prior-hour EMA context, and the complete
    2023-2025 chronological protocol.
73. [COMPLETE / SUPERSEDED UNRUN CONTRACTS] Preserve v1.0.0 protocol
    `1aa77691-6b62-4738-b1b9-89c2f1f8cc06` and the first v1.0.1 protocol
    `920b1cbf-0990-4cd6-b835-445e1c7ab2d8` as unrun superseded records. The former
    had unstable higher-timeframe semantics; the latter bound warmup as tradable
    data. Neither opened a return.
74. [COMPLETE / REJECTED] Commit authoritative protocol
    `f788795a-ac75-4763-93c2-75a031ee2c70`, run the deterministic real-data replay
    once, record validation, and audit both. Reject v1.0.1 for 14 trades,
    `-$0.5371`, PF `0.8301`, negative OOS, and 0/6 passing folds.
75. [COMPLETE / CONTAMINATION RECORDED] Add the opened BTCUSDT 15m
    2023-02-01/2026-01-01 decision period to the hash-audited contamination ledger.
    Do not tune, rerun, relabel, parity-test, or paper-trade v1.0.1.
76. [COMPLETE / STORED EVIDENCE ONLY] Perform bounded mechanism-level failure
    attribution. Preserve the classification
    `INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE`.
77. [COMPLETE / DESIGN ONLY] Freeze the Jam successor charter and select only
    aggressive sell-flow exhaustion and reclaim for capability review.
78. [COMPLETE / METADATA ONLY] Verify all 96 official 2019-2022 aggregate-trade and
    one-minute-kline archive checksum targets.
79. [COMPLETE / ONE-MONTH PAYLOAD] Prove January 2019 schema, continuity, and exact
    cross-family reconciliation.
80. [COMPLETE / FULL ACQUISITION FAILED STRICT PAIRED GATE] Acquire all 96 archives,
    preserve all defects, and stop after only 23/48 months pass the original exact
    paired-source gate.
81. [COMPLETE / NO RETURNS] Reconstruct every source defect, prove the 2021-12
    duplicate is byte-identical, freeze the 4,161-minute quarantine, adopt aggregate
    trades as primary, and freeze 2019-2020/2021/2022 evidence roles.
82. [COMPLETE / CAUSAL SPECIFICATION ONLY] Freeze the 17-feature, 133-minute Jam
    successor measurement system and pass nine synthetic conformance cases without
    reading a real market row, defining a threshold, or calculating a return.
83. [COMPLETE / DEVELOPMENT FEATURES ONLY] Run the frozen feature engine on
    2019-2020 development data, preserve all 1,052,640 calendar rows, pass all seven
    structural gates, and independently reconstruct the Parquet and result exactly.
    No future return or 2021/2022 value was opened.
84. [COMPLETE / PRE-EVENT PRE-OUTCOME] Freeze one five-condition long event, one
    selectable 30-minute horizon, 15/60-minute non-selectable diagnostics,
    60-minute suppression, realistic cost cases, deterministic matched controls,
    seven prevalence gates, and fixed development/validation/holdout outcome gates.
    Calculate zero events, labels, or returns.
85. [COMPLETE / DEVELOPMENT PREVALENCE ONLY] Freeze the bounded prevalence protocol,
    evaluate the unchanged five-condition event on 2019-2020 causal features,
    preserve all 1,430 raw events, accept 991 under the 60-minute suppression rule,
    pass all 7/7 prevalence gates, and independently reconstruct the ledger and
    result byte-for-byte. No future price, label, return, or 2021/2022 value was
    opened.
86. [COMPLETE / TERMINAL REJECTION] Freeze the development execution protocol
    before post-event price access, calculate only the 2019-2020 outcomes, costs,
    controls, inference, and eleven gates, then independently reconstruct every
    artifact. Preserve 991 event outcomes, 456 matched pairs, and the 3/11 gate
    result under decision `STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.
87. [NEXT / NEW RESEARCH DECISION REQUIRED] Do not tune, relabel, parity-test,
    paper-trade, or open validation/holdout for the failed Jam successor. Any next
    alpha track must begin with a genuinely unrelated mechanism charter, separate
    version, contamination review, and fresh preregistration before development
    outcomes. This is not authorized by the failed lineage; its artifact state is
    `NONE_DEVELOPMENT_OUTCOME_FAILED`.
88. [COMPLETE / TERMINAL SOURCE FAILURE] Preserve the Q1 periodic-flow successor
    v1-v7 lineage, classify all 37 months, independently rehash all 73 inspected
    archives, and accept only 19 paired months. Preserve decision
    `STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED`, terminal audit hash
    `d95aa05f8236d6c1ba51f8a39e1e94376578ce2bc3b446369e9da129b7725760`,
    and next authorization `NONE_SOURCE_SUFFICIENCY_FAILED`.
89. [NEXT / INDEPENDENT CHARTER REQUIRED] Do not rerun Q1, lower its pair/year/
    quarter gates, or freeze its measurement protocol. A future alpha track must
    begin with a separately versioned and genuinely independent mechanism/source
    charter frozen before outcomes. No such charter is currently selected or
    authorized.
90. [COMPLETE / NO OUTCOMES] Freeze and independently audit the S1 predecessor
    lineage ledger. Reject reuse of every prior strategy outcome for S1 selection.
91. [COMPLETE / CHARTER ONLY] Freeze S1 as the independent NFCI easing/risk-appetite
    mechanism with five contiguous evidence partitions and no parameters, BTC
    values, returns, candidates, or orders.
92. [COMPLETE / METADATA ONLY] Preserve the failed `HEAD` census and the narrow v2
    zero-read transport correction. Do not reinterpret transport success as data
    quality or edge.
93. [COMPLETE / SOURCE ADJUDICATION] Preserve the failed FRED raw pilot, then bind
    it into the ALFRED recovery. Accept only the two distinct, truncated,
    revision-bearing ALFRED vintages under result hash
    `274e9981103b3e31aea001e543f62d29d0d6941a1529b00cb5b037a854c75472`.
94. [COMPLETE / PROTOCOL ONLY] Freeze and independently audit the 281-target,
    byte-bounded, resumable development-period ALFRED NFCI acquisition protocol.
95. [COMPLETE / SUPERSEDED PRE-NETWORK] Preserve the v1 execution addendum and its
    synthetic atomic-rename restart defect. It made zero network requests and is
    not the runner authority for the completed acquisition.
96. [COMPLETE / EXECUTION V2] Freeze and independently audit the narrow v2 restart
    correction under runner contract hash
    `951318f4e7d27efa73420e69bff31fef219e647c36ed63ad12924ab94b2f9b8d`.
97. [COMPLETE / SOURCE VALUES ONLY] Acquire and independently reconstruct all 281
    development vintages. Preserve decision
    `PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION`; do not reinterpret it as edge.
98. [COMPLETE / PROTOCOL ONLY] Freeze and independently audit the causal
    normalization schema, row-selection rule, output format, structural gates, and
    zero-derived-feature boundary before transforming any NFCI value.
99. [COMPLETE / EXECUTION] Pass the synthetic parser and anti-leakage suite, then
    freeze and audit one-run authority under runner contract hash
    `a9cff8a1a1ed6f08ea1b55cde5dcf6f8949cab5044bc7b82fb03655cb8045908`.
100. [COMPLETE / MACRO VALUES ONLY] Rehash all 281 inputs and create one exact
    latest-available NFCI row per vintage. Independently reproduce the dataset and
    preserve decision `PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION`.
101. [COMPLETE / PROTOCOL ONLY] Freeze and independently audit the three-feature
    macro family, exact-decimal policy, four-row warm-up, and four-candidate ceiling
    before parsing normalized values.
102. [COMPLETE / MACRO FEATURES ONLY] Freeze the source-bound runner, calculate 277
    feature rows, and independently reproduce every input hash and output byte.
    Preserve decision `PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION`.
103. [COMPLETE / PREREGISTRATION ONLY] Freeze one promotable consistent-easing
    primary and three non-rescuing diagnostics, Friday 00:00 UTC execution, base and
    stress costs, 12 primary gates, and sealed validation before opening BTC values.
104. [COMPLETE / SOURCE PROTOCOL ONLY] Freeze and audit 277 checksum-bound official
    daily BTCUSDT Spot 1h Friday targets with zero requests, bytes, values, or returns.
105. [NEXT / RUNNER ONLY] Implement and synthetically test crash-safe paired checksum/
    ZIP acquisition, exact target-open extraction, immutable markers, and restart
    recovery. Freeze and audit the runner before any network request.

## Decision Log

### D-001 Preserve The Existing Goal

The original Stage 1-10 goal remains the program roadmap. The current master directive
is its operating doctrine, not a replacement or parallel goal.

### D-002 Preserve Real Missing-Market Intervals

Do not synthesize candles for exchange outages. A continuous 24/7 dataset may pass
only when every observed gap exactly matches attributable outage evidence and no
declaration is partial, overlapping, contradictory, or extraneous.

### D-003 Keep TradingView Trust Boundaries Separate

TradingView MCP supports research, observability, and parity. It does not replace the
Binance dataset, authenticated webhook, Aurex evidence/risk systems, or a future
exchange adapter, and it cannot become a production execution dependency.

### D-004 Preserve Negative Strategy Evidence

The current local replay is negative evidence, not a parameter-optimization prompt.
Failed candidates retain immutable lineage and receive an evidence-based verdict.

### D-005 Version Statistical Semantics Without Rewriting History

Reference validation evaluator v1.1 calculates drawdown from cumulative realized P/L
inside each evaluation segment, so the first trade cannot become an undeclared equity
baseline. It binds the result to replay drawdown and records fixed-path fee/slippage
sensitivity. Existing v1.0 records remain immutable and audit under their original
evaluator and schema. Evaluator v1.2 adds a non-negotiable temporal binding: the
durable protocol timestamp must be no later than the replay timestamp. Existing v1.0
and v1.1 records remain immutable and audit under their original semantics rather than
being silently rewritten.

### D-006 Reject trend_pullback_v1 v1.3

Verdict: `REJECT` this frozen version for eligibility and paper progression. The
candidate loses after realistic costs, fails overall and OOS edge gates, exceeds the
drawdown cap, and passes zero walk-forward folds. Preserve it as negative evidence.
Do not tune v1.3 to rescue the result. Any later redesign must be a separately versioned,
predeclared research candidate.

### D-007 Preserve Unrelated Pine Work

`pine/strategies/jam_reversal_v1.pine` and `docs/pine/jam_reversal_v1.md` are modified
in the working tree outside this checkpoint's implementation. Treat them as user-owned
and do not overwrite, revert, or use them as `trend_pullback_v1` evidence without first
establishing identity and lineage.

### D-008 Quarantine jam_reversal_v1 v1.14 Results

The active TradingView source exactly matches the current local v1.14 file, but the
documented result history repeatedly tuned versions 1.0.1 through 1.14.0 on the same
small May-July window and neighboring timeframe/symbol probes. The visible `+$24.87`
from five trades is exploratory in-sample output, not eligibility evidence. Any future
Jam candidate requires a new version, contamination map, untouched decision set, and
pre-registered protocol.

### D-009 Bound Parity Work To Engine Calibration

Run one exact Jan-March 2026 v1.3 TradingView comparison to validate local replay
semantics. Preserve all mismatches and stop treating parity as a route to rescue the
rejected candidate. After parity, retire v1.3 from active research and move to a newly
predeclared economic hypothesis.

### D-010 Do Not Trust MCP Strategy Metrics Alone

TradingView MCP correctly reads chart state, Pine source, values, screenshots, and
compile errors, but its internal strategy-results endpoint reported no strategy while
the visible Strategy Tester displayed an active strategy. MCP metrics are therefore
observability hints only; authentic exported completed trades remain required.

### D-011 Separate Webhook Delivery Proof From Trading Permission

An internally posted payload cannot prove TradingView origin. Aurex now preserves a
hashed transport receipt and distinguishes `delivery_verified`, `pipeline_verified`,
and full end-to-end `verified`. A genuine alert for a rejected strategy is expected to
prove delivery and then stop at risk rejection. External proof must never become a
backdoor around strategy eligibility.

### D-012 Seed Quarantined Jam Disabled

`jam_reversal_v1` remains registered so its source, controls, and research state are
visible, but fresh databases now seed it with `is_enabled=false`. This does not erase
or overwrite an existing operator configuration. Registration is not eligibility, and
the repeatedly tuned v1.14 result cannot justify automatic enablement.

### D-013 Select And Freeze An Expansion Candidate

`volatility_breakout_v1` v1.1 was selected because its compression-expansion mechanism
was distinct from the failed pullback mechanism. Source and parameters were frozen
before its outcome was inspected, but the attempted protocol registration was never
committed. Its later durable protocol therefore cannot be represented as
preregistration.

### D-014 Retire volatility_breakout_v1 v1.1

The audited replay is decisive diagnostic negative evidence: it loses `-$533.87`, has
PF `0.6734`, negative IS and OOS expectancy, loses all six walk-forward folds, and
still loses `-$37.10` with modeled costs removed. Retire this version. Do not tune or
rerun it against the same observed window.

### D-015 Make Temporal Preregistration Mechanical

Documentation and a source hash do not prove durable preregistration. Evaluator v1.2
blocks any protocol registered after its replay. The candidate registration workflow
now owns the transaction, commits, reloads the record in a fresh session, verifies its
hash, and refuses to register once a same-version replay exists.

### D-016 Move To A Slower Spot-Compatible Hypothesis

Failure attribution showed trend v1.3 has only a thin pre-cost edge overwhelmed by
turnover, while volatility v1.1 loses before costs. The next candidate is therefore a
distinct 4-hour, long-only, asymmetric channel mechanism with lower risk and notional
caps. This is an economic hypothesis, not an optimization of either rejected version.

### D-017 Require Two Independent Holdout Verdicts

BTCUSDT remains development-contaminated. ETHUSDT and SOLUSDT are the untouched
decision set. Each symbol must pass the complete individual protocol, then the frozen
cross-market rule must pass. Pooling cannot hide a losing symbol or allow one market to
supply more than 70% of gross profits.

### D-018 Bind Replay Monetary And Quantity Semantics

The first committed slow-spot protocol pair omitted tick size, point value, and minimum
contract. No outcome existed. Preserve those records as incomplete and superseded.
The authoritative pair binds official Binance spot increments in the risk snapshot,
and validation now blocks any declared execution-spec mismatch.

### D-019 Keep Targetless Research Honest

The slow candidate exits by channel and has no take-profit. Reference replay trades may
therefore record a null target. Current Aurex paper risk rules still reject missing
take-profit values. Do not fabricate a target; design channel-exit order management only
after held-out acceptance and Pine parity.

### D-020 Scope My-Krypt-Trader Runtime Discovery

An arbitrary donor checkout must not silently inherit machine-wide Krypt Trader
settings. Runtime discovery now prioritizes explicit paths, environment override, and
the checkout's Aurex demo userData. Global desktop profiles can auto-select only for
the actual workspace donor root. Live execution remains false.

### D-021 Reject slow_breakout_spot_v1 v1.0.0

The atomic, preregistered ETH/SOL campaign returned `REJECT`. ETH made `+$44.69`
overall and `+$7.25` OOS but passed only one of five walk-forward folds. SOL made
`+$59.74` overall but lost `-$18.39` OOS, recorded OOS PF `0.5185`, and passed zero
folds. Both individual validations were required to pass. The pooled `+$104.43`, PF
`1.6968`, and positive 150% cost stress cannot override that rule. Retire v1.0.0 and
do not tune it against the opened holdouts.

### D-022 Repair Low-Frequency Study Design Prospectively

The candidate produced roughly 16 trades per market-year, while its quarterly folds
required five trades each. Most folds could not reach that sample. This is a protocol
design lesson, not permission to recalculate the result: SOL independently failed OOS
and every gate remains frozen. Future low-frequency studies must align expected trade
rate, fold duration, minimum sample, simultaneous portfolio exposure, and untouched
data boundaries before outcomes exist.

### D-023 Seed Every Unqualified Strategy Disabled

No registered Aurex strategy is currently eligible. Fresh databases must therefore
seed every strategy with `is_enabled=false`, including the retired trend candidate and
the unvalidated range candidate. Existing operator settings remain untouched, and the
accepted-backtest risk gate remains mandatory even when an operator later enables a
configuration explicitly.

### D-024 Require Shared Capital And Mechanical Contamination Control

Independent per-symbol accounts overstate portfolio deployability when positions
overlap. The new pure portfolio engine allocates simultaneous long-spot opportunities
against one cash/equity ledger, marks open risk to market, applies costs and rounding,
records capacity rejections, and produces replayable input/result hashes. The
contamination ledger makes six known opened/development scopes machine-readable and
hash-auditable. Neither control selects a strategy or claims edge.

### D-025 Freeze The Market Universe Before Another Strategy Outcome

Current exchange metadata would erase delisted markets and create survivorship bias.
Aurex therefore enumerates Binance Vision's historical spot archive directories,
retains every historical USDT symbol and every exclusion, and uses only 2023-2024
archive availability plus daily USDT quote volume for selection. The rule requires all
24 monthly 4h archives and checksum sidecars, 731 daily rows, at least 700 active days,
median daily quote volume of at least `$10,000,000`, and nearest-rank tenth-percentile
daily quote volume of at least `$1,000,000`. Cash-like bases and leveraged-token
suffixes are excluded mechanically. BTC, ETH, and SOL are development-only because the
contamination ledger is cryptographically bound into the rule. Passing this rule means
only that a market is admissible for later evidence; it is not evidence of edge.

### D-026 Separate Development Data From Strategy Outcomes

R3 imports only the declared `2023-01-01` through `2024-12-31` development partition.
All 38 datasets must have exactly 4,386 aligned 4h candles and pass source, checksum,
continuity, role, and offline-rebuild audits before any strategy calculation. BTC, ETH,
and SOL remain diagnostic-only. Validation, holdout, and forward data stay unopened.

### D-027 Fix The Primary Before Comparing Mechanism Horizons

R3 tests cross-sectional momentum as a bounded mechanism, not a parameter search. The
84-day lookback and 14-day rebalance variant is the sole primary. The 28-day/7-day and
168-day/28-day variants can only falsify or support the mechanism; neither may replace
the primary because it looks better. Advancement requires every predeclared gate and
does not select the best result from the three variants.

### D-028 Freeze Execution Semantics Before Engine Outcomes

The study protocol alone did not fully determine tie-breaking, ATR seeding, event
ordering, gap stops, allocation scaling, final liquidation, fold resets, undefined
metrics, or leave-one-market-out selection counts. Aurex therefore froze a separate
execution contract before implementing the outcome engine. Any later semantic change
requires a new version and cannot rewrite R3 v1 evidence.

### D-029 Enforce The R3 All-Gates Verdict

The primary cross-sectional-momentum replay was profitable in aggregate and passed
cost, drawdown, sample, concentration, leave-one-market-out, and falsification-support
controls. It failed the predeclared temporal gate: only Q4 2023, Q1 2024, and Q3 2024
were positive, while Q3 2023, Q2 2024, and Q4 2024 lost money. The observed count was
3/6 against a required 4/6. R3 v1 is therefore `NO_CANDIDATE`; its positive `$330.23`
development P/L is research evidence, not eligibility.

### D-030 Do Not Promote The Better-Looking Falsification Variant

The slower 168-day/28-day falsification horizon earned `+$707.07`, PF `2.0653`, and
4/6 positive folds at base costs, but it was predeclared as a non-selectable mechanism
check and its aggregate max drawdown was 22.71%. Selecting it after seeing all three
variants would violate the frozen rule that the primary cannot be replaced by the best
result. It may inform a new bounded hypothesis only after explicit post-outcome failure
analysis and a fresh registration; it is not an R4 candidate.

### D-031 Correct Diagnostics Without Rewriting Evidence

The v1 monthly-return diagnostic assigned snapshots closing exactly at midnight to the
new calendar month, creating an extraneous `2025-01` key and shifting month-boundary
bars. No trade, equity calculation, fold, concentration measure, advancement gate, or
verdict uses that grouping. Aurex preserves the immutable v1 ledger and publishes a
hash-bound 18-month correction addendum. The defect is not used to reopen the decision.

### D-032 Continue Only Under The Frozen Failure Rule

The post-outcome analysis found all three tested horizons positive at base and double
cost, positive-fold counts strictly increasing from fast to primary to slow, passed
concentration controls, and 35/35 positive leave-one-market-out runs while the primary
temporal gate remained failed at 3/6. Its fixed decision is therefore
`PROPOSE_BOUNDED_R3_1`, not candidate promotion. R3 v1 remains `NO_CANDIDATE`, the slow
falsification variant remains non-selectable, and every discovered quarter or regime
bucket remains descriptive.

### D-033 Test Path Quality Once Or Stop The Family

R3.1 changes one mechanism component only: it ranks a positive 84-day log-price OLS
slope multiplied by regression R-squared, calculated from 505 closes spanning exactly
504 four-hour intervals. The 14-day rebalance, shared capital, ATR risk sizing, stops,
costs, folds, and all absolute gates remain fixed. There is one selectable hypothesis
and one parameter set. Any failed gate stops the cross-sectional momentum family; a
pass permits only a separately frozen R4 candidate and one later 2025 validation.

### D-034 Accept R3.1 As Development Evidence, Not Eligibility

The one-shot R3.1 path-quality study passed all 9/9 frozen development gates and
reproduced under a full second 44-replay audit. The primary earned `+$488.79`, PF
`1.5936`, 10.82% maximum drawdown, and 230 completed trades. It remained positive at
double costs with `+$423.78`; 35/35 leave-one-market-out runs were positive; single-
symbol and top-five gross-profit fractions were 13.00% and 44.92%. The result was
positive in exactly 4/6 quarters. Q2 and Q4 2024 still lost `-$39.48` and `-$129.43`.
The mechanical verdict is `PERMIT_R4_PREREGISTRATION`, not strategy eligibility.

### D-035 Freeze R4 Before Opening Validation

R3.1 used the complete 2023-2024 development partition and may not be tuned further.
The next valid action is to preserve its accepted mechanism unchanged in one separately
versioned R4 candidate, freeze the 2025 validation data and decision contract without
inspecting outcomes, and then execute exactly once. Any signal, horizon, ranking,
portfolio, cost, gate, or execution-semantic change requires a different research
lineage and cannot use R3.1's pass as authorization.

### D-036 Accept The One-Shot R4 Result Without Rescue

The candidate, 2025 data, terminal-market semantics, engine, runtime, source files,
transformed market data, and 42-run matrix were frozen and independently rebuilt
before any validation signal was calculated. The one-shot campaign committed all 42
artifacts atomically, and both the stored-artifact audit and a full independent
42-replay audit passed. The result is authoritative negative evidence. No parameter,
gate, cost, symbol, fold, or execution rule may be changed to reinterpret R4 v1.0.0.

### D-037 Retire R4 And Stop The Path-Quality Family

R4 failed base profitability, profit factor, double-cost profitability, quarterly
robustness, and leave-one-market-out robustness. Its raw-price PF was also below one,
so costs worsened rather than created the failure. Under D-033 and the frozen R4 rule,
the candidate is retired and the cross-sectional path-quality continuation is stopped.
2025 is now outcome-contaminated for this lineage. A future candidate must express a
separate economic mechanism, be preregistered before outcome access, and use evidence
that remains sealed; R4 does not authorize Pine parity, paper, sandbox, or live use.

### D-038 Return Only To Unrelated Mechanism Discovery

The frozen post-R4 analysis classified the failure as
`SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS`. Raw price P/L was already `-$52.02`; costs
increased the loss to `-$73.83`. Availability, concentration, and drawdown controls
all behaved within their frozen limits, while temporal and leave-one-market-out
robustness failed broadly. The deterministic decision is
`STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY`.

No exit-reason, holding-duration, month, symbol, omission, or rebalance-cohort result
from this outcome may become a new trading rule. The next research step must first
freeze a discovery charter for an economically unrelated mechanism. It must preserve
2026 and forward evidence, cap the number of hypotheses, separate exploratory from
confirmatory evidence, and define an automatic stop before calculating returns.

### D-039 Select Broad Spot Volatility Management Without Return Screening

The U1 charter permits three theory/data-feasibility proposals but only one
return-tested mechanism and one selectable parameter set. The theory screen inspected
no Aurex strategy return. Volatility-managed broad spot beta is the only proposal
that currently has two primary research foundations, reproducible point-in-time data,
long-only spot expressibility, no leverage requirement, low expected turnover, and no
dependency on a retired signal or R4 outcome bucket.

Signed-jump risk remains distinct but cannot be approximated honestly from four-hour
candles; it is deferred until a separately frozen high-frequency data foundation
exists. Delta-neutral funding carry remains distinct but is deferred until Aurex has
point-in-time funding/basis/collateral data and qualified derivatives execution,
reconciliation, and liquidation controls. The screen selects protocol design only.
It does not create a candidate, report a return, or authorize validation, holdout,
Pine, paper, sandbox, live trading, or capital.

### D-040 Retire U1 Despite Strong Aggregate Development Profit

U1 was frozen before outcomes and executed once across 47 planned replays. The
primary earned `+$2,168.47` from `$1,000`, PF `1.9311`, remained positive at double
costs, reduced volatility and drawdown relative to its static benchmark, passed every
leave-one-market-out run, and passed concentration controls. Those facts do not
override the two failed gates: maximum drawdown was 44.58% against a 20% ceiling, and
only 4/8 independent temporal folds were profitable against the required 6/8.

The deterministic verdict is `STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA`. Do not tune
the volatility target, estimator, lookback, rebalance schedule, basket, exposure
transform, or gate after observing this result. Do not open 2025 for U1. A new
research attempt requires a separate charter and an economically independent
mechanism. The practical priority is to build the point-in-time data and synthetic
execution controls needed to test lower-directional-risk premises without borrowing
U1's favorable quarters.

### D-041 Build The Foundation Before Selecting V2

The frozen V2 capability audit found only audited spot OHLCV ready. Historical
perpetual funding, mark/index and basis evidence, dated contract and fee metadata,
paired-leg execution, funding settlement, collateral/margin, liquidation/ADL,
spot-perpetual reconciliation, and a production derivatives adapter are absent or
intentionally disabled. My-Krypt-Trader contributes no derivatives foundation.

Official Binance documentation and archive indexes show that public funding,
futures-kline, mark-price, index-price, premium-index, basis, and contract surfaces
exist. That proves acquisition feasibility only; it does not prove completeness,
point-in-time validity, executable carry, or profitability. V2 therefore authorizes
data-contract design only. No mechanism is selected, no market data is imported under
V2, and no return is calculated until a separately frozen source/acquisition contract
and synthetic execution foundation pass.

### D-042 Census Metadata Before Downloading Derivatives Payloads

The V2 source census is fixed across the existing 35-symbol universe, January 2023
through December 2024, and six official archive families: one-minute spot klines,
one-minute USD-M contract klines, funding events, and one-minute mark, index, and
premium-index klines. It requires 5,040 checksum checks and preserves every missing
file without symbol substitution or window shrinkage.

The census may collect URL, HTTP, checksum, content-length, last-modified, and
timestamp metadata only. It cannot download archive payloads or inspect numeric
prices, funding rates, or returns. At least 20 symbols must have all six families for
all 24 months before a separate data-acquisition protocol may be designed. This
threshold is a data-feasibility gate, not a strategy-selection or profitability gate.

### D-043 Preserve The Census Result Without Filling Missing History

All 5,040 checksum requests completed. Exactly 4,790 official checksum files were
present and 250 returned `404`. Thirty-one symbols have all six families for all 24
months. CFXUSDT, LUNCUSDT, SHIBUSDT, and STXUSDT are incomplete; every derivatives
family is missing 50 observations across those symbols, while spot coverage is
complete for all 35.

The decision is `PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL`. This proves only that
the fixed public-archive source is sufficiently complete for bounded acquisition
design. Do not backfill the four incomplete symbols, shorten their windows, replace
them, or reinterpret the 31-symbol set as a profitable universe.

### D-044 Pilot Payloads Before Full Acquisition

The first payload-bearing action is limited to 54 exact archives: AAVEUSDT, FTMUSDT,
and XRPUSDT; January 2023, January 2024, and December 2024; and all six families.
Those symbols and months are selected mechanically as first/median/last, not by
returns. Every target is pinned to its census checksum.

Before any archive GET, all content lengths and free-disk/resource gates must pass.
Downloads use `.part` files, checksum-before-rename, ZIP safety checks, and frozen
schema/timestamp inspection fields. An upstream checksum revision, unknown schema,
resource breach, or integrity failure stops without a partial authoritative result.
Even a passing pilot authorizes only a separate full-acquisition protocol; it does
not authorize the remaining archives, data import, a mechanism, or a backtest.

### D-045 Accept The Pilot Without Treating It As A Dataset

All 54 checksum-pinned archives passed. The pilot contains 53,398,035 compressed
bytes, 198,582,854 uncompressed CSV bytes, and 2,009,637 structurally inspected rows.
Each of the five kline families contributed 401,760 rows; funding contributed 837
events. All timestamps are milliseconds and all rows are in their target month.
Spot archives were headerless; the 36 futures-kline archives used the observed
12-column header; all nine funding archives used
`calc_time,funding_interval_hours,last_funding_rate`.

The decision is
`PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL`. This means Aurex has evidence
that the archive sizes, ZIP structure, schemas, and timestamps are tractable. The
pilot is not a normalized dataset, did not calculate returns, and did not validate
paired execution, historical fees, collateral, liquidation, reconciliation, or an
economic mechanism. Do not begin the remaining 4,410 complete-universe archives
without a separate frozen full-acquisition protocol and explicit resource plan.

### D-046 Prove Derivatives Arithmetic Before Reading Returns

The synthetic foundation freezes decimal arithmetic and the long-spot/short-USD-M
perpetual lifecycle before any V2 mechanism is selected. It covers signed funding,
fees, spot and perpetual cash/P&L, equity, collateral, initial and maintenance margin,
liquidation fees, ADL, partial fills, rollback, duplicate-event idempotency, kill
switches, and reconciliation.

All 14 predeclared scenarios passed, including positive and negative funding, partial
open and close paths, reject/timeout rollback, margin rejection, liquidation, ADL,
duplicate fills and funding, drift detection, and reduce-only flattening. This proves
only Aurex's internal synthetic invariants. It does not prove Binance execution,
historical margin behavior, data quality, or profitability.

### D-047 Freeze Discovery After The Foundation, Not Before

The V2 discovery charter permits exactly three theory proposals, at most one selected
primary, zero return-tested mechanisms, and zero parameter sets. It keeps 2023-2024
development closed pending a full-acquisition protocol, 2025 sealed for internal
validation, 2026 H1 sealed for final eligibility, and forward evidence locked.

The charter can only select protocol design or stop research. Selection cannot create
a candidate or authorize full download, market-data import, return calculation, Pine,
paper, sandbox, live trading, or capital.

### D-048 Select Positive-Funding Carry Without Claiming Edge

The theory screen used official exchange documentation, peer-reviewed research, and
institutional working papers without reading an Aurex market value, defining a
parameter, or calculating a return. It selected
`P01_POSITIVE_FUNDING_SPOT_PERP_CARRY` because long cash-funded spot paired with a
same-quantity short USD-M perpetual fits the audited synthetic direction without
requiring spot borrowing.

`P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS` remains a nonselectable related diagnostic:
funding can anchor prices, but a perpetual has no expiry that forces convergence.
`P03_NEGATIVE_FUNDING_REVERSE_CARRY` is rejected under this charter because it
requires point-in-time spot-borrow availability, rates, limits, recall, repayment,
and reverse-pair execution mechanics that Aurex has not qualified. The decision is
`FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN`, not candidate acceptance.

### D-049 Freeze Metadata Requirements Before The P01 Design

P01 requires historical funding and intervals, synchronized spot/perpetual/mark/index/
premium prices, contract lifecycle, spot and futures filters, account fees, leverage
and maintenance brackets, and collateral/liquidation/ADL rules. The v1 source contract
froze those eight requirements and four official sources before making a source
observation. It authorizes only bounded public-document inspection and no credential,
private endpoint, market value, archive expansion, return, candidate, or eligibility.

### D-050 Version The Source Failure Instead Of Weakening It

The v1 runner correctly stopped when the Binance USD-M documentation catalog returned
HTTP 202 with an empty body and none of the required markers. It wrote no audit result.
The v1.1 contract preserves v1 and replaces only the two Binance catalog URLs with
official Binance GitHub connector sources that contain the same frozen endpoint and
temporal markers. Tests reject marker drift, permission expansion, semantic source
changes, or undeclared substitutions.

### D-051 Permit P01 Design Only With Explicit Metadata Limitations

The v1.1 audit found direct historical archive support for only settled funding/
intervals and synchronized price families. Contract lifecycle remains partial and must
fail closed on ambiguity. Historical filters, account fees, leverage brackets, margin,
liquidation, and ADL rules are unavailable; five of those gaps may use separately
frozen conservative research overrides but can never become historical execution
proof. The decision permits protocol design only.

### D-052 Freeze One P01 Study And Its Automatic Stop

P01 uses one fixed signal: three strictly positive settled funding events, mean
event-normalized annualized funding of at least 30%, nonnegative prior closed-minute
mark/spot premium, and a 10% exit hurdle. It permits no parameter search or rotation
before exit. The development protocol fixes 10,000 USDT capital, five 1,000 USDT
delta-matched pairs, current filters as proxies, adverse fees/execution, 2x isolated
margin with a 5% maintenance override, eight quarterly folds, four cost runs, and 31
leave-one-symbol-out runs. Any failed gate retires P01; a complete pass permits only
a separately frozen 2025 validation protocol and creates no eligibility.

### D-053 Retire P01 At The Pre-Return Data Gate

The full P01 runner reverified all 4,464 census checksums, acquired exactly 4,410 new
archives, reused all 54 pilot archives only after byte and hash verification, and
inspected 163,010,201 rows. All archives passed identity, ZIP safety, schema, finite
numeric, ordering, and month-bound checks. Of 3,720 kline archives, 255 failed the
frozen exact-minute continuity rule. Every symbol had at least one failed archive;
FTMUSDT and MKRUSDT also failed both current filter proxies.

The gaps are real source evidence and concentrated in six months, including common
venue-wide holes. The frozen protocol nevertheless requires strict continuity and
excludes a symbol on any lifecycle gap. Changing that interpretation after observing
the result would be a rescue. Preserve decision
`STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA`, calculate no P01 return, and do not
promote related P02 premium convergence or rejected P03 reverse carry under the
consumed V2 charter.

### D-054 Make Payload Feasibility Precede V3 Mechanism Selection

Archive existence alone is insufficient source feasibility. Before V3 selects a
primary, its charter must require a mechanism-specific payload feasibility contract:
exact synchronized fields, timestamp coverage, missing-row classification, permitted
skip behavior, prohibited filling, minimum decision-event coverage, and a
point-in-time execution path. These rules must be frozen before proposal
parameterization or return inspection. V3 remains an edge-search program, not a
promise that an edge exists.

### D-055 Freeze V3 Before Proposing Another Mechanism

The V3 charter binds the V2 charter/screen, frozen P01 protocol, immutable P01
acquisition stop, and contamination ledger. It permits at most three independent
theory proposals, one selected primary, zero parameter sets, and zero return-tested
mechanisms. Development payload access is limited to archive identity, schema,
timestamps, row counts, gap classification, and synchronized coverage. Price values,
signals, trades, P/L, and returns remain prohibited.

V3 explicitly blocks P01 continuity rescue, P02 promotion, P03 without historical
borrow/execution state, and re-expression of retired trend, breakout, path-quality,
beta, or carry families. A selected primary would permit only a separately frozen
source and one-shot development protocol; it would not create a candidate.

### D-056 Freeze Three V3 Proposals Before Their Feasibility Outcomes

V3 registers exactly three theory-supported but unselected proposals:

- cross-asset cointegration relative value expressed as long cash spot and short a
  different asset's USD-M perpetual;
- fixed UTC clock-phase predictability requiring aggregate trade evidence; and
- passive limit-order liquidity provision requiring L2, queue, fill, latency, and
  dated maker-fee evidence.

Each proposal now has an exact pre-return coverage contract. Cointegration requires
at least 99.5% total synchronized coverage, at least 95% in every included calendar
month, no gap over 1,440 minutes, and at least 20 qualified symbols. Clock-phase
requires aggregate trades, at least 99.9% total and 99% monthly coverage, no gap over
15 minutes, and at least 10 symbols. Passive liquidity requires sequence-complete
subsecond event evidence and permits no inferred queue or candle-touch fill.

These thresholds predate the proposal-specific feasibility results. No proposal is
selected, no price value or strategy outcome was inspected, and no parameter exists.

### D-057 Classify Every V3 Path By Its Actual Evidence

V3P01 is a formal feasibility rejection, not a return rejection: 4/11 requirements
passed and 7/11 failed because historical execution metadata and a cross-asset
identity/hedge/residual-risk foundation are incomplete. V3P03 is rejected under this
charter because the formal source audit could not qualify required historical L2,
sequence, queue, latency, and maker-fee evidence. Neither result proves the economic
premise universally unprofitable.

V3P02 is different again. Its 744-URL checksum census passed, all frozen resource
gates were reported as passing, and AAVEUSDT and BNBUSDT sample payloads passed
checksum, schema, timestamp-density, event-gap, and aggregate-trade-ID continuity
checks. The DOGEUSDT response ended before its HEAD-declared byte count, so the
three-sample protocol produced no authoritative result.

### D-058 Do Not Rescue The V3P02 Transport Stop

The V3P02 protocol permitted exactly three sample GET requests. All three request
markers exist; the third request failed transactionally and the partial archive was
removed. Do not add a retry, reconstruct lost HEAD observations, or widen the request
budget after observing this failure. Preserve the two verified archives and the
failed marker as useful source evidence, but authorize neither a full acquisition nor
a V3P02 primary.

A future protocol may predeclare incremental HEAD-record persistence, total
wall-clock transfer limits, and bounded resumable/recovery semantics. That must be a
separately versioned research round, not an amendment that changes V3's terminal
classification.

### D-059 Select Zero Primaries And Close V3

The V3 selection rule requires every predeclared feasibility gate to pass. No proposal
did so. Freeze `SELECT_ZERO_V3_PRIMARY_MECHANISMS`, close V3, define no parameter set,
inspect no strategy return, and create no candidate or downstream permission.

The next mechanism search may begin only under a separately frozen V4 discovery
charter. V4 must preserve all V3 terminal evidence and contamination boundaries and
must not be a renamed retry of a stopped V3 path.

### D-060 Freeze V4 With Crash-Safe Evidence Collection

V4 binds the terminal V3 screen and every V3 proposal result as immutable
predecessors. It permits at most three theory proposals, one selected primary, zero
return-tested mechanisms, and zero charter-stage parameter sets. It cannot inspect
market numeric values, calculate signals or returns, open sealed partitions, or
create Pine, paper, sandbox, live, or capital permission.

Every future V4 network attempt requires a separately frozen proposal transport
contract. Request intent must be durable before the attempt; response status,
headers, bytes, hashes, and timestamps must be appended afterward; cumulative
attempts and resource use must survive process restarts; completed observations must
be persisted incrementally; and partial-byte evidence must be preserved before
transactional cleanup. Retry, timeout, resume, concurrency, byte, storage, checksum,
and terminal-stop behavior cannot be expanded after an observation.

### D-061 Register Two Independent V4 Theories Without Padding

V4 registers two, not three, proposals:

- `V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE` tests a
  same-asset law-of-one-price mechanism using pre-funded inventory and synchronized
  executable BBO on two independently operated spot venues.
- `V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM` tests whether compensation
  for bearing option convexity and tail risk survives executable option fills,
  discrete hedging, fees, margin, liquidation, and settlement.

The first is not V3 cross-asset cointegration, price-direction forecasting, funding
carry, or passive market making. The second is not spot-perpetual carry, trend,
breakout, reversal, broad beta, clock phase, or queue-based spread capture.

Triangular arbitrage and put-call parity are not separately registered because they
reuse the execution and data foundations of V4P01 and V4P02. Stablecoin
mint/redemption is excluded because direct issuer and banking access is not a
credible Aurex assumption today. A directional liquidation-reaction rule is excluded
because it lacks one independent pre-outcome sign and overlaps retired directional
families. Leaving one proposal slot unused reduces multiplicity and is not missing
work.

### D-062 Require Feasibility Before Choosing Either V4 Primary

V4P01 requires a checksum/revision-bound, disconnect-aware, synchronized two-venue
BBO archive with quantities, exchange and local timestamps, point-in-time fees,
filters, venue state, legally accessible accounts, pre-funded inventory, and
deterministic acknowledgement, partial-fill, rollback, balance, and inventory
reconciliation. Candles, unmatched last trades, normalized quotes without recovery
evidence, and post-trade transfers cannot substitute.

V4P02 requires complete grouped option-chain quotes, trades, instrument lifecycle,
underlying hedge quotes, local timestamps, disconnect/revision evidence, point-in-time
fees, margin, liquidation, expiry, delivery, settlement, and legally accessible
derivatives execution. Marks, midpoints, model values, option trades without BBO,
current rules projected backward, and underlying candles cannot substitute.

The proposal register authorizes no network request. Each proposal needs a separate
frozen crash-safe transport and execution-feasibility contract. Source or execution
failure may reject both and close V4 with zero selected primaries. Theory support is
not edge evidence.

### D-063 Bind V4P01 To Exact ETH/BTC Evidence Before Network Access

V4P01 uses `ETH/BTC`, not a USD or stablecoin proxy: Binance Spot `ethbtc` and
Coinbase Exchange `ETH-BTC`. This removes hidden quote-conversion and redemption
legs from the law-of-one-price premise. The complete development boundary remains
2023-2024, but this feasibility contract may inspect only source identity,
availability, incidents, schema keys, timestamps, update identifiers, disconnects,
snapshots, row counts, byte counts, hashes, and resource use.

The contract authorizes exactly eight public `api.tardis.dev` GET requests:

- two exchange-metadata requests, one for Binance and one for Coinbase; then
- only if metadata passes, six exchange-native one-minute schema pilots covering
  both venues at `2023-01-01 00:00`, `2023-12-01 12:00`, and
  `2024-12-01 23:59` UTC.

Each URL has one attempt, zero retries, no range/resume, 10-second connect and
30-second read-inactivity limits, fixed per-response and cumulative byte budgets,
single-request concurrency, and a 1,200-second protocol wall-clock budget. Request
intent and response/failure records must be fsynced around every attempt; observations
must be persisted incrementally; partial bytes must be counted and hashed before
cleanup; and exactly one complete, reject, or transport-stop artifact may terminate
the protocol.

Fourteen source/execution gates are hard failures with no conservative override,
including exact product identity, source integrity, disconnect/snapshot recovery,
point-in-time fees and filters, jurisdiction/account access, pre-funded inventory,
IOC/FOK semantics, two-leg unknown/partial-fill rollback, balance reconciliation,
capacity, and stale-data controls. Passing the bounded pilot still cannot select
V4P01 or authorize returns.

### D-064 Preserve The First V4P01 Reject And Correct The Protocol Separately

The first V4P01 runner completed both metadata requests and rejected because each
exact symbol had no `availableTo` value. Official Tardis documentation defines
`availableTo` as optional and set when collection stops; the enclosing exchange
coverage extended beyond the frozen development period. This was a runner
interpretation defect, not negative market or strategy evidence.

Do not delete or rewrite the first terminal result. Bind it into a separately
versioned continuation contract that repeats neither consumed metadata request and
authorizes only the six original unconsumed payload URLs. The correction is
pre-payload and source-semantic only; it does not inspect prices, tune a strategy,
expand a budget, or authorize a return.

### D-065 Reject V4P01 Before Primary Selection And Do Not Retry It

All six continuation payload requests completed with zero transport failures and no
numeric market-value inspection. Exact product and timestamp foundations are
present, but four independent decisive hard gates fail:

- four of six frozen pilots do not expose the required recovery snapshot message;
- no payload response has an upstream ETag or Last-Modified revision identity;
- verified point-in-time 2023-2024 account-tier fees and fee-currency rules are
  absent; and
- verified point-in-time filters, product status, maintenance state, and venue rules
  are absent.

These failures are sufficient to reject V4P01 before primary selection regardless of
any uninspected spread or return. Do not request another minute, relax the snapshot
gate, substitute current venue rules, estimate missing source revisions, parameterize
the mechanism, or calculate a return under V4P01.

### D-066 Correct Terminal Explanations Without Reopening Decisions

The continuation parser compared Tardis's lowercase Binance request identity
`ethbtc` with Binance's exchange-native uppercase wire symbol `ETHBTC`. An
identity-only audit reconciles them and corrects the common-product gate explanation.
The original terminal also marked common-product identity `PASS` while claiming every
payload already matched, which was internally inconsistent.

Freeze a non-authorizing addendum that corrects both explanations and preserves the
terminal rejection. The raw-schema gate still fails after case correction because
four recovery snapshots are absent; source revision, point-in-time fee, and
point-in-time venue/filter gates also still fail. Explanation repair is mandatory
evidence hygiene, not permission to retry a rejected mechanism.

### D-067 Stage V4P02 Metadata And Headers Before Any Option Payload

V4P02 cannot begin with option-chain downloads or raw replay. Freeze a first source
census containing exactly one public Tardis Deribit exchange-metadata GET followed,
only after metadata passes, by 27 zero-body HEAD requests. The HEAD matrix covers
three dates (`2023-01-01`, `2023-12-01`, and `2024-12-01`) across nine products:
grouped `OPTIONS` options-chain, quotes, trades, book snapshots, and liquidations,
plus `BTC-PERPETUAL` quotes, trades, book snapshots, and derivative ticker.

Dataset HEAD redirects are expected by the documented source path, but the runner
may follow at most three manually validated public-HTTPS hops. It must reject
credentials, private, loopback, link-local, non-HTTPS, scheme-downgrade, retry,
range, resume, or body-bearing HEAD behavior and persist every redirect hop.

This census may observe only source identity, availability, incidents, export
boundary, headers, content length, revision identity, elapsed time, and storage
projection. It cannot inspect a CSV row, option price, BBO, amount, strike, Greek,
margin value, trade, P/L, or return. Passing it authorizes no payload: a separate
contract is still required for any bounded schema or raw-disconnect pilot.

Seventeen source and execution gates remain non-overridable, including operator
jurisdiction and derivatives access, full calendar and incident coverage, option and
hedge BBO/trade foundations, instrument lifecycle, disconnect/sequence/revision
integrity, point-in-time fees, settlement, margin and liquidation, deterministic
non-atomic multi-leg order state, collateral and balance reconciliation, capacity,
tail-loss limits, and kill switches.

### D-068 Preserve The V4P02 Metadata Budget Stop

The verified V4P02 runner consumed the one frozen Deribit metadata GET attempt.
Before reading a response-body byte, the server declared `203,310,405` bytes through
`Content-Length`; the contract permitted at most `8,388,608`. Record a durable
`ValueError` transport failure, preserve the request intent and failure in the
hash-chained journal, accept zero response-body bytes, make zero retries, and issue
none of the 27 dependent dataset HEAD requests.

This is a transport-feasibility stop, not evidence that Deribit datasets are absent
and not a profitability rejection. The documented Tardis exchange-details endpoint
returns all symbols and dataset metadata; its current response size invalidates the
frozen bounded census design. Do not resize the body budget, substitute another
endpoint, add credentials, skip metadata, continue with HEADs, or retry under
V4P02.

### D-069 Close V4 With Zero Primary Mechanisms

Apply the charter's predeclared rule that every feasibility gate must pass before
primary selection. V4P01 is terminally rejected on recovery-schema, source-revision,
historical-fee, and historical venue/filter-state evidence. V4P02 is terminally
transport-stopped before its metadata gate and consumed no HEAD. Neither is
qualified; freeze `SELECT_ZERO_V4_PRIMARY_MECHANISMS`, close V4, inspect no market
numeric value or return, and grant no candidate, development, validation, paper,
sandbox, live, or capital permission.

### D-070 Require Capability And Operator Facts Before Successor Alpha Discovery

Repeated V3/V4 feasibility failures show that mechanism-first proposal generation is
now less useful than access-first design. Freeze a post-V4 capability-gap review
before any successor charter. Aurex has proven evidence-grade bar replay and
implemented substantial paper/risk infrastructure, but it has no positive net edge,
qualified execution-grade tick/L2 source, deterministic production adapter,
qualified sandbox operation, trade-level Pine parity, or genuine external webhook
receipt.

Successor alpha discovery remains unauthorized until the operator freezes six facts:
intended venue, permitted product scope, account/API access, actual starting capital,
maximum acceptable loss, and data-acquisition budget. Until then, only two
non-alpha evidence tracks may advance under existing boundaries: rejected v1.3
trade-level parity with explicit TradingView authority, and one genuine authenticated
webhook delivery that terminates at paper-safe rejection.

### D-071 Preflight Operator Facts Before Freezing Them

Implement a separately typed post-V4 operator access, capital, loss, and data-budget
profile rather than recording free-form answers in the ledger or live-deployment
tables. The profile must bind the post-V4 review, contain no credentials or account
number, hash the exact operator attestation, derive loss and first-$100-to-capital
ratios deterministically, and preserve every failed gate.

Use a four-mode non-network workflow: print a template, preflight a filled input
without writing evidence, freeze only a passing input, and independently check the
frozen result. Refuse borrowed capital, emergency-fund capital, effective leverage
above `1x`, inconsistent product/derivative attestations, inconsistent paid-data
budgets, common credential patterns, unverified account/API access, absent sandbox
path, and planning limits above `0.5%` per trade, `1%` daily, or `10%` total.

A passing profile authorizes only design of a separately frozen successor discovery
charter. It does not authorize successor discovery execution, network requests,
market import, parameters, returns, a candidate, paper, sandbox qualification, live
trading, or capital. Do not freeze a real profile until the operator supplies the
facts and the preflight is green.

### D-072 Bind Source Policy And Database State Before External Webhook Proof

Do not accept `TRADINGVIEW_SOURCE_IP_MATCHED` by itself as external-delivery proof.
The classification could be produced by an unsafe broad CIDR or an exact but
undocumented host. Bind the canonical configured networks, network-policy status,
network hash, and official authority URL into the original webhook receipt. Require
exact `/32` IPv4 hosts from Aurex's freshly reviewed TradingView sender snapshot;
continue to classify other valid configurations for diagnostics, but block them from
the `delivery_verified` verdict.

Do not freeze pasted verification JSON. The external-proof CLI must query Aurex's
configured database, bind the operator-declared exact signal ID, and re-query the
same signal during independent audit. Require one sanitized TradingView alert-log
artifact, a delivery timestamp reconciled within 15 minutes, an official source-list
review within 24 hours before receipt, the exact rejected v1.3 identity, complete
`RECEIVED -> VALIDATED -> RISK_REJECTED` events, and zero paper order, paper trade,
live order intent, broker order, or broker fill.

A passing artifact may prove Stage 3 external delivery for that one signal only. Its
pipeline, promotion, paper, sandbox, live, and capital permissions remain false.
Synthetic tests and hand-built artifacts remain software evidence, never operational
proof. Keep the default proof output absent until a genuine alert and alert-log record
pass every gate.

### D-073 Require Exact Chart Data Before Trade Parity

Do not infer Pine/Aurex engine parity by comparing a TradingView completed-trades
report against a replay driven by unrelated market candles. Feed, venue, timestamp,
or export differences can otherwise masquerade as strategy-engine disagreement or
agreement. Parity v1.1 therefore requires a separate TradingView chart OHLCV export
from the same unchanged `BINANCE:BTCUSDT` 15-minute state as the Strategy Tester
report, plus the checksum-verified Binance Vision reference dataset.

Require exact symbol, timeframe, coverage, timestamp, and Decimal OHLCV equality
before trade matching. Missing, wrong-source, wrong-reference, or tampered chart
evidence is `BLOCKED` and cannot be recorded. Structurally valid market disagreement
is an immutable `FAILED` parity result that preserves every candle and field
mismatch; trade comparison does not run until market data match exactly.

A passing parity result calibrates the local replay engine only. It does not validate
profitability, promote a strategy, reverse v1.3's rejection, or permit paper,
sandbox, live, or capital use.

### D-074 Keep Operator HTTP Preflight No-Write And CLI Freeze Independent

The dashboard may collect non-secret operator planning facts, display status, run
the same typed gates, and download the exact passing input. It must not freeze,
overwrite, or independently reinterpret the canonical profile. Only the hash-bound
CLI may freeze and reconstruct the artifact against the post-V4 lineage.

Cap HTTP input at 64 KiB, set `Cache-Control: no-store`, refuse credentials,
secret-labelled material, and account-number-shaped aliases, and return sanitized
field/message/type errors without rejected values. Status responses expose artifact
state and hashes, never the stored operator input or capital values. Any form edit
invalidates the prior preflight and disables download/freeze-command handoff.

A synthetic `9/9` UI or API result proves software behavior only. It is not an
operator attestation and creates no artifact or authority. Even a real passing and
independently frozen profile may authorize only successor-charter design; network,
market import, parameters, returns, candidates, paper, sandbox, live, and capital
permissions remain false.

### D-075 Require Protocol-Bound Paired Exports Before Trade Parity

Exact candle equality is necessary but cannot detect a Strategy Tester CSV exported
after Pine inputs, Strategy Properties, dates, costs, sizing, or order settings were
changed. A parity result must therefore require both an imported report that consumed
the exact intact frozen protocol and a reviewed paired-export manifest binding the
frozen run, chart evidence, original report bytes, coverage, source references, and
an exact timestamped operator attestation.

Make frozen manifest and package hashes configuration-stable across protocol
consumption. Consumption state, readiness checks, and reasons remain visible, but
they do not alter the configuration hash after the report consumes its single-use
protocol. Missing protocol lineage, missing attestation, absent review, or a stale
reviewed hash is `BLOCKED` and cannot be recorded.

The attestation is not a TradingView signature and does not prove the operator's tab
state independently. It makes the claim explicit and binds it to the exact retained
artifacts. A pass remains comparison-only engine calibration, cannot reverse v1.3's
rejection, and grants no strategy, paper, sandbox, live, or capital permission.

### D-076 Treat Responsive Runtime Clarity As A Control-Plane Requirement

Static markup and API tests did not prove that an operator could see the active
workspace on a narrow screen or that legacy evidence shapes would avoid leaking
`undefined` into a decision surface. Runtime inspection showed the active Backtests
tab entirely outside the 362-pixel mobile navigation viewport and a reference replay
summary containing `undefined/undefined HTF`.

When a workspace activates, Aurex must center its active navigation control whenever
the strip overflows. Optional warm-up values must render as `n/a` or an explicit
partial pair, never as JavaScript internals. Versioned frontend assets must advance
when controller behavior changes. Critical lineage, compare, and record actions stay
disabled until their evidence contracts pass.

Responsive visual success is usability and control-plane evidence only. It cannot
substitute for authentic TradingView exports, operator attestation, parity evidence,
strategy eligibility, paper qualification, live approval, or profit.

### D-077 Separate Request Concurrency From Control Eligibility

The shared asynchronous UI wrapper set `button.disabled=true` while an action ran and
unconditionally set it to `false` in `finally`. If the action refreshed evidence and
a renderer correctly disabled that button under a new parity, eligibility, approval,
or risk state, cleanup could silently overwrite the policy decision.

Request concurrency and control eligibility are different state domains. Aurex must
track pending actions independently, reject duplicate activation while pending, and
never write native `disabled` state from generic request cleanup. Pointer activation
is suppressed by the loading state; keyboard or programmatic duplicates are rejected
by the same in-flight lock. Renderers remain the sole owners of policy state.

This decision is fail-closed UI hardening. It does not prove any strategy, external
delivery, parity result, paper outcome, exchange connection, live readiness, or
profit.

### D-078 Stop Authority-Free Continuation At The Real Evidence Boundary

Three consecutive goal checkpoints reached the same unresolved condition after
completing the permitted paired-lineage runtime and action-lifecycle audits. The
operator has not supplied a real non-secret capability profile and has not explicitly
authorized either the frozen TradingView paired-export run or the single external
safe-rejection alert.

Read-only database inspection confirms that no new external evidence silently arrived.
Aurex has no v1.3 report, fully protocol-bound report, TradingView chart dataset,
parity run, signal, or signal event. Both required real proof artifacts remain absent.
The canonical resume point expressly prohibits more synthetic UI, webhook, parity,
alpha, V3, or V4 work as a substitute.

Mark the persistent goal blocked at this evidence boundary. Unblock only on one of
three explicit operator actions: supply the exact non-secret profile facts; authorize
the exact frozen-v1.3 chart/report export workflow; or authorize the one bounded
authenticated TradingView alert workflow. Blocking changes no verdict or permission:
no strategy is eligible and live remains disabled.

### D-079 Treat Live Chart Identity As Ephemeral Context, Not Strategy Evidence

The resumed read-only TradingView check observes `BINANCE:BTCUSDT` at `30m`, whereas
the historical July 20 identity observation was `15m`. The only current study is
`Aurex jam_reversal_v1`; Strategy Tester exposes zero metrics and reports no strategy.

Preserve both observations with their dates. Current chart identity may establish
what is visibly loaded now, but it cannot establish frozen source, strategy type,
parameters, dates, costs, sizing, or order semantics. It must never be relabeled as
`trend_pullback_v1` evidence or used to infer parity. Do not change the chart to the
required `15m` frozen-v1.3 state without explicit mutation authority.

The read-only observation reactivates evidence gathering but does not unblock
paired-export parity, webhook proof, strategy eligibility, paper operation, sandbox,
live, or capital.

### D-080 Require Current Source Binding Beyond A Matching Study Name

The current chart and local file share the display name `Aurex jam_reversal_v1`.
The local file is unchanged from the historical verified v1.14 hash and declares
`strategy()`, while the current Strategy Tester reports no strategy. A source read
could not proceed because Pine Editor is closed; opening it would change TradingView
UI state and lacks explicit authority.

Do not infer current chart/local equality from the display name, historical equality,
or screenshot. Classify current loaded-source identity as unproven until source is
observed under authority and hash-compared. Preserve the local strategy declaration
and current no-strategy observation as a discrepancy, not as evidence that either is
wrong.

This blocks jam evaluation and prevents accidental substitution for trend v1.3. It
does not alter jam's quarantine, any strategy verdict, or any downstream permission.

### D-081 Re-Block After The Fresh Three-Turn Resume Audit

After the prior blocked goal was resumed, turn one established current chart identity
without mutation and turn two preserved the current jam source-binding discrepancy.
Turn three finds no new operator profile, TradingView export, parity record, webhook
event, or explicit authority. The remaining source-binding step requires opening
TradingView UI; every parity and webhook step already requires the broader exact
authority defined in the resume sequence.

The fresh resumed audit therefore satisfies the three-consecutive-turn rule again.
Mark the goal blocked rather than reading unbound study values, speculating about jam,
creating synthetic exports, or extending implementation beyond the canonical
evidence boundary.

Unblock only when the operator supplies the non-secret capability facts or explicitly
authorizes one exact TradingView workflow. No strategy is eligible, no edge is
established, live stays disabled, and real profit remains `$0`.

### D-082 Treat Binance As Provisional Research And Testnet Venue

Accept `Binance.com` as the intended research, market-data, and Spot Testnet venue for
the operator's initial `BTCUSDT` `1x` scope. Do not infer personal account
verification or API permission from platform-level documentation. The operator
reports that the account exists, API Management is visible but requires verification,
and Spot Testnet is accessible; preserve the account and API statuses as unverified
until the operator completes Binance identity verification and confirms access.

Zimbabwe's current VASP framework requires a provider register and online
registration evidence. No authoritative Binance Zimbabwe registration evidence was
established during this checkpoint. Keep Binance real-money execution provisional and
keep `legal_and_tax_obligations_acknowledged=false` until the operator confirms the
individual-use boundary and accepts responsibility for the applicable venue terms,
law, and tax obligations. This legal boundary does not block Binance public-data
research, local backtesting, or Spot Testnet work, but the real operator profile cannot
be frozen and no live permission can exist.

### D-083 Separate Testnet Engineering Authority From Production Eligibility

Freeze a dedicated Binance Spot Testnet capability profile instead of weakening the
production operator profile. The Testnet profile may authorize adapter implementation,
successor-charter design, official Testnet requests, and virtual order entry. It may
never authorize strategy eligibility, returns, candidate promotion, forward paper,
production connectivity, live trading, or real capital. Keep the REST origin fixed to
`https://testnet.binance.vision`; do not accept a configurable production host.

### D-084 Preserve Binance Placement And Cancellation Client IDs Separately

For `DELETE /api/v3/order`, treat `origClientOrderId` as the original order identity
and `clientOrderId` as the cancellation identity. Do not relax reconciliation by
ignoring either. Aurex must supply a deterministic `newClientOrderId`, require stable
external `orderId` across placement/query/cancel/final query, require the original
placement ID before cancellation and as the cancel origin, and require the
deterministic cancellation ID in the cancel response. The final query must use the
immutable external `orderId`, and its response must retain the original placement
client ID. A cancellation-operation client ID must never be sent as
`origClientOrderId`.

### D-085 Bind Test Orders To Binance's Dynamic Percentage-Price Filter

Do not derive a resting Testnet order from the last ticker alone or place it on a
filter boundary. Parse `PERCENT_PRICE_BY_SIDE`, require the matching Binance
average-price window, validate BUY and SELL multipliers separately, read the current
best bid, and construct a BUY with margin inside the allowed band and below that bid.
Revalidate the dynamic filter immediately before both `order/test` and actual
Testnet submission. If the window, band, bid, tick, quantity, notional, or resting
condition is unavailable or inconsistent, fail before submission.

### D-086 Derive Reconciliation From Exact Checkpoints

Do not trust a previously calculated `order_reconciliation` field when complete
exchange checkpoints exist. Derive the verdict from placed, queried, cancelled, and
final snapshots using the current versioned contract. Preserve the untouched source
and bind any corrected interpretation to its SHA-256 in a separate addendum. A
derived pass may close only the exact lifecycle gate it proves; it cannot set
`sandbox_qualified`, production authority, or live authority.

### D-087 Freeze And Independently Verify The Fill Ledger

Freeze Phase 2B before permitting another Testnet order. Bound one market BUY to
`6.50 USDT`, each order to at most `$10`, and the round-trip USDT loss to at most
`$0.50`. Sell only campaign-acquired BTC after actual base-asset commission and
market-step rounding. Read `GET /api/v3/myTrades` for every order and reconcile every
commission in its actual asset. Require exact before/after balance equations for all
touched assets. Query deterministic client IDs after ambiguous outcomes and never
blindly resubmit. A partial fill may use at most one filter-valid cleanup order and
must still fail qualification. Persist every checkpoint before continuing and refuse
to overwrite an existing campaign artifact. The read-only status verifier must
rebuild order totals and balance deltas from evidence rather than trust stored pass
flags. Phase 2B cannot set whole-sandbox, production, live, strategy, or profit
eligibility.

### D-088 Close Phase 2B On Exact Venue-Native Accounting

Accept Phase 2B decision `PHASE_2B_FILL_FEE_RECONCILED` from the preserved source
and independently reproducible audit. The BUY and SELL filled exactly once under
their deterministic IDs; trade quantities and quote quantities equal each order;
commission assets and amounts are explicit; BTC returned to its initial total; and
the expected and observed USDT change both equal `-0.00000100`. No cleanup or
unresolved outcome exists. Preserve the source and audit hashes and do not rerun the
campaign. This proves bounded REST fill accounting only. It does not prove streaming
execution reports, reconnect recovery, reset handling, soak stability, strategy
edge, whole-sandbox qualification, production readiness, live eligibility, or
profit.

### D-089 Bind Phase 2C To Signature Subscription And REST Gap Recovery

Use Binance's current Testnet WebSocket API endpoint and
`userDataStream.subscribe.signature` with the existing HMAC Testnet key. Do not build
new qualification logic on the retired REST listen-key endpoints. Freeze two
resting, no-fill BUY orders at no more than `$10` each. Require the first `NEW`
execution report, deliberately disconnect before cancelling it, reconnect with a
fresh signature subscription, and recover the missed cancellation through exact
REST order/account/trade queries. Require the second order's `NEW` and `CANCELED`
events to reconcile exactly with REST and require the final USDT account-position
event and BTC/USDT balances to match REST. Hash and suppress exact duplicate events
across connections. Persist no credentials, never blindly resubmit an ambiguous
order, and block on any fill, trade record, balance drift, cleanup uncertainty, or
identity mismatch. Phase 2C still cannot set whole-sandbox, production, live,
strategy, or profit eligibility.

### D-090 Close Phase 2C On Recovered And Streamed Order State

Accept decision `PHASE_2C_USER_STREAM_RECONCILED` from the byte-preserved source and
reproducible audit. The first order's streamed `NEW` state and REST-recovered
post-gap `CANCELED` state share exact order identity and zero execution. The fresh
subscription's second order has exact streamed and REST `NEW`/`CANCELED` parity.
Both account-trade ledgers are empty, five unique events were retained, the final
USDT account-position event equals REST, and initial/final BTC and USDT balances are
identical. Preserve both hashes and do not rerun the campaign. This proves bounded
event delivery and reconnect gap recovery only; it cannot set reset/soak,
whole-sandbox, production, live, strategy, or profit eligibility.

### D-091 Freeze Phase 2D As A Three-Process Fail-Closed Campaign

Freeze contract hash
`5e5f1f22a014fa087c44a13341f862fe6d64ea441db280fabae677bf2af820d8`.
The first process must require an empty `BTCUSDT` open-order census, atomically
record one deterministic intent, submit exactly one resting order capped at `$10`,
and exit while it remains `NEW`. A distinct process must recover that exact order
from durable hash-checked state and exchange reads without a second placement
request. It must persist the kill-stop before cancelling, prove a separate entry is
blocked locally, and reconcile exact `CANCELED`, zero-fill, empty-trade, balance,
and open-order state. A third process must hold the kill-stop for 600 seconds while
meeting the frozen REST heartbeat, authenticated reconciliation, and forced
WebSocket reconnect counts.

Binance Testnet periodically erases all order data without advance notice. Treat a
missing tracked order, erased canceled-order history, account drift, or unexpected
open order as invalidated exchange state. Never recreate the missing order and
never cancel unrelated orders. Passing Phase 2D may set Binance Spot Testnet
adapter sandbox qualification only after independent source preservation and
audit. It cannot set strategy, production, live, real-capital, or profit
eligibility.

### D-092 Close Phase 2D And Qualify The Testnet Adapter

Accept decision `BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED` from the byte-preserved
source and reproducible audit. Exactly one placement request created external order
`22377060`; a separate process recovered the same open order by deterministic
identity without resubmission. The durable kill-stop was persisted before
cancellation, a separate entry was blocked locally, and final order state is
`CANCELED` with zero execution, zero cumulative quote, an empty trade ledger, no
open orders, and exact initial/final BTC and USDT balances.

Accept the `602.766` second soak with 120 REST heartbeats, 21 authenticated
reconciliations, two forced WebSocket reconnects, three valid signature
subscriptions, no exchange reset, and no invalidated state. Preserve source SHA-256
`8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50`
and audit SHA-256
`0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29`.
This qualifies the Binance Spot Testnet execution adapter only. It does not qualify
a strategy, production exchange access, live trading, real capital, returns, or
profit.

### D-093 Adapt Jam To The Actual Spot Execution Boundary Before Returns

Do not validate the parent's short side and later pretend it is deployable through
Binance Spot. Preserve `jam_reversal_v1` v1.14.0 unchanged and create
`jam_reversal_spot_v1` as a separately identified long-only descendant. Bind it to
BTCUSDT 15m, `$100`, `1x`, `0.10%` commission per side, and prior confirmed
one-hour EMA values. Supersede any unrun protocol defect before opening outcomes;
never rewrite the immutable record.

### D-094 Reject Jam Reversal Spot V1.0.1

Accept the audited decision `REJECT_CURRENT_VERSION`. Protocol
`f788795a-ac75-4763-93c2-75a031ee2c70` predates replay
`82e5ff23-a4de-423b-b8df-6394d09566a1`. Validation
`6ad2fef6-ffd3-4773-9f02-52e80596bdd4` records 14 trades, `-$0.5371`, PF `0.8301`,
negative expectancy, four OOS trades, OOS PF `0.6771`, and zero of six passing
folds. Both integrity audits pass.

The zero-cost path is positive, but base fees exceed gross profit and half-cost PF
remains below the frozen aggregate gate. Retire v1.0.1 and contaminate its opened
BTCUSDT 15m 2023-2025 decision period. Do not authorize TradingView parity,
forward paper, Testnet strategy orders, live execution, or real capital.

### D-095 Adopt Aggregate Trades As Jam's Primary Historical Source

Accept the audited remediation decision
`PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION`.
The selected Jam successor mechanism requires signed aggressor flow, so official
Binance Spot monthly aggregate trades are the historical feature-authority source.
Official one-minute klines are secondary QA evidence only and may not overwrite
aggregate values.

The 2021-12 duplicate aggregate member is byte-identical to the canonical top-level
member. Treat it as a packaging defect and permit the top-level member only under
that exact identity proof. Quarantine all 4,009 missing kline minutes, eight invalid
kline rows, and 144 cross-family mismatch minutes. The resulting union is 4,161
minutes. Never synthesize a tradable bar, substitute zero flow, or carry future
state through a defect boundary.

Freeze 2019-2020 as development, 2021 as sealed validation, and 2022 as sealed
holdout before any feature or outcome access. Require a future feature to reset at
each quarantined boundary and complete its maximum causal lookback before
eligibility. This decision creates source policy only; it does not establish edge
or authorize a candidate, return, paper run, Testnet strategy order, production,
live execution, real capital, or profit.

### D-096 Freeze Jam's Measurement System Before Any Real Feature Run

Accept decision
`PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION`.
Fix the evaluation row to four causal non-overlapping phases: 120 baseline minutes,
five pre-shock-reference minutes, five shock minutes, and three confirmation minutes.
The complete 133-minute window must be valid inside one evidence partition.

Preserve the exact 17-feature vector for baseline flow, pre-shock VWAP, sell-flow
shock, price impact, confirmation flow, decay, reclaim, and bounce. Use aggregate
trade aggressor semantics, Decimal arithmetic, conventional `1.4826 * MAD`
normalization, and 18-place half-even output. Do not define a threshold, predicate,
future label, entry, exit, stop, target, sizing rule, signal, or strategy.

Only `READY` rows may expose values. Every quarantine, absent aggregate minute, or
partition boundary withholds the entire vector and requires full causal warm-up.
This decision establishes deterministic measurement only and grants no evidence of
edge, candidate, paper, order, production, live, capital, or profit authority.

### D-097 Require A Paired Raw-Trade Source Pilot Before Development Acquisition

Accept decision `PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL` only from
the separately frozen and pre-network-audited 2020-01 protocol. Exactly one
checksum-pinned USD-M raw `trades` archive was requested. The previously qualified
Spot `aggTrades` archive was reused locally and reverified without another request.

Accept bounded forward raw-ID omissions because the frozen gates measured them
before the payload was opened: 1,809 skipped IDs across 726 forward gaps represent
`0.0001759204485592173611407580450` of observed rows, below the `0.001` ceiling,
and the maximum single omission is 35 against a limit of 100. Do not waive duplicate
IDs, non-increasing IDs, timestamp regressions, incomplete clocks, or incomplete
buyer-maker semantics; all are zero or complete in the observed archive.

This is a source-capability decision, not a strategy decision. A pass authorizes
only a separately frozen paired full-development acquisition protocol. Keep price,
quantity, quote quantity, features, parameters, outcomes, validation, holdout, Pine,
paper, Testnet strategy-order, production, live, real-capital, and profit authority
false.

### D-098 Reuse Exact Local Archives Before Bounded Network Acquisition

Accept the independently reconstructed 2020-2023 paired acquisition protocol under
authorization `AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ARCHIVE_ACQUISITION`. Its 96
checksum-pinned targets contain 37 local reuse candidates and 59 possible network
targets. Reuse is not trust by filename: every candidate must match its frozen hash
and pass the same structural parser before it may enter the acquisition checkpoint.

Bind the Spot 2021-12 exception to the prior byte-identity proof. Aurex may select
the top-level canonical member only when the extra member rehashes identically; any
different member set or bytes fail the archive. Stream one target at a time, record
each request attempt before transfer, checkpoint only fully qualified archives, and
discard partial payloads. Do not use redirects or byte ranges.

This protocol authorizes source acquisition only. It does not authorize parsing
price, quantity, or quote quantity; creating features or parameters; opening
outcomes, validation, or holdout; or running Pine, paper, Testnet strategy orders,
production, live capital, or profit-seeking operation.

### D-099 Accept The Terminal Source-Sufficiency Failure Without Rescue

Accept the completed Q1 successor result
`STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED`. All 37 months were classified and
all 73 inspected archives remain checksum-verifiable, but only 19 paired months
qualified against the frozen minimum of 30. The per-year minimum failed in 2020
and 2023, and only 12 of 16 required quarters qualified.

Do not relax structural gates, reorder source rows, synthesize missing data, lower
the pair/year/quarter thresholds, or reinterpret source qualification as a market
edge. Preserve the v1-v7 lineage, all negative evidence, all 23 v7 marker pairs,
and the independent terminal audit. The artifact grants
`NONE_SOURCE_SUFFICIENCY_FAILED`; no paired measurement protocol may be frozen.
A future research path requires a separately versioned, genuinely independent
mechanism/source charter frozen before outcomes.

### D-100 Select S1 Without Reusing Prior Outcome Evidence

Accept `S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE` as one genuinely unrelated source
and mechanism feasibility path. S1 is long-or-cash BTCUSDT Spot at 1x within the
existing `$100` simulated operator boundary. Selection does not assert edge and
does not permit parameter or return inspection.

### D-101 Preserve The FRED Vintage Failure

The two `fredgraph.csv` raw requests returned byte-identical current NFCI data
through `2026-08-21`, despite 2020 and 2021 `vintage_date` parameters. Preserve the
failed result and its 347/294 post-vintage counts. Never truncate those current
files and call them historical vintages.

### D-102 Accept Only The ALFRED Point-In-Time Transport

Accept the separately frozen ALFRED recovery because both snapshots are distinct,
strictly truncated before their requested dates, and independently reconstructed.
The fact that all 2,555 overlapping values differ is evidence that current revised
NFCI would create material look-ahead leakage, not evidence that NFCI predicts BTC.

### D-103 Keep S1 At Source Acquisition

The ALFRED recovery grants only a full NFCI vintage acquisition protocol. It does
not authorize another network request before that freeze, parameter design, BTC
data access, returns, validation, holdout, Pine, paper, Testnet strategy orders,
production, or live capital.

### D-104 Freeze The Full Development Acquisition Before Network Access

Bind all 281 Thursday targets, ALFRED URLs, vintage-suffixed headers, byte and retry
ceilings, atomic persistence, chronological execution, and ten source gates before
the first full-development request. Source qualification grants no market authority.

### D-105 Preserve The Pre-Network V1 Runner Defect

Do not erase or silently patch the v1 execution contract. Preserve its failed
atomic-rename restart semantics and zero-request state, then use only the separately
frozen v2 amendment and runner contract for acquisition evidence.

### D-106 Accept The Complete Point-In-Time Source Corpus

Accept the development source corpus because all 281 targets completed, each payload
hash is distinct, every marker and byte reconciles, all ten gates pass, and an
independent audit rehashed every raw file and marker. This establishes source
integrity only; it says nothing about BTC expectancy.

### D-107 Keep S1 At Normalization Protocol Only

The acquisition result grants only a normalization protocol. Raw value
transformation, feature construction, parameter definition, BTC access, returns,
validation, holdout, Pine, paper, Testnet strategy orders, production, and live
capital remain unauthorized.

### D-108 Normalize Source Values Without Creating Features

Select only the maximum valid NFCI observation date not after each source vintage,
preserve its exact decimal source text without rounding, and retain complete source
path/hash lineage. Do not calculate changes, rolling statistics, signals, positions,
BTC fields, returns, or PnL during normalization.

### D-109 Accept The Deterministic Development Macro Table

Accept the 281-row dataset because the runner and independent auditor both rehashed
all source files and reconstructed the exact JSONL bytes. The observed 6-20 day
release-lag range is a source-timing fact, not evidence of predictive edge.

### D-110 Keep S1 At Feature Protocol Only

The normalization result permits only a separately frozen macro feature protocol.
No feature calculation, parameter search, BTC join, return calculation, validation,
holdout, Pine, paper, Testnet strategy order, production, or live authority exists.

### D-111 Use Only Three Transparent Macro Features

Permit NFCI level, one-vintage change, and four-vintage change only. Use exact
decimal subtraction with no floating point or quantization, discard only the first
four warm-up rows, and forbid rolling/expanding statistics and percentile transforms.
Cap the later preregistered candidate family at four.

### D-112 Accept The Deterministic Feature Table

Accept the 277-row table because every normalized input row hash, feature formula,
warm-up boundary, and output byte independently reconstructs. Feature integrity is
not predictive evidence and grants no market-data or return authority.

### D-113 Require Full Strategy Preregistration Before BTC Access

Before opening any BTC value, freeze the exact candidate rules, activation timing,
market-data source, execution price convention, fee/slippage stress, chronological
development selection rule, failure gates, and sealed validation boundary. No more
than four candidates may exist.

### D-114 Permit Only The Primary To Establish Eligibility

Preregister consistent one- and four-vintage easing as the sole promotable rule.
Keep one-vintage, four-vintage, and loose-plus-four-vintage rules diagnostic only.
If the primary fails any frozen gate, stop S1; do not promote a diagnostic or tune
the rule. Activate one calendar day after the source vintage and charge 15 bps per
position-changing fill at base and 22.5 bps at stress.

### D-115 Use Exact Official Friday Execution Opens

Acquire only the 277 official Binance Spot daily BTCUSDT 1h archives and checksum
sidecars required for Friday 00:00 UTC execution prices. Require exact checksums,
safe single-member ZIPs, unique target timestamps, and positive finite source text.
Do not calculate a return during acquisition.

## Evidence Register

### E-001 Primary Historical Dataset

- Dataset ID: `9724b9c7-03fa-4cba-9d5f-1e3bd69aa322`
- Symbol/timeframe: `BTCUSDT` / `15m`
- Coverage: `2023-01-01T00:00:00Z` to `2026-06-30T23:45:00Z`
- Rows: `122587`
- Verified archives: `42`
- Documented gaps: `1` outage / `5` missing intervals
- Undocumented gaps: `0`
- Evidence hash: `2a048a6709d0f066977d317ec2d013d362cc68a5f626d85201e98d9c6925440e`
- Latest integrity audit: `PASS`

### E-002 Frozen Strategy Candidate

- Strategy: `trend_pullback_v1` v1.3
- Protocol ID: `288ea36e-abbf-4c1a-b15e-85ef5b097a93`
- Protocol hash: `3a5345306896b4f57005e61f6891ebb788b071901c71f16767a290aecb7bc160`
- Manifest hash: `f5625d927d5b2310994fd0ca43280f6b4863c0034e14bd38e11827b729dce0fa`
- Package hash: `70264556b47df476837cdede26bd3d7d0ee517e066ca89deedbfe02c5d1e4cff`
- Pine SHA-256: `9e68cf52c1072d0efbb4b588d96474439d8283c4ee08c62fd8c700e4870596f7`
- Parity status: unproven

### E-003 Current Negative Strategy Evidence

- Window: January-March 2026 local comparison replay
- Trades: `165`
- Gross P/L: `+$51.15`
- Fees: `$107.41`
- Net P/L: `-$56.26`
- Profit factor: `0.887`
- OOS P/L: `-$77.40`
- OOS profit factor: `0.717`
- Failed gates: `5`
- Interpretation: meaningful negative comparison evidence; not TradingView parity.

### E-004 Complete Multi-Year Reference Replay

- Replay ID: `e1e5539a-49df-409d-8790-93639e173dc5`
- Engine: `trend-pullback-reference-v1.1.0`
- Engine evidence hash: `36601dbd7f5100c3e2a484f9287d32b7e1d5c8b298ba92086d2ad0c6193680be`
- Record evidence hash: `a8b1263e9bde08de46038b053a7f2886bc36656554211c0ee098aa2b40a8d60e`
- Evaluation window: `2023-02-01T00:00:00Z` to `2026-07-01T00:00:00Z`
- Trades: `2270` (`795` wins / `1475` losses)
- Net P/L: `-$695.5152112861285744311254420`
- Profit factor: `0.8078717551837752288683041169`
- Expectancy: `-0.306394366205342984330892264`
- Max drawdown: `$699.0051029879905739447573387`
- Replay audit: `PASS`

### E-005 Historical Trend Protocol With Late Temporal Binding

- Protocol ID: `ebcaffa2-1598-4763-81e2-163da8a77ecf`
- Protocol hash: `84ec75b04bb856a5f7d93505729776139bed87a9db1e2005c5b091666d552146`
- Planner: `explicit_anchored_fixed_parameter`
- Plan hash: `533a14b688150c52408ba85e196a167f291d0f75c2cc364cff756f25d0af7225`
- IS: `2023-02-01` through `2025-01-31`
- OOS: `2025-02-01` through `2026-07-01`
- Walk-forward folds: `6`, fixed parameter, expanding training window
- Replay recorded: `2026-07-18T15:03:58.681516Z`
- Protocol registered: `2026-07-18T15:08:06.418185Z`
- The planner inspected no result fields and thresholds were not relaxed, but the
  durable record is approximately four minutes later than the replay. It is not valid
  preregistration under evaluator v1.2.

### E-006 Preserved Historical v1.1 Validation And Cost Sensitivity

- Validation ID: `454b85d7-75b2-4a6e-8571-b9d951cbc178`
- Evaluator: `reference-replay-validation-v1.1.0`
- Validation evidence hash: `a66caaff0992ecbe8784b411dfe2eee4a2502f16587808dbf42a3f19bfb38249`
- Trade evidence hash: `f4ec3e001d14e3fcddcdcf50de410619f8f2726dc70c2076dd79ead36080c902`
- Historical v1.1 binding checks: `15/15 PASS` under the then-current evaluator.
- Statistical result: `REJECTED`; acceptance, paper, promotion, and live eligibility
  remain false.
- IS: `1298` trades, net `-$533.64736`, profit factor `0.796879`.
- OOS: `972` trades, net `-$161.86785`, profit factor `0.836960`, negative expectancy.
- Walk-forward: `0/6` folds pass.
- Cost-free upper bound: `+$175.7252`, profit factor `1.05755`, still below `1.15`.
- Half-cost case: `-$259.8950`.
- Base costs: fees `$870.59935`, slippage `$0.64106`, net `-$695.51521`.
- Double-cost stress: `-$1566.75562`.
- Historical v1.1 validation audit: `PASS`; drawdown and base-cost decomposition match
  replay. Current evaluator v1.2 blocks the pair on
  `protocol_registered_before_reference_replay_mismatch` and exposes no metrics.
- Preserved legacy validation: `9edfd67d-ec11-4885-bd5f-255daa539115` still audits
  `PASS` under evaluator v1.0.0.

### E-007 TradingView And Jam Source Identity

- Observed: `2026-07-20`, read-only MCP inspection.
- Chart: `BINANCE:BTCUSDT` / `15m`.
- Visible strategy: `Aurex jam_reversal_v1` v1.14.0.
- Source: `702` lines / `48667` characters.
- Chart/local SHA-256: `f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3`.
- Current compile errors: `0`.
- Visible May 1-July 20 result: `+$24.87`, `5/5` profitable trades, `$2.17` max
  drawdown. Classification: development-contaminated and ineligible.
- MCP strategy-results API: contradictory `no strategy found`; not accepted evidence.
- Frozen trend package: `READY`, package hash
  `70264556b47df476837cdede26bd3d7d0ee517e066ca89deedbfe02c5d1e4cff`, exact
  Pine hash `9e68cf52c1072d0efbb4b588d96474439d8283c4ee08c62fd8c700e4870596f7`.

### E-008 Webhook Delivery Evidence Boundary

- Exact request body SHA-256 and byte length are persisted on the immutable received
  event together with authentication transport, content type, peer IP, user agent,
  source-IP verdict, and a deterministic receipt hash.
- Default source networks match TradingView's four published webhook sender addresses
  as checked on `2026-07-20`; the list is environment-configurable and must be rechecked
  before an external run.
- Internal authenticated paper-path result: classified as
  `PIPELINE_VERIFIED_ORIGIN_UNPROVEN`, not genuine TradingView evidence.
- Matching-source integration fixture: proves code classification only; it is explicitly
  excluded from operational evidence.
- Focused webhook and verification tests: `22 passed`; Ruff: `PASS`.
- Dashboard evidence rendering tests pass; full suite: `322 passed` with two known
  warnings and no failures.
- Operational external receipt: missing.

### E-009 Volatility Breakout Binding Failure And Diagnostic Rejection

- Candidate: `volatility_breakout_v1` v1.1.0.
- Frozen Pine SHA-256:
  `4b692f3f95c06ae4bfa787f2c8f4fc2039859d55b9f040cd78284ce720f55d35`.
- Rolled-back transient protocol ID: `42a995dc-1a7a-40d8-ba86-21f08fe3725d`;
  never persisted and not evidence.
- Replay ID: `9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7`.
- Replay recorded: `2026-07-21T12:11:20.906155Z`; audit `PASS`.
- Replay record hash:
  `67fbd22e0b195cb16c3bc37caadb269e292b91e0e4859bd88d3c89dfcff4c20f`.
- Actual protocol ID: `6d0f10f1-8e23-42a2-874a-b36948bc1738`.
- Protocol registered: `2026-07-21T12:12:13.076304Z`, approximately 52.17 seconds
  after replay.
- Protocol hash: `56430081d944b2adf234f313bd72fe5a92eddb952119a20c45ffc4b0372572a9`.
- Walk-forward plan hash:
  `e3a9cf751dabfb5e5390702d4292016dc0cddbc4e000fc44c45194c7110c6d78`.
- Planner outcome fields inspected before source freeze: none. This does not repair the
  missing durable preregistration.
- v1.2 temporal validation: `BLOCKED`; no validation record exists.
- Diagnostic result: 1,125 trades, 368 wins, `-$533.87` net, PF `0.6734`, expectancy
  `-$0.4746`, max drawdown `$556.48`.
- OOS: 470 trades, `-$137.21`, PF `0.7222`, negative expectancy.
- Walk-forward: 0/6 folds pass.
- Zero-cost fixed-path upper bound: `-$37.10`, PF `0.9714`.
- Disposition: `RETIRED`; not paper-, promotion-, or live-eligible.

### E-010 Temporal Registration Guard

- Current evaluator: `reference-replay-validation-v1.2.0`.
- New binding: `protocol_registered_before_reference_replay`.
- Both real post-outcome protocol pairs return `BLOCKED`, expose no metrics, and
  produce no validation hash under v1.2.
- The historical trend v1.1 validation still audits `PASS` under its original version.
- `scripts/register_candidate_protocol.py` commits and reload-verifies candidate
  protocols, and refuses volatility v1.1 because replay
  `9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7` already exists.
- Focused evaluator, preregistration, and replay tests: `25 passed`; Ruff: `PASS`.

### E-011 Failure Attribution

- Trend analysis hash:
  `a7aee7fcd90981b4a51a5d6582a99843614ffec3d3620be92553d4a41118d6c5`.
- Trend pre-cost/net: `+$175.73 / -$695.52`; modeled cost burden `$871.24`.
- Volatility analysis hash:
  `cb139650893fe41b56c6e5b4630c29d27d1cfc0a6e93de8ed7ead3e680c29c1`.
- Volatility pre-cost/net: `-$37.10 / -$533.87`; no gross edge demonstrated.
- Detailed interpretation: `docs/14_STRATEGY_FAILURE_ANALYSIS.md`.

### E-012 Native 4h Decision Data

- BTC development dataset: `1c39d87b-683b-4d3d-a180-6e825f7b622b`; 7,662 rows;
  evidence hash `8059290d0af5108f6c2167bfcba21b755b5ab8d14310a48321cb995e22d15056`.
- ETH untouched dataset: `287e1cca-27d9-4308-8ae7-458d563d4867`; 7,662 rows;
  evidence hash `41acac572e4669b12af1cc477aff8ede82d792ecdce12fd670af135fdaefd12b`.
- SOL untouched dataset: `411799dd-1e55-4b97-ba7b-b6952146ecb5`; 7,662 rows;
  evidence hash `6bc0e852d6d97f30d43cd226706c080907a677d45ff2e17cff3869f0744319d1`.
- All three native 4h datasets cover 2023-01-01 through 2026-06-30, have no gaps,
  verified archive checksums, and audit `PASS`.

### E-013 Frozen slow_breakout_spot_v1 v1.0.0 Preregistration

- Pine SHA-256:
  `2312c6ce75b79b691bfa3542e4d44221a917f2efdeb0853408d93b5e1a099f16`.
- Engine: `slow-breakout-spot-reference-v1.0.0`.
- ETH authoritative protocol: `ff612386-ffa3-41e8-a332-1565d8d46495`; hash
  `66045e3554a0dd3a9db47e71dcedccb83624610b1dd2d7676480b16e47be8c67`.
- SOL authoritative protocol: `080084a0-d1b2-435b-ad9b-bd294a9bf603`; hash
  `af79109cc893bc08550993e0c1375f905b92873cfaa35a2c2afab1c7f8fdc987`.
- Shared walk-forward plan hash:
  `0ddadf63cf5c94d396b0e3020e1a75080727d1972d123b5c657526c6e556de6e`.
- Protocol commits are reload-verified; outcome fields inspected: none.
- Frozen request hashes: ETH
  `bd4a8762f5e8f8eca0ab399eabc83f5d438f7ca5d8c21f37a949bf8f9817ce11`, SOL
  `2c5175f7a5ac26b78f07615c5952f3d2091fd5ffb423ba5f6cdf09d386b7a145`.
- Recorded candidate outcomes at protocol freeze: `0`.

### E-014 Verification And Safety Isolation

- Candidate/Pine/replay/preregistration focused gate: `34 passed`; Ruff `PASS`.
- Candidate-level cross-market evaluator: `4 passed`; accepts no direct paper access.
- Full suite before holdout execution: `352 passed`, one known Starlette warning.
- MKT scoped-runtime regression: four previously environment-dependent tests pass after
  isolation; no global profile can bind to an arbitrary checkout.
- TradingView was not mutated. Live trading remains disabled.

### E-015 slow_breakout_spot_v1 Held-Out Rejection

- Campaign artifact:
  `data/evidence/slow_breakout_spot_v1_1.0.0_cross_market_decision.json`.
- Artifact evidence hash:
  `ce8ce41c25e8dff811db44bf8fe8a77af8d920f67c811be8b6fd403154a95c82`.
- Cross-market decision: `REJECT`; hash
  `b1214ceb3e2f6ef416d0ef83b27e93e331afa5ff59c3201680f5e8013c9bd4d3`.
- ETH replay `0bbe94e9-4596-41f0-9889-e21ab26085e7`, validation
  `efa5db06-08f9-4344-8869-294cdca54d38`; both audits `PASS`.
- SOL replay `97700413-7a29-4dff-aa7c-aab086e8c1b1`, validation
  `9ea9e6dd-61d1-4e4e-a1d6-f15cfb899d72`; both audits `PASS`.
- ETH: 53 trades, `+$44.6864`, PF `1.5557`; OOS 21 trades, `+$7.2549`, PF
  `1.2082`; walk-forward pass rate `0.20`.
- SOL: 53 trades, `+$59.7447`, PF `1.8602`; OOS 26 trades, `-$18.3894`, PF
  `0.5185`; walk-forward pass rate `0`.
- Combined: 106 trades, `+$104.4311`, PF `1.6968`; 150% modeled-cost stress
  `+$101.2308`; gross-profit shares ETH `49.20%`, SOL `50.80%`.
- Failure reasons: `ETHUSDT:individual_validation_failed` and
  `SOLUSDT:individual_validation_failed`.
- Development-only analysis hashes: ETH
  `875df2b26714b0fde5b4441a267b4b6ac47d7a944e70a9fc4bc46adc36274b99`, SOL
  `5e2fcdabe850dd0a9ff34061b55de745765115f87db2904ba423695631f9b558`.

### E-016 Research Reset Foundation

- Research reset contract: `docs/16_STRATEGY_RESEARCH_RESET.md`.
- Portfolio engine: `shared-capital-spot-portfolio-v1.0.0`.
- Portfolio evidence schema: `aurex-shared-capital-spot-portfolio-v1`.
- Synthetic controls prove shared allocation, input-order-independent hashing,
  exit-before-entry, priority and same-symbol collision handling, overlapping
  mark-to-market drawdown, fees, adverse slippage, quantity rounding, rejection
  evidence, deterministic replay audit, and tamper detection.
- Contamination artifact: `data/evidence/strategy_contamination_ledger_v1.json`.
- Contamination ledger hash:
  `9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`;
  independent builder check `PASS`.
- Slow holdout artifact hash recomputation: `PASS`.
- Focused portfolio, contamination, and strategy-default tests: `22 passed`; Ruff
  `PASS`.
- Complete project suite after explicit test opt-in updates: `369 passed`, one known
  Starlette/httpx deprecation warning; repository-wide Ruff `PASS`.

### E-017 Frozen Survivorship-Aware Market Universe

- Selection timestamp: `2026-07-22T13:34:26.912026Z`.
- Official historical census: `3,643` Binance Vision spot archive symbols; `680`
  historical USDT markets preserved, including non-ASCII source identity.
- Final roles: `35` decision candidates, `3` development-only (`BTCUSDT`, `ETHUSDT`,
  `SOLUSDT`), and `642` explicit exclusions.
- Decision symbols: `AAVEUSDT`, `ADAUSDT`, `APEUSDT`, `APTUSDT`, `ATOMUSDT`,
  `AVAXUSDT`, `BCHUSDT`, `BNBUSDT`, `CFXUSDT`, `CRVUSDT`, `DOGEUSDT`, `DOTUSDT`,
  `DYDXUSDT`, `ETCUSDT`, `FETUSDT`, `FILUSDT`, `FTMUSDT`, `GALAUSDT`, `GRTUSDT`,
  `ICPUSDT`, `INJUSDT`, `LDOUSDT`, `LINKUSDT`, `LTCUSDT`, `LUNCUSDT`, `MKRUSDT`,
  `NEARUSDT`, `OPUSDT`, `RUNEUSDT`, `SANDUSDT`, `SHIBUSDT`, `STXUSDT`, `TRXUSDT`,
  `UNIUSDT`, and `XRPUSDT`.
- Liquidity source methods: `262` market-data API, `12` checksum-verified archive
  fallbacks, and `406` structurally unavailable/skipped records. All 12 archive
  fallbacks remained incomplete and were excluded rather than filled or hidden.
- Raw source evidence: `1,534` official payloads, `49,939,802` bytes, with individual
  SHA-256 receipts and local tamper verification.
- Enumeration artifact hash:
  `682dbab67d1dfb87586cdc89993f05d551d81dad28aee7b36ea967c237f28e62`.
- Liquidity-input artifact hash:
  `a4c7dfbbfe94f4be4a77fa18019adf7b96f92495bbece9a763a69d638f472719`.
- Final manifest hash:
  `dacc57f649846f716b8134aa0abba5accc78b0f1607d653addb0df3d9e132a74`.
- Builder contract hash:
  `0dd484d55dc33493d73bb9831d01d79bede78c0d89df10cdc433d91537919b86`.
- Contamination ledger binding:
  `9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`.
- Partitions: development `2023-01-01` to `2025-01-01`; sealed validation through
  `2026-01-01`; sealed holdout through `2026-07-01`; locked forward thereafter.
- Selection fields inspected: only `open_time` and `quote_asset_volume`; strategy
  outcome fields inspected: none.
- Network-free `scripts/build_market_universe.py --check`: `PASS`, including every raw
  payload hash and a deterministic final-manifest rebuild.

### E-018 Frozen Development 4h Dataset Bundle

- Bundle: `data/evidence/development_4h_dataset_bundle_v1.json`.
- Bundle hash:
  `fba63b8e237220c760daf902f2c999e9b01121357a4cc583c9fa5cb50b83d341`.
- Builder contract hash:
  `41ed3387ce11c10ce995b9f09c2dbe6a06f0f458f2df88c4a0e855371ebf1772`.
- Coverage: 35 decision markets plus 3 development-only markets, each with 24 monthly
  Binance Vision archives, 24 checksum sidecars, and exactly 4,386 4h candles.
- Totals: 38 ready datasets, 166,668 candles, 1,900 preserved source/data artifacts,
  18,963,351 bytes, zero missing timestamps, zero blocked datasets.
- Partition: `[2023-01-01T00:00:00Z, 2025-01-01T00:00:00Z)` only. No validation,
  holdout, forward, or strategy-outcome field was accessed.
- Network-free `scripts/build_development_dataset_bundle.py --check`: `PASS`.

### E-019 Frozen R3 Mechanism Study

- Protocol: `data/evidence/r3_cross_sectional_momentum_study_v1.json`.
- Protocol hash:
  `8af37e15ca08bcbbdd82c457927d5a4b5039e70f173ff735c16c91a3bed4f893`.
- Status: `FROZEN_PRE_OUTCOME`; registered `2026-07-22T17:39:46.561714Z`.
- Primary: 84-day lookback / 14-day rebalance. Non-selectable falsification horizons:
  28-day / 7-day and 168-day / 28-day.
- Portfolio: `$1,000`, 0.5% risk per position, 20% symbol cap, 100% gross cap, maximum
  7 positions, minimum 3 positive-ranked markets.
- Costs: 0.10% commission and 0.05% adverse slippage per side, rerun at 1x, 1.5x, and
  2x together.
- Evaluation: six independent quarterly folds from 2023 Q3 through 2024 Q4 plus one
  continuous development replay. Validation, holdout, and forward are forbidden.
- Decision: advance only if all profitability, PF, drawdown, trade-count, fold,
  double-cost, leave-one-market-out, concentration, and falsification-support gates
  pass. Faster or slower variants cannot replace the primary.
- Network-free `scripts/freeze_r3_mechanism_study.py --check`: `PASS`.

### E-020 Frozen R3 Execution Specification

- Specification:
  `data/evidence/r3_cross_sectional_momentum_execution_spec_v1.json`.
- Specification hash:
  `7125758ab4b4672576db8de49d8f67f5988f02dc5c39e2d94d36ae2e7edb6eb6`.
- Protocol binding:
  `8af37e15ca08bcbbdd82c457927d5a4b5039e70f173ff735c16c91a3bed4f893`.
- Exact semantics cover aligned inputs, prior-close momentum ranking, symbol tie-breaks,
  Wilder ATR seeding, fixed stops and gap fills, exit/rank/entry ordering, shared-capital
  scaling, rounding, fold resets, end liquidation, mark-to-market drawdown, undefined
  gate metrics, full cost-stress reruns, concentration, and leave-one-market-out.
- The selected count remains 7 in leave-one-market-out runs to prevent the omitted
  market from silently changing portfolio breadth.
- Preexisting result artifacts and inspected outcome fields: none.
- Network-free `scripts/freeze_r3_execution_spec.py --check`: `PASS`.
- Focused development-bundle, protocol, and execution-spec verification: `24 passed`;
  focused Ruff `PASS`.

### E-021 Frozen R3 Engine And Run Package

- Engine: `r3-cross-sectional-momentum-engine-v1.0.0`.
- Run package: `data/evidence/r3_cross_sectional_momentum_run_package_v1.json`.
- Run-package hash:
  `2ca29f9328306c91f8281051731592da5e3d8b00db47573f5f4b08b9d9bb2756`.
- Transformed 35-market candle hash:
  `ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2`.
- Runtime contract: exact Python/Pydantic versions, 50-digit Decimal precision, and
  half-even arithmetic.
- Source contract hashes the engine, result schema, run-package schema, orchestrator,
  and one-shot CLI before outcomes.
- Frozen plan: 9 full-window variant/cost runs, 18 independent variant/fold runs, and
  35 primary leave-one-market-out runs; exactly 62 replays.
- Pre-freeze verification: all 131 unit tests passed with one known Starlette/httpx
  deprecation warning; repository-wide Ruff `PASS`.
- Network-free `scripts/freeze_r3_run_package.py --check`: `PASS`.

### E-022 R3 Development Result And Rejection

- Ledger: `data/evidence/r3_cross_sectional_momentum_result_v1.json`.
- Replay artifacts: `data/evidence/r3_cross_sectional_momentum_results_v1/`.
- Ledger hash:
  `dd751538457a4876ee38fbe7b139cace3b30a81f8846a0ec3e93114fa82d282c`.
- Completed/planned replays: 62/62. Verdict: `NO_CANDIDATE`. Gates: 9/10.
- Primary base result: final equity `$1,330.23`, net `+$330.23`, PF `1.3907`, raw PF
  `1.4671`, max drawdown `$205.63` / 14.78%, 237 trades, 91 winners, 146 losers.
- Primary costs: `$34.06` commission plus `$17.03` adverse slippage; turnover 34.06x.
- Primary at double cost: `+$273.65`, PF `1.3205`, max drawdown 15.89%.
- Positive primary folds: 3/6, failing the required 4/6. Fold net P/L: Q3 2023
  `-$26.27`, Q4 2023 `+$275.58`, Q1 2024 `+$42.61`, Q2 2024 `-$55.99`, Q3 2024
  `+$53.58`, and Q4 2024 `-$135.63`.
- Leave-one-market-out: 35/35 positive, fraction 1.00. The weakest omission was
  `RUNEUSDT` at `+$157.72`; this passes robustness but does not override the fold gate.
- Concentration passed: largest positive raw-profit share 14.50%; top five 57.72%.
- Falsification support passed through the slow horizon, which had 4/6 positive folds.
  It remains non-selectable and cannot replace the primary.
- `scripts/run_r3_mechanism_study.py --check`: `PASS` for all artifact, receipt, metric,
  ledger, and source bindings.
- `scripts/run_r3_mechanism_study.py --deterministic-check`: `PASS`; all 62 replays and
  the complete ledger reproduce exactly.

### E-023 R3 Monthly Diagnostic Correction

- Addendum:
  `data/evidence/r3_cross_sectional_momentum_monthly_addendum_v1.json`.
- Addendum hash:
  `7f538ce899ca6513c109510479980602d6820397fb22e19d80334f46b036192a`.
- Defect: v1 grouped close snapshots by the close timestamp's month, assigning exact
  midnight closes to the new month and creating an extraneous `2025-01` diagnostic.
- Correction: attribute each close to one microsecond before its timestamp, yielding
  the intended 18 months from 2023-07 through 2024-12.
- Affected gates: none. Original and corrected verdict: `NO_CANDIDATE`.
- `scripts/audit_r3_monthly_returns.py --check`: `PASS`.

### E-024 Frozen R3 Failure-Analysis Scope

- Protocol: `data/evidence/r3_failure_analysis_protocol_v1.json`.
- Protocol hash:
  `62ec8d11920cc4634f624ca7ce11fa93a7dc3bebd9871122984aff21e1da7725`.
- Registration is explicitly post-outcome and pre-analysis; it does not pretend the R3
  verdict was unknown.
- Inputs bind the run package, result ledger, monthly addendum, development bundle, and
  all 62 replay result hashes.
- Fixed dimensions cover quarters, corrected months, costs/turnover, BTC/ETH/SOL
  diagnostics, drawdown/exposure, exit reasons, horizon behavior, positive-market
  breadth, and symbol contribution.
- Prohibitions block gate/verdict changes, sealed data, falsification-variant promotion,
  outcome-selected parameters, candidate creation, and direct conversion of discovered
  buckets into trading rules.
- Allowed next decisions are only `PROPOSE_BOUNDED_R3_1` or
  `STOP_CROSS_SECTIONAL_MOMENTUM_FAMILY`; neither decision creates an eligible strategy.
- `scripts/freeze_r3_failure_analysis.py --check`: `PASS`.

### E-025 R3 Failure Analysis And Decision

- Analysis package: `data/evidence/r3_failure_analysis_package_v1.json`.
- Package hash:
  `7863931e7a391f693a788339b583bf5c586a98a41424419aac0d774551cfbbdb`.
- Result: `data/evidence/r3_failure_analysis_result_v1.json`.
- Result hash:
  `52a766a8d0c7e586b340ee28f5900320ed74cc0c57ddab12c4c1367026b40cab`.
- Inputs: all 62 immutable replay artifacts, the rejected ledger, corrected monthly
  addendum, and checksum-verified development bundle.
- Result: all 5/5 continuation criteria true; next decision
  `PROPOSE_BOUNDED_R3_1`.
- Primary remained positive in only 3/6 independent quarters. The largest continuous
  drawdown was 14.78%; the three losing folds summed to `-$217.89`.
- All three horizons remained positive at double cost, positive folds increased
  2 -> 3 -> 4 with horizon, concentration gates passed, and leave-one-market-out
  positivity remained 1.0.
- The result explicitly sets `creates_candidate=false`, `changes_r3_verdict=false`, and
  `opens_sealed_partition=false`.
- `scripts/run_r3_failure_analysis.py --check`: `PASS`.

### E-026 Frozen R3.1 Path-Quality Study

- Protocol: `data/evidence/r31_path_quality_study_v1.json`.
- Protocol hash:
  `dba4e1282533d5a93825eb1b6bd8b8e854f4146218bd70d5633f9a489b7030b5`.
- Registration: post-R3 outcome, post-failure-analysis decision, and pre-R3.1 outcome.
- Signal: positive OLS slope of log closes multiplied by R-squared; 505 closes span
  504 four-hour intervals; rebalance every 84 bars.
- Selection budget: one primary, one parameter set, no adaptive selection, no rescue
  variants, and no multiplicity correction because only one hypothesis is selectable.
- Gates: positive net P/L, PF >= 1.10, drawdown <= 20%, at least 100 trades, at least
  4/6 positive folds, positive double-cost P/L, at least 80% positive leave-one-market-
  out runs, and the original single/top-five concentration caps.
- The first freeze attempt wrote no authoritative artifact: Decimal literals failed
  JSON reload. Aurex removed that failed file, changed exact Decimal checks to
  coercion-safe validators, added pre-commit JSON round-trip validation, reran 111
  related tests and repository Ruff, then froze successfully.
- `scripts/freeze_r31_mechanism_study.py --check`: `PASS`.

### E-027 Frozen R3.1 Execution And Run Package

- Execution specification:
  `data/evidence/r31_path_quality_execution_spec_v1.json`.
- Execution hash:
  `76a0403f61f7d684761a05765c9d48d3310e56c8433779abb164d14e209773f1`.
- Arithmetic: 50-digit `ROUND_HALF_EVEN` Decimal log-price OLS over 505 closes,
  fixed x-mean 252, fixed Sxx 10,732,260, R-squared clamped to `[0,1]`, and score
  equal to positive slope times R-squared.
- Run package: `data/evidence/r31_path_quality_run_package_v1.json`.
- Package hash:
  `13c1e6cc657b055f3cf957fd6e841e9bdbe8ed59ce6eee89c6f7d9b39c78d722`.
- Transformed market-data hash:
  `ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2`.
- Matrix: 3 full-window cost runs, 6 independent quarterly folds, and 35
  leave-one-market-out runs; 44 total.
- Before package freeze, 36 R3.1 engine/protocol/specification/package/result/runner
  tests passed and repository-wide Ruff passed. The package reload and authoritative
  rebuild both pass.

### E-028 R3.1 Development Result And Mechanical Advancement

- Result ledger: `data/evidence/r31_path_quality_result_v1.json`.
- Ledger hash:
  `452a79da7bc12704a2685cf70f24b8d2d9c895b7123f29d646c89809ea25dd94`.
- Verdict: `PERMIT_R4_PREREGISTRATION`; gates: 9/9.
- Base costs: final equity `$1,488.79`, net `+$488.79`, PF `1.5936`, 10.82%
  maximum drawdown, and 230 completed trades.
- 1.5x costs: `+$455.93`, PF `1.5501`; 2x costs: `+$423.78`, PF `1.5081`.
- Quarterly folds: `+$7.61`, `+$273.25`, `+$16.62`, `-$39.48`, `+$56.70`, and
  `-$129.43`; exactly 4/6 positive.
- Leave-one-market-out: 35/35 positive, with net results ranging from `+$288.32` to
  `+$547.37`.
- Concentration: maximum single-symbol gross-profit fraction 13.00%; top-five
  fraction 44.92%.
- Both the stored-artifact audit and a full deterministic second 44-replay audit pass.
- The ledger fixes `creates_eligible_strategy=false` and
  `opens_validation_partition=false`. Validation, holdout, forward, paper, sandbox,
  and live execution remain closed.

### E-029 Frozen R4 Candidate And Validation Data

- Candidate protocol: `data/evidence/r4_path_quality_candidate_v1.json`.
- Candidate protocol hash:
  `24dd0e81b1aa441ec81e37366a88ee8a4cc65e25818dc6455dc1eb3d7dd4cdd5`.
- Candidate: `path_quality_spot_v1` v1.0.0; signal, portfolio, costs, and gates are
  unchanged from the accepted R3.1 primary.
- Validation bundle: `data/evidence/validation_2025_4h_bundle_v1.json`.
- Validation bundle hash:
  `0cacd38e3fbef83d4603d1df3b287c32102b5e9d6989bf6d26d59ff420cce95e`.
- Coverage: 35 frozen decision markets, 73,886 actual four-hour candles, 406
  checksum-verified Binance Vision archives, 14 recorded HTTP 404 responses, and no
  blocked dataset.
- Availability: 33 full continuous markets; FTM ends at
  `2025-01-13T00:00:00Z`, and MKR ends at `2025-09-15T00:00:00Z`. Only contiguous
  terminal missing suffixes are accepted; no replacement or synthetic candle exists.
- Pre-outcome audits: candidate `PASS`; validation bundle `PASS`.

### E-030 Frozen R4 Execution, Engine, And Run Package

- Execution specification:
  `data/evidence/r4_path_quality_execution_spec_v1.json`.
- Execution hash:
  `825391d45fde09c185186e103c963bf94776ce6de773500def5dcccbdf898cc0`.
- Terminal policy: permanently remove an unheld unavailable market; write a held
  position off to zero at the first missing bar, with no invented exit fee, slippage,
  or candle.
- The R4 engine exactly reproduced the frozen continuous R3.1 result: 230 trades,
  1,400 opportunities, 3,300 equity points, and net
  `+$488.79400413881589814287390`.
- Run package: `data/evidence/r4_path_quality_run_package_v1.json`.
- Package hash:
  `d7c734bd3f786da68c0567a2edfd8020b4ac477878e0f6f4e37fb13217bed240`.
- Transformed market-data hash:
  `49011e05e0abc55b3a0c924ae08926053a784187502bf26aa1eaf42909c4bbe5`.
- Matrix: 3 overall cost runs, 4 calendar-quarter folds, and 35 leave-one-market-out
  runs; 42 total.
- Before freeze, all 43 R4-boundary tests passed, the complete project suite passed
  534 tests with one known Starlette/httpx warning, and repository-wide Ruff passed.
- Candidate, validation data, execution specification, and run-package rebuild checks
  all passed before the one-shot run.

### E-031 R4 Validation Rejection

- Result ledger: `data/evidence/r4_path_quality_result_v1.json`.
- Ledger hash:
  `797ea50d142bbd61f22e87ff9ddf72f30b12c70940d596d027e70660ee26e626`.
- Verdict: `RETIRE_R4_CANDIDATE`; gates: 4/9.
- Base costs: final equity `$926.17`, net `-$73.83`, PF `0.7991`, raw-price PF
  `0.8530`, 14.93% maximum drawdown, and 112 completed trades.
- Double costs: `-$94.18`, PF `0.7505`.
- Quarterly folds: `-$55.31`, `-$47.61`, `+$57.29`, and `-$71.86`; exactly 1/4
  positive.
- Leave-one-market-out: 0/35 positive; positive fraction `0`.
- Concentration gates passed at 19.66% single-symbol and 64.32% top-five gross-profit
  fractions. Trade count and drawdown gates also passed.
- Base-run market termination write-offs: zero. Minimum active breadth at rebalance:
  33. Delisting handling did not cause the rejection.
- Failed gates: base net P/L, base PF, double-cost net P/L, positive quarters, and
  leave-one-market-out positivity.
- Stored-artifact audit and full independent 42-replay deterministic audit: `PASS`.
  The durable full-audit receipt is `.tmp/r4_full_audit.log`.
- The ledger fixes `permits_pine_parity_review=false`,
  `creates_paper_eligibility=false`, and `creates_live_eligibility=false`.

### E-032 R4 Failure Attribution And Family-Stop Decision

- Analysis protocol:
  `data/evidence/r4_failure_analysis_protocol_v1.json`.
- Protocol hash:
  `3b0578e826a1c93929f7a2515a44169ad7a9b7c7887c23774078fc91dc3c714b`.
- Source/run package:
  `data/evidence/r4_failure_analysis_package_v1.json`.
- Package hash:
  `e15fdf4ee9618e1b8d5f1195aebcf3065f0c0f66fa36e788129091fa6b84e2b4`.
- Result:
  `data/evidence/r4_failure_analysis_result_v1.json`.
- Result hash:
  `b46b2181bf7b890f27a1ac43f6b6307bf095230cf4694c7231c5b8166bbaad4b`.
- Scope: stored R4 ledger, all 42 bound result artifacts, and validation-bundle
  metadata only. No 2026 or forward observation was opened.
- Classification: `SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS`.
- Raw price P/L: `-$52.0183`; raw PF: `0.8530`; raw expectancy per trade:
  `-$0.4644`.
- Commission plus slippage: `$21.8157`; exact reconciled net P/L: `-$73.8340`;
  net PF: `0.7991`; net expectancy per trade: `-$0.6592`.
- Exit attribution: 68 fixed-stop exits produced `-$335.78` raw and `-$347.79`
  net; 44 rebalance exits produced `+$283.76` raw and `+$273.96` net.
- Temporal robustness: 1/4 positive quarters, 3/12 positive months, 6/12 negative
  months, and 3/12 flat months.
- Leave-one-market-out: 0/35 positive; omitting no single market restored positive
  full-window net P/L.
- Availability: two expected terminal-market events, zero held-position write-offs,
  and minimum active breadth 33. Availability did not cause the loss.
- All nine integrity checks pass, including exact cost, exit-reason, symbol, metric,
  and artifact reconciliation.
- Deterministic audit: `PASS`.
- Decision:
  `STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY`.
- Verification after implementation: 57 complete R4-focused tests pass and
  repository-wide Ruff passes.

### E-033 Frozen U1 Mechanism-Discovery Charter

- Artifact: `data/evidence/u1_mechanism_discovery_charter_v1.json`.
- Charter hash:
  `642f67fdc55fc041c010e1e7c90732e102a2214bc76c46df15d864c2d269fbcf`.
- Bound evidence: final R4 failure-analysis result, contamination ledger, market
  universe manifest, 2023-2024 development bundle, and 2025 validation bundle.
- Budget: at most three theory proposals, one return-tested mechanism, one selectable
  parameter set, and one selectable candidate.
- Development: 2023-2024. Internal validation: 2025, explicitly not final
  eligibility evidence. Final eligibility holdout: sealed 2026 H1. Forward:
  locked from `2026-07-01`.
- Minimum future gates include positive base and double-cost net P/L, PF at least
  1.15, at least 100 trades, drawdown at most 20%, at least two-thirds positive
  temporal folds, at least 80% positive leave-one-market-out runs, concentration
  limits, and deterministic audit.
- The charter creates no candidate and opens no 2026 or forward data.
- Deterministic rebuild: `PASS`.

### E-034 Frozen U1 No-Return Theory Screen

- Artifact: `data/evidence/u1_mechanism_theory_screen_v1.json`.
- Screen hash:
  `0d32405ea4eea989ee93b74b2f393d5e988cf9eadb63cbde78cc652996eab745`.
- Proposals considered: volatility-managed broad spot beta, signed-jump risk premium,
  and delta-neutral funding carry.
- Selected for primary protocol design:
  `P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA`.
- Signed-jump risk is deferred because current four-hour bars cannot reproduce its
  defining high-frequency statistic.
- Funding carry is deferred because Aurex lacks point-in-time funding, basis,
  collateral, and liquidation data plus qualified derivatives execution.
- Strategy outcomes inspected: none. Return-tested mechanisms: zero. Candidate
  created: false.
- Verification: 60 combined U1/R4 boundary tests pass, repository-wide Ruff passes,
  and deterministic rebuild passes.
- The complete project suite passed 554 tests with one known Starlette/httpx warning
  after the U1 charter implementation and before the theory-screen addition.

### E-035 Frozen U1 Protocol, Execution, Engine, And Run Package

- Primary protocol:
  `data/evidence/u1_primary_mechanism_protocol_v1.json`.
- Protocol hash:
  `3d8b335cfcee93be9e104e7bc029ea09f08e77cd39861afa8743548c245bb229`.
- Execution specification:
  `data/evidence/u1_primary_execution_spec_v1.json`.
- Execution hash:
  `220e9eca631e554833b9c063cdf960fd7b209a70b545324ca40554e2dcf460d0`.
- Run package:
  `data/evidence/u1_primary_run_package_v1.json`.
- Package hash:
  `fd6a1bd0a4faf4b8a65a650e41d69050f7d870d33dfcc29d9ce89d170bcd78b2`.
- Transformed market-data hash:
  `4a41ccae12a88ad81f3f6aa45f6d5feb19947ef5f7f211443c00c1e010c02f00`.
- Frozen matrix: three primary cost runs, one static benchmark, eight independent
  temporal folds, and 35 leave-one-market-out runs; 47 total.
- Before package freeze, the complete project suite passed 591 tests with one known
  Starlette/httpx warning and repository-wide Ruff passed.
- The package rebuilt exactly under `--check` before any U1 return was calculated.

### E-036 U1 Development Rejection

- Result ledger:
  `data/evidence/u1_primary_mechanism_result_v1.json`.
- Ledger hash:
  `06045816415f3fb270ed11bc8e9e3bbeab9382dfc886990e2e4297a5d9217669`.
- Completed replays: 47/47. Stored-artifact audit and independent full deterministic
  replay audit: `PASS`.
- Verdict: `STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA`; 11/13 gates passed.
- Base primary: 875 trades, `+$2,168.47`, PF `1.9311`, raw PF `1.9815`, and
  44.58% maximum drawdown.
- Double-cost net P/L: `+$1,993.50`. Leave-one-market-out: 35/35 positive.
- Temporal robustness: 4/8 profitable folds. The losing folds were 2023 Q2,
  2023 Q3, 2024 Q2, and 2024 Q3.
- Benchmark comparison passed: primary realized equity volatility was 0.5654 versus
  0.7448, maximum drawdown was 44.58% versus 62.11%, and return-to-drawdown was
  2.0023 versus 0.7213.
- Failed gates: maximum drawdown `44.58% <= 20%` and positive temporal folds
  `4/8 >= 6/8`.
- The ledger fixes strategy, validation-data, Pine, paper, and live permissions false.
  2025, the sealed 2026 holdout, and forward data were not opened.

### E-037 Frozen V2 Capability Audit

- Artifact: `data/evidence/v2_capability_audit_v1.json`.
- Audit hash:
  `3726b944529990be7160604942f4e580cd8d198efe79f8e074dc72b760638e42`.
- Decision:
  `BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER`.
- Capability inventory: 1 ready, 11 blocked. Only audited spot OHLCV is ready.
- The audit binds the final U1 stop, U1 theory screen, frozen universe,
  contamination ledger, and current Aurex/My-Krypt-Trader source snapshots.
- Official-source feasibility is recorded for funding history, futures klines,
  mark/index prices, premium index, basis, contract metadata, and related risk
  surfaces. None is locally integrated yet.
- Authorization: data-contract design only. Market-data acquisition, mechanism
  selection, return calculation, candidate creation, validation, holdout, Pine,
  paper, and live progression remain false.
- Verification: four focused tests pass, Ruff passes, and deterministic rebuild
  passes.

### E-038 Frozen V2 Source Census Contract

- Artifact:
  `data/evidence/v2_derivatives_source_census_contract_v1.json`.
- Contract hash:
  `7502a7eb6a54089d90bfc40889390f8c6ac18bbe55d18ef4122421e7fa18e0dc`.
- Scope: 35 frozen symbols, 24 monthly partitions from 2023-01 through 2024-12,
  six archive families, and 5,040 checksum checks.
- Resolution: one minute for spot, contract, mark, index, and premium-index klines;
  exact event archives for funding.
- Decision threshold: at least 20 symbols complete across all six families and all
  24 months.
- Archive payload download, market-data import, mechanism selection, candidate
  creation, and return calculation are false.
- Verification: four contract tests pass, eight combined V2 boundary tests pass,
  repository-wide Ruff passes, and deterministic rebuild passes.

### E-039 Immutable V2 Source Census Result

- Artifact: `data/evidence/v2_derivatives_source_census_result_v1.json`.
- Result hash:
  `ce5d60e3338903bcb8a3783bd4b41fa63bec518c3041b213c9529bd6458d652e`.
- Observations: 5,040/5,040 complete, 4,790 present, 250 missing, zero unresolved.
- Complete symbols: 31/35. Incomplete: CFXUSDT, LUNCUSDT, SHIBUSDT, STXUSDT.
- Spot coverage: 840 present, zero missing. Each of the five USD-M families has
  790 present and 50 missing.
- Decision: `PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL`.
- Archive payload requests and bytes: zero. Numeric market-data values, returns,
  mechanism selection, and strategy outcomes were not inspected.
- Verification: exact matrix, 5,040 unique canonical keys, mechanical threshold,
  result hash, deterministic rebuild, and independent count audit pass.

### E-040 Frozen V2 Pilot-Acquisition Protocol

- Artifact: `data/evidence/v2_derivatives_acquisition_protocol_v1.json`.
- Protocol hash:
  `aa88b2ff6add0637b889da27b784cd1a26b1addc4590832c9c51e973e2aaebc5`.
- Exact scope: 3 symbols x 3 months x 6 families = 54 checksum-pinned archives.
- Pilot symbols: AAVEUSDT, FTMUSDT, XRPUSDT. Pilot months: 2023-01, 2024-01,
  2024-12.
- Resource ceilings: 4 GiB total compressed, 16 GiB total uncompressed, 256 MiB
  per compressed archive, 1 GiB per uncompressed archive, and 100x expansion.
- Authorization: exact pilot payloads and structural schema/timestamp inspection
  only. Full acquisition, market-data import, returns, candidate creation, paper,
  sandbox, and live progression remain false.
- Verification: deterministic rebuild, five focused protocol tests, 23 combined V2
  boundary tests, and repository-wide Ruff pass.

### E-041 Immutable V2 Pilot-Acquisition Result

- Artifact:
  `data/evidence/v2_derivatives_pilot_acquisition_result_v1.json`.
- Result hash:
  `95e9aaaf1b05b01372ddcdc3f19fff6612f6a7f5ae4e1ca4b99b0eb6e7947874`.
- Scope: 54/54 exact targets across three symbols, three months, and six families.
- Size: 53,398,035 compressed bytes; 198,582,854 uncompressed bytes.
- Rows: 2,009,637 total; 401,760 for each kline family and 837 funding events.
- Integrity: census checksum equals refreshed checksum and archive SHA-256 for every
  target; no unresolved request, stale `.part`, resource breach, unsafe ZIP member,
  schema failure, duplicate timestamp, out-of-month row, or non-finite value.
- Schema: headerless spot klines, standard 12-column futures klines, and
  `calc_time,funding_interval_hours,last_funding_rate` funding events.
- Decision:
  `PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL`.
- Full download, market-data import, returns, mechanism selection, candidate,
  paper, sandbox, and live authorization remain false.
- Verification: local file/hash audit, result rebuild, seven focused runner tests,
  30 combined V2 boundary tests, and repository-wide Ruff pass.

### E-042 Frozen V2 Synthetic Derivatives Foundation Protocol

- Artifact: `data/evidence/v2_derivatives_foundation_protocol_v1.json`.
- Protocol hash:
  `b7709efb8555611b9041afc0cb030259c2355c1c82a76c8e22cd6b26a6767c4b`.
- Scope: exact Decimal arithmetic, signed funding, fees, spot/perpetual P&L, paired
  lifecycle, hedge tolerance, collateral, margin, liquidation/ADL, partial fills,
  rollback, kill switch, reconciliation, and 14 exact synthetic scenarios.
- Authorization: synthetic internal mechanics only. Real data, mechanism selection,
  return calculation, candidate, paper, sandbox, and live remain false.

### E-043 Immutable V2 Synthetic Derivatives Foundation Result

- Artifact: `data/evidence/v2_derivatives_foundation_result_v1.json`.
- Result hash:
  `8cf54efc7989b1370db4be80267b47a763637285a1e66d503093f9fe15a49fe8`.
- Outcome: 14/14 scenarios passed and zero failed; event-chain, idempotency, rollback,
  margin, liquidation, ADL, kill-switch, flattening, and final reconciliation
  invariants passed.
- Decision: `PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER`.
- Real market data, returns, exchange qualification, candidate, paper, sandbox, and
  live permissions remain false.

### E-044 Frozen V2 No-Return Discovery Charter

- Artifact: `data/evidence/v2_mechanism_discovery_charter_v1.json`.
- Charter hash:
  `af4dd3e28e20f9a5e99c47e98d567587ef11697c38dd976074ddcb80255db07f`.
- Budget: at most three theory proposals, one selected primary, zero return-tested
  mechanisms, and zero parameter sets.
- Boundary: 31 source-complete symbols support feasibility only; 2023-2024 remains
  closed, 2025 and 2026 remain sealed, and forward evidence remains locked.
- Selection creates no candidate and authorizes no full download, return, Pine,
  paper, sandbox, or live progression.

### E-045 Immutable V2 No-Return Theory Screen

- Artifact: `data/evidence/v2_mechanism_theory_screen_v1.json`.
- Screen hash:
  `ec03d31db661a36b1def820711b20134d416ec2d390a49cdbafaf19f27758dea`.
- Screened premises: positive-funding spot/perpetual carry, premium convergence, and
  negative-funding reverse carry.
- Selected for design only: `P01_POSITIVE_FUNDING_SPOT_PERP_CARRY`.
- Deferred/nonselectable: `P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS`.
- Rejected under V2: `P03_NEGATIVE_FUNDING_REVERSE_CARRY`.
- Outcome inspection: zero market-data numeric fields, parameters, strategy outcomes,
  and return metrics.
- Decision: `FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN`.
- Full acquisition, data import, return testing, candidate, development, validation,
  holdout, forward, paper, sandbox, and live permissions remain false.
- Verification: deterministic rebuild, six focused tamper/boundary tests, and focused
  Ruff pass.

### E-046 Frozen P01 Metadata Source Contract v1

- Artifact: `data/evidence/v2_p01_metadata_source_contract_v1.json`.
- Contract hash:
  `dfe728b5c033d354caeda372ba2a5748369442b1943c81c63337bcd07340ac24`.
- Scope: eight exact historical metadata requirements and four official public
  sources, with at most four GET requests and no credentials or private endpoints.
- Outcome boundary: no response body persistence, market numeric value, return,
  candidate, development, validation, holdout, forward, paper, sandbox, or live
  permission.
- Real runner outcome: the first Binance documentation catalog source returned HTTP
  202 with an empty body and no frozen markers. The runner stopped and correctly wrote
  no v1 audit result.

### E-047 Frozen P01 Metadata Source Contract v1.1

- Artifact: `data/evidence/v2_p01_metadata_source_contract_v1_1.json`.
- Contract hash:
  `0908d86a2ea55d26d86d44607f6e462de4cbcad1baf22fea4824bd15db1b4d13`.
- Supersedes v1 hash:
  `dfe728b5c033d354caeda372ba2a5748369442b1943c81c63337bcd07340ac24`.
- Replaced sources: only the USD-M market and account documentation catalog URLs,
  using official Binance GitHub connector source files.
- Preserved exactly: source IDs, eight requirements, required markers, temporal
  classifications, supported requirements, byte ceilings, policy, limitations, and
  every no-return/no-eligibility permission.
- Verification: deterministic rebuild, source-only supersession audit, four tamper/
  boundary tests, and focused Ruff pass.

### E-048 Immutable P01 Metadata Source Audit v1.1

- Artifact: `data/evidence/v2_p01_metadata_source_audit_v1_1.json`.
- Result hash:
  `87074a1d290b419e3a805aba578f58ee596c66d829f97853aedd44149199e1d7`.
- Observations: 4/4 official sources passed all frozen domain, byte, and marker checks.
  Bodies were hashed and discarded; credentials and private endpoints were not used.
- Direct historical requirements: 2/8, covering settled funding/intervals and the five
  synchronized historical price families.
- Unresolved historical requirements: 6/8. Five permit only conservative, separately
  frozen research overrides; contract lifecycle has no override and must fail closed.
- Decision:
  `PERMIT_P01_PROTOCOL_DESIGN_WITH_MANDATORY_METADATA_OVERRIDES`.
- Full acquisition, import, returns, candidate, development, validation, holdout,
  forward, paper, sandbox, and live permissions remain false.

### E-049 Frozen Integrated P01 Acquisition And Development Protocol

- Artifact: `data/evidence/v2_p01_primary_protocol_v1.json`.
- Protocol hash:
  `c6a66a622b80c33490af6baed6c4bcace0f31bbba57d9e760485825bf0ae6829`.
- Source-target manifest hash:
  `1c65d91ded1e93dd154b4c0832ef0ee3ac8921f5642e4c47300b9f7dcd679916`.
- Exact payload scope: 31 complete symbols x 24 months x six families = 4,464
  checksum-bound archives. The 54 pilot targets may be reused only after complete
  reverification; at most 4,410 additional archives may be downloaded.
- Resource ceilings: 16 GiB total compressed, 64 GiB total uncompressed, 512 MiB per
  compressed archive, 2 GiB per uncompressed archive, 100x expansion, four workers,
  and explicit pre/post free-disk floors.
- Metadata treatment: two current public exchangeInfo snapshots are proxies only;
  fixed adverse fees, execution, margin, liquidation, and ADL treatment retain an
  explicit non-historical and non-eligibility limitation.
- One selectable parameter set: three positive settled funding events, at least 30%
  mean event-normalized annualized funding, nonnegative prior mark/spot premium, and a
  10% exit hurdle.
- Study: 10,000 USDT fixed capital, up to five 1,000 USDT matched pairs, 2x isolated
  derivative leverage, eight quarterly folds, four cost runs, and 31 leave-one-symbol-
  out diagnostics; 35 total.
- Automatic stop gates include positive net P/L, PF >= 1.20, drawdown <= 10%, at least
  100 pairs, 6/8 positive quarters, positive double-cost P/L, funding receipts above
  execution costs, breadth/concentration limits, hedge tolerance, and zero
  liquidation, ADL, unreconciled, or rollback-failure events.
- Permission: exact full acquisition, two public snapshots, normalization, and a
  development return only after an immutable acquisition pass. 2025 validation, 2026
  holdout, forward, Pine, paper, sandbox, live, and capital remain false.
- Verification: deterministic rebuild, four tamper/boundary tests, 63 V2-focused unit
  tests, and focused Ruff pass.

### E-050 Immutable P01 Full Acquisition And Qualification Result

- Artifact: `data/evidence/v2_p01_full_acquisition_result_v1.json`.
- Result hash:
  `0c712f47c69b9b44da5ff2810bb366a7b60b819edc2a2b845b7819cbfd9f1bc5`.
- Runner behavior: 4,464/4,464 refreshed checksums and HEAD checks passed; exact
  compressed payload was 4,239,030,373 bytes. Exactly 4,410 archives were downloaded
  and all 54 pilot archives were reverified and reused.
- Structural evidence: 4,464 verified archives, 163,010,201 rows,
  16,009,662,695 uncompressed CSV bytes, and zero fatal ZIP/schema/numeric/order/month
  violations.
- Continuity: 3,465/3,720 kline archives continuous and 255 discontinuous. Failures
  were concentrated in 2023-01, 2023-02, 2023-03, 2023-04, 2023-11, and 2024-08;
  every symbol had 7-11 failed archives.
- Metadata proxies: 29/31 symbols passed both current spot and USD-M filters; FTMUSDT
  and MKRUSDT failed closed.
- Qualified symbols: 0/31 against a frozen minimum of 20.
- Decision: `STOP_P01_INSUFFICIENT_QUALIFIED_HISTORICAL_DATA`.
- Outcome boundary: signals, trades, P/L, return metrics, candidate, validation,
  Pine, paper, sandbox, live, and capital permissions remain empty or false.
- Verification: authoritative rebuild and full local archive/checksum/snapshot audit
  `PASS`; runner/result focused tests `12 passed`, V2-focused tests `75 passed`, and
  repository-wide Ruff `PASS`.

### E-051 Frozen V3 Independent Mechanism Discovery Charter

- Artifact: `data/evidence/v3_mechanism_discovery_charter_v1.json`.
- Charter hash:
  `10912cefdbd875b202fcc6903e5ffdf82652a97eddde7e9dc073a79308ed9b32`.
- Bound predecessor: P01 acquisition result hash
  `0c712f47c69b9b44da5ff2810bb366a7b60b819edc2a2b845b7819cbfd9f1bc5`
  with zero qualified symbols and no return metrics.
- Budget: at most three theory proposals, one selected primary, zero return-tested
  mechanisms, zero charter-stage parameter sets, and at most one selectable parameter
  set in a separately frozen successor protocol.
- Permitted development inspection: source identity, checksums, schema, timestamps,
  row counts, boundary completeness, duplicate/missing/gap counts, and synchronized
  coverage only.
- Prohibited: price-value inspection, signal/trade/P/L/return calculation, P01/P02
  rescue, unsupported P03 borrow assumptions, retired-family re-expression, or access
  to 2025, 2026 H1, or forward outcomes.
- Permission: proposal/source/execution feasibility screen only. Candidate, Pine,
  paper, sandbox, live, and capital remain false.
- Verification: deterministic freeze/check `PASS`, four tamper/boundary tests, and
  focused Ruff `PASS`.

### E-052 Frozen V3 Independent Mechanism Proposal Register

- Artifact: `data/evidence/v3_mechanism_proposal_register_v1.json`.
- Register hash:
  `1f0bc727d673f6daac6a6d6cad306f6e3007e1f718a67a96f249d586507ff321`.
- Bound charter hash:
  `10912cefdbd875b202fcc6903e5ffdf82652a97eddde7e9dc073a79308ed9b32`.
- Proposals:
  `V3P01_CROSS_ASSET_COINTEGRATION_RELATIVE_VALUE`,
  `V3P02_CLOCK_PHASE_INTRADAY_PREDICTABILITY`, and
  `V3P03_PASSIVE_LIMIT_ORDER_LIQUIDITY_PROVISION`.
- Primary research: three independent sources per proposal, including
  peer-reviewed work and institutional/preprint evidence; no source was selected
  using an Aurex market value or return.
- Coverage and execution contracts: frozen before feasibility observation, including
  exact no-fill and breach actions.
- Decision: `FREEZE_THREE_PROPOSALS_FOR_NO_RETURN_FEASIBILITY_AUDIT`.
- Outcome boundary: selected primaries, parameters, market numeric fields, strategy
  outcomes, returns, candidate, validation, holdout, forward, Pine, paper, sandbox,
  live, and capital remain zero, empty, or false.
- Verification: deterministic freeze/check `PASS`, five focused tests, and focused
  Ruff `PASS`.

### E-053 V3P01 Timestamp And Execution Feasibility

- Timestamp-only coverage artifact:
  `data/evidence/v3_p01_timestamp_coverage_result_v1.json`.
- Coverage hash:
  `fe2641037216596f0aeb25cf8f1b04739eb303ce1a133ef76f0faca0e136fb34`.
- Coverage result: 25/31 symbols passed the frozen synchronized timestamp gate and
  permitted only a separate execution/metadata feasibility protocol.
- Execution/metadata protocol hash:
  `2c0d56b40150dac7fc1d6a6fc4091c99bea2b8a9536ab1c3ec9573d87bf720bb`.
- Terminal result:
  `data/evidence/v3_p01_execution_feasibility_result_v1.json`.
- Terminal result hash:
  `b682aa1149203f14c20ef12732bafb13f617a7f1fc260c5af32d25726d5253a2`.
- Outcome: 4/11 requirements passed and 7/11 failed. Historical contract lifecycle,
  spot/futures filters, account fee tier, leverage/maintenance, collateral/
  liquidation/ADL, and cross-asset hedge/residual-risk foundations were not qualified.
- Decision: `REJECT_V3P01_EXECUTION_AND_METADATA_FEASIBILITY`.
- No market numeric value, parameter, return, primary, candidate, or trading
  permission was created.

### E-054 V3P02 Aggregate-Trade Census And Transport Stop

- Metadata-only census contract hash:
  `956d4019400d499e0bea5b66d39de34afe9dd5687815dce43ae57b15d83949b6`.
- Census result hash:
  `b69fb4d2f1c04df7a12020d47f2a6263442db60980ef65cd73de08062b3a36b2`.
- Census result: 744/744 official Binance Vision checksum URLs present, 31/31
  symbols complete across 2023-2024, and no archive payload requested.
- Frozen payload-pilot protocol hash:
  `2d8d1bdd347fc4e86fbf921995fc0ea39f5cd31adc398df84cdd8ee9595e5e6c`.
- Frozen scope: 744 bounded HEAD observations, a deterministic ten-symbol cohort,
  and exactly three checksum-pinned sample requests. Parsing is limited to aggregate
  trade ID and timestamp columns.
- Verified retained AAVEUSDT 2023-01 sample: 42,506,543 bytes, 3,114,414 rows,
  44,629/44,640 occupied minutes, maximum two-minute event gap, zero aggregate-trade
  ID gaps, and `PASS`.
- Verified retained BNBUSDT 2023-12 sample: 113,981,300 bytes, 8,065,287 rows,
  44,640/44,640 occupied minutes, maximum one-minute event gap, zero aggregate-trade
  ID gaps, and `PASS`.
- DOGEUSDT 2024-12 request: response ended before the HEAD-declared byte count. The
  transactional partial file was removed; its immutable request marker remains.
- No authoritative three-sample pilot result exists and no retry is authorized.
- Stop artifact:
  `data/evidence/v3_p02_payload_pilot_stop_result_v1.json`.
- Stop hash:
  `67c967764111f831d80fb2e52d965460e0d59958b285e35e28715569dcb971f8`.
- Decision: `STOP_V3P02_TRANSPORT_UNRESOLVED_NO_RETRY_NO_SELECTION`.
- Price, quantity, maker side, strategy outcome, and return fields were not parsed.

### E-055 V3P03 Historical Microstructure Source Stop

- Source-audit contract hash:
  `f52a3169b60d404033a7a41c24ef8df556d614e8975002035744153134040f7e`.
- Transport-only amendment hash:
  `e94f7576ce132fd3389311d467af605ce9e0ec438e61b151ab08e844b386c6ec`.
- Formal stop artifact:
  `data/evidence/v3_p03_source_audit_stop_result_v1.json`.
- Stop hash:
  `733556d1d95f30b1c5b012df66299cecb87234a3fe01577b2441b9504b6fb31d`.
- Two preserved attempts made seven total requests. The exact official schema source
  returned HTTP 202 until the frozen poll budget was exhausted.
- Zero of eight historical microstructure requirements were claimed evaluated or
  qualified; unresolved source IDs and both failed attempt manifests are preserved.
- Decision:
  `REJECT_V3P03_REQUIRED_HISTORICAL_MICROSTRUCTURE_EVIDENCE_UNAVAILABLE`.
- This is a source-feasibility rejection for V3, not proof that passive liquidity
  provision is universally unprofitable.

### E-056 Terminal V3 Feasibility Screen

- Artifact: `data/evidence/v3_mechanism_feasibility_screen_v1.json`.
- Screen hash:
  `48e60151a4e4f6c86f5efa2569a4c6e63747bc1ee0996bf749d51a66f16f604e`.
- Bound terminal evidence: V3P01
  `b682aa1149203f14c20ef12732bafb13f617a7f1fc260c5af32d25726d5253a2`,
  V3P02
  `67c967764111f831d80fb2e52d965460e0d59958b285e35e28715569dcb971f8`,
  and V3P03
  `733556d1d95f30b1c5b012df66299cecb87234a3fe01577b2441b9504b6fb31d`.
- Dispositions: V3P01 rejected execution/metadata feasibility; V3P02 stopped with
  unresolved transport; V3P03 rejected unavailable historical evidence.
- Selected primary count: `0`.
- Decision: `SELECT_ZERO_V3_PRIMARY_MECHANISMS`.
- Next decision:
  `CLOSE_V3_AND_REQUIRE_SEPARATELY_FROZEN_V4_DISCOVERY_CHARTER`.
- V3 retry/amendment, full payload acquisition, market-data import, return testing,
  candidate, development, validation, holdout, forward, Pine, paper, sandbox, live,
  and capital permissions are all false.

### E-057 Frozen V4 Crash-Safe Mechanism Discovery Charter

- Artifact: `data/evidence/v4_mechanism_discovery_charter_v1.json`.
- Charter hash:
  `2230f042c676f97988129bf752aff889c83404627ff782c5462bd984e13cbd81`.
- Bound terminal V3 screen:
  `48e60151a4e4f6c86f5efa2569a4c6e63747bc1ee0996bf749d51a66f16f604e`
  with decision `SELECT_ZERO_V3_PRIMARY_MECHANISMS`.
- Budget: at most three independent theories, one selected primary, zero
  return-tested mechanisms, zero charter-stage parameter sets, and one selectable
  parameter set only in a later separately frozen successor.
- Transport boundary: durable request intent before every attempt, append-only
  response evidence, cumulative restart-safe budgets, incremental observations,
  partial-byte preservation, predeclared resume semantics, metadata census before
  payload, and immutable complete/reject/transport-stop result schemas.
- Prohibited: V3 retry or rebrand, retired-family re-expression, market numeric
  values, outcomes, return-based selection, sealed partitions, Pine, paper, sandbox,
  live, credentials, private endpoints, orders, and capital.
- Verification: deterministic freeze/check `PASS`, seven charter tests, and focused
  Ruff `PASS`.

### E-058 Frozen V4 Independent Mechanism Proposal Register

- Artifact: `data/evidence/v4_mechanism_proposal_register_v1.json`.
- Register hash:
  `a4fb8e0739cdd07f8a9a810cf395aa5fed3216000cb8b37c01f232eb5ec8973a`.
- Bound V4 charter:
  `2230f042c676f97988129bf752aff889c83404627ff782c5462bd984e13cbd81`.
- Registered proposals:
  `V4P01_INVENTORY_BACKED_SAME_ASSET_CROSS_VENUE_ARBITRAGE` and
  `V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM`.
- Proposal budget: two of three consumed; one deliberately unused.
- Sources: each proposal binds peer-reviewed mechanism evidence, official exchange
  data/execution documentation, and independent historical-data documentation across
  at least three source hosts. Current mutable documentation is explicitly not
  historical execution proof.
- Screened out without returns: triangular arbitrage and put-call parity as related
  execution families, stablecoin mint/redemption for noncredible access assumptions,
  and directional liquidation reaction for retired-lineage overlap.
- Decision:
  `FREEZE_TWO_PROPOSALS_LEAVE_ONE_SLOT_UNUSED_FOR_NO_RETURN_FEASIBILITY`.
- Outcome boundary: selected primary, parameters, network requests, payloads, market
  numeric values, strategy outcomes, returns, candidate, validation, holdout,
  forward, Pine, paper, sandbox, live, and capital remain zero, empty, or false.
- Verification: deterministic freeze/check `PASS`; combined V4 charter/register
  suite `15 passed`; complete project suite `755 passed`; repository-wide Ruff
  `PASS`.

### E-059 Frozen V4P01 Cross-Venue Feasibility Contract

- Artifact: `data/evidence/v4_p01_feasibility_contract_v1.json`.
- Contract hash:
  `684a9f4de4aececab26113c46f98511037fefdcf811ab4abfbe3766a3ad0a69e`.
- Bound V4 charter:
  `2230f042c676f97988129bf752aff889c83404627ff782c5462bd984e13cbd81`.
- Bound V4 proposal register:
  `a4fb8e0739cdd07f8a9a810cf395aa5fed3216000cb8b37c01f232eb5ec8973a`.
- Exact product: Binance Spot `ethbtc` and Coinbase Exchange `ETH-BTC`, with ETH
  base and BTC quote.
- Network scope: exactly eight public Tardis GET requests, comprising two metadata
  requests and six one-minute raw schema pilots. Payload phase is conditional on a
  passing durable metadata result.
- Pilot times: `2023-01-01T00:00:00Z`, `2023-12-01T12:00:00Z`, and
  `2024-12-01T23:59:00Z` on both venues.
- Transport: eight attempts total, zero retries, one concurrent request, no
  range/resume, 117,440,512 response-byte ceiling, 268,435,456 storage-byte ceiling,
  1,200-second wall-clock ceiling, append-only fsynced request/response journal,
  incremental observation persistence, and partial-byte hashing.
- Execution/source gates: 14 hard requirements with no conservative override,
  including point-in-time fees/filters/state, account/jurisdiction access,
  pre-funded inventory, IOC/FOK behavior, two-leg failure state, reconciliation,
  capacity, staleness, source integrity, and disconnect recovery.
- Parsing boundary: raw bytes may be hashed and schema-audited; bid, ask, quantity,
  spread, trade-price, fee-value, signal, trade, P/L, and return fields may not be
  parsed or calculated.
- Decision:
  `AUTHORIZE_BOUNDED_PUBLIC_METADATA_AND_SCHEMA_PILOT_NO_MARKET_VALUES`.
- Original execution: both metadata requests completed, 74,788 response bytes were
  persisted, no request failed, and no retry occurred.
- Original metadata terminal:
  `data/evidence/v4_p01_feasibility_reject_result_v1.json`.
- Original terminal hash:
  `198d69b4358d7c980357201a7dbb2b209ccf4c8f2186009a9cc8a4c3cf7b8df2`.
- Original metadata-gate hash:
  `14d4fd139d03db5ce2ffa1fb9678f229392058388ee331ad9863e6bae6356605`.
- Interpretation status: preserved runner defect. Both exact products and enclosing
  source boundaries passed, but optional symbol `availableTo` values were absent and
  incorrectly treated as failed coverage.

### E-060 V4P01 No-Repeat Continuation And Terminal Rejection

- Continuation contract:
  `data/evidence/v4_p01_feasibility_continuation_contract_v1.json`.
- Continuation contract hash:
  `cfaa2e2b507813c81469938ab71b67c98502a8d3348e7e03256041f5e3b79f54`.
- Correction class:
  `RUNNER_INTERPRETATION_DEFECT_NOT_MARKET_OR_STRATEGY_EVIDENCE`.
- Bound official semantics: Tardis documents instrument `availableTo` as optional
  and populated when collection stops; the continuation inherits both metadata
  observations, repeats zero metadata requests, and authorizes only original request
  sequences 3-8.
- Continuation execution: all six payload requests completed, 152,078 response bytes
  were persisted, no request failed, no retry occurred, and all observations remained
  market-value opaque.
- Continuation terminal:
  `data/evidence/v4_p01_feasibility_continuation_reject_v1.json`.
- Continuation terminal hash:
  `b3941f445cca6ce4c1533fa94fdb598dd6bf6f541a69c95e76dcd51c6e0a1348`.
- Passing foundations: exact common product after identity reconciliation, exchange
  and local timestamp identity, and bounded transport/resource/storage feasibility.
- Decisive failures: `RAW_BBO_OR_L2_SCHEMA_WITH_QUANTITIES`,
  `SOURCE_REVISION_AND_BYTE_INTEGRITY`,
  `POINT_IN_TIME_FEES_AND_FEE_CURRENCY`, and
  `POINT_IN_TIME_FILTERS_PRODUCT_AND_VENUE_STATE`.
- Decision: `REJECT_V4P01_BEFORE_PRIMARY_SELECTION`.
- Outcome boundary: no price, quantity, spread, signal, trade, P/L, or return was
  inspected or calculated; no primary, parameter, candidate, validation, paper,
  sandbox, live, or capital permission exists.

### E-061 V4P01 Terminal Explanation Addendum

- Artifact: `data/evidence/v4_p01_terminal_audit_addendum_v1.json`.
- Addendum hash:
  `f88e502c7838e6b31f42f09d336e4dc7a4d5d53757f5f466ccf30ba2dc54743a`.
- Corrected defect 1: Tardis's Binance filter identity is lowercase `ethbtc`; all
  identity-only raw audits expose Binance wire symbol `ETHBTC`. Case-normalized
  product reconciliation passes.
- Corrected defect 2: the continuation common-product gate had status `PASS` but an
  overstated reason claiming every payload already matched.
- Invariant failures: four of six samples still lack a recovery snapshot, all six
  lack upstream revision identity, and point-in-time fees plus venue/filter state
  remain unproven.
- Invariant decision: `REJECT_V4P01_BEFORE_PRIMARY_SELECTION`.
- Authorization boundary: network, retry, new sample, market-value inspection,
  return calculation, candidate creation, paper, sandbox, live, and capital are all
  false.

### E-062 V4P01 Runner Verification

- Original runner synthetic coverage: ordered metadata-first execution, durable
  hash chain, hard response/storage/time budgets, partial-byte evidence, zero retry,
  process-death reconciliation, restart reconstruction, value opacity, and tamper
  refusal.
- Continuation synthetic coverage: request sequences 3-8 only, zero metadata repeat,
  inherited reject binding, separate journal/terminal paths, zero retry, value
  opacity, and terminal tamper refusal.
- Focused V4P01 contract/runner/correction suite: `31 passed` before payload access.
- Pre-continuation complete project suite: `786 passed` with one known
  Starlette/httpx deprecation warning.
- Repository-wide Ruff: `PASS`.
- Post-addendum focused V4P01 suite: `36 passed`.
- Post-addendum complete project suite: `791 passed` with the same one known
  Starlette/httpx deprecation warning.

### E-063 Frozen V4P02 Deribit Source-Census Contract

- Artifact: `data/evidence/v4_p02_feasibility_contract_v1.json`.
- Contract hash:
  `a3c4bf0aeda588c63b02dee8f75c06efd22aa59c967bee104531f604432faf17`.
- Bound V4 charter:
  `2230f042c676f97988129bf752aff889c83404627ff782c5462bd984e13cbd81`.
- Bound V4 proposal register:
  `a4fb8e0739cdd07f8a9a810cf395aa5fed3216000cb8b37c01f232eb5ec8973a`.
- Mechanism:
  `V4P02_DELTA_HEDGED_CRYPTO_VARIANCE_RISK_PREMIUM`.
- Exact source products: Deribit grouped `OPTIONS` options-chain, quotes, trades,
  `book_snapshot_25`, and liquidations; plus `BTC-PERPETUAL` quotes, trades,
  `book_snapshot_25`, and derivative ticker.
- Frozen dates: `2023-01-01`, `2023-12-01`, and `2024-12-01`.
- Network scope: one public `api.tardis.dev/v1/exchanges/deribit` metadata GET and
  27 exact `datasets.tardis.dev` HEAD requests. No dataset GET, raw replay, Deribit
  API request, credential, retry, range, or resume is permitted.
- Redirect policy: metadata redirects zero; each dataset HEAD permits at most three
  manually validated public-HTTPS hops. Private, loopback, link-local, credentialed,
  and scheme-downgraded targets are prohibited. Maximum logical requests are 28 and
  maximum HTTP hops are 109.
- Budgets: one-at-a-time execution, 8,388,608 response-body bytes total,
  33,554,432 local evidence bytes, 2 TiB projected full-dataset storage ceiling, and
  1,260 seconds active protocol time.
- Hard gates: 17 source/execution requirements with no conservative override,
  including full calendar/incidents, lifecycle, BBO/quantity, hedge state,
  disconnect/sequence/revision, historical fees/settlement/margin/liquidation,
  derivatives access, non-atomic multi-leg recovery, collateral reconciliation,
  capacity, tail loss, and kill switches.
- Decision:
  `AUTHORIZE_ONE_METADATA_GET_AND_TWENTY_SEVEN_DATASET_HEAD_REQUESTS`.
- Outcome boundary at freeze: no request had run; dataset payload, raw replay, option
  or hedge numeric values, parameters, returns, primary selection, candidate,
  validation, paper, sandbox, live, and capital were zero, empty, or false.
- Verification at freeze: deterministic freeze/check `PASS`; focused contract suite
  `10 passed`; complete project suite `801 passed` with one known Starlette/httpx
  warning; repository-wide Ruff `PASS`.

### E-064 V4P02 Crash-Safe Census Runner

- Typed evidence model:
  `src/aurex/backtest_engine/research_v4_p02_feasibility_runner.py`.
- Runner:
  `scripts/run_v4_p02_feasibility.py`.
- Runner source hash:
  `f2b4b5969f881694a7a9e1e6b32af56a51e721d64bd61e014f4f027634820c7c`.
- Synthetic coverage: exact frozen order; metadata-first gate; 27 zero-body HEADs;
  one-to-three safe redirects; HTTP, credential, loopback, link-local, shared,
  and private target refusal; fourth-redirect stop; HEAD-body refusal; missing,
  zero, and invalid `Content-Length`; 2 TiB projection; body/time/hop budgets;
  process-death closure; restart reconstruction; stale raw state; duplicate and
  tampered journals; derived-observation reconstruction; value opacity; exact
  permission boundary; and non-network CLI dry-run.
- Focused V4P02 contract and runner suite before execution: `35 passed`.
- Complete project suite before execution: `826 passed` with one known
  Starlette/httpx deprecation warning.
- Repository-wide Ruff before execution: `PASS`.
- Pre-execution contract check and dry-run: `PASS`.

### E-065 V4P02 Immutable Transport Stop

- Terminal artifact:
  `data/evidence/v4_p02_source_census_transport_stop_v1.json`.
- Terminal result hash:
  `d917c43f814e0b1ca27fff6ad7b5a5d57409e694d2c0efc2886a00508f12cd07`.
- Terminal file SHA-256:
  `540ce3916cbeb58891e58b5cbcd7ed24eb6017535794236da6a45096f8f3dc84`.
- Request journal hash:
  `d847f5a1d9cd9832f1527aaba2dec7074a6accbff1d0a7dc5d0d275b3c2b8985`.
- Exact attempt: `V4P02_META_DERIBIT_EXCHANGE_DETAILS`, attempt `1`.
- Outcome: `TRANSPORT_STOP / STOP_V4P02_TRANSPORT_NO_RETRY`.
- Failure: `ValueError: V4P02 metadata body budget exceeded`.
- Server-declared body: `203,310,405` bytes.
- Frozen metadata-body maximum: `8,388,608` bytes.
- Accepted response-body bytes: `0`.
- Attempts/hops/retries: `1 / 1 / 0`.
- Dataset HEAD attempts: `0 / 27`.
- Terminal audit/check: `PASS`.
- Boundary: no metadata body, dataset HEAD, dataset payload, market numeric value,
  parameter, return, primary, candidate, paper, sandbox, live, or capital permission.

### E-066 Terminal V4 Zero-Selection Screen

- Artifact: `data/evidence/v4_mechanism_feasibility_screen_v1.json`.
- Screen hash:
  `605d3b177b85ceaaf3ae5d9824d8eb2fc680ba355988d26d1a7769a19c897494`.
- Builder hash:
  `9ab1dee9ae3fa78431a906994539204616f986d34d4095b1ad637935959a172a`.
- Decision: `SELECT_ZERO_V4_PRIMARY_MECHANISMS`.
- Dispositions: V4P01
  `REJECTED_SOURCE_AND_EXECUTION_FEASIBILITY`; V4P02
  `STOPPED_METADATA_TRANSPORT_BUDGET`.
- V4 is closed; retry, request resizing, payload, parameter, return, candidate,
  development, validation, paper, sandbox, live, and capital remain false.
- Frozen-lineage and tamper suite: `7 passed`.

### E-067 Post-V4 Capability-Gap Review

- Artifact: `data/evidence/post_v4_capability_gap_review_v1.json`.
- Review hash:
  `01fbf52bdc75f03dac21a26c4fdd642c6671d408464ac52da5ff3b3ac3bbabc6`.
- Builder hash:
  `9ceff1b8a719134558fa0348b94b04a3143cbd316f1feb8f29231520b80ff165`.
- Decision:
  `DO_NOT_START_SUCCESSOR_ALPHA_DISCOVERY_UNTIL_ACCESS_PROFILE_IS_FROZEN`.
- Proven capability: evidence-grade bar replay.
- Implemented but externally unproven: authenticated webhook delivery and forward
  paper/risk operation.
- Absent or incomplete: positive net edge, execution-grade tick/L2, point-in-time
  venue rules, Pine parity, deterministic production adapter, qualified sandbox.
- Required operator decisions: intended venue, permitted product scope, account/API
  access, starting capital, maximum loss, and data-acquisition budget.
- Allowed next tracks only: freeze those operator facts; rejected v1.3 parity under
  explicit TradingView authority; one genuine webhook delivery to paper-safe
  rejection.
- Frozen review and V4 closure suite: `13 passed`; consolidated V4 runner/contract/
  closure/review suite: `48 passed`.

### E-068 Credential-Free Operator Profile Contract

- Typed contract:
  `src/aurex/backtest_engine/research_operator_access_profile.py`.
- CLI: `scripts/freeze_post_v4_operator_profile.py`.
- Builder hash:
  `ab83ca6ee5995a569174b4ce568c7dfcf934948bd1cc7731937b16aa2df92390`.
- This is the original CLI-only builder hash. It remains historical evidence and is
  prospectively superseded by the shared workflow builder in E-071; no frozen
  profile existed to rewrite.
- Workflow: `--template` prints a non-secret input skeleton; `--preflight --input`
  evaluates without writing; `--freeze --input` writes only when every gate passes;
  `--check --output` reconstructs from embedded operator input and frozen post-V4
  lineage.
- Hard gates: verified account/documented API access; unborrowed non-emergency
  capital; explicit free/paid data budget; ordered loss limits capped at `0.5%`
  per trade, `1%` daily, and `10%` total; no credentials; exact attestation;
  explicit product scope with maximum `1x` effective leverage; documented sandbox
  path; and named venue/jurisdiction with legal/tax acknowledgement.
- Credential refusal includes common API-key, bearer-token, password, secret-key,
  and private-key patterns in reference fields.
- A passing profile decision is
  `AUTHORIZE_SUCCESSOR_CHARTER_DESIGN_ONLY`; network, market import, discovery
  execution, parameter, return, candidate, paper, sandbox qualification, live, and
  capital permissions remain false.
- Focused adversarial suite: `22 passed`.
- Complete project suite: `861 passed` with one known Starlette/httpx deprecation
  warning; repository-wide Ruff `PASS`.
- Real profile artifact:
  `data/evidence/post_v4_operator_access_profile_v1.json` does not exist. No operator
  value, attestation, account access, capital amount, loss limit, or data budget has
  been inferred or frozen.

### E-069 TradingView External-Delivery Proof Hardening

- Source-network policy:
  `src/aurex/signal_gateway/tradingview_delivery.py`.
- Source-network policy SHA-256:
  `a60e90504532e2b410ecc894bd36fe8379f7a9ba0b27008141606e8ff266c92b`.
- Frozen proof builder:
  `src/aurex/signal_gateway/tradingview_external_proof.py`.
- Proof-builder SHA-256:
  `95b05b34811ecd2ac927d9090cbd6259ade42632fe37194f6fc690c67c688d5c`.
- CLI: `scripts/freeze_tradingview_external_delivery_proof.py`.
- CLI SHA-256:
  `74e37fd21fb4d845b883b229206a32e5caa0f2c291b1668408acb27e464a92ac`.
- TradingView's official webhook page was rechecked on `2026-07-29`: the documented
  senders remain `52.89.214.238`, `34.212.75.30`, `54.218.53.128`, and
  `52.32.178.7`; webhook ports remain 80/443; requests are cancelled after three
  seconds; IPv6 is not supported; delivery status is exposed in the alert log.
- Every new receipt binds canonical configured networks, policy status, deterministic
  network hash, and the official authority URL inside its tamper-detected delivery
  snapshot. A matching peer inside a broad or undocumented network is diagnostic
  only and cannot set `delivery_verified=true`.
- Read-only verification now exposes exact signal identity/time, receipt body/time
  fields, live-disabled state, live order intents, broker orders, and broker fills.
- The external-proof package reads current verification from the configured database,
  reconciles the operator's exact signal ID and a hashed sanitized alert-log artifact,
  applies ten gates, refuses overwrite, and independently reconstructs against the
  database and artifact.
- A pass grants only
  `ACCEPT_EXTERNAL_DELIVERY_PROOF_SAFE_REJECTION`; pipeline, strategy promotion,
  paper, sandbox, live, and capital permissions remain false.
- Focused source-policy, proof, signal-verification, and webhook suite:
  `37 passed`.
- Complete project suite: `876 passed` with one known Starlette/httpx deprecation
  warning; repository-wide Ruff `PASS`.
- Real proof artifact:
  `data/evidence/tradingview_external_delivery_proof_v1.json` does not exist. No
genuine alert, TradingView alert-log artifact, or Stage 3 external proof has been
inferred or frozen.

### E-070 TradingView Two-Dataset Parity v1.1 Preparation

- Engine: `src/aurex/backtest_engine/parity.py`.
- Engine SHA-256:
  `a6c662123971b226e8af26ebce72f41a72b8adbbf8209c0a50cb57d436cc2353`.
- Request/response contract: `src/aurex/backtest_engine/schemas.py`.
- Contract SHA-256:
  `a41ff88f1f84d88bb049f72f687d5eeed2bb496b23f995f5841836a79cf3689e`.
- Engine/schema versions: `tradingview-trade-parity-v1.1.0` /
  `aurex-backtest-parity-v2`.
- Frontend controller SHA-256:
  `5263e30c62ac5c2831502f575b571a4e87008b7bb70cf22f4ce3765e3727b1b7`.
- Frontend document SHA-256:
  `cd5c12a13395badbe5a5c8780e1060de76e3a1443c1a307fb9931920562438b1`.
- The parity request now binds a checksum-verified `binance-vision` reference
  dataset, a separate `tradingview-chart-export` dataset, and a
  `tradingview-export` Strategy Tester report. Canonical source references are
  `tradingview://chart/BINANCE:BTCUSDT/15m` and
  `tradingview://strategy-tester/BINANCE:BTCUSDT/15m`.
- Exact timestamp and Decimal open/high/low/close/volume reconciliation precedes
  every trade comparison. Missing or invalid chart evidence blocks without a
  record; valid candle disagreement records immutable `FAILED` evidence with every
  mismatch.
- The Backtests UI exposes the two datasets and report separately, renders market
  reconciliation before trade reconciliation, and leaves all evidence sources
  unselected until deliberate operator choice. Browser verification at 1440 pixels
  confirmed clean layout and a disabled comparison action with incomplete inputs.
- Focused parity file: `9 passed`; combined parity/dashboard suite: `11 passed`.
- Complete project suite: `880 passed` with one known Starlette/httpx deprecation
  warning; repository-wide Ruff `PASS`; frontend JavaScript syntax `PASS`.
- External evidence remains absent. No TradingView workspace mutation, chart export,
  Strategy Tester export, real parity record, eligibility change, paper order,
  live action, or capital use occurred.

### E-071 No-Write Operator Profile Intake And Handoff

- Shared workflow:
  `src/aurex/backtest_engine/operator_profile_workflow.py`.
- Workflow SHA-256:
  `81a470877cd746925f078ce192505964e9287899e24dee3123dd1572e12ba224`.
- Typed input/profile contract SHA-256:
  `ad75827c690473b9e1808b716376cd77726cafcb880f6407a0f0450bf745eb39`.
- No-write API route SHA-256:
  `edbad1da6c0ea809b17a63ec844801fdbe2b04663007aa99b41e1ffc21bf172e`.
- Independent freezer CLI SHA-256:
  `7db40db18b01436772661293eeefa0848a7f5372c764e48af70e41eae0bf5dab`.
- Shared builder-contract hash:
  `7f66c6aefda90daa81e1180c4827d75f50b2810b57694cf50454d77df72cc749`.
- Frontend controller/document/style SHA-256:
  `ef0f8cfcbf33e6a72c68556660364ea6a8e10d2481c22931532ff9ca25f52579`,
  `6ca59f22c353d9910aad3633181c2fb7ee7f2754ab7c7412cf6a7b713ab7071f`,
  and `687edd0a14d24bb1fae9c090ae583b92ee8b9a77fbcbbafc801ef53f91ab6664`.
- Operator runbook:
  `docs/17_OPERATOR_PROFILE_INTAKE.md`; SHA-256
  `cab3767952e1dbaf343a2c686ceeea43eb3554a21f0578d4e8d8b1816603cc38`.
- `GET /operator-profile/status` returns absent, verified, or invalid artifact state
  without operator input. `GET /operator-profile/template` returns gates and frozen
  ceilings. `POST /operator-profile/preflight` accepts at most 64 KiB, performs no
  write, sanitizes errors, and returns hashes, ratios, gates, and false permissions.
  There is no HTTP freeze endpoint.
- The dedicated Operator tab defaults to blank/unverified facts, groups access,
  product, capital/loss, data-budget, and attestation inputs, renders all nine gates,
  and enables validated-input download/CLI handoff only after `9/9`. Any edit clears
  that pass. Notifications were moved to the lower-right to avoid action overlap.
- Desktop runtime verification proved a synthetic `8/9` loss-limit block at `0.6%`
  per trade and a synthetic `9/9` charter-design-only pass at `0.5%`; both wrote
  nothing. Mobile verification at 390 pixels had one-column summary/forms and zero
  horizontal overflow. All values were synthetic software fixtures, not operator
  facts.
- Focused operator contract/API/dashboard suite: `35 passed`.
- Complete project suite: `891 passed` with one known Starlette/httpx deprecation
  warning; repository-wide Ruff `PASS`; frontend JavaScript syntax `PASS`; CLI
  template `PASS`.
- Real artifact remains absent:
  `data/evidence/post_v4_operator_access_profile_v1.json`. No real venue, account/API
  access, capital, loss limit, product scope, data budget, attestation, successor
  charter authority, paper/live permission, or capital use was inferred or frozen.

### E-072 Protocol-Bound Paired-Export Parity v1.2

- Parity engine SHA-256:
  `d7340d718404bf43d5deffefb687d4ec9e7b746c5dcaf7e6f2d515f0f5272446`.
- Schema contract SHA-256:
  `903048d623de83081c468e2966dd496fdec6ba5287bb1442e9326d8e2220d520`.
- Backtest service SHA-256:
  `e2401f9aba67392eadd0a2c24b208a666476e6baff1e181762419fabbee768a1`.
- Backtest API route SHA-256:
  `5a4030204869cc1e7aea8b8eba876f6741976deb6a3b4935e0f69a5297100f4f`.
- Engine/schema/lineage versions:
  `tradingview-trade-parity-v1.2.0`, `aurex-backtest-parity-v3`, and
  `aurex-tradingview-paired-export-v1`.
- Frontend controller/document SHA-256:
  `1828750be7a29bb1b025c7e44524e6eac7e749df9b1e1cc00a8942b3a8026e40`
  and `beb88cf1d9117be38c39a5b7f582aa787d99c45691d3d3cc52c8b0ba2571e9e3`.
- Parity/backtest/dashboard test SHA-256:
  `6647227100cbe623b4a525a0ced0501d049826e47f9b422813af6f11de49feb6`,
  `7fde19e4526929b3265a3276a9e836e027ee1c1df75a0c047df4c5c5ec3c8132`,
  and `fd41f30769f2f2b1270ed77c7c1ebb7364c25df75fec1d5e4fc5658502d62350`.
- Updated parity/runbook SHA-256:
  `232d79560836ef14819773d22a981633618acb718c16c884881ee3b741c3716d`
  and `a2fa6450cdb33d9641df492e6a7c98a0e45b90e2e6bfa0e5d6c01893eee38c2e`.
- The corrected registered v1.3 protocol remains READY. Its stable v2 manifest hash
  is `ed328491d093995d772d2bef95fc61177579676f8e785b7e57485f6ffbdfc227`
  and package hash is
  `b1bdf4e6181e6a5ea8f4a2547f41775d2d210aea7393fee80c5db3929ced25e6`.
  Protocol hash, Pine SHA-256, 19,277 source bytes, 297 lines, settings, costs, dates,
  ticker, timeframe, and source reference are unchanged; only hash scope was corrected.
- `POST /backtests/parity/export-manifest/preflight` performs no write and binds the
  intact consumed protocol, stable frozen hashes, verified reference data, chart
  evidence/canonical CSV, report trade evidence/original CSV bytes, complete coverage,
  source identities, and exact operator attestation. Parity requires the returned
  reviewed hash and independently rebuilds it.
- Negative contracts prove missing protocol lineage, missing reviewed hash, and stale
  reviewed hash block parity. Determinism tests prove identical no-write requests
  retain one evidence hash; consumption tests prove frozen configuration hashes remain
  stable before and after the report consumes its protocol. A dedicated real-data
  shape test proves audited warm-up candles may precede the report window while the
  report remains strictly contained inside exact chart/reference coverage.
- The UI exposes attestation, lineage preparation, status, and hash. Evidence-selection
  changes invalidate lineage and comparison; comparison cannot run without a READY
  manifest. Static dashboard contracts and frontend JavaScript syntax pass.
- Focused parity/backtest/dashboard suite: `53 passed`. Complete project suite:
  `895 passed` with one known Starlette/httpx deprecation warning. Repository-wide
  Ruff, frontend JavaScript syntax, and `git diff --check` pass; Git emitted only
  existing LF-to-CRLF working-copy warnings.
- Local visual runtime verification is completed and recorded separately in E-073.
- No TradingView workspace mutation, chart/report export, real paired-export
  attestation, parity record, strategy eligibility change, paper action, live action,
  or capital use occurred.

### E-073 Responsive Paired-Lineage Runtime Verification

- Local Aurex health returned HTTP `200`, service `Aurex`, environment `local`, and
  `live_trading_enabled=false` on `127.0.0.1:8918`.
- An isolated Chromium runtime loaded `/dashboard#backtests` with HTTP `200` and
  exactly one paired-lineage control set. Desktop verification at 1440 px showed the
  parity status, source selectors, attestation, lineage button, tolerances, and
  comparison table without overlap.
- Mobile verification at 390 px measured document `scrollWidth=390` and
  `innerWidth=390`. The 362-pixel navigation strip automatically moved to
  `scrollLeft=457`; the active Backtests control occupied `129.875` through
  `230.71875` px and was fully visible.
- With no authentic source selections or attestation, Prepare lineage, Compare
  trades, and Record evidence were all disabled. The legacy reference replay summary
  rendered `187/56 base / n/a HTF`, not `undefined`.
- Frontend controller SHA-256:
  `1e3a91c7e798857285c31632c85f8a5f7e9697fd441fb0c9548f08572704faa5`.
  Dashboard document SHA-256:
  `6e87cba46651863761d039433fc94a8df38bf8149b962651088665fbe84ab27d`.
  Dashboard integration-test SHA-256:
  `96fdf8df7b0a2cf3aabb92e31f26ba1463d4f10393ad66c88209d5faf1875f94`.
- The controller asset revision is `/dashboard/assets/app.js?v=20260729-1`, preventing
  an existing browser cache from retaining the pre-fix controller.
- Complete project verification against the final controller: `895 passed`.
  The cache-revision-only document/test update then passed the focused dashboard
  suite: `2 passed`. Repository-wide Ruff and frontend JavaScript syntax pass. The
  only warning is the known Starlette/httpx deprecation.
- Local diagnostic captures:
  `.tmp/aurex_parity_desktop_clip.png`,
  `.tmp/aurex_mobile_nav_top_verified.png`, and
  `.tmp/aurex_parity_mobile_verified.png`.
- No TradingView mutation, market-data request, real export, real attestation, parity
  record, strategy decision, paper order, live action, credential use, or capital use
  occurred.

### E-074 Fail-Closed Async Action Lifecycle

- The prior generic wrapper unconditionally wrote `button.disabled=false` in cleanup.
  The replacement uses one `WeakSet` in-flight lock, performs no native disabled-state
  assignment, removes only its loading/busy state, and suppresses pointer activation
  while pending.
- Isolated Chromium loaded `/dashboard#backtests` with HTTP `200` and controller asset
  `/dashboard/assets/app.js?v=20260729-2`.
- Runtime behavior proved all three contracts: a renderer-disabled control remained
  disabled after cleanup; an ordinary control remained enabled and shed its loading
  state; and two concurrent invocations executed the action exactly once.
- With no authentic exports or lineage, Prepare lineage, Compare trades, and Record
  evidence all remained disabled after the wrapper audit. Health reported
  `live_trading_enabled=false`.
- Frontend controller SHA-256:
  `5f2535c842d46d3ba06a87be7d6a9bbe650bb264f0f35bd4255dcf5d5b1bd35a`.
  Stylesheet SHA-256:
  `a019b62449dd892ba34541cb03ef6e3cc2f798e3c8b83e3504b2fcc250506f00`.
  Dashboard document SHA-256:
  `bfb0266fb97f89e05adb229d64336398ca4d16e07adfa4024daa79fedcac5447`.
  Dashboard integration-test SHA-256:
  `2cd3d7f3c5eeba697d96854b068fe9018f4a15e11822c8db97bcc30b59f57f58`.
- Focused dashboard contracts: `2 passed`. Repository-wide Ruff and frontend
  JavaScript syntax pass. The complete `895`-test result in E-073 remains the latest
  project-wide baseline; this frontend-only lifecycle change was additionally
  verified by the direct runtime behavior above.
- No TradingView mutation, market-data request, operator fact, export, attestation,
  parity record, strategy decision, paper order, exchange action, live action,
  credential use, or capital use occurred.

### E-075 External Evidence Boundary Audit

- Read-only source: `data/aurex.db` opened with SQLite `mode=ro`.
- Backtest dataset sources: exactly eight `binance-vision`; TradingView chart export
  datasets: `0`.
- Frozen-v1.3 imported reports: `0`. Reports with non-null protocol ID, protocol
  evidence hash, and source artifact hash: `0`.
- Immutable parity runs: `0`. Signals: `0`. Signal events: `0`.
- Four historical `backtest_runs` exist, but they are pre-v1.3 imports. None is a
  v1.3 report or satisfies the current protocol/artifact/paired-export contract.
- Required real profile artifact:
  `data/evidence/post_v4_operator_access_profile_v1.json` absent.
- Required external-delivery artifact:
  `data/evidence/tradingview_external_delivery_proof_v1.json` absent.
- Current settings resolve `live_trading_enabled=false`.
- No explicit TradingView mutation authority or real operator facts were supplied in
  this continuation. No write, request, import, signal, parity operation, market-data
  access, TradingView mutation, or capital use occurred during the audit.
- This is the third consecutive continuation checkpoint with the same external-input
  dependency. All permitted synthetic preparation is complete and the ledger forbids
  substituting more of it. The goal is therefore genuinely blocked pending one exact
  operator action identified in D-078.

### E-076 Resumed Read-Only TradingView Identity

- Observation time: `2026-07-30T06:58:17+02:00`.
- Read-only `chart_get_state`: success; symbol `BINANCE:BTCUSDT`; resolution `30`;
  chart type `1`.
- Visible studies: exactly one, entity `Tz9slL`, named
  `Aurex jam_reversal_v1`.
- Read-only Strategy Tester result: success response, `metric_count=0`, empty metrics,
  and `No strategy found on chart. Add a strategy indicator first.`
- Corroborating read-only chart capture:
  `C:\Users\ashumba\tradingview-mcp-jackson\screenshots\aurex_readonly_identity_20260730.png`;
  67,555 bytes; SHA-256
  `10b0d53d95ebf8e0a620d36528bef81d4efeb4ea9b1abfb33561acdaa301a2fe`.
- The capture visibly identifies Bitcoin/TetherUS, `30`, Binance, and the
  `Aurex jam_reversal_v1` study. It contains no evidence of the frozen v1.3 strategy.
- No chart, timeframe, source, input, study, panel, alert, replay, or workspace state
  was changed. No market-data payload was requested.
- This current identity does not satisfy frozen-v1.3 parity and does not authorize a
  chart mutation, export, webhook, strategy decision, paper action, sandbox, live
  action, or capital use.

### E-077 Current Jam Source-Binding Discrepancy

- A second read-only `chart_get_state` in the resumed run returned the same
  `BINANCE:BTCUSDT` `30m` state and study entity `Tz9slL`.
- Read-only `pine_get_source` returned `success=false` and
  `Could not open Pine Editor or Monaco not found in React fiber tree.` No panel was
  opened and no fallback UI action was attempted.
- Local source: `pine/strategies/jam_reversal_v1.pine`; version comment `1.14.0`;
  declaration `strategy(` at line 3.
- Local SHA-256:
  `f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3`,
  exactly matching historical E-007.
- Local raw-file measurement: 702 physical lines and 48,667 characters, exactly
  matching historical E-007.
- TradingView currently reports a same-named study but no strategy metrics. Because
  current chart source was not observed, current chart/local source equality is
  `UNPROVEN`.
- No TradingView state, Pine source, panel, chart, study, timeframe, alert, or replay
  was changed. No jam evaluation or strategy permission was created.

### E-078 Fresh Resumed-Run Boundary Re-Audit

- Audit time: `2026-07-30T07:10:02+02:00`.
- Read-only SQLite `data/aurex.db` counts:
  frozen-v1.3 reports `0`; fully protocol-bound reports `0`; TradingView chart
  datasets `0`; parity runs `0`; signals `0`; signal events `0`.
- `data/evidence/post_v4_operator_access_profile_v1.json`: absent.
- `data/evidence/tradingview_external_delivery_proof_v1.json`: absent.
- Current settings: `live_trading_enabled=false`.
- Resumed turn one preserved current read-only chart identity. Resumed turn two
  preserved local jam type/hash and current loaded-source uncertainty. Neither
  created an export, signal, profile, source binding, parity verdict, or authority.
- No explicit operator facts, Pine Editor authority, frozen-v1.3 paired-export
  authority, or bounded webhook authority were supplied.
- This is the third consecutive turn of the fresh resumed blocked audit. No permitted
  authority-free action remains that advances the requested evidence rather than
  manufacturing a substitute.

### E-079 Real Operator Draft And No-Write Preflight

- Operator-supplied facts: Zimbabwe jurisdiction; intended Binance venue; account
  exists but identity is not yet verified; API Management is visible but gated by
  verification; Spot Testnet is accessible; spot-only `BTCUSDT`; `1x`; `$100`
  unborrowed non-emergency capital; and `$0` initial data budget.
- Derived protective loss limits: `$0.50` maximum per trade, `$1.00` maximum daily,
  and `$10.00` maximum total.
- Temporary non-secret draft:
  `.tmp/aurex_operator_profile_draft_20260730.json`.
- Draft SHA-256:
  `2e02beee4daa67ef40cb14cef0689308cd8ab54748312b77a358ca650cb0a92d`.
- No-write CLI preflight decision: `BLOCK_SUCCESSOR_DISCOVERY`; charter design
  `false`; profile hash
  `a2b95051c2ebe72f600b41e556e827a6ca8cb3c193a7dd943fd5a1ec7c540794`.
- Passed gates: 7 of 9. Failed gates:
  `ACCOUNT_AND_API_ACCESS_PROVEN` and `VENUE_AND_JURISDICTION_BOUND`.
- Canonical artifact
  `data/evidence/post_v4_operator_access_profile_v1.json` remains absent. No freeze,
  strategy, return, paper, sandbox-qualification, live, or capital authority was
  created.

### E-080 Binance Spot Testnet Boundary And Signed Validation

- Canonical Testnet capability artifact:
  `data/evidence/binance_spot_testnet_sandbox_profile_v1.json`.
- Independent check: `PASS`; 9 of 9 gates; decision
  `AUTHORIZE_SANDBOX_ADAPTER_IMPLEMENTATION_AND_SUCCESSOR_CHARTER_DESIGN_ONLY`.
- Profile evidence hash:
  `adc95174c169f2f1b76ac2d53770ee13b5049850f1bcabb2cbc7d4a461e55b69`.
- Implemented Testnet-only client:
  `src/aurex/broker_engine/binance_spot_testnet.py`.
- Safety boundaries: hard-coded official Testnet origin; `/api` routes only;
  `BTCUSDT` only; Spot limit orders only; local price, quantity, and notional filter
  checks; USD 10 maximum virtual notional; deterministic client IDs; signed request
  sanitation; process-only credentials; virtual order entry off by default.
- Real public connectivity evidence:
  `data/evidence/binance_spot_testnet_public_connectivity_latest.json`.
- Public evidence SHA-256:
  `a1eee63117dc62a53b9bb285635228aa3fa159156a83efe2f0cd541e537acfbf`.
- Observed result at `2026-07-31T05:13:46.169425+00:00`: ping pass, server offset
  -79 ms, `BTCUSDT` `TRADING`, exchange filters parsed, ticker received,
  authenticated account read `PASS`, account type `SPOT`, `can_trade=true`, `SPOT`
  permission present, and signed `order/test` `PASS`.
- The validated BUY had notional `5.1524320000000000` Testnet USDT and explicitly
  did not enter the matching engine. Virtual order: not submitted. Sandbox
  qualification: false. Production/live/capital: false.
- Focused verification: 22 tests passed; Python lint, JavaScript syntax, and
  PowerShell syntax passed. The complete project suite passes 924 tests.

### E-081 First Virtual Cancel Lifecycle And Fail-Closed Identity Defect

- Real evidence:
  `data/evidence/binance_spot_testnet_public_connectivity_latest.json`.
- Evidence SHA-256:
  `d6ea8e9a0609ce50b48df0a9cfb5193a4ccf3796b1bcede5b8898f004ada126a`.
- Checked at: `2026-07-31T05:40:06.641883+00:00`.
- External Testnet order: `22276358`; BTCUSDT BUY limit; Testnet notional
  `5.1461824000000000`; original quantity `0.00016000`.
- Lifecycle: placed `NEW`, queried `NEW`, cancel response `CANCELED`, final query
  `CANCELED`, executed quantity zero, quantity match true, lifecycle `PASS`.
- Reconciliation: `FAIL`; order identity match false; sandbox qualification false.
- Root cause: Binance cancel responses use `origClientOrderId` for the order being
  cancelled and `clientOrderId` for the cancel identity, which may be generated.
  Aurex's first parser retained only `clientOrderId` and incorrectly compared it with
  the placement ID.
- Correction: preserve both IDs, submit a deterministic cancellation client ID,
  reconcile external order continuity, pre-cancel placement identity, and post-cancel
  cancellation identity independently. Network-uncertain placement still queries by
  deterministic placement ID without resubmission; post-placement errors still
  attempt cancellation.
- Corrected focused verification: 21 tests passed; repository-wide Ruff passed.
  The corrected real campaign has not run.

### E-082 Percentage-Price Rejection And Corrected Public Preflight

- The authenticated retry stopped at Binance `POST /api/v3/order/test` with
  `Filter failure: PERCENT_PRICE_BY_SIDE`.
- The rejection happened before actual order submission; it created no new
  matching-engine order.
- Root cause: the candidate price was exactly 50% of the last ticker, while Binance
  applies the lower BUY multiplier to a moving 5-minute average.
- Correction: Aurex now parses both-side percentage multipliers and filter window,
  obtains the matching average and current best bid, keeps the candidate away from
  the lower boundary, and requires it to remain below the bid.
- Credential-free public preflight:
  `data/evidence/binance_spot_testnet_percent_preflight_20260731T055914Z.json`.
- Preflight SHA-256:
  `88b761bc00c058be37aca6fe38bebce5973b6114e0d026f8204cb3edcc5da8b1`.
- Observed average: `64340.09350472`; best bid: `64363.06000000`;
  candidate price: `57926.75000000`; quantity: `0.00009000`; notional:
  `5.2134075000000000`; below best bid: true; submitted: false.
- Focused verification: 22 tests passed, including the moving-boundary regression;
  repository-wide Ruff and `git diff --check` pass. The current complete-suite rerun
  reached 62% without a failure before the 10-minute harness timeout, so it is not
  recorded as a complete pass. Sandbox qualification remains false.

### E-083 Post-Cancel Lookup-Key Defect

- The latest authenticated retry passed signed test-order validation, placement,
  pre-cancel query, and cancellation, then failed at the final query with
  `Order does not exist`.
- The traceback proves `cancel_order` returned before the bad final query ran. The
  bounded Testnet order was therefore cancelled; the failure was in post-cancel
  reconciliation lookup.
- Root cause: Aurex sent the deterministic cancellation-operation ID as
  `origClientOrderId`. Binance documents that cancel `newClientOrderId` identifies
  the cancel, while order queries accept the immutable numeric `orderId` and/or the
  order's original client ID.
- Correction: `query_order` now supports explicit external `orderId`; the final
  lifecycle query uses the exact ID returned by cancellation. Reconciliation still
  requires stable external ID, original placement lineage, deterministic
  cancellation lineage, exact quantity, zero fill, and final `CANCELED`.
- Regression verification: the final request is asserted to contain `orderId=42`
  and no `origClientOrderId`. Lifecycle checkpoints are atomically persisted after
  placement, query, cancellation, and final query. A failure after successful
  cancellation no longer attempts a redundant second cancel and now records a
  structured failed evidence artifact instead of losing state behind a traceback.
  All 23 focused Testnet/evidence/API/dashboard tests pass; repository-wide Ruff
  passes.
- No completed evidence artifact was written by the failed run. Sandbox
  qualification remains false.

### E-084 Preserved Virtual-Cancel Reconciliation

- Untouched complete source:
  `data/evidence/binance_spot_testnet_virtual_cancel_20260731T065201Z.json`.
- Source SHA-256:
  `d4a4f6a6be8ab72b2ad4424ee7fcd283dc0f69c66ad381a213077643d57123a6`.
- Checked at: `2026-07-31T06:52:01.244550+00:00`; external order `22292295`.
- Public connectivity, authenticated account read, and signed test order: `PASS`.
- Lifecycle: placed `NEW`, queried `NEW`, cancel response `CANCELED`, final query
  `CANCELED`; exact quantity `0.00009000`; executed quantity zero.
- Actual Testnet identity behavior: placed, queried, and final client IDs equal
  `aurex-cancel-bbaee2eb49a33a88`; the cancel response client ID equals
  `aurex-cancel-op-eb86fdd03f0ffb9d`, with its original client ID pointing to the
  placement ID.
- Offline reconciliation addendum:
  `data/evidence/binance_spot_testnet_virtual_cancel_reconciliation_20260731T065201Z.json`.
- Addendum SHA-256:
  `8ba2a284ddea8f8c32b7cc420fbe0d80da861e5263d52a28e0114ee799a41e06`.
- Addendum decision: `VIRTUAL_CANCEL_RECONCILED`; every identity, status, quantity,
  and zero-fill predicate is true.
- The source's stale declared `order_reconciliation=FAIL` is preserved rather than
  rewritten. API/UI status derives the corrected result from exact recorded
  checkpoints. No network request or new order was made for reconciliation.
- Verification: 25 focused tests and repository-wide Ruff pass.
- This closes the virtual-cancel gate only. `sandbox_qualified=false`,
  production/live authority false, real capital untouched.

### E-088 Jam Reversal Spot Historical Decision

- Candidate: `jam_reversal_spot_v1` v1.0.1, long-only BTCUSDT 15m.
- Pine SHA-256:
  `7aa2aaa04e17ccbad70adba9279b4e5eb3057393b5e74f0a7db4cc5dd39d7270`.
- Authoritative protocol:
  `f788795a-ac75-4763-93c2-75a031ee2c70`.
- Protocol SHA-256:
  `219d6d069e678f23d3dc49588bc21a5eda9c21970ef83f5fdcb7610d1083bbda`.
- Dataset: `9724b9c7-03fa-4cba-9d5f-1e3bd69aa322`; evidence hash
  `2a048a6709d0f066977d317ec2d013d362cc68a5f626d85201e98d9c6925440e`.
- Replay: `82e5ff23-a4de-423b-b8df-6394d09566a1`; record hash
  `e744038580b0d413c15ba25b7a8936faa6fc3f08d67f7ffbd01f29ffe77db257`.
- Validation: `6ad2fef6-ffd3-4773-9f02-52e80596bdd4`; evidence hash
  `02e2f67a72569a177cfea56ac2ec3dd3265a7cc460359188fa7611d25da64762`.
- Artifact:
  `data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json`; evidence
  hash `d8b108df43a82b3bb5db0cdffd3ec94992e9baf43fede05bbd01dd518a03c5fd`.
- Result: 14 trades, 5 wins, 9 losses, `-$0.5371`, PF `0.8301`, expectancy
  `-$0.0384`, max drawdown `$2.2222`; OOS 4 trades, `-$0.2929`, PF `0.6771`;
  0/6 folds.
- Cost boundary: zero-cost `+$1.2642`, half-cost `+$0.3635`, base fees
  `$1.8008`; the fixed path does not survive the frozen base costs.
- Replay audit and validation audit: `PASS`.
- Decision: `REJECT_CURRENT_VERSION`; paper/production authority false.

### E-089 Jam Reversal Spot Failure Analysis And Ledger Lineage

- The historical v1 contamination ledger remains immutable at six records:
  `data/evidence/strategy_contamination_ledger_v1.json`, hash
  `9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`.
- The Jam result is recorded in the append-only seven-record v2 ledger:
  `data/evidence/strategy_contamination_ledger_v2.json`, hash
  `f24cc36011e9f9ddc40e277197bd3fa03310cac12b6848b30714aae26cdb37bd`.
- This preserves every historical charter and universe binding to v1 while giving
  Jam v1.0.1 a separately auditable contamination record.
- Failure-analysis artifact:
  `data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json`, hash
  `7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`.
- Boundary:
  `STORED_DECISION_EVIDENCE_ONLY_NO_NEW_RETURN_INSPECTION`.
- Classification:
  `INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE`.
- Decision:
  `STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN`.
- Parameter retuning, new-candidate, paper, Testnet strategy-order, production, and
  live authority all remain false.
- Closeout verification: `982 passed` in `769.45` seconds; repository-wide Ruff
  `PASS`. The only warnings are the known pytest `cache_dir` configuration warning
  and Starlette/httpx deprecation.

### E-090 Jam Successor Hypothesis Charter

- Frozen at: `2026-08-01T05:28:38.171106Z`.
- Artifact:
  `data/evidence/jam_successor_hypothesis_charter_v1.json`.
- Evidence hash:
  `426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`.
- Boundary:
  `NO_NEW_MARKET_DATA_NO_NEW_RETURNS_NO_PARAMETER_DEFINITION`.
- Selected for future capability review only:
  `J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM`.
- Economic claim: a temporary aggressive sell-flow shock may partially reverse only
  after signed sell pressure decays and price reclaims a pre-shock reference.
- Rejected: candle-parameter rescue and passive-maker retest. The first is
  outcome-conditioned tuning; the second requires historical queue and fill evidence
  that the zero-dollar source cannot identify.
- Deferred: lower-activity cross-asset reversal, because current operator authority
  is BTCUSDT only.
- Exact Pine signal compatibility is false. If a later protocol qualifies, the
  Aurex backend must be the signal authority; Pine may only visualize.
- Provisional 2019-2022 aggregate-trade/kline history remains unopened and
  unverified. August 1, 2026 onward remains locked forward evidence.
- The charter creates no strategy version and authorizes no market-data import,
  parameter, return, candidate, paper, Testnet strategy order, production, or live
  action.
- Next required authorization:
  `AUTHORIZE_METADATA_ONLY_BINANCE_ARCHIVE_CENSUS`.
- Final checkpoint verification: `989 passed` in `645.14` seconds; repository-wide
  Ruff and charter rebuild checks `PASS`. The only warnings are the known pytest
  `cache_dir` configuration warning and Starlette/httpx deprecation.

### E-091 Jam Archive Quality Remediation

- Frozen protocol:
  `data/evidence/jam_archive_quality_remediation_protocol_v1.json`; evidence hash
  `128eb77a416ba9ebd47154639fe383f1f9b9c0058c149c8f7dc62c4e5e24c57a`.
- Result:
  `data/evidence/jam_archive_quality_remediation_result_v1.json`; evidence hash
  `02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`.
- Independent audit:
  `data/evidence/jam_archive_quality_remediation_audit_v1.json`; evidence hash
  `146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`.
- Duplicate-member finding: both 2021-12 uncompressed members have SHA-256
  `4a2d823de4b60232442c92cc44d109dc31da89ca988d5111c9f07209c462fa54`.
- Reconstructed defects: 4,009 missing kline minutes in 21 intervals, eight invalid
  rows, and 144 cross-family mismatch minutes.
- Quarantine: 4,161 unique minutes; manifest hash
  `618df63c38ca848e7d34188d20e99f3eac330f76cec5226bb6046d33354c9d27`.
- Source policy: aggregate trades primary; official one-minute klines secondary QA
  only; no synthesis; state reset plus full future-feature lookback after defects.
- Frozen evidence roles: 2019-2020 development, 2021 sealed validation, 2022 sealed
  holdout. The consumed 2023-2025 Jam period remains excluded.
- Decision:
  `PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION`.
- Next required authorization:
  `AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`.
- Features, parameters, thresholds, returns, strategies, signals, orders, paper,
  production, live authority, real capital, and profit all remained absent.

### E-092 Jam Successor Feature Specification

- Protocol:
  `data/evidence/jam_successor_feature_specification_protocol_v1.json`; evidence
  hash `86ee3e67c6fc78863378b4a1b30c8cb38f9aafda2335e92054309cd260bfffba`.
- Specification:
  `data/evidence/jam_successor_feature_specification_v1.json`; evidence hash
  `8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`.
- Independent audit:
  `data/evidence/jam_successor_feature_specification_audit_v1.json`; evidence hash
  `760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`.
- Causal phases: baseline lags 132-13, pre-shock 12-8, shock 7-3, confirmation
  2-0; 133 required valid minutes.
- Output: 17 Decimal features at 18 places with half-even rounding.
- Quality boundary: partition reset, source quarantine, no-aggregate minute,
  post-defect warm-up, degenerate-scale, and degenerate-denominator states all
  withhold the complete vector.
- Conformance: nine deterministic synthetic cases; manifest hash
  `cae28c8f9acdc3884747281d78003f128a33907aca89d73fed6217d5974122bc`.
- Real market rows, thresholds, future labels, returns, strategies, signals, and
  orders: zero.
- Decision:
  `PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION`.
- Next required authorization:
  `AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS`.

### E-093 Jam Successor Development Feature Distribution

- Protocol:
  `data/evidence/jam_successor_development_distribution_protocol_v1.json`;
  evidence hash
  `8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551`.
- Frozen source matrix: 24 BTCUSDT aggregate-trade archives from January 2019
  through December 2020; target manifest hash
  `2b997184d44db7992c6955e4c520b0a2c949197a3496177b1fc0cb06658441b2`.
- Feature rows:
  `data/evidence/jam_successor_development_feature_rows_v1.parquet`; 1,052,640
  calendar rows, 129,887,758 bytes, file SHA-256
  `fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`,
  schema hash
  `15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b`.
- Source accounting: 400,020,102 aggregate rows, 1,049,526 observed minute
  primitives, and 3,063 frozen development quarantine minutes.
- Quality accounting: 1,046,202 `READY`, 132 partition warm-up, 3,063 source
  quarantine, 3,147 post-defect warm-up, 96 no-aggregate minutes, and zero
  degenerate-scale or denominator rows.
- Overall ready rate:
  `0.9938839489284085727314181487`; minimum monthly ready rate:
  `0.9806227598566308243727598566`.
- Structural decision: all 7/7 frozen gates pass. Every ready row has all 17 finite
  features; minimum feature uniqueness is 192,787 and every IQR is positive.
- Result:
  `data/evidence/jam_successor_development_distribution_result_v1.json`; evidence
  hash `d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef`.
- Independent audit:
  `data/evidence/jam_successor_development_distribution_audit_v1.json`; evidence
  hash `7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`.
  It reproduced the feature Parquet, schema, serialized result, and result hash
  exactly.
- 2021 validation and 2022 holdout remained sealed. Future labels, event
  thresholds, returns, strategies, signals, candidates, orders, paper authority,
  production/live authority, real capital, and profit all remained absent.
- Decision:
  `PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION`.
- Next required authorization:
  `AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS`.

### E-094 Jam Successor Event And Outcome Protocol

- Protocol:
  `data/evidence/jam_successor_event_outcome_protocol_v1.json`; evidence hash
  `33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db`.
- Parent lineage: accepted distribution protocol/result/audit, byte-bound
  1,052,640-row feature artifact, and frozen 17-feature specification.
- Primary event: one long-only conjunction requiring shock sell-flow robust z at
  least development q95, shock sell share at least q50, shock price impact at or
  below q25, confirmation flow-decay ratio at or below q50, and reclaim at least
  q50.
- Selection space: one event, one direction, one selectable 30-minute horizon.
  Fifteen- and 60-minute horizons and path excursions are non-selectable
  diagnostics that cannot rescue the primary.
- Overlap: chronological first-event acceptance with at least 60 minutes between
  accepted events; suppressed raw events remain auditable but create no outcome.
- Prevalence boundary: seven conjunctive gates require at least 1,000 raw events,
  at least 240 accepted events, broad month/quarter coverage, bounded month/day
  concentration, and zero non-ready accepted events.
- Economic boundary: first aggregate-trade price at `t+1`, last aggregate-trade
  price at the horizon, base commission 0.10% per side plus two adverse ticks,
  stress commission 0.15% per side plus ten adverse ticks, and no synthetic path.
- Controls: one-to-one outcome-blind matching by month, UTC hour, and baseline
  sell-quote-median quartile, with 24-hour event exclusion and deterministic nearest
  timestamp selection.
- Inference: one-sided 95% calendar-month cluster bootstrap, 10,000 repetitions,
  fixed seed `20260805`; all development gates are conjunctive and unwaivable.
- Evidence order: development must pass before separate authorization can open
  2021 validation; validation must pass unchanged before separate authorization can
  open 2022 holdout.
- Independent audit:
  `data/evidence/jam_successor_event_outcome_protocol_audit_v1.json`; evidence hash
  `b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4`.
- Event flags, accepted events, labels, returns, strategies, signals, candidates,
  orders, paper authority, production/live authority, real capital, and profit:
  zero or false.
- Decision:
  `PASS_EVENT_AND_OUTCOME_PROTOCOL_AWAIT_DEVELOPMENT_EVENT_PREVALENCE_AUTHORIZATION`.
- Next required authorization:
  `AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES`.

### E-095 Jam Successor Development Event Prevalence

- Protocol:
  `data/evidence/jam_successor_development_event_prevalence_protocol_v1.json`;
  evidence hash
  `e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd`.
- Protocol-file SHA-256:
  `336c6e516f4def171cc4fd29a5f82ecfde5971f7883593fd3064a4eee7871119`.
- Builder-contract hash:
  `44937ddbc794abff611c2389b69c4f77065c3b7a0475fb3a36812360607fca50`.
- Scope: frozen 2019-2020 development causal feature rows only; no aggregate-trade
  payload, future price, label, return, control outcome, validation, or holdout
  access.
- Raw-event ledger:
  `data/evidence/jam_successor_development_event_ledger_v1.jsonl`; 1,430 records;
  SHA-256
  `b6fe0c49bbbb8b61ac268b4716d2a50ab5fa08479ccbf254ef532b15a3b7d909`.
- Suppression result: 991 accepted events and 439 suppressed events under the exact
  chronological 60-minute rule with no month/year reset.
- Calendar breadth: all 24 months have at least five accepted events; the minimum
  quarter has 70.
- Concentration: August 2019 is largest at 82/991, or
  `0.08274470232088799192734611504`; November 22, 2020 is largest day at 6/991,
  or `0.006054490413723511604439959637`.
- Gates: all 7/7 pass; accepted non-`READY` event count is zero.
- Result:
  `data/evidence/jam_successor_development_event_prevalence_result_v1.json`;
  evidence hash
  `444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea`.
- Result-file SHA-256:
  `1bd0d659f7f582899ed7a61928e77bd92383dc8d22e3d5b79f9e178dde1a41d4`.
- Runner-contract hash:
  `d03c402e8247b9f385151f36ffc3fd19390016a52116a4014edd1fcafc3d4387`.
- Independent audit:
  `data/evidence/jam_successor_development_event_prevalence_audit_v1.json`;
  evidence hash
  `414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d`.
- Future price rows, labels, returns, controls, backtests, strategies, signals,
  candidates, orders, paper authority, production/live authority, real capital,
  and profit: zero or false.
- Decision:
  `PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION`.
- This is sample-availability evidence only and is not predictive or economic
  evidence.
- Historical next required authorization:
  `AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION`.

### E-096 Jam Successor Development Outcome

- Execution protocol:
  `data/evidence/jam_successor_development_outcome_execution_protocol_v1.json`;
  evidence hash
  `e7ed92d708c80a87b36c7d24d903cd7be1c1f594def74daab22618ed9bc6e07d`.
- Protocol-file SHA-256:
  `7528082404d66fc19a999ec2afda3a438138826a24b9e480d88ecd8cc5a347b3`.
- Builder-contract hash:
  `6e45696c99efb89bde12f27971058695a7de4456dbf42c2c685c74e0cf2a833a`.
- Scope: only frozen 2019-2020 aggregate-trade outcomes, cost cases, matched
  controls, inference, and eleven development gates. No 2021 validation, 2022
  holdout, threshold change, diagnostic rescue, strategy, or trading authority.
- Source extraction: 24/24 monthly identities passed; 86,820 requested path
  minutes, 86,820 recovered, zero missing.
- Matched-control ledger:
  `data/evidence/jam_successor_development_matched_control_ledger_v1.jsonl`;
  991 records, 456 matched, 535 unmatched; SHA-256
  `c23ea774b26fa50bd4bc37dfc3273efe28d56d4a4ccd545243bbca08d0ab6e34`.
- Outcome ledger:
  `data/evidence/jam_successor_development_outcome_ledger_v1.jsonl`;
  4,341 records; SHA-256
  `0d322ac7c88f990bc7f714c47f4d4192cb4f81ca8f930e154aa7669336de53d8`.
- Primary result: 991 qualified event outcomes and 456 matched pairs. Base net
  mean `-16.008098281388651150` bps, profit factor
  `0.464374516027724364`, stress mean `-26.189788269683100509` bps,
  matched excess `2.984977884653180892` bps, base bootstrap lower bound
  `-19.768677643106546730` bps, and matched bootstrap lower bound
  `-3.041289366472522414` bps.
- Stability: zero of two years and zero of eight quarters had positive base net
  mean. Largest monthly absolute-return contribution was 2019-07 at
  `0.090391072504531228`, which passed its concentration gate.
- Gates: 3/11 passed. Sample size, matched-pair count, and month concentration
  passed; all economic and temporal stability gates failed.
- Result:
  `data/evidence/jam_successor_development_outcome_result_v1.json`; evidence hash
  `560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430`;
  file SHA-256
  `82639d4af205f089c71192856228873c13e94f8f03587560291e90583b359962`.
- Runner-contract hash:
  `c7f50b5e8920dee6c8da22caf2d72b9f36af5d07054a004c54f9ed89116d7791`.
- Independent audit:
  `data/evidence/jam_successor_development_outcome_audit_v1.json`; evidence hash
  `8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`;
  file SHA-256
  `5f658a59ac7f46be964f5c46307faef3b1503b3a37b1487346fa07ef49f3ea4f`.
- The audit regenerated all 24 source extracts, controls, outcome records,
  metrics, bootstrap values, and the complete decision byte-for-byte.
- Decision:
  `STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.
- Next required authorization:
  `NONE_DEVELOPMENT_OUTCOME_FAILED`.
- The event is retired. Validation and holdout remain sealed; candidate, signal,
  strategy, paper, Testnet strategy-order, production/live authority, real
  capital, and profit remain zero or false.

### E-097 Q1 USD-M Raw-Trades Structural Payload Pilot

- Protocol file SHA-256:
  `004f16d7f90d53ae3bdab382c817405665870e62e3fe462a1e844808df4a791d`.
- Protocol evidence hash:
  `79e7ec935f31dba86a0173398133ec4abd0acc3f2a559bc5dda0dd3f3fa77451`.
- Pre-network audit evidence hash:
  `26ec1c8fd400228443beeda4130b17a019428fa8ef22b67c937e122c2b97bbe3`.
- Canonical marker-bound result v2 file SHA-256:
  `294fd609bd9f8c0bd1449d8759b218b4cb8828cec590e8781840120634a756af`.
- Canonical result evidence hash:
  `4d0c4ef5b1f56bc498d2625fe1acd5a33faffe679425c82c5e2c83b6fc572477`.
- Independent audit evidence hash:
  `3e627038aa89748165874e32cd62bd8da202670b37613c3221944cda6e350fd0`.
- One request marker is bound by manifest hash
  `a215fed5b7e4be0f368641bb0f4d5fa3049c0b073ddf550db0a19c476d62a2ac`.
- The 128,838,558-byte raw archive matched published SHA-256
  `5d3b5ab977aa3c10e40928ce8e2fcf33bc0406235bbb7413a95f067189aa8939`.
- Structural result: 10,281,248 rows; 44,640/44,640 raw minutes;
  44,640/44,640 paired Spot/raw minutes; zero duplicate or non-increasing IDs;
  zero timestamp regressions; 726 forward gaps; 1,809 skipped IDs; maximum single
  omission 35; both buyer-maker states present.
- Price, quantity, quote quantity, features, parameters, returns, validation,
  holdout, candidates, executions, and orders remain unopened or zero.
- Decision: `PERMIT_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL`.
- Next authorization: `AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ACQUISITION_PROTOCOL`.

### E-098 Q1 Paired Full-Development Acquisition Protocol

- Protocol file SHA-256:
  `9b36d16f2c2aafb01f737e3b94b801bb3e439dd5f83cc7e4bb61229f681988ab`.
- Protocol evidence hash:
  `44264aa5cd54d6b82156e068cf93de59b0ebfbe1d151363beffe598f3803e67c`.
- Independent audit file SHA-256:
  `1a74712fda24a22ef23c62006ce0a02bba15f90a9cd3eeee23d013088d22209f`.
- Independent audit evidence hash:
  `f4193b58181ab70156edeb1ffd47a41804bb45eb038f5d2fe127948e19d40e52`.
- Scope: 48 development months, 2020-01 through 2023-12.
- Target matrix: 48 Spot `aggTrades` plus 48 USD-M raw `trades` archives.
- Reuse candidates: 37, all requiring fresh hash and structural revalidation.
- Possible network targets: 59; maximum GET attempts: 177; observed requests: 0.
- Archive HEAD, redirects, ranges, partial-file reuse, price/quantity parsing,
  outcomes, candidates, executions, and orders remain forbidden or zero.
- Next authorization:
  `AUTHORIZE_Q1_PAIRED_FULL_DEVELOPMENT_ARCHIVE_ACQUISITION`.

### E-099 Q1 Successor Terminal Source-Sufficiency Failure

- Terminal checkpoint file SHA-256:
  `565a2885aaf17af473c38e55f0a2e24bb2462a80fe8cb54f2590625bf53cd9dc`.
- Terminal checkpoint evidence hash:
  `9cb957b626f9f506168c73e51cc61d1dccee21c9fb03560fbbdbed7c1d918dcc`.
- Terminal result file SHA-256:
  `deea039ad9d3e0c3c45a5df24ed00b9ce56ac60533dc2487a081c6c16e41283c`.
- Terminal result evidence hash:
  `f1adddf98a1466920a7d58d7b1e69e2f3101f3dae221f40ced590a893ed3e444`.
- Independent terminal audit evidence hash:
  `d95aa05f8236d6c1ba51f8a39e1e94376578ce2bc3b446369e9da129b7725760`.
- V7 transport amendment/audit hashes:
  `3bd140f124cf401bcb89ca704b1383143e6bb02c7550ee4a1df7bbc7188a1314` /
  `470f1043dc02b25eeffcd670294b3eda0f518447de92645df572e2dcdb5e12d0`.
- V7 execution-contract/audit hashes:
  `445407257f7e9ceb3ab6efed88e07ba7d6bea4caf19a85d0681cc65d44efb550` /
  `3193084a0d6de96b2bece168322fc135ae405eee8d5b1b95161c97c3a9779456`.
- Frozen runner source hash:
  `493ccebe8255ec19a01fcb60571627aac4918b5f4691ea8f9c4852476c518705`.
- Corpus: 37 classified months, 73 inspected archives, 19 qualified pairs, 18
  exclusions, 23 matched v7 request/response pairs, and zero partials.
- Qualified pairs by year: 2020 `5`, 2021 `6`, 2022 `6`, 2023 `2`; qualified
  quarters: `12/16`; qualified 2023 months: July and August only.
- Decision: `STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED`.
- Next authorization: `NONE_SOURCE_SUFFICIENCY_FAILED`.
- Prices, quantities, features, parameters, returns, outcomes, strategies,
  executions, and orders remain unopened or zero. Real net profit remains `$0`.

### E-100 S1 Lineage And Macro Charter

- Lineage ledger/audit hashes:
  `0e908e278455018f195f0b3a6269e65e67b415889a2fd0bd3d3c7b0df502bdab` /
  `590d5f5a848c52dc3c4455ebb7ce2d70db8250b6048fd76dbc0e63e825dbb41d`.
- Charter/audit hashes:
  `f5f0aa9980df16c4964abe1a41512abeccce2f009a2743492e2f0e1ce86d0c7d` /
  `79cc6e3fda4f1104c2c1df967e34c537695564f2bb29b7c7634863df57ab7239`.
- Mechanism: `S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE`.
- Market numeric fields, exact parameters, returns, candidates, executions, and
  orders: zero.

### E-101 S1 Metadata And Zero-Read Transport

- V1 protocol/result/audit hashes:
  `b36cc55362af6e027aaaf16355576b7f5d478e0600fce080a442ec994ec6f4c9` /
  `e81cbfed69cb4886d756b390b7f3110b63df87669f4c4b13b0e2d5b3ed12d502` /
  `9720c07355cdafedd0a1d3e8486311770cdc70e5260cfd1981532c4d3cea9a9e`.
- V2 amendment/result/audit hashes:
  `0bef139fb71fec027b1a985f6e1170ab150bbd12ca5c5530d187ad2596ee1f82` /
  `14b097c72afef189cdbccc9493618c5773e736a35b867615e60685dfa86b9532` /
  `18bebaca422d07f42b2cbda77ab5a6433c53740982c388743d081eb600318877`.
- V2 requests: four; response read calls and application body bytes: zero.

### E-102 S1 Failed FRED Raw Pilot

- Protocol/result/audit hashes:
  `18ece31c0279273fa6913f5c99b0f564eaa3f8be7c1b5619bcfc6488cea9d992` /
  `e3249edba089c7a8ebe76ced03958ade36625d4bc759783b305e19b0f731e209` /
  `39994116cfcd85e4e049509fce104a56d9b5e7dc9c164070548d32ba1effdb11`.
- Both files: 51,425 bytes; identical hash
  `4b489d3be3574ad5c35ffba7a74869f4db1b8ad8d792230f7ed5f57cca038896`.
- Last observation: `2026-08-21`; post-vintage observations: 347 and 294.
- Decision: `STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED`.

### E-103 S1 ALFRED Source Recovery

- Protocol/result/audit hashes:
  `d60d13bbc46a93d02edd7951172e612dd04e655cde026a4be00e800e5f1bd312` /
  `274e9981103b3e31aea001e543f62d29d0d6941a1529b00cb5b037a854c75472` /
  `f658ef8639cd5ad17216389687301addf737bcfa480b6064298f5b5036905f56`.
- 2020 snapshot: 2,555 rows, last date `2019-12-20`, 42,751 bytes.
- 2021 snapshot: 2,608 rows, last date `2020-12-25`, 51,399 bytes.
- Overlap: 2,555 observations; revised: 2,555; later-only: 53.
- All ten source gates pass. Next authorization:
  `AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY`.
- BTC market values, parameters, returns, candidates, executions, and orders remain
  zero. Real net profit remains `$0`.

### E-104 S1 Full Acquisition Protocol And Execution

- Protocol/audit hashes:
  `ccbff64f29ce5d85eb52dded23df1c393bb1a5ab4d5ce2c2874d8f284b87195e` /
  `3de2d5970b537a30eb3c5be1c39571b146bdac8116d2b6dc4be0ea20fff4d819`.
- Superseded v1 addendum/audit hashes:
  `c6279a10bb2daf4e8b7bba9fe4dd9aa1f37047aeefed1f3dd48f3aa713e51f76` /
  `e0dd54aef0058539f105877fd3071d9bfacecc6d8c728fb4027f99586b5909bf`.
- Active v2 amendment/audit hashes:
  `74420379ca8d30786c9d81a269052574d1d9aae90f3e85d0e952d14ad1fdbeda` /
  `ae7a963a0c68deafd0ff9970ccae6b097c4ada036fb3b19409f8a58f9cb334c5`.
- Active runner contract hash:
  `951318f4e7d27efa73420e69bff31fef219e647c36ed63ad12924ab94b2f9b8d`.
- Pre-correction requests and payload bytes: zero.

### E-105 S1 Full Development Source Result

- Targets complete: 281/281; GET attempts: 281; failures: zero.
- Network/persisted raw bytes: 13,056,155 / 13,056,155.
- Distinct payload hashes: 281; frozen source gates passing: 10/10.
- Checkpoint/result/audit hashes:
  `92d1a8931c14b476c8217337f91cd7aa0f472ab6b7f525613f45abda982a0ae4` /
  `4e94883da8e48c1dc6282370140084101f123dad2fd427dacee7708ee14c0c5f` /
  `f6669c6d80cd73f330a4d2c09a410e4eabb4b7628152bbd15636e12f13400ab1`.
- Decision: `PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION`.
- Next authorization: `AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY`.
- BTC values, returns, candidates, executions, orders, and real net profit remain
  zero.

### E-106 S1 Normalization Protocol And Execution

- Normalization protocol/audit hashes:
  `998b775e60aad081f421b80be678fd209348df149e8a7cc8f1f05b368e0f6041` /
  `2ef0d3405e903c01cdbed8648c26a244c5878bd26bcb2532c5a7f80536d0d087`.
- Execution addendum/audit hashes:
  `4190161d1e4f8928b5d6848f29b01d1e3bd31759fa280d1c12e3c81f319a3c34` /
  `110ca7006f8014c50df7083e83d39f5218ef712b981e1209f53e291fce288db1`.
- Runner contract hash:
  `a9cff8a1a1ed6f08ea1b55cde5dcf6f8949cab5044bc7b82fb03655cb8045908`.
- Synthetic execution tests: 7 passed before source-value transformation.

### E-107 S1 Causal Development Normalization Result

- Rows: 281; dataset bytes: 107,885; source bytes rehashed: 13,056,155.
- Release-lag range: 6-20 days.
- Dataset SHA-256:
  `789829ee9a9b84de528507c660c7abdcd5bd34a3c4a5d9cae1a46b7cd2ac927b`.
- Result/audit hashes:
  `d9816fce4035ec50368eb1d0541f287ea261b9f64c5dee779fc671a998d07f4c` /
  `5070de85bafb6b657055d4e89e49927b2494c1a3116c700edac5d28bfc67e58d`.
- Decision: `PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION`.
- Next authorization: `AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY`.
- Derived features, BTC values, returns, candidates, orders, and real net profit:
  zero.

### E-108 S1 Macro Feature Protocol And Execution

- Feature protocol/audit hashes:
  `d2ecbea9b31bc07e0cfec0901f3f262a1dd7e358148ec5e317ea972b51c16ce0` /
  `2a1486c2ab3c9c5be5b3cc07a905ad3bcba6f4a961988cf3023f2797526acd8f`.
- Execution addendum/audit hashes:
  `2743b1a1f8234d7e82687fc8985dee044855bb13cc33bfc56f54018fb54f5d81` /
  `de8fdc92fa19313120776831e1405623057aee5a598e9f75b782ed7c80f2db7f`.
- Runner contract hash:
  `3b85b9bc81fa47f6e0aa5745128f2d4ef3d2a1bde35c30283da00eb3e345515a`.
- Features: NFCI level, one-vintage change, four-vintage change; candidates: zero.

### E-109 S1 Development Feature Result

- Input/output rows: 281/277; output bytes: 90,632.
- Feature dataset SHA-256:
  `db93ee6954fee447cba66b3d873282da4d289f5ef6a63446d6ad036f787b24d6`.
- Result/audit hashes:
  `a59707114ec19c2576e72071fcba5ad7fa36e5232629a40fe1e9704f122f7664` /
  `da54d8a9ee1097994b1b3fc6edc81f844abcb7f9f046426c1f0a51732a0cc1f3`.
- Decision: `PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION`.
- Next authorization:
  `AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY`.
- Strategy candidates, BTC values, returns, orders, and real net profit: zero.

### E-110 S1 Outcome-Blind Strategy Preregistration

- Protocol/audit hashes:
  `6ca639fa0ff744dc13c1c8db229d46a8a7710b77bb49eded2ac8cae4a022816f` /
  `6d10abaf857bba7dd28c10e19957bdffc7fef7bc67da96d7dfd5060d3ba17c00`.
- Candidate roles: one primary eligibility rule; three diagnostics; rescue forbidden.
- Weekly intervals/price points: 276/277.
- Base/stress total cost per fill: 15/22.5 bps.
- Frozen primary-only development gates: 12.
- Feature rows parsed, BTC values read, and returns calculated during freeze: zero.

### E-111 S1 BTC Execution-Price Source Protocol

- Protocol/audit hashes:
  `bed364619aa4a141d339e405948e6a0a4113afb5c0ee1dedf5c288346255ffe2` /
  `19cf011a7f817b221f03748d9db48a614d235c7a79de8cc6e737ad20f3bce1bd`.
- Targets: 277 Fridays from `2017-09-15` through `2022-12-30`.
- Source: official Binance Spot daily BTCUSDT 1h ZIP plus CHECKSUM pairs.
- Maximum requests/payload bytes: 1,662 / 55,541,824.
- Requests, payload bytes, BTC values, returns, orders, and real net profit: zero.
- Next authorization:
  `AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY`.

## Exact Resume Point

Goal continuation status: `BINANCE SPOT TESTNET ADAPTER SANDBOX-QUALIFIED /
JAM SUCCESSOR DEVELOPMENT OUTCOME FAILED 3 OF 11 / JAM SUCCESSOR RETIRED /
Q1 SOURCE SUFFICIENCY FAILED / NO ELIGIBLE STRATEGY`. The production operator profile remains a separate 7-of-9
draft blocked on Binance production identity/API access and the unresolved
Zimbabwe venue/legal boundary. No qualifying strategy export, webhook, source
binding, or strategy evidence exists.

No strategy is eligible. Trend v1.3, volatility v1.1, slow spot v1.0.0, R4 path
quality v1.0.0, U1 volatility-managed broad spot beta v1.0.0, Jam Reversal Spot
v1.0.1, and the Jam successor sell-flow exhaustion/reclaim event are retired.
The Jam successor's 2019-2020 outcome study passed only 3/11 gates, has artifact
authorization `NONE_DEVELOPMENT_OUTCOME_FAILED`, and may not open 2021 validation
or 2022 holdout. P01 positive-funding carry is retired before returns because zero
symbols passed its frozen full-data gate. V3 completed
its no-return feasibility round and selected zero primaries. V4 has a frozen charter,
two unselected and unparameterized theories, and a terminally rejected V4P01
source-feasibility lineage. Its exact two metadata and six payload requests are
consumed; its original interpretation reject, no-repeat correction, continuation
reject, and explanation addendum are immutable. V4P02 consumed its only metadata
attempt and stopped before body transfer because the declared 203,310,405-byte body
exceeded the frozen 8,388,608-byte limit. Its hash-chained terminal preserves zero
accepted body bytes, zero retries, and zero consumed HEADs. V4 is closed by a frozen
zero-selection screen. The post-V4 capability review authorizes no successor alpha
discovery until six operator access, capital, loss, product, venue, and data-budget
facts are frozen. The credential-free operator-profile contract and its
shared no-write API/UI intake plus template/preflight/freeze/check CLI are complete
and verified. A real temporary operator draft now exists and passes seven of nine
production gates, but no canonical production profile is frozen. A separate
independently checked Testnet-only profile is frozen and authorizes successor-charter
design plus official Spot Testnet adapter engineering within its exact virtual-funds
boundary. It creates no alpha, return, candidate, paper, sandbox-qualification,
production, live, or capital authority.
The independent TradingView delivery path now has exact sender-policy binding,
paper/live/broker side-effect verification, and a database-backed immutable proof
package. No real external proof exists because no genuine TradingView alert or
sanitized alert-log artifact has been reconciled.
The frozen v1.3 parity path now has a verified protocol-bound paired-export engine,
stable post-consumption configuration hashes, and desktop/mobile runtime-verified
operator lineage controls. Shared async cleanup can no longer re-enable controls
against current renderer policy. No authentic TradingView chart/report exports, real
attestation, or real parity record exist.
The current live chart identity is `BINANCE:BTCUSDT` `30m` with only
`Aurex jam_reversal_v1` as a study and no Strategy Tester metrics. Do not treat it as
the required frozen-v1.3 `15m` chart or change it without explicit authority. The
local jam v1.14 file still has its historical strategy hash, but current loaded-source
identity is unproven because Pine Editor remained closed.
The Q1 source path is terminal after classifying all 37 months. It qualified only
19 paired months, failed the frozen pair/year/quarter sufficiency gates, and grants
`NONE_SOURCE_SUFFICIENCY_FAILED`. Do not rerun the acquisition, relax source gates,
or freeze its measurement protocol. Any future alpha research requires a separate
independent charter frozen before outcomes.
The frozen Testnet profile authorizes only declared official Binance Spot Testnet
requests, adapter implementation, successor-charter design, and tightly bounded
virtual Testnet orders. The adapter is sandbox-qualified by the completed Phase
2A-D evidence, but no strategy has Testnet order authority. Nothing authorizes V3
or V4 retry, unrelated network access, market-value parsing for alpha discovery,
parameterization, candidate creation, P01 development, 2025 access for U1, Pine
promotion, paper eligibility, production, live progression, or real capital.

Resume sequence:

1. Preserve all prior retired-strategy, R3/R3.1/R4, U1, V2, and P01 artifacts and
   verdicts. Do not rerun, relax, relabel, or rescue any consumed mechanism lineage.
2. Keep the complete 2023-2025 decision universe outcome-contaminated for retired
   mechanisms. Keep the 2026 holdout and forward data sealed.
3. Preserve V3 charter hash
   `10912cefdbd875b202fcc6903e5ffdf82652a97eddde7e9dc073a79308ed9b32`
   and proposal-register hash
   `1f0bc727d673f6daac6a6d6cad306f6e3007e1f718a67a96f249d586507ff321`.
4. Preserve V3P01 coverage hash
   `fe2641037216596f0aeb25cf8f1b04739eb303ce1a133ef76f0faca0e136fb34`,
   execution protocol hash
   `2c0d56b40150dac7fc1d6a6fc4091c99bea2b8a9536ab1c3ec9573d87bf720bb`,
   and terminal result hash
   `b682aa1149203f14c20ef12732bafb13f617a7f1fc260c5af32d25726d5253a2`.
   Do not reinterpret 25-symbol timestamp coverage as execution qualification.
5. Preserve V3P02 census contract/result hashes
   `956d4019400d499e0bea5b66d39de34afe9dd5687815dce43ae57b15d83949b6`
   and `b69fb4d2f1c04df7a12020d47f2a6263442db60980ef65cd73de08062b3a36b2`,
   payload protocol hash
   `2d8d1bdd347fc4e86fbf921995fc0ea39f5cd31adc398df84cdd8ee9595e5e6c`,
   and stop hash
   `67c967764111f831d80fb2e52d965460e0d59958b285e35e28715569dcb971f8`.
6. Keep the two verified V3P02 archives and all three request markers immutable.
   Do not retry DOGEUSDT, reconstruct the discarded partial payload, invent exact
   lost HEAD observations, or authorize full acquisition under V3.
7. Preserve V3P03 source-audit contract, transport amendment, and stop hashes
   `f52a3169b60d404033a7a41c24ef8df556d614e8975002035744153134040f7e`,
   `e94f7576ce132fd3389311d467af605ce9e0ec438e61b151ab08e844b386c6ec`,
   and `733556d1d95f30b1c5b012df66299cecb87234a3fe01577b2441b9504b6fb31d`.
8. Preserve terminal V3 screen hash
   `48e60151a4e4f6c86f5efa2569a4c6e63747bc1ee0996bf749d51a66f16f604e`
   and decision `SELECT_ZERO_V3_PRIMARY_MECHANISMS`. V3 is closed; no V3
   proposal may receive parameters or returns.
9. Preserve V4 charter hash
   `2230f042c676f97988129bf752aff889c83404627ff782c5462bd984e13cbd81`
   and proposal-register hash
   `a4fb8e0739cdd07f8a9a810cf395aa5fed3216000cb8b37c01f232eb5ec8973a`.
   The register contains exactly two proposals, deliberately leaves one slot unused,
   selects none, and authorizes no network request, payload, parameter, or return.
10. Preserve V4P01 feasibility contract hash
    `684a9f4de4aececab26113c46f98511037fefdcf811ab4abfbe3766a3ad0a69e`.
    It binds exact ETH/BTC venue products, eight request URLs, 14 hard gates, a
    zero-retry transport budget, incremental persistence, and mutually exclusive
    terminal artifacts.
11. Preserve original V4P01 metadata-reject hash
    `198d69b4358d7c980357201a7dbb2b209ccf4c8f2186009a9cc8a4c3cf7b8df2`,
    continuation contract hash
    `cfaa2e2b507813c81469938ab71b67c98502a8d3348e7e03256041f5e3b79f54`,
    continuation terminal hash
    `b3941f445cca6ce4c1533fa94fdb598dd6bf6f541a69c95e76dcd51c6e0a1348`,
    and explanation-addendum hash
    `f88e502c7838e6b31f42f09d336e4dc7a4d5d53757f5f466ccf30ba2dc54743a`.
12. Keep all eight V4P01 request attempts consumed. Do not repeat metadata or
    payload requests, request a different minute, relax snapshot/revision gates,
    substitute current fees or venue rules, inspect market values, calculate a
    return, or create a V4P01 candidate.
13. Preserve V4P02 source-census contract hash
    `a3c4bf0aeda588c63b02dee8f75c06efd22aa59c967bee104531f604432faf17`.
    It authorizes one metadata GET and 27 zero-body dataset HEAD requests only,
    with exact initial URLs, safe manual redirect validation, 17 hard gates, and no
    payload, market-value, or return permission.
14. Preserve V4P02 runner hash
    `f2b4b5969f881694a7a9e1e6b32af56a51e721d64bd61e014f4f027634820c7c`,
    request-journal hash
    `d847f5a1d9cd9832f1527aaba2dec7074a6accbff1d0a7dc5d0d275b3c2b8985`,
    and terminal result hash
    `d917c43f814e0b1ca27fff6ad7b5a5d57409e694d2c0efc2886a00508f12cd07`.
    The metadata attempt is consumed. Do not retry it, enlarge the byte budget,
    substitute a narrower or credentialed endpoint, skip metadata, or consume any
    of the 27 HEADs under V4P02.
15. Preserve terminal V4 screen hash
    `605d3b177b85ceaaf3ae5d9824d8eb2fc680ba355988d26d1a7769a19c897494`
    and decision `SELECT_ZERO_V4_PRIMARY_MECHANISMS`. V4 is closed; no V4
    proposal may receive parameters, returns, or continuation.
16. Preserve post-V4 capability-review hash
    `01fbf52bdc75f03dac21a26c4fdd642c6671d408464ac52da5ff3b3ac3bbabc6`
    and decision
    `DO_NOT_START_SUCCESSOR_ALPHA_DISCOVERY_UNTIL_ACCESS_PROFILE_IS_FROZEN`.
17. Open the dedicated `Operator` view or use
    `scripts/freeze_post_v4_operator_profile.py --template`. Collect the exact
    intended venue and jurisdiction, permitted product scope and maximum leverage,
    verified account/API and sandbox access references, actual unborrowed
    non-emergency starting trading capital, maximum acceptable
    total/daily/per-trade loss, and one-time/monthly data-acquisition budget. Use
    aliases only; never include credentials, secrets, recovery material, or account
    numbers, and do not infer or choose any operator value. Run the dashboard
    no-write preflight. Download only the exact `9/9` input, rerun CLI
    `--preflight --input`, use `--freeze --input` only after every gate passes, then
    independently run `--check --output`. A synthetic preflight is never operator
    evidence.
18. Separately, with explicit TradingView mutation authority, open the exact frozen
    v1.3 run package without changing ticker, timeframe, parameters, dates, costs,
    sizing, or order semantics. From the same unchanged chart state export both the
    TradingView chart OHLCV CSV and Strategy Tester completed-trades CSV. Import the
    chart as `tradingview-chart-export` with source reference
    `tradingview://chart/BINANCE:BTCUSDT/15m`; import the report with source reference
    `tradingview://strategy-tester/BINANCE:BTCUSDT/15m`. Select the intended
    checksum-verified Binance Vision dataset manually. Confirm the exact paired-export
    attestation, prepare and review the lineage hash, then require exact candle
    equality first. Preserve every candle mismatch, and only then compare and preserve
    every trade-level mismatch. Any evidence-selection change invalidates lineage and
    requires a fresh attestation/review. A pass calibrates the engine only; v1.3
    remains rejected.
19. With explicit TradingView alert authority, recheck the official sender hosts,
    keep live and the live adapter disabled, expose only the authenticated HTTPS
    webhook, and send exactly one bounded rejected-v1.3 alert. Preserve its Aurex
    signal ID and a sanitized TradingView alert-log artifact. Use
    `scripts/freeze_tradingview_external_delivery_proof.py --template`, then
    `--preflight`; freeze only if the database-backed result proves exact source
    policy, receipt integrity, `RISK_REJECTED`, the complete three-event timeline,
    and zero paper/live/broker side effects. Run `--check` against the same database
    signal and alert-log file. Until then
    `data/evidence/tradingview_external_delivery_proof_v1.json` must remain absent.
20. Only after the operator profile is frozen and independently checked with decision
    `AUTHORIZE_SUCCESSOR_CHARTER_DESIGN_ONLY` may Aurex design a separately versioned
    successor discovery charter constrained to capabilities that are actually
    accessible. The profile and charter still authorize no network request, market
    import, discovery execution, parameter, return, candidate, paper campaign,
    sandbox qualification, live trading, or capital.
21. [COMPLETE / HISTORICAL BOUNDARY] Preserve the guarded virtual-cancel source
    and provenance-bound reconciliation addendum. Do not rerun it. Its own
    checkpoint remained unqualified, but the later separately preregistered Phase
    2A-D campaign completed and qualified the adapter.
22. The exchange sandbox adapter is qualified, but strategy use remains blocked
    because no strategy is eligible. Forward paper, strategy-level sandbox
    operation, micro-live, and the first `$100` remain in their original order
    behind accepted strategy evidence.

Immediate Testnet continuation is:

1. Do not rerun `virtual-cancel`; its source and reconciliation addendum are complete.
2. [COMPLETE] Preserve fill-and-fee contract hash
   `8eddafafb5db47fa218c993476f5e6ae4cf13a4f4894d671c89321953e8719cd`.
3. [COMPLETE] Preserve the separately gated market-order adapter, checkpoint-safe
   runner, exact trade/fee/balance reconciliation, independent evidence verifier,
   failure-path tests, and read-only API/UI status.
4. [COMPLETE] Preserve fill/fee source hash
   `9a8876188432292bb27842956287881bf5fc170fa3164e07a97ebc8604ce3e51`
   and audit hash
   `720e5a00ac9c97fba284420054e0f5b88751cd82cac52440402edf4d2dfc8251`.
   Do not rerun the campaign.
5. [COMPLETE] Freeze Phase 2C contract hash
   `ddf06d9d596812c9dcb45c4c6654e8e50a0b5a3ae2928b15fdbf487fad2f8c2d` against
   Binance's current WebSocket API signature-subscription path.
6. [COMPLETE] Implement typed event ingestion, cross-connection duplicate
   suppression, deliberate disconnect, REST gap recovery, exact event/order/account
   parity, credential-safe teardown, checkpoint persistence, cleanup reporting,
   independent evidence reconstruction, API/UI state, and synthetic failure tests.
7. [COMPLETE] Preserve Phase 2C source hash
   `e5bc1e5402f49a07c5fc3389259025e30e9fee1ee6a525389e8e01aee7ba333e`
   and audit hash
   `70cd169d2716a2beac17c2f4a3cca53146b1c96f490b065830d7f774e9059038`.
   Do not rerun the campaign.
8. [COMPLETE] Freeze Phase 2D contract hash
   `5e5f1f22a014fa087c44a13341f862fe6d64ea441db280fabae677bf2af820d8`.
9. [COMPLETE] Implement durable hash-checked state, authenticated startup open-order
   census, intent-before-POST persistence, no-resubmit restart resolution,
   kill-stop-before-cancel, blocked-entry proof, exact no-fill reconciliation,
   monthly-reset fail-closed handling, three-process orchestration, a 600-second
   REST/WebSocket soak, independent evidence reconstruction, read-only API/UI state,
   and synthetic failure tests.
10. [COMPLETE] Run one genuine Phase 2D campaign. Preserve external order
    `22377060`, three-process recovery, durable kill-stop, 120 REST heartbeats, 21
    reconciliations, two reconnects, exact no-fill state, and no reset.
11. [COMPLETE] Byte-preserve Phase 2D source hash
    `8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50`
    and reproducible audit hash
    `0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29`.
    Accept decision `BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED` and do not rerun any
    Phase 2 campaign.
12. [NEXT PROGRAM ACTION] Return to strategy evidence. Select or preregister one
    separately versioned candidate, obtain genuine continuous `BTCUSDT` historical
    data, and require chronological IS/OOS, walk-forward, fee-net expectancy,
    drawdown, regime, concentration, and robustness gates before forward paper.

The unresolved production profile may remain deferred while Testnet engineering
continues. Do not mutate TradingView without separate explicit authority. The
rejected v1.3 parity track and one genuine authenticated webhook delivery to
paper-safe rejection remain permitted non-alpha implementation tracks. The
parity v1.2 code preparation is complete; its next action is an explicitly authorized
frozen TradingView run, paired chart/report exports, and real reviewed lineage
attestation, not synthetic parity data. The responsive UI checkpoint is complete; do
not substitute more synthetic UI work for the missing external evidence. The shared
action-lifecycle fail-closed audit is also complete.
The webhook code preparation is also complete; its next action is the single
explicitly authorized external alert and immutable proof workflow, not another
synthetic request. Do not start V3P02 full acquisition, reopen V4P01/V4P02, inspect
V4 market values, use current exchange rules as historical truth, invent a venue or
capital amount, or select a mechanism by visual appeal or theoretical profitability
alone.

Latest Phase 2 closeout verification: 20 restart/soak, evidence-tamper, status API,
and dashboard tests pass with one known Starlette/httpx deprecation warning. The
complete project suite at the final Phase 2 code-readiness checkpoint passed `965`
tests in `635.60` seconds. After genuine evidence acceptance, repository-wide Ruff,
frontend JavaScript syntax, independent Phase 2D audit reconstruction, live
read-only API state, dashboard visual state, and `git diff --check` pass. The
protocol-bound paired-export
parity/backtest/dashboard suite passes `53` focused tests; the credential-free
operator-profile suite and API/dashboard workflow pass `35` focused tests; the
focused webhook source-policy/external-proof suite passes `37` tests; the focused
V4P02 contract/runner suite passes `35` tests; the consolidated V4P02,
terminal-screen, and post-V4 review suite passes `48` tests; all frozen V4P01, V4P02,
terminal V4, and post-V4 audit/check commands pass; repository-wide Ruff, frontend
JavaScript syntax, operator CLI template, and `git diff --check` pass.
Local-server Chromium verification now confirms the paired-lineage controls at 1440
pixels and a 390-pixel one-column layout with zero horizontal overflow. The active
Backtests tab is automatically visible on mobile, unavailable HTF warm-up data
renders as `n/a`, and lineage/compare/record remain disabled without evidence. The
action-lifecycle runtime additionally proves renderer-disabled state preservation,
ordinary-action recovery, and exact duplicate suppression. The post-controller
dashboard suite passes `2` focused tests. Operator browser verification also remains
valid for synthetic blocked/pass states; no test value was frozen.
The `2026-07-30` read-only TradingView recheck confirms `BINANCE:BTCUSDT` `30m`, one
jam study, and no strategy. Its screenshot hash is
`10b0d53d95ebf8e0a620d36528bef81d4efeb4ea9b1abfb33561acdaa301a2fe`.
The local jam v1.14 strategy hash still matches historical E-007, but current chart
source retrieval stopped with Pine Editor closed; current chart/local binding remains
unproven.
The fresh resumed-turn-three audit reconfirms zero v1.3/protocol-bound reports,
TradingView chart datasets, parity runs, signals, and signal events; both required
real proof artifacts remain absent and live remains disabled.
No real operator profile, external-delivery proof, TradingView chart/report export,
paired-export attestation, or parity record exists.
TradingView's official webhook documentation was rechecked, but TradingView workspace
state was not mutated, no TradingView alert was sent, no market-data or V3/V4 network
request was made, no market value was inspected, 2025 validation and 2026 holdout
were not opened, forward data remains sealed, real profit is `$0`, and live trading
remains disabled.

## Latest Exact Resume Point

Checkpoint: `2026-08-14T08:37:26Z`.

The active research checkpoint is
`Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED_TERMINAL`. The acquisition and independent
terminal audit are complete. Do not rerun the source path or freeze its paired
measurement protocol. The next permissible research action is a separately
versioned, genuinely independent mechanism/source charter frozen before outcomes;
no such charter is authorized or selected yet.

Phase 2 remains complete and must not be rerun. The selected Jam strategy track also
completed its first honest historical decision:

1. `jam_reversal_spot_v1` v1.0.1 is retired and disabled.
2. Preserve protocol `f788795a-ac75-4763-93c2-75a031ee2c70`, replay
   `82e5ff23-a4de-423b-b8df-6394d09566a1`, validation
   `6ad2fef6-ffd3-4773-9f02-52e80596bdd4`, and the decision artifact unchanged.
3. Preserve frozen contamination-ledger v1 hash
   `9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`
   for all historical lineage. Preserve append-only ledger v2 hash
   `f24cc36011e9f9ddc40e277197bd3fa03310cac12b6848b30714aae26cdb37bd`
   for the Jam v1.0.1 contamination record.
4. Do not run Jam v1.0.1 in TradingView, forward paper, or Testnet strategy
   execution. Historical gates failed before parity was warranted.
5. [COMPLETE] Preserve failure-analysis hash
   `7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`.
   It used stored decision evidence only and grants no trading or retuning authority.
6. [COMPLETE] Preserve Jam successor charter hash
   `426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`.
   The only selected proposal is aggressive sell-flow exhaustion and reclaim, and it
   is selected for future capability review only.
7. [COMPLETE] Preserve metadata-census contract hash
   `3670f121f303bf39a17dbc7b057bde913e30252687139046ae4785269f4e8302`.
   Its exact matrix contains 96 official checksum URLs: BTCUSDT spot monthly
   aggregate trades and one-minute klines for January 2019 through December 2022.
8. [COMPLETE] Preserve metadata-census result hash
   `e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e`
   and independent audit hash
   `3f57bd2fb843059606bf32a284db0cc15e58c436115a922073b0c862aaaabfcb`.
   All 96 targets were present in 96 first-attempt checksum GETs. Archive HEAD
   requests, payload requests, payload bytes, redirects, market values, features,
   returns, strategy executions, and orders all remained zero.
9. [COMPLETE] Preserve one-month payload protocol hash
   `1e9a6ef48ac06353f933d21cb193bf0b1489f03f79e6a4562062a0ddddbba24e`.
   January 2019 was selected as the earliest provisional month before payload
   access.
10. [COMPLETE] Preserve payload-pilot result hash
    `f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974`
    and independent audit hash
    `bc8880252f50215be1fbb46803e1325d5e40c2b34101ad02bad0d4284ad710bf`.
    Both published hashes matched. The source pair contained 5,989,468 aggregate
    rows and exactly 44,640 kline rows; IDs, continuity, OHLC, trade counts, base
    and quote volume, and taker-buy volume reconciled with zero mismatch.
11. [COMPLETE] Preserve full-acquisition protocol hash
    `b27197c3b9c7e4366b3e72442206562e1ae2967931ec3fa383e59c9133bcaf74`.
    It bound all 96 archive identities, request/storage limits, resumability,
    exact source-quality rules, and the no-return authority boundary.
12. [COMPLETE] Preserve checkpoint-migration evidence hash
    `bb971b20617fd54fb97b190d7bea68832f4a092d78b74585f698e850996ac4d0`.
    It migrated exactly 35 completed months only after rehashing 70 raw archives
    and confirming their original one-member ZIP matrix.
13. [COMPLETE] Preserve full-acquisition result hash
    `ffe45a45bc9340e3323aac9ddd4257a19597bcee260961f787b50c8b1dee121b`.
    All 96 checksums passed, but only 23/48 months passed every frozen paired-source
    quality rule. Decision:
    `STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED`. Artifact next authorization:
    `NONE_ACQUISITION_FAILED`.
14. [COMPLETE] Preserve archive-quality remediation protocol hash
    `128eb77a416ba9ebd47154639fe383f1f9b9c0058c149c8f7dc62c4e5e24c57a`.
    It froze source questions, chronological evidence roles, a 10,000-record issue
    budget, and a strict no-return/no-order boundary before detailed inspection.
15. [COMPLETE] Preserve remediation result hash
    `02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`
    and independent audit hash
    `146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`.
    Both 2021-12 members are byte-identical. The exact issue set is 4,009 missing
    kline minutes, eight invalid rows, and 144 mismatch minutes; the union contains
    4,161 quarantined minutes.
16. [COMPLETE] Adopt aggregate trades as Jam's historical primary source and
    one-minute klines as QA-only. Preserve no-synthesis, state-reset, and maximum
    future-feature-lookback recovery rules. Freeze 2019-2020 development, 2021
    sealed validation, and 2022 sealed holdout.
17. [COMPLETE] Preserve feature-specification protocol hash
    `86ee3e67c6fc78863378b4a1b30c8cb38f9aafda2335e92054309cd260bfffba`.
    It was frozen before feature design and authorized schema, causal lookback, and
    synthetic conformance work only.
18. [COMPLETE] Preserve feature-specification hash
    `8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`
    and independent audit hash
    `760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`.
    The exact system has 17 features, 133 required valid minutes, seven quality
    states, and nine passing synthetic conformance cases.
19. [COMPLETE] Preserve development-distribution protocol hash
    `8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551`,
    result hash
    `d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef`,
    feature-row SHA-256
    `fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`,
    and independent audit hash
    `7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`.
    All 7/7 structural gates passed on 2019-2020 only.
20. [COMPLETE] Preserve event/outcome protocol hash
    `33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db`
    and independent audit hash
    `b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4`.
    It freezes one event, one primary horizon, costs, controls, inference, and
    staged evidence gates while calculating zero events, labels, or returns.
21. [COMPLETE] Preserve prevalence protocol hash
    `e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd`,
    result hash
    `444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea`,
    ledger SHA-256
    `b6fe0c49bbbb8b61ac268b4716d2a50ab5fa08479ccbf254ef532b15a3b7d909`,
    and audit hash
    `414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d`.
    All 7/7 prevalence gates passed on 1,430 raw and 991 accepted events.
22. [COMPLETE / RETIRED] Preserve development execution-protocol hash
    `e7ed92d708c80a87b36c7d24d903cd7be1c1f594def74daab22618ed9bc6e07d`,
    result hash
    `560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430`,
    and audit hash
    `8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`.
    The 991 event outcomes and 456 matched pairs passed only 3/11 gates. Decision:
    `STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.
23. [SEALED] Do not open 2021 validation or 2022 holdout for this event. Do not
    tune, relabel, rerun under easier assumptions, promote a diagnostic, or create
    Pine, paper, or Testnet strategy execution. Artifact next authorization:
    `NONE_DEVELOPMENT_OUTCOME_FAILED`.
24. [COMPLETE] Freeze strategy-factory contract v1 under evidence hash
    `8676ffc5caea7782607ad7e9072e71ab8e09fbd93fe115f47c8860833f33f50e`.
    It requires development, validation, and separate holdout partitions; cost
    stress; uncertainty bounds; multiple-testing control; and one-shot holdout
    decisions. It grants no execution authority.
25. [COMPLETE] Enforce exact lifecycle state in the shared registry and risk path.
    Every current strategy is retired, quarantined, or research-only. An `ACTIVE`
    label cannot enable a strategy without the factory contract version and a
    hash-bound qualification.
26. [COMPLETE] Bind `/system/readiness` and Command to canonical readiness evidence.
    Current scoring is 14/15 PASS, 1 downstream PARTIAL, 0 FAIL, and zero research
    blockers. Desktop runtime inspection found and removed the final retired-plan
    strategy leak from Command and initial backtest/Pine resources. External
    TradingView delivery remains genuinely unproven.
27. [COMPLETE / CHARTER ONLY] Preserve Q1 periodic-flow Spot charter hash
    `17e9a73193a0c159aa6d3a15fea2412285e3cd12a5a4e0e52e3e27bcf4fa195b`
    and independent audit hash
    `ad6a76574af1f3ff5dbf91f0ed42f6c1c066ff8746b7202bf0fc1c2e0373096a`.
    It freezes one long-or-cash BTCUSDT Spot hypothesis using causally completed
    Binance USD-M perpetual order flow as a future research input. It preserves the
    V3P02 transport stop and predecessor multiplicity. It opened zero market values,
    returns, parameters, candidates, executions, or orders.
28. [COMPLETE / METADATA ONLY] Preserve Q1 census contract hash
    `841caf8e7dc20d21722247759f9804f5f896ac5936c40d8000467a96a03acb90`,
    result hash
    `54dbfba6642b9057172f32405d7ed983bb66488acd0ab31d6e26358926d41a17`,
    and audit hash
    `b9d62a43c6ac1af25f70d67f4ff8929e78c5b31b1c2e5017d9481ecacc12b18f`.
    All 144 first-attempt checksum GETs passed and all 72 paired months were
    present. No archive HEAD, ZIP payload, market value, parameter, return,
    candidate, execution, or order was opened.
29. [COMPLETE / SOURCE PILOT] Preserve Q1 paired-payload protocol hash
    `f2a6df06336a96050421c449e48a9c8c06aef871b97e73c280a3309c90ca43cc`,
    result hash
    `131d3d3a8925982379cf4186257c2c41852de95c228c6dd97b1c4abe494e3565`,
    and audit hash
    `0e099618d30dec7db047f25a0c530b38c55c6a255d09cac39a831392e303746a`.
    Spot passed. USD-M `aggTrades` stopped with 505 adjacent raw-range
    discontinuities under decision `STOP_Q1_PAIRED_PAYLOAD_CAPABILITY_FAILED`.
30. [COMPLETE / REMEDIATION STOP] Preserve result hash
    `dea09a8f545b8c1885ac1e1c8f5a6d370ab719559c801b16fb12c4f5d49685a3`
    and audit hash
    `d4b555735662dfed6ced975c32e1ed3aaf7313c6b93dc95211bbe5f7b4ccfa6f`.
    The frozen analysis found 504 forward gaps, 1,374 skipped raw IDs, and one
    adjacent overlap. It correctly stopped at
    `STOP_Q1_USDM_SOURCE_SEMANTICS_UNRESOLVED` rather than waiving the overlap.
31. [COMPLETE / CROSS-SOURCE ADJUDICATION] Preserve overlap-census result hash
    `488041793701639de79d7528aaae2f05b975668542f8a59b566e1cb025c6b727`
    and audit hash
    `c9e6170819e16f73b5eb77ae72c780c3bb2acfb188db5a8cf65ac5d59f1cc89a`,
    plus daily adjudication result hash
    `b7332d7eeb2b298f2db897939f6abc7ea29f6c2a658640c84814c5e401a6c7d4`
    and audit hash
    `998a0f38e432a4cca41709006b821a3af9808c631f6ad95e6f64702929bd3c98`.
    Official daily `aggTrades` reproduced the duplicate reference while official
    raw `trades` contained raw trade ID `30414701` exactly once. Reject USD-M
    `aggTrades` for this research path; Spot `aggTrades` remains unchanged.
32. [COMPLETE / RAW-TRADES METADATA ONLY] Preserve protocol hash
    `08ca0b4fce3790b398f3535511d19915b3a8b80e6e8c5c1326c6caf9198e9e6e`,
    pre-network audit hash
    `10d1c474780cfa3e4903022c44170fd0a3b2beaa8072f9c5c362ea07f3a9fb67`,
    result hash
    `64da0748128779cbfc040883437a1523e571fe68b3746decc9bc7adccc7c793a`,
    and result-audit hash
    `e29b821c8795482dc64f25230d6f2d50c3f9feccda48a22326ec81de2c68c95a`.
    All 72 checksum sidecars were present on their first attempt, including 48/48
    development and 24/24 validation-metadata months. No archive payload, market
    value, parameter, return, candidate, execution, or order was opened.
33. [COMPLETE / ONE-MONTH STRUCTURAL PILOT] Preserve protocol hash
    `79e7ec935f31dba86a0173398133ec4abd0acc3f2a559bc5dda0dd3f3fa77451`,
    pre-network audit hash
    `26ec1c8fd400228443beeda4130b17a019428fa8ef22b67c937e122c2b97bbe3`,
    canonical marker-bound result v2 hash
    `4d0c4ef5b1f56bc498d2625fe1acd5a33faffe679425c82c5e2c83b6fc572477`,
    and result-audit hash
    `3e627038aa89748165874e32cd62bd8da202670b37613c3221944cda6e350fd0`.
    Exactly one USD-M raw `trades` ZIP was requested. It passed every frozen
    structural and paired-clock gate. No price, quantity, feature, parameter,
    return, candidate, execution, or order was opened.
34. [COMPLETE / FROZEN PRE-NETWORK] Preserve paired full-development protocol hash
    `44264aa5cd54d6b82156e068cf93de59b0ebfbe1d151363beffe598f3803e67c`
    and independent audit hash
    `f4193b58181ab70156edeb1ffd47a41804bb45eb038f5d2fe127948e19d40e52`.
    The exact matrix has 96 targets, 37 local reuse candidates, 59 possible network
    targets, and zero requests. No market value or outcome was opened.
35. [COMPLETE / EXECUTION CONTRACT] Preserve execution-contract hash
    `542c84962812de3950a543c221f31375cacb8c5de702a805ae74379b2ce1adf9`
    and independent audit hash
    `018ef8a010f9b971c3ed638b5f2173e1520f65104ed3c1574dfb540efd6f16e3`.
    The source-bound runner implements chronological Spot-then-raw acquisition,
    immutable request/response markers, exact retry budgets, interruption recovery,
    no partial reuse, atomic archive/month checkpoints, structural-only parsing,
    and first-failure stop semantics. Synthetic transport and parser tests pass.
36. [COMPLETE / PREFLIGHT BLOCKED] Preserve preflight result hash
    `623c22fec5a5895eda9ffac2940f1cd932582d1b7977300f55e0918d78980c5c`
    and independent audit hash
    `eadf6ea3e7a7cf223f53de83ca0f44d453614579f7589b1e970af5ce15dca4ba`.
    All 37 local reuse candidates and 27,856,663,229 archive bytes passed fresh
    checksum and ZIP-policy reconstruction. The point-in-time disk observation was
    48,036,913,152 bytes free against the frozen 120,000,000,000-byte preflight
    requirement, a 71,963,086,848-byte shortfall. Network requests, payload bytes,
    outcomes, executions, and orders remain zero.
37. [BLOCKED / RESOURCE ONLY] Make at least 120,000,000,000 bytes free on the
    acquisition volume, then rerun the canonical preflight. Do not start any of the
    59 possible network targets until the disk gate passes. After it passes, run
    only the frozen checkpointed acquisition. Validation and holdout remain sealed.
38. Exact Pine parity is unavailable for exchange-native aggregate-trade order flow.
    Never substitute a candle proxy and call it equivalent.
39. Production, live, real capital, and real profit remain false. Real net profit is
    `$0`.

Latest metadata-census closeout verification: the focused Jam charter/census suite
passed `22` tests, repository-wide Ruff passed, and the full Aurex suite passed
`1004` tests in `354.13` seconds. The only warnings were the existing pytest
`cache_dir` configuration warning and Starlette/httpx deprecation.

Latest payload-pilot closeout verification: the focused Jam
charter/census/payload lineage suite passed `35` tests, repository-wide Ruff passed,
and the full Aurex suite passed `1017` tests in `556.17` seconds. The only warnings
were the existing pytest `cache_dir` configuration warning and Starlette/httpx
deprecation.

Latest full-acquisition evidence: 96/96 archive checksums passed; 94 HEAD and 95
payload GET requests were recorded; 29,691,768,890 compressed bytes and
1,972,243,570 aggregate rows were inspected. Twenty-three months passed and 25
failed. Independent raw-file reconstruction passed under audit hash
`d0f1d8bc4a2fe8745bf678aacdeeaeb3ef547fed49b9956dc54d36311c96e961`.
The 50-test focused Jam lineage suite, repository-wide Ruff, protocol/migration/
result audits, and all `1032` Aurex tests pass. The full suite completed in
`435.31` seconds with only the existing pytest `cache_dir` warning and
Starlette/httpx deprecation.

Latest archive-quality remediation evidence: the no-return protocol, 48-month kline
defect reconstruction, 2021-12 duplicate byte comparison, and 18-month
cross-family reconstruction pass. The result contains 4,161 uniquely quarantined
minutes and independently reproduces under audit hash
`146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`.
The 65-test focused Jam lineage suite and repository-wide Ruff pass. All `1036`
Aurex tests pass in `790.27` seconds with only the existing Starlette/httpx
deprecation warning.

Latest Jam feature-specification evidence: the pre-specification protocol, exact
17-feature matrix, 133-minute causal partition/reset semantics, nine synthetic
anti-leakage conformance cases, and independent reconstruction all pass. Zero real
market rows, thresholds, labels, returns, signals, strategies, or orders were
created. The 78-test focused Jam suite and repository-wide Ruff pass. All `1049`
Aurex tests pass in `1042.31` seconds with only the existing Starlette/httpx
deprecation warning.

Latest Jam development-distribution evidence: all 24 frozen 2019-2020 archive
identities, 1,052,640 calendar rows, 17 feature profiles, 136 pairwise
correlations, tail concentration records, and 7/7 structural gates pass.
Independent reconstruction reproduces the Parquet and result byte-for-byte under
audit hash
`7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`.
The 79-test focused Jam suite and repository-wide Ruff pass. All `1052` Aurex tests
pass in `1451.94` seconds with only the existing Starlette/httpx deprecation
warning.

Latest Jam event/outcome-protocol evidence: one five-condition long-only event,
one selectable 30-minute horizon, 60-minute chronological suppression, seven
prevalence gates, fixed execution costs, deterministic matched controls,
calendar-month cluster inference, and staged development/validation/holdout gates
are frozen. Independent reconstruction passes under audit hash
`b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4`.
Zero events, labels, returns, controls, backtests, signals, or orders were
calculated. The 83-test focused Jam suite and repository-wide Ruff pass. All
`1056` Aurex tests pass in `843.20` seconds with only the existing
Starlette/httpx deprecation warning.

Latest Jam development-event-prevalence evidence: the pre-run protocol, exact
five-condition predicate, 1,430-record raw-event ledger, 991 accepted events,
439 suppressions, 24 qualifying months, minimum quarter count of 70, and all 7/7
prevalence gates pass. Independent reconstruction reproduces the ledger and result
byte-for-byte under audit hash
`414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d`.
Zero future prices, labels, returns, controls, backtests, signals, or orders were
calculated. The 88-test focused Jam suite and repository-wide Ruff pass. All
`1061` Aurex tests pass in `1426.56` seconds with only the existing
Starlette/httpx deprecation warning.

Latest Jam development-outcome evidence: the execution protocol was frozen before
post-event price access. All 86,820 requested 2019-2020 path minutes were
recovered, 991 event outcomes and 456 matched pairs were calculated, and only 3/11
development gates passed. Base mean was `-16.008098281388651150` bps, profit
factor `0.464374516027724364`, stress mean
`-26.189788269683100509` bps, and both bootstrap lower bounds were negative.
Independent reconstruction reproduced both ledgers and the complete result
byte-for-byte under audit hash
`8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`.
Decision: `STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`; artifact next
authorization: `NONE_DEVELOPMENT_OUTCOME_FAILED`. The frozen protocol check,
seven focused outcome tests, 95 focused Jam lineage tests, and repository-wide
Ruff pass. All `1068` Aurex tests pass in `676.74` seconds with only the existing
Starlette/httpx deprecation warning.

Latest Q1 charter evidence: the mechanism, five sealed chronological partitions,
11 predecessor bindings, four external research sources, and 14 feasibility gates
are frozen before data outcomes. Independent reconstruction passes under audit hash
`ad6a76574af1f3ff5dbf91f0ed42f6c1c066ff8746b7202bf0fc1c2e0373096a`.
All authority beyond a metadata/checksum census remains false. Seven focused Q1
tests and focused Ruff pass. Repository-wide verification follows the source-bound
readiness v4 generation.

Latest Q1 metadata-census evidence: 144/144 official Binance checksum files were
present on first attempt, producing 72/72 paired Spot/USD-M months, with 48
development and 24 validation metadata pairs. Independent reconstruction passes
under audit hash
`b9d62a43c6ac1af25f70d67f4ff8929e78c5b31b1c2e5017d9481ecacc12b18f`.
Ten focused census tests and focused Ruff pass. Archive payload requests, market
values, parameters, returns, candidates, executions, and orders remain zero.

Latest Q1 paired-payload and source-adjudication evidence: the exact 2020-01 Spot
and USD-M `aggTrades` archives passed checksum and complete-clock checks. Spot
passed all structural gates. USD-M produced 504 documented-compatible forward
gaps and one independently reproduced duplicate raw-trade reference. The frozen
daily cross-source result found that raw trade exactly once in official USD-M raw
`trades`; Aurex therefore rejects USD-M `aggTrades` for Q1. Daily adjudication
passes under audit hash
`998a0f38e432a4cca41709006b821a3af9808c631f6ad95e6f64702929bd3c98`.
The next authorization is protocol-only: freeze a 72-month checksum census for
USD-M raw `trades`. No checksum request, full acquisition, outcome calculation,
Pine deployment, paper operation, Testnet strategy order, production, or live
trading is authorized.

Latest Q1 USD-M raw-trades metadata-census evidence: the protocol was frozen and
independently audited before network access. All 72 official monthly checksum
sidecars were present with exactly 72 HTTP attempts, including all 48 development
and 24 validation-metadata months. Independent result reconstruction passes under
audit hash
`e29b821c8795482dc64f25230d6f2d50c3f9feccda48a22326ec81de2c68c95a`.
Archive HEAD requests, ZIP payload requests, payload bytes, market values,
parameters, returns, candidates, executions, and orders remain zero. The exact
next action was a separately frozen 2020-01 raw-trades payload protocol.

Latest Q1 USD-M raw-trades payload-pilot evidence: the protocol and independent
audit were frozen before one exact archive request. The 128,838,558-byte archive
matched its published hash and contained 10,281,248 rows across all 44,640 month
minutes. It had zero duplicate or non-increasing IDs, zero timestamp regressions,
726 bounded forward gaps totaling 1,809 skipped IDs, a maximum single omission of
35, and both buyer-maker states. All 44,640 raw minutes paired with the qualified
Spot archive. Canonical marker-bound result v2 independently reconstructs under
audit hash
`3e627038aa89748165874e32cd62bd8da202670b37613c3221944cda6e350fd0`.
The next authorization is protocol-only: freeze the paired 2020-2023 development
acquisition contract. No additional ZIP, price/quantity parsing, feature,
parameter, outcome, strategy, paper, Testnet strategy order, production, or live
authority exists.

Latest Q1 paired full-development protocol evidence: the 96-target 2020-2023
manifest was frozen and independently reconstructed before any additional request.
It binds 48 Spot `aggTrades` and 48 USD-M raw `trades` archives, 37 exact local
reuse candidates requiring fresh revalidation, and at most 59 network targets.
The protocol requires one-at-a-time streaming, pre-attempt markers, per-archive
checkpoints, partial-file rejection, and fixed byte/disk ceilings. Independent audit
hash
`f4193b58181ab70156edeb1ffd47a41804bb45eb038f5d2fe127948e19d40e52`
passes with zero requests, market values, outcomes, or orders. The exact next action
is acquisition-runner implementation and the bounded development-only acquisition;
it is not feature design, backtesting, signal generation, paper trading, or live
trading.

Latest Q1 acquisition-runner and preflight evidence: the execution addendum was
frozen and independently reconstructed before any network request. Seventeen
focused protocol/runner tests pass, including full-GET identity, transient-only
retry, checksum-failure stop, interrupted-partial deletion, exact-hash completed
archive recovery, ZIP traversal rejection, and the forbidden price/quantity-field
trap. The canonical preflight freshly revalidated all 37 local candidates,
including the byte-identical 2021-12 duplicate-member exception, under audit hash
`eadf6ea3e7a7cf223f53de83ca0f44d453614579f7589b1e970af5ce15dca4ba`.
Decision: `BLOCK_Q1_ACQUISITION_INSUFFICIENT_FREE_DISK`. Required free space is
120,000,000,000 bytes; the recorded shortfall is 71,963,086,848 bytes. No new
archive, HTTP request, payload byte, market value, outcome, candidate, execution,
or order was created.

Latest Q1 successor-acquisition evidence: the versioned v1-v7 lineage is terminal.
V7 classified all 37 months, inspected 73 exact-hash archives, qualified 19 paired
months, and excluded 18. The year counts are 5, 6, 6, and 2 for 2020 through 2023,
with only 12 of 16 quarters represented. Decision:
`STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED`. Checkpoint hash
`9cb957b626f9f506168c73e51cc61d1dccee21c9fb03560fbbdbed7c1d918dcc`,
result hash
`f1adddf98a1466920a7d58d7b1e69e2f3101f3dae221f40ced590a893ed3e444`,
and independent terminal audit hash
`d95aa05f8236d6c1ba51f8a39e1e94376578ce2bc3b446369e9da129b7725760`
all verify. Next authorization is `NONE_SOURCE_SUFFICIENCY_FAILED`; do not rerun
the acquisition or freeze its measurement protocol. See
`docs/40_PERIODIC_FLOW_SUCCESSOR_ACQUISITION.md` for the exact terminal record.

## S1 Exact Resume Addendum (Latest)

Checkpoint: `2026-08-27T06:26:00Z`.

Q1, S1 v1, and S1.1 are terminal. S1 v1 failed source feasibility because target
22 had no exact 00:00 UTC bar. Result/audit hashes:
`f444378a3b89b49812615b8b9313147e32e2ecb646348675054893bea99a57fd` /
`b98dff769d6537ee55d00705ea7fe585868390f7c7d0651ed99f91177771949e`.
The v1 partial-resume defect remains preserved and does not change that failure.

S1.1 froze a first-valid-Friday-bar timing amendment with prior exposure declared,
then acquired and audited 277 checksum-bound prices. Source result/audit hashes:
`87e413172462f7006332a53be3ba74b6b7bdd1c61e03d0f7f71e218322e3caa0` /
`5685b46d8ef2c787ce606025ee76d75bbf00a830237f692b5ec7b6145ac053f3`.
All 11 source gates passed; exactly one target used a 600-minute delay.

The one-shot primary development outcome passed 7/12 gates and failed PF,
base/stress drawdown, positive-year, and stress-bootstrap gates. Result/audit hashes:
`8d900beb2dcbfcb0d11fed1f8ee0a99ecfa812e03900dae21a886973f86cc317` /
`ab1f10d0208560933e048f1fb93e5b03f0988048e7c4b5e6057dba14b0c2495d`.
Decision: `STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED`. Diagnostics cannot be promoted.

Exact resume point: `AUTHORIZE_POST_S1_FAILURE_ANALYSIS_PROTOCOL_ONLY`. Failure
analysis may explain evidence but may not tune S1, reinterpret the positive base
return, open validation or holdout, or create execution authority. Any successor
must be a separately preregistered mechanism. Pine, paper, Testnet strategy orders,
production, and live remain unauthorized. Real net profit remains `$0`. See
`docs/41_S1_MACRO_FINANCIAL_CONDITIONS.md`.

## S1 Post-Failure Analysis Resume Addendum (Latest)

Checkpoint: `2026-08-27T07:20:00Z`.

The bounded S1 postmortem is complete and independently reconstructed. Its
protocol/audit hashes are
`f4b7ebd92fd1a149d784cce1840c08180d8c942ff2e54b6047313f91ba359c9b` /
`5b88bb69058ccde7f839bcb8405123fdd8db283920bccb000ddaf8cfbd431a83`;
execution contract/audit hashes are
`84a4d09a653ca932e837adaa515faa47301a4a38cea5915839fd8ded22209064` /
`13a27548fa293a6082b9fa8311bb321162cf4f8318aeeeacc777017caf79945b`.
Zero parameter variants, new candidates, validation values, holdout values, or
orders were opened.

The primary's already-opened development path returned `22.9048%` before modeled
execution costs, `7.6958%` at base cost, and `0.8049%` under stress. It charged 88
fills, retained only `10.4588%` of the positive base return under stress, suffered
`66.3009%` base maximum drawdown, and did not recover from its `2021-04-16` peak by
development end. Tail dependence remained material, and two diagnostic variants
had identical position vectors. These facts explain the rejection; they do not
create a rescue path.

Postmortem result/audit hashes:
`0db0fd10424b5bcc07a7f10c42c88d3a3843c0dddbcdc6a29c6665529c192988` /
`be6340eb9bf978c4cff9f06427169cd1b03a76f2a5030aa028aa4343c2f97ffe`.
Decision: `RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE`.

Exact resume point: `AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY`. S2 may define
one genuinely distinct economic mechanism and its source/feasibility gates. It may
not rename, tune, or combine a retired family; inspect validation/holdout; calculate
returns; generate signals; or place paper, Testnet-strategy, production, or live
orders until separately frozen downstream stages authorize them. Real net profit
remains `$0`.

## S2 Charter Resume Addendum (Latest)

Checkpoint: `2026-08-27T07:21:41Z`.

The distinct S2 charter is frozen and independently reconstructed before any
blockchain or market value is opened. Mechanism
`S2-BTC-SETTLEMENT-DEMAND-BREADTH-SPOT` proposes one future weekly `BTCUSDT` Spot
long-or-cash test based only on jointly broadening confirmed non-coinbase settlement
count and user-paid transaction fees. It excludes price/trend, volatility, flow,
funding/carry, macro/NFCI, hashrate-primary, and active-address-proxy inputs and binds
all retired predecessor families.

The proposed raw source is Google BigQuery public Bitcoin `blocks` and
`transactions`. Coin Metrics community values are excluded as trading inputs due to
the documented non-commercial boundary. All historical target periods are declared
outcome-aware and nonqualifying. Prospective validation is locked from 2026-11-07 to
2027-05-07, future holdout from 2027-05-07 to 2027-11-07, and forward evidence after
2027-11-07.

Charter/audit hashes:
`77e61e9f01519d6b7b56aa2ce45d4689356120bb1a338ead9edce35ef18fe9b0` /
`88e82b6c0169e6e9f3f645cfadeeb8e3aac797f002e5c5f88cae9fe863746745`.
Seven focused charter tests pass. Blockchain values, market values, parameters,
returns, candidates, executions, and orders remain zero.

Exact resume point:
`AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY`. The next stage may
inspect dataset/table metadata and use bounded BigQuery dry runs to establish schema,
coverage, bytes processed, authentication, and zero-dollar cost controls. It may not
run numeric queries or acquire payloads. Pine, paper, Testnet strategy orders,
production, live, and real-capital authority remain false. Real net profit remains
`$0`. See `docs/42_S2_ONCHAIN_SETTLEMENT_DEMAND.md`.

## S2 BigQuery Feasibility Addendum (Latest)

Checkpoint: `2026-08-27`.

The S2 BigQuery metadata/dry-run protocol was frozen and independently reconstructed
before network access. Protocol/audit hashes:
`9e91ba7e6d8b388e4873ccd255336577ae1f2c900e3c88f35df6abc6a09720f0` /
`e952ebf625acad59909c506d1fe4e1683c4580d61ae4203858770ca86dcb25d0`.
Eight focused feasibility tests passed before the one-shot preflight.

The run spent exactly three metadata attempts against the frozen public BigQuery
dataset, blocks-table, and transactions-table endpoints. All three returned HTTP
`401` without authentication. The workstation has neither `gcloud` nor `bq`, no
active Cloud project is configured, and the required no-billing BigQuery sandbox
boundary cannot yet be verified. No metadata response body was accepted as evidence,
and no dry run, query execution, result row, blockchain value, market value, payload,
parameter, return, candidate, or order occurred.

Result/audit hashes:
`8986a9ed6b41af03e6ba7fe72054138362a04ee3f1eae6b1278656b1b56df9f1` /
`1c4bcf38b0484495a069b050a404c3e5135bd1fb748097dced37c3d78aa68b38`.
Decision: `BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE`. Exact artifact next
authorization: `NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES`.

Resume only after the operator creates or selects a BigQuery sandbox project without
a billing account, installs Google Cloud CLI, authenticates locally, and confirms an
active project. Aurex must then freeze a v2 feasibility amendment before retrying;
the consumed v1 attempts cannot be silently reused. Numeric queries, payloads, Pine,
paper, Testnet strategy orders, production, live, and real capital remain forbidden.
Real net profit remains `$0`.

## S2 Authenticated BigQuery Amendment Addendum (Latest)

Checkpoint: `2026-08-28`.

The required v2 feasibility amendment is implemented separately from the immutable
v1 code, frozen before authenticated requests, and independently reconstructed.
Protocol/audit hashes:
`0074b2d2594bb5aa5d430e6818218146be244ea57e2386938ebaaf01fc5147a9` /
`1140f679697b1a86757071a4afeb3ceeda120b099fa8e6c374e13e35d009fc19`.
Eighteen focused v1/v2 tests pass, and a post-freeze reconstruction confirms the
builder and protocol still match exactly.

V2 requires, in order: installed pinned clients, active user OAuth, an active Google
Cloud project, and a verified project without billing. Only then may it request one
access token in memory, make three authenticated metadata requests against the exact
public Bitcoin dataset/tables, and submit at most two CLI dry-runs. Account and
project identifiers, credentials, and tokens cannot enter evidence artifacts.

V2 has made `0` requests. Google OAuth remains incomplete and no active project is
selected. Exact resume point: the operator approves the official Google Cloud CLI
OAuth flow and selects or creates a BigQuery sandbox project without billing; Aurex
then runs and audits v2 once. No numeric query, row result, blockchain value, market
value, payload, parameter, return, candidate, signal, Pine action, paper order,
Testnet strategy order, production action, live action, real capital, or profit is
authorized. Real net profit remains `$0`.

Runtime readiness must be regenerated and independently audited after this
hash-bound control addendum is finalized. The immutable file selected by
`READINESS_CURRENT_PATH` is authoritative for the current result hash. The expected
truth remains 14/15 PASS, 1 downstream PARTIAL, 0 FAIL, zero qualified strategies,
and all execution modes locked.

## S2 Authenticated Result And REST Amendment Addendum (Latest)

Checkpoint: `2026-08-28`.

The operator completed Google user OAuth and established a BigQuery sandbox project
without billing. The consumed v2 run verified the local clients, active identity,
active project, no-billing boundary, and all three authenticated metadata targets.
The dataset, blocks table, and transactions table metadata artifacts passed exact
reference and required-schema checks. The first `bq` CLI dry run then returned an
opaque `API_ERROR`; v2 stopped before its second dry run as preregistered.

V2 result/audit hashes:
`089ee28f60c72d83004377994e46cfaabcba099f9ef153bb2de90c3f8af08ee4` /
`7b304e64033f49eb53b36b67d6012a5a44d841ed0d8821824da390215a50fedb`.
Decision: `BLOCK_S2_BIGQUERY_V2_DRY_RUN_FAILED`. The failure remains immutable and
was not retried or rewritten.

Because local diagnostics showed no billing, permission, API-enable, syntax,
location, or quota signature, Aurex froze a v3 amendment that changed only the dry-
run transport from `bq` CLI to BigQuery `jobs.insert` REST dry runs. V3 binds eight
exact v2 sources, reuses the three audited metadata artifacts, permits one in-memory
token request and at most two ordered dry runs, and forbids raw REST response,
identifier, token, row, value, or outcome persistence.

V3 protocol/audit hashes:
`4f9a3d295667eb97e5c7a08631c3c04e4eb16d1e2587e2d7375771258f268b30` /
`ebf0b1a1d1814ec271aa29c0297f087ce2e128b2ddc7c533791fa0a7c54923c4`.
Both ordered REST dry runs returned HTTP `200`. The causal-six-confirmation query
estimated `46,852,212,436` processed bytes and the development weekly aggregate
estimated `35,482,429,700` processed bytes. No query executed, no row returned, and
no raw response body was retained.

V3 result/audit hashes:
`54daa95943ab19e10fb540a4cc71a70217cb409a21ff7fb804b60386a98e0690` /
`054c85503c88f62c27bf8e6f1b1c691a9a07215e59f4c7588576eac3ac7aef66`.
Decision: `PASS_S2_BIGQUERY_REST_DRY_RUN`. Exact next authorization:
`AUTHORIZE_S2_SOURCE_PAYLOAD_PROTOCOL_ONLY`.

The next step is protocol work, not a numeric query: freeze and independently audit
the exact payload request, byte ceiling, cost ceiling, point-in-time extraction,
raw-response handling, validation rules, and failure policy. Parameters, returns,
candidate qualification, signals, Pine, paper, Testnet strategy orders, production,
live trading, and real capital remain unauthorized. Qualified strategies remain
zero and real net profit remains `$0`.

Runtime readiness must now use
`aurex_strategy_factory_readiness_current_result_v18.json`. Expected runtime state:
`S2_SOURCE_PAYLOAD_PROTOCOL_REQUIRED`, active checkpoint
`S2_BIGQUERY_V3_FEASIBILITY_PASSED`, 14/15 PASS, one downstream PARTIAL, zero FAIL,
zero qualified strategies, and every execution mode locked.

## S2 Development Payload Addendum (Latest)

Checkpoint: `2026-08-28`.

The development payload protocol was frozen and independently reconstructed before
the first numeric query. It authorized one bounded, development-only BigQuery
request for exactly 280 Saturday-to-Friday weekly Bitcoin settlement-demand rows
from `2017-08-19` through `2022-12-24`. Each row uses only blocks with the required
sixth-confirmation timestamp before its decision cutoff, and its earliest permitted
execution date is two days after that cutoff. Market prices, parameters, returns,
validation, holdout, signals, and orders remained forbidden. Protocol/audit hashes:
`63d0e0f7c7f456c8ac1015066105cfd2077cdd739ff80afc01f37ebf656868b7` /
`e1c6e4797d8d1f8027f9f7e8f06a87382c285ade70e407eddcd6587a4749f02e`.

The v1 query completed, but Aurex rejected its response before accepting any row or
writing a payload because BigQuery exposed the aggregated transaction fee as
`NUMERIC` while the frozen schema required `INTEGER`. The failed result/failure-
audit hashes are:
`38c151ef24be8987eaa970d1bb0dbb2657ec414b4898e8a1002360185ceda899` /
`2685797df5497fbd709179385d7a1d9e8565698fe04faa42bdcc2b24b9d564e8`.
Decision: `BLOCK_S2_PAYLOAD_VALIDATION_FAILED`. Zero rows and zero payload bytes
were accepted; the failure remains immutable.

A separately frozen v2 amendment changed only the fee aggregate expression by
casting its sum to `INT64`. V2 protocol/audit hashes:
`93d4280e7d852ce5e83b3c3215a67b48c906149e5041ccda08febaedd42131fb` /
`c3fda102a02c5b2fcffe50a7ac14ff25940813e2f64dd8cfaf554ce10bb5d3a4`.
The one-shot v2 query completed in one submission with no polling, processed
`46,852,212,436` bytes under the frozen 60 GB ceiling, and accepted exactly 280
validated rows. The sanitized payload contains no account or project identifier,
credential, token, raw response, market price, return, signal, or order.

V2 result/payload/audit hashes:
`a50c3c69ebfdcabcce5ea9998c5eea60db8ae74756d05fe6b9460564b247094a` /
`fc436388a09ad097829a2edcea4d2789403493a14425b35355a9a50a05eaf070` /
`edc724a48b7cd0f7726ae1cec925bd379738bf78ba152f7077f2a3b3b5ffb719`.
Decision: `PASS_S2_DEVELOPMENT_PAYLOAD_ACQUIRED`. This proves data acquisition and
point-in-time payload integrity only; it does not prove predictive value or a
profitable strategy.

Exact next authorization: `AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`.
The next work is to freeze and independently audit feature definitions,
transformations, missing-data handling, normalization, parameter-search limits,
and development-only measurement rules. No parameters or returns may be computed
before that protocol exists. Validation and holdout remain sealed. Pine, paper,
Testnet strategy orders, production, live trading, and real capital remain locked.
Qualified strategies remain zero and real net profit remains `$0`.

Runtime readiness must now use
`aurex_strategy_factory_readiness_current_result_v19.json`. Expected runtime state:
`S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_REQUIRED`, active checkpoint
`S2_DEVELOPMENT_PAYLOAD_V2_PASSED`, 14/15 PASS, one downstream PARTIAL, zero FAIL,
zero qualified strategies, and every execution mode locked.

## S2 Development Measurement Protocol Addendum (Latest)

Checkpoint: `2026-08-30`.

The S2 measurement protocol was frozen and independently reconstructed before any
payload numeric row was parsed. It binds 15 predecessor artifacts, including the
immutable v1 payload schema failure, passed v2 payload, and exact 94,662-byte payload
file. Protocol/audit hashes:
`dedb2d9a0fb23d6a943d290c36333107adf3ef873754d2b8572ac3692377a17b` /
`3a72c31dd90db8aa0b307972e70f33b7a3b0909956888c3052666343462edd0e`.

The frozen measurement is one current-four-week versus immediately-prior-four-week
family. It defines exact integer sums for confirmed non-coinbase transaction count
and confirmed fee satoshis, deterministic 28-digit Decimal growth in parts per
million with half-even rounding, and one descriptive agreement category:
`BOTH_BROADENING`, `BOTH_CONTRACTING`, or `FLAT_OR_MIXED`. Seven warmup rows imply
273 measurement rows from the 280-row development payload. Missing, duplicate,
noncausal, ambiguous, or nonpositive-denominator input rejects the entire run. No
imputation, clipping, winsorization, rank, z-score, or outcome-fitted normalization
is permitted.

Future research degrees of freedom are capped at one strategy family, one candidate,
and one parameter combination with no outcome-driven search. The protocol itself
defines zero strategy parameters and zero strategy rules. It parsed zero payload
value rows and read zero market values, returns, validation values, holdout values,
signals, or orders.

Decision: `FREEZE_S2_DEVELOPMENT_MEASUREMENT_PROTOCOL`. Exact next authorization:
`AUTHORIZE_S2_DEVELOPMENT_MEASUREMENT_RUNNER_IMPLEMENTATION_ONLY`. The next step may
implement deterministic measurement construction and freeze a separate execution
addendum. It may not read payload values or calculate measurements until that runner
and execution authority are independently tested and frozen. Prices, parameters,
returns, Pine, paper, Testnet strategy orders, production, live trading, and real
capital remain locked. Qualified strategies remain zero and real net profit remains
`$0`.

Runtime readiness must now use
`aurex_strategy_factory_readiness_current_result_v20.json`. Expected runtime state:
`S2_DEVELOPMENT_MEASUREMENT_RUNNER_REQUIRED`, active checkpoint
`S2_DEVELOPMENT_MEASUREMENT_PROTOCOL_PASSED`, 14/15 PASS, one downstream PARTIAL,
zero FAIL, zero qualified strategies, and every execution mode locked.

## S2 Development Measurement Result Addendum (Latest)

Checkpoint: `2026-08-30`.

The deterministic measurement runner passed synthetic tests for half-even PPM
arithmetic, causal current/prior four-week windows, strict agreement categories,
invalid denominators, row consistency, deterministic JSONL, and authority boundaries.
Before any real payload value was parsed, Aurex froze and independently reconstructed
a one-shot execution addendum. Addendum/audit hashes:
`2f7522cb652d888d8494a2552a01f2b6b20412e442544e978f429b070218b0d7` /
`9176539c110987c109c709d8d9b59c97b1472f5ec5ba8a274262deccfe6b544b`.

The authorized run read the exact audited 280-row on-chain payload and produced 273
measurement rows, sequences 8 through 280, in a deterministic 130,754-byte JSONL
dataset. Dataset file SHA-256:
`513237db0a939170efb2113444fdd633a5c5dc1b397b8022b154020cfdf4b327`.
Result evidence hash:
`8e4534468b2f471b56e4b7d3391a08f1299b6d0079c8fc4b3ae4880630977f3b`.
The independent result audit recomputed every row and reproduced the dataset byte
for byte. Audit evidence hash:
`3af9c1b2332932f6064fe9ccc1172b888e14abe53cd529abcd4c0c930e913523`.

Decision: `PASS_S2_DEVELOPMENT_MEASUREMENT_CONSTRUCTION`. This is a verified feature
construction result, not evidence of predictiveness. It used zero market values,
defined zero strategy parameters, calculated zero returns, created zero candidates
or signals, and submitted zero orders. Validation and holdout remain sealed.

Exact next authorization:
`AUTHORIZE_S2_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY`. The next protocol
must freeze the one permitted long-or-cash candidate, its rule, execution timing,
market-data source, cost assumptions, falsification gates, and development-only
evaluation contract before any BTC market value or return is read. Outcome-driven
parameter search is forbidden. Pine, paper, Testnet strategy orders, production,
live trading, and real capital remain locked. Qualified strategies remain zero and
real net profit remains `$0`.

Runtime readiness must now use
`aurex_strategy_factory_readiness_current_result_v21.json`. Expected runtime state:
`S2_STRATEGY_PREREGISTRATION_PROTOCOL_REQUIRED`, active checkpoint
`S2_DEVELOPMENT_MEASUREMENT_RESULT_PASSED`, 14/15 PASS, one downstream PARTIAL, zero
FAIL, zero qualified strategies, and every execution mode locked.

## S2 Strategy Preregistration Addendum (Latest)

Checkpoint: `2026-08-30`.

Before reading any BTC market value, Aurex froze and independently reconstructed the
single S2 development candidate. Protocol/audit hashes:
`5d6cd308ad31cfc22588760c8890b97d49bcce95682bcb563397fe19acfa7a6c` /
`d71184f3b0bd674f8a55750c174e01a23c9d76c7882d4d6c111c37ff92aa67c9`.
The freeze hashed the 130,754-byte measurement dataset but parsed zero measurement
rows and read zero BTC prices or returns.

The only candidate is `S2-C1-SETTLEMENT-DEMAND-BREADTH-PRIMARY`: long 1x BTCUSDT
Spot only when `settlement_demand_agreement == BOTH_BROADENING`, otherwise cash.
There are zero parameters, one parameter combination, no diagnostic candidates, and
no rescue or post-outcome tuning. Signals 8 through 279 are scored at exact Monday
00:00 UTC Binance 1h opens; sequence 280 supplies the terminal price, producing 272
weekly intervals. Position changes alone incur fills. Base cost is 15 bps per fill;
stress cost is 22.5 bps.

Fifteen frozen development gates cover interval count, transitions, exposure,
base/stress net return, profit factor, drawdown, positive calendar years, stationary
bootstrap lower bound, stress Sharpe, Calmar, and drawdown versus buy-and-hold.
Failure retires S2 without rescue. Development remains nonqualifying; historical
screen, prospective validation, and holdout remain sealed.

Exact next authorization:
`AUTHORIZE_S2_BTCUSDT_MONDAY_1H_SOURCE_ACQUISITION_PROTOCOL_ONLY`. The next step may
freeze a checksum-bound protocol for the 273 required daily Binance 1h archives from
`2017-10-16` through `2023-01-02`. No network acquisition, market-value read, return,
backtest, Pine, paper, Testnet strategy order, production, live trade, or real capital
is authorized yet. Qualified strategies remain zero and real net profit remains `$0`.

Runtime readiness must now use
`aurex_strategy_factory_readiness_current_result_v22.json`. Expected runtime state:
`S2_BTC_SOURCE_ACQUISITION_PROTOCOL_REQUIRED`, active checkpoint
`S2_STRATEGY_PREREGISTRATION_PASSED`, 14/15 PASS, one downstream PARTIAL, zero FAIL,
zero qualified strategies, and every execution mode locked.

## S2 Development Backtest Terminal Addendum (Latest)

Checkpoint: `2026-08-30`.

Aurex froze and independently audited a 273-target Binance Vision source protocol
before reading BTC prices. The bounded runner then downloaded exactly the required
BTCUSDT Spot Monday 00:00 UTC 1h opens from `2017-10-16` through `2023-01-02`.
All 273 targets passed published-checksum, safe-archive, exact-timestamp, schema,
chronology, and request-marker reconciliation gates. The run made 546 requests,
persisted 458,327 source bytes, produced a 173,031-byte price dataset, calculated
zero returns, and submitted zero orders.

Source protocol/audit hashes:
`a8d07b3ff6395ad5d08b9c50638c6d1b01453073d9392000d8583fd2be5b5610` /
`362ab972301087a05635b7cc43ec929c0b0dca1e2b8d76de7e725ad2ee0f7eb4`.
Source execution-contract/audit hashes:
`6cb6e05dd7321970403c918eaf26037014a895ab7b96aefb11da977098311b13` /
`9b368e2419b8bbe45e65e5f1054a4f3c104cfb0e7227ce8de043fc43b90ba0ce`.
Source result/dataset/audit hashes:
`6ba8c88d62c92f36696032f4fbd7697cf43369e1ace4050cf109086dcd76f3cd` /
`6c9c09c8b6a4c484f64a366a8b66a1e939d198894117f9f91b01ea12024af156` /
`8b2e6ec3aa26ea0e282051fd76a157550750c92c9d88fd1ba058e219c7d1db10`.

Before calculating any return, Aurex separately froze and audited the exact 272-
interval arithmetic, base/stress costs, annual assignment, 10,000-resample
stationary bootstrap, buy-and-hold comparison, and all 15 preregistered development
gates. Protocol/audit hashes:
`c2f105dd9d350c0a45c2d00b29bf6e744b5dac75edb9bd8cc8aa3f7f1e8f8be8` /
`2f728ce14b96901460ce1097d6346c947febb1b8d8af97b355dd207a963bc965`.
Execution-contract/audit hashes:
`e954fd8d487117c8ab649bdac5bf1241040c28a8d5007c99dbbda9d967ec784f` /
`4056d01cee712598b2e3453d580b29cb98af1876e6b0b6dad6774c0bbde9a95e`.

The one permitted candidate returned `+12.0634726023%` net at base cost and
`+9.0727083639%` under stress, but passed only 9 of 15 gates. It failed base profit
factor (`1.0274819937 < 1.10`), base maximum drawdown (`70.7740% > 25%`), stress
maximum drawdown (`70.9273% > 27%`), positive full calendar years (`2 < 3`), the
stress bootstrap lower mean weekly return (`-0.4543001949% < 0`), and base Calmar
(`0.0311030531 < 0.50`). A positive total return therefore does not establish a
durable or capital-acceptable edge.

Result/ledger/audit hashes:
`a9661515cbbb584ceaa8894c250f31916d8e35e9e67ea4670b21226c9a99eb54` /
`792a9abe0fa57e3e69af2532a0489eb918733547da66716b9b567d644e23e984` /
`c59985486e9ccc46191161f9e42d9b7b9a3ae11482720d51fe42ef45d16d0e86`.
The independent audit reparsed 273 measurement rows and 273 price rows, reconstructed
all 272 intervals exactly, and confirmed zero orders.

Terminal decision: `STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2`. Exact S2 lineage
authorization: `NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2`. S2 must not be
tuned, rescued, relabeled, or advanced to historical screening, validation,
holdout, Pine, paper, Testnet strategy orders, production, or live use.

The strategy factory remains platform-ready for research but has zero qualified or
enable-eligible strategies. Real net profit remains `$0`; all execution modes remain
locked. The only program-level next action is to freeze and independently audit a
distinct S3 economic-mechanism charter that does not reuse or tune S2. Runtime
readiness must use `aurex_strategy_factory_readiness_current_result_v23.json` and
report `S2_DEVELOPMENT_BACKTEST_FAILED_RETIRED` with the terminal checkpoint verified.

## S3 CFTC Positioning Charter Addendum (Latest)

Checkpoint: `2026-08-30`.

Aurex selected one genuinely distinct successor mechanism after the terminal S2
failure: weekly changes in CFTC-reported leveraged-money net positioning in CME
Bitcoin futures, expressed only as a future BTCUSDT Spot long-or-cash research
candidate. This is a regulated-participant-positioning hypothesis, not on-chain
demand, candle behavior, volatility, funding, order flow, basis, or macro reuse.

The charter binds 12 immutable predecessor artifacts, records 10 exhausted mechanism
families, and cites six official CFTC source pages plus two additional peer-reviewed
studies. Charter/audit hashes:
`2cf73ead1b04999c3b5f9f818bb60d18ad96d2041fae2d65d77084aa88e4802a` /
`f746adc212d5e41f66507a372d60824bdb84609e50b05e797a6116b60d39c90b`.

The favorable published leveraged-money timing result over 2018 through July 2021
is explicitly declared outcome contamination. That published rule and period cannot
qualify S3. Development begins in 2022 and remains outcome-aware and nonqualifying;
prospective validation remains locked from `2026-11-07` through `2027-05-07`, with
the separate holdout locked through `2027-11-07`.

No CFTC position value or BTC market value was read. No parameter, return, candidate,
signal, execution, or order was created. Qualified and enable-eligible strategy
counts remain zero; every execution mode remains false and real net profit remains
`$0`.

Decision: `FREEZE_S3_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY`. The sole next
authorization is
`AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY`.
The next protocol may inspect official source metadata, release calendars, historical
publication timing, revision identity, contract-code continuity, and zero-dollar
reuse terms only. It must not access CFTC position values, BTC prices, parameters,
returns, historical-screen outcomes, validation, holdout, Pine, paper, Testnet
strategy orders, production, or live execution. Failure of any source-feasibility
gate stops S3 before numeric position data.

Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v24.json`, report
`S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED`, and verify checkpoint
`S3_CFTC_POSITIONING_CHARTER_PASSED`.

## S3 CFTC Source-Feasibility Terminal Addendum (Latest)

Checkpoint: `2026-08-31`.

Aurex froze the S3 point-in-time source-feasibility protocol before making any
metadata request or reading any CFTC position value. Protocol/audit hashes:
`1d9e2b672b754c3e6d7296fc3c75fd8d7ab4f49e445b06383ec4e1722271c15a` /
`bbea600436e66ee35e809a323c0f83bdbdfe948e352c4f2f4fa1add03999d7c1`.
The protocol allowed three bounded official CFTC metadata-page requests only. It
forbade target position rows and values, BTC market values, payload acquisition,
parameters, returns, historical screening, validation, holdout, paper, Testnet
strategy orders, production, and live execution.

The first run inside the restricted network environment produced three
`NETWORK_ERROR` attempts, HTTP status zero, and no response artifact. Result hash:
`75700f67e97577d7680b97b6bedf28539c9815eb1bf424764d30094b73fe53d8`.
Because no CFTC response was received, Aurex rejected the result's nominal source-
failure interpretation as a transport failure. Transport-failure audit hash:
`704373d76fc38d794ef43b96b6ad9d13b3839ec65b11a2394e584ceceb34cef5`.

A one-run transport-only amendment was then frozen and independently audited. It
changed no URL, text token, source gate, or data authority and retained the exact
three-request ceiling. Amendment/audit hashes:
`dc3b2acdf29878250a28edb5f951b04b09e78e5f96110798f28f187fe8a2dda9` /
`dcd641b6febf4d93546f79f8113a8d5c3409d0b5984c6faf150f86913e30ffc6`.

The authorized external-network rerun exited with code `1` and exact terminal
message `S3 transport v2 did not receive all three responses; no v2 result was
written`. Filesystem verification found no v2 result and zero persisted response
artifacts. The exact count of successful in-memory responses is unknowable because
the runner did not persist partial attempts; Aurex records it as
`UNKNOWN_NOT_PERSISTED` rather than inventing a value. Execution receipt/audit
hashes:
`166e3039f51e95046ab2030eeee383e5d9cdfaa046e9fffe366b636dfc5e7d23` /
`915cc64207adb02e77efb31fb693db1970e0be612b89b51e227be8d7368bfba2`.

Terminal decision:
`RETIRE_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL`.
This means the required point-in-time source standard was not established within
the frozen and authorized acquisition path. It does not prove that CFTC data is
impossible to source, and it provides no evidence for or against predictive edge.
The one rerun authority is exhausted; S3 may not be retried, loosened, rescued,
backtested, or promoted.

No CFTC position value, BTC market value, parameter, return, candidate, signal,
execution, or order was created. Qualified and enable-eligible strategy counts
remain zero, all execution modes remain false, and real net profit remains `$0`.
The sole next authorization is
`FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY`. S4 must be economically and
informationally distinct from S1, S2, S3, and all other exhausted families; it may
not reuse the failed S3 source path or inspect outcomes before its charter is
frozen.

Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v25.json`, report
`S3_CFTC_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRED`, verify the same terminal
checkpoint, and expose only the distinct-S4-charter authorization.

## S4 U.S. Spot Bitcoin ETP Charter Addendum (Latest)

Checkpoint: `2026-08-31`.

Aurex selected one distinct S4 research mechanism after S3's terminal source-
feasibility retirement: aggregate primary-market net creation and redemption
pressure across the complete U.S. spot Bitcoin ETP universe, with cross-fund
breadth, expressed only as a future BTCUSDT Spot long-or-cash candidate. This is an
authorized-participant, sponsor, and regulated-allocator mechanism. It does not use
price patterns, volatility, order flow, funding, basis, macro, Bitcoin on-chain
activity, options, CFTC positioning, or ETP secondary-market volume or price.

The frozen charter binds 20 predecessor artifacts, declares all 11 exhausted
mechanism families, cites eight official SEC, issuer, and SEC-filing sources, and
defines six contiguous partitions. Charter/audit hashes:
`8827763c7b1d71255ceff1859c0e69835403c7653ead6ad6f233edae5b9c08b4` /
`1e083ef726bfb46cb1d37f15b5c9c16b00562a3c2923a8b0907749ebd7bffbc7`.

The causal design must distinguish the original cash-only creation/redemption
regime from the SEC's `2025-07-29` in-kind authorization and prove each fund's
actual operational effective date. It must reconstruct the complete fund universe,
first-trade and closure history, shares outstanding, Bitcoin-per-share or holdings,
publication timing, creation basket changes, fees, splits, mergers, and non-creation
holding changes without survivorship or look-ahead bias.

Official source inspection incidentally exposed the field names
`BITCOIN_QUANTITY_HELD`, `NET_ASSET_VALUE`,
`SHARES_CREATED_OR_REDEEMED_ANNUAL_TOTAL`, and `SHARES_OUTSTANDING`. Aurex records
that exposure explicitly. It parsed zero ETP time-series rows, acquired zero numeric
payloads, inspected zero BTC market numeric fields, and calculated zero parameters,
returns, candidates, signals, executions, or orders. All available ETP and BTC
history is outcome-aware and cannot qualify S4. Prospective validation remains
locked from `2026-11-07` through `2027-05-07`, followed by a separately locked
holdout through `2027-11-07`.

Decision: `FREEZE_S4_FOR_POINT_IN_TIME_SOURCE_FEASIBILITY_ONLY`. The sole next
authorization is
`AUTHORIZE_S4_ETP_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY`.
That protocol may inspect official metadata, filing identities, publication-timing
markers, universe coverage, regime dates, zero-dollar access, and reuse rights only.
It may not read ETP numeric values, BTC prices, payloads, parameters, returns,
historical-screen outcomes, validation, holdout, Pine, paper, Testnet strategy
orders, production, or live execution. Failure of any source gate must stop S4
before numeric data.

Qualified and enable-eligible strategy counts remain zero. Every execution mode
remains false and real net profit remains `$0`. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v26.json`, report
`S4_ETP_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED`, verify checkpoint
`S4_SPOT_BITCOIN_ETP_CHARTER_PASSED`, and expose only the metadata-feasibility
authorization.

## S4 Source-Protocol Viability Terminal Addendum (Latest)

Checkpoint: `2026-08-31`.

Aurex froze and independently audited the S4 metadata and point-in-time source-
feasibility protocol before making any network request. Protocol/audit hashes:
`6c0415149eabf9c22c60854a35b563a26b68b2746899cd53a17e08fac79883bd` /
`68f6ef9529dbd8f2a62fc690dd4c29cb699994149a3b84aafb0ff0e4ab70a258`.
The protocol limited access to five official SEC documentation or identity-catalog
endpoints and up to 32 derived SEC submissions metadata requests. It required every
attempt and partial response to be persisted on every exit, eliminating the unknown
partial-success defect exposed by S3.

Before consuming the one-run authority, an independent reachability review found a
protocol-design contradiction. Six mandatory PASS gates require complete official
issuer data endpoints, daily shares and Bitcoin history descriptors, actual issuer
publication timing, per-fund cash/in-kind operating dates, and reconciliation of
fees, splits, mergers, and non-creation holding changes. The frozen protocol permits
only SEC identity fields while forbidding issuer page bodies, SEC filing bodies, and
XBRL fact endpoints. No allowed response can establish those six facts. A PASS is
therefore logically unreachable regardless of transport success.

Viability review/audit hashes:
`1837ce1e7fb36edeee235d0270043455fa7a3e3e005d183141c6376b4d4f23ff` /
`a656f8a605c1dc1be0d599aa5b74d41ef1dd2f0e7fb073f81b8639b8855b0696`.
The review was reconstructed exactly and confirms zero network requests, unused run
authority, zero ETP rows or values, zero BTC market values, zero parameters,
returns, candidates, signals, executions, and orders.

Decision: `BLOCK_S4_RUN_PROTOCOL_PASS_CONDITION_UNREACHABLE`. This is a protocol-
design failure only. It does not establish that ETP sources are unavailable and it
does not evaluate predictive edge. Running the protocol would spend authority on a
test that cannot pass, so the run and any amendment are blocked. S4 may not advance
to numeric payloads, returns, Pine, paper, Testnet strategy orders, production, or
live execution.

Qualified and enable-eligible strategies remain zero, every execution mode remains
false, and real net profit remains `$0`. The sole next authorization is
`FREEZE_AND_AUDIT_DISTINCT_S5_MECHANISM_CHARTER_ONLY`. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v27.json`, report
`S4_PROTOCOL_DESIGN_INFEASIBLE_RETIRED`, verify the same terminal checkpoint, and
expose only the distinct-S5-charter authorization.

## S5 Bitcoin Core Development-Breadth Source Addendum (Latest)

Checkpoint: `2026-09-01`.

Aurex rejected public-company Bitcoin treasury XBRL before charter because the
standardized crypto-asset accounting and taxonomy history is too recent and
quarterly for a defensible independent sample. It selected one distinct S5 source
and mechanism hypothesis instead: accepted Bitcoin Core development breadth,
peer-reviewed integration continuity, and official release continuity, expressed
only as a future monthly BTCUSDT Spot long-or-cash candidate. This is a software
maintenance and contributor-review mechanism, not a price, volatility, order-flow,
funding, macro, on-chain settlement, derivatives, CFTC, ETP, or corporate-treasury
signal.

The frozen charter binds 28 immutable predecessor artifacts and all 12 exhausted
mechanism families. It records the pre-freeze public Git reachability probe and the
incidental visibility of current aggregate repository statistics while parsing
zero commit-history records, zero GitHub historical API records, and zero repository
history payload bytes. Exact aggregate statistic values are not persisted in the
charter and cannot qualify S5. Charter/audit hashes:
`9e06088399d772ff9136456d01c76f44e1c13a3efbac0f5e0fbf3c218c5e8da0` /
`72e0cbec8030d93339243df94726762eaef6bf407243639e5d119e40346d80e3`.

The charter treats Git author dates as noncausal because Git permits them to be
overridden. Any later measurement must match accepted master evidence to actual
public availability markers, apply a preregistered conservative lag, detect history
rewrites, avoid retroactive mailmap look-ahead, and treat aliases, pseudonyms, bots,
and deleted accounts as explicit uncertainty. Missing or ambiguous evidence must
select cash. All available repository and BTC history is outcome-aware and cannot
qualify S5; prospective validation remains locked from `2026-11-07` through
`2027-05-07`, followed by a separately locked holdout through `2027-11-07`.

The separately frozen metadata protocol corrected S4's design defect by requiring
only facts its allowed sources could actually prove. It permitted exactly one
unauthenticated GitHub repository GET and one credential-free `git ls-remote`
attempt. It prohibited clone, fetch, commit history, pull-request history, release
history, BTC values, parameters, returns, screens, Pine, paper, Testnet strategy
orders, production, and live execution. Protocol/audit hashes:
`62af43c11658ea6f8c887e6a376524cb4b0df3bab3f55f6bb61a589b0ca01fa8` /
`a8d7cbc990eee5e6aa11bef384d443e0af28b368fa054e4cc24b0288fd3f8152`.

Both bounded attempts succeeded. The result verified the canonical public
`bitcoin/bitcoin` repository, `master` default branch, MIT license, exact public Git
refs, matching `HEAD` and `master`, and a zero-dollar unauthenticated API path. All
14 mandatory gates passed. The raw GitHub response and Git output are separately
hash-bound, and the independent result audit reconstructed the decision exactly.
Result/audit hashes:
`b01f9305f3bf82d556444e94cb51b3b71feb49e9c07f9b2fe208c2e0e30c2904` /
`bf569e885c0cf987a39f0a29e7e90fbe6f604d7de36bcaa7914f12a2328eae09`.

Decision: `PASS_S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY`. This establishes a
technically usable metadata path only and does not establish predictive edge. Zero
repository-history records, BTC market values, parameters, returns, candidates,
signals, executions, and orders were created. Qualified and enable-eligible
strategies remain zero, every execution mode remains false, and real net profit
remains `$0`.

The sole next authorization is
`AUTHORIZE_S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_ONLY`. It permits protocol design
only; repository clone/history access remains false until that new protocol is
frozen and audited. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v28.json`, report
`S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_REQUIRED`, verify checkpoint
`S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PASSED`, and expose only the bounded
history-payload-protocol authorization.

## S5 Bitcoin Core History-Payload Correction Addendum (Latest)

Checkpoint: `2026-09-02`.

Aurex froze and independently audited a one-run Bitcoin Core history-payload
protocol before repository history access. The protocol fixed the canonical remote,
`master` branch, source cutoff commit
`dc0395c5858a1d55239b82a834e5075cf2069219`, a bare single-branch tagless
`blob:none` clone, a 2 GB dataset ceiling, and zero semantic history parsing,
GitHub API calls, BTC values, parameters, returns, candidates, or orders.
Protocol/audit hashes:
`e23a6368563bd45908f9e89fa14c15f37778a5ce276908aef5fe363d73b2b2b5` /
`9de05f97359ff82f0fe17f870b623e7c05f0b2dce17f39d7b04c67098a162775`.

The single credential-free clone process succeeded in 61.297 seconds. The v1
verifier then incorrectly treated an intentionally promised missing blob as a
transport failure because its object-list command omitted Git's
`--missing=print` option. The original v1 STOP and audit remain immutable; they
are not relabeled as a PASS. V1 result/audit hashes:
`cdb84ccb79fd4db8e1fb795799a2a16a4fcb14c81c95bb504b38a3956dcbd633` /
`0a2b12f261463e78c5973feeb8b0b709989c40444e2bcbf80a3e2803903381ff`.

Following Aurex's established transport-amendment doctrine, an independent failure
audit verified that the clone itself succeeded, the preserved repository was bare
and non-shallow, origin remained the canonical public Bitcoin Core repository,
promisor mode and `blob:none` were active, the frozen cutoff commit existed, and
the cutoff contained 50,395 commits. It hash-bound all 23 preserved files totaling
77,762,990 bytes and confirmed that zero commit messages, author identities,
timestamps, pull-request identifiers, BTC values, returns, or orders were read.
Failure-audit hash:
`1216ec25104c1466ebaa9e5fa637a75136a46b718a048e6e10da267b844dadfe`.

The v2 amendment allowed exactly one local revalidation and zero additional
network processes. It changed only the object enumeration from
`git rev-list --objects --no-object-names <cutoff>` to
`git rev-list --objects --no-object-names --missing=print <cutoff>`. The source
cutoff, 14 gate identifiers, byte limits, semantic prohibitions, and every trading
lock remained unchanged. Amendment/audit hashes:
`ad78b4587f081bc71143f83fc581385eee0266228f87578f84a8eb03e9abdf84` /
`4e84f6e60c23dc886859e38c7be29084e859b894a4703af61fbe8ec3ed811c82`.

The corrected local verifier and its independent full reconstruction both passed
all 14 gates. The finalized immutable payload contains 23 files and 77,762,990
bytes. At the frozen cutoff it contains 50,395 commits and 320,247 reachable object
identifiers, including 116,360 question-mark-prefixed promised missing blob
identifiers. Those counts and hashes are integrity evidence only. No commit message,
author identity, timestamp, pull-request identifier, release record, BTC market
value, parameter, return, candidate, signal, execution, or order was parsed or
created. V2 result/audit hashes:
`0725c5080e6940290bde9134ac297d7c073013b7392219ec9f9ce9f1fd608bbb` /
`93d8b2285c0865f63cc626424c47fc4aa508d8e5cd6b717128093971cee45efa`.

Decision: `PASS_S5_BITCOIN_CORE_HISTORY_PAYLOAD`. This proves only that Aurex has a
canonical, cutoff-bound, independently audited Git history payload. It does not
establish measurement completeness, point-in-time pull-request availability,
predictive edge, a reliable signal, or profit. Qualified and enable-eligible
strategy counts remain zero, every execution mode remains false, and real net
profit remains `$0`.

The sole next authorization is
`AUTHORIZE_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_ONLY`. That next
protocol may inspect accepted merge topology and opaque pull-request identifiers
only to determine history completeness and the exact official GitHub metadata
request budget. It may not access BTC values, define parameters, calculate returns,
create a candidate, or submit an order. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v29.json`, report
`S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_REQUIRED`, verify checkpoint
`S5_BITCOIN_CORE_HISTORY_PAYLOAD_PASSED`, and expose only the completeness-census
protocol authorization.

## S5 Bitcoin Core History-Completeness Census Addendum (Latest)

Checkpoint: `2026-09-02`.

Aurex froze and independently audited a one-run, local-only history-completeness
census before opening commit messages. The protocol bound the corrected history
payload, both corrected-history audits, readiness v29, the exact source cutoff, and
two deterministic pull-request patterns. It permitted exactly two local Git
processes: a first-parent commit enumeration and one batch commit-object read. It
prohibited network access, repository fetch, GitHub API requests, author and
committer parsing, timestamp parsing, BTC values, parameters, returns, candidates,
and orders. Protocol/audit hashes:
`2dc3d2a7fb4696881b3c82d024b8e96f420c0676e2d2b0f0f55cc7a0f9c6c0ba` /
`e484d4c319e0e2a0774009c7b12ba6ec333c0b64c5f189e111809d99f66fe95e`.

The census and its independent full reconstruction passed all 13 gates. The
first-parent stream contains 17,543 commits: one root, 821 single-parent commits,
and 16,721 two-parent merges. The two frozen first-line patterns recognized 7,961
unique pull-request IDs with zero duplicate references. Of those, 6,570 use the
Bitcoin Core maintainer merge form and 1,391 use GitHub's default pull-merge form.
The remaining 8,760 merge messages are unrecognized under the frozen patterns and
are hash-covered. Only the first 25 diagnostics were persisted; those earliest
samples are SVN synchronization merges. This observation does not prove that all
later unrecognized merges have the same cause.

The exact direct-endpoint budget is 7,961 requests. Under GitHub's official current
primary limits, that is a lower bound of 133 unauthenticated rate-limit hours or two
authenticated rate-limit hours. A list endpoint allowing at most 100 records per
page has an 80-page mathematical lower bound for the recognized set, but its actual
page count and completeness remain unadjudicated. No GitHub token was present or
used. Census result/audit hashes:
`6596e9e8d4d1c360247642373d387ddd33f08058423ddf30f1f8817f2cc977dd` /
`829eb1701cac6552f38578fefbd649c54d2267c57b5cec272a5a559c9ab369f0`.

Decision: `PASS_S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS`. This establishes a
reproducible history inventory and an exact direct-request budget only. It does not
establish source completeness, historical point-in-time availability, predictive
edge, a reliable signal, or profit. Qualified and enable-eligible strategies remain
zero, every execution mode remains false, and real net profit remains `$0`.

The sole next authorization is
`AUTHORIZE_S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_ONLY`. That decision
must choose or reject an official, resumable, rate-limit-aware metadata path before
any request executes. It may not access BTC values, define parameters, calculate
returns, create a candidate, or submit an order. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v30.json`, report
`S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_REQUIRED`, verify checkpoint
`S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PASSED`, and expose only the metadata
transport-decision authorization.

## S5 GitHub Pull-Request Transport Decision Addendum (Latest)

Checkpoint: `2026-09-02`.

Aurex evaluated five transport paths without executing a metadata request. Direct
pull lookup was rejected because 7,961 requests require at least 133
unauthenticated rate-limit hours and cannot discover pull requests missed by the
two frozen merge-message patterns. GraphQL was rejected because it requires
authentication that is not approved or present. Local Git alone was rejected
because it cannot establish GitHub's public `merged_at` field. Third-party archives
were rejected because they are outside the charter's authoritative source set.

The selected transport is GitHub's official REST pull-list endpoint, filtered to
closed pull requests targeting `master`, sorted by creation time ascending. GitHub
documents a maximum of 100 records per page, but the actual matching record count
is not known and no bulk request budget has been authorized. The next protocol may
make one page-one request with `per_page=1`; its terminal `Link` page can reveal the
exact record count before bulk acquisition is designed. All 12 decision gates
passed. Decision/audit hashes:
`6d271dd3095439538aa97c9dc67c5ea60cd98994767422c23e73417ba310a3e2` /
`a081dfa9cc92d7f0d1f078eadf057513ea0b4aa757e316b74650f3df38449535`.

This decision does not prove endpoint availability, schema stability, pagination
completeness, historical record preservation, source completeness, predictive
edge, or profit. It executed zero GitHub API requests and parsed zero metadata
records. Qualified and enable-eligible strategies remain zero, every execution
mode remains false, and real net profit remains `$0`.

The sole next authorization is
`FREEZE_S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_ONLY`. The preflight
protocol must bind the exact request, headers, byte and time limits, redirect
policy, response preservation, pagination parser, rate-limit checks, and terminal
failure behavior before the one request executes. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v31.json`, report
`S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_REQUIRED`, verify checkpoint
`S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_SELECTED`, and expose only the preflight
protocol authorization.

## S5 GitHub Metadata Preflight Correction Addendum (Latest)

Checkpoint: `2026-09-02`.

Aurex froze and independently audited a one-request, unauthenticated GitHub REST
preflight protocol before any pull-request bulk acquisition. It fixed the closed,
`master`, creation-time-ascending query, one-record response, exact headers, a 1 MB
response ceiling, no redirects, no retries, no environment proxy, and zero token
access. Protocol/audit hashes:
`b711d7010c0a549bd699712a1b6605b8b77a4836516f66a98a5b077d7293e41d` /
`c03407225007c4b15ed917953255881a88353576545e7ddc2616fb26ac8353e5`.

The single request returned HTTP 200, exactly one record, a 15,733-byte preserved
response, and valid unauthenticated core rate-limit headers. The v1 interpreter
nevertheless stopped because it required GitHub's textual repository path in the
pagination link and a list-level `merge_commit_sha`. GitHub returned its canonical
numeric repository path, `/repositories/1181927/pulls`, and exposed `head.sha`
instead. The immutable v1 STOP and its independent audit remain preserved; they
were not rewritten as a pass. V1 result/audit hashes:
`08984a1bd4f5c01fb1d062a5b5bb6b0cea4a3829b27d06dfab216314b53035e3` /
`f015c24de0ed4dbdd65b49b96ff8bd6aa8e2c7f3ed0ff7917eed56530f8af291`.

The failure audit bound prior official repository metadata proving repository ID
`1181927` is `bitcoin/bitcoin`, classified the event as transport success with a
local interpreter defect, and authorized no request replay. Its hash is
`ffaf4571bafcdac3d4771e59a8a8905178a7e16cf0863b7199dbc7de805bb093`.
The frozen v2 amendment accepted either exact canonical repository path and changed
the future identity rule to match each API `head.sha` against the accepted Git merge
commit's second parent, failing closed on absence or ambiguity. It permitted one
local revalidation and zero additional network requests. Amendment/audit hashes:
`49d5be7ee08ea89e83295cb206f0992681e2d6d559c497b9a34554fea377b3db` /
`50b935b96fb20db2a3f92060a3f739bdf14bcbe11c0e3f314088b841dcdc5224`.

The corrected local result and its independent reconstruction passed all 14 gates.
The preserved pagination link reports 24,012 closed pull requests targeting
`master`, requiring 241 pages at 100 records per page and at least five
unauthenticated rate-limit windows. This is a current endpoint count, not a
completeness conclusion. Corrected result/audit hashes:
`f0ac3019b1d2487d53c6225f4a625609fe36bcd29878b77cc1b6fc9129258ae7` /
`748b61fe787cec5c1554155676e41c3c74400c9946370dfa816b1a759445597d`.

Decision: `PASS_S5_GITHUB_METADATA_PREFLIGHT_LOCAL_CORRECTION`. This proves only
that the official transport, response shape, pagination count, and rate-limit
budget are usable. It does not prove snapshot stability, deleted-record coverage,
source completeness, predictive edge, a reliable signal, or profit. No BTC market
value, parameter, return, candidate, signal, strategy execution, or order was
created. Qualified and enable-eligible strategy counts remain zero, every
execution mode remains false, and real net profit remains `$0`.

The sole next authorization is
`FREEZE_S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_ONLY`. The protocol must be
bounded, resumable, rate-limit-aware, page-hash preserving, and fail closed on
pagination drift, duplicate identity, schema drift, or an incomplete terminal
page. It may not acquire BTC prices, define strategy parameters, calculate returns,
create a signal, or submit an order. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v33.json`, report
`S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_REQUIRED`, verify checkpoint
`S5_GITHUB_METADATA_PREFLIGHT_PASSED_AFTER_LOCAL_CORRECTION`, and expose only the
bulk-acquisition-protocol authorization.

## S5 GitHub Metadata Bulk-Acquisition Addendum (Latest)

Checkpoint: `2026-09-03`.

Aurex froze and independently audited the bounded bulk-acquisition protocol before
opening any pull-request page. To prevent open/closed transitions from changing
page membership, the bulk query uses `state=all`, targets `master`, sorts by
creation time ascending, and applies the original frozen creation cutoff after
capture. It permits at most 300 total request attempts, 300 terminal pages, 4 MiB
per response, 1 GiB in total, one serial request per page, no retries, no redirects,
no environment proxy, no token access, and mandatory rate-limit waits. Protocol and
audit hashes:
`ee1564712af978eddd0081fe7ede7fb19dd275fc2f04e7a19306160f8b3174f5` /
`0643d3dceb5e4bc763fc3f5c551d8bfa3576f5cecac415cda91fbba4f64f4b55`.

The first runner stopped before reading a response because its local httpx usage
treated `Response` as a context manager. The immutable STOP result and failure
audit identify a local implementation defect and preserve the one charged request;
their hashes are
`a3443b57f5cb805cf37daa79cbe561d317a4ede3ca552cccf0675bec97f131f8` /
`7b81b91b39d1960f444764574cc62a4ba159deb65bcf8f394f9d526aa9540738`.
The frozen response-handling amendment changed only the response-stream context and
kept every endpoint, query, gate, limit, and authority unchanged. Amendment and
audit hashes:
`b5788d7ff5c2aa582a228625dd9dcd8dbc2a20a263e598f7b146ae8a683c7499` /
`06d9be9468a63ca72c1c5d3afc82615806405df3ccd57287708738bfd5e4e5fe`.

The corrected v2 process preserved pages 1 through 117, totaling 11,700 records,
then stopped locally after host suspension pushed its elapsed clock beyond the
12-hour bound before page 118 was requested. Result and suspension-audit hashes:
`1ea0cbe722ee25db4b766e3c955f0fcb2b3ff42ef8d91de35894f3e659275f85` /
`925d5edb0a719596977699b8d549ccef4029fe5bdbc3aa3ff184d0f001be1841`.
The v3 contiguous-resume amendment preserved the original cutoff and request
ceiling while allowing a fresh process clock at page 118. Amendment and audit
hashes:
`af1524f5ed40d588878aafb5f09e18b1b1164426ae93c1687b6cf80a42b59ffc` /
`b796a4852668bdce9172a8610cbd3d45ba6a6f7786f8d081546159e78fdea934`.

Page 118 returned HTTP 200 with 100 valid, ordered, identity-disjoint records, but
the endpoint terminal count had grown from 244 to 245. V3 correctly stopped before
canonicalizing the page. The exact cause of the growth is not inferred. The STOP
result and local drift audit hashes are
`6354ab5cdb329a3246a32b02b0cf34cbc5d63ff89aaeee5ef6c2fca277d8a4c5` /
`6ad04a3458c8fe972a0f13d89c3b75c4e546b5b95e3edb260faf75dd1012391d`.
The v4 amendment allowed that preserved response to be promoted with zero new
requests and allowed only nondecreasing terminal growth. Although 300 remains the
protocol's absolute page bound, the 119 already charged requests leave capacity to
complete at most terminal page 299; observing page 300 would require a STOP.
Amendment and audit hashes:
`db23014df1fedcc4562e2ef927da4a77ee08402830c6461f60d3ce004825e187` /
`ed9fe2a2cf7398d8c1110a6a92dd0092b4b667928f34f5eaa62ce10070bbed6b`.

The v4 acquisition completed at terminal page 245. All 245 canonical pages and
their response bodies are hash-bound. They contain 24,407 unique records in
monotonic creation order: 24,398 are on or before the frozen cutoff and nine are
explicitly excluded as post-cutoff. The terminal page contains seven records. All
16 gates passed with zero duplicate pull numbers. Across every attempt, including
the original local failure, the acquisition charged 246 requests. Result and final
independent-audit hashes:
`3c2bd020ee115e0d28e75fc80c977ffef2a4bad8ac6ad4cd5f4219380a25e082` /
`cc1a4604a6d8c2819dd629900374f60cbac7ff50499eb14af34f63c2bc1acc29`.

Decision: `PASS_S5_GITHUB_METADATA_BULK_ACQUISITION`. This proves complete capture
of the bounded current endpoint pages under the frozen protocol. It does not yet
prove Git-to-GitHub merge identity coverage, deleted or retargeted record coverage,
historical publication timing, source completeness, predictive edge, a reliable
signal, or profit. No BTC market value, parameter, return, candidate, strategy
execution, or order was created. Qualified and enable-eligible strategy counts
remain zero, every execution mode remains false, and real net profit remains `$0`.

The sole next authorization is
`FREEZE_S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_ONLY`. That
protocol may normalize the frozen cohort, retain uncertainty fields, match accepted
Git merge second parents to GitHub `head.sha`, and quantify recognized and
unrecognized coverage. It may not read BTC prices, define strategy parameters,
calculate returns, create signals, or submit orders. Runtime readiness must use
`aurex_strategy_factory_readiness_current_result_v34.json`, report
`S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_REQUIRED`, verify
checkpoint `S5_GITHUB_METADATA_BULK_ACQUISITION_PASSED`, and expose only the
normalization-and-completeness protocol authorization.

## S5 GitHub Corrected-Normalization Addendum (Latest)

Checkpoint: `2026-09-08`.

The first frozen normalization stopped after producing 16,167 exact mappings. It
left 554 first-parent merges unresolved and found 112 accepted GitHub pulls without
one canonical first-parent owner. The STOP remains immutable under result hash
`02f461aeb23e00479a9044e7017daa4eaa569f296cd69d8fdbc7dd7e6e6c3a89`.
Independent adjudication established that the one-accepted-pull-per-merge invariant
was false. Two targeted correction implementations then stopped on local execution
or response-shape defects; neither failure was rewritten as success.

The corrected v3 targeted acquisition covered the exact 194-record correction
union, preserved 186 HTTP 200 and eight HTTP 404 responses, and recovered 75 of 83
recognized mappings by exact second-parent-to-`head.sha` identity. Result/audit
hashes:
`e7c059f0a01998e2af13b72c1ee4d5a6c01f05184f79c3b915dac619f08e2d50` /
`5e6c1f1b7dfd5a28395ec28a0f9cfed08ad053203edacaeb38628687c7edacac`.

The corrected normalization protocol separates canonical Git integrations from
accepted GitHub pull events, applies census precedence for canonical ownership,
retains ambiguous many-to-one source links without guessing, and uses GitHub
`merged_at` or a source-labeled Git committer time. Protocol/audit hashes:
`d8a6c5bf331c75a127e47f63c3e2f14c6d3a1292f9015666009da3a1b106bc95` /
`b664ae816c730550f7876aaba41c7090797b848bfdfeaf9c2c0fa420d36fff8c`.
Execution contract/audit hashes:
`9a374dc928e74d3708e587ed5e9eec436225dc560f35d62b036c277a69779477` /
`bec0bd3756616fe3161b74f18318111dc0d9a4bd55365c9af65114f552f8ced6`.

The one authorized run passed all 19 gates. It produced 24,398 normalized pull
rows, 16,242 canonical mappings, 194 target resolutions, 16,279 accepted-source
coverage rows, and 479 unresolved Git merges. Of the accepted GitHub events,
16,271 have a verified local source link and eight remain explicitly unverified.
The result evidence hash is
`a205e0759b235fae0810ae9203afa4dd81087f52ce782cd4e8c00c670fdd45a5`.

An independent auditor rehashed and strictly parsed all 57,592 rows, reran the two
permitted Git reconstructions, and rebuilt all five datasets and the final result
exactly. It made zero network requests and read zero BTC values. Audit evidence
hash: `d0d66d194c6136164999341f5e044bf60d8f2e7b585531a863ba599d54254648`.
The full S5 source-through-normalization unit set passes `129` tests. The detailed
evidence record is `docs/45_S5_BITCOIN_CORE_ACCEPTED_DEVELOPMENT_BREADTH.md`.

Decision: `PASS_S5_GITHUB_CORRECTED_NORMALIZATION`. This proves deterministic
source linkage and explicit uncertainty only. It does not prove a causal relation
to BTC returns, predictive edge, a reliable signal, or profit. Qualified and
enable-eligible strategy counts remain zero, every execution mode remains false,
and real net profit remains `$0`.

The sole next authorization is
`FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`. The protocol must bind
the primary and sensitivity event universes, complete-month availability,
identity and many-to-one uncertainty, release-tag treatment, exact formulas,
resource ceilings, and deterministic serialization before any measurement output
is computed. BTC values, returns, candidates, Pine, paper, Testnet strategy orders,
production, live execution, and real capital remain locked.

## S5 Accepted-Development Measurement Rejection Addendum (Latest)

Checkpoint: `2026-09-08`.

Aurex froze and independently audited a 17-field, 212-month measurement protocol
before parsing any source row. It separates the 16,271 source-verified accepted
pulls, 16,279 all-accepted sensitivity events, and 16,242 canonical first-parent
integrations; applies a seven-day complete-month lag; and preserves identity,
many-to-one, component, release, and timestamp uncertainty. Protocol/audit hashes:
`0d4f9dbc73675a0e625971a9a53181bcd4a2b707ebe02f01a28edfc4c65478d0` /
`0b6ad1358d206822ab530447bc184dfb98ecd12d209e8cd8c2f3675f17c70064`.

The runner and three-process Git execution contract were frozen and audited under
hashes `da08133f957e4129421e5e708b93c87212d4273b3da8bdc1daed5b62e86a0154` /
`68a683dc72b1292131929af5ce1f23ef960bd672d7525bd09afbbaef69ca7c71`.
The one authorized run emitted 212 rows and internally reconciled every primary,
sensitivity, canonical, and unresolved event. Output/result hashes:
`56a54bee72f77102e21c03975eb7a32e95b8eb2ff68882dd32fbe8a01f8bddd8` /
`6d0d3efc7da6dc5d909bea7bca0e892e8ea45c8ab9541c521109d644b85d7c3c`.

The independent result audit did not uphold the nominal PASS. The frozen history
repository has `tagOpt = --no-tags`, one packed master ref, and zero tag refs. Its
zero release counts therefore encode missing source data as observed zero values.
The output remains immutable, but release fields are invalid and non-release fields
have not yet been independently reconstructed from the source inputs. Rejection
audit hash:
`e8b8970a7af07f2298f4b1cf9e53d656c6dc0bcd7396838968ffda915ea5afdd`.

Decision: `REJECT_S5_MEASUREMENT_PASS_RELEASE_TAG_SOURCE_ABSENT`. This is a source-
scope defect, not evidence against Bitcoin Core releases, S5 predictive edge, or
profitability. Qualified strategies remain zero, all execution modes remain false,
and real net profit remains `$0`.

The sole next authorization is
`FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY`. It may design bounded,
credential-free acquisition of official Git tag refs and objects into a new
isolated evidence repository. It may not mutate the frozen source, access BTC
values or returns, create a strategy or signal, or authorize any trading mode.
