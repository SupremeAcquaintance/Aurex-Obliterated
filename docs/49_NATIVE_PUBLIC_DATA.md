# Native Public Market Data

Checkpoint: 2026-10-08. Scope: read-only acquisition and offline reconstruction,
not a trading runner or strategy qualification. Canonical scheduling: docs/10.

## Contract

`src/aurex/signal_gateway/native_market_data.py` uses the fixed HTTPS origin
`https://data-api.binance.vision` and only `GET /api/v3/time` plus
`GET /api/v3/klines`. There are no credentials, order methods, alternate hosts,
redirects, environment proxies, database writes or automated retries. TLS uses
normal certificate and hostname verification. A 418/429 or other non-200 status
stops the call; the sanitized exception carries an integer Retry-After when valid.
A future supervisor must respect that delay and must not loop on these errors.

The contract was checked against Binance's official documentation on October 6:
- [Market-data-only endpoints](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md).
- [REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data).

BTCUSDT, 15m and UTC are fixed. Requests carry exact start/end milliseconds and
an explicit count. The API's maximum page size is 1,000; Aurex permits 1-4,096
candles per acquisition, at most five pages. Each row must have the documented
12 fields, expected open/close milliseconds, integer trade count, finite decimal
strings and valid OHLC/volume geometry. No sorting, deduplication, gap fill,
partial success or microsecond guessing is performed.

Server time must lie within the local request/response interval plus a two-second
tolerance. Only candles closed before the earlier server/local request time, minus
a further two-second close delay, are requested. Existing entry freshness limits
are separate and unchanged. An explicit historical request is permitted as data,
not as a retroactive entry or forward-paper observation.

Transport uses a ten-second socket timeout and rejects completed requests taking
over ten seconds. A blocked socket operation can take until its timeout; this is
not a hard real-time cancellation guarantee. Whole acquisition is checked against
a 90-second budget. Bodies are capped at 512 KiB per response, retained artifacts
at 8 MiB. Non-JSON, compressed, duplicate-key, malformed, oversized or invalid-UTF8
responses fail closed. Wall-clock jumps and inconsistent page timing also reject.

## Retained Evidence

`PublicCandleEvidence` records exact response text and SHA-256, exact request URLs,
local request/receipt times and monotonic elapsed times, stream scope and canonical
normalized-candle hash. `verify_public_evidence` re-parses every retained row and
reconstructs the normalized history without network or DB access. Default HTTPS
acquisition and injected transport/clock fixtures have different labels.

Labels and local hashes are not cryptographic origin signatures. Whole-artifact
replacement by an administrator is outside this check's guarantees. Offline
verification proves consistency of recorded evidence, not a live TLS session,
ongoing availability, economic edge or a qualifying forward observation. The
native processor's `source_origin_verified` remains false. The one-shot acquisition-owned
path records operational call lineage, not signed authentication or a qualified forward
campaign. Retained binding alone does not supply that lifecycle. No fixture may be
relabelled as real outside explicitly synthetic tests.

Writes use exclusive creation and fsync; existing files are never overwritten.
This is not an atomic processor commit. A failed or interrupted write is not
accepted merely because a path exists. Truncated files fail reconstruction; a
complete file left by an fsync/acknowledgement failure still grants no authority.
The CLI reports PASS only after write and readback verification.

## Entry Points

These are reference commands for the agent/operator, not a request to run them now:

```powershell
.\.venv\Scripts\python.exe scripts/check_native_public_data.py --count 1000 --output data/evidence/NEW_UNIQUE_NAME.json
.\.venv\Scripts\python.exe scripts/check_native_public_data.py --verify data/evidence/NEW_UNIQUE_NAME.json
```

Optional `--first-open` specifies an aware UTC-aligned historical open. The default
selects the latest fully closed window after the close delay. Verification performs
no acquisition. Neither mode opens the operator DB, resets an account, migrates,
submits a signal/order or enables a strategy. A blocked check returns exit code 1.

## Operational Check

