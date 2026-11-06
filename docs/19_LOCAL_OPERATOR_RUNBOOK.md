# Aurex Local Operator Runbook

## 1. Open The Repository

PowerShell:

```powershell
Set-Location "C:\Users\ashumba\Documents\New project\Aurex"
```

Git Bash:

```bash
cd "/c/Users/ashumba/Documents/New project/Aurex"
```

## 2. First-Time Setup

Use Python 3.12.

These setup migrations are for a NEW installation. For an existing operator database,
use the backup/rehearsal section below first. Do not upgrade the only copy of its ledger.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Git Bash:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -m alembic upgrade head
```

Do not recreate the virtual environment when it already exists.

### Existing Database: Backup And Rehearse First

The private backup tools require explicit paths. They never reset trading state,
activate a strategy, replace an existing database, or enable live execution.
Use a new directory for every attempt, including after an interrupted attempt.
`data/backups/` is git-ignored; keep these private snapshots out of commits and uploads.

```powershell
.\.venv\Scripts\python.exe scripts/manage_database_backup.py create `
  --database data/aurex.db --backup-directory data/backups/operator-backup-UNIQUE
.\.venv\Scripts\python.exe scripts/manage_database_backup.py verify `
  --backup-directory data/backups/operator-backup-UNIQUE
.\.venv\Scripts\python.exe scripts/manage_database_backup.py restore-copy `
  --backup-directory data/backups/operator-backup-UNIQUE `
  --destination data/backups/operator-restore-UNIQUE.db
```

The destination parent must exist. Backup uses SQLite's consistent snapshot API,
including committed WAL content, and checks integrity, foreign keys, schema, every
table's content hash and full logical content. Restores only create a NEW file;
an existing destination is refused. Partial artifacts are retained but are not valid
backups unless their completed manifest and independent verification pass. Current
bounds are 512 MiB per database and time/disk limits, not unlimited backup support.

The guarded native-schema rehearsal copies a supported 0029/0030/0031 database,
upgrades only its new copy to 0031, verifies existing table/schema content is unchanged,
then restores a second rollback copy from the frozen backup:

```powershell
.\.venv\Scripts\python.exe scripts/rehearse_native_database_upgrade.py `
  --database data/aurex.db `
  --work-directory data/backups/native-upgrade-rehearsal-UNIQUE
```

This is a rehearsal, NOT authorization or execution of an operator upgrade. Inspect
the report and retained migration log. Runtime resume and service cutover remain
separate acceptance checks. Never use a destructive Alembic downgrade as a substitute
for restoring a verified pre-upgrade snapshot. Before any real replacement or cutover,
stop writers, reconcile positions and verify the complete operational recovery plan.

These backups cover SQLite only. External market/evidence files, credentials,
environment configuration, application source and dependency recovery are NOT included.
The manifest says `includes_external_files=false`; do not claim complete application
restoration from a database-only check. Secrets need separate approved secure storage.

### Application And Dependency Recovery

`manage_recovery_bundle.py` covers Aurex source, migrations, static dashboard, tests,
Pine files, documentation, non-secret settings, runtime version inventory, a verified
SQLite snapshot, and explicitly scoped retained evidence. It excludes donor checkouts,
Git working history, caches, the existing virtual environment and private credentials.
The archive manifest binds every included file. Links/reparse points, path traversal,
case collisions, unexpected members, changed source files and low disk fail closed.
Restore creates a NEW tree and independently verifies every file and database content.

```powershell
.\.venv\Scripts\python.exe scripts/manage_recovery_bundle.py plan --root . `
  --database data/aurex.db --bundle data/backups/application-recovery-UNIQUE `
  --scope FULL_EVIDENCE
```

The full mode includes historical raw archives and needs room for a separate restore.
October 10 preflight required about 158 GB free versus about 80 GB available. Do not
delete history to make this check pass. A separate suitable destination is pending.
The explicit `OPERATIONAL_WITHOUT_RAW_ARCHIVES` mode omits only `.zip`/`.part` files
under evidence, lists all of them in the manifest, and never claims full historical
recovery. It preserves source and operational/checkpoint evidence for a narrower
service-recovery rehearsal; replaying an omitted archive remains unavailable there.

```powershell
.\.venv\Scripts\python.exe scripts/manage_recovery_bundle.py create --root . `
  --database data/backups/native-upgrade-rehearsal-UNIQUE/upgraded.db `
  --bundle data/backups/application-recovery-UNIQUE `
  --scope OPERATIONAL_WITHOUT_RAW_ARCHIVES
.\.venv\Scripts\python.exe scripts/manage_recovery_bundle.py verify `
  --bundle data/backups/application-recovery-UNIQUE
