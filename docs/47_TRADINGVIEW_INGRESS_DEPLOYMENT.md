# TradingView Ingress Deployment

Updated: 2026-09-27. This is a delivery-mechanics campaign, not a trading deployment.
The full dashboard/API remains loopback-only. No public service has been started.

## Latest Resume Checkpoint - 2026-09-27

This section supersedes older hosting questions below. The operator confirmed a
free Vercel account, enabled TradingView 2FA, and authorized the non-trading
diagnostic. They signed in to Cloudflare themselves. Its Workers plans page now
shows Free as the current plan, including SQLite Durable Objects. No upgrade,
payment information, API credential, CLI authorization, or deployment was created
by the agent.

The actual TradingView alert dialog was inspected before deployment. Selecting
Webhook URL displayed an upgrade prompt naming the current plan Basic; webhook
notifications are not available on this account. The prompt was dismissed and
the unsaved alert canceled. No alert was created and no subscription was started.
2FA alone does not resolve this entitlement blocker.

Local work in progress, NOT deployment-ready: `deploy/tradingview-relay/` contains
a disabled-by-default single-message Worker, SQLite mailbox, and synthetic tests;
`src/aurex/signal_gateway/tradingview_relay.py` contains a separate signed-receipt
verifier with corresponding Python tests. Runtime/cross-language tests and review
remain outstanding. There is no collector CLI, local signal-ingestion adapter, or
accepted external proof. The direct-peer ingress and proof are unchanged. Do not
upload the full repo, arm the receiver, or claim this unfinished path is verified.

The initially selected older deployment toolchain reported four high-severity
dependency findings. The manifest was changed to current Wrangler 4.141.0 and its
matching Miniflare 5.20260925.0-alpha dependency. Installation completed and its npm
audit reported zero vulnerabilities; functional tests remain outstanding. The emulator's alpha suffix
is upstream's dependency choice, not a claim that Aurex uses a production-tested
relay. No `audit fix --force` or global Node update was performed.

The operator chose: "okay, lets keep the $0 route and continue". Pine webhooks,
relay development and deployment are now DEFERRED, not complete. Continue the
Aurex-native core checkpoint in `docs/10_PROJECT_CONTROL.md`. Do not ask for paid
access, start trials, deploy/arm a receiver, or resume hosting searches without a
new decision. Preserve the unfinished relay work as disabled WIP. Native intake
does not satisfy external-delivery or Pine parity gates. Strategy qualification
remains unresolved and live remains off.

## Completed Local Work

- `scripts/run_tradingview_ingress.py` checks configuration without opening a port.
  `--serve` refuses weak/default secrets, enabled live execution, unreviewed sender
  networks, unusable TLS files, and a missing or outdated local SQLite migration.
  The migration check opens SQLite read-only and never creates a missing database.
  Configuration checks do not import the DB-backed router; invalid settings and
  database URLs produce sanitized blocker codes, not import-time tracebacks.
- Its restricted app exposes only `POST /webhooks/tradingview`. Dashboard, OpenAPI,
  risk, live and other management routes are absent.
- The launcher disables Uvicorn proxy-header trust, including environment overrides,
  and access logging. Never put webhook credentials in process arguments or reports.
- Requests require direct HTTPS, a reviewed exact sender IP, and the dedicated
  secret. Forwarding headers are rejected on both restricted and ordinary webhooks.
- Only the frozen retired `trend_pullback_v1` 1.3.0 BTCUSDT 15m settings are accepted
  for this campaign. This reuses a known rejection path; it does not revive trend
  research or replace the user's strategy priorities. Lifecycle and live locks are
  rechecked per request. The normal risk engine still produces the rejection.
- Actual body bytes are capped at 16 KiB, including chunked requests. Body reception
  times out after two seconds. These bounds do not guarantee TradingView's total
  three-second delivery deadline; actual external receipt latency must be measured.
- Local fixtures exercise successful receipt, rejection, exact-body hashing,
  duplicate handling, spoofed proxy headers, oversized/slow bodies, disconnects,
  invalid secrets, wrong campaign scope, and absent execution side effects.
  Simulated sender addresses are test fixtures, never external proof.

## Observed Local State