The October 6 public attempt reached the HTTPS time endpoint but **did not pass**:
`public_server_clock_skew`. A subsequent retained response was about 7.75 seconds
ahead of the local receipt time. Diagnostic:
`data/evidence/native_public_clock_blocker_20261006_v1.json` (Windows PowerShell
UTF-16LE report, not a successful candle artifact). No candle page was requested
after the failed clock guard and no real candles were accepted.

Read-only Windows inspection reports a domain-managed time source. No time service,
registry, policy, server or system clock was changed. A source can also
have a bad clock; the measurement establishes disagreement, not which clock is UTC.
Do not raise the tolerance or substitute a fabricated/injected clock to get PASS.

The October 8 recheck passed the unchanged clock guard, fetched one closed candle,
and passed separate offline reconstruction. Retained artifact:
`data/evidence/native_public_probe_20261008_v1.json`, file SHA-256
`9078183e309cdd971cf78d5f77c563ccc239658bd1a2ff05776ba2ac6a639804`.
Time request/receipt: 11:26:39.783102 / 11:26:42.212949 UTC. Candle open: 11:00 UTC;
receipt: 11:26:43.895326 UTC, 703.895326 seconds after its close. This exceeds the
separate 180-second entry window and was not submitted to any native stream.
No operator database, migration, signal or order was involved. The old measurement
remains historical; the latest diagnostic passes, but does not prove lasting clock
agreement, continuously timely acquisition, source authenticity or forward readiness.

## Native Receipt Binding

`NativeBarProcessor.process_sourced(evidence, scope=..., purpose=...)` now persists
the complete `PublicCandleEvidence` packet and a canonical JSON acquisition hash
inside a versioned v4 native receipt. That acquisition hash is not the outer file's
byte hash; individual response bodies retain their original byte hashes separately.
The source, bar outcome, seed/checkpoint and any recovery effects commit in one
SQLite transaction. A separate file is not needed to reconstruct committed input.

Purposes are explicit:
- `SEED`: a fresh-ending warmup window, bound to the initial retained seed and its
  checkpoint. It cannot reset an initialized stream.
- `CLOSED_BAR`: exactly one contiguous fresh closed candle, outcome
  `SOURCE_OBSERVED_NO_ENTRY`. This records observation, not a strategy decision.
- `RECOVERY`: exactly one contiguous candle for existing exit-only recovery. It may
  be stale, cannot initialize a stream and never becomes qualifying forward data.

There is no signal/entry argument on this path. A receipt cannot grant origin,
entry or qualification authority merely by labelling a packet `public_https`.
Injected packets require fixture stream scope; the public label is retained only
as untrusted metadata on this reconstruction path. It does not attest to a live
TLS session. Existing strategy retirement and live-disabled controls are unchanged.

Every chain audit re-parses raw responses and verifies scope, raw/canonical hashes,
normalization, receipt time, processed candle and seed checkpoint. Known retries
must provide the original packet and purpose. A newly fetched packet with different
request/receipt timing does not replace a committed witness even if OHLCV matches.
A future supervisor must inspect retained state after ambiguous acknowledgement
and retry the retained witness or move to the next unprocessed candle.

Once attached, source tracking cannot silently disappear on new raw processing or
recovery calls. Legacy receipts remain unchanged; attaching source later does not
retroactively authenticate unbound seed/history. Old unchanged retries still work.
v4 supports both the legacy prefix and bounded indicator continuation; v1-v3 bytes
and hashes are preserved. No additional migration is required. The operator DB
has not been migrated or populated by this work.

## Acquisition-Owned Observation

`NativePublicObserver(engine, settings).observe(scope=..., seed_count=1000)` is an
opt-in local service, not an HTTP endpoint or a daemon. It accepts no candle packet,
client, URL, clock or transport argument. It constructs the default public HTTPS
client itself, with the existing fixed-host, clock and body checks. The scope must
be `binance_spot_public`; live trading and its adapter must remain disabled.

