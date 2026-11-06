# Binance Spot Testnet Sandbox Boundary

## Purpose

This phase gives Aurex permission to implement and exercise a Binance Spot
Testnet adapter using virtual funds. It does not prove a strategy has edge,
qualify the sandbox, authorize production, or authorize real-capital trading.

## Frozen Scope

- Venue: Binance Spot Testnet
- Product: spot only
- Symbol: BTCUSDT only
- Maximum effective leverage: 1x
- Simulated starting equity: USD 100
- Maximum modeled loss per trade: USD 0.50
- Maximum modeled daily loss: USD 1.00
- Maximum modeled total strategy loss: USD 10.00
- Market-data budget: USD 0
- Production account and real capital: excluded

The canonical capability artifact is:

`data/evidence/binance_spot_testnet_sandbox_profile_v1.json`

Its decision authorizes only:

- sandbox adapter implementation;
- successor strategy charter design;
- Binance Spot Testnet network requests; and
- virtual Testnet order entry.

The artifact explicitly does not authorize:

- declaring the sandbox qualified;
- treating Testnet results as alpha or profitability evidence;
- parameter selection or candidate promotion;
- forward-paper eligibility;
- production connectivity;
- live trading; or
- real-capital deployment.

## Verify The Frozen Boundary

From the Aurex repository root:

```powershell
.\.venv\Scripts\python.exe scripts\freeze_binance_spot_testnet_profile.py --check
```

The command must print `PASS`, show no failed gates, and continue to show
`sandbox_qualified=False` and `live=False`.

The same status is available from:

```text
GET /sandbox-profile/status
```

and in the dashboard's Operator view.

## Credential Rule

Never place an API key or secret in:

- source code;
- JSON evidence;
- screenshots;
- chat;
- tests;
- shell command arguments; or
- committed environment files.

The execution qualification phase must obtain credentials at runtime from
process environment variables or an interactive no-echo prompt. Aurex must
fail closed when either credential is absent and must never return credentials
through an API response, log record, exception, or evidence artifact.

## Phase Completion

Phase 1A is complete only when:

1. The canonical artifact independently verifies.
2. All nine capability gates pass.
3. The API reports `FROZEN_VERIFIED`.
4. The Operator view displays the exact sandbox and production boundaries.
5. Tests confirm that no sandbox profile path grants production or live authority.

## Next Phase

Phase 2 implements the Binance Spot Testnet adapter and proves, in order:

1. public endpoint reachability;
2. server-time synchronization;
3. `exchangeInfo` parsing and BTCUSDT filter enforcement;
4. authenticated account read without secret leakage;
5. signed test-order validation;
6. one tightly bounded virtual order lifecycle;
7. cancellation, fill, fee, balance, and reconciliation evidence;
8. idempotency and retry behavior; and
9. deterministic fail-closed risk controls.

Completing those checks may qualify the adapter mechanics. It still cannot
qualify a trading strategy or authorize production.