.\.venv\Scripts\python.exe scripts/manage_recovery_bundle.py restore `
  --bundle data/backups/application-recovery-UNIQUE `
  --destination data/backups/application-restored-UNIQUE
```

Use quiescent source/evidence and a source database with no unreviewed writes. Partial
attempts are retained without a completed manifest. The private `_recovery` records
contain no copied webhook/API secret. Reprovision credentials separately; the service
rehearsal uses a fresh transient webhook secret and grants no external delivery rights.

Exact dependency wheels are a separate private recovery artifact. Download uses only
binary versions already installed in the source environment, public PyPI, no user pip
configuration and no inherited credentials. The wheel manifest binds package identity,
version, bytes and SHA-256; the install lock requires those hashes. Installation uses
`--no-index --no-deps --require-hashes`, a new venv with system packages disabled,
`pip check` and an exact installed-version comparison. No existing environment changes.

```powershell
.\.venv\Scripts\python.exe scripts/manage_recovery_environment.py download `
  --wheelhouse data/backups/recovery-wheelhouse-UNIQUE
.\.venv\Scripts\python.exe scripts/manage_recovery_environment.py verify `
  --wheelhouse data/backups/recovery-wheelhouse-UNIQUE
.\.venv\Scripts\python.exe scripts/manage_recovery_environment.py create `
  --wheelhouse data/backups/recovery-wheelhouse-UNIQUE `
  --destination data/backups/recovery-environment-UNIQUE
```

Run the restored script with the rebuilt interpreter, not the source checkout:

Current restores publish an `aurex_application_restore_v2` receipt only AFTER full
readback verification succeeds. The current rehearsal requires that version and
`readback_verified: true`; legacy receipts do not establish this launch condition.
Do not edit an old receipt to satisfy it. Failed/interrupted restores remain
non-launchable; retain the failed tree and restore into a new destination.

```powershell
data/backups/recovery-environment-UNIQUE/Scripts/python.exe `
  data/backups/application-restored-UNIQUE/scripts/rehearse_recovered_application.py `
  --expected-environment data/backups/recovery-environment-UNIQUE `
  --report-directory data/backups/application-rehearsal-UNIQUE
```

This checks restored-module import paths, exact runtime versions, preserved safe
settings and readiness source/checkpoint integrity, then runs two private service
processes against the restored DB with kill-state persistence and unchanged trading
tables. It does not start a supervisor, render all UI workflows or perform cutover.
The Python interpreter/OS are prerequisites, not included artifacts. These local
copies do not demonstrate off-device disaster recovery. Retain the bundle and matching
wheelhouse together, plus separately approved secure credential storage where needed.

## 3. Verify Aurex

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Git Bash:

```bash
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check .
```

## 4. Run Aurex

Use the guarded private launcher for the supported current-schema operator workflow.
It refuses missing/outdated databases, missing schema columns, failed integrity or
foreign-key checks, live-enabled settings and production environment configuration.
It never creates/migrates the DB, auto-starts the native supervisor or activates trading.
The October 9 operator DB is still 0029: do not bypass this rejection or upgrade it
without completing guarded recovery/cutover acceptance. Rehearsal copies use 0031.

PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/run_private_operator.py --check --database data/aurex.db
.\.venv\Scripts\python.exe scripts/run_private_operator.py --serve --database data/aurex.db `
  --port 8917 --run-directory data/backups/private-operator-run-UNIQUE
```

Git Bash:

```bash
./.venv/Scripts/python.exe scripts/run_private_operator.py --check --database data/aurex.db
./.venv/Scripts/python.exe scripts/run_private_operator.py --serve --database data/aurex.db \
  --port 8917 --run-directory data/backups/private-operator-run-UNIQUE
```

Keep that terminal open. Visit:

- Dashboard: `http://127.0.0.1:8917/dashboard`
- API documentation: `http://127.0.0.1:8917/docs`
- Health check: `http://127.0.0.1:8917/health`
- Private configuration status: `http://127.0.0.1:8917/system/private-runtime`

Stop Aurex with `Ctrl+C`.

If port 8917 is occupied, use 8918 in both the command and URL.

The launcher binds only 127.0.0.1, uses one worker and trusts no proxy headers.

The Command view reports the private service boundary, instance and schema separately
from supervisor operation and acceptance. A ready web service does not start or prove
a running trading supervisor. Dashboard reads are bounded to four concurrent sources;
refreshes serialize so post-action reads cannot be replaced by an older refresh.
GET requests time out after 30 seconds; mutations are never retried automatically.
Failed safety sources clear readiness/risk state and disable reset/enable controls.
An unavailable source is not a zero balance or a passing gate. Equity plots use only
recorded observations; empty/unavailable data never draws a synthetic curve.