The observer audits a consistent SQLite read snapshot and closes that transaction
before network I/O. An uninitialized stream waits for a fresh-ending seed window;
an initialized stream requests exactly its next contiguous closed candle, never
the latest candle over a gap. Polling before the two-second close delay returns
`WAITING_FOR_CLOSE` with the next due time and no acquisition or ledger writes.
Missing the 180-second admission window of an initialized stream fails closed and
requires reconciliation; it does not automatically backfill or invoke recovery.
Open positions are rejected before acquisition and rechecked during processing.

On successful acquisition, v5 receipts commit source, observation timing, expected
previous receipt hash, seed/checkpoint and no-entry outcome in one transaction.
The write transaction checks the planned head again. Identical concurrent witnesses
are idempotent; different witnesses or changed heads reject. No network lock spans
acquisition. After lost acknowledgement, a new instance audits retained state and
waits for or requests the next unprocessed candle; it does not refetch and overwrite
the committed packet. Source files are not required for resume.

The public imported-packet path cannot supply online admission metadata or retry
an online receipt as an import. Once online admission appears, normal new records
cannot drop it, even after an explicit recovery interval. Recovery still has no
entry or qualification authority. Existing source-bound imported history can be
continued, but its earlier receipts are not rewritten or retroactively attested.
Unbound history is not automatically promoted. v1-v4 canonical bytes are preserved.

This is an operational boundary for trusted application code, not a Python sandbox
or cryptographic signature. Monkeypatched local code and wholesale administrator
rewrites are outside its guarantees. Fixtures exercise the path with mocked clients
in disposable databases only. `source_origin_verified`, `forward_qualifying` and
execution authority remain false. The observation-only method supplies no entry or exit;
the explicit exit-only method is described below. No strategy evaluator,
scheduler, operator migration, accepted real feed or paper campaign is supplied by
this service. Errors propagate to its caller without automatic retries or background
tasks; supervision and operational stop/alert policy remain unfinished.

## Acquired-Candle Paper Exits

`NativePublicObserver.manage_exits(scope=...)` explicitly manages one next fresh
closed candle in an initialized stream. It cannot seed, accept an imported packet,
submit a signal, open a trade or use stale recovery as a fallback. It uses the same
default acquisition client, freshness and expected-head checks as observation.
The ordinary `observe` method still rejects open positions instead of silently
choosing a management mode. A supervisor must make this choice explicitly.

Versioned v6 receipts retain `ONLINE_EXIT_NO_ENTRY` and a FLAT, HELD or CLOSED
management record linked to the exact acquisition hash, original entry receipt and
frozen costs. Source, outcome, trade/position/account changes, equity point and
checkpoint commit together. Retry mode changes reject; identical witnesses are
idempotent. A new instance after lost acknowledgement reads retained state rather
than closing twice. v1-v5 canonical evidence is unchanged; no new migration exists.

Management reuses the existing conservative replay brackets and paper cost engine.
It recognizes realized P/L at current processing time, never an invented intrabar
timestamp. Stop/target ambiguity is adverse, price gaps are explicit, and partially
observed entry candles cannot claim pre-entry target touches. Such partial stops
use a documented adverse price bound. These are OHLC-model assumptions, not actual
exchange fills or guaranteed stop prices.

Live execution must stay disabled. Entry kill switches or a disabled strategy do
not prevent this explicit exit-only path. Unreconciled quantities, costs, account
equity, orphaned/open records or missing management intervals fail closed. The
receipt auditor reconstructs outcomes and checks ledger linkage before commit.
Recovery quarantine stays permanent for a position across later online steps;
unrecorded held-position/model changes reject.

The new `native_ohlc_online_exit_v1` model is deliberately outside the qualifying
paper fill-model allowlist. Existing `native_ohlc_recovery_v1` quarantine is never
upgraded. Legacy native paper entries may be managed without rewriting or attesting
their old history. `source_origin_verified`, `forward_qualifying` and entry authority
remain false. No eligible strategy, genuine online acceptance, live order or unattended
availability follows from these fixture-tested mechanics.

## Bounded Jam Feature Arithmetic

