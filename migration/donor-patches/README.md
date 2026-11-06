# Preserved Donor Edits

Generated from tracked working-tree changes on November 6, 2026. These patches
preserve existing local work; they are not a new integration or upstream upgrade.
No untracked Electron profile, cookie store, API key or environment file is included.

| Patch | Pinned Upstream Base | Modified Files |
| --- | --- | --- |
| My-Krypt-Trader.patch | 4ab5c0b83546879d3088ccbe14a5c92987887fc0 | electron/main.ts, package.json, package-lock.json, scripts/python-utils.mjs, scripts/setup-python.mjs |
| tradingview-mcp-jackson.patch | 5d6d7bcbd6a75539fa3697465c56944f544b001b | src/core/pine.js |

Follow `docs/50_GIT_MACHINE_MIGRATION.md` from the Aurex repository root. Apply only
to clean checkouts at these bases, checking before applying. The original local
donors already contain the changes: do not apply the patches there again.