Developer transport checks: `node --test tests/frontend/dashboard-transport.test.cjs`.
`scripts/rehearse_operator_dashboard.cjs` is a Playwright rehearsal requiring an
explicit loopback URL, expected private instance, NEW report directory and
`--allow-disposable-controls`. Run only against a disposable verified database copy:
it enables the paper kill switch and leaves it enabled, never submits orders or
enables strategies. It checks real page requests and all tabs at desktop/mobile
widths, then injects named source failures and verifies recovery. The injected
failures are UI fixtures, not genuine-feed or strategy qualification evidence.
Browser binaries/test tooling are separate prerequisites, not production app assets.

### Owned Native Supervisor

Without `--native-config`, lifecycle status is UNCONFIGURED and its start/stop
buttons are disabled. Supplying a bounded `NativeSupervisorConfig` JSON file to
`--check` validates it without starting a child. Supplying it to `--serve` pins the
mode/scope/settings for that private service; it does NOT auto-start the runner.
The configured Command view provides Start, Stop and (after verified exit) Restart.
There is no HTTP command/path/config override. Use an accepted existing current-schema
copy and a NEW service run directory; do not point a rehearsal at the operator DB.

Start binds the service instance, expected previous run, request identity, source,
DB identity and non-secret settings. Identical request retries cannot spawn a second
child. Changed instance/run or reused conflicting request IDs reject. Each service
permits at most 32 starts. Source/DB changes require investigation and a fresh
service, not a bypass. JAM mode still rejects retired/unqualified strategies.
OBSERVE grants no entry authority; EXIT_ONLY does not grant entry authority either.

The process field is authoritative only for this service's owned child. External
processes are NOT_OBSERVED; a PID/lock file alone is not liveness evidence. A live
process is not a working feed. Terminal journal verification is not qualification.
Stop is cooperative: an in-flight acquisition/atomic step may finish before exit.
It never liquidates positions. UI status polls every five seconds in the foreground;
unavailable status disables controls rather than preserving a stale success. Control
requests have a 45-second response deadline and are never retried automatically;
timeout means uncertain delivery, followed by status readback, not permission to resubmit.

Private service shutdown closes its owned child's parent pipe and waits up to 120
seconds (90-second acquisition bound plus grace). Forced owned-child termination is
recorded as failure. Missing/corrupt exit evidence or failed control logging blocks
further starts; logging failures cannot suppress a stop. Runtime-settings drift still
allows owned status/protective stop behind the same local request boundary.
Independent journal/database reconciliation remains required before any campaign.

`--exercise-managed-controls` extends the browser rehearsal through two start/stop
cycles. It is exercised with `tests/fixtures/private_native_wait_service.py`, which
substitutes acquisition with a no-data wait in a real child process. This test-only
entry point is never an operational launcher and produces no fresh-feed evidence.

Host, peer and same-origin browser checks reject cross-site/DNS-rebinding requests.
This is NOT user authentication: other trusted local processes can use the private
API. Do not expose it through a tunnel, proxy or public listener. The legacy raw
ASGI entry point does not provide this wrapper and is not the supported private
launch command. Browser requests work normally at the matching loopback origin;
non-browser mutating calls require `X-Aurex-Local-Request: 1`.

Every run requires a new directory. Its fsynced `events.jsonl` records STARTING,
LISTENING and STOPPED/BLOCKED. These are operational diagnostics, not immutable
trading receipts or proof that an old process is alive. An optional
`--max-runtime-seconds` bounds a diagnostic run. A `STOP` file in that run directory
also requests graceful shutdown; wait for process exit and socket closure before
claiming it stopped. Stopping the UI does not stop a separately launched supervisor,
close positions or cancel orders. Ctrl+C remains the normal foreground stop.

### Rehearse Restored Service Operation

The following command requires an already current-schema SOURCE COPY. It creates a
verified backup and another new service copy, starts two separate loopback processes,
checks HTTP assets/status/ledger reads, rejects a cross-origin write, enables the
kill switch on the disposable copy and verifies it persists across restart. It stops
both processes, confirms ports close, and checks trading-table content hashes remain
unchanged. The instance ID binds requests to that rehearsal process, not another
service on a reused port; it is a diagnostic ID, not an authentication credential.

```powershell
.\.venv\Scripts\python.exe scripts/rehearse_private_operator.py `
  --database data/backups/native-upgrade-rehearsal-UNIQUE/upgraded.db `
  --work-directory data/backups/private-runtime-rehearsal-UNIQUE
```