`native_jam_features.py` supplies a pure fixed BTCUSDT 15m/60m feature state. Explicit
lengths (1-500) bind trend/pullback EMA, ATR, volume SMA, DMI/ADX and local-reversal
lookback. It retains previous ATR/pullback and the candles needed by Jam's existing
two-bar pattern. Current complete-hour EMA values become visible only at the next
hour's :00 candle; an initial partial hour is excluded. Completed-hour warmup counts
still match the replay, which counts a full hour at :45 even before it becomes visible.

Initialization accepts 1-4,096 contiguous candles, including an unready warmup prefix.
Continuation accepts exactly the next candle; repeats, revisions and gaps reject.
The retained candle tuple is at most 501 rows; each RMA retains fewer than its length
of seed samples and discards them on initialization. Missing DX retains ADX state
but exposes no ADX value for that candle, exactly as replay. Decimal28/half-even is
required, and serialization preserves exact values. Readiness means only arithmetic
warmup, not source validity, strategy eligibility, execution readiness or profitability.

The arithmetic module has no database, network or broker effects. Structural
validation cannot detect an arbitrarily fabricated valid-looking history. The
read-only reconstruction boundary below now binds it to retained history and full
settings. Fixed-bracket exit mechanics are unchanged; Jam-specific pure proposals
now exist below, while their atomic ledger integration remains unfinished. Existing
retired/quarantined Jam lineages stay disabled; no historical result was retuned.

## Read-Only Jam History Binding

`NativeJamHistoryReader(engine, settings).snapshot(scope=..., strategy_parameters=...,
expected_head_hash=...)` reads existing file-backed SQLite only. It uses its own
`mode=ro` connection with query-only enforcement and an explicit BEGIN; both paged
audit passes see a single snapshot even when a WAL writer appends concurrently.
The writer pool is not modified. Missing databases are not created. Memory/URI
database URLs and other engines are outside this increment's supported scope.

The full existing Jam Spot v1.0.1 parameter contract must match the retained stream
fingerprint. Missing/unknown settings, fractional/boolean integer counts, unsupported
timeframes/lengths and scope/head changes reject. Canonical internal spaces in native
fingerprints now work without changing their bytes; outer whitespace and control
characters reject. A head/settings binding is not strategy eligibility or approval.

The reader reuses seed, prefix, continuation, source, signal and management audits.
It reconstructs Jam state rather than accepting candles or a saved feature cache.
Source-bound-from-seed and online-observed-from-seed coverage are separate metadata;
late source attachment does not attest earlier history. Origin, execution and forward
qualification remain false. The reader has no network, entry, strategy-enable or
write API. Current provenance is local content validation, not an administrator-proof
signature. Audit memory is bounded, but two passes and total audit time grow with
history. The result is a pinned read, not a lock on a later decision: a future writer
must revalidate its exact head/settings atomically before applying any decision.

## Pure Jam Decision And Management Proposals

`native_jam_decisions.py` adds bounded immutable setup and managed-position state.
It has no database/network/order effects. Full settings, stream scope and explicit
tick/lot/slippage terms bind the state; feature parameters and Decimal28 arithmetic
are revalidated. Each step requires exactly one contiguous feature bar. The feature
hash records supplied content, not proof that the input came from a verified reader.
Future operational integration must reconstruct both features AND decision state
from retained evidence, not accept a saved state simply because it parses or hashes.

`initialize_jam_setup` anchors the warmup head without claiming historical setups
or fills. `evaluate_jam_setup` applies pending expiry/cancellation, context/volume,
confirmation, target geometry and reference quantity feasibility. It exposes no order
quantity; cost-aware native risk/affordability/loss limits must size independently.
The explicit caller entry-window flag is a policy input, not authorization. Frozen
historical start/end dates are not repurposed as a native production schedule.

A candidate leaves the state awaiting resolution, with no inferred fill/cooldown.
`resolve_jam_entry` requires the exact proposal hash and explicit boolean outcome.
Rejection consumes that proposal; only acknowledged fill starts cooldown. This is a
pure transition, NOT fill evidence or permission for a caller to modify the ledger.
The future transaction coordinator must own the acknowledgment using actual results.

