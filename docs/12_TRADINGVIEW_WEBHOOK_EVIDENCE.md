# Aurex TradingView Webhook Evidence

## Purpose

This contract defines what Aurex must preserve before Stage 3 can be called externally
proven. A payload that declares `source=tradingview` is not evidence that TradingView
sent it. Internal API tests prove software behavior only.

The external webhook is a signal-ingress path. It is never an exchange execution
adapter, and passing delivery verification never grants paper or live eligibility.

## Independent Verdicts

Aurex reports three separate verdicts:

- `delivery_verified`: the shared secret was validated, exact request-body evidence was
  preserved, and the direct peer matched a configured TradingView source network.
- `pipeline_verified`: the signal timeline, accepted-strategy provenance, risk approval,
  paper order, and paper trade all passed.
- `verified`: both delivery and pipeline verdicts passed for the same signal.

This separation is intentional. A real TradingView alert for an ineligible strategy
may produce `DELIVERY_VERIFIED_PIPELINE_BLOCKED`. That proves external delivery while
showing that Aurex protected capital and created no paper order.

An internal TestClient, curl, dashboard preflight, MCP call, or manually constructed
request may prove pipeline behavior but cannot prove TradingView origin.

## Immutable Delivery Receipt

The first `RECEIVED` signal event stores `metadata_json.webhook_delivery` with:

- authentication status and transport, without storing the secret;
- request method and path;
- content type;
- SHA-256 of the exact HTTP body and its byte length;
- direct peer IP;
- user agent;
- source-IP classification;
- canonical configured sender networks, their configuration-safety status, and their
  deterministic SHA-256;
- the official TradingView source-network authority URL;
- deterministic SHA-256 of the complete delivery snapshot.

Verification recomputes the receipt hash from the stored fields. Presence of a
hash-shaped string is insufficient; any metadata change blocks receipt integrity.

The default source networks are the four IPv4 senders rechecked against TradingView's
official page on September 26, 2026. They are configurable with
`AUREX_TRADINGVIEW_WEBHOOK_SOURCE_NETWORKS` as a comma-separated list of IPv4 or IPv6
CIDRs for classification, but external delivery proof accepts only exact `/32` IPv4
hosts present in Aurex's reviewed official-host snapshot. A broad CIDR can still
classify a peer as matched, but the independent verification result is blocked. The
operator must compare all configured values with TradingView's current official
documentation within 24 hours before each external proof run. TradingView currently
documents no IPv6 webhook support.

When Aurex sits behind a reverse proxy or tunnel, the direct peer is the proxy and
origin remains unproven. The webhook now rejects forwarding headers explicitly.
This is necessary because Uvicorn's ordinary defaults can rewrite the peer from
`X-Forwarded-For` before application code runs. The dedicated launcher disables
that middleware and access logging, which could otherwise expose query secrets.
There is no trusted-proxy proof path yet. Use the direct-TLS restricted listener in
`docs/47_TRADINGVIEW_INGRESS_DEPLOYMENT.md`, not a public tunnel to the full app.

## External Proof Procedure

1. Keep `AUREX_LIVE_TRADING_ENABLED=false` and the live execution adapter disabled.
2. Use a dedicated high-entropy `AUREX_WEBHOOK_SECRET`; never use exchange credentials.
3. Expose only the webhook endpoint through HTTPS on port 443. Restrict the network
   edge to TradingView's current published source addresses where practical.
4. Confirm the exact strategy, version, settings fingerprint, symbol, timeframe, and
   expected risk outcome with the no-write preflight endpoint.
5. Create one bounded TradingView alert only with explicit workspace authority.
6. Preserve the TradingView alert-log delivery entry and timestamp.
7. Query `/signals/tradingview-verification` for the same strategy and symbol.
8. Audit the delivery hash, body hash, direct peer, authentication, idempotency key,
   configured network snapshot, normalized payload, signal events, risk decision,
   paper objects, live order intents, broker orders, and broker fills.
9. Preserve a sanitized TradingView alert-log artifact showing the alert name,
   delivery timestamp, and webhook status. Do not include credentials or account
   numbers.
10. Run the external-proof CLI in preflight mode. It reads the verification snapshot
    directly from Aurex's configured database rather than trusting pasted JSON.
11. Freeze the proof only if every gate passes, then independently check the frozen
    artifact against the same database signal and alert-log file.
12. Send no further alerts until the first receipt is reconciled.

## Frozen External-Proof Package

The credential-free input template is printed with:

```text
python scripts/freeze_tradingview_external_delivery_proof.py --template
```

Preflight, freeze, and independent audit use:

```text
python scripts/freeze_tradingview_external_delivery_proof.py \
  --preflight --input <operator-input.json> --alert-log <sanitized-alert-log-file>

python scripts/freeze_tradingview_external_delivery_proof.py \
  --freeze --input <operator-input.json> --alert-log <sanitized-alert-log-file>

python scripts/freeze_tradingview_external_delivery_proof.py \
  --check --output data/evidence/tradingview_external_delivery_proof_v1.json \
  --alert-log <sanitized-alert-log-file>
```

The package can pass only for the frozen rejected `trend_pullback_v1` v1.3 signal
contract on `BTCUSDT` `15m`. It requires
`DELIVERY_VERIFIED_PIPELINE_BLOCKED`, `RISK_REJECTED`, the exact three-event safe
rejection timeline, no paper order or trade, live disabled with the execution adapter
disabled, no live order intent, no broker order or fill, an alert-log timestamp within
15 minutes of Aurex receipt, and an official source-network review no more than 24
hours old.

A passing package proves only one externally delivered alert and the intended safe
rejection. It does not prove the Pine strategy, pipeline eligibility, profitability,
paper readiness, sandbox readiness, live readiness, or permission to deploy capital.
The default output remains absent until genuine external evidence passes every gate.

For the rejected `trend_pullback_v1` v1.3 candidate, the expected safe outcome is an
authenticated and origin-matched delivery followed by `RISK_REJECTED`, with no paper
order and no paper trade. This run may prove Stage 3 delivery mechanics, but it cannot
promote the strategy or begin Stage 6.

## Acceptance Evidence

Stage 3 external delivery is proven only when all of the following exist for one real
TradingView alert:

- TradingView alert-log evidence;
- Aurex `delivery_verified=true`;
- exact body and delivery evidence hashes;
- source IP match against a freshly checked official list;
- authenticated request transport;
- complete signal and risk event timeline;
- the expected eligibility-safe outcome;
- no live order intent, broker order, fill, position, or balance mutation.

Synthetic tests of matching IP addresses verify classification logic only. They are
never accepted as operational Stage 3 evidence.

## Authoritative References

- TradingView webhook configuration and current sender IPs:
  `https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/`
- TradingView webhook client-certificate authentication:
  `https://www.tradingview.com/support/solutions/43000680459-webhook-authentication/`