This does not render/validate all dashboard workflows, restore external files,
demonstrate genuine-feed operation or perform operator cutover. A passed service
rehearsal is not whole-platform acceptance. Keep original snapshots and private
reports; failed attempts must not overwrite an earlier directory.

## 5. Verify The Testnet Boundary

```powershell
.\.venv\Scripts\python.exe scripts\freeze_binance_spot_testnet_profile.py --check
```

The result must show:

- `PASS`
- `sandbox_qualified=False`
- `live=False`
- no failed gates

## 6. Run The Public Testnet Check

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\run_binance_spot_testnet_check.ps1 `
  -Mode public `
  -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

This makes public requests only. It checks ping, server time, BTCUSDT exchange
filters, and ticker price.

From Git Bash, invoke the PowerShell wrapper:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  scripts/run_binance_spot_testnet_check.ps1 \
  -Mode public \
  -Output data/evidence/binance_spot_testnet_public_connectivity_latest.json
```

## 7. Run The Authenticated Testnet Check

Create or obtain the Binance Spot Testnet HMAC API key and secret from the official
Testnet API-key page. Do not paste either value into chat, source files, `.env`,
screenshots, or shell command arguments.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\run_binance_spot_testnet_check.ps1 `
  -Mode authenticated `
  -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

The wrapper prompts for both values with hidden input, passes them only through the
child process environment, clears those environment variables, and zeroes the
unmanaged secure-string buffers after the command. Plaintext necessarily exists
briefly in process memory while requests are signed; the wrapper does not write it to
disk, command arguments, evidence, or logs.

## 8. Validate A Signed Test Order

Only after the authenticated check passes:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\run_binance_spot_testnet_check.ps1 `
  -Mode test-order `
  -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

This uses `POST /api/v3/order/test`. Binance validates the signature, permissions,
BTCUSDT filters, quantity, price, and notional, but the order does not enter the
matching engine.

## 9. Run The Guarded Virtual Cancel Lifecycle

Only after authenticated read and signed `order/test` both pass:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\run_binance_spot_testnet_check.ps1 `
  -Mode virtual-cancel `
  -Output data\evidence\binance_spot_testnet_public_connectivity_latest.json
```

The wrapper requires the exact acknowledgement `VIRTUAL FUNDS ONLY` before asking
for credentials. Aurex then:

1. Repeats signed non-mutating order validation.
2. Reads Binance's current `PERCENT_PRICE_BY_SIDE` reference average and best bid.
3. Constructs a resting BTCUSDT BUY well inside the allowed percentage band and
   below the best bid.
4. Enforces price, percentage-price, quantity, notional, and Aurex USD 10 maximum
   notional limits again immediately before submission.
5. Queries the order by deterministic client ID.
6. Cancels the order with a separate deterministic cancellation ID.
7. Queries its final state by the immutable external `orderId`, never by the
   cancellation-operation client ID.
8. Requires matching identifiers and quantities, zero executed quantity, and final
   `CANCELED` status.

If submission becomes network-uncertain, Aurex queries by client ID and attempts
cleanup cancellation. It never blindly repeats order submission.
Sanitized lifecycle checkpoints are atomically written after placement, query,
cancellation, and final query. A later failure therefore preserves the last known
external order ID and state instead of discarding them behind a traceback.

This is a real Testnet matching-engine order using virtual funds. It is not a fill
test, strategy test, profitability test, sandbox qualification, production order, or
real-capital transaction.

## 10. Read The Result

Restart or refresh Aurex, open the Operator view, and inspect:

- frozen Testnet profile;
- public connectivity;
- authenticated read;
- signed test order;
- virtual order authority;
- sandbox qualification; and
- production/live boundary.

At the current checkpoint:

- public connectivity is verified;
- authenticated read is verified;
- signed test order is verified;
- the first virtual order was submitted, remained unfilled, and was cancelled;
- its first reconciliation failed closed on cancellation identity;
- the identity contract is corrected;
- a subsequent retry stopped before submission because the old candidate price
  violated Binance's moving `PERCENT_PRICE_BY_SIDE` boundary;
- percent-price-aware construction now passes a current public Testnet preflight;
- the next lifecycle placed and cancelled successfully but its final query used the
  cancellation-operation ID as an order lookup ID;
- final lookup now uses the immutable external `orderId`;
- the preserved complete lifecycle reconciles under the corrected identity contract;
- no virtual-cancel rerun is required;
- the next execution gate is a separately designed fill-and-fee reconciliation
  campaign;
- the sandbox is not qualified;
- no strategy is eligible; and
- production and live trading remain disabled.