`initialize_jam_position` supports a modeled fill exactly at the signal-bar close.
Best price starts at the fill price, excluding pre-fill signal-bar highs. Nonboundary
fills reject; existing conservative partial-entry bounds must remain in execution.
`plan_jam_exit` checks the prior stop/target first (adverse gaps and stop-first
ambiguity), then updates breakeven/trailing stops for the NEXT bar, never retroactively.
Close exits retain midpoint > pullback > time priority. Historical backtest-window-end
liquidation is absent. BRACKET versus CLOSE phase is explicit: only an actually
resolved bracket exit may make the account flat before this candle's setup evaluation;
close exits belong after it. An unresolved exit proposal blocks further management.
Missing features still permit existing-bracket checks, not dynamic management.

Synthetic reference comparisons establish matching proposal/exit geometry on their
fixtures, not universal Pine parity, exchange fills, economic edge or strategy
eligibility. No fees/P&L are realized by this module; it reuses geometry/fill helpers
without altering the frozen replay or its historical results. Jam stays retired.
All source-origin, execution-authority and forward-qualification flags remain false.

## Atomic Jam Decision And Managed-Paper Transactions

`NativePublicObserver.evaluate_jam(scope=..., config=..., seed_count=...)` is an opt-in
new-stream mode, not a new HTTP endpoint. It owns public acquisition and accepts no
caller candles, decision, equity, position cache or fill acknowledgment. Its config
binds full Jam settings and tick/minimum-contract terms. Native modeled slippage is
a money cost, so nonzero price-slippage ticks reject instead of double charging.
The supplied contract terms are not current exchange-filter qualification.

The v7 receipt requires both retained source and owned-observation admission. Scope,
head and settings are rechecked under the existing SQLite write lock. The coordinator
reconstructs features/setup/management from the seed and prior receipts, generates
the exact signal, invokes existing risk and paper services without committing, and
resolves the entry proposal using actual ledger results. Approved quantity remains
native cost-aware sizing, not the reference candidate's quantity feasibility check.
Retired Jam still rejects; only disposable positive fixtures mock qualification.

Each receipt binds the risk snapshot, new entry (if any), management plan/outcome,
resolved states, equity before management, equity at setup evaluation and equity
after the transaction. Entries are nonqualifying `native_ohlc_online_exit_v1` from
creation. The original ledger stop/target never change; next-bar dynamic stops and
best price live in reconstructible managed state. Historical entry audit still
works after closing the trade, using the canonical opening snapshot rather than
comparing an old opening hash to the order's newer closed hash.

Actual fill time remains processing time. The managed state's `entry_open` is the
signal candle cursor, not a claimed boundary fill. On the first partially observed
candle, a stop touch uses the adverse low bound; a target requires the close to be
at/above it and is a CLOSE-phase exit. Otherwise management advances its cursor
without changing best price or stops and without close-based dynamic exits. This
deliberately conservative policy excludes pre-fill highs; full Jam management starts
on the next fully observed candle. It is not an assertion of exact intrabar fills.

Fully observed candles evaluate the existing bracket first, including stop-first
ambiguity/gap semantics. Stop updates take effect next bar. BRACKET closes realize
net P/L before setup evaluation; CLOSE exits keep the position open during setup
evaluation and close afterward. Entry kill/retirement controls do not suppress
protective paper exits. Existing close logic applies frozen entry costs, with no
second price-slippage charge. Stops/exit prices are rounded down to ledger precision.

The audit reconstructs proposals, partial-bar handling, phase ordering, frozen costs,
close metadata, realized P/L and account transitions. Extra/manual position changes,
unreceipted closes, orphan orders, dropped modes/settings and changed heads reject.
The first seed requires an existing reconciled 100-unit paper account; nothing is
reset or silently created. A receipt failure rolls back all ledger/state effects;
exact retry returns the durable receipt rather than reexecuting it. Legacy v1-v6
receipt bytes remain unchanged. No new migration is required for v7 JSON evidence.

This is still one-shot trusted-local-code orchestration, not a supervisor, signature,
qualified campaign or broker adapter. All live/source-origin/forward qualification
flags remain false. Missed windows stop; Jam-mode gap recovery remains explicit
unfinished work, not a silent backfill or a reason to reactivate the strategy.