At this checkpoint, the configured secret is still the development default. No TLS
certificate/key is configured. The read-only deployment check is BLOCKED for those
two reasons. The database revision `20260718_0029` matches Alembic head. A synthetic
preflight against the actual database, opened read-only, predicted HTTP 202 with
`RISK_REJECTED`, `would_execute_paper=false`, and no ledger mutation. It submitted
no webhook, order, or external request. Local probes found no listeners on 443,
8917 or 8918 at inspection time.

Report: `data/evidence/tradingview_ingress_local_preflight_20260926_v2.json`.
The earlier v1 report is preserved; it did not include the database migration check.
These are diagnostic snapshots, not immutable external-delivery proofs.

## Hosting Decision - 2026-09-26

This checkpoint supersedes the earlier request for a Google project display name.
The Cloud CLI has an active login but no selected project. A bounded read-only
lookup of accessible active projects returned five projects, all with the display
name `My First Project`. Each project's billing and enabled-service metadata was
read successfully:

| Check | Observed result |
| --- | --- |
| Billing enabled | False in all five projects |
| Compute Engine API enabled | False in all five projects |
| Cloud Run API enabled | False in all five projects |
| Cloud DNS API enabled | False in all five projects |
| BigQuery API enabled | True in all five projects |

Instance inventories were deliberately not requested where Compute was disabled.
These observations do not prove that no stopped or historical resources exist, or
that no other account has a suitable host. They establish that this inspection
found no ready hosting path in the accessible projects. The same display name is
not a safe way to select one. Do not ask the operator to repeat OAuth or guess a
project name, and do not enable billing or services to force progress.

All commands were metadata-only, with bounded timeouts. No project was selected,
service enabled, resource created, billing setting changed, or public listener
opened. Raw account/project identifiers and addresses were not printed or saved to
Aurex artifacts. Normal CLI credential-cache behavior was not independently audited.

Google documents that its general Free Tier requires an active billing account;
usage beyond the applicable limits can consume trial credit or incur charges on a
paid account. Merely having BigQuery sandbox access does not establish a usable
free HTTPS server. No Google hosting spend or billing activation is approved.

