# Aurex Implementation Log

Date: 2026-06-05

## Migration Preparation - 2026-11-06 Git Transfer

User redirected work to transferring Aurex to a new machine through GitHub. Updated
ignore rules to preserve source/tests/docs and top-level research JSON/JSONL/Markdown
while excluding local dependencies, secrets, databases, backups and nested payload/
snapshot/result directories. ZIP archives alone total 75.9 GB. Candidate tracked plus
untracked regular files total about 103.3 MB, largest 24.8 MB. Originals were not deleted.

Added byte-preserving attributes (hash-bound evidence must not be EOL-normalized),
missing donor submodule URLs and exports of the existing tracked donor edits under
`migration/donor-patches/`. Both patches passed non-mutating reverse-apply validation.
Untracked Electron cookies/profile files were NOT exported. Preserved the exact active
goal attachment as `migration/ACTIVE_GOAL.txt`; SHA-256:
`6b22909cf1bf3cf68d892d2b4b989069c955403b25fb97e5c336b5c76eb0844e`.

29 transfer-policy tests passed (93.53s), report `.tmp/git_transfer_20261106_v1.xml`;
focused Ruff passed. A limited credential-pattern screen found only a rejection-test
header fixture, not a stored key. This is not a complete secret audit. No commit,
push, remote rewrite, data deletion or operator migration was performed at this entry.
`git add --all` subsequently completed successfully under the reviewed ignore rules.
No commit or push was made. Final index audit verified 1,757 regular files (about
103.3 MB) plus the two pinned donor links, zero ignored tracked paths, zero files
over 30 MiB and zero byte mismatches between working files and indexed Git blobs.
This final checkpoint summary is restaged after that audit.

MIGRATION NEXT: use `docs/50_GIT_MACHINE_MIGRATION.md`. Git is NOT a complete operational
backup: transfer raw/historical evidence, verified database backups and required test
artifacts privately before retiring the old machine. On the new workspace reconcile
the existing v64 verification artifacts with source before resuming Stage 3. This
maintenance step does not establish feed readiness, strategy eligibility or live authority.

## In Progress - 2026-10-11 Managed Native Lifecycle (v64)

Resumed the active goal after the requested goal-text response (no code progress
in that response). Stage 3 continues; v63 is the last combined verified release.
The interrupted lifecycle/dashboard patch landed. Initial backend verification:
18 tests passed in 55.96s, zero failures/errors/skips, retained in
`.tmp/native_lifecycle_v64a_20261011.xml`. This is focused evidence only.

Managed child ownership, pinned launch/config/database/source, no-autostart private
API controls, idempotent start, cooperative stop and terminal-journal audit exist.
Current work adds real child wait/stop/restart proof, logging-failure stop protection,
honest shutdown classification, CLI config checks and rendered control verification.
The v63 source-bound readiness artifacts are historical until a fresh audit is frozen.
The v63 disposable preview stopped cooperatively; recheck actual handles before reuse.
No original operator DB migration, strategy promotion, live authority or feed-readiness
claim. Genuine-feed clock and full-history recovery capacity remain external blockers.
NEXT: run expanded lifecycle/private regressions, verify browser controls on a copy,
then freeze source-bound evidence and continue remaining operational acceptance.

v64b retained `.tmp/native_lifecycle_v64b_20261011.xml`: 91 passed, 1 failed.
Real competing-owner test found the rejected child hung during interpreter exit
while a daemon held stdin's buffered-reader lock. Replaced managed reads with
unbuffered `os.read`; v64c targeted real EOF/stop/restart/second-owner checks all
passed (3 cases, 36.37s), report `.tmp/native_lifecycle_v64c_20261011.xml`.
Added protective stop despite logging/settings failures; no eligibility/risk bypass.
All test children were reaped, including the failed attempt's recorded forced exit.

## Verified - 2026-10-10 Operator Workflow Verification (v63)

LATEST RESUME: this verified entry supersedes pending v63 verification text in the
source-bound docs/10 checkpoint. Stage 3 remains in progress; the entire goal is not
complete. Final combined recovery/native/risk/private/dashboard suite: 189 distinct
tests passed in 182.44s, no failures/errors/skips; independent JUnit identity check
passed. Six Node transport cases passed separately. Repo Ruff and tracked whitespace
checks pass (known Starlette/httpx deprecation and CRLF notices only).

Final browser rehearsal PASSED against verified v63 source/checkpoint evidence:
`.tmp/operator-dashboard-v63-final-20261010/result.json`. All 14 tabs at 1440x1000
and 390x844, zero document overflow/JS errors/real initial HTTP failures, empty equity
state, private runtime, disposable kill protection, four deliberate source failures
and actual backend recovery were checked. Final desktop/mobile screenshots inspected.
This is not every business workflow, genuine feed evidence, or strategy qualification.

Post-browser read-only snapshot comparison confirms paper orders/trades, positions,
signals, native receipts and seeds are unchanged versus the source backup. The original
operator DB SHA-256 still equals `14607fd3a391d676c7b36337c6f4f014a426efe19c5fbbf0f810f28e4f5a938b`.
All foreground test/rehearsal processes completed and all three rehearsal services
stopped cooperatively. A separate one-hour preview is being started on the same
disposable copy at `http://127.0.0.1:8927/dashboard`; it is not operator cutover.
Preview startup VERIFIED by process handle and matching HTTP/journal instance
`67e2f4d5eb6d49afb1a1838d70faaaa3` (launcher PID 16196 at this check). Live authority
and supervisor-start flags are false. This is a one-hour disposable UI preview, not
an unattended trading process. Stop/restart it before further backend changes.
Preview journal/STOP path: `data/backups/operator-ui-20261010-v1/preview-v63/`.
Verify its actual process/listener state before reuse; never infer liveness from logs.

NEXT ACTION: implement owned native-supervisor status/start/stop/restart integration
with authoritative process handles, fixed local paths, exact database/config binding,
bounded cooperative shutdown and rejection of unapproved modes/strategy promotion.
Existing child acquisitions can take up to 90 seconds; private HTTP shutdown allows
30 seconds, so resolve that mismatch explicitly before owning a supervisor. Retain
the no-entry observer route and retired-Jam guard. Verify lifecycle fixtures and UI;
do not retry genuine-feed admission without meaningful clock-state change.
Full-history storage still needs an external destination. Refresh a latest-source
recovery package before final guarded cutover. Live trading remains disabled.

## Implementation Detail - 2026-10-10 Operator Workflow (v62/v63)

Continued after v61 without requesting renewed permission. Bounded dashboard source
reads to four workers, serialized refreshes, added GET deadlines without mutation
retries, cleared stale safety data and disabled unsafe reset/enable affordances.
Added explicit private service/instance/schema status separate from supervisor and
acceptance. Removed synthetic equity curves/bars and arbitrary readiness percentages;
unknown risk is labeled unknown, and a disabled kill switch is no longer called Ready.

Six executable Node transport cases passed. Initial combined dashboard/private/runtime
readiness regression passed 43 cases (74.20s). Browser a failed because the bundled
headless binary was absent; b caught the test's CSS text-case assumption, not a server
failure. Both reports retained. Browser c passed all 14 views at 1440x1000/390x844,
no document overflow, actual disposable kill activation, four injected unavailable
sources, cleared safety state and subsequent real-backend recovery. No real initial
HTTP failures or JS exceptions. Screenshots were inspected; mobile capture caught an
in-progress animation, now disabled for final screenshots.

v63 freezes the final labels/guards and requires source/checkpoint integrity in the
browser driver. Final combined recovery/native/risk/operator regression and exact-source
browser checks subsequently passed as recorded above. Service, DB and browser profiles are disposable/private.
Full-history capacity and real-feed clock remain external blockers. Next dependency:
native supervisor lifecycle/status integration, not strategy promotion or live orders.

## In Progress - 2026-10-10 Restore Receipt Safety (v61)

The preceding user-requested goal-text turn made no implementation progress. Resumed
the active goal, read its attachment and reconciled retained recovery evidence.
The v60 restore and restored-source rehearsal completed successfully: two services
started/stopped, kill state persisted, hostile origins were rejected, and trading
ledger hashes were unchanged. Exact report and limitations are recorded in docs/46.

Review identified a receipt-publication ordering risk in the historical v60 package.
Final readback now precedes publication. Added versioned v2/readback markers and a
launcher guard rejecting legacy, absent, false or non-boolean verification. Added
failed-readback and real-process launcher rejection tests. Verification pending.
Continue operator workflow work after the focused correction/source audit; no operator
migration, strategy activation, public exposure or live authority is granted.

v61 final verification: 98 distinct recovery/private-runtime/readiness tests passed
in 263.69s, zero failures/errors/skips; independent JUnit count passed. Source result
and reconstruction: 14 PASS / 1 PARTIAL / 0 FAIL, still capability-only. Continued
Stage 3 into dashboard request bounds, stale readiness handling, honest chart empty
states and private service status. Browser rehearsal uses a new 0031 restored copy
at `data/backups/operator-ui-20261010-v1/aurex.db`, never the operator database.

## In Progress - 2026-10-10 Application Recovery (v60)

Previous goal turn classified as progress: v59 implementation and real copy-only
service restart passed, with 145 distinct combined tests. Continued Stage 3 recovery.
Added scoped source/evidence/config bundles, per-file content verification, safe
new-tree restore, explicit raw-archive omission inventory and snapshot integration.
Added pinned binary wheel escrow, hash-locked offline installation and a restored-source
service rehearsal. Initial bundle tests: 24 passed (39.47s); combined bundle/dependency
contract tests: 35 passed (20.03s), counts overlap. Expanded tests and real recovery
evidence follow in docs/46. Thirty-nine installed-version wheels downloaded successfully.

Full-evidence capacity preflight is blocked: 158,297,787,786 bytes required versus
79,915,769,856 available. Operator was asked for a separate destination with >=160 GB
free. No archives were deleted or bought storage. Operational scope explicitly excludes
6,827 ZIP/partial files totaling 76,175,685,917 bytes; it does not close full-history
recovery. Continue independent offline install, operational restore and UI work.
Clock synchronization remains a separate external genuine-feed blocker.

v60 verification update: final combined regression passed 182 distinct tests in
288.73s, zero failures/errors/skips; independent JUnit count/identity check passed.
All 39 exact pinned dependencies were installed offline into a new isolated venv;
`pip check` and installed-version equality passed. Source-capability reconstruction
passes (14 PASS / 1 PARTIAL / 0 FAIL; not operational acceptance).
Operational capture passed: 20,339 files, 570,623,150-byte archive, 6,827 explicit raw
archive omissions. Bundle: `data/backups/application-operational-recovery-20261010-v1/`.
The new tree `data/backups/application-restored-20261010-v1/` is undergoing restore
and complete readback; do not launch it until that command succeeds. Then use the
rebuilt interpreter `data/backups/recovery-environment-20261010-v1/Scripts/python.exe`
to run the RESTORED `scripts/rehearse_recovered_application.py` with its expected
environment and new report directory. Exact outcomes/hashes are in docs/46.

## Verified - 2026-10-09 Private Operator Runtime (v59)

Continued directly after v58 verification. Added a private launcher with explicit
existing/current-schema database checks, bounded integrity/foreign-key checks,
model table/column checks, live-disabled settings, loopback-only binding, request
peer/host/origin defenses, instance correlation and graceful shutdown. It does not
start the trading supervisor. New connections refuse changed/missing DB identity.
The diagnostic journal distinguishes listener startup, clean stop and failed bind.
Added copy-only service recovery rehearsal with two real processes, retained kill
switch, cross-origin rejection and unchanged trading-table hash checks.

Initial 33 tests passed (46.15s); expanded 36 passed (87.94s). Actual upgraded snapshot
passes preflight; unchanged operator DB correctly blocks at 0029. Actual service-copy
rehearsal PASSED: both processes stopped gracefully, the kill switch survived restart,
trading-table hashes are unchanged, and the source snapshot was not modified.
Final combined regression: 145 distinct tests passed in 143.58 seconds, zero failures,
errors or skips; JUnit counts independently checked. Repo lint and source reconstruction
pass. Exact hashes and limits: docs/46. No operator upgrade or trading activation.

Next eligible task: complete external configuration/source/dependency/evidence recovery,
then operator status/control integration and rendered workflow verification before
guarded operator cutover. Inventory started: 580 top-level evidence files total
208,541,116 bytes, excluding all subdirectories and research archives. Python requirements
are ranges in pyproject.toml, not a recovery lock; package-lock.json has no matching
package.json, and the dashboard is served as static source. Inspect actual runtime
dependencies and retained external-file requirements before packaging. Do not claim
all evidence fits from that top-level count, include secrets by default, or reset history.
The fresh-feed clock blocker remains external; no unchanged probe was repeated.
All owned verification/rehearsal processes exited; no new server was left running.

## Verified - 2026-10-09 Private Database Recovery (v58)

After the verified v56/v57 integration and supervisor work, continued independent
Stage 3 recovery tooling while the genuine feed waits for time synchronization.
Implemented private consistent SQLite backup/verify/restore-copy and a guarded
copy-only native upgrade/rollback rehearsal. Thirteen expanded fixture tests pass.
The actual 205 MB operator snapshot rehearsal passes too: original DB hash unchanged,
existing tables preserved on the 0031 copy, and a verified 0029 rollback copy. Private
artifacts are under git-ignored `data/backups/native-upgrade-rehearsal-20261009-v1/`.
The operator database itself remains 0029 and has zero paper orders/trades. No live
or strategy authority changed. SQLite-only backup is not complete application recovery.
Final combined regression: 93 distinct tests passed, zero failures/errors/skips.
Fresh-process backup verification and v58 source reconstruction pass; hashes: docs/46.
Exact next work: restored-copy
service startup/shutdown, private controls/status, external file/config recovery and
guarded deployment cutover. The full goal remains active; no routine approval needed.

## Checkpoint - 2026-10-09 Atomic Jam Runtime (v56)

The autonomous goal is active; no routine checkpoint requires renewed approval.
Added v7 source/admission/head/config-bound setup, risk, entry, managed exit and
equity receipts in the existing transaction. Audit reconstructs state and costed
ledger effects, including historical entries after their trades close. Dynamic stops
do not rewrite original trade terms. Partial candles use adverse stop bounds and
close-confirmed targets, excluding pre-fill highs. Full-bar BRACKET/CLOSE ordering
matches the pure decision contract. Retired Jam remains rejected; all positive
eligibility is mocked only in disposable tests. No operator migration/write occurred.

Verification: v56a entry-only 22 passed; v56b expanded 38 passed; v56c 45 passed and
one failed test hook (savepoint callback mistaken for outer-commit acknowledgment).
The corrected v56d run passed 50: 47 runtime and 3 readiness cases, 40.89 seconds.
Reports retained in `.tmp/native_jam_runtime_v56[a-d]_20261009.xml`; counts overlap,
not additive. Final combined native/risk/paper/readiness regression: 884 distinct
tests passed in 301.88 seconds, zero failures/errors/skips, including all 47 runtime
cases. JUnit counts/identities verified in `.tmp/native_jam_runtime_v56_final_20261009.xml`.
Repository lint passes. v56 source capability and reconstruction: 14 PASS / 1 PARTIAL /
0 FAIL, all operational authority false. Exact artifact hashes are in docs/46.

Continued directly to Stage 2: bounded cooperative supervisor, explicit existing-DB
CLI and read-only journal/database auditor added. Final v57 combined regression passed
186 distinct cases in 76.97 seconds, including 28 supervisor cases, zero failures/errors/
skips. Source-capability reconstruction passes; hashes and remaining limits: docs/46.
A real observation-only attempt in a
separate newly migrated diagnostic DB stopped on `public_server_clock_skew` at the
21:15 UTC boundary. Reconciliation confirms zero receipts/signals/orders/trades.
Windows reports unsynchronized Local CMOS Clock; configuration inspection was denied.
No OS time settings were changed. Operator time-sync action requested asynchronously;
continue independent work. Artifacts: `data/evidence/native_supervisor_public_20261009_v1/`.
The operator DB was not migrated. Fresh admitted feed/restart demonstration, gap policy,
deployment/restore acceptance, strategy qualification and Testnet refresh remain undone.

## Checkpoint - 2026-10-09 Pure Jam Decisions And Managed Exits (v55)

Added a pure bounded decision kernel on the existing feature/settings contracts.
Setup state distinguishes arming, confirmation, unresolved entry and explicit
fill/rejection acknowledgment; rejected proposals cannot fabricate cooldowns.
Managed positions check prior brackets before next-bar breakeven/trailing updates,
then midpoint/pullback/time exits. Full scope/settings/terms bind each state.
Exact-next-bar checks and JSON restart validation reject inconsistent transitions.
Boundary fills exclude pre-fill candle highs; partial entry candles deliberately
reject. Historical window-end liquidation is not a native scheduling rule.

Initial 66 tests and the expanded 80-test run passed, including eight synthetic
reference comparisons across all stop/target modes. These overlapping runs are not
additive. Final combined regression passed 627 distinct tests in 231.49 seconds,
including all 80 decision cases, zero failures/errors/skips. JUnit identities/counts
verified in `.tmp/native_jam_decisions_v55_final_20261009.xml` (231.412 seconds).
One existing Starlette/httpx deprecation warning remains; no full-repository test
pass is claimed. New-file formatting and scoped whitespace checks pass; the legacy
readiness test's unrelated formatting was preserved. Repository lint passes. v55 capability
inspection and separate reconstruction pass with 14 PASS / 1 PARTIAL / 0 FAIL;
operational flags remain false. Prior readiness artifacts remain unchanged.

No database schema, operator migration, source acquisition, signal submission,
strategy activation or order was added. Read-only inspection confirms live/adapter
disabled, revision `20260718_0029`, no native outcome/seed tables, zero paper orders
and trades. Pure acknowledgments and content hashes are not actual fill/source proof.
Next: reconstruct and atomically bind decision state to audited receipts and the
current risk/paper ledger; preserve exit phase ordering and conservative partial-bar
bounds. Then supervised-runner and operational deployment acceptance. Candidate
qualification and real trading remain blocked; Jam is not reactivated. Exact resume:
docs/10; decision contract and deliberate scope limits: docs/49.

## Checkpoint - 2026-10-08 Jam Retained-History Binding (v54)

Following v53, added a read-only Jam history reader that binds full Spot v1.0.1
settings and reconstructs features from the existing audited seed/receipt chain.
Both paged audit passes share an explicit SQLite read snapshot; no state cache or
caller candles are accepted. Fixed native fingerprint validation to allow canonical
internal spaces without rewriting evidence; outer whitespace/control characters
still reject. Storage opens with enforced `mode=ro` and query-only protection on
a separate connection; missing databases are not created and the writer pool is
unchanged. No order, candidate enablement or state-cache persistence API was added.

Final targeted regression: 661 distinct tests passed in 585.80 seconds, including
41 new history-binding cases, zero failures/errors/skips. Verified JUnit identities
and counts in `.tmp/native_jam_history_v54_final_20261008.xml` (585.688 seconds).
The hardened 41-case run overlaps and is not additive. The initial run's two fixture
failures are retained in its report; transport-label fixtures were corrected before
the successful runs. Repo Ruff lint, three-file formatting and scoped whitespace
checks pass. Existing Starlette/httpx deprecation warning remains; no full-repo test
pass is claimed. v54 capability inspection/reconstruction: 14 PASS, 1 PARTIAL, 0 FAIL;
operational execution flags remain false. Artifact hashes and proof: docs/46.

The real one-candle public diagnostic passed the unchanged clock guard and separate
offline reconstruction. Retained artifact: `data/evidence/native_public_probe_20261008_v1.json`.
Its candle was 703.895326 seconds old on receipt, outside the 180-second entry window;
it was not admitted to the operator database or a campaign. This supersedes the old
point-in-time clock failure without claiming lasting agreement or continuous feed
readiness. No OS clock or tolerance change occurred. Read-only operator inspection:
live/adapter disabled, revision `20260718_0029`, no native outcome/seed tables, zero
paper orders/trades. No migration, account reset, strategy activation or order.

Next: deterministic candidate decisions and managed-exit state, then atomic source/
head/settings decision binding and the supervised runner. Production acceptance also
needs genuine operating evidence, deployment recovery tests and secure access if
published; management remains unauthenticated and must stay private. Real trading
additionally needs independent candidate qualification, eligible forward evidence,
current Testnet/risk/account/compliance checks and explicit micro-live approval.
No qualified strategy or demonstrated live profit. Exact resume and ordered gates:
docs/10; implementation contract: docs/49. Do not restart hosting research or promote
retired Jam merely because this engineering increment passed.

## Checkpoint - 2026-10-08 Bounded Jam Features

Added `native_jam_features.py`: bounded, restartable trend/pullback EMA, previous
ATR/pullback, volume SMA, DMI/ADX, local-reversal context and confirmed-hour EMA.
Arithmetic matches the existing replay with explicit lengths, warmup/nulls, partial
initial hours and missing-DX handling. At most 501 recent candles are retained;
RMA seeds are discarded when initialized. Continuation passes 4,096 without sliding
or reseeding. This is a pure arithmetic module, not a source witness or evaluator.
Copied state is revalidated, but history must be reconstructed from retained inputs
before connecting strategy decisions; valid-looking fabricated state is not proof.

Final targeted regression: 326 distinct tests passed in 264.81 seconds, including
75 new feature tests, with zero failures/errors/skips. JUnit counts and identities
verified in `.tmp/native_jam_features_v53_verified_20261008.xml` (264.709 seconds).
The existing Starlette/httpx warning remains. Repo Ruff lint, new-file formatting
and scoped tracked whitespace checks pass. This is not a full-repository test run.
The initial 74-case run and the first combined run overlap; do not add their counts.
The first combined run hit 129 setup errors because old `.tmp/pytest` was inaccessible.
The successful rerun used confirmed-new `.tmp/pytest-v53-retry-20261008` and
`.tmp/pytest-cache-v53-retry-20261008`; old contents/permissions were left alone.
Its failed report is retained, not relabeled as a pass. Use a fresh validated scratch
path for later test runs if the existing sandbox-helper/old-directory issue persists.

v53 capability inspection and independent reconstruction: 14 PASS, 1 PARTIAL, 0 FAIL;
all operational execution flags remain false. Historical evidence stays unchanged.
Read-only operator inspection confirms live/adapter disabled, revision `20260718_0029`,
no native outcome/seed tables and zero paper orders/trades. No real acquisition,
clock change, operator migration, strategy activation or order occurred.
The prior managed-clock discrepancy was not rechecked. No qualified strategy or
demonstrated live profit. Next: bind Jam features/settings to retained history,
then deterministic evaluation and managed-exit state, followed by the supervised
runner. Retired/quarantined Jam remains disabled. Resume: docs/10; proof: docs/46;
feature contract and remaining gaps: docs/49.

## Checkpoint - 2026-10-07 Source-Bound Online Paper Exits

Added `NativePublicObserver.manage_exits` and v6 `ONLINE_EXIT_NO_ENTRY` receipts.
The explicit one-candle method acquires fresh source data and atomically records
FLAT/HELD/CLOSED management with source/admission/checkpoint and any trade, position,
equity and account changes. It cannot seed, enter, accept imported packets, skip
candles or fall back to stale recovery. Observation-only calls retain their open-
position guard. Existing v1-v5 canonical receipt bytes remain unchanged.

Shared conservative bracket and frozen-cost mechanics now support both recovery
and the new `native_ohlc_online_exit_v1` model. Both remain nonqualifying; earlier
recovery quarantine cannot be removed by later online steps. Partial entry candles
retain adverse bounds, not invented intrabar fills. Entry kill switches do not
prevent explicit exit management. Held-model changes, skipped management intervals,
mode-switch retries and inconsistent ledger state reject. Old entries are not
retroactively authenticated. No strategy or production authority was added.

Initial exit suite: 40 passed in 62.10 seconds. Expanded native suite: 268 distinct
tests passed in 339.24 seconds, including 47 new exit cases, zero failures/errors/
skips. The final targeted regression exited 0: 806 distinct tests passed in 647.96
seconds, including 47 exit cases, with zero failures/errors/skips. XML identities
and totals were verified in `.tmp/aurex_native_online_exits_v52_final_20261007.xml`.
Earlier runs overlap and are not additive; this is not a full-repository suite.
v52 inspection/reconstruction reports 14 PASS, 1 PARTIAL, 0 FAIL, not operational
readiness. Ruff lint and five native implementation/test format checks pass.
The existing Starlette/httpx deprecation warning remains.

Post-test read-only operator inspection confirms live/adapter disabled, database
revision `20260718_0029`, neither native outcome/seed table, and zero paper orders
or trades. No real acquisition, operator migration, strategy enablement or order occurred.
The earlier clock discrepancy remains unresolved and was not rechecked in this
step. Next: deterministic evaluation and feature buffers, then the stoppable
supervisor and a separately justified eligible execution-evidence path. Canonical
resume: docs/10. Verification/hashes: docs/46. No qualified strategy or live profit.
The completed exit increment handles fixed brackets, not Jam-specific trailing,
breakeven, midpoint/pullback failure or time exits. Those rules already exist in
`jam_reversal_reference.py`; integrate and parity-test their state during the next
evaluator work without reactivating the quarantined/retired Jam lineages.

## Checkpoint - 2026-10-06 Acquisition-Owned Native Observation

Added `NativePublicObserver.observe`: a single owned public acquisition and atomic
no-entry observation, without a caller-supplied packet, transport or clock API.
It closes a consistent read snapshot before network I/O and rechecks its expected
stream head in the processing transaction. v5 receipts bind admission timing and
the prior receipt hash; v1-v4 canonical serialization remains unchanged.

Bootstrap waits for a fresh seed window. Initialized streams request only the next
contiguous candle; early polls wait without refetching, missed windows stop instead
of skipping/backfilling, and open positions block pending online exit management.
Imported packets cannot retry or silently replace online admission. Explicit
nonqualifying recovery does not clear the later online-admission requirement.
Lost acknowledgement and process death resume from retained state. No signature,
live-origin authentication, entry or forward-qualification authority is claimed.

Initial observation tests: 48 passed in 22.79 seconds. Expanded native suite: 221
distinct tests passed in 263.95 seconds, including 59 observation cases, with zero
failures/errors/skips. These overlapping runs are not additive. The final targeted
regression exited 0: 759 distinct tests passed in 819.45 seconds, including 59
observation cases, zero failures/errors/skips. XML totals and identities were checked
in `.tmp/aurex_native_observation_v51_final_20261006.xml`. This is not a full-repository
suite. One unusually slow case passed an isolated rerun in 5.47 seconds (0.05-second
test body); no timing cause or unattended-performance guarantee is inferred.
v51 source inspection and reconstruction report 14 PASS, 1 PARTIAL, 0 FAIL, not
operational readiness. Repo Ruff lint and four native implementation/test formatting
checks pass. The existing Starlette/httpx deprecation warning remains.

Read-only operator reinspection confirms live/adapter disabled, revision
`20260718_0029`, neither native outcome/seed table, and zero paper orders/trades.
No real acquisition, operator migration, strategy enablement or trading occurred.
The previously measured managed-clock discrepancy remains unresolved and has not
been rechecked here. Next: causal online paper exits, deterministic evaluation and
the supervised runner, then genuine feed acceptance and eligible forward evidence.
Canonical resume: docs/10. Verification/hashes: docs/46. No qualified strategy or
demonstrated live profit exists.

## Checkpoint - 2026-10-06 Native Source-To-Receipt Binding

Added `NativePublicSourceBinding` and `NativeBarProcessor.process_sourced`, retaining
the complete public acquisition packet and canonical hash atomically with v4 bar
receipts, initial seed/checkpoint and any exit-only recovery effects. Purposes are
SEED, CLOSED_BAR and RECOVERY. Observation outcomes explicitly state no entry and
do not claim strategy evaluation. There is no signal argument or forward authority.

Audits reconstruct source responses, normalization, timing, scope and seed linkage.
Known retries must use the original witness; changed or dropped bindings fail.
Legacy v1-v3 bytes remain unchanged, source can attach without rewriting old history,
and continuation past 4,096 bars still works. Import labels cannot establish live
origin; recovery positions remain nonqualifying. No additional migration is needed.

Initial 48 source cases passed; the expanded native integration run passed 162
tests in 211.49 seconds. The final targeted regression exited successfully: 700
distinct tests passed, including 54 source-binding cases, with zero failures,
errors or skips (550.24 seconds). XML identities and totals were checked in
`.tmp/aurex_native_source_v50_final_20261006.xml`; this was not the full repository
suite. Repo Ruff lint and native processor/source/test formatting pass. The wider
format check flags the readiness runner, route and readiness test; their mixed
formatting was left unchanged. The existing Starlette/httpx warning remains.
v50 source/capability reconstruction matches current source and reports 14 PASS,
1 PARTIAL, 0 FAIL; it is not operational readiness.
The intermediate v49 result preceded a final formatting correction and remains
historical; v50 is current. Final verification details and hashes are in docs/46.

The prior real clock discrepancy remains unresolved and was not rechecked in this
source-binding work. Post-test read-only inspection confirms live trading and its
adapter disabled, operator revision `20260718_0029`, neither native outcome/seed
table, and zero paper orders/trades. No network acquisition, operator migration,
fixture insertion or trade occurred. Next: acquisition-owned observation admission
and causal online paper exits, then deterministic evaluation and the supervised runner.
Canonical resume: docs/10. No qualified strategy or demonstrated live profit.

## Checkpoint - 2026-10-06 Native Public Candle Acquisition

Added a bounded, credential-free BTCUSDT 15m public HTTPS client plus acquisition/
offline-verification CLI. Exact request intervals, raw response hashes, normalized
candles, pagination, clock checks, body limits and fail-closed transport handling
are retained and tested. The client has no DB, signal or order path. Fixture inputs
are labelled; retained hashes are not cryptographic source authentication or forward
qualification. Source binding into processor receipts and online exits are next.

The actual public request reached Binance, but our clock guard rejected a measured
7.746558-second server/local receipt discrepancy before any candle request. The
host reports a managed domain time source; no time settings were changed. Retained
failure diagnostic: `data/evidence/native_public_clock_blocker_20261006_v1.json`.
This is blocked operational acceptance, not a successful feed or paper campaign.

Final changed-source regression passed 646 distinct tests, including 109 acquisition
cases, with zero failures/errors/skips (266.49 seconds). Repo Ruff, changed-file
formatting and scoped whitespace checks pass. The existing Starlette/httpx warning
remains. v48 source/capability inspection and reconstruction report 14 PASS, 1 PARTIAL,
0 FAIL; this does not claim operational readiness. Details and file hashes: docs/46.

Read-only reinspection confirms live/adapter disabled, operator DB revision 0029,
neither native table, and zero paper orders/trades. No migration, account reset,
strategy reactivation, paid service or order. docs/10 is the canonical resume point;
docs/49 records acquisition behavior, the clock blocker and remaining work.

## Checkpoint - 2026-10-04 Exit-Only Native Recovery

Added `recover_next` for one contiguous closed candle at a time, without signal or
entry authority. v3 receipts record FLAT/HELD/CLOSED outcomes and atomically commit
costed paper closes with ledger/account/position changes. Replay bracket semantics
are reused; partial entry candles get explicit conservative bounds. No historical
fill time is invented: close/loss recognition uses the current processing time.

Every touched position is marked `native_ohlc_recovery_v1`, which existing forward
qualification rejects. Entry kill switches and strategy disablement do not prevent
reduction of existing modeled exposure. Normal processing cannot silently advance
past an open position needing management. Retries, transition audits, ownership,
frozen costs, equity, gaps, changed inputs and unrecorded ledger changes fail closed.
Real subprocess-death, concurrency and rollback tests use disposable ledgers only.

No operator migration, order, cloud service or genuine forward campaign was started.
This is recovery simulation, not a continuously running source-verified exit monitor.
Next: verified acquisition/online exits, deterministic evaluation, supervised runner
and failure stops. Final test counts and v47 source-inspection audit are in docs/46;
docs/10 carries the canonical resume point. Zero qualified strategies/live profit.

## Checkpoint - 2026-10-04 Native Indicator Continuation

Implemented versioned continuation beyond the 4,096-candle legacy prefix, retaining
exact replay EMA/RSI/ATR recurrences and previous-confirmed-hour EMA visibility.
The old v1 receipt bytes stay unchanged. New v2 receipts retain bounded indicator
state and an explicit chained content digest. Every resumed state is reconstructed
from the retained seed/bars before use, with paged receipt reads and existing
transaction, idempotency, strategy retirement, freshness and risk guards.

This closes the fixed-prefix stop, not all long-running operational requirements.
Audit time/storage still grow; stale backlog, strategy-specific feature buffers,
acquisition/evaluation, automatic paper exits and the continuous runner remain.
All tests use disposable fixtures. No operator migrations, cloud services, genuine
paper campaign, strategy enablement or live orders were introduced. Exact regression
results and the source-inspection v46 reconstruction are recorded in docs/46.
Final review also closed skipped nonpositive sequence keys in paged audits and a
caller-mutation race between seed preflight and persistence; seed size is checked
before copying. Regressions reproduced the faults before the fixes.
The next implementation is explicit downtime/backlog treatment and paper-position
management, without retroactive entries or fabricated candles. See docs/10.

## Checkpoint - 2026-10-04 Retained Native History

Recovered the interrupted September 30 final XML report: 375 tests, zero failures,
errors or skips, 390.724 seconds. The v43 artifacts remain historical and unchanged.

Added atomic initial-seed retention and one-candle resume in the bounded SQLite
native processor. Seed plus committed outcomes reconstruct every history prefix;
canonical prefix hashes are verified in one pass. Missing, orphaned or revised
seed/history data reject without repair. A new process can resume without the
caller resupplying warmup data. Fresh-process, corruption, timing, retry, concurrent
resume and capacity tests remain synthetic and use disposable databases.

Migration `20261004_0031` preserves existing receipts but does not fabricate seeds
for historical streams. The 4,096-bar capacity still blocks further advancement;
the next task is explicit continuation without reseeding, plus stale-backlog and
position-management behavior. No source acquisition, strategy evaluator, automated
exit or continuous runner was added. Operator migrations and live execution were
not enabled. Final regression and v44 evidence are recorded in docs/46.

## Checkpoint - 2026-09-30 Native Atomic Processing

Added a SQLite-native transaction owner and append-only bar outcome/checkpoint
model plus migration `20260930_0030`. The processor requires closed-bar preflight,
binds scope and signal requests, validates the recorded hash chain and signal
links, serializes native workers before reading the head, and commits paper effects
with the receipt. Retries return the existing receipt; changing a processed
decision, history or scope fails closed. No-signal is a caller-supplied outcome,
not an implemented strategy evaluator or source attestation.

Native intake now has an opt-in caller-managed transaction mode. Existing native
and webhook callers keep their commit behavior. The SQLite guard requires an
actual database transaction because an ORM transaction alone does not prevent a
first SAVEPOINT release from committing independently under the legacy driver.

Tests exercise rollback, acknowledgement loss, concurrent workers, process death
before/after commit, corruption, stale/gapped inputs, scope drift and migration
preservation in disposable file-backed databases. The operator database was not
migrated or populated with fixtures. Final counts, limits, v43 readiness snapshot
and exact continuation point are recorded in docs/46 and docs/10.
Next: retained seed and bounded-window continuation, then verified data acquisition,
strategy evaluation, paper exits and a stoppable runner. No strategy or live path
was enabled, and no MCP server or cloud hosting was added.

## Checkpoint - 2026-09-29 Native Closed-Bar Preflight And Assistant Audit

Added a pure BTCUSDT 15m input preflight and signal/bar consistency helper. It
validates UTC candle alignment, OHLCV, closed/fresh timestamps, continuity, warmup,
unchanged history and exactly one next bar. Hash-bound cursors detect duplicates,
changed seeds, scope and parameter drift. Indicators reuse existing replay helpers
including previously confirmed hourly timing. No fetching, strategy evaluation,
cursor persistence, operator-ledger writes or continuous runner was added.

Input readiness is neither source-origin attestation nor execution permission.
Synthetic integration tests retain strategy retirement and shared risk/idempotency
gates. The fixed-seed 4,096-bar limit deliberately refuses silent reseeding; longer
operation requires explicit incremental-state/continuation work. Atomic outcome
and cursor persistence is the next native task.

Audited assistant access: local services/scripts and FastAPI exist, but a dedicated
Aurex MCP connector does not. The main API lacks general authentication and some
read routes can initialize records, so publishing it as an assistant endpoint is
not appropriate. `docs/48_ASSISTANT_INTEGRATION.md` records the inventory and proposed
read-only local MCP scope; no connector or public listener was installed.
Final verification and v42 source-inspection evidence are recorded in docs/46.

## Checkpoint - 2026-09-29 Native Spot Risk (Started September 27)

Added a bounded native BTCUSDT spot paper policy: long only, explicit 100-unit
starting equity, one open position, no borrowing, fee/slippage-inclusive stop
sizing, cash affordability, net reward:risk, capped daily/weekly admission budgets,
and 10-unit cumulative net account/strategy loss boundaries. The engine shares
execution cost arithmetic and records its assumptions. Native paper execution
revalidates a risk approval before creating an order. Price/quantity precision,
stale approvals and unreconciled ledgers fail closed. Real gap losses remain real
losses in paper accounting, not clipped to the modeled stop budget.

The actual local paper ledger was inspected under read-only access and found empty.
A guarded SQLite transaction then aligned its old 1,000-unit default to the
operator-approved 100, one position and minimum reward:risk 2, retaining the kill
switch state and recording before/after metadata in the system-event ledger.
It refused nonempty or unexpected account state; no strategy or live adapter was
enabled. Tests remain synthetic, with no real/Testnet trades or paid resources.
Final review also added orphan-paper-order rejection. The final regression, v41
capability audit and next action are recorded in docs/46
and the top of `docs/10_PROJECT_CONTROL.md`.

## Checkpoint - 2026-09-27 Native $0 Route

Operator selected deferral of paid TradingView webhook access and cloud receiver
deployment. Added a local-only `NativeSignalPayload` and `ingest_native` path into
the existing risk/paper services. Version/settings and timezone are explicit;
source identity is distinct and cannot be substituted at either service boundary.
Live-enabled configuration is rejected before signal writes. Shared risk now
rejects future timestamps as well as stale signals.

Synthetic integration tests use isolated databases, not the operator ledger, for
paper costs, closing/accounting, duplicate and risk rejection, source separation,
and absence of broker effects. No strategy was revived or qualified. The existing
8,545-bar BTCUSDT import reproduced its stored hash via a read-only database audit;
this is data integrity, not a new strategy outcome. Final regression details,
limits, and capability evidence are in `docs/46_AUREX_DELIVERY_REBASELINE.md`.
Next: all-in cost/spot-affordability review before causal native closed-bar intake.

## Checkpoint - 2026-09-26 TradingView Ingress

Completed local ingress inspection and direct-TLS safe-rejection implementation.
Added `scripts/run_tradingview_ingress.py`, a webhook-only app, guarded campaign
scope, bounded body handling, source/authentication checks, and spoofed-proxy
regression tests. The main webhook rejects forwarding headers as well. Updated
launch instructions to disable proxy trust/access logs and keep management local.

The current local SQLite migration and a read-only synthetic risk preflight passed
their safety checks. Actual external delivery remains blocked by the development
secret and absent TLS endpoint configuration. No external alert, public listener,
real/testnet order, purchase or cloud deployment was made. The complete next-step
record is `docs/47_TRADINGVIEW_INGRESS_DEPLOYMENT.md`; final test counts and readiness
hashes are in `docs/46_AUREX_DELIVERY_REBASELINE.md`. No strategy is qualified and no
live profit is demonstrated.

## Completed

### Stage 0: Blueprint

Created:

```text
docs/00_AUREX_MASTER_PLAN.md
```

The plan defines the mission, missing assumptions, architecture, implementation gates, backtesting standard, paper trading standard, and first live `$100` protocol.

### Stage 1: Backend Skeleton

Created:

```text
FastAPI application factory
Health endpoint
Settings module
Structured JSON logging
Python project metadata
Local SQLite database default
Initial health test
```

Verified:

```text
GET /health returns safe local defaults.
live_trading_enabled defaults to false.
```

### Stage 2: Database And Migrations

Created:

```text
SQLAlchemy base and session infrastructure
Domain enums
Core operational models
Alembic configuration
Initial explicit schema migration
SQLite-backed migration test
SQLite-backed ORM persistence test
```

Core tables:

```text
accounts
risk_profiles
symbols
signals
signal_events
market_states
strategy_scores
risk_decisions
paper_orders
paper_trades
positions
equity_curve_points
strategy_runs
backtest_runs
backtest_results
system_events
```

Note:

```text
Local development now defaults to SQLite at sqlite:///./data/aurex.db.
Migrations are verified locally against SQLite.
PostgreSQL remains a later scaling option, not the active local dependency.
```

### Stage 3: TradingView Signal Gateway

Created:

```text
TradingView webhook payload schema
Webhook secret authentication
Signal intake service
Symbol normalization
Idempotency hashing
Duplicate signal rejection
Duplicate attempt journaling
Signal event history
POST /webhooks/tradingview
GET /signals
GET /signals/{id}
Webhook integration tests
```

Verified:

```text
Valid webhook is accepted and stored.
Malformed webhook is rejected.
Invalid webhook secret is rejected.
Duplicate webhook is rejected, stored, and linked to the original signal.
Signal lifecycle events are stored.
```

### Stage 4: Risk Engine

Created:

```text
Risk calculation helpers
Default paper account bootstrap
Default risk profile bootstrap
RiskDecision persistence
Automatic post-webhook risk evaluation
Risk-approved and risk-rejected signal lifecycle events
GET /risk/status
POST /risk/kill-switch
POST /risk/kill-switch/reset
Latest risk decision included in signal API responses
```

Implemented rules:

```text
Missing stop loss rejection
Missing take profit rejection
Invalid price geometry rejection
Minimum reward:risk rejection
Position sizing
Daily loss limit rejection
Weekly loss limit rejection
Max open positions rejection
Stale signal rejection
Kill switch rejection
Duplicate signal cooldown remains enforced by the signal gateway before risk evaluation
```

Verified:

```text
Approved signals include risk amount and position size.
Rejected signals include exact rejection reason.
Risk decisions are stored.
Webhook responses expose the latest risk decision.
Risk status and kill switch endpoints work.
Real HTTP smoke test returned RISK_APPROVED with position size.
No paper orders or paper trades are created in Stage 4.
```

### Stage 5: Paper Execution Engine

Created:

```text
Paper execution service
Instant paper-fill model
PaperOrder creation after risk approval
PaperTrade creation after risk approval
Open Position creation after risk approval
EquityCurvePoint creation on open and close
GET /trades
GET /trades/{id}
POST /paper/close-trade
POST /paper/reset
Long and short paper close calculations
```

Implemented rules:

```text
Paper execution requires approved RiskDecision.
Paper execution requires position size and risk amount.
Paper execution requires stop loss and take profit.
Risk-rejected signals create no paper trades.
Manual close calculates realized P/L.
Manual close calculates R multiple.
Manual close updates account equity.
Manual close closes the matching open position.
Paper reset clears paper orders, trades, positions, and equity curve points.
Paper reset keeps signal and risk audit history intact.
```

Verified:

```text
Risk-approved webhook creates paper order, paper trade, position, and equity point.
Risk-rejected webhook creates no paper trade.
Long paper close calculates profit and R multiple.
Short paper close calculates profit and R multiple.
Paper reset clears paper trading state.
Real HTTP smoke test opened, listed, closed, and reset a paper trade.
No broker execution exists.
```

### Stage 6: Analytics Engine

Created:

```text
Analytics service
Performance summary schema
Equity curve schema
GET /performance/summary
GET /performance/equity-curve
Known-fixture analytics tests
Zero-trade analytics tests
API-level analytics tests
```

Implemented metrics:

```text
total trades
wins
losses
breakeven trades
win rate
average win
average loss
expectancy
profit factor
max drawdown
total net P/L
equity curve points
best strategy
worst strategy
strategy breakdown
market regime breakdown
```

Verified:

```text
Metrics match known fixture data.
Equity curve returns limited points in chronological order with latest equity, max drawdown, and realized P/L.
Zero-trade state returns clean defaults.
Closed paper trades appear in the performance summary and equity curve API.
Real HTTP smoke test opened, closed, and summarized a paper trade.
No broker execution exists.
```

### Stage 7: Pine Strategy V1

Created:

```text
pine/strategies/trend_pullback_v1.pine
docs/pine/trend_pullback_v1.md
Static Pine strategy contract tests
```

Implemented strategy:

```text
Higher timeframe EMA 50/200 trend filter
Current timeframe EMA 200 filter
Pullback near EMA 20 or EMA 50
RSI reset filter
Bullish and bearish confirmation candle filters
ATR, swing, or wider stop mode
Fixed reward:risk take profit
strategy.entry calls
strategy.exit calls
Webhook-ready JSON alert messages
```

Non-repainting controls:

```text
Pine Script v6
barstate.isconfirmed
request.security(..., lookahead = barmerge.lookahead_off)
calc_on_every_tick = false
process_orders_on_close = true
```

Verified locally:

```text
Static tests confirm required Pine constructs exist.
Static tests confirm Aurex payload fields exist.
Static tests reject known lookahead-on repaint pattern.
```

External verification still required:

```text
Paste the script into TradingView Pine Editor.
Compile it in TradingView.
Run TradingView Strategy Tester.
Create an alert using any alert() function call.
Send a webhook to Aurex and verify it reaches POST /webhooks/tradingview.
```

### Stage 8: Historical Backtest Lab

Created:

```text
Backtest lab service
Backtest report schemas
Alembic migration for backtest lab fields
POST /backtests/reports
GET /backtests/reports
GET /backtests/reports/{id}
GET /backtests/reports/{id}/csv
POST /backtests/ohlcv/import-csv
POST /backtests/trades/import-csv
```

Implemented:

```text
Historical OHLCV CSV adapter
Backtest trade-result CSV adapter
Deterministic config hash
Strategy version recording
Symbols and timeframe recording
Cost model snapshot
Slippage model snapshot
Risk snapshot
Parameter snapshot
Backtest metric calculation
Report CSV export
Acceptance gate approval/rejection
```

Backtest metrics:

```text
total trades
wins
losses
breakeven
win rate
average win
average loss
expectancy
profit factor
max drawdown
total net P/L
equity curve snapshot
```

Acceptance gate checks:

```text
minimum trade count
minimum profit factor
positive expectancy
maximum drawdown
```

Verified:

```text
Metrics match known fixture data.
Config hash is deterministic.
Backtest report can be stored.
Strategy version and config hash are recorded.
Cost and slippage assumptions are stored.
Acceptance gate can approve a valid report.
Acceptance gate can reject a weak report.
Profitable no-loss reports are not rejected solely for undefined profit factor.
OHLCV CSV import works.
Trade-result CSV import works.
Report CSV export works.
Real HTTP smoke test created, exported, and imported backtest data.
No broker execution exists.
```

### Stage 9: Paper Trading Dashboard

Created:

```text
apps/frontend/index.html
apps/frontend/styles.css
apps/frontend/app.js
GET /dashboard
Static dashboard asset mount
GET /system/events
System event recorder
Dashboard contract tests
```

Dashboard views:

```text
Command Center
Data-driven Market Preview
Risk panel
Performance panel
Signals table
Paper trades table
System events feed
Kill switch controls
```

Backend event feed:

```text
Signal validated
Duplicate signal rejected
Risk approved signal
Risk rejected signal
Paper trade opened
Paper trade closed
Paper trading state reset
Backtest report stored
```

Verified:

```text
Dashboard shell is served by FastAPI.
Dashboard assets are served by FastAPI.
Dashboard reads real backend endpoints.
Risk state is visible.
Rejected signal reasons are available in the signals table.
Paper trades and performance data are visible.
Market Preview reads the real equity curve API and falls back safely when no curve exists.
System events are visible.
Kill switch enable/reset controls work against a writable local server.
No live trading controls exist.
Browser screenshot verified the dashboard with real seeded paper data.
Headless Chrome file-render verification covers the empty fallback preview and mocked-data equity curve preview at desktop and mobile widths.
No broker execution exists.
```

### Stage 10: Market State Engine

Created:

```text
Market candle persistence model
Alembic migration for market_candles
Market state indicator helpers
Market state classification service
POST /market/candles/import
POST /market/state/compute
Market state API schemas
Market state engine unit tests
Market state API integration tests
```

Implemented indicators:

```text
EMA 50/200 trend relationship
EMA slope
ADX
ATR percentile
Volume relative average
VWAP distance
Higher-timeframe trend
Regime confidence score
```

Implemented regimes:

```text
TRENDING_UP
TRENDING_DOWN
RANGING
HIGH_VOLATILITY
LOW_VOLATILITY
BREAKOUT_EXPANSION
CHOPPY_DANGER_ZONE
UNKNOWN
```

Implemented rules:

```text
Signals are enriched with computed market regime when enough candles exist.
The computed regime overrides the claimed webhook regime.
trend_pullback_v1 only accepts LONG in TRENDING_UP and SHORT in TRENDING_DOWN.
range_mean_reversion_v1 only accepts RANGING.
volatility_breakout_v1 accepts LOW_VOLATILITY and BREAKOUT_EXPANSION.
UNKNOWN remains allowed so missing candle data does not silently break old flows.
```

Verified:

```text
Market candles import and update by symbol, timeframe, and timestamp.
Trend fixture computes TRENDING_UP.
Range fixture computes RANGING.
Webhook signals are enriched with computed regime data before risk evaluation.
Risk rejects a trend strategy when the computed regime is RANGING.
MarketState rows are stored for computed API calls and signal-linked enrichment.
Real HTTP smoke test imported 240 candles, computed TRENDING_UP, updated 240 candles to RANGING, and risk-rejected an incompatible webhook.
No broker execution exists.
```

### Stage 11: Strategy Portfolio

Created:

```text
StrategyConfig persistence model
Alembic migration for strategy_configs
Strategy registry for Stage 11 strategies
Strategy portfolio service
GET /strategies
GET /strategies/comparison
PATCH /strategies/{strategy}
Dashboard Strategy Portfolio panel
pine/strategies/volatility_breakout_v1.pine
pine/strategies/range_mean_reversion_v1.pine
docs/pine/volatility_breakout_v1.md
docs/pine/range_mean_reversion_v1.md
Strategy portfolio integration tests
Expanded Pine contract tests
```

Implemented strategies:

```text
trend_pullback_v1
volatility_breakout_v1
range_mean_reversion_v1
```

Implemented controls:

```text
Per-strategy enabled/disabled state
Per-strategy allowed market regimes
Per-strategy risk per trade
Per-strategy minimum reward:risk
Per-strategy open-position cap
Per-strategy comparison metrics
Dashboard enable/disable actions
```

Implemented risk behavior:

```text
Disabled strategies are risk-rejected before paper execution.
The computed or claimed market regime must match the strategy policy.
Per-strategy risk_per_trade controls position sizing.
Per-strategy minimum_reward_risk overrides the global minimum.
Per-strategy max_open_positions controls portfolio exposure.
Disabling one strategy does not disable the others.
```

Verified:

```text
Default portfolio seeds all three Stage 11 strategies.
Bad strategies can be disabled without touching other strategies.
Per-strategy risk overrides change RiskDecision sizing.
Per-strategy open-position cap blocks exposure.
Strategy comparison reports independent metrics.
Real HTTP smoke test disabled trend_pullback_v1 and confirmed the webhook was risk-rejected while the other two strategies stayed enabled.
Browser verification showed the dashboard Strategy Portfolio panel with all three strategies and confirmed the trend_pullback_v1 toggle changed only that row.
Screenshot captured at C:/Users/ashumba/AppData/Local/Temp/stage11_strategy_dashboard.png.
No broker execution exists.
```

### Stage 12: AI Analyst Layer

Created:

```text
AnalystNote persistence model
AnalystNoteType domain enum
Alembic migration for analyst_notes
Advisory analyst service
GET /analyst/summary
GET /analyst/notes
POST /analyst/trades/{trade_id}/review
POST /analyst/trades/{trade_id}/similarity
POST /analyst/risk-anomalies/scan
POST /analyst/strategy-degradation/scan
Dashboard Analyst panel
Analyst integration tests
```

Implemented advisory functions:

```text
Trade quality summaries
Pattern similarity search across closed paper trades
Risk anomaly detection
Strategy degradation detection
Post-trade review notes
Stored evidence snapshots
System event logging for analyst notes
```

Implemented guardrails:

```text
Every analyst response is advisory_only.
Analyst notes have no execution authority.
Analyst scans do not create paper orders, paper trades, positions, or broker actions.
Open trades cannot be analyst-reviewed as final outcomes.
The risk engine remains final authority.
Live trading remains disabled.
```

Verified:

```text
Zero-trade analyst summary returns a clean advisory state.
Closed trade review creates a stored TRADE_REVIEW note.
Pattern similarity returns matched historical trades and stores a PATTERN_SIMILARITY note.
Risk anomaly scan flags oversized losses and stores RISK_ANOMALY notes.
Strategy degradation scan flags recent expectancy decay and stores STRATEGY_DEGRADATION notes.
Real HTTP smoke test reviewed 10 closed trades, created review/similarity/anomaly/degradation notes, and confirmed every analyst response was advisory_only.
Browser verification showed the Dashboard Analyst panel, verified the scan button created notes, and confirmed open positions remained 0.
Screenshot captured at C:/Users/ashumba/AppData/Local/Temp/stage12_analyst_dashboard_viewport.png.
No broker execution exists.
```

### Stage 13: Live Broker Readiness

Created:

```text
Broker readiness domain enums
BrokerConnection persistence model
OrderIntent persistence model
BrokerOrder persistence model
BrokerFill persistence model
BrokerPositionSnapshot persistence model
BrokerReconciliationReport persistence model
LiveReadinessCheck persistence model
Alembic migration for broker readiness tables
Sandbox broker adapter
Broker readiness service
GET /broker/readiness
POST /broker/readiness/run
GET /broker/connections
POST /broker/sandbox/order-intents
GET /broker/order-intents
POST /broker/sandbox/order-intents/{order_intent_id}/submit
GET /broker/orders
POST /broker/sandbox/orders/{broker_order_id}/simulate-fill
POST /broker/reconciliation/run
GET /broker/reconciliation
POST /broker/emergency-stop
Dashboard Broker Readiness panel
Broker readiness integration tests
```

Implemented readiness behavior:

```text
Stage 13 only supports sandbox broker connections.
Sandbox order intents can be created only from approved risk decisions.
Sandbox order intents can be submitted to the sandbox adapter.
Sandbox broker fills can be simulated and persisted.
Paper execution and sandbox broker fills can be reconciled.
Broker fill fees reconcile against Aurex paper order fees.
Broker and Aurex snapshots expose per-order cost totals, implied slippage, and aggregate cost totals.
Sandbox broker position snapshots reconcile against Aurex open positions.
Readiness checks record live trading disabled, sandbox connection, sandbox order/fill test, reconciliation, paper-trading gate, and emergency-stop evidence.
The paper-trading gate is intentionally BLOCKED until evidence is complete.
ready_for_live remains false while any required readiness gate is not PASS.
Emergency stop cancels open sandbox orders/intents and enables the risk kill switch.
```

Implemented guardrails:

```text
Live trading remains disabled.
No live broker adapter is implemented.
No live broker credentials are accepted.
No Stage 13 endpoint can submit a live order.
The dashboard labels broker readiness as sandbox/paper only.
```

Verified:

```text
Sandbox readiness defaults are safe and not live.
Sandbox order intent, submission, fill simulation, and reconciliation work end to end.
Readiness checks pass for sandbox intent/fill and reconciliation while paper-trading remains BLOCKED.
Broker fee mismatches fail broker reconciliation and the position-reconciliation readiness check.
Position quantity or entry mismatches fail broker reconciliation and the position-reconciliation readiness check.
Emergency stop cancels open sandbox work and turns on the risk kill switch.
Real HTTP smoke test created a paper trade, created a sandbox order intent, submitted it, simulated a fill, reconciled MATCHED, and confirmed live trading stayed disabled.
Browser verification showed the Broker Readiness panel with SANDBOX, live enabled No, CONNECTED, MATCHED, visible Run checks/Stop controls, and the intentional Blocked state.
Screenshot captured at C:/Users/ashumba/AppData/Local/Temp/stage13_broker_readiness_dashboard_polished.png.
No live broker execution exists.
```

### Stage 14: Live Micro-Deployment Guard

Created:

```text
LiveDeploymentStatus domain enum
LiveDailyReviewStatus domain enum
LiveDeploymentPlan persistence model
LiveDeploymentGate persistence model
LiveDailyReviewReport persistence model
LiveApprovalRecord persistence model
LivePaperEvidenceReport persistence model
LiveBrokerStatementReport persistence model
LiveProfitMilestoneReport persistence model
LiveApprovalPacket persistence model
TradeJournalEntry persistence model
Alembic migration for live micro-deployment tables
Alembic migration for live approval and paper evidence tables
Alembic migration for live approval packet tables
Alembic migration for paper evidence collection-window fields
Alembic migration for paper evidence integrity fields
Alembic migration for approval packet due-diligence fields
Alembic migration for trade journal entries
Alembic migration for broker statement reconciliation reports
Alembic migration for first-profit milestone reports
Live micro-deployment service
Trade journal service
GET /live/deployment
PATCH /live/deployment/plan
POST /live/deployment/checks/run
POST /live/deployment/daily-review
GET /live/deployment/daily-reviews
POST /live/deployment/approvals
GET /live/deployment/approvals
POST /live/deployment/paper-evidence/run
GET /live/deployment/paper-evidence
POST /live/deployment/broker-statements/reconcile
POST /live/deployment/broker-statements/preflight-csv
POST /live/deployment/broker-statements/reconcile-csv
GET /live/deployment/broker-statements
POST /live/deployment/profit-milestone/run
GET /live/deployment/profit-milestones
POST /live/deployment/approval-packet
GET /live/deployment/approval-packets
POST /live/deployment/activation-attempt
POST /journal/trades
GET /journal/trades
Dashboard Live Micro-Deployment panel
Live micro-deployment integration tests
```

Implemented gate behavior:

```text
Stage 14 defaults to one strategy, BTCUSDT, $100 target, and tiny risk settings.
The live trading flag must remain disabled.
Stage 13 broker readiness must pass before Stage 14 can advance.
One reviewed live broker and one account must be selected.
The reviewed broker/account selection must come from a complete due-diligence approval packet.
The dashboard can submit the review-only approval packet references without accepting broker credentials.
The dashboard can record explicit broker, account, jurisdiction, and live-execution approvals or revocations without enabling live trading.
The dashboard can run the first-profit milestone report without enabling live trading.
The dashboard summarizes the latest activation-attempt audit with blocking gate count and gate-key preview.
One enabled strategy must be selected.
One to three symbols must be selected.
An accepted backtest report must exist for the selected deployment strategy and cover the selected symbols.
Risk per trade must stay <= 0.50%.
Daily loss must stay <= 1%.
Weekly loss must stay <= 3%.
Open positions must stay between 1 and 3.
Paper evidence requires at least 100 closed paper trades for the selected deployment strategy and symbols, 30 observed calendar days, at least 15 active trading days, no single day above 25% of counted trades, positive expectancy, profit factor >= 1.20, drawdown within the Stage 14 plan limit, zero unexplained trades, and zero risk-rule violations.
Paper evidence requires every counted closed paper trade to have a journal entry.
Paper evidence blocks journal entries that report a rule break or emotional override.
Paper evidence must be generated as a report before the paper-evidence gate can pass.
The risk kill switch must be clear.
A clean daily review report is required.
Broker statement reconciliation must match Aurex closed-trade count, net P/L, fees, and slippage.
Broker statement CSV preflight derives trade count, net P/L, fees, slippage, and statement window from closed-trade statement rows without creating a report.
The first-profit milestone report audits net realized P/L after fees, trade journals, risk lineage, daily/weekly loss breaches, broker statement reconciliation, kill-switch state, and live-execution availability.
Daily review flags daily loss breaches, weekly loss breaches, three consecutive losses, missing journals, journaled rule breaks, and journaled emotional overrides.
Broker, account, jurisdiction, and live execution approval must be explicit.
Each approval domain is stored as an approval or revocation record with approver and evidence reference.
The approval packet stores broker name, account label, account type, asset class, jurisdiction, terms reference, fee reference, margin reference, account constraints reference, execution policy reference, fee/slippage model reference, paper-to-live checklist reference, optional sandbox test reference, no-leverage status, and credential-storage status.
```

Implemented guardrails:

```text
Activation attempts are audits only.
Activation attempts never submit broker orders.
Activation attempts never enable the live trading flag.
Plan updates force live_trading_enabled back to false.
No live broker credentials are accepted.
No live execution adapter exists in Stage 14 guard mode.
Approval records do not enable live trading.
Paper-evidence reports only read paper-trading analytics.
Paper-evidence reports never excuse missing trade lineage or oversized risk.
Paper-evidence reports never excuse missing trade journals or journaled rule violations.
Broker-statement reports only reconcile reviewed statement totals against closed-trade analytics; they do not enable live execution.
Broker-statement CSV reconciliation refuses malformed rows and reuses the same broker-statement gate when the CSV is READY.
First-profit milestone reports remain BLOCKED while no live broker execution adapter exists, even if net P/L, journal, risk, and statement evidence are otherwise clean.
Approval packets create only review-mode accounts and non-live broker connections.
Packets that indicate stored credentials remain DRAFT and keep the broker/account gate blocked.
Packets that indicate leverage is allowed remain DRAFT and keep the broker/account gate blocked.
```

Verified:

```text
Default live micro-deployment state is BLOCKED and non-live.
Plan updates normalize symbols and remain non-live.
Too-large risk settings fail the tiny-risk gate.
Daily review reports are blocked when reconciliation is not matched.
Daily review reports become VIOLATION when the first-live failure protocol is breached.
Daily review reports snapshot daily P/L, weekly P/L, loss limits, consecutive losses, readiness violations, protocol violations, and journal audit details.
Activation attempts return blocking gate keys and do not enable live trading.
Static dashboard contract confirms the activation-attempt audit summary row is served.
Dashboard contract includes the Live Micro-Deployment panel and API calls.
Accepted backtest evidence is blocked when missing or scoped to the wrong strategy, and passes only when a stored accepted backtest matches the deployment strategy and selected symbols.
Weak paper evidence generates a BLOCKED report with explicit reasons.
Same-day 100-trade paper evidence remains BLOCKED until the 30-calendar-day window and sustained-coverage requirements are met.
Sparse 30-calendar-day paper evidence remains BLOCKED when active trading days are too low or one day dominates the trade count.
Strong distributed 30-calendar-day paper evidence fixtures generate a PASS report and update the paper-evidence gate.
Paper-evidence reports expose minimum trades, first/latest trade timestamps, observed calendar days, minimum calendar days, active trading days, and single-day concentration.
Paper-evidence reports expose strategy/symbol scope, in-scope trade count, and out-of-scope trade count.
Paper-evidence reports expose max allowed drawdown, unexplained trade count, and risk-rule violation count.
Paper-evidence reports block excessive drawdown, missing trade lineage, and trades exceeding approved risk decision sizing.
Paper-evidence reports expose journaled trade count, unjournaled trade count, and journal rule violation count.
Paper-evidence reports block missing journals, journaled rule breaks, and journaled emotional overrides.
Trade journal API records auditable journal entries for paper trades.
Broker statement reconciliation blocks mismatched statement trade counts, net P/L, fees, and slippage.
Broker statement reconciliation passes only when a non-empty statement window matches Aurex closed-trade analytics.
Broker statement CSV preflight summarizes READY and rejected rows, and reconcile-csv passes the same statement gate while malformed CSV rows create no report.
First-profit milestone reports block empty or under-target ledgers and missing broker statements.
First-profit milestone reports can show all accounting, journal, risk-lineage, loss-limit, and statement evidence as clean while still blocking only on live_execution_adapter_not_implemented.
Approval records update the explicit-approval gate while activation remains blocked.
Static dashboard contract confirms explicit approval record fields and submit control are served.
Static dashboard contract confirms the first-profit milestone run control is served.
Complete no-credentials approval packets link a review-only LIVE broker connection and account, passing only the broker/account selection gate.
Credential-stored packets remain DRAFT and keep the broker/account selection gate blocked.
Leveraged packets remain DRAFT and keep the broker/account selection gate blocked.
Static dashboard contract confirms approval-packet due-diligence fields and submit control are served.
Full local test suite passed.
Ruff passed.
Real HTTP smoke test confirmed /live/deployment, plan update, daily review, and activation-attempt endpoints keep activation_allowed false and live_trading_enabled false.
Real HTTP smoke test confirmed daily review snapshots first-live failure-protocol fields while activation remains false.
Real HTTP smoke test confirmed broker reconciliation snapshots broker/Aurex positions and activation remains false.
Real HTTP smoke test confirmed a broker fill fee mismatch reports broker_fee_mismatch, snapshots broker fee total 1.25000000 against Aurex order fee total 0, fails reconciliation/readiness, keeps live_trading_enabled false, and closes the temporary HTTP port after shutdown.
Real HTTP smoke test confirmed a broker statement mismatch blocks on statement_net_pl_mismatch, a corrected statement passes the statement gate, activation_allowed remains false, live_trading_enabled remains false, and the temporary HTTP port closes after shutdown.
Real HTTP smoke test confirmed 50 closed and journaled trades with net P/L 161.57338093, a PASS broker statement, and a first-profit milestone report blocked only by live_execution_adapter_not_implemented while activation_allowed and live_trading_enabled remain false and the temporary HTTP port closes after shutdown.
Runtime smoke confirmed the dashboard first-profit milestone control is served and the milestone report remains BLOCKED while live execution is unavailable.
Runtime smoke confirmed activation-attempt audit returns blocking gate keys, the dashboard serves the audit row, activation_allowed remains false, and live_trading_enabled remains false.
Real HTTP smoke test confirmed approval and paper-evidence endpoints persist auditable evidence while activation remains false.
Real HTTP smoke test confirmed all four explicit approvals can be recorded, a complete no-credentials/no-leverage packet passes the broker/account gate, credential-stored and leveraged draft packets block it, dashboard packet and approval controls are served, and activation remains false.
Real HTTP smoke test confirmed empty paper evidence blocks at 0/100 trades and 0/30 calendar days with explicit reasons.
Static dashboard HTTP verification confirmed the Live Micro-Deployment panel serves the Paper progress, Paper integrity, Journal coverage, Statement reconciliation, First profit milestone, and Broker diligence rows.
Static dashboard contract confirms broker-statement CSV preflight/reconcile controls and summary fields are served.
Static dashboard contract confirms the Backtest evidence row is served.
Browser DOM verification showed the Live Micro-Deployment panel with BLOCKED state, live enabled No, trend_pullback_v1, BTCUSDT, 0.25% risk, $100 target, and the visible blocking gates.
Browser DOM verification confirmed the Evidence button updates paper evidence to BLOCKED and keeps approvals at 0/4 and live enabled No.
Browser DOM verification confirmed Broker packet changes to COMPLETE after a review packet is submitted and live enabled remains No.
In the current paper-evidence-window verification session, the in-app browser blocked localhost navigation with ERR_BLOCKED_BY_CLIENT and Chrome headless emitted no DOM output, so the new Paper progress row is static-route and contract verified rather than browser-DOM verified.
Screenshot capture timed out in the in-app browser and Chrome headless did not emit a file, so Stage 14 visual proof remains DOM/API/contract verified rather than screenshot-archived.
```

### Stage 15: Real Paper Evidence Intake

Created:

```text
PaperEvidenceImportBatch persistence model
Alembic migration for paper evidence import batches
Paper evidence CSV import service
Paper evidence collection status service
Paper evidence preflight/import analysis summary
POST /paper/evidence/preflight-csv
POST /paper/evidence/import-csv
GET /paper/evidence/collection-status
GET /paper/evidence/imports
GET /paper/evidence/imports/{batch_id}
GET /paper/evidence/template.csv
Dashboard Paper Evidence Intake panel
Glassmorphism dashboard refresh with first-screen market preview
Paper evidence import integration tests
```

Implemented behavior:

```text
Paper evidence CSV imports require a source and source reference.
Paper evidence CSV preflight uses the same parser, duplicate detection, stop-distance risk reconciliation, and realized P/L checks as import, but creates no batches, trades, signals, journals, or equity points.
Preflight and import responses include analysis_summary with status counts, rejected reasons, a fix queue, active trading days, calendar span, net P/L, total fees, total slippage, and strategy/symbol/direction counts.
Each imported row requires external_trade_id, strategy, symbol, timeframe, direction, opened_at, closed_at, entry_price, exit_price, stop_loss, take_profit, quantity, risk_amount, fees, slippage, close_reason, journal_author, journal_thesis, rule_followed, and emotional_override.
Rows reconstruct the full audit chain: Signal, approved RiskDecision, filled PaperOrder, closed PaperTrade, closed Position, EquityCurvePoint, and TradeJournalEntry.
Rows are imported in chronological close order so the equity curve and drawdown evidence follow the trade sequence.
Duplicate source/external_trade_id rows are skipped and do not double-count paper trades.
Duplicate external_trade_id values inside the same CSV are rejected before persistence.
Rows with invalid direction, invalid price geometry, bad timestamps, negative costs, mismatched stop-distance risk, or mismatched provided realized P/L are rejected with row-level reasons.
Imported risk_amount must reconcile to abs(entry_price - stop_loss) * quantity within the database money precision.
Import batches persist source, source_reference, import_hash, counts, row_results, required_headers, evidence_snapshot, and the analysis summary inside the evidence snapshot.
Import history and detail endpoints return persisted batch outcomes for review.
The collection-status endpoint aggregates accepted-backtest gate status, paper-evidence gate status, import totals, remaining trade/day gaps, blocking reasons, and next actions.
The CSV template endpoint exposes the required headers plus optional market regime, journal notes, and realized P/L verification columns.
The dashboard can load the template, preflight CSV evidence, submit CSV evidence, render the latest import batches, show export-window analysis, expose the fix queue, and show collection status.
The dashboard now uses a dark glassmorphism command-center design with a first-screen market preview, luminous status cards, frosted panels, and TradingView-style visual density while keeping live mode visibly locked.
Imported trades are compatible with Stage 14 paper-evidence integrity and journal audits without special exemptions.
Stage 14 paper-evidence integrity audits independently flag closed paper trades whose stored risk_amount does not match abs(entry_price - stop_loss) * quantity.
Stage 14 paper-evidence coverage audits require at least 15 active trading days and block evidence when one day contains more than 25% of counted trades.
Stage 14 paper-evidence reports count only the selected deployment strategy and symbols; unrelated paper trades are excluded and surfaced as out-of-scope evidence.
The dashboard shows Paper scope and Paper coverage alongside progress, integrity, and journal coverage.
```

Implemented guardrails:

```text
The importer creates paper evidence only; it does not create live trades.
The importer does not accept broker credentials.
The importer does not mark paper evidence complete by itself.
Preflight does not mutate the evidence ledger.
Collection status is derived from existing import batches and Stage 14 gates; it does not weaken readiness requirements.
The Stage 14 accepted-backtest, 100-trade, 30-calendar-day, expectancy, profit-factor, drawdown, risk-lineage, and journal gates still decide readiness.
Live trading remains disabled.
```

Verified:

```text
Focused importer tests confirmed two CSV rows import into auditable closed paper trades.
Preflight tests confirm valid rows report READY without creating import batches or paper trades.
Preflight tests confirm duplicate external_trade_id values and risk mismatches are rejected without mutating the ledger.
Preflight and import tests confirm analysis_summary exposes status counts, net P/L, active/calendar coverage, strategy/symbol/direction counts, rejected reasons, and fix queue rows.
Stage 14 paper-evidence reports show imported rows as journaled, explained, and risk-lineage clean while still blocking on insufficient trade count.
Duplicate import tests confirmed the same source/external_trade_id rows are skipped without double-counting trades.
Duplicate-in-file import tests confirm only one trade is imported and the duplicate row is rejected.
Missing required CSV headers return HTTP 400 and create no import batch or paper trade.
Risk amount mismatches are rejected during import with risk_amount_does_not_match_entry_stop_and_quantity.
Stage 14 paper-evidence reports flag trade_risk_amount_does_not_match_stop_distance for inconsistent closed paper trades.
Import list/detail/template endpoints are tested.
Collection-status endpoint tests cover missing evidence and partial collection with accepted backtest plus two imported trades.
Static dashboard contract confirms the Paper Evidence Intake panel and API calls are served.
Static dashboard contract confirms the market preview, glassmorphism styles, and preflight controls are served.
Static dashboard contract confirms export-window analysis and fix-queue fields are served.
Static dashboard contract confirms broker-statement CSV preflight/reconcile controls are served.
Static dashboard contract confirms approval-packet due-diligence fields and submit control are served.
Static dashboard contract confirms explicit approval record fields and submit control are served.
Static dashboard contract confirms the first-profit milestone run control is served.
Static dashboard contract confirms the activation-attempt audit summary row is served.
Runtime smoke confirmed /dashboard, /paper/evidence/imports, /paper/evidence/template.csv, and /live/deployment return 200 while live deployment remains BLOCKED and live_trading_enabled remains false.
Focused live-deployment tests confirm same-day and sparse-span evidence are blocked while distributed 30-day evidence can pass.
Focused live-deployment tests confirm out-of-scope strategy trades cannot satisfy the paper-evidence gate.
Focused live-deployment tests confirm missing and wrong-scope backtests cannot satisfy the accepted-backtest gate.
```

### Goal Continuation: Accepted Backtest Gate Hardening

Created:

```text
Out-of-sample metric snapshots for stored backtest reports
Trade distribution snapshots for dated backtest trades
Market-regime breakdown snapshots for stored backtest trades
Acceptance criteria for sample windows, out-of-sample metrics, cost model, slippage model, and risk snapshot
Acceptance criteria for dated trades, active trading days, single-day concentration, and market-regime coverage
Independent Stage 14 live-readiness audit for accepted backtests
Regression coverage for deliberately weakened self-accepted backtest reports
Regression coverage for concentrated self-accepted backtest reports
```

Implemented behavior:

```text
Backtest reports now store all-trade, in-sample, and out-of-sample metric snapshots when dated trades and sample windows are supplied.
Backtest reports now store dated-trade distribution and performance by market regime.
Backtest acceptance can require non-overlapping in-sample/out-of-sample windows, enough out-of-sample trades, positive out-of-sample expectancy, out-of-sample profit factor, cost assumptions, slippage assumptions, risk assumptions, dated trades, enough active trading days, limited single-day concentration, and complete market-regime labels.
The live micro-deployment accepted-backtest gate independently requires at least 100 total trades, at least 30 out-of-sample trades, at least 15 active backtest trading days, no single day above 25% of counted backtest trades, complete market-regime labels, and a declared max-drawdown limit for the selected strategy/symbol scope.
The live gate blocks a report that passed only because its submitted acceptance criteria were weakened below the live-readiness floor.
The live gate blocks concentrated backtests that pass only because their submitted active-day or concentration criteria were weakened below the live-readiness floor.
The live gate surfaces backtest live-readiness reasons and the out-of-sample evidence snapshot in the gate evidence.
The live gate surfaces trade-distribution and market-regime evidence snapshots in the gate evidence.
When multiple scoped accepted reports exist, Aurex prefers the newest report that satisfies the live-readiness floor while still exposing the latest weaker accepted report if no stronger report exists.
```

Verified:

```text
Focused tests passed for the backtest lab, live micro-deployment guard, and paper evidence import.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Backtest Report CSV Workflow

Created:

```text
POST /backtests/reports/preflight-csv
POST /backtests/reports/import-csv
GET /backtests/report-template.csv
Strict backtest report CSV parser
Backtest report CSV row-level READY/REJECTED outcomes
Backtest report CSV analysis summary and fix queue
End-to-end CSV import coverage for the accepted-backtest live-readiness gate
```

Implemented behavior:

```text
Operators can preflight exported backtest trades before mutating the backtest ledger.
Preflight requires realized_pl, closed_at, and market_regime headers.
Optional strategy and symbol columns are validated against the report scope when present.
Rejected rows return row-level reasons and a grouped fix queue.
Import refuses any CSV that is not READY, so partial or malformed exports do not create backtest reports.
READY CSV imports create a normal BacktestRun and BacktestResult with the same strict acceptance, in-sample/out-of-sample, trade-distribution, and regime-breakdown checks as JSON reports.
The accepted-backtest live-readiness gate can pass from a strict CSV-imported report when the selected strategy/symbol evidence meets the live-readiness floor.
```

Verified:

```text
Focused backtest CSV workflow tests passed.
Focused live micro-deployment test confirms a strict CSV-imported backtest can satisfy the accepted-backtest gate while activation remains blocked by other gates.
Live trading remains disabled.
```

### Goal Continuation: Dashboard Backtest Evidence Intake

Created:

```text
Dashboard Backtest Evidence Intake panel
Backtest report metadata form
Backtest CSV template loader
Backtest CSV preflight action
Backtest CSV import action
Backtest analysis summary rows
Backtest report history table
Static dashboard contract coverage for the new controls
```

Implemented behavior:

```text
The dashboard can load the strict backtest report CSV template from /backtests/report-template.csv.
The dashboard can submit strategy, version, symbol scope, sample windows, cost model, slippage model, risk snapshot, acceptance criteria, and CSV text to /backtests/reports/preflight-csv.
The dashboard can import READY CSV evidence through /backtests/reports/import-csv.
The dashboard renders acceptance, out-of-sample, trade-distribution, regime-coverage, and fix-queue summaries.
The dashboard lists recent backtest reports and their accepted/blocked status, trade count, OOS trade count, scope, and config hash.
Backtest CSV import remains an evidence operation only; live activation remains governed by the existing live-readiness gates.
```

Verified:

```text
Static dashboard test passed.
Node syntax check passed for apps/frontend/app.js.
Live trading remains disabled.
```

### Goal Continuation: Pre-Paper Backtest Eligibility Gate

Created:

```text
Paper backtest eligibility helper
Risk-engine pre-paper accepted-backtest gate
Regression test for risk rejection when accepted backtest evidence is missing
Accepted-backtest fixture helper for execution-positive integration tests
```

Implemented behavior:

```text
Risk-approved paper execution now requires accepted backtest evidence for the signal strategy and symbol.
The pre-paper gate requires at least 100 historical trades, at least 30 out-of-sample trades, positive out-of-sample expectancy, out-of-sample profit factor >= 1.15 when applicable, a declared max-drawdown limit, non-overlapping sample windows, at least 15 active backtest trading days, no single day above 25% of counted backtest trades, full market-regime coverage, and recorded cost, slippage, and risk assumptions.
Signals that pass ordinary setup checks but lack accepted backtest evidence are risk-rejected before position sizing or paper order creation.
Immediate safety rejections such as kill switch, disabled strategy, stale signal, invalid stops, daily/weekly loss limits, and open-position limits still speak before the pre-paper evidence gate.
Live trading remains disabled.
```

Verified:

```text
Focused risk, webhook, strategy portfolio, broker readiness, and market-state tests passed.
Live trading remains disabled.
```

### Goal Continuation: Risk Decision Backtest Gate Audit Snapshot

Created:

```text
Rule evaluation result object for carrying audit snapshot fragments
RiskDecision rules_snapshot paper_backtest_gate evidence
Regression assertions for approved and blocked pre-paper gate snapshots
Webhook response assertion for operator-visible backtest-gate evidence
```

Implemented behavior:

```text
Risk decisions that reach the pre-paper accepted-backtest gate now store paper_backtest_gate inside rules_snapshot.
Approved paper-trading risk decisions record the accepted backtest run id, gate reason, and eligibility evidence snapshot that authorized the paper trade.
Rejected paper-trading risk decisions caused by missing or insufficient accepted backtest evidence record the exact gate reason, scoped strategy/symbol, requirements, and evidence reasons.
If an accepted backtest passes but a later sizing check rejects the signal, the decision still retains the backtest-gate snapshot that authorized progression to sizing.
Webhook and signal API responses expose the same rules_snapshot evidence through latest_risk_decision.
Live trading remains disabled.
```

Verified:

```text
Focused risk and TradingView webhook tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Strategy Evidence Review Decision Artifact

Created:

```text
StrategyEvidenceDecision domain enum
StrategyEvidenceReview persistence model
Alembic migration for strategy_evidence_reviews
POST /live/deployment/evidence-review/run
GET /live/deployment/evidence-reviews
Dashboard Strategy review row and Evidence review control
Regression coverage for BLOCKED, DO_NOT_TRADE, and CANDIDATE review outcomes
```

Implemented behavior:

```text
Aurex can now persist a strategy evidence review that snapshots the current pre-live evidence gates, latest paper-evidence report, latest broker-statement reconciliation, latest first-profit milestone report, activation state, and live-trading flag.
The review returns BLOCKED when required evidence is incomplete, missing, or not reconciled.
The review returns DO_NOT_TRADE when mature evidence is negative or unsafe, including non-positive expectancy, insufficient profit factor, excessive drawdown, unexplained trades, risk-rule violations, journal rule violations, or a live flag enabled before review completion.
The review returns CANDIDATE only when the scoped pre-live evidence gates pass; this does not authorize live trading and does not bypass broker/account approval, daily review, explicit approval, live adapter, or activation gates.
The dashboard can run the review and displays the latest strategy evidence decision alongside deployment readiness rows.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment and schema tests passed.
Static dashboard contract test passed.
Node syntax check passed for apps/frontend/app.js.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Do-Not-Trade Review Enforcement

Created:

```text
Risk-engine lookup for latest scoped strategy evidence review
RiskDecision rules_snapshot strategy_evidence_review_gate evidence
Regression test for risk rejection after a DO_NOT_TRADE review
Webhook regression test proving DO_NOT_TRADE prevents paper execution
```

Implemented behavior:

```text
After an accepted-backtest gate passes, the risk engine now checks the latest strategy evidence review matching the signal strategy and symbol before position sizing.
A latest DO_NOT_TRADE review blocks risk approval and prevents paper order/trade creation.
Risk decisions that reach this gate record strategy_evidence_review_gate with the review id, decision, reasons, next actions, scope, and reviewed timestamp.
Missing strategy evidence reviews and latest non-DO_NOT_TRADE reviews do not replace the accepted-backtest gate, so paper trading can still collect evidence until mature evidence proves the strategy should stop.
The TradingView webhook path surfaces the review block through latest_risk_decision.rules_snapshot and leaves /trades empty.
Live trading remains disabled.
```

Verified:

```text
Focused risk and TradingView webhook tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Strategy Evidence Review Live Gate

Created:

```text
strategy_evidence_review_clear live-deployment gate
Scoped latest strategy evidence review lookup for deployment strategy and symbols
Readiness status mapping for CANDIDATE, BLOCKED, DO_NOT_TRADE, and missing reviews
Regression assertions for missing, BLOCKED, DO_NOT_TRADE, and CANDIDATE review gate states
```

Implemented behavior:

```text
Live deployment readiness now requires a latest scoped CANDIDATE strategy evidence review.
Missing strategy evidence reviews keep the new gate NOT_RUN.
BLOCKED strategy evidence reviews keep the new gate BLOCKED.
DO_NOT_TRADE strategy evidence reviews make the new gate FAIL and keep activation blocked.
CANDIDATE strategy evidence reviews make the new gate PASS, but activation still remains blocked unless every other required gate and live flag condition is independently satisfied.
The strategy evidence review generator remains independent from this new gate so operators can create a review from current evidence before the live gate evaluates it.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Strategy Review Freshness Gate

Created:

```text
Strategy evidence review freshness audit for live deployment gates
Reviewed/current artifact id snapshots for accepted backtest, paper evidence, and broker statement
Regression coverage for stale CANDIDATE reviews after newer paper evidence
```

Implemented behavior:

```text
A CANDIDATE strategy evidence review now passes the live gate only if it still matches the current latest accepted backtest, paper-evidence report, and broker-statement reconciliation for the deployment scope.
The strategy_evidence_review_clear gate records reviewed_artifacts, current_artifacts, and freshness_reasons.
If newer evidence appears after a CANDIDATE review, the gate changes from PASS to BLOCKED until a fresh strategy evidence review is generated.
Missing reviews still return NOT_RUN, BLOCKED reviews remain BLOCKED, and DO_NOT_TRADE reviews remain FAIL.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Dashboard Strategy Review Freshness Summary

Created:

```text
Dashboard Strategy review summary tied to strategy_evidence_review_clear gate
Static dashboard contract assertion for strategyEvidenceReviewSummary
```

Implemented behavior:

```text
The dashboard Strategy review row now shows the live gate status, latest review decision, and the first freshness or review reason.
Stale CANDIDATE reviews therefore render as BLOCKED with the freshness reason instead of appearing clean just because the latest stored review says CANDIDATE.
Live trading remains disabled.
```

Verified:

```text
Static dashboard contract test passed.
Node syntax check passed for apps/frontend/app.js.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Strategy Review Plan Freshness Gate

Created:

```text
Deployment plan snapshot inside strategy evidence reviews
Freshness audit comparison for reviewed/current deployment strategy, symbols, risk limits, open-position cap, and target profit
Regression coverage for stale CANDIDATE reviews after micro-live risk changes
```

Implemented behavior:

```text
Strategy evidence reviews now record the deployment plan settings they reviewed.
The strategy_evidence_review_clear gate compares the reviewed plan snapshot against the current deployment plan.
If strategy, symbol scope, risk_per_trade, max_daily_loss, max_weekly_loss, max_open_positions, or target_net_profit changes after a CANDIDATE review, the gate becomes BLOCKED until a fresh review is generated.
The gate exposes reviewed_plan, current_plan, and deployment_plan_*_changed_since_review freshness reasons for operator audit.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Explicit Approval Freshness Gate

Created:

```text
Approval context snapshots for recorded live approval records
Explicit approval freshness audit for current deployment plan, evidence artifacts, strategy review, and approval packet
Regression coverage for stale approvals after micro-live risk changes
```

Implemented behavior:

```text
Each explicit approval now records the deployment plan, accepted backtest, paper-evidence report, broker-statement report, strategy evidence review, and approval packet context that was approved.
The explicit_user_approval gate only passes when broker, account, jurisdiction, and live-execution approvals are approved, unexpired, and still match the current deployment context.
If the deployment plan or evidence context changes after approval, the affected approval booleans become false and the gate reports *_changed_since_approval reasons.
Decimal plan values are normalized before freshness comparison so SQL numeric scale differences do not create false stale approvals.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Live Execution Adapter Readiness Gate

Created:

```text
Disabled live execution adapter boundary
Required live_execution_adapter_ready deployment gate
Dashboard live execution adapter summary row
Regression coverage that a true live flag cannot bypass the missing adapter
```

Implemented behavior:

```text
Live execution availability is now audited through a dedicated adapter boundary instead of a hidden module constant.
The default adapter is disabled, reports implemented false, supports_live_order_submission false, and blocks with live_execution_adapter_not_implemented.
The live_execution_adapter_ready gate is required in deployment status and activation audits.
First-profit milestone reports snapshot the same adapter audit, so a clean accounting report cannot imply live readiness without a concrete execution adapter.
The dashboard surfaces the adapter gate status, selected adapter, and first blocking reason.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment and dashboard tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Paper Evidence Report Freshness Gate

Created:

```text
Paper-evidence ledger snapshots inside generated evidence reports
Current ledger freshness audit for the paper_evidence_complete gate
Material trade, journal, and risk-lineage hashes for stale-report detection
Dashboard Paper freshness summary row
Regression coverage for stale PASS reports after trade-ledger and journal changes
```

Implemented behavior:

```text
Generated paper-evidence reports now snapshot the selected strategy/symbol scope, counted trade ids, material trade hash, journal hash, lineage hash, performance metrics, coverage metrics, scope counts, journal counts, and integrity counts.
The paper_evidence_complete gate recomputes the current ledger and blocks a previously PASS report if trades, material trade fields, journals, risk lineage, coverage, scope, or plan strategy/symbols changed after the report was generated.
Stale evidence exposes reviewed_ledger, current_ledger, and paper_evidence_*_changed_since_report freshness reasons for audit.
The dashboard surfaces Paper freshness from the live gate so stale evidence is visible without opening raw gate JSON.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment, paper evidence import, and dashboard tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: Broker Statement Freshness Gate

Created:

```text
Broker-statement ledger snapshots inside reconciliation reports
Current statement-window ledger freshness audit for broker_statement_reconciliation
Regression coverage for stale PASS statements after trade P/L and fee changes
Dashboard Statement freshness summary row
```

Implemented behavior:

```text
Broker-statement reconciliation now snapshots the selected strategy/symbol scope, reviewed statement window, counted Aurex trade ids, material trade hash, Aurex trade count, net P/L, fees, and slippage.
The broker_statement_reconciliation gate recomputes the current statement-window ledger and blocks a previously PASS report if trade membership, material P/L/cost fields, scope, totals, or window evidence changed after reconciliation.
First-profit milestone checks now treat broker statements with freshness reasons as not current.
The dashboard surfaces Statement freshness from the live gate so stale broker reconciliation is visible to the operator.
Live trading remains disabled.
```

Verified:

```text
Focused live micro-deployment tests passed.
Full local test suite passed.
Ruff passed.
Live trading remains disabled.
```

### Goal Continuation: TradingView Completed-Trade Evidence

Created:

```text
TradingView Strategy Tester completed-trades CSV auto-detection and normalization
Persisted backtest_trades ledger linked to backtest_runs
Backtest source format, source reference, and deterministic evidence hash
GET /backtests/reports/{id}/trades
Trade-ledger integrity checks in paper and live-readiness gates
TradingView fixture plus weak, strong, missing-cost, round-trip, and tamper tests
Operator runbook at docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
```

Implemented behavior:

```text
Common English TradingView entry/exit exports are paired into completed Aurex trades.
Malformed, empty, header-only, duplicate, and unmatched exports fail with row-level reasons.
Fees and slippage are persisted when supplied and remain explicitly missing when absent.
Reported TradingView net P/L is not charged a second time inside Aurex.
Every normalized trade is persisted with its source rows and included in a stable hash.
Paper and live-readiness gates block missing, count-mismatched, or modified trade ledgers.
The trend Pine script preserves regime labels in order IDs and enforces the recorded date window, 0.05% commission, and two-tick slippage.
trend_pullback_v1 version 1.1.0 sizes fractional positions from stop distance at 0.5% equity risk and caps position value at 95% of equity, preventing unaffordable one-contract BTC orders from producing an empty Strategy Tester report.
Weak evidence remains rejected; only the all-gates strong fixture is accepted.
Live trading remains disabled.
```

Verified:

```text
Focused backtest, database migration, Pine, dashboard, risk, webhook, and live-readiness tests passed.
The local SQLite database upgraded from 20260607_0017 to 20260623_0018.
Full local test suite passed with 120 tests.
Ruff and dashboard JavaScript syntax checks passed.
Runtime HTTP smoke auto-detected the TradingView fixture, paired two completed trades, rejected zero rows, and returned a deterministic evidence hash.
TradingView compilation and real-market results remain external operator steps.
```

### Goal Continuation: Single-View Operations Console

Created:

```text
Stateful sidebar view navigation with URL history and keyboard controls
One visible operational surface at a time instead of anchor scrolling
Dedicated fixed notification region with success, warning, and error states
Button busy states and explicit last-sync/degraded-source status
Resilient Promise.allSettled dashboard refreshes
Grouped deployment actions adjacent to their evidence forms
Responsive horizontal navigation for tablet and mobile widths
Navigation queue counts for signals, trades, backtests, evidence, and events
```

Corrected:

```text
Duplicate evidence section id and malformed nested section
API errors overwriting health text above the Command navigation item
One failed endpoint preventing every dashboard module from rendering
Oversized marketing-style command hero and excessive nested mini-cards
Deployment gate results buried below unrelated forms
Mobile navigation expanding into a tall button grid
```

Verified:

```text
Unique-id and balanced-tag structural audits passed.
Dashboard navigation/notification regression contracts passed.
Dashboard JavaScript syntax and Ruff passed.
Full local test suite passed with 121 tests.
HTTP smoke confirmed the served navigation, notification, refresh, and active-view assets.
The in-app visual browser connection was unavailable, so no fresh interactive screenshot is claimed.
Live trading remains disabled.
```

### Goal Continuation: MKT Research Evidence Ledger

Created:

```text
strategy_research_backtest_runs model and Alembic migration
Persistent research-gate run records with metrics, requirements, reasons, reviewed_at, and evidence hash
GET /strategies/research-candidates/{candidate_id}/evidence
Candidate evidence response with latest gate run, recent gate runs, recent observations, and summary counts
Dashboard selected-candidate evidence drilldown
Dashboard gate-run history and observation evidence tables
Selected-candidate backtest flow so Inspect follows the chosen candidate
```

Verified:

```text
Research candidate, dashboard, and Alembic schema focused tests passed.
Full local test suite passed with 142 tests.
Ruff passed.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Research Readiness Queue

Created:

```text
GET /strategies/research-candidates/readiness-queue
Evidence-state ranking for MKT-derived research candidates
Readiness states for paper-research eligible, gate-blocked, ready-for-gate, and needs-resolution
Next-action summaries for blocked or incomplete candidates
Dashboard Readiness queue panel in the Strategy tab
Inspect buttons that load the selected candidate evidence drilldown
```

Verified:

```text
Focused research-candidate and dashboard tests passed.
Full local test suite passed with 143 tests.
Ruff passed.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Intent Research Gate

Created:

```text
Paper-engine guard requiring accepted Aurex research-gate evidence for mkt_* prediction-market paper intents
Research-gate intent_snapshot with required/approved, candidate id, backtest run id, evidence hash, reason, and live_execution=blocked
Auditable RISK_BLOCK evidence payloads for mkt_* paper intents rejected by missing or failed research gates
Regression coverage for blocked mkt_* paper intents and allowed mkt_* paper intents after accepted research-gate evidence
Neutral paper-engine fixture strategies for raw simulator lifecycle tests
```

Verified:

```text
Focused prediction-market API, paper-engine, and strategy-research tests passed.
Full local test suite passed with 144 tests.
Ruff passed on the touched prediction-market files and tests.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Intent Gate UI

Created:

```text
Prediction Markets Paper intent gate panel
Pre-intent strategy gate status sourced from the research readiness queue
Latest intent-gate result display from prediction order intent snapshots
Rejected-intent success notification that names rejection and evidence recording
Dashboard regression coverage for the visible paper-intent gate
```

Verified:

```text
Dashboard contract and JavaScript syntax checks passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Demo Readiness

Created:

```text
GET /prediction-market/paper/demo-readiness
Paper-demo readiness response with blocked, ready-to-run, and verified states
Checks for live-disabled operation, eligible MKT research candidate evidence, contract snapshots,
approved paper-intent gate evidence, paper fills, settlement, and matched reconciliation
Prediction Markets dashboard paper-demo readiness panel
Dashboard regression coverage for the visible demo readiness fields
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Full test suite passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
In-process dashboard route smoke confirmed health ok, live trading disabled, the Batch replay button rendered,
and the dashboard JavaScript exposed the batch route and action.
Live execution remains disabled.
```

### Goal Continuation: Prediction Market Snapshot CSV Import

Created:

```text
Prediction contract snapshot CSV importer
GET /prediction-market/contracts/template.csv
POST /prediction-market/contracts/preflight-csv
POST /prediction-market/contracts/import-csv
Aurex-format CSV support for strict contract snapshot intake
My-Krypt-Trader markets-table CSV support with explicit derived no-side quote metadata
Row-level READY/REJECTED preflight results and actionable quote counts
Prediction Markets dashboard Snapshot CSV controls
Dashboard regression coverage for the CSV import surface
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Full test suite passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
In-process dashboard route smoke confirmed health ok, live trading disabled, the Batch preflight button rendered,
and the dashboard JavaScript exposed the preflight route and action.
Live execution remains disabled.
```

### Goal Continuation: Guided Prediction Paper Demo Run

Created:

```text
POST /prediction-market/paper/demo-run
GET /prediction-market/paper/demo-progress
Guided paper-demo orchestration using the existing research gate, risk limits, paper order,
fill, settlement, and reconciliation code
Progress accounting for 100 closed paper/demo records over 30 calendar days
Fee-net realized P/L and latest reconciliation status in the progress response
Prediction Markets dashboard Demo run control
Prediction Markets dashboard paper-demo evidence progress panel
Regression coverage for accepted guided demo runs and rejected runs missing MKT research evidence
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Full test suite passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
In-process dashboard route smoke confirmed health ok, live trading disabled, and campaign-quality
fields for unique contracts, provenance, contract concentration, and clean ledger coverage rendered.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Demo Progress Quality Gate

Created:

```text
Paper-demo progress quality checks
Active-day target and remaining active-day count
Single-day concentration check and max-day share
Fee-net expectancy, profit factor, drawdown, win/loss/breakeven counts, and unique contract count
Structured progress checks list with next failing action
Dashboard active-day, expectancy, and concentration rows
Regression coverage for quality checks on guided paper-demo progress
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Resolved Prediction Market Outcome Intake

Created:

```text
Optional settlement_value on PredictionContractSnapshot and PredictionContractSnapshotRequest
Settlement outcome persistence on imported prediction contract snapshots
Aurex CSV settlement_value column support
My-Krypt-Trader markets result/settlement_value import support
Guided paper-demo settlement fallback from imported contract settlement_value
Manual settlement UI now requires explicit settlement input
Regression coverage for guided paper-demo settlement from imported resolved MKT market rows
```

Verified:

```text
Focused prediction-market API, paper-engine, and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: General Backtest Walk-Forward Gate

Created:

```text
Walk-forward validation fields on general backtest acceptance criteria
Chronological walk-forward metrics snapshot in Backtest Lab reports and CSV preflight analysis
Acceptance rejection when walk-forward window count or pass rate misses the configured threshold
Independent paper-trading eligibility audit for stored walk-forward evidence
Dashboard Backtest Evidence Intake walk-forward summary row
Dashboard default acceptance JSON exposes walk-forward thresholds
Dashboard backtest report and deployment evidence summaries include walk-forward pass/window counts
Regression coverage for walk-forward decay and accepted TradingView evidence snapshots
```

Implemented behavior:

```text
Backtest reports now split dated trades into chronological walk-forward windows.
Each window must have enough trades, positive expectancy, and profit factor above the configured minimum, with no-loss profitable windows treated as passable.
Stored accepted reports without walk-forward evidence are blocked from paper-trading eligibility until regenerated.
The live-readiness accepted-backtest gate independently requires at least three walk-forward windows and at least a 66% pass rate.
Live execution remains disabled.
```

Verified:

```text
Focused backtest lab, live micro-deployment, and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Manual Cancellation

Created:

```text
Explicit paper order-intent cancellation endpoint
Manual cancellation support for created, submitted, and partially-filled prediction paper orders
Distinct CANCELLED lifecycle handling with ORDER_CANCELLED evidence payloads and operator reasons
Dashboard Cancel action for prediction paper intents
Regression coverage for partial-fill cancellation through the paper engine and API
```

Implemented behavior:

```text
Filled and rejected intents cannot be manually cancelled.
Already-cancelled or expired intents return idempotently.
Partial fills retain their open paper position and reconciliation remains matched.
Stale expiry remains separate from operator-initiated cancellation.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market paper engine, API, and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
In-process dashboard route smoke confirmed health ok, live trading disabled, the Cancel button rendered,
and the dashboard JavaScript exposed the cancel function and /cancel route.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Demo Ledger

Created:

```text
GET /prediction-market/paper/demo-ledger
Read-only paper/demo evidence ledger composed from settlements, positions, fills, orders,
contract snapshot provenance, reconciliation reports, and immutable settlement evidence events
Dashboard Demo ledger table inside the Prediction Markets view
Regression coverage for MKT-imported clean ledger records and unreconciled blocked records
Dashboard contract coverage for the new ledger endpoint and render path
```

Implemented behavior:

```text
Closed paper/demo records expose strategy attribution, source/import provenance, MKT-import flag,
settlement evidence hash, fees, fee-net P/L, reconciliation status, countable state, and blockers.
Records are not countable unless settlement evidence exists, strategy attribution is present,
the settlement is paper-only, and a matched reconciliation exists after settlement.
Aggregate progress remains separate from record-level ledger auditability.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Full test suite passed.
Ruff passed.
Dashboard JavaScript syntax passed.
In-process dashboard route smoke confirmed health ok, live trading disabled, the demo ledger table rendered,
and the dashboard JavaScript exposed the demo-ledger route and renderer.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Demo Batch Replay

Created:

```text
POST /prediction-market/paper/demo-batch-run
Guarded batch replay across imported/resolved prediction contract snapshots
Duplicate settled contract/strategy skip for paper-demo batch collection
Dashboard Batch replay control and batch status summary
Regression coverage for multi-contract MKT resolved snapshot replay and duplicate skip
```

Implemented behavior:

```text
Batch replay reuses the single guided paper-demo lifecycle instead of creating a separate execution path.
Each batch is capped at 25 attempted records and defaults to imported snapshots with settlement values.
Already-settled contract/strategy/side records are skipped so repeated clicks cannot inflate evidence.
Batch responses include progress and ledger snapshots after replay.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Demo Batch Preflight

Created:

```text
POST /prediction-market/paper/demo-batch-preflight
Non-mutating preview of imported/resolved prediction contracts before batch replay
Dashboard Batch preflight control and preview status summary
Regression coverage proving preflight does not create intents, orders, fills, or settlements
Regression coverage for duplicate settled contract/strategy preview after replay
```

Implemented behavior:

```text
Batch preflight uses the same imported/resolved candidate selection as batch replay.
Preview rows report READY or SKIPPED with duplicate, research-gate, missing-price, batch-limit,
and max-order-cost skip reasons.
Preflight does not mutate the paper ledger.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Paper Campaign Quality Gates

Created:

```text
Paper-demo progress campaign-quality metrics for unique contracts, single-contract concentration,
imported snapshot provenance, and clean/countable ledger coverage
Dashboard visibility for unique contracts, contract concentration, provenance, and ledger-clean state
Regression coverage for imported resolved batch records and manual guided demo campaign blockers
```

Implemented behavior:

```text
Live-review readiness now requires at least 25 unique contracts and no contract above 10% of closed records.
Closed records must include imported snapshot provenance with source reference and CSV format.
Closed records must be clean/countable in the demo ledger.
Matched reconciliation must be newer than or equal to the latest settlement.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on the touched backend and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Demo Live-Readiness Bridge

Created:

```text
Live deployment prediction_demo_campaign_quality gate
MKT-only requirement for prediction paper/demo campaign quality before live review
Deployment dashboard Prediction demo summary
Regression coverage for non-MKT not-applicable pass and mkt_* NOT_RUN blocker
```

Implemented behavior:

```text
Non-MKT deployment strategies pass this gate as not applicable.
mkt_* deployment strategies require prediction paper/demo progress to pass before live readiness can proceed.
The gate reuses the prediction paper-demo progress checks so live readiness sees unique-contract,
concentration, provenance, ledger countability, and fresh reconciliation blockers.
This does not replace the existing broker/paper evidence gate.
Live execution remains disabled.
```

Verified:

```text
Focused live micro-deployment and dashboard tests passed.
Ruff passed on touched backend and tests.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Direct MKT Markets DB Import

Created:

```text
POST /prediction-market/contracts/preflight-mkt-db
POST /prediction-market/contracts/import-mkt-db
Bounded direct My-Krypt-Trader SQLite markets-table snapshot importer
Dashboard MKT DB snapshot preflight/import controls
Regression coverage for preflight non-mutation, resolved-row filtering, rejected-row reporting, and raw provenance
```

Implemented behavior:

```text
Operators can preflight or import local My-Krypt-Trader markets rows without manually converting them to CSV.
The default request is replay-oriented: resolved rows only, settlement value required, max 100 rows.
Imports reuse the same MKT markets normalization as CSV imports, including derived NO quotes and result/settlement_value handling.
Imported MARKET_SNAPSHOT evidence records raw db_path, sqlite_table, direct_db_import, source, source_reference, and raw row provenance.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched backend, importer, schemas, and tests.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Paper/Demo Campaign Replay

Created:

```text
POST /prediction-market/paper/demo-mkt-db-campaign-preflight
POST /prediction-market/paper/demo-mkt-db-campaign-run
Source-reference filtering for prediction paper/demo batch candidates
Dashboard MKT DB campaign preflight/replay controls
Regression coverage for preflight rollback, import, replay, settlement, reconciliation, duplicate skip, and countable ledger progress
```

Implemented behavior:

```text
Campaign preflight temporarily imports bounded MKT DB rows, previews the batch replay, and rolls back so contracts, intents, orders, fills, settlements, and evidence are not mutated.
Campaign run imports bounded MKT DB rows and replays them through the existing research-gated paper/demo lifecycle in one operator action.
Batch replay can now scope candidates by source_reference as well as source.
Duplicate campaign replay reports NO_NEW_CONTRACTS instead of creating duplicate evidence.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Campaign Projection

Created:

```text
Rollback-protected projected_replay summary in MKT DB campaign preflight
Projection response fields for attempted/completed records, fee-net P/L, countable records, blocked records, live-review readiness, and first failed progress gate
Dashboard projection visibility for projected fee-net P/L and first blocker
Regression coverage proving projection exists while preflight leaves the ledger unmutated
```

Implemented behavior:

```text
Campaign preflight temporarily imports DB rows, previews eligible records, runs a projected replay, summarizes the expected evidence result, and rolls back.
Projection is not counted as evidence and does not persist contracts, intents, orders, fills, settlements, reconciliations, or evidence events.
The projection can show a profitable-looking sample while still exposing failed campaign gates.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Campaign Side Sensitivity

Created:

```text
Opposite-side projected replay in MKT DB campaign preflight
Side field in campaign projection responses
Side-sensitivity warning when the opposite side projects better or results are side-fragile
Dashboard visibility for opposite-side P/L and side-sensitivity warning
Regression coverage proving selected and opposite projections both run while preflight leaves the ledger empty
```

Implemented behavior:

```text
Campaign preflight now projects the requested side and the opposite side in separate rollback cycles.
Projection output shows when the selected side underperforms the opposite side on the same imported rows.
This is a warning against hindsight-driven side choice, not a recommendation to trade the better-looking side.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Campaign Side-Rationale Guard

Created:

```text
acknowledge_side_sensitivity and side_selection_rationale fields for MKT DB campaign run
Pre-mutation server-side guard rejecting side-sensitive replay without acknowledgement and rationale
Dashboard controls for side-sensitivity acknowledgement and side rationale
Regression coverage proving rejected side-sensitive replay leaves the prediction ledger empty
```

Implemented behavior:

```text
Campaign run recomputes rollback-protected preflight before mutation.
If the projection is side-sensitive, replay is rejected unless acknowledgement is checked and the side-selection rationale is substantive.
The accepted run response records the warning, acknowledgement state, and normalized rationale.
This prevents after-the-fact side switching from silently becoming paper evidence.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Campaign Evidence Event

Created:

```text
PredictionMarketEvidenceKind.PAPER_DEMO_CAMPAIGN
Public paper-engine evidence-event recorder
Durable campaign_evidence response field for MKT DB campaign run
Dashboard campaign evidence hash visibility
Regression coverage proving accepted campaign replay writes a PAPER_DEMO_CAMPAIGN event with side-warning and rationale context
```

Implemented behavior:

```text
Accepted MKT DB campaign replay now records an immutable prediction evidence event after import/replay/progress are known.
The evidence payload includes paper-only/live-blocked state, import hash, source reference, replay result IDs, progress summary, ledger summary, side-sensitivity warning, acknowledgement, and side-selection rationale.
The event hash is returned in the run response and visible in the dashboard campaign panel.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched enum, paper engine, route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Prediction Campaign Audit Surface

Created:

```text
GET /prediction-market/paper/demo-campaigns
PredictionPaperDemoCampaignAuditResponse and record schema
Dashboard Campaign audit table
Regression coverage proving campaign audit summarizes PAPER_DEMO_CAMPAIGN evidence events
```

Implemented behavior:

```text
The campaign audit endpoint reads immutable PAPER_DEMO_CAMPAIGN events and summarizes status, strategy, source reference, import hash, side, warning, rationale, completed records, countable records, fee-net P/L, and live-review readiness.
The dashboard shows recent campaign audit rows separately from the settlement ledger.
This lets operators review accepted campaign decisions without digging through generic evidence events.
Live execution remains disabled.
```

Verified:

```text
Focused prediction-market API and dashboard tests passed.
Ruff passed on touched route, schema, and test files.
Dashboard JavaScript syntax passed.
Live execution remains disabled.
```

### Goal Continuation: Research Significance Gate

Implemented:

```text
StrategyResearchBacktestRequest now includes default statistical evidence thresholds.
Research-gate metrics now persist a one-sided OOS binomial survival test.
The p-value is Bonferroni-adjusted by the effective tested-variant count.
Gate results now block when the OOS significance sample is too small or the adjusted p-value is above threshold.
The Strategy tab surfaces statistical edge in the research gate panel, readiness queue, and gate-run history.
```

Current behavior:

```text
This does not prove a profitable strategy.
It makes weak positive OOS samples harder to promote to paper research eligibility.
Live execution remains disabled.
```

### Goal Continuation: MKT DB Data Readiness

Created:

```text
POST /prediction-market/contracts/mkt-db-readiness
PredictionContractSnapshotMktDbReadinessResponse
Dashboard MKT DB readiness control and readout
```

Implemented behavior:

```text
The readiness endpoint checks whether the configured My-Krypt-Trader SQLite file exists, can be read,
has a markets table, and contains importable resolved rows under the selected query settings.
Missing or unusable local donor data returns a structured status and next action instead of a generic
preflight failure.
The endpoint is non-mutating and keeps live_execution_enabled=false.
The Prediction Markets tab now exposes DB readiness, usable row count, rejected row count, and next action
before campaign preflight/replay.
```

Current behavior:

```text
The current worktree does not include My-Krypt-Trader/python/data/krypt-trader.db.
Aurex now reports that absence explicitly as MISSING_DB until real MKT market data is created or exported.
```

### Goal Continuation: MKT DB Campaign Readiness Checklist

Created:

```text
POST /prediction-market/paper/demo-mkt-db-campaign-readiness
PredictionPaperDemoMktDbCampaignReadinessResponse
Dashboard Campaign readiness control and readout
```

Implemented behavior:

```text
The readiness endpoint combines MKT DB data readiness, selected strategy research-gate status,
rollback-protected campaign projection, side-sensitivity acknowledgement/rationale readiness, and
live-disabled state into one non-mutating checklist.
It short-circuits when donor DB data is missing, then reports research-gate blockers before running
the heavier projection path.
When data and research evidence are present, it reuses the existing campaign preflight projection and
returns whether the campaign is ready for guarded replay.
Side-sensitive projections remain blocked until the operator acknowledges the warning and records a
pre-declared side-selection rationale.
```

Current behavior:

```text
This is a pre-replay control only. It does not import contracts, run replay, write campaign evidence,
or enable live execution.
```

### Goal Continuation: MKT DB Discovery

Created:

```text
POST /prediction-market/contracts/discover-mkt-dbs
PredictionContractSnapshotMktDbDiscoveryResponse and candidate schema
Dashboard MKT DB discovery control and readout
```

Implemented behavior:

```text
The discovery endpoint searches bounded local roots for SQLite-like donor database files while
skipping build/cache folders.
Each candidate is evaluated through the existing non-mutating MKT DB readiness check, so discovery
reports whether the file has a markets table and importable resolved rows without mutating the ledger.
The dashboard can fill the MKT DB path/source reference with the first ready discovered database.
Live execution remains disabled.
```

Current behavior:

```text
If no DB exists under the searched donor roots, Aurex reports NO_DBS_FOUND and asks the operator to
run or export My-Krypt-Trader market collection.
```

### Goal Continuation: MKT DB Candidate Inspection

Created:

```text
Dashboard Discovered DB candidates table
Dashboard candidate Use/Inspect action for discovered MKT SQLite files
Dashboard regression coverage for the candidate table and selection hook
```

Implemented behavior:

```text
The prediction-market dashboard now shows each discovered MKT SQLite candidate with readiness status,
usable rows, actionable YES/NO counts, rejected rows, modified time, and the next blocker/action.
Selecting a candidate only fills the MKT DB path/source reference and renders that candidate's
readiness report. It does not import rows, run campaign replay, write campaign evidence, or enable
live execution.
```

### Goal Continuation: MKT Campaign Manifest

Created:

```text
POST /prediction-market/paper/demo-mkt-db-campaign-manifest
PredictionPaperDemoMktDbCampaignManifestResponse
Dashboard Campaign manifest control and readout
Stable replay-plan hash for MKT DB paper/demo campaign review
```

Implemented behavior:

```text
The campaign manifest endpoint reuses the existing MKT DB data readiness, research-gate, campaign
preflight projection, side-sensitivity, and live-disabled checks to build a non-mutating replay plan.
The manifest includes the selected DB import, batch strategy/side/risk controls, projected replay,
opposite-side projection, blockers, side rationale state, and controls proving the manifest does
not mutate the ledger or enable live execution.
The manifest hash excludes generation time so repeated requests for the same replay plan produce
the same hash. The dashboard exposes manifest state, hash, and next action before campaign replay.
```

### Goal Continuation: MKT Donor Readiness

Created:

```text
POST /prediction-market/contracts/mkt-donor-readiness
PredictionContractSnapshotMktDonorReadinessResponse
Dashboard Donor readiness control and readout
Safer local MKT DB discovery scan that prunes .tmp, virtualenvs, node_modules, and cache folders
```

Implemented behavior:

```text
The donor-readiness endpoint checks whether the local My-Krypt-Trader checkout, python directory,
data directory, db.py schema module, collector files, expected krypt-trader.db paths, and discovered
SQLite donor DB candidates are present before any import, manifest, or replay step.
It reuses the non-mutating DB discovery/readiness gate and reports explicit blockers such as
mkt_data_dir_missing, mkt_sqlite_db_missing, or mkt_sqlite_db_not_ready.
The dashboard now exposes donor status, ready/found DB counts, blockers, and next action. Command
hints are returned as operator guidance only; Aurex does not run MKT, install dependencies, import
rows, replay campaigns, or enable live execution from donor readiness.
```

### Goal Continuation: MKT DB Inventory

Created:

```text
POST /prediction-market/contracts/mkt-db-inventory
PredictionContractSnapshotMktDbInventoryResponse and table schema
Dashboard DB inventory control, summary, and table
```

Implemented behavior:

```text
The MKT DB inventory endpoint inspects a selected SQLite donor DB without mutation and reports
whether the database exists, which expected MKT tables exist, table row counts, resolved-row counts,
latest timestamps, replay-candidate count, research-observation candidate count, execution-history
presence, missing tables, blockers, and next action.
Inventory reuses the existing MKT markets readiness gate for replay eligibility but keeps research
tables visible separately so alerts, whale_trades, and crypto15m_signals can be evaluated as
research candidates even when replay-ready markets are still missing.
The dashboard exposes inventory state, total rows/tables, blockers, next action, and a per-table
inventory table. It does not import rows, replay campaigns, write evidence, or enable live execution.
```

### Goal Continuation: MKT Donor Runbook

Created:

```text
POST /prediction-market/contracts/mkt-donor-runbook
PredictionContractSnapshotMktDonorRunbookResponse and step schema
Dashboard Donor runbook control and step table
```

Implemented behavior:

```text
The donor-runbook endpoint combines MKT donor readiness and DB inventory into a non-mutating
operator checklist. It reports checkout/code readiness, Python dependency setup status, required
manual demo/dry-run safety verification, collection commands, inventory review, and the final
Aurex gate path for research import or replay readiness.
Commands are guidance only. Aurex does not run npm, create the MKT virtualenv, open MKT, save
credentials, import donor rows, replay campaigns, write evidence, or enable live execution from
this endpoint.
```

### Goal Continuation: MKT Runtime Safety Preflight

Created:

```text
POST /prediction-market/contracts/mkt-runtime-safety
PredictionContractSnapshotMktRuntimeSafetyResponse, check schema, and credential-presence schema
Dashboard Runtime safety control, summary, and check table
Donor-runbook step 3 now consumes the runtime safety report
```

Implemented behavior:

```text
The runtime-safety endpoint inspects the local My-Krypt-Trader checkout without mutation. It checks
the Python DEFAULT_CONFIG, Electron DEFAULT_CONFIG, optional runtime settings.json, and credential
file presence for demo/production environments without reading credential contents.
Unsafe known runtime settings such as kalshiEnv=production, enableTrading=true, crypto15mLive=true,
or gamblingMode=true become hard blockers. Missing runtime settings become SAFETY_DEFAULTS_ONLY
with an explicit manual-confirmation blocker instead of a fake pass.
The donor runbook now shows whether MKT runtime safety is confirmed, requires manual confirmation,
or is blocked before donor collection. Aurex still does not start MKT, run npm, save credentials,
read secrets, import rows, replay campaigns, or enable live execution from this endpoint.
```

### Goal Continuation: MKT Runtime Path Discovery

Created:

```text
Runtime safety settings/userdata candidate discovery
PredictionContractSnapshotMktRuntimePathCandidateResponse
Dashboard selected settings/userdata path readouts
Auto-fill of discovered MKT runtime paths after safety/runbook checks
```

Implemented behavior:

```text
Runtime safety now looks for operator-supplied paths first, then safe local candidates such as
KRYPT_TRADER_USERDATA/settings.json and Windows Electron userData locations derived from MKT's
productName/package name. It selects only existing settings files, reports settings/userdata
candidate paths with selected/existence flags, and uses a discovered userData directory for
credential-file presence checks without reading credential contents.
The dashboard displays the selected settings and userData paths and fills those inputs when Aurex
discovers them. Missing runtime settings remain a manual-confirmation blocker; discovery does not
start MKT or lower any safety gate.
```

### Goal Continuation: MKT Demo Donor Bootstrap

Created:

```text
POST /prediction-market/contracts/mkt-donor-bootstrap
PredictionContractSnapshotMktDonorBootstrapResponse
Dashboard Demo bootstrap control, summary, and command table
Workspace-local MKT .aurex-demo-userdata scaffold
```

Implemented behavior:

```text
The donor-bootstrap endpoint prepares a local MKT demo runtime folder under
My-Krypt-Trader/.aurex-demo-userdata by default. It creates logs, data, and credentials
directories, writes a demo/dry-run settings.json only when one is missing or explicit overwrite is
requested, then reruns the runtime-safety gate against that exact settings/userData path.
Existing unsafe settings are not overwritten by default; the endpoint reports hard blockers
instead. The response includes the PowerShell command to start MKT with KRYPT_TRADER_USERDATA
pointing at the Aurex-prepared folder and the expected krypt-trader.db path for later DB discovery
and inventory.
This endpoint still does not install dependencies, start MKT, save credentials, read secrets,
collect markets, import rows, replay campaigns, or enable live execution.
```

### Goal Continuation: MKT Donor Collection Status

Created:

```text
POST /prediction-market/contracts/mkt-donor-collection-status
PredictionContractSnapshotMktDonorCollectionStatusResponse
Dashboard Collection status control, summary, and log metadata table
Runtime discovery of Aurex-created .aurex-demo-userdata
```

Implemented behavior:

```text
The donor-collection-status endpoint is a read-only post-bootstrap monitor. It rediscovers the
Aurex demo userData folder, reruns runtime safety, infers the expected
.aurex-demo-userdata/data/krypt-trader.db path, reuses MKT DB inventory/readiness, and reports
whether collection is waiting for a DB, has an empty DB, has research-only rows, or is replay-ready.
It also reports recent log file metadata from the selected userData logs folder without reading log
contents.
The dashboard exposes collection state, selected DB path/readiness, next action, and log file
metadata. The demo bootstrap action now also fills the MKT DB path with the expected scoped donor
DB so standalone DB inventory/preflight controls inspect the same file.
No live execution is enabled and the endpoint does not start MKT, collect markets, import rows,
write evidence, or replay campaigns.
```

### Goal Continuation: MKT Runbook Collection-State Integration

Changed:

```text
PredictionContractSnapshotMktDonorRunbookResponse now includes collection_status
Donor runbook DB path now follows the collection-status inferred donor DB
Dashboard runbook action hydrates collection status and the selected MKT DB path
Runbook collection step uses the scoped KRYPT_TRADER_USERDATA command when available
```

Implemented behavior:

```text
The donor runbook no longer drifts back to My-Krypt-Trader/python/data/krypt-trader.db after
bootstrap. It now calls the read-only donor collection-status gate, uses the same inferred
.aurex-demo-userdata/data/krypt-trader.db path, carries collection_status in the response, refreshes
the dashboard collection monitor from the runbook response, and shows the scoped
KRYPT_TRADER_USERDATA launch command in step 4.
This keeps bootstrap, runtime safety, collection status, DB inventory, and runbook instructions on
one operator path without starting MKT, importing rows, replaying campaigns, writing evidence, or
enabling live execution.
```

### Goal Continuation: MKT Donor Launch Preflight

Created:

```text
POST /prediction-market/contracts/mkt-donor-launch-preflight
PredictionContractSnapshotMktDonorLaunchPreflightResponse and check schema
Dashboard Launch preflight control, summary, and check table
```

Implemented behavior:

```text
The launch-preflight endpoint validates the final manual MKT launch path without running npm or
starting MKT. It combines runtime safety and collection status with package.json script checks,
node_modules presence, MKT Python venv checks, scoped userData selection, and the generated
KRYPT_TRADER_USERDATA launch command. The venv check reads pyvenv.cfg and reports stale or broken
base Python paths as setup warnings instead of treating a leftover .venv folder as launch-ready.
It reports LAUNCH_READY when safety is confirmed and local runtime prerequisites are present,
LAUNCH_NEEDS_SETUP when setup warnings remain, and LAUNCH_BLOCKED when hard safety/package/path
checks fail. The response includes setup command hints for npm install / py:setup and the exact
scoped launch command for operator use.
No credentials are read, no MKT process starts, no DB rows are imported, no evidence is written,
and live execution remains disabled.
```

### Goal Continuation: MKT Strict Backend Setup Repair

Changed:

```text
My-Krypt-Trader/scripts/setup-python.mjs now supports --strict and --force
My-Krypt-Trader/scripts/python-utils.mjs accepts KRYPT_TRADER_PYTHON/PYTHON interpreter override
MKT setup recreates an unusable python/.venv instead of trusting a stale folder
Aurex donor setup/runbook hints now use a strict repair command with the active Aurex Python
Aurex emits npm.cmd in Windows PowerShell command hints to avoid npm.ps1 execution-policy blocks
```

Implemented behavior:

```text
The MKT donor backend can now be repaired from the Aurex operator path even when no py/python/python3
launcher is on PATH. Aurex points setup at its known working Python interpreter, forces recreation
of the MKT venv, and requires setup to fail loudly if dependency installation fails. This keeps MKT
as a donor process while Aurex remains the truth gate.

Real local smoke moved the donor launch preflight from LAUNCH_NEEDS_SETUP to LAUNCH_READY after
recreating My-Krypt-Trader/python/.venv. Runtime safety remains SAFETY_CONFIRMED, node_modules is
present, and the launch command is scoped to .aurex-demo-userdata with npm.cmd on Windows. The donor DB is still
COLLECTION_DB_EMPTY / INVENTORY_EMPTY_SCHEMA, so this is only ready for demo data collection, not
backtesting, signal trust, paper replay, live trading, or profit claims.
```

### Goal Continuation: MKT Donor Collection Quality Gate

Changed:

```text
PredictionContractSnapshotMktDonorCollectionStatusResponse now includes collection_quality
Collection quality reports replay candidates, research observations, context rows, total rows, and
latest donor timestamp
Collection quality includes explicit targets, remaining row counts, and backtest-depth progress
Dashboard summary now shows Collection quality and Quality next
```

Implemented behavior:

```text
The collection monitor now separates technical readiness from evidence maturity. A single resolved
row can be a replay sample, but it is not enough to call the donor dataset backtest-quality. The
quality gate reports QUALITY_EMPTY, QUALITY_CONTEXT_ONLY, QUALITY_RESEARCH_SAMPLE,
QUALITY_REPLAY_SAMPLE, QUALITY_REPLAY_AND_RESEARCH_SAMPLE, or QUALITY_BACKTEST_CANDIDATE.

Backtest-candidate quality currently requires at least 100 resolved replay candidates and 100
resolved research observations before any serious strategy claim can be entertained, and even then
Aurex still requires the normal research/backtest/paper gates. Live execution remains disabled.
The response reports per-target progress for market context rows, resolved replay candidates, and
resolved research observations, plus a capped backtest-depth progress percentage based only on
replay/research depth.

Real local smoke currently reports COLLECTION_DB_EMPTY / INVENTORY_EMPTY_SCHEMA /
QUALITY_EMPTY with 0% depth, 0 replay candidates, 0 research observations, 0 context rows, and
remaining targets of 1 context row, 100 replay candidates, and 100 research observations.
```

### Goal Continuation: MKT Donor Collection Freshness Telemetry

Changed:

```text
PredictionContractSnapshotMktDonorCollectionStatusResponse now reports DB file size, DB modified
time, latest log modified time, and collection_freshness_status
Dashboard summary now shows Collection freshness beside DB path and collection quality
```

Implemented behavior:

```text
The donor collection monitor now distinguishes a missing DB, a recently written DB, recent log
activity, stale rows, and no recent writes. No-recent-write and stale-row states now become
first-class collection blockers/statuses instead of being described as ordinary empty collection.
This does not import rows, start MKT, inspect secrets, or enable live execution. It only helps the
operator confirm whether scoped demo collection appears active after launching MKT.

Real local smoke currently reports LAUNCH_READY plus COLLECTION_INACTIVE /
FRESHNESS_NO_RECENT_WRITES with a 208896-byte empty schema DB, no latest log timestamp, and
QUALITY_EMPTY. That means the donor runtime setup is ready, but MKT is not currently collecting
into the scoped DB.
```

### Goal Continuation: MKT Scoped Electron userData Enforcement

Changed:

```text
My-Krypt-Trader/electron/main.ts now maps KRYPT_TRADER_USERDATA into Electron app userData
Launch preflight now verifies MKT Electron main supports that scoped userData override
Launch preflight blocks donor launch if Electron would ignore the scoped demo folder
```

Implemented behavior:

```text
MKT's Python backend already uses app.getPath('userData') and passes that path to the Python
service as KRYPT_TRADER_USERDATA. Aurex now also requires Electron main startup to map the
operator-provided KRYPT_TRADER_USERDATA environment variable into app.setPath('userData') before
settings/backend startup. This keeps settings, logs, credentials, and krypt-trader.db inside the
Aurex demo userData folder when the operator runs the scoped launch command.

Real local smoke reports LAUNCH_READY and electron_userdata_env_override_available=PASS. Collection
still reports COLLECTION_INACTIVE / FRESHNESS_NO_RECENT_WRITES until MKT is actually launched.
```

### Goal Continuation: MKT Donor Launch Health Gate

Changed:

```text
PredictionContractSnapshotMktDonorCollectionStatusResponse now includes launch_health
Dashboard summary now shows Launch health and Health next beside collection quality/freshness
```

Implemented behavior:

```text
Launch health separates MKT operational state from strategy evidence. It reports whether runtime
safety is blocked, MKT appears to be starting, the donor feed is inactive/stale, rows are collecting,
a sparse replay/research sample is available, or the donor dataset has enough resolved depth to be a
backtest candidate. The health checks require runtime safety, recent DB/log activity, donor rows,
an evidence sample, and the 100 replay / 100 research resolved-observation depth target before any
backtest-candidate label is emitted.

This does not start MKT, import rows, read secrets, enable production settings, enable live trading,
or claim profitability. It only gives the operator a truthful next action before Aurex replay,
research, paper-demo, or live-review gates.
```

### Goal Continuation: MKT Research Import Quality Gate

Changed:

```text
MktResearchImportResponse now reports resolved/unresolved observation depth, import quality status,
per-source quality, blockers, next_action, and live_execution_enabled=false
Strategy dashboard now shows MKT import quality, resolved depth, and per-source import targets
```

Implemented behavior:

```text
The MKT research importer still imports rows only as Aurex research observations, but it now labels
the imported dataset as empty, unresolved-only, sparse resolved sample, or backtest candidate. Each
source reports its MKT table, table presence, processed/resolved/unresolved observation counts, a
100-resolved-observation target, remaining resolved observations, and a next action.

Sparse imports remain useful for inspection, but the response explicitly blocks evidence claims with
mkt_research_backtest_depth_missing until at least one source reaches the resolved-depth target.
This does not enable live execution, does not mark imported candidates as trusted strategies, and
does not bypass the existing Aurex research backtest, paper-demo, or live-review gates.
```

### Goal Continuation: MKT Research Import Preflight

Changed:

```text
POST /strategies/research-candidates/preflight-mkt
MktResearchImportPreflightResponse with preflight_only=true and mutates_research_ledger=false
Strategy dashboard MKT preflight button and ledger-write indicator
```

Implemented behavior:

```text
The MKT research SQLite scanner is now split from the write path. Preflight parses the selected MKT
database with the same source filters and quality rules as import, then returns potential candidate
count, processed/resolved/unresolved observation counts, source quality, blockers, and next action
without creating StrategyResearchCandidate rows, StrategyResearchObservation rows, StrategyConfig
records, evidence hashes, or paper/live eligibility.

Import still uses the same scan result before writing, so operator preview and committed import stay
aligned. Live execution remains disabled in both responses.
```

### Goal Continuation: MKT Research Intake Readiness

Changed:

```text
POST /strategies/research-candidates/mkt-intake-readiness
MktResearchIntakeReadinessResponse with safe_to_import_research and ready_for_research_backtest
Strategy dashboard MKT readiness button plus Intake gate / Intake next fields
```

Implemented behavior:

```text
The readiness gate wraps the same non-mutating MKT research preflight and classifies the donor DB as
missing, waiting for rows, waiting for resolved outcomes, ready for research import, or ready for
backtest-depth import. Sparse resolved samples can be imported for research inspection, but they are
not treated as backtest-depth evidence. Backtest readiness requires the import-quality preflight to
report IMPORT_BACKTEST_CANDIDATE.

Missing DB readiness returns a 200 response with explicit blockers instead of forcing the operator
through a failing import/preflight path. The endpoint writes no research candidates, observations,
strategy configs, or evidence, and live execution remains disabled.
```

### Goal Continuation: MKT Research-Only Import Acknowledgement

Changed:

```text
MktResearchImportRequest now includes acknowledge_research_only_import
MKT research import blocks sparse/unresolved imports unless the operator acknowledges research-only use
Strategy dashboard now includes a Research-only MKT import checkbox
```

Implemented behavior:

```text
The mutating MKT research import endpoint now refuses to write parsed rows when the import quality is
not IMPORT_BACKTEST_CANDIDATE unless acknowledge_research_only_import=true is supplied. This prevents
sparse resolved samples or unresolved rows from quietly entering the research ledger as if they were
backtest-depth evidence.

Preflight and readiness remain non-mutating and do not require the acknowledgement. Backtest-candidate
imports still do not imply profitability or paper/live eligibility; they only mean Aurex has enough
resolved donor observations to run the existing research backtest gates.

Imported MKT research candidates now persist import_quality_status, source_quality_status, source
resolved-depth counts, import blockers, trusted_profitable_strategy=false, and
research_only_import_acknowledged in normalized_payload. The Strategy dashboard surfaces that quality
state in the research-candidate table so the warning is still visible after the import response is
gone.
```

### Goal Continuation: MKT Research Intake DB Freshness

Changed:

```text
MktResearchIntakeReadinessResponse now reports db_file_size_bytes, db_modified_at,
db_age_seconds, and db_freshness_status
Strategy dashboard now shows DB freshness beside the MKT research intake gate
```

Implemented behavior:

```text
The MKT research intake readiness gate now distinguishes a missing, recent, stale, or unknown donor
SQLite DB using the selected scoped DB file timestamp. Empty recent DBs tell the operator to keep
MKT running; empty stale DBs point to launching or restarting MKT in scoped demo mode. This is
read-only telemetry and does not start MKT, import research rows, write evidence, or enable live
execution.
```

### Goal Continuation: MKT Research Intake Launch Command Hint

Changed:

```text
MktResearchIntakeReadinessResponse now includes command_hints
Strategy dashboard now shows a Start command for scoped MKT research collection
```

Implemented behavior:

```text
The MKT research intake readiness response now returns a scoped KRYPT_TRADER_USERDATA launch
command derived from the selected donor DB path. The hint points MKT at the Aurex demo userData
folder and keeps the expected donor DB path visible. It does not execute the command, start MKT,
read credentials, import rows, write evidence, or enable live execution.
```

### Goal Continuation: MKT Research Collection Health

Changed:

```text
MktResearchIntakeReadinessResponse now includes collection_health
Strategy dashboard now shows Collection health in the MKT import quality panel
```

Implemented behavior:

```text
The Strategy Lab MKT research readiness gate now classifies donor collection health as waiting for
DB, inactive, collecting, unresolved-only, sparse sample-ready, or backtest-depth-ready. The status
is derived from read-only DB freshness and preflight row depth, exposes remaining backtest-depth
blockers, and keeps strategy reliability behind the existing Aurex research evidence gates. It does
not execute MKT, import observations, write evidence, or enable live execution.
```

### Goal Continuation: MKT Research Log Activity

Changed:

```text
MktResearchIntakeReadinessResponse now reports logs_dir, logs_dir_exists,
latest_log_modified_at, log_files, and collection_activity_status
Strategy dashboard now shows Log activity beside DB freshness and Collection health
```

Implemented behavior:

```text
The MKT research intake readiness gate now inspects bounded log-file metadata from the scoped
userData logs folder derived from the selected donor DB path. Fresh log activity can classify a
collector as starting or recently active even before research rows appear, while stale DB/log
metadata remains inactive. Aurex records only file names, paths, sizes, and modified timestamps; it
does not read log contents, start MKT, import observations, write evidence, or enable live
execution.
```

### Goal Continuation: MKT Research Intake Runbook

Changed:

```text
POST /strategies/research-candidates/mkt-intake-runbook
MktResearchIntakeRunbookResponse and ordered runbook steps
Strategy dashboard now includes an MKT runbook button, status, next action, and step table
```

Implemented behavior:

```text
The MKT research intake runbook converts the existing non-mutating readiness/preflight context into
an ordered operator checklist: use scoped demo runtime, confirm collector activity, wait for
research rows, wait for resolved outcomes, run non-mutating preflight, optionally import only as
disabled research candidates, run Aurex research backtest gates only after resolved depth, and keep
live execution disabled. Steps explicitly mark whether the target action writes the research
ledger. Building the runbook does not start MKT, import observations, write evidence, promote a
candidate, or enable live execution.
```

### Goal Continuation: MKT Research Runbook Current Step

Changed:

```text
MktResearchIntakeRunbookResponse now reports current_step, completed_step_count,
total_step_count, and progress_pct
Strategy dashboard now shows Current step and Runbook progress beside the runbook status
```

Implemented behavior:

```text
The MKT research runbook now identifies the next actionable step instead of requiring the operator
to infer it from the full checklist. Ready ledger-writing steps are surfaced before later blockers;
otherwise the first blocked or running step is selected. This keeps the path explicit: start or
restart collection, wait for rows, wait for resolved outcomes, import only as research, then run
the Aurex research gate. The summary is read-only and does not mutate the research ledger or enable
live execution.
```

### Goal Continuation: MKT Research Runbook Current Command

Changed:

```text
MktResearchIntakeRunbookResponse now reports current_command
Strategy dashboard now shows Current command beside Current step and Runbook progress
```

Implemented behavior:

```text
The MKT research runbook now lifts the current step's manual command to a top-level response field
so the dashboard can show the exact scoped MKT command for the active blocker. This is display-only:
Aurex does not execute the command, start MKT, import observations, write evidence, or enable live
execution.
```

### Goal Continuation: Prediction Paper Demo Readiness Current Gate

Changed:

```text
PredictionPaperDemoReadinessResponse now reports current_check, completed_check_count,
total_check_count, and progress_pct
Prediction Markets dashboard now shows Current demo gate and Readiness progress
```

Implemented behavior:

```text
Prediction paper/demo readiness now surfaces the first failing paper-demo lifecycle gate and a
completed/total progress summary. The readiness path still only reads existing research-gate,
contract, intent, fill, settlement, reconciliation, and live-disabled evidence; it does not create
orders, settle positions, reconcile ledgers, or enable live execution.
```

### Goal Continuation: Prediction Paper Demo Progress Current Gate

Changed:

```text
PredictionPaperDemoProgressResponse now reports current_check, completed_check_count,
total_check_count, and progress_pct
Prediction Markets dashboard now shows Current evidence gate and Evidence progress
```

Implemented behavior:

```text
Prediction paper/demo progress now identifies the first failing evidence-quality check across the
100-record/30-day/active-day/unique-contract/concentration/provenance/ledger/P&L/reconciliation
target set and reports completed/total progress. This makes evidence collection operationally
clear while remaining read-only: it does not create paper records, import snapshots, reconcile
ledgers, or enable live execution.
```

### Goal Continuation: Prediction Paper Demo Runbook

Changed:

```text
GET /prediction-market/paper/demo-runbook
PredictionPaperDemoRunbookResponse and PredictionPaperDemoRunbookStepResponse
Prediction Markets dashboard now shows Demo runbook, Current runbook step, Runbook progress, and
an ordered Paper/demo runbook table
```

Implemented behavior:

```text
Prediction paper/demo runbook now combines paper/demo readiness and evidence-progress status into
one ordered operator checklist: keep live disabled, pass an MKT research gate, record/import a
contract snapshot, create an approved paper intent, record a fill, settle the paper position, match
reconciliation, collect diversified evidence, and only then run an independent live-readiness
review. The endpoint is read-only and does not create intents, submit orders, settle positions,
reconcile ledgers, import rows, or enable live execution.
```

### Goal Continuation: Prediction Paper Demo Upstream Research Context

Changed:

```text
PredictionPaperDemoRunbookResponse now includes upstream_research_runbook when no MKT research
candidate is paper-eligible
Prediction Markets dashboard now shows Research blocker in the paper/demo runbook summary
```

Implemented behavior:

```text
The paper/demo runbook now summarizes the upstream MKT research intake runbook when paper/demo is
blocked by missing accepted MKT research evidence. This connects the Stage 7 paper/demo blocker back
to the actual upstream issue, such as inactive donor collection or missing resolved research rows,
without importing observations, creating paper records, reconciling ledgers, or enabling live
execution.
```

### Goal Continuation: Command Center Evidence Path

Changed:

```text
Command Center now includes an Evidence path panel
Dashboard app renders command-evidence path state, current blocker, upstream blocker, path
progress, live boundary, donor DB, unblock command, and next action from the paper/demo runbook
Command Center exposes a copy action for the upstream MKT command when the runbook provides one
```

Implemented behavior:

```text
The main Command Center now surfaces the paper/demo runbook's current blocker chain without making
the operator open the Prediction Markets tab. It shows the active paper/demo step, any upstream MKT
research blocker, path progress, donor DB, manual unblock command, and the live-disabled boundary.
The copy action helps the operator launch scoped MKT demo collection from an external terminal, but
Aurex still does not start MKT, import data, create paper records, or enable live execution.
```

### Goal Continuation: MKT Donor Credential Boundary

Changed:

```text
Live deployment gates now include mkt_donor_credential_boundary
MKT-derived strategies fail the gate when production MKT credential material is present
Strategy evidence review includes the credential boundary gate for mkt_* strategies
Deployment dashboard shows MKT credential boundary status
```

Implemented behavior:

```text
The new gate adopts MKT's credential-awareness lesson but keeps Aurex stricter: it checks only
credential file presence in scoped donor credential directories and never reads or stores secret
contents. Non-MKT deployment strategies mark the gate as not required. mkt_* strategies pass only
when production credential material is absent; demo credential presence is reported separately for
operator awareness. A production apikey or RSA key file in an inspected donor profile fails live
readiness and blocks a clean strategy evidence review.
```

### Goal Continuation: Command Center MKT Collection Telemetry

Changed:

```text
MKT research intake runbook response now carries DB freshness, DB modified time, log modified time,
collection health, processed/resolved/unresolved observation counts, and backtest-depth progress
MKT research intake runbook response now carries a threshold ladder for parseable rows, resolved
rows, and backtest-depth resolved rows
Prediction paper/demo upstream research summary now includes that telemetry
Command Center Evidence path renders DB freshness, MKT collection state, research rows, and resolved
depth beside the copyable scoped MKT command
Command Center Evidence path renders the next unfinished MKT research threshold
```

Implemented behavior:

```text
The operator can now launch MKT externally, refresh Aurex, and see whether the upstream donor
collector is inactive, starting, collecting, sample-ready, or backtest-depth ready without opening
the Strategy tab. It also shows whether the next unlock is parseable rows, resolved rows, or the
100-row resolved-depth threshold. This remains read-only telemetry: Aurex does not launch MKT,
import research rows, run a backtest gate, create paper/demo records, or enable live execution.
```

### Goal Continuation: Strategy Review Gate-State Freshness

Changed:

```text
Strategy evidence review freshness now compares reviewed gate statuses with current gate statuses
strategy_evidence_review_clear now exposes reviewed_gate_statuses and current_gate_statuses
Regression coverage blocks stale CANDIDATE reviews after a reviewed gate flips status
```

Implemented behavior:

```text
A CANDIDATE strategy evidence review now remains clean only while the reviewed readiness gates
still have the same status. If a gate that was approved during review later changes to FAIL,
BLOCKED, NOT_RUN, or was missing from the stored review snapshot, the live-deployment review gate
becomes BLOCKED and records a <gate>_status_changed_since_review or <gate>_missing_from_review
freshness reason. This protects MKT credential-boundary checks, kill-switch state, evidence gates,
and deployment-scope controls from becoming stale after review.
```

### Goal Continuation: TradingView No-Trade Backtest Diagnostics

Changed:

```text
Backtest CSV preflight now returns structured REJECTED diagnostics for header-only exports
Backtest CSV preflight now diagnoses TradingView entry rows without completed exits
Dashboard Backtests fix summary renders the diagnostic status and next action
Regression coverage confirms imports remain blocked for no-completed-trade exports
```

Implemented behavior:

```text
When TradingView Strategy Tester has no completed trade data, Aurex no longer leaves the operator
with only a generic preflight error. Header-only exports now return NO_COMPLETED_TRADE_ROWS, and
entry-only exports return ENTRY_ROWS_WITHOUT_COMPLETED_EXITS. Both are non-mutating preflight
states: they do not create a backtest report, do not unlock paper execution, and do not weaken
acceptance gates. The dashboard surfaces the diagnostic beside the existing backtest fix queue so
the next move is to confirm Pine closed trades, extend the date/chart window, or export completed
List of Trades evidence.
```

### Goal Continuation: trend_pullback_v1 Pine Diagnostics

Changed:

```text
trend_pullback_v1 bumped to strategy version 1.2.0
Optional on-chart Aurex diagnostics table added to the Pine strategy
Backtest dashboard default strategy version updated to 1.2.0
Pine docs and TradingView import workflow now describe no-trade diagnostics before CSV export
Static Pine contract tests now verify diagnostics exist without loosening setup gates
```

Implemented behavior:

```text
The TradingView chart now shows an operator-facing diagnostics table for trend_pullback_v1. It
counts bars checked inside the selected backtest window and shows long/short pass counts for flat
position, trend, pullback, RSI reset, confirmation, risk geometry, position quantity, setup count,
and the latest blocker. The table is diagnostic only: it does not change entries, exits, alerts,
position sizing, commission, slippage, date controls, or Aurex evidence gates. This gives the
operator a direct way to diagnose Strategy Tester no-trade runs before exporting CSV.
```

### Goal Continuation: Known Pine Parameter Evidence Gate

Changed:

```text
Backtest acceptance now checks complete known-strategy parameter snapshots
trend_pullback_v1 required parameter evidence is recorded in metrics snapshots
Paper and live accepted-backtest audits block missing known Pine parameters
Backtest dashboard parameter default now includes the full trend_pullback_v1 v1.2.0 input snapshot
Regression coverage confirms incomplete parameters cannot become accepted evidence
```

Implemented behavior:

```text
Aurex now treats completed-trade rows and strategy settings as one evidence package. For
trend_pullback_v1, accepted backtests require the recorded Pine input snapshot: initial capital,
backtest window, higher timeframe, EMA lengths, RSI/ATR settings, reward:risk, swing and pullback
controls, stop mode, risk percent, position-value cap, and long/short toggles. A structurally valid
TradingView CSV can still be imported as a rejected evidence record, but missing known-strategy
parameters block acceptance, paper eligibility, and live accepted-backtest readiness. The live gate
now surfaces strategy_parameter_evidence with the missing parameter list.
```

### Goal Continuation: Dashboard Backtest Parameter Evidence

Changed:

```text
Backtests panel now shows a Parameter evidence summary row
Deployment accepted-backtest summary now points to missing parameters when they are the blocker
Dashboard contract tests cover the new summary row and render helper
```

Implemented behavior:

```text
The operator can now see whether a known Pine backtest has complete strategy-parameter provenance
without opening raw JSON. The Backtests panel renders COMPLETE with the required setting count, or
MISSING with the number of missing settings and the first missing key. If live readiness is blocked
because stored accepted-backtest parameters were removed or incomplete, the Deployment backtest
summary points directly to the parameter evidence problem.
```

### Goal Continuation: Pine Signal Provenance Gate

Changed:

```text
TradingView webhook payload schema now accepts strategy_version and settings_fingerprint
trend_pullback_v1 alert payload now emits version and deterministic settings fingerprint
Risk engine now blocks known-Pine paper execution when signal provenance is missing or mismatched
Risk snapshots include signal_backtest_provenance_gate evidence
Signal API responses expose strategy_version and settings_fingerprint from stored payload JSON
Regression coverage confirms missing provenance stores the signal but creates no paper trade
```

Implemented behavior:

```text
Accepted backtest evidence is no longer enough by itself to approve any later alert with the same
strategy and symbol. For known Pine strategies, Aurex now requires incoming TradingView signals to
carry a strategy version and settings fingerprint matching the accepted backtest's recorded version
and parameter snapshot. Missing or mismatched provenance is risk-rejected before paper execution,
with an explicit signal_backtest_provenance_gate in the risk decision snapshot. This keeps alerts
from a changed Pine script or changed settings profile from silently reusing old evidence.
```

### Goal Continuation: Dashboard Signal Provenance Visibility

Changed:

```text
Signals table now includes a Provenance column
Dashboard renders MATCHED, BLOCKED, PAYLOAD, or untracked signal provenance summaries
Dashboard contract coverage checks the signal provenance helper and table header
```

Implemented behavior:

```text
Operators no longer need to inspect raw signal JSON or risk snapshots to understand whether an
incoming Pine alert matched the accepted backtest evidence. The Signals panel now shows the
strategy-version/settings-fingerprint state beside each signal, including the first blocker when
the signal_backtest_provenance_gate rejects paper execution.
```

### Goal Continuation: Signal Contract Preflight

Changed:

```text
Added read-only /signals/contract preflight endpoint
Signal contract reports accepted-backtest readiness, expected Pine version, expected settings fingerprint, and required webhook fields
Signals dashboard now shows the active contract, accepted backtest id, expected version, expected fingerprint preview, and next action
Regression coverage verifies blocked-without-backtest and ready-with-accepted-backtest states
```

Implemented behavior:

```text
Aurex now lets the operator check the TradingView alert contract before sending a live webhook into
paper execution. The preflight uses the same accepted-backtest eligibility audit as the risk engine,
so it reports the blocker that would stop paper trading, or the exact strategy_version and
settings_fingerprint the Pine alert must carry when the known strategy is ready. This makes the next
manual TradingView test less ambiguous: first import accepted backtest evidence, then verify the
Signals contract reads READY, then send alerts that match that contract.
```

### Goal Continuation: TradingView Payload Preflight

Changed:

```text
Added read-only POST /signals/preflight/tradingview
Preflight simulates duplicate checks, accepted-backtest gate, Pine provenance gate, and risk sizing without writing ledger rows
Signals dashboard now includes a pasted-alert JSON preflight control with pass/block status and estimated size
Regression coverage proves passing and blocked provenance preflights do not create accounts, risk profiles, signals, risk decisions, or paper trades
```

Implemented behavior:

```text
The operator can now paste the exact TradingView alert JSON into Aurex before sending it to the
webhook. Aurex normalizes the payload, checks the current signal contract, simulates the same risk
rule path used by paper execution, reports whether paper execution would happen, and returns the
first blocker plus next action. The response explicitly marks mutates_ledger=false, and tests
confirm the preflight does not create hidden execution state.
```

### Goal Continuation: Usable TradingView Contract Example

Changed:

```text
Signal contract example payload now uses positive long-side price geometry
Signal contract example payload now uses a fresh UTC timestamp instead of a stale fixed date
Regression coverage posts the contract's own example payload through no-write preflight and expects PASS
```

Implemented behavior:

```text
The Signals dashboard no longer hydrates the preflight textbox with an example that immediately
fails schema validation or signal-staleness checks. After accepted backtest evidence exists, the
contract example payload is a valid preflight starter: entry 100, stop 95, target 110, current UTC
timestamp, and the expected Pine provenance fields.
```

### Goal Continuation: TradingView Preflight Duplicate Evidence

Changed:

```text
TradingView payload preflight now returns idempotency_key, duplicate_status, duplicate_signal_id, and duplicate_cooldown_minutes
Signals dashboard now shows duplicate check and idempotency preview after alert preflight
Regression coverage verifies duplicate preflight reports the original signal id without creating new ledger rows
```

Implemented behavior:

```text
Aurex now makes webhook duplicate behavior visible before the real webhook is called. When a pasted
TradingView payload would collide with an existing signal or cooldown window, the no-write preflight
returns DUPLICATE_BLOCKED plus the original signal id and idempotency key evidence. This keeps manual
TradingView testing from being mistaken for strategy failure when the actual issue is duplicate
protection.
```

### Goal Continuation: TradingView Preflight/Webhook Parity

Changed:

```text
TradingView payload preflight now returns expected_webhook_status and expected_webhook_http_status
Signals dashboard now shows the expected webhook outcome beside preflight sizing and duplicate evidence
Regression coverage proves PASS, provenance BLOCKED, and DUPLICATE_BLOCKED preflight outcomes match the real webhook response
```

Implemented behavior:

```text
The no-write TradingView preflight is now a verified rehearsal for the real webhook path. If
preflight says a payload should paper execute, the real webhook is expected to return HTTP 202 and
PAPER_EXECUTED. If preflight blocks for Pine provenance, the real webhook is expected to return HTTP
202 and RISK_REJECTED with the same reason. If preflight blocks as a duplicate, the real webhook is
expected to return HTTP 409 and DUPLICATE_REJECTED.
```

### Goal Continuation: TradingView Paper-Test Runbook

Changed:

```text
Added read-only GET /signals/tradingview-runbook
Runbook combines live-disabled boundary, accepted-backtest contract, payload preflight, webhook rehearsal, and paper evidence collection steps
Signals dashboard now shows runbook status, current step, progress, and an ordered step table
Regression coverage verifies blocked-before-backtest and ready-to-preflight states
```

Implemented behavior:

```text
Aurex now gives the operator an ordered TradingView paper-test checklist instead of relying on
memory. The runbook stays conservative: accepted backtest plus live-disabled settings can make the
system READY_TO_PREFLIGHT, but ready_to_send_webhook remains false until the no-write payload
preflight is run and reviewed. This keeps Stage 7 testing explicit and keeps live execution out of
scope.
```

### Goal Continuation: TradingView Paper-Path Verification

Changed:

```text
Added read-only GET /signals/tradingview-verification
Verification inspects latest TradingView signal, risk decision, Pine provenance gate, paper order, and paper trade
Signals dashboard now shows paper-path status, latest signal/trade ids, and verification checks
Regression coverage verifies no-signal, paper-executed, and risk-rejected states without mutating ledger rows
```

Implemented behavior:

```text
After sending a TradingView alert, Aurex can now verify whether the paper path actually completed.
The report confirms the latest signal was received, risk approved, Pine provenance matched, a paper
order was created, and a paper trade opened. If the latest signal was rejected, the report points to
the first blocked check instead of forcing the operator to inspect raw signals and trades manually.
```

## Current Test Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check apps/frontend/app.js
Set-Location .\My-Krypt-Trader; npm run py:test -- -q --basetemp ..\..\.tmp\mkt-pytest-<stamp> -p no:cacheprovider
```

Current result:

```text
200 tests passed.
Ruff passed.
Frontend JavaScript syntax check passed.
My-Krypt-Trader Python backend tests passed: 160 tests with a workspace-local basetemp.
My-Krypt-Trader TypeScript typecheck passed after the scoped userData patch.
Focused and full regression tests confirmed TradingView paper-path verification reports no-signal,
paper-executed, and risk-rejected states without mutating ledger rows.
Focused and full regression tests confirmed the TradingView paper-test runbook reports blocked
contract state and ready-to-preflight state without enabling live webhook execution.
Focused and full regression tests confirmed TradingView preflight expected webhook status matches
real webhook outcomes for paper execution, Pine provenance rejection, and duplicate rejection.
Focused and full regression tests confirmed TradingView payload preflight exposes duplicate and
idempotency evidence without mutating account, risk, signal, decision, or trade rows.
Focused and full regression tests confirmed TradingView payload preflight passes or blocks on
Pine provenance without mutating account, risk, signal, decision, or trade rows.
Focused and full regression tests confirmed the generated TradingView contract example payload can
pass no-write payload preflight after accepted backtest evidence exists.
Focused and full regression tests confirmed the signal contract preflight reports blocked
no-backtest state and ready accepted-backtest Pine provenance before webhook execution.
Focused and full regression tests confirmed known Pine TradingView signals must carry the same
strategy version and settings fingerprint as the accepted backtest before paper execution.
Focused and full regression tests confirmed the dashboard Signals table exposes Pine signal
provenance status without breaking the single-view operator console.
Focused and full regression tests confirmed incomplete known Pine strategy parameters cannot become
accepted backtest evidence or pass live accepted-backtest readiness.
Focused and full regression tests confirmed trend_pullback_v1 exposes diagnostic setup blockers
without loosening Pine entry gates.
Focused and full regression tests confirmed CANDIDATE strategy evidence reviews become stale when a
reviewed readiness gate changes status after the review.
Focused and full regression tests confirmed TradingView no-completed-trade exports return
structured no-trade diagnostics while import remains blocked.
Focused and full regression tests confirmed MKT donor collection quality reports empty, sparse
sample, and backtest-depth blockers without mutating the ledger.
Focused and full regression tests confirmed MKT donor collection freshness reports missing DB,
recent DB writes, and dashboard freshness fields without mutating the ledger.
Runtime smoke passed for dashboard Market Preview/Preflight/Collection status, dashboard backtest CSV template/preflight/import controls, dashboard walk-forward backtest evidence visibility, prediction-market snapshot CSV template/preflight/import/cancel controls, prediction-market MKT DB preflight/import controls and routes, prediction-market MKT DB campaign preflight/run controls and routes, prediction-market demo-ledger, batch preflight, batch replay, and campaign-quality controls, deployment prediction-demo campaign status, resolved prediction-market outcome import, guided prediction demo rejection without accepted research evidence, prediction demo progress and quality checks, pre-paper accepted-backtest eligibility, approval-packet dashboard controls, explicit approval records, first-profit milestone control, activation-attempt audit summary, preflight analysis summary, backtest report CSV preflight/import, broker-statement CSV preflight/reconcile, /performance/equity-curve, /paper/evidence/preflight-csv, /paper/evidence/collection-status, and live deployment guard.
Runtime smoke also confirmed MKT DB campaign preflight OpenAPI schema exposes projected_replay and the dashboard renders projected fee-net P/L plus first-blocker fields.
Runtime smoke confirmed MKT DB campaign preflight OpenAPI schema exposes opposite_side_projection, side_sensitivity_warning, projection side, and the dashboard renders opposite-side P/L plus side-sensitivity fields.
Runtime smoke confirmed MKT DB campaign run OpenAPI schema exposes side-sensitivity acknowledgement/rationale fields and the dashboard sends those controls only for replay.
Runtime smoke confirmed MKT DB campaign run OpenAPI schema exposes campaign_evidence, PredictionMarketEvidenceKind includes PAPER_DEMO_CAMPAIGN, and the dashboard renders the campaign evidence hash field.
Runtime smoke confirmed the campaign audit endpoint/schema and dashboard Campaign audit table render.
Focused and full regression tests confirmed the research significance gate persists adjusted OOS p-value evidence and blocks statistically weak positive samples.
Focused and full regression tests confirmed MKT DB readiness reports missing donor data and ready fixture rows without mutating the ledger.
Focused and full regression tests confirmed MKT DB campaign readiness combines data readiness, strategy-gate status, projection readiness, side-rationale acknowledgement, and live-disabled state without mutating the ledger.
Focused and full regression tests confirmed MKT DB discovery finds ready local donor DB files, reports blocked SQLite files, and leaves the ledger unmutated.
Dashboard regression coverage now confirms discovered MKT DB candidates render as an inspectable table
and expose a non-mutating selection hook.
Focused and full regression tests confirmed MKT DB campaign manifests are non-mutating, expose
blocked/ready replay states, preserve live-disabled controls, and produce a stable hash for the
same replay plan.
Focused and full regression tests confirmed MKT runtime safety preflight blocks unsafe production
or live-trading settings, reports defaults-only/manual-confirmation state, avoids reading
credential contents, and feeds the donor runbook safety step.
Focused and full regression tests confirmed MKT runtime safety auto-discovers a safe
KRYPT_TRADER_USERDATA settings path, reports selected path candidates, and keeps live execution
disabled.
Focused and full regression tests confirmed MKT donor bootstrap creates a demo-safe local userData
folder, writes safe settings, returns the scoped MKT launch command, refuses unsafe existing
settings by default, and keeps live execution disabled.
Focused and full regression tests confirmed MKT donor collection status rediscovers the
Aurex-created demo userData folder, reports missing DB vs replay-ready DB states, includes log-file
metadata only, and keeps the ledger/live execution untouched.
Focused and full regression tests confirmed the donor runbook now carries collection status,
selects the Aurex demo-userData donor DB after bootstrap, and shows the scoped
KRYPT_TRADER_USERDATA collection command.
Focused and full regression tests confirmed launch preflight reports setup warnings when
node_modules or the MKT Python venv are missing or stale, becomes LAUNCH_READY when those
prerequisites exist with a reachable pyvenv.cfg base Python, keeps the launch command scoped to
KRYPT_TRADER_USERDATA, and does not mutate the ledger.
Runtime smoke confirmed the local My-Krypt-Trader venv was recreated with the Aurex Python
interpreter, httpx/cryptography dependencies import, and launch preflight is LAUNCH_READY for demo
collection while collection remains DB-empty.
Focused and full regression tests confirmed MKT donor readiness reports missing local donor data,
recognizes ready local donor DBs, exposes command hints without executing them, and leaves the
ledger unmutated.
Focused and full regression tests confirmed MKT DB inventory reports missing DBs, replay-ready
markets, research-observation rows, execution-history presence, missing tables, and leaves the
ledger unmutated.
Focused and full regression tests confirmed MKT donor runbooks report missing-data collection
steps, replay-ready donor paths, manual demo/dry-run safety gates, non-executed commands, and leave
the ledger unmutated.
Focused and full regression tests confirmed TradingView paper-path verification now proves the
signal audit timeline is complete, reports recorded and missing signal event statuses, blocks
missing audit events before a run can be trusted, and leaves the ledger unmutated.
Focused and full regression tests confirmed prediction-market paper-demo ledger records now prove
market snapshot, order intent, order submission, fill, settlement, and reconciliation evidence is
present before a settled paper/demo record can count toward progress.
Focused and full regression tests confirmed prediction-market paper-demo readiness and runbook
verification now require lifecycle-clean ledger evidence before marking a paper/demo lifecycle as
verified.
Focused and full regression tests confirmed prediction-market paper-demo progress metrics now use
only lifecycle-clean countable ledger records for closed-record, calendar, active-day,
concentration, P/L, expectancy, and provenance progress while separately surfacing blocked ledger
records.
Focused and full regression tests confirmed prediction-market paper-demo progress now exposes raw
settled record count separately from countable progress records, and the dashboard clean-ledger
summary shows clean versus raw records plus blocked count.
Focused and full regression tests confirmed MKT-derived research backtests now persist
regime/category diagnostics that identify unknown, thin, weak, and passing groups, expose next
actions, and surface a concise diagnostics label in the research readiness queue without loosening
paper-eligibility gates.
Focused and full regression tests confirmed MKT-derived research backtests now persist
variant/parameter-set diagnostics that identify too-many-tested-variant blockers, adjusted
profit-factor blockers, thin variants, weak variants, and concise readiness labels without
loosening paper-eligibility gates.
Focused and full regression tests confirmed live-deployment prediction-demo campaign quality now
surfaces raw versus lifecycle-clean ledger records, current failed progress checks, progress
percentage, P/L/provenance/concentration details, and blocks mkt_* live-readiness when a settled
paper/demo record is missing required lifecycle evidence.
Focused and full regression tests confirmed MKT DB campaign preflight projections now expose the
post-replay evidence gap toward the 100-clean-record/30-calendar-day/15-active-day/25-contract
target, including raw versus countable records, remaining records/days/contracts, and progress
percentage, with dashboard readouts that remain visible after replay.
Focused and full regression tests confirmed accepted MKT DB campaign replay now writes the
operator-reviewed preflight projection and final evidence-gap progress snapshot into the immutable
PAPER_DEMO_CAMPAIGN evidence event, so campaign audit can reconstruct remaining records,
days/contracts, side sensitivity, and live-disabled state after the replay.
Focused and full regression tests confirmed campaign-audit rows now expose typed evidence-gap
fields from immutable PAPER_DEMO_CAMPAIGN payloads and the dashboard renders clean/raw records,
remaining target count, progress percentage, and the current failed gate for each replay.
Focused and full regression tests confirmed MKT DB campaign replay now requires a reviewed
manifest hash matching the current replay plan before mutating the paper/demo ledger, and the
dashboard sends the current manifest hash after the operator builds the manifest.
Focused and full regression tests confirmed regular prediction paper/demo batch replay now requires
a reviewed batch preflight hash before mutating the ledger; preflight hashes cover the reviewed
contract rows, assumptions, and live-disabled state, while duplicate/no-new-contract previews block
replay instead of writing a no-op batch.
Focused and full regression tests confirmed reviewed regular prediction paper/demo batch replay now
records an immutable PAPER_DEMO_BATCH evidence event and exposes a batch-audit endpoint/dashboard
table with preflight hash, clean/raw records, remaining evidence gap, fee-net P/L, and live-disabled
state.
Focused and full regression tests confirmed MKT DB campaign manifest hashes now exclude volatile
regular-batch fields such as idempotency_prefix and reviewed_preflight_hash, so a dashboard-built
manifest remains valid for replay even when the run generates a fresh idempotency prefix.
Local MKT donor inspection found `My-Krypt-Trader/.aurex-demo-userdata/data/krypt-trader.db`
present but empty across every donor table, so Stage 7 remains blocked by real demo data collection
rather than replay logic. The dashboard now renders MKT collection quality gates and launch-health
gates as dedicated operator tables, exposing donor-row, context, replay-sample, research-sample,
backtest-depth, and launch-activity blockers instead of hiding them inside one dense summary pill.
The MKT donor collection-status response now includes the scoped demo-userData launch command hints,
and the dashboard exposes a copyable launch command beside launch preflight/collection status. This
keeps the empty/inactive donor-DB state actionable without requiring a separate preflight just to
find the next command, and still does not launch MKT, read credentials, import rows, replay
campaigns, or enable live execution.
Collection status now also exposes explicit DB age seconds, latest-log age seconds, and the
freshness window used by the backend. The dashboard renders those ages in the MKT collection
freshness line so post-launch verification can distinguish "recently started but no rows yet" from
"stale/inactive" using the same 15-minute window enforced by the launch-health checks.
Collection status now includes a recommended recheck interval and next-check timestamp. The
dashboard renders this beside collection next-action guidance, giving the operator a concrete
refresh cadence after running the scoped MKT launch command while blocked/safety-failed states still
require fixing blockers first.
MKT collection quality now exposes an explicit donor evidence tier and Aurex use scope. Empty,
context-only, sparse replay/research samples, and backtest-depth candidates are labeled separately,
and the dashboard renders the tier so `COLLECTION_REPLAY_READY` cannot be mistaken for mature
live-review evidence when only a sparse donor sample exists.
MKT launch preflight now also carries a launch/evidence boundary: launch scope, current donor
evidence tier, Aurex use scope, backtest-depth readiness, and an explicit reminder that launch
readiness only starts the scoped donor collector. The dashboard renders this boundary beside launch
status so `LAUNCH_READY` cannot be mistaken for import, replay, backtest, paper/demo, live-review,
or real-trading approval.
MKT DB campaign readiness now carries the selected donor DB's quality status, evidence tier, Aurex
use scope, and backtest-depth readiness. The dashboard renders the campaign evidence tier so a
guarded campaign replay based on sparse resolved rows is visibly a sparse replay sample, not a
backtest-depth or live-review evidence set.
Accepted MKT DB campaign replay now persists donor quality status, evidence tier, Aurex use scope,
backtest-depth readiness, row counts, and depth progress into the immutable PAPER_DEMO_CAMPAIGN
event. Campaign audit rows expose the tier/use scope directly, so later review can see whether a
replay came from sparse donor rows or backtest-depth candidate data without re-querying the donor DB.
Prediction-market paper execution now supports paper SELL-to-close orders in addition to BUY
orders. SELL orders use bid-side execution checks, require an existing open paper position, reject
over-sells as risk blocks, reduce open quantity, allocate entry fees, record exit fees, persist
fee-net realized P/L on the position, and reconcile positions from net buy-minus-sell fills. The
dashboard exposes the paper action selector and order action column while live execution remains
disabled.
Prediction-market paper intents now support an explicit max quote-age risk limit. When set, Aurex
compares the selected contract snapshot's last_seen_at to the paper-intent time, rejects stale
quotes as RISK_BLOCK evidence, and stores the quote-freshness snapshot in the intent and evidence
payload. The dashboard applies a 900-second guard to manual paper order intents; historical
paper/demo replay can still omit the guard deliberately so imported resolved MKT data remains
usable for reviewed replay evidence.
Prediction-market paper intents also support an explicit selected-side max-spread risk limit. When
set, Aurex records bid, ask, spread, configured spread cap, and any spread rejection reason before
order creation. Missing, invalid, or too-wide quote spreads become RISK_BLOCK evidence. The
dashboard applies a manual 0.10 spread cap to paper order intents so thin binary markets cannot be
mistaken for executable opportunities without an explicit review choice.
Prediction-market paper submission now supports an explicit max-latency risk limit. The intent
stores the latency cap, and submission rejects too-slow modeled fills as paper REJECTED orders with
RISK_BLOCK evidence, execution-latency metadata, zero fills, and zero positions. The dashboard
applies a manual 1000ms latency cap to paper order intents so paper fills can be blocked when the
modeled delay would make the quote unsafe to trust.
Prediction-market paper submission now also supports an explicit max-slippage risk limit. BUY
orders compare modeled execution price against the selected-side ask, SELL-to-close orders compare
against the selected-side bid, and only adverse drift counts as slippage. Too-wide modeled
slippage becomes a paper REJECTED order with RISK_BLOCK evidence, zero fills, zero positions, and
execution-slippage metadata. The dashboard applies a manual 0.02 slippage cap to paper order
intents.
Prediction-market paper orders now support additive fills after a SUBMITTED or PARTIALLY_FILLED
order already exists for the intent. Later accepted submission attempts fill only the remaining
quantity, update cumulative filled quantity, average fill price, total fees, intent/order status,
and position cost basis, and record an additional FILL_RECEIVED evidence event instead of returning
the old partial result unchanged. Final, cancelled, expired, and rejected orders remain idempotent.
The dashboard now builds prediction paper execution risk limits through one shared helper for
manual paper intents, guided demo runs, batch preflight/replay, and MKT DB campaign payloads. Quote
age, spread, latency, and slippage caps no longer apply to one paper path while being accidentally
omitted from another. Guided demo API coverage confirms the execution risk gate rejects a
slippage-blocked demo order with zero fills, zero positions, and no demo-ledger record.
Prediction-market settlement accounting now preserves realized P/L from earlier paper
SELL-to-close fills. Settlement of the remaining open quantity records prior realized P/L,
remaining-settlement realized P/L, and cumulative realized P/L in the settlement payload and
evidence event. The position and settlement realized P/L now reflect the full lifecycle instead of
overwriting earlier closed-share P/L.
Prediction-market settlement fee accounting now reports total lifecycle fees after partial
SELL-to-close fills. Sell fills persist cumulative allocated entry fees, exit fees, total realized
sell-to-close fees, and sell-to-close P/L on the position payload. Settlement adds those realized
fees to the remaining open-position fees and records prior realized fees, remaining settlement
fees, and total lifecycle fees in the settlement payload and evidence event, so demo progress and
audit review see the real fee burden across the full paper trade lifecycle. Position API responses
now expose realized sell-to-close fees and lifecycle fees, and the dashboard positions table shows
open fees separately from lifecycle fees so settled or partially closed positions do not visually
understate costs.
Prediction-market demo ledger records now verify settlement evidence integrity before counting
toward paper/demo progress. A settlement record is blocked if its SETTLEMENT_RECORDED evidence hash
does not recompute, if the evidence entity does not match the settlement, or if the evidence payload
disagrees with settlement value, gross payout, realized P/L, fees, or position id. Tampered or
drifted money evidence now blocks the ledger and progress gates instead of being treated as a clean
closed record.
Prediction-market demo lifecycle evidence checks now require valid evidence hashes for every
required lifecycle event, not just row existence. Mutated MARKET_SNAPSHOT, ORDER_INTENT,
ORDER_SUBMITTED, FILL_RECEIVED, SETTLEMENT_RECORDED, or POSITION_RECONCILED evidence no longer
counts as present for closed-record readiness; a focused regression mutates fill evidence and
confirms the ledger/progress gates block the record.
Prediction-market demo ledger fill attribution is now scoped to the settled position's own
open-to-settlement lifecycle window. Reusing the same prediction contract and side for a later
paper position no longer causes the later closed record to inherit earlier fills or strategy
attribution. A regression reopens the same contract id, settles a second YES position under a
different strategy, and confirms each ledger record keeps its own strategy and quantity.
Prediction-market paper reconciliation now audits settlement money consistency in addition to
order/fill/position quantity checks. Settlements are flagged if the linked position is missing, not
settled, tied to the wrong contract, closed at a different time, has different realized P/L, or has
lifecycle fees that disagree with the settled position payload or settlement raw payload. Settled
positions without exactly one settlement are also discrepancies. A regression mutates settlement
realized P/L and fees after a clean lifecycle and confirms reconciliation reports DISCREPANCY with
explicit money-drift reasons.
Prediction-market demo lifecycle evidence validation now requires row-level semantic agreement for
order-intent, order-submission, fill, settlement, and reconciliation evidence. Hash-valid evidence
is no longer enough if its payload disagrees with the authoritative row's strategy, side, action,
quantity, price, fee, settlement, or reconciliation fields. Market snapshots remain historical
hash-validated observations. A focused regression mutates fill quantity evidence and recomputes the
evidence hash; Aurex still blocks the closed record with `fill_evidence_payload_mismatch`.
FILL_RECEIVED evidence now also has to point at a real prediction position whose contract, side, and
open/close lifecycle window contain the fill. A hash-valid fill proof with a wrong `position_id`
now fails semantic validation and blocks demo-ledger progress with `fill_evidence_payload_mismatch`.
Prediction-market campaign audit now separates immutable historical campaign payloads from current
result-ledger health. Each campaign audit row recomputes the current countable/blocked state for
the settlement ids written by that campaign and reports `CURRENT_RESULT_LEDGER_CLEAN`,
`CURRENT_RESULT_LEDGER_DRIFTED`, missing-settlement blockers, and current result fee-net P/L. The
dashboard renders this current ledger status beside historical campaign progress. A regression
mutates and rehashes one campaign fill evidence row after replay and confirms the original campaign
payload still shows its historical counts while the audit row flags current-result drift and the
underlying `fill_evidence_payload_mismatch`.
Prediction-market batch audit now uses the same current-result ledger health model. Batch audit
rows expose current result records, countable records, blocked records, fee-net P/L, drift status,
and result-ledger blockers for the settlement ids written by the batch replay. The dashboard renders
the current ledger status in the Batch audit table. A regression mutates and rehashes one batch fill
evidence row after replay and confirms the historical batch payload remains intact while the audit
row reports `CURRENT_RESULT_LEDGER_DRIFTED` and `paper_demo_result_records_blocked`.
Campaign and batch audit responses now also expose top-level current-result clean/drift counts and
prioritize current-result ledger drift in `next_action`. The dashboard audit state pills include the
drift count and turn danger when any campaign or batch replay has drifted current result evidence,
so operators do not have to inspect individual rows to notice compromised replay evidence.
Prediction-market demo ledger/progress/readiness now verify that the latest matched reconciliation
report still agrees with the current ledger rows. The paper engine exposes a read-only
`paper_reconciliation_discrepancies` preview, and closed demo records are blocked with
`current_reconciliation_drift_detected` when a stale matched report would no longer reconcile after
ledger drift. A regression mutates settlement raw accounting after a clean matched reconciliation
and confirms the record no longer counts until reconciliation is rerun cleanly.
MKT live-deployment readiness now consumes campaign and batch audit current-result health instead
of relying only on aggregate paper-demo progress. The `prediction_demo_campaign_quality` gate
requires reviewed campaign evidence for MKT-derived strategies, exposes clean/drift counts and
latest audit-row snapshots, and blocks with explicit reasons when campaign or batch replay evidence
has current-result ledger drift. A live-deployment regression replays a guarded MKT campaign,
mutates and rehashes fill evidence afterward, and confirms the live gate surfaces
`prediction_demo_campaign_current_result_drifted` plus the underlying
`fill_evidence_payload_mismatch`.
MKT live-deployment readiness is now selected-strategy scoped. The paper-demo progress builder can
filter records by strategy for internal live-gate use, and the MKT live gate reports both global
campaign/batch audit context and selected-strategy campaign/batch audit counts. A foreign MKT
campaign can no longer satisfy the selected strategy's `prediction_demo_campaign_quality` gate; the
gate blocks with `prediction_demo_campaign_strategy_evidence_missing` until the selected strategy
has its own guarded campaign replay evidence.
Strategy evidence review now gives MKT-specific next actions when the prediction demo campaign gate
blocks. Missing selected-strategy campaign evidence tells the operator to run a guarded MKT DB
paper/demo campaign replay for that strategy, current-result campaign or batch drift tells the
operator to resolve ledger drift and rerun clean reconciliation, and unacknowledged side-sensitivity
warnings tell the operator to record an explicit side-selection rationale. Regressions cover both
missing MKT campaign evidence and drifted campaign evidence flowing through evidence-review
`next_actions`.
The live deployment dashboard now surfaces the selected-strategy MKT campaign evidence directly
instead of compressing it into one generic prediction-demo line. Operators can see selected versus
total campaign audit counts, selected/total campaign drift, selected/total batch drift, and the
current demo-gate next action from the deployment panel. Dashboard contract tests pin the new
fields and helper functions so selected-strategy campaign evidence cannot disappear from the UI.
The live deployment dashboard now also surfaces strategy evidence-review next actions and blocker
summaries. After running Strategy review, the panel shows the first prescribed action from
`next_actions` and a compact blocker preview beside the review decision, so MKT campaign replay,
ledger-drift repair, broker reconciliation, or backtest work is visible without opening raw gate
snapshots. Dashboard contract tests pin the new fields and helper functions.
Strategy evidence-review freshness now fingerprints the reviewed evidence snapshots for every
required strategy-evidence gate. A CANDIDATE review is blocked if a gate's status stays the same
but its underlying evidence snapshot changes, such as an accepted backtest config hash, paper
evidence gate details, broker reconciliation evidence, or prediction-demo campaign evidence.
Volatile `checked_at` timestamps are excluded from the fingerprint so normal gate refreshes do not
create false stale-review blockers. A regression mutates the accepted backtest config hash after a
candidate review and confirms the review gate blocks with
`accepted_backtest_complete_evidence_changed_since_review` while the accepted-backtest gate itself
remains PASS.
Explicit live approvals now snapshot the current strategy evidence-review gate context, including
review id, decision, review-gate status, freshness reasons, and current required-gate fingerprints.
Approvals become stale if a previously approved CANDIDATE review later blocks because same-status
underlying evidence changed. A regression records all four manual approvals after a clean candidate
review, mutates the accepted backtest config hash without changing the backtest id or gate PASS
status, and confirms the approval gate blocks with
`strategy_evidence_review_context_changed_since_approval` while activation remains disabled.
Activation attempts now return actionable blocker summaries instead of only gate keys. The response
includes each blocking gate's key, name, status, first reason, capped reason list, and next action,
plus a deduplicated activation `next_actions` checklist. The dashboard activation summary uses the
first next action so the operator sees the repair path immediately. Regressions cover blocked
manual approvals and missing live execution adapter guidance; no live broker execution is attempted.
Approval packets now carry a stable content fingerprint, and explicit approval context snapshots
include the latest packet id, status, and fingerprint. Manual approvals become stale if the same
approval packet id later has different broker/account due-diligence content, credentials/leverage
flags, or policy/reference fields. A regression records all four approvals after a complete packet,
mutates the packet fee/slippage model reference under the same id, and confirms the approval gate
blocks with `approval_packet_context_changed_since_approval` while broker-account selection itself
still remains PASS.
Daily review readiness is now bound to the reviewed deployment context instead of trusting any
latest clean report. Daily review snapshots include the current deployment plan, accepted backtest,
paper evidence, broker-statement reconciliation, strategy evidence-review state, and approval packet
fingerprint. The `daily_review_ready` gate now blocks stale clean reviews when the current context
drifts, such as a risk-limit change after review. A regression creates a clean daily review, changes
the plan risk, and confirms the gate blocks with
`daily_review_deployment_plan_risk_per_trade_changed_since_review`.
Paper evidence CSV imports now write deterministic evidence hashes for every imported row into the
row results, import-batch snapshot, signal raw payload, risk-decision rule snapshot, and journal
evidence snapshot. Stage 14 paper-evidence integrity checks recompute the current persisted
trade/order/risk/signal/journal payload for imported trades and block if it no longer matches the
original import hash. A regression imports a clean paper export, mutates an imported trade's realized
P/L, and confirms the paper-evidence report blocks with
`imported_trade_evidence_payload_mismatch`.
Paper evidence collection status now carries `paper_evidence_freshness_reasons` from the live
paper-evidence gate and prioritizes ledger-drift repair in `next_actions`. Operators can see when a
previous paper-evidence report is stale after imported ledger drift instead of only seeing a generic
BLOCKED status. A regression imports a full passing 100-trade/30-day paper export, generates a PASS
paper-evidence report, mutates an imported trade afterward, and confirms collection status blocks
with `paper_evidence_lineage_changed_since_report`.
The dashboard paper-evidence intake panel now shows an explicit Evidence drift field sourced from
`paper_evidence_freshness_reasons`, rendering `Clean` when the current paper ledger still matches
the latest report and showing the first drift reasons when it does not. Dashboard contract tests pin
the field and JavaScript wiring.
The paper-evidence import table now includes a compact Hash column that shows the batch import hash
and the first imported row evidence hash. This gives operators a visible fingerprint trail from CSV
import to immutable imported trade evidence without flooding the table with full hashes. Dashboard
contract tests pin the hash helper and fields.
Paper evidence collection status now separates global imported rows from deployment-scoped imported
rows with `scoped_imported_count` and `out_of_scope_imported_count`. If CSV imports exist but none
match the selected deployment strategy and symbols, collection status blocks with
`paper_evidence_import_scope_missing` and tells the operator to import evidence for the current
scope. The dashboard Imported rows summary now shows scoped, out-of-scope, accepted, and rejected
counts. Regressions cover both normal scoped imports and out-of-scope-only imports.
Collection status now also returns `out_of_scope_import_summary`, a capped strategy/symbol/count
breakdown for imported paper trades that do not match the selected deployment scope. The dashboard
Imported rows summary shows the first wrong-scope symbol/count so operators can immediately see
whether they imported ETHUSDT evidence for a BTCUSDT plan, or similar scope mistakes. Regression
coverage confirms the out-of-scope summary identifies the mismatched symbol.
Paper evidence CSV preflight now receives the active deployment strategy and symbol scope and returns
`scope_status`, scoped/out-of-scope importable counts, wrong-scope summaries, and a scope next action
before any import mutates the ledger. The dashboard preflight summary shows this scope status so an
ETHUSDT export for a BTCUSDT deployment warns as OUT_OF_SCOPE before the operator imports it.
Regressions cover both in-scope and out-of-scope preflight without creating paper trades or import
batches.
Broker statement CSV preflight now previews reconciliation against the current scoped Aurex paper
ledger before any broker-statement report is recorded. The response includes current deployment
scope, Aurex trade count/net P&L/fees/slippage, reconciliation status, discrepancies, and a next
action. The dashboard statement CSV summary shows the reconciliation status and first discrepancy.
Regressions cover clean statement preflight, a READY broker CSV with no matching Aurex trades, and
bad-row CSV preflight staying non-mutating.
Live deployment remains BLOCKED and live_trading_enabled remains false.
In-app Browser tooling was not exposed in the dashboard backtest-intake turn, so the new panel is covered by static dashboard contract tests and Node syntax verification; earlier headless Chrome file-render screenshots verified the redesigned dashboard fallback and mocked-data equity curve preview at desktop and mobile widths.
```

### Goal Continuation: Core Non-Kalshi Pipeline Audit

```text
Artifacts touched:
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
src/aurex/strategy_engine/registry.py
pine/strategies/trend_pullback_v1.pine
docs/pine/trend_pullback_v1.md
tests/unit/test_pine_strategy_contract.py

Stage 1 now has a core-only audit that explicitly keeps Kalshi and My-Krypt-Trader as
optional research modules. The audit documents the current Pine, webhook, backtest,
paper evidence, and live-readiness path, plus the concrete blockers before a clean
Pine-to-paper-to-backtest run.

trend_pullback_v1 registry provenance was corrected from 1.0.0 to 1.2.0 so the
registered strategy version matches the Pine script version. A unit test now pins that
registry-to-Pine version relationship to prevent silent strategy provenance drift.

The trend_pullback_v1 Pine diagnostics table now shows strategy.opentrades and
strategy.closedtrades in addition to setup counts and latest blockers. This does not
loosen entries or claim an edge; it gives the operator a sharper TradingView diagnostic
when Strategy Tester shows no trade data.

Focused verification passed:
python -m ruff check src/aurex/strategy_engine/registry.py tests/unit/test_pine_strategy_contract.py
python -m pytest tests/unit/test_pine_strategy_contract.py tests/integration/test_strategy_portfolio.py tests/integration/test_signal_contract.py -q

Result: 15 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Backtest Setup Contract

```text
Artifacts touched:
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/api/routes/backtests.py
apps/frontend/index.html
apps/frontend/app.js
tests/integration/test_backtest_lab.py
tests/integration/test_dashboard.py

Backtest metadata for the core TradingView path now has an Aurex-owned setup contract:
GET /backtests/strategy-setup. For trend_pullback_v1 it returns the registered Pine
version, Pine/docs paths, default TradingView source reference, known strategy
parameters, settings fingerprint, cost model, slippage model, risk snapshot,
acceptance criteria, and next actions. The response is explicitly non-mutating.

The Backtest Evidence Intake panel now has a Setup action and Pine setup summary. The
button hydrates the form from /backtests/strategy-setup instead of relying only on
hand-copied version/settings JSON. This reduces the chance that an accepted backtest,
Pine alert provenance, and dashboard import metadata drift apart before paper testing.

Regression coverage now pins the setup endpoint and dashboard wiring.

Verification passed:
python -m ruff check .
python -m pytest -q
node --check apps/frontend/app.js

Result: 239 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: TradingView Alert Setup Contract

```text
Artifacts touched:
src/aurex/api/routes/webhooks.py
src/aurex/api/routes/signals.py
src/aurex/signal_gateway/schemas.py
src/aurex/signal_gateway/service.py
apps/frontend/index.html
apps/frontend/app.js
docs/pine/trend_pullback_v1.md
docs/00_AUREX_MASTER_PLAN.md
tests/integration/test_tradingview_webhook.py
tests/integration/test_signal_contract.py
tests/integration/test_dashboard.py

The TradingView webhook now accepts either the existing X-Aurex-Webhook-Secret header
or a TradingView-compatible URL query secret:
/webhooks/tradingview?secret=<AUREX_WEBHOOK_SECRET>. Header auth remains available for
controlled API clients, while query-secret auth handles TradingView's URL-and-body alert
configuration model.

The signal gateway now exposes GET /signals/tradingview-alert-setup. It returns the
exact webhook URL template, POST method, alert condition, alert message payload,
accepted-backtest provenance, required fields, security notes, TradingView delivery
constraints, preflight endpoint, verification endpoint, and next actions. The endpoint
is non-mutating and does not expose the actual secret value.

The Signals dashboard now shows Alert setup, Webhook URL, and Webhook auth, plus a
Setup alert button that loads /signals/tradingview-alert-setup and hydrates the
preflight payload text area from the backend contract. This keeps TradingView alert
configuration tied to the same accepted-backtest provenance gates used by risk
approval.

Docs now direct TradingView operators to use the HTTPS webhook URL with a query secret
and keep broker/exchange credentials out of alert bodies. The master plan security
section now distinguishes TradingView-compatible URL-secret auth from header auth for
controlled API clients.

Verification passed:
python -m ruff check .
python -m pytest -q
node --check apps/frontend/app.js

Result: 243 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Explicit Walk-Forward Evidence Gate

```text
Artifacts touched:
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/backtest_engine/eligibility.py
src/aurex/live_deployment/service.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/pine/trend_pullback_v1.md
tests/integration/backtest_helpers.py
tests/integration/test_backtest_lab.py
tests/integration/test_dashboard.py
tests/integration/test_live_micro_deployment.py
tests/integration/test_paper_evidence_import.py

The prior walk-forward calculation divided one completed-trade history into equal
chronological slices. That is a useful temporal-stability diagnostic, but it is not
independent walk-forward evidence and could contribute to an acceptance pass.

Backtest requests now support explicit anchored fixed-parameter train/test folds. Aurex
validates fold chronology, in-sample containment, non-overlapping ordered test windows,
expanding/rolling training coverage, unique window IDs, and exact strategy-parameter
fingerprints. It derives each test fold's metrics from the dated trade ledger and stores
per-fold trade hashes plus a deterministic walk-forward evidence hash.

Automatic chronological slices remain visible with method
chronological_trade_slices, but acceptance_eligible is false. Backtest acceptance,
paper eligibility, and live readiness require explicit_anchored_fixed_parameter folds,
at least three valid windows, the configured pass rate, and an intact evidence hash.
Tampering with persisted fold metrics now blocks live readiness.

The Backtest Evidence Intake panel now accepts Walk-forward windows JSON and labels the
summary EXPLICIT or DIAGNOSTIC. The setup contract returns the required method and an
empty fold list so no generated placeholder can be mistaken for real evidence. The
operator runbook documents the fold shape and keeps the final OOS period separate.

Verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js

Result: 246 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Immutable Backtest Protocol Pre-Registration

```text
Artifacts touched:
infra/alembic/versions/20260717_0022_backtest_protocols.py
src/aurex/db/models.py
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/backtest_engine/eligibility.py
src/aurex/api/routes/backtests.py
src/aurex/live_deployment/service.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/pine/trend_pullback_v1.md
tests/integration/backtest_helpers.py
tests/integration/test_backtest_lab.py
tests/integration/test_dashboard.py
tests/integration/test_database_schema.py
tests/integration/test_live_micro_deployment.py
tests/integration/test_paper_evidence_import.py
tests/integration/test_tradingview_webhook.py

Backtest designs can no longer become acceptance-eligible when their dates, settings,
costs, acceptance thresholds, or walk-forward folds are supplied only alongside the
results. POST /backtests/protocols now records the full design before report evaluation
with a registration timestamp, canonical snapshot, and deterministic SHA-256 hash.

Protocols are immutable, idempotent while unconsumed, and single-use. Exact duplicate
registration returns the existing unconsumed protocol. A changed report does not
consume the protocol; a matched report does. Reusing a consumed protocol, omitting a
protocol, changing the report configuration, or damaging protocol evidence forces
acceptance_passed=false while preserving the rejected report for audit.

Backtest runs now persist protocol_id and protocol_evidence_hash. Paper eligibility and
live readiness independently recheck the protocol record, registration ordering,
single-run consumption, run hash, metrics snapshot, and canonical protocol hash.
Protocol snapshot tampering blocks live readiness even when historical result metrics
were previously accepted.

The Backtest dashboard now exposes Register protocol, a protocol selector, protocol
status/hash feedback, and the enforced sequence: setup, register, run, preflight,
import. The runbook states the human control boundary honestly: Aurex records when the
protocol was registered, but cannot infer when an operator first viewed an external
TradingView result, so the operating procedure must still be followed.

Verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js
.\.venv\Scripts\python.exe -m alembic upgrade head

Result: 251 passed, 1 Starlette/httpx deprecation warning.
Local migration 20260717_0022 applied successfully. Real-database smoke checks returned
200 for GET /backtests/protocols and GET /dashboard.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Outcome-Blind Fold Planner And Direct CSV Loading

```text
Artifacts touched:
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/api/routes/backtests.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/pine/trend_pullback_v1.md
tests/integration/test_backtest_lab.py
tests/integration/test_dashboard.py

POST /backtests/window-plan now produces deterministic anchored fixed-parameter folds
from only the declared strategy, in-sample dates, parameter snapshot, fold count, and
initial training fraction. It does not accept or inspect CSV rows, trades, P/L, win
rate, drawdown, or other outcomes, and it has no database dependency. Repeated inputs
produce the same SHA-256 plan hash and no protocol or report record.

The planner creates expanding training coverage, ordered non-overlapping test periods,
full in-sample containment, an exact final in-sample boundary, and the same complete
parameter snapshot in every fold. It warns that calendar folds do not guarantee enough
trades and that a weak result must fail without replanning after outcomes are visible.

The Backtest Evidence Intake dashboard now exposes Plan folds before Register protocol,
shows fold count, plan hash, and zero inspected outcome fields, and hydrates the
walk-forward JSON automatically. Planning clears stale protocol selection and preflight
state so changed dates cannot silently reuse old evidence.

The dashboard can now load a TradingView CSV directly from disk while preserving the
frozen source reference. Empty files and files above 20 MiB are rejected, and loading a
new file invalidates stale preflight state. Manual paste remains available.

Verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js

Result: 254 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Immutable Historical OHLCV Evidence

```text
Artifacts touched:
infra/alembic/versions/20260717_0023_backtest_datasets.py
src/aurex/db/models.py
src/aurex/backtest_engine/datasets.py
src/aurex/backtest_engine/schemas.py
src/aurex/api/routes/backtests.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/05_HISTORICAL_DATASETS.md
tests/integration/test_backtest_datasets.py
tests/integration/test_backtest_lab.py
tests/integration/test_dashboard.py
tests/integration/test_database_schema.py

The prior POST /backtests/ohlcv/import-csv endpoint only parsed a CSV and returned a
row count. It did not import candles, preserve provenance, record a data hash, or make
the data available to a future replay engine.

Historical OHLCV inputs now have immutable backtest_datasets and
backtest_dataset_candles ledgers. Prices and volumes are stored as canonical decimal
strings so integrity checks do not silently lose source precision through database
numeric conversion. Every accepted dataset records symbol, canonical timeframe,
source, stable source reference, declared timezone, continuity policy, coverage,
quality snapshot, row count, import time, and a deterministic SHA-256 evidence hash.

POST /backtests/ohlcv/preflight-csv is no-write. It validates headers, finite values,
OHLC geometry, non-negative volume, timezone normalization, monotonic order, duplicate
timestamps, interval alignment, and gap policy. Descending exports are canonicalized;
mixed order is rejected. Missing intervals block continuous 24/7 data and remain
explicit warnings for session-based data. Fewer than 200 candles produces a warm-up
warning rather than a false sufficiency claim.

POST /backtests/ohlcv/import-csv now performs real persistence and is idempotent by
evidence hash. Dataset list, detail, and integrity-audit endpoints are available. Any
persisted candle, quality snapshot, coverage summary, metadata, hash, or row-count
drift blocks the audit. Presentation-only row-order warnings are excluded from the
canonical hash, so ascending and descending exports of the same candles remain
idempotent. No update
endpoint exists.

The Backtests dashboard now contains a Historical data workflow with direct file
loading, continuity selection, no-write preflight, quality summaries, coverage, missing
intervals, evidence hash, latest dataset, and import disabled until READY.

This is input-evidence infrastructure, not a strategy result. Aurex still does not
claim candle-by-candle Pine parity; TradingView remains authoritative until a future
reference replay engine is implemented and comparison-tested.

Verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js
.\.venv\Scripts\python.exe -m alembic upgrade head

Result: 262 passed, 1 Starlette/httpx deprecation warning.
Local database migration 20260717_0023 applied successfully.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Comparison-Only trend_pullback Reference Replay

```text
Artifacts touched:
src/aurex/backtest_engine/reference_replay.py
src/aurex/backtest_engine/schemas.py
src/aurex/api/routes/backtests.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/05_HISTORICAL_DATASETS.md
docs/06_REFERENCE_REPLAY.md
tests/integration/test_reference_replay.py
tests/integration/test_dashboard.py

POST /backtests/reference-replay/preflight now runs trend_pullback_v1 v1.2.0 against
one hash-intact continuous 24/7 dataset without writing a backtest or mutating any
ledger. Every response is comparison_only=true, acceptance_eligible=false, and
mutates_ledger=false. It cannot unlock paper or live execution.

Engine trend-pullback-reference-v1.0.0 implements causal EMA, Wilder RSI, Wilder ATR,
confirmed higher-timeframe close merging, trend/pullback/RSI/confirmation filters,
ATR/swing/wider stops, equity-risk quantity, position-value caps, directional entry
slippage, stop slippage, entry/exit commission, static brackets, post-window closure,
diagnostics, normalized trades, metrics, and a deterministic engine evidence hash.

Warm-up is enforced at the declared backtest boundary. Required base history covers
the longest local indicator, while required higher-timeframe history covers the slowest
HTF EMA. A default 15-minute/60-minute/HTF-EMA-200 setup therefore requires roughly
800 base candles before the test window instead of treating a barely initialized EMA
as equivalent to TradingView chart history.

When one candle touches stop and target, the replay resolves stop-first and records an
ambiguous exit. HTF groups use UTC epoch boundaries, session-based datasets are blocked,
positive limit gaps receive no favorable improvement, and no tick/bar-magnifier data,
funding, borrow, spread, liquidity impact, or partial fills are claimed.

The Backtests UI now exposes immutable dataset selection, replay costs, engine state,
reference trade count, fee-net P/L, warm-up coverage, blocker, replay hash, and a fixed
COMPARISON ONLY eligibility label.

Deterministic tests verify indicator values, no future HTF availability, conservative
same-bar ambiguity, a complete synthetic long/take-profit replay, repeated hash and
trade equality, no BacktestRun writes, and strict warm-up blocking.

Verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js

Result: 267 passed, 1 Starlette/httpx deprecation warning.
Live deployment remains BLOCKED and live_trading_enabled remains false.
```

### Goal Continuation: Immutable TradingView Trade-Level Parity

```text
Artifacts touched:
infra/alembic/versions/20260717_0024_backtest_parity_runs.py
src/aurex/backtest_engine/parity.py
src/aurex/backtest_engine/schemas.py
src/aurex/db/models.py
src/aurex/api/routes/backtests.py
apps/frontend/index.html
apps/frontend/app.js
docs/00_AUREX_MASTER_PLAN.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/06_REFERENCE_REPLAY.md
docs/07_TRADINGVIEW_PARITY.md
tests/integration/test_backtest_parity.py
tests/integration/test_dashboard.py
tests/integration/test_database_schema.py

The parity engine binds one immutable OHLCV dataset, one persisted TradingView report,
the report's parameter/cost/slippage configuration, the deterministic reference replay,
bounded tolerances, and complete mismatch diagnostics into one SHA-256 evidence record.

Chronological alignment isolates TradingView-only and replay-only trades instead of
shifting the remaining sequence. Aligned trades compare direction, entry/exit time,
entry/exit price, quantity, fees, net P/L, and inferred exit cause. Missing comparison
fields or broken source hashes block recording. Measurable disagreement is preserved as
FAILED negative evidence; agreement is PASSED only when every trade and required field
matches within the declared tolerances.

POST /backtests/parity/preflight is no-write. POST /backtests/parity/runs records a
PASSED or FAILED result idempotently. List, detail, and audit endpoints expose immutable
results. Audit re-hashes the stored snapshot and reruns the bound comparison to detect
source, record, or replay drift. No update endpoint exists.

The Backtests UI exposes dataset/report selectors, bounded tolerance controls, exact and
unmatched counts, top mismatch, evidence hash, mismatch rows, no-write comparison, and
explicit recording. Every result remains comparison_only=true,
acceptance_eligible=false, and cannot alter accepted-backtest, paper, or live gates.

Focused verification passed:
.\.venv\Scripts\python.exe -m pytest tests\integration\test_backtest_parity.py -q -p no:cacheprovider

Full verification passed:
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
node --check apps/frontend/app.js
.\.venv\Scripts\python.exe -m alembic upgrade head

Result: 272 passed, 1 existing Starlette/httpx deprecation warning. Local migration
20260717_0024 applied successfully. Runtime inspection found zero parity records and
zero OHLCV datasets, so validation wrote no production comparison evidence. Dashboard
desktop/mobile review found no overlap or console errors. Live trading remains false.
Real TradingView parity remains unproven until the operator supplies a matching chart
export and completed-trades export from TradingView.
```

### Goal Continuation: Trusted Core Pine Backtest Promotion

```text
Artifacts touched:
infra/alembic/versions/20260718_0025_backtest_source_artifact_hash.py
src/aurex/backtest_engine/eligibility.py
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/db/models.py
src/aurex/api/routes/backtests.py
src/aurex/live_deployment/service.py
apps/frontend/index.html
apps/frontend/app.js
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/08_TRUSTED_BACKTEST_PROMOTION.md
tests/integration/backtest_helpers.py
tests/integration/test_backtest_lab.py
tests/integration/test_backtest_source_eligibility.py
tests/integration/test_dashboard.py
tests/integration/test_live_micro_deployment.py
tests/integration/test_backtest_parity.py

Known Pine reports can remain statistically accepted for research while promotion is
blocked. POST /backtests/reports refuses payloads that self-label as TradingView; the
original completed-trades CSV must pass the dedicated importer. Each CSV preflight and
import computes a SHA-256 source_artifact_hash over the exact submitted text and
persists it on the backtest run.

The shared paper/live source policy requires TradingView parser provenance,
data_source=tradingview-export, a TradingView strategy-tester source reference, a valid
artifact hash, complete trade fields, and the registry's exact commission/slippage
assumptions. The no-write paper-eligibility endpoint exposes the selected run, source
evidence, and exact blocker. Signal contracts and live readiness consume the same
policy.

The dashboard distinguishes METRICS ACCEPTED from PROMOTION BLOCKED and PAPER ELIGIBLE.
It says source contract passed rather than implying external cryptographic trust.
TradingView does not sign operator-supplied CSV exports; Aurex binds what it receives
but cannot prove the file was not edited before upload.

Focused verification passed:
80 backtest, parity, risk, signal, and webhook tests.
43 source-eligibility, dashboard, and backtest-lab tests.
Ruff checks passed for the changed Python surfaces.
Node syntax validation passed for apps/frontend/app.js.
Alembic reports 20260718_0025 as the single head.

Full verification passed:
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check apps/frontend/app.js
.\.venv\Scripts\python.exe -m alembic upgrade head

Result: 278 passed, 1 existing Starlette/httpx deprecation warning. Migration
20260718_0025 applied to the local SQLite ledger. Runtime inspection confirmed the new
paper-eligibility route is present, health is OK, deployment is BLOCKED, live trading
is false, and the four existing reports remain ineligible old/weak evidence. No fake
backtest, dataset, parity, paper, or live record was created during smoke testing.

Browser verification loaded the Backtests view with the eligibility row visible,
plain-language source-contract state, versioned frontend asset, and no console warnings
or errors. Live trading remains disabled.
```

### Goal Continuation: Pine v1.3 And Frozen TradingView Run

```text
Artifacts touched:
pine/strategies/trend_pullback_v1.pine
src/aurex/backtest_engine/reference_replay.py
src/aurex/backtest_engine/parity.py
src/aurex/backtest_engine/eligibility.py
src/aurex/backtest_engine/schemas.py
src/aurex/backtest_engine/service.py
src/aurex/api/routes/backtests.py
src/aurex/strategy_engine/registry.py
apps/frontend/index.html
apps/frontend/app.js
docs/02_TRADINGVIEW_BACKTEST_IMPORT.md
docs/06_REFERENCE_REPLAY.md
docs/07_TRADINGVIEW_PARITY.md
docs/08_TRUSTED_BACKTEST_PROMOTION.md
docs/09_FROZEN_TRADINGVIEW_RUN.md
docs/pine/trend_pullback_v1.md
tests/unit/test_pine_strategy_contract.py
tests/integration/test_reference_replay.py
tests/integration/test_backtest_parity.py
tests/integration/test_backtest_lab.py
tests/integration/test_backtest_source_eligibility.py
```

`trend_pullback_v1` v1.3 uses previous confirmed higher-timeframe EMA values, rejects
an invalid higher-timeframe selection, sizes from the expected slipped fill using
symbol point value, rounds down to the symbol minimum contract, and closes an open
position on the frozen end-boundary candle. Diagnostics distinguish setups, submitted
orders, filled entries, open trades, and completed trades.

Reference replay v1.1 mirrors those semantics and requires explicit tick size, point
value, and minimum contract. Protocol hashes now include the exact Pine source SHA-256
and embedded version. The no-write run-manifest endpoint validates source, strategy,
scope, settings, costs, timeframe geometry, protocol integrity, and consumption state.
Promotion policy v2 blocks old strategy versions, protocols without source evidence,
and recorded/current Pine hash drift.

Focused verification passed: 62 Pine, replay, parity, protocol, manifest, and source-
promotion tests.

Full verification passed:

```text
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check apps/frontend/app.js
.\.venv\Scripts\python.exe -m alembic current
```

Result: 281 passed with one existing Starlette/httpx deprecation warning. Alembic is at
`20260718_0025 (head)`. Runtime health is OK; the current source is v1.3.0 with source
evidence ready; the manifest endpoint is present in OpenAPI; deployment remains
BLOCKED with live trading false. No protocol or fake trade evidence was created during
runtime checks. Desktop and 390 px browser checks found no page-level overflow,
overlap, or console errors. The Backtests UI correctly displays a current Pine source
while keeping the run manifest blocked until a real protocol is registered.

## Next Stage

```text
Run the source-bound v1.3 manifest in TradingView and import authentic completed trades.
```

Only an authentic external run can establish whether the strategy produces completed
trades and whether the replay matches TradingView. Paper evidence collection remains
downstream of accepted backtest and promotion gates. Live mode remains disabled.
### Goal Continuation: TradingView Delivery Contract Hardening

- TradingView timestamps now normalize to UTC and minute-only timeframe values such as `15`
  normalize to Aurex's canonical `15m` form before persistence, preflight, cooldown checks, or
  idempotency hashing.
- Signal idempotency now includes strategy version and settings fingerprint. Cooldown duplicate
  checks only compare signals with matching provenance, preventing a newly reviewed strategy
  version from being conflated with an older alert.
- The database now enforces one non-duplicate signal per idempotency key using a partial unique
  index. Rejected redeliveries remain stored as immutable `DUPLICATE_REJECTED` audit records.
- Webhook authentication rejects conflicting header/query credentials instead of accepting a
  request when only one supplied credential is valid. Production configuration rejects the local
  default secret and secrets shorter than 32 characters.
- Webhook responses now include signal/idempotency identifiers, measured processing time, the
  configured 2.5-second budget, and whether the request stayed within budget. The Signals table
  shows measured processing latency and an idempotency-key preview.
- The webhook remains synchronous. These measurements prove the bounded local request path; they
  do not claim a durable asynchronous queue or guaranteed internet delivery.

### Goal Continuation: Core-First Command Center

- The Command Center evidence path no longer derives its primary blocker from the optional
  prediction-market/MKT demo runbook.
- The first screen now orders the real non-Kalshi path: current Pine source, frozen protocol,
  verified run manifest, accepted TradingView backtest, signal contract, paper evidence, broker
  sandbox, and the locked live boundary.
- A matching registered protocol now triggers automatic no-write run-manifest verification during
  dashboard refresh, so the next operator action remains current without mutating evidence.
- MKT remains available in its dedicated research and Markets views, but it cannot displace the
  core Pine-to-paper roadmap on the Command Center.

### Goal Continuation: Verified Real Data And Immutable Reference Replay Evidence

```text
Artifacts touched:
infra/alembic/versions/20260718_0027_reference_replay_evidence.py
src/aurex/backtest_engine/binance_vision.py
src/aurex/backtest_engine/datasets.py
src/aurex/backtest_engine/reference_replay.py
src/aurex/backtest_engine/schemas.py
src/aurex/api/routes/backtests.py
src/aurex/db/models.py
scripts/prepare_binance_vision_ohlcv.py
scripts/submit_ohlcv_dataset.py
apps/frontend/index.html
apps/frontend/app.js
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/06_REFERENCE_REPLAY.md
docs/09_FROZEN_TRADINGVIEW_RUN.md
tests/integration/test_backtest_datasets.py
tests/integration/test_database_schema.py
tests/integration/test_dashboard.py
tests/integration/test_reference_replay.py
tests/unit/test_binance_vision.py
```

Official Binance Vision monthly spot kline archives for BTCUSDT 15-minute candles from
December 2025 through March 2026 were downloaded with their official CHECKSUM files.
All four ZIP SHA-256 values match. Aurex normalized 11,521 continuous candles with no
rejected rows, gaps, duplicates, or interval mismatches and persisted the artifact
manifest, transformation evidence, canonical CSV hash, and dataset evidence hash.

Reference replay runs can now be recorded in a separate immutable comparison ledger.
The record binds the request, dataset evidence, engine evidence, and complete result
snapshot under an independent record hash. Audit recomputes the record hash, re-audits
the dataset, reruns the engine, and compares all source and result evidence. Blocked
runs cannot be recorded; negative READY runs can and must be preserved. List responses
carry summaries only, while the detail endpoint retains the complete trade ledger.

The frozen v1.3 settings produced 165 completed trades: 60 wins, 105 losses, net P/L
`-56.26266144456834359502881484`, profit factor
`0.8873119185405395227734327481`, expectancy
`-0.340985826936777839969871606`, and max drawdown
`105.2860460418374101497583642`. The immutable run ID is
`a0780214-6e6a-4e89-92e0-6e0c8e64e0a3`; record evidence is
`d5cf749742e8407e589f47206630534157a3a5c55e234344467cbe29aff6de90`.
Its live audit passes the record, dataset, engine, and full-result checks.

Verification passed:

```text
293 tests passed.
Ruff checks passed.
Node syntax validation passed.
Alembic is at 20260718_0027 (head).
Runtime health is OK at http://127.0.0.1:8921.
Live trading remains false.
```

Browser verification confirmed the Backtests view renders the checksum-verified
dataset, `READY / RECORDED` comparison state, negative P/L, replay and record hashes,
and disabled record action until a new READY preflight exists. TradingView parity is
still `NOT_RUN`. No acceptance, paper, or live eligibility was granted.

### Goal Continuation: Immutable Frozen Replay Validation

```text
Artifacts added or updated:
infra/alembic/versions/20260718_0028_reference_replay_validation.py
src/aurex/backtest_engine/reference_validation.py
src/aurex/backtest_engine/schemas.py
src/aurex/api/routes/backtests.py
src/aurex/db/models.py
apps/frontend/index.html
apps/frontend/app.js
docs/04_CORE_NON_KALSHI_PIPELINE_AUDIT.md
docs/06_REFERENCE_REPLAY.md
docs/09_FROZEN_TRADINGVIEW_RUN.md
tests/integration/test_reference_replay_validation.py
tests/integration/test_dashboard.py
tests/integration/test_database_schema.py
```

Recorded reference replays can now be evaluated against intact frozen protocols in a
separate immutable validation ledger. Preflight checks 13 execution and protocol
bindings. Bound results preserve both `PASSED` and `REJECTED` evidence and reuse the
trusted evaluator for whole-period, IS/OOS, fixed-parameter walk-forward,
concentration, purge-gap assignment, and market-regime metrics. Audit recomputes the
record hash and reruns the complete evaluation to distinguish row tampering from
source or evaluator drift. The workflow never consumes a TradingView protocol and can
never grant acceptance, paper, promotion, or live eligibility.

The real frozen v1.3 validation was recorded as `REJECTED` under ID
`a497fbb1-4ac2-4129-9fd5-0906e60caffd`. All 13 source bindings pass and the live audit
passes. Out of sample, 80 trades lose `-77.40020859563734909558749818`, profit factor
falls to `0.7166499314333067526012171848`, and expectancy falls to
`-0.967502607445466863694843726`. The evaluator rejects five gates: overall profit
factor, overall expectancy, maximum drawdown, OOS expectancy, and OOS profit factor.
The protocol remains registered and unconsumed.

Verification passed:

```text
297 tests passed.
Ruff checks passed.
Node syntax validation passed.
Alembic is at 20260718_0028 (head).
Runtime health is OK at http://127.0.0.1:8922.
Live trading remains false.
```

Browser verification confirmed `REJECTED / RECORDED`, 13/13 binding checks, the OOS
metrics, all three in-sample walk-forward folds, concentration, regime split,
assignment counts, evidence hash, and primary blocker. The record action is disabled
without a new recordable preflight. The next boundary is unchanged: run the frozen
manifest in TradingView, preserve authentic completed trades and chart OHLCV, import
the report, and measure trade-level parity before strategy revision.

### Goal Continuation: Venue-Bound TradingView Run Package

The external run contract previously identified `BTCUSDT` and `15m` but omitted the
TradingView venue. Aurex now parses the source reference structurally and requires
`tradingview://strategy-tester/<VENUE>:<SYMBOL>/<timeframe>` for new TradingView
protocols. Manifest checks bind the qualified ticker's symbol and timeframe to the
protocol. The historical unqualified protocol remains immutable and unconsumed, but
its current manifest correctly blocks it.

A new no-write run-package endpoint returns the exact Pine source, source SHA-256,
byte and line counts, venue-qualified TradingView URL, frozen setup, manifest hash,
and an independent package hash. Backtest Lab exposes **Prepare run**, **Copy Pine**,
and **Copy setup** only when the corrected manifest and package are ready.

```text
Corrected protocol:   288ea36e-abbf-4c1a-b15e-85ef5b097a93
Protocol hash:        3a5345306896b4f57005e61f6891ebb788b071901c71f16767a290aecb7bc160
Manifest hash:        f5625d927d5b2310994fd0ca43280f6b4863c0034e14bd38e11827b729dce0fa
Run package hash:     70264556b47df476837cdede26bd3d7d0ee517e066ca89deedbfe02c5d1e4cff
Ticker ID:            BINANCE:BTCUSDT
Manifest / package:   READY 13/13 / READY
Corrected validation: 4e580237-2abe-4c56-99fb-94e780c1f992 / REJECTED / audit PASS
```

The replacement corrects setup identity; it does not improve results. The same 165
replay trades still fail five frozen statistical gates. TradingView execution and
trade-level parity remain the next evidence boundary.

Verification passed:

```text
298 tests passed.
Ruff checks passed.
Node syntax validation passed.
Alembic is at 20260718_0028 (head).
Runtime health is OK at http://127.0.0.1:8923.
Live trading remains false.
```

Desktop and narrow-viewport browser checks show the qualified ticker, ready manifest,
ready package, 13/13 checks, corrected validation hash, and no console errors. Copying
Pine on Windows converts LF to CRLF on the system clipboard; normalizing line endings
reproduces the registered 19,277-byte source and SHA-256 exactly.

### Goal Continuation: Evidence-Grade Core Paper Execution

The native core paper engine no longer creates optimistic `instant` fills with zero
cost. New webhook-driven paper orders use `deterministic_costed_market_v1` and bind
commission, half-spread, market-impact, latency, entry costs, exit costs, lifecycle
state, and reference-price semantics into a versioned assumptions snapshot and
SHA-256 evidence hash. Defaults are conservative and configurable through
`AUREX_PAPER_*`; they remain simulation assumptions rather than broker observations.

Paper close accounting now subtracts both previously recorded entry costs and exit
costs. Omitted or understated operator close costs cannot undercut the deterministic
model floor. The sandbox broker uses the originating modeled entry fee by default so
an ordinary sandbox fill can reconcile without silently assuming zero cost.

Paper-evidence and first-profit reports now audit fill status, price, quantity,
complete lifecycle assumptions, assumptions hash, cost breakdown, net P/L
reconciliation, and model provenance. Only hash-valid deterministic fills and
hash-verified `paper_evidence_import` fills are evidence-grade. Legacy `instant`,
fixture, incomplete, cost-inconsistent, or drifted fills block promotion and the
first `$100` milestone. Fill-model changes invalidate an already-passed report through
the paper ledger freshness gate.

The Deployment and Evidence Collection views expose evidence-grade count, non-grade
count, execution violations, and fill-model distribution. Native deterministic paper
evidence no longer requires a separate CSV import, while strict external paper CSV
evidence remains supported.

```text
Migration: 20260718_0029 (head)
Focused core execution/live/broker/import tests: 80 passed
Database migration tests: 2 passed
Dashboard tests: 2 passed
Ruff checks passed.
Node syntax validation passed.
Full suite: 300 tests passed with one upstream Starlette/httpx deprecation warning.
Live trading remains false.
```

### Goal Continuation: Complete Multi-Year Verdict And Versioned Cost Audit

The documented-outage replay path now strictly re-audits persisted gap metadata,
including exact observed/documented windows, interval counts, boundaries, overlap,
contradictions, and zero undocumented gaps. The checksum-verified Binance Vision
BTCUSDT 15-minute dataset remains immutable with 122,587 candles, 42 verified monthly
archives, one documented five-candle outage, no malformed rows, no undocumented gaps,
and evidence hash
`2a048a6709d0f066977d317ec2d013d362cc68a5f626d85201e98d9c6925440e`.

The complete frozen `trend_pullback_v1` v1.3 replay was recorded under ID
`e1e5539a-49df-409d-8790-93639e173dc5`. Across 2,270 trades it loses
`-695.5152112861285744311254420`, records profit factor
`0.8078717551837752288683041169`, expectancy
`-0.306394366205342984330892264`, and replay max drawdown
`699.0051029879905739447573387`. Its dataset, engine, result, and record hashes audit
`PASS`.

An outcome-blind six-fold expanding chronological protocol was registered under ID
`ebcaffa2-1598-4763-81e2-163da8a77ecf` using the already frozen acceptance thresholds.
No result fields were inspected by the window planner and no thresholds were relaxed.
The corrected immutable validation is ID
`454b85d7-75b2-4a6e-8571-b9d951cbc178`, evaluator
`reference-replay-validation-v1.1.0`, evidence hash
`a66caaff0992ecbe8784b411dfe2eee4a2502f16587808dbf42a3f19bfb38249`.
All 15 lineage and metric bindings pass and the validation audit replays exactly.

Evaluator v1.1 removes post-trade account equity from statistical drawdown input, so
the first loss is measured against the segment start. Whole-period validation now
matches replay drawdown exactly. Legacy evaluator v1.0.0 records remain immutable and
continue to audit under their original schema; the preserved real legacy validation
`9edfd67d-ec11-4885-bd5f-255daa539115` still audits `PASS`.

The new fixed-path cost audit reconciles base replay results and records five scenarios:

```text
Zero-cost upper bound: +175.7252 / PF 1.05755 / max DD 96.7403
Half cost:             -259.8950 / PF 0.92211
Base cost:             -695.5152 / PF 0.80787 / fees 870.5994 / slippage 0.6411
150% cost stress:     -1131.1354 / PF 0.71026
200% cost stress:     -1566.7556 / PF 0.62592
```

The formal validation fails six gates: overall profit factor, overall expectancy,
maximum drawdown, OOS profit factor, OOS expectancy, and walk-forward pass rate. IS
loses approximately 533.65, OOS loses approximately 161.87, both detected market
regimes lose, and zero of six fixed-parameter folds pass. The frozen verdict is
`REJECT trend_pullback_v1 v1.3` for eligibility and paper progression. The result is
preserved; it is not a prompt to parameter-tune this version.

Verification passed:

```text
Focused replay/dataset tests: 35 passed.
Wider Stage 4 integration tests: 77 passed.
Full suite: 315 passed with two known pytest/Starlette warnings.
Ruff checks passed.
Runtime health is OK at http://127.0.0.1:8926.
Live trading remains false.
```

The exact next boundary is authentic TradingView strategy identity and trade-level
parity. The observed `Aurex jam_reversal_v1` study is not assumed to be the frozen
candidate. Parity remains comparison evidence and cannot reverse this local rejection
without authentic, separately preserved TradingView trades and OHLCV.

### Goal Continuation: Restored Goal And Strategy Research Discipline

The persistent goal service no longer exposed the prior active goal after task
interruption, so the single Aurex Stage 1-10 program was restored from
`docs/10_PROJECT_CONTROL.md`. The restored goal preserves all evidence and makes the
post-rejection sequence explicit: bounded v1.3 parity calibration, genuine external
webhook proof, then a separately versioned and predeclared candidate. Live trading
remains disabled.

Read-only TradingView inspection proved the active chart is `BINANCE:BTCUSDT` at 15m
with `Aurex jam_reversal_v1` v1.14.0. Pine source retrieval matched the current local
702-line, 48,667-character file exactly under SHA-256
`f1c7231bd2f9a919157dbe14388fc838d6d484f9cda50c2a36c4e6b79b49a7c3`.
The current source has zero compile errors. A fresh screenshot visibly confirms
`+$24.87`, five profitable trades out of five, and `$2.17` max drawdown from May 1
through July 20, 2026.

Those metrics were classified as development-contaminated rather than promoted.
The strategy document records repeated entry, exit, filter, target, stop, timeframe,
and symbol probes from v1.0.1 through v1.14.0 against the same sparse windows. The Pine
console independently shows repeated compile/save cycles. Nearby BTC timeframes plus
documented ETH and SOL probes are also contaminated for the inspected periods. A
five-trade no-loss survivor is not reliable edge evidence.

`docs/11_STRATEGY_RESEARCH_DOCTRINE.md` now defines lifecycle states, contamination,
single-use held-out decisions, required freeze records, and current candidate states.
`trend_pullback_v1` v1.3 remains retired/rejected. `jam_reversal_v1` v1.14.0 is
exploratory/quarantined and cannot unlock paper trading. Any Jam continuation requires
a new version, explicit contamination map, untouched decision set, and frozen protocol.

The v1.3 TradingView package remains `READY` with package hash
`70264556b47df476837cdede26bd3d7d0ee517e066ca89deedbfe02c5d1e4cff` and exact Pine
hash `9e68cf52c1072d0efbb4b588d96474439d8283c4ee08c62fd8c700e4870596f7`.
TradingView MCP's internal strategy-results call incorrectly returned `no strategy`
despite the visible Strategy Tester, so it is not accepted as a metrics source.
Completed-trades CSV remains the parity evidence requirement.

The exact blocker is now explicit user authority to replace the current Jam editor/chart
state with the frozen trend source for one bounded Jan-March 2026 parity run. No chart,
Pine, alert, paper, or live mutation was performed during this checkpoint.

### Goal Continuation: Genuine Webhook Evidence Boundary

The Stage 3 audit found that the prior verification endpoint could label an internally
posted payload as TradingView-verified after observing its downstream paper objects.
The payload's declared `source=tradingview` did not establish delivery origin. That
false-positive evidence boundary is now closed.

The webhook route now hashes the exact HTTP body and records authentication transport,
method, path, content type, byte length, direct peer IP, user agent, source-IP verdict,
and a deterministic delivery-receipt hash on the first `RECEIVED` signal event. The
shared secret itself is never persisted. Source networks are configurable through
`AUREX_TRADINGVIEW_WEBHOOK_SOURCE_NETWORKS`; defaults match TradingView's four published
webhook sender addresses checked on July 20, 2026. Forwarded headers are not trusted,
so a proxy or tunnel cannot silently claim platform origin.

Verification now separates `delivery_verified`, `pipeline_verified`, and full
end-to-end `verified`. A real alert for an ineligible strategy may correctly produce
`DELIVERY_VERIFIED_PIPELINE_BLOCKED`: delivery is proven, risk rejects the signal, and
no paper order is created. This allows Stage 3 to be proven without bypassing the
rejected v1.3 evidence or starting Stage 6.

The Signals UI exposes external proof, delivery proof, Aurex pipeline status, origin,
and authentication transport separately. `docs/12_TRADINGVIEW_WEBHOOK_EVIDENCE.md`
defines the operational proof procedure and explicitly excludes synthetic source-IP
fixtures from accepted evidence.

The complete suite exposed one stale portfolio assertion after Jam registration. The
contract now includes Jam, while fresh databases seed quarantined `jam_reversal_v1`
disabled. Existing operator records are not overwritten. This preserves research
visibility without treating registration or five tuned trades as eligibility.

Verification passed:

```text
Webhook, verification, and dashboard tests: 24 passed.
Strategy registry and Pine contract tests: 17 passed.
Full suite: 322 passed with two known pytest/Starlette warnings.
Ruff checks passed.
Frontend JavaScript syntax passed.
Live trading remains disabled; TradingView was not mutated.
```

Operational Stage 3 evidence is still missing because no real TradingView alert was
sent. The next external actions remain the explicitly authorized frozen parity run and
one bounded webhook probe with an expected eligibility-safe risk rejection.

The final receipt audit now recomputes the deterministic evidence hash during
verification. A focused tamper test changes stored delivery metadata without updating
its hash and proves that `webhook_payload_integrity_recorded` becomes `BLOCKED`.

### Goal Continuation: Volatility Replay, Preregistration Incident, And Temporal Guard

`volatility_breakout_v1` was hardened without inspecting a strategy outcome. Pine
v1.1.0 now has confirmed higher-timeframe EMA inputs, explicit costs and slippage,
date bounds, risk-based sizing, position-value caps, end-of-window liquidation,
diagnostics, source/version identity, and an exact settings fingerprint. Its frozen
source SHA-256 is
`4b692f3f95c06ae4bfa787f2c8f4fc2039859d55b9f040cd78284ce720f55d35`.
The original signal thresholds were not changed.

A separate preregistration package fixed the BTCUSDT 15-minute dataset, 2023-2026
window, IS/OOS split, six expanding fixed-parameter folds, base costs, risk settings,
and acceptance gates. The first registration call flushed protocol ID
`42a995dc-1a7a-40d8-ba86-21f08fe3725d` but the caller failed to commit the transaction.
Session close rolled it back. That ID is not persisted evidence and all earlier claims
that it was immutable preregistration are withdrawn.

The deterministic replay was then persisted under ID
`9c2f12c7-9ee8-46c3-b8ea-c4aacbb5fae7` at
`2026-07-21T12:11:20.906155Z`. It uses engine
`volatility-breakout-reference-v1.0.0`, record hash
`67fbd22e0b195cb16c3bc37caadb269e292b91e0e4859bd88d3c89dfcff4c20f`,
and audits `PASS`. The actual protocol
`6d0f10f1-8e23-42a2-874a-b36948bc1738` was committed at
`2026-07-21T12:12:13.076304Z`, approximately 52.17 seconds after the replay. No formal
validation record was created.

The replay is preserved as diagnostic negative evidence:

```text
Overall: 1,125 trades / -$533.8729 / PF 0.6734 / expectancy -$0.4746
IS:        655 trades / -$396.6601 / PF 0.6523
OOS:       470 trades / -$137.2127 / PF 0.7222 / negative expectancy
Drawdown:  $556.4810
Walk-forward: 0/6 folds pass
Zero-cost fixed-path upper bound: -$37.1046 / PF 0.9714
```

This is enough to retire v1.1.0 even though the late protocol prevents a formal
eligibility verdict. The full result is now contaminated and cannot be reused as a
held-out decision for a renamed or lightly edited successor.

The audit also found that the historical trend protocol used by the corrected v1.1
validation was committed approximately four minutes after its replay. Its immutable
negative validation remains auditable under evaluator v1.1.0 and its rejection remains
conservative, but it is not strict preregistration by current standards.

Evaluator `reference-replay-validation-v1.2.0` now requires the durable protocol
timestamp to be no later than replay time. A violation returns `BLOCKED`, exposes no
metrics, creates no validation hash, and cannot be recorded. Evaluation schemas remain
versioned so old v1.0.0 and v1.1.0 records still audit without historical rewriting.

Candidate registration now has a transaction-owning workflow in
`scripts/register_candidate_protocol.py`. It refuses any candidate version with an
existing replay, commits the protocol, reopens it in a fresh session, and verifies its
stored hash before emitting a receipt. Against the real ledger it correctly refuses
volatility v1.1 because its replay already exists.

Verification at this checkpoint:

```text
Focused evaluator, preregistration, and replay tests: 25 passed.
Full suite: 334 passed with one known Starlette/httpx deprecation warning.
Ruff checks passed.
Historical trend v1.1 validation audit: PASS.
Current trend and volatility temporal preflights: BLOCKED as expected.
Live trading remains disabled. No TradingView mutation occurred.
```

### Goal Continuation: Slow-Spot Rejection And Research Reset Foundation

The one-shot `slow_breakout_spot_v1` v1.0.0 ETH/SOL holdout campaign completed and
returned `REJECT`. Both replay audits and both validation audits pass. ETH made
`+$44.6864` overall and `+$7.2549` OOS but passed only one of five walk-forward folds.
SOL made `+$59.7447` overall but lost `-$18.3894` OOS, recorded OOS PF `0.5185`, and
passed zero folds. The preregistered rule required both individual validations to
pass, so the pooled `+$104.4311`, PF `1.6968`, and positive 150% cost stress could not
rescue the candidate.

The campaign artifact is
`data/evidence/slow_breakout_spot_v1_1.0.0_cross_market_decision.json`, hash
`ce8ce41c25e8dff811db44bf8fe8a77af8d920f67c811be8b6fd403154a95c82`.
An independent canonical recomputation passes. Cross-market decision hash is
`b1214ceb3e2f6ef416d0ef83b27e93e331afa5ff59c3201680f5e8013c9bd4d3`.
Version 1.0.0 is retired without tuning.

Development-only failure attribution showed modeled costs were small and the positive
whole-period return depended on isolated trends that decayed across time. It also
identified a prospective study-design flaw: an approximately 16-trade annual rate was
paired with quarterly folds requiring five trades. The frozen result was not changed;
SOL independently failed OOS. Future low-frequency fold designs must be mechanically
compatible before registration.

`docs/16_STRATEGY_RESEARCH_RESET.md` now blocks nearby parameter edits and defines a
portfolio-aware reset. A new pure engine,
`shared-capital-spot-portfolio-v1.0.0`, allocates simultaneous long-spot opportunities
against one shared cash/equity ledger. It applies adverse slippage, commission,
quantity rounding, symbol/portfolio exposure, priority and position limits, aligned
mark-to-market drawdown, rejection evidence, canonical hashes, deterministic replay,
and tamper-detecting audit.

The machine-readable contamination ledger records six known development/opened scopes
under hash
`9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`.
Its builder check passes and overlap queries can now block reused family/symbol/
timeframe/windows mechanically. Every unqualified registered strategy now seeds
disabled on fresh databases; existing operator records are preserved.

Focused verification at this point:

```text
Portfolio, contamination, and strategy-default tests: 22 passed.
Relevant Ruff checks passed.
Slow holdout artifact hash: PASS.
Contamination ledger builder check: PASS.
Full project suite: 369 passed with one known Starlette/httpx warning.
Repository-wide Ruff: PASS.
Live trading remains false. TradingView was not mutated.
```

The exact next local control is a survivorship-aware, machine-readable market-universe
manifest and data partition freeze. No new candidate or market outcome may be opened
before it exists.

### Goal Continuation: Survivorship-Aware Universe And Partition Freeze

R2 is complete without importing a new strategy outcome. Aurex enumerated Binance
Vision's historical monthly spot-kline namespace rather than using current
`exchangeInfo`, preserving `3,643` historical spot symbols and all `680` USDT markets.
The source pass encountered a valid historical non-ASCII USDT market; acquisition was
stopped, storage paths were hardened with deterministic ASCII-safe IDs while exact
market identity remained intact in the artifact, tests were added, and acquisition
resumed from the existing receipts.

The frozen rule uses only January 2023 through December 2024 archive availability,
checksum-sidecar presence, UTC daily open times, and USDT quote volume. It requires 24
complete 4h archive months, 731 daily rows, at least 700 active days, median daily quote
volume of `$10,000,000`, and nearest-rank p10 volume of `$1,000,000`. It excludes
cash-like bases and leveraged-token suffixes mechanically. The contamination-ledger
hash makes BTC, ETH, and SOL development-only. OHLC prices, returns, trades, P/L,
profit factor, and every other strategy outcome field are forbidden by schema.

The resulting manifest is `READY`: `35` decision candidates, `3` development-only
markets, and `642` exclusions. Twelve delisted/current-API-inaccessible markets used
checksum-verified daily archive fallbacks; none had complete 731-day coverage, so all
were excluded instead of filled or hidden. The exact source snapshot contains `1,534`
raw official payloads totaling `49,939,802` bytes.

Evidence hashes:

```text
Enumeration: 682dbab67d1dfb87586cdc89993f05d551d81dad28aee7b36ea967c237f28e62
Liquidity:   a4c7dfbbfe94f4be4a77fa18019adf7b96f92495bbece9a763a69d638f472719
Manifest:    dacc57f649846f716b8134aa0abba5accc78b0f1607d653addb0df3d9e132a74
Builder:     0dd484d55dc33493d73bb9831d01d79bede78c0d89df10cdc433d91537919b86
```

`scripts/build_market_universe.py --check` performs no network access. It verifies all
raw payload sizes and SHA-256 hashes, reloads both input artifacts, rebuilds every role
and summary from the current contamination ledger and builder contract, audits the
manifest, and refuses a structurally valid universe if fewer than 12 decision markets
pass. The offline check passes.

R3 is now the next local stage. It begins with checksum-verified 4h OHLC for only the
2023-2024 development partition across the 38 included markets, followed by a frozen
mechanism-study protocol before any development return is calculated. Validation,
holdout, forward paper, sandbox, micro-live, and real capital remain unopened.

Checkpoint verification completed with `395` tests passing across five exhaustive
bounded shards and repository-wide Ruff passing. The only warning is the known
Starlette/httpx deprecation. One earlier monolithic pytest process lost its command
runner pipe at roughly 80 percent and returned no test failure or valid completion, so
it was discarded rather than counted.

### Goal Continuation: R3 Data, Protocol, And Execution Freeze

R3 crossed the complete pre-outcome boundary without calculating a strategy return.
The official Binance Vision acquisition contains 38 continuous development datasets:
35 mechanically selected decision markets and diagnostic-only BTC, ETH, and SOL. Each
contains all 4,386 expected 4h candles from `2023-01-01T00:00:00Z` through the final
bar before `2025-01-01T00:00:00Z`. The bundle preserves 912 monthly archives, 912
checksum sidecars, 38 canonical CSVs, and 38 source manifests. All 166,668 candles are
ready with zero missing timestamps.

The R3 mechanism study is separately frozen before outcomes. It tests long-only
cross-sectional momentum with one non-replaceable 84-day/14-day primary and fixed
28-day/7-day and 168-day/28-day falsification variants. It uses six independent
quarterly folds, one shared `$1,000` portfolio, 0.5% position risk, a 20% symbol cap,
a 100% gross cap, conservative two-sided costs, simultaneous cost stress, and
all-or-nothing profitability, drawdown, sample, fold, concentration, and
leave-one-market-out gates. Validation, holdout, and forward partitions are forbidden.

Before engine implementation, a second artifact froze details that the hypothesis
protocol did not fully settle: timestamp alignment, score indexes, symbol tie-breaks,
Wilder ATR seeding, stop construction and gaps, rebalance event order, same-symbol
re-entry, simultaneous allocation, rounding, fold anchors and liquidation, metric
denominators, concentration, and full cost-stress replay scope. The first direct freeze
invocation found a package-import defect and exited before writing evidence. The entry
point was repaired and directly tested; no outcome or partial artifact was created by
that failed invocation.

Evidence hashes:

```text
Development bundle: fba63b8e237220c760daf902f2c999e9b01121357a4cc583c9fa5cb50b83d341
R3 protocol:        8af37e15ca08bcbbdd82c457927d5a4b5039e70f173ff735c16c91a3bed4f893
R3 execution spec:  7125758ab4b4672576db8de49d8f67f5988f02dc5c39e2d94d36ae2e7edb6eb6
```

All three artifacts reproduce through network-free checks. Focused bundle, study, and
execution-spec verification passes with `24 passed`; focused Ruff passes. The last
full-project checkpoint remains 395 passing tests and must be rerun after the R3 engine
lands. The exact next step is engine implementation on synthetic fixtures, followed by
an engine-source and run-package hash freeze. Only then may the first development
outcome be calculated. Live trading remains false and no TradingView mutation occurred.

### Goal Continuation: Frozen R3 Engine, One-Shot Study, And No-Candidate Verdict

The R3 engine was implemented and verified entirely on synthetic fixtures before any
development outcome was calculated. It pins a 50-digit half-even Decimal context and
implements exact all-market alignment, prior-close momentum ranking, symbol tie-breaks,
Wilder ATR, sample log-return volatility diagnostics, exit/rank/re-entry ordering,
entry-bar stop exclusion, gap stops, proportional shared-capital allocation, quantity
rounding, cost stress, independent fold resets, final liquidation, raw/net P&L,
mark-to-market drawdown, turnover, exposure, concentration, and tamper-detecting hashes.

The final pre-outcome run package bound the exact Python/Pydantic runtime, transformed
35-market data hash, all outcome source hashes, and a 62-replay matrix: 9 full-window
variant/cost runs, 18 independent variant/fold runs, and 35 primary leave-one-market-out
runs. Repository-wide Ruff and all 131 unit tests passed before freeze. The package
hash is
`2ca29f9328306c91f8281051731592da5e3d8b00db47573f5f4b08b9d9bb2756`; the
transformed candle hash is
`ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2`.

The one-shot campaign completed all 62 planned replays and committed ledger hash
`dd751538457a4876ee38fbe7b139cace3b30a81f8846a0ec3e93114fa82d282c`.
The primary produced final equity `$1,330.23`, net `+$330.23`, PF `1.3907`, raw PF
`1.4671`, 14.78% maximum drawdown, and 237 trades. It remained positive at 2x costs
with `+$273.65`, passed 35/35 leave-one-market-out runs, kept the largest positive
raw-profit symbol at 14.50%, and kept the top five at 57.72%.

The required temporal gate failed. Independent primary fold results were:

```text
2023 Q3  -$26.27
2023 Q4 +$275.58
2024 Q1  +$42.61
2024 Q2  -$55.99
2024 Q3  +$53.58
2024 Q4 -$135.63
```

That is 3/6 positive quarters against a frozen 4/6 requirement. The verdict is
`NO_CANDIDATE`, 9/10 gates passed. The stronger-looking slow falsification horizon
earned `+$707.07`, PF `2.0653`, and 4/6 positive folds, but it was explicitly
non-selectable and had 22.71% aggregate drawdown. It cannot replace the primary after
outcomes.

Both the fast artifact audit and a full second 62-replay deterministic audit pass.
Post-result QA then found a diagnostic-only monthly grouping defect: exact-midnight
close timestamps were assigned to the new month, producing an extra `2025-01` key.
The immutable v1 ledger was preserved. A separately tested and hash-bound 18-month
addendum corrects interval labeling under hash
`7f538ce899ca6513c109510479980602d6820397fb22e19d80334f46b036192a`; it names zero
affected gates and preserves `NO_CANDIDATE`.

The next controlled stage is a preregistered post-outcome failure analysis using only
opened development evidence. It must explain temporal instability without converting
discovered buckets into rules. Only then may Aurex decide whether a bounded R3.1 study
with explicit selection control is justified. Validation, holdout, paper, sandbox,
micro-live, and real capital remain unopened.

Before explanatory aggregation, Aurex froze an explicitly post-outcome failure-analysis
protocol under hash
`62ec8d11920cc4634f624ca7ce11fa93a7dc3bebd9871122984aff21e1da7725`. It binds the
run package, rejected result ledger, monthly addendum, development bundle, and all 62
replay hashes. Its fixed dimensions cover quarters, corrected months, cost/turnover,
diagnostic benchmark behavior, drawdown/exposure, exit reasons, horizon behavior,
positive-market breadth, and symbol contribution. It prohibits gate or verdict edits,
sealed data access, outcome-selected parameters, falsification-variant promotion,
candidate creation, and direct conversion of discovered buckets into trading rules.
Five focused protocol tests and the offline rebuild check pass.

### Goal Continuation: Frozen R3 Failure Result And R3.1 Preregistration

The post-outcome failure analysis was implemented as a second frozen transaction before
its descriptive aggregation. Package hash
`7863931e7a391f693a788339b583bf5c586a98a41424419aac0d774551cfbbdb` binds the exact
formulas, decision criteria, result path, and three source files. The one-shot result
hash is `52a766a8d0c7e586b340ee28f5900320ed74cc0c57ddab12c4c1367026b40cab`;
its deterministic rebuild passes.

The analysis preserved R3's 3/6 temporal failure. It found all three horizons positive
at base and double cost, positive-fold counts ordered 2/3/4 from fast to primary to
slow, both concentration gates passed, and leave-one-market-out positivity of 1.0.
Under the frozen all-five rule the next decision is `PROPOSE_BOUNDED_R3_1`. This creates
no candidate, changes no R3 evidence, and opens no sealed data.

R3.1 is a single-hypothesis path-quality test. It keeps the parent 84-day horizon,
14-day rebalance, 35-market universe, shared capital, ATR sizing/stops, costs, six
folds, and every absolute advancement gate. Its only signal change is ranking a
strictly positive OLS slope of log closes multiplied by regression R-squared. The
regression uses 505 completed closes spanning exactly 504 four-hour intervals.

The first protocol-freeze attempt failed honestly before any outcome: Decimal literal
fields built in memory but rejected their JSON string representations on reload. The
failed artifact was removed, exact-value checks were changed to coercion-safe Decimal
validators, and the writer now validates serialized JSON before replacing the target.
After 111 related tests and repository-wide Ruff passed, the successful protocol froze
under hash `dba4e1282533d5a93825eb1b6bd8b8e854f4146218bd70d5633f9a489b7030b5`.

R3.1 permits one selectable primary and one parameter set, so there is no best-variant
selection and no multiplicity correction. Any failed gate stops this mechanism family.
Even a complete pass creates no eligible strategy; it permits only a separately frozen
R4 candidate before one-shot 2025 validation. Validation, holdout, forward data, paper,
sandbox, live trading, and real capital remain closed.

### Goal Continuation: R3.1 Engine Freeze, One-Shot Result, And R4 Permission

The R3.1 arithmetic contract was frozen before market outcomes under execution hash
`76a0403f61f7d684761a05765c9d48d3310e56c8433779abb164d14e209773f1`.
It pins a 50-digit half-even Decimal context, 505 completed closes, x-mean 252,
Sxx 10,732,260, log-price OLS slope and intercept, clamped R-squared, and score equal
to positive slope times R-squared. Every non-signal execution rule is inherited from
the immutable R3 contract.

A separate R3.1 engine was implemented against synthetic fixtures. Tests cover exact
exponential-path recovery, degenerate constant windows, deterministic symbol
tie-breaking, recorded signal evidence, all-cash behavior when no positive path
qualifies, request/result hashes, ambient Decimal-context independence, doubled costs,
and rejection of unfrozen parameters. The parent R3 engine was not edited.

Before run-package freeze, new contract tests found a real result-ledger builder defect:
the builder omitted literal default fields from the pre-validation hash payload while
the validator included them in the canonical model dump. A real study could therefore
have completed every replay and failed at final ledger creation. The builder now
materializes every canonical default before hashing. The one-shot writer was also
hardened to roll back an already-renamed replay directory if the final ledger rename
fails, avoiding stranded half-committed evidence.

The final pre-outcome run package froze under hash
`13c1e6cc657b055f3cf957fd6e841e9bdbe8ed59ce6eee89c6f7d9b39c78d722`.
It binds transformed market data hash
`ec5e60c129d941b0f72ea39fde63a99df992efbca2c9348c7abc9d313c3c50c2`,
the Python/Pydantic runtime, every outcome-producing source file, and exactly 44
replays: three full-window cost levels, six quarterly folds, and 35
leave-one-market-out runs. Thirty-six focused R3.1 tests and repository-wide Ruff
passed before freeze; the stored package equals its authoritative rebuild.

The one-shot study completed all 44 replays and committed ledger hash
`452a79da7bc12704a2685cf70f24b8d2d9c895b7123f29d646c89809ea25dd94`.
At base costs the path-quality primary produced final equity `$1,488.79`, net
`+$488.79`, PF `1.5936`, 10.82% maximum drawdown, and 230 completed trades. It
remained positive at 1.5x costs with `+$455.93` and at 2x costs with `+$423.78`.
Maximum single-symbol and top-five gross-profit fractions were 13.00% and 44.92%.
All 35 leave-one-market-out replays were positive.

Independent quarterly fold net results were:

```text
2023 Q3   +$7.61
2023 Q4 +$273.25
2024 Q1  +$16.62
2024 Q2  -$39.48
2024 Q3  +$56.70
2024 Q4 -$129.43
```

Exactly 4/6 quarters passed the frozen temporal gate. Every other frozen gate also
passed, producing the mechanical 9/9 verdict `PERMIT_R4_PREREGISTRATION`. A fast
stored-artifact audit and a full second 44-replay deterministic audit both pass.

This verdict is deliberately narrow. The ledger sets
`creates_eligible_strategy=false` and `opens_validation_partition=false`. It permits
only a separately frozen R4 candidate and one later 2025 validation campaign. The
2023-2024 mechanism history is development-contaminated and may not be tuned again.
Validation, 2026 holdout, forward data, Pine promotion, paper, sandbox, live trading,
and real capital remain closed.

The first complete post-outcome suite run passed 489 tests and exposed two stale
pre-outcome assertions that still required the R3.1 result artifact list to be empty.
Those test-only checks now require exactly the authorized
`r31_path_quality_result_v1.json` artifact. The affected 16 tests pass, and the final
complete checkpoint passes 491 tests with the known pytest config and Starlette/httpx
warnings. Repository-wide Ruff passes.

### Goal Continuation: R4 Freeze, Untouched Validation, And Retirement

R4 preserved the accepted R3.1 path-quality mechanism without changing its signal,
84-day lookback, 14-day rebalance, shared-capital construction, ATR sizing and stop,
cost assumptions, or concentration rules. The pre-outcome candidate protocol froze
under hash
`24dd0e81b1aa441ec81e37366a88ee8a4cc65e25818dc6455dc1eb3d7dd4cdd5`.
Its all-or-nothing validation matrix contains three overall cost levels, four 2025
calendar quarters, and 35 leave-one-market-out runs.

The checksum-verified 2025 Binance Vision bundle froze under hash
`0cacd38e3fbef83d4603d1df3b287c32102b5e9d6989bf6d26d59ff420cce95e`.
It contains 73,886 actual four-hour candles across the fixed 35-market universe, 406
verified monthly archives, 14 recorded 404 responses, and no blocked dataset. Thirty-
three markets are fully continuous. FTM and MKR have contiguous terminal missing
suffixes beginning after `2025-01-13T00:00:00Z` and
`2025-09-15T00:00:00Z`, respectively.

Execution hash
`825391d45fde09c185186e103c963bf94776ce6de773500def5dcccbdf898cc0`
pins prospective market termination behavior: an unheld market is permanently removed
from ranking at its first missing bar; a held position is written off to zero without
an invented candle, exit fee, or slippage. The new R4 engine blocks leading, internal,
duplicate, or resumed gaps and records availability and active-breadth evidence.

Before source freeze, the R4 engine exactly reproduced the known continuous R3.1
primary: 230 trades, 1,400 opportunities, 3,300 equity snapshots, and net
`+$488.79400413881589814287390`. Held and unheld terminal-market behavior, absence of
synthetic candles, fixed LOMO selection, Decimal-context independence, result hashing,
and deterministic replay were tested separately.

The final run package froze under hash
`d7c734bd3f786da68c0567a2edfd8020b4ac477878e0f6f4e37fb13217bed240`
and transformed-data hash
`49011e05e0abc55b3a0c924ae08926053a784187502bf26aa1eaf42909c4bbe5`.
It binds the runtime, candidate, development and validation data, execution contract,
known-data regression receipt, exact 42-run plan, and all direct and transitive
outcome-producing source files. Before freeze, 43 R4-boundary tests, the complete
534-test project suite, and repository-wide Ruff passed. Candidate, data, execution,
and package rebuild checks all passed with no R4 result artifact present.

The one-shot campaign then committed all 42 replay artifacts and result ledger hash
`797ea50d142bbd61f22e87ff9ddf72f30b12c70940d596d027e70660ee26e626`.
The frozen verdict is `RETIRE_R4_CANDIDATE`, with 4/9 gates passed. Base-cost final
equity was `$926.17`: net `-$73.83`, PF `0.7991`, raw-price PF `0.8530`, 14.93%
maximum drawdown, and 112 trades. Double-cost net was `-$94.18`.

Independent quarter results were:

```text
2025 Q1 -$55.31
2025 Q2 -$47.61
2025 Q3 +$57.29
2025 Q4 -$71.86
```

Only 1/4 quarters was positive, and none of the 35 leave-one-market-out runs was
positive. Trade count, drawdown, single-symbol concentration, and top-five
concentration passed; base net P/L, base PF, double-cost P/L, quarterly robustness,
and LOMO robustness failed. The base campaign had zero market-termination write-offs
and at least 33 active markets at every rebalance, so delisting semantics did not cause
the failure.

Both the stored-artifact audit and a full independent second 42-replay audit pass. The
ledger explicitly sets Pine parity permission, paper eligibility, and live eligibility
to false. Under the predeclared family-stop rule, path quality cannot be rescued or
retuned, and 2025 is now outcome-contaminated for this lineage. The next permissible
research action is a separately frozen post-rejection analysis using stored evidence
only; 2026 holdout, forward data, paper, sandbox, live trading, and real capital remain
closed.

### Goal Continuation: R4 Failure Attribution And Family Stop

Before inspecting any new failure dimension, Aurex froze
`r4_failure_analysis_protocol_v1.json` under hash
`3b0578e826a1c93929f7a2515a44169ad7a9b7c7887c23774078fc91dc3c714b`.
The protocol binds all 42 R4 result artifacts and permits only predeclared
availability, drawdown/exposure, exit/holding-duration, gross/net cost, temporal,
rebalance-cohort, and symbol/LOMO attribution. It prohibits outcome-derived bucket
rules, inversion, reparameterization, candidate creation, verdict changes, and access
to 2026 or forward data.

The deterministic analysis implementation and its 13 direct/transitive source files
froze in `r4_failure_analysis_package_v1.json` under hash
`e15fdf4ee9618e1b8d5f1195aebcf3065f0c0f66fa36e788129091fa6b84e2b4`.
All 57 R4-focused tests and repository-wide Ruff pass. Both the package rebuild and
analysis audit pass.

The one-shot analysis result froze under hash
`b46b2181bf7b890f27a1ac43f6b6307bf095230cf4694c7231c5b8166bbaad4b`.
Its classification is `SIGNAL_NEGATIVE_BEFORE_MODELED_COSTS`. Raw price P/L was
`-$52.0183`, raw PF was `0.8530`, and modeled commission plus slippage added
`$21.8157`, reconciling exactly to net `-$73.8340` and PF `0.7991`.

Sixty-eight fixed-stop exits lost `-$335.78` before costs, while 44 rebalance exits
made `+$283.76` before costs. Only 1/4 quarters and 3/12 months were positive. No
leave-one-market-out run was profitable. Concentration and drawdown remained within
their frozen limits, and two expected terminal-market events caused no write-off, so
fees, missing markets, concentration, and excessive drawdown do not explain away the
failure.

All nine integrity checks pass. The final decision is
`STOP_PATH_QUALITY_FAMILY_RETURN_TO_UNRELATED_MECHANISM_DISCOVERY`. No descriptive
exit, duration, month, symbol, omission, or cohort observation may become a new rule.
The next strategy-research action must first freeze a mechanism-discovery charter for
an economically unrelated hypothesis with capped multiplicity, separated exploratory
and confirmatory evidence, realistic shared-capital execution, and a mechanical stop
rule. The 2026 holdout, forward data, Pine promotion, paper, sandbox, live trading,
and real capital remain closed.

### Goal Continuation: U1 Discovery Charter And No-Return Theory Screen

Aurex froze `u1_mechanism_discovery_charter_v1.json` under hash
`642f67fdc55fc041c010e1e7c90732e102a2214bc76c46df15d864c2d269fbcf`.
It binds the final R4 family-stop result, contamination ledger, universe manifest,
2023-2024 development bundle, and 2025 validation bundle. The charter permits no more
than three theory proposals, one return-tested mechanism, one selectable parameter
set, and one candidate.

The data progression is now stricter than the prior R4 progression. The 2023-2024
partition is development. The already handled 2025 history may serve only as internal
validation for an unrelated mechanism. January-June 2026 remains the sealed final
eligibility holdout, and evidence from `2026-07-01` remains locked forward data. A
2025 pass alone cannot create eligibility.

Before the charter froze, the new controls passed 6 focused tests and the complete
project suite passed 554 tests with the known Starlette/httpx warning. Repository-wide
Ruff passed. The stored charter then passed an authoritative rebuild against all five
bound evidence inputs.

The subsequent theory screen calculated no strategy outcome. It evaluated exactly
three premises using only primary research support, point-in-time data feasibility,
current execution fit, independence, turnover, and model complexity:

- volatility-managed broad spot market beta;
- cross-sectional signed-jump risk premium;
- delta-neutral spot-perpetual funding carry.

The screen selected `P01_VOLATILITY_MANAGED_BROAD_SPOT_BETA` for primary protocol
design. It is the only proposal reproducible with current OHLCV and expressible through
current long-only spot mechanics without leverage. Signed-jump risk is deferred
because four-hour candles cannot reproduce its high-frequency defining statistic.
Funding carry is deferred because Aurex lacks point-in-time funding, basis, collateral,
and liquidation data plus a qualified derivatives execution and reconciliation path.

The no-return screen froze under hash
`0d32405ea4eea989ee93b74b2f393d5e988cf9eadb63cbde78cc652996eab745`.
All 60 combined U1/R4 boundary tests, repository-wide Ruff, and the deterministic
screen rebuild pass. The screen creates no candidate and authorizes no validation,
holdout, Pine, paper, sandbox, live trading, or capital.

### Goal Continuation: U1 Frozen Development Falsification

Aurex froze one `volatility_managed_broad_spot_beta_v1` primary with a static
equal-weight benchmark. The protocol fixes a 28-day realized-variance window, 60%
annualized volatility target, unlevered inverse-variance exposure capped at one,
28-day full rotation, 35-market equal weighting, realistic fee/slippage stress,
eight independent temporal folds, 35 leave-one-market-out runs, and all-or-nothing
risk, profitability, robustness, benchmark, concentration, and audit gates.

The protocol and execution specification froze under hashes
`3d8b335cfcee93be9e104e7bc029ea09f08e77cd39861afa8743548c245bb229`
and `220e9eca631e554833b9c063cdf960fd7b209a70b545324ca40554e2dcf460d0`.
The deterministic engine was verified using synthetic data only. Before any
development return was calculated, 591 complete project tests passed with one known
Starlette/httpx warning and repository-wide Ruff passed.

The source/runtime/data package then froze under hash
`fd6a1bd0a4faf4b8a65a650e41d69050f7d870d33dfcc29d9ce89d170bcd78b2`.
It binds transformed market-data hash
`4a41ccae12a88ad81f3f6aa45f6d5feb19947ef5f7f211443c00c1e010c02f00`
and exactly 47 runs: three primary cost levels, one benchmark, eight folds, and
35 leave-one-market-out replays. An authoritative `--check` rebuilt the package
exactly before execution.

The one-shot study completed all 47 runs and immediately replay-audited each one.
The committed ledger froze under hash
`06045816415f3fb270ed11bc8e9e3bbeab9382dfc886990e2e4297a5d9217669`.
Both stored-artifact audit and an independent full deterministic replay audit pass.

The primary earned `+$2,168.47` from `$1,000`, PF `1.9311`, raw PF `1.9815`, and
875 completed trades. It remained positive at double modeled costs with
`+$1,993.50`; all 35 leave-one-market-out runs were positive; concentration gates
passed. Against the static benchmark, realized equity volatility fell from 0.7448
to 0.5654, maximum drawdown fell from 62.11% to 44.58%, and return-to-drawdown
improved from 0.7213 to 2.0023.

U1 nevertheless failed two mandatory gates. Maximum drawdown was 44.58% against a
20% ceiling, and only 4/8 temporal folds were profitable against a required 6/8.
The deterministic verdict is `STOP_VOLATILITY_MANAGED_BROAD_SPOT_BETA`, with
11/13 gates passed. No rescue target, lookback, rebalance interval, basket, exposure
transform, or relaxed gate is allowed. U1 may not open 2025 and creates no strategy,
Pine, paper, sandbox, live, or capital permission.

### Goal Continuation: V2 No-Return Capability Audit

After preserving the U1 stop, Aurex audited the local foundation required for a
separate lower-directional-risk lineage. The audit binds the U1 result, U1 theory
screen, universe, contamination ledger, current Aurex execution and broker source,
and the relevant My-Krypt-Trader source snapshot.

Only audited spot OHLCV is ready. Eleven capabilities are absent or intentionally
disabled: historical perpetual funding; mark/index and point-in-time basis data;
historical contract and fee metadata; funding settlement; paired spot/perpetual
execution; collateral and margin state; liquidation and ADL; paired reconciliation;
and a production derivatives adapter. My-Krypt-Trader supplies no derivatives
foundation.

Official Binance documentation and archive indexes expose public USD-M funding,
futures-kline, mark-price, index-price, premium-index, basis, contract, position-risk,
ADL, and insurance-fund surfaces. The audit treats this as acquisition feasibility,
not completeness, executable carry, or profit evidence.

The capability audit froze at
`data/evidence/v2_capability_audit_v1.json` under hash
`3726b944529990be7160604942f4e580cd8d198efe79f8e074dc72b760638e42`.
Its decision is
`BUILD_RESEARCH_ONLY_DERIVATIVES_FOUNDATION_BEFORE_NEW_CHARTER`.
Four focused tests, Ruff, and the deterministic rebuild pass. It authorizes only
data-contract design: zero mechanisms selected, zero return tests, zero new market
data imported, and no candidate, validation, holdout, paper, or live permission.

### Goal Continuation: Frozen V2 Metadata-Only Source Census

Before downloading any derivatives payload, Aurex froze an official-archive census
contract across the existing 35 decision symbols, January 2023 through December 2024,
and six required families: one-minute spot klines, one-minute USD-M contract klines,
funding events, and one-minute mark, index, and premium-index klines.

The contract requires exactly 5,040 checksum checks. It permits only URL, HTTP,
checksum, content-length, last-modified, and checked-at metadata. Archive payload
downloads, numeric price or funding inspection, market-data import, mechanism
selection, candidate creation, and return calculation remain prohibited. Missing
archives must be preserved without substitute symbols or a shorter window.

At least 20 symbols must have all six families for all 24 months before a separate
payload-acquisition protocol may be designed. The contract froze at
`data/evidence/v2_derivatives_source_census_contract_v1.json` under hash
`7502a7eb6a54089d90bfc40889390f8c6ac18bbe55d18ef4122421e7fa18e0dc`.
Four focused contract tests, eight combined V2 boundary tests, repository-wide Ruff,
and the deterministic rebuild pass.

### Goal Continuation: V2 Census Result And Bounded Acquisition Pilot

The metadata-only runner completed every frozen request against the official Binance
archive. Its transactional first attempt was correctly rolled back when the local
sandbox denied socket access; no partial artifact was written. The authorized rerun
completed 5,040/5,040 observations and froze
`data/evidence/v2_derivatives_source_census_result_v1.json` under hash
`ce5d60e3338903bcb8a3783bd4b41fa63bec518c3041b213c9529bd6458d652e`.

The result records 4,790 valid checksum files and 250 `404` observations, with no
unresolved request. Thirty-one symbols are complete across all six families and all
24 months. CFXUSDT, LUNCUSDT, SHIBUSDT, and STXUSDT remain incomplete. Spot has
840/840 observations; each USD-M family has 790 present and 50 missing. No archive
payload was requested and no numeric market data, return, signal, or strategy outcome
was inspected. The mechanical decision is
`PERMIT_SEPARATE_V2_DATA_ACQUISITION_PROTOCOL`.

Aurex then froze a resource/schema pilot before touching any archive payload. The
pilot selects AAVEUSDT, FTMUSDT, and XRPUSDT as first/median/last complete symbols,
and 2023-01, 2024-01, and 2024-12 as first/middle/last months. Across all six
families, this creates exactly 54 targets. Every target pins the checksum observed by
the census so Binance archive revisions cannot silently alter future evidence.

The pilot protocol is
`data/evidence/v2_derivatives_acquisition_protocol_v1.json` under hash
`aa88b2ff6add0637b889da27b784cd1a26b1addc4590832c9c51e973e2aaebc5`.
It caps total compressed bytes at 4 GiB and uncompressed bytes at 16 GiB, requires
content-length and free-disk preflight, uses transactional `.part` downloads,
verifies SHA-256 before rename, blocks unsafe ZIP structure, and permits only
structural schema/timestamp inspection. It does not authorize full acquisition,
market-data import, returns, mechanism selection, a candidate, paper, sandbox, or
live trading.

Ten source-census runner tests, five acquisition-protocol tests, all 23 combined V2
boundary tests, repository-wide Ruff, census result audit, and deterministic protocol
rebuild pass. The next work is the exact 54-target transactional pilot plus the
independent synthetic derivatives execution/risk foundation.

### Goal Continuation: V2 Pilot Execution And Structural Qualification

The pilot runner froze before payload execution through its protocol and source hash.
Its preflight-only pass refreshed every checksum, obtained all 54 archive content
lengths, and calculated an aggregate 53,398,035-byte transfer against approximately
95 GiB free disk. No ZIP was downloaded during that preflight.

The bounded run repeated preflight, downloaded only the 54 authorized targets, wrote
each transfer to `.part`, verified census checksum, refreshed checksum, content
length, and archive SHA-256 before rename, then inspected each ZIP and CSV
structurally. No stale `.part` remains.

The immutable result is
`data/evidence/v2_derivatives_pilot_acquisition_result_v1.json` under hash
`95e9aaaf1b05b01372ddcdc3f19fff6612f6a7f5ae4e1ca4b99b0eb6e7947874`.
The pilot contains 53,398,035 compressed bytes, 198,582,854 uncompressed bytes, and
2,009,637 rows. Each of the five kline families has 401,760 rows; the funding family
has 837 events. All 54 archives use millisecond timestamps, strict ordering, unique
timestamps, finite numeric fields, and exact target-month containment.

The observed schema classes match the pre-run implementation: nine headerless spot
kline archives, 36 standard 12-column futures-kline archives, and nine funding-event
archives headed `calc_time,funding_interval_hours,last_funding_rate`. The decision is
`PERMIT_SEPARATE_FULL_V2_ARCHIVE_ACQUISITION_PROTOCOL`, but the result explicitly
keeps full download, market-data import, returns, mechanism selection, candidate,
paper, sandbox, and live permissions false.

Seven focused pilot-runner tests, all 30 combined V2 boundary tests, repository-wide
Ruff, local archive/hash audit, and deterministic result rebuild pass. The next
foundation is synthetic paired execution, funding settlement, fees, collateral,
margin, liquidation/ADL, partial-fill rollback, kill switches, and reconciliation.

### Goal Continuation: V2 Synthetic Derivatives Foundation

Aurex froze the arithmetic and state-transition contract before implementing a V2
mechanism. The protocol fixes Decimal precision; long-spot/short-USD-M position and
cash semantics; signed funding; fees; equity and collateral; initial and maintenance
margin; liquidation and ADL; hedge tolerance; partial fills; timeouts; rollback;
duplicate-event idempotency; reduce-only flattening; kill switches; reconciliation;
and 14 exact synthetic scenarios.

The protocol froze at
`data/evidence/v2_derivatives_foundation_protocol_v1.json` under hash
`b7709efb8555611b9041afc0cb030259c2355c1c82a76c8e22cd6b26a6767c4b`.
The engine and deterministic result then froze under result hash
`8cf54efc7989b1370db4be80267b47a763637285a1e66d503093f9fe15a49fe8`.

All 14 scenarios passed. The suite covers a complete open/funding/close/reconcile
lifecycle, partial first-leg fill with second-leg rejection and rollback, duplicate
fills and funding, timeout/cancel, pretrade margin rejection, maintenance breach and
liquidation, ADL and forced flatten, position and fee drift, kill-switch opening
blocks, asymmetric partial fills, negative funding paid by the short, and partial
close without residue. Hash-chained events and corrected final reconciliation pass.

The result decision is `PERMIT_SEPARATE_V2_NO_RETURN_DISCOVERY_CHARTER`. This proves
only internal synthetic mechanics. It uses no real market data and provides no
evidence of exchange behavior, mechanism edge, profitability, candidate eligibility,
paper readiness, sandbox readiness, or live readiness.

### Goal Continuation: V2 No-Return Discovery And Theory Screen

After the synthetic foundation passed, Aurex froze a separate discovery charter under
hash `af4dd3e28e20f9a5e99c47e98d567587ef11697c38dd976074ddcb80255db07f`.
It permits exactly three theory proposals, at most one selected primary, zero
return-tested mechanisms, and zero parameter sets. The development partition remains
closed pending a full-acquisition protocol; 2025 and 2026 remain sealed and forward
evidence remains locked.

The screen used official Binance funding and API documentation, one peer-reviewed
perpetual-pricing article, and institutional perpetual-futures and basis-risk working
papers. It did not inspect an Aurex numeric market field, define a parameter, calculate
a return, or read a strategy outcome.

Three premises were screened:

- `P01_POSITIVE_FUNDING_SPOT_PERP_CARRY`: selected for full-data and protocol design
  because long cash-funded spot paired with a same-quantity short USD-M perpetual
  fits the audited synthetic direction without spot borrowing.
- `P02_PREMIUM_CONVERGENCE_SPOT_PERP_BASIS`: retained only as a nonselectable related
  diagnostic because it overlaps P01 and no perpetual expiry forces convergence.
- `P03_NEGATIVE_FUNDING_REVERSE_CARRY`: rejected under V2 because point-in-time spot
  borrow availability, rates, limits, recalls, repayment state, and reverse-pair
  execution are not qualified.

The immutable screen is
`data/evidence/v2_mechanism_theory_screen_v1.json` under hash
`ec03d31db661a36b1def820711b20134d416ec2d390a49cdbafaf19f27758dea`.
Its decision is `FREEZE_ONE_PRIMARY_FOR_FULL_DATA_AND_PROTOCOL_DESIGN`. Six focused
tamper/boundary tests, focused Ruff, and deterministic rebuild pass. The screen
authorizes no full download, data import, return test, candidate, development,
validation, holdout, forward paper, sandbox, live trading, or capital.

After the checkpoint documentation was reconciled, all 55 combined V2 boundary tests,
repository-wide Ruff, and the complete 646-test project suite passed. The only warning
is the existing Starlette/httpx test-client deprecation. No TradingView state, sealed
partition, API runtime, exchange path, or live control was changed.

### 2026-07-31 - Binance Percentage-Price Fail-Closed Correction

The corrected virtual-cancel retry stopped at Binance's non-mutating `order/test`
with `Filter failure: PERCENT_PRICE_BY_SIDE`; no new order entered the matching
engine. Aurex had placed its BUY exactly at 50% of the last ticker even though
Binance applies that boundary to a moving 5-minute average.

The Testnet client now parses BUY and SELL percentage multipliers and the required
average-price window, checks the matching average, reads the current best bid, and
constructs a bounded BUY with margin inside the band and below the bid. Dynamic
filters are revalidated before signed test and actual Testnet submission. A
credential-free live preflight produced a `$5.2134075` candidate at `57926.75`
against a `64363.06` bid and recorded `submitted=false`.

The 22 focused Testnet, evidence, API, and dashboard tests pass, including a
regression for the exact moving-boundary failure. Repository-wide Ruff and
`git diff --check` pass. The complete-suite rerun reached 62% without a failure
before the 10-minute harness timeout and is not claimed as a complete pass. The
authenticated corrected lifecycle has not run, sandbox qualification remains false,
and production/live authority remains absent.

The next authenticated run passed the signed test, placed and cancelled the bounded
order, then failed during final reconciliation because Aurex queried the
cancellation-operation client ID as an order's `origClientOrderId`. Binance rejected
that lookup with `Order does not exist`. The final lookup now uses the immutable
numeric `orderId` returned by cancellation; placement and cancellation client IDs
remain independently checked in the responses. The exact regression asserts an
`orderId` lookup with no `origClientOrderId`. Sanitized lifecycle state is now
atomically persisted at every step, and a post-cancel failure neither loses the
cancel result nor attempts a redundant second cancellation. All 23 focused tests
plus repository-wide Ruff pass. No complete lifecycle artifact was written and
sandbox qualification remains false.

The complete `2026-07-31T06:52:01.244550+00:00` checkpoint then established the
actual REST identity contract. Placement, pre-cancel query, and final query returned
the original placement client ID; only the cancel response returned the deterministic
cancel-operation ID together with `origClientOrderId`. External order `22292295`
remained stable, all quantities matched, executed quantity remained zero, and the
final status was `CANCELED`.

The untouched source was preserved under SHA-256
`d4a4f6a6be8ab72b2ad4424ee7fcd283dc0f69c66ad381a213077643d57123a6`.
An offline, provenance-bound reconciliation addendum under SHA-256
`8ba2a284ddea8f8c32b7cc420fbe0d80da861e5263d52a28e0114ee799a41e06`
returns every v2 predicate true and decision `VIRTUAL_CANCEL_RECONCILED`. No network
request or new order was used for reinterpretation. The API derives status from the
recorded checkpoints rather than trusting the stale declared `FAIL`; 25 focused
tests and repository-wide Ruff pass. The virtual-cancel gate is complete. Full
sandbox qualification, production, and live authority remain false.

### Binance Spot Testnet Phase 2B Contract And Code Readiness

On `2026-07-31`, Aurex froze the separate Phase 2B fill, fee, and balance
reconciliation contract at
`data/evidence/binance_spot_testnet_fill_fee_contract_v1.json`, SHA-256
`8eddafafb5db47fa218c993476f5e6ae4cf13a4f4894d671c89321953e8719cd`.
It binds one `6.50 USDT` Testnet market BUY, a campaign-acquired BTC market SELL,
the `$10` per-order cap, the `$0.50` round-trip USDT-loss cap, deterministic IDs,
partial-fill handling, at most one valid cleanup, no blind retry after an ambiguous
outcome, and exact order/trade/commission/balance gates.

The fixed-Testnet adapter now parses market filters, exposes sanitized balances,
supports separately disabled market test/entry methods, reads account trades, and
preserves original quote quantity. The campaign runner persists every checkpoint,
refuses evidence overwrite, and records filter-blocked cleanup instead of forcing an
invalid order. The read-only status verifier reconstructs trade totals and
before/after asset deltas rather than trusting stored pass fields. The Operator view
shows contract and fill-reconciliation state.

The scoped Testnet, API, profile, and dashboard suite passes 41 tests, repository
Ruff passes, frontend JavaScript syntax passes, and the frozen contract independently
rechecks. No genuine Testnet fill has been sent by this implementation checkpoint.
Phase 2B, whole-sandbox qualification, production, live trading, strategy
eligibility, and profit remain unproven.

The operator then executed the one acknowledged Phase 2B campaign at
`2026-07-31T09:10:50.791755+00:00`. BUY order `22331495` filled
`0.00010000 BTC` for `6.38180000 USDT`; SELL order `22331518` filled the same
base quantity for `6.38179900 USDT`. The matching account-trade records exactly
equal both order totals. BTC and USDT commissions were both zero, BTC returned to
its initial `1.00000000` total, and expected and observed USDT deltas both equal
`-0.00000100`. No cleanup order was used.

The canonical source is preserved byte-for-byte at
`data/evidence/binance_spot_testnet_fill_fee_20260731T091050Z.json` with SHA-256
`9a8876188432292bb27842956287881bf5fc170fa3164e07a97ebc8604ce3e51`.
The independently reproducible audit is preserved at
`data/evidence/binance_spot_testnet_fill_fee_audit_20260731T091050Z.json` with
audit SHA-256
`720e5a00ac9c97fba284420054e0f5b88751cd82cac52440402edf4d2dfc8251`
and decision `PHASE_2B_FILL_FEE_RECONCILED`. Phase 2B is complete. Whole-sandbox
qualification, production, live trading, strategy eligibility, and profit remain
false pending Phase 2C and later gates.

### Binance Spot Testnet Phase 2C Contract And Code Readiness

On `2026-07-31`, Aurex froze the Phase 2C user-data stream contract at
`data/evidence/binance_spot_testnet_user_stream_contract_v1.json`, SHA-256
`ddf06d9d596812c9dcb45c4c6654e8e50a0b5a3ae2928b15fdbf487fad2f8c2d`.
The contract uses Binance's current
`wss://ws-api.testnet.binance.vision/ws-api/v3` endpoint and
`userDataStream.subscribe.signature`; it does not rely on the retired REST
listen-key workflow.

The fixed-origin client signs subscriptions with the process-only HMAC key, parses
typed `executionReport` and `outboundAccountPosition` events, hashes complete event
wrappers, suppresses duplicates across connections, rejects unexpected response and
subscription identities, and supports explicit unsubscribe and teardown. The
bounded runner places at most two resting BUY orders below the current bid and under
the `$10` cap. It deliberately disconnects before cancelling the first, establishes
a fresh subscription, recovers the missed cancellation through REST, then requires
the second order's connected `NEW` and `CANCELED` events to match REST exactly.
Empty trade ledgers, zero execution, a matching final USDT event, exact initial/final
BTC and USDT balances, and unambiguous cleanup are mandatory.

The independent evidence reader reconstructs order, event, account, and safety
predicates instead of trusting the runner's pass fields. Synthetic success,
credential-redaction, malformed-message, duplicate, identity-drift, and
balance-drift paths pass. The API and Operator view now expose the frozen contract
and reconnect-recovery state. No genuine Phase 2C campaign has run, no Phase 2C
order has been submitted, and whole-sandbox qualification, production, live
trading, strategy eligibility, and profit remain false.

The operator then executed the one acknowledged Phase 2C campaign at
`2026-07-31T10:00:23.441972+00:00`. Order `22344038` emitted a matching streamed
`NEW` report, was cancelled during the deliberate disconnection, and was recovered
as `CANCELED` through REST with zero execution and an empty trade ledger. After a
fresh signature subscription, order `22344082` emitted matching `NEW` and
`CANCELED` reports and also retained zero execution and an empty trade ledger.

Five unique user-data events were retained: three execution reports and two account
positions. The final account-position event exactly matches REST. BTC remained
`1.00000000`; USDT remained `9999.99999900`; both locked balances returned to zero.
No duplicate was observed, no fill occurred, and no cleanup was needed.

The canonical source is preserved byte-for-byte at
`data/evidence/binance_spot_testnet_user_stream_20260731T100023Z.json` with SHA-256
`e5bc1e5402f49a07c5fc3389259025e30e9fee1ee6a525389e8e01aee7ba333e`.
The independently reproducible audit is preserved at
`data/evidence/binance_spot_testnet_user_stream_audit_20260731T100023Z.json` with
audit SHA-256
`70cd169d2716a2beac17c2f4a3cca53146b1c96f490b065830d7f774e9059038`
and decision `PHASE_2C_USER_STREAM_RECONCILED`. Phase 2C is complete. Whole-sandbox
qualification, production, live trading, strategy eligibility, and profit remain
false pending Phase 2D and later gates.

### Binance Spot Testnet Phase 2D Contract And Code Readiness

On `2026-07-31`, Aurex froze the Phase 2D restart, idempotency, kill-stop, reset,
and duration-soak contract at
`data/evidence/binance_spot_testnet_restart_soak_contract_v1.json`, SHA-256
`5e5f1f22a014fa087c44a13341f862fe6d64ea441db280fabae677bf2af820d8`.
The contract permits one resting Testnet BUY capped at `$10`, requires three
distinct operating-system processes, and keeps production, live, real-capital, and
strategy authority false.

The fixed Testnet REST client now exposes a typed, symbol-bound authenticated
`GET /api/v3/openOrders` census. The prepare stage requires that census to be empty,
atomically persists deterministic intent before the sole placement request, and
exits with the order deliberately resting. The recovery stage loads hash-verified
durable state, requires exactly one matching exchange order, resolves it without a
duplicate POST, persists the kill-stop before cancellation, proves a second entry
is blocked locally, and requires exact canceled identity, zero execution, an empty
trade ledger, no open order, and exact BTC/USDT balance restoration.

The soak stage runs in a third process with the kill-stop still enabled for 600
seconds. It requires at least 120 REST heartbeats, 20 authenticated account/order
reconciliations, two forced WebSocket reconnections, and three signature
subscriptions. The known canceled order must remain queryable. Binance error
`-2013`, account drift, changed execution state, or an unexpected open order
invalidates the run as a possible Testnet reset or external mutation; Aurex never
recreates the missing order. Binance's current Testnet documentation confirms that
all order data is periodically erased approximately monthly without advance
notice.

Durable-state tampering, duplicate submission, kill-stop behavior, exact recovery,
simulated exchange reset, the complete ten-minute contract under a fake clock,
independent evidence reconstruction, the read-only status API, and dashboard
presentation pass 35 focused tests. The complete repository suite passes 965 tests
in 635.60 seconds, repository Ruff passes, frontend JavaScript syntax passes, the
frozen contract reproduces, and `git diff --check` passes with line-ending warnings
only. At this code-readiness checkpoint, no genuine Phase 2D order or soak had run.

The next operator action at that checkpoint was exactly one guarded campaign:

`powershell -NoProfile -ExecutionPolicy Bypass -File
.\scripts\run_binance_spot_testnet_restart_soak.ps1`

The operator must leave the terminal open for slightly more than ten minutes and
must preserve durable state after any failure rather than rerun. Until genuine
source preservation and an independent audit pass, Binance adapter sandbox
qualification, production, live trading, strategy eligibility, and profit remain
false.

The operator then executed the one acknowledged Phase 2D campaign. Prepare process
`656` submitted external order `22377060` exactly once and exited with the order
resting. Recovery process `48024` found the same order in the authenticated
open-order census, resolved it idempotently without another placement request,
persisted the kill-stop, canceled the order, and proved a separate order entry was
blocked locally. Soak process `57776` retained the kill-stop for
`602.765999999945` seconds.

Final order state is `CANCELED` with zero executed quantity, zero cumulative quote,
and an empty trade ledger. No open order remained. BTC stayed at `1.00000000` and
USDT stayed at `9999.99999900`, with both locked balances at zero. The soak recorded
120 REST heartbeats, 21 authenticated order/account reconciliations, two forced
WebSocket reconnects, and three valid signature subscriptions. No exchange reset,
state invalidation, failed gate, credential persistence, or cleanup uncertainty
occurred.

The canonical source was preserved byte-for-byte at
`data/evidence/binance_spot_testnet_restart_soak_20260731T125305Z.json` with
SHA-256
`8481e2da91fd8810f41ebeffdb9dca65f6b6da2e2e678bae0ef92e05e3036e50`.
The independently reproducible audit is preserved at
`data/evidence/binance_spot_testnet_restart_soak_audit_20260731T125305Z.json`
with audit-record SHA-256
`0a9a62be2946516be924ffbbe7d1221363de30f648044c363e6c6224b06cfc29`
and decision `BINANCE_SPOT_TESTNET_ADAPTER_QUALIFIED`.

Phase 2 is complete and the Binance Spot Testnet execution adapter is
sandbox-qualified. This still does not qualify a strategy, authorize production or
live execution, authorize real capital, establish positive expectancy, or prove
profit.

### Jam Reversal Spot V1 Historical Decision

On `2026-07-31`, Aurex resumed strategy evidence after qualifying the Binance Spot
Testnet adapter. The operator selected Aurex Jam Reversal. The existing
`jam_reversal_v1` v1.14.0 source and 2026 TradingView observations remained
quarantined because repeated outcome-conditioned tuning and a seven-trade sample
could not establish edge.

Aurex created `jam_reversal_spot_v1` as a separately identified descendant before
opening earlier returns. It is long-only because the qualified adapter is Binance
Spot, restricts operation to BTCUSDT 15m, uses `$100` initial capital and `1x`,
models `0.10%` commission per side, and uses the prior confirmed one-hour EMA so
realtime and reloaded history share stable higher-timeframe inputs. Parent signal,
confirmation, stop, target, and management settings otherwise remained frozen.

Two preregistration defects were caught before any return was opened. The v1.0.0
protocol retained a developing-hour higher-timeframe risk. The first v1.0.1 protocol
included January warmup in `data_start`, which evaluator v1.2 would not bind to the
February trading start. Both immutable protocols were preserved unrun. The
authoritative v1.0.1 protocol
`f788795a-ac75-4763-93c2-75a031ee2c70`, hash
`219d6d069e678f23d3dc49588bc21a5eda9c21970ef83f5fdcb7610d1083bbda`,
was committed at `2026-07-31T18:24:22.241923Z` with no prior outcome and zero
inspected outcome fields.

The new deterministic reference engine reproduces the Pine-ordered long path:
Wilder ATR/DMI, confirmed higher-timeframe EMA context, two-candle Jam recognition,
pending breakout confirmation, cost-aware sizing, close-fill entry, dynamic
breakeven and ATR trailing stops, midpoint/pullback/time exits, commission,
slippage, and stop-first intrabar ambiguity. Synthetic engine, idempotency, audit,
source, and preregistration coverage passes 35 focused tests.

The immutable real-data replay then opened BTCUSDT 15m from
`2023-02-01T00:00:00Z` through `2026-01-01T00:00:00Z` exactly once. Replay
`82e5ff23-a4de-423b-b8df-6394d09566a1` and validation
`6ad2fef6-ffd3-4773-9f02-52e80596bdd4` both audit `PASS`. The result was:

- 14 trades, 5 wins, 9 losses;
- net P/L `-$0.5371308518` on `$100`;
- PF `0.8301176115`;
- expectancy `-$0.0383664894`;
- maximum drawdown `$2.2222264237`;
- OOS 4 trades, `-$0.2928541667`, PF `0.6770872775`;
- 0 of 6 passing walk-forward folds.

The zero-cost fixed path earned `+$1.2642` at PF `1.6461`, but base fees were
`$1.8008`; half-cost PF was only `1.1421`. Six exits were small pullback failures,
and every fold lacked the frozen minimum sample. The candidate failed eight gates
and received `REJECT_CURRENT_VERSION`.

The complete decision is preserved at
`data/evidence/jam_reversal_spot_v1_1.0.1_historical_decision.json`, artifact
evidence hash
`d8b108df43a82b3bb5db0cdffd3ec94992e9baf43fede05bbd01dd518a03c5fd`.
The original six-record contamination ledger v1 remains byte-stable in meaning and
hash-stable at
`9f7face6a22a51b2a0b20d653561396fb6415f532ad0fecd883b3c6e6c132207`.
The opened Jam period is recorded in append-only ledger v2 under hash
`f24cc36011e9f9ddc40e277197bd3fa03310cac12b6848b30714aae26cdb37bd`.
This prevents a new result from invalidating historical research charters bound to
the v1 hash.

The bounded failure analysis then rebuilt only from the stored decision and ledger
evidence. It opened no return and chose no rescue parameter. Artifact
`data/evidence/jam_reversal_spot_v1_1.0.1_failure_analysis.json`, hash
`7507c5cdf5fb1ac1a564c6c583423e316c5f06b9f284f16a3d710858c69d2ed4`,
classifies v1.0.1 as
`INSUFFICIENT_SAMPLE_AND_FEE_FRAGILE_NON_DURABLE_EDGE`. Its decision is
`STOP_CURRENT_VERSION_AND_RETURN_TO_PREREGISTERED_HYPOTHESIS_DESIGN`.

Version v1.0.1 remains disabled and has no retuning, new-candidate, parity, paper,
Testnet strategy-order, production, live, real-capital, or profit authority.

Final closeout verification passed all `982` Aurex tests in `769.45` seconds and
repository-wide Ruff. The two emitted warnings are the existing pytest `cache_dir`
configuration warning and Starlette/httpx deprecation. Both contamination ledgers
and the Jam failure-analysis artifact independently rebuild and audit.

### Jam Successor Mechanism-First Charter

On `2026-08-01`, Aurex completed the next permitted Jam stage without opening market
payloads or returns. Four mechanism proposals were evaluated against the retired
result, BTCUSDT-only Spot scope, zero-dollar data budget, observable historical
inputs, conservative execution, and external market-microstructure research.

The charter rejected loosening the candle strategy because that would be
outcome-conditioned parameter rescue. It rejected passive-maker retest execution
because official zero-cost history cannot identify queue position, missed fills, or
adverse selection. It deferred the academically motivated lower-activity cross-asset
reversal because the operator profile permits BTCUSDT only.

The sole proposal selected for future capability review is
`J2-P01-AGGRESSIVE-SELL-FLOW-EXHAUSTION-RECLAIM`. Its falsifiable hypothesis is that
a temporary aggressive sell-flow shock may partially reverse only after signed sell
pressure decays and BTCUSDT reclaims a pre-shock reference. Official Binance spot
aggregate trades can expose price, quantity, timestamp, and buyer-maker identity.
One-minute klines may provide reconciliation. No threshold, feature implementation,
or profitability claim has been made.

This mechanism is not exactly Pine-compatible because Pine does not expose Binance
aggregate-trade aggressor identity. A future qualified implementation would use the
Aurex backend as signal authority. Pine may only visualize; a candle proxy cannot be
treated as parity.

The frozen artifact is
`data/evidence/jam_successor_hypothesis_charter_v1.json`, evidence hash
`426e1f6eceb62f24e6c30d23d5848cc92f05260fa0b56cd65c8c737775642019`.
It binds the Jam failure analysis, contamination ledger v2, Testnet sandbox profile,
Phase 2 source and audit file identities, research sources, proposal register,
evidence map, and feasibility gates. Its independent rebuild passes.

The provisional 2019-2022 BTCUSDT aggregate-trade and one-minute-kline pool remains
unopened and unverified. August 1, 2026 onward remains locked forward evidence. The
charter creates no strategy and authorizes no market-data import, parameter
definition, return testing, candidate, paper campaign, Testnet strategy order,
production, live execution, real capital, or profit.

The first full-suite closeout process was interrupted by the desktop runner before
completion and left no Python process running. The clean resumed run passed all
`989` tests in `645.14` seconds. Repository-wide Ruff and the independent charter
rebuild also pass. The only warnings are the existing pytest `cache_dir`
configuration warning and Starlette/httpx deprecation.

### Jam Archive Metadata Census

On `2026-08-01`, the user explicitly authorized the next charter gate:
metadata-only official Binance archive census. Aurex first froze contract
`3670f121f303bf39a17dbc7b057bde913e30252687139046ae4785269f4e8302`,
binding exactly 96 BTCUSDT spot monthly checksum URLs across aggregate trades and
one-minute klines for January 2019 through December 2022.

The runner rejected redirects and ZIP signatures, capped each response at 4,096
bytes, checkpointed every completed observation, and requested checksum text only.
All 96 targets were present on the first attempt: 48 aggregate-trade months and 48
one-minute-kline months. Total checksum-text transfer was 8,785 bytes. Archive HEAD
requests, archive payload requests, archive payload bytes, redirects, market values,
features, parameters, returns, strategy executions, and orders were all zero.

The result is
`data/evidence/jam_archive_metadata_census_result_v1.json`, evidence hash
`e673175638469d2b0d6133678b9749742c361981703cd89bd4f271ab06a0451e`.
The independent audit is
`data/evidence/jam_archive_metadata_census_audit_v1.json`, evidence hash
`3f57bd2fb843059606bf32a284db0cc15e58c436115a922073b0c862aaaabfcb`;
the result-file SHA-256 is
`5a998bc2ff7b778c7c6052a297114d0d490314bff1d47b779d24abf46aeb5102`.

Decision:
`PASS_METADATA_COVERAGE_AWAIT_SEPARATE_PAYLOAD_PILOT_AUTHORIZATION`.
This proves publication coverage only. It creates no candidate or trading authority.
The exact next gate is
`AUTHORIZE_FROZEN_ONE_MONTH_ARCHIVE_PAYLOAD_PILOT`; no ZIP payload may be acquired
before that separate authorization and pre-network protocol freeze.

Closeout verification passed the 22-test focused charter/census suite,
repository-wide Ruff, the reproducible contract/result/audit checks, and all `1004`
Aurex tests in `354.13` seconds. The only warnings were the existing pytest
`cache_dir` configuration warning and Starlette/httpx deprecation.

### Jam One-Month Archive Payload Pilot

On `2026-08-01`, the user explicitly authorized the frozen one-month archive
payload pilot. Aurex selected January 2019 by the earliest-unused-month rule before
opening payloads and froze protocol
`1e9a6ef48ac06353f933d21cb193bf0b1489f03f79e6a4562062a0ddddbba24e`.

The run made one HEAD and one GET for each of two exact official Binance archives.
No retry or redirect occurred. Aggregate-trade compressed size was 93,204,261 bytes
and kline compressed size was 2,120,781 bytes. Both observed SHA-256 hashes matched
their published census hashes.

ZIP safety, exact single-member identity, CRC, schema, timestamp, ordering,
duplicate, and gap checks passed. The aggregate source contained 5,989,468 rows
covering all 44,640 minutes with zero aggregate-ID or raw-trade-span gaps. The kline
source contained exactly 44,640 aligned rows with no gaps or duplicates.

For every minute, Aurex reconstructed raw-trade count, OHLC, base volume, quote
volume, taker-buy base volume, and taker-buy quote volume from aggregate trades.
All seven frozen cross-family mismatch counts were zero at decimal tolerance
`0.00000001`.

Result
`data/evidence/jam_archive_payload_pilot_result_v1.json` has evidence hash
`f205b1042681bd5bcab901773a4b04c496e6cfab3946913bc6d91940550fc974`.
The independent raw-file rebuild has audit hash
`bc8880252f50215be1fbb46803e1325d5e40c2b34101ad02bad0d4284ad710bf`;
the result-file SHA-256 is
`ce63c4a89e1281bbf7e95b16e3412b9e7142a09d005bb59ad5191ae4f8420f7f`.

Decision:
`PASS_ONE_MONTH_DATA_CAPABILITY_AWAIT_FULL_ACQUISITION_AUTHORIZATION`.
No feature, parameter, return, candidate, paper, Testnet strategy-order,
production, live, capital, or profit authority was created. The exact next gate is
`AUTHORIZE_FROZEN_2019_2022_ARCHIVE_ACQUISITION`.

Closeout verification passed the 35-test Jam charter/census/payload lineage suite,
repository-wide Ruff, all reproducible protocol/result/audit checks, and all `1017`
Aurex tests in `556.17` seconds. The only warnings were the existing pytest
`cache_dir` configuration warning and Starlette/httpx deprecation.

### Jam Full 2019-2022 Archive Acquisition

On `2026-08-01`, the user explicitly authorized the frozen full archive
acquisition. Protocol
`b27197c3b9c7e4366b3e72442206562e1ae2967931ec3fa383e59c9133bcaf74`
bound 96 BTCUSDT Spot monthly archive identities, 94 network targets, resource and
request ceilings, resumable transport, exact source-quality rules, and a strict
no-return authority boundary.

All 96 archive SHA-256 identities passed. The run recorded 94 HEAD requests, 95
payload GET requests, no redirect, 29,691,768,890 compressed bytes, and
161,290,218,393 declared member bytes. April 2022 aggregate trades required one
resumable retry. The runner preserved and recorded genuine source defects rather
than aborting the remaining census.

One controlled checkpoint migration was necessary after the 2021-12 official
aggregate archive exposed a duplicate nested CSV member. Before migration, Aurex
rehash-verified all 70 completed archives and confirmed their exact original
single-member matrices. Migration evidence hash is
`bb971b20617fd54fb97b190d7bea68832f4a092d78b74585f698e850996ac4d0`.

The completed result inspected 1,972,243,570 aggregate rows and 2,099,831 of
2,103,840 expected kline rows. Sixteen months failed continuity, eight failed a
kline row invariant, one failed the ZIP member matrix/safety rule, and 18 failed
cross-family reconciliation. Aggregate events outside available kline minutes were
zero. Mismatch totals were 144 raw-trade counts, 135 OHLC, 144 base volume, 144
quote volume, 142 taker-buy base volume, and 142 taker-buy quote volume.

Only 23/48 months passed every frozen rule. Result
`data/evidence/jam_archive_full_acquisition_result_v1.json` has evidence hash
`ffe45a45bc9340e3323aac9ddd4257a19597bcee260961f787b50c8b1dee121b`
and file SHA-256
`d33559a1696c1e4db45b410ef25e2b72d61854a9d10c2b5403521bac12a136a6`.
Decision is `STOP_JAM_SUCCESSOR_FULL_ARCHIVE_QUALITY_FAILED`; artifact next
authorization is `NONE_ACQUISITION_FAILED`.

Independent raw-file reconstruction rehashed all 96 archives and rebuilt all 48
monthly records. Audit
`data/evidence/jam_archive_full_acquisition_audit_v1.json` has evidence hash
`d0f1d8bc4a2fe8745bf678aacdeeaeb3ef547fed49b9956dc54d36311c96e961`
and raw-manifest hash
`362633896615d1ce287f71563b5e63c97b87a47dec4a5a8a5af5524fbbfe017d`.

Until a separate
`AUTHORIZE_JAM_ARCHIVE_QUALITY_REMEDIATION_DESIGN_NO_RETURNS` authorization is
given, Aurex may not define successor features or parameters, inspect returns,
create a candidate, begin paper, submit Testnet strategy orders, or enable
production/live execution. Real profit remains `$0`.

Closeout verification passed the frozen protocol check, checkpoint-migration
replay, final result/raw-hash audit, independent raw reconstruction, 50 focused Jam
lineage tests, repository-wide Ruff, and all `1032` Aurex tests in `435.31`
seconds. The only warnings were the existing pytest `cache_dir` configuration
warning and Starlette/httpx deprecation.

### Jam Archive Quality Remediation

On `2026-08-04`, the user explicitly authorized a no-return remediation design over
the existing 96 BTCUSDT 2019-2022 archives. Aurex froze protocol
`128eb77a416ba9ebd47154639fe383f1f9b9c0058c149c8f7dc62c4e5e24c57a`
before reading any detailed defect values. The contract binds the failed
full-acquisition result and audit, forbids network access and all outcome work, and
freezes 2019-2020 development, 2021 sealed validation, and 2022 sealed holdout.

The remediation reconstructed all 48 kline months and all 18 cross-family failure
months. It found 4,009 missing kline minutes in 21 intervals, eight invalid rows,
and 144 mismatch minutes. Mismatch dimensions exactly reproduce the parent totals:
144 raw counts, 135 OHLC, 144 base volume, 144 quote volume, 142 taker-buy base,
and 142 taker-buy quote. Their union with the kline defects is 4,161 quarantined
minutes.

The official 2021-12 aggregate archive contains two members. Both uncompressed
members have SHA-256
`4a2d823de4b60232442c92cc44d109dc31da89ca988d5111c9f07209c462fa54`,
so the top-level canonical member is accepted under an exact byte-identity rule.

Result
`data/evidence/jam_archive_quality_remediation_result_v1.json` has evidence hash
`02a3b8fef4e44995ebc1c0150044f1506e1f805d6c565f86d54bacc227f4f00c`.
Independent raw reconstruction produced audit hash
`146bbf5e1406ed0444edaf62ffdb2788647b4c7f064f087a9202ea602ea6cc48`.
Decision:
`PASS_AGGTRADES_PRIMARY_SOURCE_POLICY_AWAIT_NO_RETURN_FEATURE_SPECIFICATION`.

Aggregate trades are now the Jam successor's historical primary source; official
one-minute klines are QA-only. Missing minutes are never synthesized or interpreted
as zero flow. All defects are quarantined, future state must reset at defect
boundaries, and eligibility must wait for the maximum future feature lookback.

No feature, parameter, threshold, return, PnL, strategy, signal, paper eligibility,
Testnet strategy order, production/live authority, real capital, or profit was
created. The exact next authorization is
`AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`.

Closeout verification passed two complete raw reconstructions, 65 focused Jam
lineage tests, repository-wide Ruff, and all `1036` Aurex tests in `790.27`
seconds. The only warning was the existing Starlette/httpx deprecation.

### Jam Successor Causal Feature Specification

On `2026-08-04`, the user explicitly authorized
`AUTHORIZE_JAM_SUCCESSOR_FEATURE_SPECIFICATION_NO_RETURNS`. Aurex first froze
protocol
`86ee3e67c6fc78863378b4a1b30c8cb38f9aafda2335e92054309cd260bfffba`.
The protocol bound the selected sell-flow mechanism, remediation result and audit,
4,161-minute quarantine, append-only contamination ledger, and frozen
2019-2020/2021/2022 evidence roles. It allowed schema-level causal feature design
and synthetic fixtures only.

The specification fixes four non-overlapping phases relative to evaluation minute
`t`: 120 baseline minutes at lags 132-13, five pre-shock minutes at lags 12-8,
five shock minutes at lags 7-3, and three confirmation minutes at lags 2-0. Every
row requires 133 contiguous valid minutes inside one partition.

Seventeen Decimal features measure baseline sell quote/share, pre-shock VWAP,
shock sell-flow intensity/share, shock price impact/low, confirmation sell
flow/share, sell-flow and sell-share decay, reclaim, and bounce. Robust flow scores
use `1.4826 * MAD`; outputs use 18-place half-even rounding. No cutoff or signal
predicate exists.

Seven quality states ensure only `READY` exposes values. Partition starts,
quarantined evaluation minutes, defects inside the lookback, absent aggregate
minutes, zero robust scale, and zero denominators withhold the entire vector.
Klines remain QA-only and cannot synthesize or overwrite a feature.

Nine synthetic conformance cases pass aggressor mapping, exact readiness,
future-invariance, partition reset, quarantine, post-defect warm-up, no-aggregate
behavior, zero-MAD failure, and Decimal determinism. Conformance manifest hash:
`cae28c8f9acdc3884747281d78003f128a33907aca89d73fed6217d5974122bc`.

Specification
`data/evidence/jam_successor_feature_specification_v1.json` has evidence hash
`8c69103a5e65c73ff248e365a5c25362c0f4f7fffc1452ca197bf57e04d53701`.
Independent audit
`data/evidence/jam_successor_feature_specification_audit_v1.json` has evidence hash
`760ff52b46792772072d9b14622e1a8555dfed2758b24f148fe81ecf01f512a2`.

Decision:
`PASS_CAUSAL_FEATURE_SPECIFICATION_AWAIT_DEVELOPMENT_DISTRIBUTION_AUTHORIZATION`.
Zero real market rows, thresholds, future labels, returns, strategies, signals,
orders, paper authority, production/live authority, real capital, or profit were
created. The exact next gate is
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS`.

Closeout verification passed all protocol/specification/audit rebuilds, nine
synthetic conformance cases, 78 focused Jam lineage tests, repository-wide Ruff,
and all `1049` Aurex tests in `1042.31` seconds. The only warning was the existing
Starlette/httpx deprecation.

### Jam Successor Development Feature Distribution

On `2026-08-04`, the user explicitly authorized
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_FEATURE_DISTRIBUTION_NO_RETURNS`. Aurex froze
protocol
`8451a456171524092390ce3ef9536032d3d6e3dea1eee4eedc8e70cd014b8551`
before reading development market values. It bound 24 BTCUSDT aggregate-trade
archives from January 2019 through December 2020, 1,052,640 UTC calendar minutes,
the exact 3,063-minute development quarantine, fixed descriptive statistics, seven
structural gates, and a strict no-outcome/no-return boundary.

All 24 archive identities and source invariants passed. The runner aggregated
400,020,102 source rows into 1,049,526 observed minute primitives and calculated the
frozen 17-feature vector. The hash-bound Parquet contains exactly 1,052,640 rows:
1,046,202 `READY`, 132 partition warm-up, 3,063 source quarantine, 3,147
post-defect warm-up, 96 no-aggregate minutes, and zero degenerate-scale or
degenerate-denominator rows.

Every ready row contains all 17 finite features. Overall ready rate is
`0.9938839489284085727314181487`; the minimum monthly ready rate is
`0.9806227598566308243727598566`. Every feature has at least 192,787 unique
values and positive IQR. All 136 pairwise correlations and fixed marginal/tail
profiles were preserved as descriptive evidence only.

All 7/7 structural gates passed. Result
`data/evidence/jam_successor_development_distribution_result_v1.json` has evidence
hash
`d79092c225bb5cd4ecda603a45f1114f6e7f669c1413e3e36057cdcac72b9eef`.
Feature artifact
`data/evidence/jam_successor_development_feature_rows_v1.parquet` has SHA-256
`fbb6ee42fca63ea6fe38db093c6c5c5484d2c6997d658d616f09f6fd4c2a0dfa`
and schema hash
`15995c028cfb437bea77990389eee4e036f9493b106270476ad1ce07cfcc037b`.

The independent audit reprocessed all 24 archives and reproduced the feature
Parquet, schema, serialized result, and result hash exactly. Audit evidence hash:
`7ede08a05049a8f2bb82c4b660488b5803449b6536aaf17628630eb113a1bc9b`.

Decision:
`PASS_DEVELOPMENT_FEATURE_DISTRIBUTIONS_AWAIT_EVENT_PROTOCOL_AUTHORIZATION`.
The 2021 validation and 2022 holdout partitions remained sealed. No event threshold,
future label, return, PnL, strategy, signal, candidate, order, paper authority,
production/live authority, real capital, or profit was created. The exact next
authorization is
`AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS`.

Closeout verification passed the frozen protocol rebuild, byte-identical
independent distribution reconstruction, 79 focused Jam lineage tests,
repository-wide Ruff, and all `1052` Aurex tests in `1451.94` seconds. The only
warning was the existing Starlette/httpx deprecation.

### Jam Successor Event And Outcome Protocol

On `2026-08-05`, the user explicitly authorized
`AUTHORIZE_JAM_SUCCESSOR_EVENT_AND_OUTCOME_PROTOCOL_NO_RETURNS`. Aurex bound the
accepted 2019-2020 development feature distribution and froze one non-editable
long-only event:
`J2-P01-SELL-FLOW-EXHAUSTION-RECLAIM-EVENT-V1`.

The event requires five simultaneous conditions fixed from prespecified
development quantiles: extreme robust sell flow, elevated sell share, adverse
five-minute price impact, decaying sell flow, and price reclaim. It has no score,
ranking, model, threshold grid, or alternate variant. Raw events are processed
chronologically; the first is accepted and subsequent events are suppressed until
at least 60 minutes have elapsed.

Seven prevalence gates require at least 1,000 raw events, at least 240 accepted
non-overlapping events, broad monthly and quarterly representation, limited
monthly and daily concentration, and zero accepted non-`READY` rows. Failure stops
the event definition; thresholds cannot be relaxed.

The protocol freezes one selectable 30-minute outcome. Fifteen- and 60-minute
outcomes are non-selectable diagnostics and cannot rescue a failed primary
outcome. Entry is the first aggregate trade in minute `t+1`; exit is the final
aggregate trade at the fixed horizon. Full path continuity is mandatory, defects
are never synthesized, and outcomes cannot cross partitions.

Base costs are 0.10% commission per side plus two adverse one-cent ticks per fill.
Stress costs are 0.15% per side plus ten adverse ticks per fill. Deterministic
non-event controls match calendar month, UTC hour, and the frozen baseline-flow
quartile without replacement or outcome-aware selection. Primary inference uses
a 10,000-repetition calendar-month cluster bootstrap with fixed seed `20260805`.
Eleven development gates, seven validation gates, and separate holdout gates are
fixed before any outcome calculation.

Protocol
`data/evidence/jam_successor_event_outcome_protocol_v1.json` has evidence hash
`33323ff5864c9dfdeed1b5ddd5dc237ac5a7b7d23d1a1ac484abf75e02ded8db`,
file SHA-256
`6eaf28df7810a9ebb93a048ded432c27d9d7791fdca6210d84d752e89a1f5081`,
and builder-contract hash
`9a4835b95eb6a8c1c91a71e3543ed45f1b9f4da6d96d3e7ae696e968f97bacd8`.
Independent reconstruction produced audit evidence hash
`b2236b02b9e3bbbf495bf66f9d862f446a29ae4bf3a9422d495bd8f0501f80e4`.

Decision:
`PASS_EVENT_AND_OUTCOME_PROTOCOL_AWAIT_DEVELOPMENT_EVENT_PREVALENCE_AUTHORIZATION`.
The 2021 validation and 2022 holdout partitions remain sealed. No event flag,
future label, return, PnL, backtest, candidate, signal, order, paper authority,
production/live authority, real capital, or profit was created.

The exact next authorization is
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES`. It permits
development event prevalence and concentration only. Outcome calculation remains
a separate later gate.

Closeout verification passed the frozen protocol check, independent audit
reconstruction, 83 focused Jam lineage tests, repository-wide Ruff, and all
`1056` Aurex tests in `843.20` seconds. The only warning was the existing
Starlette/httpx deprecation.

### Jam Successor Development Event Prevalence

On `2026-08-05`, the user instructed Aurex to continue with the exact next bounded
stage,
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_EVENT_PREVALENCE_NO_OUTCOMES`.
Aurex first froze prevalence protocol
`e43339f5186b5702c6db0d316b236415c5bb02f0bc2cb18d9188f5122adbe0cd`
while event flags, labels, and returns remained zero.

The runner then evaluated the unchanged five-condition event predicate on only the
hash-bound 2019-2020 development feature artifact. It preserved all 1,430 raw
events in an immutable JSONL ledger. Chronological 60-minute suppression accepted
991 events and suppressed 439; suppression did not reset at month or year
boundaries.

All 24 months contained at least five accepted events. The weakest of eight
quarters contained 70. August 2019 was the largest month with 82 accepted events,
or `0.08274470232088799192734611504` of the total. November 22, 2020 was the
largest day with six events, or
`0.006054490413723511604439959637`. Every accepted event used a `READY` causal
feature row.

All 7/7 frozen prevalence gates passed. Result
`data/evidence/jam_successor_development_event_prevalence_result_v1.json` has
evidence hash
`444fe28b86c6283181f3e99cfe55258fd4e9136cbca1c92b978cbdfae9ea77ea`.
The raw-event ledger has SHA-256
`b6fe0c49bbbb8b61ac268b4716d2a50ab5fa08479ccbf254ef532b15a3b7d909`.

Independent reconstruction reproduced all 1,430 ledger lines and the serialized
result byte-for-byte. Audit evidence hash:
`414e9affc9e138a38a25c7a3d3432f0672217c9ff3e8707b73147200ea5f544d`.

Decision:
`PASS_DEVELOPMENT_EVENT_PREVALENCE_AWAIT_OUTCOME_AUTHORIZATION`.
This proves sample availability and distribution only. Future price rows, labels,
returns, controls, backtests, strategies, signals, orders, 2021 validation, and
2022 holdout all remained unopened or zero.

The exact next authorization is
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION`.

Closeout verification passed the frozen prevalence protocol check, canonical
evidence validation, byte-identical independent reconstruction, 88 focused Jam
lineage tests, repository-wide Ruff, and all `1061` Aurex tests in `1426.56`
seconds. The only warning was the existing Starlette/httpx deprecation.

### Jam Successor Development Outcome

On `2026-08-05`, the user authorized
`AUTHORIZE_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_CALCULATION`. Before reading any
post-event price, Aurex froze execution protocol
`e7ed92d708c80a87b36c7d24d903cd7be1c1f594def74daab22618ed9bc6e07d`.
The protocol fixed control matching, aggregate-trade price extraction, full-path
continuity, base and stress costs, 18-place arithmetic, the 30-minute primary
horizon, a deterministic 10,000-repetition month-cluster bootstrap, and all eleven
development gates. Validation, holdout, strategy, signal, paper, Testnet strategy
order, production, live, and real-capital authority remained false.

The runner opened only the hash-bound 2019-2020 development aggregate-trade
archives. It requested 86,820 event/control path minutes and recovered all 86,820
with no missing requested minute. The deterministic control matcher produced 456
matched and 535 unmatched events. All 991 accepted events had available 15-, 30-,
and 60-minute outcomes; all 456 controls had all three horizons. The immutable
control ledger contains 991 records and the outcome ledger contains 4,341 records.

The primary 30-minute result failed economically. Base net mean was
`-16.008098281388651150` bps, profit factor was
`0.464374516027724364`, stress net mean was
`-26.189788269683100509` bps, and matched excess mean was only
`2.984977884653180892` bps. Bootstrap lower bounds were negative for both the
base mean (`-19.768677643106546730` bps) and matched excess
(`-3.041289366472522414` bps). Neither year and none of the eight quarters had
positive base net mean. Only sample size, matched-pair count, and month
concentration passed: `3/11` gates.

Result evidence hash:
`560d990748bcefce3e7a46c4bb88e89bf16563bef659213e55b2934005bff430`.
Independent audit hash:
`8c62f09705fe2013cdbc2d61234aa92070badd9b70189a620be0e37088251c95`.
The independent run regenerated all source extraction, controls, outcomes,
metrics, bootstrap values, and the complete result byte-for-byte.

Decision:
`STOP_JAM_SUCCESSOR_DEVELOPMENT_OUTCOME_FAILED`.
Next required authorization:
`NONE_DEVELOPMENT_OUTCOME_FAILED`.
The event definition is retired without opening 2021 validation or 2022 holdout.
It cannot be tuned, rescued with diagnostics, sent to Pine, paper-traded, or used
for a Testnet strategy order. A future research path requires a separate,
genuinely unrelated and preregistered mechanism. Real net profit remains `$0`.

Closeout verification passed the frozen execution-protocol check, independent
byte-for-byte reconstruction, seven focused outcome tests, 95 focused Jam lineage
tests, repository-wide Ruff, and all `1068` Aurex tests in `676.74` seconds. The
only warning was the existing Starlette/httpx deprecation.

### Q1 Successor Acquisition V2 Terminal Audit And V3 Transport Correction

On `2026-08-10` and `2026-08-11`, Aurex preserved the immutable successor v2
terminal result after three unresolved May 2020 USD-M full-GET attempts. The
independent terminal audit accounted for all three request/response pairs and
16,332,030 body bytes, confirmed that no complete or partial v2 archive remained,
and documented that the v2 response-marker schema omitted the underlying exception
type and message. Terminal audit evidence hash:
`1c475bd0b60ed92930fa8b54580b91f4ea49b00cb731ab5c881b78db74465a7d`.

A separately versioned transport amendment then authorized exact range resume and
bounded error observability without changing the source manifest, structural gates,
sufficiency gates, byte limits, disk reserve, or no-outcome boundary. Amendment
hash:
`e32c9f0d6c74a1eefa9ba60f9c4cc836a30fff5540575972510446f2b39bf19d`.
Independent amendment audit hash:
`5c060fc2df07ed15d875fb341081199438bce55a53e32b3f67bf8850164d1dd4`.

The v3 runner preserves partial bytes after transient failure, requires exact HTTP
`206` and `Content-Range` for every positive offset, records failure class/type/
message, handles both interruption-before-response and interruption-before-rename,
and requires the published full-file SHA-256 before completion. It seeds three
archive records and one paired month from v2 and copies the exact preserved
42,991,616-byte v1 partial into a fresh root. Source-bound execution-contract hash:
`402b83efbf928cce5bd8227c5ae723474a3fe58cdac97a3f1a280409bafb96b0`.
Independent audit hash:
`73c0fc1981650f570e23964e5f19d6ccc0166eb00737e5b469de60dd70b95b8a`.

Eleven focused tests and repository-wide Ruff pass. Canonical preflight verified
26/26 local candidates, the v2 seed, the bootstrap partial, and 156,206,239,744
free bytes against the 120,000,000,000-byte requirement. V3 network requests,
outcomes, strategy executions, and orders remained zero at this checkpoint.

The first v3 network run then completed May 2020 USD-M across three resumable
attempts. Attempt 1 was deliberately interrupted and reconciled at 103,245,365
partial bytes, of which 60,253,749 were new v3 body bytes. Attempt 2 ended as a
valid incomplete HTTP `206` response after another 37,649,510 bytes. Attempt 3
resumed from 140,894,875 and received the remaining 230,028,906 bytes. The complete
370,923,781-byte archive passed its published SHA-256 and contained 34,806,643 rows.
It then failed the unchanged structural gate
`SINGLE_SKIPPED_TRADE_ID_COUNT_EXCEEDS_100`, so May was excluded whole.

July 2020 Spot passed with 19,098,848 rows. July USD-M attempt 1 was intentionally
closed at 42,808,757 partial bytes and reconciled without network access under
evidence hash
`e72dea916e071c39c4cc6565337d497262551d90738bb4c81450d7ba9af44cea`.
Current checkpoint evidence hash:
`c83c181fe1062039ef461f5613dd62d120fd28be38591db81b27b8725db138e2`.
Current checkpoint file SHA-256:
`da4eb765253af854a2b6c0d636ed4346a733d85e723dbf0ba17efa4f6090a99f`.
It records five inspected archives, one paired month, one excluded month, four
matched request/response pairs, 370,740,922 v3 payload bytes, zero outcomes, zero
orders, and no terminal result. The exact next action is to resume the unchanged
v3 acquisition runner.

Because the original contract freeze and audit reconstruct the pre-network empty
root, their `--check` commands correctly cease to apply after network evidence is
created. A separate post-network lineage checker now validates the immutable
amendment, amendment audit, execution contract, execution audit, unchanged runner
source, and active checkpoint without requiring an empty root. It passes with
contract hash `402b83efbf928cce5bd8227c5ae723474a3fe58cdac97a3f1a280409bafb96b0`,
audit hash `73c0fc1981650f570e23964e5f19d6ccc0166eb00737e5b469de60dd70b95b8a`,
and runner hash
`dbd9304fcab694e02a42cf8dc310730f0c191912fdfeee8e18444a561bfaf618`.

### Q1 Successor V4-V7 Terminal Source-Sufficiency Decision

On `2026-08-13` and `2026-08-14`, Aurex completed the versioned successor source
qualification without opening prices, quantities, features, parameters, returns,
validation, holdout, or forward outcomes.

V4 preserved a DNS-stop terminal. V5 added bounded DNS resilience and reached the
January 2023 USD-M archive, where an order-dependent gap metric produced an invalid
fraction for interleaved source rows. Independent v5 audit proved the archive hash
and transport were valid and classified the defect as a validator evidence-model
failure. V6 froze a narrow correction: non-monotonic USD-M rows remain excluded
whole, while inapplicable ordered-gap fields are encoded as zero. No source row is
sorted, dropped, deduplicated, changed, or synthesized.

V6 then stopped at April 2023 USD-M after an incomplete body and a DNS outage
exhausted 24 bounded attempts. Independent v6 terminal audit hash:
`afdcc398d4255b754c384166d1681577292bda4cdb52e9dc9096e3459bf8d05f`.

V7 seeded the exact 56-archive v6 checkpoint, left the 184,135,287-byte v6 partial
untouched, and started a fresh April USD-M request. Amendment and audit hashes are
`3bd140f124cf401bcb89ca704b1383143e6bb02c7550ee4a1df7bbc7188a1314`
and `470f1043dc02b25eeffcd670294b3eda0f518447de92645df572e2dcdb5e12d0`.
Execution contract and audit hashes are
`445407257f7e9ceb3ab6efed88e07ba7d6bea4caf19a85d0681cc65d44efb550`
and `3193084a0d6de96b2bece168322fc135ae405eee8d5b1b95161c97c3a9779456`.
Frozen runner source hash:
`493ccebe8255ec19a01fcb60571627aac4918b5f4691ea8f9c4852476c518705`.

Five initial v7 attempts were denied by the local Windows socket sandbox with zero
received bytes and no partial. Offline recovery evidence hash
`705f57584bf94a726b010b98fcd6eb395fabdd72640abd2a489333a57350af23`
reconciled the complete marker pairs. The same frozen runner resumed with network
permission. June USD-M demonstrated exact Range recovery after one incomplete
body; all completed archives required the published SHA-256 before atomic rename.

The terminal checkpoint classified all 37 months, inspected 73 archives, qualified
19 paired months, and excluded 18. Qualified pairs by year were 5 in 2020, 6 in
2021, 6 in 2022, and 2 in 2023. Only July and August qualified in 2023, and only 12
of 16 quarters qualified. The frozen gates required at least 30 pairs, at least six
per year, and all 16 quarters.

Terminal checkpoint evidence hash:
`9cb957b626f9f506168c73e51cc61d1dccee21c9fb03560fbbdbed7c1d918dcc`.
Terminal result evidence hash:
`f1adddf98a1466920a7d58d7b1e69e2f3101f3dae221f40ced590a893ed3e444`.
Decision: `STOP_Q1_SUCCESSOR_SOURCE_SUFFICIENCY_FAILED`.
Next authorization: `NONE_SOURCE_SUFFICIENCY_FAILED`.

The independent terminal audit rehashed all 73 archives, verified 23 matching v7
request/response pairs and zero partials, reconstructed every count, and then
passed a second full reconstruction. Audit evidence hash:
`d95aa05f8236d6c1ba51f8a39e1e94376578ce2bc3b446369e9da129b7725760`.

Focused v6/v7 terminal, validator, and transport tests pass. Focused Ruff passes.
No measurement protocol, candidate, Pine strategy, signal, paper authority,
Testnet strategy-order authority, production authority, live authority, order, or
profit was created. Real net profit remains `$0`.

### S1 Independent Macro Lineage And Point-In-Time Source Recovery

On `2026-08-26`, Aurex froze an eight-lineage predecessor ledger and selected one
independent successor mechanism without reading new outcomes:
`S1-NFCI-EASING-BTC-SPOT-RISK-APPETITE`. The charter binds Binance Spot Testnet
BTCUSDT, long-or-cash, 1x, `$100` simulated equity, five contiguous evidence
partitions, and a point-in-time-only NFCI policy. Lineage/charter audit hashes are
`590d5f5a848c52dc3c4455ebb7ce2d70db8250b6048fd76dbc0e63e825dbb41d`
and `79cc6e3fda4f1104c2c1df967e34c537695564f2bb29b7c7634863df57ab7239`.

The first four-request metadata probe used `HEAD`, read zero body bytes, and
stopped on three download-endpoint timeouts. A narrow v2 `GET`-open/close
amendment then proved both no-key CSV URLs reachable while making zero response
read calls and persisting zero payload bytes. Its independent audit hash is
`18bebaca422d07f42b2cbda77ab5a6433c53740982c388743d081eb600318877`.

The frozen FRED raw pilot downloaded two 51,425-byte files and correctly failed.
Both 2020 and 2021 requests returned the same current-data hash, ending
`2026-08-21`, with 347 and 294 post-vintage observations. Aurex preserved decision
`STOP_S1_NFCI_POINT_IN_TIME_RAW_PILOT_FAILED`; audit hash:
`39994116cfcd85e4e049509fce104a56d9b5e7dc9c164070548d32ba1effdb11`.

A separately frozen recovery changed only the host/path to ALFRED's vintage graph
transport. The 2020 vintage contains 2,555 rows through `2019-12-20`; the 2021
vintage contains 2,608 rows through `2020-12-25`. Their hashes differ, no row is
post-vintage, all 2,555 overlapping values are revised, and all ten frozen gates
pass. Result hash:
`274e9981103b3e31aea001e543f62d29d0d6941a1529b00cb5b037a854c75472`.
Independent audit hash:
`f658ef8639cd5ad17216389687301addf737bcfa480b6064298f5b5036905f56`.

The exact next authority is protocol-only:
`AUTHORIZE_S1_FULL_NFCI_VINTAGE_ACQUISITION_PROTOCOL_ONLY`. BTC market values,
strategy parameters, returns, candidates, signals, executions, orders, and trading
authority remain zero or false. Real net profit remains `$0`.

### S1 Full Point-In-Time Development Source Acquisition

On `2026-08-26`, Aurex froze and independently audited a 281-target ALFRED
acquisition protocol covering every Thursday from `2017-08-17` through
`2022-12-29`. Protocol/audit hashes are
`ccbff64f29ce5d85eb52dded23df1c393bb1a5ab4d5ce2c2874d8f284b87195e`
and `3de2d5970b537a30eb3c5be1c39571b146bdac8116d2b6dc4be0ea20fff4d819`.

Before network access, a synthetic interruption test found that the v1 runner could
not reconcile a completed atomic raw-file rename followed by a missing response
marker. Aurex preserved v1 as superseded with zero requests and froze a narrow v2
repair. V2 amendment/audit hashes are
`74420379ca8d30786c9d81a269052574d1d9aae90f3e85d0e952d14ad1fdbeda`
and `ae7a963a0c68deafd0ff9970ccae6b097c4ada036fb3b19409f8a58f9cb334c5`;
runner contract hash is
`951318f4e7d27efa73420e69bff31fef219e647c36ed63ad12924ab94b2f9b8d`.

The full run completed 281/281 targets in 281 GET attempts, persisted 13,056,155
of 13,056,155 received bytes, produced 281 distinct payload hashes, and passed all
ten source gates. Checkpoint/result hashes are
`92d1a8931c14b476c8217337f91cd7aa0f472ab6b7f525613f45abda982a0ae4`
and `4e94883da8e48c1dc6282370140084101f123dad2fd427dacee7708ee14c0c5f`.
An independent audit rehashed all 281 raw files and 562 markers and passed under
hash `f6669c6d80cd73f330a4d2c09a410e4eabb4b7628152bbd15636e12f13400ab1`.

Decision: `PASS_S1_NFCI_DEVELOPMENT_SOURCE_ACQUISITION`. The only next authority
is `AUTHORIZE_S1_NFCI_DEVELOPMENT_NORMALIZATION_PROTOCOL_ONLY`. No BTC value,
return, candidate, signal, execution, order, production authority, live authority,
or real profit was created.

### S1 Causal Development Normalization

On `2026-08-26`, Aurex froze the exact one-row-per-vintage normalization schema
before reading raw NFCI values for transformation. It binds latest-valid-observation
selection, exact decimal text preservation, source path/hash lineage, deterministic
JSONL, ten causal/structural gates, and explicit exclusion of derived features and
BTC outcomes. Protocol/audit hashes are
`998b775e60aad081f421b80be678fd209348df149e8a7cc8f1f05b368e0f6041`
and `2ef0d3405e903c01cdbed8648c26a244c5878bd26bcb2532c5a7f80536d0d087`.

Seven synthetic parser/serialization tests passed before execution authority was
frozen. Execution addendum/audit hashes are
`4190161d1e4f8928b5d6848f29b01d1e3bd31759fa280d1c12e3c81f319a3c34`
and `110ca7006f8014c50df7083e83d39f5218ef712b981e1209f53e291fce288db1`;
runner contract hash is
`a9cff8a1a1ed6f08ea1b55cde5dcf6f8949cab5044bc7b82fb03655cb8045908`.

The run rehashed all 281 raw files and 13,056,155 source bytes, then produced 281
causal rows and a 107,885-byte dataset with SHA-256
`789829ee9a9b84de528507c660c7abdcd5bd34a3c4a5d9cae1a46b7cd2ac927b`.
Source-release lags range from 6 to 20 days. Result hash:
`d9816fce4035ec50368eb1d0541f287ea261b9f64c5dee779fc671a998d07f4c`.
An independent replay matched all raw identities, rows, and dataset bytes under
audit hash `5070de85bafb6b657055d4e89e49927b2494c1a3116c700edac5d28bfc67e58d`.

Decision: `PASS_S1_NFCI_DEVELOPMENT_NORMALIZATION`. The only next authority is
`AUTHORIZE_S1_NFCI_DEVELOPMENT_FEATURE_PROTOCOL_ONLY`. Derived features, BTC
values, returns, candidates, signals, orders, live authority, and real profit remain
zero or false. The focused S1 suite passes 33 tests and repository-wide Ruff passes.

### S1 Macro-Only Development Feature Construction

On `2026-08-26`, Aurex froze a three-feature family before parsing normalized
values: NFCI level, one-vintage change, and four-vintage change. Exact Decimal
arithmetic, a four-row warm-up, 277 expected rows, deterministic JSONL, and a
four-candidate ceiling are mandatory. Rolling/expanding statistics, percentile
transforms, strategy rules, and market fields are forbidden. Protocol/audit hashes:
`d2ecbea9b31bc07e0cfec0901f3f262a1dd7e358148ec5e317ea972b51c16ce0`
and `2a1486c2ab3c9c5be5b3cc07a905ad3bcba6f4a961988cf3023f2797526acd8f`.

The source-bound runner passed synthetic exact-arithmetic, warm-up, tamper, and
serialization tests before execution. Addendum/audit hashes are
`2743b1a1f8234d7e82687fc8985dee044855bb13cc33bfc56f54018fb54f5d81`
and `de8fdc92fa19313120776831e1405623057aee5a598e9f75b782ed7c80f2db7f`;
runner contract hash is
`3b85b9bc81fa47f6e0aa5745128f2d4ef3d2a1bde35c30283da00eb3e345515a`.

The run produced 277 feature rows and a 90,632-byte dataset with SHA-256
`db93ee6954fee447cba66b3d873282da4d289f5ef6a63446d6ad036f787b24d6`.
Result hash:
`a59707114ec19c2576e72071fcba5ad7fa36e5232629a40fe1e9704f122f7664`.
Independent reconstruction matched every source row hash, feature row, and output
byte under audit hash
`da54d8a9ee1097994b1b3fc6edc81f844abcb7f9f046426c1f0a51732a0cc1f3`.

Decision: `PASS_S1_NFCI_DEVELOPMENT_FEATURE_CONSTRUCTION`. The only next authority
is `AUTHORIZE_S1_NFCI_DEVELOPMENT_STRATEGY_PREREGISTRATION_PROTOCOL_ONLY`.
Candidates, BTC values, returns, validation, holdout, signals, orders, live
authority, and real profit remain zero or false. The focused S1 suite passes 40
tests and repository-wide Ruff passes.

### S1 Strategy Preregistration And BTC Source Contract

On `2026-08-26`, Aurex froze one promotable primary rule before opening BTC values:
long at 1x only when both one- and four-vintage NFCI changes are negative; otherwise
cash. Three simpler variants are diagnostics only and cannot rescue a failed
primary. Execution is Friday 00:00 UTC, one day after the source vintage. Base cost
is 15 bps per position-changing fill; stress cost is 22.5 bps. Twelve gates bind
276 development intervals, transitions, exposure, profitability, profit factor,
drawdown, calendar-year breadth, and an 8-week stationary-block bootstrap.
Preregistration/audit hashes are
`6ca639fa0ff744dc13c1c8db229d46a8a7710b77bb49eded2ac8cae4a022816f`
and `6d10abaf857bba7dd28c10e19957bdffc7fef7bc67da96d7dfd5060d3ba17c00`.

The subsequent source protocol binds 277 official Binance Spot daily BTCUSDT 1h
ZIP/checksum pairs from `2017-09-15` through `2022-12-30`, exact Friday 00:00 UTC
opens, safe ZIP membership, positive finite decimal text, immutable markers, and
fixed request/byte ceilings. Protocol/audit hashes are
`bed364619aa4a141d339e405948e6a0a4113afb5c0ee1dedf5c288346255ffe2`
and `19cf011a7f817b221f03748d9db48a614d235c7a79de8cc6e737ad20f3bce1bd`.

The exact next authority is runner implementation only:
`AUTHORIZE_S1_BTCUSDT_DAILY_1H_SOURCE_ACQUISITION_RUNNER_IMPLEMENTATION_ONLY`.
Requests, payload bytes, BTC values, returns, validation, holdout, orders, live
authority, and real profit remain zero or false.

### S1 BTC Source Failure, S1.1 Completion, And Terminal Outcome

On `2026-08-27`, the checksum-bound v1 BTC runner stopped at target 22 because the
official `2018-02-09` archive begins at 10:00 UTC and has no preregistered exact
00:00 bar. The independently audited terminal result is
`f444378a3b89b49812615b8b9313147e32e2ecb646348675054893bea99a57fd`;
audit hash is
`b98dff769d6537ee55d00705ea7fe585868390f7c7d0651ed99f91177771949e`.
Audit also exposed a v1 partial-checkpoint strict-ZIP defect. It did not cause the
source failure and remains preserved rather than rewritten.

S1.1 froze a separate first-valid-Friday-bar amendment before inspecting the
remaining dates, declared 21 prior development price values and zero returns, and
implemented a prefix-safe resume verifier. The amended source run reused 22 files,
downloaded 255 new checksum/archive pairs in 510 first-attempt requests, classified
277/277 targets, and passed all 11 gates. One target was delayed 600 minutes. Source
result/audit hashes are
`87e413172462f7006332a53be3ba74b6b7bdd1c61e03d0f7f71e218322e3caa0` /
`5685b46d8ef2c787ce606025ee76d75bbf00a830237f692b5ec7b6145ac053f3`.

The outcome protocol froze exact Decimal arithmetic, costs on every binary position
change, forced terminal liquidation, dollar-P&L profit factor, compounded drawdown,
full-year assignment, and a seeded 10,000-sample stationary-block bootstrap before
parsing either dataset. The one-shot primary passed 7/12 gates. Base return was
`7.6958%` and stress return `0.8049%`, but base PF was `1.01395`, base drawdown
`66.3009%`, only two full years were positive, and the stress-bootstrap lower bound
was negative. Five frozen gates failed. Diagnostics were reported and not promoted.

Terminal result/audit hashes are
`8d900beb2dcbfcb0d11fed1f8ee0a99ecfa812e03900dae21a886973f86cc317` /
`ab1f10d0208560933e048f1fb93e5b03f0988048e7c4b5e6057dba14b0c2495d`.
Decision: `STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED`. Validation and holdout remain
sealed. Exact program continuation is
`AUTHORIZE_POST_S1_FAILURE_ANALYSIS_PROTOCOL_ONLY`; real net profit remains `$0`.

### S1 Controlled Failure Analysis And Retirement

On `2026-08-27`, Aurex froze and independently audited a seven-question
development-only postmortem before calculating any analysis metric. Protocol/audit
hashes are
`f4b7ebd92fd1a149d784cce1840c08180d8c942ff2e54b6047313f91ba359c9b` /
`5b88bb69058ccde7f839bcb8405123fdd8db283920bccb000ddaf8cfbd431a83`;
execution contract/audit hashes are
`84a4d09a653ca932e837adaa515faa47301a4a38cea5915839fd8ded22209064` /
`13a27548fa293a6082b9fa8311bb321162cf4f8318aeeeacc777017caf79945b`.
Eight focused synthetic tests passed before the one-shot execution.

The analysis reconstructed the 276 primary development intervals and all three
diagnostic position vectors from the immutable 1,104-row ledger. Gross return was
`22.9048%`; 88 fills reduced it to `7.6958%` at base cost and `0.8049%` under
stress. Base maximum drawdown was `66.3009%`, the maximum drawdown episode never
recovered inside development, the five largest gains and losses supplied `40.1360%`
and `37.9805%` of their respective stress totals, and two diagnostics were exact
position-vector duplicates. Zero parameter variants, new candidates, validation,
holdout, or orders were opened.

Result/audit hashes are
`0db0fd10424b5bcc07a7f10c42c88d3a3843c0dddbcdc6a29c6665529c192988` /
`be6340eb9bf978c4cff9f06427169cd1b03a76f2a5030aa028aa4343c2f97ffe`.
Decision: `RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE`. Exact continuation:
`AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY`. Real net profit remains `$0`.

Canonical control, `/system/readiness`, and the dashboard were advanced to
`S1_POST_FAILURE_ANALYSIS_COMPLETE_S1_RETIRED`. Readiness current result v13 passes
14/15 capability gates with one downstream TradingView proof partial and zero
research blockers. Result/audit hashes are
`106792f04a7c747b0404a37fa3766ae1907702fc282b88ef28321d73e36ed336` /
`3815eeb4a708c1fc1cc267a76580ec7ca1f77dae4ade499c1253d4b9b38fca8d`.
## 2026-08-27 - S2 settlement-demand charter frozen

- Preserved the terminal S1 decision
  `RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE` and selected a genuinely distinct
  successor family rather than tuning or renaming the failed macro mechanism.
- Added `s2_onchain_settlement_charter.py` with a fail-closed typed charter for one
  weekly Bitcoin on-chain settlement-demand hypothesis, `BTCUSDT` Spot long-or-cash,
  maximum `1x`, and the existing simulated `$100` operator limits.
- Bound eight predecessor artifacts, six external research sources, exact BigQuery
  source requirements, six-confirmation/prior-Friday causal timing, five contiguous
  evidence partitions, nine predecessor-family exclusions, and zero outcome or
  trading authority.
- Explicitly excluded Coin Metrics community values from trading inputs because the
  free community service is documented for non-commercial use. Google BigQuery
  public Bitcoin metadata and bounded query dry runs are the only authorized next
  source-feasibility actions.
- Added freeze and independent-audit CLIs plus seven focused tests. Charter evidence
  hash:
  `77e61e9f01519d6b7b56aa2ce45d4689356120bb1a338ead9edce35ef18fe9b0`;
  audit evidence hash:
  `88e82b6c0169e6e9f3f645cfadeeb8e3aac797f002e5c5f88cae9fe863746745`.
- Updated `/system/readiness` to verify the full S2 predecessor chain and fail closed
  if the charter, audit, or any predecessor changes. Runtime checkpoint is now
  `S2_ONCHAIN_SETTLEMENT_CHARTER_FROZEN`; exact next action is
  `AUTHORIZE_S2_BIGQUERY_METADATA_AND_QUERY_COST_FEASIBILITY_ONLY`.
- Generated and independently reconstructed readiness v14 at 14/15 PASS, 1 PARTIAL,
  and 0 FAIL. Result/audit hashes:
  `05e499de7eb84108c18953b000f427a473537c365bae497879105f2d09d7073a` /
  `e5db43dd5f06e0d7344c7746fdad6b2be52431c05dd26e2fd32596ca85f12b47`.
- Focused S2 charter verification: `7 passed`. Readiness integration: `1 passed`
  with the existing Starlette/httpx deprecation warning. Numeric blockchain queries,
  payload acquisition, market-value access, parameters, returns, candidates, Pine,
  paper, Testnet strategy orders, production, live, real capital, and profit remain
  unauthorized.

## 2026-08-27 - S2 BigQuery feasibility blocked honestly

- Added a typed, hash-bound BigQuery metadata and dry-run feasibility protocol with
  three exact public metadata endpoints, two exact GoogleSQL dry-run specifications,
  response-size and timeout ceilings, zero result rows, and no numeric-query or
  trading authority.
- Froze and independently reconstructed the protocol before network access.
  Protocol/audit hashes:
  `9e91ba7e6d8b388e4873ccd255336577ae1f2c900e3c88f35df6abc6a09720f0` /
  `e952ebf625acad59909c506d1fe4e1683c4580d61ae4203858770ca86dcb25d0`.
- Added eight unit tests covering query tampering, metadata failure, missing clients,
  missing project, no-billing enforcement, and zero execution authority. All eight
  passed before the bounded run.
- Spent the three exact metadata attempts. Dataset, blocks, and transactions returned
  HTTP `401`. No response artifact was accepted. Local checks found no `gcloud`, no
  `bq`, no active Google Cloud project, and no verified BigQuery sandbox without a
  billing account.
- Recorded and independently audited decision
  `BLOCK_S2_BIGQUERY_PUBLIC_METADATA_UNAVAILABLE`. Result/audit hashes:
  `8986a9ed6b41af03e6ba7fe72054138362a04ee3f1eae6b1278656b1b56df9f1` /
  `1c4bcf38b0484495a069b050a404c3e5135bd1fb748097dced37c3d78aa68b38`.
- Updated readiness to fail closed at
  `S2_BIGQUERY_FEASIBILITY_BLOCKED_AUTH_REQUIRED`, with exact next authorization
  `NONE_UNTIL_S2_BIGQUERY_FEASIBILITY_PREFLIGHT_PASSES`.
- Generated readiness v15 at 14/15 PASS, 1 PARTIAL, and 0 FAIL. Platform capability
  remains healthy while the active research track is blocked. Result/audit hashes:
  `9e25605d0ccd64804c78749f9c3c8a058228faaead66e55b43a8a32789a69a7b` /
  `7497bf8421b9ab2a96db75ac95bd25180016fb3b9cb9519d8244f1e90711f0ba`.
- No dry run, query execution, row result, blockchain value, market value, payload,
  parameter, return, candidate, Pine signal, paper order, Testnet strategy order,
  production action, live action, real capital, or profit was authorized or created.
- Combined focused S1/S2/readiness verification passed `42` tests; repository-wide
  Ruff passed. Fresh v15 runtime/API and `1280x720` browser QA passed at port `8922`
  with source integrity true, no horizontal overflow, and no console errors.
- Downloaded Google's exact versioned Windows Cloud CLI `579.0.0` archive and
  verified its published SHA-256
  `032231d56bdc86cede7648e56720b3ef0eb9c3b9e4129e8f6f97286ce97e8c8a`
  before extraction. `gcloud 579.0.0` and `bq 2.1.36` respond from the self-contained
  `%LOCALAPPDATA%/AurexTools579/google-cloud-sdk` path. Boolean-only checks show no
  active authentication and no active project; no identifier was displayed.

## 2026-08-28 - S2 authenticated feasibility amendment frozen

- Preserved the consumed v1 protocol, result, audit, and source code without edits.
  Added a separate v2 model, freeze/audit pair, runner, result auditor, and focused
  tests rather than silently reusing the three failed unauthenticated attempts.
- V2 orders prerequisites before any source request: pinned `gcloud` and `bq`, active
  user OAuth, active project, and a verified no-billing boundary. It then permits at
  most one in-memory token request, three authenticated public-metadata requests, and
  two BigQuery CLI dry-runs.
- Structurally forbids account/project identifier persistence, credential/token
  persistence, query result rows, blockchain or market values, payload acquisition,
  parameters, returns, candidates, orders, production, and live authority.
- Froze and independently reconstructed the amendment with zero network requests.
  Protocol/audit hashes:
  `0074b2d2594bb5aa5d430e6818218146be244ea57e2386938ebaaf01fc5147a9` /
  `1140f679697b1a86757071a4afeb3ceeda120b099fa8e6c374e13e35d009fc19`.
- Focused v1/v2 feasibility verification passed `18` tests. Post-freeze builder and
  protocol reconstruction remain exact. The known pytest `cache_dir` warning is
  unchanged.
- Two official Google OAuth flows were opened for the operator, but neither consent
  callback completed. Stale CLI listeners were stopped. Boolean-only verification
  still reports no active authentication and no active project; no identifier was
  displayed or written.
- Exact resume point: operator approval of the official Google Cloud CLI OAuth flow,
  followed by selection or creation of a BigQuery sandbox project without billing.
  Aurex then runs and audits v2 once. V2 requests, result rows, orders, and real net
  profit remain `0`.
- Updated `/system/readiness` to verify both the immutable v1 result lineage and the
  frozen v2 amendment. Runtime checkpoint is `S2_BIGQUERY_V2_READY_AUTH_REQUIRED`;
  paper, sandbox strategy use, production, and live remain false.
- Generated and independently audited readiness v17 at 14/15 PASS, 1 PARTIAL, and 0
  FAIL. Result/audit hashes:
  `5f9fe4d7548027ea536db557985b68fbdb1132726da221762bd2fc64f3dcc9a9` /
  `c9187ff5f43355bb68fb650b714c22c9f56f665511fe09b1425e6aa487a4a0a2`.
- Combined focused v1/v2/API verification passed `19` tests with the two existing
  pytest configuration and Starlette/httpx warnings.
- The first complete-suite run found one order-dependent legacy failure: the
  derivatives foundation raised process-global Decimal precision from 28 to 60,
  changing slow-breakout candidate evidence-string length. The isolated test passed,
  proving test-order leakage rather than an S2 failure.
- Made candidate-decision addition and division explicitly use a local 28-digit
  Decimal context and added a regression test that evaluates under forced 60-digit
  process precision. The hostile derivatives-then-candidate sequence passed `14`
  tests.
- The clean complete-suite rerun passed all `1323` tests in `1532.54s`. Only the two
  existing pytest `cache_dir` and Starlette/httpx warnings remain.
- Started the v17-backed runtime at `127.0.0.1:8923`. `/system/readiness` reports
  `S2_SOURCE_FEASIBILITY_BLOCKED`, checkpoint
  `S2_BIGQUERY_V2_READY_AUTH_REQUIRED`, verified source/checkpoint integrity, zero
  qualified strategies, and paper/sandbox-strategy/production/live all false.
- Desktop and mobile browser QA found no horizontal page overflow or console issues.
  The long OAuth next-action uses normal wrapping with `overflow-wrap: anywhere` and
  no clipped scroll width. The refreshed dashboard tab remains available to the
  operator.

## 2026-08-28 - S2 authenticated payload acquired and readiness advanced

- Completed authenticated BigQuery metadata verification without recording account
  or project identifiers, credentials, tokens, or raw responses in Aurex evidence.
- Preserved the consumed v2 CLI dry-run failure, froze a REST-transport v3
  amendment, and passed two bounded REST dry runs. V3 result/audit hashes:
  `54daa95943ab19e10fb540a4cc71a70217cb409a21ff7fb804b60386a98e0690` /
  `054c85503c88f62c27bf8e6f1b1c691a9a07215e59f4c7588576eac3ac7aef66`.
- Froze and audited the S2 development payload protocol before a numeric query. The
  first one-shot response failed exact schema validation and persisted no payload.
  The immutable failed result/failure-audit hashes are
  `38c151ef24be8987eaa970d1bb0dbb2657ec414b4898e8a1002360185ceda899` /
  `2685797df5497fbd709179385d7a1d9e8565698fe04faa42bdcc2b24b9d564e8`.
- Froze a v2 amendment limited to casting the aggregate fee to `INT64`. Its one-shot
  query acquired and independently audited 280 causal weekly development rows under
  the frozen 60 GB ceiling. Passed result/payload/audit hashes:
  `a50c3c69ebfdcabcce5ea9998c5eea60db8ae74756d05fe6b9460564b247094a` /
  `fc436388a09ad097829a2edcea4d2789403493a14425b35355a9a50a05eaf070` /
  `edc724a48b7cd0f7726ae1cec925bd379738bf78ba152f7077f2a3b3b5ffb719`.
- Added API verification for the complete v1-failure/v2-success payload lineage and
  advanced the runtime checkpoint to `S2_DEVELOPMENT_PAYLOAD_V2_PASSED`.
- Generated and independently audited readiness v19 at 14/15 PASS, one downstream
  PARTIAL, zero FAIL, zero qualified strategies, and zero orders. Result/audit
  hashes:
  `ff3a049b8cc054d2e2253d3ea64e7444b6c2acd3637caa60a692560fa59a2a10` /
  `eeb404262d0eb710c8e29fc00061e11691f6443afa4a29bbda55f23fdab86300`.
- S2 feasibility/payload verification passed `49` tests; readiness integration
  passed. Exact next authority is measurement-protocol design only. Prices,
  parameters, returns, Pine, paper, Testnet strategy orders, production, live, and
  real capital remain locked; real net profit remains `$0`.
- Repository-wide Ruff passed. The combined S2/readiness chain passed `50` tests,
  and the complete repository suite passed all `1354` tests in `665.82s`. Only the
  existing pytest `cache_dir` and Starlette/httpx warnings remain.
- Started the v19-backed runtime at `127.0.0.1:8924`. API verification reports the
  payload checkpoint and source integrity true with every execution mode false.
  Desktop `1280x720` and mobile `390x844` browser QA found no page overflow or
  console errors; the measurement-protocol next action remains readable.

## 2026-08-30 - S2 development measurements frozen, run, and audited

- Froze and independently reconstructed the S2 development measurement protocol
  before parsing payload values. Protocol/audit hashes:
  `dedb2d9a0fb23d6a943d290c36333107adf3ef873754d2b8572ac3692377a17b` /
  `3a72c31dd90db8aa0b307972e70f33b7a3b0909956888c3052666343462edd0e`.
- Implemented exact integer/Decimal PPM measurement construction, synthetic causal
  window and failure tests, and deterministic JSONL serialization. The combined
  pre-run protocol/runner boundary passed `35` tests.
- Froze and audited one-shot payload-only execution authority before reading the
  280 numeric rows. Addendum/audit hashes:
  `2f7522cb652d888d8494a2552a01f2b6b20412e442544e978f429b070218b0d7` /
  `9176539c110987c109c709d8d9b59c97b1472f5ec5ba8a274262deccfe6b544b`.
- Produced 273 deterministic measurement rows and independently reproduced them
  byte for byte. Dataset/result/audit hashes:
  `513237db0a939170efb2113444fdd633a5c5dc1b397b8022b154020cfdf4b327` /
  `8e4534468b2f471b56e4b7d3391a08f1299b6d0079c8fc4b3ae4880630977f3b` /
  `3af9c1b2332932f6064fe9ccc1172b888e14abe53cd529abcd4c0c930e913523`.
- Generated and audited readiness v21. Result/audit hashes:
  `2829175094ceecdc98f9f93eae7d7126ddfb6f54b64b60d4cd5156262bab4f12` /
  `e0980b16b8e25a314baa1905134c9167f504a7a311754ba882aab6fdc359848f`.
- Post-run tests prove the consumed execution addendum cannot be rebuilt or reused.
  Market values, parameters, returns, candidates, signals, orders, and profit remain
  zero. Exact next authority is strategy preregistration protocol only.
- Repository-wide Ruff passed; the focused measurement/readiness chain passed `36`
  tests; and the complete repository suite passed all `1389` tests in `575.12s`.
  Only the existing pytest `cache_dir` and Starlette/httpx warnings remain.
- Started the v21-backed runtime at `127.0.0.1:8925`. API and desktop/mobile browser
  QA verify the strategy-preregistration checkpoint, no overflow or console errors,
  zero qualified strategies, and all execution modes locked.

## 2026-08-30 - S2 single strategy preregistered before BTC outcomes

- Froze one zero-parameter long-or-cash candidate before parsing measurement rows or
  reading BTC prices. Protocol/audit hashes:
  `5d6cd308ad31cfc22588760c8890b97d49bcce95682bcb563397fe19acfa7a6c` /
  `d71184f3b0bd674f8a55750c174e01a23c9d76c7882d4d6c111c37ff92aa67c9`.
- Fixed exact Monday execution dates, base/stress costs, 272 scored intervals, one
  candidate/combination, no diagnostics, and 15 development falsification gates.
- Generated and audited readiness v22. Result/audit hashes:
  `397d4971bb087f919ca106caa4c265e2bd8fc6aef794f2258788661d4e8acdfa` /
  `bc00e9866ddbc74f4f0e7198f3ba8f86f6c29d1b55a8f6a6b0461d6d959899ba`.
- Targeted preregistration/readiness verification passed `18` tests. Market values,
  returns, candidate outcomes, orders, and profit remain zero.
- Started the v22-backed runtime at `127.0.0.1:8926`. API and desktop/mobile browser
  QA verify source/checkpoint integrity, no overflow or console errors, zero
  qualified strategies, and every execution mode locked.

## 2026-08-30 - S2 BTC development backtest failed and lineage retired

- Froze and audited the 273-target Binance Vision BTC source protocol with zero
  market-value reads during protocol construction. Protocol/audit hashes:
  `a8d07b3ff6395ad5d08b9c50638c6d1b01453073d9392000d8583fd2be5b5610` /
  `362ab972301087a05635b7cc43ec929c0b0dca1e2b8d76de7e725ad2ee0f7eb4`.
- Implemented and synthetically tested the bounded checksum, archive-safety,
  timestamp, schema, interruption-recovery, and deterministic-dataset runner before
  freezing one acquisition authority. The source contract/audit passed with hashes
  `6cb6e05dd7321970403c918eaf26037014a895ab7b96aefb11da977098311b13` /
  `9b368e2419b8bbe45e65e5f1054a4f3c104cfb0e7227ce8de043fc43b90ba0ce`.
- Acquired all 273 exact Monday opens in 546 requests with zero failed target. The
  independently reconstructed result/dataset/audit hashes are
  `6ba8c88d62c92f36696032f4fbd7697cf43369e1ace4050cf109086dcd76f3cd` /
  `6c9c09c8b6a4c484f64a366a8b66a1e939d198894117f9f91b01ea12024af156` /
  `8b2e6ec3aa26ea0e282051fd76a157550750c92c9d88fd1ba058e219c7d1db10`.
- Froze and audited the S2 backtest protocol before computing returns, then tested
  exact fills, costs, profit factor, drawdown, Sharpe, CAGR, Calmar, bootstrap,
  alignment, and all 15 gate mappings. Protocol/audit hashes:
  `c2f105dd9d350c0a45c2d00b29bf6e744b5dac75edb9bd8cc8aa3f7f1e8f8be8` /
  `2f728ce14b96901460ce1097d6346c947febb1b8d8af97b355dd207a963bc965`.
- Froze one-shot execution only after the 17-test runner contract passed. Execution
  contract/audit hashes:
  `e954fd8d487117c8ab649bdac5bf1241040c28a8d5007c99dbbda9d967ec784f` /
  `4056d01cee712598b2e3453d580b29cb98af1876e6b0b6dad6774c0bbde9a95e`.
- Ran S2 once. It passed 9/15 gates and failed base profit factor, base/stress
  drawdown, positive calendar years, stress-bootstrap lower bound, and base Calmar.
  Result/ledger/audit hashes:
  `a9661515cbbb584ceaa8894c250f31916d8e35e9e67ea4670b21226c9a99eb54` /
  `792a9abe0fa57e3e69af2532a0489eb918733547da66716b9b567d644e23e984` /
  `c59985486e9ccc46191161f9e42d9b7b9a3ae11482720d51fe42ef45d16d0e86`.
- Recorded terminal decision `STOP_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2`.
  Despite positive total return, the edge and risk evidence are unacceptable. S2
  has no rescue authority and cannot advance.
- Added API verification for the complete preregistration, source, backtest, ledger,
  and audit chain. Readiness v23 must keep zero qualified strategies, zero orders,
  `$0` real net profit, and every execution mode locked. The next research step is a
  distinct S3 charter, not S2 tuning.

## 2026-08-30 - S3 CFTC positioning charter frozen before position values

- Audited the full exhausted-family lineage and selected one distinct successor:
  weekly CFTC TFF futures-only leveraged-money net-position changes for CME Bitcoin,
  expressed only as a future BTCUSDT Spot long-or-cash research hypothesis.
- Bound 12 predecessor artifacts, 8 official or peer-reviewed sources, 10 exhausted
  mechanism families, and 6 contiguous research partitions. The published 2018
  through July 2021 leveraged-money timing result is explicitly contaminated and
  cannot qualify S3.
- Froze and independently reconstructed the S3 charter before reading CFTC position
  values or BTC outcomes. Charter/audit hashes:
  `2cf73ead1b04999c3b5f9f818bb60d18ad96d2041fae2d65d77084aa88e4802a` /
  `f746adc212d5e41f66507a372d60824bdb84609e50b05e797a6116b60d39c90b`.
- Added tamper tests for position-value authority and partition continuity. The S3
  charter suite passed `8` tests; focused charter/readiness verification passed `9`
  tests with only the existing Starlette/httpx warning.
- Added fail-closed API verification for the charter, audit, terminal S2 chain, all
  predecessor file hashes, zero-value fields, and locked execution authority.
- Generated and independently audited readiness v24. Result/audit hashes:
  `fd8e0d0d38169a18f018d722ff4e60423c1f18b23152a880b0f90aec2977baa0` /
  `eae481ece180c6d5fcecb9cfe309df9916c25c51ff62ba06c2e0ff8390909afe`.
  It remains 14/15 PASS, one downstream delivery PARTIAL, zero FAIL, zero qualified
  strategies, zero orders, every execution mode false, and `$0` real net profit.
- The only next authority is
  `AUTHORIZE_S3_CFTC_SOURCE_METADATA_AND_POINT_IN_TIME_FEASIBILITY_PROTOCOL_ONLY`.
  Position values, market values, parameters, returns, candidates, Pine, paper,
  Testnet strategy orders, production, and live execution remain locked.

## 2026-08-31 - S3 source feasibility not established; lineage retired

- Froze and independently audited a metadata-only S3 point-in-time source protocol
  before requests or numeric CFTC access. Protocol/audit hashes:
  `1d9e2b672b754c3e6d7296fc3c75fd8d7ab4f49e445b06383ec4e1722271c15a` /
  `bbea600436e66ee35e809a323c0f83bdbdfe948e352c4f2f4fa1add03999d7c1`.
- The first restricted-network run recorded three `NETWORK_ERROR` attempts and no
  response artifact. Result hash:
  `75700f67e97577d7680b97b6bedf28539c9815eb1bf424764d30094b73fe53d8`.
  Because no CFTC response existed, a separate audit rejected its nominal source-
  failure verdict as transport-only. Failure-audit hash:
  `704373d76fc38d794ef43b96b6ad9d13b3839ec65b11a2394e584ceceb34cef5`.
- Froze and audited one transport-only amendment with unchanged URLs, tokens,
  gates, and three-request ceiling. Amendment/audit hashes:
  `dc3b2acdf29878250a28edb5f951b04b09e78e5f96110798f28f187fe8a2dda9` /
  `dcd641b6febf4d93546f79f8113a8d5c3409d0b5984c6faf150f86913e30ffc6`.
- Ran the one authorized external-network retry. It exited `1`, did not obtain all
  three required responses, and wrote no v2 result or response body. The durable
  receipt preserves the partial-success count as `UNKNOWN_NOT_PERSISTED` instead of
  inferring it. Receipt/audit hashes:
  `166e3039f51e95046ab2030eeee383e5d9cdfaa046e9fffe366b636dfc5e7d23` /
  `915cc64207adb02e77efb31fb693db1970e0be612b89b51e227be8d7368bfba2`.
- Recorded terminal decision
  `RETIRE_S3_SOURCE_FEASIBILITY_NOT_ESTABLISHED_WITHIN_FROZEN_PROTOCOL`.
  This does not claim source impossibility or evaluate predictive edge. The rerun
  authority is exhausted and S3 cannot be rescued, loosened, or backtested.
- Added API verification for the complete charter/protocol/transport/amendment/
  receipt chain, source hashes, absent v2 artifacts, exhausted authority, and zero
  numeric/execution access. Added the durable S3 record in
  `docs/43_S3_CFTC_POSITIONING_SOURCE_FEASIBILITY.md`.
- Generated and independently audited readiness v25. Result/audit hashes:
  `a21f0a7afa76f274523ba75e3a077fabb4fa98938162e09ef3839f52a492a362` /
  `031a2471668222a94b294b1d1d1dacec80634d48b064f01829bbdaa5ebf1c5b1`.
  It remains 14/15 PASS, one downstream PARTIAL, zero FAIL, zero qualified or
  enable-eligible strategies, zero orders, and `$0` real net profit.
- Focused S3/readiness verification passed `16` tests. Repository-wide Ruff and
  `git diff --check` passed; Git emitted only existing LF-to-CRLF notices. The full
  repository suite passed `1491` tests in `5643.14s`, with only the existing pytest
  `cache_dir` and Starlette/httpx warnings.
- Started the v25 runtime at `127.0.0.1:8929`. The API and rendered desktop
  dashboard report source/checkpoint integrity true, status
  `S3_CFTC_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRED`, 14/15 PASS, all execution
  modes false, and next action
  `FREEZE_AND_AUDIT_DISTINCT_S4_MECHANISM_CHARTER_ONLY`. Desktop `1280x720` had no
  horizontal overflow. The selected in-app browser did not expose viewport
  mutation, so this checkpoint makes no fresh mobile-layout claim.
- No CFTC position value, BTC market value, parameter, return, candidate, signal,
  execution, or order was created. Paper, Binance Testnet strategy use, production,
  live trading, and real capital remain locked.

## 2026-08-31 - S4 spot Bitcoin ETP mechanism charter frozen

- Selected one distinct primary-market mechanism after S3 retirement: complete-
  universe U.S. spot Bitcoin ETP net creation/redemption pressure with cross-fund
  breadth, expressed only as a future BTCUSDT Spot long-or-cash candidate.
- Bound 20 predecessor artifacts, 11 exhausted mechanism families, 8 official SEC,
  issuer, and SEC-filing sources, and 6 contiguous partitions. The design separates
  the 2024 cash-only regime from the `2025-07-29` SEC in-kind authorization and
  requires every fund's actual operational effective date.
- Froze and independently reconstructed the charter before reading ETP values or
  BTC outcomes. Charter/audit hashes:
  `8827763c7b1d71255ceff1859c0e69835403c7653ead6ad6f233edae5b9c08b4` /
  `1e083ef726bfb46cb1d37f15b5c9c16b00562a3c2923a8b0907749ebd7bffbc7`.
- Disclosed four incidentally observed issuer field names. Parsed zero ETP time-
  series rows and numeric payloads, inspected zero BTC market numeric fields, and
  created zero parameters, returns, candidates, signals, executions, or orders.
- Added fail-closed API verification for every predecessor hash, source and
  partition count, cash/in-kind declarations, incidental field disclosure, zero-
  value boundary, audit lineage, and locked execution authority.
- Generated and independently audited readiness v26. Result/audit hashes:
  `dc74c231794432335ea3fceb525dd3e336c37e108763ee6cba595b4a69f4ee8d` /
  `ab0d3e55cf04ec5f201c0e874b4487912be5ac3f9db6691d64cef76e6b912b15`.
  It is 14/15 PASS, one downstream PARTIAL, zero FAIL, zero qualified strategies,
  zero orders, and `$0` real net profit.
- S4 charter and integrated readiness verification passed `9` focused tests; Ruff
  passed. Runtime now requires a frozen metadata and point-in-time feasibility
  protocol. ETP numeric values, prices, returns, Pine, paper, Testnet strategy
  orders, production, live execution, and real capital remain locked.

## 2026-08-31 - S4 infeasible protocol design stopped before network

- Froze and independently audited the five-static plus 32-dynamic-request maximum
  S4 SEC metadata protocol. Protocol/audit hashes:
  `6c0415149eabf9c22c60854a35b563a26b68b2746899cd53a17e08fac79883bd` /
  `68f6ef9529dbd8f2a62fc690dd4c29cb699994149a3b84aafb0ff0e4ab70a258`.
- Added a durable every-exit result contract requiring exact planned, attempted,
  successful, failed, and persisted-response counts. Synthetic transport failure
  tests prove partial outcomes cannot disappear or become unknown.
- Detected before execution that six mandatory source gates are unreachable from
  the allowed SEC identity surface while issuer bodies, filing bodies, and XBRL
  facts remain forbidden. Recorded and independently reconstructed the design-stop
  review. Review/audit hashes:
  `1837ce1e7fb36edeee235d0270043455fa7a3e3e005d183141c6376b4d4f23ff` /
  `a656f8a605c1dc1be0d599aa5b74d41ef1dd2f0e7fb073f81b8639b8855b0696`.
- Stopped the protocol without a network request and without consuming its one-run
  authority. This is not a source-unavailability or predictive-edge conclusion.
- Generated and audited readiness v27. Result/audit hashes:
  `691b04e6bbf7069094a7c3dbd039439f78a2b2c2accd3947f8aebbb7db741efe` /
  `6ee5c34d911a3756d89e9050f3f2813293f659ee314c00f2dee229b776879134`.
  It reports the terminal S4 design checkpoint, 14/15 PASS, one downstream PARTIAL,
  zero FAIL, zero qualified strategies, zero orders, and `$0` real net profit.
- The combined S4 charter, protocol, viability, and runtime verification passed
  `23` focused tests with only the existing Starlette/httpx warning. S4 has no run,
  amendment, payload, backtest, paper, Testnet strategy, production, or live
  authority. Only a distinct S5 mechanism charter is authorized.

## 2026-09-03 - S5 GitHub metadata bulk acquisition completed and audited

- Froze and independently audited a 300-attempt, unauthenticated, serial GitHub
  bulk-acquisition protocol. Protocol/audit hashes:
  `ee1564712af978eddd0081fe7ede7fb19dd275fc2f04e7a19306160f8b3174f5` /
  `0643d3dceb5e4bc763fc3f5c551d8bfa3576f5cecac415cda91fbba4f64f4b55`.
- Preserved three immutable STOPs: an httpx context-manager defect, host suspension
  after 117 pages, and a valid page-118 response whose terminal count grew from
  244 to 245. Their result/adjudication hashes are recorded in the canonical
  project-control addendum; no STOP was rewritten as a pass.
- Froze and audited a narrow v4 amendment that promoted the already preserved page
  118 with zero requests and allowed only bounded, nondecreasing terminal growth.
  Amendment/audit hashes:
  `db23014df1fedcc4562e2ef927da4a77ee08402830c6461f60d3ce004825e187` /
  `ed9fe2a2cf7398d8c1110a6a92dd0092b4b667928f34f5eaa62ce10070bbed6b`.
- Completed and independently reconstructed 245 canonical pages containing 24,407
  unique creation-ordered pull-request records. The frozen cohort contains 24,398
  records and excludes nine post-cutoff records. The terminal page contains seven
  records, all 16 gates passed, and total historical request usage is 246.
  Result/audit hashes:
  `3c2bd020ee115e0d28e75fc80c977ffef2a4bad8ac6ad4cd5f4219380a25e082` /
  `cc1a4604a6d8c2819dd629900374f60cbac7ff50499eb14af34f63c2bc1acc29`.
- Added a fail-closed API verifier for all amendments, historical failures, runner
  and auditor contracts, exact artifact set, and every canonical page-file hash.
  The full S5 checkpoint verifies in approximately six seconds on this host.
- Generated and independently audited readiness v34. Result/audit hashes:
  `e01b352bbe52441a22bf3e3fe5a708fb3e8dd38e4c745cb0513725945922f616` /
  `460f993de0d380135c2b8e527bf8d89a9df9281e85aa4c82a74e97573daad87c`.
- Focused S5 pagination and runtime verification passes `17` tests. Readiness
  remains 14/15 PASS with authenticated external TradingView delivery partial,
  zero qualified strategies, zero orders, all execution modes false, and `$0` real
  net profit. Only normalization-and-completeness protocol design is authorized.

## 2026-09-08 - S5 corrected normalization completed and independently audited

- Preserved the original normalization STOP and two targeted-correction STOPs.
  The investigation proved that one accepted pull per first-parent merge is not a
  valid universal invariant; no failed artifact was rewritten as a pass.
- Completed the bounded v3 targeted acquisition for the exact 194-record correction
  union. It preserved 186 HTTP 200 and eight HTTP 404 responses and recovered 75
  recognized mappings by exact Git second-parent-to-GitHub-head identity. Result/
  audit hashes:
  `e7c059f0a01998e2af13b72c1ee4d5a6c01f05184f79c3b915dac619f08e2d50` /
  `5e6c1f1b7dfd5a28395ec28a0f9cfed08ad053203edacaeb38628687c7edacac`.
- Froze and audited a corrected normalization protocol that separates GitHub
  accepted events from canonical first-parent integrations, retains uncertainty,
  and never guesses canonical ownership. Protocol/audit hashes:
  `d8a6c5bf331c75a127e47f63c3e2f14c6d3a1292f9015666009da3a1b106bc95` /
  `b664ae816c730550f7876aaba41c7090797b848bfdfeaf9c2c0fa420d36fff8c`.
  Execution contract/audit hashes:
  `9a374dc928e74d3708e587ed5e9eec436225dc560f35d62b036c277a69779477` /
  `bec0bd3756616fe3161b74f18318111dc0d9a4bd55365c9af65114f552f8ced6`.
- Ran the corrected normalization once. All 19 gates passed, producing 24,398
  normalized pulls, 16,242 canonical mappings, 194 target resolutions, 16,279
  accepted-source coverage rows, and 479 unresolved merges. Exactly 16,271 accepted
  events have verified local source linkage; eight remain explicitly unverified.
  Result hash:
  `a205e0759b235fae0810ae9203afa4dd81087f52ce782cd4e8c00c670fdd45a5`.
- Added an independent result auditor that strictly parsed and rehashed all 57,592
  rows, reran exactly two Git processes, and rebuilt all outputs and the result
  byte-for-byte. Audit hash:
  `d0d66d194c6136164999341f5e044bf60d8f2e7b585531a863ba599d54254648`.
- The full S5 source-through-normalization unit set passes `129` tests. Network
  requests, BTC value reads, return calculations, candidates, and orders were all
  zero. Qualified strategies remain zero, all execution modes remain false, and
  real net profit remains `$0`.
- Added the durable S5 record in
  `docs/45_S5_BITCOIN_CORE_ACCEPTED_DEVELOPMENT_BREADTH.md`. The only next authority
  is `FREEZE_S5_ACCEPTED_DEVELOPMENT_MEASUREMENT_PROTOCOL_ONLY`.

## 2026-09-08 - S5 measurement protocol frozen; first run rejected in audit

- Froze and audited a 17-field, 212-month measurement protocol that keeps primary
  accepted events, all-accepted sensitivity events, and canonical Git integrations
  separate. Protocol/audit hashes:
  `0d4f9dbc73675a0e625971a9a53181bcd4a2b707ebe02f01a28edfc4c65478d0` /
  `0b6ad1358d206822ab530447bc184dfb98ecd12d209e8cd8c2f3675f17c70064`.
- Implemented the runner, validated its exact Git framing on a disposable repository,
  and froze/audited its three-process execution contract. Contract/audit hashes:
  `da08133f957e4129421e5e708b93c87212d4273b3da8bdc1daed5b62e86a0154` /
  `68a683dc72b1292131929af5ce1f23ef960bd672d7525bd09afbbaef69ca7c71`.
- The one authorized run emitted 212 internally consistent rows in 7.250 seconds.
  Output/result hashes:
  `56a54bee72f77102e21c03975eb7a32e95b8eb2ff68882dd32fbe8a01f8bddd8` /
  `6d0d3efc7da6dc5d909bea7bca0e892e8ea45c8ab9541c521109d644b85d7c3c`.
- The independent result audit found that the source repository was cloned with
  `tagOpt = --no-tags` and contains zero tag refs. It rejected the nominal PASS
  because absent release metadata had been serialized as zero release activity.
  Rejection audit hash:
  `e8b8970a7af07f2298f4b1cf9e53d656c6dc0bcd7396838968ffda915ea5afdd`.
- No BTC value, return, parameter, candidate, signal, or order was created. The sole
  next authority is `FREEZE_S5_RELEASE_TAG_SOURCE_REMEDIATION_PROTOCOL_ONLY`.

## 2026-09-26 - Complete S5 Measurement And Rebaseline Delivery

- Completed the independent audit of the 132-tag repair, preserving the rejected
  42-tag repair and original missing-tag result. Complete-source audit hash:
  `f224e7b99256ac04b0ffd8762076cd75f528e7cb88dd402371a2e126ab128e6c`.
- Froze and checked the amended measurement protocol and implementation; ran three
  local Git commands. Produced 212 monthly rows and all 132 release rows. Every
  non-release value matches v1. Result hash:
  `69d42d1c9e8754d8fa43a0b4ea1aa5cd52904f150c1475e25a572cba34e39c71`.
- Independently reconstructed all monthly arithmetic and output bytes. Audit hash:
  `37f27c2ddfb81aaad18424aaa6ed9224da5fe086bb4f8490514caba0c796cfd1`.
- Updated the working goal and exact resume point. S5's frozen future holdout ends
  2027-11-07, so it is retained as long-term research and additional outcome work is
  deferred while operational delivery evidence is closed.
- Corrected historical package reconstruction tests to use recorded Python metadata;
  the installed runtime changed from 3.12.13 to 3.12.14. Preserved the actual R3
  execution runtime guard and all historical source, package, and result hashes.
- Added a hash-verified current measurement checkpoint to readiness. Missing or
  changed evidence fails closed. Current v36 readiness includes the new verifier
  and its tests in the source manifest; all strategy execution modes stay locked.
- Focused verification: 194 S5 unit tests, 13 historical-package tests, 2 readiness
  integration tests, and 70 pipeline/risk/paper/parity/dashboard integration tests
  passed. Repository-wide Ruff passed. The entire repository suite was not rerun.
- Recorded the execution-evidence inventory and next bounded webhook proof work in
  `docs/46_AUREX_DELIVERY_REBASELINE.md`. No strategy was qualified and no orders,
  real-capital operations, network acquisitions, or profits were created.