## Bounded Private Supervision

`scripts/run_native_supervisor.py` requires explicit existing database, JSON config
and a new run directory. It has no migration/reset/strategy-enable/live-order path.
Modes are OBSERVE, JAM and EXIT_ONLY; JAM must provide matching decision config.
The CLI opens SQLite with `mode=rw` to prevent accidental database creation.
Ctrl+C/SIGTERM, a caller stop event or a `STOP` file requests cooperative shutdown.
An in-flight bounded acquisition/atomic step finishes or fails before stopping;
shutdown never automatically liquidates a position or asserts it is flat.

The OS-held advisory lock is tied to the process handle, not a PID or stale file.
SQLite transactional head/retry checks still apply. Persistent state is reconstructed
by the existing observer on restart, never read from the run journal as trading state.
Runtime caps limit duration, newly processed bars, total receipts, database+WAL size,
journal size, retries and free disk (at least 1 GiB). These are conservative stops,
not a claim of indefinite availability. Audit work still grows with retained history.

Transport failures/429/5xx use bounded backoff; Retry-After is never shortened.
Clock, stale/missing candle, integrity, scope and reconciliation failures stop.
Unknown failures are BLOCKED, not retried. No clock adjustment, tolerance expansion,
history skip, automatic recovery or reclassification of backfill is performed.
Existing entry kill controls do not disable protective Jam paper exits.

Each new run gets a fsynced, hash-chained journal. A missing terminal record is
INCOMPLETE evidence, not proof of a live/dead process. Structural audit checks the
config, chain and terminal counts but explicitly does not reconcile the database.
`scripts/audit_native_supervisor.py` separately opens SQLite in enforced read-only
mode, audits retained history and checks journal references against its receipts.
An audit PASS for a BLOCKED run only verifies that failure evidence. Source-origin,
forward-qualification, live authority and platform acceptance remain false.

October 9 real no-entry attempt: a separate diagnostic database was migrated to
0031 and the supervisor waited for a fresh close. The acquisition clock guard stopped
it; read-only audit confirms zero receipts/signals/orders/trades. Windows reports
unsynchronized Local CMOS Clock; configuration inspection was denied. Operator time
synchronization is needed before another genuine admission attempt. No operator DB
migration or clock-setting change occurred. Evidence and final fixture results:
docs/46 and `data/evidence/native_supervisor_public_20261009_v1/`.

## Next Work

Private lifecycle integration (v64) pins a launch-time supervisor config and offers
instance/run-bound start, stop and explicit restart. It owns actual subprocess
handles; startup never automatically runs a strategy. The managed child receives
only whitelisted non-secret settings, source/DB identity and a parent-lifetime pipe.
Cooperative stop is distinct from exit; terminal journals are audited after actual
process exit. A forced or unverified exit is not a clean run. The OS-held database
lock still rejects competing owners. The private runbook describes bounded controls.
No-data child fixtures exercise these mechanics without public acquisition and
cannot satisfy fresh-feed, strategy, paper-campaign or Testnet evidence requirements.

1. Retained source-to-input binding and one-shot acquisition-owned admission are
   implemented and fixture-tested. October 8's one-candle diagnostic passed, but the
   October 9 supervisor attempt is blocked by current clock skew; admission is unproven.
2. One-shot source-bound paper exit management is implemented and fixture-tested.
   Explicit supervision modes and failure stops now exist; operational demonstration
   remains incomplete. OHLC-model exits remain nonqualifying.
3. Bounded Jam features, retained-history/settings binding, proposals and atomic
   entry/managed-exit integration passed the v56 regression. Finish supervisor
   operational verification, private backup/restore/upgrade/rollback and explicit
   gap-recovery policy without treating stale data as fresh forward observations.
4. Demonstrate real fresh admitted observations with continuing clock checks before
   claiming operational feed readiness; run a campaign only for an eligible candidate.

Zero qualified strategies, zero demonstrated live profit, live execution disabled.
Public acquisition is not exchange permission, Testnet qualification or live approval.