[Google Cloud Free Tier requirements](https://docs.cloud.google.com/free/docs/free-cloud-features)

### Decision Awaiting Operator

The proposed alternative is Cloudflare Workers Free for one diagnostic-only receipt
campaign. Its documented allowance is 100,000 requests per day with a 10 ms CPU
limit per request, and a `workers.dev` address avoids purchasing a domain. Account
eligibility, the actual plan, required storage, and whether the complete design fits
free limits must still be checked. Cloudflare describes `workers.dev` as a personal
or hobby route, not a business-critical production endpoint. This proposal is not
a trading deployment or a promise of zero-cost production hosting.

[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
[workers.dev scope](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)

The operator has been asked to choose this free diagnostic route, supply an existing
approved HTTPS server, or leave deployment paused. Signup/login and provider terms
remain operator actions. No Cloudflare account, service, subscription, or deployment
has been created. No relay code is represented as implemented or tested.

If the free relay is chosen, complete these bounded steps before external use:

1. Confirm Free plan limits and provider source-address semantics; stop if the
   required design needs a paid component or cannot establish trustworthy origin.
2. Specify a separate relay evidence contract. Preserve exact raw-body binding,
   authenticated relay provenance, freshness, replay protection, campaign scope,
   and operator alert-log reconciliation. A forwarding header alone is insufficient.
3. Implement and test that contract without changing the current direct-peer proof
   or its rejection of forwarded headers. Synthetic fixtures remain synthetic.
4. Deploy only the scoped receiver after account authority is confirmed. Keep the
   full Aurex API/dashboard private, exchange credentials local, and trading locked.
   Verify secrets, log redaction, expiry/stop behavior, and quota failures first.
5. Receive one genuine alert and reconcile it with Aurex's safe rejection and zero
   execution side effects. A receipt at the provider alone is not end-to-end proof.
   Freeze a separate passing relay proof only if all its declared gates pass.

There is no approved provider switch yet. The original direct-HTTPS sequence below
remains valid for an existing host; it must not be described as fulfilled by a relay.

### Vercel Assessment - 2026-09-26

The operator suggested Vercel as a familiar free alternative. It is a technically
plausible host for a small receiver: Vercel supports Python/FastAPI request handlers.
This is not approval to upload the full Aurex repository or deploy the existing
direct-TLS launcher unchanged. The restricted application expects a direct peer
and local SQLite; a managed receiver needs a separately verified origin model,
durable receipt handling, and an authenticated route back to local Aurex. A public
Vercel URL alone cannot reach the laptop's loopback API. No Vercel adapter exists
or has been tested as part of this campaign.

[Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
[Vercel request headers](https://vercel.com/docs/headers/request-headers)

The current fair-use guidance restricts Hobby to non-commercial personal use and
defines commercial deployments by financial-gain purpose. Given Aurex's stated
objective, do not assume Hobby eligibility, even for a preliminary diagnostic.
This is a conservative eligibility assessment, not a provider ruling on Aurex.
Obtain Vercel clarification if using Hobby; an existing Pro plan would still need
usage/budget review and deployment authority. Do not upgrade, start a paid trial,
or reclassify the project to bypass the restriction. The same guidance excludes
general-purpose proxies; any scoped webhook design must be reviewed on its actual
function, not merely renamed to avoid a policy question.

[Vercel fair-use guidance](https://vercel.com/docs/limits/fair-use-guidelines)

Next operator facts: existing Vercel plan (Hobby/Pro/unknown), TradingView webhook
option availability and 2FA status, and authority for one non-trading diagnostic
alert after the receiver is ready. Passwords, exchange keys, and account numbers
are not needed. Vercel remains an assessed option, not a selected deployment.

## Direct HTTPS Sequence

1. Identify an existing operator-approved hostname and server with direct IPv4
   ingress on HTTPS port 443. No paid infrastructure, domain purchase, cloud
   provisioning, firewall change or public tunnel is authorized by this document.
   The operator has been asked whether existing infrastructure is available.
2. Obtain a valid publicly trusted certificate for that hostname. Keep the private
   key outside the repository. Set `AUREX_INGRESS_TLS_CERTFILE` and
   `AUREX_INGRESS_TLS_KEYFILE` to local file paths in the receiving process.
   Local TLS loading alone does not verify hostname, expiry, trust or reachability.
3. Provision a dedicated cryptographically random webhook secret of at least 32
   characters in the receiver's environment and TradingView alert URL only. Never
   use exchange keys. Do not print, commit, or attach the resulting URL. Keep any
   hosting/access/error logs from retaining it. No secret was generated this session.
4. Run the deployment check and repeat the no-write candidate preflight on that
   deployment's migrated database. This launcher currently supports local SQLite;
   another database or a proxy requires explicit implementation and verification.
5. Recheck the official source list within 24 hours of the alert. Verify direct
   sender preservation, public certificate validity, routing, and source filtering.
   The checked list remains 52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7.
6. Only after endpoint setup and explicit account/workspace authority, create one
   bounded TradingView alert with 2FA and webhook access enabled. No alert was
   created or changed this session. Reconcile it before allowing another alert.
7. Preserve the sanitized genuine alert log. Verify one exact Aurex receipt, its
   body hash, rejection timeline, and zero paper/live/broker side effects using
   `docs/12_TRADINGVIEW_WEBHOOK_EVIDENCE.md`. Freeze only a passing genuine proof.
8. Continue with candidate-specific Pine parity and forward paper evidence only
   when an eligible candidate exists. Keep all capital and live locks intact.

## Launcher Interface

From the repository root, the read-only command is:

```powershell
.\.venv\Scripts\python.exe scripts/run_tradingview_ingress.py --check
```

`--output <new-report.json>` writes a credential-free report and refuses overwrite.
The optional serving mode is `--serve --host 127.0.0.1` (loopback default) or
`--serve --host 0.0.0.0` (all IPv4 interfaces); both use TLS on port 443. The latter
must wait for the approved deployment boundary. Use this launcher, not an ordinary
Uvicorn command that restores proxy trust or access logs. Do not use this listener
for strategy trading or point TradingView at the full management application.

## Official Requirements

TradingView still documents the four addresses above, ports 80/443 only, a
three-second timeout, no IPv6 webhook support, and 2FA for webhook alerts, as checked
on 2026-09-26. Aurex intentionally requires HTTPS 443.

[TradingView webhook configuration](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)

Passing this campaign proves delivery and safe rejection only. Qualified strategies
remain zero, live authority remains false, and demonstrated real net profit is $0.
