# Aurex Assistant Integration

## Verified State - 2026-09-29

Aurex can be operated programmatically. It does not yet ship an Aurex MCP server
or an installed ChatGPT/Codex custom connector. These are different capabilities.

| Surface | Present | Boundary |
| --- | --- | --- |
| Python services and scripts | Yes | Usable by an authorized local agent with repository access. Commands may have side effects; inspection and execution are separate operations. |
| FastAPI management API | Yes | `src/aurex/api/app.py` registers the application routes and OpenAPI documentation. Not a secure public assistant endpoint. |
| Native signal intake | Yes | `SignalIntakeService.ingest_native` is a local service, not a native HTTP endpoint. Strategy, evidence and risk gates still apply. |
| TradingView webhook intake | Yes, implemented | Source-authenticated signal delivery is separate from assistant access. Genuine external delivery is not proven and is deferred on the $0 route. |
| Aurex MCP server / tool registration | No | No dedicated server implementation, MCP dependency or Aurex-specific tool in the inspected active tool inventory. |
| Autonomous native market runner | No | Intake, risk, closed-bar preflight and bounded SQLite atomic processing are components, not a continuous acquisition/evaluation/exit service. |
| Production trading permission | No | Neither API access nor future MCP access grants live approval or strategy qualification. |

The donor/research TradingView MCP project is not an Aurex MCP server and must not
become a production execution dependency. Access from this local coding task is
not automatic access from every ChatGPT conversation or another device.

## Security Findings

The main management app has no application-wide authentication dependency in
`src/aurex/api/app.py` or `src/aurex/api/dependencies.py`. Route-specific webhook
authentication does not protect unrelated management routes. Keep the main app
on a private local interface; do not publish it through a tunnel for convenience.

HTTP GET is not a sufficient read-only boundary. For example,
`src/aurex/api/routes/risk.py` commits after computing status, and
`StrategyPortfolioService.list_configs` calls `ensure_default_strategies`, which
can add or update records. An assistant reader must not simply proxy all GETs or
automatically expose the application's OpenAPI operations as tools.

Do not return raw settings, credentials, account identifiers, unfiltered logs or
arbitrary database rows. Notes, logs and external source text are untrusted data,
not instructions to change risk limits or run commands.

## Recommended First Connector - Not Implemented

Use a local STDIO MCP server with a small read-only tool allowlist. Codex supports
local STDIO and remote Streamable HTTP MCP connections; local STDIO does not need
public hosting. See [OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
This is a proposed implementation, not an installed connection or a remote-access
promise. A cloud ChatGPT connection requires its own supported access setup.

Initial tool scope: sanitized system status, strategy eligibility and blockers,
bounded paper-trade summaries, dataset/evidence integrity and readiness results.
Use fixed queries against enforced read-only storage, bounded pagination/timeouts,
output schemas and field allowlists. For SQLite, open the existing database with
`mode=ro` and query-only enforcement; never create a missing database or initialize
defaults. Other storage engines require a separately restricted database role.
Evidence readers must have fixed roots and validate paths and hashes. No arbitrary
SQL, shell, URL fetching or filesystem tool belongs in this connector.

Before enabling it, prove protocol negotiation and tool calls with the intended
client; assert database non-mutation, missing/schema-incompatible database errors,
secret redaction, bounded output, path traversal rejection and stale-evidence
reporting. Tool names and descriptions must distinguish source inspection,
synthetic tests, historical results and genuine forward observations.

No order submission, candidate enablement, kill-switch reset, risk-limit edits or
live approval tools in the initial connector. If write operations are later needed,
design them separately with explicit operator authorization, idempotency and audit
records; they may not bypass existing gates. The deterministic trading engine must
continue operating safely when the assistant is disconnected.

## Sequence

Continue the native closed-bar and restart-safe paper workflow in docs/10 first.
Keep the connector as a scoped operational follow-up, not another cloud-hosting
detour. No new subscription, public listener, credential or user action is needed
for the current local development. This document records an audit and proposed
scope only; it is not connector acceptance evidence.
