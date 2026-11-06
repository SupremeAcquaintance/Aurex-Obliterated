"""Restricted direct-TLS ingress for the retired-candidate delivery campaign."""

import asyncio

from fastapi import Depends, FastAPI, HTTPException
from starlette.datastructures import Headers, QueryParams
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from aurex.config.settings import Settings, get_settings
from aurex.signal_gateway.schemas import TradingViewSignalPayload
from aurex.signal_gateway.tradingview_delivery import (
    has_forwarding_headers,
    tradingview_origin_status,
    tradingview_source_network_snapshot,
)
from aurex.signal_gateway.tradingview_external_proof import (
    EXPECTED_SETTINGS_FINGERPRINT,
    EXPECTED_STRATEGY,
    EXPECTED_STRATEGY_VERSION,
    EXPECTED_SYMBOL,
    EXPECTED_TIMEFRAME,
)
from aurex.strategy_engine.registry import REGISTERED_STRATEGIES, StrategyLifecycleStatus

MAX_BODY_BYTES = 16 * 1024
BODY_TIMEOUT_SECONDS = 2


def ingress_configuration_blockers(settings: Settings) -> list[str]:
    blockers = []
    if settings.live_trading_enabled or settings.live_execution_adapter != "disabled":
        blockers.append("LIVE_EXECUTION_MUST_BE_DISABLED")
    secret = settings.webhook_secret
    if secret == "local-dev-secret" or len(secret) < 32 or secret != secret.strip():
        blockers.append("DEDICATED_HIGH_ENTROPY_WEBHOOK_SECRET_REQUIRED")
    networks = tradingview_source_network_snapshot(settings.tradingview_webhook_source_networks)
    if networks.configuration_status != "SOURCE_NETWORK_CONFIGURATION_DOCUMENTED_IPV4_HOSTS":
        blockers.append("REVIEWED_EXACT_SENDER_IPS_REQUIRED")
    definition = REGISTERED_STRATEGIES.get(EXPECTED_STRATEGY)
    if (
        definition is None
        or definition.version != EXPECTED_STRATEGY_VERSION
        or definition.lifecycle_status != StrategyLifecycleStatus.RETIRED
    ):
        blockers.append("SAFE_REJECTION_CANDIDATE_MUST_REMAIN_RETIRED")
    return blockers


def require_campaign_scope(payload: TradingViewSignalPayload) -> None:
    if (
        payload.strategy != EXPECTED_STRATEGY
        or payload.strategy_version != EXPECTED_STRATEGY_VERSION
        or payload.settings_fingerprint != EXPECTED_SETTINGS_FINGERPRINT
        or payload.symbol.upper() != EXPECTED_SYMBOL
        or payload.timeframe != EXPECTED_TIMEFRAME
    ):
        raise HTTPException(422, "Payload is outside the safe-rejection delivery campaign")


class DirectWebhookBoundary:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return

        async def reject(code: int, detail: str) -> None:
            await JSONResponse(
                {"detail": detail}, status_code=code, headers={"Cache-Control": "no-store"}
            )(scope, receive, send)

        if scope["path"] != "/webhooks/tradingview" or scope["method"] != "POST":
            await reject(404, "Not found")
            return
        if ingress_configuration_blockers(self.settings):
            await reject(503, "Safe-rejection ingress configuration is blocked")
            return
        headers = Headers(scope=scope)
        if scope.get("scheme") != "https" or has_forwarding_headers(headers):
            await reject(400, "Direct HTTPS without forwarding headers is required")
            return
        client = scope.get("client")
        networks = tradingview_source_network_snapshot(
            self.settings.tradingview_webhook_source_networks
        )
        if tradingview_origin_status(client[0] if client else None, networks) != (
            "TRADINGVIEW_SOURCE_IP_MATCHED"
        ):
            await reject(403, "Source is not an allowed direct sender")
            return
        query = QueryParams(scope.get("query_string", b""))
        from aurex.api.routes.webhooks import valid_webhook_secret

        if (
            len(query.getlist("secret")) > 1
            or len(headers.getlist("x-aurex-webhook-secret")) > 1
            or not valid_webhook_secret(
                self.settings.webhook_secret,
                headers.get("x-aurex-webhook-secret"),
                query.get("secret"),
            )
        ):
            await reject(401, "Invalid webhook secret")
            return
        if headers.get("content-type", "").split(";", 1)[0].strip().lower() != (
            "application/json"
        ):
            await reject(415, "JSON content is required")
            return

        # Bound actual received bytes, not the untrusted Content-Length header.
        body = bytearray()
        try:
            async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > MAX_BODY_BYTES:
                        await reject(413, "Webhook body exceeds the campaign limit")
                        return
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await reject(408, "Webhook body receive timeout")
            return

        delivered = False

        async def replay_body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay_body, send)


def create_webhook_ingress(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    blockers = ingress_configuration_blockers(settings)
    if blockers:
        raise ValueError("Webhook ingress blocked: " + ", ".join(blockers))
    # The DB-backed router must not load during the sanitized configuration check.
    from aurex.api.routes.webhooks import router

    app = FastAPI(
        title="Aurex safe-rejection webhook ingress",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(router, dependencies=[Depends(require_campaign_scope)])
    app.add_middleware(DirectWebhookBoundary, settings=settings)
    return app
