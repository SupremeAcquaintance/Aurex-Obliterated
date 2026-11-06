# Aurex Git And Machine Migration

## What Git Preserves

The source, frontend, Pine scripts, migrations, tests, dependency declarations,
deployment templates and documentation remain eligible for Git. Top-level
`data/evidence/*.json`, `*.jsonl` and `*.md` retain the research contracts, audit
reports, decisions, contamination history and current readiness records.
Use a PRIVATE GitHub repository: evidence can contain machine paths and operational
metadata. Ignoring common secret files is not a comprehensive secret audit.

The project-control, implementation-log and delivery-rebaseline documents are the
resume records. `migration/ACTIVE_GOAL.txt` is a byte-verified copy of the active
goal attachment, preserved for setting the goal again on the new workspace. Its
historical checkpoint must be reconciled with newer records; it is not a new plan.
The desktop chat, live Goal state, other attachments outside this repository,
account sessions and secret stores do NOT transfer with a Git clone.
No external upload, commit or history rewrite is performed by this configuration.

`.gitattributes` disables automatic line-ending conversion because source/evidence
hashes bind exact bytes. Do not run a bulk EOL formatter or `git add --renormalize`
over historical evidence. Existing unrelated edits are preserved.

## What Git Does Not Preserve

Git excludes local virtual environments, node_modules, caches, browser profiles,
secret configuration, databases (including journals/WAL), recovery bundles, raw
market archives, partial downloads, derived datasets and nested evidence directories.
Those nested directories also contain historical source snapshots, API responses,
per-run results and older validation artifacts. They are not disposable merely
because Git ignores them. Keep the original copies or transfer them separately.

A code clone plus checkpoint reports is NOT full historical recovery or a restored
operator installation. Reports referring to absent files are not reverified evidence.
Some audits and data-dependent tests will remain unavailable until their artifacts
are restored. Never regenerate old evidence or relax a gate to hide missing files.

## Upload The Code And Checkpoints

If an earlier `git add .` is still running in your own terminal, cancel that command
once with Ctrl+C before restarting it. Do not delete Git lock files while a Git
process is running. `.gitignore` does not untrack previously committed/staged files.
The transfer-policy tests check representative include/exclude and byte-preservation
rules; review the staged file list before committing.

```powershell
git add .
git diff --cached --stat
git diff --cached --name-only
git commit -m "Preserve Aurex development and research checkpoints"
git push -u origin main
```

The push assumes `origin` is already YOUR intended private repository and `main` is
the intended branch. Do not replace an unknown remote or force-push. If a large file
was committed previously, changing ignore rules will not remove it from history;
investigate before choosing any history-rewrite operation.

## On The New Machine

Clone your own Aurex remote with `--recurse-submodules`, then enter that checkout.
The two donor links now have explicit upstream URLs. Their pinned base revisions are
recorded by Git; no donor branch is automatically upgraded. Aurex-native code remains
the source of truth. The donor repositories are optional for the core runtime.

Local tracked donor edits are exported in `migration/donor-patches/`. They are not
part of the upstream commits. Apply them once to clean, pinned donor checkouts:

```powershell
git -C My-Krypt-Trader apply --check ../migration/donor-patches/My-Krypt-Trader.patch
git -C My-Krypt-Trader apply ../migration/donor-patches/My-Krypt-Trader.patch
git -C tradingview-mcp-jackson apply --check ../migration/donor-patches/tradingview-mcp-jackson.patch
git -C tradingview-mcp-jackson apply ../migration/donor-patches/tradingview-mcp-jackson.patch
```

These patches exclude the donor's local Electron browser profile/cookies. Do not
upload those profiles. Regenerate/review patches if donor source changes later.

Recreate the Python environment using Python 3.12 and the existing project setup;
do not copy the old `.venv` between machines. Use the verified wheelhouse/recovery
environment tooling for exact-version restoration when required; a new install from
broad dependency ranges is not proof of the original runtime. Configure credentials
locally through approved channels, never through commits or chat.

Before resuming operational work, read these records IN the cloned checkout:

- `docs/10_PROJECT_CONTROL.md`
- newest entries in `docs/01_IMPLEMENTATION_LOG.md`
- `docs/46_AUREX_DELIVERY_REBASELINE.md`
- `docs/19_LOCAL_OPERATOR_RUNBOOK.md`
- `docs/49_NATIVE_PUBLIC_DATA.md`
- `migration/ACTIVE_GOAL.txt`

Treat an interrupted/pending step as unverified until its current artifacts and
process state are inspected. Continue the existing plan; do not restart research or
reactivate retired candidates. Desktop Goals must be set again in the new workspace.

## Transfer Private Operational State Separately

Use the existing verified SQLite backup/restore and application recovery tools in
the operator runbook. A live `.db` file copied without its committed WAL is not a
verified backup. Never overwrite the only operator ledger, migrate it automatically,
or treat a rehearsal database as the operator account.

Preserve `data/evidence/` in full through a private external drive or other explicitly
approved destination if full replay/audit continuity is needed. Preserve recovery
bundles, matching dependency wheels and any cited `.tmp` verification artifacts too.
Use a consistent capture, checksums and independent readback; a folder's existence is
not proof of complete transfer. Keep required secrets separately in secure storage.

Do not wipe or retire the old machine until the new copy passes source/evidence
checks, database reconciliation, restoration checks and the appropriate runtime
tests. Live execution stays disabled. Migration does not qualify a strategy, repair
the unresolved public-feed clock issue or grant real-money authority.

## Verification On November 6, 2026

Transfer-policy tests: 29 passed, covering include/exclude boundaries and exact-byte
hash preservation with autocrlf enabled. Both donor patches passed reverse-apply
checks against the unchanged local donor worktrees. Candidate inventory was about
103.3 MB across 1,757 regular files before this final log update; the largest file
was 24.8 MB. ZIP archives alone account for 75.9 GB excluded from Git.
No ignored paths were already tracked at inspection, and the index had no staged
changes then. A high-confidence credential-pattern screen found only the deliberate
private-key-header rejection fixture in `test_research_operator_access_profile.py`;
this is not a full secret audit or approval to publish the repository publicly.
