# Operator Profile Intake

This workflow collects the operator facts required by the frozen post-V4 capability
review. It is a research-planning boundary, not a trading permission.

## Safety Contract

- Never enter an API key, private key, password, bearer token, secret, seed phrase,
  account number, or recovery material.
- Use non-secret aliases and official public URLs or non-secret local evidence
  references.
- The dashboard preflight performs no file, database, exchange, TradingView, paper,
  live, or capital write.
- A passing preflight authorizes only independent freezing of the operator profile.
- A frozen passing profile authorizes only design of a separately preregistered
  successor research charter.
- It never authorizes market-data acquisition, parameter selection, return testing,
  candidate creation, paper trading, sandbox qualification, live trading, or capital
  deployment.

## Dashboard Workflow

1. Open the `Operator` control view.
2. Enter the real venue, jurisdiction, account/API/sandbox status, product boundary,
   capital source, starting capital, loss limits, and data budget.
3. Use only an account alias. Aurex rejects account-number-shaped aliases.
4. Confirm the unborrowed-capital, emergency-fund, legal/tax, no-credentials, and
   accuracy attestations that are actually true.
5. Run `Preflight`.
6. Correct every failed gate. The download and freeze-command actions remain disabled
   until all nine gates pass.
7. Download the exact validated input. Editing it after preflight invalidates the
   browser result and requires another preflight.
8. Freeze and independently check with the CLI. The dashboard cannot freeze the
   artifact.

## HTTP Contract

### `GET /operator-profile/status`

Returns one of:

- `INPUT_REQUIRED`: the canonical frozen artifact is absent.
- `FROZEN_VERIFIED`: the artifact parses, audits, and matches the current builder
  contract.
- `FROZEN_INVALID`: an artifact exists but is malformed, tampered, or stale.

The response contains no operator input or capital values and uses
`Cache-Control: no-store`.

### `GET /operator-profile/template`

Returns the typed input template, nine ordered gate IDs, maximum planning ratios,
the `$100` measurement milestone, expected filename, and CLI handoff. It writes
nothing and uses `Cache-Control: no-store`.

### `POST /operator-profile/preflight`

Accepts one exact `aurex-post-v4-operator-access-input-v1` JSON object. The endpoint:

- accepts at most 64 KiB;
- validates with the same typed contract used by the freezer;
- never echoes rejected input values or secrets in validation responses;
- binds the frozen post-V4 capability review and current builder contract;
- returns all gate results, derived risk ratios, evidence hashes, and next action;
- writes no artifact.

`PASS` means the input may proceed to independent CLI freezing. `BLOCKED` means the
failed gates must be corrected. Neither response creates trading authority.

## Frozen Gates

1. `ACCOUNT_AND_API_ACCESS_PROVEN`
2. `CAPITAL_SOURCE_AND_RESERVE_SAFE`
3. `DATA_BUDGET_EXPLICIT`
4. `LOSS_LIMITS_CAPITAL_PROTECTIVE`
5. `NO_CREDENTIALS_OR_SECRETS`
6. `OPERATOR_ATTESTATION_COMPLETE`
7. `PRODUCT_SCOPE_AND_LEVERAGE_SAFE`
8. `SANDBOX_PATH_AVAILABLE`
9. `VENUE_AND_JURISDICTION_BOUND`

Planning loss limits must be ordered
`per-trade <= daily <= total <= starting capital` and may not exceed:

- `0.5%` of capital per trade;
- `1%` of capital per day;
- `10%` of capital in total.

Maximum effective leverage is `1x`.

## Independent Freeze

From the Aurex project root, using the exact downloaded and reviewed input:

```powershell
python scripts/freeze_post_v4_operator_profile.py --preflight --input "path\to\aurex-operator-profile-input.json"
python scripts/freeze_post_v4_operator_profile.py --freeze --input "path\to\aurex-operator-profile-input.json"
python scripts/freeze_post_v4_operator_profile.py --check
```

The expected artifact is:

`data/evidence/post_v4_operator_access_profile_v1.json`

Do not create or modify that file manually. If it already exists, use `--check`;
never overwrite it to change an operator decision.
